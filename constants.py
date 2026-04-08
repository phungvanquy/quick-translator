"""Shared colour palette, font constants, and UI helpers.

Design system inspired by Linear / GitHub dark -- a professional, clean
dark palette with high-contrast text and subtle accent colours.
"""

import platform
import tkinter as tk

# -- Platform-aware font family ------------------------------------------------
_system = platform.system()
if _system == "Windows":
    _FONT = "Segoe UI"
    _MONO = "Consolas"
elif _system == "Darwin":
    _FONT = "SF Pro Text"
    _MONO = "Menlo"
else:  # Linux / other
    _FONT = "Noto Sans"
    _MONO = "Noto Sans Mono"

# -- Colours -------------------------------------------------------------------
# Base backgrounds -- dark, neutral-cool greys
BG        = "#0d1117"   # main background  (GitHub dark)
MANTLE    = "#010409"   # deepest layer
CRUST     = "#010409"
SURFACE   = "#161b22"   # cards, header bars
SURFACE1  = "#21262d"   # elevated surfaces, dividers
SURFACE2  = "#30363d"   # higher-contrast surface

# Overlays / interactive state layers
OVERLAY   = "#21262d"
OVERLAY1  = "#30363d"

# Text hierarchy
MUTED     = "#484f58"   # disabled / hint text
SUBTEXT   = "#8b949e"   # secondary text
TEXT_C    = "#e6edf3"   # primary text (WCAG AA on #0d1117)

# Accent palette -- restrained, professional
BLUE      = "#58a6ff"   # primary accent (links, focus rings)
CYAN      = "#56d4dd"
SAPPHIRE  = "#79c0ff"   # lighter hover state for blue buttons
GREEN     = "#3fb950"   # success
YELLOW    = "#d29922"   # warning
MAUVE     = "#bc8cff"   # headings, decorative
RED       = "#f85149"   # danger / close button
PEACH     = "#f0883e"
LAVENDER  = "#d2a8ff"

# Code blocks
CODE_BG   = "#161b22"
CODE_FG   = "#e6edf3"
SCROLLBAR = "#30363d"

# Derived / semantic
BORDER    = "#21262d"
SHADOW    = "#010409"
USER_BG   = "#121a27"   # subtle blue-tint for user bubbles
AI_BG     = "#0d1117"   # AI bubbles keep main bg
INPUT_BG  = "#0d1117"   # input field matches main bg
INPUT_BORDER = "#30363d"
ACCENT    = BLUE

# Button-specific semantic tokens
BTN_PRIMARY_BG    = "#238636"   # green primary action (GitHub style)
BTN_PRIMARY_FG    = "#ffffff"
BTN_PRIMARY_HOVER = "#2ea043"
BTN_SECONDARY_BG  = "#21262d"
BTN_SECONDARY_FG  = "#c9d1d9"
BTN_SECONDARY_HOVER = "#30363d"
BTN_DANGER_BG     = "#21262d"
BTN_DANGER_FG     = "#f85149"
BTN_DANGER_HOVER  = "#da3633"

# -- Fonts ---------------------------------------------------------------------
# Expose _FONT for one-off font tuples in other modules
FONT_FAMILY = _FONT
FONT_MONO_FAMILY = _MONO
FONT_UI   = (_FONT, 10)
FONT_BOLD = (_FONT, 10, "bold")
FONT_ITAL = (_FONT, 10, "italic")
FONT_BI   = (_FONT, 10, "bold italic")
FONT_MONO = (_MONO, 10)
FONT_H1   = (_FONT, 14, "bold")
FONT_H2   = (_FONT, 12, "bold")
FONT_H3   = (_FONT, 11, "bold")
FONT_SM   = (_FONT, 9)
FONT_XS   = (_FONT, 8)
FONT_BTN  = (_FONT, 9, "bold")
FONT_BTN_LG = (_FONT, 10, "bold")

WRAP_WIDTH = 440  # px -- wraplength for message labels

# -- Padding / radius constants ------------------------------------------------
PAD_SM    = 6
PAD       = 12
PAD_LG    = 18
CORNER_R  = 8    # conceptual corner radius (used for frame padding tricks)


# -- Hover helper --------------------------------------------------------------
def bind_hover(widget, enter_bg, leave_bg, enter_fg=None, leave_fg=None):
    """Bind mouse enter/leave colour changes to a widget."""
    def on_enter(e):
        widget.config(bg=enter_bg)
        if enter_fg:
            widget.config(fg=enter_fg)
    def on_leave(e):
        widget.config(bg=leave_bg)
        if leave_fg:
            widget.config(fg=leave_fg)
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


# -- Fade-in animation helper -------------------------------------------------
def fade_in(toplevel, duration_ms: int = 150, target_alpha: float = 0.97):
    """Smoothly fade a Toplevel from 0 to target_alpha."""
    steps = max(1, duration_ms // 16)  # ~60fps
    step_alpha = target_alpha / steps
    toplevel.attributes("-alpha", 0.0)

    def _step(i=0):
        if i >= steps:
            toplevel.attributes("-alpha", target_alpha)
            return
        try:
            toplevel.attributes("-alpha", min(step_alpha * (i + 1), target_alpha))
            toplevel.after(16, lambda: _step(i + 1))
        except Exception:
            pass

    toplevel.after(10, _step)


# -- Animated loading spinner --------------------------------------------------
_SPINNER_FRAMES = [
    "\u280b", "\u2819", "\u2839", "\u2838",
    "\u283c", "\u2834", "\u2826", "\u2827",
    "\u2807", "\u280f",
]


class LoadingSpinner:
    """Animated braille-dot spinner inside a tk.Text widget.

    Usage::

        spinner = LoadingSpinner(text_widget)
        spinner.start()
        # ... later ...
        spinner.stop()
    """

    def __init__(self, text_widget: tk.Text, label: str = " Thinking\u2026",
                 interval_ms: int = 80):
        self._widget = text_widget
        self._label = label
        self._interval = interval_ms
        self._frame_idx = 0
        self._running = False
        self._after_id = None

    def start(self):
        self._running = True
        self._frame_idx = 0
        self._widget.delete("1.0", tk.END)
        self._tick()

    def _tick(self):
        if not self._running or self._widget is None:
            return
        try:
            if not self._widget.winfo_exists():
                self._cleanup()
                return
        except tk.TclError:
            self._cleanup()
            return
        self._widget.delete("1.0", tk.END)
        frame = _SPINNER_FRAMES[self._frame_idx % len(_SPINNER_FRAMES)]
        self._widget.insert(tk.END, f"{frame}{self._label}", "normal")
        self._frame_idx += 1
        self._after_id = self._widget.after(self._interval, self._tick)

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                if self._widget is not None:
                    self._widget.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None

    def _cleanup(self):
        """Release all references so the widget can be GC'd."""
        self._running = False
        if self._after_id is not None:
            try:
                if self._widget is not None:
                    self._widget.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None
        self._widget = None
