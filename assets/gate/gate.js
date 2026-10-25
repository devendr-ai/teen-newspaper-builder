/* News Pebbles: the Parental Gate. Only in the app build (python -m ygc site --kids).

   Before anything that leaves the app or is meant for grown-ups, a grown-up answers a sum written
   in words ("What is sixteen multiplied by four?", or "What is twelve times three, plus five?").
   One listener covers the whole page:
   - links to other websites, and mailto:, tel: and sms: links;
   - anything marked data-gate (share, print), with data-gate-reason saying why;
   - pages marked <html data-gate-page> (parents, feedback, builder, monthly report): the page stays
     hidden until the sum is answered.
   The unlock lives only in this page view's memory: it ends when the page is left (or comes back
   from the back-forward cache), and links out, email and share always ask again
   (data-gate="always"). Three wrong answers pause the gate for 30 seconds.
   Nothing is stored except that pause, in sessionStorage. */
(function () {
  "use strict";
  if (window.npGate) return;
  var doc = document, html = doc.documentElement;
  var TRIES = 3, PAUSE_MS = 30000, PAUSE_KEY = "np-gate-pause";
  var REASONS = {
    link: "This opens a website outside News Pebbles.",
    mail: "This opens your email app.",
    share: "This shares a link with another app.",
    print: "This opens printing and saving.",
    page: "This part of News Pebbles is for parents and teachers.",
    grown: "This is for grown-ups."
  };
  var me = doc.currentScript ? doc.currentScript.src : "";
  var HOME = me ? me.replace(/gate\/gate\.js(\?.*)?$/, "index.html") : "index.html";
  var pageOpen = false, wrong = 0, pausedUntil = 0, box = null, sum = null, job = null, back = null, timer = 0, hidden = [];

  // ---------------------------------------------------------------- the sums
  var ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen " +
              "sixteen seventeen eighteen nineteen").split(" ");
  var TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
  function words(n) {
    if (n < 20) return ONES[n];
    if (n < 100) return TENS[Math.floor(n / 10)] + (n % 10 ? "-" + ONES[n % 10] : "");
    return ONES[Math.floor(n / 100)] + " hundred" + (n % 100 ? " and " + words(n % 100) : "");
  }
  function pick(lo, hi) {
    var c = window.crypto || window.msCrypto;
    if (c && c.getRandomValues) { var a = new Uint32Array(1); c.getRandomValues(a); return lo + (a[0] % (hi - lo + 1)); }
    return lo + Math.floor(Math.random() * (hi - lo + 1));
  }
  function newSum() {
    if (pick(0, 1)) {
      var a = pick(12, 19), b = pick(3, 9);
      return { q: "What is " + words(a) + " multiplied by " + words(b) + "?", a: a * b };
    }
    var x = pick(11, 15), y = pick(3, 6), z = pick(2, 9);
    return { q: "What is " + words(x) + " times " + words(y) + ", plus " + words(z) + "?", a: x * y + z };
  }

  // ---------------------------------------------------------------- the 30-second pause
  function pauseLeft() {
    var until = pausedUntil;
    try { until = Math.max(until, +sessionStorage.getItem(PAUSE_KEY) || 0); } catch (e) {}
    return Math.max(0, until - Date.now());
  }
  function pause() {
    pausedUntil = Date.now() + PAUSE_MS;
    try { sessionStorage.setItem(PAUSE_KEY, String(pausedUntil)); } catch (e) {}
  }

  // ---------------------------------------------------------------- the dialog
  function $(sel) { return box.querySelector(sel); }
  function build() {
    box = doc.createElement("div");
    box.className = "np-gate";
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-labelledby", "np-gate-title");
    box.setAttribute("aria-describedby", "np-gate-why");
    box.hidden = true;
    box.innerHTML =
      '<form class="np-gate-box" novalidate>' +
      '<p class="np-gate-kicker">For grown-ups</p>' +
      '<h2 id="np-gate-title">Ask a grown-up</h2>' +
      '<p id="np-gate-why"></p>' +
      '<label for="np-gate-answer" id="np-gate-q"></label>' +
      '<input id="np-gate-answer" name="answer" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="4" ' +
      'autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" aria-describedby="np-gate-msg">' +
      '<p id="np-gate-msg" class="np-gate-msg" role="alert" aria-live="assertive"></p>' +
      '<div class="np-gate-btns"><button type="button" class="np-gate-back">Go back</button>' +
      '<button type="submit" class="np-gate-ok">Continue</button></div></form>';
    doc.body.appendChild(box);
    $("form").addEventListener("submit", function (e) { e.preventDefault(); check(); });
    $(".np-gate-back").addEventListener("click", cancel);
    box.addEventListener("keydown", function (e) {
      if (e.key === "Escape" || e.key === "Esc") { e.preventDefault(); cancel(); return; }
      if (e.key !== "Tab") return;
      var f = [].filter.call(box.querySelectorAll("input,button"), function (el) { return !el.disabled; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && doc.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && doc.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }
  function ask() {
    sum = newSum();
    $("#np-gate-q").textContent = sum.q;
    $("#np-gate-answer").value = "";
  }
  function waitOut() {
    var left = pauseLeft(), input = $("#np-gate-answer"), ok = $(".np-gate-ok");
    clearTimeout(timer);
    if (left > 0) {
      input.disabled = ok.disabled = true;
      $("#np-gate-msg").textContent = "Too many tries. Please wait " + Math.ceil(left / 1000) + " seconds.";
      timer = setTimeout(waitOut, Math.min(1000, left));
      return true;
    }
    if (input.disabled) {
      input.disabled = ok.disabled = false;
      $("#np-gate-msg").textContent = "";
      wrong = 0;
      ask();
      input.focus();
    }
    return false;
  }
  function open(reason, onPass, onCancel) {
    if (!box) build();
    job = { pass: onPass, cancel: onCancel };
    back = doc.activeElement;
    $("#np-gate-why").textContent = REASONS[reason] || reason || REASONS.grown;
    $("#np-gate-msg").textContent = "";
    ask();
    hidden = [];
    [].forEach.call(doc.body.children, function (el) {          // the rest of the page can't be reached
      if (el !== box && !el.hasAttribute("inert")) { el.setAttribute("inert", ""); hidden.push(el); }
    });
    box.hidden = false;
    html.classList.add("np-gate-open");
    if (!waitOut()) $("#np-gate-answer").focus();
    else $(".np-gate-back").focus();
  }
  function close() {
    clearTimeout(timer);
    box.hidden = true;
    html.classList.remove("np-gate-open");
    hidden.forEach(function (el) { el.removeAttribute("inert"); });
    hidden = [];
    var j = job; job = null;
    if (back && back.focus && doc.contains(back)) { try { back.focus(); } catch (e) {} }
    return j;
  }
  function check() {
    if (waitOut()) return;
    var input = $("#np-gate-answer"), v = input.value.replace(/\s+/g, "");
    if (!/^\d+$/.test(v)) { $("#np-gate-msg").textContent = "Please type the answer as a number."; input.focus(); return; }
    if (+v === sum.a) { wrong = 0; var j = close(); if (j && j.pass) j.pass(); return; }
    wrong += 1;
    if (wrong >= TRIES) { pause(); waitOut(); $(".np-gate-back").focus(); return; }
    $("#np-gate-msg").textContent = "That's not right. Here is a new one.";
    ask();
    input.focus();
  }
  function cancel() { var j = close(); if (j && j.cancel) j.cancel(); }

  // ---------------------------------------------------------------- what needs a grown-up
  function reasonFor(el) {
    if (box && box.contains(el)) return null;
    var g = el.getAttribute("data-gate");
    if (g !== null) {
      if (g !== "always" && pageOpen) return null;           // inside an unlocked parents' page
      return el.getAttribute("data-gate-reason") || "grown";
    }
    if (el.tagName !== "A" || !el.hasAttribute("href")) return null;
    var href = (el.getAttribute("href") || "").trim();
    if (/^(mailto|tel|sms):/i.test(href)) return "mail";
    var u;
    try { u = new URL(el.href, location.href); } catch (e) { return null; }
    if (u.protocol === "blob:" || u.protocol === "javascript:" || href.charAt(0) === "#") return null;
    return u.origin !== location.origin ? "link" : null;    // leaving the app, always
  }
  function intercept(e) {
    var el = e.target && e.target.closest ? e.target.closest("a[href], [data-gate]") : null;
    if (!el) return;
    if (el.__npGatePass) { el.__npGatePass = false; return; }   // the grown-up already said yes
    var why = reasonFor(el);
    if (!why) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    open(why, function () { el.__npGatePass = true; el.click(); });
  }
  doc.addEventListener("click", intercept, true);
  doc.addEventListener("auxclick", function (e) { if (e.button === 1) intercept(e); }, true);

  // ---------------------------------------------------------------- parents' pages
  function leave() {
    var ref = "";
    try { ref = doc.referrer ? new URL(doc.referrer).origin : ""; } catch (e) {}
    if (ref === location.origin && history.length > 1) history.back();
    else location.href = html.getAttribute("data-gate-back") || HOME;
  }
  function lockPage() {
    pageOpen = false;
    html.classList.remove("np-unlocked");
    open("page", function () { pageOpen = true; html.classList.add("np-unlocked"); }, leave);
  }
  function start() {
    if (html.hasAttribute("data-gate-page")) lockPage();
  }
  window.addEventListener("pageshow", function (e) {           // back from the back-forward cache: ask again
    if (e.persisted && html.hasAttribute("data-gate-page")) { if (box && !box.hidden) close(); lockPage(); }
  });
  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", start); else start();

  // For code that leaves the app or shares by itself: npGate("share", function () { ... }).
  window.npGate = function (reason, onPass, onCancel) { open(reason, onPass, onCancel); };
})();
