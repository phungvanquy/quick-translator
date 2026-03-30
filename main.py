"""
Quick Translator - main.py
Ctrl+C+C to translate selected text via OpenAI-compatible API.
Right-click tray icon to open settings.

Security hardening:
  - API key stored in Windows Credential Manager via keyring (never on disk)
  - Base URL validated against HTTPS before use
  - Clipboard input capped at 2000 characters
  - Rate limiting: max 1 translation per 3 seconds
  - Error messages sanitized — API key never leaked in UI
  - config.json only stores non-sensitive settings
"""

import threading
import time
import json
import os
import tkinter as tk
from tkinter import ttk
from urllib.parse import urlparse
import pyperclip
import keyboard
from openai import OpenAI
import pystray
from PIL import Image, ImageDraw
import keyring

# ── Constants ─────────────────────────────────────────────────────────────────

APP_NAME         = "QuickTranslator"
KEYRING_SERVICE  = "QuickTranslator_APIKey"
KEYRING_USERNAME = "openai"
CONFIG_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
MAX_INPUT_CHARS  = 2000       # clipboard cap to avoid runaway API costs
RATE_LIMIT_SEC   = 3.0        # minimum seconds between translations

# ── Config (non-sensitive only) ───────────────────────────────────────────────

DEFAULT_CONFIG = {
    "base_url":        "https://api.openai.com/v1",
    "target_language": "English",
    "model":           "gpt-4o-mini",
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {k: data.get(k, v) for k, v in DEFAULT_CONFIG.items()}
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> None:
    safe = {k: cfg[k] for k in DEFAULT_CONFIG if k in cfg}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2, ensure_ascii=False)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass  # Windows uses ACLs; chmod is a no-op but harmless

config = load_config()

# ── API key via keyring (Windows Credential Manager) ─────────────────────────

def get_api_key() -> str:
    return keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME) or ""

def set_api_key(key: str) -> None:
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except keyring.errors.PasswordDeleteError:
            pass

# ── URL validation ────────────────────────────────────────────────────────────

def validate_base_url(url: str) -> tuple:
    """Return (is_valid, reason). Localhost http is allowed; remote must be https."""
    if not url:
        return False, "Base URL cannot be empty."
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Could not parse URL."
    if parsed.scheme not in ("https", "http"):
        return False, f"URL must start with https:// (got '{parsed.scheme}://')."
    host = parsed.hostname or ""
    is_local = host in ("localhost", "127.0.0.1", "::1")
    if parsed.scheme == "http" and not is_local:
        return False, "Plain http:// is only allowed for localhost. Use https:// for remote endpoints."
    if not host:
        return False, "URL has no host."
    return True, ""

# ── Rate limiter ──────────────────────────────────────────────────────────────

_last_translation_time = 0.0
_rate_lock = threading.Lock()

def is_rate_limited() -> bool:
    global _last_translation_time
    with _rate_lock:
        now = time.time()
        if now - _last_translation_time < RATE_LIMIT_SEC:
            return True
        _last_translation_time = now
        return False

# ── Translation ───────────────────────────────────────────────────────────────

def sanitize_error(e: Exception) -> str:
    """Return a safe error string that never contains the API key."""
    api_key = get_api_key()
    msg = str(e)
    if api_key and api_key in msg:
        msg = msg.replace(api_key, "sk-***")
    msg = msg.splitlines()[0] if msg else "Unknown error"
    return msg[:200]

def translate(text: str) -> str:
    api_key = get_api_key()
    if not api_key:
        return "⚠ No API key set.\nRight-click the tray icon → Settings."

    ok, reason = validate_base_url(config["base_url"])
    if not ok:
        return f"⚠ Invalid Base URL: {reason}"

    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS] + "…"

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=config["base_url"],
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
            timeout=30,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠ Error: {sanitize_error(e)}"

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

    # ── Top bar: language badge + X button ────────────────────────────────────
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

    # ── Original text (truncated) ─────────────────────────────────────────────
    orig_short = original if len(original) < 80 else original[:77] + "…"
    tk.Label(
        popup, text=orig_short,
        bg="#1e1e2e", fg="#6c7086",
        font=("Segoe UI", 9), wraplength=380, justify="left",
    ).pack(anchor="w", padx=pad, pady=(0, 6))

    tk.Frame(popup, bg="#313244", height=1).pack(fill="x", padx=pad)

    # ── Translation ───────────────────────────────────────────────────────────
    tk.Label(
        popup, text=translation,
        bg="#1e1e2e", fg="#cdd6f4",
        font=("Segoe UI", 12), wraplength=380, justify="left",
    ).pack(anchor="w", padx=pad, pady=(8, 4))

    # ── Copy button ───────────────────────────────────────────────────────────
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

    # ── Close triggers ────────────────────────────────────────────────────────
    # Escape key
    popup.bind("<Escape>", close)

    # Click anywhere outside the popup window
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

    # ── Position & show ───────────────────────────────────────────────────────
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

    win.update_idletasks()
    w, h = 420, 400
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TLabel",  background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
    style.configure("TEntry",  fieldbackground="#313244", foreground="#cdd6f4", insertcolor="#cdd6f4")
    style.configure("TButton", background="#313244", foreground="#cdd6f4", font=("Segoe UI", 10))
    style.map("TButton", background=[("active", "#45475a")])

    def row(parent, label, default, show=None):
        ttk.Label(parent, text=label).pack(anchor="w", padx=20, pady=(12, 2))
        var = tk.StringVar(value=default)
        ttk.Entry(parent, textvariable=var, width=50, show=show or "").pack(padx=20, fill="x")
        return var

    api_var   = row(win, "API Key", get_api_key(), show="•")
    url_var   = row(win, "Base URL", config["base_url"])
    model_var = row(win, "Model", config["model"])
    lang_var  = row(win, "Target Language", config["target_language"])

    # Show/hide API key toggle
    api_entry = [c for c in win.winfo_children() if isinstance(c, ttk.Entry)][0]

    def toggle_key():
        current = api_entry.cget("show")
        api_entry.config(show="" if current == "•" else "•")
        show_btn.config(text="Hide" if current == "•" else "Show")

    show_btn = tk.Button(
        win, text="Show", command=toggle_key,
        bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9),
        relief="flat", padx=8, cursor="hand2",
        activebackground="#45475a", activeforeground="#cdd6f4",
    )
    show_btn.place(x=w - 60, y=60)

    # Inline validation error
    err_label = tk.Label(win, text="", bg="#1e1e2e", fg="#f38ba8", font=("Segoe UI", 9))
    err_label.pack(pady=(4, 0))

    def save_and_close():
        new_key   = api_var.get().strip()
        new_url   = url_var.get().strip()
        new_model = model_var.get().strip()
        new_lang  = lang_var.get().strip()

        if not new_key:
            err_label.config(text="⚠ API Key cannot be empty.")
            return

        ok, reason = validate_base_url(new_url)
        if not ok:
            err_label.config(text=f"⚠ {reason}")
            return

        if not new_model:
            err_label.config(text="⚠ Model name cannot be empty.")
            return

        # API key → Windows Credential Manager (never written to disk)
        set_api_key(new_key)

        # Non-sensitive settings → config.json
        config["base_url"]        = new_url
        config["model"]           = new_model
        config["target_language"] = new_lang or "English"
        save_config(config)
        win.destroy()

    tk.Button(
        win, text="Save", command=save_and_close,
        bg="#89b4fa", fg="#1e1e2e",
        font=("Segoe UI", 10, "bold"),
        relief="flat", padx=20, pady=6,
        cursor="hand2",
        activebackground="#74c7ec", activeforeground="#1e1e2e",
    ).pack(pady=12)

    win.mainloop()

# ── Hotkey detection (Ctrl+C+C) ───────────────────────────────────────────────

_last_ctrl_c = 0.0

def on_ctrl_c(event) -> None:
    global _last_ctrl_c
    now = time.time()
    if now - _last_ctrl_c < 0.5:
        _last_ctrl_c = 0.0
        if not is_rate_limited():
            threading.Thread(target=handle_translate, daemon=True).start()
    else:
        _last_ctrl_c = now

def handle_translate() -> None:
    time.sleep(0.05)
    text = pyperclip.paste().strip()
    if not text:
        return
    result = translate(text)
    show_popup(text, result)

keyboard.on_press_key("c", on_ctrl_c, suppress=False)

# ── Tray icon ─────────────────────────────────────────────────────────────────

def make_icon() -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill="#89b4fa")
    d.text((18, 16), "Tr", fill="#1e1e2e")
    return img

def build_tray() -> None:
    icon = pystray.Icon(APP_NAME)
    icon.icon = make_icon()
    icon.title = "Quick Translator"
    icon.menu = pystray.Menu(
        pystray.MenuItem("Settings", lambda: threading.Thread(target=open_settings, daemon=True).start()),
        pystray.MenuItem("Quit", lambda: (icon.stop(), os._exit(0))),
    )
    icon.run()

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not get_api_key():
        threading.Thread(target=open_settings, daemon=True).start()
    build_tray()
