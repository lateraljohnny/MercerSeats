import requests
from bs4 import BeautifulSoup
import time
import re

#SETTINGS
DISCORD_WEBHOOK = "https://discordapp.com/api/webhooks/1435337474422476973/_by6UEO_E2cPYWiZSVNitR2hd3dgEzs8Jc1E-Rt5xPO5BJD7Hc9X-eMMs1KWxZE0EiPJ"
COURSES = [
    {"code": "MAT 192", "section": "007"},
    {"code": "MAT 192", "section": "008"},
    {"code": "PHY 161", "section": "004"},
    {"code": "PHY 161", "section": "005"},
    {"code": "TCO 141", "section": "003"},
    {"code": "REL 110", "section": "001"},
    {"code": "REL 110", "section": "002"},    
]
CHECK_INTERVAL = 300 #5MINS
SEARCH_URL = "https://adminapps.mercer.edu/classroomsched/default.aspx?C=M"
REQUEST_TIMEOUT = 15

def find_name(names, substrings):
    for s in substrings:
        for n in names:
            if n and s.lower() in n.lower():
                return n
    return None

def notif(msg):
    try:
        r = requests.post(DISCORD_WEBHOOK, json={"content": msg}, timeout=REQUEST_TIMEOUT)
        if 200 <= r.status_code < 300:
            print("✅ Sent alert to Discord.")
        else:
            print(f"⚠️ Discord webhook returned HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print("⚠️ Failed to send alert to Discord:", e)

def _parse_seats_from_table(soup, target_code, target_section):
    #look for header containing 'course' and '# seats')
    tables = soup.find_all('table')
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if not headers:
            first_row = table.find('tr')
            if first_row:
                headers = [td.get_text(strip=True).lower() for td in first_row.find_all(['th', 'td'])]
        if any('course' in h for h in headers) and any('# seats' in h or 'seats available' in h or 'seats' == h for h in headers):
            course_idx = next((i for i, h in enumerate(headers) if 'course' in h), None)
            section_idx = next((i for i, h in enumerate(headers) if 'section' in h), None)
            seats_idx = next((i for i, h in enumerate(headers) if '# seats' in h or 'seats available' in h or h == 'seats'), None)
            rows = table.find_all('tr')
            for row in rows[1:]:
                cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if not cols:
                    continue
                sec_text = cols[section_idx].strip() if section_idx is not None and section_idx < len(cols) else ''
                course_text = cols[course_idx].strip() if course_idx is not None and course_idx < len(cols) else ''
                if sec_text.endswith(target_section) or sec_text == target_section:
                    if seats_idx is not None and seats_idx < len(cols):
                        seats_text = cols[seats_idx]
                        m = re.search(r"(\d+)", seats_text)
                        if m:
                            return int(m.group(1))
                        else:
                            return 0
                        

                if target_section in ' '.join(cols) and target_code.lower() in course_text.lower():
                    if seats_idx is not None and seats_idx < len(cols):
                        m = re.search(r"(\d+)", cols[seats_idx])
                        if m:
                            return int(m.group(1))
                        else:
                            return 0
    return None

def check_course(code, section):
    """Submit the search form and parse the results table for seats available in the given section."""
    session = requests.Session()
    try:
        r = session.get(SEARCH_URL, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            print(f"⚠️ GET {SEARCH_URL} returned {r.status_code}")
            return False
    except Exception as e:
        print("⚠️ Error fetching search page:", e)
        return False

    soup = BeautifulSoup(r.text, 'html.parser')

    hidden_inputs = {inp.get('name'): inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'}) if inp.get('name')}
    names = set([tag.get('name') for tag in soup.find_all(['input', 'select', 'textarea']) if tag.get('name')])

    # Heuristics to find field names used by the form
    campus_name = find_name(names, ['ddlCampus', 'ddlcampus', 'ddl_Campus', 'campus'])
    term_name = find_name(names, ['rblTerm', 'rblterm', 'term', 'ddlTerm'])
    level_name = find_name(names, ['rblLevel', 'rbllevel', 'level'])
    code_name = find_name(names, ['txtCourseCode', 'txtCourse', 'txtCourseCode$', 'coursecode'])
    section_name = find_name(names, ['txtCourseSection', 'txtCourseSection$', 'txtSection', 'section'])
    submit_name = find_name(names, ['btnSubmit', 'submit', 'ctl00$'])
    data = hidden_inputs.copy()

    if campus_name:
        sel = soup.find(attrs={'name': campus_name})
        val = 'Macon Campus'
        if sel and sel.name == 'select':
            opt = next((o for o in sel.find_all('option') if 'macon' in o.get_text(strip=True).lower()), None)
            if opt and opt.get('value') is not None:
                val = opt.get('value')
        data[campus_name] = val

    if term_name:
        val = None
        elems = soup.find_all(attrs={'name': term_name})
        for e in elems:
            v = e.get('value', '')
            if 'spring' in v.lower() or '2026' in v:
                val = v
                break
            if e.name == 'select':
                opt = next((o for o in e.find_all('option') if 'spring' in o.get_text(strip=True).lower() or '2026' in o.get_text(strip=True)), None)
                if opt:
                    val = opt.get('value')
                    break
        if val is None and elems:
            val = elems[0].get('value', '')
        if val is not None:
            data[term_name] = val

    if level_name:
        val = None
        elems = soup.find_all(attrs={'name': level_name})
        for e in elems:
            v = e.get('value', '')
            if 'undergrad' in v.lower() or 'undergraduate' in v.lower():
                val = v
                break
            if e.name == 'select':
                opt = next((o for o in e.find_all('option') if 'undergrad' in o.get_text(strip=True).lower() or 'undergraduate' in o.get_text(strip=True)), None)
                if opt:
                    val = opt.get('value')
                    break
        if val is None and elems:
            val = elems[0].get('value', '')
        if val is not None:
            data[level_name] = val

    #course code and section input
    if code_name:
        data[code_name] = code
    if section_name:
        data[section_name] = section
    if submit_name and submit_name not in data:
        data[submit_name] = 'Submit'

    try:
        r2 = session.post(SEARCH_URL, data=data, timeout=REQUEST_TIMEOUT)
        if r2.status_code != 200:
            print(f"returned HTTP {r2.status_code}")
            return False
    except Exception as e:
        print("error submitting search form:", e)
        return False
    soup2 = BeautifulSoup(r2.text, 'html.parser')
    seats = _parse_seats_from_table(soup2, code, section)
    if seats is None:
        text = soup2.get_text(' ', strip=True).lower()
        is_open = 'open' in text and 'full' not in text
        return is_open
    
    return seats


def main():
    print("searching for:")
    for c in COURSES:
        print(f"   - {c['code']} Section {c['section']}")
    last_status = {f"{c['code']}-{c['section']}": None for c in COURSES}

    while True:
        for c in COURSES:
            try:
                key = f"{c['code']}-{c['section']}"
                seats = check_course(c['code'], c['section'])
                now = time.strftime("%I:%M:%S %p")

                if isinstance(seats, int):
                    if seats > 0:
                        print(f"[{now}] {seats} seat{'s' if seats != 1 else ''} in {c['code']} section {c['section']}")
                        if last_status[key] != seats:
                            msg = f"{seats} seat{'s' if seats != 1 else ''} in {c['code']} section {c['section']}; {now} [View Schedule]({SEARCH_URL})"
                            notif(msg)
                            last_status[key] = seats
                    else:
                        print(f"[{now}] ❌{c['code']} section {c['section']} full.")
                        if last_status[key] != 0:
                            last_status[key] = 0
                elif isinstance(seats, bool):
                    if seats:
                        print(f"[{now}] {c['code']} section {c['section']} open (boolean).")
                        if last_status[key] != True:
                            msg = f"{c['code']} section {c['section']} open; {now} [View Schedule]({SEARCH_URL})"
                            notif(msg)
                            last_status[key] = True
                    else:
                        print(f"[{now}] ❌{c['code']} section {c['section']} full (boolean).")
                        if last_status[key] != False:
                            last_status[key] = False
                else:
                    print(f"[{now}] error check result for {c['code']} {c['section']}: {seats!r}")
            except Exception as e:
                print(f"error {c['code']} {c['section']}: {e}")
        print(f"waiting {CHECK_INTERVAL/60:.1f} minutes before next check")
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
