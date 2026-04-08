"""Hotkey engine for Quick Translator.

Ctrl+C+C      → translate selected text
Ctrl+C+Space  → chat about selected text
"""

import threading
import time

import keyboard


# ── Combo state ──────────────────────────────────────────────────────────────
_last_ctrl_c_time = 0.0
_waiting_for_combo = False
_last_trigger_time = 0.0
_trigger_lock = threading.Lock()
_combo_timer: threading.Timer | None = None


def _reset_combo():
    global _waiting_for_combo
    _waiting_for_combo = False


def _make_on_press(handle_translate, handle_chat):
    """Return an on_press callback wired to the given handler functions."""

    def on_press(event):
        global _last_ctrl_c_time, _waiting_for_combo, _last_trigger_time, _combo_timer

        ctrl_held = keyboard.is_pressed("ctrl")
        now = time.time()

        with _trigger_lock:
            if now - _last_trigger_time < 0.4:
                return

        if event.name == "c" and ctrl_held:
            if _waiting_for_combo and (now - _last_ctrl_c_time < 0.6):
                if _combo_timer:
                    _combo_timer.cancel()
                _waiting_for_combo = False
                with _trigger_lock:
                    _last_trigger_time = now
                threading.Thread(target=handle_translate, daemon=True).start()
            else:
                _last_ctrl_c_time = now
                _waiting_for_combo = True
                if _combo_timer:
                    _combo_timer.cancel()
                _combo_timer = threading.Timer(0.6, _reset_combo)
                _combo_timer.daemon = True
                _combo_timer.start()

        elif event.name == "space" and ctrl_held and _waiting_for_combo:
            if now - _last_ctrl_c_time < 0.6:
                if _combo_timer:
                    _combo_timer.cancel()
                _waiting_for_combo = False
                with _trigger_lock:
                    _last_trigger_time = now
                threading.Thread(target=handle_chat, daemon=True).start()
            else:
                _waiting_for_combo = False

        elif event.name not in ("ctrl", "shift", "alt", "left ctrl", "right ctrl"):
            _waiting_for_combo = False
            if _combo_timer:
                _combo_timer.cancel()

    return on_press


def register_hotkeys(handle_translate, handle_chat):
    """Register the global hotkey listener with the given handler functions."""
    on_press = _make_on_press(handle_translate, handle_chat)
    keyboard.on_press(on_press)
