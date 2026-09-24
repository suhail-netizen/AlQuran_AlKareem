# Precomputes each ayah's theme tint (day palette) into data/theme_tints.json ("surah:ayah" -> hex),
# using the tint assignment in source_data/theme_tints.py: every theme from quran_complete.json
# gets one of six soft tints so neighbouring themes are always told apart. Done at build time so
# generating pages only needs data/.
#
# Usage: run from the Mushaf_Overlay_App root: python tools/build_theme_tints.py

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(HERE)
SOURCE_DATA = os.path.join(APP_ROOT, 'source_data')

sys.path.insert(0, SOURCE_DATA)
from theme_tints import compute_tints, load_colours  # noqa: E402


def main():
    with open(os.path.join(SOURCE_DATA, 'quran_complete.json'), encoding='utf-8') as f:
        themes = json.load(f)
    with open(os.path.join(SOURCE_DATA, 'quran-full-tashkeel.json'), encoding='utf-8') as f:
        quran = json.load(f)
    colours = load_colours()
    day = colours['day']
    tints = compute_tints(themes, quran, colours)
    out = {f'{s}:{a}': day[name] for (s, a), name in tints.items()}

    out_path = os.path.join(APP_ROOT, 'data', 'theme_tints.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out, f)
    total = sum(len(s['verses']) for s in quran)
    print(f'wrote {out_path} - {len(out)} of {total} ayahs tinted')


if __name__ == '__main__':
    main()
