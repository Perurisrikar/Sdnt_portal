import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime, timezone, timedelta


BASE_URL = "http://103.52.36.11/Attendance"
USERNAME = "999"
PASSWORD = "vgnt"

FROM_DATE = "2026-08-01"

# Sections to fetch
SECTIONS = ["CSM_A", "CSM_B", "CSM_C", "CSM_D", "CSM_E","ME","CE","EIE","CSE_A", "CSE_B", "CSE_C", "CSE_D","EEE","CSE_E"]

# ============================================================
# INDIA DATE
# ============================================================

def get_india_date():
    """
    Return today's date in India.

    Uses UTC + 5:30 directly so this does not require
    the tzdata package.
    """

    india_time = (
        datetime.now(timezone.utc)
        + timedelta(hours=5, minutes=30)
    )

    return india_time.strftime("%Y-%m-%d")


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

    # ========================================================
    # LOCATE IMPORTANT COLUMNS
    # ========================================================

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

        print(
            "Detected headers:",
            headers
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

    conducted_total = None

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
            # values are:
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

            # ------------------------------------------------
            # Subject conducted hours
            # ------------------------------------------------

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

            # ------------------------------------------------
            # Actual total conducted from report
            # ------------------------------------------------

            conducted_total_index = (
                total_index - ht_index
            )

            try:

                conducted_total = int(
                    values[conducted_total_index]
                )

            except (
                ValueError,
                IndexError
            ):

                # Fallback to sum of subjects
                conducted_total = sum(
                    hours_conducted.values()
                )

            break

    if not conducted_row_found:

        print(
            f"ERROR: 'Number of Hours Conducted' "
            f"row not found for {section}"
        )

        return None

    if conducted_total is None:

        conducted_total = sum(
            hours_conducted.values()
        )

    # ========================================================
    # DISPLAY CONDUCTED HOURS
    # ========================================================

    print()
    print("Hours conducted:")

    for subject, hours in (
        hours_conducted.items()
    ):

        print(
            f"  {subject}: {hours}"
        )

    print(
        f"  Total: {conducted_total}"
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

        # Student row must contain enough columns.
        if len(values) < len(headers):
            continue

        # ----------------------------------------------------
        # Skip conducted-hours row
        # ----------------------------------------------------

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

        # Don't accidentally parse another header row.
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
        "total_conducted": conducted_total,
        "students": students
    }


# ============================================================
# MAIN SCRAPER
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
    # Don't overwrite existing file if everything failed
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
