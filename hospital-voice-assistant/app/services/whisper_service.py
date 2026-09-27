"""
Whisper Transcription Service
Downloads audio from Twilio recording URL and transcribes it using OpenAI Whisper.
Prints live speech-to-text output to the terminal during active calls.
"""

import logging
import os
import tempfile
from datetime import datetime
import requests
from openai import OpenAI
from app.services.config import Config

logger = logging.getLogger(__name__)
client = OpenAI(api_key=Config.OPENAI_API_KEY)

# ── Twilio STT lang code → Whisper language code ───────────────────────────
# Twilio uses BCP-47 tags (e.g. "hi-IN"); Whisper uses ISO 639-1 (e.g. "hi")
TWILIO_LANG_TO_WHISPER = {
    "en-IN": "en",
    "hi-IN": "hi",
    "gu-IN": "gu",
    "mr-IN": "mr",
    "kn-IN": "kn",
    "ta-IN": "ta",
    "te-IN": "te",
}

# ── Terminal colour codes ──────────────────────────────────────────────────
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"


def _print_transcript(call_sid: str, step: str, text: str, language: str = "en"):
    """Print a clearly formatted transcript line to the terminal."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    sid_short = call_sid[-6:] if call_sid else "------"
    print(
        f"\n{_BOLD}{_CYAN}┌─ LIVE TRANSCRIPT [{timestamp}] "
        f"Call: ...{sid_short} | Lang: {language}{_RESET}\n"
        f"{_BOLD}{_YELLOW}│  Step : {_RESET}{step}\n"
        f"{_BOLD}{_GREEN}│  Heard: {_RESET}\"{text}\"\n"
        f"{_CYAN}└{'─' * 55}{_RESET}\n",
        flush=True,
    )


def transcribe_from_twilio(
    recording_url: str,
    call_sid: str = "",
    step: str = "unknown",
    twilio_lang: str = "en-IN",
) -> str:
    """
    Downloads a Twilio recording and transcribes it with OpenAI Whisper.
    Prints the result live to the terminal.

    Args:
        recording_url : The Twilio recording URL (without extension)
        call_sid      : CallSid — used to label terminal output
        step          : Name of the call step e.g. 'collect-name', 'collect-disease'
        twilio_lang   : BCP-47 language tag from the caller's session e.g. 'hi-IN'

    Returns:
        Transcribed text string, or empty string on failure
    """
    audio_url     = recording_url + ".mp3"
    whisper_lang  = TWILIO_LANG_TO_WHISPER.get(twilio_lang, "en")

    print(
        f"{_YELLOW}[Whisper] Downloading audio for step '{step}' "
        f"(lang={whisper_lang})...{_RESET}",
        flush=True,
    )

    try:
        response = requests.get(
            audio_url,
            auth=(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN),
            timeout=30,
        )
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=whisper_lang,
            )

        os.unlink(tmp_path)
        transcribed = result.text.strip()

        # ── Print live to terminal ─────────────────────────────────────────
        _print_transcript(call_sid, step, transcribed, twilio_lang)
        logger.info(f"[{call_sid}] step={step} lang={whisper_lang} → '{transcribed}'")

        return transcribed

    except Exception as e:
        print(f"{_RED}[Whisper ERROR] step={step} | {e}{_RESET}", flush=True)
        logger.error(f"Whisper transcription failed (step={step}): {e}")
        return ""


def transcribe_from_file(file_path: str, language: str = "en") -> str:
    """
    Transcribes a local audio file using OpenAI Whisper.
    Useful for testing without Twilio.

    Args:
        file_path : Path to the audio file (.mp3, .wav, .m4a, etc.)
        language  : ISO 639-1 language code e.g. 'hi', 'gu', 'mr'

    Returns:
        Transcribed text string
    """
    try:
        with open(file_path, "rb") as audio_file:
            result = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
            )
        transcribed = result.text.strip()
        print(f"{_GREEN}[Whisper File] '{transcribed}'{_RESET}", flush=True)
        return transcribed
    except Exception as e:
        print(f"{_RED}[Whisper File ERROR] {e}{_RESET}", flush=True)
        logger.error(f"File transcription failed: {e}")
        return ""
