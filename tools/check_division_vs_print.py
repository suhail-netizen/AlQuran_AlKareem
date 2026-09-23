# QA check: compares every rendered division tag with where the print says it belongs.
# - Star tags: the printed rub-el-hizb star of its ayah (data/hizb_glyphs.json) must fall within
#   the tag's width, with the tag in the gap just above the star's own line.
# - After-ayah tags (divisions opening a new surah, which have no star): the tag must sit just past
#   the previous surah's last ayah-end circle, or directly over it when the line has no room past
#   it - in the gap above that circle's line either way.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/check_division_vs_print.py

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import compose_page as cp

TAG_RE = re.compile(r'class="division-label" style="left:([\d.]+)px; top:([\d.-]+)px;"><img src="([^"]+)"')


def main():
    data = cp.MushafData()
    with open(os.path.join(cp.DATA_DIR, 'hizb_glyphs.json'), encoding='utf-8') as f:
        stars = json.load(f)
    all_kinds = frozenset(cp.DIVISION_PRIORITY)

    star_ok, after_ok, off = 0, 0, []
    for page in range(1, 605):
        entries = data.division_markers.get(str(page), [])
        if not entries:
            continue
        # Same one-tag-per-ayah dedup compose_page applies, in the same order it renders them.
        by_position = {}
        for e in entries:
            pos = (e['surah'], e['ayah'])
            if pos not in by_position or cp.DIVISION_PRIORITY[e['kind']] > cp.DIVISION_PRIORITY[by_position[pos]['kind']]:
                by_position[pos] = e
        tags = TAG_RE.findall(cp.build_page_html(data, page, enabled_divisions=all_kinds))
        for e, (left, top, _src) in zip(by_position.values(), tags):
            key = f"{e['surah']}:{e['ayah']}"
            left, top = float(left), float(top)
            half_w = cp._display_width(data.slate_path(e['label']), cp.DIVISION_LABEL_H) / 2
            mid = top + cp.DIVISION_LABEL_H / 2
            if e['after_ayah']:
                cx, line_y = cp._content_px(e['x'], e['y'])
                circle_left = cx - cp.ORNAMENT_R * cp.SCALE
                past = circle_left - 40 <= left + half_w <= circle_left
                over = left - half_w - 20 <= cx <= left + half_w + 20
                if (past or over) and 40 <= line_y - mid <= 120:
                    after_ok += 1
                    continue
                off.append((page, key, e['label'], 'after-ayah', round(left - cx), round(line_y - mid)))
                continue
            sx, sy = cp._content_px(stars[key]['x'], stars[key]['y'])
            if left - half_w - 20 <= sx <= left + half_w + 20 and 40 <= sy - mid <= 120:
                star_ok += 1
            else:
                off.append((page, key, e['label'], 'star', round(left - sx), round(sy - mid)))

    print('on its printed star:', star_ok)
    print('just after the previous surah\'s last ayah (no star printed):', after_ok)
    print('NOT where it belongs (page, ayah, label, anchor, dx, dy):', len(off))
    for row in off:
        print('  ', row)


if __name__ == '__main__':
    main()
