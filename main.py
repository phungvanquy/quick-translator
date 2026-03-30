"""
Quick Translator — main.py
Ctrl+C+C      → translate selected text
Ctrl+C+Space  → chat about selected text
Right-click tray icon to open Settings or quit.
"""

import threading
import time
import json
import os
import tkinter as tk
from tkinter import ttk
import pyperclip
import keyboard
from openai import OpenAI
import pystray
from PIL import Image, ImageDraw

from chat_popup import show_chat_popup as _show_chat_popup

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".quicktranslator_config.json")
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model": "gpt-4o-mini",
}

_config_lock = threading.Lock()
_config: dict = {}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def get_config() -> dict:
    with _config_lock:
        return dict(_config)

def update_config(partial: dict) -> None:
    with _config_lock:
        _config.update(partial)
        save_config(_config)

_config = load_config()

# ── OpenAI helpers ────────────────────────────────────────────────────────────
def get_client(cfg: dict) -> OpenAI:
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"] or "https://api.openai.com/v1",
    )

def translate(text: str) -> str:
    cfg = get_config()
    if not cfg["api_key"]:
        return "⚠ No API key set.\nRight-click the tray icon → Settings."
    try:
        response = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a translator. Translate the user's text to "
                        f"{cfg['target_language']}. "
                        "Reply with ONLY the translation — no explanations, no notes."
                    ),
                },
                {"role": "user", "content": text},
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠ Error: {e}"

def chat_with_context(selected_text: str, user_question: str, history: list) -> str:
    cfg = get_config()
    if not cfg["api_key"]:
        return "⚠ No API key set.\nRight-click the tray icon → Settings."
    try:
        system = (
            "You are a helpful assistant. The user has selected the following text:\n\n"
            f"---\n{selected_text}\n---\n\n"
            "Answer the user's questions about it concisely and clearly. "
            "You may use Markdown formatting (bold, italic, code blocks, lists) "
            "where it helps readability."
        )
        messages = [{"role": "system", "content": system}] + history + [
            {"role": "user", "content": user_question}
        ]
        response = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=messages,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠ Error: {e}"

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

from constants import BG, SURFACE, OVERLAY, MUTED, TEXT_C, BLUE, SAPPHIRE

# ── Translation popup ─────────────────────────────────────────────────────────
def _bind_close_outside(popup, close_fn):
    def on_click_outside(e=None):
        try:
            if not popup.winfo_exists():
                return
            px, py = popup.winfo_rootx(), popup.winfo_rooty()
            pw, ph = popup.winfo_width(), popup.winfo_height()
            mx, my = popup.winfo_pointerx(), popup.winfo_pointery()
            if not (px <= mx <= px + pw and py <= my <= py + ph):
                close_fn()
        except Exception:
            pass
    popup.bind_all("<Button-1>", on_click_outside, add=True)

def show_translate_popup(original: str, translation: str) -> None:
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.97)
    popup.configure(bg=BG)

    pad = 14
    drag_data = {"x": 0, "y": 0}

    def close(e=None):
        try: popup.destroy()
        except Exception: pass

    # Header is the drag handle
    header = tk.Frame(popup, bg=SURFACE)
    header.pack(fill="x")

    def _press(e):
        drag_data["x"] = e.x_root - popup.winfo_x()
        drag_data["y"] = e.y_root - popup.winfo_y()

    def _drag(e):
        popup.geometry(f"+{e.x_root - drag_data['x']}+{e.y_root - drag_data['y']}")

    header.bind("<Button-1>",  _press)
    header.bind("<B1-Motion>", _drag)

    cfg = get_config()
    tk.Label(header, text=f"→ {cfg['target_language']}", bg=SURFACE, fg=TEXT_C,
             font=("Segoe UI", 9), padx=8, pady=6).pack(side="left")
    tk.Button(header, text="✕", command=close, bg=SURFACE, fg=MUTED,
              font=("Segoe UI", 10), relief="flat", padx=8, pady=0,
              cursor="hand2", activebackground=SURFACE, activeforeground=TEXT_C, bd=0,
    ).pack(side="right")

    orig_short = original if len(original) < 80 else original[:77] + "…"
    tk.Label(popup, text=orig_short, bg=BG, fg=MUTED,
             font=("Segoe UI", 9), wraplength=380, justify="left",
    ).pack(anchor="w", padx=pad, pady=(8, 6))
    tk.Frame(popup, bg=SURFACE, height=1).pack(fill="x", padx=pad)
    tk.Label(popup, text=translation, bg=BG, fg=TEXT_C,
             font=("Segoe UI", 12), wraplength=380, justify="left",
    ).pack(anchor="w", padx=pad, pady=(8, 4))

    def copy_translation():
        pyperclip.copy(translation)
        copy_btn.config(text="Copied!")
        popup.after(800, close)

    copy_btn = tk.Button(popup, text="Copy", command=copy_translation,
                         bg=SURFACE, fg=TEXT_C, font=("Segoe UI", 9),
                         relief="flat", padx=10, pady=4, cursor="hand2",
                         activebackground=OVERLAY, activeforeground=TEXT_C)
    copy_btn.pack(anchor="e", padx=pad, pady=(4, pad))

    popup.bind("<Escape>", close)
    _bind_close_outside(popup, close)

    popup.update_idletasks()
    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    pw, ph = popup.winfo_width(), popup.winfo_height()
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    if x + pw > sw: x = sw - pw - 10
    if y + ph > sh: y = sh - ph - 10
    popup.geometry(f"+{x}+{y}")
    popup.focus_force()

# ── Chat popup (delegates to chat_popup.py) ───────────────────────────────────
def show_chat_popup(selected_text: str) -> None:
    _show_chat_popup(
        selected_text,
        get_tk_root=get_tk_root,
        chat_with_context=chat_with_context,
        get_config=get_config,
    )

# ── Hotkey engine ─────────────────────────────────────────────────────────────
_last_ctrl_c_time = 0.0
_waiting_for_combo = False
_last_trigger_time = 0.0
_trigger_lock  = threading.Lock()
_combo_timer: threading.Timer | None = None

def _reset_combo():
    global _waiting_for_combo
    _waiting_for_combo = False

def on_press(event):
    global _last_ctrl_c_time, _waiting_for_combo, _last_trigger_time, _combo_timer

    ctrl_held = keyboard.is_pressed("ctrl")
    now = time.time()

    with _trigger_lock:
        if now - _last_trigger_time < 0.4:
            return

    if event.name == "c" and ctrl_held:
        if _waiting_for_combo and (now - _last_ctrl_c_time < 0.6):
            if _combo_timer: _combo_timer.cancel()
            _waiting_for_combo = False
            with _trigger_lock: _last_trigger_time = now
            threading.Thread(target=handle_translate, daemon=True).start()
        else:
            _last_ctrl_c_time = now
            _waiting_for_combo = True
            if _combo_timer: _combo_timer.cancel()
            _combo_timer = threading.Timer(0.6, _reset_combo)
            _combo_timer.daemon = True
            _combo_timer.start()

    elif event.name == "space" and ctrl_held and _waiting_for_combo:
        if now - _last_ctrl_c_time < 0.6:
            if _combo_timer: _combo_timer.cancel()
            _waiting_for_combo = False
            with _trigger_lock: _last_trigger_time = now
            threading.Thread(target=handle_chat, daemon=True).start()
        else:
            _waiting_for_combo = False

    elif event.name not in ("ctrl", "shift", "alt", "left ctrl", "right ctrl"):
        _waiting_for_combo = False
        if _combo_timer: _combo_timer.cancel()

keyboard.on_press(on_press)

# ── Handlers ──────────────────────────────────────────────────────────────────
def handle_translate():
    text = get_clipboard_after_copy()
    if text:
        result = translate(text)
        tk_call(lambda: show_translate_popup(text, result))

def handle_chat():
    text = get_clipboard_after_copy()
    if text:
        tk_call(lambda: show_chat_popup(text))

# ── System tray ───────────────────────────────────────────────────────────────
def make_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=BLUE)
    d.text((18, 16), "Tr", fill=BG)
    return img

def build_tray():
    icon = pystray.Icon("QuickTranslator")
    icon.icon = make_icon()
    icon.title = "Quick Translator"
    icon.menu = pystray.Menu(
        pystray.MenuItem("Settings", lambda: threading.Thread(
            target=open_settings, daemon=True).start()),
        pystray.MenuItem("Quit", lambda: (icon.stop(), os._exit(0))),
    )
    icon.run()

# ── Settings window ───────────────────────────────────────────────────────────
def open_settings() -> None:
    cfg = get_config()
    root = get_tk_root()
    win = tk.Toplevel(root)
    win.title("Quick Translator — Settings")
    win.resizable(False, False)
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    w, h = 420, 370
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TLabel", background=BG, foreground=TEXT_C,
                    font=("Segoe UI", 10))
    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT_C,
                    insertcolor=TEXT_C)

    def row(label, default, show=None):
        ttk.Label(win, text=label).pack(anchor="w", padx=20, pady=(12, 2))
        var = tk.StringVar(value=default)
        ttk.Entry(win, textvariable=var, width=50, show=show or "").pack(
            padx=20, fill="x")
        return var

    api_var   = row("API Key", cfg["api_key"], show="•")
    url_var   = row("Base URL", cfg["base_url"])
    model_var = row("Model", cfg["model"])
    lang_var  = row("Target Language", cfg["target_language"])

    def toggle_key():
        entries = [c for c in win.winfo_children() if isinstance(c, ttk.Entry)]
        cur = entries[0].cget("show")
        new_show = "" if cur == "•" else "•"
        entries[0].config(show=new_show)
        show_btn.config(text="Hide" if new_show == "" else "Show")

    show_btn = tk.Button(win, text="Show", command=toggle_key,
                         bg=SURFACE, fg=TEXT_C, font=("Segoe UI", 9),
                         relief="flat", padx=8, cursor="hand2",
                         activebackground=OVERLAY, activeforeground=TEXT_C)
    show_btn.place(x=w - 65, y=68)

    def save_and_close():
        update_config({
            "api_key":         api_var.get().strip(),
            "base_url":        url_var.get().strip(),
            "model":           model_var.get().strip() or "gpt-4o-mini",
            "target_language": lang_var.get().strip(),
        })
        win.destroy()

    tk.Button(win, text="Save", command=save_and_close,
              bg=BLUE, fg=BG, font=("Segoe UI", 10, "bold"),
              relief="flat", padx=20, pady=6, cursor="hand2",
              activebackground=SAPPHIRE, activeforeground=BG).pack(pady=20)

    win.wait_window()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Quick Translator running.")
    print(" Ctrl+C+C     → translate selected text")
    print(" Ctrl+C+Space → chat about selected text")
    print("Right-click tray icon to configure or quit.")

    get_tk_root()   # initialise hidden root on main thread

    cfg = get_config()
    if not cfg["api_key"]:
        threading.Thread(target=open_settings, daemon=True).start()

    tray_thread = threading.Thread(target=build_tray, daemon=True)
    tray_thread.start()

    get_tk_root().mainloop()