# Mushaf Overlay App - assembles all 604 overlaid pages into one PDF.
# Built page-by-page with pymupdf rather than holding all 604 full-resolution images in memory at
# once (which would need several GB) - each page is rendered, inserted into the PDF, and discarded.

import io
import fitz
from PIL import Image
from overlay_engine import MushafOverlayData, render_page, TOTAL_PAGES


def build_pdf(output_path, mode='ramadan', progress_callback=None, jpeg_quality=80, target_width=1000):
    """progress_callback(done, total) is called after each page, if given.

    Pages are stored as JPEG (DCTDecode), downscaled to target_width first. The source pages were
    extracted at 200dpi (1562px wide) for pixel-accurate marker detection, but the original mushaf
    PDF itself ships each page at only 750px wide - our own overlay elements (rings, labels) don't
    need more resolution than that either. width=1000/quality=80 lands the full 604-page PDF around
    the same ballpark as the original source file (~160MB) while staying fully legible.
    """
    data = MushafOverlayData(mode=mode)
    doc = fitz.open()
    for page_num in range(1, TOTAL_PAGES + 1):
        im = render_page(data, page_num).convert('RGB')
        if target_width and im.width > target_width:
            ratio = target_width / im.width
            im = im.resize((target_width, int(im.height * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=jpeg_quality)
        img_rect = fitz.Rect(0, 0, im.width, im.height)
        page = doc.new_page(width=im.width, height=im.height)
        page.insert_image(img_rect, stream=buf.getvalue())
        if progress_callback:
            progress_callback(page_num, TOTAL_PAGES)

    doc.save(output_path, deflate=True, garbage=4)
    doc.close()


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'output.pdf'
    build_pdf(out, progress_callback=lambda d, t: print(f'\r{d}/{t}', end='', flush=True))
    print('\nwrote', out)
