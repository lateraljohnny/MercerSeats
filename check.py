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
    # ... (Headers and initial GET remain the same) ...

    try:
        # ... (POST request logic remains the same) ...
        r2 = session.post(searchUrl, data=data, timeout=20)
        
        if "no classes found" in r2.text.lower():
            return 0
            
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        table = soup2.find('table', {'id': 'dgCounts'})
        
        if not table:
            return "TABLE_MISSING"

        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cols) < 5: continue # Basic safety check
            
            # 1. Aggressive cleaning for matching
            # We look for the code (e.g., 'ACC204') inside the text of the first few columns
            row_content_all = "".join(cols).replace(" ", "").upper()
            target_code_clean = code.replace(" ", "").upper()
            
            # 2. Section check (usually column 3 or 4)
            # We iterate through columns to find one that exactly matches your section
            section_match = any(target_section.upper() == c.upper() for c in cols)

            if target_code_clean in row_content_all and section_match:
                # 3. Find the seats column
                # In dgCounts, seats is usually the LAST column or the 10th column (index 9)
                try:
                    return int(cols[-1]) # Try the very last column first
                except:
                    # Fallback: find the first column that looks like a standalone number
                    for col_text in reversed(cols):
                        if col_text.isdigit():
                            return int(col_text)
                    return "PARSE_ERR"
                    
        return "NOT_IN_TABLE"

    except Exception as e:
        return f"CONN_ERROR: {str(e)[:20]}"

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