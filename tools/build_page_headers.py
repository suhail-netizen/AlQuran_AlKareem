# Derives the running page-top header (current Surah name + current Juz, written as an Arabic
# ordinal) for every one of the 604 pages, using the exact "pickBanner" rule already proven in
# Quran_Project's v1.3 paginate.js: for a page whose ayahs span more than one surah/juz, prefer
# whichever one actually STARTS on that page (the last one to start, if more than one does);
# otherwise there is only one candidate for that page and it's used directly.

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
SOURCE_DATA = os.path.join(APP_ROOT, 'source_data')

with open(os.path.join(SOURCE_DATA, 'quran_divisions_map.json'), encoding='utf-8') as f:
    divisions = json.load(f)

with open(os.path.join(APP_ROOT, 'data', 'page_map.json'), encoding='utf-8') as f:
    page_map = json.load(f)

with open(os.path.join(APP_ROOT, 'data', 'surah_header_pages.json'), encoding='utf-8') as f:
    surah_header_pages = json.load(f)

surah_names = {}
for entries in surah_header_pages.values():
    for e in entries:
        surah_names[e['surah']] = e['name']

JUZ_ORDINAL = [
    'الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع', 'الثامن', 'التاسع', 'العاشر',
    'الحادي عشر', 'الثاني عشر', 'الثالث عشر', 'الرابع عشر', 'الخامس عشر', 'السادس عشر', 'السابع عشر',
    'الثامن عشر', 'التاسع عشر', 'العشرون', 'الحادي والعشرون', 'الثاني والعشرون', 'الثالث والعشرون',
    'الرابع والعشرون', 'الخامس والعشرون', 'السادس والعشرون', 'السابع والعشرون', 'الثامن والعشرون',
    'التاسع والعشرون', 'الثلاثون',
]


def juz_label(n):
    return f'الجزء {JUZ_ORDINAL[n - 1]}'


def pick_banner(items):
    """items: list of (name, starts_here). Prefer the last one that starts on this page; else
    there's only one candidate and it's used as-is - same rule as v1.3's pickBanner()."""
    starting = [name for name, starts in items if starts]
    return starting[-1] if starting else items[0][0]


# Ordered (surah, ayah) -> page, and per-ayah juz, built straight from the source maps.
page_entries = {}
for e in page_map:
    page_entries.setdefault(e['page'], []).append((e['surah'], e['ayah']))
for pg in page_entries:
    page_entries[pg].sort(key=lambda t: (t[0], t[1]))

page_headers = {}
for pg in range(1, 605):
    chunk = page_entries[pg]
    first_juz = divisions[f'{chunk[0][0]}:{chunk[0][1]}']['juz']

    surah_items, seen_s = [], set()
    juz_items, seen_j = set(), set()
    juz_items = []
    for surah_id, ayah_id in chunk:
        if surah_id not in seen_s:
            seen_s.add(surah_id)
            surah_items.append((surah_names[surah_id], ayah_id == 1))
        j = divisions[f'{surah_id}:{ayah_id}']['juz']
        if j not in seen_j:
            seen_j.add(j)
            juz_items.append((j, j != first_juz))

    surah = pick_banner(surah_items)
    juz = pick_banner(juz_items)
    page_headers[str(pg)] = {'surah': f'سورة {surah}', 'juz': juz_label(juz)}

out_path = os.path.join(APP_ROOT, 'data', 'page_headers.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(page_headers, f, ensure_ascii=False, indent=1)
print('wrote', out_path, '-', len(page_headers), 'pages')
