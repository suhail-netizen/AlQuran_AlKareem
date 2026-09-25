# Builds data/page_theme_ruku_markers.json: a CANDIDATE ruku scheme under evaluation (2026-09-25),
# separate from the traditional scheme in data/standard_ruku_markers.json - not wired into the app.
# One marker per real Mushaf page (604 pages), placed so it never falls in the middle of a
# thematic section (pages 1-584) or a surah (pages 585-604, past An-Nazi'at):
#
# Pages 1-584 (Al-Fatihah through An-Nazi'at 79):
#   - If the page's own last ayah is already a thematic-section end (source_data/quran_complete.json),
#     keep it there.
#   - Otherwise look both forward and backward to the nearest thematic-section end and measure the
#     word-distance to each. If the closer one is within 60 words, move the marker there. Otherwise
#     leave it at the page's own last ayah (thematically imprecise, but every page still gets exactly
#     one marker).
#   - Result: 584 markers, all distinct (verified 2026-09-25: 309 already aligned, 128 moved back,
#     155 moved forward, 12 kept unaligned, 0 collisions).
#
# Pages 585-604 (surahs 80-114, each traditionally a single ruku on its own - too short to be
# separately ع-marked in print, confirmed with the user): search forward ONLY (never backward) from
# the page's own last ayah to the next surah's ending, so a marker never cuts into an earlier surah.
# Where 2-3 short surahs share one page, only the LAST of them keeps a marker - the earlier ones are
# treated as part of that page's single segment, per the user's explicit choice. Where one surah
# (only Al-Mutaffifin, 83, in this range) spans more than one page, every page touching it forward-
# searches to the same true ending, which collapses to one marker there once positions are
# deduplicated - so it still gets exactly one ruku despite spanning pages 587-589.
#   - Result: 19 distinct markers for the 20 tail pages (587+588 share Al-Mutaffifin's ending).
#
# Total: 584 + 19 = 603 markers, all distinct positions (verified 2026-09-25).
#
# Usage: run from the Mushaf_Overlay_App root: python tools/build_page_theme_ruku_markers.py

import bisect
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(APP_ROOT, 'data')
SOURCE_DATA = os.path.join(APP_ROOT, 'source_data')

TAIL_START_PAGE = 585  # first page holding any surah 80-114 material (An-Nazi'at's own page is 584)

with open(os.path.join(SOURCE_DATA, 'quran-full-tashkeel.json'), encoding='utf-8') as f:
    text = json.load(f)
with open(os.path.join(SOURCE_DATA, 'quran_complete.json'), encoding='utf-8') as f:
    complete = json.load(f)
with open(os.path.join(SOURCE_DATA, 'quran_divisions_map.json'), encoding='utf-8') as f:
    divisions = json.load(f)
with open(os.path.join(DATA_DIR, 'ayah_positions.json'), encoding='utf-8') as f:
    ayah_positions = json.load(f)

words = {(s['id'], v['id']): len(v['text'].split()) for s in text for v in s['verses']}
ayah_order = [(s['id'], v['id']) for s in text for v in s['verses']]
index_of = {k: i for i, k in enumerate(ayah_order)}
surah_len = {s['id']: len(s['verses']) for s in text}

prefix = [0] * (len(ayah_order) + 1)
for i, k in enumerate(ayah_order):
    prefix[i + 1] = prefix[i] + words[k]


def words_between(i1, i2):
    """Words in ayahs strictly after index i1 through index i2 inclusive (i1 < i2)."""
    return prefix[i2 + 1] - prefix[i1 + 1]


theme_end_idx = sorted(index_of[(s['surah_id'], sec['ayah_end'])]
                        for s in complete['surahs'] for sec in s['sections'])
surah_end_idx = sorted(index_of[(s, surah_len[s])] for s in range(1, 115))

last_ayah_of_page = {}
for key, d in divisions.items():
    p = d['page']
    cur = last_ayah_of_page.get(p)
    if cur is None or (d['surah'], d['ayah']) > cur:
        last_ayah_of_page[p] = (d['surah'], d['ayah'])

WORD_LIMIT = 60
final_points = []

for page_num, (surah, ayah) in sorted(last_ayah_of_page.items()):
    idx = index_of[(surah, ayah)]

    if page_num < TAIL_START_PAGE:
        pos = bisect.bisect_left(theme_end_idx, idx)
        if pos < len(theme_end_idx) and theme_end_idx[pos] == idx:
            final_points.append((surah, ayah))
            continue
        candidates = []
        if pos > 0:
            candidates.append((words_between(theme_end_idx[pos - 1], idx), theme_end_idx[pos - 1]))
        if pos < len(theme_end_idx):
            candidates.append((words_between(idx, theme_end_idx[pos]), theme_end_idx[pos]))
        candidates.sort()
        best_dist, best_idx = candidates[0]
        final_points.append(ayah_order[best_idx] if best_dist <= WORD_LIMIT else (surah, ayah))
    else:
        pos = bisect.bisect_left(surah_end_idx, idx)  # first surah-end at or after idx
        final_points.append(ayah_order[surah_end_idx[pos]])

final_points = sorted(set(final_points), key=lambda k: index_of[k])

by_page = {}
for ruku_num, (surah, ayah) in enumerate(final_points, start=1):
    pos = ayah_positions[f'{surah}:{ayah}']
    entry = {
        'surah': surah, 'ayah': ayah, 'ruku': ruku_num,
        'polygon': pos['polygon'], 'x': pos['cx'], 'y': pos['cy'],
    }
    by_page.setdefault(str(pos['page']), []).append(entry)

out_path = os.path.join(DATA_DIR, 'page_theme_ruku_markers.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(by_page, f, ensure_ascii=False)
print(f'wrote {out_path} - {len(final_points)} markers across {len(by_page)} pages')
