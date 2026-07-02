"""
Quick Translator — main.py
Ctrl+C+C      → translate selected text
Ctrl+C+Space  → chat about selected text
Right-click tray icon to open Settings or quit.
"""

import threading
import time
import tkinter as tk

import pyperclip

from config import get_config
from api import translate_stream, chat_with_context_stream
from settings import open_settings
from translate_popup import show_translate_popup
from chat_popup import show_chat_popup as _show_chat_popup
from hotkeys import register_hotkeys
from tray import build_tray


# ── Clipboard helper ──────────────────────────────────────────────────────────
def get_clipboard_after_copy(retries: int = 10, interval: float = 0.05) -> str:
    prev = pyperclip.paste()
    for _ in range(retries):
        time.sleep(interval)
        current = pyperclip.paste()
        if current and current != prev:
            return current.strip()
    return prev.strip()


# ── Single Tk root ────────────────────────────────────────────────────────────
_tk_root: tk.Tk | None = None
_tk_lock = threading.Lock()


def get_tk_root() -> tk.Tk:
    global _tk_root
    with _tk_lock:
        if _tk_root is None:
            _tk_root = tk.Tk()
            _tk_root.withdraw()
            _tk_root.attributes("-topmost", True)
        return _tk_root


def tk_call(fn):
    get_tk_root().after(0, fn)


# ── Chat popup (delegates to chat_popup.py) ───────────────────────────────────
def show_chat_popup(selected_text: str) -> None:
    _show_chat_popup(
        selected_text,
        get_tk_root=get_tk_root,
        chat_with_context_stream=chat_with_context_stream,
    )


# ── Handlers ──────────────────────────────────────────────────────────────────
def handle_translate():
    text = get_clipboard_after_copy()
    if text:
        stream = translate_stream(text)
        tk_call(lambda: show_translate_popup(text, stream, get_tk_root=get_tk_root))


def handle_chat():
    text = get_clipboard_after_copy()
    if text:
        tk_call(lambda: show_chat_popup(text))


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Quick Translator running.")
    print(" Ctrl+C+C     → translate selected text")
    print(" Ctrl+C+Space → chat about selected text")
    print("Right-click tray icon to configure or quit.")

    get_tk_root()  # initialise hidden root on main thread

    cfg = get_config()
    if not cfg["api_key"]:
        threading.Thread(target=lambda: open_settings(get_tk_root), daemon=True).start()

    register_hotkeys(handle_translate, handle_chat)

    tray_thread = threading.Thread(target=lambda: build_tray(get_tk_root), daemon=True)
    tray_thread.start()

    get_tk_root().mainloop()
