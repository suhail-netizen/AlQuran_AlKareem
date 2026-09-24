# AlQuran AlKareem — Madinah Mushaf with thematic colours

Two applications built on the 604-page Madinah Mushaf (Ḥafṣ):

1. **Mushaf generator** (repository root): builds the 604 pages as HTML, and optionally as one merged PDF. Theme colours, the Ramadan khatm markers, standard ruku markers and the juz / hizb / half-hizb / quarter labels can each be switched on or off.
2. **Mushaf reader** (`viewer/`): an installable web app for reading those pages. It has a surah and juz index, bookmarks, and ayah details on tap. It works offline, and readers can switch the theme colours and the khatm markers on or off.

## Mushaf generator

```bash
npm run setup          # Puppeteer + Chrome, only needed for PDF output
python app.py          # desktop window: pick the layers, then generate HTML or HTML + PDF
```

Page generation uses only the Python standard library. Some tools in `tools/`, and `viewer/make_icons.py`, also need `pip install pillow numpy`.

Command line: `python build_pdf.py ramadan|standard|none out.pdf [juz,hizb,nisf,rub]`

- `compose_page.py` draws one page: the vector page text, frame, surah banners, theme colours and markers.
- `data/` holds everything page generation needs: page SVGs, ayah positions, markers, labels and tints.
- `tools/` rebuilds the files in `data/`. The Python tools read `source_data/`.

## Mushaf reader

```bash
python viewer/build_pages.py   # generates viewer/Pages (604 pages) and refreshes viewer/data
python viewer/serve.py         # opens http://127.0.0.1:8000/index.html
```

The page files are generated, so they are not stored in git. Every push to `main` publishes the reader to GitHub Pages: `.github/workflows/publish-reader.yml` generates the pages and deploys `viewer/`. The one-time setup is Settings → Pages → Source: GitHub Actions. To host it elsewhere, upload the `viewer/` folder, including `Pages/`, to any HTTPS static host. `sw.js` and `manifest.webmanifest` make it installable and readable offline. If you add or rename app files, list them in `SHELL_FILES` in `sw.js` and bump `SHELL_VERSION`.

## Source data (`source_data/`)

- `quran-full-tashkeel.json`: ayah text (Uthmani, with tashkeel).
- `quran_complete.json`: surah details and the thematic sections, with their ayah ranges and theme text. The theme text was checked against the printed «التقسيم الموضوعي» tables, and every flagged section matched (2026-09-24).
- `quran_divisions_map.json`: juz / hizb-quarter / ruku / page for every ayah.
- `theme_tints.py` and `theme_colours.json`: give each theme one of six soft tints, so that neighbouring themes never share a colour.

## Credits and terms

- **Mushaf page artwork:** King Fahd Glorious Qur'an Printing Complex (مجمع الملك فهد لطباعة المصحف الشريف), from its free digital Muṣḥaf al-Madinah. The Complex allows free use in websites and software; printing muṣḥafs for commercial sale is reserved to the Complex. See its [usage rights](https://dm.qurancomplex.gov.sa/rights/).
- **Vector pages and ayah regions:** [quran-svg](https://github.com/quranpedia/quran-svg) by Quran.ws (CC BY 4.0; attribution waived inside products).
- **Font:** KFGQPC Uthmanic Script HAFS v3.0, King Fahd Complex ([fonts.qurancomplex.gov.sa](https://fonts.qurancomplex.gov.sa)). It is free to use, copy and distribute, but must not be sold or modified, so it is included unmodified.
- The Qur'anic text is never altered. Colours and markers are drawn around and beneath it.
