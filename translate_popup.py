"""Translation popup window for Quick Translator."""

import threading
import tkinter as tk

from config import get_config
from utils import bind_close_outside, block_edits
from constants import (
    BG, SURFACE, SURFACE1, OVERLAY, MUTED, SUBTEXT, TEXT_C,
    RED, BORDER, SHADOW,
    FONT_FAMILY, FONT_SM, FONT_XS,
    PAD_SM, PAD, PAD_LG,
    bind_hover, fade_in, LoadingSpinner,
)
from chat_popup import _configure_tags, render_markdown_to_text
from tts import speak_text, stop_speaking


def show_translate_popup(original: str, stream_gen, get_tk_root=None) -> None:
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
        try:
            stop_speaking()
            _spinner.stop()
            popup.destroy()
        except Exception:
            pass

    # ── Outer border frame (1px shadow border) ────────────────────────────────
    border = tk.Frame(popup, bg=BORDER, bd=0)
    border.pack(fill="both", expand=True, padx=1, pady=1)

    inner = tk.Frame(border, bg=BG, bd=0)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Header (drag handle) ──────────────────────────────────────────────────
    header = tk.Frame(inner, bg=SURFACE, padx=PAD, pady=10)
    header.pack(fill="x")
    header.grid_columnconfigure(0, weight=1)  # title stretches
    header.grid_columnconfigure(1, weight=0)  # close button fixed

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
    title_lbl.grid(row=0, column=0, sticky="w")
    title_lbl.bind("<Button-1>",  _press)
    title_lbl.bind("<B1-Motion>", _drag)

    close_btn = tk.Button(header, text="✕", command=close, bg=SURFACE, fg=MUTED,
                          font=FONT_SM, relief="flat", padx=8, pady=2,
                          cursor="hand2", activebackground=RED,
                          activeforeground=TEXT_C, bd=0)
    close_btn.grid(row=0, column=1, sticky="e", padx=(PAD_SM, 0))
    bind_hover(close_btn, RED, SURFACE, TEXT_C, MUTED)

    # ── Original text (muted, selectable) ─────────────────────────────────────
    orig_short = original if len(original) < 120 else original[:117] + "…"
    orig_lbl = tk.Label(inner, text=orig_short, bg=BG, fg=MUTED,
                        font=FONT_XS, wraplength=WIN_W - pad * 2 - 4,
                        justify="left", anchor="w")
    orig_lbl.pack(anchor="w", fill="x", padx=pad, pady=(PAD, PAD_SM))

    # Separator
    tk.Frame(inner, bg=SURFACE1, height=1).pack(fill="x", padx=pad)

    # ── Translation result (selectable Text widget) ───────────────────────────
    trans_text = tk.Text(inner, bg=BG, fg=TEXT_C, font=(FONT_FAMILY, 12),
                         wrap="word", relief="flat", bd=0, padx=pad, pady=10,
                         highlightthickness=0, cursor="xterm",
                         selectbackground=OVERLAY, selectforeground=TEXT_C,
                         inactiveselectbackground=OVERLAY,
                         height=2, spacing1=2, spacing3=2)
    _configure_tags(trans_text)
    trans_text.config(state="normal")
    trans_text.pack(anchor="w", fill="x", padx=0, pady=(6, 0))

    # Animated loading spinner (replaces static emoji)
    _spinner = LoadingSpinner(trans_text, label=" Translating\u2026")
    _spinner.start()

    # Read-only: block edits but allow selection
    trans_text.bind("<Key>", block_edits)

    # ── Bottom bar ────────────────────────────────────────────────────────────
    bottom = tk.Frame(inner, bg=BG)
    bottom.pack(fill="x", padx=pad, pady=(PAD_SM, PAD))

    _full_text = {"value": ""}

    hint_lbl = tk.Label(bottom, text="Esc to close · Ctrl+C to copy",
                        bg=BG, fg=MUTED, font=FONT_XS, anchor="w")
    hint_lbl.pack(side="left")

    # 🔊 Read-aloud button — reads selected text, or full translation if nothing selected
    def _speak_selected():
        try:
            sel = trans_text.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            sel = ""
        text = sel.strip() if sel.strip() else _full_text["value"]
        if text:
            speak_text(text)

    speak_btn = tk.Button(bottom, text="🔊", command=_speak_selected,
                          bg=BG, fg=MUTED, font=FONT_SM, relief="flat",
                          padx=6, pady=0, cursor="hand2",
                          activebackground=SURFACE1, activeforeground=TEXT_C, bd=0)
    speak_btn.pack(side="right")
    bind_hover(speak_btn, SURFACE1, BG, TEXT_C, MUTED)

    popup.bind("<Escape>", close)
    bind_close_outside(popup, close)

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
            _spinner.stop()
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
            # Close the generator to release the OpenAI HTTP stream
            try:
                stream_gen.close()
            except Exception:
                pass
            if popup.winfo_exists():
                popup.after(0, _stream_done)

    threading.Thread(target=_do_stream, daemon=True).start()
