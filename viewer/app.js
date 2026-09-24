// ------------------------------------------------------------------
// Quran Reader App
// Swipes through the 604 page files in Pages/ (001.html ... 604.html). Each page is loaded into
// a shadow root so its own styles stay contained, and scaled to fit. Page/surah/juz metadata
// comes from data/app_index.js and ayah text from data/quran_text.js (build_app_data.py).
// ------------------------------------------------------------------

const TOTAL_PAGES = 604;
const PAGE_W = 1816;
const PAGE_H = 2609;
const KEEP_LOADED = 4;          // pages kept in memory on each side of the current one
const INDEX = window.QURAN_INDEX;

const $ = (id) => document.getElementById(id);
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩';
const ar = (n) => String(n).replace(/\d/g, (d) => AR_DIGITS[d]);
const surahName = (id) => INDEX.surahs[id - 1].name;

// ------------------------------------------------------------------
// 1. IndexedDB Helper for Bookmarks
// ------------------------------------------------------------------
const DB_NAME = 'QuranReaderDB';
const DB_VERSION = 1;
let db = null;

function initDB() {
  return new Promise((resolve) => {
    let request;
    try { request = indexedDB.open(DB_NAME, DB_VERSION); } catch (e) { return resolve(null); }
    request.onupgradeneeded = (e) => {
      const d = e.target.result;
      if (!d.objectStoreNames.contains('bookmarks')) {
        // id is "p:<page>" for a page bookmark, "a:<surah>:<ayah>" for an ayah bookmark.
        d.createObjectStore('bookmarks', { keyPath: 'id' });
      }
    };
    request.onsuccess = (e) => { db = e.target.result; resolve(db); };
    request.onerror = () => resolve(null);   // private windows etc.: run without bookmarks storage
  });
}

function dbRequest(mode, fn) {
  if (!db) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const store = db.transaction('bookmarks', mode).objectStore('bookmarks');
    const req = fn(store);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
const getBookmark = (id) => dbRequest('readonly', (s) => s.get(id));
const getBookmarks = () => dbRequest('readonly', (s) => s.getAll()).then((r) => r || []);
const putBookmark = (bm) => dbRequest('readwrite', (s) => s.put(bm));
const deleteBookmark = (id) => dbRequest('readwrite', (s) => s.delete(id));

async function toggleBookmark(bm) {
  if (!db) return toast('لا يمكن الحفظ في هذا المتصفح');
  if (await getBookmark(bm.id)) {
    await deleteBookmark(bm.id);
    toast('تمت إزالة العلامة');
  } else {
    await putBookmark({ ...bm, timestamp: new Date().toISOString() });
    toast('تم الحفظ');
  }
  refreshBookmarkButton();
  renderBookmarks();
}

// ------------------------------------------------------------------
// 2. Small persistence helpers (last page read)
// ------------------------------------------------------------------
function loadLastPage() {
  try { return parseInt(localStorage.getItem('quran.lastPage'), 10) || 1; } catch (e) { return 1; }
}
function saveLastPage(p) {
  try { localStorage.setItem('quran.lastPage', String(p)); } catch (e) { /* ignore */ }
}

// ------------------------------------------------------------------
// 3. Page metadata
// ------------------------------------------------------------------
function pageSurah(p) {
  // The last surah that starts on this page, otherwise the one continuing onto it.
  const info = INDEX.pages[p - 1];
  const starting = info.surahs.filter((s) => INDEX.surahs[s - 1].page === p &&
    !(s === info.first[0] && info.first[1] !== 1));
  return starting.length ? starting[starting.length - 1] : info.surahs[0];
}

function pageLabel(p) {
  const info = INDEX.pages[p - 1];
  return { surah: `سورة ${surahName(pageSurah(p))}`, juz: `الجزء ${ar(info.juz)}`, hizb: Math.ceil(info.hq / 4) };
}

// ------------------------------------------------------------------
// 4. Swiper Controller
// ------------------------------------------------------------------
let swiper = null;
let spread = false;             // two pages side by side on wide screens
let currentPage = 1;
let focusPage = null;           // page the reader jumped to; wins over the right-hand page of a spread

function isSpreadLayout() {
  const r = $('reader').getBoundingClientRect();
  return r.width / r.height > 1.15;
}

function goToPage(p, speed = 0) {
  p = Math.min(TOTAL_PAGES, Math.max(1, p | 0));
  focusPage = p;
  let idx = p - 1;
  if (spread) idx -= idx % 2;   // snap to the right-hand page of the pair
  swiper.slideTo(idx, speed);
  if (speed === 0) onPageChange();
}

function visiblePages() {
  const first = swiper.activeIndex + 1;
  return spread && first < TOTAL_PAGES ? [first, first + 1] : [first];
}

function onPageChange() {
  const pages = visiblePages();
  currentPage = pages.includes(focusPage) ? focusPage : pages[0];
  focusPage = currentPage;
  const lbl = pageLabel(currentPage);
  $('surah-title').textContent = lbl.surah;
  $('juz-title').textContent = lbl.juz;
  $('page-num').textContent = `صفحة ${pages.map(ar).join('–')}`;
  $('page-slider').value = currentPage;
  document.title = `${lbl.surah} – صفحة ${ar(currentPage)}`;
  history.replaceState(null, '', `#page=${currentPage}`);
  saveLastPage(currentPage);
  refreshBookmarkButton();

  // Load visible pages and neighbours, release the rest to keep memory in check.
  const lo = pages[0] - (spread ? 2 : 1);
  const hi = pages[pages.length - 1] + (spread ? 2 : 1);
  for (let p = lo; p <= hi; p++) if (p >= 1 && p <= TOTAL_PAGES) loadPageContent(p);
  for (const p of [...loaded.keys()]) {
    if (p < pages[0] - KEEP_LOADED || p > pages[0] + KEEP_LOADED + 1) unloadPage(p);
  }
}

function applyLayout() {
  const want = isSpreadLayout();
  if (want !== spread) {
    const keep = currentPage;
    spread = want;
    swiper.params.slidesPerView = spread ? 2 : 1;
    swiper.params.slidesPerGroup = spread ? 2 : 1;
    swiper.update();
    goToPage(keep);
  }
  for (const p of loaded.keys()) fitPage(p);
}

function showFileWarning() {
  // Opened by double-clicking index.html: the browser blocks loading Pages/ from file://.
  const box = document.createElement('div');
  box.className = 'file-warning';
  box.innerHTML = `<div class="help-card">
    <h2>يجب تشغيل التطبيق عبر الخادم المحلي</h2>
    <p>فُتح الملف مباشرةً من المجلد، والمتصفح يمنع تحميل صفحات المصحف بهذه الطريقة.</p>
    <p>شغّل هذا الأمر في الطرفية، وسيفتح التطبيق تلقائيًا:</p>
    <code>python viewer/serve.py</code>
    <p>أو افتح هذا العنوان إذا كان الخادم يعمل:</p>
    <code>http://127.0.0.1:8000/index.html</code>
  </div>`;
  document.body.appendChild(box);
}

// A menu switch that shows/hides a layer of every page through a CSS variable on <body>
// (inherited into the pages' shadow roots, see PAGE_EXTRA_CSS). Remembered per device.
function setupLayerSwitch(inputId, storageKey, cssVar, name) {
  const box = $(inputId);
  const apply = (on) => document.body.style.setProperty(cssVar, on ? 'block' : 'none');
  let on = true;
  try { on = localStorage.getItem(storageKey) !== '0'; } catch (e) { /* ignore */ }
  box.checked = on;
  apply(on);
  box.addEventListener('change', () => {
    apply(box.checked);
    try { localStorage.setItem(storageKey, box.checked ? '1' : '0'); } catch (e) { /* ignore */ }
    toast(`${name}: ${box.checked ? 'ظاهر' : 'مخفي'}`);
  });
}

function setupHelp() {
  const help = $('help');
  const close = () => {
    help.hidden = true;
    try { localStorage.setItem('quran.helpSeen', '1'); } catch (e) { /* ignore */ }
  };
  $('help-close').addEventListener('click', close);
  help.addEventListener('click', (e) => { if (e.target === help) close(); });
  $('help-open').addEventListener('click', () => { closeDrawer(); help.hidden = false; });
  let seen = false;
  try { seen = localStorage.getItem('quran.helpSeen') === '1'; } catch (e) { /* ignore */ }
  if (!seen) help.hidden = false;
}

document.addEventListener('DOMContentLoaded', async () => {
  if (location.protocol === 'file:') return showFileWarning();
  await initDB();

  const wrapper = $('swiper-wrapper');
  for (let i = 1; i <= TOTAL_PAGES; i++) {
    const slide = document.createElement('div');
    slide.className = 'swiper-slide';
    slide.dataset.page = i;
    slide.innerHTML = `<div class="page-wrapper" id="page-slot-${i}"></div>`;
    wrapper.appendChild(slide);
  }

  spread = isSpreadLayout();
  const hashPage = parseInt((location.hash.match(/page=(\d+)/) || [])[1], 10);
  const startPage = hashPage || loadLastPage();

  // Swiper configured for RTL Quran reading: swiping right moves to the next page.
  swiper = new Swiper('#reader', {
    rtl: true,
    slidesPerView: spread ? 2 : 1,
    slidesPerGroup: spread ? 2 : 1,
    spaceBetween: 0,
    keyboard: { enabled: false },
    on: { slideChange: () => onPageChange(), resize: () => applyLayout() },
  });
  goToPage(startPage);

  new ResizeObserver(() => applyLayout()).observe($('reader'));
  window.addEventListener('resize', () => applyLayout());

  $('bookmark-btn').addEventListener('click', () =>
    toggleBookmark({ id: `p:${currentPage}`, page: currentPage, type: 'page' }));
  $('next-btn').addEventListener('click', () => swiper.slideNext());
  $('prev-btn').addEventListener('click', () => swiper.slidePrev());
  $('page-slider').addEventListener('input', (e) => {
    $('page-num').textContent = `صفحة ${ar(e.target.value)}`;
  });
  $('page-slider').addEventListener('change', (e) => goToPage(+e.target.value));

  setupDrawer();
  setupSheet();
  setupKeyboard();
  setupHelp();
  setupLayerSwitch('khatm-toggle', 'quran.showKhatm', '--khatm-display', 'علامات ختم القرآن في القيام');
  setupLayerSwitch('theme-toggle', 'quran.showThemes', '--theme-display', 'التلوين الموضوعي');
  setupOffline();
  window.addEventListener('hashchange', () => {
    const p = parseInt((location.hash.match(/page=(\d+)/) || [])[1], 10);
    if (p && p !== currentPage) goToPage(p);
  });
});

// ------------------------------------------------------------------
// 5. Page Fetching, Scaling & Ayah Interaction
// ------------------------------------------------------------------
const loaded = new Map();       // page -> { host, root }
const pending = new Map();      // page -> Promise

const PAGE_EXTRA_CSS = `
  .text * { pointer-events: none; }            /* glyphs sit above the ayah outlines: let taps through */
  .text .ayahPolygon { pointer-events: all; cursor: pointer; transition: fill-opacity .15s; }
  .ayahPolygon:hover { fill: #d4af37; fill-opacity: .12; }
  /* Khatm-in-qiyam markers (ruku circle + تراويح/تهجد label, and the الليلة label at the top):
     the menu switch sets --khatm-display on <body>. */
  .marker-fill, .marker-label, .night-label { display: var(--khatm-display, block); }
  /* Thematic colouring: the tinted layer under the text; --theme-display from its menu switch. */
  .text svg.theme-layer { display: var(--theme-display, block); }
  .ayahPolygon.selected { fill: #d4af37; fill-opacity: .35; }
`;

function loadPageContent(p) {
  if (loaded.has(p)) return Promise.resolve();
  if (pending.has(p)) return pending.get(p);

  const slot = $(`page-slot-${p}`);
  slot.innerHTML = `<div class="page-loading">جارٍ تحميل صفحة ${ar(p)}…</div>`;
  const job = fetch(`Pages/${String(p).padStart(3, '0')}.html`)
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.text(); })
    .then((html) => {
      if (!pending.has(p)) return;              // released while loading
      const host = document.createElement('div');
      host.className = 'page-host';
      const root = host.attachShadow({ mode: 'open' });
      // Drop the page's own fit-to-window script (the app does the scaling), and repair theme-tint
      // paths written as bare point lists without a moveto (pages 1-2), which browsers refuse to draw.
      html = html.replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<path d="\s*(\d[^"]*)"/g, '<path d="M $1 Z"');
      root.innerHTML = html + `<style>${PAGE_EXTRA_CSS}</style>`;
      slot.replaceChildren(host);
      loaded.set(p, { host, root });
      bindSvgInteractions(root, p);
      fitPage(p);
    })
    .catch(() => {
      slot.innerHTML = navigator.onLine
        ? `<div class="page-loading">تعذّر تحميل صفحة ${ar(p)}</div>`
        : `<div class="page-loading">صفحة ${ar(p)} غير محفوظة للقراءة دون اتصال</div>`;
    })
    .finally(() => pending.delete(p));
  pending.set(p, job);
  return job;
}

function unloadPage(p) {
  loaded.delete(p);
  pending.delete(p);
  const slot = $(`page-slot-${p}`);
  if (slot) slot.replaceChildren();
}

function fitPage(p) {
  const entry = loaded.get(p);
  if (!entry) return;
  const slot = $(`page-slot-${p}`);
  const w = slot.clientWidth, h = slot.clientHeight;
  if (!w || !h) return;
  const pad = 8;
  const scale = Math.min((w - pad * 2) / PAGE_W, (h - pad * 2) / PAGE_H);
  const sw = PAGE_W * scale;
  let left = (w - sw) / 2;
  if (spread) left = p % 2 === 1 ? 0 : w - sw;   // odd page on the right: hug the spine
  entry.host.style.transform = `translate(${left}px, ${(h - PAGE_H * scale) / 2}px) scale(${scale})`;
}

let selected = null;            // { surah, ayah, page }

function bindSvgInteractions(root, page) {
  root.addEventListener('click', (e) => {
    const poly = e.target.closest && e.target.closest('.ayahPolygon');
    if (!poly) return;
    e.stopPropagation();
    selectAyah(+poly.getAttribute('surah'), +poly.getAttribute('ayah'), page);
  });
  if (selected && selected.page === page) highlight(selected);
}

function highlight(sel) {
  for (const { root } of loaded.values()) {
    root.querySelectorAll('.ayahPolygon.selected').forEach((el) => el.classList.remove('selected'));
    if (sel) {
      root.querySelectorAll(`.ayahPolygon[surah="${sel.surah}"][ayah="${sel.ayah}"]`)
        .forEach((el) => el.classList.add('selected'));
    }
  }
}

function themeFor(surah, ayah) {
  const t = (window.QURAN_THEMES || []).find(([s, a, b]) => s === surah && ayah >= a && ayah <= b);
  return t ? t[3] : '';
}

function selectAyah(surah, ayah, page) {
  selected = { surah, ayah, page };
  highlight(selected);
  $('ayah-ref').textContent = `سورة ${surahName(surah)} – الآية ${ar(ayah)}`;
  const text = window.QURAN_TEXT ? window.QURAN_TEXT[surah - 1][ayah - 1] : '';
  $('ayah-text').textContent = text ? `${text} ﴿${ar(ayah)}﴾` : '';
  $('ayah-theme').textContent = themeFor(surah, ayah);
  getBookmark(`a:${surah}:${ayah}`).then((bm) => {
    $('ayah-bookmark').textContent = bm ? 'إزالة الحفظ' : 'حفظ الآية';
  });
  $('ayah-sheet').classList.add('open');
  $('ayah-sheet').setAttribute('aria-hidden', 'false');
}

function closeSheet() {
  selected = null;
  highlight(null);
  $('ayah-sheet').classList.remove('open');
  $('ayah-sheet').setAttribute('aria-hidden', 'true');
}

function setupSheet() {
  $('sheet-close').addEventListener('click', closeSheet);
  $('reader').addEventListener('click', () => { if (selected) closeSheet(); });
  $('ayah-copy').addEventListener('click', async () => {
    if (!selected) return;
    const { surah, ayah } = selected;
    const text = `${window.QURAN_TEXT[surah - 1][ayah - 1]} ﴿${ar(ayah)}﴾\n[سورة ${surahName(surah)}: ${ar(ayah)}]`;
    try { await navigator.clipboard.writeText(text); toast('تم النسخ'); } catch (e) { toast('تعذّر النسخ'); }
  });
  $('ayah-bookmark').addEventListener('click', async () => {
    if (!selected) return;
    const { surah, ayah, page } = selected;
    await toggleBookmark({ id: `a:${surah}:${ayah}`, page, surah, ayah, type: 'ayah' });
    const bm = await getBookmark(`a:${surah}:${ayah}`);
    $('ayah-bookmark').textContent = bm ? 'إزالة الحفظ' : 'حفظ الآية';
  });
}

// ------------------------------------------------------------------
// 6. Drawer: surah index, juz grid, bookmarks
// ------------------------------------------------------------------
function openDrawer(tab) {
  if (tab) selectTab(tab);
  $('drawer').classList.add('open');
  $('drawer').setAttribute('aria-hidden', 'false');
  $('scrim').classList.add('show');
  markCurrent();
  refreshOfflineStatus();
  if (document.querySelector('.tab.active').dataset.tab === 'bookmarks') renderBookmarks();
}
function closeDrawer() {
  $('drawer').classList.remove('open');
  $('drawer').setAttribute('aria-hidden', 'true');
  $('scrim').classList.remove('show');
}
const drawerOpen = () => $('drawer').classList.contains('open');

function selectTab(name) {
  document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === `tab-${name}`));
  if (name === 'bookmarks') renderBookmarks();
  markCurrent();
}

function jump(p) {
  closeDrawer();
  goToPage(p);
}

function setupDrawer() {
  $('menu-btn').addEventListener('click', () => (drawerOpen() ? closeDrawer() : openDrawer()));
  $('scrim').addEventListener('click', closeDrawer);
  document.querySelectorAll('.tab').forEach((t) => t.addEventListener('click', () => selectTab(t.dataset.tab)));

  $('goto-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const p = parseInt($('goto-input').value, 10);
    if (p >= 1 && p <= TOTAL_PAGES) { $('goto-input').value = ''; jump(p); } else toast('أدخل رقمًا بين ١ و٦٠٤');
  });

  // Surah list
  const list = $('surah-list');
  for (const s of INDEX.surahs) {
    const li = document.createElement('li');
    li.dataset.surah = s.id;
    li.dataset.search = `${s.id} ${s.name} ${s.tr}`.toLowerCase();
    li.innerHTML = `<span class="num">${ar(s.id)}</span>
      <span class="main"><div class="title">${s.name}</div>
      <div class="sub">${s.type === 'meccan' ? 'مكية' : 'مدنية'} · ${ar(s.verses)} آية · ${s.tr}</div></span>
      <span class="side">ص ${ar(s.page)}</span>`;
    li.addEventListener('click', () => jump(s.page));
    list.appendChild(li);
  }
  $('surah-search').addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase().replace(/[٠-٩]/g, (d) => AR_DIGITS.indexOf(d));
    list.querySelectorAll('li').forEach((li) => { li.hidden = q && !li.dataset.search.includes(q); });
  });

  // Juz grid
  const grid = $('juz-grid');
  INDEX.juz.forEach((page, i) => {
    const b = document.createElement('button');
    b.dataset.juz = i + 1;
    b.innerHTML = `الجزء ${ar(i + 1)}<small>ص ${ar(page)}</small>`;
    b.addEventListener('click', () => jump(page));
    grid.appendChild(b);
  });
}

function markCurrent() {
  const s = pageSurah(currentPage);
  document.querySelectorAll('#surah-list li').forEach((li) => li.classList.toggle('current', +li.dataset.surah === s));
  const j = INDEX.pages[currentPage - 1].juz;
  document.querySelectorAll('#juz-grid button').forEach((b) => b.classList.toggle('current', +b.dataset.juz === j));
  const cur = document.querySelector('#tab-surahs.active #surah-list li.current');
  if (cur && !$('surah-search').value) cur.scrollIntoView({ block: 'center' });
}

async function renderBookmarks() {
  const list = $('bookmark-list');
  const bookmarks = (await getBookmarks()).sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  list.replaceChildren();
  for (const bm of bookmarks) {
    const li = document.createElement('li');
    const date = new Date(bm.timestamp).toLocaleDateString('ar');
    const title = bm.type === 'ayah'
      ? `سورة ${surahName(bm.surah)} – الآية ${ar(bm.ayah)}`
      : `صفحة ${ar(bm.page)} – ${pageLabel(bm.page).surah}`;
    li.innerHTML = `<span class="num">${bm.type === 'ayah' ? '۝' : '▭'}</span>
      <span class="main"><div class="title"></div><div class="sub">${pageLabel(bm.page).juz} · ${date}</div></span>
      <button class="remove" aria-label="حذف">✕</button>`;
    li.querySelector('.title').textContent = title;
    li.addEventListener('click', () => {
      jump(bm.page);
      if (bm.type === 'ayah') loadPageContent(bm.page).then(() => selectAyah(bm.surah, bm.ayah, bm.page));
    });
    li.querySelector('.remove').addEventListener('click', async (e) => {
      e.stopPropagation();
      await deleteBookmark(bm.id);
      refreshBookmarkButton();
      renderBookmarks();
    });
    list.appendChild(li);
  }
}

async function refreshBookmarkButton() {
  const on = !!(await getBookmark(`p:${currentPage}`));
  $('bookmark-btn').classList.toggle('on', on);
  $('bookmark-btn').setAttribute('aria-pressed', on);
  $('bookmark-label').textContent = on ? 'محفوظة' : 'حفظ الصفحة';
}

// ------------------------------------------------------------------
// 7. Keyboard & feedback
// ------------------------------------------------------------------
function setupKeyboard() {
  document.addEventListener('keydown', (e) => {
    if (e.target.matches('input, textarea')) {
      if (e.key === 'Escape') e.target.blur();
      return;
    }
    switch (e.key) {
      case 'ArrowLeft': case 'PageDown': case ' ': swiper.slideNext(); break;      // RTL: next page is to the left
      case 'ArrowRight': case 'PageUp': swiper.slidePrev(); break;
      case 'Home': goToPage(1); break;
      case 'End': goToPage(TOTAL_PAGES); break;
      case 'm': case 'M': drawerOpen() ? closeDrawer() : openDrawer(); break;
      case 'b': case 'B': $('bookmark-btn').click(); break;
      case 'Escape': if (drawerOpen()) closeDrawer(); else if (selected) closeSheet(); break;
      default: return;
    }
    e.preventDefault();
  });
}

// ------------------------------------------------------------------
// 8. Install & offline reading (service worker in sw.js)
// ------------------------------------------------------------------
const PAGES_CACHE = 'quran-pages';      // must match sw.js
const DOWNLOAD_PARALLEL = 6;
const pageUrl = (p) => new URL(`Pages/${String(p).padStart(3, '0')}.html`, location.href).href;
let offlineReady = false;
let downloading = false;
let installPrompt = null;

async function setupOffline() {
  // Needs HTTPS (or localhost) and a browser with service workers.
  if (!('serviceWorker' in navigator) || !window.caches) return;
  try { await navigator.serviceWorker.register('sw.js'); } catch (e) { return; }
  offlineReady = true;

  // Pages regenerated since they were stored: drop the stale copies.
  try {
    const seen = localStorage.getItem('quran.pagesVersion');
    if (seen && seen !== INDEX.pagesVersion) await caches.delete(PAGES_CACHE);
    localStorage.setItem('quran.pagesVersion', INDEX.pagesVersion);
  } catch (e) { /* no localStorage: keep what is stored */ }

  $('offline-box').hidden = false;
  $('offline-download').addEventListener('click', () => (downloading ? (downloading = false) : downloadAll()));
  $('offline-remove').addEventListener('click', removeOffline);

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    installPrompt = e;
    $('install-btn').hidden = false;
  });
  window.addEventListener('appinstalled', () => { $('install-btn').hidden = true; toast('تم تثبيت التطبيق'); });
  $('install-btn').addEventListener('click', async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice;
    installPrompt = null;
    $('install-btn').hidden = true;
  });
  refreshOfflineStatus();
}

async function cachedPages() {
  const cache = await caches.open(PAGES_CACHE);
  const have = new Set();
  for (const req of await cache.keys()) {
    const m = new URL(req.url).pathname.match(/\/Pages\/(\d{3})\.html$/);
    if (m) have.add(+m[1]);
  }
  return have;
}

const isStandalone = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

async function refreshOfflineStatus() {
  if (!offlineReady || downloading) return;
  const n = (await cachedPages()).size;
  let msg = n === TOTAL_PAGES
    ? 'المصحف كامل محفوظ على هذا الجهاز'
    : `محفوظ ${ar(n)} من ${ar(TOTAL_PAGES)} صفحة`;
  if (navigator.storage && navigator.storage.estimate) {
    const { usage } = await navigator.storage.estimate();
    if (usage) msg += ` · ${ar(Math.round(usage / 1048576))} م.ب`;
  }
  if (isIOS() && !isStandalone()) msg += ' · للتثبيت: زر المشاركة ← «إضافة إلى الشاشة الرئيسية»';
  $('offline-status').textContent = msg;
  $('offline-progress').value = n;
  $('offline-download').textContent = n === TOTAL_PAGES ? 'تم التنزيل' : 'تنزيل المصحف كاملًا';
  $('offline-download').disabled = n === TOTAL_PAGES;
  $('offline-remove').disabled = n === 0;
}

async function downloadAll() {
  if (!navigator.onLine) return toast('لا يوجد اتصال بالإنترنت');
  // Ask the browser not to evict the stored Mushaf when space runs low.
  if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});

  const cache = await caches.open(PAGES_CACHE);
  const have = await cachedPages();
  const todo = [];
  for (let p = 1; p <= TOTAL_PAGES; p++) if (!have.has(p)) todo.push(p);
  let done = have.size, failed = 0;

  downloading = true;
  $('offline-download').textContent = 'إيقاف';
  $('offline-remove').disabled = true;
  const show = () => {
    $('offline-progress').value = done;
    $('offline-status').textContent = `جارٍ التنزيل… ${ar(done)} من ${ar(TOTAL_PAGES)}`;
  };
  show();

  const worker = async () => {
    while (downloading && todo.length) {
      const p = todo.shift();
      try { await cache.add(pageUrl(p)); done++; } catch (e) { failed++; }
      show();
      if (failed > 10) downloading = false;     // connection lost: stop rather than hammer on
    }
  };
  await Promise.all(Array.from({ length: DOWNLOAD_PARALLEL }, worker));

  const stopped = !downloading;
  downloading = false;
  if (failed) toast(`تعذّر تنزيل ${ar(failed)} صفحة، حاول مرة أخرى`);
  else if (stopped && done < TOTAL_PAGES) toast('تم إيقاف التنزيل');
  else toast('المصحف محفوظ للقراءة دون اتصال');
  refreshOfflineStatus();
}

async function removeOffline() {
  if (!confirm('حذف الصفحات المحفوظة من هذا الجهاز؟ ستبقى المحفوظات والعلامات كما هي.')) return;
  await caches.delete(PAGES_CACHE);
  toast('تم حذف النسخة المحفوظة');
  refreshOfflineStatus();
}

let toastTimer = null;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
}
