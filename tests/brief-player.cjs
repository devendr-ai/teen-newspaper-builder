// The car-ride brief on Read & Play, in a real browser at laptop and phone sizes: node tests/brief-player.cjs <base url>
const { chromium } = require('playwright');
const B = process.argv[2];
const out = [];
const ok = (name, pass, info) => out.push({ name, pass: !!pass, info });
(async () => {
  const browser = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'], ...(process.env.CHROME ? { executablePath: process.env.CHROME } : {}) });
  for (const [label, vp] of [['web', { width: 1280, height: 900 }], ['mobile', { width: 390, height: 844 }]]) {
    const page = await browser.newPage({ viewport: vp, deviceScaleFactor: 2 });
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.addInitScript(() => { window.__counts = []; window.npCount = (p) => window.__counts.push(p); });
    await page.goto(B + 'play/index.html', { waitUntil: 'networkidle' });
    await page.waitForSelector('#brief .nb', { timeout: 5000 });
    const h = await page.$eval('#brief .nb', e => e.getBoundingClientRect().height);
    ok(`${label}: card is compact`, h < (label === 'web' ? 90 : 80), Math.round(h));
    await page.$eval('#brief', e => e.scrollIntoView({ block: 'center' }));
    
    await page.evaluate(() => { window.npCount = (p) => window.__counts.push(p); });
    await page.click('#brief .nb-play');
    await page.waitForTimeout(2500);
    
    const state = await page.evaluate(() => ({ text: document.querySelector('#brief .nb-t').textContent, h: document.querySelector('#brief .nb-h').innerText,
      chips: !document.querySelector('#brief .nb-ch').hidden, counts: window.__counts }));
    ok(`${label}: plays`, /^0:0[1-9]|^0:[1-9]/.test(state.text) || /of/.test(await page.$eval('#brief .nb-s', e => e.innerText)), state);
    ok(`${label}: counts a start`, state.counts.some(c => c.startsWith('brief/started')), state.counts);
    ok(`${label}: shows where it is`, /^Now: /.test(state.h), state.h);
    
    // jump to Cyclone Arnab from the menu
    await page.click('#brief .nb-more');
    ok(`${label}: menu opens`, await page.isVisible('#brief .nb-menu'));
    
    await page.click('#brief .nb-menu .jump button:nth-child(2)');
    await page.waitForTimeout(800);
    ok(`${label}: jumps to a story`, /Cyclone Arnab/.test(await page.$eval('#brief .nb-h', e => e.innerText)));
    // read along
    await page.click('#brief .nb-more'); await page.click('#brief [data-do="read"]');
    await page.waitForTimeout(400);
    const now = await page.$eval('.nb-sheet .nb-line.now', e => e.innerText).catch(() => '');
    ok(`${label}: read along highlights the line`, now.length > 0, now.slice(0, 80));
    
    await page.click('.nb-sheet [data-do="close"]');
    // mini player when scrolled away
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(600);
    const away = await page.$eval('#brief .nb', e => e.getBoundingClientRect().bottom < (document.querySelector('header.bar')?.offsetHeight || 0));
    ok(`${label}: mini-player while scrolled away`, away ? await page.isVisible('.nb-mini') : !(await page.isVisible('.nb-mini')), { away });
    if (!away) { out.push({ name: `${label}: (page too short to scroll the card away)`, pass: true }); }
    
    await page.click(away ? '.nb-mini .nb-play' : '#brief .nb-play'); await page.waitForTimeout(300);
    ok(`${label}: pause from the mini-player`, await page.evaluate(() => /Play/.test(document.querySelector('#brief .nb-play').getAttribute('aria-label'))));
    ok(`${label}: no page errors`, errors.length === 0, errors);
    await page.close();
  }
  const home = await browser.newPage();
  await home.goto(B + 'index.html', { waitUntil: 'networkidle' });
  ok('home: no brief on the home page', !(await home.$('#brief')) && !(await home.$('.nb')));
  await browser.close();
  console.log(JSON.stringify(out, null, 1));
  process.exit(out.every(o => o.pass) ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
