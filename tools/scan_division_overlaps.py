# QA scan: for every division marker across the whole book, checks whether its label's own
# rendered bounding box lands on top of real ayah-text ink (using the label-free page screenshots
# in tools/_tmp_pages/*.png as ground truth) - flags any that overlap significantly so they can be
# reviewed, instead of relying on spot-checking individual pages by eye.
#
# Requires tools/_tmp_shot_pages.js to have been run against the CURRENT output/ (labels hidden).
#
# Usage: run from the Mushaf_Overlay_App root: python tools/scan_division_overlaps.py

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compose_page as cp

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(APP_ROOT, 'data')
SHOTS_DIR = os.path.join(HERE, '_tmp_pages')

DARK_PIXEL = 40  # a grayscale pixel below this is "ink"
OVERLAP_RATIO_FLAG = 0.03  # flag if more than 3% of the label's own footprint sits on ink

DIVISION_PRIORITY = cp.DIVISION_PRIORITY


def main():
    with open(os.path.join(DATA_DIR, 'division_markers.json'), encoding='utf-8') as f:
        division_markers = json.load(f)
    with open(os.path.join(DATA_DIR, 'division_label_offsets.json'), encoding='utf-8') as f:
        offsets = json.load(f)
    with open(os.path.join(DATA_DIR, 'labels_slate', 'manifest.json'), encoding='utf-8') as f:
        slate_manifest = json.load(f)

    png_size_cache = {}

    def label_wh(text):
        if text not in png_size_cache:
            path = os.path.join(DATA_DIR, 'labels_slate', slate_manifest[text])
            with Image.open(path) as im:
                w, h = im.size
            png_size_cache[text] = (w * 46 / h, 46)
        return png_size_cache[text]

    flagged = []
    for page_str, entries in sorted(division_markers.items(), key=lambda kv: int(kv[0])):
        shot_path = os.path.join(SHOTS_DIR, f'{int(page_str):03d}.png')
        if not os.path.exists(shot_path):
            continue
        img = np.array(Image.open(shot_path).convert('L'))

        # Same all-kinds-enabled dedup compose_page.py itself applies.
        by_position = {}
        for e in entries:
            pos = (e['surah'], e['ayah'])
            best = by_position.get(pos)
            if best is None or DIVISION_PRIORITY[e['kind']] > DIVISION_PRIORITY[best['kind']]:
                by_position[pos] = e

        text_svg = cp._read_text_svg(int(page_str))
        vb_min_x, vb_min_y = cp._viewbox_origin(text_svg)

        for e in by_position.values():
            key = f"{e['surah']}:{e['ayah']}"
            info = offsets.get(key)
            anchor_y = info['anchor_y'] if info else e['y']
            offset = info['offset'] if info else -75.0
            cx = e['x'] - vb_min_x
            cy = anchor_y - vb_min_y
            anchor_left, anchor_top = cp._content_px(cx, cy)
            label_top = anchor_top + offset
            w, h = label_wh(e['label'])
            x0 = int(anchor_left - w / 2)
            x1 = int(anchor_left + w / 2)
            y0 = int(label_top)
            y1 = int(label_top + h)
            x0c, x1c = max(0, x0), min(img.shape[1], x1)
            y0c, y1c = max(0, y0), min(img.shape[0], y1)
            if x1c <= x0c or y1c <= y0c:
                flagged.append((page_str, key, e['label'], 'off-page', 0.0))
                continue
            region = img[y0c:y1c, x0c:x1c]
            ink_ratio = (region < DARK_PIXEL).mean()
            if ink_ratio > OVERLAP_RATIO_FLAG:
                flagged.append((page_str, key, e['label'], 'overlap', round(float(ink_ratio), 3)))

    print(f'checked {sum(1 for _ in division_markers)} pages, {len(flagged)} flagged markers')
    for row in flagged:
        print(row)


if __name__ == '__main__':
    main()
