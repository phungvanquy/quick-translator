"""Offline text-to-speech using pyttsx3 (OS-native speech engines)."""

import threading

import pyttsx3

_lock = threading.Lock()
_engine_ref: pyttsx3.Engine | None = None
_engine_lock = threading.Lock()


def speak_text(text: str) -> None:
    """Speak *text* aloud in a background thread (non-blocking).

    If speech is already in progress, it is stopped first.
    """
    stop_speaking()

    def _speak():
        global _engine_ref
        if not _lock.acquire(timeout=2):
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 0.9)
            with _engine_lock:
                _engine_ref = engine
            engine.say(text)
            engine.runAndWait()
        except Exception:
            pass
        finally:
            with _engine_lock:
                _engine_ref = None
            _lock.release()

    threading.Thread(target=_speak, daemon=True).start()


def stop_speaking() -> None:
    """Stop any in-progress speech immediately."""
    with _engine_lock:
        engine = _engine_ref
    if engine is not None:
        try:
            engine.stop()
        except Exception:
            pass
