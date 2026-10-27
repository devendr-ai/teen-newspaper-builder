"""The car-ride brief: a 3-minute, two-host audio version of a paper, on Read & Play.

A paper opts in with `site: {audio_brief: true}` in its edition.yaml (The Breakfast Table). Its issues then
carry `play.brief` (online only, never printed): a short script for two hosts, Maya and Sam, written only
from facts already in that issue. `check()` enforces that; `ygc.narration` turns the newest scripts into
audio with two Kokoro voices, and writes a podcast feed so families can play it in the car.
"""
import datetime as dt
import json
import re
from xml.sax.saxutils import escape

HOSTS = {"maya": {"name": "Maya", "voice": "af_heart"},       # explains; the voice Read & Play already uses
         "sam": {"name": "Sam", "voice": "am_michael"}}       # asks what a curious reader would ask
WORDS = (300, 600)              # about 2 to 4 minutes at a calm pace
LINE_WORDS = 70
CHAPTERS = (2, 6)
CHAPTER_CHARS = 22
NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def wants(ed):
    return bool((ed.get("site") or {}).get("audio_brief"))


def skeleton():
    return {"lines": [{"who": "maya", "text": "", "chapter": ""}, {"who": "sam", "text": ""},
                      {"who": "maya", "text": ""}]}


PROMPT = ("**Car-ride brief (online only, read aloud).** Fill `play.brief.lines` with a script of about three "
          f"minutes ({WORDS[0]} to {WORDS[1]} words) for two hosts who talk the family through this issue on the "
          "way to school. `who` is `maya` (who explains) or `sam` (who asks what a curious nine-year-old would "
          "ask, like \"Wait, why does that change prices here?\"); `text` is what they say, one to three short "
          f"sentences (at most {LINE_WORDS} words). Open with a hello naming the paper and the day, cover the "
          "lead and two or three other stories, then a one-line round-up, and end with the issue's first TALK "
          "ABOUT IT question for the car. Put `chapter` (a short label of at most "
          f"{CHAPTER_CHARS} characters, like \"Riyadh & oil\") on the first line of each story, "
          f"{CHAPTERS[0]} to {CHAPTERS[1]} in all. Use only facts already in this issue, with numbers written as "
          "the issue writes them; no new facts, no jokes about the news, nothing scary, and no made-up banter.\n")


def _numbers(text):
    return [float(n.replace(",", "")) for n in NUM.findall(str(text))]


def _strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in ("sources", "url"):
                yield from _strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)


def check(issue, brief, r):
    """play.brief: hosts, length, chapters, and no number the issue doesn't give."""
    lines = brief.get("lines") if isinstance(brief, dict) else None
    if not isinstance(lines, list) or len(lines) < 6:
        r.err("play.brief.lines: a script of at least 6 lines")
        return
    words, speakers, chapters = 0, set(), []
    for i, ln in enumerate(lines):
        at = f"play.brief.lines[{i}]"
        if not isinstance(ln, dict):
            r.err(f"{at} must be {{who, text}}")
            continue
        who, text = ln.get("who"), str(ln.get("text", "")).strip()
        if who not in HOSTS:
            r.err(f"{at}.who must be one of {', '.join(HOSTS)}")
        speakers.add(who)
        n = len(text.split())
        if not n:
            r.err(f"{at}.text is empty")
        elif n > LINE_WORDS:
            r.err(f"{at}.text: {n} words; keep each turn to {LINE_WORDS} or fewer")
        if re.search(r"https?://|www\.", text):
            r.err(f"{at}.text: no web addresses in speech")
        words += n
        ch = str(ln.get("chapter") or "").strip()
        if ch:
            if len(ch) > CHAPTER_CHARS:
                r.err(f"{at}.chapter: at most {CHAPTER_CHARS} characters")
            chapters.append(ch)
    if not WORDS[0] <= words <= WORDS[1]:
        r.err(f"play.brief: {words} words; write {WORDS[0]} to {WORDS[1]} (about three minutes)")
    if not set(HOSTS) <= speakers:
        r.err("play.brief: both hosts, maya and sam, should speak")
    if not CHAPTERS[0] <= len(chapters) <= CHAPTERS[1]:
        r.err(f"play.brief: mark {CHAPTERS[0]} to {CHAPTERS[1]} chapters (`chapter` on a story's first line)")
    elif len(set(c.lower() for c in chapters)) != len(chapters):
        r.err("play.brief: chapter labels must differ")
    source = " ".join(_strings(issue.get("blocks", {})))
    have = _numbers(source)
    try:                                                       # "Monday, 26 October" in the hello
        d = dt.date.fromisoformat(str(issue.get("date")))
        have += [d.day, d.year, d.month]
    except ValueError:
        pass
    for i, ln in enumerate(lines):
        if not isinstance(ln, dict):
            continue
        for n in _numbers(ln.get("text", "")):
            if not any(abs(n - m) <= max(0.1 * abs(m), 0.5) for m in have):
                r.err(f"play.brief.lines[{i}]: the number {n:g} isn't in this issue; use only its facts")


def data(ed, issue, date):
    """The script as Read & Play serves it (play/briefs/<date>.json), before audio is made."""
    lines = [{"who": ln["who"], "name": HOSTS[ln["who"]]["name"], "text": str(ln["text"]).strip(),
              **({"chapter": str(ln["chapter"]).strip()} if str(ln.get("chapter") or "").strip() else {})}
             for ln in (issue.get("play") or {}).get("brief", {}).get("lines", [])
             if isinstance(ln, dict) and ln.get("who") in HOSTS and str(ln.get("text", "")).strip()]
    day = dt.date.fromisoformat(date)
    return {"paper": ed["id"], "name": ed["name"], "date": date, "day": f"{day:%a} {day.day} {day:%b}",
            "title": f"{ed['name']} Brief, {day.day} {day:%B %Y}",
            "chapters": [ln["chapter"] for ln in lines if ln.get("chapter")], "lines": lines}


def feed(cfg, episodes):
    """A podcast feed (RSS 2.0 with iTunes tags) for the briefs that have audio, newest first."""
    base = (cfg.get("base_url") or "").rstrip("/") + "/"
    title = f"{cfg.get('title', 'News Pebbles')}: The Breakfast Table Brief"
    items = []
    for e in episodes:
        when = dt.datetime.fromisoformat(e["date"] + "T06:00:00+00:00")
        url = base + "play/" + e["audio"]
        summary = "Today: " + ", ".join(e.get("chapters") or []) + "."
        items.append(f"""<item><title>{escape(e['day'] + ' · ' + ', '.join((e.get('chapters') or [])[:3]))}</title>
<description>{escape(summary)}</description><pubDate>{when:%a, %d %b %Y %H:%M:%S +0000}</pubDate>
<guid isPermaLink="false">{escape(e['paper'] + '-brief-' + e['date'])}</guid>
<enclosure url="{escape(url)}" length="{int(e.get('bytes', 0))}" type="audio/mpeg"/>
<itunes:duration>{int(round(e.get('duration', 0)))}</itunes:duration><itunes:explicit>false</itunes:explicit></item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel><title>{escape(title)}</title><link>{escape(base + 'play/')}</link><language>en</language>
<description>{escape("Three minutes of the day's news for the ride to school, from The Breakfast Table. Two AI voices, Maya and Sam, talk through the paper using only its checked facts.")}</description>
<itunes:author>{escape(cfg.get('title', 'News Pebbles'))}</itunes:author><itunes:explicit>false</itunes:explicit>
<itunes:category text="Kids &amp; Family"/><itunes:image href="{escape(base + 'play/icon-512.png')}"/>
{''.join(items)}
</channel></rss>
"""


def write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


# Read & Play's player: one compact row at the top of Today's papers (web and phone).
CSS = r"""
.brief{position:relative;margin:4px 0 16px}
.brief .nb{position:relative;display:flex;align-items:center;gap:14px;background:var(--card);border:1.5px solid var(--teal);
  border-radius:14px;padding:10px 14px 14px 10px;overflow:hidden}
.nb-art{width:52px;height:52px;flex:none;border-radius:11px;background:linear-gradient(135deg,#00727E,#173438);display:grid;place-items:center;position:relative}
.nb-art img{width:36px;height:36px}
.nb-art i{position:absolute;right:-5px;bottom:-5px;background:var(--coral);border-radius:50%;width:20px;height:20px;display:grid;place-items:center;
  font-size:10px;font-style:normal;border:2px solid var(--card)}
.nb-tx{flex:1;min-width:0}
.nb-k{font:800 .68rem/1.3 var(--text);letter-spacing:.07em;color:var(--teal);text-transform:uppercase;white-space:nowrap}
.nb-h{font:800 1.02rem/1.25 var(--display);color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin:1px 0}
.nb-s{font:.82rem/1.3 var(--text);color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nb .m{display:none}
.nb-ch{display:flex;gap:6px;flex:none}
.nb-ch[hidden]{display:none}
.nb-ch button,.nb-menu .jump button{font:700 .72rem var(--text);background:color-mix(in srgb,var(--teal) 14%,var(--card));color:var(--ink);
  border:0;border-radius:999px;padding:5px 10px;cursor:pointer}
.nb-ch button[aria-current="true"]{background:var(--teal);color:#fff}
.nb-t{font:700 .78rem var(--text);color:var(--muted);white-space:nowrap;flex:none;font-variant-numeric:tabular-nums}
.nb-play{width:42px;height:42px;flex:none;border-radius:50%;background:var(--ink);color:var(--card);border:0;display:grid;place-items:center;cursor:pointer;padding:0}
.nb-play svg{width:18px;height:18px;fill:currentColor}
.nb-more{width:34px;height:34px;flex:none;border-radius:9px;border:1.5px solid var(--line);background:none;color:var(--ink);font:800 16px/1 var(--text);cursor:pointer}
.nb-bar{position:absolute;left:0;right:0;bottom:0;height:5px;background:color-mix(in srgb,var(--teal) 16%,var(--card));cursor:pointer}
.nb-bar b{display:block;height:100%;width:0;background:var(--teal)}
.nb-bar i{position:absolute;top:0;width:2px;height:100%;background:var(--card)}
.nb-menu{position:absolute;z-index:30;right:0;top:calc(100% + 6px);background:var(--card);border:1px solid var(--line);border-radius:12px;
  box-shadow:0 10px 26px rgba(0,0,0,.16);padding:6px;min-width:250px;max-width:calc(100vw - 32px)}
.nb-menu[hidden],.nb-sheet[hidden],.nb-mini[hidden]{display:none}
.nb-menu>button,.nb-menu>a{display:block;width:100%;text-align:left;font:700 .92rem var(--text);color:var(--ink);background:none;border:0;
  padding:10px 12px;border-radius:8px;text-decoration:none;cursor:pointer}
.nb-menu>button:hover,.nb-menu>a:hover,.nb-menu>button:focus-visible,.nb-menu>a:focus-visible{background:color-mix(in srgb,var(--teal) 12%,var(--card))}
.nb-menu small{display:block;font:700 .7rem var(--text);color:var(--muted);padding:8px 12px 2px;text-transform:uppercase;letter-spacing:.06em}
.nb-menu .jump{display:flex;flex-wrap:wrap;gap:6px;padding:4px 12px 8px}
.nb-menu p{font:.78rem/1.4 var(--text);color:var(--muted);margin:6px 12px 4px}
.nb-sheet{position:fixed;z-index:40;left:50%;transform:translateX(-50%);bottom:0;width:min(640px,100%);max-height:62vh;overflow:auto;
  background:var(--card);border-radius:20px 20px 0 0;box-shadow:0 -10px 30px rgba(0,0,0,.25);padding:12px 18px calc(110px + env(safe-area-inset-bottom,0px))}
.nb-sheet header{display:flex;align-items:center;justify-content:space-between;gap:8px;position:sticky;top:-12px;background:var(--card);padding:6px 0 8px}
.nb-sheet h3{font:800 1rem var(--display);margin:0;color:var(--ink)}
.nb-sheet header button{border:1.5px solid var(--line);background:none;border-radius:8px;padding:5px 10px;font:700 .82rem var(--text);color:var(--ink);cursor:pointer}
.nb-line{display:grid;grid-template-columns:48px 1fr;gap:8px;margin:0 0 10px;font:1rem/1.5 var(--text);color:var(--muted);cursor:pointer}
.nb-line b{font:800 .7rem var(--text);text-transform:uppercase;letter-spacing:.06em;padding-top:5px}
.nb-line.maya b{color:var(--teal)}.nb-line.sam b{color:#B8336A}
.nb-line.now{color:var(--ink)}.nb-line.now span{background:color-mix(in srgb,var(--teal) 16%,var(--card));border-radius:6px;padding:1px 4px}
.nb-line em{display:block;font:800 .7rem var(--text);font-style:normal;color:var(--teal);text-transform:uppercase;letter-spacing:.06em;margin-bottom:2px}
.nb-mini{position:fixed;z-index:35;right:16px;bottom:16px;width:min(360px,calc(100vw - 20px));background:#1E2A32;color:#F4F1EA;border-radius:14px;
  padding:10px 12px 12px;display:flex;align-items:center;gap:10px;box-shadow:0 8px 24px rgba(0,0,0,.35);overflow:hidden}
.nb-mini img{width:38px;height:38px;border-radius:8px;background:#00727E;padding:4px;box-sizing:border-box}
.nb-mini button.go{flex:1;min-width:0;text-align:left;background:none;border:0;color:inherit;cursor:pointer;padding:0}
.nb-mini b{display:block;font:800 .86rem var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nb-mini small{font:600 .74rem var(--text);opacity:.82;font-variant-numeric:tabular-nums}
.nb-mini .nb-play{background:#F4F1EA;color:#1E2A32;width:38px;height:38px}
.nb-mini u{position:absolute;left:0;right:0;bottom:0;height:3px;background:rgba(255,255,255,.18)}.nb-mini u b{height:3px;width:0;background:#41B6C1}
@media (max-width:699px){
  .brief .nb{gap:11px;padding:9px 10px 12px 9px}.nb-art{width:46px;height:46px}.nb-art img{width:32px;height:32px}
  .nb .d,.nb-ch,.nb-t{display:none!important}.nb .m{display:inline}.nb-h{font-size:.98rem}.nb-play{width:40px;height:40px}
  .nb-mini{left:10px;right:10px;width:auto;bottom:calc(84px + env(safe-area-inset-bottom,0px))}
}
@media (prefers-reduced-motion:reduce){.nb-bar b,.nb-mini u b{transition:none}}
@media print{.brief,.nb-mini,.nb-sheet{display:none!important}}
"""

JS = r"""
(function () {
  const box = document.getElementById("brief");
  if (!box) return;
  const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const clock = (s) => { s = Math.max(0, Math.round(s || 0)); return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  const keep = { get(k, d) { try { const v = localStorage.getItem("rp-brief-" + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
                 set(k, v) { try { localStorage.setItem("rp-brief-" + k, JSON.stringify(v)); } catch (e) {} } };
  const count = (p, t) => { if (window.npCount) window.npCount(p, t, true); };
  const PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l13-7.5z"/></svg>';
  const PAUSE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 4h4.5v16H6zm7.5 0H18v16h-4.5z"/></svg>';
  fetch(box.dataset.src, { cache: "no-cache" }).then((r) => r.ok ? r.json() : null).then((b) => { if (b && b.audio) start(b); }).catch(() => {});

  function start(b) {
    const marks = b.marks || [], lines = b.lines || [], dur = b.duration || 0, mins = Math.max(1, Math.round(dur / 60));
    const day = new Date(b.date + "T12:00:00"), today = new Date();
    const fresh = (today - day) / 864e5 < 1.6;
    const title = fresh ? "Today's news, talked through by two hosts" : "The news from " + b.day + ", talked through";
    const short = b.name.replace(/^The /, "");
    const topics = (b.chapters || []).slice(0, 3).join(", ");
    const feed = new URL("podcast.xml", location.href).href;
    box.innerHTML = `<div class="nb"><div class="nb-art" aria-hidden="true"><img src="owl.svg" alt=""><i>🎧</i></div>
<div class="nb-tx"><div class="nb-k">Car-ride brief · ${mins} min</div>
<div class="nb-h"><span class="d">${esc(title)}</span><span class="m">${fresh ? "Today's news, aloud" : esc("News from " + b.day)}</span></div>
<div class="nb-s"><span class="d">${esc(b.name + " · " + b.day + (topics ? " · " + topics : ""))}</span><span class="m">${esc(short + " · " + b.day.replace(/^\w+ /, ""))}</span></div></div>
<div class="nb-ch" hidden>${marks.map((m, i) => `<button type="button" data-i="${i}">${esc(m.title)}</button>`).join("")}</div>
<span class="nb-t">${clock(dur)}</span>
<button type="button" class="nb-play" aria-label="Play the car-ride brief">${PLAY}</button>
<button type="button" class="nb-more" aria-haspopup="true" aria-expanded="false" aria-label="More: read along, speed, listen in the car">⋯</button>
<div class="nb-bar" aria-hidden="true"><b></b>${marks.slice(1).map((m) => `<i style="left:${(100 * m.start / dur).toFixed(2)}%"></i>`).join("")}</div></div>
<div class="nb-menu" role="menu" hidden>
<button type="button" role="menuitem" data-do="read">Read along</button>
<small>Jump to a story</small><div class="jump">${marks.map((m, i) => `<button type="button" data-i="${i}">${esc(m.title)}</button>`).join("")}</div>
<button type="button" role="menuitem" data-do="speed">Speed: 1×</button>
<small>Listen in the car</small>
<a role="menuitem" href="${esc(feed.replace(/^https?:/, "podcasts:"))}">Add to Apple Podcasts</a>
<button type="button" role="menuitem" data-do="copy">Copy podcast link (for any podcast app)</button>
<p>Maya and Sam are AI voices. Everything they say comes from ${esc(b.name)} for ${esc(b.day)}.</p></div>`;
    const sheet = document.createElement("div");
    sheet.className = "nb-sheet"; sheet.hidden = true; sheet.setAttribute("role", "dialog"); sheet.setAttribute("aria-label", "Read along");
    sheet.innerHTML = `<header><h3>Read along · ${esc(b.name)} Brief</h3><button type="button" data-do="close">Close</button></header>` +
      lines.map((l, i) => `<div class="nb-line ${esc(l.who)}" data-i="${i}"><b>${esc(l.name)}</b><div>${l.chapter ? `<em>${esc(l.chapter)}</em>` : ""}<span>${esc(l.text)}</span></div></div>`).join("");
    const mini = document.createElement("div");
    mini.className = "nb-mini"; mini.hidden = true;
    mini.innerHTML = `<img src="owl.svg" alt=""><button type="button" class="go" aria-label="Back to the car-ride brief"><b>${esc(short)} Brief</b><small></small></button>
<button type="button" class="nb-play" aria-label="Pause">${PAUSE}</button><u><b></b></u>`;
    document.body.append(sheet, mini);
    box.hidden = false;

    const audio = window.NPApp && NPApp.native            // the app: the phone's own player (lock screen, screen off)
      ? NPApp.audio({ id: "brief-" + b.date, title: "Car-ride brief · " + b.day, artist: b.name }) : new Audio();
    audio.preload = "none";
    audio.src = b.audio;
    const card = $(".nb", box), menu = $(".nb-menu", box), more = $(".nb-more", box), chips = $(".nb-ch", box);
    const plays = [$(".nb-play", box), $(".nb-play", mini)];
    const speeds = [1, 1.25, 0.85];
    let speed = keep.get("speed", 1), started = false, finished = false, inView = true;
    const chapterAt = (t) => { let i = -1; marks.forEach((m, k) => { if (t >= m.start - 0.05) i = k; }); return i; };
    const lineAt = (t) => { let i = 0; lines.forEach((l, k) => { if (t >= (l.start || 0) - 0.05) i = k; }); return i; };
    function paint() {
      const t = audio.currentTime || 0, on = !audio.paused, c = chapterAt(t), pct = dur ? Math.min(100, 100 * t / dur) : 0;
      plays.forEach((p) => { p.innerHTML = on ? PAUSE : PLAY; p.setAttribute("aria-label", on ? "Pause the car-ride brief" : "Play the car-ride brief"); });
      const live = on || t > 0;
      chips.hidden = !live;
      $$("button", chips).forEach((x, i) => x.setAttribute("aria-current", String(i === c)));
      const now = c >= 0 ? marks[c].title : "Hello";
      $(".nb-h .d", box).textContent = live ? "Now: " + now : title;
      $(".nb-h .m", box).textContent = live ? "Now: " + now : (fresh ? "Today's news, aloud" : "News from " + b.day);
      $(".nb-s .m", box).textContent = live ? clock(t) + " of " + clock(dur) + " · " + short : short + " · " + b.day.replace(/^\w+ /, "");
      $(".nb-t", box).textContent = live ? clock(t) + " / " + clock(dur) : clock(dur);
      $(".nb-bar b", box).style.width = pct + "%";
      $("u b", mini).style.width = pct + "%";
      $("small", mini).textContent = (c >= 0 ? marks[c].title + " · " : "") + clock(t) + " / " + clock(dur);
      mini.hidden = !(live && !inView && !audio.ended);
      if (!sheet.hidden) {
        const li = lineAt(t);
        $$(".nb-line", sheet).forEach((x, i) => x.classList.toggle("now", i === li));
      }
    }
    function seek(t) { audio.currentTime = Math.max(0, Math.min(dur - 0.2, t)); paint(); if (audio.paused) toggle(); }
    function toggle() {
      if (audio.paused) {
        if (!started) { started = true; count("brief/started", "Car-ride brief started: " + b.date); }
        const at = keep.get("at-" + b.date, 0);
        if (!audio.currentTime && at > 5 && at < dur - 10) audio.currentTime = at;
        audio.playbackRate = speed;
        audio.play().catch(() => {});
      } else audio.pause();
    }
    plays.forEach((p) => p.addEventListener("click", toggle));
    chips.addEventListener("click", (e) => { const x = e.target.closest("button"); if (x) seek(marks[+x.dataset.i].start); });
    $(".nb-bar", box).addEventListener("click", (e) => { const r = e.currentTarget.getBoundingClientRect(); seek(dur * (e.clientX - r.left) / r.width); });
    more.addEventListener("click", () => { menu.hidden = !menu.hidden; more.setAttribute("aria-expanded", String(!menu.hidden)); });
    document.addEventListener("click", (e) => { if (!menu.hidden && !menu.contains(e.target) && e.target !== more) { menu.hidden = true; more.setAttribute("aria-expanded", "false"); } });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") { if (!menu.hidden) { menu.hidden = true; more.focus(); } else if (!sheet.hidden) { sheet.hidden = true; } } });
    const speedBtn = $('[data-do="speed"]', menu);
    const showSpeed = () => { speedBtn.textContent = "Speed: " + speed + "×"; };
    showSpeed();
    menu.addEventListener("click", (e) => {
      const x = e.target.closest("button,a"); if (!x) return;
      if (x.dataset.i !== undefined) { seek(marks[+x.dataset.i].start); menu.hidden = true; }
      else if (x.dataset.do === "read") { sheet.hidden = false; menu.hidden = true; paint(); const n = $(".nb-line.now", sheet); if (n) n.scrollIntoView({ block: "center" }); $("header button", sheet).focus(); }
      else if (x.dataset.do === "speed") { speed = speeds[(speeds.indexOf(speed) + 1) % speeds.length]; audio.playbackRate = speed; keep.set("speed", speed); showSpeed(); }
      else if (x.dataset.do === "copy") {
        const done = () => { x.textContent = "Copied. Paste it into your podcast app."; setTimeout(() => { x.textContent = "Copy podcast link (for any podcast app)"; }, 2600); };
        if (navigator.clipboard) navigator.clipboard.writeText(feed).then(done, () => prompt("Podcast link:", feed)); else prompt("Podcast link:", feed);
      }
    });
    sheet.addEventListener("click", (e) => {
      if (e.target.closest('[data-do="close"]')) { sheet.hidden = true; more.focus(); return; }
      const l = e.target.closest(".nb-line"); if (l) seek(lines[+l.dataset.i].start || 0);
    });
    $(".go", mini).addEventListener("click", () => card.scrollIntoView({ behavior: "smooth", block: "center" }));
    if ("IntersectionObserver" in window) {         // hidden under the sticky header counts as out of view
      const top = ($("header.bar") || { offsetHeight: 0 }).offsetHeight;
      new IntersectionObserver((es) => { inView = es[0].isIntersecting; paint(); }, { rootMargin: `-${top}px 0px 0px 0px` }).observe(card);
    }
    let saved = 0;
    audio.addEventListener("timeupdate", () => {
      paint();
      if (Math.abs(audio.currentTime - saved) > 4) { saved = audio.currentTime; keep.set("at-" + b.date, saved); }
      if (!finished && dur && audio.currentTime > dur * 0.9) { finished = true; count("brief/finished", "Car-ride brief finished: " + b.date); }
    });
    ["play", "pause", "seeked", "loadedmetadata"].forEach((ev) => audio.addEventListener(ev, paint));
    audio.addEventListener("ended", () => { keep.set("at-" + b.date, 0); paint(); });
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({ title: b.name + " Brief · " + b.day, artist: "News Pebbles", album: "Car-ride brief",
          artwork: [{ src: new URL("icon-512.png", location.href).href, sizes: "512x512", type: "image/png" }] });
        const ms = navigator.mediaSession, at = () => chapterAt(audio.currentTime);
        ms.setActionHandler("play", () => { if (audio.paused) toggle(); });
        ms.setActionHandler("pause", () => audio.pause());
        ms.setActionHandler("seekbackward", () => seek(audio.currentTime - 10));
        ms.setActionHandler("seekforward", () => seek(audio.currentTime + 10));
        ms.setActionHandler("previoustrack", () => seek(marks[Math.max(0, at() - (audio.currentTime - (marks[at()] || { start: 0 }).start < 3 ? 1 : 0))]?.start || 0));
        ms.setActionHandler("nexttrack", () => { const n = marks[at() + 1]; if (n) seek(n.start); });
      } catch (e) { /* lock-screen controls are optional */ }
    }
    paint();
  }
})();
"""
