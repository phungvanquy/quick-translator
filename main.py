"""
Quick Translator - main.py
Ctrl+C+C to translate selected text via OpenAI-compatible API.
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
    "api_key":         "",
    "base_url":        "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model":           "gpt-4o-mini",
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

# ── Translation ───────────────────────────────────────────────────────────────

def translate(text: str) -> str:
    if not config["api_key"]:
        return "⚠ No API key set.\nRight-click the tray icon → Settings."
    try:
        client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"] or "https://api.openai.com/v1",
        )
        response = client.chat.completions.create(
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

# ── Popup window ──────────────────────────────────────────────────────────────

def show_popup(original: str, translation: str) -> None:
    popup = tk.Tk()
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.97)
    popup.configure(bg="#1e1e2e")

    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    popup.geometry(f"+{x}+{y}")
    pad = 14

    def close(e=None):
        try:
            popup.destroy()
        except Exception:
            pass

    # Top bar: language badge + X button
    top = tk.Frame(popup, bg="#1e1e2e")
    top.pack(fill="x", padx=pad, pady=(pad, 4))

    tk.Label(
        top, text=f"→ {config['target_language']}",
        bg="#313244", fg="#cdd6f4",
        font=("Segoe UI", 9), padx=8, pady=3,
    ).pack(side="left")

    tk.Button(
        top, text="✕", command=close,
        bg="#1e1e2e", fg="#6c7086",
        font=("Segoe UI", 10), relief="flat",
        padx=4, pady=0, cursor="hand2",
        activebackground="#1e1e2e", activeforeground="#cdd6f4", bd=0,
    ).pack(side="right")

    # Original text (truncated)
    orig_short = original if len(original) < 80 else original[:77] + "…"
    tk.Label(
        popup, text=orig_short,
        bg="#1e1e2e", fg="#6c7086",
        font=("Segoe UI", 9), wraplength=380, justify="left",
    ).pack(anchor="w", padx=pad, pady=(0, 6))

    tk.Frame(popup, bg="#313244", height=1).pack(fill="x", padx=pad)

    # Translation text
    tk.Label(
        popup, text=translation,
        bg="#1e1e2e", fg="#cdd6f4",
        font=("Segoe UI", 12), wraplength=380, justify="left",
    ).pack(anchor="w", padx=pad, pady=(8, 4))

    # Copy button
    def copy_translation():
        pyperclip.copy(translation)
        copy_btn.config(text="Copied!")
        popup.after(1000, close)

    copy_btn = tk.Button(
        popup, text="Copy", command=copy_translation,
        bg="#313244", fg="#cdd6f4",
        font=("Segoe UI", 9), relief="flat", padx=10, pady=4,
        cursor="hand2",
        activebackground="#45475a", activeforeground="#cdd6f4",
    )
    copy_btn.pack(anchor="e", padx=pad, pady=(4, pad))

    # Close on Escape
    popup.bind("<Escape>", close)

    # Close on click outside popup
    def on_click_outside(e=None):
        try:
            px, py = popup.winfo_rootx(), popup.winfo_rooty()
            pw, ph = popup.winfo_width(), popup.winfo_height()
            mx, my = popup.winfo_pointerx(), popup.winfo_pointery()
            if not (px <= mx <= px + pw and py <= my <= py + ph):
                close()
        except Exception:
            pass

    popup.bind_all("<Button-1>", on_click_outside)

    # Keep popup on screen
    popup.update_idletasks()
    pw, ph = popup.winfo_width(), popup.winfo_height()
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    if x + pw > sw: x = sw - pw - 10
    if y + ph > sh: y = sh - ph - 10
    popup.geometry(f"+{x}+{y}")

    popup.focus_force()
    popup.mainloop()

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

    api_var   = row("API Key",         config["api_key"],         show="•")
    url_var   = row("Base URL",        config["base_url"])
    model_var = row("Model",           config["model"])
    lang_var  = row("Target Language", config["target_language"])

    # Show/hide API key toggle
    def toggle_key():
        entries = [c for c in win.winfo_children() if isinstance(c, ttk.Entry)]
        cur = entries[0].cget("show")
        entries[0].config(show="" if cur == "•" else "•")
        show_btn.config(text="Hide" if cur == "•" else "Show")

    show_btn = tk.Button(
        win, text="Show", command=toggle_key,
        bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9),
        relief="flat", padx=8, cursor="hand2",
        activebackground="#45475a", activeforeground="#cdd6f4",
    )
    show_btn.place(x=w - 60, y=60)

    def save_and_close():
        config["api_key"]         = api_var.get().strip()
        config["base_url"]        = url_var.get().strip()
        config["model"]           = model_var.get().strip() or "gpt-4o-mini"
        config["target_language"] = lang_var.get().strip()
        save_config(config)
        win.destroy()

    tk.Button(
        win, text="Save", command=save_and_close,
        bg="#89b4fa", fg="#1e1e2e",
        font=("Segoe UI", 10, "bold"),
        relief="flat", padx=20, pady=6, cursor="hand2",
        activebackground="#74c7ec", activeforeground="#1e1e2e",
    ).pack(pady=20)

    win.mainloop()

# ── Hotkey: Ctrl+C+C ──────────────────────────────────────────────────────────

_last_ctrl_c = 0.0

def on_ctrl_c(event):
    global _last_ctrl_c
    now = time.time()
    if now - _last_ctrl_c < 0.5:
        _last_ctrl_c = 0.0
        threading.Thread(target=handle_translate, daemon=True).start()
    else:
        _last_ctrl_c = now

def handle_translate():
    time.sleep(0.05)
    text = pyperclip.paste().strip()
    if not text:
        return
    result = translate(text)
    show_popup(text, result)

keyboard.on_press_key("c", on_ctrl_c, suppress=False)

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
        pystray.MenuItem("Quit",     lambda: (icon.stop(), os._exit(0))),
    )
    icon.run()

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Quick Translator running. Ctrl+C+C to translate. Right-click tray to configure.")
    if not config["api_key"]:
        threading.Thread(target=open_settings, daemon=True).start()
    build_tray()
