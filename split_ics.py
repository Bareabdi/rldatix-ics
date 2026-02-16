import re
import requests
from icalendar import Calendar, Event
from pathlib import Path
from datetime import datetime, timezone

SOURCE_ICS_URL = "https://regionhovedstaden.allocate-cloud.de/EmployeeOnlineHealth/REGHLIVE/ical/38a57d6a-b516-494c-986b-3889c34426dc"

RULES = {
    "modtagelse": ["modtag", "akut", "skad", "heakm1"],
    "stuegang": ["stg", "stuegang", "he119stg", "he114stg"],
    "ambulatorie": ["heskamb", "amb", "ambu"],
    "aften_nat": ["hefvan", "aften", "nat", "natte", "aftenvagt"],
}

FALLBACK_CAL = "andet"
OUTPUT_DIR = Path("out")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().lower()


def classify(summary: str, description: str, location: str) -> str:
    hay = norm(" ".join([summary, description, location]))
    for name, kws in RULES.items():
        if any(kw in hay for kw in kws):
            return name
    return FALLBACK_CAL


def make_calendar(name: str) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//rldatix split//")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"RLDatix - {name}")
    cal.add("x-wr-timezone", "Europe/Copenhagen")
    return cal


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    r = requests.get(SOURCE_ICS_URL, timeout=30)
    r.raise_for_status()
    src = Calendar.from_ical(r.content)

    buckets = {}
    n = 0

    for comp in src.walk():
        if comp.name != "VEVENT":
            continue
        n += 1
        summary = str(comp.get("summary", ""))
        desc = str(comp.get("description", ""))
        loc = str(comp.get("location", ""))

        bucket = classify(summary, desc, loc)
        if bucket not in buckets:
            buckets[bucket] = make_calendar(bucket)

                ev = Event()

        summary = comp.get("summary")
        dtstart = comp.get("dtstart")
        dtend = comp.get("dtend")
        dtstamp = comp.get("dtstamp") or datetime.now(timezone.utc)
        uid = comp.get("uid")
        description = comp.get("description")
        location = comp.get("location")

        if summary:
            ev.add("summary", summary)
        if dtstart:
            ev.add("dtstart", dtstart)
        if dtend:
            ev.add("dtend", dtend)

        ev.add("dtstamp", dtstamp)

        if uid:
            ev.add("uid", f"{uid}-{bucket}")
        else:
            ev.add("uid", f"gen-{bucket}-{n}")

        if description:
            ev.add("description", description)
        if location:
            ev.add("location", location)

        buckets[bucket].add_component(ev)


    for name, cal in buckets.items():
        (OUTPUT_DIR / f"{name}.ics").write_bytes(cal.to_ical())

    print(f"Splittede {n} events i {len(buckets)} kalendere:")
    for name in sorted(buckets.keys()):
        print(" -", OUTPUT_DIR / f"{name}.ics")


if __name__ == "__main__":
    main()

