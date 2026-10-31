// Store screenshots of the app pack, with a stand-in for the app so the Listen tab shows a player and
// For parents shows "This app":
//   NODE_PATH=$(npm root -g) node tools/app_screenshots.cjs https://newspebbles.com/app/ mobile/store/screenshots
//     App Store: 6.9" iPhone (1320 × 2868) and 13" iPad (2064 × 2752)
//   ... mobile/store/screenshots/iphone-other-sizes apple-iphone-sizes
//     the other iPhone sizes App Store Connect accepts (1290 × 2796, 1284 × 2778, 1242 × 2688, 1242 × 2208)
//   NODE_PATH=$(npm root -g) node tools/app_screenshots.cjs https://newspebbles.com/app/ mobile/store/play play
//     Google Play: phone (1080 × 1920), 7" and 10" tablets (1200 × 1920, 1600 × 2560), the 1024 × 500
//     feature graphic and the 512 × 512 icon
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const [B, OUT, STORE] = [process.argv[2], process.argv[3] || 'mobile/store/screenshots', process.argv[4] || 'apple'];
const DEVICES = STORE === 'play'
  ? [['phone', { width: 360, height: 640 }, 3], ['tablet7', { width: 600, height: 960 }, 2], ['tablet10', { width: 800, height: 1280 }, 2]]
  : STORE === 'apple-iphone-sizes'                       // every other size App Store Connect accepts for iPhone
    ? [['iphone-1290x2796', { width: 430, height: 932 }, 3], ['iphone-1284x2778', { width: 428, height: 926 }, 3],
       ['iphone-1242x2688', { width: 414, height: 896 }, 3], ['iphone-1242x2208', { width: 414, height: 736 }, 3]]
    : [['iphone', { width: 440, height: 956 }, 3], ['ipad', { width: 1032, height: 1376 }, 2]];
const ICON = path.join(__dirname, '..', 'mobile', 'assets', 'icon.png');

// Google Play's feature graphic: the owl, the wordmark and what the app does, in the site's own fonts.
const FEATURE = (base) => `<!doctype html><html><head><base href="${base}"><style>
@font-face{font-family:B;src:url(fonts/BricolageGrotesque-latin.woff2)}
@font-face{font-family:A;src:url(fonts/AtkinsonHyperlegible-400-latin.woff2)}
@font-face{font-family:A;font-weight:700;src:url(fonts/AtkinsonHyperlegible-700-latin.woff2)}
html,body{margin:0;width:1024px;height:500px;background:#F4F1EA;overflow:hidden}
.w{display:flex;align-items:center;gap:44px;height:100%;padding:0 70px;box-sizing:border-box}
img{width:250px;height:250px;flex:none}
h1{font:800 82px/1 B;color:#1E2A32;margin:0;letter-spacing:-1.5px}h1 span{color:#E2584D}
p{font:400 32px/1.3 A;color:#3B4A53;margin:20px 0 26px}
ul{display:flex;gap:12px;margin:0;padding:0;list-style:none}
li{font:700 22px A;color:#fff;background:#007C89;border-radius:999px;padding:9px 20px}li:nth-child(2n){background:#E2584D}
</style></head><body><div class="w"><img src="owl.svg" alt=""><div><h1>News <span>Pebbles</span></h1>
<p>Today's news, written for your child's age</p><ul><li>Read</li><li>Play</li><li>Listen</li><li>Offline</li></ul></div></div></body></html>`;

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
  if (STORE === 'play') {
    const p = await b.newPage({ viewport: { width: 1024, height: 500 } });
    await p.setContent(FEATURE(B), { waitUntil: 'networkidle' });
    await p.evaluate(() => document.fonts.ready);
    await p.screenshot({ path: path.join(OUT, 'feature-graphic.png') });
    await p.setViewportSize({ width: 512, height: 512 });
    const icon = 'data:image/png;base64,' + fs.readFileSync(ICON).toString('base64');
    await p.setContent(`<body style="margin:0"><img src="${icon}" style="width:512px;height:512px;display:block">`);
    await p.screenshot({ path: path.join(OUT, 'icon-512.png') });
    await p.close();
  }
  await b.close();
  console.log('screenshots in', OUT);
})();
