"""Shared colour palette, font constants, and UI helpers (Catppuccin Mocha)."""

# ── Colours ──────────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
MANTLE    = "#181825"
CRUST     = "#11111b"
SURFACE   = "#313244"
SURFACE1  = "#45475a"
SURFACE2  = "#585b70"
OVERLAY   = "#45475a"
OVERLAY1  = "#585b70"
MUTED     = "#6c7086"
SUBTEXT   = "#a6adc8"
TEXT_C    = "#cdd6f4"
BLUE      = "#89b4fa"
CYAN      = "#89dceb"
SAPPHIRE  = "#74c7ec"
GREEN     = "#a6e3a1"
YELLOW    = "#f9e2af"
MAUVE     = "#cba6f7"
RED       = "#f38ba8"
PEACH     = "#fab387"
LAVENDER  = "#b4befe"
CODE_BG   = "#181825"
CODE_FG   = "#cdd6f4"
SCROLLBAR = "#45475a"

# Derived / semantic
BORDER    = "#313244"
SHADOW    = "#11111b"
USER_BG   = "#2a2b3d"   # subtle distinct bg for user bubbles
AI_BG     = "#1e1e2e"   # AI bubbles keep main bg
INPUT_BG  = "#262637"   # slightly lighter input field bg
ACCENT    = BLUE

# ── Fonts ────��───────────────────────────────────────────────────────────────
_FONT     = "Segoe UI"
FONT_UI   = (_FONT, 10)
FONT_BOLD = (_FONT, 10, "bold")
FONT_ITAL = (_FONT, 10, "italic")
FONT_BI   = (_FONT, 10, "bold italic")
FONT_MONO = ("Consolas", 10)
FONT_H1   = (_FONT, 14, "bold")
FONT_H2   = (_FONT, 12, "bold")
FONT_H3   = (_FONT, 11, "bold")
FONT_SM   = (_FONT, 9)
FONT_XS   = (_FONT, 8)

WRAP_WIDTH = 440  # px — wraplength for message labels

# ── Padding / radius constants ───────────────────────────────────────────────
PAD_SM    = 6
PAD       = 12
PAD_LG    = 18
CORNER_R  = 8    # conceptual corner radius (used for frame padding tricks)


# ── Hover helper ─────────────────────────────────────────────────────────────
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


# ── Fade-in animation helper ────────────────────────────────────────────────
def fade_in(toplevel, duration_ms: int = 150, target_alpha: float = 0.97):
    """Smoothly fade a Toplevel from 0 → target_alpha."""
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
