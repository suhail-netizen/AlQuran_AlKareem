// Builds a reusable, authoritative per-ayah position file: for every one of the 6236 ayahs, its
// real ayah-end ornament center (precise pixel-perfect center, taken straight from the SVG's own
// rendering via getBBox() - which resolves the whole translate/scale/matrix transform chain
// correctly, unlike hand-computing it) plus its full text polygon (already known, copied through
// for convenience). This single file is meant to be the one source of truth for "where is ayah
// (surah,ayah) on its page" - used now to precisely center ruku/rak'ah markers (replacing the
// guessed-offset approach, which didn't generalize: it looked right on some ayahs and was badly
// off on others), and later for thematic per-ayah coloring, which needs the same kind of precise
// per-ayah geometry.
//
// Usage: run from the Mushaf_Overlay_App root: node tools/build_ayah_positions.js

const puppeteer = require(require('path').join(__dirname, '..', '..', 'Quran_Project', 'node_modules', 'puppeteer'));
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

const DATA_DIR = path.join(__dirname, '..', 'data');
const TOTAL_PAGES = 604;

async function main() {
    const browser = await puppeteer.launch({ headless: true, args: ['--disable-gpu'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 345, height: 550 });

    const result = {};   // "surah:ayah" -> { page, cx, cy, polygon }
    let mismatches = 0;

    for (let pg = 1; pg <= TOTAL_PAGES; pg++) {
        const svgPath = path.join(DATA_DIR, 'svg', `${String(pg).padStart(3, '0')}.svg`);
        const jsonPath = path.join(DATA_DIR, 'json', `${String(pg).padStart(3, '0')}.json`);
        const svgContent = fs.readFileSync(svgPath, 'utf-8');
        const ayahs = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));

        const html = `<!DOCTYPE html><html><head><style>body{margin:0;}</style></head><body>${svgContent}</body></html>`;
        const tmpPath = path.join(DATA_DIR, '_tmp_ayah_pos.html');
        fs.writeFileSync(tmpPath, html);
        await page.goto(pathToFileURL(path.resolve(tmpPath)).href, { waitUntil: 'load' });

        const centers = await page.evaluate(() => {
            const svg = document.querySelector('svg');
            const svgRect = svg.getBoundingClientRect();
            const vb = svg.viewBox.baseVal;
            const els = Array.from(document.querySelectorAll('.ayah-mark-ornament'));
            return els.map((el) => {
                const r = el.getBoundingClientRect();
                const cxPx = r.x + r.width / 2 - svgRect.x;
                const cyPx = r.y + r.height / 2 - svgRect.y;
                // vb.x/vb.y account for the two ornate-opening pages' offset viewBox origin.
                return { cx: vb.x + cxPx / svgRect.width * vb.width, cy: vb.y + cyPx / svgRect.height * vb.height };
            });
            // NOT reversed here: DOM order's relationship to the ayahs' reading order isn't
            // consistent across pages (page 1 runs the SAME direction as the ayah list; most
            // other pages run opposite) - matching by array position silently swapped ayahs on
            // page 1. Nearest-neighbor matching below sidesteps the question of DOM order
            // entirely by using each ayah's own known-approximate x,y instead.
        });

        if (centers.length !== ayahs.length) {
            console.error(`page ${pg}: ${centers.length} ornaments vs ${ayahs.length} ayahs - skipping precise centers, falling back to raw x,y`);
            mismatches++;
            ayahs.forEach((a) => {
                result[`${a.surahNumber}:${a.ayahNumber}`] = { page: pg, cx: a.x, cy: a.y, polygon: a.polygon };
            });
            continue;
        }

        // Greedy nearest-neighbor match: each ayah's own (approximate) x,y picks the closest
        // still-unclaimed precise center. Robust regardless of DOM order, since ornaments are
        // small and well-separated - the correct match is always far closer than any wrong one.
        const remaining = centers.slice();
        ayahs.forEach((a) => {
            let bestIdx = 0, bestDist = Infinity;
            remaining.forEach((c, i) => {
                const d = (c.cx - a.x) ** 2 + (c.cy - a.y) ** 2;
                if (d < bestDist) { bestDist = d; bestIdx = i; }
            });
            const match = remaining.splice(bestIdx, 1)[0];
            result[`${a.surahNumber}:${a.ayahNumber}`] = { page: pg, cx: match.cx, cy: match.cy, polygon: a.polygon };
        });

        if (pg % 50 === 0) console.log(`...${pg}/${TOTAL_PAGES}`);
    }

    fs.unlinkSync(path.join(DATA_DIR, '_tmp_ayah_pos.html'));
    const outPath = path.join(DATA_DIR, 'ayah_positions.json');
    fs.writeFileSync(outPath, JSON.stringify(result));
    await browser.close();
    console.log('wrote', outPath, '-', Object.keys(result).length, 'ayahs,', mismatches, 'page(s) fell back to raw x,y');
}

main().catch((e) => { console.error(e); process.exit(1); });
