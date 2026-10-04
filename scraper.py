import requests
from bs4 import BeautifulSoup
import json
from datetime import date
from zoneinfo import ZoneInfo

BASE_URL = "http://103.52.36.11/Attendance"
USERNAME = "999"
PASSWORD = "vgnt"

FROM_DATE = "2026-08-01"

# Sections to fetch
SECTIONS = ["CSM_D", "CSM_A","ME","CE","EIE","CSE_A"]



# ============================================================
# INDIA DATE
# ============================================================

def get_india_date():
    """Return today's date in India."""

    india_now = datetime.now(
        ZoneInfo("Asia/Kolkata")
    )

    return india_now.strftime("%Y-%m-%d")


# ============================================================
# LOGIN
# ============================================================

def login(session):
    """Login to Vignan attendance portal."""

    print("Opening Vignan login page...")

    try:
        response = session.get(
            BASE_URL + "/index.html",
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR opening login page: {e}")
        return False

    print("Logging in to Vignan portal...")

    try:
        response = session.post(
            BASE_URL + "/Validate.php",
            data={
                "uname": USERNAME,
                "pass": PASSWORD
            },
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR during login: {e}")
        return False

    print("Login request completed.")

    return True


# ============================================================
# FETCH AND PARSE ONE SECTION
# ============================================================

def scrape_section(session, section, to_date):

    print()
    print("=" * 60)
    print(f"Fetching section: {section}")
    print(f"From: {FROM_DATE}")
    print(f"To  : {to_date}")
    print("=" * 60)

    report_data = {
        "br": "BSH",
        "yr": "1",
        "sc": section,
        "fdt": FROM_DATE,
        "tdt": to_date,
        "Submit": "VIEW REPORT"
    }

    # --------------------------------------------------------
    # Request report
    # --------------------------------------------------------

    try:

        response = session.post(
            BASE_URL + "/Crprint.php",
            data=report_data,
            timeout=180
        )

        response.raise_for_status()

    except requests.RequestException as e:

        print(
            f"ERROR fetching {section}: {e}"
        )

        return None

    # --------------------------------------------------------
    # Parse HTML
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    report_table = soup.find(
        "table",
        class_="report-table"
    )

    # Fallback if class is not available
    if report_table is None:

        tables = soup.find_all("table")

        if not tables:

            print(
                f"ERROR: No table found for {section}"
            )

            return None

        report_table = tables[0]

    rows = report_table.find_all("tr")

    if len(rows) < 3:

        print(
            f"ERROR: Not enough rows in {section} report"
        )

        return None

    # ========================================================
    # FIND TABLE HEADER
    # ========================================================

    headers = None

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        if not values:
            continue

        normalized = [
            value.upper().strip()
            for value in values
        ]

        has_ht = any(
            "H.T" in value
            for value in normalized
        )

        has_total = any(
            value == "TOTAL"
            for value in normalized
        )

        if has_ht and has_total:

            headers = values
            break

    if headers is None:

        print(
            f"ERROR: Could not find header "
            f"for {section}"
        )

        return None

    # --------------------------------------------------------
    # Locate important columns
    # --------------------------------------------------------

    ht_index = None
    total_index = None
    percentage_index = None

    for index, header in enumerate(headers):

        normalized = header.upper().strip()

        if (
            ht_index is None
            and "H.T" in normalized
        ):
            ht_index = index

        if normalized == "TOTAL":
            total_index = index

        if "PERCENTAGE" in normalized:
            percentage_index = index

    if (
        ht_index is None
        or total_index is None
        or percentage_index is None
    ):

        print(
            f"ERROR: Could not identify required "
            f"columns for {section}"
        )

        return None

    # ========================================================
    # SUBJECT NAMES
    # ========================================================

    # Everything between H.T No. and Total
    # is a subject column.

    subject_headers = headers[
        ht_index + 1:total_index
    ]

    subject_headers = [
        subject.strip()
        for subject in subject_headers
        if subject.strip()
    ]

    if not subject_headers:

        print(
            f"ERROR: No subjects detected "
            f"for {section}"
        )

        return None

    print()
    print("Subjects detected:")

    for subject in subject_headers:

        print(f"  {subject}")

    # ========================================================
    # FIND NUMBER OF HOURS CONDUCTED ROW
    # ========================================================

    hours_conducted = {}

    conducted_row_found = False

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        if not values:
            continue

        row_text = " ".join(
            values
        ).lower()

        if (
            "number of hours conducted"
            in row_text
        ):

            conducted_row_found = True

            # Because the label cell uses colspan="2",
            # the values are:
            #
            # [label, subject1, subject2, ...,
            #  total, percentage]

            if len(values) < (
                len(subject_headers) + 2
            ):

                print(
                    f"ERROR: Invalid conducted-hours "
                    f"row for {section}"
                )

                print(
                    "Conducted row:",
                    values
                )

                return None

            for index, subject in enumerate(
                subject_headers
            ):

                value_index = index + 1

                try:

                    hours_conducted[
                        subject
                    ] = int(
                        values[value_index]
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    print(
                        f"ERROR: Invalid conducted "
                        f"hours for {subject} "
                        f"in {section}"
                    )

                    return None

            break

    if not conducted_row_found:

        print(
            f"ERROR: 'Number of Hours Conducted' "
            f"row not found for {section}"
        )

        return None

    # ========================================================
    # TOTAL HOURS CONDUCTED
    # ========================================================

    try:

        total_conducted = sum(
            hours_conducted.values()
        )

    except Exception:

        total_conducted = 0

    print()
    print("Hours conducted:")

    for subject, hours in (
        hours_conducted.items()
    ):

        print(
            f"  {subject}: {hours}"
        )

    print(
        f"  Total: {total_conducted}"
    )

    # ========================================================
    # PARSE STUDENTS
    # ========================================================

    students = []

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        # Normal student row must contain
        # the same number of columns as the header.
        if len(values) < len(headers):
            continue

        # Skip conducted-hours row
        row_text = " ".join(
            values
        ).lower()

        if (
            "number of hours conducted"
            in row_text
        ):
            continue

        # ----------------------------------------------------
        # Get HT number
        # ----------------------------------------------------

        ht_no = values[
            ht_index
        ].strip()

        if not ht_no:
            continue

        # Don't accidentally parse another header row
        if "H.T" in ht_no.upper():
            continue

        # ----------------------------------------------------
        # Student object
        # ----------------------------------------------------

        student = {
            "sno": values[0],
            "ht_no": ht_no
        }

        # ----------------------------------------------------
        # Store actual subject names and raw values
        # ----------------------------------------------------

        for index, subject in enumerate(
            subject_headers
        ):

            value_index = (
                ht_index
                + 1
                + index
            )

            if value_index >= len(values):
                continue

            student[
                subject
            ] = values[
                value_index
            ]

        # ----------------------------------------------------
        # Total
        # ----------------------------------------------------

        student["total"] = values[
            total_index
        ]

        # ----------------------------------------------------
        # Overall percentage
        # ----------------------------------------------------

        student["percentage"] = values[
            percentage_index
        ]

        students.append(
            student
        )

    print()
    print(
        f"{section}: "
        f"{len(students)} students fetched."
    )

    # ========================================================
    # RETURN SECTION DATA
    # ========================================================

    return {
        "section": section,
        "branch": "BSH",
        "year": "1",
        "from_date": FROM_DATE,
        "to_date": to_date,

        "subjects": subject_headers,

        "hours_conducted": hours_conducted,

        "total_conducted": total_conducted,

        "students": students
    }


# ============================================================
# MAIN
# ============================================================

def scrape_attendance():

    to_date = get_india_date()

    print()
    print("=" * 60)
    print("VIGNAN ATTENDANCE SCRAPER")
    print("=" * 60)

    print(
        f"Sections: {', '.join(SECTIONS)}"
    )

    print(
        f"Date: {FROM_DATE} to {to_date}"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # Create session
    # --------------------------------------------------------

    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 "
            "Safari/537.36"
        )
    })

    # --------------------------------------------------------
    # Login once
    # --------------------------------------------------------

    if not login(session):

        print()
        print("LOGIN FAILED.")

        return False

    # --------------------------------------------------------
    # One combined JSON object
    # --------------------------------------------------------

    all_sections = {}

    successful = 0

    # --------------------------------------------------------
    # Fetch every section
    # --------------------------------------------------------

    for section in SECTIONS:

        section_data = scrape_section(
            session,
            section,
            to_date
        )

        if section_data is None:

            print()
            print(
                f"FAILED: {section}"
            )

            continue

        all_sections[
            section
        ] = section_data

        successful += 1

    # --------------------------------------------------------
    # Don't overwrite the existing file if everything failed
    # --------------------------------------------------------

    if not all_sections:

        print()
        print(
            "ERROR: No sections were successfully fetched."
        )

        print(
            "attendance.json was NOT replaced."
        )

        return False

    # --------------------------------------------------------
    # Save ONE JSON file
    # --------------------------------------------------------

    try:

        with open(
            "attendance.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                all_sections,
                f,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:

        print(
            f"ERROR saving attendance.json: {e}"
        )

        return False

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 60)

    print(
        "SUCCESS!"
    )

    print(
        f"Sections fetched: "
        f"{successful}/{len(SECTIONS)}"
    )

    print(
        "Created: attendance.json"
    )

    print("=" * 60)

    return True


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    success = scrape_attendance()

    if not success:

        raise SystemExit(1)
# ============================================================

def login(session):
    """Login to Vignan attendance portal."""

    print("Opening Vignan login page...")

    try:
        response = session.get(
            BASE_URL + "/index.html",
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR opening login page: {e}")
        return False

    print("Logging in to Vignan portal...")

    try:
        response = session.post(
            BASE_URL + "/Validate.php",
            data={
                "uname": USERNAME,
                "pass": PASSWORD
            },
            timeout=30
        )

        response.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR during login: {e}")
        return False

    print("Login request completed.")

    return True


# ============================================================
# FETCH AND PARSE ONE SECTION
# ============================================================

def scrape_section(session, section, to_date):

    print()
    print("=" * 60)
    print(f"Fetching section: {section}")
    print(f"From: {FROM_DATE}")
    print(f"To  : {to_date}")
    print("=" * 60)

    report_data = {
        "br": "BSH",
        "yr": "1",
        "sc": section,
        "fdt": FROM_DATE,
        "tdt": to_date,
        "Submit": "VIEW REPORT"
    }

    # --------------------------------------------------------
    # Request report
    # --------------------------------------------------------

    try:

        response = session.post(
            BASE_URL + "/Crprint.php",
            data=report_data,
            timeout=180
        )

        response.raise_for_status()

    except requests.RequestException as e:

        print(
            f"ERROR fetching {section}: {e}"
        )

        return None

    # --------------------------------------------------------
    # Parse HTML
    # --------------------------------------------------------

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    report_table = soup.find(
        "table",
        class_="report-table"
    )

    # Fallback if class is not available
    if report_table is None:

        tables = soup.find_all("table")

        if not tables:

            print(
                f"ERROR: No table found for {section}"
            )

            return None

        report_table = tables[0]

    rows = report_table.find_all("tr")

    if len(rows) < 3:

        print(
            f"ERROR: Not enough rows in {section} report"
        )

        return None

    # ========================================================
    # FIND TABLE HEADER
    # ========================================================

    headers = None

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        if not values:
            continue

        normalized = [
            value.upper().strip()
            for value in values
        ]

        has_ht = any(
            "H.T" in value
            for value in normalized
        )

        has_total = any(
            value == "TOTAL"
            for value in normalized
        )

        if has_ht and has_total:

            headers = values
            break

    if headers is None:

        print(
            f"ERROR: Could not find header "
            f"for {section}"
        )

        return None

    # --------------------------------------------------------
    # Locate important columns
    # --------------------------------------------------------

    ht_index = None
    total_index = None
    percentage_index = None

    for index, header in enumerate(headers):

        normalized = header.upper().strip()

        if (
            ht_index is None
            and "H.T" in normalized
        ):
            ht_index = index

        if normalized == "TOTAL":
            total_index = index

        if "PERCENTAGE" in normalized:
            percentage_index = index

    if (
        ht_index is None
        or total_index is None
        or percentage_index is None
    ):

        print(
            f"ERROR: Could not identify required "
            f"columns for {section}"
        )

        return None

    # ========================================================
    # SUBJECT NAMES
    # ========================================================

    # Everything between H.T No. and Total
    # is a subject column.

    subject_headers = headers[
        ht_index + 1:total_index
    ]

    subject_headers = [
        subject.strip()
        for subject in subject_headers
        if subject.strip()
    ]

    if not subject_headers:

        print(
            f"ERROR: No subjects detected "
            f"for {section}"
        )

        return None

    print()
    print("Subjects detected:")

    for subject in subject_headers:

        print(f"  {subject}")

    # ========================================================
    # FIND NUMBER OF HOURS CONDUCTED ROW
    # ========================================================

    hours_conducted = {}

    conducted_row_found = False

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        if not values:
            continue

        row_text = " ".join(
            values
        ).lower()

        if (
            "number of hours conducted"
            in row_text
        ):

            conducted_row_found = True

            # Because the label cell uses colspan="2",
            # the values are:
            #
            # [label, subject1, subject2, ...,
            #  total, percentage]

            if len(values) < (
                len(subject_headers) + 2
            ):

                print(
                    f"ERROR: Invalid conducted-hours "
                    f"row for {section}"
                )

                print(
                    "Conducted row:",
                    values
                )

                return None

            for index, subject in enumerate(
                subject_headers
            ):

                value_index = index + 1

                try:

                    hours_conducted[
                        subject
                    ] = int(
                        values[value_index]
                    )

                except (
                    ValueError,
                    IndexError
                ):

                    print(
                        f"ERROR: Invalid conducted "
                        f"hours for {subject} "
                        f"in {section}"
                    )

                    return None

            break

    if not conducted_row_found:

        print(
            f"ERROR: 'Number of Hours Conducted' "
            f"row not found for {section}"
        )

        return None

    # ========================================================
    # TOTAL HOURS CONDUCTED
    # ========================================================

    try:

        total_conducted = sum(
            hours_conducted.values()
        )

    except Exception:

        total_conducted = 0

    print()
    print("Hours conducted:")

    for subject, hours in (
        hours_conducted.items()
    ):

        print(
            f"  {subject}: {hours}"
        )

    print(
        f"  Total: {total_conducted}"
    )

    # ========================================================
    # PARSE STUDENTS
    # ========================================================

    students = []

    for row in rows:

        cells = row.find_all(
            ["th", "td"]
        )

        values = [
            cell.get_text(
                " ",
                strip=True
            )
            for cell in cells
        ]

        # Normal student row must contain
        # the same number of columns as the header.
        if len(values) < len(headers):
            continue

        # Skip conducted-hours row
        row_text = " ".join(
            values
        ).lower()

        if (
            "number of hours conducted"
            in row_text
        ):
            continue

        # ----------------------------------------------------
        # Get HT number
        # ----------------------------------------------------

        ht_no = values[
            ht_index
        ].strip()

        if not ht_no:
            continue

        # Don't accidentally parse another header row
        if "H.T" in ht_no.upper():
            continue

        # ----------------------------------------------------
        # Student object
        # ----------------------------------------------------

        student = {
            "sno": values[0],
            "ht_no": ht_no
        }

        # ----------------------------------------------------
        # Store actual subject names and raw values
        # ----------------------------------------------------

        for index, subject in enumerate(
            subject_headers
        ):

            value_index = (
                ht_index
                + 1
                + index
            )

            if value_index >= len(values):
                continue

            student[
                subject
            ] = values[
                value_index
            ]

        # ----------------------------------------------------
        # Total
        # ----------------------------------------------------

        student["total"] = values[
            total_index
        ]

        # ----------------------------------------------------
        # Overall percentage
        # ----------------------------------------------------

        student["percentage"] = values[
            percentage_index
        ]

        students.append(
            student
        )

    print()
    print(
        f"{section}: "
        f"{len(students)} students fetched."
    )

    # ========================================================
    # RETURN SECTION DATA
    # ========================================================

    return {
        "section": section,
        "branch": "BSH",
        "year": "1",
        "from_date": FROM_DATE,
        "to_date": to_date,

        "subjects": subject_headers,

        "hours_conducted": hours_conducted,

        "total_conducted": total_conducted,

        "students": students
    }


# ============================================================
# MAIN
# ============================================================

def scrape_attendance():

    to_date = get_india_date()

    print()
    print("=" * 60)
    print("VIGNAN ATTENDANCE SCRAPER")
    print("=" * 60)

    print(
        f"Sections: {', '.join(SECTIONS)}"
    )

    print(
        f"Date: {FROM_DATE} to {to_date}"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # Create session
    # --------------------------------------------------------

    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 "
            "Safari/537.36"
        )
    })

    # --------------------------------------------------------
    # Login once
    # --------------------------------------------------------

    if not login(session):

        print()
        print("LOGIN FAILED.")

        return False

    # --------------------------------------------------------
    # One combined JSON object
    # --------------------------------------------------------

    all_sections = {}

    successful = 0

    # --------------------------------------------------------
    # Fetch every section
    # --------------------------------------------------------

    for section in SECTIONS:

        section_data = scrape_section(
            session,
            section,
            to_date
        )

        if section_data is None:

            print()
            print(
                f"FAILED: {section}"
            )

            continue

        all_sections[
            section
        ] = section_data

        successful += 1

    # --------------------------------------------------------
    # Don't overwrite the existing file if everything failed
    # --------------------------------------------------------

    if not all_sections:

        print()
        print(
            "ERROR: No sections were successfully fetched."
        )

        print(
            "attendance.json was NOT replaced."
        )

        return False

    # --------------------------------------------------------
    # Save ONE JSON file
    # --------------------------------------------------------

    try:

        with open(
            "attendance.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                all_sections,
                f,
                indent=4,
                ensure_ascii=False
            )

    except OSError as e:

        print(
            f"ERROR saving attendance.json: {e}"
        )

        return False

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    print()
    print("=" * 60)

    print(
        "SUCCESS!"
    )

    print(
        f"Sections fetched: "
        f"{successful}/{len(SECTIONS)}"
    )

    print(
        "Created: attendance.json"
    )

    print("=" * 60)

    return True


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    success = scrape_attendance()

    if not success:

        raise SystemExit(1)

    try:
        response = session.post(
            BASE_URL + "/Crprint.php",
            data=data,
            timeout=180
        )

        response.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR fetching {section}: {e}")
        return []

    print(f"Parsing {section} HTML...")

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")

    if not tables:
        print(f"ERROR: No table found for {section}")
        return []

    students_data = []

    rows = tables[0].find_all("tr")

    for i, row in enumerate(rows):

        # Skip header rows
        if i < 2:
            continue

        cells = row.find_all(["th", "td"])
        values = [cell.get_text(" ", strip=True) for cell in cells]

        # Expected columns:
        # S.No.
        # H.T No.
        # M&C
        # AEP
        # EDC
        # BEE
        # PPS
        # AEP LAB
        # PPS LAB
        # EW
        # BEE LAB
        # CRT
        # Total
        # Percentage

        if len(values) >= 14:

            student = {
                "ht_no": values[1],
                "m_c": values[2],
                "aep": values[3],
                "edc": values[4],
                "bee": values[5],
                "pps": values[6],
                "aep_lab": values[7],
                "pps_lab": values[8],
                "ew": values[9],
                "bee_lab": values[10],
                "crt": values[11],
                "total_classes": values[12],
                "percentage": values[13]
            }

            students_data.append(student)

    print(f"{section}: {len(students_data)} students fetched.")

    return students_data


def scrape_attendance():

    print("Logging in to Vignan portal...")

    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    })

    # Open login page first to establish session/cookies
    try:
        login_page = session.get(
            BASE_URL + "/index.html",
            timeout=30
        )

        login_page.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR opening login page: {e}")
        return []

    # Login
    try:
        login_response = session.post(
            BASE_URL + "/Validate.php",
            data={
                "uname": USERNAME,
                "pass": PASSWORD
            },
            timeout=30
        )

        login_response.raise_for_status()

    except requests.RequestException as e:
        print(f"ERROR during login: {e}")
        return []

    print("Login request completed.")

    # ---------------------------------------------------------
    # Fetch BOTH sections into ONE single list.
    #
    # IMPORTANT:
    # We do NOT add a "section" field.
    # We do NOT create separate JSON objects.
    # We simply append CSM_D and CSM_A students together.
    # ---------------------------------------------------------

    all_students = []

    for section in SECTIONS:

        section_students = scrape_section(
            session,
            section
        )

        all_students.extend(section_students)

    return all_students


if __name__ == "__main__":

    data = scrape_attendance()

    if data:

        with open(
            "attendance.json",
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=4,
                ensure_ascii=False
            )

        print()
        print("----------------------------------------")
        print(f"SUCCESS! Saved {len(data)} students.")
        print("----------------------------------------")

    else:

        print()
        print("----------------------------------------")
        print("ERROR: No attendance data was fetched.")
        print("attendance.json was NOT replaced.")
        print("----------------------------------------")
