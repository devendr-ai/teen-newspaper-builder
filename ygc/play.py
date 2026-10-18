"""Read & Play: the children's side of the website.

The newsstand is for grown-ups (choose, download, print). Read & Play is for the
child, on a tablet or phone: each recent issue as a web page, one story per
screen for younger readers, read aloud with the sentence lit up, new words to
tap, bigger text and a night mode, and a game made from the issue. Built from
the same issue files as the PDFs, by `python -m ygc site`. Nothing is tracked:
settings and stars stay in the browser.
"""
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil

from . import brand, edition, scenes, threads, world
from .chat import sentences

E = html.escape
BANDS = ["Ages 6–8", "Ages 9–11", "Ages 12–14", "Ages 15+"]
CARD_BANDS = {"Ages 6–8", "Ages 9–11"}          # one story per screen
SKIP = {"quote", "watchlist", "sign_off"}       # print-only sections

# Each section gets an icon and a colour, from the words in its kicker (or its id).
DESKS = [
    (("top story", "lead"), "⭐", "coral"),
    (("space", "astronomy", "rocket", "moon", "planet"), "🔭", "violet"),
    (("science", "tech", "ai", "robot", "invent", "physics", "computer"), "🔬", "violet"),
    (("climate", "environment", "weather", "nature", "animal", "wildlife", "ocean"), "🌱", "leaf"),
    (("health", "medicine", "doctor"), "🩺", "rose"),
    (("sport", "sports", "cricket", "football", "olympics", "tennis", "f1", "game"), "🏅", "sun"),
    (("money", "economy", "business", "trade", "fuel", "prices", "jobs"), "💰", "sun"),
    (("politics", "civics", "election", "elections", "vote", "voting", "democracy", "law", "court"), "🗳️", "teal"),
    (("history", "on this day"), "📜", "sand"),
    (("art", "arts", "culture", "music", "film", "books"), "🎨", "rose"),
    (("my city", "local", "city"), "🏙️", "sky"),
    (("india",), "🪔", "coral"),
    (("world", "europe", "asia", "africa", "america", "americas", "united states", "united kingdom", "middle east",
      "global", "international"), "🌍", "teal"),
]


def nice(text):
    """'SAUDI ARABIA AND YEMEN' as 'Saudi Arabia and Yemen' (kickers are printed in capitals)."""
    if not text.isupper():
        return text
    small = {"and", "of", "the", "in", "on", "for", "to", "a", "at", "by", "or", "vs"}
    return " ".join(w.lower() if i and w.lower() in small else w.capitalize() for i, w in enumerate(text.split()))


def desk(kicker, bid=""):
    """(name, icon, colour) for a section, from the first part of its kicker ("WORLD  •  RUSSIA")."""
    k = plain(kicker or "")
    name = k.split("•")[0].strip()
    for text in (name, k, bid.replace("_", " ")):
        low = text.lower()
        for words, icon, tone in DESKS:
            if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
                return nice(name) if "•" in k else "", icon, tone
    return nice(name) if "•" in k else "", "📰", "teal"


# ------------------------------------------------------------------ text
def clean(text):
    """Issue text is written for the PDF engine (a little HTML, entities). Make it safe HTML."""
    t = E(html.unescape(str(text)), quote=False)
    return re.sub(r"&lt;(/?)(b|i)&gt;", r"<\1\2>", t)


def plain(text):
    return re.sub(r"<[^>]+>", "", html.unescape(str(text)))


def vocab_of(issue):
    out = []
    for b in issue.get("blocks", {}).values():
        if isinstance(b, dict) and isinstance(b.get("items"), list):
            for v in b["items"]:
                if isinstance(v, dict) and v.get("word"):
                    meaning, _, today = plain(v.get("def", "")).partition("Today:")
                    out.append({"word": plain(v["word"]).strip(), "meaning": meaning.strip(), "today": today.strip()})
    return out


def _highlight(htm, vocab, used):
    """Mark the first use of each new word in this story (outside tags)."""
    parts = re.split(r"(<[^>]+>)", htm)
    for i, v in enumerate(vocab):
        if i in used:
            continue
        pat = re.compile(rf"\b({re.escape(v['word'])}(?:s|es|ed|d|ing)?)\b", re.I)
        for k, p in enumerate(parts):
            if p.startswith("<"):
                continue
            new, n = pat.subn(rf'<mark class="w" role="button" tabindex="0" data-w="{i}">\1</mark>', p, count=1)
            if n:
                parts[k] = new
                used.add(i)
                break
        htm = "".join(parts)
        parts = re.split(r"(<[^>]+>)", htm)
    return "".join(parts)


def _sentences(text, vocab, used):
    return " ".join(f'<span class="s">{_highlight(clean(s), vocab, used)}</span>' for s in sentences(plain(text)))


# ------------------------------------------------------------------ pictures, charts, maps
def chart_html(spec):
    """A printed bar chart as bars that grow when they come into view (play.js counts the numbers up)."""
    s = spec or {}
    vals = [v for v in s.get("values") or [] if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not vals:
        return ""
    top = s.get("max") or max(vals) or 1
    pre, hi, labels = E(str(s.get("value_prefix", ""))), s.get("highlight_after", -1), s.get("labels") or []
    lab = lambda i: plain(labels[i]).replace("\n", " ") if i < len(labels) else ""
    bars = "".join(
        f'<div class="bc{" hi" if i > hi else ""}" style="--h:{max(0, min(100, v / top * 100)):.1f}">'
        f'<span class="v">{pre}<b data-v="{v:g}">{v:g}</b></span><i></i><span class="l">{E(lab(i))}</span></div>'
        for i, v in enumerate(vals))
    said = "; ".join(f"{lab(i)}: {plain(s.get('value_prefix', ''))}{v:g}" for i, v in enumerate(vals))
    cap = plain(s.get("caption", ""))
    return (f'<figure class="chart"><p class="ct"><b>{E(plain(s.get("title", "")))}</b> <span>{E(plain(s.get("subtitle", "")))}</span></p>'
            f'<div class="bars" role="img" aria-label="{E(plain(s.get("title", "")))}. {E(said)}">{bars}</div>'
            + (f"<figcaption>{E(cap)}</figcaption>" if cap else "") + "</figure>")


def scene_html(kind, spec):
    """A printed illustration (or a map with no country we know) as a moving picture."""
    s = spec or {}
    cap = plain(s.get("caption", ""))
    title = plain(s.get("title", ""))
    svg = scenes.scene(s.get("motif", ""), cap or title) if kind == "illustration" else scenes.sketch_map(s, cap or title)
    badge = f'<span class="badge">{E(nice(title))}</span>' if title and kind == "illustration" else ""
    return f'<figure class="pic">{badge}{svg}' + (f"<figcaption>{E(cap)}</figcaption>" if cap else "") + "</figure>"


def where_of(story, given=None):
    """Where a story happens: from the issue's play.where if it says, else the places its kicker, headline,
    deck or printed map name. None when it names nowhere."""
    lat = lon = None
    place = ""
    if given:
        ccs = [n for n in (world.country_name(c) for c in given.get("countries") or []) if n]
        place = plain(given.get("place", "")).strip()
        try:
            lat, lon = float(given["lat"]), float(given["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                lat = lon = None
        except (KeyError, TypeError, ValueError):
            pass
    else:
        m = story.get("map") or {}
        ccs, city = world.find(story.get("kicker"), story.get("headline"), story.get("deck"),
                               m.get("label_top"), m.get("label_bottom"), m.get("title"))
        if not ccs and not city:                 # last try: the first place the story itself names
            ccs, city = world.find(*(story.get("body") or [])[:2])
            ccs = ccs[:1]
        if city:
            place, (lat, lon) = city, world.city(city)
    ccs = [c for c in dict.fromkeys(ccs)][:6]
    if lat is None and ccs:
        lon, lat = world.by_name()[ccs[0]]["label"]
    if lat is None:
        return None
    x, y = world.project(lon, lat)
    boxes = [world.by_name()[c]["box"] for c in ccs] + [(x, y, x, y)]
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    return {"place": place, "countries": ccs, "lat": round(lat, 3), "lon": round(lon, 3),
            "box": " ".join(f"{v:.1f}" for v in box)}


def place_name(w):
    return w["place"] or ", ".join(world.DISPLAY.get(c, c) for c in w["countries"][:3])


def where_html(w, heading=False):
    names = [world.DISPLAY.get(c, c) for c in w["countries"]]
    label = place_name(w)
    more = ", ".join(n for n in names if n != w["place"])[:80] if w["place"] else ""
    return (f'<figure class="where" data-c="{E("|".join(w["countries"]))}" data-lat="{w["lat"]}" data-lon="{w["lon"]}" '
            f'data-box="{w["box"]}">' + ('<h3 class="wh">🗺️ Where in the world?</h3>' if heading else "")
            + f'<div class="map" role="img" aria-label="A world map with a pin on {E(label)}"></div>'
              f'<figcaption><span class="here">📍 <b>{E(label)}</b>{f" · {E(more)}" if more else ""}</span>'
              f'<span class="far" aria-live="polite"></span>'
              f'<button type="button" class="zoom">🌍 Whole world</button></figcaption></figure>')


# ------------------------------------------------------------------ one issue
def top_figure(story, w):
    """The picture at the top of a story card: its real map, moving picture, or growing chart."""
    if story.get("map"):
        return where_html(w) if w else scene_html("map", story["map"])
    if story.get("illustration"):
        return scene_html("illustration", story["illustration"])
    if story.get("chart"):
        return chart_html(story["chart"])
    return ""


def sections(ed, issue, date, chips=None):
    """[(kind, block id, html, colour)] in reading order, the data the games need, and where each story happens.
    `chips`: {story id: link} for stories that are part of a big ongoing story ("the story so far")."""
    chips = chips or {}
    blocks = issue.get("blocks", {})
    vocab = vocab_of(issue)
    used = set()
    out, stories, places = [], [], []
    briefs = []
    play = issue.get("play") if isinstance(issue.get("play"), dict) else {}
    given = {w.get("story"): w for w in play.get("where") or [] if isinstance(w, dict)}
    easy = play.get("easy") if isinstance(play.get("easy"), dict) else {}

    def kick(icon, name, topic=""):
        name = f'<span class="desk"><span aria-hidden="true">{icon}</span> {E(name)}</span>' if name else f'<span class="desk solo" aria-hidden="true">{icon}</span>'
        return f'<p class="kicker">{name}{f" {E(topic)}" if topic else ""}</p>'

    for bid in edition.placed_blocks(ed):
        cfg, b = ed["blocks"][bid], blocks.get(bid)
        t = cfg["type"]
        if not isinstance(b, dict) or t in SKIP or bid == "quiz":
            continue
        if t == "story":
            k = plain(b.get("kicker", ""))
            topic = k.split("•")[-1].strip() if "•" in k else k
            name, icon, tone = desk(k, bid)
            w = where_of(b, given.get(bid))
            top = top_figure(b, w)
            below = where_html(w, heading=True) if w and not b.get("map") else ""
            if w:
                places.append((bid, plain(b.get("headline", "")), w))
            seen = set(used)                         # new words already marked in earlier stories
            body = "".join(f"<p>{_sentences(p, vocab, used)}</p>" for p in b.get("body", []) if str(p).strip())
            boxes = "".join(
                f'<aside class="box"><h3>{E(ed["labels"][x].capitalize())}</h3><p>{_sentences(b[x], vocab, used)}</p></aside>'
                for x in ("why", "connect", "analyst") if b.get(x))
            ez = easy.get(bid) if isinstance(easy.get(bid), dict) else None
            ez_body = [x for x in (ez or {}).get("body") or [] if str(x).strip()]
            if ez and str(ez.get("headline", "")).strip() and ez_body:  # the easier version, shown instead on a tap
                easy_btn = ('<button type="button" class="easy" aria-pressed="false"><span aria-hidden="true">🪶</span>'
                            ' <span>Easier version</span></button>')
                easy_head = f'<h2 class="v-easy" hidden><span class="s">{clean(ez["headline"])}</span></h2>'
                easy_text = ('<div class="text v-easy" hidden>'
                             + "".join(f"<p>{_sentences(x, vocab, set(seen))}</p>" for x in ez_body) + "</div>")
            else:
                easy_btn = easy_head = easy_text = ""
            src = "".join(f'<li><a href="{E(s.get("url", "") if isinstance(s, dict) else s)}" rel="noopener" target="_blank">'
                          f'{E((s.get("title") or s.get("outlet") or s.get("url", "")) if isinstance(s, dict) else s)}</a></li>'
                          for s in b.get("sources", []) or [])
            orig = ' v-orig' if easy_btn else ''          # what the easier version replaces
            if easy_btn and boxes:
                boxes = f'<div class="v-orig">{boxes}</div>'
            out.append(("story", bid, f'''{easy_btn}{kick(icon, name, nice(topic))}
<h2{' class="v-orig"' if easy_btn else ''}><span class="s">{clean(b.get("headline", ""))}</span></h2>{easy_head}
{f'<p class="deck{orig}"><span class="s">{clean(b["deck"])}</span></p>' if b.get("deck") else ""}
{f'<a class="tchip" href="{E(chips[bid])}">🧵 New to this story? Read the story so far →</a>' if bid in chips else ""}
{top}<div class="text{orig}">{body}</div>{easy_text}{below}{boxes}
{f'<details class="grown"><summary>For grown-ups: sources</summary><ul>{src}</ul></details>' if src else ""}''', tone))
            first = plain(b.get("body", [""])[0]) if b.get("body") else ""
            stories.append({"headline": plain(b.get("headline", "")), "first": (sentences(first) or [""])[0]})
        elif t == "feature":
            body = "".join(f"<p>{_sentences(p, vocab, used)}</p>" for p in b.get("body", []) if str(p).strip())
            label = cfg.get("label", "").title()
            _, icon, tone = desk(label, bid)
            out.append(("feature", bid, f'{kick(icon, label)}'
                                   f'<h2><span class="s">{clean(b.get("title", ""))}</span></h2><div class="text">{body}</div>', tone))
        elif t == "did_you_know" and b.get("text"):
            out.append(("fact", bid, f'{kick("💡", "Did you know?")}<h2 class="big"><span class="s">{clean(b["text"])}</span></h2>', "sun"))
        elif t == "sports" and b.get("body"):
            out.append(("feature", bid, f'{kick("🏅", "Sport")}<h2><span class="s">{clean(b.get("title", ""))}</span></h2>'
                                   f'<div class="text"><p>{_sentences(b["body"], vocab, used)}</p></div>', "sun"))
        elif t == "briefs":
            briefs += [x for x in b.get("items", []) if str(x).strip()]
    if briefs:
        out.append(("briefs", "briefs", f'{kick("🗞️", "In brief")}<h2><span class="s">More news</span></h2><ul class="text">'
                    + "".join(f"<li>{_sentences(x, vocab, used)}</li>" for x in briefs) + "</ul>", "sky"))
    if vocab:
        out.append(("words", "words", f'{kick("🔤", "New words")}<h2><span class="s">Words from this issue</span></h2><dl class="words">'
                    + "".join(f'<dt><span class="s">{E(v["word"])}</span></dt><dd><span class="s">{E(v["meaning"])}</span>'
                              + (f' <i>Today: {E(v["today"])}</i>' if v["today"] else "") + "</dd>" for v in vocab) + "</dl>", "violet"))
    at = {bid: i for i, (_, bid, _, _) in enumerate(out)}
    quiz = [{"q": plain(q["q"]), "options": [plain(o) for o in q["options"]], "answer": q["answer"],
             "why": plain(q.get("why", "")), "card": at.get(q.get("story"), -1)}
            for q in play.get("quiz") or [] if isinstance(q, dict) and q.get("q") and len(q.get("options") or []) == 3
            and q.get("answer") in (0, 1, 2)]
    facts = [{"claim": plain(f["claim"]), "true": bool(f["true"]), "why": plain(f.get("why", "")),
              "card": at.get(f.get("story"), -1)}
             for f in play.get("fact_or_fiction") or [] if isinstance(f, dict) and f.get("claim") and isinstance(f.get("true"), bool)]
    return out, {"vocab": vocab, "stories": [s for s in stories if s["headline"] and s["first"]], "quiz": quiz, "facts": facts}, places


def issue_page(cfg, ed, band, issue, date, others, chips=None):
    """The page, and where its stories happen (for the lobby's map)."""
    secs, data, places = sections(ed, issue, date, chips)
    cards = "".join(f'<section class="card {k} t-{tone}" id="s-{E(b)}" data-i="{i}" data-b="{E(b)}"><button type="button" class="read" aria-label="Read this to me">'
                    f'<span aria-hidden="true">🔊</span> Read it to me</button>{h}</section>' for i, (k, b, h, tone) in enumerate(secs))
    d = dt.date.fromisoformat(date)
    mode = "cards" if band in CARD_BANDS else "scroll"
    earlier = "".join(f'<option value="{o}.html"{" selected" if o == date else ""}>{dt.date.fromisoformat(o):%a %d %b}</option>'
                      for o in others)
    body = f'''<header class="bar"><a class="home" href="../index.html">← Read &amp; Play</a>
<div class="tools" role="toolbar" aria-label="Reading settings">
<button type="button" data-act="smaller" aria-label="Smaller text">A−</button><button type="button" data-act="bigger" aria-label="Bigger text">A+</button>
<button type="button" data-act="night" aria-label="Night mode">🌙</button>
<select data-act="rate" aria-label="Reading speed"><option value="0.8">Slow</option><option value="1" selected>Normal</option><option value="1.2">Fast</option></select>
</div></header>
<main class="issue" data-mode="{mode}" data-key="{E(ed['id'])}-{date}">
<div class="title"><h1>{E(ed["name"])}</h1><p>{d:%A %d %B %Y} · No. {E(str(issue.get("issue", "")))}</p>
<nav class="tabs" role="tablist"><button type="button" role="tab" data-tab="read" aria-selected="true">Read</button><button type="button" role="tab" data-tab="play" aria-selected="false">Play</button></nav></div>
<div id="read" role="tabpanel">
<div class="trail" aria-hidden="true"><div class="track"><i></i><b class="walker">🚀</b><b class="flag">🏁</b></div><span class="count"></span></div>
{cards}
<section class="card end" data-i="{len(secs)}">{brand.inline("owl cheer")}<h2>You read today's paper! 🎉</h2><p class="streak" role="status"></p><p>Ready for a game?</p>
<button type="button" class="big go" data-tab="play">Play now</button>
<p class="mine"><a href="../index.html#badges">See my streak and badges</a></p></section>
<div class="steps"><button type="button" class="big prev">← Back</button><button type="button" class="big next">Next →</button></div>
</div>
<div id="play" role="tabpanel" hidden><div id="game"></div></div>
<p class="older"><label>Other days: <select onchange="location.href=this.value">{earlier}</select></label>
· <a href="../../e/{E(ed['id'])}/index.html">Print this paper (for grown-ups)</a></p>
</main>
<div id="pop" role="dialog" aria-modal="false" hidden><button type="button" class="x" aria-label="Close">✕</button><h3></h3><p class="m"></p><p class="t"></p>
<button type="button" class="say">🔊 Say it</button></div>
<script id="data" type="application/json">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>'''
    return shell(cfg, f"{ed['name']}, {d:%d %b} · Read & Play", body, root="../../"), places


# ------------------------------------------------------------------ the space
def asset_version():
    """Changes whenever the page's style, script or map change, so a phone never mixes old and new."""
    global _VERSION
    if not _VERSION:
        _VERSION = hashlib.sha1((CSS + scenes.CSS + JS + world.world_js()).encode()).hexdigest()[:10]
    return _VERSION


_VERSION = ""
ASSETS = ("play.css", "world.js", "play.js")


def shell(cfg, title, body, root=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="Read today's news, hear it read aloud and play a game. For children, from {E(cfg['title'])}.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&display=swap" rel="stylesheet">
<link rel="manifest" href="{root}play/manifest.webmanifest"><meta name="theme-color" content="#E2584D">
<link rel="icon" href="{root}play/owl.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="{root}play/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Read &amp; Play">
<link rel="stylesheet" href="{root}play/play.css?v={asset_version()}"></head><body>{body}
<script src="{root}play/world.js?v={asset_version()}"></script><script src="{root}play/play.js?v={asset_version()}"></script></body></html>"""


# ------------------------------------------------------------------ the story so far
def thread_href(tid, level):
    return f"{tid}.html" if level == "younger" else f"{tid}-more.html"


def thread_page(cfg, t, level, links, active, dates=()):
    """One big ongoing story for one age level. `links`: {date: Read & Play page} for the timeline."""
    v = t[level]
    other = "older" if level == "younger" else "younger"
    switch = (f'<a class="lvl" href="{thread_href(t["id"], other)}">'
              f'{"More detail →" if level == "younger" else "← Easier version"}</a>')
    updated = dt.date.fromisoformat(threads.last_news(t, dates))
    w = play_where(t.get("where"))
    lines = [e for e in t["timeline"] if e.get(level) or level == "older"][::-1]      # newest first

    def li(e):
        d = dt.date.fromisoformat(e["date"])
        when = e.get("when") or f"{d.day} {d:%b}"
        link = links.get(e["date"])
        return (f'<li><b>{E(when)}</b><span class="s">{clean(e.get(level) or e["older"])}</span>'
                + (f' <a href="{E(link)}">Read it</a>' if link else "") + "</li>")
    recent, earlier = lines[:3], lines[3:]
    timeline = (f'<details open><summary>📅 What happened</summary><ul class="tl">{"".join(li(e) for e in recent)}</ul>'
                + (f'<details class="earlier"><summary>Show earlier days ({len(earlier)})</summary><ul class="tl">'
                   f'{"".join(li(e) for e in earlier)}</ul></details>' if earlier else "") + "</details>")
    who = ('<details><summary>👥 Who\'s who</summary><div class="who2">'
           + "".join(f'<div><b>{E(p["name"])}</b><span class="s">{clean(p["about"])}</span></div>' for p in v["who"])
           + "</div></details>")
    qs = ("".join(f'<details><summary>❓ {E(q["q"])}</summary><p><span class="s">{clean(q["a"])}</span></p></details>'
                  for q in v.get("questions") or []))
    worry = (f'<details class="worry"><summary>💛 If this news worries you</summary><p><span class="s">{clean(v["worry"])}</span></p></details>'
             if v.get("worry") else "")
    src = "".join(f'<li><a href="{E(u)}" rel="noopener" target="_blank">{E(u.split("//")[-1].split("/")[0])}</a></li>'
                  for u in t.get("sources") or [])
    body = f'''<header class="bar"><a class="home" href="../index.html">← Read &amp; Play</a>{switch}</header>
<main class="threadpage"><section class="card thread t-violet"><button type="button" class="read" aria-label="Read this to me">
<span aria-hidden="true">🔊</span> Read it to me</button>
<p class="kicker"><span class="desk">🧵 The story so far</span> {"Updated" if active else "Last news"} {updated:%a %d %b}</p>
<h2><span class="s">{E(t["title"])}</span></h2>
<p class="oneminute"><b>In one minute:</b> <span class="s">{clean(v["one_minute"])}</span></p>
{where_html(w) if w else ""}{timeline}{who}{qs}{worry}
<details class="grown"><summary>For grown-ups: sources</summary><ul>{src}</ul></details></section>
<p class="older"><a href="index.html">All the big stories</a></p></main>'''
    return shell(cfg, f"{t['title']}: the story so far · Read & Play", body, root="../../")


def play_where(w):
    """A thread's `where` as the map figure's data."""
    if not isinstance(w, dict):
        return None
    return where_of({}, w)


def thread_index(cfg, items):
    rows = "".join(f'''<a class="bigstory" href="{thread_href(t["id"], "younger")}" data-young="{thread_href(t["id"], "younger")}"
data-old="{thread_href(t["id"], "older")}"><span class="ic" aria-hidden="true">🧵</span><span><b>{E(t["title"])}</b>
<small>{"Updated" if active else "Last news"} {dt.date.fromisoformat(threads.last_news(t, dates)):%a %d %b}</small></span></a>'''
                   for t, active, dates in items)
    body = f'''<header class="bar"><a class="home" href="../index.html">← Read &amp; Play</a></header>
<main class="lobby"><h1>{brand.inline("owl")}Big stories</h1><p class="lede">News that goes on for days. Catch up on what happened,
who's who, and the questions people are asking.</p><div class="big3">{rows}</div></main>'''
    return shell(cfg, f"Big stories · Read & Play", body, root="../../")


# ------------------------------------------------------------------ an app on the home screen
def manifest(cfg):
    return json.dumps({
        "name": f"Read & Play · {cfg['title']}", "short_name": "Read & Play",
        "description": "Today's news for children: read it, hear it, play a game.",
        "start_url": "./index.html", "scope": "./", "display": "standalone",
        "background_color": "#FFF8EE", "theme_color": "#E2584D",
        "icons": [{"src": f"icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any maskable"}
                  for n in (192, 512)]}, ensure_ascii=False, indent=1)


SW = r"""// Read & Play's service worker: keeps today's papers on the device so they open without internet.
const V = "%VERSION%", CORE = %CORE%;
self.addEventListener("install", (e) => e.waitUntil(caches.open(V).then((c) => c.addAll(CORE)).then(() => self.skipWaiting())));
self.addEventListener("activate", (e) => e.waitUntil(caches.keys()
  .then((ks) => Promise.all(ks.filter((k) => k.startsWith("rp-") && k !== V).map((k) => caches.delete(k))))
  .then(() => self.clients.claim())));
const keep = (r, res) => { if (res.ok) { const copy = res.clone(); caches.open(V).then((c) => c.put(r, copy)); } return res; };
self.addEventListener("fetch", (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin || !u.pathname.startsWith(new URL("./", location).pathname)) return;
  if (r.mode === "navigate") {              // pages: the newest from the network, else the one kept
    e.respondWith(fetch(r).then((res) => keep(r, res))
      .catch(() => caches.match(r, { ignoreSearch: true }).then((hit) => hit || caches.match("index.html"))));
    return;
  }
  e.respondWith(caches.match(r).then((hit) => {   // styles, scripts, map, icons: the kept copy, refreshed behind
    const net = fetch(r).then((res) => keep(r, res)).catch(() => hit);
    return hit || net;
  }));
});
"""


def stub(cfg, ed, date, latest):
    """A page for an issue that has left Read & Play (its printed QR code still points here)."""
    d = dt.date.fromisoformat(date)
    body = f'''<header class="bar"><a class="home" href="../index.html">← Read &amp; Play</a></header>
<main class="stub"><section class="card end">{brand.inline("owl cheer")}<h2>This paper is from {d:%A %d %B}</h2>
<p>Read &amp; Play keeps the last week's papers. Here's the newest {E(ed["name"])}!</p>
<a class="big go" href="{latest}.html">Read the newest one →</a></section></main>'''
    return shell(cfg, f"{ed['name']}, {d:%d %b} · Read & Play", body, root="../../")


def write_threads(pdir, cfg, known, in_thread, pages):
    """play/threads/: each thread at two levels, and the list of them all. Returns the active ones,
    newest first, for the front page: [(thread, its story dates, newest date on the site)]."""
    tdir = os.path.join(pdir, "threads")
    os.makedirs(tdir, exist_ok=True)
    newest = max((d for _, d in pages), default="")
    items, big = [], []
    linked = {tid: [d for (_, d, _), x in in_thread.items() if x == tid] for tid in known}
    for t in sorted(known.values(), key=lambda t: (threads.last_news(t, linked[t["id"]]), t["title"]), reverse=True):
        refs = [(e, d, b) for (e, d, b), tid in in_thread.items() if tid == t["id"]]
        dates = [d for _, d, _ in refs]
        active = bool(newest) and threads.is_active(t, newest, dates)
        for level in threads.LEVELS:
            links = {}                              # a timeline line -> the story that reported it, at this age if we can
            for e in t.get("timeline", []):
                near = sorted((0 if threads.level_of(pages[(p, d)]) == level else 1, p, b) for p, d, b in refs
                              if d == e.get("reported") and (p, d) in pages)
                if near:
                    _, p, b = near[0]
                    links[e["date"]] = f"../{p}/{e['reported']}.html#s-{b}"
            open(os.path.join(tdir, thread_href(t["id"], level)), "w", encoding="utf-8").write(
                thread_page(cfg, t, level, links, active, dates))
        items.append((t, active, dates))
        if active and len(big) < threads.MAX_ACTIVE:
            big.append((t, dates, newest))
    open(os.path.join(tdir, "index.html"), "w", encoding="utf-8").write(thread_index(cfg, items))
    return big


def build(out, cfg, keep=7, log=print):
    """Write out/play/: the Who's reading? page with today's news map, and a page per recent issue of every listed paper."""
    from .site import audience, issues_of, lead_headline
    pdir = os.path.join(out, "play")
    os.makedirs(pdir, exist_ok=True)
    open(os.path.join(pdir, "play.css"), "w", encoding="utf-8").write(CSS + scenes.CSS)
    open(os.path.join(pdir, "play.js"), "w", encoding="utf-8").write(JS)
    open(os.path.join(pdir, "world.js"), "w", encoding="utf-8").write(world.world_js())
    tiles, pins, newest = [], [], []
    every = []                                      # (paper, date, issue) for every listed paper: which stories join a thread
    for eid in edition.list_editions():
        ed = edition.load(eid)
        if (ed.get("site") or {}).get("listed") is not False:
            every += [(eid, d, json.load(open(p, encoding="utf-8"))) for d, p in issues_of(ed)]
    in_thread = threads.story_index(every)
    known = {t["id"]: t for t in threads.load_all()}
    pages = {}                                      # (paper, date) -> age band, for pages Read & Play keeps
    for eid in edition.list_editions():
        ed = edition.load(eid)
        if (ed.get("site") or {}).get("listed") is False:
            continue
        band = audience(ed)
        dates = [d for d, _ in issues_of(ed)[:keep]]
        if not dates:
            continue
        edir = os.path.join(pdir, eid)
        os.makedirs(edir, exist_ok=True)
        latest = None
        for date, path in issues_of(ed)[:keep]:
            issue = json.load(open(path, encoding="utf-8"))
            level = threads.level_of(band)
            chips = {b: f"../threads/{thread_href(tid, level)}" for (e, d, b), tid in in_thread.items()
                     if e == eid and d == date and tid in known}
            try:
                html_, places = issue_page(cfg, ed, band, issue, date, dates, chips)
            except Exception as e:
                log(f"  ! play {eid} {date}: {e}")
                continue
            open(os.path.join(edir, f"{date}.html"), "w", encoding="utf-8").write(html_)
            pages[(eid, date)] = band
            if not latest:
                latest = (date, lead_headline(ed, issue), issue)
                pins += [{"lat": w["lat"], "lon": w["lon"], "h": h, "p": ed["name"], "b": band, "place": place_name(w),
                          "u": f"{eid}/{date}.html#s-{bid}"} for bid, h, w in places]
        if not latest:
            continue
        for date, _ in issues_of(ed)[keep:]:       # older papers: their QR codes open the newest
            open(os.path.join(edir, f"{date}.html"), "w", encoding="utf-8").write(stub(cfg, ed, date, latest[0]))
        newest.append(f"{eid}/{latest[0]}.html")
        lead = next((latest[2]["blocks"].get(b) for b in edition.story_blocks(ed)
                     if isinstance(latest[2]["blocks"].get(b), dict)), None) or {}
        fig = top_figure(lead, None if lead.get("illustration") or lead.get("chart") else where_of(lead))
        tiles.append((BANDS.index(band) if band in BANDS else 9, ed["name"], f'''<article class="tile" data-band="{E(band)}">
{fig}<h2>{E(ed["name"])}</h2><p class="when">{E(band)} · {dt.date.fromisoformat(latest[0]):%a %d %b}</p>
<p>{E(latest[1])}</p><div class="go2"><a class="big go" href="{eid}/{latest[0]}.html">Read</a><a class="big" href="{eid}/{latest[0]}.html#play">Play</a></div></article>'''))
        log(f"  play {eid}: {len(dates)} issue(s)")
    big = write_threads(pdir, cfg, known, in_thread, pages)
    big_row = ("<section class=\"bigrow\"><h2>🧵 Big stories right now <a href=\"threads/index.html\">All</a></h2><div class=\"big3\">"
               + "".join(f'''<a class="bigstory" href="threads/{thread_href(t["id"], "younger")}" data-young="threads/{thread_href(t["id"], "younger")}"
data-old="threads/{thread_href(t["id"], "older")}"><span class="ic" aria-hidden="true">🌍</span><span><b>{E(t["title"])}</b>
<small>Day {(dt.date.fromisoformat(newest_d) - dt.date.fromisoformat(t["opened"])).days + 1} · {len(t["timeline"])} updates</small></span>
{"<span class=\"new\">NEW TODAY</span>" if threads.last_news(t, ld) == newest_d else ""}</a>''' for t, ld, newest_d in big)
               + "</div></section>") if big else ""
    who = "".join(f'<button type="button" class="who" data-band="{E(b)}">{E(b.replace("Ages ", ""))}</button>' for b in BANDS)
    news_map = (f'''<section class="newsmap"><h2>🗺️ Where's the news today?</h2><p class="how">Tap a pin to see the story.</p>
<figure class="where wide" data-pins="{E(json.dumps(pins, ensure_ascii=False))}"><div class="map" role="img" aria-label="A world map with a pin for each of today's stories"></div>
<figcaption><span class="far" aria-live="polite"></span></figcaption><div class="pinlist" aria-live="polite"></div></figure></section>'''
                if pins else "")
    body = f'''<header class="bar"><a class="home" href="../index.html">← {E(cfg["title"])} (grown-ups)</a></header>
<main class="lobby"><h1>{brand.inline("owl")}Read &amp; Play</h1><p class="lede">Today's news, read to you if you like, with a game at the end.</p>
<div class="install" hidden><p><img class="app" src="icon-192.png" alt="" width="48" height="48"><b>Keep Read &amp; Play on your home screen.</b> It opens like an app, and
today's papers work without the internet.</p><button type="button" class="big go add" hidden>Add to home screen</button>
<p class="ios" hidden>On an iPhone or iPad: tap <b>Share</b> <span aria-hidden="true">⬆️</span>, then <b>Add to Home Screen</b>.</p></div>
<section class="myreading" id="badges" aria-label="My reading"></section>
<h2>Who's reading? <span>How old are you?</span></h2><div class="whos">{who}<button type="button" class="who" data-band="">Show all</button></div>
{big_row}{news_map}<div class="tiles">{"".join(t[2] for t in sorted(tiles))}</div>
<p class="note">For grown-ups: nothing here is tracked. Settings and stars stay on this device. Maps show India's borders as on
India's official maps (Natural Earth, India view).</p></main>'''
    open(os.path.join(pdir, "index.html"), "w", encoding="utf-8").write(shell(cfg, f"Read & Play · {cfg['title']}", body, root="../"))
    for n in (180, 192, 512):                     # the owl, from assets/ (tools/brand/make_icons.js)
        shutil.copy(os.path.join(brand.ASSETS, f"owl-icon-{n}.png"), os.path.join(pdir, f"icon-{n}.png"))
    shutil.copy(brand.SVG, os.path.join(pdir, "owl.svg"))
    open(os.path.join(pdir, "manifest.webmanifest"), "w", encoding="utf-8").write(manifest(cfg))
    core = (["index.html", "manifest.webmanifest", "icon-192.png"] + [f"{a}?v={asset_version()}" for a in ASSETS]
            + newest)
    version = hashlib.sha1((asset_version() + "".join(open(os.path.join(pdir, f), encoding="utf-8").read()
                                                    for f in ["index.html"] + newest)).encode()).hexdigest()[:12]
    open(os.path.join(pdir, "sw.js"), "w", encoding="utf-8").write(
        SW.replace("%VERSION%", f"rp-{version}").replace("%CORE%", json.dumps(core)))


CSS = r"""
:root{--bg:#FFF8EE;--card:#FFFFFF;--ink:#1E2A32;--muted:#5B6870;--line:#E7DCCB;--coral:#E2584D;--teal:#007C89;--sun:#F4B400;
--sun-t:#FFE9A8;--leaf:#2E7D4F;--leaf-t:#DDF2E4;--rose-t:#FBE1DE;--fs:19px;--lh:1.7;
--display:"Bricolage Grotesque","Avenir Next","Segoe UI",system-ui,sans-serif;--text:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;
box-sizing:border-box}
:root{--sea:#CFE8F3;--land:#EADFC4;--map-line:#FFFFFF;--bar:#A9BCC4}
:root[data-theme="night"]{--bg:#12181C;--card:#1B242A;--ink:#E8EEEC;--muted:#A3B0B6;--line:#2C3940;--sun-t:#5A4A12;--leaf-t:#173326;--rose-t:#3B2224;
  --sea:#17323F;--land:#45524C;--map-line:#1B242A;--bar:#5F7480}
*,*::before,*::after{box-sizing:inherit}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--ink);font:var(--fs)/var(--lh) var(--text);-webkit-text-size-adjust:100%}
h1,h2,h3{font-family:var(--display);line-height:1.15;margin:0}
a{color:var(--teal)}
button,select{font:inherit;color:inherit}
.bar{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
  padding:10px 16px;background:var(--bg);border-bottom:2px solid var(--line)}
.home{font-weight:700;text-decoration:none;font-size:16px}
.tools{display:flex;gap:6px;flex-wrap:wrap}
.tools button,.tools select{font-size:16px;min-width:44px;min-height:44px;border:2px solid var(--line);background:var(--card);border-radius:12px;padding:4px 10px;cursor:pointer}
button:focus-visible,a:focus-visible,select:focus-visible,mark:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
.issue,.lobby,.stub{max-width:760px;margin:0 auto;padding:16px 16px 60px}
.title h1{font-size:clamp(1.6rem,6vw,2.4rem)}.title p{margin:2px 0 10px;color:var(--muted);font-size:16px}
.tabs{display:flex;gap:8px;margin:6px 0 14px}
.tabs button{flex:1;min-height:52px;border:2px solid var(--line);background:var(--card);border-radius:14px;font-weight:700;font-size:18px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--teal);border-color:var(--teal);color:#fff}
.card{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:18px 18px 20px;margin:0 0 16px;position:relative}
.card h2{font-size:1.45em;margin:4px 0 8px}.card h2.big{font-size:1.3em;line-height:1.35}
.kicker{margin:0;font-size:.72em;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--tone-ink,var(--coral))}
/* each section's colour and icon */
.t-coral{--tone:#E2584D;--tone-t:#FBE1DE;--tone-ink:#B23A30}.t-teal{--tone:#007C89;--tone-t:#D6EEF0;--tone-ink:#00606A}
.t-violet{--tone:#6B5BD2;--tone-t:#E7E3FA;--tone-ink:#4D3FB0}.t-leaf{--tone:#2E7D4F;--tone-t:#DDF2E4;--tone-ink:#236140}
.t-sun{--tone:#E0A100;--tone-t:#FFF0C2;--tone-ink:#7A5700}.t-rose{--tone:#D0487A;--tone-t:#FADDE8;--tone-ink:#A4305B}
.t-sky{--tone:#2B83C6;--tone-t:#DCEBF7;--tone-ink:#1D669E}.t-sand{--tone:#A9793F;--tone-t:#F3E7D3;--tone-ink:#7D5626}
:root[data-theme="night"] [class*=" t-"]{--tone-t:color-mix(in srgb,var(--tone) 30%,#1B242A);--tone-ink:color-mix(in srgb,var(--tone) 45%,#FFFFFF)}
.card[class*=" t-"]{border-top:7px solid var(--tone)}
.desk{display:inline-flex;gap:5px;align-items:center;background:var(--tone-t);color:var(--tone-ink);border-radius:999px;padding:3px 11px;margin:0 6px 4px 0;letter-spacing:.04em}
.desk.solo{padding:3px 8px}
/* moving pictures and growing charts */
.pic{position:relative}.pic .badge{position:absolute;left:10px;top:10px;background:rgba(255,255,255,.92);color:#1E2A32;font-weight:700;
  font-size:.66em;padding:2px 10px;border-radius:999px;letter-spacing:.02em}
:root[data-theme="night"] .scene{filter:brightness(.88)}
figcaption{font-size:.75em;color:var(--muted);margin-top:5px}
.chart{background:var(--bg);border:1px solid var(--line);border-radius:14px;padding:12px 12px 8px}
.chart .ct{margin:0 0 6px;font-size:.8em;line-height:1.35}.chart .ct span{color:var(--muted)}
.bars{display:flex;align-items:flex-end;gap:6px;height:170px;border-bottom:2px solid var(--line)}
.bc{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;position:relative}
.bc i{display:block;width:72%;max-width:60px;height:0;border-radius:4px 4px 0 0;background:var(--bar);transition:height 1.2s cubic-bezier(.2,.8,.2,1)}
.bc.hi i{background:var(--coral)}
.chart.on .bc i{height:calc(var(--h) * 1.15px)}
.bc .v{font-weight:800;font-size:.85em;margin-bottom:3px;color:var(--ink)}
.bc .l{position:absolute;top:100%;left:-2px;right:-2px;font-size:.68em;color:var(--muted);text-align:center;line-height:1.2;padding-top:5px}
.bars{margin-bottom:3em}
@media (prefers-reduced-motion:reduce){.bc i{transition:none}}
/* where in the world? */
.where .wh{font-size:.95em;margin:4px 0 6px}
.where .map{aspect-ratio:16/9;border-radius:14px;overflow:hidden;background:var(--sea);border:1px solid var(--line)}
.where.wide .map{aspect-ratio:2/1}
.where svg{display:block;width:100%;height:100%}
.where .sea{fill:var(--sea)}.where use{fill:var(--land);stroke:var(--map-line);stroke-width:1}
.where .hi{fill:var(--coral);fill-opacity:.85;stroke:var(--map-line);stroke-width:1}
.where .trip{fill:none;stroke:var(--teal);stroke-width:2.5;stroke-dasharray:7 6;stroke-linecap:round;animation:rp-flow .9s linear infinite}
.where .ring{fill:none;stroke:var(--coral);stroke-width:2.5;animation:rp-pulse 1.8s ease-out infinite}
.where .dot{fill:var(--coral);stroke:#fff;stroke-width:2}.where .me .dot{fill:var(--teal)}
.where .lp{cursor:pointer}.where .lp .n{fill:#fff;font:700 10px var(--text);pointer-events:none}.where .lp .hit{fill:transparent}
.where .lp.on .dot{fill:var(--teal)}.where .lp:focus{outline:none}.where .lp:focus-visible .dot{stroke:var(--ink);stroke-width:3}
.where figcaption{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;font-size:.8em;color:var(--ink)}
.where .far{color:var(--muted)}.where .far b{color:var(--ink)}.where select{font:inherit;border-radius:8px;padding:2px 4px;max-width:12em}
.where .zoom{margin-left:auto;border:2px solid var(--line);background:var(--card);border-radius:999px;padding:2px 12px;min-height:40px;cursor:pointer;font-weight:700;font-size:.95em}
@media (prefers-reduced-motion:reduce){.where .trip,.where .ring{animation:none}}
.newsmap{margin:4px 0 22px}.newsmap .how{margin:0 0 8px;color:var(--muted)}
.pinlist ul{list-style:none;padding:0;margin:8px 0 0;display:grid;gap:8px}
.pinlist li{background:var(--card);border:2px solid var(--line);border-radius:14px;padding:10px 12px}
.pinlist li a{font-weight:700;font-size:1.05em}.pinlist small{display:block;color:var(--muted)}
.deck{color:var(--muted);margin:0 0 10px}
.text p{margin:0 0 .8em}.text li{margin:0 0 .5em}
figure{margin:10px 0 14px}
figcaption{font-size:.75em;color:var(--muted);margin-top:4px}
.box{background:var(--leaf-t);border-radius:14px;padding:12px 14px;margin:10px 0}.box h3{font-size:.8em;text-transform:uppercase;letter-spacing:.06em;color:var(--leaf)}
.box p{margin:4px 0 0}
.read{display:inline-flex;gap:6px;align-items:center;margin:0 0 10px;min-height:44px;border:2px solid var(--coral);background:var(--card);color:var(--coral);border-radius:999px;padding:4px 14px;font-weight:700;font-size:16px;cursor:pointer}
.read[aria-pressed="true"]{background:var(--coral);color:#fff}
.easy{display:inline-flex;gap:6px;align-items:center;margin:0 0 10px 6px;min-height:44px;border:2px solid #6B5BD2;background:var(--card);
  color:#4D3FB0;border-radius:999px;padding:4px 14px;font-weight:700;font-size:16px;cursor:pointer}
.easy[aria-pressed="true"]{background:#6B5BD2;color:#fff}
:root[data-theme="night"] .easy{color:#C9C1FF}:root[data-theme="night"] .easy[aria-pressed="true"]{color:#fff}
.v-easy.text p{font-size:1.04em}
.s.now{background:var(--sun-t);border-radius:4px;box-shadow:0 0 0 3px var(--sun-t)}
mark.w{background:none;color:inherit;border-bottom:3px dotted var(--coral);font-weight:700;cursor:pointer}
dl.words dt{font-weight:700;font-size:1.1em;margin-top:10px}dl.words dd{margin:0 0 4px}dl.words i{color:var(--muted)}
.grown{margin-top:12px;font-size:15px}.grown summary{color:var(--muted);cursor:pointer}
.end{text-align:center}.end h2{font-size:1.6em}
.big{display:inline-block;min-height:56px;padding:12px 24px;border-radius:16px;border:2px solid var(--ink);background:var(--card);font-weight:800;font-size:19px;cursor:pointer;text-decoration:none;color:var(--ink)}
.big.go{background:var(--coral);border-color:var(--coral);color:#fff}
.steps{display:none;justify-content:space-between;gap:10px;margin-top:6px}
[data-mode="cards"] .steps{display:flex}
[data-mode="cards"] #read .card{display:none}[data-mode="cards"] #read .card.on{display:block}
/* the trail: how far through today's paper */
.trail{display:none;align-items:center;gap:14px;margin:0 0 12px}[data-mode="cards"] .trail{display:flex}
.track{position:relative;flex:1;height:10px;border-radius:999px;background:var(--line);margin:0 16px 0 14px}
.track i{position:absolute;left:0;top:0;bottom:0;width:0;border-radius:999px;background:var(--coral);transition:width .5s ease}
.walker{position:absolute;top:50%;left:0;transform:translate(-50%,-50%) rotate(45deg);font-size:22px;line-height:1;transition:left .5s ease}
.flag{position:absolute;right:-16px;top:50%;transform:translateY(-60%);font-size:18px;line-height:1}
.count{font-weight:700;color:var(--muted);font-size:15px;white-space:nowrap;min-width:4.5em;text-align:right}
@keyframes rp-in-r{from{opacity:0;transform:translateX(48px)}}
@keyframes rp-in-l{from{opacity:0;transform:translateX(-48px)}}
.card.in-r{animation:rp-in-r .35s ease-out}.card.in-l{animation:rp-in-l .35s ease-out}
.js [data-mode="scroll"] #read .card{opacity:0;transform:translateY(18px);transition:opacity .5s ease,transform .5s ease}
.js [data-mode="scroll"] #read .card.seen{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){.card.in-r,.card.in-l{animation:none}.walker,.track i{transition:none}
  .js [data-mode="scroll"] #read .card{opacity:1;transform:none;transition:none}}
.confetti{position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:30}
.older{font-size:15px;color:var(--muted);margin-top:24px}.older select{padding:4px;border-radius:8px}
#pop{position:fixed;left:12px;right:12px;bottom:12px;max-width:520px;margin:0 auto;background:var(--card);border:3px solid var(--coral);border-radius:20px;padding:16px 18px;z-index:20;box-shadow:0 8px 30px rgba(0,0,0,.25)}
#pop h3{font-size:1.5em}#pop .t{color:var(--muted);font-style:italic}#pop .x{position:absolute;top:8px;right:10px;border:0;background:none;font-size:22px;cursor:pointer;min-width:44px;min-height:44px}
#pop .say{min-height:44px;border:2px solid var(--coral);background:none;color:var(--coral);border-radius:999px;padding:4px 14px;font-weight:700;cursor:pointer}
/* game */
.game h2{font-size:1.4em}.game .how{color:var(--muted);margin:4px 0 14px}
.pairs{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.pairs .col{display:grid;gap:10px;align-content:start}
.pairs button{min-height:56px;text-align:left;border:2px solid var(--line);background:var(--card);border-radius:14px;padding:10px 12px;cursor:pointer;font-size:.9em;line-height:1.35}
.pairs .w button{font-weight:800;font-size:1em}
.pairs button.sel{border-color:var(--teal);box-shadow:0 0 0 3px var(--teal)}
.pairs button.ok{background:var(--leaf-t);border-color:var(--leaf);cursor:default}
.pairs button.no{background:var(--rose-t);animation:shake .3s}
@keyframes shake{25%{transform:translateX(-5px)}75%{transform:translateX(5px)}}
@media (prefers-reduced-motion:reduce){.pairs button.no{animation:none}}
.menu{display:grid;gap:12px}
.menu button{display:flex;gap:14px;align-items:center;text-align:left;min-height:84px;border:2px solid var(--line);background:var(--card);border-radius:18px;padding:12px 16px;cursor:pointer}
.menu button b{display:block;font-family:var(--display);font-size:1.25em}.menu button small{color:var(--muted);font-size:.8em}
.menu button .ic{font-size:2em}.menu button .got{margin-left:auto;color:var(--sun);font-size:1.1em;white-space:nowrap}
.back{border:0;background:none;color:var(--teal);font-weight:700;cursor:pointer;padding:6px 0;margin-bottom:6px;font-size:16px}
.qn{color:var(--muted);font-size:.8em;margin:0}.q{font-size:1.2em;font-weight:700;margin:6px 0 14px;line-height:1.4}
.opts{display:grid;gap:10px}
.opts button{min-height:58px;text-align:left;border:2px solid var(--line);background:var(--card);border-radius:14px;padding:10px 14px;cursor:pointer;font-size:.95em}
.opts button.ok{background:var(--leaf-t);border-color:var(--leaf)}.opts button.no{background:var(--rose-t);border-color:var(--coral)}
.opts button:disabled{cursor:default;color:inherit}
.tf{grid-template-columns:1fr 1fr}.tf button{text-align:center;font-weight:800;font-size:1.05em}
.why{margin:12px 0 0;padding:10px 12px;border-radius:12px;background:var(--bg)}.why a{font-weight:700}
.claim{font-size:1.2em;font-weight:700;margin:6px 0 14px;line-height:1.4;border-left:5px solid var(--sun);padding-left:12px}
.cheer{font-size:1.15em;font-weight:700;margin-top:14px;min-height:1.6em}
.stars{font-size:2em;letter-spacing:4px;color:var(--sun)}
/* lobby */
.lobby h1{font-size:clamp(2.2rem,9vw,3.4rem);color:var(--coral);display:flex;align-items:center;gap:.2em}
.owl{width:1.3em;height:1.3em;flex:none}
.end .owl{display:block;width:96px;height:96px;margin:0 auto 4px;animation:rp-hop 1.6s ease-in-out infinite}
.install p:first-child{display:flex;gap:12px;align-items:center}.install .app{border-radius:12px;flex:none}
@media (prefers-reduced-motion:reduce){.end .owl{animation:none}}.lede{font-size:1.1em;margin:4px 0 18px}
.lobby h2{font-size:1.3em;margin:10px 0 8px}.lobby h2 span{font-family:var(--text);font-weight:400;color:var(--muted);font-size:.75em}
.whos{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.who{min-height:56px;min-width:84px;border:2px solid var(--line);background:var(--card);border-radius:16px;font-weight:800;font-size:20px;cursor:pointer;padding:6px 14px}
.who[aria-pressed="true"]{background:var(--teal);border-color:var(--teal);color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:14px}
.tile{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:14px;display:flex;flex-direction:column;gap:6px}
.tile figure{margin:0 0 4px}.tile figcaption,.tile .badge{display:none}
.tile h2{font-size:1.25em;margin:4px 0 0}.tile p{margin:0}.tile .when{font-size:15px;color:var(--muted)}
.go2{display:flex;gap:8px;margin-top:auto;padding-top:8px}.go2 .big{flex:1;text-align:center}
.note{font-size:14px;color:var(--muted);margin-top:28px}
/* the story so far */
.tchip{display:inline-flex;align-items:center;gap:6px;background:#E7E3FA;color:#4D3FB0;border-radius:999px;padding:8px 14px;
  font-weight:700;font-size:.78em;text-decoration:none;margin:2px 0 12px;line-height:1.3}
:root[data-theme="night"] .tchip{background:#2E2A4D;color:#C9C1FF}
.threadpage{max-width:760px;margin:0 auto;padding:16px 16px 60px}
.bar .lvl{font-weight:700;text-decoration:none;font-size:16px}
.thread .oneminute{font-size:1.05em;margin:6px 0 14px}
.thread details{border-top:2px solid var(--line);padding:10px 0}.thread details details{border-top:0;padding:4px 0 0}
.thread summary{font-family:var(--display);font-weight:800;font-size:1.05em;cursor:pointer;list-style:none;display:flex;justify-content:space-between;gap:10px;min-height:32px}
.thread summary::-webkit-details-marker{display:none}
.thread summary::after{content:"+";color:var(--muted);font-family:var(--text)}.thread details[open]>summary::after{content:"−"}
.thread details.earlier>summary,.thread details.grown>summary{font-family:var(--text);font-size:.8em;color:var(--teal);font-weight:700}
.thread details p{margin:8px 0 0}
.who2{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,150px),1fr));gap:8px;margin-top:8px}
.who2 div{background:var(--bg);border-radius:12px;padding:8px 10px;font-size:.8em;line-height:1.35}.who2 b{display:block;font-size:1.05em}
.tl{list-style:none;margin:8px 0 0;padding:0 0 0 18px;border-left:3px solid #E7E3FA}
.tl li{position:relative;margin:0 0 12px;font-size:.9em;line-height:1.45}
.tl li::before{content:"";position:absolute;left:-26px;top:5px;width:12px;height:12px;border-radius:50%;background:#6B5BD2;border:2px solid var(--card)}
.tl b{display:block;color:#4D3FB0;font-size:.85em}:root[data-theme="night"] .tl b{color:#C9C1FF}
.bigrow{margin:0 0 20px}.bigrow h2 a{font-family:var(--text);font-size:.65em;margin-left:8px}
.big3{display:grid;gap:8px}
.bigstory{display:flex;gap:12px;align-items:center;background:var(--card);border:2px solid var(--line);border-left:6px solid #6B5BD2;
  border-radius:16px;padding:10px 12px;text-decoration:none;color:var(--ink)}
.bigstory .ic{font-size:1.6em}.bigstory b{font-family:var(--display);font-size:1.05em}.bigstory small{display:block;color:var(--muted)}
.bigstory .new{margin-left:auto;background:var(--rose-t);color:#B23A30;font-size:.68em;font-weight:800;border-radius:999px;padding:3px 9px;white-space:nowrap}
/* app, streaks and badges */
.install{background:var(--card);border:2px dashed var(--coral);border-radius:18px;padding:12px 16px;margin:0 0 18px}
.install p{margin:0 0 8px}.install .big{min-height:48px;padding:8px 18px;font-size:17px}
.myreading{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:14px 16px;margin:0 0 18px}
.myreading:empty{display:none}
.myreading h2{margin:0 0 8px}
.myreading .st{display:flex;align-items:center;gap:12px}.myreading .st p{margin:0;line-height:1.3}.myreading .st p span{color:var(--muted);font-size:.8em}
.flame{font-size:2.4em;line-height:1}.flame.off{filter:grayscale(1);opacity:.5}
.myreading .n{margin-left:auto!important;text-align:center}.myreading .n b{font-size:1.6em;font-family:var(--display)}
.myreading summary{cursor:pointer;font-weight:700;color:var(--teal);margin-top:10px;min-height:32px}
.shelf{list-style:none;padding:0;margin:12px 0 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,140px),1fr));gap:8px}
.shelf li{border:2px solid var(--line);border-radius:14px;padding:8px 10px;display:grid;gap:2px;opacity:.65;font-size:.8em;line-height:1.25}
.shelf li.got{opacity:1;border-color:var(--sun);background:var(--sun-t)}
.shelf .bi{font-size:1.8em;line-height:1.1}.shelf small{color:var(--muted)}
.streak{font-weight:700;color:var(--coral)}.streak:empty{display:none}.mine{font-size:.85em;margin:14px 0 0}
.toast{position:fixed;left:50%;top:16px;transform:translateX(-50%);z-index:40;background:var(--card);border:3px solid var(--sun);
  border-radius:18px;padding:10px 18px;box-shadow:0 8px 30px rgba(0,0,0,.25);animation:rp-pop .4s ease-out;transition:opacity .5s,transform .5s}
.toast{width:max-content;max-width:calc(100vw - 32px)}
.toast p{margin:4px 0;display:flex;gap:12px;align-items:center;line-height:1.2}.toast .bi{font-size:2em}
.toast small{display:block;color:var(--muted);font-size:.75em}.toast b{display:block;font-family:var(--display);font-size:1.1em}
.toast.bye{opacity:0;transform:translate(-50%,-20px)}
@keyframes rp-pop{from{transform:translate(-50%,-30px) scale(.8);opacity:0}}
@media (prefers-reduced-motion:reduce){.toast{animation:none;transition:none}}

"""

JS = r"""
(function () {
  const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
  const store = { get(k, d) { try { const v = localStorage.getItem("rp-" + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
                  set(k, v) { try { localStorage.setItem("rp-" + k, JSON.stringify(v)); } catch (e) {} } };
  const SELF = document.currentScript ? document.currentScript.src : "";
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const root = document.documentElement;
  root.classList.add("js");
  const calm = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  // settings, kept on this device
  let fs = store.get("fs", 19);
  const apply = () => { root.style.setProperty("--fs", fs + "px"); root.dataset.theme = store.get("night", false) ? "night" : ""; };
  apply();
  $$("[data-act]").forEach((b) => {
    const act = b.dataset.act;
    if (act === "rate") { b.value = String(store.get("rate", 1)); b.addEventListener("change", () => store.set("rate", +b.value)); return; }
    b.addEventListener("click", () => {
      if (act === "bigger") fs = Math.min(30, fs + 2);
      if (act === "smaller") fs = Math.max(15, fs - 2);
      if (act === "night") store.set("night", !store.get("night", false));
      store.set("fs", fs); apply();
    });
  });


  // ---------------------------------------------------------------- where in the world? (world.js has the shapes)
  const WD = window.WORLD;
  const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, MM = Math.sqrt(3) / 2, RAD = Math.PI / 180;
  function proj(lon, lat) {                                  // Equal Earth, as ygc/world.py draws the countries
    const t = Math.asin(MM * Math.sin(lat * RAD)), t2 = t * t, t6 = t2 * t2 * t2;
    return [WD.w / 2 + lon * RAD * Math.cos(t) / (MM * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))) * WD.s,
            WD.h / 2 - t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2)) * WD.s];
  }
  const shapes = {};
  let defsDone = false;
  function worldDefs() {
    if (defsDone) return; defsDone = true;
    WD.c.forEach((c) => { shapes[c.n] = c; });
    document.body.insertAdjacentHTML("beforeend", '<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs><g id="rp-world">'
      + WD.c.map((c) => `<path d="${c.d}" vector-effect="non-scaling-stroke"/>`).join("") + "</g></defs></svg>");
  }
  const WORLDBOX = () => [0, WD.top, WD.w, WD.bottom - WD.top];
  const CITIES = WD ? WD.cities : [];
  function home() {
    const saved = store.get("home", null);
    if (saved !== null) return CITIES.find((c) => c[0] === saved) || null;
    let tz = ""; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) {}
    const guess = /Kolkata|Calcutta/.test(tz) ? "Delhi" : tz.split("/").pop().replace(/_/g, " ");
    return CITIES.find((c) => c[0] === guess) || null;
  }
  function km(a, b) {
    const h = Math.sin((b[0] - a[0]) * RAD / 2) ** 2 + Math.cos(a[0] * RAD) * Math.cos(b[0] * RAD) * Math.sin((b[1] - a[1]) * RAD / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(h));
  }
  function arc(a, b) {                                       // the shortest way round the globe, split at the map's edge
    const v3 = (p) => [Math.cos(p[0] * RAD) * Math.cos(p[1] * RAD), Math.cos(p[0] * RAD) * Math.sin(p[1] * RAD), Math.sin(p[0] * RAD)];
    const p = v3(a), q = v3(b), d = Math.acos(Math.min(1, p[0] * q[0] + p[1] * q[1] + p[2] * q[2]));
    let path = "", last = null;
    for (let i = 0; i <= 48; i++) {
      const f = i / 48, A = d < 1e-6 ? 1 : Math.sin((1 - f) * d) / Math.sin(d), B = d < 1e-6 ? 0 : Math.sin(f * d) / Math.sin(d);
      const v = [A * p[0] + B * q[0], A * p[1] + B * q[1], A * p[2] + B * q[2]];
      const xy = proj(Math.atan2(v[1], v[0]) / RAD, Math.atan2(v[2], Math.hypot(v[0], v[1])) / RAD);
      path += (last && Math.abs(xy[0] - last[0]) < WD.w / 2 ? "L" : "M") + xy[0].toFixed(1) + " " + xy[1].toFixed(1);
      last = xy;
    }
    return path;
  }
  function fit(b) {                                          // a box to zoom to, with room around it, the map's shape
    let w = Math.max(b[2] - b[0], 60) * 1.6, h = Math.max(b[3] - b[1], 34) * 1.6;
    const cx = (b[0] + b[2]) / 2, cy = (b[1] + b[3]) / 2, aspect = 16 / 9;
    if (w / h < aspect) w = h * aspect; else h = w / aspect;
    return w >= WD.w * 0.8 ? WORLDBOX() : [cx - w / 2, cy - h / 2, w, h];
  }
  function scale(svg, vb) {                                  // pins stay the same size on screen as the map zooms
    const k = Math.max(vb[2] / (svg.clientWidth || 340), vb[3] / (svg.clientHeight || 190));
    $$(".sc", svg).forEach((g) => g.setAttribute("transform", `scale(${k})`));
  }
  function zoom(fig, to, ms) {
    const svg = $("svg", fig), from = svg.getAttribute("viewBox").split(" ").map(Number), t0 = performance.now();
    fig.dataset.view = to.join(" ");
    const step = (now) => {
      const f = calm() || !ms ? 1 : Math.min(1, (now - t0) / ms), e = f < .5 ? 4 * f * f * f : 1 - Math.pow(-2 * f + 2, 3) / 2;
      const vb = from.map((v, i) => v + (to[i] - v) * e);
      svg.setAttribute("viewBox", vb.join(" ")); scale(svg, vb);
      if (f < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  function picker(h) {
    return `<select class="home" aria-label="Your city"><option value="">Pick your city</option>${CITIES.slice().sort((a, b) => a[0].localeCompare(b[0]))
      .map((c) => `<option${h && h[0] === c[0] ? " selected" : ""}>${esc(c[0])}</option>`).join("")}</select>`;
  }
  function target(fig) {
    const b = fig.dataset.box.split(" ").map(Number), h = home();
    if (h) { const p = proj(h[3], h[2]); b[0] = Math.min(b[0], p[0]); b[1] = Math.min(b[1], p[1]); b[2] = Math.max(b[2], p[0]); b[3] = Math.max(b[3], p[1]); }
    return fit(b);
  }
  function homeOn(fig) {                                     // your city, the line to the story, and how far it is
    const svg = $("svg", fig), h = home(), far = $(".far", fig), me = $(".me", svg), trip = $(".trip", svg);
    const there = fig.dataset.lat ? [+fig.dataset.lat, +fig.dataset.lon] : null;
    me.toggleAttribute("hidden", !h); trip.setAttribute("d", "");
    if (h) { const p = proj(h[3], h[2]); me.setAttribute("transform", `translate(${p[0]} ${p[1]})`); }
    if (!there) { far.innerHTML = `<label>🏠 You live in ${picker(h)}</label>`; return; }
    if (!h) { far.innerHTML = `<label>🏠 How far is it from you? ${picker(h)}</label>`; return; }
    const d = km([h[2], h[3]], there);
    if (d > 60) trip.setAttribute("d", arc([h[2], h[3]], there));
    const n = d < 1000 ? Math.round(d / 10) * 10 : Math.round(d / 100) * 100, hrs = Math.max(1, Math.round(d / 800));
    far.innerHTML = d <= 60 ? `<span>🏠 That's near you in ${picker(h)}!</span>`
      : `<span>🏠 From ${picker(h)} it's about <b>${n.toLocaleString("en-IN")} km</b>${d > 400 ? ` · ✈️ about ${hrs} hour${hrs > 1 ? "s" : ""} by plane` : ""}</span>`;
  }
  function drawMap(fig) {
    worldDefs();
    const hi = (fig.dataset.c || "").split("|").filter((n) => shapes[n]);
    const pin = fig.dataset.lat ? proj(+fig.dataset.lon, +fig.dataset.lat) : null;
    $(".map", fig).innerHTML = `<svg viewBox="${WORLDBOX().join(" ")}" preserveAspectRatio="xMidYMid meet">
      <rect class="sea" x="-1000" y="-1000" width="3000" height="3000"/><use href="#rp-world"/>
      ${hi.map((n) => `<path class="hi" d="${shapes[n].d}" vector-effect="non-scaling-stroke"/>`).join("")}
      <path class="trip" vector-effect="non-scaling-stroke"/><g class="me" hidden><g class="sc"><circle class="dot" r="6"/></g></g>
      ${pin ? `<g transform="translate(${pin[0]} ${pin[1]})"><g class="sc"><circle class="ring" r="9"/><circle class="dot" r="7"/></g></g>` : ""}
      <g class="lps"></g></svg>`;
    scale($("svg", fig), WORLDBOX());
    homeOn(fig);
  }
  function mapIn(fig) {
    if (!WD) return;
    drawMap(fig);
    if (fig.classList.contains("wide")) { lobbyPins(fig); return; }
    (fig.dataset.c || "").split("|").filter(Boolean).forEach((c) => addTo("lands", c, 300)); award();
    setTimeout(() => zoom(fig, target(fig), 1800), calm() ? 0 : 500);
    $(".zoom", fig).addEventListener("click", (e) => {
      const whole = fig.dataset.view === WORLDBOX().join(" ");
      zoom(fig, whole ? target(fig) : WORLDBOX(), 1200);
      e.currentTarget.textContent = whole ? "🌍 Whole world" : "🔍 Zoom in";
    });
  }
  document.addEventListener("change", (e) => {
    if (!e.target.matches(".where select.home")) return;
    store.set("home", e.target.value || null);
    $$(".where").forEach((f) => { if (!$("svg", f)) return; homeOn(f); if (!f.classList.contains("wide")) zoom(f, target(f), 900); });
    const sel = $(`.where select.home`); if (sel) sel.focus();
  });
  // the lobby's map: one pin per place, the stories behind it underneath
  let band = null;
  function lobbyPins(fig) {
    const svg = $("svg", fig), list = $(".pinlist", fig), vb = WORLDBOX();
    const near = 26 * Math.max(vb[2] / (svg.clientWidth || 340), vb[3] / (svg.clientHeight || 170));
    const groups = [];                                       // pins closer than a fingertip on screen share one
    JSON.parse(fig.dataset.pins).filter((p) => !band || p.b === band).forEach((p) => {
      const xy = proj(p.lon, p.lat), g = groups.find((g) => Math.hypot(g.xy[0] - xy[0], g.xy[1] - xy[1]) < near);
      if (g) g.items.push(p); else groups.push({ xy, items: [p] });
    });
    const places = (g) => [...new Set(g.items.map((p) => p.place))];
    $(".lps", svg).innerHTML = groups.map((g, i) => `<g class="lp" tabindex="0" role="button" data-g="${i}"
        aria-label="${g.items.length} ${g.items.length > 1 ? "stories" : "story"}: ${esc(places(g).join(", "))}"
        transform="translate(${g.xy[0]} ${g.xy[1]})"><g class="sc"><circle class="hit" r="18"/><circle class="ring" r="11"/><circle class="dot" r="10"/>
        <text class="n" y="3.5" text-anchor="middle">${g.items.length}</text></g></g>`).join("");
    scale(svg, vb);
    list.innerHTML = groups.length ? "" : "<p>No stories with a place for this age today.</p>";
    const open = (i) => {
      $$(".lp", svg).forEach((x) => x.classList.toggle("on", +x.dataset.g === i));
      list.innerHTML = `<p><b>📍 ${esc(places(groups[i]).join(" · "))}</b></p><ul>${groups[i].items.map((p) =>
        `<li><a href="${esc(p.u)}">${esc(p.h)}</a><small>📍 ${esc(p.place)} · ${esc(p.p)} · ${esc(p.b)}</small></li>`).join("")}</ul>`;
    };
    $$(".lp", svg).forEach((x) => {
      x.addEventListener("click", () => open(+x.dataset.g));
      x.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(+x.dataset.g); } });
    });
  }

  // ---------------------------------------------------------------- things that move when they come into view
  function grow(chart) {
    chart.classList.add("on");
    $$("b[data-v]", chart).forEach((b) => {
      const v = +b.dataset.v, dp = (b.dataset.v.split(".")[1] || "").length, t0 = performance.now();
      if (calm()) return;
      const step = (now) => { const f = Math.min(1, (now - t0) / 1200), e = 1 - Math.pow(1 - f, 3);
        b.textContent = (v * e).toFixed(dp); if (f < 1) requestAnimationFrame(step); };
      requestAnimationFrame(step);
    });
  }
  const watch = "IntersectionObserver" in window ? new IntersectionObserver((es) => es.forEach((e) => {
    const el = e.target;
    if (el.classList.contains("scene")) { el.classList.toggle("still", !e.isIntersecting); return; }
    if (!e.isIntersecting) return;
    watch.unobserve(el);
    if (el.classList.contains("chart")) grow(el);
    else if (el.classList.contains("where")) mapIn(el);
    else { el.classList.add("seen"); if (el.classList.contains("end")) { confetti(); paperDone(); } }
  }), { threshold: 0.2 }) : null;
  const watchAll = (sel) => $$(sel).forEach((el) => {
    if (watch) watch.observe(el); else if (el.classList.contains("chart")) grow(el); else if (el.classList.contains("where")) mapIn(el); else el.classList.add("seen");
  });
  watchAll(".scene"); watchAll(".chart"); watchAll(".where");
  function confetti() {
    if (calm()) return;
    const c = document.createElement("canvas"), r = window.devicePixelRatio || 1; c.className = "confetti"; document.body.appendChild(c);
    const W = c.width = innerWidth * r, H = c.height = innerHeight * r, x = c.getContext("2d");
    const cols = ["#E2584D", "#F4B400", "#007C89", "#2E7D4F", "#6B5BD2", "#2B83C6"];
    const ps = Array.from({ length: 160 }, () => ({ x: W / 2 + (Math.random() - .5) * W * .4, y: H * .45, vx: (Math.random() - .5) * 18 * r,
      vy: (-Math.random() * 16 - 6) * r, w: (Math.random() * 6 + 5) * r, c: cols[Math.floor(Math.random() * cols.length)], a: Math.random() * 6, s: Math.random() * .3 - .15 }));
    const t0 = performance.now();
    const step = (now) => {
      x.clearRect(0, 0, W, H);
      ps.forEach((p) => { p.vy += .45 * r; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.a += p.s;
        x.save(); x.translate(p.x, p.y); x.rotate(p.a); x.fillStyle = p.c; x.fillRect(-p.w / 2, -p.w / 4, p.w, p.w / 2); x.restore(); });
      if (now - t0 < 2600) requestAnimationFrame(step); else c.remove();
    };
    requestAnimationFrame(step);
  }


  // ---------------------------------------------------------------- an app on the home screen, that works offline
  if ("serviceWorker" in navigator && window.isSecureContext && SELF)
    navigator.serviceWorker.register(SELF.replace(/play\.js(\?.*)?$/, "sw.js")).catch(() => {});
  const inst = $(".install");
  if (inst && !(window.matchMedia && matchMedia("(display-mode: standalone)").matches) && !navigator.standalone) {
    let ask = null;
    window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); ask = e; inst.hidden = false; $(".add", inst).hidden = false; });
    $(".add", inst).addEventListener("click", () => {
      if (!ask) return; ask.prompt(); ask.userChoice.finally(() => { ask = null; inst.hidden = true; });
    });
    if (/iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)) {
      inst.hidden = false; $(".ios", inst).hidden = false;
    }
  }

  // ---------------------------------------------------------------- my reading: streaks and badges, kept on this device
  const ymd = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  const addTo = (k, v, cap) => { const a = store.get(k, []); if (a.includes(v)) return false; a.push(v); store.set(k, a.slice(-(cap || 1000))); return true; };
  const count = (k) => store.get(k, []).length;
  function streak() {
    const days = new Set(store.get("days", [])), d = new Date(); let n = 0;
    if (!days.has(ymd(d))) d.setDate(d.getDate() - 1);         // not read yet today: yesterday's streak still counts
    while (days.has(ymd(d))) { n++; d.setDate(d.getDate() - 1); }
    return n;
  }
  const BADGES = [
    ["first", "📰", "First paper", "Read a whole paper", () => count("read") >= 1],
    ["shelf", "📚", "Bookworm", "Read 10 papers", () => count("read") >= 10],
    ["fire3", "🔥", "On fire", "Read 3 days in a row", () => streak() >= 3],
    ["week", "🌟", "Super week", "Read 7 days in a row", () => streak() >= 7],
    ["month", "🏆", "News champion", "Read 30 days in a row", () => streak() >= 30],
    ["maps", "🗺️", "Map explorer", "See stories in 10 countries", () => count("lands") >= 10],
    ["words", "🔤", "Word wizard", "Tap 15 new words", () => count("words") >= 15],
    ["ears", "🔊", "Good listener", "Hear 5 stories read aloud", () => store.get("heard", 0) >= 5],
    ["quiz", "🧠", "Quiz champ", "Get 3 stars on 3 quizzes", () => count("3s-quiz") >= 3],
    ["facts", "🕵️", "Fact detective", "Get 3 stars on 3 Fact or fiction games", () => count("3s-facts") >= 3],
    ["match", "🧩", "Perfect match", "Get 3 stars on 3 matching games", () => count("3s-words") >= 3],
  ];
  function award() {
    const have = store.get("badges", {}), fresh = BADGES.filter((b) => !have[b[0]] && b[4]());
    if (!fresh.length) return;
    fresh.forEach((b) => { have[b[0]] = ymd(new Date()); });
    store.set("badges", have);
    const t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status");
    t.innerHTML = fresh.map((b) => `<p><span class="bi" aria-hidden="true">${b[1]}</span><span><small>New badge!</small><b>${esc(b[2])}</b></span></p>`).join("");
    document.body.appendChild(t);
    setTimeout(() => t.classList.add("bye"), 3800); setTimeout(() => t.remove(), 4400);
    shelf();
  }
  function paperDone() {
    const issue = $(".issue"); if (!issue) return;
    addTo("days", ymd(new Date()), 400); addTo("read", issue.dataset.key, 2000);
    award();
    const s = streak(), el = $(".end .streak");
    if (el) el.textContent = s > 1 ? `🔥 ${s} days in a row! Come back tomorrow to make it ${s + 1}.` : "🔥 Your reading streak has started. Come back tomorrow!";
  }
  function shelf() {
    const box = $("#badges"); if (!box) return;
    const have = store.get("badges", {}), s = streak(), today = store.get("days", []).includes(ymd(new Date()));
    box.innerHTML = `<h2>My reading <span>On this device</span></h2><div class="st"><span class="flame${s ? "" : " off"}" aria-hidden="true">🔥</span>
      <p><b>${s ? `${s}-day streak` : "No streak yet"}</b><br><span>${s && !today ? "Read a paper today to keep it going!"
        : s ? "You've read today. See you tomorrow!" : "Read a whole paper to start one."}</span></p>
      <p class="n"><b>${count("read")}</b><br><span>${count("read") === 1 ? "paper" : "papers"} read</span></p></div>
      <details${location.hash === "#badges" ? " open" : ""}><summary>My badges: ${Object.keys(have).length} of ${BADGES.length}</summary>
      <ul class="shelf">${BADGES.map((b) => `<li class="${have[b[0]] ? "got" : ""}"><span class="bi" aria-hidden="true">${have[b[0]] ? b[1] : "🔒"}</span>
        <b>${esc(b[2])}</b><small>${have[b[0]] ? "Earned!" : esc(b[3])}</small></li>`).join("")}</ul></details>`;
  }
  shelf();

  // ---------------------------------------------------------------- the lobby: who's reading?
  const whos = $$(".who");
  if (whos.length) {
    const pick = (b) => {
      store.set("band", b); band = b;
      whos.forEach((w) => w.setAttribute("aria-pressed", String(w.dataset.band === b)));
      $$(".tile").forEach((t) => { t.hidden = !!b && t.dataset.band !== b; });
      $$(".where.wide").forEach((f) => { if ($("svg", f)) lobbyPins(f); });
      const older = b && !/6–8|9–11/.test(b);               // the story so far, at the reader's level
      $$(".bigstory").forEach((a) => { a.href = older ? a.dataset.old : a.dataset.young; });
    };
    whos.forEach((w) => w.addEventListener("click", () => pick(w.dataset.band)));
    pick(store.get("band", ""));
    return;
  }

  // ---------------------------------------------------------------- read aloud, sentence by sentence
  const speech = "speechSynthesis" in window ? window.speechSynthesis : null;
  let reading = null;
  const voice = () => {
    const vs = speech.getVoices().filter((v) => /^en/i.test(v.lang));
    return vs.find((v) => /en-IN/i.test(v.lang) && v.localService) || vs.find((v) => v.localService) || vs[0] || null;
  };
  function stop() {
    if (speech) speech.cancel();
    $$(".s.now").forEach((s) => s.classList.remove("now"));
    $$(".read[aria-pressed='true']").forEach((b) => { b.setAttribute("aria-pressed", "false"); b.lastChild.textContent = " Read it to me"; });
    reading = null;
  }
  function say(text, onend) {
    const u = new SpeechSynthesisUtterance(text);
    const v = voice(); if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = store.get("rate", 1);
    u.onend = onend; u.onerror = onend;
    speech.speak(u);
  }
  function readCard(card, btn) {
    if (reading === card) { stop(); return; }
    stop();
    const parts = $$(".s", card).filter((x) => !x.closest("[hidden]"));   // only the version on screen
    reading = card; btn.setAttribute("aria-pressed", "true"); btn.lastChild.textContent = " Stop";
    store.set("heard", store.get("heard", 0) + 1); award();
    let i = 0;
    const next = () => {
      if (reading !== card) return;
      $$(".s.now", card).forEach((s) => s.classList.remove("now"));
      if (i >= parts.length) { stop(); return; }
      const s = parts[i++]; s.classList.add("now");
      s.scrollIntoView({ block: "nearest", behavior: "smooth" });
      say(s.textContent, next);
    };
    next();
  }
  $$(".read").forEach((b) => {
    if (!speech) { b.hidden = true; return; }
    b.addEventListener("click", () => readCard(b.closest(".card"), b));
  });

  const main = $(".issue");
  if (!main) return;
  const data = JSON.parse($("#data").textContent);

  // ---------------------------------------------------------------- the easier version of a story (papers for 12+)
  function easyView(card, on) {
    $$(".v-orig", card).forEach((x) => { x.hidden = on; });
    $$(".v-easy", card).forEach((x) => { x.hidden = !on; });
    const b = $(".easy", card);
    b.setAttribute("aria-pressed", String(on));
    b.lastChild.textContent = on ? "Original version" : "Easier version";
  }
  $$(".card .easy").forEach((b) => {
    const card = b.closest(".card");
    easyView(card, store.get("easy", false));                 // the reader's last choice
    b.addEventListener("click", () => {
      stop();
      const on = b.getAttribute("aria-pressed") !== "true";
      easyView(card, on); store.set("easy", on);
    });
  });

  // ---------------------------------------------------------------- tap a word
  const pop = $("#pop");
  let popWord = null;
  function openWord(i) {
    const v = data.vocab[i]; if (!v) return;
    popWord = v;
    if (addTo("words", v.word.toLowerCase(), 2000)) award();
    $("h3", pop).textContent = v.word; $(".m", pop).textContent = v.meaning;
    $(".t", pop).textContent = v.today ? "Today: " + v.today : "";
    $(".say", pop).hidden = !speech;
    pop.hidden = false; $(".x", pop).focus();
  }
  $$("mark.w").forEach((m) => {
    m.addEventListener("click", () => openWord(+m.dataset.w));
    m.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openWord(+m.dataset.w); } });
  });
  $(".x", pop).addEventListener("click", () => { pop.hidden = true; });
  $(".say", pop).addEventListener("click", () => { stop(); if (popWord) say(popWord.word + ". " + popWord.meaning, () => {}); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") pop.hidden = true; });

  // ---------------------------------------------------------------- one story per screen (younger readers)
  const cards = $$("#read .card");
  let at = 0, show = null;
  if (main.dataset.mode === "cards") {
    const bar = $(".track i"), walker = $(".walker"), count = $(".count"), last = cards.length - 1;
    show = (n) => {
      stop(); const was = at; at = Math.max(0, Math.min(last, n));
      cards.forEach((c, i) => { c.classList.toggle("on", i === at); c.classList.remove("in-r", "in-l"); });
      if (at !== was) cards[at].classList.add(at > was ? "in-r" : "in-l");
      const pct = last ? at / last * 100 : 100;
      bar.style.width = pct + "%"; walker.style.left = pct + "%";
      count.textContent = at === last ? "Done! 🎉" : `${at + 1} of ${last}`;
      $(".prev").style.visibility = at ? "visible" : "hidden";
      $(".next").style.visibility = at < last ? "visible" : "hidden";
      if (at === last && was !== last) { confetti(); paperDone(); }
      window.scrollTo({ top: 0 });
    };
    document.addEventListener("rp-show", (e) => show(e.detail));
    $(".prev").addEventListener("click", () => show(at - 1));
    $(".next").addEventListener("click", () => show(at + 1));
    let x0 = null;
    $("#read").addEventListener("touchstart", (e) => { x0 = e.target.closest(".where") ? null : e.touches[0].clientX; }, { passive: true });
    $("#read").addEventListener("touchend", (e) => {
      if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) > 60) show(at + (dx < 0 ? 1 : -1));
    });
    document.addEventListener("keydown", (e) => {
      if ($("#read").hidden || e.target.matches("select")) return;
      if (e.key === "ArrowRight") show(at + 1); if (e.key === "ArrowLeft") show(at - 1);
    });
    show(0);
  } else {
    watchAll("#read .card");
  }

  // ---------------------------------------------------------------- read / play tabs
  function tab(name) {
    stop();
    $$(".tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
    $("#read").hidden = name !== "read"; $("#play").hidden = name !== "play";
    if (name === "play") game();
    window.scrollTo({ top: 0 });
  }
  $$("[data-tab]").forEach((b) => b.addEventListener("click", () => tab(b.dataset.tab)));

  // ---------------------------------------------------------------- games: a menu, then match pairs, quiz, fact or fiction
  const shuffle = (a) => { a = a.slice(); for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const young = main.dataset.mode === "cards";
  const box = $("#game");
  const starsFor = (right, total) => (right === total ? 3 : right / total >= 0.6 ? 2 : 1);
  const best = (name) => store.get("stars-" + main.dataset.key + "-" + name, 0);
  const keep = (name, n) => {
    store.set("stars-" + main.dataset.key + "-" + name, Math.max(n, best(name)));
    if (n === 3 && addTo("3s-" + name, main.dataset.key)) award();
  };
  const GAMES = [];
  if (data.vocab.length >= 2) GAMES.push({ id: "words", ic: "🔤", name: "Word match", sub: "Match each new word to its meaning", run: () => match("words") });
  else if (data.stories.length >= 2) GAMES.push({ id: "words", ic: "📰", name: "Story match", sub: "Match each headline to its story", run: () => match("words") });
  if (data.quiz.length) GAMES.push({ id: "quiz", ic: "❓", name: "Quiz", sub: data.quiz.length + " questions about today's paper", run: quiz });
  if (data.facts.length) GAMES.push({ id: "facts", ic: "🕵️", name: "Fact or fiction?", sub: "True, or not true?", run: facts });
  function game() {
    stop();
    box.className = "card game";
    if (!GAMES.length) { box.innerHTML = "<p>No game for this issue. Come back tomorrow!</p>"; return; }
    if (GAMES.length === 1) { GAMES[0].run(); return; }
    box.innerHTML = `<h2>Pick a game</h2><p class="how">Play one, or all three.</p><div class="menu">${GAMES.map((g, i) =>
      `<button type="button" data-g="${i}"><span class="ic" aria-hidden="true">${g.ic}</span><span><b>${g.name}</b><small>${g.sub}</small></span>
       <span class="got" aria-label="${best(g.id)} stars">${best(g.id) ? "★".repeat(best(g.id)) : ""}</span></button>`).join("")}</div>`;
    $$(".menu button", box).forEach((b) => b.addEventListener("click", () => GAMES[+b.dataset.g].run()));
  }
  const back = () => (GAMES.length > 1 ? '<button type="button" class="back">← All games</button>' : "");
  const wireBack = () => { const b = $(".back", box); if (b) b.addEventListener("click", game); };
  function readAgain(card) {
    if (card < 0) return "";
    return ` <a href="#" data-card="${card}">Read it again</a>`;
  }
  box.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-card]"); if (!a) return;
    e.preventDefault(); tab("read");
    const i = +a.dataset.card;
    if (show) { if (cards[i]) show(i); }
    else { const c = $$("#read .card")[i]; if (c) c.scrollIntoView({ behavior: "smooth" }); }
  });
  function finishText(right, total, name) {
    const n = starsFor(right, total); keep(name, n);
    if (n === 3) setTimeout(confetti, 200);
    return `<p class="cheer" role="status">${right === total ? "Every one right! 🎉" : `You got ${right} out of ${total}! 🎉`}</p>
      <p class="stars" aria-label="${n} stars">${"★".repeat(n)}${"☆".repeat(3 - n)}</p>
      <button type="button" class="big again">Play again</button> ${back()}`;
  }
  function match(name) {
    let pairs, title, how;
    if (data.vocab.length >= 2) {
      pairs = data.vocab.slice(0, young ? 4 : 6).map((v) => [v.word, v.meaning]);
      title = "Word match"; how = "Tap a word, then tap what it means.";
    } else {
      pairs = data.stories.slice(0, 4).map((s) => [s.headline, s.first]);
      title = "Story match"; how = "Tap a headline, then tap the sentence that starts its story.";
    }
    box.innerHTML = `${back()}<h2>${title}</h2><p class="how">${how}</p>
      <div class="pairs"><div class="col w"></div><div class="col m"></div></div>
      <p class="cheer" role="status"></p><div class="end2"></div>`;
    wireBack();
    const L = $(".w", box), R = $(".m", box), cheer = $(".cheer", box);
    let sel = null, done = 0, misses = 0;
    const mk = (text, i, side) => {
      const b = document.createElement("button"); b.type = "button"; b.textContent = text; b.dataset.i = i;
      b.addEventListener("click", () => tap(b, side)); return b;
    };
    shuffle(pairs.map((p, i) => [p[0], i])).forEach(([t, i]) => L.appendChild(mk(t, i, "L")));
    shuffle(pairs.map((p, i) => [p[1], i])).forEach(([t, i]) => R.appendChild(mk(t, i, "R")));
    const praise = ["Yes!", "Great!", "You got it!", "Brilliant!", "Spot on!"];
    function tap(b, side) {
      if (b.classList.contains("ok")) return;
      if (!sel || sel.side === side) { $$("button.sel", box).forEach((x) => x.classList.remove("sel")); sel = { b, side }; b.classList.add("sel"); return; }
      const a = sel.b; sel = null; a.classList.remove("sel");
      if (a.dataset.i === b.dataset.i) {
        a.classList.add("ok"); b.classList.add("ok"); done++; cheer.textContent = praise[done % praise.length];
        if (done === pairs.length) {
          const n = misses === 0 ? 3 : misses <= 2 ? 2 : 1; keep(name, n);
          cheer.textContent = n === 3 ? "All matched, first time! 🎉" : "All matched! 🎉";
          if (n === 3) confetti();
          $(".end2", box).innerHTML = `<p class="stars" aria-label="${n} stars">${"★".repeat(n)}${"☆".repeat(3 - n)}</p><button type="button" class="big again">Play again</button> ${back()}`;
          $(".again", box).onclick = () => match(name); $$(".end2 .back", box).forEach((x) => x.addEventListener("click", game));
        }
      } else {
        misses++; [a, b].forEach((x) => { x.classList.add("no"); setTimeout(() => x.classList.remove("no"), 400); });
        cheer.textContent = "Not quite. Try another one!";
      }
    }
  }
  function steps(items, name, render) {
    let i = 0, right = 0;
    const show = () => {
      if (i >= items.length) {
        box.innerHTML = finishText(right, items.length, name);
        $(".again", box).onclick = () => steps(items, name, render); $$(".back", box).forEach((x) => x.addEventListener("click", game));
        return;
      }
      render(items[i], i, items.length, (ok) => { if (ok) right++; }, () => { i++; show(); });
    };
    show();
  }
  function speakBtn(text) { return speech ? `<button type="button" class="read say1" data-say="${esc(text)}">🔊 Hear it</button>` : ""; }
  box.addEventListener("click", (e) => { const b = e.target.closest(".say1"); if (b) { stop(); say(b.dataset.say, () => {}); } });
  function quiz() {
    steps(data.quiz, "quiz", (q, i, n, score, next) => {
      box.innerHTML = `${back()}<p class="qn">Question ${i + 1} of ${n}</p>${young ? speakBtn(q.q + " " + q.options.join(". ")) : ""}
        <p class="q">${esc(q.q)}</p><div class="opts">${q.options.map((o, k) => `<button type="button" data-k="${k}">${esc(o)}</button>`).join("")}</div>
        <div class="fb" role="status"></div>`;
      wireBack();
      $$(".opts button", box).forEach((b) => b.addEventListener("click", () => {
        const k = +b.dataset.k, ok = k === q.answer;
        score(ok);
        $$(".opts button", box).forEach((x) => { x.disabled = true; if (+x.dataset.k === q.answer) x.classList.add("ok"); });
        if (!ok) b.classList.add("no");
        $(".fb", box).innerHTML = `<p class="why"><b>${ok ? "Yes! " : "Not quite. "}</b>${esc(q.why)}${ok ? "" : readAgain(q.card)}</p>
          <p><button type="button" class="big go nx">${i + 1 < n ? "Next question →" : "See my score"}</button></p>`;
        $(".nx", box).addEventListener("click", next);
      }));
    });
  }
  function facts() {
    steps(data.facts, "facts", (f, i, n, score, next) => {
      box.innerHTML = `${back()}<p class="qn">Claim ${i + 1} of ${n}</p>${young ? speakBtn(f.claim) : ""}
        <p class="claim">${esc(f.claim)}</p><div class="opts tf"><button type="button" data-v="1">✅ True</button><button type="button" data-v="0">❌ Not true</button></div>
        <div class="fb" role="status"></div>`;
      wireBack();
      $$(".opts button", box).forEach((b) => b.addEventListener("click", () => {
        const said = b.dataset.v === "1", ok = said === f.true;
        score(ok);
        $$(".opts button", box).forEach((x) => { x.disabled = true; if ((x.dataset.v === "1") === f.true) x.classList.add("ok"); });
        if (!ok) b.classList.add("no");
        $(".fb", box).innerHTML = `<p class="why"><b>${ok ? "Right! " : "Not quite. "}</b>It's ${f.true ? "true" : "not true"}. ${esc(f.why)}${ok ? "" : readAgain(f.card)}</p>
          <p><button type="button" class="big go nx">${i + 1 < n ? "Next →" : "See my score"}</button></p>`;
        $(".nx", box).addEventListener("click", next);
      }));
    });
  }
  if (location.hash === "#play") tab("play");
  else if (location.hash.startsWith("#s-")) {               // from a pin on the lobby's map
    const c = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (c && show) show(cards.indexOf(c)); else if (c) setTimeout(() => c.scrollIntoView({ block: "start" }), 50);
  }
})();
"""
