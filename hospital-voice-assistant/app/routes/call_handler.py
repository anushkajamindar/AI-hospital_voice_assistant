"""
Call Handler Route
Full conversation flow:
  1. Greet → ask name
  2. Ask symptoms/disease
  3. Show matched doctors → ask doctor preference
  4. Ask appointment date → check Excel for availability on that date
     - If doctor fully booked that day → ask for another date
  5. Read out free time slots → ask preferred time
     - If slot taken → ask again from remaining free slots
  6. Confirm → book (save to Excel) → goodbye

Availability is checked entirely from the Excel sheet.
No Google Calendar required.
"""

import re
import logging
from flask import Blueprint, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from app.services.config import Config

logger = logging.getLogger(__name__)

call_bp = Blueprint("call", __name__)

HOSPITAL_NAME = Config.HOSPITAL_NAME

# ── Language configuration ─────────────────────────────────────────────────
# Each language defines: voice, TTS lang code, and all spoken prompts
LANGUAGE_CONFIG = {
    "1": {
        "voice":   "Polly.Aditi",
        "lang":    "en-IN",
        "name":    "English",
        "prompts": {
            "welcome":          "Hello and welcome to {{hospital}}. We are here to assist you 24 hours a day, 7 days a week. To get started, could you please tell us your full name?",
            "ask_symptoms":     "Please describe your symptoms or the health concern you are experiencing today.",
            "doctors_one":      "Based on your symptoms, we recommend {{doctors}}. Please say yes to confirm, or tell us another preference.",
            "doctors_many":     "Based on your symptoms, we have the following doctors available: {{doctors}}. Please say the name of the doctor you would prefer.",
            "ask_date":         "We have noted your preference for {{doctor}}. Please tell us your preferred appointment date. For example, you may say tomorrow, this Friday, or the 5th of June.",
            "bad_date":         "Sorry, I could not understand that date. Please say a date like tomorrow, this Saturday, or the 10th of June.",
            "blocked_day":      "I am sorry, the hospital is closed on {{date}} as it is {{reason}}. Doctors are not available. Could you please suggest a weekday?",
            "fully_booked":     "I am sorry, {{doctor}} is fully booked on {{date}}. Could you please suggest another date?",
            "ask_time":         "Great. {{doctor}} is available on {{date}}. The available time slots are: {{slots}}. Which time would you prefer?",
            "bad_time":         "Sorry, I did not catch that time. The available slots are: {{slots}}. Please say one of these times.",
            "slot_unavailable": "I am sorry, {{time}} is not available on that date. The available times are: {{slots}}. Please choose one of these.",
            "slot_just_taken":  "I am sorry, the {{time}} slot was just taken. The remaining available slots are: {{slots}}. Please choose another time.",
            "all_slots_gone":   "I am sorry, all slots for {{doctor}} on {{date}} are now fully booked. Please call back to choose another date. Thank you for contacting us. Goodbye!",
            "confirmed":        "Wonderful{{name}}. Your appointment with {{doctor}} has been confirmed for {{date}} at {{time}} at {{hospital}}. Our team will send you a reminder before your visit. Please carry any previous medical reports with you. We wish you good health. Thank you for calling. Goodbye!",
            "thank_you":        "Thank you,",
        },
    },
    "2": {
        "voice":   "Polly.Aditi",
        "lang":    "hi-IN",
        "name":    "Hindi",
        "prompts": {
            "welcome":          "Namaste aur {{hospital}} mein aapka swagat hai. Hum aapki seva ke liye 24 ghante, 7 din uplabdh hain. Shuru karne ke liye, kripya apna poora naam batayein.",
            "ask_symptoms":     "Kripya apne lakshan ya aaj aap jo swasthya samasya anubhav kar rahe hain, woh batayein.",
            "doctors_one":      "Aapke lakshano ke aadhar par, hum {{doctors}} ki salah dete hain. Hamare liye haan kahein ya koi aur pasand batayein.",
            "doctors_many":     "Aapke lakshano ke aadhar par, hamare paas yeh doctors uplabdh hain: {{doctors}}. Kripya us doctor ka naam kahein jise aap pasand karein.",
            "ask_date":         "Humne {{doctor}} ki aapki pasand note kar li hai. Kripya apni pasandida appointment ki taareekh batayein. Udaharan ke liye, aap kal, is Shukravar, ya 5 June keh sakte hain.",
            "bad_date":         "Maafi chahte hain, woh taareekh samajh nahi aayi. Kripya kal, is Shanivaar, ya 10 June jaisi taareekh batayein.",
            "blocked_day":      "Khed hai, {{date}} ko hospital band hai kyunki woh {{reason}} hai. Doctors uplabdh nahi hain. Kripya koi weekday batayein?",
            "fully_booked":     "Maafi chahte hain, {{doctor}} {{date}} ko puri tarah se booked hain. Kripya koi aur taareekh bataein?",
            "ask_time":         "Bahut accha. {{doctor}} {{date}} ko uplabdh hain. Uplabdh samay slots hain: {{slots}}. Aap kaunsa samay chahenge?",
            "bad_time":         "Maafi chahte hain, woh samay samajh nahi aaya. Uplabdh slots hain: {{slots}}. Kripya inme se koi ek samay kahein.",
            "slot_unavailable": "Khed hai, {{time}} us taareekh ko uplabdh nahi hai. Uplabdh samay hain: {{slots}}. Kripya inme se chunein.",
            "slot_just_taken":  "Khed hai, {{time}} slot abhi kisi ne le liya. Shesh uplabdh slots hain: {{slots}}. Kripya koi aur samay chunein.",
            "all_slots_gone":   "Khed hai, {{doctor}} ke sabhi slots {{date}} ke liye bhar gaye hain. Kripya doosri taareekh chunne ke liye wapas call karein. Dhanyavad. Alvida!",
            "confirmed":        "Bahut accha{{name}}. {{doctor}} ke saath aapki appointment {{date}} ko {{time}} baje {{hospital}} mein confirm ho gayi hai. Hamari team aapke daurse pehle reminder bhejegi. Kripya apne poorane medical reports saath laayein. Hum aapke swasthya ki kamna karte hain. Call karne ke liye dhanyavad. Alvida!",
            "thank_you":        "Dhanyavad,",
        },
    },
    "3": {
        "voice":   "Polly.Aditi",
        "lang":    "gu-IN",
        "name":    "Gujarati",
        "prompts": {
            "welcome":          "Namaste ane {{hospital}} ma aapnu swagat che. Ame 24 kaak, 7 divas aapni seva mate hajir chhiye. Sharu karva mate, krupa kari ne aapnu puru naam janavao.",
            "ask_symptoms":     "Krupa kari ne aapna lakshano athva aaj aap je swasthya samasya anubhav kari raha cho te janavao.",
            "doctors_one":      "Aapna lakshano na aadhar par, ame {{doctors}} ni salah aapiye chhiye. Confirm karva mate haa kaho athva biji pasand janavo.",
            "doctors_many":     "Aapna lakshano na aadhar par, amara daktar uplabdh chhe: {{doctors}}. Krupa kari ne je daktar ne aap pasand karo tena naam kaho.",
            "ask_date":         "Amne {{doctor}} ni aapni pasand nondh lai lidhi chhe. Krupa kari ne aapni pasandida appointment ni tarikH janavao. Udaharan tarike, aap kal, aa Shukravar, athva 5 June kahi shakao chho.",
            "bad_date":         "Maafi mangiye chhiye, peli tarikH samjhayi nahi. Krupa kari ne kal, aa Shanivaar, athva 10 June jevi tarikH janavao.",
            "blocked_day":      "Khed chhe, {{date}} na roje hospital band chhe karan ke e {{reason}} chhe. Doctors uplabdh nathi. Krupa kari ne koi weekday janavao?",
            "fully_booked":     "Maafi mangiye chhiye, {{doctor}} {{date}} na roje pura booked chhe. Shu aap biji koi tarikh suchavi shako?",
            "ask_time":         "Khub saaru. {{doctor}} {{date}} na roje uplabdh chhe. Uplabdh samay slots chhe: {{slots}}. Aap kayo samay pasand karishO?",
            "bad_time":         "Maafi mangiye chhiye, pelo samay samjhayo nahi. Uplabdh slots chhe: {{slots}}. Krupa kari ne inman thi koi ek samay kaho.",
            "slot_unavailable": "Khed chhe, {{time}} e tarikhe uplabdh nathi. Uplabdh samay chhe: {{slots}}. Krupa kari ne inman thi pasand karo.",
            "slot_just_taken":  "Khed chhe, {{time}} slot haju j koine mali gayu. Baki uplabdh slots chhe: {{slots}}. Krupa kari ne bijo samay pasand karo.",
            "all_slots_gone":   "Khed chhe, {{doctor}} na badha slots {{date}} mate bhari gaya chhe. Krupa kari ne biji tarikH pasand karva wapas call karo. Aabhar. Alvida!",
            "confirmed":        "Khub saaru{{name}}. {{doctor}} saathe aapni appointment {{date}} na roje {{time}} vage {{hospital}} ma confirm thai gayi chhe. Amari team aapne yaad apavse. Krupa kari ne aapna purana medical reports saath laavo. Aapni tabiati saari rahe tevi shubhechha. Call karava badal aabhar. Alvida!",
            "thank_you":        "Aabhar,",
        },
    },
    "4": {
        "voice":   "Polly.Aditi",
        "lang":    "mr-IN",
        "name":    "Marathi",
        "prompts": {
            "welcome":          "Namaskar ani {{hospital}} madhe aaple swagat ahe. Aapli seva karnyasathi aamhi 24 taas, 7 divas uplabdh aahot. Suruwat karnyasathi, krupa karun aapale poorna naav sangaa.",
            "ask_symptoms":     "Krupa karun aapale lakshane kinva aaj aapan anubhavet asalelya arogyavishayi samasya sangaa.",
            "doctors_one":      "Aapaly a lakshananusaar, aamhi {{doctors}} chi shifaaris karto. Confirm karnyasathi hoy mhana kinva dusari pasant sangaa.",
            "doctors_many":     "Aapaly a lakshananusaar, khaalil daktar uplabdh aahet: {{doctors}}. Krupa karun je daktar aapnaas pasant aahe tyanche naav sangaa.",
            "ask_date":         "Aamhi {{doctor}} sathi aapali pasant nondh keyli ahe. Krupa karun aapali ishtanusaar appointment chi tarik sangaa. Udaharanasathi, aap udyaa, ya Shukrawaree, kinva 5 June mhanu shaktat.",
            "bad_date":         "Maafi asat, ti tarik samajali nahi. Krupa karun udyaa, ya Shaniwaaree, kinva 10 June ashlya tarika sangaa.",
            "blocked_day":      "Kshama asaa, {{date}} la hospital band ahe karan to {{reason}} ahe. Daktar uplabdh naahit. Krupa karun koi weekday sangaal kaay?",
            "fully_booked":     "Maafi asat, {{doctor}} {{date}} la purne booked aahet. Krupa karun dusari tarik suchvaal kaay?",
            "ask_time":         "Chhan. {{doctor}} {{date}} la uplabdh aahet. Uplabdh vel slots aahet: {{slots}}. Aapnaas konata vel pasant aahe?",
            "bad_time":         "Maafi asat, to vel samajala nahi. Uplabdh slots aahet: {{slots}}. Krupa karun yateel ek vel sangaa.",
            "slot_unavailable": "Khed vatat, {{time}} tya tarikhela uplabdh nahi. Uplabdh vel aahet: {{slots}}. Krupa karun yatun nivdaa.",
            "slot_just_taken":  "Khed vatat, {{time}} slot aataach kuni gheetlaa. Uralele uplabdh slots aahet: {{slots}}. Krupa karun dusara vel nivdaa.",
            "all_slots_gone":   "Khed vatat, {{doctor}} che sarve slots {{date}} sathi bharlele aahet. Krupa karun dusari tarik nivadnyasathi parat call karaa. Dhanyawaad. Namaskar!",
            "confirmed":        "Khoop chhan{{name}}. {{doctor}} sobat aapali appointment {{date}} la {{time}} vajata {{hospital}} madhye confirm zali aahe. Aamchi team aapnaas athwan karun denaar. Krupa karun aapale junhe medical reports sobat aanaa. Aapale arogya changale rahot ashi shubhechha. Call kely a badal dhanyawaad. Namaskar!",
            "thank_you":        "Dhanyawaad,",
        },
    },
    "5": {
        "voice":   "Polly.Aditi",
        "lang":    "kn-IN",
        "name":    "Kannada",
        "prompts": {
            "welcome":          "Namaskara mattu {{hospital}} ge svagata. Naavu nimma seva gagi 24 ganTe, vaaram 7 dina iddeeve. PraramBhisalu, dayavittu nimma hoLa hesaru heliri.",
            "ask_symptoms":     "Dayavittu nimma lakshaNagaLu athava iidu nimma aarogya samasye enbadannu heliri.",
            "doctors_one":      "Nimma lakshaNagaLa aadharadalli, naavu {{doctors}} annu sUchisutteve. DhruDhapaDisu houdhu enniri athava bere aaDa heliri.",
            "doctors_many":     "Nimma lakshaNagaLa aadharadalli, ee doctors laByaviddarE: {{doctors}}. Dayavittu nimagu iShTapaaTTa doctor avara hesaru heliri.",
            "ask_date":         "Naavu {{doctor}} gagi nimma aaDa nondhaayisiddeeve. Dayavittu nimma iShTapaaTTa appointment dhinaankavanu heliri. UdaaharaNakke, naaleya, ee Shukravaar, athava 5 June ennabahudhu.",
            "bad_date":         "KshaMisi, aa dhinaanka Arthaavaagalilla. Dayavittu naaleya, ee Shanivaar, athava 10 June nantaha dhinaanka heliri.",
            "blocked_day":      "Kshamisiri, {{date}} nandu hospital mUDidhe, {{reason}} iruvatarinda. Doctors laByavillA. Dayavittu ondu weekday heliri?",
            "fully_booked":     "Kshamisiri, {{doctor}} {{date}} nanu poorNavaagi book aagiddarE. DayavitTu inna ondu dhinaanka sUchisuveera?",
            "ask_time":         "Tumba chennagide. {{doctor}} {{date}} nandu laByaviddarE. LaByavirukka samaya slots: {{slots}}. Nimagu yaava samaya iShTa?",
            "bad_time":         "Kshamisiri, aa samaya Arthaavaagalilla. LaByavirukka slots: {{slots}}. Dayavittu ivan alli ondu samaya heliri.",
            "slot_unavailable": "Vaiyataapaada, {{time}} aa dinada nanu laByavillA. LaByavirukka samaya: {{slots}}. Dayavittu ivan alli arisiri.",
            "slot_just_taken":  "Vaiyataapaada, {{time}} slot ippataane yaarigoo doridhu. Uuridirukka laByairukka slots: {{slots}}. Dayavittu inna samaya arisiri.",
            "all_slots_gone":   "Vaiyataapaada, {{doctor}} avara ella slots {{date}} gagi thumbidE. Inna dinaamka arisalu dayavittu tiLisi call maaDispiri. DhanyavadagaLu. Namaskara!",
            "confirmed":        "Tumba chennagide{{name}}. {{doctor}} avara jote nimma appointment {{date}} nandu {{time}} gante {{hospital}} nalli dhruDhapaTTidE. Naama nimma bheatikku mundhe nyapisikeetteve. Dayavittu nimma haLe medical reports jote taanni. Nimma aarogya chennagirali enna haardika shubhaashayagaLu. Call maaDistadakke dhanyavadagaLu. Namaskara!",
            "thank_you":        "DhanyavadagaLu,",
        },
    },
}

def _get_lang_cfg(call_sid):
    """Return language config dict for this call. Defaults to English."""
    from app.services.session_store import session_store
    lang_key = session_store.get(call_sid, "language") or "1"
    return LANGUAGE_CONFIG.get(lang_key, LANGUAGE_CONFIG["1"])

# ── Doctor database ────────────────────────────────────────────────────────
DOCTORS = {
    "Dr. Sharma":  {"specialty": "General Physician",   "keywords": ["fever", "cold", "headache", "flu", "cough", "weakness"]},
    "Dr. Mehta":   {"specialty": "General Physician",   "keywords": ["cold", "fever", "body ache", "throat", "running nose"]},
    "Dr. Verma":   {"specialty": "Cardiologist",        "keywords": ["heart", "chest pain", "palpitation", "blood pressure", "bp"]},
    "Dr. Gupta":   {"specialty": "Cardiologist",        "keywords": ["heart", "cardiac", "chest", "shortness of breath"]},
    "Dr. Khan":    {"specialty": "Dermatologist",       "keywords": ["skin", "rash", "acne", "allergy", "itching", "eczema"]},
    "Dr. Roy":     {"specialty": "Dermatologist",       "keywords": ["skin", "hair", "nail", "fungal", "psoriasis"]},
    "Dr. Kapoor":  {"specialty": "Orthopedic Surgeon",  "keywords": ["back", "joint", "knee", "spine", "bone", "fracture"]},
    "Dr. Singh":   {"specialty": "Ophthalmologist",     "keywords": ["eye", "vision", "sight", "blur", "cataract", "glasses"]},
    "Dr. Bose":    {"specialty": "ENT Specialist",      "keywords": ["ear", "nose", "throat", "hearing", "tonsil", "sinus"]},
    "Dr. Nair":    {"specialty": "Neurologist",         "keywords": ["neuro", "migraine", "seizure", "memory", "dizziness"]},
}

# ── Time slot mappings ─────────────────────────────────────────────────────
SLOT_HOURS = {
    "9": 9, "9am": 9, "nine": 9, "09:00": 9, "9:00": 9,
    "10": 10, "10am": 10, "ten": 10, "10:00": 10,
    "11": 11, "11am": 11, "eleven": 11, "11:00": 11,
    "12": 12, "12pm": 12, "twelve": 12, "noon": 12, "12:00": 12,
    "1": 13, "1pm": 13, "one": 13, "13:00": 13,
    "2": 14, "2pm": 14, "two": 14, "14:00": 14,
    "3": 15, "3pm": 15, "three": 15, "15:00": 15,
    "4": 16, "4pm": 16, "four": 16, "16:00": 16,
    "5": 17, "5pm": 17, "five": 17, "17:00": 17,
}

SLOT_DISPLAY = {
    9: "9:00 AM", 10: "10:00 AM", 11: "11:00 AM", 12: "12:00 PM",
    13: "1:00 PM", 14: "2:00 PM", 15: "3:00 PM", 16: "4:00 PM", 17: "5:00 PM"
}


def _base_url():
    return Config.NGROK_URL.rstrip("/")


def _send_booking_sms(
    to_number: str,
    patient_name: str,
    doctor: str,
    date_display: str,
    slot_display: str,
) -> None:
    """
    Sends a WhatsApp/SMS confirmation message to the patient after booking.
    Uses Twilio. Silently logs errors so the call flow is never interrupted.
    """
    try:
        from twilio.rest import Client
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)

        name_part = patient_name if patient_name else "Patient"
        message_body = (
            f"Dear {name_part},\n\n"
            f"Thank you for contacting {HOSPITAL_NAME}. 🏥\n\n"
            f"Your appointment has been confirmed:\n"
            f"👨‍⚕️ Doctor : {doctor}\n"
            f"📅 Date   : {date_display}\n"
            f"⏰ Time   : {slot_display}\n\n"
            f"Please carry any previous medical reports with you.\n\n"
            f"We wish you good health!\n"
            f"— {HOSPITAL_NAME}"
        )

        # ── Send as plain SMS ─────────────────────────────────────────────
        from_number = Config.TWILIO_PHONE

        msg = client.messages.create(
            body  = message_body,
            from_ = from_number,
            to    = to_number,
        )
        logger.info(f"Booking SMS sent → SID: {msg.sid} | To: {to_number}")

    except Exception as e:
        logger.error(f"[SMS] Failed to send booking confirmation: {e}")


def _transcribe(req, step: str = "unknown"):
    """
    Extract speech from the Twilio request.
    - Prefers Twilio's own SpeechResult (fast, no extra cost).
    - Falls back to Whisper for recording-based transcription.
    Always prints a live transcript to the terminal.
    """
    from app.services.session_store import session_store

    call_sid      = req.form.get("CallSid", "")
    speech_result = req.form.get("SpeechResult", "").strip()

    # ── Twilio STT result (from <Gather input="speech">) ──────────────────
    if speech_result:
        # Get language for display only (no Whisper needed)
        lang_key    = session_store.get(call_sid, "language") or "1"
        cfg         = LANGUAGE_CONFIG.get(lang_key, LANGUAGE_CONFIG["1"])
        twilio_lang = cfg["lang"]

        from app.services.whisper_service import _print_transcript
        _print_transcript(call_sid, step, speech_result, twilio_lang)
        return speech_result

    # ── Whisper fallback (from <Record>) ──────────────────────────────────
    recording_url = req.form.get("RecordingUrl", "")
    if recording_url:
        try:
            from app.services.whisper_service import transcribe_from_twilio
            lang_key    = session_store.get(call_sid, "language") or "1"
            cfg         = LANGUAGE_CONFIG.get(lang_key, LANGUAGE_CONFIG["1"])
            twilio_lang = cfg["lang"]
            return transcribe_from_twilio(
                recording_url,
                call_sid=call_sid,
                step=step,
                twilio_lang=twilio_lang,
            ) or ""
        except Exception:
            pass
    return ""


def _parse_time(time_str: str):
    """
    Returns the hour (int, 24h) if the spoken time matches a valid slot.
    FIX: Uses word-boundary regex to avoid false matches like
         'one' inside 'phone', 'two' inside 'twenty-two', etc.
    """
    t = time_str.lower().strip()
    t = t.replace("o'clock", "").replace("o clock", "").replace(".", "").replace(",", "")
    # Note: we keep spaces so word boundaries work correctly
    for key, hour in SLOT_HOURS.items():
        # Use word boundary matching to avoid false positives
        if re.search(rf'\b{re.escape(key)}\b', t):
            return hour
    return None


def _match_doctors(disease: str) -> list:
    disease_lower = disease.lower()
    matched = []
    for name, info in DOCTORS.items():
        for kw in info["keywords"]:
            if kw in disease_lower:
                matched.append(name)
                break
    if not matched:
        matched = ["Dr. Sharma", "Dr. Mehta"]
    return list(dict.fromkeys(matched))[:3]


# ─────────────────────────────────────────────────────────────
# STEP 1 — Incoming call: language selection
# ─────────────────────────────────────────────────────────────
@call_bp.route("/incoming-call", methods=["POST"])
def incoming_call():
    resp = VoiceResponse()
    gather = Gather(
        input="dtmf",                        # keypad input (1 / 2 / 3 / #)
        num_digits=1,
        action=f"{_base_url()}/select-language",
        method="POST",
        timeout=8,
        finish_on_key="",                    # don't stop on #; handle it ourselves
    )
    gather.say(
        f"Hello and welcome to {HOSPITAL_NAME}. "
        "For English, press 1. "
        "Hindi ke liye, 2 dabaiye. "
        "Gujarati mate, 3 dabavo. "
        "Marathi sathi, 4 dabaa. "
        "Kannada ge, 5 goLisi. "
        "Is sandesh ko dobara sunne ke liye, hash dabaiye.",
        voice="Polly.Aditi",
        language="en-IN",
    )
    resp.append(gather)
    # No input → repeat
    resp.redirect(f"{_base_url()}/incoming-call", method="POST")
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# STEP 1b — Handle language key press
# ─────────────────────────────────────────────────────────────
@call_bp.route("/select-language", methods=["POST"])
def select_language():
    from app.services.session_store import session_store

    call_sid = request.form.get("CallSid", "")
    digit    = request.form.get("Digits", "").strip()

    if digit == "#":
        # Replay the language menu
        resp = VoiceResponse()
        resp.redirect(f"{_base_url()}/incoming-call", method="POST")
        return str(resp), 200, {"Content-Type": "text/xml"}

    if digit not in LANGUAGE_CONFIG:
        # Invalid key → replay menu
        resp = VoiceResponse()
        resp.say("Invalid option.", voice="Polly.Aditi", language="en-IN")
        resp.redirect(f"{_base_url()}/incoming-call", method="POST")
        return str(resp), 200, {"Content-Type": "text/xml"}

    # Save language choice and proceed to name collection
    session_store.set(call_sid, "language", digit)
    session_store.set(call_sid, "caller_number", request.form.get("From", ""))
    cfg = LANGUAGE_CONFIG[digit]

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{_base_url()}/collect-name",
        method="POST",
        speech_timeout="auto",
        language=cfg["lang"],
    )
    gather.say(
        cfg["prompts"]["welcome"].replace("{{hospital}}", HOSPITAL_NAME),
        voice=cfg["voice"],
        language=cfg["lang"],
    )
    resp.append(gather)
    resp.redirect(f"{_base_url()}/collect-name", method="POST")
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# STEP 2 — Collect name → ask symptoms
# ─────────────────────────────────────────────────────────────
@call_bp.route("/collect-name", methods=["POST"])
def collect_name():
    from app.services.session_store import session_store

    call_sid     = request.form.get("CallSid", "")
    patient_name = _transcribe(request, step="collect-name") or "there"
    session_store.set(call_sid, "name", patient_name)

    cfg = _get_lang_cfg(call_sid)
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{_base_url()}/collect-disease",
        method="POST",
        speech_timeout="auto",
        language=cfg["lang"],
    )
    gather.say(
        f"{cfg['prompts']['thank_you']} {patient_name}. "
        + cfg["prompts"]["ask_symptoms"],
        voice=cfg["voice"],
        language=cfg["lang"],
    )
    resp.append(gather)
    resp.redirect(f"{_base_url()}/collect-disease", method="POST")
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# STEP 3 — Collect disease → suggest doctors → ask preference
# ─────────────────────────────────────────────────────────────
@call_bp.route("/collect-disease", methods=["POST"])
def collect_disease():
    from app.services.session_store import session_store

    call_sid = request.form.get("CallSid", "")
    disease  = _transcribe(request, step="collect-disease") or "Not specified"
    session_store.set(call_sid, "disease", disease)

    matched = _match_doctors(disease)
    session_store.set(call_sid, "matched_doctors", ",".join(matched))

    doctor_intros = []
    for name in matched:
        spec = DOCTORS.get(name, {}).get("specialty", "Specialist")
        doctor_intros.append(f"{name}, our {spec}")

    cfg = _get_lang_cfg(call_sid)
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{_base_url()}/collect-doctor",
        method="POST",
        speech_timeout="auto",
        language=cfg["lang"],
    )

    if len(matched) == 1:
        text = cfg["prompts"]["doctors_one"].replace("{{doctors}}", doctor_intros[0])
    else:
        intro_text = "; ".join(doctor_intros[:-1]) + f"; and {doctor_intros[-1]}"
        text = cfg["prompts"]["doctors_many"].replace("{{doctors}}", intro_text)

    gather.say(text, voice=cfg["voice"], language=cfg["lang"])
    resp.append(gather)
    resp.redirect(f"{_base_url()}/collect-doctor", method="POST")
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# STEP 4 — Collect doctor → ask appointment date
# ─────────────────────────────────────────────────────────────
@call_bp.route("/collect-doctor", methods=["POST"])
def collect_doctor():
    from app.services.session_store import session_store

    call_sid = request.form.get("CallSid", "")
    spoken   = _transcribe(request, step="collect-doctor").strip()

    doctor = None
    data   = session_store.get_all(call_sid)
    matched_doctors = data.get("matched_doctors", "").split(",")

    spoken_lower = spoken.lower()
    for name in matched_doctors:
        if name.lower().split(".")[-1].strip() in spoken_lower or name.lower() in spoken_lower:
            doctor = name
            break

    if not doctor and ("yes" in spoken_lower) and len(matched_doctors) == 1:
        doctor = matched_doctors[0]

    if not doctor:
        for name in DOCTORS:
            if name.lower().split(".")[-1].strip() in spoken_lower:
                doctor = name
                break

    if not doctor:
        doctor = matched_doctors[0] if matched_doctors else "Dr. Sharma"

    session_store.set(call_sid, "doctor", doctor)

    cfg = _get_lang_cfg(call_sid)
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{_base_url()}/collect-date",
        method="POST",
        speech_timeout="auto",
        language=cfg["lang"],
    )
    text = cfg["prompts"]["ask_date"].replace("{{doctor}}", doctor)
    gather.say(text, voice=cfg["voice"], language=cfg["lang"])
    resp.append(gather)
    resp.redirect(f"{_base_url()}/collect-date", method="POST")
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# STEP 5 — Collect date → check Excel availability → ask time
# ─────────────────────────────────────────────────────────────
@call_bp.route("/collect-date", methods=["POST"])
def collect_date():
    from app.services.session_store import session_store
    from app.services.calendar_service import parse_date_string, DateRejected
    from app.services.excel_service import get_free_slots_from_excel

    call_sid = request.form.get("CallSid", "")
    date_str = _transcribe(request, step="collect-date") or ""
    data     = session_store.get_all(call_sid)
    doctor   = data.get("doctor", "Dr. Sharma")
    cfg      = _get_lang_cfg(call_sid)

    parsed_date = parse_date_string(date_str)

    # ── Could not understand the date at all ──────────────────────────────
    if parsed_date is None:
        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{_base_url()}/collect-date",
            method="POST",
            speech_timeout="auto",
            language=cfg["lang"],
        )
        gather.say(cfg["prompts"]["bad_date"], voice=cfg["voice"], language=cfg["lang"])
        resp.append(gather)
        resp.redirect(f"{_base_url()}/collect-date", method="POST")
        return str(resp), 200, {"Content-Type": "text/xml"}

    # ── Date is a weekend or public holiday ───────────────────────────────
    if isinstance(parsed_date, DateRejected):
        date_label = parsed_date.date.strftime("%A, %d %B")  # e.g. "Sunday, 15 June"
        reason     = parsed_date.reason                       # e.g. "Sunday" or "Republic Day"
        print(
            f"\033[93m[Holiday Block] {date_label} is blocked: {reason}\033[0m",
            flush=True,
        )
        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{_base_url()}/collect-date",
            method="POST",
            speech_timeout="auto",
            language=cfg["lang"],
        )
        text = (cfg["prompts"]["blocked_day"]
                .replace("{{date}}", date_label)
                .replace("{{reason}}", reason))
        gather.say(text, voice=cfg["voice"], language=cfg["lang"])
        resp.append(gather)
        resp.redirect(f"{_base_url()}/collect-date", method="POST")
        return str(resp), 200, {"Content-Type": "text/xml"}

    date_iso     = parsed_date.strftime("%Y-%m-%d")
    date_display = parsed_date.strftime("%A, %d %B %Y")

    free_slots = get_free_slots_from_excel(doctor, date_iso)

    if not free_slots:
        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{_base_url()}/collect-date",
            method="POST",
            speech_timeout="auto",
            language=cfg["lang"],
        )
        text = (cfg["prompts"]["fully_booked"]
                .replace("{{doctor}}", doctor)
                .replace("{{date}}", parsed_date.strftime("%A, %d %B")))
        gather.say(text, voice=cfg["voice"], language=cfg["lang"])
        resp.append(gather)
        return str(resp), 200, {"Content-Type": "text/xml"}

    session_store.set(call_sid, "date",         date_iso)
    session_store.set(call_sid, "date_display", date_display)
    session_store.set(call_sid, "free_slots",   ",".join(str(h) for h in free_slots))

    slots_display = ", ".join(SLOT_DISPLAY[h] for h in free_slots)

    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        action=f"{_base_url()}/collect-time",
        method="POST",
        speech_timeout="auto",
        language=cfg["lang"],
    )
    text = (cfg["prompts"]["ask_time"]
            .replace("{{doctor}}", doctor)
            .replace("{{date}}", parsed_date.strftime("%A, %d %B"))
            .replace("{{slots}}", slots_display))
    gather.say(text, voice=cfg["voice"], language=cfg["lang"])
    resp.append(gather)
    resp.redirect(f"{_base_url()}/collect-time", method="POST")
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# STEP 6 — Collect time → verify slot → book or retry
# ─────────────────────────────────────────────────────────────
@call_bp.route("/collect-time", methods=["POST"])
def collect_time():
    from app.services.session_store import session_store
    from app.services.excel_service import save_appointment, is_slot_taken

    call_sid       = request.form.get("CallSid", "")
    preferred_time = _transcribe(request, step="collect-time") or ""
    data           = session_store.get_all(call_sid)
    doctor         = data.get("doctor", "Dr. Sharma")
    date_iso       = data.get("date", "")
    date_display   = data.get("date_display", date_iso)
    cfg            = _get_lang_cfg(call_sid)

    free_hours = []
    free_slots_str = data.get("free_slots", "")
    if free_slots_str:
        try:
            free_hours = [int(h) for h in free_slots_str.split(",") if h.strip()]
        except ValueError:
            pass

    hour = _parse_time(preferred_time)

    if hour is None:
        available_display = ", ".join(SLOT_DISPLAY[h] for h in (free_hours or list(SLOT_DISPLAY.keys())))
        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{_base_url()}/collect-time",
            method="POST",
            speech_timeout="auto",
            language=cfg["lang"],
        )
        text = cfg["prompts"]["bad_time"].replace("{{slots}}", available_display)
        gather.say(text, voice=cfg["voice"], language=cfg["lang"])
        resp.append(gather)
        return str(resp), 200, {"Content-Type": "text/xml"}

    if free_hours and hour not in free_hours:
        available_display = ", ".join(SLOT_DISPLAY[h] for h in free_hours)
        resp = VoiceResponse()
        gather = Gather(
            input="speech",
            action=f"{_base_url()}/collect-time",
            method="POST",
            speech_timeout="auto",
            language=cfg["lang"],
        )
        text = (cfg["prompts"]["slot_unavailable"]
                .replace("{{time}}", SLOT_DISPLAY.get(hour, preferred_time))
                .replace("{{slots}}", available_display))
        gather.say(text, voice=cfg["voice"], language=cfg["lang"])
        resp.append(gather)
        return str(resp), 200, {"Content-Type": "text/xml"}

    if date_iso and is_slot_taken(doctor, date_iso, hour):
        remaining = [h for h in free_hours if h != hour]
        session_store.set(call_sid, "free_slots", ",".join(str(h) for h in remaining))

        if remaining:
            available_display = ", ".join(SLOT_DISPLAY[h] for h in remaining)
            resp = VoiceResponse()
            gather = Gather(
                input="speech",
                action=f"{_base_url()}/collect-time",
                method="POST",
                speech_timeout="auto",
                language=cfg["lang"],
            )
            text = (cfg["prompts"]["slot_just_taken"]
                    .replace("{{time}}", SLOT_DISPLAY.get(hour, ""))
                    .replace("{{slots}}", available_display))
            gather.say(text, voice=cfg["voice"], language=cfg["lang"])
            resp.append(gather)
        else:
            resp = VoiceResponse()
            text = (cfg["prompts"]["all_slots_gone"]
                    .replace("{{doctor}}", doctor)
                    .replace("{{date}}", date_display))
            resp.say(text, voice=cfg["voice"], language=cfg["lang"])
            resp.hangup()
        return str(resp), 200, {"Content-Type": "text/xml"}

    slot_display = SLOT_DISPLAY.get(hour, preferred_time)
    patient_name = data.get("name", "")
    disease      = data.get("disease", "Not specified")

    try:
        save_appointment(
            name           = patient_name,
            disease        = disease,
            doctor         = doctor,
            preferred_time = f"{date_display} at {slot_display}",
            call_sid       = call_sid,
        )
    except Exception as e:
        print(f"[ERROR] Excel save failed: {e}")

    # ── Send SMS confirmation to patient ──────────────────────────────────
    patient_phone = request.form.get("From", "")
    _send_booking_sms(
        to_number    = patient_phone,
        patient_name = patient_name,
        doctor       = doctor,
        date_display = date_display,
        slot_display = slot_display,
    )

    session_store.clear(call_sid)

    resp = VoiceResponse()
    name_part = f", {patient_name}" if patient_name else ""
    text = (cfg["prompts"]["confirmed"]
            .replace("{{name}}", name_part)
            .replace("{{doctor}}", doctor)
            .replace("{{date}}", date_display)
            .replace("{{time}}", slot_display)
            .replace("{{hospital}}", HOSPITAL_NAME))
    resp.say(text, voice=cfg["voice"], language=cfg["lang"])
    resp.hangup()
    return str(resp), 200, {"Content-Type": "text/xml"}


# ─────────────────────────────────────────────────────────────
# Debug endpoint
# ─────────────────────────────────────────────────────────────
@call_bp.route("/debug", methods=["GET"])
def debug():
    return f"OK - Flask running | NGROK: {_base_url()}", 200
