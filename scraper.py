import requests
from bs4 import BeautifulSoup
import json
from datetime import date

BASE_URL = "http://103.52.36.11/Attendance"
USERNAME = "999"
PASSWORD = "vgnt"

FROM_DATE = "2026-08-01"
TO_DATE = date.today().strftime("%Y-%m-%d")

def scrape_attendance():
    print("Logging in to Vignan portal...")
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
    })
    
    # Login
    session.get(BASE_URL + "/index.html", timeout=20)
    session.post(BASE_URL + "/Validate.php", data={"uname": USERNAME, "pass": PASSWORD}, timeout=30)
    
    print(f"Fetching report from {FROM_DATE} to {TO_DATE}...")
    data = {
        "br": "BSH", 
        "yr": "1", 
        "sc": "CSM_D", 
        "fdt": FROM_DATE, 
        "tdt": TO_DATE, 
        "Submit": "VIEW REPORT"
    }
    
    # Request the report (this takes time)
    r = session.post(BASE_URL + "/Crprint.php", data=data, timeout=180)
    
    print("Parsing HTML data...")
    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    
    if not tables:
        print("Error: No table found in the response.")
        return []
    
    students_data = []
    
    # Loop through the table rows
    for i, row in enumerate(tables[0].find_all("tr")):
        if i >= 2: # Skip the two header rows
            cells = row.find_all(["th", "td"])
            values = [cell.get_text(" ", strip=True) for cell in cells]
            
            # Make sure the row has all 14 columns before grabbing data
            if values and len(values) >= 14:
                students_data.append({
                    "ht_no": values[1],
                    "total_classes": values[12],
                    "percentage": values[13]
                })
                
    return students_data

if __name__ == "__main__":
    data = scrape_attendance()
    
    if data:
        # Save the list of dictionaries as a JSON file
        with open("attendance.json", "w") as f:
            json.dump(data, f, indent=4)
        print(f"Success! Saved {len(data)} students to attendance.json")
    else:
        print("Failed to scrape data. JSON file not created.")
  
