"""
Google Calendar Service
Handles:
  - Checking doctor availability on a date
  - Getting free time slots (9 AM – 5 PM)
  - Booking appointments on Google Calendar
  - Parsing spoken date strings into datetime objects

Prerequisites:
  - Google Cloud project with Calendar API enabled
  - OAuth2 credentials (credentials.json) OR Service Account (service_account.json)
  - Each doctor must share their Google Calendar with the service account email
  - Set DOCTOR_CALENDARS in config.py mapping doctor name → calendar ID

Setup:
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib dateparser
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
import os

logger = logging.getLogger(__name__)

# ── Weekend & Holiday blocking ─────────────────────────────────────────────────
#
# BLOCKED_WEEKDAYS: 5 = Saturday, 6 = Sunday (Python's weekday() convention)
#
# PUBLIC_HOLIDAYS: Add/remove dates here as needed.
# Format: "MM-DD" for annual holidays (repeat every year)
#         "YYYY-MM-DD" for one-off holidays (specific year only)
#
# Current list covers all major Indian national holidays.
# Add your state-specific or hospital-specific holidays below.

BLOCKED_WEEKDAYS = {5, 6}  # Saturday, Sunday

PUBLIC_HOLIDAYS = {
    # ── National holidays (repeat every year, MM-DD) ──────────────────────
    "01-26",   # Republic Day
    "03-25",   # Holi (approximate — update yearly if needed)
    "04-14",   # Dr. Ambedkar Jayanti / Tamil New Year / Baisakhi
    "08-15",   # Independence Day
    "10-02",   # Gandhi Jayanti
    "10-24",   # Dussehra (approximate — update yearly)
    "11-01",   # Diwali / Karnataka Rajyotsava (approximate — update yearly)
    "12-25",   # Christmas
    # ── Floating holidays (add specific year dates here) ──────────────────
    # "2026-04-03",   # Good Friday 2026
    # "2026-04-10",   # Ram Navami 2026
    # "2026-10-20",   # Diwali 2026
    # ── Hospital-specific closures (add your own below) ───────────────────
    # "2026-01-01",   # New Year's Day
    # "2026-08-26",   # Hospital Foundation Day
}

# Human-readable names for holidays (used in voice messages)
HOLIDAY_NAMES = {
    "01-26": "Republic Day",
    "03-25": "Holi",
    "04-14": "Dr. Ambedkar Jayanti",
    "08-15": "Independence Day",
    "10-02": "Gandhi Jayanti",
    "10-24": "Dussehra",
    "11-01": "Diwali",
    "12-25": "Christmas Day",
}

WEEKDAY_NAMES = {
    5: "Saturday",
    6: "Sunday",
}


class DateRejected:
    """
    Returned by parse_date_string() when a date is valid but blocked.
    Carries a reason so the IVR can speak an informative message.
    """
    def __init__(self, reason: str, date: "datetime"):
        self.reason = reason   # e.g. "Sunday" or "Republic Day"
        self.date   = date     # The parsed datetime (for display)

    def __bool__(self):
        return False           # Behaves like None in boolean checks


def is_date_available(date: "datetime") -> "tuple[bool, str]":
    """
    Checks if the hospital is open on the given date.
    Returns (True, "") if available, or (False, reason_string) if blocked.
    """
    weekday = date.weekday()

    # ── Weekend check ──────────────────────────────────────────────────────
    if weekday in BLOCKED_WEEKDAYS:
        return False, WEEKDAY_NAMES[weekday]

    # ── Public holiday check ───────────────────────────────────────────────
    mm_dd   = date.strftime("%m-%d")        # e.g. "08-15"
    yyyy_mm_dd = date.strftime("%Y-%m-%d")  # e.g. "2026-08-15"

    if mm_dd in PUBLIC_HOLIDAYS or yyyy_mm_dd in PUBLIC_HOLIDAYS:
        reason = (
            HOLIDAY_NAMES.get(mm_dd)
            or HOLIDAY_NAMES.get(yyyy_mm_dd)
            or "a public holiday"
        )
        return False, reason

    return True, ""


# ── Slot definitions ───────────────────────────────────────────────────────────
ALL_SLOTS = list(range(9, 18))  # 9, 10, 11, 12, 13, 14, 15, 16, 17
SLOT_DURATION_MINUTES = 60

SLOT_DISPLAY = {
    9: "9:00 AM", 10: "10:00 AM", 11: "11:00 AM", 12: "12:00 PM",
    13: "1:00 PM", 14: "2:00 PM", 15: "3:00 PM", 16: "4:00 PM", 17: "5:00 PM"
}


# ── Google Calendar client ─────────────────────────────────────────────────────

def _get_calendar_service():
    """
    Returns an authenticated Google Calendar API service object.
    Uses Service Account by default (recommended for server apps).
    Falls back to OAuth2 if service account file not found.
    """
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account

        SERVICE_ACCOUNT_FILE = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
        SCOPES = ["https://www.googleapis.com/auth/calendar"]

        if os.path.exists(SERVICE_ACCOUNT_FILE):
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=SCOPES
            )
            return build("calendar", "v3", credentials=creds, cache_discovery=False)

        # Fallback: OAuth2 flow (for development)
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        TOKEN_FILE = "token.json"
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    except Exception as e:
        logger.error(f"Failed to initialise Google Calendar service: {e}")
        return None


# ── Date parsing ───────────────────────────────────────────────────────────────

def _basic_parse_date(date_str: str) -> Optional[datetime]:
    """
    Fallback date parser used when dateparser is not installed.
    Handles: 'tomorrow', 'today', 'day after tomorrow',
             weekday names ('this Friday', 'next Monday'),
             and explicit dates ('15 June', 'June 15', '5th of June').

    FIX: Replaced %-d (Linux-only strftime) with str(d.day) which is
         cross-platform and works correctly on Windows.
    """
    today = datetime.now()
    date_lower = date_str.lower().strip()

    # ── Relative day keywords ──────────────────────────────────────────────
    if "day after tomorrow" in date_lower:
        return today + timedelta(days=2)
    if "tomorrow" in date_lower:
        return today + timedelta(days=1)
    if "today" in date_lower:
        return today

    # ── Weekday names ──────────────────────────────────────────────────────
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(days):
        if day in date_lower:
            days_ahead = (i - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7  # "this Monday" when today is Monday → next Monday
            return today + timedelta(days=days_ahead)

    # ── Explicit month + day  ("15 June", "June 15", "5th of June") ───────
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }
    for month_name, month_num in months.items():
        if month_name in date_lower:
            nums = re.findall(r"\d+", date_lower)
            if nums:
                day_num = int(nums[0])
                year = today.year
                try:
                    candidate = datetime(year, month_num, day_num)
                    if candidate.date() < today.date():
                        candidate = datetime(year + 1, month_num, day_num)
                    return candidate
                except ValueError:
                    pass  # Invalid day for that month — skip

    return None


def parse_date_string(date_str: str) -> "Optional[datetime] | DateRejected":
    """
    Converts natural language date strings to datetime objects.
    Supports: 'tomorrow', 'this Friday', '5th June', 'June 10', etc.

    Returns:
      - datetime         → valid, available date
      - DateRejected     → valid date but blocked (weekend / public holiday)
      - None             → could not parse, or date is in the past
    """
    if not date_str or not date_str.strip():
        return None

    # ── Try dateparser first (best results) ───────────────────────────────
    parsed = None
    try:
        import dateparser
        parsed = dateparser.parse(
            date_str,
            settings={
                "PREFER_DATES_FROM": "future",
                "RETURN_AS_TIMEZONE_AWARE": False,
                "DATE_ORDER": "DMY",
            },
        )
        if parsed and parsed.date() < datetime.now().date():
            logger.warning(f"dateparser returned a past date for '{date_str}': {parsed.date()}")
            parsed = None
        logger.debug(f"dateparser could not parse '{date_str}', trying basic parser")
    except ImportError:
        logger.warning("dateparser not installed — using basic date parser. Run: pip install dateparser")
    except Exception as e:
        logger.error(f"dateparser raised an unexpected error for '{date_str}': {e}")

    # ── Fallback to basic parser ───────────────────────────────────────────
    if not parsed:
        try:
            parsed = _basic_parse_date(date_str)
            if parsed and parsed.date() < datetime.now().date():
                parsed = None
        except Exception as e:
            logger.error(f"Basic date parsing also failed for '{date_str}': {e}")
            return None

    if not parsed:
        return None

    # ── Weekend / holiday check ────────────────────────────────────────────
    available, reason = is_date_available(parsed)
    if not available:
        logger.info(f"Date {parsed.date()} blocked: {reason}")
        return DateRejected(reason=reason, date=parsed)

    return parsed


# ── Free slot calculation ──────────────────────────────────────────────────────

def get_free_slots(calendar_id: str, date: datetime) -> list:
    """
    Returns a list of free hour slots (int, 24h) for the given doctor's calendar
    on the given date. Slots are 9 AM – 5 PM, 1-hour each.

    Falls back to all slots if Google Calendar is unavailable.
    """
    service = _get_calendar_service()
    if not service:
        logger.warning("Calendar service unavailable — returning all slots")
        return ALL_SLOTS[:]

    try:
        # Build time range for the day
        tz_offset = "+05:30"  # IST
        day_start = f"{date.strftime('%Y-%m-%d')}T00:00:00{tz_offset}"
        day_end   = f"{date.strftime('%Y-%m-%d')}T23:59:59{tz_offset}"

        # Fetch busy times
        body = {
            "timeMin": day_start,
            "timeMax": day_end,
            "items": [{"id": calendar_id}],
        }
        freebusy = service.freebusy().query(body=body).execute()
        busy_periods = freebusy.get("calendars", {}).get(calendar_id, {}).get("busy", [])

        # Find which slots are taken
        busy_hours = set()
        for period in busy_periods:
            start_str = period["start"]
            end_str   = period["end"]

            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_dt   = datetime.fromisoformat(end_str.replace("Z", "+00:00"))

            # Convert to IST (UTC+5:30)
            ist_offset = timedelta(hours=5, minutes=30)
            start_ist  = start_dt.astimezone(timezone(ist_offset))
            end_ist    = end_dt.astimezone(timezone(ist_offset))

            # Mark all overlapping slots as busy
            for slot_hour in ALL_SLOTS:
                slot_start = date.replace(hour=slot_hour, minute=0, second=0, microsecond=0)
                slot_end   = slot_start + timedelta(hours=1)
                if start_ist < slot_end and end_ist > slot_start:
                    busy_hours.add(slot_hour)

        free = [h for h in ALL_SLOTS if h not in busy_hours]
        logger.info(f"Free slots for {calendar_id} on {date.date()}: {free}")
        return free

    except Exception as e:
        logger.error(f"Failed to fetch free slots: {e}")
        return ALL_SLOTS[:]  # Safe fallback


def is_slot_booked_on_calendar(calendar_id: str, date_str: str, hour: int) -> bool:
    """
    Live check: returns True if the specific hour slot on the given date
    is already booked in the doctor's Google Calendar.
    """
    service = _get_calendar_service()
    if not service:
        return False

    try:
        tz_offset = "+05:30"
        slot_start = f"{date_str}T{hour:02d}:00:00{tz_offset}"
        slot_end   = f"{date_str}T{hour+1:02d}:00:00{tz_offset}"

        body = {
            "timeMin": slot_start,
            "timeMax": slot_end,
            "items": [{"id": calendar_id}],
        }
        freebusy = service.freebusy().query(body=body).execute()
        busy = freebusy.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return len(busy) > 0

    except Exception as e:
        logger.error(f"Slot availability check failed: {e}")
        return False


# ── Booking ────────────────────────────────────────────────────────────────────

def book_appointment(
    calendar_id: str,
    patient_name: str,
    disease: str,
    doctor: str,
    date_str: str,
    hour: int,
) -> Optional[str]:
    """
    Creates a 1-hour Google Calendar event for the appointment.
    Returns the event ID if successful, None otherwise.
    """
    service = _get_calendar_service()
    if not service:
        logger.warning("Google Calendar unavailable — appointment NOT synced to calendar")
        return None

    try:
        tz = "Asia/Kolkata"
        start_time = f"{date_str}T{hour:02d}:00:00"
        end_time   = f"{date_str}T{hour+1:02d}:00:00"

        event = {
            "summary":     f"Appointment: {patient_name}",
            "description": (
                f"Patient: {patient_name}\n"
                f"Symptoms: {disease}\n"
                f"Doctor: {doctor}\n"
                f"Booked via: AI Voice System"
            ),
            "start": {"dateTime": start_time, "timeZone": tz},
            "end":   {"dateTime": end_time,   "timeZone": tz},
            "colorId": "3",  # Sage green
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email",  "minutes": 24 * 60},
                    {"method": "popup",  "minutes": 30},
                ],
            },
        }

        created = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"Calendar event created: {created.get('htmlLink')}")
        return created.get("id")

    except Exception as e:
        logger.error(f"Failed to create calendar event: {e}")
        return None
