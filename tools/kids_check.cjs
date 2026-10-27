// A real-browser check of a built site (tools/kids_check.cjs), for App Store / Play review.
//
//   python -m ygc site --kids --out _kids && python -m http.server 8777 --directory _kids &
//   NODE_PATH=$(npm root -g) node tools/kids_check.cjs http://localhost:8777/ kids
//   (or "web" for the public website build, which must not show the gate)
//
// Kids: every page type loads with no request to another host; links out, email, share, print and
// the parents' pages ask a grown-up first and then work; 3 wrong answers pause the gate for 30 s.
// Web: nothing is gated, and nothing loads from Google Fonts or a CDN. Prints one JSON report;
// exit code 1 if anything failed. Needs Playwright with Chromium (CHROME=path to use a given one).
const { chromium } = require("playwright");
// A new window starts at about:blank: wait until it reaches an address matching `re` (slow machines).
const settle = async (w, re) => { if (w) await w.waitForURL(re, { timeout: 15000 }).catch(() => {}); return w; };
const fs = require("fs"), path = require("path");

const BASE = process.argv[2] || "http://localhost:8777/", MODE = process.argv[3] || "kids";
const ROOT = path.join(__dirname, "..");
const results = [], external = new Map(), subscriptions = [];
let browser;
const ok = (name, pass, detail) => { results.push({ name, pass: !!pass, detail: detail || "" }); };

const ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(" ");
const TENS = { twenty: 20, thirty: 30, forty: 40, fifty: 50, sixty: 60, seventy: 70, eighty: 80, ninety: 90 };
function num(w) {                                  // "twenty-three" -> 23
  let n = 0;
  for (const p of w.split("-")) n += TENS[p] !== undefined ? TENS[p] : ONES.indexOf(p);
  return n;
}
function solve(q) {                                // the gate's question -> its answer
  let m = q.match(/What is ([a-z-]+) multiplied by ([a-z-]+)\?/);
  if (m) return num(m[1]) * num(m[2]);
  m = q.match(/What is ([a-z-]+) times ([a-z-]+), plus ([a-z-]+)\?/);
  if (m) return num(m[1]) * num(m[2]) + num(m[3]);
  throw new Error("unknown question: " + q);
}

(async () => {
  browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const host = new URL(BASE).host;
  let where = "";
  await ctx.route("**/*", (r) => {                // record anything leaving the site; never actually send it
    const u = new URL(r.request().url());
    if (u.host === host || u.protocol === "data:" || u.protocol === "blob:") return r.continue();
    // Chrome's built-in PDF viewer reads local extension/UI resources. These
    // schemes are not outside network hosts; HTTP(S) remains fully audited.
    if (u.protocol === "chrome-extension:" || u.protocol === "chrome:") return r.continue();
    // Tests never submit an email to the real delivery service.
    if (u.pathname === "/api/subscribe") {
      subscriptions.push({ url: u.href, method: r.request().method(), body: r.request().postData() });
      return r.fulfill({ status: 202, contentType: "application/json", body: '{"ok":true}',
        headers: { "Access-Control-Allow-Origin": new URL(BASE).origin,
          "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "POST" } });
    }
    const k = u.host;
    if (!external.has(k)) external.set(k, new Set());
    external.get(k).add(where);
    if (r.request().resourceType() === "document")           // a page a grown-up opened: a stand-in, not the real site
      return r.fulfill({ status: 200, contentType: "text/html", body: "<p>outside page</p>" });
    return r.abort();
  });
  await ctx.addInitScript(() => {
    window.__shared = []; window.__printed = 0; window.__opened = [];
    navigator.share = async (d) => { window.__shared.push(d); };
    window.print = () => { window.__printed++; };
    const open = window.open; window.open = (u, ...a) => { window.__opened.push(String(u)); return null; };
    document.addEventListener("click", (e) => {    // a link the gate let through: note it, don't leave
      const a = e.target.closest && e.target.closest('a[href^="mailto:"]');
      if (a) { window.__mailed = !e.defaultPrevented; e.preventDefault(); }
    });
  });
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(where + ": " + e.message));
  const go = async (u, label) => {
    where = label || u;
    await p.goto(BASE + u, { waitUntil: "load" });
    await p.waitForTimeout(400);
    for (let i = 0; i < 5; i++) { await p.mouse.wheel(0, 1200); await p.waitForTimeout(80); }
  };
  const gateShown = () => p.locator(".np-gate:not([hidden])").count();
  const answer = async (right = true) => {
    const q = await p.locator("#np-gate-q").textContent();
    await p.fill("#np-gate-answer", String(right ? solve(q) : solve(q) + 1));
    await p.click(".np-gate-ok");
    await p.waitForTimeout(250);
  };

  // ---------------------------------------------------------------- every page type
  await go("play/index.html");
  const issues = await p.evaluate(() => [...new Set([...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"))
    .filter((h) => /^[a-z-]+\/\d{4}-\d\d-\d\d\.html$/.test(h)))]);
  const pages = ["index.html", "play/index.html", "about.html", "standards.html", "corrections.html", "privacy.html",
    "terms.html", "404.html", "play/threads/index.html", "play/certificate.html?b=first", ...issues.map((h) => "play/" + h)];
  const papers = fs.readdirSync(path.join(ROOT, "editions")).filter((e) => fs.existsSync(path.join(ROOT, "editions", e, "edition.yaml")));
  for (const e of papers) pages.push(`e/${e}/index.html`);
  for (const u of pages) await go(u);
  const threads = await p.evaluate(() => [...document.querySelectorAll("a[href]")].map((a) => a.href).filter((h) => /threads\/[a-z-]+\.html$/.test(h)));
  ok("every page type loads", errors.length === 0, errors.slice(0, 3).join(" | "));
  ok("no subscription requests while browsing page types", subscriptions.length === 0);

  // Enabled subscription forms: placement, scoped math, and the app's gate.
  // Intercepted responses above ensure these checks can never send real email.
  const signupPages = ["index.html", "e/little-explorers/index.html", "parents.html"];
  for (const url of signupPages) {
    const before = subscriptions.length;
    await go(url);
    if (MODE === "kids" && await gateShown()) await answer(true);
    if (url === "index.html") {
      await p.locator('.agebar button[data-v="Ages 6–8"]').click();
      const signup = p.locator('.recommended:not([hidden]) .subscription-signup');
      if (!(await signup.count())) continue; // Disabled builds have no signup links.
      ok('homepage stays compact with no signup form', await p.locator('form[data-gate-form="subscribe"]').count() === 0);
      await signup.click();
      if (MODE === "kids") await answer(true);
      await p.locator('select[name="edition_slug"]').waitFor();
      ok('homepage paper is selected on Parents', await p.locator('select[name="edition_slug"]').inputValue() === 'little-explorers');
      await p.locator('select[name="edition_slug"]').selectOption('breakfast-table');
      ok('parent can change the selected paper', await p.locator('select[name="edition_slug"]').inputValue() === 'breakfast-table');
    }
    const form = p.locator('form[data-gate-form="subscribe"]:visible').first();
    if (!(await form.count())) continue; // Disabled builds deliberately have no forms.
    ok(`${url}: signup makes no initial requests`, subscriptions.length === before);
    ok(`${url}: correct subscription mode`,
      await form.getAttribute("data-subscribe-kids") === String(MODE === "kids"));
    if (await form.locator('select[name="edition_slug"]').count())
      await form.locator('select[name="edition_slug"]').selectOption("little-explorers");
    await form.locator('[name="email"]').fill("parent@example.com");
    if (MODE === "web") {
      await form.locator('[name="grownup_answer"]').fill("1");
      await form.evaluate(f => f.requestSubmit());
      ok(`${url}: wrong math sends nothing`, subscriptions.length === before);
      const factors = (await form.locator('[data-math-question]').textContent()).match(/\d+/g).map(Number);
      await form.locator('[name="grownup_answer"]').fill(String(factors[0] * factors[1]));
    } else ok(`${url}: no duplicate inline math`, await form.locator('[name="grownup_answer"]').count() === 0);
    const parentOpen = await p.evaluate(() => document.documentElement.hasAttribute('data-gate-page') && document.documentElement.classList.contains('np-unlocked'));
    await form.evaluate(f => f.requestSubmit());
    if (MODE === "kids" && !parentOpen) {
      ok(`${url}: app gate blocks network`, await gateShown() && subscriptions.length === before);
      await p.click(".np-gate-back");
      ok(`${url}: cancelling sends nothing`, subscriptions.length === before);
      await form.evaluate(f => f.requestSubmit());
      await answer(true);
    } else if (MODE === "kids") ok(`${url}: parent unlock is reused`, !(await gateShown()));
    await form.locator('.subscription-status').filter({ hasText: "Check your inbox to confirm" }).waitFor();
    const sent = subscriptions.slice(before).filter(r => r.method === "POST");
    ok(`${url}: one authorized request`, sent.length === 1 &&
      JSON.parse(sent[0].body).email === "parent@example.com");
  }

  if (MODE === "web") {
    // ---------------------------------------------------------------- the public website: unchanged, never gated
    const bad = [...external.keys()].filter((h) => /fonts\.(googleapis|gstatic)\.com|cdn\.jsdelivr\.net/.test(h));
    ok("no Google Fonts or CDN requests", bad.length === 0, bad.join(", "));
    await go(issues.length ? "play/" + issues[0] : "index.html");
    const went = await p.evaluate(() => {
      const a = document.querySelector('a[href^="http"]'); if (!a) return null;
      let through = null;
      document.addEventListener("click", (e) => { through = !e.defaultPrevented; e.preventDefault(); }, { once: true });
      a.click(); return through;
    });
    ok("links out go straight through (no gate on the website)", went === true && (await gateShown()) === 0 &&
       !(await p.evaluate(() => !!window.npGate)));
    await go("parents.html");
    ok("parents' page shows without a gate", await p.locator("body > .wrap").isVisible() && (await gateShown()) === 0);
    await go("builder.html");
    await p.waitForFunction(() => /ready/.test(document.getElementById("engine").textContent), null, { timeout: 120000 }).catch(() => {});
    ok("builder engine loads from this site", /ready/.test(await p.locator("#engine").textContent()),
       await p.locator("#engine").textContent());
  } else {
    // ---------------------------------------------------------------- kids: the gate, everywhere it's needed
    for (const u of threads.slice(0, 2)) await go(u.replace(BASE, ""));
    const issue = "play/" + issues[0];
    await go(issue);
    // 1. a source link in a Read & Play paper
    const src = p.locator('a[href^="http"]').first();
    await src.evaluate((a) => a.scrollIntoView());
    await src.evaluate((a) => a.click());
    ok("source link: gate appears", await gateShown());
    ok("gate is an accessible modal dialog", await p.locator('.np-gate[role="dialog"][aria-modal="true"][aria-labelledby]').count());
    const q = await p.locator("#np-gate-q").textContent();
    ok("question is word-based multiplication or two-step maths", /multiplied by|times .*, plus/.test(q), q);
    await answer(false); await answer(false); await answer(false);
    ok("3 wrong answers pause the gate", await p.locator("#np-gate-answer").isDisabled() &&
       /Too many tries/.test(await p.locator("#np-gate-msg").textContent()), await p.locator("#np-gate-msg").textContent());
    await p.waitForTimeout(31000);
    ok("after 30 seconds the gate asks again", !(await p.locator("#np-gate-answer").isDisabled()));
    const popup = p.waitForEvent("popup", { timeout: 15000 }).catch(() => null);
    const href = await src.getAttribute("href");
    await answer(true);
    const opened = await popup;
    await settle(opened, (u) => u.href.startsWith(href.slice(0, 20)));
    ok("right answer opens the source", opened && opened.url().startsWith(href.slice(0, 20)), opened ? opened.url() : "no new page");
    if (opened) await opened.close();
    // 2. the next link out asks again (no lasting unlock)
    await src.evaluate((a) => a.click());
    ok("every link out asks again", await gateShown());
    await p.click(".np-gate-back");
    ok("Go back closes the gate and stays on the page", !(await gateShown()) && p.url().includes(issue));
    // 3. Read & Play's "Print this paper (for grown-ups)"
    await p.locator("text=Print this paper (for grown-ups)").evaluate((a) => a.click());
    ok("Print this paper (Read & Play): gate appears", await gateShown());
    await answer(true);
    await p.waitForLoadState("load");
    ok("…then opens the paper's page", /\/e\/[a-z-]+\/index\.html$/.test(p.url()), p.url());
    // 4. email
    await p.locator('a[href^="mailto:"]').first().evaluate((a) => a.click());
    ok("email link: gate appears", await gateShown());
    await answer(true);
    ok("…then the email link goes through", await p.evaluate(() => window.__mailed === true));
    // 5. share
    await go("index.html");
    const share = p.locator("a.edition-share").first();
    if (await share.count()) {
      await share.evaluate((a) => a.click());
      ok("share: gate appears", await gateShown());
      await answer(true);
      await p.waitForTimeout(300);
      ok("…then the share sheet opens with the paper's link", await p.evaluate(() => window.__shared.length === 1 && /newspebbles|http/.test(window.__shared[0].url)));
    }
    // 6. "Print this paper" on the grown-ups' side
    const print = p.locator("a.recommended-print").first();
    if (await print.count()) {
      await print.evaluate((a) => a.click());
      ok("Print this paper (website side): gate appears", await gateShown());
      const pdf = p.waitForEvent("popup", { timeout: 15000 }).catch(() => null);
      await answer(true);
      const w = await settle(await pdf, /\.pdf$/);
      ok("…then the PDF opens", w && /\.pdf$/.test(w.url()), w ? w.url() : "");
      if (w) await w.close();
    }
    // 7. certificate printing
    await p.evaluate(() => localStorage.setItem("rp-badges", JSON.stringify({ first: "2026-10-25" })));
    await go("play/certificate.html?b=first");
    await p.locator("button.print").evaluate((b) => b.click());
    ok("certificate print: gate appears", await gateShown());
    await answer(true);
    ok("…then printing opens", await p.evaluate(() => window.__printed === 1));
    // 8. the parents' pages
    for (const u of ["parents.html", "play/report.html", "feedback.html"]) {
      await go("index.html"); await go(u);
      const hidden = await p.evaluate(() => getComputedStyle(document.body.firstElementChild).visibility === "hidden");
      ok(`${u}: hidden behind the gate`, hidden && await gateShown());
      await p.click(".np-gate-back"); await p.waitForLoadState("load"); await p.waitForTimeout(300);
      ok(`${u}: Go back leaves the page`, !p.url().endsWith(u), p.url());
      await go(u); await answer(true);
      ok(`${u}: right answer shows it`, await p.evaluate(() => getComputedStyle(document.body.firstElementChild).visibility === "visible"));
    }
    // inside the unlocked feedback page, the form still asks first, then opens
    const form = p.locator("a.btn", { hasText: "Open the feedback form" });
    ok("feedback: no embedded form", (await p.locator("iframe").count()) === 0);
    await form.evaluate((a) => a.click());
    ok("feedback form button: gate appears even on the unlocked page", await gateShown());
    const fpop = p.waitForEvent("popup", { timeout: 15000 }).catch(() => null);
    await answer(true);
    const fw = await fpop;
    await settle(fw, /docs\.google\.com/);
    ok("…then the Google Form opens", fw && /docs\.google\.com/.test(fw.url()), fw ? fw.url() : "");
    if (fw) await fw.close();
    ok("feedback: email options", (await p.locator('a[href^="mailto:"]').count()) >= 2);
    // monthly report: printing works without a second question once the page is open
    await go("play/report.html"); await answer(true);
    await p.locator("button.print").click();
    ok("report: print works on the unlocked page", await p.evaluate(() => window.__printed >= 1) && !(await gateShown()));
    // back-forward cache: coming back asks again
    await go("parents.html"); await answer(true);
    await go("about.html"); await p.goBack(); await p.waitForTimeout(500);
    ok("parents' page asks again after leaving and coming back", await gateShown());
    // For parents → Design: the grown-up already answered, so Design opens without a second question
    await go("parents.html"); await answer(true);
    await p.locator('.parent-link[href="builder.html"]').click();
    await p.waitForURL(/builder\.html$/); await p.waitForTimeout(500);
    ok("parents → Design: one question, not two", !(await gateShown()), p.url());
    // 9. the builder: gated, then everything works, Pyodide from this site
    await go("builder.html");
    ok("builder: gate appears", await gateShown());
    await answer(true);
    await p.waitForFunction(() => /ready/.test(document.getElementById("engine").textContent), null, { timeout: 120000 }).catch(() => {});
    ok("builder: engine (Pyodide) loads from this site", /ready/.test(await p.locator("#engine").textContent()), await p.locator("#engine").textContent());
    await p.locator('#presets button[data-id="young-global-citizen"]').click();
    await p.waitForTimeout(300);
    const reply = fs.readFileSync(path.join(ROOT, "editions", "young-global-citizen", "issues", "2026", "2026-10-10.json"), "utf8");
    await p.fill("#reply", reply);
    await p.click("#makePdf");
    await p.waitForSelector('#result a[download]', { timeout: 60000 }).catch(() => {});
    const pdfLink = p.locator('#result a[download]');
    ok("builder: makes the PDF", await pdfLink.count(), (await p.locator("#result").textContent()).slice(0, 160));
    if (await pdfLink.count()) {
      const size = await pdfLink.evaluate(async (a) => (await (await fetch(a.href)).arrayBuffer()).byteLength);
      ok("builder: the PDF is real", size > 3000, size + " bytes");
      const openIt = p.locator('#result a[target="_blank"]');
      const ow = p.waitForEvent("popup", { timeout: 15000 }).catch(() => null);
      await openIt.evaluate((a) => a.click());
      const w = await ow;
      ok("builder: Open it works on the unlocked page", w && !(await gateShown()));
      if (w) await w.close();
    }
    await p.locator("[data-bot]").first().evaluate((b) => { b.disabled = false; b.click(); });
    ok("builder: AI helper button asks first", await gateShown());
    await answer(true);
    ok("…then opens the chatbot", await p.evaluate(() => window.__opened.length === 1 && /^https:/.test(window.__opened[0])));
    const gh = p.locator('a[href^="https://github.com"]');
    if (await gh.count()) { await gh.evaluate((a) => a.click()); ok("builder: GitHub link asks first", await gateShown()); await p.click(".np-gate-back"); }
    // zero outside requests, except ones a grown-up asked for after the gate
    const asked = new Set(["docs.google.com"]);
    if (href) asked.add(new URL(href).host);
    const leaks = [...external.entries()].filter(([h]) => !asked.has(h)).map(([h, w]) => `${h} (on ${[...w].join(", ")})`);
    ok("no request to any other host on load, on any page", leaks.length === 0, leaks.join("; "));
  }
  await browser.close();
  const failed = results.filter((r) => !r.pass);
  console.log(JSON.stringify({ mode: MODE, passed: results.length - failed.length, failed: failed.length, results }, null, 1));
  process.exitCode = failed.length ? 1 : 0;
})().catch(async (e) => {
  console.error(e);
  if (browser) await browser.close();
  process.exitCode = 1;
});
