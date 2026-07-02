"""Settings window for Quick Translator."""

import tkinter as tk
from tkinter import ttk

from config import get_config, update_config, DEFAULT_PROMPT
from constants import (
    BG, SURFACE, SURFACE1, OVERLAY, MUTED, SUBTEXT, TEXT_C,
    BORDER, INPUT_BORDER, ACCENT,
    BTN_PRIMARY_BG, BTN_PRIMARY_FG, BTN_PRIMARY_HOVER,
    BTN_SECONDARY_BG, BTN_SECONDARY_FG, BTN_SECONDARY_HOVER,
    FONT_FAMILY, FONT_UI, FONT_XS, FONT_BTN_LG,
    PAD_SM, PAD, PAD_LG,
    bind_hover,
)


def open_settings(get_tk_root) -> None:
    cfg = get_config()
    root = get_tk_root()
    win = tk.Toplevel(root)
    win.title("Quick Translator — Settings")
    win.resizable(False, False)
    win.configure(bg=BG)
    win.attributes("-topmost", True)
    w, h = 500, 660
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    style = ttk.Style(win)
    style.theme_use("clam")
    style.configure("TLabel", background=BG, foreground=TEXT_C, font=FONT_UI)
    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT_C,
                    insertcolor=TEXT_C)
    style.configure("Section.TLabel", background=BG, foreground=SUBTEXT,
                    font=(FONT_FAMILY, 8, "bold"))

    pad_x = 28

    # ── Bottom buttons (packed FIRST with side='bottom' to reserve space) ────
    btn_frame = tk.Frame(win, bg=BG)
    btn_frame.pack(side="bottom", fill="x", padx=pad_x, pady=(PAD, PAD_LG))

    bottom_sep = tk.Frame(win, bg=SURFACE1, height=1)
    bottom_sep.pack(side="bottom", fill="x", padx=pad_x, pady=0)

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
                           bg=BTN_SECONDARY_BG, fg=BTN_SECONDARY_FG,
                           font=FONT_BTN_LG, relief="flat",
                           padx=24, pady=0, cursor="hand2",
                           activebackground=BTN_SECONDARY_HOVER,
                           activeforeground=TEXT_C, bd=0)
    cancel_btn.pack(side="right", padx=(PAD, 0), ipady=10)
    bind_hover(cancel_btn, BTN_SECONDARY_HOVER, BTN_SECONDARY_BG)

    save_btn = tk.Button(btn_frame, text="Save changes", command=save_and_close,
                         bg=BTN_PRIMARY_BG, fg=BTN_PRIMARY_FG,
                         font=FONT_BTN_LG, relief="flat",
                         padx=24, pady=0, cursor="hand2",
                         activebackground=BTN_PRIMARY_HOVER,
                         activeforeground=BTN_PRIMARY_FG, bd=0)
    save_btn.pack(side="right", ipady=10)
    bind_hover(save_btn, BTN_PRIMARY_HOVER, BTN_PRIMARY_BG)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(win, bg=SURFACE, height=52)
    hdr.pack(fill="x")
    hdr.pack_propagate(False)
    tk.Label(hdr, text="Settings", bg=SURFACE, fg=TEXT_C,
             font=(FONT_FAMILY, 12, "bold"), padx=pad_x).pack(
                 side="left", fill="y")

    # ── Section: API ──────────────────────────────────────────────────────────
    ttk.Label(win, text="API CONFIGURATION", style="Section.TLabel").pack(
        anchor="w", padx=pad_x, pady=(PAD_LG, 4))
    tk.Frame(win, bg=SURFACE1, height=1).pack(fill="x", padx=pad_x, pady=(0, 4))

    def entry_row(label, default, show=None):
        ttk.Label(win, text=label).pack(anchor="w", padx=pad_x, pady=(8, 3))
        var = tk.StringVar(value=default)
        row_frame = tk.Frame(win, bg=BG)
        row_frame.pack(padx=pad_x, fill="x")
        row_frame.grid_columnconfigure(0, weight=1)
        e = tk.Entry(row_frame, textvariable=var, bg=SURFACE, fg=TEXT_C,
                     insertbackground=TEXT_C, font=FONT_UI, relief="flat",
                     highlightthickness=1, highlightbackground=INPUT_BORDER,
                     highlightcolor=ACCENT, bd=6,
                     show=show or "")
        e.grid(row=0, column=0, sticky="ew", ipady=4)
        return var, e, row_frame

    api_var, api_entry, api_row = entry_row("API Key", cfg["api_key"], show="•")
    url_var, _, _ = entry_row("Base URL", cfg["base_url"])
    model_var, _, _ = entry_row("Model", cfg["model"])

    _key_visible = {"v": False}
    def toggle_key():
        _key_visible["v"] = not _key_visible["v"]
        api_entry.config(show="" if _key_visible["v"] else "•")
        show_btn.config(text="Hide" if _key_visible["v"] else "Show")

    show_btn = tk.Button(api_row, text="Show", command=toggle_key,
                         bg=BTN_SECONDARY_BG, fg=SUBTEXT, font=FONT_XS,
                         relief="flat", padx=10, pady=3, cursor="hand2",
                         activebackground=BTN_SECONDARY_HOVER,
                         activeforeground=TEXT_C, bd=0)
    show_btn.grid(row=0, column=1, sticky="e", padx=(PAD_SM, 0))
    bind_hover(show_btn, BTN_SECONDARY_HOVER, BTN_SECONDARY_BG)

    # ── Section: Translation ──────────────────────────────────────────────────
    ttk.Label(win, text="TRANSLATION", style="Section.TLabel").pack(
        anchor="w", padx=pad_x, pady=(PAD_LG, 4))
    tk.Frame(win, bg=SURFACE1, height=1).pack(fill="x", padx=pad_x, pady=(0, 4))

    lang_var, _, _ = entry_row("Target Language", cfg["target_language"])

    # Custom prompt
    ttk.Label(win, text="Custom Prompt").pack(anchor="w", padx=pad_x, pady=(8, 3))
    prompt_text = tk.Text(win, bg=SURFACE, fg=TEXT_C,
                          insertbackground=TEXT_C, font=FONT_UI,
                          relief="flat", bd=6, height=4, wrap="word",
                          highlightthickness=1, highlightbackground=INPUT_BORDER,
                          highlightcolor=ACCENT, selectbackground=OVERLAY,
                          selectforeground=TEXT_C)
    prompt_text.pack(padx=pad_x, fill="x")
    prompt_text.insert("1.0", cfg.get("custom_prompt", DEFAULT_PROMPT))

    hint = tk.Label(win, text="Use {target_language} as placeholder.  Leave blank for default.",
                    bg=BG, fg=SUBTEXT, font=FONT_XS, anchor="w")
    hint.pack(anchor="w", padx=pad_x, pady=(3, 0))

    def reset_prompt():
        prompt_text.delete("1.0", tk.END)
        prompt_text.insert("1.0", DEFAULT_PROMPT)

    reset_btn = tk.Button(win, text="Reset to default", command=reset_prompt,
                          bg=BG, fg=SUBTEXT, font=FONT_XS,
                          relief="flat", padx=0, pady=0, cursor="hand2",
                          activebackground=BG, activeforeground=TEXT_C, bd=0)
    reset_btn.pack(anchor="w", padx=pad_x, pady=(2, 0))
    bind_hover(reset_btn, BG, BG, ACCENT, SUBTEXT)

    win.wait_window()
