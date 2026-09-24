// Renders each needed label (page numbers, rak'ah/ruku tags, night headers) as a small transparent
// PNG using the real KFGQPC font via Chromium's own text shaping - Pillow/plain CSS can't shape
// this font's joined Arabic letters correctly on its own.
//
// Usage: node render_labels.js labels.json out_dir [style]
//   style: 'boxed' (pale-green rounded box, default - for the night-of-Ramadan header)
//          'plain' (no background, just black text - for page numbers)
//          'slate' (subdued, semi-transparent slate-grey box - for Juz/Hizb/Half-Hizb/Quarter
//                   division labels)
//          'gold'  (semi-transparent gold box matching the rak'ah marker circle's own color -
//                   for the تراويح/تهجد tags)

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');
const { pathToFileURL } = require('url');

const FONT_PATH = path.join(__dirname, '..', 'viewer', 'fonts', 'KFGQPC-Hafs-V30.ttf');

async function main() {
    const labelsPath = process.argv[2];
    const outDir = process.argv[3];
    const style = process.argv[4] || 'boxed';
    const labels = JSON.parse(fs.readFileSync(labelsPath, 'utf-8'));
    fs.mkdirSync(outDir, { recursive: true });

    const browser = await puppeteer.launch({ headless: true, args: ['--disable-gpu'] });
    const page = await browser.newPage();
    await page.setViewport({ width: 400, height: 150 });

    const fontUrl = pathToFileURL(path.resolve(FONT_PATH)).href;
    let labelCss;
    if (style === 'plain') {
        labelCss = `display: inline-block; font-family: 'KFGQPC', serif; font-size: 44px; color: #000; white-space: nowrap;`;
    } else if (style === 'slate') {
        // Semi-transparent so the box never fully hides ayah text it happens to land over.
        labelCss = `display: inline-block; font-family: 'KFGQPC', serif; font-size: 38px; color: #3a434c;
       background: rgba(238,241,244,0.72); border: 2px solid rgba(143,154,165,0.85); border-radius: 8px;
       padding: 6px 14px; white-space: nowrap;`;
    } else if (style === 'gold') {
        // Exactly the same gold as the ruku/rak'ah marker-fill circle (#d9a441 at opacity 0.35 -
        // see compose_page.py's .marker-fill), not just a similar tint.
        labelCss = `display: inline-block; font-family: 'KFGQPC', serif; font-size: 30px; color: #5c4413;
       background: rgba(217,164,65,0.35); border: 2px solid rgba(217,164,65,0.35); border-radius: 8px;
       padding: 6px 14px; white-space: nowrap;`;
    } else if (style === 'boxed') {
        // Night-of-Ramadan header - grown to match the page-top surah/juz header's font size.
        labelCss = `display: inline-block; font-family: 'KFGQPC', serif; font-size: 44px; color: #000;
       background: #cbe7be; border-radius: 8px; padding: 6px 14px; white-space: nowrap;`;
    } else {
        labelCss = `display: inline-block; font-family: 'KFGQPC', serif; font-size: 30px; color: #000;
       background: #cbe7be; border-radius: 8px; padding: 6px 14px; white-space: nowrap;`;
    }

    await page.goto('about:blank');
    await page.setContent(`
    <html><head><style>
      @font-face { font-family: 'KFGQPC'; src: url('${fontUrl}'); }
      body { margin: 0; padding: 0; }
      .label { ${labelCss} }
    </style></head><body><span id="lbl" class="label"></span></body></html>
  `);
    await page.evaluate(() => document.fonts.ready);

    const manifest = {};
    for (let i = 0; i < labels.length; i++) {
        const text = labels[i];
        await page.evaluate((t) => { document.getElementById('lbl').textContent = t; }, text);
        const el = await page.$('#lbl');
        const outPath = path.join(outDir, `${i}.png`);
        await el.screenshot({ path: outPath, omitBackground: true });
        manifest[text] = `${i}.png`;
    }
    fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 1));
    console.log('rendered', labels.length, 'labels');

    await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
