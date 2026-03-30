"""Shared colour palette and font constants (Catppuccin Mocha)."""

# ── Colours ──────────────────────────────────────────────────────────────────
BG        = "#1e1e2e"
MANTLE    = "#181825"
CRUST     = "#11111b"
SURFACE   = "#313244"
SURFACE1  = "#45475a"
OVERLAY   = "#45475a"
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
CODE_BG   = "#181825"
CODE_FG   = "#cdd6f4"
SCROLLBAR = "#45475a"

# ── Fonts ────────────────────────────────────────────────────────────────────
FONT_UI   = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_ITAL = ("Segoe UI", 10, "italic")
FONT_BI   = ("Segoe UI", 10, "bold italic")
FONT_MONO = ("Consolas", 10)
FONT_H1   = ("Segoe UI", 14, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_H3   = ("Segoe UI", 11, "bold")
FONT_SM   = ("Segoe UI", 9)
FONT_XS   = ("Segoe UI", 8)

WRAP_WIDTH = 440  # px — wraplength for message labels


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
