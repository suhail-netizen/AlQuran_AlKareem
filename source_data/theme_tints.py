#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assigns each drawn theme one of six standard tints so that neighbouring themes are always told apart.

A theme is a run of consecutive ayahs drawn from the same section of quran_complete.json (an ayah takes the
last section that covers it, as the page generator does). The book's colour name only gives a starting preference
(theme_colours.json, "mapping"; null = no preference). A theme keeps its preferred tint unless that would repeat the
tint of the theme before it; the assignment that changes the fewest themes is found by dynamic programming.
"""

import json
import math
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CLOSE = 8.0            # tints closer than this (colour difference) are avoided as neighbours when the choice is free
CHANGE_COST = 10.0     # cost of giving a theme a tint other than its preferred one


def load_colours():
    with open(os.path.join(BASE, 'theme_colours.json'), 'r', encoding='utf-8') as f:
        return json.load(f)


def _lab(hex_colour):
    r, g, b = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = lambda c: ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = lin(r), lin(g), lin(b)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return (116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z)))


def colour_difference(a, b):
    return math.dist(_lab(a), _lab(b))


def compute_tints(themes_data, quran_data, colours=None):
    """Return {(surah, ayah): tint name} for every ayah that belongs to a theme."""
    colours = colours or load_colours()
    palette = colours['day']
    names = list(palette)
    mapping = colours['mapping']

    sections = []
    for surah in themes_data.get('surahs', []):
        for sec in surah.get('sections', []):
            sections.append((surah['surah_id'], sec))
    owner = {}
    for idx, (sid, sec) in enumerate(sections):
        for ayah in range(sec['ayah_start'], sec['ayah_end'] + 1):
            owner[(sid, ayah)] = idx

    runs = []      # [section index, [ayahs]]
    for surah in quran_data:
        for verse in surah['verses']:
            key = (surah['id'], verse['id'])
            idx = owner.get(key)
            if idx is None:
                runs.append(None)          # an ayah without a theme breaks the chain
                continue
            if runs and runs[-1] is not None and runs[-1][0] == idx:
                runs[-1][1].append(key)
            else:
                runs.append([idx, [key]])

    result = {}
    chain = []
    for run in runs + [None]:
        if run is None:
            if chain:
                _assign_chain(chain, sections, names, palette, mapping, result)
                chain = []
        else:
            chain.append(run)
    return result


def _assign_chain(chain, sections, names, palette, mapping, result):
    n = len(chain)
    pref = [mapping.get(sections[run[0]][1].get('color')) for run in chain]
    close = {(a, b): colour_difference(palette[a], palette[b]) < CLOSE for a in names for b in names}
    inf = float('inf')
    cost = [{c: inf for c in names} for _ in range(n)]
    back = [{c: None for c in names} for _ in range(n)]
    for c in names:
        cost[0][c] = 0 if pref[0] in (None, c) else CHANGE_COST
    for i in range(1, n):
        for c in names:
            own = 0 if pref[i] in (None, c) else CHANGE_COST
            for p in names:
                if p == c:
                    continue
                v = cost[i - 1][p] + own + (0.3 if close[(p, c)] else 0)
                if i >= 2 and back[i - 1][p] == c:
                    v += 0.01               # avoid ABAB patterns when nothing else decides
                if v < cost[i][c]:
                    cost[i][c] = v
                    back[i][c] = p
    last = min(names, key=lambda c: cost[n - 1][c])
    final = [None] * n
    final[n - 1] = last
    for i in range(n - 1, 0, -1):
        final[i - 1] = back[i][final[i]]
    for run, tint in zip(chain, final):
        for key in run[1]:
            result[key] = tint
