"""
Excel Service
Saves patient appointment data to Excel.
Also provides slot availability checking using Excel as source of truth.
"""

import os
import logging
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from app.services.config import Config

logger = logging.getLogger(__name__)

EXCEL_PATH = Config.EXCEL_FILE_PATH
HEADERS    = [
    "#", "Patient Name", "Disease / Symptoms",
    "Doctor Preference", "Preferred Time", "Call SID", "Recorded At"
]

HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill("solid", start_color="1F4E79")
ALT_FILL    = PatternFill("solid", start_color="D6E4F0")
THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"),  bottom=Side(style="thin"),
)
COL_WIDTHS = [6, 22, 30, 25, 25, 38, 22]

# All possible slots in a day (9 AM – 5 PM)
ALL_SLOTS = [9, 10, 11, 12, 13, 14, 15, 16, 17]
SLOT_DISPLAY = {
    9: "9:00 AM", 10: "10:00 AM", 11: "11:00 AM", 12: "12:00 PM",
    13: "1:00 PM", 14: "2:00 PM", 15: "3:00 PM", 16: "4:00 PM", 17: "5:00 PM"
}


def _format_day(d: datetime) -> str:
    """
    Returns the day number without a leading zero, cross-platform.
    %-d works on Linux/Mac, %#d works on Windows.
    This helper avoids using either directly.
    """
    return str(d.day)  # e.g. "1", "15" — no leading zero, works everywhere


def _init_workbook(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Appointments"
    ws.append(HEADERS)
    for col_idx, (_, width) in enumerate(zip(HEADERS, COL_WIDTHS), start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = THIN_BORDER
        ws.column_dimensions[cell.column_letter].width = width
    ws.row_dimensions[1].height = 20
    ws.freeze_panes = "A2"
    wb.save(path)
    logger.info(f"Created new Excel file: {path}")


def _load_booked_slots(doctor: str = None, date_str: str = None) -> list:
    """
    Returns a list of booked preferred_time strings from the Excel sheet.
    If doctor and date_str are given, only returns slots for that doctor on that date.
    date_str should be in "YYYY-MM-DD" format.
    """
    if not os.path.exists(EXCEL_PATH):
        return []
    try:
        wb = load_workbook(EXCEL_PATH, read_only=True, data_only=True)
        ws = wb["Appointments"]

        # Column indices (0-based from row tuple):
        # 0=#, 1=Patient Name, 2=Disease, 3=Doctor Preference, 4=Preferred Time, 5=Call SID, 6=Recorded At
        booked = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue

            row_doctor = str(row[3]).strip() if row[3] else ""
            row_time   = str(row[4]).strip() if row[4] else ""

            if not row_time or row_time.lower() == "none":
                continue

            # If filtering by doctor+date, check both
            if doctor and date_str:
                if row_doctor.lower() != doctor.lower():
                    continue
                # The preferred_time format is "Sunday, 01 June 2026 at 10:00 AM"
                # Check if date_str (YYYY-MM-DD) or its human-readable variants appear in the stored string
                if date_str not in row_time:
                    try:
                        from datetime import datetime as dt
                        d = dt.strptime(date_str, "%Y-%m-%d")
                        day_no = _format_day(d)          # e.g. "1" or "15"
                        month  = d.strftime("%B")        # e.g. "June"
                        year   = d.strftime("%Y")        # e.g. "2026"
                        weekday = d.strftime("%A")       # e.g. "Sunday"

                        # FIX: replaced %-d (Linux-only) with _format_day() which is cross-platform
                        variants = [
                            f"{d.strftime('%d')} {month} {year}",    # 01 June 2026
                            f"{day_no} {month} {year}",              # 1 June 2026
                            f"{weekday}, {d.strftime('%d')} {month} {year}",  # Sunday, 01 June 2026
                            f"{weekday}, {day_no} {month} {year}",  # Sunday, 1 June 2026
                            f"{d.strftime('%d')} {month}",           # 01 June
                            f"{day_no} {month}",                     # 1 June
                        ]
                        if not any(v in row_time for v in variants):
                            continue
                    except Exception:
                        continue

            booked.append(row_time.lower())

        wb.close()
        return booked
    except Exception as e:
        logger.error(f"Failed to load booked slots: {e}")
        return []


def get_free_slots_from_excel(doctor: str, date_str: str) -> list:
    """
    Returns a list of free hour-slots (int, 24h) for the given doctor on the given date,
    based purely on what is already booked in the Excel sheet.

    date_str: "YYYY-MM-DD"
    Returns: list of ints from ALL_SLOTS that are NOT already booked
    """
    booked_entries = _load_booked_slots(doctor=doctor, date_str=date_str)

    # Parse which hours are already taken
    taken_hours = set()
    for entry in booked_entries:
        for hour, display in SLOT_DISPLAY.items():
            if display.lower() in entry:
                taken_hours.add(hour)
                break

    free = [h for h in ALL_SLOTS if h not in taken_hours]
    logger.info(f"Free slots for {doctor} on {date_str}: {[SLOT_DISPLAY[h] for h in free]}")
    return free


def is_doctor_available_on_date(doctor: str, date_str: str) -> bool:
    """
    Returns True if the doctor has at least one free slot on the given date.
    date_str: "YYYY-MM-DD"
    """
    free = get_free_slots_from_excel(doctor, date_str)
    return len(free) > 0


def is_slot_taken(doctor: str, date_str: str, hour: int) -> bool:
    """
    Returns True if the specific hour slot is already booked for this doctor+date.
    doctor: e.g. "Dr. Sharma"
    date_str: "YYYY-MM-DD"
    hour: int (9–17)
    """
    free = get_free_slots_from_excel(doctor, date_str)
    return hour not in free


def save_appointment(
    name: str,
    disease: str,
    doctor: str,
    preferred_time: str,
    call_sid: str,
) -> None:
    if not os.path.exists(EXCEL_PATH):
        _init_workbook(EXCEL_PATH)

    wb       = load_workbook(EXCEL_PATH)
    ws       = wb["Appointments"]
    next_row = ws.max_row + 1
    serial   = next_row - 1
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row_data = [serial, name, disease, doctor, preferred_time, call_sid, timestamp]
    ws.append(row_data)

    fill = ALT_FILL if serial % 2 == 1 else PatternFill()
    for col_idx, _ in enumerate(row_data, start=1):
        cell           = ws.cell(row=next_row, column=col_idx)
        cell.font      = Font(name="Arial", size=10)
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border    = THIN_BORDER
        if fill:
            cell.fill = fill
    ws.row_dimensions[next_row].height = 18

    wb.save(EXCEL_PATH)
    logger.info(
        f"Saved — Name: {name} | Disease: {disease} | "
        f"Doctor: {doctor} | Time: {preferred_time}"
    )
