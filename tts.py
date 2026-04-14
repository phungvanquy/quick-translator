"""Offline text-to-speech using pyttsx3 (OS-native speech engines)."""

import threading

import pyttsx3

# Module-level lock to prevent overlapping speech
_lock = threading.Lock()
_stop_event = threading.Event()


def speak_text(text: str) -> None:
    """Speak *text* aloud in a background thread (non-blocking).

    If speech is already in progress, the previous utterance is interrupted
    and the new one starts.
    """
    _stop_event.set()  # signal any running speech to stop

    def _speak():
        _stop_event.clear()
        if not _lock.acquire(timeout=2):
            return
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.setProperty("volume", 0.9)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass
        finally:
            _lock.release()

    threading.Thread(target=_speak, daemon=True).start()


def stop_speaking() -> None:
    """Signal any in-progress speech to stop."""
    _stop_event.set()
