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

# ── Global Root (IMPORTANT: only ONE Tk instance) ─────────────────────────────
_root = tk.Tk()
_root.withdraw()

_action_lock = threading.Lock()

# ── Config ────────────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "api_key": "",
    "base_url": "https://api.openai.com/v1",
    "target_language": "Vietnamese",
    "model": "gpt-4o-mini",
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

config = load_config()

# ── OpenAI ────────────────────────────────────────────────────────────────────

# Initialize the client once globally to reuse connections
openai_client = OpenAI(
    api_key=config["api_key"],
    base_url=config["base_url"],
)

# ── Drag Support ──────────────────────────────────────────────────────────────

def make_draggable(widget, root):
    def start_move(event):
        root._x = event.x
        root._y = event.y

    def do_move(event):
        x = root.winfo_pointerx() - root._x
        y = root.winfo_pointery() - root._y
        root.geometry(f"+{x}+{y}")

    widget.bind("<Button-1>", start_move)
    widget.bind("<B1-Motion>", do_move)

# ── Popup helpers ─────────────────────────────────────────────────────────────

def position_popup(popup):
    popup.update_idletasks()
    x = popup.winfo_pointerx() + 16
    y = popup.winfo_pointery() + 16
    popup.geometry(f"+{x}+{y}")

def focus_window(popup, entry=None):
    def _focus():
        try:
            popup.deiconify()
            popup.lift()
            popup.attributes("-topmost", True)
            if entry:
                entry.focus_set()
        except:
            pass
    popup.after(10, _focus)

# ── Translate ─────────────────────────────────────────────────────────────────

def translate(text):
    try:
        response = openai_client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": f"Translate to {config['target_language']}. Only output result."},
                {"role": "user", "content": text},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

# ── Chat ──────────────────────────────────────────────────────────────────────

def chat_with_context(selected_text, question, history):
    try:
        messages = [{"role": "system", "content": f"Context:\n{selected_text}"}]
        messages += history
        messages.append({"role": "user", "content": question})

        response = openai_client.chat.completions.create(
            model=config["model"],
            messages=messages,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

# ── Translate Popup ───────────────────────────────────────────────────────────

def show_translate_popup(original, translation):
    popup = tk.Toplevel(_root)
    popup.overrideredirect(True)
    popup.configure(bg="#1e1e2e")

    top = tk.Frame(popup, bg="#1e1e2e")
    top.pack(fill="x", padx=10, pady=5)

    make_draggable(top, popup)

    tk.Label(top, text="Translate", fg="white", bg="#1e1e2e").pack(side="left")
    tk.Button(top, text="✕", command=popup.destroy).pack(side="right")

    tk.Label(popup, text=translation, fg="white", bg="#1e1e2e", wraplength=300).pack(padx=10, pady=10)

    position_popup(popup)
    focus_window(popup)

# ── Chat Popup ────────────────────────────────────────────────────────────────

def show_chat_popup(selected_text):
    popup = tk.Toplevel(_root)
    popup.overrideredirect(True)
    popup.configure(bg="#1e1e2e")

    chat_history = []

    top = tk.Frame(popup, bg="#1e1e2e")
    top.pack(fill="x", padx=10, pady=5)

    make_draggable(top, popup)

    tk.Label(top, text="Chat", fg="white", bg="#1e1e2e").pack(side="left")
    tk.Button(top, text="✕", command=popup.destroy).pack(side="right")

    history_frame = tk.Frame(popup, bg="#1e1e2e")
    history_frame.pack(padx=10, pady=5)

    def add_msg(text):
        tk.Label(history_frame, text=text, fg="white", bg="#1e1e2e", wraplength=300).pack(anchor="w")

    input_var = tk.StringVar()
    entry = tk.Entry(popup, textvariable=input_var)
    entry.pack(fill="x", padx=10, pady=5)

    def send():
        q = input_var.get().strip()
        if not q:
            return
        input_var.set("")
        add_msg("You: " + q)

        def worker():
            reply = chat_with_context(selected_text, q, chat_history)
            chat_history.append({"role": "user", "content": q})
            chat_history.append({"role": "assistant", "content": reply})
            popup.after(0, lambda: add_msg("AI: " + reply))

        threading.Thread(target=worker, daemon=True).start()

    entry.bind("<Return>", lambda e: send())

    position_popup(popup)
    focus_window(popup, entry)

# ── Handlers ──────────────────────────────────────────────────────────────────

def handle_translate():
    if not _action_lock.acquire(False):
        return
    
    def worker():
        try:
            # Sleep slightly to let the OS finish putting text on the clipboard
            time.sleep(0.1)
            text = pyperclip.paste().strip()
            if text:
                result = translate(text)
                # Safely push the UI creation back to the main thread
                _root.after(0, lambda: show_translate_popup(text, result))
        finally:
            _action_lock.release()
            
    # Fire and forget the network request so the keyboard hook is instantly freed
    threading.Thread(target=worker, daemon=True).start()

def handle_chat():
    if not _action_lock.acquire(False):
        return
        
    def worker():
        try:
            # Sleep slightly to let the OS finish putting text on the clipboard
            time.sleep(0.1)
            text = pyperclip.paste().strip()
            if text:
                _root.after(0, lambda: show_chat_popup(text))
        finally:
            _action_lock.release()
            
    # Free up the keyboard hook instantly
    threading.Thread(target=worker, daemon=True).start()

# ── Hotkey ────────────────────────────────────────────────────────────────────

_last_time = 0
_waiting = False

def on_key(e):
    global _last_time, _waiting
    now = time.time()

    if e.name == "c" and keyboard.is_pressed("ctrl"):
        if _waiting and now - _last_time < 0.6:
            _waiting = False
            handle_translate()
        else:
            _waiting = True
            _last_time = now

    elif e.name == "space" and keyboard.is_pressed("ctrl") and _waiting:
        _waiting = False
        handle_chat()
    else:
        # Prevent canceling the double-tap sequence just because they let go of 'C' or 'Ctrl'
        if e.event_type == "down" and e.name not in ["ctrl", "c"]:
            _waiting = False

keyboard.hook(on_key)

# ── Tray ──────────────────────────────────────────────────────────────────────

def make_icon():
    img = Image.new("RGB", (64, 64), "blue")
    return img

def quit_app():
    # Safely tell the Tkinter main loop to destroy itself from the tray's thread
    _root.after(0, _root.destroy)

def build_tray():
    icon = pystray.Icon("QuickTranslator")
    icon.icon = make_icon()
    icon.menu = pystray.Menu(
        pystray.MenuItem("Quit", quit_app)
    )
    icon.run()

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    threading.Thread(target=build_tray, daemon=True).start()
    _root.mainloop()
