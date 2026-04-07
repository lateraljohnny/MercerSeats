import requests
from bs4 import BeautifulSoup
import time
import re
import sys
import random

# SETTINGS
discordWebhook = "https://discord.com/api/webhooks/1436527367593005156/RJuSxq33K7soLf-Wvr6P-E-0_8hFTj6SBFSzfA_shTlFOH2QwcUQb8HHZbaFisgS8cEx"
COURSES = [
    {"code": "PHY 162", "section": "001"},
    {"code": "PHY 162", "section": "002"},
    {"code": "EGR 232", "section": "003"},
    {"code": "MAT 330", "section": "004"},
    {"code": "EGR 244", "section": "004"},
    {"code": "EGR 251", "section": "0W1"},
    {"code": "HID 364", "section": "001"},
]
checkInterval = 300  # 5mins
searchUrl = "https://adminapps.mercer.edu/classroomsched/default.aspx?C=M"
requestTimeout = 15

# ---------- HELPERS ----------
def findName(names, substrings):
    for s in substrings:
        for n in names:
            if n and s.lower() in n.lower():
                return n
    return None

def notify(msg):
    try:
        r = requests.post(discordWebhook, json={"content": msg}, timeout=requestTimeout)
        if 200 <= r.status_code < 300:
            print("Discord alert sent.")
        else:
            print(f"Discord webhook returned HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"Failed to send Discord alert: {e}")


# ---------- PARSER ----------
def parseSeatsFromTable(soup, targetCode, targetSection):
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', s.lower() or '')

    try:
        targetSectionInt = int(re.search(r'(\d+)', targetSection).group(1))
    except Exception:
        targetSectionInt = None
    normTargetCode = norm(targetCode)

    tables = soup.find_all('table')
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if not headers:
            firstRow = table.find('tr')
            if firstRow:
                headers = [td.get_text(strip=True).lower() for td in firstRow.find_all(['th', 'td'])]
        if not headers or not (any('course' in h for h in headers) and any('seat' in h for h in headers)):
            continue

        courseIdx = next((i for i, h in enumerate(headers) if 'course' in h), None)
        sectionIdx = next((i for i, h in enumerate(headers) if 'section' in h), None)
        seatsIdx = next((i for i, h in enumerate(headers)if '# seats available' in h or 'available' in h),None)
        if seatsIdx is None:
            seatsIdx = next((i for i, h in enumerate(headers) if 'seat' in h), None)

        for row in table.find_all('tr')[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
            if not cols:
                continue

            secText = cols[sectionIdx] if sectionIdx is not None and sectionIdx < len(cols) else ''
            courseText = cols[courseIdx] if courseIdx is not None and courseIdx < len(cols) else ''
            courseNorm = re.sub(r'[^A-Za-z0-9]', '', courseText).lower()
            targetCourseNorm = re.sub(r'[^A-Za-z0-9]', '', targetCode).lower()
            secTextNorm = re.sub(r'[^A-Za-z0-9]', '', secText).lower()
            targetSectionNorm = re.sub(r'[^A-Za-z0-9]', '', targetSection).lower()

            if targetCourseNorm in courseNorm and targetSectionNorm == secTextNorm:
                if seatsIdx is not None and seatsIdx < len(cols):
                    seatsText = cols[seatsIdx]
                    m = re.search(r"(\d+)", seatsText)
                    if m:
                        return int(m.group(1))
                    else:
                        return 0
    return None


def checkCourse(code, section):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": searchUrl,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    })

    try:
        # Step 1: Initial GET to grab fresh ViewState/EventValidation tokens
        r = session.get(searchUrl, timeout=requestTimeout)
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"Connection Error: {e}")
        return False

    # Extract all hidden ASP.NET fields (__VIEWSTATE, __VIEWSTATEGENERATOR, etc.)
    data = {}
    for inp in soup.find_all('input', {'type': 'hidden'}):
        if inp.get('name'):
            data[inp.get('name')] = inp.get('value', '')
    
    # Dynamically find the Term input (e.g. Fall 2026)
    termFieldName = 'radTerm' # Fallback default
    for inp in soup.find_all('input', {'type': 'radio'}):
        if '2026' in inp.get('value', '') and 'FA' in inp.get('value', ''):
            termFieldName = inp.get('name')
            break

    # Construct the base search payload using the EXACT names from the HTML
    data.update({
        termFieldName: '2026-FA',
        'radLevel': 'U',                   # Ensure 'Undergraduate' is selected
        'searchCourse': '',                # Blank out the 'Course Title' field
        'searchCourseCode': code,          # CRITICAL FIX: Was txtCourseCode
        'searchCourseSection': section,    # CRITICAL FIX: Was txtCourseSection
        '__EVENTTARGET': '', 
        '__EVENTARGUMENT': ''
    })

    # Dynamically find the Submit button to ensure we use the correct name (Button1)
    submitButton = soup.find('input', {'type': ['submit', 'image']})
    if submitButton and submitButton.get('name'):
        btnName = submitButton.get('name')
        if submitButton.get('type') == 'image':
            # Only send coordinates if it's actually an image button
            data[f'{btnName}.x'] = '15'
            data[f'{btnName}.y'] = '15'
        else:
            # Otherwise just send the button name and its value
            data[btnName] = submitButton.get('value', 'Submit')
    else:
        # Fallback if we somehow can't find a button
        data['Button1'] = 'Submit'

    try:
        # Step 2: POST the specific search criteria
        r2 = session.post(searchUrl, data=data, timeout=requestTimeout)
        
        # Verify the server actually processed the search
        if code.upper() not in r2.text.upper() and "no classes found" not in r2.text.lower():
            # DEBUGGING TRAP: Save the HTML so we can see what went wrong
            debugFilename = f"debug_failed_{code.replace(' ', '_')}.html"
            with open(debugFilename, "w", encoding="utf-8") as f:
                f.write(r2.text)
            print(f"[DEBUG] Search for {code} failed to trigger. Saved server response to {debugFilename}")
            return None 

    except Exception as e:
        print(f"POST Error: {e}")
        return False

    soup2 = BeautifulSoup(r2.text, 'html.parser')
    
    # Check for the "No classes found" message specifically
    if "no classes found" in r2.text.lower():
        return 0

    return parseSeatsFromTable(soup2, code, section)


def promptWebhook():
    while True:
        webhook = input("Enter Discord webhook URL: ").strip()
        if webhook.startswith("https://discord.com/api/webhooks/"):
            return webhook
        print("Invalid webhook URL. Try again.\n")


def promptCourseCode():
    while True:
        code = input("Enter course code (e.g., MAT 192): ").strip()
        if re.match(r'^[A-Za-z]+\s*\d+$', code):
            return code
        print("Invalid input. Try again (example: MAT 192).\n")


def promptSection():
    while True:
        section = input("\nEnter section (Ex: 008/08/8): ").strip()
        if not section.isdigit():
            print("Invalid input. Digits only (Ex: 008/08/8).\n")
            continue
        section = section.zfill(3)
        return section


def promptCourses():
    courses = []
    print("Enter courses you want to monitor (Ctrl+C to cancel).")
    try:
        while True:
            code = promptCourseCode()
            section = promptSection()
            courses.append({"code": code, "section": section})
            print("\nCurrent courses:")
            for i, c in enumerate(courses, start=1):
                print(f"  [{i}] {c['code']} section {c['section']}")

            while True:
                more = input("\nAdd another, remove one, or finish? [a/r/f]: ").strip().lower()
                if more == 'f' or more == 'finish':
                    return courses
                elif more in ('a', 'y', ''):
                    break
                elif more in ('r', 'remove'):
                    if not courses:
                        print("No courses to remove.")
                        continue
                    try:
                        rembIdx = int(input("Enter the number of the course to remove: ")) - 1
                        if 0 <= rembIdx < len(courses):
                            removed = courses.pop(rembIdx)
                            print(f"Removed {removed['code']} section {removed['section']}.")
                            if not courses:
                                print("No courses remaining.")
                                break
                        else:
                            print("Invalid selection.")
                    except ValueError:
                        print("Invalid input. Enter a valid number.")
                else:
                    print("Invalid choice. Enter A to add, R to remove, or N to finish.")
    except KeyboardInterrupt:
        print("\nInput cancelled.")
    return courses


def monitor(courseList):
    print(f"Starting monitor for Fall 2026 courses...")
    for c in courseList:
        print(f"  - {c['code']} section {c['section']}")

    while True:
        for c in courseList:
            try:
                seats = checkCourse(c['code'], c['section'])
                now = time.strftime("%I:%M:%S %p")
                
                if isinstance(seats, int):
                    if seats > 0:
                        msg = f"SEAT OPEN: {seats} available in {c['code']} section {c['section']}"
                        print(f"[{now}] {msg}")
                        notify(f"{msg}; Checked at {now} [Schedule]({searchUrl})")
                    else:
                        print(f"[{now}] {c['code']} {c['section']} is currently FULL.")
                elif seats is None:
                    print(f"[{now}] Could not find {c['code']} {c['section']} on the page.")
            except Exception as e:
                print(f"Error during check: {e}")

        # RANDOMIZED DELAY: 15 to 25 minutes (900 to 1500 seconds)
        delay = random.randint(900, 1500)
        print(f"\n[{time.strftime('%I:%M:%S %p')}] Waiting {delay/60:.1f} minutes until next check...\n")
        time.sleep(delay)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        monitor(COURSES)
    else:
        print("Welcome to the Mercer University Course Seat Monitor!\n")
        print("\nFirst, you'll need to provide a Discord webhook URL to receive notifications.")
        discordWebhook = promptWebhook()
        print("\nNow, let's enter the courses you want to monitor.\n")
        userCourses = promptCourses()
        if not userCourses:
            print("No courses entered. Exiting.")
            sys.exit(0)
        monitor(userCourses)
