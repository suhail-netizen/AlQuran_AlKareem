# Derives Juz / Hizb / Half-Hizb / Quarter-Hizb division tags and where each one is anchored, using
# the same boundary logic as Quran_Project's generate_mushaf_continuous_v1_1.py (v1.2):
# hizb_quarter (1..240) from quran_divisions_map.json gives juz directly, and hizb/half-hizb/quarter
# by integer division. Hierarchy suppression (Juz > Hizb > Half-Hizb > Quarter) is NOT baked in -
# all raw events are kept, one per (surah, ayah, kind), so the app applies it at render time based
# on whichever kinds the user enables.
#
# Anchors, checked against the printed Madinah Mushaf:
# - A division inside a surah: its printed rub-el-hizb star (found by tools/find_hizb_glyphs.py),
#   which sits right before the division's first word. Every such division has one; the build fails
#   if the data and the print ever disagree.
# - A division that opens a new surah has no printed star (the surah banner marks it). It anchors
#   to the previous surah's last ayah-end circle, on the same page as the text it follows;
#   compose_page.py places the tag just past that circle, or above it when the line has no room.
# - Except a new Juz that opens a new surah: no tag at all. The page header already names the new
#   Juz on that surah's first page, and the Hizb/Half/Quarter starting at the same point add nothing
#   a new Juz doesn't already imply.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/build_division_markers.py

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(APP_ROOT, 'data')
SOURCE_DATA = os.path.join(APP_ROOT, 'source_data')

with open(os.path.join(SOURCE_DATA, 'quran_divisions_map.json'), encoding='utf-8') as f:
    divisions = json.load(f)
with open(os.path.join(DATA_DIR, 'hizb_glyphs.json'), encoding='utf-8') as f:
    stars = json.load(f)
with open(os.path.join(DATA_DIR, 'ayah_positions.json'), encoding='utf-8') as f:
    ayah_positions = json.load(f)

# Ordered (surah, ayah) list, and per-surah verse counts, both derived straight from the divisions map.
verses = sorted(((v['surah'], v['ayah']) for v in divisions.values()), key=lambda t: (t[0], t[1]))
surah_verse_count = {}
for s, a in verses:
    surah_verse_count[s] = max(surah_verse_count.get(s, 0), a)

raw_events = []  # (surah, ayah, kind, label), in Quran order
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

juz_at_surah_start = {(s, a) for s, a, kind, _ in raw_events if kind == 'juz' and a == 1 and s > 1}

by_page = {}
for surah_id, ayah_id, kind, label in raw_events:
    if (surah_id, ayah_id) in juz_at_surah_start:
        continue
    if ayah_id == 1 and surah_id > 1:
        # Opens a new surah: anchor on the previous surah's last ayah-end circle.
        target_surah, target_ayah = surah_id - 1, surah_verse_count[surah_id - 1]
        pos = ayah_positions[f'{target_surah}:{target_ayah}']
        page, x, y, after_ayah = pos['page'], pos['cx'], pos['cy'], True
    else:
        target_surah, target_ayah = surah_id, ayah_id
        star = stars.get(f'{surah_id}:{ayah_id}')
        if not star:
            raise RuntimeError(f'{surah_id}:{ayah_id} ({label}): no printed star - data disagrees with print')
        page, x, y, after_ayah = star['page'], star['x'], star['y'], False
    by_page.setdefault(str(page), []).append({
        'surah': target_surah, 'ayah': target_ayah, 'kind': kind, 'label': label,
        'x': x, 'y': y, 'after_ayah': after_ayah,
    })

used = {f"{e['surah']}:{e['ayah']}" for es in by_page.values() for e in es if not e['after_ayah']}
unused = sorted(set(stars) - used)
if unused:
    raise RuntimeError(f'printed stars with no division event (data disagrees with print): {unused}')

out_path = os.path.join(DATA_DIR, 'division_markers.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(by_page, f, ensure_ascii=False)

counts = {}
for events in by_page.values():
    for e in events:
        counts[e['kind']] = counts.get(e['kind'], 0) + 1
print('wrote', out_path)
print('counts:', counts)
