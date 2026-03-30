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

from chat_popup import show_chat_popup as _show_chat_popup, _configure_tags, render_markdown_to_text

# ── Config ────────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".quicktranslator_config.json")
DEFAULT_PROMPT = (
    "You are a translator. Translate the user's text to {target_language}. "
    "Reply with ONLY the translation — no explanations, no notes."
)
DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model": "gpt-4o-mini",
    "custom_prompt": DEFAULT_PROMPT,
}

_config_lock = threading.Lock()
_config: dict = {}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass  # fall through to defaults
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
        prompt = cfg.get("custom_prompt", DEFAULT_PROMPT)
        try:
            system_content = prompt.format(target_language=cfg["target_language"])
        except (KeyError, ValueError):
            system_content = prompt
        response = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_content},
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

from constants import (
    BG, MANTLE, SURFACE, SURFACE1, OVERLAY, MUTED, SUBTEXT, TEXT_C,
    BLUE, SAPPHIRE, GREEN, RED,
    FONT_UI, FONT_BOLD, FONT_SM, FONT_XS, FONT_MONO,
    bind_hover,
)

# ── Translation popup ─────────────────────────────────────────────────────────
def _bind_close_outside(popup, close_fn):
    """Close popup when clicking outside it. Returns cleanup function."""
    def on_click_outside(e=None):
        try:
            if not popup.winfo_exists():
                _unbind()
                return
            px, py = popup.winfo_rootx(), popup.winfo_rooty()
            pw, ph = popup.winfo_width(), popup.winfo_height()
            mx, my = popup.winfo_pointerx(), popup.winfo_pointery()
            if not (px <= mx <= px + pw and py <= my <= py + ph):
                _unbind()
                close_fn()
        except Exception:
            pass
    bind_id = popup.bind_all("<Button-1>", on_click_outside, add=True)
    def _unbind():
        try:
            popup.unbind_all("<Button-1>")
        except Exception:
            pass
    popup.bind("<Destroy>", lambda e: _unbind(), add=True)

def show_translate_popup(original: str, translation: str) -> None:
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.97)
    popup.configure(bg=BG)

    WIN_W = 420
    pad = 16
    drag_data = {"x": 0, "y": 0}

    def close(e=None):
        try: popup.destroy()
        except Exception: pass

    # ── Header (drag handle) ──────────────────────────────────────────────────
    header = tk.Frame(popup, bg=SURFACE, padx=12, pady=8)
    header.pack(fill="x")

    def _press(e):
        drag_data["x"] = e.x_root - popup.winfo_x()
        drag_data["y"] = e.y_root - popup.winfo_y()
    def _drag(e):
        popup.geometry(f"+{e.x_root - drag_data['x']}+{e.y_root - drag_data['y']}")

    header.bind("<Button-1>",  _press)
    header.bind("<B1-Motion>", _drag)

    cfg = get_config()
    title_lbl = tk.Label(header, text=f"⟶  {cfg['target_language']}", bg=SURFACE,
                         fg=SUBTEXT, font=FONT_SM, anchor="w")
    title_lbl.pack(side="left")
    title_lbl.bind("<Button-1>",  _press)
    title_lbl.bind("<B1-Motion>", _drag)

    close_btn = tk.Button(header, text="✕", command=close, bg=SURFACE, fg=MUTED,
                          font=FONT_SM, relief="flat", padx=6, pady=0,
                          cursor="hand2", activebackground=RED,
                          activeforeground=TEXT_C, bd=0)
    close_btn.pack(side="right")
    bind_hover(close_btn, RED, SURFACE, TEXT_C, MUTED)

    # ── Original text (muted, selectable) ─────────────────────────────────────
    orig_short = original if len(original) < 120 else original[:117] + "…"
    orig_lbl = tk.Label(popup, text=orig_short, bg=BG, fg=MUTED,
                        font=FONT_XS, wraplength=WIN_W - pad * 2,
                        justify="left", anchor="w")
    orig_lbl.pack(anchor="w", padx=pad, pady=(10, 6))

    # Separator
    tk.Frame(popup, bg=SURFACE1, height=1).pack(fill="x", padx=pad)

    # ── Translation result (selectable Text widget) ───────────────────────────
    trans_text = tk.Text(popup, bg=BG, fg=TEXT_C, font=("Segoe UI", 12),
                         wrap="word", relief="flat", bd=0, padx=pad, pady=8,
                         highlightthickness=0, cursor="xterm",
                         selectbackground=OVERLAY, selectforeground=TEXT_C,
                         inactiveselectbackground=OVERLAY,
                         height=1)
    _configure_tags(trans_text)
    render_markdown_to_text(trans_text, translation)
    # Strip trailing blank lines
    content = trans_text.get("1.0", tk.END)
    stripped = content.rstrip("\n")
    if len(stripped) < len(content) - 1:
        trans_text.delete(f"1.0 + {len(stripped)}c", tk.END)
    trans_text.config(state="normal")
    trans_text.pack(anchor="w", fill="x", padx=0, pady=(4, 0))

    # Read-only: block edits but allow selection
    def _block_edits(event):
        if event.state & 0x4:  # Ctrl held
            if event.keysym.lower() in ("a", "c"):
                return
            return "break"
        if event.keysym in ("Left","Right","Up","Down","Home","End",
                            "Prior","Next","Shift_L","Shift_R",
                            "Control_L","Control_R"):
            return
        return "break"
    trans_text.bind("<Key>", _block_edits)

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = tk.Frame(popup, bg=BG)
    bottom.pack(fill="x", padx=pad, pady=(4, pad))

    def copy_translation():
        # If user has selected text in the Text widget, copy that instead
        try:
            sel = trans_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if sel:
                pyperclip.copy(sel)
                copy_btn.config(text="✓ Copied", fg=GREEN)
                popup.after(800, close)
                return
        except tk.TclError:
            pass
        pyperclip.copy(translation)
        copy_btn.config(text="✓ Copied", fg=GREEN)
        popup.after(800, close)

    copy_btn = tk.Button(bottom, text="⎘ Copy", command=copy_translation,
                         bg=SURFACE, fg=TEXT_C, font=FONT_SM,
                         relief="flat", padx=12, pady=5, cursor="hand2",
                         activebackground=OVERLAY, activeforeground=TEXT_C, bd=0)
    copy_btn.pack(side="right")
    bind_hover(copy_btn, OVERLAY, SURFACE)

    popup.bind("<Escape>", close)
    popup.bind("<Control-c>", lambda e: copy_translation())
    _bind_close_outside(popup, close)

    # ── Size & position ──────────────────────────────────────────────────────
    # Force fixed width, then compute display lines for proper height
    popup.update_idletasks()
    popup.geometry(f"{WIN_W}x1")
    popup.update_idletasks()

    # Count actual display lines (accounts for word wrap)
    try:
        dl = trans_text.count("1.0", tk.END, "displaylines")
        display_lines = int(dl[0]) if dl else 3
    except (TypeError, IndexError, tk.TclError):
        display_lines = max(3, int(trans_text.index(tk.END).split(".")[0]))
    trans_text.config(height=max(2, min(display_lines + 1, 15)))

    popup.update_idletasks()
    ph = popup.winfo_reqheight()
    # Clamp total popup height
    MIN_H, MAX_H = 120, 500
    ph = max(MIN_H, min(ph, MAX_H))

    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    if x + WIN_W > sw: x = sw - WIN_W - 10
    if y + ph > sh: y = sh - ph - 10
    popup.geometry(f"{WIN_W}x{ph}+{x}+{y}")
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

# ── Handlers ──────────────────────────────────────────────────────────────
_loading_popup = None

def _show_loading():
    global _loading_popup
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.attributes("-alpha", 0.95)
    popup.configure(bg=SURFACE)
    tk.Label(popup, text="⏳ Translating…", bg=SURFACE, fg=SUBTEXT,
             font=FONT_SM, padx=16, pady=10).pack()
    popup.update_idletasks()
    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    popup.geometry(f"+{x}+{y}")
    _loading_popup = popup

def _dismiss_loading():
    global _loading_popup
    if _loading_popup:
        try: _loading_popup.destroy()
        except Exception: pass
        _loading_popup = None

def handle_translate():
    text = get_clipboard_after_copy()
    if text:
        tk_call(_show_loading)
        result = translate(text)
        tk_call(lambda: (_dismiss_loading(), show_translate_popup(text, result)))

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
    w, h = 480, 620
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TLabel", background=BG, foreground=TEXT_C, font=FONT_UI)
    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT_C,
                    insertcolor=TEXT_C)
    style.configure("Section.TLabel", background=BG, foreground=MUTED,
                    font=FONT_XS)

    pad_x = 24

    # ── Section: API ──────────────────────────────────────────────────────────
    ttk.Label(win, text="API CONFIGURATION", style="Section.TLabel").pack(
        anchor="w", padx=pad_x, pady=(16, 4))
    tk.Frame(win, bg=SURFACE1, height=1).pack(fill="x", padx=pad_x, pady=(0, 4))

    def entry_row(label, default, show=None):
        ttk.Label(win, text=label).pack(anchor="w", padx=pad_x, pady=(8, 2))
        var = tk.StringVar(value=default)
        e = tk.Entry(win, textvariable=var, bg=SURFACE, fg=TEXT_C,
                     insertbackground=TEXT_C, font=FONT_UI, relief="flat",
                     highlightthickness=1, highlightbackground=OVERLAY,
                     highlightcolor=BLUE, bd=4,
                     show=show or "")
        e.pack(padx=pad_x, fill="x", ipady=3)
        return var, e

    api_var, api_entry = entry_row("API Key", cfg["api_key"], show="•")
    url_var, _ = entry_row("Base URL", cfg["base_url"])
    model_var, _ = entry_row("Model", cfg["model"])

    _key_visible = {"v": False}
    def toggle_key():
        _key_visible["v"] = not _key_visible["v"]
        api_entry.config(show="" if _key_visible["v"] else "•")
        show_btn.config(text="Hide" if _key_visible["v"] else "Show")

    show_btn = tk.Button(win, text="Show", command=toggle_key,
                         bg=SURFACE, fg=SUBTEXT, font=FONT_XS,
                         relief="flat", padx=8, pady=2, cursor="hand2",
                         activebackground=OVERLAY, activeforeground=TEXT_C, bd=0)
    show_btn.place(x=w - 70, y=80)
    bind_hover(show_btn, OVERLAY, SURFACE)

    # ── Section: Translation ──────────────────────────────────────────────────
    ttk.Label(win, text="TRANSLATION", style="Section.TLabel").pack(
        anchor="w", padx=pad_x, pady=(16, 4))
    tk.Frame(win, bg=SURFACE1, height=1).pack(fill="x", padx=pad_x, pady=(0, 4))

    lang_var, _ = entry_row("Target Language", cfg["target_language"])

    # Custom prompt
    ttk.Label(win, text="Custom Prompt").pack(anchor="w", padx=pad_x, pady=(8, 2))
    prompt_frame = tk.Frame(win, bg=OVERLAY, bd=0)
    prompt_frame.pack(padx=pad_x, fill="x")
    prompt_text = tk.Text(prompt_frame, bg=SURFACE, fg=TEXT_C,
                          insertbackground=TEXT_C, font=FONT_UI,
                          relief="flat", bd=4, height=4, wrap="word",
                          highlightthickness=1, highlightbackground=OVERLAY,
                          highlightcolor=BLUE, selectbackground=OVERLAY,
                          selectforeground=TEXT_C)
    prompt_text.pack(fill="x", expand=True)
    prompt_text.insert("1.0", cfg.get("custom_prompt", DEFAULT_PROMPT))

    hint = tk.Label(win, text="Use {target_language} as placeholder.  Leave blank for default.",
                    bg=BG, fg=MUTED, font=FONT_XS, anchor="w")
    hint.pack(anchor="w", padx=pad_x, pady=(2, 0))

    def reset_prompt():
        prompt_text.delete("1.0", tk.END)
        prompt_text.insert("1.0", DEFAULT_PROMPT)

    reset_btn = tk.Button(win, text="↺ Reset to default", command=reset_prompt,
                          bg=BG, fg=MUTED, font=FONT_XS,
                          relief="flat", padx=0, pady=0, cursor="hand2",
                          activebackground=BG, activeforeground=TEXT_C, bd=0)
    reset_btn.pack(anchor="w", padx=pad_x, pady=(2, 0))
    bind_hover(reset_btn, BG, BG, BLUE, MUTED)

    # ── Bottom buttons ────────────────────────────────────────────────────────
    btn_frame = tk.Frame(win, bg=BG)
    btn_frame.pack(fill="x", padx=pad_x, pady=(20, 16))

    def save_and_close():
        prompt_val = prompt_text.get("1.0", tk.END).strip()
        if not prompt_val:
            prompt_val = DEFAULT_PROMPT
        update_config({
            "api_key":         api_var.get().strip(),
            "base_url":        url_var.get().strip(),
            "model":           model_var.get().strip() or "gpt-4o-mini",
            "target_language": lang_var.get().strip(),
            "custom_prompt":   prompt_val,
        })
        win.destroy()

    cancel_btn = tk.Button(btn_frame, text="Cancel", command=win.destroy,
                           bg=SURFACE, fg=TEXT_C, font=FONT_SM,
                           relief="flat", padx=16, pady=6, cursor="hand2",
                           activebackground=OVERLAY, activeforeground=TEXT_C, bd=0)
    cancel_btn.pack(side="right", padx=(8, 0))
    bind_hover(cancel_btn, OVERLAY, SURFACE)

    save_btn = tk.Button(btn_frame, text="Save", command=save_and_close,
                         bg=BLUE, fg=MANTLE, font=("Segoe UI", 10, "bold"),
                         relief="flat", padx=20, pady=6, cursor="hand2",
                         activebackground=SAPPHIRE, activeforeground=MANTLE, bd=0)
    save_btn.pack(side="right")
    bind_hover(save_btn, SAPPHIRE, BLUE)

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