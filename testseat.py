import requests
from bs4 import BeautifulSoup
import time
import re
import sys

# SETTINGS
discordWebhook = "https://discord.com/api/webhooks/1435337474422476973/_by6UEO_E2cPYWiZSVNitR2hd3dgEzs8Jc1E-Rt5xPO5BJD7Hc9X-eMMs1KWxZE0EiPJ"
COURSES = [
    {"code": "TCO 141", "section": "003"},
    {"code": "PHY 161", "section": "004"},
    {"code": "PHY 161", "section": "005"},
    {"code": "CHM 321", "section": "006"},
    {"code": "CHM 321", "section": "007"},
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
def parseSeatsFromTable(soup, target_code, target_section):
    def norm(s):
        return re.sub(r'[^a-z0-9]', '', s.lower() or '')

    try:
        targetSectionInt = int(re.search(r'(\d+)', target_section).group(1))
    except Exception:
        targetSectionInt = None
    normTargetCode = norm(target_code)

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
            targetCourseNorm = re.sub(r'[^A-Za-z0-9]', '', target_code).lower()
            secTextNorm = re.sub(r'[^A-Za-z0-9]', '', secText).lower()
            targetSectionNorm = re.sub(r'[^A-Za-z0-9]', '', target_section).lower()

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
    try:
        r = session.get(searchUrl, timeout=requestTimeout)
        if r.status_code != 200:
            print(f"GET request failed ({r.status_code})")
            return False
    except Exception as e:
        print(f"Error loading search page: {e}")
        return False

    soup = BeautifulSoup(r.text, 'html.parser')
    hiddenInputs = {inp.get('name'): inp.get('value', '') for inp in soup.find_all('input', {'type': 'hidden'}) if inp.get('name')}
    names = set(tag.get('name') for tag in soup.find_all(['input', 'select', 'textarea']) if tag.get('name'))
    codeName = findName(names, ['txtCourseCode', 'coursecode'])
    sectionName = findName(names, ['txtCourseSection', 'section'])
    submitName = findName(names, ['btnSubmit', 'submit'])
    data = hiddenInputs.copy()

    if codeName:
        data[codeName] = code
    if sectionName:
        data[sectionName] = section
    if submitName:
        data[submitName] = 'Submit'

    try:
        r2 = session.post(searchUrl, data=data, timeout=requestTimeout)
        if r2.status_code != 200:
            print(f"POST request failed ({r2.status_code})")
            return False
    except Exception as e:
        print(f"Error submitting search form: {e}")
        return False

    soup2 = BeautifulSoup(r2.text, 'html.parser')
    seats = parseSeatsFromTable(soup2, code, section)
    if seats is None:
        text = soup2.get_text(' ', strip=True).lower()
        return 'open' in text and 'full' not in text
    return seats


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


def monitor(courses):
    print("\nChecking the following course(s):")
    for c in courses:
        print(f"  {c['code']} section {c['section']}")
    lastStatus = {f"{c['code']}-{c['section']}": None for c in courses}

    while True:
        for c in courses:
            try:
                key = f"{c['code']}-{c['section']}"
                seats = checkCourse(c['code'], c['section'])
                now = time.strftime("%I:%M:%S %p")
                print(f"[{now}] Checking {c['code']} section {c['section']}...")

                if isinstance(seats, int):
                    if seats > 0:
                        msg = f"{seats} seat{'s' if seats != 1 else ''} available in {c['code']} section {c['section']}"
                        print(f"[{now}] {msg}")
                        notify(f"{msg}; Checked at {now} [View Schedule]({searchUrl})")
                        lastStatus[key] = seats
                    else:
                        print(f"[{now}] {c['code']} section {c['section']} full.")
                        lastStatus[key] = 0
                elif isinstance(seats, bool):
                    if seats:
                        msg = f"{c['code']} section {c['section']} open"
                        print(f"[{now}] {msg}")
                        notify(f"{msg}; Checked at {now} [View Schedule]({searchUrl})")
                        lastStatus[key] = True
                    else:
                        print(f"[{now}] {c['code']} section {c['section']} full.")
                        lastStatus[key] = False
            except Exception as e:
                print(f"Error checking {c['code']} {c['section']}: {e}")

        print(f"\nWaiting {checkInterval/60:.1f} minutes before next check...\n")
        time.sleep(checkInterval)


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
