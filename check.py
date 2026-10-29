import requests
from bs4 import BeautifulSoup
import time
import os

# ---------- CONFIGURATION ----------
discordWebhook = os.getenv("DISCORD_WEBHOOK")

COURSES = [
    {"code": "ACC 204", "section": "008"},
    {"code": "BIO 482", "section": "001"},
    {"code": "BIO 382", "section": "001"},
    {"code": "INT 301", "section": "009"}, 
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
        
        # Capture ALL hidden fields
        data = {i.get('name'): i.get('value', '') for i in soup.find_all('input', {'type': 'hidden'}) if i.get('name')}
        all_names = [i.get('name') for i in soup.find_all('input')]

        # 2. Map dynamic field names
        term_f = findName(all_names, ["radTerm"])
        lvl_f = findName(all_names, ["radLevel"])
        code_f = findName(all_names, ["searchCourseCode"])
        sect_f = findName(all_names, ["searchCourseSection"])
        btn_f = findName(all_names, ["Button1"])

        if not all([term_f, code_f, btn_f]):
            return "FIELD_MAP_ERROR"

        data.update({
            term_f: '2027-SP',
            lvl_f: 'U',
            code_f: code,
            sect_f: section,
            btn_f: 'Submit',
            '__EVENTTARGET': '',
            '__EVENTARGUMENT': ''
        })

        # 3. Perform Search
        r2 = session.post(searchUrl, data=data, timeout=20)
        
        if "no classes found" in r2.text.lower():
            return 0
            
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        table = soup2.find('table', {'id': 'dgCounts'})
        
        if not table:
            return "TABLE_MISSING"

        rows = table.find_all('tr')
        if not rows:
            return "TABLE_EMPTY"

        # Map headers to find the exact index of "Seats Available"
        headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
        avail_idx = -1
        for idx, h in enumerate(headers):
            if "avail" in h:
                avail_idx = idx
                break

        for row in rows[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all('td')]
            if len(cols) < 5: continue 
            
            row_content_all = "".join(cols).replace(" ", "").upper()
            target_code_clean = code.replace(" ", "").upper()
            target_section = section.strip().upper()
            
            section_match = any(target_section == c.upper() for c in cols)

            if target_code_clean in row_content_all and section_match:
                try:
                    # Use dynamically found index if available, otherwise fallback safely
                    if avail_idx != -1 and len(cols) > avail_idx and cols[avail_idx].isdigit():
                        return int(cols[avail_idx])
                    
                    # Fallback: if header wasn't found, pick the appropriate column index manually 
                    # (Adjust index [3] or [4] based on your table layout, avoiding the last column)
                    if len(cols) > 4 and cols[4].isdigit():
                        return int(cols[4])
                        
                    return "PARSE_ERR"
                except:
                    return "PARSE_ERR"
                    
        return "NOT_IN_TABLE"

    except Exception as e:
        return f"CONN_ERR: {str(e)[:15]}"

if __name__ == "__main__":
    print(f"--- Mercer Seat Check: {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
    
    for c in COURSES:
        seats = checkCourse(c['code'], c['section'])
        t = time.strftime("%I:%M %p")
        
        if isinstance(seats, int):
            status = f"OPEN ({seats} seats)" if seats > 0 else "FULL"
            print(f"[{t}] {c['code']} {c['section']}: {status}")
            if seats > 0:
                notify(f"**SEAT OPEN**: {seats} available in **{c['code']}** (Section {c['section']})")
        else:
            print(f"[{t}] {c['code']} {c['section']}: ERROR ({seats})")

    print("--- Check Finished ---")
