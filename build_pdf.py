# Mushaf Overlay App v2 - builds the 604-page mushaf from the vector page compositor, with theme
# colours, Ramadan rak'ah markers, standard ruku markers, the page/theme candidate ruku markers, and
# Juz/Hizb/Half-Hizb/Quarter division markers all independently toggleable and freely combinable.
# Two output stages, each usable on its own:
# generate_html_pages() writes the 604 HTML pages (viewable directly, no PDF needed), and
# render_pdf_from_html() prints an existing HTML folder to a merged PDF via Puppeteer (subprocess,
# one Node call handling all pages in one browser session for speed, each page its own isolated
# print job, merged via pdf-lib). build_pdf() runs both for the common "give me a PDF" case.

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compose_page import MushafData, build_page_html

HERE = os.path.dirname(os.path.abspath(__file__))
TOTAL_PAGES = 604


def generate_html_pages(html_dir, show_ramadan=False, show_standard_ruku=False, show_page_theme_ruku=False,
                        enabled_divisions=frozenset(), progress_callback=None, show_themes=False):
    data = MushafData()
    os.makedirs(html_dir, exist_ok=True)
    for page_num in range(1, TOTAL_PAGES + 1):
        html = build_page_html(data, page_num, show_ramadan, show_standard_ruku, show_page_theme_ruku,
                                enabled_divisions, show_themes)
        with open(os.path.join(html_dir, f'{page_num:03d}.html'), 'w', encoding='utf-8') as f:
            f.write(html)
        if progress_callback:
            progress_callback('layout', page_num, TOTAL_PAGES)


def render_pdf_from_html(html_dir, output_path, progress_callback=None):
    # Writes progress markers to stdout that this Python process reads to drive the PDF-phase
    # progress bar.
    node_script = os.path.join(HERE, 'print_pages.js')
    proc = subprocess.Popen(
        ['node', node_script, html_dir, output_path, str(TOTAL_PAGES)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
    )
    for line in proc.stdout:
        line = line.strip()
        if line.startswith('PROGRESS '):
            done = int(line.split()[1])
            if progress_callback:
                progress_callback('pdf', done, TOTAL_PAGES)
        else:
            print(line)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError('PDF rendering failed (see log above)')


def build_pdf(output_path, show_ramadan=False, show_standard_ruku=False, show_page_theme_ruku=False,
              enabled_divisions=frozenset(), progress_callback=None, show_themes=False):
    html_dir = os.path.join(HERE, '_build_html')
    generate_html_pages(html_dir, show_ramadan, show_standard_ruku, show_page_theme_ruku,
                        enabled_divisions, progress_callback, show_themes)
    render_pdf_from_html(html_dir, output_path, progress_callback)


if __name__ == '__main__':
    # Quick CLI smoke test: python build_pdf.py ramadan|standard|pagetheme|none out.pdf [juz,hizb,nisf,rub]
    mode = sys.argv[1] if len(sys.argv) > 1 else 'ramadan'
    out = sys.argv[2] if len(sys.argv) > 2 else f'output_{mode}.pdf'
    divisions = frozenset(sys.argv[3].split(',')) if len(sys.argv) > 3 else frozenset()
    build_pdf(
        out, show_ramadan=(mode == 'ramadan'), show_standard_ruku=(mode == 'standard'),
        show_page_theme_ruku=(mode == 'pagetheme'),
        enabled_divisions=divisions,
        progress_callback=lambda phase, d, t: print(f'\r{phase}: {d}/{t}', end='', flush=True),
    )
    print('\nwrote', out)
