#  Hospital AI Voice Assistant

An AI-powered phone receptionist for hospitals.  
When a patient calls your Twilio number, the AI answers, collects their **name**, **symptoms**, and **preferred appointment time** via natural speech — then saves everything to an Excel sheet automatically.

```
Patient calls  →  Twilio  →  ngrok  →  Flask  →  Whisper (OpenAI)  →  Excel
```

---

##  Project Structure

```
hospital-voice-assistant/
│
├── app.py                        # Entry point — starts Flask
├── frontend_api.py               # Dashboard + /api/appointments endpoints
├── app.html                      # Dashboard UI
├── test_call.py                  # Places a test call to TEST_TO_NUMBER
├── start_ngrok.py                # Starts ngrok & auto-updates .env
├── start.sh                      # One-command launcher (ngrok + Flask)
├── requirements.txt
├── .env.example                  # Template — copy to .env
├── .gitignore
│
├── app/
│   ├── __init__.py               # Flask app factory
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── call_handler.py       # Conversation flow (TwiML)
│   │   └── webhook.py            # Status callbacks + health check
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── config.py             # Loads all env vars from .env
│   │   ├── calendar_service.py   # Date parsing, holidays (+ optional Google Calendar)
│   │   ├── whisper_service.py    # OpenAI Whisper transcription
│   │   ├── excel_service.py      # Saves to appointments.xlsx
│   │   └── session_store.py      # In-memory per-call state
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py             # Logging setup
│
├── data/
│   └── appointments.xlsx         # Auto-created on first call
│
└── logs/
    └── app_YYYYMMDD.log          # Daily log files
```

---

## ⚙️ Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.10+ | Runtime | [python.org](https://python.org) |
| ngrok | Expose localhost to Twilio | [ngrok.com](https://ngrok.com) |
| Twilio account | Phone number & call routing | [twilio.com](https://twilio.com) |
| OpenAI account | Whisper transcription | [platform.openai.com](https://platform.openai.com) |

---

##  Setup (Step by Step)

### 1. Clone & Install

```bash
git clone <your-repo>
cd hospital-voice-assistant

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

---

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your real credentials:

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE=+1xxxxxxxxxx

OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

HOSPITAL_NAME=City Care Hospital

EXCEL_FILE_PATH=data/appointments.xlsx
```

> `NGROK_URL` is filled in automatically when you run `start_ngrok.py`.

---

### 3. Install & Authenticate ngrok

```bash
# macOS
brew install ngrok

# Windows / Linux — download from https://ngrok.com/download

# Authenticate (one-time setup)
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

Get your authtoken from: https://dashboard.ngrok.com/get-started/your-authtoken

---

### 4. Start the Application

**Option A — One command (recommended):**
```bash
bash start.sh
```

**Option B — Two terminals:**

Terminal 1 (ngrok):
```bash
python start_ngrok.py
```

Terminal 2 (Flask), after ngrok URL appears:
```bash
python app.py
```

---

### 5. Configure Twilio Webhook

After ngrok starts, you'll see output like:
```
✓  ngrok tunnel active: https://abc123.ngrok-free.app
   Webhook base URL:    https://abc123.ngrok-free.app/incoming-call
```

Go to your **Twilio Console** → Phone Numbers → Your Number → Voice & Fax:

| Field | Value |
|-------|-------|
| **A call comes in** | Webhook |
| **URL** | `https://abc123.ngrok-free.app/incoming-call` |
| **HTTP Method** | `POST` |
| **Call Status Changes** | `https://abc123.ngrok-free.app/call-status` |

Click **Save**.

---

### 6. Test It!

Call your Twilio phone number. The AI will:

1.  **Greet** — "Welcome to City Care Hospital…"
2.  **Ask for name** — records and transcribes with Whisper
3.  **Ask for symptoms** — records and transcribes
4.  **Ask for preferred time** — records and transcribes
5.  **Confirm & hang up** — saves to Excel

Check `data/appointments.xlsx` to see the entry.

---

##  Excel Output

| # | Patient Name | Disease / Symptoms | Doctor Preference | Preferred Time | Call SID | Recorded At |
|---|---|---|---|---|---|---|
| 1 | Rahul Sharma | Fever and headache | Dr. Sharma | Monday, 01 June 2026 at 10:00 AM | CAxxxxx | 2026-05-30 14:32:00 |

---

##  How Whisper Works Here

- Twilio collects the patient's speech via `<Gather input="speech">`
- The `SpeechResult` field (Twilio's basic transcript) is used as a fallback
- When a `RecordingUrl` is available, audio is downloaded and sent to **OpenAI Whisper** (`whisper-1`) for a higher-accuracy transcription
- The best available result is stored in the session

---

## 🔧 Customisation

### Change hospital name
Edit `HOSPITAL_NAME` in `.env`.

### Change AI voice
Edit the `voice=` parameter in `call_handler.py`. Options include:
- `Polly.Aditi` (Indian English — default)
- `Polly.Joanna` (US English)
- `Polly.Amy` (UK English)

### Add more questions
Follow the pattern in `call_handler.py` — each step is a separate route that stores data in `session_store` and redirects to the next step.

---

##  Troubleshooting

| Problem | Fix |
|---------|-----|
| ngrok URL not updating | Run `python start_ngrok.py` manually first |
| Twilio says "Application Error" | Check Flask console for traceback; verify `.env` values |
| Whisper not transcribing | Check `OPENAI_API_KEY`; Twilio recording may not be enabled |
| Excel not created | Ensure `data/` directory exists and is writable |
| Call hangs up immediately | Verify ngrok is running and Twilio webhook URL is correct |

---

##  Security Notes

- Never commit `.env` to git (it's in `.gitignore`)
- ngrok free URLs change every restart — update Twilio webhook each time
- For production, use a fixed domain (ngrok paid plan or a real server)
