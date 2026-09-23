# Mushaf Overlay App - core engine.
# Draws markers onto the real Madinah mushaf page scans (data/pages/, standard1/green theme), using
# pixel positions and label images already precomputed and verified. No web/Chromium dependency at
# runtime - labels are pre-rendered image assets.
#
# Two modes:
#   'ramadan'  - the 304 rak'ah-end markers (tarawih/tahajjud N) + a repeating "night N" header,
#                from data/rakah_markers.json + data/page_night_map.json + data/labels/.
#   'standard' - the 556 traditional ruku markers, from data/standard_ruku_markers.json +
#                data/labels_standard_ruku/. No night header in this mode.

import json
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
PAGES_DIR = os.path.join(DATA_DIR, 'pages')

GREEN = (203, 231, 190)  # same pale green as the mushaf's own ayah-marker circles
TOTAL_PAGES = 604

MODES = ('ramadan', 'standard')


class MushafOverlayData:
    def __init__(self, mode='ramadan'):
        if mode not in MODES:
            raise ValueError(f'unknown mode: {mode}')
        self.mode = mode
        self._label_cache = {}

        if mode == 'ramadan':
            with open(os.path.join(DATA_DIR, 'rakah_markers.json'), encoding='utf-8') as f:
                self.markers = json.load(f)
            with open(os.path.join(DATA_DIR, 'page_night_map.json'), encoding='utf-8') as f:
                self.page_night = json.load(f)
            self.labels_dir = os.path.join(DATA_DIR, 'labels')
        else:
            with open(os.path.join(DATA_DIR, 'standard_ruku_markers.json'), encoding='utf-8') as f:
                self.markers = json.load(f)
            self.page_night = {}
            self.labels_dir = os.path.join(DATA_DIR, 'labels_standard_ruku')

        with open(os.path.join(self.labels_dir, 'manifest.json'), encoding='utf-8') as f:
            self._manifest = json.load(f)

    def label_image(self, text):
        if text not in self._label_cache:
            fname = self._manifest[text]
            self._label_cache[text] = Image.open(os.path.join(self.labels_dir, fname)).convert('RGBA')
        return self._label_cache[text]

    def label_text_for_marker(self, entry):
        if self.mode == 'ramadan':
            return f"{SESSION_AR[entry['session']]} {entry['rakah']}"
        return f"ركوع {entry['ruku']}"


SESSION_AR = {'Taraweeh': 'تراويح', 'Tahajjud': 'تهجد'}


def night_label_text(night_value):
    if isinstance(night_value, list):
        return " - ".join(f"الليلة {n}" for n in night_value)
    return f"الليلة {night_value}"


def _draw_marker_ring(draw, entry, color=GREEN, width=5, pad=10):
    x, y, w, h = entry['x'], entry['y'], entry['w'], entry['h']
    draw.ellipse([x - pad, y - pad, x + w + pad, y + h + pad], outline=color, width=width)


def _top_row_gap_center(im):
    import numpy as np
    gray = np.array(im.convert('L'))
    dark_full = gray < 200
    row_counts = dark_full.sum(axis=1)
    band_bottom = len(row_counts)
    for y in range(20, len(row_counts)):
        if row_counts[y] > 400:
            band_bottom = y
            break
    region = gray[0:band_bottom, :]
    dark = region < 200
    ys, xs = np.where(dark)
    w = gray.shape[1]
    mid = w // 2
    left_xs = xs[xs < mid]
    right_xs = xs[xs >= mid]
    gap_x0 = left_xs.max() if len(left_xs) else 0
    gap_x1 = right_xs.min() if len(right_xs) else w
    cy = (ys.min() + ys.max()) / 2 if len(ys) else 140
    return (gap_x0 + gap_x1) / 2, cy


def _paste_label(im, label_im, cx, cy):
    x = int(cx - label_im.width / 2)
    y = int(cy - label_im.height / 2)
    im.paste(label_im, (x, y), label_im)


def _paste_label_near(im, label_im, entry, above=True, gap=20):
    x, y, w, h = entry['x'], entry['y'], entry['w'], entry['h']
    cx = x + w / 2
    cy = y - gap - label_im.height / 2 if above else y + h + gap + label_im.height / 2
    _paste_label(im, label_im, cx, cy)


def render_page(data: MushafOverlayData, page_num: int) -> Image.Image:
    """Returns the fully-overlaid image for one real mushaf page (1..604)."""
    im = Image.open(os.path.join(PAGES_DIR, f'{page_num:03d}.png')).convert('RGB')
    draw = ImageDraw.Draw(im)

    for entry in data.markers.get(str(page_num), []):
        _draw_marker_ring(draw, entry)
        label_im = data.label_image(data.label_text_for_marker(entry))
        _paste_label_near(im, label_im, entry, above=True)

    night = data.page_night.get(str(page_num))
    if night is not None:
        cx, cy = _top_row_gap_center(im)
        _paste_label(im, data.label_image(night_label_text(night)), cx, cy)

    return im
