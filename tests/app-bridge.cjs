// The app build's bridge (assets/app/app.js) in a real browser, with a stand-in for the iPhone app:
//   node tests/app-bridge.cjs <base url of an app build with narration>
// The stand-in records what pages send (window.__sent) and answers like the app does.
const { chromium } = require('playwright');
const B = process.argv[2];
const out = [];
const ok = (name, pass, info) => out.push({ name, pass: !!pass, info });

function nativeApp() {
  window.__sent = [];
  window.ReactNativeWebView = {
    postMessage: (raw) => {
      const m = JSON.parse(raw);
      window.__sent.push(m);
      const reply = (x) => setTimeout(() => window.__np && window.__np(x), 30);
      if (m.t === 'settings?') reply({ t: 'settings', reminder: { on: false, time: '06:45' },
        offline: { state: '✓ Up to date', what: 'Papers and audio from the last 7 days · 41 MB', note: 'Updated 6:31 AM.' } });
      if (m.t === 'audio' && m.op === 'list') reply({ t: 'status', s: { id: m.id, title: m.title, track: m.tracks[0].title,
        index: 0, count: m.tracks.length, playing: true, time: 12, duration: 60, ended: false } });
    },
  };
}

(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'],
    ...(process.env.CHROME ? { executablePath: process.env.CHROME } : {}) });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = []; page.on('pageerror', (e) => errors.push(e.message));
  await page.addInitScript(nativeApp);
  const sent = () => page.evaluate(() => window.__sent);

  // Listen: the list, then playing in the phone's player
  await page.goto(B + 'play/listen.html', { waitUntil: 'networkidle' });
  const rows = await page.$$eval('.lp-row', (r) => r.map((x) => x.dataset.id));
  ok('listen: briefs and papers listed', rows.some((r) => r.startsWith('brief-')) && rows.some((r) => r.startsWith('paper-')), rows);
  ok('listen: the tab bar has Listen, current', await page.$eval('.tabbar a[aria-current="page"]', (a) => a.textContent.trim()) === 'Listen');
  ok('listen: claims its own player', (await sent()).some((m) => m.t === 'claim' && m.id === '*'));
  await page.click('#lp-papers .lp-row');
  await page.waitForTimeout(300);
  const list = (await sent()).find((m) => m.t === 'audio' && m.op === 'list');
  ok('listen: hands the paper to the phone, every track', list && list.tracks.length > 1 && list.tracks.every((t) => /\/play\/audio\/[0-9a-f]+\.mp3$/.test(t.src) && t.title), list);
  ok('listen: shows what is playing', await page.isVisible('#lp-now') && (await page.$eval('#lp-papers .lp-row', (r) => r.getAttribute('aria-current'))) === 'true');
  await page.click('#lp-now .lp-next');
  ok('listen: next goes to the phone', (await sent()).some((m) => m.t === 'audio' && m.op === 'next'));

  // The car-ride brief on Read & Play plays in the phone's player
  await page.goto(B + 'play/index.html', { waitUntil: 'networkidle' });
  await page.waitForSelector('#brief .nb', { timeout: 5000 });
  ok('brief: the podcast links are hidden in the app', !(await page.isVisible('#brief .nb-menu a[href^="podcasts:"]')));
  await page.click('#brief .nb-play');
  await page.waitForTimeout(400);
  const brief = (await sent()).filter((m) => m.t === 'audio' && m.op === 'list').pop();
  ok('brief: plays in the phone\'s player', brief && brief.id.startsWith('brief-') && /\/play\/audio\/[0-9a-f]+\.mp3$/.test(brief.tracks[0].src), brief);
  ok('brief: its card follows the phone', /^Now: |0:12/.test(await page.$eval('#brief .nb', (e) => e.innerText)),
    await page.$eval('#brief .nb', (e) => e.innerText.slice(0, 120)));

  // Home: the app's tab bar
  await page.goto(B + 'index.html', { waitUntil: 'networkidle' });
  const tabs = await page.$$eval('nav.tabbar a', (a) => a.map((x) => x.textContent.trim()));
  ok('home: Home, Read & Play, Listen, For parents', JSON.stringify(tabs) === JSON.stringify(['Home', 'Read & Play', 'Listen', 'For parents']), tabs);
  const pg = (await sent()).filter((m) => m.t === 'page').pop();
  ok('home: tells the app its colour', pg && /^rgb/.test(pg.bg), pg);

  // For parents → This app (after the gate)
  await page.goto(B + 'parents.html', { waitUntil: 'networkidle' });
  await page.evaluate(() => {                         // past the gate (tests/test_kids_mode.py checks the gate itself)
    const h = document.documentElement; h.classList.add('np-unlocked'); h.classList.remove('np-gate-open');
    document.querySelectorAll('.np-gate').forEach((e) => e.remove()); document.querySelectorAll('[inert]').forEach((e) => e.removeAttribute('inert'));
  });
  await page.waitForTimeout(200);
  ok('parents: This app is shown, filled in', await page.isVisible('#np-app') && (await page.$eval('#np-off-what', (e) => e.textContent)).includes('41 MB'));
  await page.check('#np-rem-on');
  const rem = (await sent()).filter((m) => m.t === 'reminder').pop();
  ok('parents: the reminder goes to the phone', rem && rem.on === true && rem.time === '06:45', rem);
  const design = await page.$eval('.parent-link[href*="builder.html"]', (a) => a.getAttribute('href'));
  ok('parents: Design opens the website', /^https:\/\//.test(design), design);

  // Print after the gate, and the certificate's window.print()
  await page.goto(B + 'play/index.html', { waitUntil: 'networkidle' });
  const paper = await page.$eval('.tile h2 a', (a) => a.getAttribute('href'));
  await page.goto(B + 'e/' + paper, { waitUntil: 'networkidle' });                 // the paper's own page (PDF)
  const printLink = await page.$('a[data-gate-reason="print"][href$=".pdf"]');
  if (printLink) {
    await printLink.evaluate((a) => { a.__npGatePass = true; a.click(); });    // as the gate does after a right answer
    await page.waitForTimeout(200);
    const pr = (await sent()).filter((m) => m.t === 'print').pop();
    ok('paper: print goes to the phone\'s print sheet', pr && /\.pdf$/.test(pr.url), pr);
  } else ok('paper: has a gated print link', false);
  await page.goto(B + 'play/certificate.html', { waitUntil: 'networkidle' });
  await page.evaluate(() => window.print());
  await page.waitForTimeout(1500);
  const ph = (await sent()).filter((m) => m.t === 'printHtml').pop();
  ok('certificate: window.print() sends the page, styles built in', ph && ph.html.includes('<style') && !/<link rel="stylesheet"/.test(ph.html), ph && ph.html.length);

  ok('no page errors', errors.length === 0, errors);

  // Without the app (a browser), Listen plays by itself
  const plain = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errs2 = []; plain.on('pageerror', (e) => errs2.push(e.message));
  await plain.goto(B + 'play/listen.html', { waitUntil: 'networkidle' });
  await plain.click('#lp-papers .lp-row');
  await plain.waitForTimeout(1500);
  ok('browser: Listen plays by itself', await plain.isVisible('#lp-now'), errs2);
  await browser.close();
  console.log(JSON.stringify(out, null, 1));
  process.exit(out.every((x) => x.pass) ? 0 : 1);
})().catch((e) => { console.error(e); process.exit(2); });
