#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draws the reader app's home-screen icons into icons/ (the gold eight-pointed star of the page
frame's corner ornament, on the app bar's green). Rerun only if the design changes:

    python make_icons.py
"""

import math
import os

from PIL import Image, ImageDraw

HTML_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HTML_DIR, 'icons')
BG = (26, 54, 54)
GOLD = (212, 175, 55)
DEEP = (45, 80, 22)
CREAM = (255, 251, 245)
BIG = 1024


def square(cx, cy, half, angle):
    pts = []
    for k in range(4):
        a = angle + math.pi / 4 + k * math.pi / 2
        pts.append((cx + half * math.sqrt(2) * math.cos(a), cy + half * math.sqrt(2) * math.sin(a)))
    return pts


def draw(fill_ratio, rounded):
    """fill_ratio: share of the canvas the ornament spans (maskable icons need a safe margin)."""
    img = Image.new('RGBA', (BIG, BIG), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if rounded:
        d.rounded_rectangle([0, 0, BIG - 1, BIG - 1], radius=BIG * 0.22, fill=BG)
    else:
        d.rectangle([0, 0, BIG, BIG], fill=BG)
    c = BIG / 2
    r = BIG * fill_ratio / 2
    d.ellipse([c - r, c - r, c + r, c + r], fill=CREAM, outline=GOLD, width=int(r * 0.07))
    d.ellipse([c - r * 0.82, c - r * 0.82, c + r * 0.82, c + r * 0.82], outline=DEEP, width=int(r * 0.03))
    half = r * 0.42
    for ang in (0, math.pi / 4):
        d.polygon(square(c, c, half, ang), fill=GOLD, outline=DEEP, width=int(r * 0.025))
    d.ellipse([c - r * 0.23, c - r * 0.23, c + r * 0.23, c + r * 0.23], fill=DEEP)
    d.ellipse([c - r * 0.1, c - r * 0.1, c + r * 0.1, c + r * 0.1], fill=CREAM)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    plain = draw(0.78, rounded=False)
    maskable = draw(0.6, rounded=False)      # stays inside the 80% safe zone when the OS crops it
    for size in (192, 512):
        plain.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, f'icon-{size}.png'))
    maskable.resize((512, 512), Image.LANCZOS).save(os.path.join(OUT, 'icon-maskable-512.png'))
    plain.resize((180, 180), Image.LANCZOS).convert('RGB').save(os.path.join(OUT, 'apple-touch-icon.png'))
    draw(0.86, rounded=True).resize((64, 64), Image.LANCZOS).save(os.path.join(OUT, 'favicon.png'))
    print('icons written to', OUT)


if __name__ == '__main__':
    main()
