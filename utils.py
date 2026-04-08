"""Shared UI utilities used by multiple popup modules."""

import tkinter as tk


def bind_close_outside(popup: tk.Toplevel, close_fn):
    """Close popup when clicking outside it. Cleans up on destroy."""
    _state = {"unbound": False}

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
        if _state["unbound"]:
            return
        _state["unbound"] = True
        try:
            # unbind_all removes ALL handlers for this event, so we use the
            # root widget's unbind with the specific bind_id instead.
            popup.winfo_toplevel().unbind("<Button-1>", bind_id)
        except Exception:
            try:
                popup.unbind_all("<Button-1>")
            except Exception:
                pass

    popup.bind("<Destroy>", lambda e: _unbind(), add=True)


def block_edits(event):
    """Key handler that makes a tk.Text read-only while allowing selection/copy."""
    # Allow copy / select-all
    if event.state & 0x4:  # Ctrl held
        if event.keysym.lower() in ("a", "c"):
            return
        return "break"
    # Allow navigation and selection keys
    if event.keysym in (
        "Left", "Right", "Up", "Down",
        "Home", "End", "Prior", "Next",
        "Shift_L", "Shift_R",
        "Control_L", "Control_R",
    ):
        return
    return "break"
