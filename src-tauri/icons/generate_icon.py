#!/usr/bin/env python3
"""Generate the Quick Translator app icon (icon.png + icon.ico).

Brand mark: a two-arrows exchange glyph (⇄) in white on an indigo gradient,
rounded-square background. Mirrors the geometry in brand.svg.

Requires Pillow. Run once; the generated PNG/ICO are committed.
    python generate_icon.py
"""
from PIL import Image, ImageDraw

SIZE = 512
SS = 4  # supersample factor for smooth edges
S = SIZE * SS

ACCENT_TOP = (124, 107, 255)   # #7C6BFF
ACCENT_BOT = (109, 90, 230)    # #6D5AE6
WHITE = (255, 255, 255, 255)


def diagonal_gradient(size, c0, c1):
    """Top-left -> bottom-right linear gradient."""
    base = Image.new("RGB", (size, size), c0)
    top = Image.new("RGB", (size, size), c1)
    mask = Image.new("L", (size, size))
    px = mask.load()
    for y in range(size):
        for x in range(size):
            px[x, y] = int((x + y) / (2 * (size - 1)) * 255)
    base.paste(top, (0, 0), mask)
    return base


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return m


def draw_arrows(img):
    d = ImageDraw.Draw(img)
    w = 34 * SS
    def line(pts):
        d.line([(x * SS, y * SS) for x, y in pts], fill=WHITE, width=w, joint="curve")
    def cap(pts):  # round the endpoints
        for x, y in pts:
            r = w // 2
            d.ellipse([x * SS - r, y * SS - r, x * SS + r, y * SS + r], fill=WHITE)
    # top arrow →
    line([(150, 196), (360, 196)])
    line([(312, 148), (360, 196), (312, 244)])
    cap([(150, 196), (360, 196), (312, 148), (312, 244)])
    # bottom arrow ←
    line([(362, 316), (152, 316)])
    line([(200, 268), (152, 316), (200, 364)])
    cap([(362, 316), (152, 316), (200, 268), (200, 364)])


def build():
    grad = diagonal_gradient(S, ACCENT_TOP, ACCENT_BOT).convert("RGBA")
    mask = rounded_mask(S, radius=112 * SS)
    icon = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    icon.paste(grad, (0, 0), mask)
    draw_arrows(icon)
    icon = icon.resize((SIZE, SIZE), Image.LANCZOS)
    return icon


def main():
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    icon = build()
    icon.save(os.path.join(here, "icon.png"))
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.save(os.path.join(here, "icon.ico"), sizes=sizes)
    print("wrote icon.png (512) and icon.ico", sizes)


if __name__ == "__main__":
    main()
