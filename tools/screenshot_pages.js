// Screenshots every page that carries a division marker, with all overlay labels hidden, into
// data/_page_shots/NNN.png - the plain-text ground truth that build_division_label_offsets.py and
// scan_division_overlaps.py measure line gaps and overlaps against.
//
// Usage (from the Mushaf_Overlay_App root, after generating output/):
//   node tools/screenshot_pages.js [html_dir]      (html_dir defaults to output)

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

async function main() {
    const appRoot = path.join(__dirname, '..');
    const htmlDir = path.resolve(appRoot, process.argv[2] || 'output');
    const outDir = path.join(appRoot, 'data', '_page_shots');
    fs.mkdirSync(outDir, { recursive: true });
    const divisions = JSON.parse(fs.readFileSync(path.join(appRoot, 'data', 'division_markers.json'), 'utf-8'));

    const browser = await puppeteer.launch({ headless: true, args: ['--disable-gpu'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 1816, height: 2609 });
    const pages = Object.keys(divisions).map(Number).sort((a, b) => a - b);
    for (const pg of pages) {
        const name = `${String(pg).padStart(3, '0')}`;
        await page.goto(pathToFileURL(path.join(htmlDir, `${name}.html`)).href, { waitUntil: 'load' });
        await page.evaluate(() => {
            document.querySelectorAll('.division-label, .marker-label').forEach((el) => { el.style.display = 'none'; });
        });
        await page.screenshot({ path: path.join(outDir, `${name}.png`) });
    }
    await browser.close();
    console.log('screenshotted', pages.length, 'pages into', outDir);
}

main().catch((e) => { console.error(e); process.exit(1); });
