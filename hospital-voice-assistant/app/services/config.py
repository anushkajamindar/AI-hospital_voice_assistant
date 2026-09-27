"""
Configuration
Load from environment variables (.env file).
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── Hospital ───────────────────────────────────────────────────────────────
    HOSPITAL_NAME  = os.environ.get("HOSPITAL_NAME", "City Care Hospital")
    NGROK_URL      = os.environ.get("NGROK_URL", "http://localhost:5000")

    # ── Twilio ─────────────────────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN  = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE       = os.environ.get("TWILIO_PHONE", "")

    # ── Excel ──────────────────────────────────────────────────────────────────
    EXCEL_FILE_PATH = os.environ.get("EXCEL_FILE_PATH", "data/appointments.xlsx")

    # ── Google Calendar ────────────────────────────────────────────────────────
    # Path to Google Service Account JSON file (recommended for production)
    GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json"
    )

    # Map each doctor name → their Google Calendar ID
    # Each doctor must share their calendar with the service account email.
    # Calendar ID format: "doctorname@gmail.com" or the long ID from Google Calendar settings.
    # -- OpenAI
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    DOCTOR_CALENDARS = {
        "Dr. Sharma":  os.environ.get("CAL_DR_SHARMA",  "dr.sharma@citycarehospital.com"),
        "Dr. Mehta":   os.environ.get("CAL_DR_MEHTA",   "dr.mehta@citycarehospital.com"),
        "Dr. Verma":   os.environ.get("CAL_DR_VERMA",   "dr.verma@citycarehospital.com"),
        "Dr. Gupta":   os.environ.get("CAL_DR_GUPTA",   "dr.gupta@citycarehospital.com"),
        "Dr. Khan":    os.environ.get("CAL_DR_KHAN",    "dr.khan@citycarehospital.com"),
        "Dr. Roy":     os.environ.get("CAL_DR_ROY",     "dr.roy@citycarehospital.com"),
        "Dr. Kapoor":  os.environ.get("CAL_DR_KAPOOR",  "dr.kapoor@citycarehospital.com"),
        "Dr. Singh":   os.environ.get("CAL_DR_SINGH",   "dr.singh@citycarehospital.com"),
        "Dr. Bose":    os.environ.get("CAL_DR_BOSE",    "dr.bose@citycarehospital.com"),
        "Dr. Nair":    os.environ.get("CAL_DR_NAIR",    "dr.nair@citycarehospital.com"),
    }