/* News Pebbles app bridge (the app build: python -m ygc site --kids). See docs/APP_BUILD.md.
 *
 * Inside the iPhone/iPad app (window.ReactNativeWebView), pages hand a few things to the phone:
 *  - audio: the car-ride brief and the Listen tab play in the phone's own player, so they carry on with
 *    the screen locked and show on the lock screen (NPApp.audio, NPApp.listen);
 *  - print and share, after the Parental Gate: the phone's print and share sheets;
 *  - For parents → "This app": the morning reminder and what's saved for offline.
 * In a browser NPApp still exists (native: false): the Listen page plays its tracks itself, and
 * everything else stays as on the website. Nothing here sends data anywhere but the app itself.
 */
(function () {
  "use strict";
  var RN = window.ReactNativeWebView;
  var ROOT = ((document.currentScript && document.currentScript.src) || "").replace(/app\.js(\?.*)?$/, "");
  var statusFns = [], last = null, players = {};
  function post(m) { if (RN) RN.postMessage(JSON.stringify(m)); }
  function abs(u) { try { return new URL(u, location.href).href; } catch (e) { return u; } }
  function emit(s) { last = s; statusFns.forEach(function (f) { try { f(s); } catch (e) {} }); }

  // ---------------------------------------------------------------- audio in the phone's player
  function Track(meta) {                            // enough of an <audio> element for the brief player
    var self = this, L = {};
    this.meta = meta || {}; this.id = this.meta.id || "audio-" + Math.random().toString(36).slice(2);
    this.preload = "none"; this._src = ""; this._t = 0; this._d = 0; this.paused = true; this.ended = false; this._rate = 1;
    this._live = false;
    this.addEventListener = function (n, f) { (L[n] = L[n] || []).push(f); };
    this.removeEventListener = function (n, f) { L[n] = (L[n] || []).filter(function (g) { return g !== f; }); };
    this._fire = function (n) {
      var ev = { type: n, target: self };
      (L[n] || []).forEach(function (f) { try { f.call(self, ev); } catch (e) {} });
      if (typeof self["on" + n] === "function") try { self["on" + n](ev); } catch (e) {}
    };
    players[this.id] = this;
    post({ t: "claim", id: this.id });
  }
  Track.prototype = {
    get src() { return this._src; }, set src(v) { this._src = abs(v); },
    get currentTime() { return this._t; },
    set currentTime(v) { this._t = Math.max(0, +v || 0); if (this._live) post({ t: "audio", op: "seek", id: this.id, at: this._t }); this._fire("seeked"); this._fire("timeupdate"); },
    get duration() { return this._d || NaN; },
    get playbackRate() { return this._rate; },
    set playbackRate(v) { this._rate = +v || 1; if (this._live) post({ t: "audio", op: "rate", id: this.id, rate: this._rate }); },
    play: function () {
      if (this._live) post({ t: "audio", op: "play", id: this.id });
      else post({ t: "audio", op: "list", id: this.id, title: this.meta.title, artist: this.meta.artist,
                  tracks: [{ src: this._src, title: this.meta.title }], at: this._t, rate: this._rate });
      this._live = true; this.paused = false; this.ended = false; this._fire("play");
      return Promise.resolve();
    },
    pause: function () { if (this._live) post({ t: "audio", op: "pause", id: this.id }); this.paused = true; this._fire("pause"); },
    _status: function (s) {
      var was = this.paused, hadD = this._d > 0;
      this._live = true; this._t = s.time || 0; this._d = s.duration || this._d; this.paused = !s.playing;
      if (!hadD && this._d > 0) this._fire("loadedmetadata");
      if (was && !this.paused) this._fire("play");
      if (!was && this.paused) this._fire("pause");
      this._fire("timeupdate");
      if (s.ended && !this.ended) { this.ended = true; this._fire("ended"); }
    }
  };

  // In a browser: the same calls, played here one track after another.
  var web = null;
  function webListen(item) {
    if (!web) { web = new Audio(); web.addEventListener("ended", function () { webGo(web.i + 1); }); }
    web.item = item; webGo(0);
    ["timeupdate", "play", "pause"].forEach(function (n) { web["on" + n] = webStatus; });
  }
  function webGo(i) {
    if (!web.item || i >= web.item.tracks.length) { web.pause(); webStatus(); return; }
    web.i = i; web.src = abs(web.item.tracks[i].src, location.href); web.play().catch(function () {});
  }
  function webStatus() {
    var it = web.item;
    emit(it ? { id: it.id, title: it.title, track: it.tracks[web.i].title, index: web.i, count: it.tracks.length,
                playing: !web.paused, time: web.currentTime || 0, duration: web.duration || 0 } : null);
  }

  window.NPApp = {
    native: !!RN,
    audio: function (meta) { return new Track(meta); },
    listen: function (item) {
      var tracks = item.tracks.map(function (t) { return { src: abs(t.src), title: t.title }; });
      if (RN) post({ t: "audio", op: "list", id: item.id, title: item.title, artist: item.artist, tracks: tracks });
      else webListen({ id: item.id, title: item.title, tracks: tracks });
    },
    toggle: function () {
      if (RN) post({ t: "audio", op: "toggle" });
      else if (web) { if (web.paused) web.play().catch(function () {}); else web.pause(); }
    },
    next: function () { if (RN) post({ t: "audio", op: "next" }); else if (web) webGo(web.i + 1); },
    onStatus: function (f) { statusFns.push(f); if (last !== undefined) f(last); if (RN) post({ t: "status?" }); }
  };
  if (!RN) return;

  // Parent-only API actions from file: pages cannot use browser CORS. Ask here, before even
  // posting a message to native code. No network fallback if the gate or native reply is missing.
  var parentJobs = {}, parentSeq = 0, parentPrefix = Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
  window.NPApp.parentPost = function (url, body) {
    return new Promise(function (resolve, reject) {
      if (typeof window.npGate !== 'function') { reject(new Error('gate_unavailable')); return; }
      var authorize = window.npGate.parent || function (yes, no) { window.npGate('grown', yes, no); };
      authorize(function () {
        var id = parentPrefix + '-' + (++parentSeq);
        var timer = setTimeout(function () { delete parentJobs[id]; reject(new Error('native_request_timeout')); }, 22000);
        parentJobs[id] = function (m) {
          clearTimeout(timer); delete parentJobs[id];
          if (m.error) { reject(new Error('native_request_failed')); return; }
          resolve({ ok: m.status >= 200 && m.status < 300, status: m.status, json: function () { return Promise.resolve(m.data); } });
        };
        post({ t: 'parent-request', id: id, url: url, body: body });
      }, function () { resolve(null); });
    });
  };

  // ---------------------------------------------------------------- messages from the app
  window.__np = function (m) {
    if (!m) return;
    if (m.t === 'parent-result') {
      if (parentJobs[m.id]) parentJobs[m.id](m);
    } else if (m.t === "status") {
      var s = m.s || null;
      if (s && players[s.id]) players[s.id]._status(s);
      emit(s);
    } else if (m.t === "settings") settings(m);
    else if (m.t === "go" && ROOT) location.href = new URL(m.href, ROOT).href;      // e.g. the mini-player → Listen
  };

  // Files saved on the phone: some iOS versions won't fetch() file: addresses, so read them the old way
  // (the builder's engine, Listen's list, the brief).
  var nativeFetch = window.fetch && window.fetch.bind(window);
  var TYPES = { wasm: "application/wasm", json: "application/json", js: "text/javascript", zip: "application/zip" };
  window.fetch = function (input, init) {
    var url = abs(typeof input === "string" ? input : (input && input.url) || "");
    if (!/^file:/.test(url) || (init && init.method && init.method !== "GET")) return nativeFetch(input, init);
    return new Promise(function (ok, fail) {
      var x = new XMLHttpRequest();
      x.open("GET", url);
      x.responseType = "arraybuffer";
      x.onload = function () {
        var ext = url.split(/[?#]/)[0].split(".").pop().toLowerCase();
        ok(new Response(x.response, { status: 200, headers: { "Content-Type": TYPES[ext] || "application/octet-stream" } }));
      };
      x.onerror = function () { fail(new TypeError("Could not read " + url)); };
      x.send();
    });
  };

  document.documentElement.classList.add("np-app");
  var css = document.createElement("style");               // things that only make sense on the website
  css.textContent = "html.np-app #np-tablet-install,html.np-app .install,html.np-app .nb-menu a[href^='podcasts:']," +
    "html.np-app .nb-menu [data-do=copy],html.np-app .nb-menu small:nth-of-type(2){display:none!important}";
  document.head.appendChild(css);

  function hello() {
    var bg = getComputedStyle(document.body).backgroundColor;
    post({ t: "page", url: location.href, title: document.title, bg: bg,
           dark: document.documentElement.getAttribute("data-theme") === "night" });
    if (/\/play\/listen\.html$/.test(location.pathname)) post({ t: "claim", id: "*" });   // Listen shows its own player
    Object.keys(players).forEach(function (id) { post({ t: "claim", id: id }); });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", hello); else hello();
  new MutationObserver(hello).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // ---------------------------------------------------------------- print and share (the gate has already asked)
  window.addEventListener("click", function (e) {
    if (e.defaultPrevented) return;                         // the Parental Gate is asking first
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a) return;
    var u = abs(a.getAttribute("href"));
    if (/\.pdf(\?|#|$)/i.test(u) && a.closest("[data-gate-reason=print]")) {
      e.preventDefault();
      post({ t: "print", url: u, title: a.getAttribute("data-share-title") || document.title });
    }
  });
  // A PDF made on the phone (Design your own): the share sheet, to print, save to Files or send.
  window.addEventListener("click", function (e) {
    if (e.defaultPrevented) return;
    var a = e.target.closest && e.target.closest('a[href^="blob:"]');
    if (!a) return;
    e.preventDefault();
    var name = a.getAttribute("download") || "News Pebbles.pdf";
    fetch(a.href).then(function (r) { return r.blob(); }).then(function (b) {
      var f = new FileReader();
      f.onload = function () { post({ t: "pdfData", name: name, data: String(f.result).split(",")[1] }); };
      f.readAsDataURL(b);
    });
  });
  navigator.share = function (d) {
    d = d || {};
    post({ t: "share", title: d.title || document.title, text: d.text || "", url: d.url ? abs(d.url) : "" });
    return Promise.resolve();
  };
  navigator.canShare = function () { return true; };

  // window.print() (the certificate): the page with its styles and pictures built in, for the print sheet.
  window.print = function () {
    var doc = document.documentElement.cloneNode(true);
    doc.querySelectorAll("script,.tabbar,.nb-mini,.np-gate").forEach(function (n) { n.remove(); });
    var jobs = [];
    doc.querySelectorAll("link[rel=stylesheet]").forEach(function (l) {
      jobs.push(fetch(abs(l.getAttribute("href"))).then(function (r) { return r.text(); }).then(function (t) {
        var s = document.createElement("style"); s.textContent = t; l.replaceWith(s);
      }).catch(function () { l.remove(); }));
    });
    doc.querySelectorAll("img[src]").forEach(function (img) {
      jobs.push(fetch(abs(img.getAttribute("src"))).then(function (r) { return r.blob(); }).then(function (b) {
        return new Promise(function (ok) { var f = new FileReader(); f.onload = function () { img.src = f.result; ok(); }; f.readAsDataURL(b); });
      }).catch(function () {}));
    });
    Promise.all(jobs).then(function () {
      post({ t: "printHtml", html: "<!doctype html>" + doc.outerHTML, landscape: /certificate/.test(location.pathname) });
    });
  };

  // ---------------------------------------------------------------- For parents → This app
  function settings(m) {
    var box = document.getElementById("np-app");
    if (!box) return;
    var on = document.getElementById("np-rem-on"), time = document.getElementById("np-rem-time");
    if (m.reminder) { on.checked = !!m.reminder.on; time.value = m.reminder.time || "07:00"; }
    if (m.offline) {
      document.getElementById("np-off-state").textContent = m.offline.state || "";
      document.getElementById("np-off-what").textContent = m.offline.what || "";
      document.getElementById("np-off-note").textContent = m.offline.note || "";
    }
    box.hidden = false;
  }
  function wireBox() {
    var box = document.getElementById("np-app");
    if (!box) return;
    var on = document.getElementById("np-rem-on"), time = document.getElementById("np-rem-time");
    var save = function () { post({ t: "reminder", on: on.checked, time: time.value || "07:00" }); };
    on.addEventListener("change", save); time.addEventListener("change", function () { if (on.checked) save(); });
    post({ t: "settings?" });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wireBox); else wireBox();
})();
