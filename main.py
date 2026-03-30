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

import sys

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

def translate_stream(text: str):
    """Yield translation chunks. Yields strings; first may be an error."""
    cfg = get_config()
    if not cfg["api_key"]:
        yield "⚠ No API key set.\nRight-click the tray icon → Settings."
        return
    try:
        prompt = cfg.get("custom_prompt", DEFAULT_PROMPT)
        try:
            system_content = prompt.format(target_language=cfg["target_language"])
        except (KeyError, ValueError):
            system_content = prompt
        stream = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": text},
            ],
            max_completion_tokens=1000,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        yield f"⚠ Error: {e}"

def chat_with_context_stream(selected_text: str, user_question: str, history: list):
    """Yield chat response chunks as strings."""
    cfg = get_config()
    if not cfg["api_key"]:
        yield "⚠ No API key set.\nRight-click the tray icon → Settings."
        return
    try:
        if selected_text:
            system = (
                "You are a helpful assistant. The user has selected the following text:\n\n"
                f"---\n{selected_text}\n---\n\n"
                "Answer the user's questions about it concisely and clearly. "
                "You may use Markdown formatting (bold, italic, code blocks, lists) "
                "where it helps readability."
            )
        else:
            system = (
                "You are a helpful assistant. Answer concisely and clearly. "
                "You may use Markdown formatting (bold, italic, code blocks, lists) "
                "where it helps readability."
            )
        messages = [{"role": "system", "content": system}] + history + [
            {"role": "user", "content": user_question}
        ]
        stream = get_client(cfg).chat.completions.create(
            model=cfg["model"],
            messages=messages,
            max_completion_tokens=1000,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
    except Exception as e:
        yield f"⚠ Error: {e}"

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
    BG, MANTLE, CRUST, SURFACE, SURFACE1, SURFACE2, OVERLAY, MUTED, SUBTEXT, TEXT_C,
    BLUE, SAPPHIRE, GREEN, RED, BORDER, SHADOW, INPUT_BG, ACCENT,
    FONT_UI, FONT_BOLD, FONT_SM, FONT_XS, FONT_MONO,
    PAD_SM, PAD, PAD_LG,
    bind_hover, fade_in,
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

def show_translate_popup(original: str, stream_gen) -> None:
    """Show translation popup with streaming. stream_gen is a generator yielding chunks."""
    root = get_tk_root()
    popup = tk.Toplevel(root)
    popup.overrideredirect(True)
    popup.attributes("-topmost", True)
    popup.configure(bg=SHADOW)  # shadow border trick: 1px dark border via outer bg

    WIN_W = 440
    pad = PAD_LG
    drag_data = {"x": 0, "y": 0}

    def close(e=None):
        try: popup.destroy()
        except Exception: pass

    # ── Outer border frame (1px shadow border) ────────────────────────────────
    border = tk.Frame(popup, bg=BORDER, bd=0)
    border.pack(fill="both", expand=True, padx=1, pady=1)

    inner = tk.Frame(border, bg=BG, bd=0)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Header (drag handle) ──────────────────────────────────────────────────
    header = tk.Frame(inner, bg=SURFACE, padx=PAD, pady=10)
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
                          font=FONT_SM, relief="flat", padx=8, pady=2,
                          cursor="hand2", activebackground=RED,
                          activeforeground=TEXT_C, bd=0)
    close_btn.pack(side="right")
    bind_hover(close_btn, RED, SURFACE, TEXT_C, MUTED)

    # ── Original text (muted, selectable) ─────────────────────────────────────
    orig_short = original if len(original) < 120 else original[:117] + "…"
    orig_lbl = tk.Label(inner, text=orig_short, bg=BG, fg=MUTED,
                        font=FONT_XS, wraplength=WIN_W - pad * 2,
                        justify="left", anchor="w")
    orig_lbl.pack(anchor="w", padx=pad, pady=(PAD, PAD_SM))

    # Separator
    tk.Frame(inner, bg=SURFACE1, height=1).pack(fill="x", padx=pad)

    # ── Translation result (selectable Text widget) ───────────────────────────
    trans_text = tk.Text(inner, bg=BG, fg=TEXT_C, font=("Segoe UI", 12),
                         wrap="word", relief="flat", bd=0, padx=pad, pady=10,
                         highlightthickness=0, cursor="xterm",
                         selectbackground=OVERLAY, selectforeground=TEXT_C,
                         inactiveselectbackground=OVERLAY,
                         height=2, spacing1=2, spacing3=2)
    _configure_tags(trans_text)
    trans_text.insert(tk.END, "⏳", "normal")
    trans_text.config(state="normal")
    trans_text.pack(anchor="w", fill="x", padx=0, pady=(6, 0))

    # Read-only: block edits but allow selection
    def _block_edits(event):
        if event.state & 0x4:
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
    bottom = tk.Frame(inner, bg=BG)
    bottom.pack(fill="x", padx=pad, pady=(PAD_SM, PAD))

    _full_text = {"value": ""}

    def copy_translation():
        try:
            sel = trans_text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if sel:
                pyperclip.copy(sel)
                copy_btn.config(text="✓ Copied!", fg=GREEN, bg=BG)
                popup.after(900, close)
                return
        except tk.TclError:
            pass
        pyperclip.copy(_full_text["value"])
        copy_btn.config(text="✓ Copied!", fg=GREEN, bg=BG)
        popup.after(900, close)

    copy_btn = tk.Button(bottom, text="⎘  Copy", command=copy_translation,
                         bg=SURFACE, fg=TEXT_C, font=("Segoe UI", 9, "bold"),
                         relief="flat", padx=14, pady=6, cursor="hand2",
                         activebackground=OVERLAY, activeforeground=TEXT_C, bd=0)
    copy_btn.pack(side="right")
    bind_hover(copy_btn, OVERLAY, SURFACE)

    popup.bind("<Escape>", close)
    popup.bind("<Control-c>", lambda e: copy_translation())
    _bind_close_outside(popup, close)

    # ── Size & position (initial) ────────────────────────────────────────────
    popup.update_idletasks()
    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    if x + WIN_W > sw: x = sw - WIN_W - 10
    if y + 200 > sh: y = sh - 200 - 10
    popup.geometry(f"{WIN_W}x200+{x}+{y}")
    popup.focus_force()
    fade_in(popup, duration_ms=120)

    # ── Resize helper ────────────────────────────────────────────────────────
    _pos = {"x": x, "y": y}

    def _resize_popup():
        if not popup.winfo_exists():
            return
        popup.update_idletasks()
        try:
            dl = trans_text.count("1.0", tk.END, "displaylines")
            display_lines = int(dl[0]) if dl else 3
        except (TypeError, IndexError, tk.TclError):
            display_lines = max(3, int(trans_text.index(tk.END).split(".")[0]))
        trans_text.config(height=max(2, min(display_lines + 1, 15)))
        popup.update_idletasks()
        ph = popup.winfo_reqheight()
        MIN_H, MAX_H = 140, 520
        ph = max(MIN_H, min(ph, MAX_H))
        popup.geometry(f"{WIN_W}x{ph}+{_pos['x']}+{_pos['y']}")

    # ── Stream chunks from background thread ─────────────────────────────────
    _stream_started = {"v": False}

    def _append_chunk(chunk):
        if not popup.winfo_exists():
            return
        if not _stream_started["v"]:
            trans_text.delete("1.0", tk.END)
            _stream_started["v"] = True
        trans_text.insert(tk.END, chunk, "normal")
        _full_text["value"] += chunk
        _resize_popup()

    def _stream_done():
        if not popup.winfo_exists():
            return
        full = _full_text["value"].strip()
        trans_text.delete("1.0", tk.END)
        render_markdown_to_text(trans_text, full)
        content = trans_text.get("1.0", tk.END)
        stripped = content.rstrip("\n")
        if len(stripped) < len(content) - 1:
            trans_text.delete(f"1.0 + {len(stripped)}c", tk.END)
        _full_text["value"] = full
        _resize_popup()

    def _do_stream():
        try:
            for chunk in stream_gen:
                if not popup.winfo_exists():
                    return
                popup.after(0, lambda c=chunk: _append_chunk(c))
        finally:
            if popup.winfo_exists():
                popup.after(0, _stream_done)

    threading.Thread(target=_do_stream, daemon=True).start()

# ── Chat popup (delegates to chat_popup.py) ───────────────────────────────────
def show_chat_popup(selected_text: str) -> None:
    _show_chat_popup(
        selected_text,
        get_tk_root=get_tk_root,
        chat_with_context_stream=chat_with_context_stream,
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

def handle_translate():
    text = get_clipboard_after_copy()
    if text:
        stream = translate_stream(text)
        tk_call(lambda: show_translate_popup(text, stream))

def handle_chat():
    text = get_clipboard_after_copy()
    if text:
        tk_call(lambda: show_chat_popup(text))

# ── System tray ───────────────────────────────────────────────────────────────
def _app_path(filename: str) -> str:
    """Resolve a file path that works both from source and PyInstaller bundle."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

def make_icon():
    # Try to load the proper icon file
    ico_path = _app_path("icon.ico")
    png_path = _app_path("icon.png")
    for path in (ico_path, png_path):
        if os.path.exists(path):
            try:
                return Image.open(path)
            except Exception:
                pass
    # Fallback: generate a simple icon in memory
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill=BLUE)
    d.text((18, 16), "Qt", fill=BG)
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
    w, h = 500, 640
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TLabel", background=BG, foreground=TEXT_C, font=FONT_UI)
    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT_C,
                    insertcolor=TEXT_C)
    style.configure("Section.TLabel", background=BG, foreground=MUTED,
                    font=("Segoe UI", 8, "bold"))

    pad_x = 28

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg=SURFACE, height=48)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="⚙  Settings", bg=SURFACE, fg=TEXT_C,
             font=("Segoe UI", 11, "bold"), padx=pad_x).pack(
                 side="left", fill="y")

    # ── Section: API ──────────────────────────────────────────────────────────
    ttk.Label(win, text="API CONFIGURATION", style="Section.TLabel").pack(
        anchor="w", padx=pad_x, pady=(PAD_LG, 4))
    tk.Frame(win, bg=SURFACE1, height=1).pack(fill="x", padx=pad_x, pady=(0, 4))

    def entry_row(label, default, show=None):
        ttk.Label(win, text=label).pack(anchor="w", padx=pad_x, pady=(8, 3))
        var = tk.StringVar(value=default)
        e = tk.Entry(win, textvariable=var, bg=INPUT_BG, fg=TEXT_C,
                     insertbackground=TEXT_C, font=FONT_UI, relief="flat",
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT, bd=6,
                     show=show or "")
        e.pack(padx=pad_x, fill="x", ipady=4)
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
    show_btn.place(x=w - 75, y=128)
    bind_hover(show_btn, OVERLAY, SURFACE)

    # ── Section: Translation ──────────────────────────────────────────────────
    ttk.Label(win, text="TRANSLATION", style="Section.TLabel").pack(
        anchor="w", padx=pad_x, pady=(PAD_LG, 4))
    tk.Frame(win, bg=SURFACE1, height=1).pack(fill="x", padx=pad_x, pady=(0, 4))

    lang_var, _ = entry_row("Target Language", cfg["target_language"])

    # Custom prompt
    ttk.Label(win, text="Custom Prompt").pack(anchor="w", padx=pad_x, pady=(8, 3))
    prompt_text = tk.Text(win, bg=INPUT_BG, fg=TEXT_C,
                          insertbackground=TEXT_C, font=FONT_UI,
                          relief="flat", bd=6, height=4, wrap="word",
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=ACCENT, selectbackground=OVERLAY,
                          selectforeground=TEXT_C)
    prompt_text.pack(padx=pad_x, fill="x")
    prompt_text.insert("1.0", cfg.get("custom_prompt", DEFAULT_PROMPT))

    hint = tk.Label(win, text="Use {target_language} as placeholder.  Leave blank for default.",
                    bg=BG, fg=MUTED, font=FONT_XS, anchor="w")
    hint.pack(anchor="w", padx=pad_x, pady=(3, 0))

    def reset_prompt():
        prompt_text.delete("1.0", tk.END)
        prompt_text.insert("1.0", DEFAULT_PROMPT)

    reset_btn = tk.Button(win, text="↺  Reset to default", command=reset_prompt,
                          bg=BG, fg=MUTED, font=FONT_XS,
                          relief="flat", padx=0, pady=0, cursor="hand2",
                          activebackground=BG, activeforeground=TEXT_C, bd=0)
    reset_btn.pack(anchor="w", padx=pad_x, pady=(2, 0))
    bind_hover(reset_btn, BG, BG, ACCENT, MUTED)

    # ── Bottom buttons ────────────────────────────────────────────────────────
    btn_frame = tk.Frame(win, bg=BG)
    btn_frame.pack(fill="x", padx=pad_x, pady=(24, PAD_LG))

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
                           bg=SURFACE, fg=TEXT_C, font=("Segoe UI", 9, "bold"),
                           relief="flat", padx=18, pady=7, cursor="hand2",
                           activebackground=OVERLAY, activeforeground=TEXT_C, bd=0)
    cancel_btn.pack(side="right", padx=(10, 0))
    bind_hover(cancel_btn, OVERLAY, SURFACE)

    save_btn = tk.Button(btn_frame, text="  Save  ", command=save_and_close,
                         bg=ACCENT, fg=MANTLE, font=("Segoe UI", 10, "bold"),
                         relief="flat", padx=22, pady=7, cursor="hand2",
                         activebackground=SAPPHIRE, activeforeground=MANTLE, bd=0)
    save_btn.pack(side="right")
    bind_hover(save_btn, SAPPHIRE, ACCENT)

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