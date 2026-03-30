"""
Quick Translator - main.py
Ctrl+C+C → translate selected text
Ctrl+C+Space → chat about selected text
Right-click tray icon to open Settings or quit.
"""

import threading
import time
import json
import os
import ctypes
import tkinter as tk
from tkinter import ttk
import pyperclip
import keyboard
from openai import OpenAI
import pystray
from PIL import Image, ImageDraw

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".quicktranslator_config.json")
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model": "gpt-4o-mini",
}

# FIX: Protect config reads/writes with a lock so the settings window
# saving and an in-flight API call can't interleave on the same dict.
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
    """Return a shallow snapshot — callers read a stable copy."""
    with _config_lock:
        return dict(_config)

def update_config(partial: dict) -> None:
    with _config_lock:
        _config.update(partial)
    save_config(_config)

_config = load_config()

# ── OpenAI client helper ──────────────────────────────────────────────────────
def get_client(cfg: dict) -> OpenAI:
    # FIX: Accept a snapshot dict instead of reading the global directly,
    # so the client is always built from a consistent config state.
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"] or "https://api.openai.com/v1",
    )

# ── Translation ───────────────────────────────────────────────────────────────
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

# ── Chat (multi-turn with context) ────────────────────────────────────────────
def chat_with_context(selected_text: str, user_question: str, history: list) -> str:
    cfg = get_config()
    if not cfg["api_key"]:
        return "⚠ No API key set.\nRight-click the tray icon → Settings."
    try:
        system = (
            "You are a helpful assistant. The user has selected the following text:\n\n"
            f"---\n{selected_text}\n---\n\n"
            "Answer the user's questions about it concisely and clearly."
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
    """
    FIX: Retry reading the clipboard instead of a single fixed sleep.
    Ctrl+C is asynchronous — the OS may not have flushed the selection
    into the clipboard by the time we read it. Poll until the content
    stabilises or we time out (~0.5 s max).
    """
    prev = pyperclip.paste()
    for _ in range(retries):
        time.sleep(interval)
        current = pyperclip.paste()
        if current and current != prev:
            return current.strip()
    return prev.strip()

# ── Single Tk root (hidden) ───────────────────────────────────────────────────
# FIX: One tk.Tk() root lives for the entire process lifetime.
# Every popup becomes a tk.Toplevel() child instead of its own root.
# Multiple tk.Tk() instances cause "can't invoke event" crashes when a
# second popup is opened while the first is still alive, and make focus
# management unpredictable across threads.
_tk_root: tk.Tk | None = None
_tk_lock = threading.Lock()

def get_tk_root() -> tk.Tk:
    global _tk_root
    with _tk_lock:
        if _tk_root is None:
            _tk_root = tk.Tk()
            _tk_root.withdraw()          # keep the root hidden
            _tk_root.attributes("-topmost", True)
        return _tk_root

def tk_call(fn):
    """Schedule fn() on the Tk main thread via after(0, ...)."""
    get_tk_root().after(0, fn)

# ── Popup Dragging ────────────────────────────────────────────────────────────
def make_draggable(popup):
    drag_data = {"x": 0, "y": 0}

    def start_drag(event):
        drag_data["x"] = event.x
        drag_data["y"] = event.y

    def do_drag(event):
        deltax = event.x - drag_data["x"]
        deltay = event.y - drag_data["y"]
        x = popup.winfo_x() + deltax
        y = popup.winfo_y() + deltay
        popup.geometry(f"+{x}+{y}")

    popup.bind("<Button-1>", start_drag)
    popup.bind("<B1-Motion>", do_drag)

# ── Shared popup helpers ──────────────────────────────────────────────────────
def bind_close_outside(popup, close_fn):
    # FIX: Guard the callback with winfo_exists() so that clicks arriving
    # after the popup is destroyed don't raise TclError.
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

def position_popup(popup):
    popup.update_idletasks()
    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    pw, ph = popup.winfo_width(), popup.winfo_height()
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    if x + pw > sw: x = sw - pw - 10
    if y + ph > sh: y = sh - ph - 10
    popup.geometry(f"+{x}+{y}")

def force_window_focus(popup, entry=None):
    """Force OS-level focus using ctypes — works even from hotkey threads."""
    try:
        if not popup.winfo_exists():
            return
        popup.lift()
        popup.focus_force()
        if entry:
            entry.focus_force()
            entry.icursor(tk.END)
        hwnd = ctypes.windll.user32.GetParent(popup.winfo_id())
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass

# ── Translation popup ─────────────────────────────────────────────────────────
def show_translate_popup(original: str, translation: str) -> None:
    # FIX: Toplevel() instead of a second Tk() root.
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.97)
    popup.configure(bg="#1e1e2e")

    pad = 14

    def close(e=None):
        try: popup.destroy()
        except Exception: pass

    top = tk.Frame(popup, bg="#1e1e2e")
    top.pack(fill="x", padx=pad, pady=(pad, 4))
    cfg = get_config()
    tk.Label(top, text=f"→ {cfg['target_language']}", bg="#313244", fg="#cdd6f4",
             font=("Segoe UI", 9), padx=8, pady=3).pack(side="left")
    tk.Button(top, text="✕", command=close, bg="#1e1e2e", fg="#6c7086",
              font=("Segoe UI", 10), relief="flat", padx=4, pady=0,
              cursor="hand2", activebackground="#1e1e2e", activeforeground="#cdd6f4", bd=0,
    ).pack(side="right")

    orig_short = original if len(original) < 80 else original[:77] + "…"
    tk.Label(popup, text=orig_short, bg="#1e1e2e", fg="#6c7086",
             font=("Segoe UI", 9), wraplength=380, justify="left"
    ).pack(anchor="w", padx=pad, pady=(0, 6))
    tk.Frame(popup, bg="#313244", height=1).pack(fill="x", padx=pad)

    tk.Label(popup, text=translation, bg="#1e1e2e", fg="#cdd6f4",
             font=("Segoe UI", 12), wraplength=380, justify="left"
    ).pack(anchor="w", padx=pad, pady=(8, 4))

    def copy_translation():
        pyperclip.copy(translation)
        copy_btn.config(text="Copied!")
        popup.after(800, close)

    copy_btn = tk.Button(popup, text="Copy", command=copy_translation,
                         bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9),
                         relief="flat", padx=10, pady=4, cursor="hand2",
                         activebackground="#45475a", activeforeground="#cdd6f4")
    copy_btn.pack(anchor="e", padx=pad, pady=(4, pad))

    popup.bind("<Escape>", close)
    bind_close_outside(popup, close)
    make_draggable(popup)
    position_popup(popup)
    popup.focus_force()

# ── Chat popup ────────────────────────────────────────────────────────────────
def show_chat_popup(selected_text: str) -> None:
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.97)
    popup.configure(bg="#1e1e2e")

    pad = 14
    chat_history = []

    def close(e=None):
        try: popup.destroy()
        except Exception: pass

    top = tk.Frame(popup, bg="#1e1e2e")
    top.pack(fill="x", padx=pad, pady=(pad, 4))
    tk.Label(top, text="💬 Chat", bg="#313244", fg="#cdd6f4",
             font=("Segoe UI", 9), padx=8, pady=3).pack(side="left")
    tk.Button(top, text="✕", command=close, bg="#1e1e2e", fg="#6c7086",
              font=("Segoe UI", 10), relief="flat", padx=4, pady=0,
              cursor="hand2", activebackground="#1e1e2e", activeforeground="#cdd6f4", bd=0,
    ).pack(side="right")

    orig_short = selected_text if len(selected_text) < 80 else selected_text[:77] + "…"
    tk.Label(popup, text=orig_short, bg="#1e1e2e", fg="#6c7086",
             font=("Segoe UI", 9), wraplength=400, justify="left"
    ).pack(anchor="w", padx=pad, pady=(0, 6))
    tk.Frame(popup, bg="#313244", height=1).pack(fill="x", padx=pad)

    history_frame = tk.Frame(popup, bg="#1e1e2e")
    history_frame.pack(fill="both", padx=pad, pady=(8, 4), expand=True)

    def add_message(role: str, text: str):
        if not popup.winfo_exists():
            return
        is_user = role == "user"
        bubble_bg = "#313244" if is_user else "#1e1e2e"
        bubble_fg = "#89b4fa" if is_user else "#cdd6f4"
        prefix = "You: " if is_user else "AI: "
        anchor = "e" if is_user else "w"
        row_frame = tk.Frame(history_frame, bg="#1e1e2e")
        row_frame.pack(fill="x", pady=2, anchor=anchor)
        tk.Label(row_frame, text=prefix + text, bg=bubble_bg, fg=bubble_fg,
                 font=("Segoe UI", 10), wraplength=360, justify="left",
                 padx=8, pady=4).pack(anchor=anchor)

    input_frame = tk.Frame(popup, bg="#1e1e2e")
    input_frame.pack(fill="x", padx=pad, pady=(4, pad))

    input_var = tk.StringVar()
    input_entry = tk.Entry(input_frame, textvariable=input_var,
                           bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
                           font=("Segoe UI", 10), relief="flat", width=40)
    input_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 6))

    def send(e=None):
        question = input_var.get().strip()
        if not question: return
        input_var.set("")
        send_btn.config(state="disabled", text="…")
        add_message("user", question)
        popup.update_idletasks()

        def do_chat():
            reply = chat_with_context(selected_text, question, chat_history)
            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": reply})
            if popup.winfo_exists():
                popup.after(0, lambda: add_message("assistant", reply))
                popup.after(0, lambda: send_btn.config(state="normal", text="Send"))
                popup.after(0, popup.update_idletasks)

        threading.Thread(target=do_chat, daemon=True).start()

    send_btn = tk.Button(input_frame, text="Send", command=send,
                         bg="#89b4fa", fg="#1e1e2e", font=("Segoe UI", 9, "bold"),
                         relief="flat", padx=12, pady=6, cursor="hand2",
                         activebackground="#74c7ec", activeforeground="#1e1e2e")
    send_btn.pack(side="right")

    input_entry.bind("<Return>", send)
    popup.bind("<Escape>", close)
    bind_close_outside(popup, close)
    make_draggable(popup)
    position_popup(popup)

    popup.after(100, lambda: force_window_focus(popup, input_entry))
    popup.after(250, lambda: force_window_focus(popup, input_entry))
    popup.after(450, lambda: force_window_focus(popup, input_entry))

# ── Hotkey engine ─────────────────────────────────────────────────────────────
_last_ctrl_c_time = 0.0
_waiting_for_combo = False
_last_trigger_time = 0.0
_trigger_lock = threading.Lock()
_combo_timer: threading.Timer | None = None  # FIX: auto-reset timer handle

def _reset_combo():
    """Called by the timer when 0.6 s elapses without a completing key."""
    global _waiting_for_combo
    _waiting_for_combo = False

def on_press(event):
    # FIX: Use keyboard.on_press instead of keyboard.hook so we only fire
    # on keydown events — hook fires on both down and up, doubling the load
    # and occasionally causing duplicate triggers.
    global _last_ctrl_c_time, _waiting_for_combo, _last_trigger_time, _combo_timer

    ctrl_held = keyboard.is_pressed("ctrl")
    now = time.time()

    with _trigger_lock:
        if now - _last_trigger_time < 0.4:
            return

    if event.name == "c" and ctrl_held:
        if _waiting_for_combo and (now - _last_ctrl_c_time < 0.6):
            # Second Ctrl+C within window → translate
            if _combo_timer:
                _combo_timer.cancel()
            _waiting_for_combo = False
            with _trigger_lock:
                _last_trigger_time = now
            threading.Thread(target=handle_translate, daemon=True).start()
        else:
            # First Ctrl+C — start waiting
            _last_ctrl_c_time = now
            _waiting_for_combo = True
            # FIX: Auto-reset combo state after 0.6 s so stale state
            # can't ghost-trigger on the next unrelated Ctrl+C.
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
        # Any other key cancels the combo
        _waiting_for_combo = False
        if _combo_timer:
            _combo_timer.cancel()

keyboard.on_press(on_press)

# ── Handlers ──────────────────────────────────────────────────────────────────
def handle_translate():
    text = get_clipboard_after_copy()
    if text:
        result = translate(text)
        # FIX: Schedule on the Tk thread instead of calling directly from
        # a background thread — Tkinter is not thread-safe.
        tk_call(lambda: show_translate_popup(text, result))

def handle_chat():
    text = get_clipboard_after_copy()
    if text:
        tk_call(lambda: show_chat_popup(text))

# ── System tray ───────────────────────────────────────────────────────────────
def make_icon():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill="#89b4fa")
    d.text((18, 16), "Tr", fill="#1e1e2e")
    return img

def build_tray():
    icon = pystray.Icon("QuickTranslator")
    icon.icon = make_icon()
    icon.title = "Quick Translator"
    icon.menu = pystray.Menu(
        pystray.MenuItem("Settings", lambda: threading.Thread(target=open_settings, daemon=True).start()),
        pystray.MenuItem("Quit", lambda: (icon.stop(), os._exit(0))),
    )
    icon.run()

# ── Settings window ───────────────────────────────────────────────────────────
def open_settings() -> None:
    cfg = get_config()
    # Settings gets its own Toplevel too
    root = get_tk_root()
    win = tk.Toplevel(root)
    win.title("Quick Translator — Settings")
    win.resizable(False, False)
    win.configure(bg="#1e1e2e")
    win.attributes("-topmost", True)
    w, h = 420, 370
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
    style.configure("TEntry", fieldbackground="#313244", foreground="#cdd6f4", insertcolor="#cdd6f4")

    def row(label, default, show=None):
        ttk.Label(win, text=label).pack(anchor="w", padx=20, pady=(12, 2))
        var = tk.StringVar(value=default)
        ttk.Entry(win, textvariable=var, width=50, show=show or "").pack(padx=20, fill="x")
        return var

    api_var  = row("API Key", cfg["api_key"], show="•")
    url_var  = row("Base URL", cfg["base_url"])
    model_var= row("Model", cfg["model"])
    lang_var = row("Target Language", cfg["target_language"])

    def toggle_key():
        entries = [c for c in win.winfo_children() if isinstance(c, ttk.Entry)]
        cur = entries[0].cget("show")
        new_show = "" if cur == "•" else "•"
        entries[0].config(show=new_show)
        show_btn.config(text="Hide" if new_show == "" else "Show")

    show_btn = tk.Button(win, text="Show", command=toggle_key,
                         bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9),
                         relief="flat", padx=8, cursor="hand2",
                         activebackground="#45475a", activeforeground="#cdd6f4")
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
              bg="#89b4fa", fg="#1e1e2e", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=20, pady=6, cursor="hand2",
              activebackground="#74c7ec", activeforeground="#1e1e2e").pack(pady=20)

    win.mainloop()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Quick Translator running.")
    print(" Ctrl+C+C → translate selected text")
    print(" Ctrl+C+Space → chat about selected text")
    print("Right-click tray icon to configure or quit.")

    # Initialise the hidden Tk root on the main thread before any popup is needed
    get_tk_root()

    cfg = get_config()
    if not cfg["api_key"]:
        threading.Thread(target=open_settings, daemon=True).start()

    # FIX: Run the Tk event loop on the main thread alongside the tray.
    # Previously mainloop() was only called inside each popup (blocking that
    # thread). Now the hidden root runs it permanently, and the tray runs in
    # its own thread.
    tray_thread = threading.Thread(target=build_tray, daemon=True)
    tray_thread.start()

    get_tk_root().mainloop()
