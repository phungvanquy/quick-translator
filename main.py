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
import tkinter as tk
from tkinter import ttk
import pyperclip
import keyboard
from openai import OpenAI
import pystray
from PIL import Image, ImageDraw

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model": "gpt-4o-mini",
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

config = load_config()

# ── Global hotkey variables (moved to top to fix syntax error) ────────────────
_last_ctrl_c_time = 0.0
_waiting_for_combo = False
_last_trigger_time = 0.0
_trigger_lock = threading.Lock()

# ── OpenAI client helper ──────────────────────────────────────────────────────
def get_client():
    return OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"] or "https://api.openai.com/v1",
    )

# ── Translation ───────────────────────────────────────────────────────────────
def translate(text: str) -> str:
    if not config["api_key"]:
        return "⚠ No API key set.\nRight-click the tray icon → Settings."
    try:
        response = get_client().chat.completions.create(
            model=config["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a translator. Translate the user's text to "
                        f"{config['target_language']}. "
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

# ── Chat (single turn with context) ──────────────────────────────────────────
def chat_with_context(selected_text: str, user_question: str, history: list) -> str:
    if not config["api_key"]:
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
        response = get_client().chat.completions.create(
            model=config["model"],
            messages=messages,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠ Error: {e}"

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
    def on_click_outside(e=None):
        try:
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

# ── Translation popup ─────────────────────────────────────────────────────────
def show_translate_popup(original: str, translation: str) -> None:
    popup = tk.Tk()
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
    tk.Label(top, text=f"→ {config['target_language']}", bg="#313244", fg="#cdd6f4",
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
    popup.mainloop()

# ── Chat popup ────────────────────────────────────────────────────────────────
def show_chat_popup(selected_text: str) -> None:
    popup = tk.Tk()
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

    # Strong auto-focus (works reliably now)
    popup.grab_set()
    popup.lift()

    def force_focus():
        popup.focus_force()
        input_entry.focus_force()
        input_entry.icursor(tk.END)
        input_entry.select_range(0, tk.END)

    popup.after(0, force_focus)
    popup.after(30, force_focus)
    popup.after(80, force_focus)
    popup.after(150, force_focus)

    popup.mainloop()

# ── Hotkey engine (fixed global declarations) ─────────────────────────────────
def on_key(event):
    global _last_ctrl_c_time, _waiting_for_combo, _last_trigger_time   # ← MUST be at the top

    ctrl_held = keyboard.is_pressed("ctrl")
    now = time.time()

    # Debounce protection (prevents multiple popups)
    with _trigger_lock:
        if now - _last_trigger_time < 0.4:
            return

    if event.name == "c" and ctrl_held:
        if _waiting_for_combo and (now - _last_ctrl_c_time < 0.6):
            _waiting_for_combo = False
            with _trigger_lock:
                _last_trigger_time = now
            threading.Thread(target=handle_translate, daemon=True).start()
        else:
            _last_ctrl_c_time = now
            _waiting_for_combo = True

    elif event.name == "space" and ctrl_held and _waiting_for_combo:
        if now - _last_ctrl_c_time < 0.6:
            _waiting_for_combo = False
            with _trigger_lock:
                _last_trigger_time = now
            threading.Thread(target=handle_chat, daemon=True).start()
        else:
            _waiting_for_combo = False

    elif event.name not in ("ctrl", "shift", "alt", "left ctrl", "right ctrl"):
        _waiting_for_combo = False

# ── Handlers ──────────────────────────────────────────────────────────────────
def handle_translate():
    time.sleep(0.05)
    text = pyperclip.paste().strip()
    if text:
        result = translate(text)
        show_translate_popup(text, result)

def handle_chat():
    time.sleep(0.05)
    text = pyperclip.paste().strip()
    if text:
        show_chat_popup(text)

keyboard.hook(on_key)

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
    win = tk.Tk()
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

    api_var = row("API Key", config["api_key"], show="•")
    url_var = row("Base URL", config["base_url"])
    model_var = row("Model", config["model"])
    lang_var = row("Target Language", config["target_language"])

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
        config["api_key"] = api_var.get().strip()
        config["base_url"] = url_var.get().strip()
        config["model"] = model_var.get().strip() or "gpt-4o-mini"
        config["target_language"] = lang_var.get().strip()
        save_config(config)
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

    if not config["api_key"]:
        threading.Thread(target=open_settings, daemon=True).start()

    build_tray()
