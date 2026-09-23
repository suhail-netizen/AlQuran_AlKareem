// Prints all generated page HTML files to PDF (one Puppeteer session, one page.pdf() call per
// page - keeps each print job isolated, avoiding the whole-book-single-print Chromium quirks hit
// earlier in this project) and merges them into the final PDF via pdf-lib.
//
// Usage: node print_pages.js <html_dir> <output.pdf> <total_pages>

const puppeteer = require(require('path').join(__dirname, '..', 'Quran_Project', 'node_modules', 'puppeteer'));
const { PDFDocument } = require(require('path').join(__dirname, '..', 'Quran_Project', 'node_modules', 'pdf-lib'));
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

async function main() {
    const htmlDir = process.argv[2];
    const outPath = process.argv[3];
    const totalPages = parseInt(process.argv[4], 10);

    const browser = await puppeteer.launch({ headless: true, args: ['--disable-gpu'] });
    const page = await browser.newPage();
    // Must be at least the page's own size, so the HTML's auto-fit-to-window script (added for
    // on-screen viewing on a normal laptop, which is much smaller than the page) computes a no-op
    // scale of 1 here - otherwise the printed PDF would come out shrunk to Puppeteer's tiny default
    // viewport instead of the real page dimensions.
    await page.setViewport({ width: 1816, height: 2609 });

    const merged = await PDFDocument.create();
    for (let i = 1; i <= totalPages; i++) {
        const htmlPath = path.join(htmlDir, `${String(i).padStart(3, '0')}.html`);
        await page.goto(pathToFileURL(path.resolve(htmlPath)).href, { waitUntil: 'load' });
        const buf = await page.pdf({
            width: '1816px', height: '2609px',
            margin: { top: '0', bottom: '0', left: '0', right: '0' },
            printBackground: true,
        });
        const donor = await PDFDocument.load(buf);
        const [copied] = await merged.copyPages(donor, [0]);
        merged.addPage(copied);
        console.log(`PROGRESS ${i}`);
    }

    const bytes = await merged.save();
    fs.writeFileSync(outPath, bytes);
    await browser.close();
    console.log('done');
}

main().catch((e) => { console.error(e); process.exit(1); });
