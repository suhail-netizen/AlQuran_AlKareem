# Derives Juz / Hizb / Half-Hizb / Quarter-Hizb boundary positions for the vector pipeline, using
# the same logic already proven in Quran_Project's generate_mushaf_continuous_v1_1.py (v1.2):
# hizb_quarter (1..240) from quran_divisions_map.json gives juz directly, and hizb/half-hizb/quarter
# by integer division. A boundary landing on ayah 1 of a new surah is moved to the end of the
# previous surah instead (same rule already applied to ruku markers). Unlike that HTML generator,
# hierarchy suppression (Juz > Hizb > Half-Hizb > Quarter) is NOT baked in here - all raw boundary
# events are kept, one per (surah, ayah, kind), so the app can apply suppression at render time
# based on whichever kinds the user actually enables.
#
# v1.2 inserts each marker span BEFORE the target ayah's own text, since it's one continuous
# scrolling document with no fixed page boundaries. Our app renders the real, fixed 604-page
# Mushaf, so a marker must stay on the physical page where its division actually starts - anchoring
# to the *previous* ayah's position (as v1.2 effectively does) can push it onto the wrong page when
# that previous ayah falls on the prior page. So markers anchor to the target ayah's own position -
# but its START (the polygon's own top-right corner, where RTL text begins), not its 'x'/'y' fields
# (which mark the ayah's own END ornament, a full line or more away). The real printed Madinah
# Mushaf already carries an authentic rub-el-hizb ornament (a Unicode glyph, U+06DE) at this exact
# spot, right before the marked ayah's text - this anchors our overlay on top of it.
#
# Usage: node-free, run from the Mushaf_Overlay_App root: python tools/build_division_markers.py

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
QURAN_PROJECT = os.path.join(APP_ROOT, '..', 'Quran_Project')

with open(os.path.join(QURAN_PROJECT, 'quran_divisions_map.json'), encoding='utf-8') as f:
    divisions = json.load(f)

with open(os.path.join(APP_ROOT, 'data', 'page_map.json'), encoding='utf-8') as f:
    page_map = json.load(f)

ayah_to_page = {(e['surah'], e['ayah']): e['page'] for e in page_map}

# Ordered (surah, ayah) list, and per-surah verse counts, both derived straight from the divisions map.
verses = sorted(((v['surah'], v['ayah']) for v in divisions.values()), key=lambda t: (t[0], t[1]))
surah_verse_count = {}
for s, a in verses:
    surah_verse_count[s] = max(surah_verse_count.get(s, 0), a)

json_cache = {}


def ayah_anchor(surah, ayah):
    page = ayah_to_page[(surah, ayah)]
    if page not in json_cache:
        with open(os.path.join(APP_ROOT, 'data', 'json', f'{page:03d}.json'), encoding='utf-8') as f:
            json_cache[page] = {(a['surahNumber'], a['ayahNumber']): a for a in json.load(f)}
    a = json_cache[page][(surah, ayah)]
    return page, a['polygon']


SRC_W = 345   # page content viewBox width (compose_page.py's SRC_W)
RING_R = 17   # division-ring radius, viewBox units (compose_page.py's RING_R)


def polygon_start_point(polygon):
    # Right edge, vertical center of the polygon's own topmost row - where RTL text begins
    # reading, i.e. right where this ayah's own text starts (and where its rub-el-hizb ornament,
    # if any, sits). Each row is one rectangular subpath (top-left, top-right, bottom-right,
    # bottom-left), so the first subpath alone gives that row's own y-range and right edge.
    first_subpath = polygon.split('Z', 1)[0]
    nums = [float(v) for v in re.findall(r'-?[\d.]+', first_subpath)]
    pts = list(zip(nums[0::2], nums[1::2]))
    row_top, row_bottom = min(y for _, y in pts), max(y for _, y in pts)
    row_right = max(x for x, _ in pts)
    GLYPH_DX = 4   # empirically calibrated: the polygon boundary sits slightly left of the glyph itself
    # When an ayah opens a fresh line right at the text area's own margin, row_right is already at
    # (or very near) SRC_W - nudging further right, or even the ring's own radius, would push the
    # marker past the printable area and outside the frame. Clamp so it always stays inside.
    x = min(row_right + GLYPH_DX, SRC_W - RING_R - 2)
    return x, (row_top + row_bottom) / 2


raw_events = []  # (surah, ayah, kind, label), in Quran order, before surah-start repositioning
prev = None
for surah_id, ayah_id in verses:
    curr = divisions[f'{surah_id}:{ayah_id}']
    if surah_id == 1 and ayah_id == 1:
        prev = curr
        continue

    hq = curr.get('hizb_quarter', 1)
    phq = prev.get('hizb_quarter', 1)

    if curr.get('juz') != prev.get('juz'):
        raw_events.append((surah_id, ayah_id, 'juz', f"الجزء {curr.get('juz')}"))

    hizb = (hq - 1) // 4 + 1
    prev_hizb = (phq - 1) // 4 + 1
    if hizb != prev_hizb:
        raw_events.append((surah_id, ayah_id, 'hizb', f'الحزب {hizb}'))

    nisf = (hq - 1) // 2 + 1
    prev_nisf = (phq - 1) // 2 + 1
    if nisf != prev_nisf:
        raw_events.append((surah_id, ayah_id, 'nisf', 'نصف الحزب'))

    if hq != phq:
        raw_events.append((surah_id, ayah_id, 'rub', 'ربع الحزب'))

    prev = curr

# Reposition: a boundary at ayah 1 of a surah (other than the very first) moves to the end of the
# previous surah - never opens a new surah, matching the ruku/rak'ah convention.
by_page = {}
for surah_id, ayah_id, kind, label in raw_events:
    if ayah_id == 1 and surah_id > 1:
        target_surah, target_ayah = surah_id - 1, surah_verse_count[surah_id - 1]
    else:
        target_surah, target_ayah = surah_id, ayah_id

    page, polygon = ayah_anchor(target_surah, target_ayah)
    x, y = polygon_start_point(polygon)
    by_page.setdefault(str(page), []).append({
        'surah': target_surah, 'ayah': target_ayah, 'kind': kind, 'label': label,
        'x': x, 'y': y, 'polygon': polygon,
    })

out_path = os.path.join(APP_ROOT, 'data', 'division_markers.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(by_page, f, ensure_ascii=False)

counts = {}
for events in by_page.values():
    for e in events:
        counts[e['kind']] = counts.get(e['kind'], 0) + 1
print('wrote', out_path)
print('counts:', counts)
