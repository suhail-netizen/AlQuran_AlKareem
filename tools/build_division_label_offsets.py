# Measures, per division tag, how far above its anchor the tag should sit, from the rendered page
# itself. Anchors (build_division_markers.py) lie on a text line: a printed rub-el-hizb star, or the
# previous surah's last ayah-end circle. The tag belongs in the band between that line and the line
# above it. That gap isn't always fully blank (a tall letter from either line can cross it) and line
# spacing varies across pages, so rather than a fixed offset the tag is slid through the band and
# placed where it covers the least ink.
#
# Requires tools/screenshot_pages.js to have screenshotted every page with markers (labels hidden)
# into data/_page_shots/*.png.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/build_division_label_offsets.py

import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from compose_page import DATA_DIR, DIVISION_LABEL_H, MushafData, _content_px, division_tag_center

SHOTS_DIR = os.path.join(DATA_DIR, '_page_shots')

MID_RANGE = (45, 115)  # tag center sits this many px above its anchor: the band between the
                       # anchor's own line and the line above it
TAG_HALF_W = 80        # approximate half-width of a division tag, px


def least_ink_mid(arr, tag_center_x, anchor_top):
    x0 = max(0, int(tag_center_x - TAG_HALF_W))
    x1 = min(arr.shape[1], int(tag_center_x + TAG_HALF_W))
    ink = (255.0 - arr[:, x0:x1]).sum(axis=1)
    half_h = DIVISION_LABEL_H // 2
    band_mid = sum(MID_RANGE) / 2
    best = None
    for dy in range(MID_RANGE[0], MID_RANGE[1] + 1):
        mid = int(anchor_top) - dy
        cost = ink[mid - half_h:mid + half_h].sum()
        # On ties prefer the middle of the band: a blank gap is flat, so center the tag in it.
        key = (cost, abs(dy - band_mid))
        if best is None or key < best[0]:
            best = (key, mid)
    return best[1]


def main():
    data = MushafData()
    offsets = {}
    for page_str, entries in data.division_markers.items():
        arr = np.array(Image.open(os.path.join(SHOTS_DIR, f'{int(page_str):03d}.png')).convert('L'))
        for e in entries:
            key = f"{e['surah']}:{e['ayah']}"
            if key in offsets:
                continue
            anchor_left, anchor_top = _content_px(e['x'], e['y'])
            mid = least_ink_mid(arr, division_tag_center(data, e, anchor_left), anchor_top)
            offsets[key] = round(mid - DIVISION_LABEL_H / 2 - anchor_top, 2)

    out_path = os.path.join(DATA_DIR, 'division_label_offsets.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(offsets, f, indent=1)
    print(f'wrote {out_path} - {len(offsets)} offsets')


if __name__ == '__main__':
    main()
