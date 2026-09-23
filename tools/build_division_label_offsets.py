# Measures, per division marker, the true blank vertical gap nearest its anchor point (the target
# ayah's own row-top/center, from build_division_markers.py's polygon_start_point) and records the
# exact pixel offset needed to center a label in that gap. A single hand-picked offset constant
# (tried earlier: -72) only matched the one page it was calibrated against - row spacing above a
# division anchor isn't constant across pages - so this measures every marker for real instead of
# guessing one more constant.
#
# An earlier version of this script tried to detect and "correct" cases where the ayah's topmost
# polygon row spans more than one real text line (which happens whenever consecutive lines are
# full-width with no ayah boundary between them) by re-deriving a synthetic anchor point. That
# guess was wrong as often as it was right - e.g. surah 2 ayah 283 (page 49), where the real
# rub-el-hizb boundary falls mid-ayah (after "وليتق", not at the ayah's own start), so any anchor
# derived purely from the row geometry landed nowhere near the true gap. What actually works: keep
# the anchor as polygon_start_point() computed it (uncorrected), but search BOTH directions from it
# for the nearest genuine blank gap over a wide enough window, and trust the pixels - the real
# printed line spacing is what the label needs to sit in, not our guess about which "row" it means.
#
# Requires tools/_tmp_shot_pages.js to have already screenshotted every page with markers (labels
# hidden) into tools/_tmp_pages/*.png.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/build_division_label_offsets.py

import json
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(APP_ROOT, 'data')
SHOTS_DIR = os.path.join(HERE, '_tmp_pages')

TEXT_LEFT, TEXT_TOP, TEXT_W, TEXT_H = 110, 170, 1596, 2329
SRC_W, SRC_H = 345, 550
SX, SY = TEXT_W / SRC_W, TEXT_H / SRC_H
SCALE = min(SX, SY)
MARGIN_X = (TEXT_W - SRC_W * SCALE) / 2
MARGIN_Y = (TEXT_H - SRC_H * SCALE) / 2

LABEL_BOX_H = 46  # current .division-label img display height in compose_page.py
BLANK_THRESHOLD = 0.5  # row mean "darkness" (255-mean) below this counts as truly blank
MIN_GAP_ROWS = 15  # a real inter-line gap; short blank dips inside text (between diacritics) are shorter
SEARCH_ABOVE = 260  # how far above the anchor to look for a gap
SEARCH_BELOW = 140  # how far below the anchor to look for a gap


def content_px(vx, vy):
    return TEXT_LEFT + MARGIN_X + vx * SCALE, TEXT_TOP + MARGIN_Y + vy * SCALE


def find_gap_center(arr, anchor_left, anchor_top):
    # Text has brief near-zero dips between letters/diacritics that a simple "walk until blank"
    # scan mistakes for the real inter-line gap. Instead, find every run of consecutive blank rows
    # in the search window and pick the one nearest the anchor (in either direction) that is long
    # enough to be a genuine line gap, not text-internal whitespace.
    x0 = max(0, int(anchor_left) - 250)
    x1 = min(arr.shape[1], int(anchor_left) + 50)
    top_limit = max(0, int(anchor_top) - SEARCH_ABOVE)
    bottom_limit = min(arr.shape[0], int(anchor_top) + SEARCH_BELOW)

    darkness = 255 - arr[top_limit:bottom_limit, x0:x1].mean(axis=1)
    is_blank = darkness < BLANK_THRESHOLD

    runs = []  # (start_y, end_y_exclusive) in absolute page coords
    y = 0
    n = len(is_blank)
    while y < n:
        if is_blank[y]:
            start = y
            while y < n and is_blank[y]:
                y += 1
            runs.append((top_limit + start, top_limit + y))
        else:
            y += 1

    candidates = [r for r in runs if r[1] - r[0] >= MIN_GAP_ROWS]
    if not candidates:
        return None

    def dist(r):
        center = (r[0] + r[1]) / 2
        return abs(center - anchor_top)

    gap_top, gap_bottom = min(candidates, key=dist)
    return (gap_top + gap_bottom) / 2


def main():
    import numpy as np

    with open(os.path.join(DATA_DIR, 'division_markers.json'), encoding='utf-8') as f:
        division_markers = json.load(f)

    offsets = {}
    misses = []  # (page, key, anchor_y) - anchor_y already corrected, just no gap found
    for page_str, entries in division_markers.items():
        shot_path = os.path.join(SHOTS_DIR, f'{int(page_str):03d}.png')
        if not os.path.exists(shot_path):
            continue
        img = Image.open(shot_path).convert('L')
        arr = np.array(img)

        seen_positions = set()
        for e in entries:
            key = f"{e['surah']}:{e['ayah']}"
            if key in seen_positions:
                continue
            seen_positions.add(key)

            anchor_y = e['y']
            anchor_left, anchor_top = content_px(e['x'], anchor_y)
            gap_center = find_gap_center(arr, anchor_left, anchor_top)
            if gap_center is None:
                misses.append((page_str, key, anchor_y))
                continue
            offset = gap_center - LABEL_BOX_H / 2 - anchor_top
            offsets[key] = {'anchor_y': round(anchor_y, 2), 'offset': round(offset, 2)}

    # Fall back to the median measured offset for the handful of markers where no clean gap could
    # be found at all (e.g. right at a page's very top/bottom edge).
    if offsets:
        median_offset = sorted(v['offset'] for v in offsets.values())[len(offsets) // 2]
    else:
        median_offset = -75.0
    for page_str, key, anchor_y in misses:
        offsets[key] = {'anchor_y': round(anchor_y, 2), 'offset': median_offset}

    out_path = os.path.join(DATA_DIR, 'division_label_offsets.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(offsets, f, ensure_ascii=False, indent=1)

    print(f'wrote {out_path} - {len(offsets)} offsets, {len(misses)} used the median fallback')
    if misses:
        print('fallback cases:', [(p, k) for p, k, _ in misses[:20]])


if __name__ == '__main__':
    main()
