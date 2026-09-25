# Builds data/standard_ruku_markers.json (the traditional ~558-ruku division, independent of the
# Ramadan khatm scheme) from source_data/standard_ruku_reference.txt - a classical ruku table the
# user supplied (surah name: comma-separated ayah numbers where each ruku ends), covering surahs
# 2-79. Surahs 1 and 80-114 are not in that table because each is a single ruku on its own (short
# enough that print editions mark it only by the surah's own ending, with no separate ع tag) -
# confirmed with the user 2026-09-25 - so this script adds one entry per surah for those, at its
# last ayah. Total: 522 (table) + 1 (Al-Fatihah) + 35 (surahs 80-114) = 558, matching the Quran's
# traditionally cited ruku count - an internal consistency check on the source table itself.
#
# The previous data/standard_ruku_markers.json (generated some other, undocumented way) does not
# match this table - not even after a constant ayah-number shift - and was wrong; this replaces it.
# No repositioning/snapping is applied here: every ruku keeps exactly the ayah given in the source
# table (or its surah's last ayah, for the 36 single-ruku surahs). That is a separate, later step.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/build_standard_ruku_markers.py

import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
DATA_DIR = os.path.join(APP_ROOT, 'data')
SOURCE_DATA = os.path.join(APP_ROOT, 'source_data')

with open(os.path.join(SOURCE_DATA, 'quran-full-tashkeel.json'), encoding='utf-8') as f:
    text = json.load(f)
with open(os.path.join(DATA_DIR, 'ayah_positions.json'), encoding='utf-8') as f:
    ayah_positions = json.load(f)

name_to_id = {}
surah_verse_count = {}
for s in text:
    name_to_id[s['name']] = s['id']
    surah_verse_count[s['id']] = len(s['verses'])

# Classical/alternate surah names used in the reference table, where they differ from
# quran-full-tashkeel.json's own naming.
ALIASES = {
    'بني إسرائيل': 17,   # Al-Isra
    'المؤمن': 40,         # Ghafir
    'الدهر': 76,          # Al-Insan
    'إبراهيم': 14,
    'سبأ': 34,
    'النبأ': 78,
}

# (surah, ayah), in reading order, in the order the table lists them per surah.
table_endpoints = []
seen_sajda = 0  # "السجدة" names both As-Sajdah (32) and, second time, Fussilat's alternate name (41)
with open(os.path.join(SOURCE_DATA, 'standard_ruku_reference.txt'), encoding='utf-8') as f:
    for line in f:
        line = line.strip().rstrip('.').strip()
        if not line:
            continue
        name, nums = line.split(':', 1)
        name = name.strip()
        ayahs = [int(n) for n in re.findall(r'\d+', nums)]
        if name == 'السجدة':
            seen_sajda += 1
            surah = 32 if seen_sajda == 1 else 41
        else:
            surah = ALIASES.get(name) or name_to_id[name]
        for ayah in ayahs:
            table_endpoints.append((surah, ayah))

table_surahs = {s for s, a in table_endpoints}
assert table_surahs == set(range(2, 80)), \
    f'expected the table to cover surahs 2-79 exactly, got {sorted(table_surahs)}'

# Add the 36 single-ruku surahs: Al-Fatihah, and every short surah after the table's range.
single_ruku_surahs = [1] + list(range(80, 115))
endpoints = table_endpoints + [(s, surah_verse_count[s]) for s in single_ruku_surahs]
endpoints.sort()  # canonical Quran order: surah, then ayah

expected_total = 558
assert len(endpoints) == expected_total, f'expected {expected_total} rukus total, got {len(endpoints)}'

by_page = {}
for ruku_num, (surah, ayah) in enumerate(endpoints, start=1):
    pos = ayah_positions[f'{surah}:{ayah}']
    entry = {
        'surah': surah, 'ayah': ayah, 'ruku': ruku_num,
        'polygon': pos['polygon'], 'x': pos['cx'], 'y': pos['cy'],
    }
    by_page.setdefault(str(pos['page']), []).append(entry)

out_path = os.path.join(DATA_DIR, 'standard_ruku_markers.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(by_page, f, ensure_ascii=False)
print(f'wrote {out_path} - {len(endpoints)} rukus across {len(by_page)} pages')
