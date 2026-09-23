// Finds the pixel bounding box of each surah's built-in title text within its opening page's SVG
// (345x550 viewBox units). Scans a window bounded by the bottom of the immediately preceding ayah
// on the page (or the page top, if this is the first content) and the top of this surah's own
// first ayah - correctly excludes any prior surah's actual verse content on the same page. That
// window also contains the basmala graphic sitting below the title (every surah but At-Tawbah), so
// only the first contiguous band of inked rows (the title itself) is kept - the basmala starts
// after a blank gap and is deliberately excluded from the box.

const puppeteer = require(require('path').join(__dirname, '..', '..', 'Quran_Project', 'node_modules', 'puppeteer'));
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

const SCALE = 4;

function polyYRange(polygon) {
    const nums = polygon.match(/-?[\d.]+/g).map(Number);
    const ys = [];
    for (let i = 1; i < nums.length; i += 2) ys.push(nums[i]);
    return [Math.min(...ys), Math.max(...ys)];
}

function viewBoxMinY(svgContent) {
    // Nearly every page's viewBox is "0 0 345 550", but pages 1 and 2 (the ornate opening spread)
    // use an offset origin. Ayah polygon Y values are in that same coordinate space, so the scan
    // window must subtract the viewBox's own minY before converting to canvas pixels - otherwise
    // the window lands on the wrong part of the canvas and no title pixels are found there.
    const m = svgContent.match(/<svg[^>]*viewBox="([^"]+)"/);
    const [, minY] = m[1].split(/\s+/).map(Number);
    return minY;
}

async function main() {
    const surahHeaderPages = JSON.parse(fs.readFileSync('surah_header_pages.json', 'utf-8'));

    const browser = await puppeteer.launch({ headless: true, args: ['--disable-gpu'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 345 * SCALE, height: 550 * SCALE });

    const titleBoxes = {};
    const pages = Object.keys(surahHeaderPages).map(Number).sort((a, b) => a - b);

    for (const pg of pages) {
        const svgPath = `svg/${String(pg).padStart(3, '0')}.svg`;
        const ayahs = JSON.parse(fs.readFileSync(`json/${String(pg).padStart(3, '0')}.json`, 'utf-8'));
        const surahsHere = new Set(surahHeaderPages[String(pg)].map((s) => s.surah));

        const svgContent = fs.readFileSync(svgPath, 'utf-8');
        const vbMinY = viewBoxMinY(svgContent);
        const html = `<!DOCTYPE html><html><head><style>
      body{margin:0;}
      .text{width:${345 * SCALE}px; height:${550 * SCALE}px; background:#fff;}
      .text svg { width:100%; height:100%; display:block; }
    </style></head><body><div class="text">${svgContent}</div></body></html>`;
        fs.writeFileSync('title_scan_tmp.html', html);
        await page.goto(pathToFileURL(path.resolve('title_scan_tmp.html')).href, { waitUntil: 'load' });

        const results = [];
        for (let i = 0; i < ayahs.length; i++) {
            const a = ayahs[i];
            if (a.ayahNumber !== 1 || !surahsHere.has(a.surahNumber)) continue;

            const [thisTop] = polyYRange(a.polygon);
            let windowTop = vbMinY;   // true top of the visible page, not a bare 0
            if (i > 0) {
                const [, prevBottom] = polyYRange(ayahs[i - 1].polygon);
                windowTop = prevBottom;
            }
            const windowBottom = Math.max(windowTop + 1, thisTop - 1);

            const scanTopPx = Math.round((windowTop - vbMinY) * SCALE);
            const scanBottomPx = Math.round((windowBottom - vbMinY) * SCALE);

            const box = await page.evaluate((scanTopPx, scanBottomPx) => {
                const target = document.querySelector('.text');
                const rect = target.getBoundingClientRect();
                const svgEl = target.querySelector('svg');
                const svgStr = new XMLSerializer().serializeToString(svgEl);
                const h = scanBottomPx - scanTopPx;
                const canvas = document.createElement('canvas');
                canvas.width = rect.width; canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = '#fff';
                ctx.fillRect(0, 0, canvas.width, h);
                return new Promise((resolve) => {
                    const img = new Image();
                    const blob = new Blob([svgStr], { type: 'image/svg+xml' });
                    const url = URL.createObjectURL(blob);
                    img.onload = () => {
                        ctx.drawImage(img, 0, -scanTopPx, rect.width, rect.height);
                        const data = ctx.getImageData(0, 0, canvas.width, h).data;
                        // Per-row ink presence, so the title (first text block) can be separated from
                        // the basmala that sits below it in the same window - only the first
                        // contiguous band of inked rows is kept.
                        const rowHasInk = new Array(h).fill(false);
                        for (let y = 0; y < h; y++) {
                            for (let x = 0; x < canvas.width; x++) {
                                const idx = (y * canvas.width + x) * 4;
                                const r = data[idx], g = data[idx + 1], b = data[idx + 2], a2 = data[idx + 3];
                                if (a2 > 50 && (r + g + b) / 3 < 180) { rowHasInk[y] = true; break; }
                            }
                        }
                        const GAP = 24; // canvas px (SCALE=4 -> 6 viewBox units) of blank rows that ends a band
                        let bandStart = -1, bandEnd = -1, blank = 0;
                        for (let y = 0; y < h; y++) {
                            if (rowHasInk[y]) {
                                if (bandStart === -1) bandStart = y;
                                bandEnd = y;
                                blank = 0;
                            } else if (bandStart !== -1) {
                                blank++;
                                if (blank >= GAP) break;   // first band is complete - stop, ignore the rest
                            }
                        }
                        let minX = canvas.width, maxX = 0, minY = h, maxY = 0, found = false;
                        if (bandStart !== -1) {
                            for (let y = bandStart; y <= bandEnd; y++) {
                                for (let x = 0; x < canvas.width; x++) {
                                    const idx = (y * canvas.width + x) * 4;
                                    const r = data[idx], g = data[idx + 1], b = data[idx + 2], a2 = data[idx + 3];
                                    if (a2 > 50 && (r + g + b) / 3 < 180) {
                                        found = true;
                                        if (x < minX) minX = x;
                                        if (x > maxX) maxX = x;
                                        if (y < minY) minY = y;
                                        if (y > maxY) maxY = y;
                                    }
                                }
                            }
                        }
                        URL.revokeObjectURL(url);
                        resolve(found ? { minX, minY, maxX, maxY } : null);
                    };
                    img.onerror = () => resolve(null);
                    img.src = url;
                });
            }, scanTopPx, scanBottomPx);

            if (box) {
                results.push({
                    surah: a.surahNumber,
                    x0: box.minX / SCALE, y0: (box.minY + scanTopPx) / SCALE,
                    x1: box.maxX / SCALE, y1: (box.maxY + scanTopPx) / SCALE,
                });
            } else {
                results.push({ surah: a.surahNumber, error: true });
                console.error('no title found on page', pg, 'surah', a.surahNumber);
            }
        }
        titleBoxes[pg] = results;
    }

    fs.writeFileSync('title_boxes.json', JSON.stringify(titleBoxes));
    await browser.close();
    console.log('done,', pages.length, 'pages processed');
}

main().catch((e) => { console.error(e); process.exit(1); });
