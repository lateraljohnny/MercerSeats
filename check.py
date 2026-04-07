import requests
from bs4 import BeautifulSoup
import time
import os

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

def notify(message):
    if not discordWebhook:
        print(f"No Webhook set. Message: {message}")
        return
    try:
        requests.post(discordWebhook, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Discord error: {e}")

def checkCourse(code, section):
    session = requests.Session()
    # Adding a realistic User-Agent is crucial for Mercer's server
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    try:
        # Step 1: Get the initial page to grab ViewState/EventValidation
        response = session.get(searchUrl, timeout=requestTimeout)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract all hidden ASP.NET fields
        payload = {
            inp.get('name'): inp.get('value', '') 
            for inp in soup.find_all('input', {'type': 'hidden'})
        }

        # Step 2: Set the search parameters
        # We find the name of the radio button for the term '2026-FA'
        term_name = "radTerm" # Default
        for radio in soup.find_all('input', {'type': 'radio'}):
            if '2026-FA' in str(radio.get('value')):
                term_name = radio.get('name')
                break

        payload.update({
            term_name: '2026-FA',
            'radLevel': 'U',
            'searchCourseCode': code,
            'searchCourseSection': section,
            'Button1': 'Submit'
        })

        # Step 3: Post the search
        res = session.post(searchUrl, data=payload, timeout=requestTimeout)
        if "no classes found" in res.text.lower():
            return 0
        
        # Step 4: Parse the results table
        results_soup = BeautifulSoup(res.text, 'html.parser')
        table = results_soup.find('table', {'id': 'dgCounts'})
        if not table:
            return None
            
        rows = table.find_all('tr')[1:] # Skip header
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10: continue
            
            # Clean up text for matching
            row_code = cols[1].text.strip().replace(" ", "").upper()
            target_code = code.replace(" ", "").upper()
            row_section = cols[3].text.strip()
            
            if target_code in row_code and section == row_section:
                try:
                    return int(cols[9].text.strip())
                except:
                    return None
        return None

    except Exception as e:
        print(f"Connection error for {code}: {e}")
        return False

if __name__ == "__main__":
    print(f"--- Starting Seat Check: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    for c in COURSES:
        seats = checkCourse(c['code'], c['section'])
        now = time.strftime("%I:%M %p")
        
        if isinstance(seats, int):
            status = f"OPEN ({seats} seats)" if seats > 0 else "FULL"
            print(f"[{now}] {c['code']} {c['section']}: {status}")
            if seats > 0:
                notify(f"🚨 **SEAT OPEN**: {seats} available in {c['code']} ({c['section']})")
        else:
            print(f"[{now}] {c['code']} {c['section']}: not found/error.")
            
    print("--- Check Complete ---")