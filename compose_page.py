# Mushaf Overlay App v2 - page compositor.
# Builds the HTML for one real mushaf page (1..604): simple frame, a running page-top header
# (current Surah name + current Juz, plain black text, always shown - same pick-the-page's-own-
# banner rule as Quran_Project's v1.3), real vector page text (from quran-svg), the page's own
# built-in surah title framed with a matching border (auto-sized per title, not hardcoded, and
# excluding the basmala beneath it), page number, and - independently toggleable - theme colours
# (each ayah tinted by its theme), Ramadan rak'ah markers, standard ruku markers, and
# Juz/Hizb/Half-Hizb/Quarter division markers.

import base64
import json
import os
import re
from functools import lru_cache
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data')

PAGE_W, PAGE_H = 1816, 2609
FRAME_LEFT, FRAME_TOP, FRAME_W, FRAME_H, FRAME_BORDER = 60, 60, 1696, 2489, 14
TEXT_LEFT, TEXT_TOP, TEXT_W, TEXT_H = 110, 170, 1596, 2329
SRC_W, SRC_H = 345, 550

# The page's own SVG (viewBox 345x550) does NOT stretch independently to fill the TEXT_W x TEXT_H
# box - its aspect ratio (345:550 = 0.627) doesn't match the box's (1596:2329 = 0.685), so the
# browser's default preserveAspectRatio="xMidYMid meet" scales it UNIFORMLY (by whichever of
# SX,SY is smaller) and centers it, leaving a margin on the constrained axis. Every per-ayah x,y
# coordinate must go through this same uniform SCALE + MARGIN, not independent SX/SY - using SX
# for x-positions (as earlier code did) put every marker off by the ignored horizontal margin,
# which is exactly why marker centering never generalized across pages no matter what offset
# constant was tried. Confirmed empirically: SCALE below is the true rendering scale (measured
# ornament positions matched it to within a fraction of a pixel).
SX, SY = TEXT_W / SRC_W, TEXT_H / SRC_H
SCALE = min(SX, SY)
MARGIN_X = (TEXT_W - SRC_W * SCALE) / 2
MARGIN_Y = (TEXT_H - SRC_H * SCALE) / 2


def _content_px(vx, vy):
    """Convert a point in the page SVG's own 0..345 x 0..550 content space to absolute page
    pixels, accounting for the uniform-scale-plus-margin letterboxing described above."""
    return TEXT_LEFT + MARGIN_X + vx * SCALE, TEXT_TOP + MARGIN_Y + vy * SCALE

ROSETTE = ('<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">'
           '<circle cx="32" cy="32" r="30" fill="#fffbf5" stroke="#b8860b" stroke-width="2.5"/>'
           '<circle cx="32" cy="32" r="25" fill="none" stroke="#2d5016" stroke-width="1"/>'
           '<rect x="19" y="19" width="26" height="26" fill="#d4af37" stroke="#2d5016" stroke-width="1"/>'
           '<rect x="19" y="19" width="26" height="26" fill="#d4af37" stroke="#2d5016" stroke-width="1" '
           'transform="rotate(45 32 32)"/><circle cx="32" cy="32" r="7" fill="#2d5016"/>'
           '<circle cx="32" cy="32" r="3" fill="#fffbf5"/></svg>')

MARKER_LABEL_H = 44    # displayed height of rak'ah (تراويح/تهجد) labels, px
DIVISION_LABEL_H = 46  # displayed height of Juz/Hizb/Half/Quarter labels, px
LABEL_GAP = 10         # min horizontal clearance between a division label and a rak'ah label, px
ORNAMENT_R = 12        # half-width of an ayah-end circle, viewBox units

SESSION_AR = {'Taraweeh': 'تراويح', 'Tahajjud': 'تهجد'}
DIVISION_PRIORITY = {'juz': 4, 'hizb': 3, 'nisf': 2, 'rub': 1}


def _load_json(name):
    with open(os.path.join(DATA_DIR, name), encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=None)
def _data_uri(path):
    # Embedding these small label PNGs inline avoids a real bug: the generated HTML lives in a
    # different folder than data/labels_*/ (a sibling of DATA_DIR), and Chromium-based browsers
    # sandbox a local file:// page to its own directory tree - a file:// <img> src pointing outside
    # it (even to a sibling folder) is silently blocked, so page numbers, division labels, and the
    # running header would never show when the HTML is opened directly (double-clicked) rather than
    # built into a PDF via Puppeteer (which has full filesystem access and never hit this).
    with open(path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


@lru_cache(maxsize=None)
def _png_size(path):
    with open(path, 'rb') as f:
        header = f.read(24)
    return int.from_bytes(header[16:20], 'big'), int.from_bytes(header[20:24], 'big')


def _display_width(path, display_h):
    w, h = _png_size(path)
    return w * display_h / h


def _fits(center, half_w):
    return TEXT_LEFT + half_w <= center <= TEXT_LEFT + TEXT_W - half_w


def division_tag_center(data, e, anchor_left):
    """Horizontal center of a division tag, before any collision nudge. A star tag is centered on
    its star. A tag for a division opening a new surah goes just past the previous surah's last
    ayah-end circle when the line has room, else directly above the circle (a surah's last ayah
    usually runs to the line's left edge, leaving nothing past the circle)."""
    if not e['after_ayah']:
        return anchor_left
    half_w = _display_width(data.slate_path(e['label']), DIVISION_LABEL_H) / 2
    past = anchor_left - ORNAMENT_R * SCALE - LABEL_GAP - half_w
    return past if _fits(past, half_w) else anchor_left


class MushafData:
    def __init__(self):
        self.title_boxes = _load_json('title_boxes.json')
        self.ayah_positions = _load_json('ayah_positions.json')
        self.rakah_markers = _load_json('rakah_markers.json')
        self.standard_markers = _load_json('standard_ruku_markers.json')
        self.page_theme_markers = _load_json('page_theme_ruku_markers.json')
        self.page_night = _load_json('page_night_map.json')
        self.division_markers = _load_json('division_markers.json')
        with open(os.path.join(DATA_DIR, 'labels_pagenum', 'manifest.json'), encoding='utf-8') as f:
            self.pagenum_manifest = json.load(f)
        with open(os.path.join(DATA_DIR, 'labels_boxed', 'manifest.json'), encoding='utf-8') as f:
            self.boxed_manifest = json.load(f)
        with open(os.path.join(DATA_DIR, 'labels_gold', 'manifest.json'), encoding='utf-8') as f:
            self.gold_manifest = json.load(f)
        with open(os.path.join(DATA_DIR, 'labels_slate', 'manifest.json'), encoding='utf-8') as f:
            self.slate_manifest = json.load(f)
        self.page_headers = _load_json('page_headers.json')
        with open(os.path.join(DATA_DIR, 'labels_header', 'manifest.json'), encoding='utf-8') as f:
            self.header_manifest = json.load(f)
        self.division_label_offsets = _load_json('division_label_offsets.json')
        self.theme_tints = _load_json('theme_tints.json')
        self.page_ayah_polygons = {}  # page -> [("surah:ayah", polygon)]
        for key, pos in self.ayah_positions.items():
            self.page_ayah_polygons.setdefault(pos['page'], []).append((key, pos['polygon']))

    def pagenum_src(self, text):
        path = os.path.join(DATA_DIR, 'labels_pagenum', self.pagenum_manifest[text])
        return _data_uri(path)

    def boxed_src(self, text):
        path = os.path.join(DATA_DIR, 'labels_boxed', self.boxed_manifest[text])
        return _data_uri(path)

    def gold_path(self, text):
        return os.path.join(DATA_DIR, 'labels_gold', self.gold_manifest[text])

    def gold_src(self, text):
        return _data_uri(self.gold_path(text))

    def slate_path(self, text):
        return os.path.join(DATA_DIR, 'labels_slate', self.slate_manifest[text])

    def slate_src(self, text):
        return _data_uri(self.slate_path(text))

    def header_src(self, text):
        path = os.path.join(DATA_DIR, 'labels_header', self.header_manifest[text])
        return _data_uri(path)


AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'


def to_arabic_indic(n):
    return ''.join(AR_DIGITS[int(d)] for d in str(n))


def night_label_text(v):
    if isinstance(v, list):
        return ' - '.join(f'الليلة {n}' for n in v)
    return f'الليلة {v}'


def _polygon_bbox(polygon):
    nums = [float(x) for x in re.findall(r'-?[\d.]+', polygon)]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _read_text_svg(page_num):
    with open(os.path.join(DATA_DIR, 'svg', f'{page_num:03d}.svg'), encoding='utf-8') as f:
        return f.read()


def _viewbox(text_svg):
    return re.search(r'<svg[^>]*viewBox="([^"]+)"', text_svg).group(1)


def _viewbox_origin(text_svg):
    # Nearly every page's SVG viewBox is "0 0 345 550", but the two ornate opening-spread pages
    # (1 and 2) use an offset origin. Ayah x,y anchors are given in that same coordinate space, so
    # marker placement must subtract the viewBox's own origin before scaling to pixels.
    min_x, min_y, _w, _h = (float(v) for v in _viewbox(text_svg).split())
    return min_x, min_y


def build_page_html(data: MushafData, page_num: int, show_ramadan: bool = False,
                     show_standard_ruku: bool = False, show_page_theme_ruku: bool = False,
                     enabled_divisions: frozenset[str] = frozenset(), show_themes: bool = False) -> str:
    """show_ramadan, show_standard_ruku and show_page_theme_ruku are independent toggles (any
    combination can be on at once), just like enabled_divisions - subset of {'juz', 'hizb', 'nisf',
    'rub'}, any combination. When more than one enabled division kind coincides on the same ayah,
    only the highest-priority one is shown (Juz > Hizb > Half-Hizb > Quarter), matching the proven
    hierarchy from the v1.2 continuous-mushaf generator.

    show_page_theme_ruku draws data/page_theme_ruku_markers.json: a candidate ruku scheme (one
    marker per real Mushaf page, snapped to the nearest thematic/surah boundary - see
    tools/build_page_theme_ruku_markers.py), evaluated 2026-09-25 alongside the traditional scheme."""
    text_svg = _read_text_svg(page_num)
    vb_min_x, vb_min_y = _viewbox_origin(text_svg)

    # --- layer: surah title box(es), auto-sized to the page's own built-in calligraphy ---
    title_html = ''
    for entry in data.title_boxes.get(str(page_num), []):
        if entry.get('error'):
            continue
        pad_y = 20
        side_margin = 26
        box_top = TEXT_TOP + MARGIN_Y + entry['y0'] * SCALE - pad_y
        box_h = (entry['y1'] - entry['y0']) * SCALE + pad_y * 2
        box_left = FRAME_LEFT + FRAME_BORDER + side_margin
        box_w = FRAME_W - 2 * FRAME_BORDER - 2 * side_margin
        title_html += (
            f'<div class="title-box" style="left:{box_left}px; top:{box_top}px; '
            f'width:{box_w}px; height:{box_h}px;"></div>'
        )

    # --- layer: theme colours - each ayah's outline filled with its theme's tint ---
    # Drawn in the page text's own viewBox, so the ayah polygons (same coordinate space) line up
    # exactly, and blended with multiply: the tint colours the paper but can't wash out the ink.
    theme_fill_html = ''
    if show_themes:
        paths = ''.join(
            f'<path d="{polygon}" fill="{data.theme_tints[key]}"/>'
            for key, polygon in data.page_ayah_polygons.get(page_num, [])
            if key in data.theme_tints
        )
        theme_fill_html = f'<svg class="theme-layer" viewBox="{_viewbox(text_svg)}">{paths}</svg>'

    # --- layer: markers (mode-dependent) ---
    # Both Ramadan rak'ah and standard ruku markers use the same small, light, filled circle sat
    # right behind the ayah's own end ornament (so its ink shows through on top), drawn inside
    # .text before the SVG so it paints beneath it. The circle is centered on data.ayah_positions'
    # precise per-ayah ornament center (read straight off the SVG's own rendering via
    # getBoundingClientRect - see tools/build_ayah_positions.js) rather than a guessed offset from
    # the marker JSON's own x,y field: an earlier fixed-offset approach looked right on the one
    # ayah it was calibrated against but was badly off on others, since that offset isn't constant.
    FILL_R = 13

    def _fill_circle_html(e, extra_class=''):
        # Nested inside .text, so positions are LOCAL to it (no TEXT_LEFT/TEXT_TOP) - but the same
        # MARGIN_X/MARGIN_Y letterbox offset still applies, since it's internal to that box too.
        # ayah_positions.json stores raw (un-normalized) viewBox coordinates, so vb_min_x/vb_min_y
        # (nonzero only for the two ornate opening-spread pages) must be subtracted here too.
        pos = data.ayah_positions[f"{e['surah']}:{e['ayah']}"]
        cx = pos['cx'] - vb_min_x
        cy = pos['cy'] - vb_min_y
        left = MARGIN_X + (cx - FILL_R) * SCALE
        top = MARGIN_Y + (cy - FILL_R) * SCALE
        w = h = FILL_R * 2 * SCALE
        cls = f'marker-fill {extra_class}'.strip()
        return f'<div class="{cls}" style="left:{left}px; top:{top}px; width:{w}px; height:{h}px;"></div>'

    def _label_above_html(e, label_text):
        # Centered above the filled circle (not beside it), so it never crowds the adjacent word -
        # same idea as the division-marker labels.
        pos = data.ayah_positions[f"{e['surah']}:{e['ayah']}"]
        cx = pos['cx'] - vb_min_x
        cy = pos['cy'] - vb_min_y
        anchor_left, _ = _content_px(cx, 0)
        circle_top = TEXT_TOP + MARGIN_Y + (cy - FILL_R) * SCALE
        top = circle_top - 50
        half_w = _display_width(data.gold_path(label_text), MARKER_LABEL_H) / 2
        rakah_label_boxes.append((anchor_left - half_w, anchor_left + half_w, top, top + MARKER_LABEL_H))
        label_src = data.gold_src(label_text)
        return (
            f'<div class="marker-label" style="left:{anchor_left}px; top:{top}px;">'
            f'<img src="{label_src}"></div>'
        )

    rakah_label_boxes = []  # (x0, x1, y0, y1), absolute page px - for division-label collision checks

    standard_fill_html = ''
    if show_standard_ruku:
        for e in data.standard_markers.get(str(page_num), []):
            standard_fill_html += _fill_circle_html(e, 'marker-fill-standard')

    page_theme_fill_html = ''
    if show_page_theme_ruku:
        for e in data.page_theme_markers.get(str(page_num), []):
            page_theme_fill_html += _fill_circle_html(e, 'marker-fill-pagetheme')

    rakah_fill_html = ''
    marker_html = ''
    if show_ramadan:
        for e in data.rakah_markers.get(str(page_num), []):
            rakah_fill_html += _fill_circle_html(e, 'marker-fill-ramadan')
            marker_html += _label_above_html(e, f"{SESSION_AR[e['session']]} {e['rakah']}")

    def _avoid_rakah_labels(center, top, label_text):
        # A division boundary often falls right after the ayah that ends a rak'ah, so both labels
        # would sit in the same gap on top of each other. Slide the division label sideways until
        # it clears every rak'ah label it would overlap, on whichever side it already leans toward.
        # Near the page margin only one side has room - clamping afterwards would drag the tag back
        # on top of the rak'ah label, so pick a side that fits instead.
        half_w = _display_width(data.slate_path(label_text), DIVISION_LABEL_H) / 2
        bottom = top + DIVISION_LABEL_H
        for x0, x1, y0, y1 in rakah_label_boxes:
            if bottom <= y0 or top >= y1 or center + half_w <= x0 - LABEL_GAP or center - half_w >= x1 + LABEL_GAP:
                continue
            left_side, right_side = x0 - LABEL_GAP - half_w, x1 + LABEL_GAP + half_w
            preferred, other = (left_side, right_side) if center <= (x0 + x1) / 2 else (right_side, left_side)
            center = preferred if _fits(preferred, half_w) or not _fits(other, half_w) else other
        return min(max(center, TEXT_LEFT + half_w), TEXT_LEFT + TEXT_W - half_w)

    # --- layer: Juz/Hizb/Half-Hizb/Quarter division labels (independent toggles) ---
    division_html = ''
    if enabled_divisions:
        by_position = {}
        for e in data.division_markers.get(str(page_num), []):
            if e['kind'] not in enabled_divisions:
                continue
            pos = (e['surah'], e['ayah'])
            best = by_position.get(pos)
            if best is None or DIVISION_PRIORITY[e['kind']] > DIVISION_PRIORITY[best['kind']]:
                by_position[pos] = e

        for e in by_position.values():
            # The anchor (tools/build_division_markers.py) is the printed rub-el-hizb star, or for a
            # division opening a new surah, the previous surah's last ayah-end circle - see
            # division_tag_center(). The vertical offset into the gap above the anchor's line
            # varies by page, so it's measured per tag (tools/build_division_label_offsets.py).
            anchor_left, anchor_top = _content_px(e['x'] - vb_min_x, e['y'] - vb_min_y)
            top = anchor_top + data.division_label_offsets[f"{e['surah']}:{e['ayah']}"]
            center = _avoid_rakah_labels(division_tag_center(data, e, anchor_left), top, e['label'])
            label_src = data.slate_src(e['label'])
            division_html += (
                f'<div class="division-label" style="left:{center}px; top:{top}px;">'
                f'<img src="{label_src}"></div>'
            )

    # --- layer: night-of-Ramadan header (Ramadan mode only) ---
    night_html = ''
    if show_ramadan:
        night_val = data.page_night.get(str(page_num))
        if night_val is not None:
            label_src = data.boxed_src(night_label_text(night_val))
            night_html = f'<div class="night-label"><img src="{label_src}"></div>'

    # --- layer: running page header (Surah name + current Juz), always shown ---
    header = data.page_headers[str(page_num)]
    header_html = (
        f'<div class="page-header juz"><img src="{data.header_src(header["juz"])}"></div>'
        f'<div class="page-header surah"><img src="{data.header_src(header["surah"])}"></div>'
    )

    # --- page number ---
    pagenum_src = data.pagenum_src(to_arabic_indic(page_num))

    return f'''<!DOCTYPE html><html><head><style>
  body{{margin:0;}}
  .page{{position:relative; width:{PAGE_W}px; height:{PAGE_H}px; background:#fff;}}
  .frame{{position:absolute; left:{FRAME_LEFT}px; top:{FRAME_TOP}px; width:{FRAME_W}px; height:{FRAME_H}px;
          border:{FRAME_BORDER}px solid #d4af37; border-radius:8px; box-shadow: inset 0 0 0 3px #8b7355; box-sizing:border-box;}}
  .corner{{position:absolute; width:48px; height:48px;}}
  .corner.tl{{top:-4px; left:-4px;}} .corner.tr{{top:-4px; right:-4px;}}
  .corner.bl{{bottom:-4px; left:-4px;}} .corner.br{{bottom:-4px; right:-4px;}}
  .text{{position:absolute; left:{TEXT_LEFT}px; top:{TEXT_TOP}px; width:{TEXT_W}px; height:{TEXT_H}px;}}
  .text svg {{ width:100%; height:100%; display:block; }}
  .theme-layer {{ position:absolute; left:0; top:0; mix-blend-mode:multiply; }}
  .title-box {{ position:absolute; border:5px double #b8860b; border-radius:10px;
                background: linear-gradient(180deg, #fffdf5 0%, #f7ecc8 100%); }}
  .marker-fill {{ position:absolute; background:#d9a441; border-radius:50%; opacity:0.35; }}
  .marker-label img {{ height:{MARKER_LABEL_H}px; display:block; }}
  .marker-label {{ position:absolute; transform: translateX(-50%); }}
  .division-label {{ position:absolute; transform: translateX(-50%); }}
  .division-label img {{ height:{DIVISION_LABEL_H}px; display:block; }}
  .night-label {{ position:absolute; left:0; right:0; top:118px; text-align:center; }}
  .night-label img {{ height:48px; }}
  .page-header {{ position:absolute; top:118px; }}
  .page-header img {{ height:48px; }}
  .page-header.juz {{ left:130px; }}
  .page-header.surah {{ right:130px; }}
  .pagenum {{ position:absolute; left:0; right:0; bottom:10px; text-align:center; }}
  .pagenum img {{ height:38px; }}
</style></head><body>
<div class="page">
  <div class="frame">
    <div class="corner tl">{ROSETTE}</div><div class="corner tr">{ROSETTE}</div>
    <div class="corner bl">{ROSETTE}</div><div class="corner br">{ROSETTE}</div>
  </div>
  {header_html}
  {title_html}
  <div class="text">{theme_fill_html}{standard_fill_html}{page_theme_fill_html}{rakah_fill_html}{text_svg}</div>
  {marker_html}
  {division_html}
  {night_html}
  <div class="pagenum"><img src="{pagenum_src}"></div>
</div>
<script>
// Shrink the page to fit the browser window when viewing the HTML directly (a laptop screen is
// far smaller than the page's native {PAGE_W}x{PAGE_H}px). Never enlarges past 1:1, and is a
// no-op whenever the viewport is already at least this size - which is exactly the case during
// PDF generation (print_pages.js sets its own viewport to the full page size first), so the
// printed PDF's layout and dimensions are completely unaffected by this.
(function() {{
  var pageEl = document.querySelector('.page');
  var scale = Math.min(1, window.innerWidth / {PAGE_W}, window.innerHeight / {PAGE_H});
  if (scale < 1) {{
    pageEl.style.transform = 'scale(' + scale + ')';
    pageEl.style.transformOrigin = 'top left';
    document.body.style.width = ({PAGE_W} * scale) + 'px';
    document.body.style.height = ({PAGE_H} * scale) + 'px';
  }}
}})();
</script>
</body></html>'''
