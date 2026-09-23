# QA scan: for every division tag across the whole book, checks whether the tag as actually
# rendered lands on top of ayah-text ink (using the label-free page screenshots in
# data/_page_shots/*.png as ground truth), and flags any that cover noticeable ink.
#
# Requires tools/screenshot_pages.js to have been run against the CURRENT output/.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/scan_division_overlaps.py

import os
import re
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compose_page as cp

SHOTS_DIR = os.path.join(cp.DATA_DIR, '_page_shots')
DARK_PIXEL = 40             # a grayscale pixel below this is "ink"
OVERLAP_RATIO_FLAG = 0.03   # flag if more than 3% of the tag's footprint sits on ink

TAG_RE = re.compile(r'class="division-label" style="left:([\d.]+)px; top:([\d.-]+)px;"><img src="([^"]+)"')


def main():
    data = cp.MushafData()
    src_to_path = {data.slate_src(t): data.slate_path(t) for t in data.slate_manifest}
    flagged = []
    pages = sorted(int(p) for p in data.division_markers)
    for page in pages:
        img = np.array(Image.open(os.path.join(SHOTS_DIR, f'{page:03d}.png')).convert('L'))
        html = cp.build_page_html(data, page, enabled_divisions=frozenset(cp.DIVISION_PRIORITY))
        for left, top, src in TAG_RE.findall(html):
            left, top = float(left), float(top)
            half_w = cp._display_width(src_to_path[src], cp.DIVISION_LABEL_H) / 2
            region = img[int(top):int(top + cp.DIVISION_LABEL_H), int(left - half_w):int(left + half_w)]
            ink_ratio = float((region < DARK_PIXEL).mean())
            if ink_ratio > OVERLAP_RATIO_FLAG:
                flagged.append((page, round(left), round(top), round(ink_ratio, 3)))

    print(f'checked {len(pages)} pages, {len(flagged)} tags cover noticeable ink (page, x, y, ink ratio)')
    for row in flagged:
        print('  ', row)


if __name__ == '__main__':
    main()
