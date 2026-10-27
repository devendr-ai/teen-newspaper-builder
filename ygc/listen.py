"""The app's Listen tab: the car-ride briefs and today's papers read aloud, saved on the phone.

Only the app build (`ygc site --kids`) has the page (play/listen.html). Its list, play/listen.json, is
written by the narration step (ygc.narration), which makes the recordings:

    {"briefs": [{"date", "name", "chapters", "audio", "duration"}],             newest first
     "papers": [{"eid", "name", "band", "date", "href",
                 "tracks": [{"title", "src", "duration"}]}]}               each paper's newest issue

Paths are relative to play/. In the app, playing goes to the phone's own player (app.js, NPApp.listen),
so it carries on with the screen locked and shows on the lock screen; in a browser the page plays the
tracks one after another itself.
"""
import html
import json
import re
from pathlib import Path

E = html.escape
BRIEFS = 7                                      # how many recent briefs the list offers

CARD = re.compile(r'<section class="card[ "][^>]*>')
H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.S)
TITLE = re.compile(r"<title>(.*?)</title>", re.S)


def _text(fragment):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def card_titles(source):
    """Each story card's heading, in page order (the order narration numbers them)."""
    starts = [m.start() for m in CARD.finditer(source)] + [len(source)]
    out = []
    for a, b in zip(starts, starts[1:]):
        h = H2.search(source, a, b)
        out.append(_text(h.group(1)) if h else "")
    return out


def paper(page, source, manifest, band=""):
    """A paper's entry from its Read & Play page and the narration manifest written into it."""
    titles = card_titles(source)
    name = TITLE.search(source)
    name = _text(name.group(1)).split(",")[0] if name else page.parent.name
    tracks = []
    for card in sorted(manifest, key=int):
        rec = manifest[card].get("original") or manifest[card].get("easy")
        if not rec or not rec.get("segments"):
            continue
        title = titles[int(card)] if int(card) < len(titles) else ""
        tracks.append({"title": title.capitalize() if title.isupper() else title or f"Story {int(card) + 1}",
                       "src": "audio/" + rec["src"].rsplit("/", 1)[-1],
                       "duration": round(rec["segments"][-1]["end"], 1)})
    return {"eid": page.parent.name, "name": name, "band": band, "date": page.stem,
            "href": f"{page.parent.name}/{page.name}", "tracks": tracks}


def write_json(site, papers):
    """play/listen.json: the recorded briefs (from play/briefs/) and the papers narration just read."""
    play = Path(site) / "play"
    briefs = []
    for f in sorted((play / "briefs").glob("20*.json"), reverse=True):
        b = json.loads(f.read_text(encoding="utf-8"))
        if b.get("audio"):
            briefs.append({"date": f.stem, "name": b.get("name", ""), "chapters": b.get("chapters", []),
                           "audio": b["audio"], "duration": b.get("duration", 0)})
        if len(briefs) == BRIEFS:
            break
    papers = sorted((p for p in papers if p["tracks"]), key=lambda p: (p["date"], p["name"]), reverse=True)
    (play / "listen.json").write_text(json.dumps({"briefs": briefs, "papers": papers}, ensure_ascii=False,
                                                 separators=(",", ":")), encoding="utf-8")
    return len(briefs), len(papers)


def page(cfg):
    """play/listen.html (app build only)."""
    from . import play
    body = f'''<header class="bar"><h1 class="lp-h">Listen</h1></header>
<main class="lp front"><p class="how">Everything here is saved on this phone, for the car, the bus or a plane.</p>
<section aria-labelledby="lp-b"><h2 id="lp-b">🚗 Car-ride briefs</h2><p class="lp-sub">Maya and Sam talk through the day's news.</p><div class="lp-list" id="lp-briefs"></div></section>
<section aria-labelledby="lp-p"><h2 id="lp-p">📰 Today's papers, read aloud</h2><div class="lp-list" id="lp-papers"></div></section>
<p class="lp-empty" id="lp-empty" hidden>The recordings arrive with each morning's papers. Check back soon.</p>
<div class="lp-now" id="lp-now" hidden><button type="button" class="lp-toggle" aria-label="Pause"></button>
<div class="lp-what"><b></b><span></span></div><button type="button" class="lp-next" aria-label="Next story">⏭</button>
<div class="lp-bar"><i></i></div></div></main>
<style>{CSS}</style><script>{JS}</script>'''
    return play.shell(cfg, f"Listen · {cfg['title']}", body, root="../", here="listen")


CSS = r"""
.lp{max-width:720px;margin:0 auto;padding:6px 16px 120px}.lp-h{font-size:30px}
.lp .how{color:var(--muted);margin:6px 0 4px;font-size:17px}
.lp h2{font-size:21px;margin:22px 0 2px}.lp-sub{color:var(--muted);font-size:15px;margin:0 0 4px}
.lp-row{display:flex;align-items:center;gap:12px;width:100%;padding:12px 4px;border:0;border-bottom:1px solid var(--line);
 background:none;text-align:left;cursor:pointer;color:var(--ink);font:inherit;min-height:72px}
.lp-art{width:56px;height:56px;border-radius:12px;flex:none;display:grid;place-items:center;color:#fff;font:800 15px/1 var(--display);text-align:center}
.lp-tx{flex:1;min-width:0}.lp-tx b{display:block;font-size:16px;line-height:1.25}.lp-tx span{font-size:14px;color:var(--muted)}
.lp-ic{flex:none;width:40px;height:40px;border-radius:50%;border:2px solid var(--line);display:grid;place-items:center;font-size:15px;color:var(--teal)}
.lp-row[aria-current="true"] .lp-ic{background:var(--teal);border-color:var(--teal);color:#fff}
.lp-row[aria-current="true"] .lp-tx b{color:var(--teal)}
.lp-empty{color:var(--muted)}
.lp-now{position:fixed;left:10px;right:10px;bottom:calc(84px + env(safe-area-inset-bottom,0px));z-index:7;background:var(--ink);color:var(--bg);
 border-radius:18px;padding:10px 12px 14px;display:flex;align-items:center;gap:12px;box-shadow:0 10px 24px rgba(0,0,0,.25)}
.lp-now button{flex:none;width:44px;height:44px;border-radius:50%;border:0;background:var(--teal);color:#fff;font-size:17px;cursor:pointer}
.lp-now .lp-next{background:none;color:var(--bg)}.lp-what{flex:1;min-width:0}
.lp-what b,.lp-what span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.lp-what span{font-size:13px;opacity:.75}
.lp-bar{position:absolute;left:14px;right:14px;bottom:6px;height:4px;border-radius:2px;background:rgba(255,255,255,.25)}
.lp-bar i{display:block;height:100%;width:0;border-radius:2px;background:#fff}
@media(min-width:900px){.lp-now{left:auto;right:24px;width:420px;bottom:24px}}
"""

JS = r"""
(function () {
  const $ = (s, r) => (r || document).querySelector(s);
  const COLORS = ["#E2584D", "#2E7D4F", "#B7791F", "#5B5BD6", "#007C89"];
  const mins = (s) => Math.max(1, Math.round((s || 0) / 60)) + " min";
  const day = (d) => { const t = new Date(d + "T12:00:00"); return [t.getDate(), t.toLocaleString("en-GB", { month: "short" })]; };
  const initials = (n) => n.replace(/^The /, "").split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  let band = ""; try { band = JSON.parse(localStorage.getItem("rp-band") || '""') || ""; } catch (e) {}
  let current = null;
  function row(list, item, art, title, meta) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "lp-row"; b.dataset.id = item.id;
    b.innerHTML = '<span class="lp-art"></span><span class="lp-tx"><b></b><span></span></span><span class="lp-ic" aria-hidden="true">▶</span>';
    const a = $(".lp-art", b); a.style.background = art.color; a.innerHTML = art.html;
    $(".lp-tx b", b).textContent = title; $(".lp-tx span", b).textContent = meta;
    b.setAttribute("aria-label", "Play " + title + ", " + meta);
    b.addEventListener("click", () => {
      if (current && current.id === item.id) { NPApp.toggle(); return; }
      NPApp.listen(item);
    });
    list.appendChild(b);
  }
  fetch("listen.json", { cache: "no-store" }).then((r) => r.json()).then((d) => {
    const briefs = d.briefs || [], papers = (d.papers || []).slice();
    if (band) papers.sort((x, y) => (y.band === band) - (x.band === band));
    briefs.forEach((b, i) => {
      const [n, m] = day(b.date);
      row($("#lp-briefs"), { id: "brief-" + b.date, title: "Car-ride brief · " + n + " " + m, artist: b.name || "News Pebbles",
        tracks: [{ src: b.audio, title: (b.chapters || []).slice(0, 3).join(" · ") || "Car-ride brief" }], chapters: b.chapters },
        { color: i ? "#4C8A96" : "#007C89", html: n + "<br>" + m }, (b.chapters || []).slice(0, 3).join(" · ") || "Car-ride brief",
        "Maya & Sam · " + mins(b.duration));
    });
    papers.forEach((p, i) => {
      const [n, m] = day(p.date), total = p.tracks.reduce((t, x) => t + (x.duration || 0), 0);
      row($("#lp-papers"), { id: "paper-" + p.eid + "-" + p.date, title: p.name, artist: n + " " + m + " · News Pebbles",
        tracks: p.tracks.map((t) => ({ src: t.src, title: t.title })) },
        { color: COLORS[i % COLORS.length], html: initials(p.name) }, p.name,
        n + " " + m + " · " + p.tracks.length + (p.tracks.length === 1 ? " story · " : " stories · ") + mins(total));
    });
    $("#lp-b").parentElement.hidden = !briefs.length;
    $("#lp-p").parentElement.hidden = !papers.length;
    $("#lp-empty").hidden = !!(briefs.length || papers.length);
  }).catch(() => { $("#lp-empty").hidden = false; });
  const now = $("#lp-now");
  $(".lp-toggle", now).addEventListener("click", () => NPApp.toggle());
  $(".lp-next", now).addEventListener("click", () => NPApp.next());
  NPApp.onStatus((s) => {
    current = s && s.id ? s : null;
    document.querySelectorAll(".lp-row").forEach((r) => {
      const on = !!current && r.dataset.id === current.id;
      r.setAttribute("aria-current", String(on));
      $(".lp-ic", r).textContent = on && current.playing ? "❚❚" : "▶";
    });
    now.hidden = !current;
    if (!current) return;
    $("b", now).textContent = current.title || "";
    $("span", now).textContent = current.track || "";
    $(".lp-toggle", now).textContent = current.playing ? "❚❚" : "▶";
    $(".lp-toggle", now).setAttribute("aria-label", current.playing ? "Pause" : "Play");
    $(".lp-next", now).hidden = !(current.count > 1);
    $(".lp-bar i", now).style.width = (current.duration ? Math.min(100, 100 * current.time / current.duration) : 0) + "%";
  });
})();
"""
