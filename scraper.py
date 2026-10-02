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
SECTIONS = ["CSM_D", "CSM_A"]


def get_india_date():
    """Get today's date in India."""
    return date.today().strftime("%Y-%m-%d")


def scrape_section(session, section):
    """Fetch and parse attendance for one section."""

    to_date = get_india_date()

    print(f"Fetching {section} from {FROM_DATE} to {to_date}...")

    data = {
        "br": "BSH",
        "yr": "1",
        "sc": section,
        "fdt": FROM_DATE,
        "tdt": to_date,
        "Submit": "VIEW REPORT"
    }

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
