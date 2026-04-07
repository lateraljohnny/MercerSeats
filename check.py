import requests
from bs4 import BeautifulSoup
import time
import re
import sys
import os

# ---------- SETTINGS ----------
# Pulls from GitHub Secrets for security
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

# ---------- FUNCTIONS ----------

def notify(message):
    if not discordWebhook:
        print(f"Notification (No Webhook): {message}")
        return
    try:
        requests.post(discordWebhook, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")

def parseSeatsFromTable(soup, code, section):
    table = soup.find('table', {'id': 'dgCounts'})
    if not table:
        return None
    
    rows = table.find_all('tr')
    for row in rows[1:]:  # Skip header
        cols = row.find_all('td')
        if len(cols) < 5: continue
        
        row_text = row.get_text(separator=" ").upper()
        clean_code = code.upper().replace(" ", "")
        
        if clean_code in row_text.replace(" ", "") and section.upper() in row_text:
            try:
                # Typically the 5th or 6th column contains 'Available' seats
                seats_str = cols[4].get_text(strip=True)
                return int(seats_str)
            except:
                continue
    return None

def checkCourse(code, section):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": searchUrl
    })

    try:
        r = session.get(searchUrl, timeout=requestTimeout)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Collect ASP.NET Hidden Fields
        data = {inp.get('name'): inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'}) if inp.get('name')}
        
        # Determine Term field name (radTerm)
        term_field = 'radTerm'
        for inp in soup.find_all('input', {'type': 'radio'}):
            if '2026' in inp.get('value', '') and 'FA' in inp.get('value', ''):
                term_field = inp.get('name')
                break

        # Setup POST Data
        data.update({
            term_field: '2026-FA',
            'radLevel': 'U',
            'searchCourseCode': code,
            'searchCourseSection': section,
            'Button1': 'Submit' 
        })

        r2 = session.post(searchUrl, data=data, timeout=requestTimeout)
        
        if "no classes found" in r2.text.lower():
            return 0
        
        return parseSeatsFromTable(BeautifulSoup(r2.text, 'html.parser'), code, section)

    except Exception as e:
        print(f"Error checking {code}: {e}")
        return False

# ---------- MAIN EXECUTION ----------

if __name__ == "__main__":
    print(f"--- Starting Seat Check: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    if not discordWebhook:
        print("WARNING: DISCORD_WEBHOOK environment variable not found.")

    for c in COURSES:
        seats = checkCourse(c['code'], c['section'])
        timestamp = time.strftime("%I:%M %p")
        
        if isinstance(seats, int):
            if seats > 0:
                msg = f"🟢 SEAT OPEN: {seats} available in {c['code']} section {c['section']}"
                print(f"[{timestamp}] {msg}")
                notify(f"{msg} (Checked at {timestamp})")
            else:
                print(f"[{timestamp}] {c['code']} {c['section']} is FULL.")
        else:
            print(f"[{timestamp}] {c['code']} {c['section']} not found/error.")
    
    print("--- Check Complete ---")