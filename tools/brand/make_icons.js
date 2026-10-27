// Draw the home-screen icons and favicon from assets/owl.svg (run after changing the owl):
//   NODE_PATH=$(npm root -g) node tools/brand/make_icons.js
// Needs Playwright with Chromium. The PNGs are committed, so building the site doesn't need this.
const { chromium } = require("playwright");
const fs = require("fs"), path = require("path");
const assets = path.join(__dirname, "..", "..", "assets");
const owl = fs.readFileSync(path.join(assets, "owl.svg"), "utf8");
(async () => {
  const b = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const p = await b.newPage();
  const shot = async (size, html, file) => {
    await p.setViewportSize({ width: size, height: size });
    await p.setContent(`<body style="margin:0">${html}</body>`);
    await p.screenshot({ path: path.join(assets, file), omitBackground: true });
  };
  for (const n of [180, 192, 512])             // full-bleed, the owl inside the middle 70% (phones crop to a circle)
    await shot(n, `<div style="width:${n}px;height:${n}px;background:#EFE9DD;display:grid;place-items:center">
      <div style="width:${n * 0.7}px;height:${n * 0.7}px">${owl.replace("<svg ", '<svg width="100%" height="100%" ')}</div></div>`, `owl-icon-${n}.png`);
  await shot(32, owl.replace("<svg ", '<svg width="32" height="32" '), "owl-32.png");
  await shot(512, owl.replace("<svg ", '<svg width="512" height="512" '), "owl-share.png");   // for the share pictures (ygc/share.py)
  // The iPhone/iPad app (mobile/assets): an opaque 1024 icon, the launch-screen owl, Android's adaptive layers.
  const app = path.join(__dirname, "..", "..", "mobile", "assets");
  const at = (n, inner, bg) => `<div style="width:${n}px;height:${n}px;${bg ? `background:${bg};` : ""}display:grid;place-items:center">
      <div style="width:${n * inner}px;height:${n * inner}px">${owl.replace("<svg ", '<svg width="100%" height="100%" ')}</div></div>`;
  const shotTo = async (size, html, file, transparent) => {
    await p.setViewportSize({ width: size, height: size });
    await p.setContent(`<body style="margin:0">${html}</body>`);
    await p.screenshot({ path: path.join(app, file), omitBackground: !!transparent });
  };
  await shotTo(1024, at(1024, 0.7, "#EFE9DD"), "icon.png");
  await shotTo(1024, at(1024, 1), "splash-icon.png", true);
  await shotTo(1024, at(1024, 0.6), "android-icon-foreground.png", true);
  await shotTo(1024, `<div style="width:1024px;height:1024px;background:#EFE9DD"></div>`, "android-icon-background.png");
  await shotTo(48, at(48, 1), "favicon.png", true);
  await b.close();
})();
