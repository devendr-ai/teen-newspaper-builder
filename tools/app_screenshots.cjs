// App Store screenshots of the app pack (6.9" iPhone and 13" iPad), with a stand-in for the app so the
// Listen tab shows a player and For parents shows "This app":
//   NODE_PATH=$(npm root -g) node tools/app_screenshots.cjs https://newspebbles.com/app/ mobile/store/screenshots
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const [B, OUT] = [process.argv[2], process.argv[3] || 'mobile/store/screenshots'];
const DEVICES = [['iphone', { width: 440, height: 956 }, 3], ['ipad', { width: 1032, height: 1376 }, 2]];

function stand_in() {
  window.ReactNativeWebView = { postMessage: (raw) => {
    const m = JSON.parse(raw), reply = (x) => setTimeout(() => window.__np && window.__np(x), 30);
    if (m.t === 'settings?') reply({ t: 'settings', reminder: { on: true, time: '07:00' },
      offline: { state: '✓ Up to date', what: 'Papers and audio from the last 7 days', note: 'New papers download when the app opens.' } });
    if (m.t === 'audio' && m.op === 'list') reply({ t: 'status', s: { id: m.id, title: m.title, track: m.tracks[0].title,
      index: 0, count: m.tracks.length, playing: true, time: 95, duration: 240, ended: false } });
  } };
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  for (const [name, viewport, scale] of DEVICES) {
    const p = await b.newPage({ viewport, deviceScaleFactor: scale });
    await p.addInitScript(stand_in);
    const shot = async (n, url, then) => {
      await p.goto(B + url, { waitUntil: 'networkidle' });
      if (then) await then();
      await p.waitForTimeout(700);
      await p.screenshot({ path: path.join(OUT, `${name}-${n}.png`) });
    };
    await shot('1-home', 'index.html');
    await shot('2-read-and-play', 'play/index.html', () => p.click('.who[data-band="Ages 9–11"]').catch(() => {}));
    const paper = await p.$eval('.tile:not([hidden]) h2 a', (a) => a.getAttribute('href'));
    await shot('3-paper', 'play/' + paper);
    await shot('4-listen', 'play/listen.html', () => p.click('#lp-briefs .lp-row'));
    await shot('5-for-parents', 'parents.html', () => p.evaluate(() => {
      const h = document.documentElement; h.classList.add('np-unlocked'); h.classList.remove('np-gate-open');
      document.querySelectorAll('.np-gate').forEach((e) => e.remove()); document.querySelectorAll('[inert]').forEach((e) => e.removeAttribute('inert'));
    }));
    await p.close();
  }
  await b.close();
  console.log('screenshots in', OUT);
})();
