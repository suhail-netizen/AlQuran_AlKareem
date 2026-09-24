#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Builds the reader's 604 page files (viewer/Pages/001.html ... 604.html) with the app's page compositor,
then refreshes the reader's data files (build_app_data.py). Run from anywhere:

    python viewer/build_pages.py

The pages carry every layer the reader can switch on and off (theme colours; the Ramadan khatm
markers: night labels, تراويح/تهجد labels and their ruku circles), plus the juz / hizb / half-hizb /
quarter labels. Standard ruku markers are left out, as the reader uses the Ramadan scheme.
These options reproduce the published pages exactly. The pages are generated, so they are not in git.
"""

import os
import sys

VIEWER = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(VIEWER)
sys.path.insert(0, APP_ROOT)
sys.path.insert(0, VIEWER)

from build_pdf import generate_html_pages  # noqa: E402
import build_app_data  # noqa: E402

PAGES_DIR = os.path.join(VIEWER, 'Pages')
OPTIONS = dict(
    show_ramadan=True,
    show_standard_ruku=False,
    enabled_divisions=frozenset({'juz', 'hizb', 'nisf', 'rub'}),
    show_themes=True,
)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    generate_html_pages(
        PAGES_DIR, **OPTIONS,
        progress_callback=lambda phase, done, total: print(f'\rpages: {done}/{total}', end='', flush=True),
    )
    print()
    build_app_data.main()


if __name__ == '__main__':
    main()
