import requests
from bs4 import BeautifulSoup
import time
import os

# ---------- CONFIGURATION ----------
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

def findName(names, substrings):
    for s in substrings:
        for n in names:
            if n and s.lower() in n.lower():
                return n
    return None

def notify(message):
    if not discordWebhook:
        print(f"DEBUG: No Webhook. Message: {message}")
        return
    try:
        requests.post(discordWebhook, json={"content": message}, timeout=10)
    except Exception as e:
        print(f"Discord Error: {e}")

def checkCourse(code, section):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": searchUrl
    })

    try:
        # 1. Initial Load to get tokens
        r = session.get(searchUrl, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Capture ALL hidden fields (ViewState, EventValidation, etc.)
        data = {i.get('name'): i.get('value', '') for i in soup.find_all('input', {'type': 'hidden'}) if i.get('name')}
        
        # Get all input names for dynamic mapping
        all_names = [i.get('name') for i in soup.find_all('input')]

        # 2. Map the dynamic field names
        term_f = findName(all_names, ["radTerm"])
        lvl_f = findName(all_names, ["radLevel"])
        code_f = findName(all_names, ["searchCourseCode"])
        sect_f = findName(all_names, ["searchCourseSection"])
        btn_f = findName(all_names, ["Button1"])

        if not all([term_f, code_f, btn_f]):
            return "FIELD_MAP_ERROR"

        # 3. Build Post Data
        data.update({
            term_f: '2026-FA',
            lvl_f: 'U',
            code_f: code,
            sect_f: section,
            btn_f: 'Submit',
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': ''
        })

        # 4. Perform Search
        r2 = session.post(searchUrl, data=data, timeout=20)
        
        if "no classes found" in r2.text.lower():
            return 0
            
        # 5. Parse Results Table
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        table = soup2.find('table', {'id': 'dgCounts'})
        
        if not table:
            # This is where your current error triggers. 
            # If the table is missing, the search didn't fire.
            return None

        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 10: continue
            
            row_code_clean = cols[1].text.strip().replace(" ", "").upper()
            target_code_clean = code.replace(" ", "").upper()
            row_sect_clean = cols[3].text.strip().upper()
            target_sect_clean = section.strip().upper()

            if target_code_clean in row_code_clean and target_sect_clean == row_sect_clean:
                try:
                    return int(cols[9].text.strip())
                except:
                    return "PARSE_ERR"
        return "NOT_IN_TABLE"

    except Exception as e:
        print(f"Request Error: {e}")
        return "CONN_ERROR"

if __name__ == "__main__":
    print(f"--- Mercer Seat Check: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    for c in COURSES:
        seats = checkCourse(c['code'], c['section'])
        t = time.strftime("%I:%M %p")
        
        if isinstance(seats, int):
            status = f"OPEN ({seats} seats)" if seats > 0 else "FULL"
            print(f"[{t}] {c['code']} {c['section']}: {status}")
            if seats > 0:
                notify(f"🟢 **SEAT OPEN**: {seats} available in **{c['code']}** (Section {c['section']})")
        else:
            print(f"[{t}] {c['code']} {c['section']}: ERROR ({seats})")

    print("--- Check Finished ---")