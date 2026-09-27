"""
Session Store
Keeps per-call state (name, disease, time) in memory using CallSid as key.
Thread-safe for use with Flask's development server and gunicorn.
"""

import threading
import logging

logger = logging.getLogger(__name__)


class SessionStore:
    def __init__(self):
        self._store: dict[str, dict] = {}
        self._lock = threading.Lock()

    def set(self, call_sid: str, key: str, value: str):
        with self._lock:
            if call_sid not in self._store:
                self._store[call_sid] = {}
            self._store[call_sid][key] = value
            logger.debug(f"Session [{call_sid}] set {key}='{value}'")

    def get(self, call_sid: str, key: str, default: str = "") -> str:
        with self._lock:
            return self._store.get(call_sid, {}).get(key, default)

    def get_all(self, call_sid: str) -> dict:
        with self._lock:
            return dict(self._store.get(call_sid, {}))

    def clear(self, call_sid: str):
        with self._lock:
            self._store.pop(call_sid, None)
            logger.debug(f"Session [{call_sid}] cleared")


# Singleton — shared across all routes
session_store = SessionStore()
