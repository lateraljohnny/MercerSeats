import requests
from bs4 import BeautifulSoup
import time
import os
import sys

# ---------- SETTINGS ----------
discordWebhook = os.getenv("DISCORD_WEBHOOK")

COURSES = [
    {"code": "ACC 204", "section": "001"},
    {"code": "PHY 162", "section": "001"},
    {"code": "PHY 162", "section": "002"},
    {"code": "EGR 232", "section": "003"},
    {"code": "MAT 330", "section": "004"},
    {"code": "EGR 244", "section": "004"},
    {"code": "EGR 251", "section": "0W1"},
    {"code": "HID 364", "section": "001"},
]

searchUrl = "https://adminapps.mercer.edu/classroomsched/default.aspx?C=M"
requestTimeout = 20

# ---------- HELPERS (From testseat.py) ----------

def findName(names, substrings):
    for s in substrings:
        for n in names:
            if n and s.lower() in n.lower():
                return n
    return None

def notify(message):
    if not discordWebhook:
        print(f"Notification (No Webhook): {message}")
        return
    try:
        requests.post(discordWebhook, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

def checkCourse(code, section):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    try:
        # Step 1: Initial Page Load
        r = session.get(searchUrl, timeout=requestTimeout)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Get all inputs
        inputs = soup.find_all('input')
        input_names = [i.get('name') for i in inputs]
        
        # Capture ASP.NET hidden fields
        data = {i.get('name'): i.get('value', '') for i in inputs if i.get('type') == 'hidden'}

        # Step 2: Match field names using testseat's findName logic
        term_field = findName(input_names, ["radTerm", "term"])
        level_field = findName(input_names, ["radLevel", "level"])
        code_field = findName(input_names, ["searchCourseCode", "txtCourseCode"])
        sect_field = findName(input_names, ["searchCourseSection", "txtSection"])
        btn_field = findName(input_names, ["Button1", "btnSubmit", "Submit"])

        if not all([term_field, code_field, btn_field]):
            return None

        # Step 3: Build Payload
        data.update({
            term_field: '2026-FA',
            level_field: 'U',
            code_field: code,
            sect_field: section,
            btn_field: 'Submit'
        })

        # Step 4: Submit Search
        r2 = session.post(searchUrl, data=data, timeout=requestTimeout)
        
        if "no classes found" in r2.text.lower():
            return 0
            
        # Step 5: Parse Table
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        table = soup2.find('table', {'id': 'dgCounts'})
        if not table:
            return None

        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10: continue
            
            row_code = cols[1].text.strip().replace(" ", "").upper()
            row_sect = cols[3].text.strip()
            
            if code.replace(" ", "").upper() in row_code and section == row_sect:
                try:
                    return int(cols[9].text.strip())
                except:
                    return None
        return None

    except Exception as e:
        print(f"Error: {e}")
        return False

# ---------- EXECUTION ----------

if __name__ == "__main__":
    print(f"--- Starting Seat Check: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    for c in COURSES:
        seats = checkCourse(c['code'], c['section'])
        timestamp = time.strftime("%I:%M %p")
        
        if isinstance(seats, int):
            status = f"OPEN ({seats} seats)" if seats > 0 else "FULL"
            print(f"[{timestamp}] {c['code']} {c['section']}: {status}")
            if seats > 0:
                notify(f"🟢 **SEAT OPEN**: {seats} available in {c['code']} section {c['section']}")
        else:
            print(f"[{timestamp}] {c['code']} {c['section']}: not found/error.")
            
    print("--- Check Complete ---")