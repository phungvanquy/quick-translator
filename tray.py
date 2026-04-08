"""System tray icon and shutdown logic for Quick Translator."""

import os
import sys
import threading

import keyboard
import pystray
from PIL import Image, ImageDraw

from api import close_client
from settings import open_settings
from constants import BG, BLUE


def _app_path(filename: str) -> str:
    """Resolve a file path that works both from source and PyInstaller bundle."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def make_icon():
    """Load the app icon from file or generate a fallback."""
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


def build_tray(get_tk_root):
    """Build and run the system tray icon. Blocks until tray is stopped."""
    icon = pystray.Icon("QuickTranslator")
    icon.icon = make_icon()
    icon.title = "Quick Translator"

    def _quit():
        icon.stop()
        _graceful_shutdown(get_tk_root)

    icon.menu = pystray.Menu(
        pystray.MenuItem("Settings", lambda: threading.Thread(
            target=lambda: open_settings(get_tk_root), daemon=True).start()),
        pystray.MenuItem("Quit", _quit),
    )
    icon.run()


def _graceful_shutdown(get_tk_root):
    """Clean up resources before exiting."""
    try:
        keyboard.unhook_all()
    except Exception:
        pass
    try:
        close_client()
    except Exception:
        pass
    try:
        root = get_tk_root()
        root.quit()
        root.destroy()
    except Exception:
        pass
    os._exit(0)
