
import json
import urllib.request
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = (
    "https://lebaptiste.com/schedule-pro-limbo/public/"
    "institutions/catalyst/schedule-entries"
    "?active_period_id=127&discard=false"
)

GROUP = "VFX-26"
BERLIN = ZoneInfo("Europe/Berlin")
DAYS = {
    "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5,
    "saturday": 6, "sunday": 7
}


def escape(value):
    return (str(value or "")
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace(",", "\\,")
            .replace(";", "\\;"))


def weeks(series):
    result = set()
    for part in str(series or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = map(int, part.split("-", 1))
            result.update(range(first, last + 1))
        else:
            result.add(int(part))
    return sorted(result)


def fold(line):
    # iCalendar lines must be folded at 75 octets.
    pieces = []
    current = ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            pieces.append(current)
            current = " " + char
        else:
            current += char
    pieces.append(current)
    return "\r\n".join(pieces)


request = urllib.request.Request(
    API, headers={"User-Agent": "CatalystCalendar/1.0"}
)
with urllib.request.urlopen(request, timeout=30) as response:
    data = json.load(response)

if isinstance(data, dict):
    entries = data.get("entries") or data.get("data")
else:
    entries = data

if not isinstance(entries, list):
    raise ValueError("Unexpected Catalyst API response")

lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Catalyst VFX Calendar//ES",
    "CALSCALE:GREGORIAN",
    "X-WR-CALNAME:Catalyst VFX-26",
    "X-WR-TIMEZONE:Europe/Berlin",
    "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
]

count = 0
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

for entry in entries:
    groups = entry.get("groups") or []
    if not any(
        g.get("name", "").upper() == GROUP
        for g in groups
    ):
        continue

    if entry.get("discard") or entry.get("exceptions"):
        # Entries with exceptions need separate handling.
        if entry.get("exceptions"):
            print("Review exceptions for", entry.get("id"))
        if entry.get("discard"):
            continue

    year = int(entry["year"])
    weekday = DAYS.get(str(entry.get("day", "")).lower())
    if not weekday:
        continue

    for week in weeks(entry.get("week_series")):
        try:
            day = date.fromisocalendar(year, week, weekday)
        except ValueError:
            continue

        start = datetime.combine(
            day, datetime.strptime(
                entry["start_time"], "%H:%M:%S"
            ).time(), BERLIN
        )
        end = datetime.combine(
            day, datetime.strptime(
                entry["end_time"], "%H:%M:%S"
            ).time(), BERLIN
        )
        if end <= start:
            end += timedelta(days=1)

        title = entry.get("subject_name") or entry.get("title") or "Class"
        room = entry.get("room_name") or ""
        teacher = entry.get("teacher_name") or ""
        description = f"Teacher: {teacher}"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:catalyst-{entry['id']}-{day.isoformat()}@vfx26",
            f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Europe/Berlin:{start:%Y%m%dT%H%M%S}",
            f"DTEND;TZID=Europe/Berlin:{end:%Y%m%dT%H%M%S}",
            f"SUMMARY:{escape(title)}",
            f"LOCATION:{escape(room)}",
            f"DESCRIPTION:{escape(description)}",
            "END:VEVENT",
        ])
        count += 1

if count == 0:
    raise ValueError("No VFX-26 classes found. Check group names.")

lines.append("END:VCALENDAR")
Path("calendar.ics").write_bytes(
    ("\r\n".join(fold(line) for line in lines) + "\r\n")
    .encode("utf-8")
)

print(f"Generated {count} VFX-26 events")
