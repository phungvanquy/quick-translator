import threading
import time
import json
import os
import tkinter as tk
from tkinter import ttk, scrolledtext
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
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except: return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

config = load_config()

# ── OpenAI client helper ──────────────────────────────────────────────────────

def get_client():
    return OpenAI(
        api_key=config["api_key"],
        base_url=config["base_url"] or "https://api.openai.com/v1",
    )

# ── Translation Logic ─────────────────────────────────────────────────────────

def translate(text: str) -> str:
    if not config["api_key"]:
        return "⚠ No API key set.\nRight-click tray → Settings."
    try:
        response = get_client().chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": f"Translate to {config['target_language']}. Reply ONLY with translation."},
                {"role": "user", "content": text},
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠ Error: {e}"

def chat_with_context(selected_text: str, user_question: str, history: list) -> str:
    if not config["api_key"]:
        return "⚠ No API key set."
    try:
        system = f"Context text:\n{selected_text}\n\nAnswer concisely."
        messages = [{"role": "system", "content": system}] + history + [{"role": "user", "content": user_question}]
        response = get_client().chat.completions.create(
            model=config["model"],
            messages=messages,
            max_tokens=1000,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠ Error: {e}"

# ── UI Helpers ────────────────────────────────────────────────────────────────

def make_movable(widget, root):
    """Allows dragging the window by clicking anywhere on the widget."""
    def start_move(event):
        root.x = event.x
        root.y = event.y
    def stop_move(event):
        root.x = None
        root.y = None
    def do_move(event):
        deltax = event.x - root.x
        deltay = event.y - root.y
        x = root.winfo_x() + deltax
        y = root.winfo_y() + deltay
        root.geometry(f"+{x}+{y}")
    
    widget.bind("<ButtonPress-1>", start_move)
    widget.bind("<ButtonRelease-1>", stop_move)
    widget.bind("<B1-Motion>", do_move)

def position_popup(popup):
    popup.update_idletasks()
    x, y = popup.winfo_pointerx() + 10, popup.winfo_pointery() + 10
    sw, sh = popup.winfo_screenwidth(), popup.winfo_screenheight()
    pw, ph = popup.winfo_width(), popup.winfo_height()
    if x + pw > sw: x = sw - pw - 10
    if y + ph > sh: y = sh - ph - 10
    popup.geometry(f"+{x}+{y}")

# ── Translation Popup ─────────────────────────────────────────────────────────

def show_translate_popup(original: str, translation: str):
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True, "-alpha", 0.98)
    root.configure(bg="#1e1e2e")
    
    # Make whole window draggable
    make_movable(root, root)

    pad = 15
    top = tk.Frame(root, bg="#1e1e2e")
    top.pack(fill="x", padx=pad, pady=(pad, 5))
    make_movable(top, root)

    tk.Label(top, text=f"→ {config['target_language']}", bg="#313244", fg="#cdd6f4", font=("Segoe UI", 9, "bold"), padx=6).pack(side="left")
    tk.Button(top, text="✕", command=root.destroy, bg="#1e1e2e", fg="#6c7086", bd=0, cursor="hand2").pack(side="right")

    txt = tk.Label(root, text=translation, bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 11), wraplength=350, justify="left")
    txt.pack(padx=pad, pady=10)
    make_movable(txt, root)

    btn = tk.Button(root, text="Copy & Close", command=lambda: [pyperclip.copy(translation), root.destroy()], 
                    bg="#313244", fg="#cdd6f4", relief="flat", padx=10, pady=5, cursor="hand2")
    btn.pack(pady=(0, pad))

    root.bind("<Escape>", lambda e: root.destroy())
    position_popup(root)
    root.mainloop()

# ── Chat Popup ────────────────────────────────────────────────────────────────

def show_chat_popup(selected_text: str):
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True, "-alpha", 0.98)
    root.configure(bg="#1e1e2e")
    make_movable(root, root)

    chat_history = []
    pad = 12

    # Header
    top = tk.Frame(root, bg="#1e1e2e")
    top.pack(fill="x", padx=pad, pady=(pad, 5))
    make_movable(top, root)
    tk.Label(top, text="💬 Context Chat", bg="#89b4fa", fg="#1e1e2e", font=("Segoe UI", 9, "bold"), padx=6).pack(side="left")
    tk.Button(top, text="✕", command=root.destroy, bg="#1e1e2e", fg="#6c7086", bd=0).pack(side="right")

    # History Area (ScrolledText is better for memory/performance than many labels)
    display = scrolledtext.ScrolledText(root, width=45, height=12, bg="#181825", fg="#cdd6f4", 
                                        font=("Segoe UI", 10), bd=0, padx=10, pady=10, state="disabled")
    display.pack(padx=pad, pady=5)

    # Input Area
    entry_var = tk.StringVar()
    entry = tk.Entry(root, textvariable=entry_var, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", 
                     font=("Segoe UI", 10), relief="flat", width=40)
    entry.pack(fill="x", padx=pad, pady=5, ipady=8)

    def append_chat(role, msg):
        display.config(state="normal")
        prefix = "You: " if role == "user" else "AI: "
        color = "#89b4fa" if role == "user" else "#a6e3a1"
        display.insert("end", prefix, (role,))
        display.tag_config(role, foreground=color, font=("Segoe UI", 10, "bold"))
        display.insert("end", f"{msg}\n\n")
        display.see("end")
        display.config(state="disabled")

    def handle_send(e=None):
        query = entry_var.get().strip()
        if not query: return
        entry_var.set("")
        append_chat("user", query)
        
        def run():
            ans = chat_with_context(selected_text, query, chat_history)
            chat_history.append({"role": "user", "content": query})
            chat_history.append({"role": "assistant", "content": ans})
            root.after(0, lambda: append_chat("assistant", ans))
        
        threading.Thread(target=run, daemon=True).start()

    entry.bind("<Return>", handle_send)
    root.bind("<Escape>", lambda e: root.destroy())

    position_popup(root)
    # FIX 1: Auto-focus the entry bar
    entry.focus_force()
    root.after(100, lambda: entry.focus_set()) 
    
    root.mainloop()

# ── Settings & System Tray ────────────────────────────────────────────────────

def open_settings():
    win = tk.Tk()
    win.title("Settings")
    win.configure(bg="#1e1e2e")
    win.attributes("-topmost", True)
    
    # Simple form
    fields = {}
    for i, (k, v) in enumerate(config.items()):
        tk.Label(win, text=k.replace("_", " ").title(), bg="#1e1e2e", fg="#cdd6f4").grid(row=i, column=0, padx=10, pady=5)
        var = tk.StringVar(value=v)
        tk.Entry(win, textvariable=var, width=30).grid(row=i, column=1, padx=10, pady=5)
        fields[k] = var

    def save():
        for k, var in fields.items(): config[k] = var.get()
        save_config(config)
        win.destroy()

    tk.Button(win, text="Save", command=save, bg="#89b4fa").grid(row=len(config), columnspan=2, pady=10)
    win.mainloop()

def handle_translate():
    time.sleep(0.1) # Wait for clipboard
    text = pyperclip.paste().strip()
    if text:
        res = translate(text)
        show_translate_popup(text, res)

def handle_chat():
    time.sleep(0.1)
    text = pyperclip.paste().strip()
    if text: show_chat_popup(text)

# ── Hotkey Logic ──────────────────────────────────────────────────────────────

_last_c = 0
_waiting = False

def on_key(e):
    global _last_c, _waiting
    if not keyboard.is_pressed("ctrl"): return
    now = time.time()
    
    if e.name == "c":
        if _waiting and (now - _last_c < 0.6):
            _waiting = False
            threading.Thread(target=handle_translate, daemon=True).start()
        else:
            _last_c = now
            _waiting = True
    elif e.name == "space" and _waiting:
        if now - _last_c < 0.6:
            _waiting = False
            threading.Thread(target=handle_chat, daemon=True).start()

keyboard.hook(on_key)

def build_tray():
    img = Image.new("RGBA", (64, 64), (0,0,0,0))
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, 60, 60], fill="#89b4fa")
    icon = pystray.Icon("Translator", img, "Quick Translator", menu=pystray.Menu(
        pystray.MenuItem("Settings", lambda: threading.Thread(target=open_settings, daemon=True).start()),
        pystray.MenuItem("Quit", lambda: os._exit(0))
    ))
    icon.run()

if __name__ == "__main__":
    if not config["api_key"]:
        threading.Thread(target=open_settings, daemon=True).start()
    build_tray()
