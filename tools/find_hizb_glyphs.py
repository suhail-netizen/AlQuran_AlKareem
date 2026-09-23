# Locates every printed rub-el-hizb star glyph in the page SVGs.
#
# Each page's text is one large path of relative sub-shapes. A given glyph is always drawn with the
# same relative commands, so its sub-shape body (everything after the leading "m dx dy") is a
# position-independent fingerprint. This tracks the pen position through the path to recover where
# each sub-shape starts, in the page's viewBox coordinates.
#
# Usage (from the app root):
#   python tools/find_hizb_glyphs.py probe PAGE X Y   - list sub-shapes near a viewBox point
#   python tools/find_hizb_glyphs.py scan             - write data/hizb_glyphs.json
#                                                       ("surah:ayah" -> star's page and x,y)

import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), 'data')

TOKEN_RE = re.compile(r'[a-zA-Z]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?')
ARGS = {'m': 2, 'l': 2, 'c': 6, 's': 4, 'q': 4, 't': 2, 'h': 1, 'v': 1, 'z': 0}


def page_subpaths(page):
    """Returns (vb_x, vb_y, signature, width, height) for each sub-shape of the page's text path;
    width/height are the extents of its on-curve points, in path units."""
    with open(os.path.join(DATA_DIR, 'svg', f'{page:03d}.svg'), encoding='utf-8') as f:
        svg = f.read()
    outer = re.search(r'<g transform="matrix\(([^)]+)\)">', svg).group(1).replace(',', ' ').split()
    a, b, c, d, e, f_ = (float(v) for v in outer)
    content = svg[svg.index('id="content"'):]
    out = []
    # Most pages hold all text in one path; some split it into one translated path per word.
    for m in re.finditer(r'<g transform="translate\(([^)]+)\)"><path d="([^"]+)"', content):
        tx, ty = (float(v) for v in m.group(1).replace(',', ' ').split())
        _walk_path(m.group(2), lambda px, py, tx=tx, ty=ty: (a * (px + tx) + c * (py + ty) + e,
                                                            b * (px + tx) + d * (py + ty) + f_),
                   page, out)
    return out


def _walk_path(path_d, to_vb, page, out):
    tokens = TOKEN_RE.findall(path_d)
    x = y = 0.0
    start = (0.0, 0.0)
    i = 0
    current = None  # [vb_x, vb_y, [tokens], [xs], [ys]]

    def close_current():
        if current:
            xs, ys = current[3], current[4]
            out.append((current[0], current[1], ' '.join(current[2]), max(xs) - min(xs), max(ys) - min(ys)))

    while i < len(tokens):
        cmd = tokens[i]
        i += 1
        if cmd.lower() not in ARGS:
            raise ValueError(f'page {page}: unsupported path command {cmd!r}')
        if cmd in 'Zz':
            x, y = start
            current[2].append('z')
            continue
        n = ARGS[cmd.lower()]
        first = True
        while i < len(tokens) and not tokens[i].isalpha():
            nums = [float(t) for t in tokens[i:i + n]]
            raw = tokens[i:i + n]
            i += n
            op = cmd.lower()
            if op == 'm' and first:
                close_current()
                x, y = x + nums[0], y + nums[1]
                start = (x, y)
                current = [*to_vb(x, y), [], [x], [y]]
                first = False
                cmd = 'l'  # extra pairs after m are implicit lineto
                continue
            current[2].append(op + ' ' + ' '.join(raw))
            if op in 'ml':
                x, y = x + nums[0], y + nums[1]
            elif op == 'c':
                x, y = x + nums[4], y + nums[5]
            elif op in 'sq':
                x, y = x + nums[2], y + nums[3]
            elif op == 't':
                x, y = x + nums[0], y + nums[1]
            elif op == 'h':
                x += nums[0]
            elif op == 'v':
                y += nums[0]
            current[3].append(x)
            current[4].append(y)
    close_current()


def probe(page, vx, vy):
    for sx, sy, sig, w, h in page_subpaths(page):
        if abs(sx - vx) < 15 and abs(sy - vy) < 15:
            print(f'({sx:.1f},{sy:.1f}) {w:.2f}x{h:.2f} len={len(sig)} {sig[:80]}')


# The star is a ~1.1-unit round center dot ringed by eight near-identical petals. Copies differ in
# rounding noise and even in how the same curve is encoded (c vs s commands), so match on geometry,
# not text: a small round sub-shape with at least six petal-sized sub-shapes clustered around it.
def _is_dot(sig, w, h):
    return len(sig) < 150 and 0.9 <= w <= 1.3 and 0.9 <= h <= 1.3


def _is_petal(sig):
    return 250 <= len(sig) <= 350


def _first_row(polygon):
    nums = [float(v) for v in re.findall(r'-?[\d.]+', polygon.split('Z', 1)[0])]
    return min(nums[0::2]), max(nums[0::2]), min(nums[1::2]), max(nums[1::2])


def _star_ayah(page, sx, sy):
    # The star is printed immediately before its ayah's first word: on that ayah's topmost row,
    # at the row's right (RTL start) edge.
    with open(os.path.join(DATA_DIR, 'json', f'{page:03d}.json'), encoding='utf-8') as f:
        ayahs = json.load(f)
    best = None
    for a in ayahs:
        _, x1, y0, y1 = _first_row(a['polygon'])
        if y0 - 3 <= sy <= y1 + 3 and (best is None or abs(x1 - sx) < best[0]):
            best = (abs(x1 - sx), a['surahNumber'], a['ayahNumber'])
    return f'{best[1]}:{best[2]}' if best else None


def scan():
    found = {}  # "surah:ayah" -> {page, x, y}
    for page in range(1, 605):
        subs = page_subpaths(page)
        for sx, sy, sig, w, h in subs:
            if not _is_dot(sig, w, h):
                continue
            petals = sum(1 for px, py, ps, _, _ in subs
                         if _is_petal(ps) and abs(px - sx) < 4 and abs(py - sy) < 4)
            if petals >= 6:
                key = _star_ayah(page, sx, sy)
                if key is None:
                    raise RuntimeError(f'page {page}: star at ({sx:.1f},{sy:.1f}) matches no ayah')
                found[key] = {'page': page, 'x': round(sx, 2), 'y': round(sy, 2)}
    with open(os.path.join(DATA_DIR, 'hizb_glyphs.json'), 'w', encoding='utf-8') as f:
        json.dump(found, f)
    print('glyphs found:', len(found))


if __name__ == '__main__':
    if sys.argv[1] == 'probe':
        probe(int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]))
    elif sys.argv[1] == 'scan':
        scan()
