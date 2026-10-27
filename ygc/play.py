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

from . import brand, brief, edition, scenes, site, stats, threads, world, pwa, navigation, story_timeline, listen
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
def thumb(story, href, w=None):
    """The small picture beside a paper on the lobby: its lead story's moving picture, a little real map zoomed
    to where it happens (`w`, drawn by play.js from world.js), else the section's icon."""
    _, icon, tone = desk(re.sub(r"(?i)\b(top|big|lead) story\b", "", plain(story.get("kicker", ""))))
    if icon == "📰" and (story.get("map") or story.get("chart")):    # a map's whole picture won't fit this small
        icon, tone = ("🌍", "teal") if story.get("map") else ("📊", "sun")
    if story.get("illustration"):
        pic = scenes.scene(story["illustration"].get("motif", ""), plain(story["illustration"].get("caption", "")))
    elif w:
        pic = (f'<span class="mini" data-c="{E("|".join(w["countries"]))}" data-lat="{w["lat"]}" data-lon="{w["lon"]}" '
               f'data-box="{w["box"]}"><span class="ic">{icon}</span></span>')
    else:
        pic = f'<span class="ic">{icon}</span>'
    return f'<a class="thumb t-{tone}" href="{href}" tabindex="-1" aria-hidden="true">{pic}</a>'


def top_figure(story, w):
    """The picture at the top of a story card: its real map, moving picture, or growing chart."""
    if story.get("map"):
        return where_html(w) if w else scene_html("map", story["map"])
    if story.get("illustration"):
        return scene_html("illustration", story["illustration"])
    if story.get("chart"):
        return chart_html(story["chart"])
    return ""


_STOP = {"after", "about", "again", "their", "there", "these", "those", "which", "while", "with", "from", "into", "over",
         "than", "that", "this", "what", "when", "where", "more", "most", "says", "said", "will", "have", "been", "were", "they"}


_HARSH = re.compile(r"\b(kill\w*|die[sd]?|dying|dead|deaths?|wound\w*|injur\w*|bomb\w*|shot|shoot\w*|"
                   r"murder\w*|massacre\w*|casualt\w*|corpses?|blood\w*)\b", re.I)


def _words(text):
    return {w for w in re.findall(r"[a-z]{4,}", plain(text).lower()) if w not in _STOP}


ORDER_EVENTS = {"Ages 6–8": 3, "Ages 9–11": 4, "Ages 12–14": 4, "Ages 15+": 5}


def order_events(t, level, k):
    """Put it in order: k events from a big story's timeline at this reading level, each on a different day
    (so there is one right order), spread over its latest news, oldest first. Lines about deaths or injuries
    are left out of the game."""
    by_day = {}
    for e in t.get("timeline") or []:
        text = plain(e.get(level) or "")
        if text and e.get("date") and not _HARSH.search(text):
            by_day[e["date"]] = {"text": text, "date": e["date"], "when": plain(e.get("when") or "")}
    days = [by_day[d] for d in sorted(by_day)][-8:]
    if len(days) < 3:
        return []
    k = min(k, len(days))
    return [days[round(i * (len(days) - 1) / (k - 1))] for i in range(k)]


def quiz_pool(ed, issue):
    """This issue's quiz questions, each with its story's headline and place: other papers' stretch and easier questions."""
    play = issue.get("play") if isinstance(issue.get("play"), dict) else {}
    blocks = issue.get("blocks", {})
    given = {w.get("story"): w for w in play.get("where") or [] if isinstance(w, dict)}
    out = []
    for q in play.get("quiz") or []:
        b = blocks.get(q.get("story")) if isinstance(q, dict) else None
        if isinstance(b, dict) and q.get("q") and len(q.get("options") or []) == 3 and q.get("answer") in (0, 1, 2):
            out.append({"q": plain(q["q"]), "options": [plain(o) for o in q["options"]], "answer": q["answer"],
                        "why": plain(q.get("why", "")), "h": plain(b.get("headline", "")),
                        "place": plain((given.get(q["story"]) or {}).get("place", "")), "paper": ed["name"]})
    return out


def sections(ed, issue, date, chips=None, stretch=None, orders=None):
    """[(kind, block id, html, colour)] in reading order, the data the games need, and where each story happens.
    `chips`: {story id: thread history or background link} for ongoing stories."""
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
{story_timeline.render(chips[bid], bid) if bid in chips else ""}
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
    where = [{"place": place_name(w), "lat": w["lat"], "lon": w["lon"], "countries": w["countries"],
              "names": [world.DISPLAY.get(c, c) for c in w["countries"]], "h": plain(h), "card": at.get(bid, -1)}
             for bid, h, w in places]
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    numbers = [{"q": plain(n["q"]), "answer": n["answer"], "min": n["min"], "max": n["max"],
                "prefix": plain(n.get("prefix") or ""), "unit": plain(n.get("unit") or ""), "why": plain(n.get("why", "")),
                "card": at.get(n.get("story"), -1)}
               for n in play.get("numbers") or [] if isinstance(n, dict) and n.get("q")
               and all(num(n.get(k)) for k in ("answer", "min", "max")) and n["min"] < n["answer"] < n["max"]]
    mine = [(at[bid], _words(blocks[bid].get("headline", "")), plain((given.get(bid) or {}).get("place", "")).lower())
            for bid in edition.story_blocks(ed) if isinstance(blocks.get(bid), dict) and bid in at]

    def related(cands, gentle=False):     # other papers' questions about the same story: same place, or 2 headline words
        found, seen = [], set()
        for c in cands or []:
            if gentle and _HARSH.search(" ".join([c["q"], c["why"]] + c["options"])):
                continue                  # an older paper's question can be blunter than a younger reader's paper
            w, place = _words(c["h"]), c["place"].lower()
            hit = next((card for card, mw, mp in mine if (place and place == mp) or len(w & mw) >= 2), None)
            if hit is not None and c["q"].lower() not in seen:
                seen.add(c["q"].lower())
                found.append({k: c[k] for k in ("q", "options", "answer", "why", "paper")} | {"card": hit})
        return found[:6]
    stretch = stretch or {}
    return out, {"vocab": vocab, "stories": [s for s in stories if s["headline"] and s["first"]], "quiz": quiz, "facts": facts,
                 "where": where, "numbers": numbers, "harder": related(stretch.get("harder"), gentle=True),
                 "easier": related(stretch.get("easier")),
                 "order": [{"title": o["title"], "href": o["href"], "card": at.get(o["bid"], -1), "events": o["events"]}
                           for o in orders or [] if len(o["events"]) >= 3]}, places


def issue_page(cfg, ed, band, issue, date, others, chips=None, stretch=None, orders=None):
    """The page, and where its stories happen (for the lobby's map). `stretch`: {"harder", "easier"}: quiz
    questions from the same days' papers one age up and one age down, for adaptive play."""
    secs, data, places = sections(ed, issue, date, chips, stretch, orders)
    cards = "".join(f'<section class="card {k} t-{tone}" id="s-{E(b)}" data-i="{i}" data-b="{E(b)}"><button type="button" class="read" aria-label="Read this to me">'
                    f'<span aria-hidden="true">🔊</span> Read it to me</button>{h}</section>' for i, (k, b, h, tone) in enumerate(secs))
    d = dt.date.fromisoformat(date)
    mode = "cards" if band in CARD_BANDS else "scroll"
    earlier = "".join(f'<option value="{o}.html"{" selected" if o == date else ""}>{dt.date.fromisoformat(o):%a %d %b}</option>'
                      for o in others)
    body = f'''<header class="bar"><a class="home" href="../index.html#today">← Back to Today</a>
<div class="tools" role="toolbar" aria-label="Reading settings">
<button type="button" data-act="smaller" aria-label="Smaller text">A−</button><button type="button" data-act="bigger" aria-label="Bigger text">A+</button>
<button type="button" data-act="night" aria-label="Night mode">🌙</button>
<select data-act="rate" aria-label="Reading speed"><option value="0.8">Slow</option><option value="1" selected>Normal</option><option value="1.2">Fast</option></select>
</div></header>
<main class="issue" data-mode="{mode}" data-key="{E(ed['id'])}-{date}" data-band="{E(band)}">
<div class="title"><h1>{E(ed["name"])}</h1><p>{d:%A %d %B %Y} · No. {E(str(issue.get("issue", "")))}</p>
<button type="button" id="listen-edition" class="read-edition">{navigation.icon("headphones")} Listen to this edition</button>
<nav class="tabs" role="tablist"><button type="button" role="tab" data-tab="read" aria-selected="true">Read</button><button type="button" role="tab" data-tab="play" aria-selected="false">Play</button></nav></div>
<div id="read" role="tabpanel">
<aside id="listen-resume" hidden><span>Pick up where you left off.</span>
<button type="button" data-listen="continue">Continue listening</button><button type="button" data-listen="restart">Start again</button></aside>
<div class="trail" aria-hidden="true"><div class="track"><i></i><b class="walker">🚀</b><b class="flag">🏁</b></div><span class="count"></span></div>
{cards}
<section class="card end" data-i="{len(secs)}">{brand.inline("owl cheer")}<h2>You read today's paper! 🎉</h2><p class="streak" role="status"></p><p>Ready for a game?</p>
<button type="button" class="big go" data-tab="play">Play now</button>
<p class="mine"><a href="../index.html#badges">See my pebble tower and badges</a></p></section>
<div class="steps"><button type="button" class="big prev">← Back</button><button type="button" class="big next">Next →</button></div>
</div>
<div id="play" role="tabpanel" hidden><div id="game"></div></div>
<p class="older"><label>Other days: <select onchange="location.href=this.value">{earlier}</select></label>
· <a href="../../e/{E(ed['id'])}/index.html">Print this paper (for grown-ups)</a></p>
</main>
<section id="listen-player" aria-label="Audio player" hidden>
<div class="listen-heading"><p class="listen-title"></p><span class="listen-time"></span></div>
<div class="listen-controls"><button type="button" data-listen="previous" aria-label="Previous sentence">←</button><button type="button" data-listen="toggle">Pause</button><button type="button" data-listen="next" aria-label="Next sentence">→</button>
<input type="range" min="0" max="100" value="0" step="0.1" aria-label="Listening progress">
<details class="listen-more"><summary aria-label="More audio controls">⋯</summary><div><button type="button" data-listen="auto-follow" aria-pressed="true">Follow text: on</button><button type="button" data-listen="restart">Start again</button><button type="button" data-listen="close" aria-label="Close audio player">Close player</button></div></details></div>
<button type="button" class="listen-return" data-listen="follow" hidden>Back to listening</button>
<p class="listen-status" role="status"></p></section>
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


def child_nav(root, here="today", desktop=False, app=False):
    tabs = [("home", "index.html", "house", "Home"),
            ("today", "play/index.html#today", "newspaper", "Today"),
            ("explore", "play/index.html#explore", "compass", "Explore"),
            ("me", "play/index.html#me", "sprout", "My Pebbles")]
    if app:                                         # the app build: Listen (the car-ride brief and papers read aloud)
        tabs.insert(3, ("listen", "play/listen.html", "headphones", "Listen"))
    classes = "childnav desktopnav noprint" if desktop else "tabbar childnav noprint"
    return f'<nav class="{classes}" aria-label="Main navigation">' + "".join(
        f'<a href="{root}{href}" data-view="{key}"' + (' aria-current="page"' if key == here else '')
        + f'><span aria-hidden="true">{navigation.icon(icon)}</span>{label}</a>' for key, href, icon, label in tabs) + '</nav>'


def shell(cfg, title, body, root="", here="today"):
    desktop_brand = (f'<a class="desktopbrand" href="{root}play/index.html">{brand.inline("owl")}Read &amp; Play</a>'
                     if '<header class="bar lb">' not in body else '')
    app = bool(cfg.get("kids_mode"))
    body = body.replace('</header>', desktop_brand + child_nav(root, here, desktop=True, app=app) + '</header>', 1)
    if '<header class="bar lb">' in body:
        body = body.replace('</header>', '</header>' + pwa.tablet_prompt(), 1)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="Read today's news, hear it read aloud and play a game. For children, from {E(cfg['title'])}.">
{site.fonts(root)}
{pwa.head(cfg, root)}
<link rel="icon" href="{root}play/owl.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}play/play.css?v={asset_version()}">{stats.snippet(cfg, root)}</head><body>{body}
{child_nav(root, here, app=app)}
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
    body = f'''<header class="bar"><a class="home" href="../index.html#explore">← Back to Explore</a>{switch}</header>
<main class="threadpage"><section class="card thread t-violet"><button type="button" class="read" aria-label="Read this to me">
<span aria-hidden="true">🔊</span> Read it to me</button>
<p class="kicker"><span class="desk">🧵 The story so far</span> {"Updated" if active else "Last news"} {updated:%a %d %b}</p>
<h2><span class="s">{E(t["title"])}</span></h2>
<p class="oneminute"><b>In one minute:</b> <span class="s">{clean(v["one_minute"])}</span></p>
{where_html(w) if w else ""}{timeline}{who}{qs}{worry}
<details class="grown"><summary>For grown-ups: sources</summary><ul>{src}</ul></details></section>
<p class="older"><a href="index.html">All the big stories</a></p></main>'''
    return shell(cfg, f"{t['title']}: the story so far · Read & Play", body, root="../../", here="explore")


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
    body = f'''<header class="bar"><a class="home" href="../index.html#explore">← Back to Explore</a></header>
<main class="lobby"><h1>{brand.inline("owl")}Big stories</h1><p class="lede">News that goes on for days. Catch up on what happened,
who's who, and the questions people are asking.</p><div class="big3">{rows}</div></main>'''
    return shell(cfg, f"Big stories · Read & Play", body, root="../../", here="explore")


# ------------------------------------------------------------------ an app on the home screen
def certificate(cfg):
    """A printable certificate for a badge (certificate.html?b=<badge>), filled in by play.js from what this device earned."""
    body = f'''<style>@media print{{@page{{size:landscape}}}}</style><header class="bar noprint"><a class="home" href="index.html#me">← My badges</a></header>
<main class="certpage"><div class="cert" hidden>{brand.inline("owl")}<p class="org">{E(cfg["title"]).upper()}</p>
<p class="kind">Certificate</p><p class="to">This certificate is awarded to</p><p class="nm"></p><h1 class="bn"></h1><p class="bd"></p>
<div class="ft"><span class="dt"></span><span>{E(cfg["tagline"])}</span></div></div>
<div class="ctl noprint" hidden><label>Name on the certificate <input class="name" maxlength="40" autocomplete="off"></label>
<button type="button" class="big go print">🖨️ Print certificate</button>
<p class="note">The name stays on this device. To keep a copy, choose “Save as PDF” in the print window.</p></div>
<p class="none" hidden>This badge isn't earned on this device yet. <a href="index.html#me">See my badges</a></p></main>'''
    return shell(cfg, f"Certificate · {cfg['title']}", body, root="../", here="me")


def report(cfg, names):
    """A one-page monthly report to print or save as a PDF, made by play.js from what this device kept."""
    body = f'''<header class="bar noprint"><a class="home" href="index.html#me">← Back</a></header>
<main class="reportpage"><div class="ctl noprint"><label>Month <select class="month"></select></label>
<label>Name on the report <input class="name" maxlength="40" autocomplete="off"></label>
<button type="button" class="big go print">🖨️ Print or save as PDF</button></div>
<article class="report"><div class="rhead">{brand.inline("owl")}<b>{E(cfg["title"])}</b><span class="mo"></span></div><h1 class="rt"></h1>
<div class="rbody"></div><p class="rfoot">Made on this device from what was read and played here. Nothing is sent anywhere. {E(cfg["tagline"])}</p></article>
<script id="papers" type="application/json">{json.dumps(names, ensure_ascii=False)}</script></main>'''
    return shell(cfg, f"Monthly report · {cfg['title']}", body, root="../", here="me")


def manifest(cfg):
    return pwa.manifest(cfg, legacy_reader=True)


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
  if (u.pathname.includes("/play/audio/") && r.headers.has("range")) {
    e.respondWith(caches.match(u.href).then(async (hit) => {
      if (!hit) return fetch(r);
      const match = /^bytes=(\d+)-(\d*)$/.exec(r.headers.get("range"));
      if (!match) return fetch(r);
      const bytes = await hit.arrayBuffer(), start = Number(match[1]);
      const end = match[2] ? Math.min(Number(match[2]), bytes.byteLength - 1) : bytes.byteLength - 1;
      if (start > end) return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${bytes.byteLength}` } });
      return new Response(bytes.slice(start, end + 1), { status: 206, headers: {
        "Content-Type": "audio/mpeg", "Content-Length": String(end - start + 1),
        "Content-Range": `bytes ${start}-${end}/${bytes.byteLength}`, "Accept-Ranges": "bytes"
      } });
    }));
    return;
  }
  if (r.mode === "navigate" || u.pathname.includes("/play/briefs/")) {   // pages and the car-ride brief: newest first, else the one kept
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
    pools = {}                                      # age band -> [(date, question)], for stretch and easier questions
    for eid, d, issue in every:
        pools.setdefault(audience(edition.load(eid)), []).extend((d, q) for q in quiz_pool(edition.load(eid), issue))

    def stretch_for(band, date):
        i = BANDS.index(band) if band in BANDS else -1
        near = lambda b: [q for d, q in pools.get(b, []) if abs((dt.date.fromisoformat(d) - dt.date.fromisoformat(date)).days) <= 1]
        return {"harder": near(BANDS[i + 1]) if 0 <= i < len(BANDS) - 1 else [],
                "easier": near(BANDS[i - 1]) if i > 0 else []}
    known = {t["id"]: t for t in threads.load_all()}
    bands = {eid: audience(edition.load(eid)) for eid, _, _ in every}
    names = {eid: edition.load(eid)["name"] for eid in bands}
    history = story_timeline.catalog(every, in_thread, bands, names)
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
            chips = {b: {"href": f"../threads/{thread_href(tid, level)}", "title": known[tid]["title"],
                         "updates": story_timeline.recent(history.get(tid, []), known[tid], eid, b, band, date, level)}
                     for (e, d, b), tid in in_thread.items()
                     if e == eid and d == date and tid in known}
            try:
                orders = [{"bid": b, "title": known[tid]["title"], "href": f"../threads/{thread_href(tid, level)}",
                           "events": order_events(known[tid], level, ORDER_EVENTS.get(band, 4))}
                          for (e, d, b), tid in in_thread.items() if e == eid and d == date and tid in known
                          and not (band == "Ages 6–8" and known[tid].get("younger", {}).get("worry"))]   # no war games for 6–8
                html_, places = issue_page(cfg, ed, band, issue, date, dates, chips, stretch_for(band, date), orders)
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
        if brief.wants(ed):                         # the car-ride brief: script now, audio from ygc.narration
            os.makedirs(os.path.join(pdir, "briefs"), exist_ok=True)
            for date, path in issues_of(ed)[:keep]:
                issue = json.load(open(path, encoding="utf-8"))
                if (issue.get("play") or {}).get("brief"):
                    brief.write(os.path.join(pdir, "briefs", f"{date}.json"), brief.data(ed, issue, date))
        for date, _ in issues_of(ed)[keep:]:       # older papers: their QR codes open the newest
            open(os.path.join(edir, f"{date}.html"), "w", encoding="utf-8").write(stub(cfg, ed, date, latest[0]))
        newest.append(f"{eid}/{latest[0]}.html")
        lid = next((b for b in edition.story_blocks(ed) if isinstance(latest[2]["blocks"].get(b), dict)), None)
        lead = latest[2]["blocks"].get(lid) or {}
        given = next((w for w in ((latest[2].get("play") or {}).get("where") or [])
                      if isinstance(w, dict) and w.get("story") == lid), None)       # where the paper says it happened
        u, name = f"{eid}/{latest[0]}.html", E(ed["name"])
        tiles.append((BANDS.index(band) if band in BANDS else 9, ed["name"], latest[0], f'''<article class="tile" data-band="{E(band)}" data-key="{E(eid)}-{latest[0]}">
{thumb(lead, u, None if lead.get("illustration") else where_of(lead, given))}<div class="tx"><p class="when">{name} · {dt.date.fromisoformat(latest[0]):%a %d %b}<!--NEW--><span class="done" hidden> · ✓ read</span></p>
<h2><a href="{u}">{E(latest[1])}</a></h2><div class="go2"><a class="big go" href="{u}" aria-label="Read {name}">Read</a><a class="big" href="{u}#play" aria-label="Play {name}">Play</a></div></div></article>'''))
        log(f"  play {eid}: {len(dates)} issue(s)")
    big = write_threads(pdir, cfg, known, in_thread, pages)
    fresh = max((t[2] for t in tiles), default="")
    tiles = [t[3].replace("<!--NEW-->", ' <span class="new">NEW</span>' if t[2] == fresh else "") for t in sorted(tiles)]
    big_row = ("<section class=\"bigrow\" id=\"stories\"><h2>🧵 Big stories right now <a href=\"threads/index.html\">All</a></h2><div class=\"big3\">"
               + "".join(f'''<a class="bigstory" href="threads/{thread_href(t["id"], "younger")}" data-young="threads/{thread_href(t["id"], "younger")}"
data-old="threads/{thread_href(t["id"], "older")}"><span class="ic" aria-hidden="true">🌍</span><span><b>{E(t["title"])}</b>
<small>Day {(dt.date.fromisoformat(newest_d) - dt.date.fromisoformat(t["opened"])).days + 1} · {len(t["timeline"])} updates</small></span>
{"<span class=\"new\">NEW TODAY</span>" if threads.last_news(t, ld) == newest_d else ""}</a>''' for t, ld, newest_d in big)
               + "</div></section>") if big else ""
    who = "".join(f'<button type="button" class="who" data-band="{E(b)}">{E(b.replace("Ages ", ""))}</button>' for b in BANDS)
    news_map = (f'''<section class="newsmap" id="map"><h2>🗺️ Where's the news today?</h2><p class="how">Tap a pin to see the story.</p>
<figure class="where wide" data-pins="{E(json.dumps(pins, ensure_ascii=False))}"><div class="map" role="img" aria-label="A world map with a pin for each of today's stories"></div>
<figcaption><span class="far" aria-live="polite"></span></figcaption><div class="pinlist" aria-live="polite"></div></figure></section>'''
                if pins else "")
    body = f'''<header class="bar lb"><h1><a href="index.html">{brand.inline("owl")}Read &amp; Play</a></h1>
<a class="home" href="../index.html">{navigation.icon("house")} Home</a><div class="chips" id="chips"></div></header>
<main class="lobby front"><section class="today lobby-panel" id="today" aria-labelledby="h-today"><p class="motto">The world's news, one pebble a day.</p>
<div class="pick"><h2>Who's reading? <span>How old are you?</span></h2><div class="whos">{who}<button type="button" class="who" data-band="">Show all</button></div></div>
<p class="hello" hidden><span></span> <button type="button" class="change">Change age</button></p>
<h2 id="h-today" tabindex="-1">📰 Today’s papers</h2>
<section class="brief" id="brief" data-src="briefs/latest.json" aria-label="Car-ride brief: today's news, read aloud" hidden></section><div class="tiles">{"".join(tiles)}</div></section>
<section class="side lobby-panel" id="explore" aria-labelledby="h-explore"><h2 id="h-explore" class="view-title" tabindex="-1">Explore</h2>
{big_row}{news_map}</section>
<section class="me lobby-panel" id="me" aria-labelledby="h-pebbles"><h2 id="h-pebbles" class="view-title" tabindex="-1">My Pebbles</h2><div id="corner"></div><section class="myreading" id="badges" aria-label="My reading"></section>
<div class="install" hidden><p><img class="app" src="icon-192.png" alt="" width="48" height="48"><b>Keep Read &amp; Play on your home screen.</b> It opens like an app, and
today's papers work without the internet.</p><button type="button" class="big go add" hidden>Add to home screen</button>
<p class="ios" hidden>On an iPhone or iPad: tap <b>Share</b> <span aria-hidden="true">⬆️</span>, then <b>Add to Home Screen</b>.</p></div>
<p class="note"><a href="../index.html">← {E(cfg["title"])} (grown-ups)</a><br>For grown-ups: no accounts, no ads, no cookies. Settings and stars stay on this device
(<a href="../privacy.html">privacy</a>).
Maps show India's borders as on India's official maps (Natural Earth, India view).</p></section></main>'''
    open(os.path.join(pdir, "index.html"), "w", encoding="utf-8").write(shell(cfg, f"Read & Play · {cfg['title']}", body, root="../"))
    open(os.path.join(pdir, "certificate.html"), "w", encoding="utf-8").write(certificate(cfg))
    names = {e: edition.load(e)["name"] for e in edition.list_editions()}
    open(os.path.join(pdir, "report.html"), "w", encoding="utf-8").write(report(cfg, names))
    if cfg.get("kids_mode"):
        open(os.path.join(pdir, "listen.html"), "w", encoding="utf-8").write(listen.page(cfg))
    for n in (180, 192, 512):                     # the owl, from assets/ (tools/brand/make_icons.js)
        shutil.copy(os.path.join(brand.ASSETS, f"owl-icon-{n}.png"), os.path.join(pdir, f"icon-{n}.png"))
    shutil.copy(brand.SVG, os.path.join(pdir, "owl.svg"))
    open(os.path.join(pdir, "manifest.webmanifest"), "w", encoding="utf-8").write(manifest(cfg))
    open(os.path.join(out, "manifest.webmanifest"), "w", encoding="utf-8").write(pwa.manifest(cfg))
    core = (["index.html", "manifest.webmanifest", "icon-192.png"] + [f"{a}?v={asset_version()}" for a in ASSETS]
            + newest)
    version = hashlib.sha1((asset_version() + "".join(open(os.path.join(pdir, f), encoding="utf-8").read()
                                                    for f in ["index.html"] + newest)).encode()).hexdigest()[:12]
    open(os.path.join(pdir, "sw.js"), "w", encoding="utf-8").write(
        SW.replace("%VERSION%", f"rp-{version}").replace("%CORE%", json.dumps(core)))


CSS = r"""
.narration-credit{font-size:14px;color:var(--muted);white-space:nowrap}
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
.menu button .ic{font-size:2em}.menu button .got{margin-left:auto;color:var(--sun);font-size:1.05em;white-space:nowrap;
  display:grid;grid-template-columns:auto auto;gap:0 6px;align-items:center;text-align:right}
.menu button .got small{color:var(--muted);font-size:.68em;font-weight:700}
.scores{display:flex;flex-wrap:wrap;gap:6px 18px;margin:-4px 0 8px;color:var(--muted);font-weight:700}
.scores b{color:var(--sun);font-size:1.2em;letter-spacing:2px;margin-left:4px}
.practice{margin:0 0 10px;color:var(--muted);font-size:.9em}
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
/* the front of Read & Play: everything important on the first screen */
.bar.lb{padding:8px 16px;flex-wrap:nowrap}
.lb h1{font-size:1.45em;margin:0}.lb h1 a{color:var(--coral);text-decoration:none;display:inline-flex;align-items:center;gap:.25em;white-space:nowrap}
.lb .owl{width:1.45em;height:1.45em}.lb .home{margin-right:auto;font-size:15px;white-space:nowrap}
.chips{display:flex;gap:6px;margin-left:auto}
.chip{display:inline-flex;align-items:center;gap:5px;min-height:44px;border:2px solid var(--line);background:var(--card);border-radius:999px;
  padding:4px 12px;font-weight:800;font-size:16px;text-decoration:none;color:var(--ink);white-space:nowrap}

.front .today,.front .side>section,.front .me{scroll-margin-top:72px}
.front h2{margin:6px 0 8px}
.motto{margin:0 0 2px;font-size:15px;color:var(--muted);font-weight:700}
.hello{display:flex;flex-wrap:wrap;align-items:center;gap:0 12px;margin:0;font-size:1.02em}
.hello .change{border:0;background:none;color:var(--teal);font-weight:700;cursor:pointer;padding:0;font-size:16px;min-height:44px}
.tiles{display:grid;gap:10px;margin-bottom:22px}
.tile{display:flex;align-items:center;gap:12px;background:var(--card);border:2px solid var(--line);border-radius:18px;padding:10px}
.thumb{flex:none;width:clamp(100px,24vw,150px);aspect-ratio:4/3;border-radius:12px;overflow:hidden;display:grid;place-items:center;
  background:var(--tone-t,var(--sun-t));text-decoration:none}
.thumb .scene{width:auto;height:100%;max-width:none;border-radius:0}.thumb .ic{font-size:2.4em}
.mini{display:grid;place-items:center;width:100%;height:100%}.mini svg{display:block;width:100%;height:100%;background:var(--sea)}
.mini use{fill:var(--land);stroke:var(--map-line);stroke-width:1}.mini .hi{fill:var(--coral);fill-opacity:.8;stroke:var(--map-line);stroke-width:1}
.mini .dot{fill:var(--coral);stroke:#fff;stroke-width:2}
.tile .tx{flex:1;min-width:0}
.tile .when{margin:0;font-size:14px;color:var(--muted);line-height:1.35}
.tile .new{background:var(--rose-t);color:#B23A30;font-size:11px;font-weight:800;border-radius:999px;padding:1px 7px;margin-left:4px;letter-spacing:.03em}
.tile .done{color:var(--leaf);font-weight:700}
.tile h2{font-family:var(--text);font-size:1em;line-height:1.3;margin:2px 0 8px}.tile h2 a{color:inherit;text-decoration:none}
.go2{display:flex;gap:8px}.go2 .big{min-height:44px;padding:6px 18px;font-size:16px;border-radius:12px;text-align:center}
.side .bigrow{margin:0 0 18px}
.me{margin-top:8px}
.tabbar{display:none;position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--card);border-top:2px solid var(--line);
  padding:4px 6px calc(4px + env(safe-area-inset-bottom,0px))}
.tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:52px;font-size:12.5px;font-weight:700;
  line-height:1.2;color:var(--muted);text-decoration:none;border-radius:12px}
.tabbar a span{font-size:22px;line-height:1.15}
.tabbar a[aria-current="true"]{color:#B23A30;background:var(--rose-t)}
:root[data-theme="night"] .tabbar a[aria-current="true"]{color:#FFB3AB}
@media (max-width:699px){
  .lb .home,.chip .of{display:none}
  .front{padding-bottom:100px}.tabbar{display:flex}
  .big3{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:10px;margin:0 -16px;padding:0 16px 6px}
  .big3 .bigstory{flex:0 0 84%;scroll-snap-align:start}}
@media (min-width:700px) and (max-width:999px){.side{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}}
@media (min-width:1000px){
  .lobby.front{max-width:1240px;display:grid;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr);gap:0 32px;align-items:start;padding-top:18px}
  .front .today{grid-column:1;grid-row:1}.front .side{grid-column:2;grid-row:1/span 2}.front .me{grid-column:1}
  .bar.lb{padding:10px max(16px,calc((100vw - 1240px)/2 + 16px))}}
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
/* new games: hints, Map hunt, Guess the number, a Full set */
.why.hint{background:var(--sun-t)}
.lvltag{display:inline-block;border-radius:999px;padding:3px 12px;font-weight:800;font-size:.8em;margin:2px 0 4px}
.lvltag.up{background:#E7E3FA;color:#4D3FB0}.lvltag.down{background:var(--leaf-t);color:var(--leaf)}.lvltag small{font-weight:600;opacity:.8}
:root[data-theme="night"] .lvltag.up{background:#2E2A4D;color:#C9C1FF}
.hunt .tap.miss{fill:#B9C9CF}
.ord{list-style:none;padding:0;margin:8px 0;display:grid;gap:8px}
.ord li{display:flex;align-items:center;gap:10px;background:var(--card);border:2px solid var(--line);border-radius:16px;padding:8px 10px;font-size:.9em;line-height:1.35}
.ord li.ok{border-color:var(--leaf);background:var(--leaf-t)}
.ord .n{flex:none;min-width:30px;height:30px;padding:0 6px;border-radius:999px;background:var(--ink);color:var(--card);display:grid;place-items:center;font-weight:800;font-size:.85em}
.ord.done .n{background:var(--leaf);color:#fff;font-size:.72em}
.ord .tx{flex:1}.ord .mv{display:flex;flex-direction:column;gap:4px;flex:none;color:var(--leaf);font-weight:800}
.ord .mv button{min-width:44px;min-height:36px;border:2px solid var(--line);background:var(--card);color:var(--ink);border-radius:10px;cursor:pointer;font-size:.9em}
.ord .mv button:disabled{opacity:.3;cursor:default}
.hunt{border-radius:16px;overflow:hidden;border:2px solid var(--line);margin:4px 0 6px;touch-action:manipulation}
.hunt svg{display:block;width:100%;height:auto;cursor:crosshair}
.hunt .sea{fill:var(--sea)}.hunt use{fill:var(--land);stroke:var(--map-line);stroke-width:1}
.hunt .hl path{fill:var(--coral);fill-opacity:.45;stroke:var(--coral);stroke-width:1.5}
.hunt .trip{stroke:var(--teal);stroke-width:2.5;stroke-dasharray:6 5;vector-effect:non-scaling-stroke;fill:none}
.hunt .tap{fill:#5A8394;stroke:#fff;stroke-width:2;vector-effect:non-scaling-stroke}
.hunt .dot{fill:var(--coral);stroke:#fff;stroke-width:2;vector-effect:non-scaling-stroke}
.hunt .ring{fill:none;stroke:var(--coral);stroke-width:2.5;vector-effect:non-scaling-stroke;transform-box:fill-box;transform-origin:center;animation:rp-pulse 1.8s ease-out infinite}
@media (prefers-reduced-motion:reduce){.hunt .ring{animation:none}}
.slide{margin:18px 4px 6px;text-align:center}
.slide .val{display:inline-block;background:var(--ink);color:var(--card);font-weight:800;border-radius:10px;padding:4px 12px;font-size:1.1em;margin-bottom:10px}
.slide input{width:100%;height:44px;accent-color:var(--teal)}
.slide .ends{display:flex;justify-content:space-between;font-size:14px;color:var(--muted)}
.nbars{display:grid;gap:6px;margin:10px 0}.nbars div{position:relative;background:var(--bg);border-radius:8px;min-height:32px}
.nbars i{position:absolute;left:0;top:0;bottom:0;border-radius:8px;background:#B9C9CF}.nbars .ans i{background:var(--coral);opacity:.75}
.nbars span{position:relative;display:block;padding:5px 10px;font-size:.8em;font-weight:700}
.opts.nums{grid-template-columns:1fr;gap:12px}.opts.nums button{font-size:1.25em;font-weight:800;text-align:center;min-height:64px}
.fullset{background:var(--sun-t);border:2px solid var(--sun);border-radius:16px;padding:12px 14px;margin:10px 0;font-size:1.05em}
.newbadge{display:flex;gap:12px;align-items:center;background:var(--card);border:2px solid var(--sun);border-radius:16px;padding:10px 12px;margin:8px 0;
  text-decoration:none;color:var(--ink)}.newbadge .bi{font-size:2em}.newbadge b{display:block}.newbadge small{color:var(--muted)}
.game.grown .fullset{background:var(--bg);border-color:var(--line)}.game.grown .newbadge{border-color:var(--teal)}
.game.grown .stars{font-size:1.4em;letter-spacing:2px}
/* app, streaks and badges */
.install{background:var(--card);border:2px dashed var(--coral);border-radius:18px;padding:12px 16px;margin:0 0 18px}
.install p{margin:0 0 8px}.install .big{min-height:48px;padding:8px 18px;font-size:17px}
.myreading{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:14px 16px;margin:0 0 18px}
.myreading:empty{display:none}
.myreading h2{margin:0 0 8px}
.myreading .st{display:flex;align-items:center;gap:12px}.myreading .st p{margin:0;line-height:1.3}.myreading .st p span{color:var(--muted);font-size:.8em}
.tower{display:inline-flex;flex-direction:column-reverse;align-items:center;gap:2px;min-width:40px;flex:none}
.tower i{display:block;height:12px;border:2px solid var(--ink);border-radius:58% 42% 55% 45%/52% 58% 42% 48%}
.tower.empty i{width:34px;border-style:dashed;border-color:var(--muted);background:none;opacity:.6}
.pg{display:inline-block;width:18px;height:12px;background:#8E9AA0;border:2px solid var(--ink);border-radius:58% 42% 55% 45%/52% 58% 42% 48%}
.chip.off .pg{background:none;border-style:dashed;border-color:var(--muted)}
.end .streak{display:flex;align-items:center;justify-content:center;gap:12px;text-align:left}
.myreading .n{margin-left:auto!important;text-align:center}.myreading .n b{font-size:1.6em;font-family:var(--display)}
.myreading summary{cursor:pointer;font-weight:700;color:var(--teal);margin-top:10px;min-height:32px}
.shelf{list-style:none;padding:0;margin:12px 0 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,140px),1fr));gap:8px}
.shelf li{border:2px solid var(--line);border-radius:14px;padding:8px 10px;display:grid;gap:2px;opacity:.65;font-size:.8em;line-height:1.25}
.shelf li.got{opacity:1;border-color:var(--sun);background:var(--sun-t)}
.shelf .bi{font-size:1.8em;line-height:1.1}.shelf small{color:var(--muted)}
.shelf li:not(.got) .bi{filter:grayscale(1);opacity:.5}
.shelf .bp{display:block;height:6px;border-radius:9px;background:var(--line);overflow:hidden;margin-top:4px}.shelf .bp i{display:block;height:100%;background:var(--teal)}
.shelf .cert1{font-weight:700;font-size:.95em;margin-top:2px}
/* the Pebble Garden (6–11) and My progress (12+) */
.gardencard,.progress{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:14px 16px;margin:0 0 18px}
.gardencard h2,.progress h2{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 10px}
.gardencard h3,.progress h3{font-size:1em;margin:16px 0 6px}
.purse{margin-left:auto;font-family:var(--text);font-size:.68em;font-weight:800;border:2px solid var(--line);border-radius:999px;padding:3px 10px;display:inline-flex;gap:5px;align-items:center}
.garden{position:relative;aspect-ratio:32/15;border-radius:16px;overflow:hidden;border:2px solid var(--line);
  background:linear-gradient(#DDEFF5 0 32%,#C5DDA8 32% 100%)}
:root[data-theme="night"] .garden{background:linear-gradient(#22394A 0 32%,#3E5A3B 32% 100%)}
.garden .river{position:absolute;left:-10%;right:-10%;top:58%;height:17%;background:#8CC7D8;border-radius:50%;transform:rotate(-6deg);box-shadow:inset 0 6px 0 rgba(255,255,255,.35)}
.garden .gi{position:absolute;line-height:1;cursor:grab;touch-action:none;user-select:none;-webkit-user-select:none;
  transition:transform .12s;border-radius:8px}
.garden .gi:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
.garden .gi.lift{cursor:grabbing;transform:translateY(-10%) scale(1.25);filter:drop-shadow(0 6px 4px rgba(0,0,0,.25))}
.movehint{margin:6px 0 0}
.garden .gowl{position:absolute;left:16%;top:32%;width:15%}.garden .gowl svg{width:100%;height:auto}
.garden .gstack{position:absolute;left:4%;bottom:6%}.garden .gstack .tower i{height:9px}
.garden .empty1{position:absolute;left:30%;right:6%;top:30%;background:rgba(255,255,255,.85);color:#1E2A32;border-radius:12px;padding:8px 10px;font-size:.78em;font-weight:700;text-align:center}
.shop{display:grid;grid-template-columns:repeat(auto-fill,minmax(88px,1fr));gap:8px;margin-top:6px}
.shop button{border:2px solid var(--line);background:var(--card);border-radius:14px;padding:6px 4px;cursor:pointer;font-size:.72em;font-weight:700;line-height:1.25;min-height:84px}
.shop button span{display:block;font-size:2em;line-height:1.2}.shop button small{display:block;color:var(--muted);font-weight:600}
.shop button:disabled{cursor:default;opacity:.55}.shop button.have{opacity:1;background:var(--leaf-t);border-color:var(--leaf)}
.shop button.have:disabled{opacity:.55}
.garden-extras{margin-top:12px}.garden-extras summary{font-size:.85em;font-weight:700;color:var(--teal);cursor:pointer;min-height:44px;padding:10px 0}
.pebble-tabs{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 18px}
.pebble-tabs button{font:inherit;font-size:.85em;font-weight:700;min-height:44px;padding:8px 14px;border:2px solid transparent;border-radius:12px;background:none;color:var(--muted);cursor:pointer}
.pebble-tabs button[aria-selected="true"]{background:var(--leaf-t);border-color:var(--teal);color:var(--teal)}
.pebble-panel[hidden],#badges[hidden]{display:none!important}
@media(max-width:699px){
 .garden{aspect-ratio:4/3}.garden .gi{transform:translateY(-10%)}
 .pebble-tabs{flex-wrap:nowrap;gap:4px}.pebble-tabs button{flex:1;min-width:0;padding:8px 6px;font-size:.78em}
}
.quest{display:flex;gap:12px;align-items:center;background:var(--sun-t);border-radius:16px;padding:10px 12px;margin-top:12px}
.quest .qi{font-size:2.2em}.quest div{flex:1}.quest small{color:var(--muted);font-size:.78em}
.bar2{display:block;height:9px;border-radius:999px;background:var(--line);overflow:hidden;margin:5px 0 3px}.bar2 i{display:block;height:100%;background:var(--teal);border-radius:999px}
.bar2 i.low{background:var(--coral)}
.passport{display:block;width:100%;height:auto;border-radius:12px;border:2px solid var(--line)}
.passport .sea{fill:var(--sea)}.passport use{fill:var(--land);stroke:var(--map-line);stroke-width:1}.passport .been{fill:var(--teal);fill-opacity:.75;stroke:var(--map-line);stroke-width:1}
.grownup{font-size:.78em;color:var(--muted);margin:12px 0 0}
.dash{display:grid;grid-template-columns:1fr 1fr;gap:8px}.dash div{border:2px solid var(--line);border-radius:14px;padding:8px 10px;background:var(--card)}
.dash b{display:block;font-family:var(--display);font-size:1.35em}.dash small{color:var(--muted);font-size:.72em;line-height:1.2;display:block}
.lvl{border:2px solid var(--line);border-radius:14px;padding:8px 10px;margin-top:10px}.lvl span:not(.bar2){color:var(--muted);font-size:.85em}.lvl small{color:var(--muted);font-size:.75em}
.tb{display:grid;grid-template-columns:7.5em 1fr 6.5em;gap:8px;align-items:center;font-size:.85em}.tb small{color:var(--muted);font-size:.85em}
.rev{list-style:none;padding:0;margin:0;display:grid;gap:8px}.rev li{border:2px solid var(--line);border-radius:12px;padding:8px 10px;display:grid;gap:2px;font-size:.85em}
.rev small{color:var(--muted)}.rev button{justify-self:start;border:2px solid var(--teal);background:none;color:var(--teal);border-radius:999px;padding:3px 12px;font-weight:700;cursor:pointer;min-height:36px;font-size:.95em}
.earned{font-weight:800;color:var(--leaf);display:flex;gap:6px;align-items:center;margin:4px 0}
/* a monthly report to print */
.reportpage{max-width:820px;margin:0 auto;padding:16px}
.report{background:#fff;color:#1E2A32;border:1.5px solid #CFD6D8;border-radius:8px;padding:22px;margin-top:14px;font-size:16px}
.report .rhead{display:flex;align-items:center;gap:10px}.report .rhead .owl{width:44px;height:44px}.report .rhead .mo{margin-left:auto;color:#56646C}
.report h1{font-size:1.6em;margin:12px 0 10px}.report p{margin:8px 0}.report .dash div{background:#fff;border-color:#E1E5E6}
.report .passport{max-width:520px;margin-top:6px}.report .rfoot{border-top:1px solid #E1E5E6;padding-top:8px;margin-top:14px;font-size:13px;color:#56646C}
.reportpage .ctl label{display:grid;gap:4px;font-weight:700}.reportpage select{font:inherit;padding:8px;border-radius:10px;border:2px solid var(--line)}
@media print{.reportpage{padding:0;max-width:none}.report{border:0;padding:0;margin:0}}
/* a certificate to print */
.certpage{max-width:900px;margin:0 auto;padding:16px}
.cert{background:#fff;color:#1E2A32;border:10px double #5A8394;border-radius:6px;padding:28px 24px 18px;text-align:center;font-family:Georgia,"Times New Roman",serif}
.cert .owl{display:block;width:84px;height:84px;margin:0 auto}
.cert .org{margin:6px 0 0;font:700 14px var(--text);letter-spacing:.25em;color:#5A8394}
.cert .kind{margin:2px 0 10px;font-size:15px;font-style:italic;color:#56646C}.cert .to{margin:0;font-size:17px}
.cert .nm{font-size:34px;min-width:60%;display:inline-block;border-bottom:1.5px solid #1E2A32;margin:10px 0 6px;padding:0 20px 2px;min-height:1.3em}
.cert h1{font-family:Georgia,serif;font-size:40px;color:#E2584D;margin:6px 0 4px}.cert .bd{font-size:18px;margin:0 0 18px}
.cert .ft{display:flex;justify-content:space-between;font:13px var(--text);color:#56646C;border-top:1px solid #D9DEE0;padding-top:8px}
.ctl{display:grid;gap:10px;margin-top:16px}.ctl label{display:grid;gap:4px;font-weight:700}
.ctl input{font:inherit;font-size:18px;padding:10px 12px;border:2px solid var(--line);border-radius:12px;background:var(--card);color:var(--ink)}
.ctl .note{font-size:14px;color:var(--muted);margin:0}
@media print{@page{margin:12mm}body{background:#fff}.noprint{display:none!important}.certpage{padding:0;max-width:none}
  .cert{border-width:12px;min-height:170mm;display:flex;flex-direction:column;justify-content:center;align-items:center}.cert .ft{align-self:stretch}}
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

CSS += r"""
:root{--bg:#F4F1EA;--line:#DDD5C6;--teal:#00727E}
:root[data-theme="night"]{--bg:#11181C;--line:#344249;--teal:#62C6CD}
body{padding-bottom:calc(86px + env(safe-area-inset-bottom,0px))}
#pop{bottom:calc(82px + env(safe-area-inset-bottom,0px))}
.childnav{display:flex}
.childnav a[aria-current="page"]{color:var(--teal);background:var(--leaf-t)}
.childnav a{min-height:58px;font-size:13px}
.childnav a span{font-size:22px}
.lobby-panel[hidden]{display:none!important}
.view-title{font-size:1.6em;margin:0 0 18px;font-family:var(--display)}
.lobby-panel{scroll-margin-top:calc(var(--bar-height,90px) + 12px)}
#stories,#map,#badges{scroll-margin-top:calc(var(--bar-height,90px) + 12px)}
.lobby.front{display:block;max-width:1100px;padding-bottom:24px}
.front .side{display:block}.front .me{margin-top:0}
.lb .home{display:inline-flex;white-space:nowrap;font-size:15px;min-height:44px;align-items:center}
.bar.lb{flex-wrap:wrap;gap:6px 14px}
@media(max-width:699px){
 .bar.lb{display:grid;grid-template-columns:minmax(0,1fr) auto}
 .lb .home{justify-self:end;margin:0;gap:4px}
 .lb .chips{grid-column:1/-1;justify-self:end;margin-left:0}
}
@media(min-width:700px){.childnav{justify-content:center}.childnav a{flex:0 1 190px}.front .tiles{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}}
@media(max-width:699px){.childnav a{font-size:12px}.big3{display:grid;overflow:visible;margin:0;padding:0}.big3 .bigstory{width:100%}}
@media print{body{padding-bottom:0}.childnav{display:none!important}}
"""


CSS += navigation.STYLE
CSS += story_timeline.CSS

CSS += r"""
#listen-player{position:fixed;left:12px;right:12px;bottom:calc(86px + env(safe-area-inset-bottom,0px));z-index:7;
 max-width:580px;margin:auto;padding:6px 10px;background:var(--card);border:1.5px solid var(--line);border-radius:14px;box-shadow:0 3px 16px #0002;font-size:13px}
.listen-heading{display:flex;align-items:center;gap:10px;margin-bottom:2px}
.listen-title{flex:1;min-width:0;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0}
.listen-time{flex:none;white-space:nowrap;font-variant-numeric:tabular-nums;font-size:12px}
.listen-controls{display:flex;align-items:center;gap:4px}
.listen-controls input{flex:1;min-width:0;width:0;min-height:44px;margin:0 4px;accent-color:var(--teal)}
.listen-controls button,.listen-more summary,#listen-resume button{font:inherit;min-height:44px;border:1.5px solid var(--line);border-radius:9px;padding:5px 8px;background:var(--card);color:var(--teal);font-weight:700;cursor:pointer}
.listen-controls>button{flex:none;min-width:44px}
.listen-controls button[data-listen=toggle]{background:var(--teal);border-color:var(--teal);color:var(--card);width:66px}
.listen-more{position:relative;flex:none}.listen-more summary{display:flex;align-items:center;justify-content:center;box-sizing:border-box;width:44px;height:44px;list-style:none;font-size:22px;line-height:1}
.listen-more summary::-webkit-details-marker{display:none}
.listen-more>div{position:absolute;right:0;bottom:calc(100% + 8px);min-width:180px;padding:5px;background:var(--card);border:1.5px solid var(--line);border-radius:12px;box-shadow:0 3px 16px #0002}
.listen-more button{display:block;width:100%;text-align:left;border:0;white-space:nowrap}
.listen-return{display:block;min-height:44px;border:0;background:none;color:var(--teal);font:inherit;text-decoration:underline;padding:2px 0;cursor:pointer}
.read-edition{font:inherit;display:inline-flex;align-items:center;gap:6px;font-size:16px;font-weight:700;min-height:44px;padding:6px 12px;border:1.5px solid var(--line);border-radius:12px;background:var(--card);color:var(--teal);cursor:pointer;margin:2px 0 8px}
.listen-status{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
#listen-resume{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:12px;border:1.5px solid var(--line);border-radius:14px;background:var(--card);font-size:15px;margin:8px 0 16px}
#listen-resume span{flex-basis:100%}body.listening{padding-bottom:calc(230px + env(safe-area-inset-bottom,0px))}
body.listening #pop{bottom:calc(220px + env(safe-area-inset-bottom,0px))}
@media print{#listen-player,#listen-resume,#listen-edition{display:none!important}}
.desktopbrand,.childnav.desktopnav{display:none}
@media screen and (min-width:700px){
 .childnav.tabbar{display:none}
 .bar{gap:8px 18px;justify-content:flex-start}
 .bar>.home{display:none}
 .desktopbrand{display:inline-flex;align-items:center;gap:.25em;order:0;color:var(--coral);font-family:var(--display);font-size:1.45em;font-weight:800;text-decoration:none;white-space:nowrap}
 .desktopbrand .owl{width:1.45em;height:1.45em}
 .childnav.desktopnav{--nav-active-bg:#DDEFF0;display:flex;order:1;gap:4px;align-items:center;justify-content:flex-start}
 :root[data-theme="night"] .desktopnav{--nav-active-bg:#203D40}
 .desktopnav a{flex:none;display:flex;align-items:center;min-height:44px;padding:6px 10px;font-size:16px;font-weight:700;text-decoration:none;white-space:nowrap;border-radius:9px;color:var(--muted)}
 .desktopnav a span{display:none}
 .desktopnav a[aria-current="page"]{color:var(--teal);background:var(--nav-active-bg,#DDEFF0)}
 .bar>.chips,.bar>.tools,.bar>.lvl{order:2;margin-left:auto}
 body{padding-bottom:20px}
 #listen-player,#pop{bottom:12px}
 body.listening{padding-bottom:140px}
 body.listening #pop{bottom:112px}
}
@media screen and (min-width:1000px){
 .childnav.desktopnav{margin-left:auto}
 .bar>.chips,.bar>.tools,.bar>.lvl{margin-left:0}
}
"""

JS = r"""
(function () {
  const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
  const store = { get(k, d) { try { const v = localStorage.getItem("rp-" + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
                  set(k, v) { try { localStorage.setItem("rp-" + k, JSON.stringify(v)); } catch (e) {} } };
  window.addEventListener("storage", e => {
    if (e.key === "np-reading-reset" && e.newValue) {
      store.set = () => {}; // Old reader callbacks must not restore data while this page reloads.
      document.dispatchEvent(new Event("rp-reading-reset"));
      location.reload();
    }
  });
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
    if (act === "rate") { b.value = String(store.get("rate", 1)); b.addEventListener("change", () => { store.set("rate", +b.value); document.dispatchEvent(new Event("rp-rate")); }); return; }
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
  if (inst && !document.documentElement.hasAttribute('data-tablet-install') && !(window.matchMedia && matchMedia("(display-mode: standalone)").matches) && !navigator.standalone) {
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

  // ---------------------------------------------------------------- usage counts (ygc/stats.py): anonymous events, no ID;
  // the first-visit date the "came back" counts need stays on this device
  const tally = (p, t) => { if (window.npCount) window.npCount(p, t, true); };
  function readerToday() {
    const today = ymd(new Date());
    if (store.get("seen", "") === today) return;
    store.set("seen", today);
    let first = store.get("first", "");
    if (!first) {           // a device that read before counting began isn't new, and isn't counted coming back
      first = count("days") || count("read") || Object.keys(store.get("badges", {})).length ? "before" : today;
      store.set("first", first);
      if (first === today) tally("reader/new", "A new reader");
    }
    if (first !== "before") {
      const gap = Math.round((Date.parse(today) - Date.parse(first)) / 864e5);
      if (gap === 1) tally("reader/back-next-day", "Came back the day after their first visit");
      if (gap === 7) tally("reader/back-day-7", "Came back 7 days after their first visit");
    }
    tally("reader/today", "Opened a paper today");
  }
  if ($("main.issue")) readerToday();
  function streak() {
    const days = new Set(store.get("days", [])), d = new Date(); let n = 0;
    if (!days.has(ymd(d))) d.setDate(d.getDate() - 1);         // not read yet today: yesterday's streak still counts
    while (days.has(ymd(d))) { n++; d.setDate(d.getDate() - 1); }
    return n;
  }
  // Each badge has a name for younger readers and a plainer one for 12 and up, what it was for (on the
  // certificate), and how far along the reader is: [done, needed].
  const B = (id, icon, name, gname, did, prog) => ({ id, icon, name, gname, did, prog });
  const BADGES = [
    B("first", "📰", "First paper", "First paper", "reading a whole paper", () => [count("read"), 1]),
    B("shelf", "📚", "Bookworm", "Regular reader", "reading 10 papers", () => [count("read"), 10]),
    B("fire3", "🔥", "On fire", "3-day streak", "reading 3 days in a row", () => [streak(), 3]),
    B("week", "🌟", "Super week", "7-day streak", "reading 7 days in a row", () => [streak(), 7]),
    B("month", "🏆", "News champion", "Month of news", "reading 30 days in a row", () => [streak(), 30]),
    B("maps", "🗺️", "Map explorer", "Globetrotter", "reading stories from 10 countries", () => [count("lands"), 10]),
    B("words", "🔤", "Word wizard", "Wordsmith", "learning 15 new words", () => [count("words"), 15]),
    B("ears", "🔊", "Good listener", "Listener", "listening to 5 stories read aloud", () => [store.get("heard", 0), 5]),
    B("quiz", "🧠", "Quiz champ", "Quiz ace", "3 stars on 3 quizzes", () => [count("3s-quiz"), 3]),
    B("facts", "🕵️", "Fact detective", "Fact checker", "3 stars on 3 Fact or fiction games", () => [count("3s-facts"), 3]),
    B("match", "🧩", "Perfect match", "Perfect match", "3 stars on 3 matching games", () => [count("3s-words"), 3]),
    B("pins", "📍", "Map master", "Cartographer", "finding 10 places in the news on the map", () => [count("map3"), 10]),
    B("nums", "🎚️", "Number ninja", "Data detective", "10 spot-on guesses of numbers in the news", () => [count("num3"), 10]),
    B("order", "🔀", "Time keeper", "Chronologist", "putting 5 big stories' events in the right order", () => [count("ord3"), 5]),
    B("set1", "⭐", "Full set", "Set complete", "playing every game in a paper", () => [count("sets"), 1]),
    B("set5", "🌠", "Super set", "Five sets", "playing every game in 5 papers", () => [count("sets"), 5]),
    B("clean", "🎯", "First try", "Clean sheet", "a full set of games with no hints", () => [count("clean"), 1]),
  ];
  const grownUp = () => { const m = $(".issue"); return /12–14|15\+/.test((m ? m.dataset.band : store.get("band", "")) || ""); };
  const nameOf = (b) => (grownUp() ? b.gname : b.name);
  const earned = (b) => { const [n, of] = b.prog(); return n >= of; };
  function award() {
    const have = store.get("badges", {}), fresh = BADGES.filter((b) => !have[b.id] && earned(b));
    if (!fresh.length) return [];
    fresh.forEach((b) => { have[b.id] = ymd(new Date()); });
    store.set("badges", have);
    const t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status");
    t.innerHTML = fresh.map((b) => `<p><span class="bi" aria-hidden="true">${b.icon}</span><span><small>${grownUp() ? "Achievement" : "New badge!"}</small><b>${esc(nameOf(b))}</b></span></p>`).join("");
    document.body.appendChild(t);
    setTimeout(() => t.classList.add("bye"), 3800); setTimeout(() => t.remove(), 4400);
    shelf();
    return fresh;
  }
  function paperDone() {
    const issue = $(".issue"); if (!issue) return;
    addTo("days", ymd(new Date()), 400);
    if (addTo("read", issue.dataset.key, 2000)) {             // 3 pebbles for each paper read to the end
      earn(3);
      tally("finished/" + issue.dataset.key.slice(0, -11), "Finished: " + $("h1", issue).textContent);
    }
    award();
    const s = streak(), el = $(".end .streak");
    if (el) el.innerHTML = tower(s) + `<span>${s > 1 ? `Pebble number ${s} is on your tower! Come back tomorrow for number ${s + 1}.`
      : "Your first pebble is on your tower. Come back tomorrow for another!"}</span>`;
  }
  const STONES = ["#8E9AA0", "#D9C7A3", "#9DB48A", "#E2584D", "#5A8394"];
  function tower(n, cls) {                                   // the streak as a little stack of pebbles, one per day
    const shown = Math.min(n, 7), w = (i) => 34 - i * 3;
    return `<span class="tower${cls ? " " + cls : ""}${n ? "" : " empty"}" aria-hidden="true">${n ? Array.from({ length: shown }, (_, i) =>
      `<i style="width:${w(i)}px;background:${STONES[i % STONES.length]}"></i>`).join("") : "<i></i>"}</span>`;
  }
  function shelf() {
    const box = $("#badges"); if (!box) return;
    const have = store.get("badges", {}), s = streak(), today = store.get("days", []).includes(ymd(new Date()));
    const n = Object.keys(have).length, chips = $("#chips");
    if (chips) chips.innerHTML = `<a class="chip${s ? "" : " off"}" href="#me" aria-label="${s ? `Pebble tower: ${s} days in a row` : "No pebbles on your tower yet"}"><span class="pg" aria-hidden="true"></span> ${s}</a>
      <a class="chip" href="${grownUp() ? '#badges' : '#me'}" aria-label="${n} of ${BADGES.length} badges"><span aria-hidden="true">🏅</span> ${n}<span class="of"> of ${BADGES.length}</span></a>`;
    box.innerHTML = `<h2>My reading <span>On this device</span></h2><div class="st">${tower(s)}
      <p><b>${s ? `My pebble tower: ${s} ${s === 1 ? "day" : "days"}` : "No pebbles yet"}</b><br><span>${s && !today ? `Read a whole paper today to add pebble number ${s + 1}!`
        : s ? "Today's pebble is on. See you tomorrow!" : "Read a whole paper to put your first pebble on your tower."}</span></p>
      <p class="n"><b>${count("read")}</b><br><span>${count("read") === 1 ? "paper" : "papers"} read</span></p></div>
      <details${location.hash === "#badges" ? " open" : ""}><summary>${grownUp() ? "Achievements" : "My badges"}: ${Object.keys(have).length} of ${BADGES.length}</summary>
      <ul class="shelf">${BADGES.slice().sort((x, y) => (have[y.id] ? 2 : y.prog()[0] / y.prog()[1]) - (have[x.id] ? 2 : x.prog()[0] / x.prog()[1]))
        .map((b) => { const [n, of] = b.prog(); return have[b.id]
        ? `<li class="got"><span class="bi" aria-hidden="true">${b.icon}</span><b>${esc(nameOf(b))}</b><small>For ${esc(b.did)}</small>
           <a class="cert1" href="certificate.html?b=${b.id}">🖨️ Certificate</a></li>`
        : `<li><span class="bi" aria-hidden="true">${b.icon}</span><b>${esc(nameOf(b))}</b><small>For ${esc(b.did)}</small>
           <span class="bp" aria-hidden="true"><i style="width:${Math.min(100, Math.round(100 * n / of))}%"></i></span><small>${Math.min(n, of)} of ${of}</small></li>`; }).join("")}</ul></details>`;
  }
  shelf();

  // ---------------------------------------------------------------- pebbles: earned by reading and playing, spent in the garden
  const pebbles = () => store.get("peb", 0) - store.get("spent", 0);
  const earn = (n) => { if (n > 0) store.set("peb", store.get("peb", 0) + n); };
  function toast1(icon, small, big) {
    const t = document.createElement("div"); t.className = "toast"; t.setAttribute("role", "status");
    t.innerHTML = `<p><span class="bi" aria-hidden="true">${icon}</span><span><small>${esc(small)}</small><b>${esc(big)}</b></span></p>`;
    document.body.appendChild(t); setTimeout(() => t.classList.add("bye"), 3800); setTimeout(() => t.remove(), 4400);
  }
  // Levels across days: Pebble, then Stone (some questions from the paper a step older), then Boulder (mostly).
  // Up after 10 of the last 12 answers right first time, over at least 2 days; down after 3 or fewer of the last 8.
  const SKILL = ["Pebble", "Stone", "Boulder"];
  const skill = () => store.get("skill", { l: 0, at: 0 });
  const sinceLevel = () => { const s = skill(); return store.get("answers", []).filter((a) => (a.ts || 0) > s.at); };
  function skillCheck() {
    const s = skill(), recent = sinceLevel(), l12 = recent.slice(-12), l8 = recent.slice(-8);
    if (s.l < 2 && l12.length >= 12 && l12.filter((a) => a.ok).length >= 10 && new Set(l12.map((a) => a.d)).size >= 2) {
      s.l++; s.at = Date.now(); store.set("skill", s);
      toast1("⬆️", "Level up!", `${SKILL[s.l]}: ${s.l === 1 ? "some harder questions now" : "mostly harder questions now"}`);
    } else if (s.l > 0 && l8.length >= 8 && l8.filter((a) => a.ok).length <= 3) {
      s.l--; s.at = Date.now(); store.set("skill", s);              // quietly back a step; no fuss
    }
  }
  function levelHtml(grownTone) {
    const s = skill(), l12 = sinceLevel().slice(-12), ok = l12.filter((a) => a.ok).length;
    const what = [grownTone ? "Questions at your paper's level." : "Questions just right for your paper.",
      grownTone ? "Some questions come from the paper a step older." : "Some stretch questions from an older paper!",
      grownTone ? "Mostly questions from the paper a step older." : "Mostly stretch questions. Brilliant!"][s.l];
    return `<div class="lvl"><b>Level: ${SKILL[s.l]}</b> <span>${what}</span>
      <span class="bar2"><i style="width:${s.l < 2 ? Math.round(100 * Math.min(ok, 10) / 10) : 100}%"></i></span>
      <small>${s.l < 2 ? `${ok} of your last ${l12.length || 0} answers right first time. Get 10 of 12 right, over 2 days, to reach ${SKILL[s.l + 1]}.` : "Top level."}</small></div>`;
  }
  // What the garden can hold: [id, icon, name, cost, left %, top %, size in em]. Quest prizes can't be bought.
  const ITEMS = [["daisy", "🌼", "Daisies", 3, 36, 44, 1.6], ["tulip", "🌷", "Tulips", 3, 50, 47, 1.6], ["mush", "🍄", "Mushroom", 4, 8, 84, 1.5],
    ["sunflower", "🌻", "Sunflower", 5, 64, 40, 1.8], ["butterfly", "🦋", "Butterfly", 5, 44, 20, 1.4], ["duck", "🦆", "Duck", 6, 44, 66, 1.7],
    ["frog", "🐸", "Frog", 6, 70, 74, 1.5], ["hedgehog", "🦔", "Hedgehog", 8, 24, 86, 1.6], ["turtle", "🐢", "Turtle", 8, 84, 86, 1.6],
    ["tree", "🌳", "Tree", 10, 2, 16, 3.4], ["pine", "🌲", "Pine tree", 10, 84, 14, 3], ["house", "🏡", "Little house", 15, 60, 14, 2.4],
    ["rainbow", "🌈", "Rainbow", 20, 28, 0, 3.2],
    ["bee", "🐝", "Bee", 5, 54, 22, 1.3], ["ladybird", "🐞", "Ladybird", 5, 40, 82, 1.2],
    ["snail", "🐌", "Snail", 8, 32, 78, 1.4], ["cactus", "🌵", "Cactus", 12, 72, 28, 2],
    ["cherry", "🌸", "Blossom", 15, 56, 38, 1.8], ["fox", "🦊", "Fox", 20, 34, 76, 1.9],
    ["fountain", "⛲", "Fountain", 25, 48, 44, 2.3], ["tent", "⛺", "Adventure tent", 30, 40, 20, 2.8],
    ["gazebo", "🛖", "Garden hideaway", 35, 76, 35, 2.7], ["castle", "🏰", "Castle", 40, 58, 12, 3.2],
    ["dragon", "🐉", "Dragon", 45, 30, 30, 2.8], ["unicorn", "🦄", "Unicorn", 50, 70, 66, 2.7]];
  const PRIZES = { flamingo: ["🦩", "Flamingo", 58, 56, 2], peacock: ["🦚", "Peacock", 16, 58, 2], swan: ["🦢", "Swan", 28, 66, 1.8],
    rabbit: ["🐇", "Rabbit", 90, 50, 1.6], deer: ["🦌", "Deer", 74, 28, 2.2], parrot: ["🦜", "Parrot", 12, 12, 1.5] };
  const QUESTS = [["read", 5, "Read 5 papers this week", "flamingo"], ["lands", 5, "Read stories from 5 countries", "peacock"],
    ["sets", 2, "Play 2 full sets of games", "swan"], ["map3", 5, "Find 5 places spot on in Map hunt", "rabbit"],
    ["words", 10, "Tap 10 new words", "deer"], ["num3", 3, "Get 3 numbers spot on", "parrot"]];
  function quest() {                                         // this week's quest: from Monday, how far along, and its prize
    const m = new Date(); m.setHours(12, 0, 0, 0); m.setDate(m.getDate() - (m.getDay() + 6) % 7);
    const wk = ymd(m), [k, n, text, prize] = QUESTS[Math.floor(m.getTime() / 6048e5) % QUESTS.length];
    let q = store.get("quest", null);
    if (!q || q.w !== wk) { q = { w: wk, base: count(k), done: false }; store.set("quest", q); }
    const got = Math.max(0, Math.min(n, count(k) - q.base));
    if (got >= n && !q.done) {
      q.done = true; store.set("quest", q); addTo("garden", prize); earn(5);
      toast1(PRIZES[prize][0], "Quest done! +5 pebbles", PRIZES[prize][1] + " for your garden");
    }
    return { n, got, text, prize, done: q.done };
  }
  function passport(label) {                                  // every country read about, coloured in
    if (!WD) return "";
    worldDefs();
    const vb = WORLDBOX(), lands = store.get("lands", []).filter((c) => shapes[c]);
    return `<svg class="passport" viewBox="${vb.join(" ")}" role="img" aria-label="${esc(label)}"><rect class="sea" x="${vb[0]}" y="${vb[1]}" width="${vb[2]}" height="${vb[3]}"/>
      <use href="#rp-world"/>${lands.map((c) => `<path class="been" d="${shapes[c].d}" vector-effect="non-scaling-stroke"/>`).join("")}</svg>`;
  }
  let gardenExtrasOpen = false;
  function gardenHtml() {
    const q = quest(), own = store.get("garden", []), have = pebbles(), owl = $(".lb .owl");
    const pos = store.get("gpos", {});                          // where the child has moved things: {id: [left %, top %, layer]}
    const put = (id, e, x, y, z, name) => { const p = pos[id] || [x, y, 0];
      return `<span class="gi" data-g="${id}" tabindex="0" role="button" aria-label="${esc(name)}: drag, or use the arrow keys, to move it"
        style="left:${p[0]}%;top:${p[1]}%;font-size:${z}em;z-index:${2 + (p[2] || 0)}" title="${esc(name)}">${e}</span>`; };
    // Keep the first copy's old ID and position; extra copies have stable, independent IDs.
    const copies = {}, placed = own.flatMap((type) => {
      const item = ITEMS.find(it => it[0] === type), prize = PRIZES[type];
      if (!item && !prize) return [];
      const n = copies[type] = (copies[type] || 0) + 1, id = n === 1 ? type : type + ':' + n;
      const [icon, name, x, y, size] = item ? [item[1], item[2], item[4], item[5], item[6]] : prize;
      const dx = n === 1 ? 0 : ((n - 1) * 13) % 55, dy = n === 1 ? 0 : ((n - 1) * 11) % 36;
      return [put(id, icon, n === 1 ? x : 8 + (x + dx) % 78, n === 1 ? y : 16 + (y + dy) % 64, size, name + (n > 1 ? ' ' + n : ''))];
    });
    const pz = PRIZES[q.prize];
    const shop = items => items.map(it => {
      const n = copies[it[0]] || 0;
      return `<button type="button" data-buy="${it[0]}"${n ? ' class="have"' : ''}${have < it[3] ? " disabled" : ""}
        aria-label="Buy ${n ? 'another ' : ''}${esc(it[2])} for ${it[3]} pebbles${n ? ', ' + n + ' in your garden' : ''}"><span>${it[1]}</span>${esc(it[2])}<small>${it[3]} pebbles</small>${n ? `<small>${n} in your garden · Buy another</small>` : ''}</button>`;
    }).join('');
    return `<section class="gardencard"><h2>🌱 My Pebble Garden <span class="purse"><i class="pg"></i> ${have} ${have === 1 ? "pebble" : "pebbles"}</span></h2>
      <div class="garden" role="group" aria-label="My garden: ${own.length ? own.length + " things growing" : "nothing planted yet"}"><span class="river"></span>
        ${placed.join("")}<span class="gowl">${owl ? owl.outerHTML : ""}</span><span class="gstack">${tower(streak())}</span>
        ${own.length ? "" : `<span class="empty1">Get your first flowers with your pebbles below 🌼</span>`}</div>
      ${own.length ? `<p class="how movehint">✋ Drag anything in your garden to move it.</p>` : ""}
      ${levelHtml(false)}
      <p class="how">Earn pebbles: <b>3</b> for reading a whole paper, <b>1</b> for each star on a game's first try, <b>2</b> for a Full set.</p>
      <div class="shop">${shop(ITEMS.slice(0, 13))}</div>
      <details class="garden-extras"${gardenExtrasOpen ? ' open' : ''}><summary>More garden treasures · up to 50 pebbles</summary><div class="shop">${shop(ITEMS.slice(13))}</div></details>
      <div class="quest"><span class="qi">${pz[0]}</span><div><b>This week's quest: ${esc(q.text)}</b>
        <span class="bar2"><i style="width:${Math.round(100 * q.got / q.n)}%"></i></span>
        <small>${q.done ? `Done! The ${pz[1].toLowerCase()} is in your garden.` : `${q.got} of ${q.n} · unlocks the ${pz[1].toLowerCase()} and 5 pebbles`}</small></div></div>
      <h3>My passport: ${store.get("lands", []).length} ${store.get("lands", []).length === 1 ? "country" : "countries"}</h3>${passport("Countries I've read about")}
      <p class="grownup">For grown-ups: <a href="report.html">this month's reading report</a></p></section>`;
  }
  function topicStats(list) {                                 // [topic, share right, answers], best first; 3 answers at least
    const by = {};
    list.forEach((a) => { const t = by[a.t] || (by[a.t] = [0, 0]); t[1]++; if (a.ok) t[0]++; });
    return Object.entries(by).filter(([, v]) => v[1] >= 3).map(([t, v]) => [t, v[0] / v[1], v[1]]).sort((a, b) => b[1] - a[1]);
  }
  function progressHtml() {
    const ans = store.get("answers", []), since = ymd(new Date(Date.now() - 6 * 864e5)), wk = ans.filter((a) => a.d >= since);
    const acc = wk.length ? Math.round(100 * wk.filter((a) => a.ok).length / wk.length) + "%" : "–";
    const topics = topicStats(ans.slice(-300)), rev = store.get("revise", []), s = streak();
    return `<section class="progress"><h2>📈 My progress</h2>
      <div class="dash"><div><b>${s} ${s === 1 ? "day" : "days"}</b><small>reading streak</small></div><div><b>${acc}</b><small>answers right, last 7 days</small></div>
        <div><b>${count("read")}</b><small>papers read</small></div><div><b>${store.get("lands", []).length}</b><small>countries in your news</small></div></div>
      ${levelHtml(true)}
      <h3>Topics</h3>${topics.length ? topics.slice(0, 6).map(([t, r]) => `<div class="tb"><span>${esc(t)}</span>
        <span class="bar2"><i class="${r < 0.6 ? "low" : ""}" style="width:${Math.max(4, Math.round(r * 100))}%"></i></span><small>${Math.round(r * 100)}%${r < 0.6 ? " · practise" : ""}</small></div>`).join("")
        : `<p class="how">Answer a few questions to see your strongest and weakest topics.</p>`}
      <h3>Countries in your news</h3>${passport("Countries in the news I've read")}
      <h3>Revision list${rev.length ? ` (${rev.length})` : ""}</h3>${rev.length ? `<ul class="rev">${rev.slice(0, 8).map((r, i) => `<li><b>${esc(r.q)}</b>
        <span>Answer: ${esc(r.a)}${r.why ? ". " + esc(r.why) : ""}</span><small>${esc(r.p || "")}</small><button type="button" data-done="${i}">Got it ✓</button></li>`).join("")}</ul>`
        : `<p class="how">Questions you get wrong first time are kept here to revise.</p>`}
      <p><a class="big go" href="report.html">⬇ Monthly report</a></p></section>`;
  }
  const PEBBLE_VIEWS = [['progress', 'Reading progress'], ['badges', 'Badges'], ['garden', 'My garden']];
  let pebbleView = 'progress', cornerOlder = null;
  function corner(view) {                                     // 6–11 keep the garden; 12+ can choose all three views
    const c = $("#corner"); if (!c) return;
    const extras = $('.garden-extras'); if (extras) gardenExtrasOpen = extras.open;
    const old = grownUp();
    if (cornerOlder !== old) { pebbleView = 'progress'; cornerOlder = old; }
    if (PEBBLE_VIEWS.some(([id]) => id === view)) pebbleView = view;
    const badges = $('#badges');
    if (badges) {
      badges.hidden = !!old && pebbleView !== 'badges';
      if (old) { badges.setAttribute('role', 'tabpanel'); badges.setAttribute('aria-labelledby', 'pebble-tab-badges'); }
      else { badges.removeAttribute('role'); badges.removeAttribute('aria-labelledby'); }
    }
    const tabs = old ? `<div class="pebble-tabs" role="tablist" aria-label="My Pebbles sections">${PEBBLE_VIEWS.map(([id, label]) =>
      `<button type="button" role="tab" id="pebble-tab-${id}" data-pebble-view="${id}" aria-selected="${pebbleView === id}" tabindex="${pebbleView === id ? 0 : -1}" aria-controls="${id === 'badges' ? 'badges' : 'pebble-panel'}">${label}</button>`).join('')}</div>` : '';
    c.innerHTML = tabs + (old ? `<div id="pebble-panel" class="pebble-panel" role="tabpanel" aria-labelledby="pebble-tab-${pebbleView}"${pebbleView === 'badges' ? ' hidden' : ''}>`
      + (pebbleView === 'progress' ? progressHtml() : pebbleView === 'garden' ? gardenHtml() : '') + '</div>' : gardenHtml());
    if (old && pebbleView === 'badges') { const details = $('#badges details'); if (details) details.open = true; }
    requestAnimationFrame(fitGarden);
  }
  function selectPebbleView(view) {
    corner(view); $('#pebble-tab-' + view)?.focus({preventScroll:true});
  }
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-buy]"), d = e.target.closest("[data-done]"), tab = e.target.closest('[data-pebble-view]');
    if (tab) selectPebbleView(tab.dataset.pebbleView);
    if (b) {
      const it = ITEMS.find((x) => x[0] === b.dataset.buy);
      if (!it || pebbles() < it[3]) return;
      const own = store.get('garden', []); own.push(it[0]);
      store.set("spent", store.get("spent", 0) + it[3]); store.set('garden', own);
      corner(); $('[data-buy="' + it[0] + '"]')?.focus({preventScroll:true}); toast1(it[1], "In your garden!", it[2]);
    }
    if (d) { const r = store.get("revise", []); r.splice(+d.dataset.done, 1); store.set("revise", r); corner(); }
  });
  document.addEventListener('keydown', e => {
    const tab = e.target.closest?.('[data-pebble-view]'); if (!tab) return;
    const i = PEBBLE_VIEWS.findIndex(([id]) => id === tab.dataset.pebbleView);
    const next = e.key === 'ArrowRight' ? (i + 1) % 3 : e.key === 'ArrowLeft' ? (i + 2) % 3 : e.key === 'Home' ? 0 : e.key === 'End' ? 2 : -1;
    if (next >= 0) { e.preventDefault(); selectPebbleView(PEBBLE_VIEWS[next][0]); }
  });
  function fitGarden() {                                      // smaller scenery must not crop saved items at its edges
    $$('.garden .gi').forEach(el => { if (el.parentElement.clientWidth) gplace(el, parseFloat(el.style.left), parseFloat(el.style.top)); });
  }
  addEventListener('resize', fitGarden);
  // Moving things around the garden: drag with a finger or mouse, or arrow keys; kept on this device.
  function gplace(el, x, y) {
    const g = el.parentElement, gw = g.clientWidth, gh = g.clientHeight;
    x = Math.max(0, Math.min(100 - 100 * el.offsetWidth / gw, x)); y = Math.max(0, Math.min(100 - 100 * el.offsetHeight / gh, y));
    el.style.left = x.toFixed(1) + "%"; el.style.top = y.toFixed(1) + "%";
    return [+x.toFixed(1), +y.toFixed(1)];
  }
  function gsave(el, xy) {
    const pos = store.get("gpos", {}), top = Math.max(0, ...Object.values(pos).map((p) => p[2] || 0)) + 1;
    pos[el.dataset.g] = [xy[0], xy[1], top]; store.set("gpos", pos); el.style.zIndex = 2 + top;
  }
  let drag = null;
  document.addEventListener("pointerdown", (e) => {
    const el = e.target.closest(".garden .gi"); if (!el || (e.button && e.button !== 0)) return;
    e.preventDefault();
    const r = el.getBoundingClientRect();
    drag = { el, dx: e.clientX - r.left, dy: e.clientY - r.top, xy: null };
    el.classList.add("lift"); el.style.zIndex = 99;
    try { el.setPointerCapture(e.pointerId); } catch (err) {}
  });
  document.addEventListener("pointermove", (e) => {
    if (!drag) return;
    const g = drag.el.parentElement.getBoundingClientRect();
    drag.xy = gplace(drag.el, 100 * (e.clientX - drag.dx - g.left) / g.width, 100 * (e.clientY - drag.dy - g.top) / g.height);
  });
  const drop = () => {
    if (!drag) return;
    drag.el.classList.remove("lift");
    gsave(drag.el, drag.xy || [parseFloat(drag.el.style.left), parseFloat(drag.el.style.top)]);
    drag = null;
  };
  document.addEventListener("pointerup", drop); document.addEventListener("pointercancel", drop);
  document.addEventListener("keydown", (e) => {
    const el = e.target.closest && e.target.closest(".garden .gi");
    const k = { ArrowLeft: [-2, 0], ArrowRight: [2, 0], ArrowUp: [0, -2], ArrowDown: [0, 2] }[e.key];
    if (!el || !k) return;
    e.preventDefault();
    gsave(el, gplace(el, parseFloat(el.style.left) + k[0], parseFloat(el.style.top) + k[1]));
  });

  // ---------------------------------------------------------------- a monthly report to print, from this device
  const rp = $(".reportpage");
  if (rp) {
    const names = JSON.parse($("#papers").textContent), sel = $(".month", rp), input = $(".name", rp), now = new Date();
    for (let i = 0; i < 3; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      sel.insertAdjacentHTML("beforeend", `<option value="${ymd(d).slice(0, 7)}">${d.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}</option>`);
    }
    input.value = store.get("name", "");
    const draw = () => {
      const m = sel.value, label = sel.selectedOptions[0].textContent, old = grownUp();
      const days = store.get("days", []).filter((d) => d.startsWith(m)).sort();
      let run = 0, bestRun = 0, prev = null;
      days.forEach((d) => { const t = new Date(d + "T12:00:00"); run = prev && (t - prev) / 864e5 === 1 ? run + 1 : 1; bestRun = Math.max(bestRun, run); prev = t; });
      const read = store.get("read", []).filter((k) => k.slice(-10).startsWith(m));
      const papers = [...new Set(read.map((k) => names[k.slice(0, -11)]).filter(Boolean))];
      const ans = store.get("answers", []).filter((a) => a.d.startsWith(m)), right = ans.filter((a) => a.ok).length;
      const topics = topicStats(ans), have = store.get("badges", {});
      const won = BADGES.filter((b) => (have[b.id] || "").startsWith(m)).map(nameOf);
      $(".mo", rp).textContent = label;
      $(".rt", rp).textContent = `${old ? "Monthly reading report" : "My month of news"}${input.value.trim() ? ": " + input.value.trim() : ""}`;
      $(".rbody", rp).innerHTML = `<div class="dash"><div><b>${days.length}</b><small>days with a paper read</small></div><div><b>${read.length}</b><small>papers read</small></div>
        <div><b>${ans.length ? Math.round(100 * right / ans.length) + "%" : "–"}</b><small>answers right${ans.length ? ` (${right} of ${ans.length})` : ""}</small></div>
        <div><b>${bestRun} ${bestRun === 1 ? "day" : "days"}</b><small>longest streak</small></div></div>
        ${papers.length ? `<p><b>Papers:</b> ${papers.map(esc).join(", ")}</p>` : ""}
        ${topics.length ? `<p><b>Strongest:</b> ${topics.slice(0, 2).map(([t, r]) => `${esc(t)} (${Math.round(r * 100)}%)`).join(", ")}</p>` : ""}
        ${topics.filter(([, r]) => r < 0.6).length ? `<p><b>To practise:</b> ${topics.filter(([, r]) => r < 0.6).slice(-2).map(([t, r]) => `${esc(t)} (${Math.round(r * 100)}%)`).join(", ")}</p>` : ""}
        <p><b>${old ? "Achievements" : "Badges"} this month:</b> ${won.length ? won.map(esc).join(", ") : "none yet"}</p>
        <p><b>Countries in the news so far:</b> ${store.get("lands", []).length}</p>${passport("Countries read about")}`;
    };
    sel.addEventListener("change", draw);
    input.addEventListener("input", () => { store.set("name", input.value.trim()); draw(); });
    $(".print", rp).addEventListener("click", () => window.print());
    draw();
    return;
  }

  // ---------------------------------------------------------------- a certificate to print, for a badge earned here
  const cp = $(".certpage");
  if (cp) {
    const id = new URLSearchParams(location.search).get("b"), b = BADGES.find((x) => x.id === id), when = store.get("badges", {})[id];
    if (!b || !when) { $(".none", cp).hidden = false; return; }
    const c = $(".cert", cp), input = $(".name", cp);
    c.hidden = false; $(".ctl", cp).hidden = false;
    $(".kind", c).textContent = grownUp() ? "Certificate of achievement" : "Certificate";
    $(".bn", c).textContent = nameOf(b);
    $(".bd", c).textContent = "for " + b.did;
    $(".dt", c).textContent = new Date(when + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
    const fill = () => { $(".nm", c).textContent = input.value.trim() || " "; };
    input.value = store.get("name", ""); fill();
    input.addEventListener("input", () => { store.set("name", input.value.trim()); fill(); });
    $(".print", cp).addEventListener("click", () => window.print());
    return;
  }

  // ---------------------------------------------------------------- lobby navigation
  function lobbyNavigation() {
    const panels = $$(".lobby-panel"), nav = $$(".childnav [data-view]");
    const header = $(".bar"), sizeHeader = () => {
      if (header) root.style.setProperty("--bar-height", header.offsetHeight + "px");
    };
    sizeHeader();
    if (header && window.ResizeObserver) new ResizeObserver(sizeHeader).observe(header);
    const route = (focus) => {
      const hash = location.hash.slice(1);
      const view = ["stories", "map", "explore"].includes(hash) ? "explore"
        : ["me", "badges", "garden", "progress"].includes(hash) ? "me" : "today";
      panels.forEach((panel) => { panel.hidden = panel.id !== view; });
      nav.forEach((link) => {
        if (link.dataset.view === view) link.setAttribute("aria-current", "page");
        else link.removeAttribute("aria-current");
      });
      const active = document.getElementById(view);
      if (['badges', 'garden', 'progress'].includes(hash) && grownUp()) corner(hash);
      if (hash === "badges") { const badges = $("#badges details"); if (badges) badges.open = true; }
      if (view === 'me') requestAnimationFrame(fitGarden);
      requestAnimationFrame(() => {
        if (view === "explore") $$(".where.wide").forEach((fig) => { if ($("svg", fig)) lobbyPins(fig); });
        const target = document.getElementById(hash);
        if (["stories", "map", "badges"].includes(hash) && target) target.scrollIntoView({block:"start"});
        else { window.scrollTo(0, 0); if (focus) $("h2", active)?.focus({preventScroll:true}); }
      });
    };
    addEventListener("hashchange", () => route(true));
    route(false);
  }

  // ---------------------------------------------------------------- the lobby: who's reading?
  const whos = $$(".who");
  if (whos.length) {
    if (WD) {                                                // each paper's little map, zoomed to its lead story
      worldDefs();
      $$(".mini").forEach((m) => {
        const b = m.dataset.box.split(" ").map(Number), xy = proj(+m.dataset.lon, +m.dataset.lat);
        const sea = !m.dataset.c;                            // an ocean: zoom out enough to see land
        let w = Math.max(b[2] - b[0], sea ? 150 : 60) * 1.8, h = Math.max(b[3] - b[1], sea ? 110 : 45) * 1.8;
        if (w / h < 4 / 3) w = h * 4 / 3; else h = w * 3 / 4;
        const vb = [(b[0] + b[2]) / 2 - w / 2, (b[1] + b[3]) / 2 - h / 2, w, h];
        const hi = (m.dataset.c || "").split("|").filter((c) => shapes[c])
          .map((c) => `<path class="hi" d="${shapes[c].d}" vector-effect="non-scaling-stroke"/>`).join("");
        m.innerHTML = `<svg viewBox="${vb.join(" ")}" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><use href="#rp-world"/>${hi}
          <circle class="dot" cx="${xy[0]}" cy="${xy[1]}" r="${w / 24}" vector-effect="non-scaling-stroke"/></svg>`;
      });
    }
    const picker = $(".pick"), hi = $(".hello");
    const pick = (b, asked) => {
      store.set("band", b); band = b;
      whos.forEach((w) => w.setAttribute("aria-pressed", String(w.dataset.band === b)));
      $$(".tile").forEach((t) => { t.hidden = !!b && t.dataset.band !== b; });
      $$(".where.wide").forEach((f) => { if ($("svg", f)) lobbyPins(f); });
      const older = b && !/6–8|9–11/.test(b);               // the story so far, at the reader's level
      $$(".bigstory").forEach((a) => { a.href = older ? a.dataset.old : a.dataset.young; });
      picker.hidden = true; hi.hidden = false;               // asked once, then a line to change it
      $("span", hi).innerHTML = b ? `Hi! Papers for <b>${esc(b.replace("Ages", "ages"))}</b>` : "Papers for <b>every age</b>";
      if (asked) $(".change", hi).focus();
      shelf(); corner();
    };
    whos.forEach((w) => w.addEventListener("click", () => pick(w.dataset.band, true)));
    $(".change", hi).addEventListener("click", () => { hi.hidden = true; picker.hidden = false; $(".who[aria-pressed=true]", picker)?.focus(); });
    const was = store.get("band", null);
    if (was === null) { $$(".tile").forEach((t) => { t.hidden = false; }); corner(); } else pick(was);
    const done = store.get("read", []);                      // papers read on this device
    $$(".tile").forEach((t) => { if (done.includes(t.dataset.key)) $(".done", t).hidden = false; });
    document.addEventListener("click", (e) => {             // the chips open "My reading" with the badges
      const chip = e.target.closest(".chip");
      if (chip) {
        if (grownUp() && chip.getAttribute('href') === '#badges') corner('badges');
        const d = $("#badges details"); if (d) d.open = true;
      }
    });
    lobbyNavigation();
    return;
  }

  // ---------------------------------------------------------------- read aloud, sentence by sentence
  const speech = "speechSynthesis" in window ? window.speechSynthesis : null;
  let reading = null, narrationAudio = null, speechTicket = 0, listening = null, resetReadingData = false;
  const player = $("#listen-player"), resumePrompt = $("#listen-resume");
  const narrationNode = $("#narration");
  let narration = {};
  try { narration = narrationNode ? JSON.parse(narrationNode.textContent) : {}; } catch (e) { /* device voice remains available */ }
  const positions = () => {
    const saved = store.get("listening", {});
    return saved && typeof saved === "object" && !Array.isArray(saved) ? saved : {};
  };
  const editionKey = $(".issue")?.dataset.key || location.pathname;
  const clock = (n) => `${Math.floor(n / 60)}:${String(Math.floor(n % 60)).padStart(2, "0")}`;
  function savePosition(done = false) {
    if (!listening || resetReadingData) return;
    const saved = positions();
    if (done) delete saved[editionKey];
    else saved[editionKey] = { card: reading.id, variant: listening.variant, src: listening.track?.src || "",
      time: narrationAudio ? narrationAudio.currentTime : 0, sentence: listening.index, edition: listening.edition,
      mode: narrationAudio ? "audio" : "speech", updated: Date.now() };
    const recent = Object.entries(saved).sort((a, b) => (b[1]?.updated || 0) - (a[1]?.updated || 0)).slice(0, 80);
    store.set("listening", Object.fromEntries(recent));
  }
  function savedCard() {
    const saved = positions()[editionKey];
    return saved && $$(".card").find(c => c.id === saved.card && $(".read", c)) ? saved : null;
  }
  function refreshResume() { if (resumePrompt) resumePrompt.hidden = !!reading || !savedCard(); }
  document.addEventListener("rp-rate", () => { if (narrationAudio) narrationAudio.playbackRate = store.get("rate", 1); });
  window.addEventListener("pagehide", () => stop());
  document.addEventListener("rp-reading-reset", () => { resetReadingData = true; stop(); });
  document.addEventListener("visibilitychange", () => { if (document.hidden) savePosition(); });
  const voice = () => {
    const vs = speech.getVoices().filter((v) => /^en/i.test(v.lang));
    return vs.find((v) => /en-IN/i.test(v.lang) && v.localService) || vs.find((v) => v.localService) || vs[0] || null;
  };
  function updatePlayer() {
    if (!player || !listening) return;
    const state = listening, audio = narrationAudio, segments = state.track?.segments;
    const duration = audio && Number.isFinite(audio.duration) && audio.duration > 0 ? audio.duration : segments?.at(-1)?.end || 0;
    const elapsed = audio ? audio.currentTime : state.index;
    const total = audio ? duration : state.parts.length;
    const range = $("input", player);
    range.max = String(total || 1); range.value = String(Math.min(elapsed, total));
    range.step = audio ? "0.1" : "1";
    range.disabled = !total;
    $(".listen-time", player).textContent = audio ? `${clock(elapsed)} / ${clock(duration)}` : `Sentence ${Math.min(state.index + 1, total)} of ${total}`;
    range.setAttribute("aria-valuetext", $(".listen-time", player).textContent);
    $("[data-listen=toggle]", player).textContent = state.paused ? "Resume" : "Pause";
    $("[data-listen=follow]", player).hidden = state.follow;
    const following = $("[data-listen=auto-follow]", player);
    following.setAttribute("aria-pressed", String(state.follow));
    following.textContent = state.follow ? "Follow text: on" : "Follow text: off";
    $("[data-listen=previous]", player).disabled = state.index === 0;
    $("[data-listen=next]", player).disabled = state.index >= state.parts.length - 1;
    $(".listen-status", player).textContent = state.paused ? "Paused. Your place is saved on this device." : "";
    const button = $(".read", reading);
    button.setAttribute("aria-pressed", String(!state.paused));
    button.setAttribute("aria-label", state.paused ? "Resume reading this story" : "Pause reading this story");
    button.lastChild.textContent = state.paused ? " Resume" : " Pause";
  }
  function highlight(sentence) {
    $$(".s.now").forEach(s => s.classList.remove("now"));
    if (!sentence) return;
    sentence.classList.add("now");
    if (listening) listening.sentence = sentence;
    if (listening && !listening.follow) return;
    const rect = sentence.getBoundingClientRect(), header = $("header.bar");
    const top = header?.getBoundingClientRect().bottom || 0;
    const bottom = player && !player.hidden ? player.getBoundingClientRect().top : window.innerHeight - 86;
    if (rect.top < top + 8 || rect.bottom > bottom - 8) window.scrollBy({top:rect.top - top - Math.max(8, (bottom - top - rect.height) / 2), behavior:calm() ? "auto" : "smooth"});
  }
  function stop(done = false) {
    savePosition(done);
    reading = null; listening = null; ++speechTicket;
    if (narrationAudio) {
      narrationAudio.onended = narrationAudio.onerror = narrationAudio.ontimeupdate = narrationAudio.onloadedmetadata = narrationAudio.onpause = narrationAudio.onplay = null;
      narrationAudio.pause(); narrationAudio.removeAttribute("src"); narrationAudio.load(); narrationAudio = null;
    }
    if (speech) speech.cancel();
    $$(".s.now").forEach(s => s.classList.remove("now"));
    $$(".read").forEach(b => { b.setAttribute("aria-pressed", "false"); b.setAttribute("aria-label", "Read this to me"); b.lastChild.textContent = " Read it to me"; });
    if (player) player.hidden = true;
    if (player) $(".listen-more", player).open = false;
    document.body.classList.remove("listening"); refreshResume();
  }
  document.addEventListener('rp-thread-report', () => stop());
  function say(text, onend) {
    if (!speech) { onend(); return; }
    const ticket = speechTicket;
    const u = new SpeechSynthesisUtterance(text);
    const v = voice(); if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = store.get("rate", 1);
    u.onend = u.onerror = () => { if (ticket === speechTicket) onend(); };
    speech.speak(u);
  }
  function toggleListening() {
    if (!listening) return;
    listening.paused = !listening.paused;
    if (!listening.paused && listening.follow) highlight(listening.sentence || listening.parts[listening.index]);
    if (narrationAudio) {
      if (listening.paused) narrationAudio.pause();
      else playAudio();
    } else {
      ++speechTicket; if (speech) speech.cancel();
      if (!listening.paused) speakSentence();
    }
    savePosition(); updatePlayer();
  }
  function speakSentence() {
    if (!listening || listening.paused) return;
    const state = listening;
    if (state.index >= state.parts.length) { finishStory(); return; }
    highlight(state.parts[state.index]); savePosition(); updatePlayer();
    say(state.parts[state.index].textContent, () => { if (listening === state) { ++state.index; speakSentence(); } });
  }
  function playAudio() {
    const audio = narrationAudio, state = listening;
    if (!audio || !state) return;
    const result = audio.play();
    if (result) result.catch(() => {
      if (narrationAudio !== audio || listening !== state || state.paused) return;
      // A phone can require another tap after an interruption; do not switch voices for an autoplay restriction.
      state.paused = true; savePosition(); updatePlayer();
    });
  }
  const playableCards = () => $$(".card").filter(c => { const b = $(".read", c); return b && !b.hidden && $$(".s", c).length; });
  function revealCard(card) {
    if ($(".issue")?.dataset.mode === "cards") document.dispatchEvent(new CustomEvent("rp-show", {detail:Number(card.dataset.i)}));
  }
  function finishStory() {
    if (!listening) return;
    const cards = playableCards(), next = listening.edition ? cards[cards.indexOf(reading) + 1] : null;
    const audio = narrationAudio, follow = listening.follow, scroll = window.scrollY;
    stop(true);
    if (next) {
      revealCard(next);
      if (!follow) window.scrollTo({top:scroll});
      readCard(next, $(".read", next), true, true, audio);
      listening.follow = follow; updatePlayer();
    }
  }
  function skipSentence(delta) {
    if (!listening) return;
    const state = listening;
    state.index = Math.max(0, Math.min(state.parts.length - 1, state.index + delta)); state.follow = true;
    if (narrationAudio) {
      const segment = state.track.segments.find(s => $$(".s", reading)[s.index] === state.parts[state.index]);
      if (segment) { narrationAudio.currentTime = segment.start; narrationAudio.ontimeupdate(); }
    } else {
      ++speechTicket; if (speech) speech.cancel();
      if (!state.paused) speakSentence(); else highlight(state.parts[state.index]);
    }
    savePosition(); updatePlayer();
  }
  function readCard(card, btn, restart = false, editionMode = false, reusableAudio = null) {
    if (reading === card && !restart) { toggleListening(); return; }
    stop();
    const parts = $$(".s", card).filter(x => !x.closest("[hidden]"));
    if (!parts.length) return;
    const key = String($$(".card").indexOf(card));
    const variant = $(".easy", card)?.getAttribute("aria-pressed") === "true" ? "easy" : "original";
    const track = narration[key]?.[variant];
    const previous = positions()[editionKey];
    const saved = !restart && previous?.card === card.id && previous.variant === variant && previous.src === (track?.src || "") ? previous : null;
    reading = card;
    listening = {parts, track, variant, edition:editionMode || !!saved?.edition, follow:true, paused:false,
      index:Math.max(0, Math.min(parts.length - 1, Number(saved?.sentence) || 0))};
    if (player) {
      player.hidden = false; document.body.classList.add("listening");
      const cards = playableCards();
      $(".listen-title", player).textContent = (listening.edition ? `Section ${cards.indexOf(card) + 1} of ${cards.length} · ` : "") + ($("h2:not([hidden])", card)?.textContent || "Read it to me");
    }
    if (resumePrompt) resumePrompt.hidden = true;
    store.set("heard", store.get("heard", 0) + 1); award();
    const state = listening, all = $$(".s", card);
    if (track?.segments?.length && typeof Audio !== "undefined") {
      const audio = reusableAudio || new Audio(); narrationAudio = audio;
      audio.preload = "auto"; audio.src = track.src; audio.playbackRate = store.get("rate", 1);
      audio.onpause = () => { if (listening === state && !audio.ended) { state.paused = true; savePosition(); updatePlayer(); } };
      audio.onplay = () => { if (listening === state) { state.paused = false; updatePlayer(); } };
      const fallbackStart = saved?.mode === "speech" ? track.segments[listening.index]?.start || 0 : 0;
      const start = Math.max(0, Math.min(Number(saved?.time) || fallbackStart, track.segments.at(-1).end));
      audio.onloadedmetadata = () => { if (listening === state) { audio.currentTime = start; updatePlayer(); } };
      let last = -1, savedSecond = -1;
      audio.ontimeupdate = () => {
        if (listening !== state || narrationAudio !== audio) return;
        const segment = track.segments.find(x => audio.currentTime >= x.start && audio.currentTime < x.end);
        if (segment && segment.index !== last) {
          last = segment.index; const sentence = all[segment.index];
          state.index = Math.max(0, parts.indexOf(sentence));
          if (sentence && !sentence.closest("[hidden]")) highlight(sentence);
        }
        const second = Math.floor(audio.currentTime);
        if (second !== savedSecond) { savedSecond = second; savePosition(); }
        updatePlayer();
      };
      audio.onended = () => { if (listening === state) finishStory(); };
      audio.onerror = () => {
        if (listening !== state || narrationAudio !== audio) return;
        audio.onended = audio.onerror = audio.ontimeupdate = audio.onloadedmetadata = audio.onpause = audio.onplay = null;
        audio.pause(); narrationAudio = null;
        if (speech) speakSentence(); else { stop(); }
      };
      if ("caches" in window && navigator.serviceWorker?.controller) {
        const url = new URL(track.src, location.href).href;
        caches.keys().then(keys => {
          const key = keys.find(k => k.startsWith("rp-"));
          if (key) return caches.open(key).then(async cache => { if (!await cache.match(url)) await cache.add(url); });
        }).catch(() => {});
      }
      updatePlayer(); playAudio(); return;
    }
    speakSentence();
  }
  if (player) {
    $("[data-listen=auto-follow]", player).addEventListener("click", () => {
      if (!listening) return;
      listening.follow = !listening.follow;
      $(".listen-more", player).open = false;
      if (listening.follow) highlight(listening.sentence || listening.parts[listening.index]);
      updatePlayer();
    });
    $("[data-listen=previous]", player).addEventListener("click", () => skipSentence(-1));
    $("[data-listen=next]", player).addEventListener("click", () => skipSentence(1));
    $("[data-listen=follow]", player).addEventListener("click", () => { if (listening) { listening.follow = true; highlight(listening.sentence); updatePlayer(); } });
    $("[data-listen=toggle]", player).addEventListener("click", toggleListening);
    $("[data-listen=close]", player).addEventListener("click", () => stop());
    $("[data-listen=restart]", player).addEventListener("click", () => { if (reading) readCard(reading, $(".read", reading), true, listening.edition); });
    $("input", player).addEventListener("change", e => {
      if (!listening) return;
      listening.follow = true;
      if (narrationAudio) { narrationAudio.currentTime = +e.target.value; narrationAudio.ontimeupdate(); }
      else {
        ++speechTicket; if (speech) speech.cancel();
        listening.index = Math.min(listening.parts.length - 1, Math.floor(+e.target.value));
        if (!listening.paused) speakSentence(); else highlight(listening.parts[listening.index]);
      }
      savePosition(); updatePlayer();
    });
  }
  // Follow stays on during ordinary scrolling. It is disabled only by the explicit player control.
  window.addEventListener("resize", () => { if (listening?.follow) highlight(listening.sentence); });
  $("#listen-edition")?.addEventListener("click", () => {
    const first = playableCards()[0]; if (!first) return;
    if ($("#read")?.hidden) tab("read");
    revealCard(first); readCard(first, $(".read", first), true, true);
  });
  if (resumePrompt) $$("button", resumePrompt).forEach(b => b.addEventListener("click", () => {
    const saved = savedCard(); if (!saved) return;
    const card = $$(".card").find(c => c.id === saved.card);
    // Reveal the saved card in the younger reader's one-story-at-a-time layout.
    revealCard(card);
    if ($(".easy", card)) easyView(card, saved.variant === "easy");
    readCard(card, $(".read", card), b.dataset.listen === "restart", !!saved.edition);
  }));
  $$(".read").forEach(b => {
    const card = b.closest(".card");
    if (!speech && !narration[String($$(".card").indexOf(card))]) { b.hidden = true; return; }
    if (narration[String($$(".card").indexOf(card))]) b.insertAdjacentHTML("afterend", ' <small class="narration-credit">AI narration</small>');
    b.addEventListener("click", () => readCard(card, b));
  });
  if ($("#listen-edition")) $("#listen-edition").hidden = !playableCards().length;
  refreshResume();

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
    $("#read").addEventListener("touchstart", (e) => { x0 = e.target.closest(".where,.follow-thread") ? null : e.touches[0].clientX; }, { passive: true });
    $("#read").addEventListener("touchend", (e) => {
      if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) > 60) show(at + (dx < 0 ? 1 : -1));
    });
    document.addEventListener("keydown", (e) => {
      if ($("#read").hidden || e.target.matches("select,input,button,textarea") || e.target.closest("#listen-player")) return;
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
  // How old the reader is sets each game's level and its tone: 0 = 6–8, 1 = 9–11, 2 = 12–14, 3 = 15+.
  const TIERS = { "Ages 6–8": 0, "Ages 9–11": 1, "Ages 12–14": 2, "Ages 15+": 3 };
  const tier = TIERS[main.dataset.band] === undefined ? 1 : TIERS[main.dataset.band], grown = tier >= 2;
  const say2 = (kid, older) => (grown ? older : kid);
  const key = main.dataset.key;
  const starsFor = (pts, total) => (pts >= total ? 3 : pts / total >= 0.6 ? 2 : 1);
  const starLine = (n) => `<p class="stars" aria-label="${n} stars">${"★".repeat(n)}${"☆".repeat(3 - n)}</p>`;
  const best = (name) => store.get("stars-" + key + "-" + name, 0);
  // The first try is what counts: a game's first try starts with its first answer, its stars are kept apart from
  // the best so far, and only the first try earns pebbles and counts towards badges and progress. Replays are
  // practice, as many as you like (seeing the answers and playing again is learning, not winning).
  let playing = "", firstGo = false;
  const began = (name) => store.get("go-" + key + "-" + name, false);
  const firstOf = (name) => {                               // stars on the first try; null if not finished yet
    const f = store.get("first-" + key + "-" + name, null);
    return f !== null ? f : began(name) ? 0 : best(name) || null;   // from before first tries were kept: the best
  };
  const run = (g) => { playing = g.id; firstGo = firstOf(g.id) === null && !began(g.id); g.run(); };
  const markTried = () => { if (firstGo) store.set("go-" + key + "-" + playing, true); };
  const hinted = () => { if (firstGo) addTo("hinted", key, 400); };
  const firstHit = (k, v) => { if (firstGo) addTo(k, v, 2000); };
  const stars3 = (n) => "★".repeat(n) + "☆".repeat(3 - n);
  function scores(name, first) {                            // first try and best so far, side by side
    const f = firstOf(name), b = best(name);
    if (f === null && !b) return "";
    return `<p class="scores"><span>${say2("First try", "First attempt")} <b aria-label="${f || 0} stars">${f === null ? "–" : stars3(f)}</b></span>
      <span>${say2("Now", "Best")} <b aria-label="${b} stars">${stars3(b)}</b></span></p>`
      + (first ? "" : `<p class="practice">${say2("Practice round! Your first-try stars are the ones that count for badges and pebbles.",
          "Practice round: only first attempts count towards achievements.")}</p>`);
  }
  const GAMES = [];
  function keep(name, n) {            // the stars, then a Full set and any new badges: what to show at the end
    const first = firstGo && playing === name;
    store.set("stars-" + key + "-" + name, Math.max(n, best(name)));
    if (first) {
      store.set("first-" + key + "-" + name, n); firstGo = false;
      if (n === 3) addTo("3s-" + name, key);
    }
    let set = false;
    if (GAMES.length > 1 && GAMES.every((g) => best(g.id) > 0) && addTo("sets", key)) {
      set = true;
      if (!store.get("hinted", []).includes(key)) addTo("clean", key);
    }
    const gain = (first ? n : 0) + (set ? 2 : 0);           // pebbles: first-try stars, and 2 for a Full set
    earn(gain);
    const fresh = award();
    if (!grown && (set || n === 3)) setTimeout(confetti, 200);
    return (gain && !grown ? `<p class="earned"><i class="pg"></i> +${gain} ${gain === 1 ? "pebble" : "pebbles"} for your garden</p>` : "")
      + (set ? `<div class="fullset"><b>${say2("Full set! 🎉", "Set complete.")}</b> ${say2(`You played all ${GAMES.length} of today's games.`,
              `All ${GAMES.length} of today's games played.`)}</div>` : "")
      + fresh.map((b) => `<a class="newbadge" href="../certificate.html?b=${b.id}"><span class="bi" aria-hidden="true">${b.icon}</span>
          <span><b>${grown ? "Achievement" : "New badge"}: ${esc(nameOf(b))}</b><small>For ${esc(b.did)} · Print the certificate 🖨️</small></span></a>`).join("");
  }
  if (data.quiz.length) GAMES.push({ id: "quiz", ic: "❓", name: "Quiz", sub: data.quiz.length + " questions about today's paper", run: quiz });
  if (window.WORLD && data.where.length >= 2) GAMES.push({ id: "map", ic: "📍", name: "Map hunt", sub: say2("Find where the stories happened", "Pin where the stories happened"), run: hunt });
  if (data.numbers.length) GAMES.push({ id: "numbers", ic: "🎚️", name: "Guess the number", sub: say2("Numbers from today's news", "Estimate the numbers in the news"), run: numbers });
  if (data.order.length) GAMES.push({ id: "order", ic: "🔀", name: "Put it in order", sub: say2("What happened first?", "Order the events of a big story"), run: order });
  if (data.facts.length) GAMES.push({ id: "facts", ic: "🕵️", name: "Fact or fiction?", sub: "True, or not true?", run: facts });
  if (data.vocab.length >= 2) GAMES.push({ id: "words", ic: "🔤", name: "Word match", sub: "Match each new word to its meaning", run: () => match("words") });
  else if (data.stories.length >= 2) GAMES.push({ id: "words", ic: "📰", name: "Story match", sub: "Match each headline to its story", run: () => match("words") });
  function game() {
    stop();
    box.className = "card game" + (grown ? " grown" : "");
    if (!GAMES.length) { box.innerHTML = "<p>No game for this issue. Come back tomorrow!</p>"; return; }
    if (GAMES.length === 1) { run(GAMES[0]); return; }
    const played = GAMES.filter((g) => best(g.id) > 0).length;
    box.innerHTML = `<h2>${say2("Pick a game", "Today's games")}</h2><p class="how">${played === GAMES.length
      ? say2("Full set done! Play again to practise. Your first-try stars are the ones that count.",
             "Set complete. Replay any game to practise; first attempts are what count.")
      : say2(`Play all ${GAMES.length} for a Full set ⭐ (${played} done)`, `Play all ${GAMES.length} to complete the set (${played} done).`)}</p>
      <div class="menu">${GAMES.map((g, i) =>
      `<button type="button" data-g="${i}"><span class="ic" aria-hidden="true">${g.ic}</span><span><b>${g.name}</b><small>${g.sub}</small></span>
       ${menuStars(g.id)}</button>`).join("")}</div>`;
    $$(".menu button", box).forEach((b) => b.addEventListener("click", () => run(GAMES[+b.dataset.g])));
  }
  function menuStars(id) {
    const f = firstOf(id), b = best(id);
    if (f === null && !b) return "";
    return `<span class="got" aria-label="First try ${f || 0} stars, now ${b} stars"><small>${say2("1st try", "1st")}</small>${f === null ? "–" : stars3(f)}
      <small>${say2("Now", "Best")}</small>${stars3(b)}</span>`;
  }
  const back = () => (GAMES.length > 1 ? `<button type="button" class="back">← ${say2("All games", "Today's games")}</button>` : "");
  const wireBack = () => { $$(".back", box).forEach((b) => b.addEventListener("click", game)); };
  function readAgain(card) {
    if (card < 0) return "";
    return ` <a href="#" data-card="${card}">Read it again</a>`;
  }
  const TOPICS = [["⭐", "Top stories"], ["🔭", "Science"], ["🔬", "Science"], ["🌱", "Nature"], ["🩺", "Health"], ["🏅", "Sport"],
    ["💰", "Money"], ["🗳️", "Politics"], ["📜", "History"], ["🎨", "Culture"], ["🏙️", "My city"], ["🪔", "India"], ["🌍", "World"]];
  const topicOf = (card) => {
    const c = card >= 0 ? $$("#read .card")[card] : null, d = c && $(".desk", c), t = d ? d.textContent.trim() : "";
    const hit = TOPICS.find(([i]) => t.startsWith(i)); return hit ? hit[1] : "Other";
  };
  function logAnswer(card, ok, miss) {                       // for My progress and the monthly report; misses to revise (12+)
    if (!firstGo) return;                                    // practice rounds don't count
    markTried();
    const a = store.get("answers", []); a.push({ d: ymd(new Date()), ts: Date.now(), t: topicOf(card), ok: !!ok }); store.set("answers", a.slice(-600));
    if (!ok && grown && miss) { const r = store.get("revise", []); r.unshift({ ...miss, p: $(".title h1").textContent }); store.set("revise", r.slice(0, 30)); }
    skillCheck();
  }
  const headline = (card) => { const c = card >= 0 ? $$("#read .card")[card] : null, h = c && $("h2", c); return h ? h.textContent.trim() : ""; };
  box.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-card]"); if (!a) return;
    e.preventDefault(); tab("read");
    const i = +a.dataset.card;
    if (show) { if (cards[i]) show(i); }
    else { const c = $$("#read .card")[i]; if (c) c.scrollIntoView({ behavior: "smooth" }); }
  });
  function ending(n, line, again) {   // the last screen of a game: stars, first try and best, a Full set, new badges, play again
    const first = firstGo && playing === again.id, more = keep(again.id, n);
    box.innerHTML = `<p class="cheer" role="status">${line}</p>${starLine(n)}${scores(again.id, first)}${more}
      <button type="button" class="big again">${say2("Play again to practise", "Practise again")}</button> ${back()}`;
    $(".again", box).onclick = () => run(again); wireBack();
  }
  function finishText(pts, right, total, g) {
    const n = starsFor(pts, total);
    ending(n, right === total && pts >= total ? say2("Every one right! 🎉", "All correct.")
      : say2(`You got ${right} out of ${total}! 🎉`, `${right} of ${total} correct.`), g);
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
    let sel = null, matched = 0, misses = 0;
    const mk = (text, i, side) => {
      const b = document.createElement("button"); b.type = "button"; b.textContent = text; b.dataset.i = i;
      b.addEventListener("click", () => tap(b, side)); return b;
    };
    shuffle(pairs.map((p, i) => [p[0], i])).forEach(([t, i]) => L.appendChild(mk(t, i, "L")));
    shuffle(pairs.map((p, i) => [p[1], i])).forEach(([t, i]) => R.appendChild(mk(t, i, "R")));
    const praise = grown ? ["Correct.", "Yes.", "Right.", "Good.", "Correct."] : ["Yes!", "Great!", "You got it!", "Brilliant!", "Spot on!"];
    function tap(b, side) {
      if (b.classList.contains("ok")) return;
      if (!sel || sel.side === side) { $$("button.sel", box).forEach((x) => x.classList.remove("sel")); sel = { b, side }; b.classList.add("sel"); return; }
      const a = sel.b; sel = null; a.classList.remove("sel"); markTried();
      if (a.dataset.i === b.dataset.i) {
        a.classList.add("ok"); b.classList.add("ok"); matched++; cheer.textContent = praise[matched % praise.length];
        if (matched === pairs.length) {
          const n = misses === 0 ? 3 : misses <= 2 ? 2 : 1;
          ending(n, n === 3 ? say2("All matched, no mistakes! 🎉", "All matched, no mistakes.") : say2("All matched! 🎉", "All matched."),
            { id: name, run: () => match(name) });
        }
      } else {
        misses++; [a, b].forEach((x) => { x.classList.add("no"); setTimeout(() => x.classList.remove("no"), 400); });
        cheer.textContent = say2("Not quite. Try another one!", "Not a match. Try again.");
      }
    }
  }
  function steps(items, g, render) {   // one question at a time; each scores 1, ½ (on a second try) or 0
    let i = 0, pts = 0, right = 0;
    const next = () => {
      if (i >= items.length) { finishText(pts, right, items.length, g); return; }
      render(items[i], i, items.length, (v) => { v = v === true ? 1 : +v || 0; pts += v; if (v > 0) right++; }, () => { i++; next(); });
    };
    next();
  }
  function speakBtn(text) { return speech ? `<button type="button" class="read say1" data-say="${esc(text)}">🔊 Hear it</button>` : ""; }
  box.addEventListener("click", (e) => { const b = e.target.closest(".say1"); if (b) { stop(); say(b.dataset.say, () => {}); } });
  function quiz() {
    // Adaptive: two right first time in a row brings a stretch question (from the same day's paper a step
    // older, about a story in this paper); a miss brings an easier one (a step younger). At Stone every third
    // question is a stretch; at Boulder the quiz starts stretched. The game is as long as this paper's quiz.
    const g = { id: "quiz", run: quiz }, own = data.quiz.slice(), up = shuffle(data.harder || []), down = shuffle(data.easier || []);
    const n = own.length, lvl = skill().l;
    let d = lvl === 2 ? 1 : 0, run = 0, i = 0, pts = 0, right = 0;
    const pick = () => {
      if (d > 0 && up.length) return [up.shift(), "up"];
      if (d < 0 && down.length) return [down.shift(), "down"];
      if (lvl === 1 && i % 3 === 2 && up.length) return [up.shift(), "up"];
      return own.length ? [own.shift(), ""] : up.length ? [up.shift(), "up"] : [down.shift(), "down"];
    };
    const ask = () => {
      if (i >= n) { finishText(pts, right, n, g); return; }
      const [q, kind] = pick();
      const tag = kind === "up" ? `<p class="lvltag up">${say2("⭐ Stretch question!", "Harder question")} <small>from ${esc(q.paper)}</small></p>`
        : kind === "down" ? `<p class="lvltag down">${say2("Here's an easier one 🙂", "Easier question")} <small>from ${esc(q.paper)}</small></p>` : "";
      box.innerHTML = `${back()}<p class="qn">Question ${i + 1} of ${n} · Level: ${SKILL[lvl]}</p>${tag}${young ? speakBtn(q.q + " " + q.options.join(". ")) : ""}
        <p class="q">${esc(q.q)}</p><div class="opts">${q.options.map((o, k) => `<button type="button" data-k="${k}">${esc(o)}</button>`).join("")}</div>
        <div class="fb" role="status"></div>`;
      wireBack();
      let tries = 0;
      $$(".opts button", box).forEach((b) => b.addEventListener("click", () => {
        const k = +b.dataset.k, ok = k === q.answer;
        tries++;
        if (!ok && tries === 1) {               // a clue and a second try, not just a cross
          b.disabled = true; b.classList.add("no"); hinted();
          const h = headline(q.card);
          $(".fb", box).innerHTML = `<p class="why hint"><b>${say2("Not quite! Have another go.", "Not quite. One more try.")}</b>
            ${h ? say2(`Hint: look in the story “${esc(h)}”.`, `The answer is in “${esc(h)}”.`) : say2("Think about what the paper said.", "")}</p>`;
          return;
        }
        const first = ok && tries === 1;
        pts += ok ? (tries === 1 ? 1 : 0.5) : 0; if (ok) right++;
        if (first) { run++; if (run >= 2) { d = Math.min(1, d + 1); run = 0; } } else { d = Math.max(-1, d - 1); run = 0; }
        logAnswer(q.card, first, { q: q.q, a: q.options[q.answer], why: q.why });
        $$(".opts button", box).forEach((x) => { x.disabled = true; if (+x.dataset.k === q.answer) x.classList.add("ok"); });
        if (!ok) b.classList.add("no");
        const nextUp = d > 0 && up.length && i + 1 < n;
        $(".fb", box).innerHTML = `<p class="why"><b>${ok ? (tries === 1 ? say2("Yes! ", "Correct. ") : say2("Got it on the second try! ", "Correct on the second try. "))
          : say2("Not this time. ", "Incorrect. ")}</b>${esc(q.why)}${ok ? "" : readAgain(q.card)}</p>
          ${nextUp && first && kind !== "up" ? `<p class="lvltag up">${say2("Two in a row! The next one's a stretch ⭐", "Two in a row: the next question is harder.")}</p>` : ""}
          <p><button type="button" class="big go nx">${i + 1 < n ? "Next question →" : say2("See my stars", "See my score")}</button></p>`;
        $(".nx", box).addEventListener("click", () => { i++; ask(); });
      }));
    };
    ask();
  }
  function facts() {
    const g = { id: "facts", run: facts };
    steps(data.facts, g, (f, i, n, score, next) => {
      box.innerHTML = `${back()}<p class="qn">Claim ${i + 1} of ${n}</p>${young ? speakBtn(f.claim) : ""}
        <p class="claim">${esc(f.claim)}</p><div class="opts tf"><button type="button" data-v="1">${grown ? "True" : "✅ True"}</button><button type="button" data-v="0">${grown ? "False" : "❌ Not true"}</button></div>
        <div class="fb" role="status"></div>`;
      wireBack();
      $$(".opts button", box).forEach((b) => b.addEventListener("click", () => {
        const said = b.dataset.v === "1", ok = said === f.true;
        score(ok);
        logAnswer(f.card, ok, { q: f.claim, a: f.true ? "True" : "Not true", why: f.why });
        $$(".opts button", box).forEach((x) => { x.disabled = true; if ((x.dataset.v === "1") === f.true) x.classList.add("ok"); });
        if (!ok) b.classList.add("no");
        $(".fb", box).innerHTML = `<p class="why"><b>${ok ? say2("Right! ", "Correct. ") : say2("Not quite. ", "Incorrect. ")}</b>It's ${f.true ? "true" : "not true"}. ${esc(f.why)}${ok ? "" : readAgain(f.card)}</p>
          <p><button type="button" class="big go nx">${i + 1 < n ? "Next →" : say2("See my stars", "See my score")}</button></p>`;
        $(".nx", box).addEventListener("click", next);
      }));
    });
  }

  // ---------------------------------------------------------------- Map hunt: tap where the story happened
  function unproj(x, y) {                                    // Equal Earth backwards: a point on the map to [lat, lon]
    const yy = (WD.h / 2 - y) / WD.s; let t = yy;
    for (let k = 0; k < 20; k++) {
      const t2 = t * t, t6 = t2 * t2 * t2;
      t -= (t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2)) - yy) / (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2));
    }
    const t2 = t * t, t6 = t2 * t2 * t2;
    const lon = (x - WD.w / 2) / WD.s * MM * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)) / Math.cos(t) / RAD;
    return [Math.asin(Math.max(-1, Math.min(1, Math.sin(t) / MM))) / RAD, Math.max(-180, Math.min(180, lon))];
  }
  const roundKm = (d) => (d < 100 ? Math.round(d / 10) * 10 : d < 1000 ? Math.round(d / 50) * 50 : Math.round(d / 100) * 100).toLocaleString("en");
  const stepUp = () => Math.min(3, tier + (skill().l === 2 ? 1 : 0));   // Boulder plays Map hunt and Guess the number a step older
  const NEARS = [[1000, 2500], [500, 1500], [500, 1000], [500, 1000]];   // km for 3 stars, then 2, at each age
  function hunt() {
    worldDefs();
    const g = { id: "map", run: hunt }, items = shuffle(data.where).slice(0, 3), got = [], mt = stepUp(), NEAR = NEARS[mt];
    let i = 0;
    const ask = () => {
      if (i >= items.length) {
        const n = Math.round(got.reduce((a, b) => a + b, 0) / got.length), close = got.filter((x) => x === 3).length;
        ending(n, say2(close === got.length ? "You found them all! 🎉" : `You found ${close} of ${got.length} spot on! 🌍`,
          `${close} of ${got.length} pinned within ${NEAR[0].toLocaleString("en")} km.`), g);
        return;
      }
      const p = items[i], country = p.names[0];
      const q = mt === 0 && country ? `Where is ${esc(country)}? Tap it on the map!`
        : say2(`Where did this happen? “${esc(p.h)}” Tap the map!`, `Where did this happen? “${esc(p.h)}” Tap the map.`);
      const vb = WORLDBOX();
      box.innerHTML = `${back()}<p class="qn">Place ${i + 1} of ${items.length}</p><p class="q">${q}</p>
        <div class="hunt"><svg viewBox="${vb.join(" ")}" role="img" aria-label="World map. Tap where it happened.">
        <rect class="sea" x="${vb[0]}" y="${vb[1]}" width="${vb[2]}" height="${vb[3]}"/><use href="#rp-world"/><g class="hl"></g><g class="mk"></g></svg></div>
        <div class="fb" role="status"></div>`;
      wireBack();
      const svg = $(".hunt svg", box);
      let answered = false, tries = 0;
      svg.addEventListener("click", (e) => {
        if (answered) return;
        tries++;
        const pt = new DOMPoint(e.clientX, e.clientY).matrixTransform(svg.getScreenCTM().inverse());
        const d = km(unproj(pt.x, pt.y), [p.lat, p.lon]), hl = $(".hl", svg);
        hl.innerHTML = p.countries.filter((c) => shapes[c]).map((c) => `<path d="${shapes[c].d}" vector-effect="non-scaling-stroke"/>`).join("");
        let inside = false;
        $$("path", hl).forEach((pa) => { try { if (pa.isPointInFill(new DOMPoint(pt.x, pt.y))) inside = true; } catch (err) {} });
        let n = d <= NEAR[0] ? 3 : d <= NEAR[1] ? 2 : 1;
        if (inside) n = mt <= 1 ? 3 : Math.max(n, 2);
        if (n === 1 && tries === 1) {                       // far off: a hint, and one more tap (worth 2 stars at most)
          hl.innerHTML = ""; hinted();
          $(".mk", svg).innerHTML = `<circle cx="${pt.x}" cy="${pt.y}" r="${6 * vb[2] / (svg.clientWidth || 340)}" class="tap miss"/>`;
          $(".fb", box).innerHTML = `<p class="why hint"><b>${say2("Not quite! Have another go.", "Not quite. One more try.")}</b>
            ${p.names.length ? say2(`Hint: it's in ${esc(p.names.slice(0, 2).join(" or "))}.`, `It's in ${esc(p.names.slice(0, 2).join(" or "))}.`) : say2("Hint: think about the story's ocean or sea.", "Think about the story's ocean or sea.")}</p>`;
          return;
        }
        answered = true;
        if (tries > 1) n = Math.min(n, 2);
        got.push(n); if (n === 3) firstHit("map3", key + "|" + p.place);
        logAnswer(p.card, n >= 2 && tries === 1, { q: "Where did this happen? " + p.h, a: p.place, why: "" });
        const at = proj(p.lon, p.lat), u = vb[2] / (svg.clientWidth || 340);
        $(".mk", svg).innerHTML = `<line x1="${pt.x}" y1="${pt.y}" x2="${at[0]}" y2="${at[1]}" class="trip"/>
          <circle cx="${pt.x}" cy="${pt.y}" r="${6 * u}" class="tap"/><circle cx="${at[0]}" cy="${at[1]}" r="${11 * u}" class="ring"/>
          <circle cx="${at[0]}" cy="${at[1]}" r="${7 * u}" class="dot"/>`;
        const where = inside && tier <= 1 ? say2("You tapped the right country!", "Right country.") : d < 25 ? "" : `About ${roundKm(d)} km away.`;
        $(".fb", box).innerHTML = `<p class="why"><b>${n === 3 ? say2("Spot on! 🎯", "Spot on.") : n === 2 ? say2("So close!", "Close.") : say2("Good try!", "Some way off.")}</b>
          ${where} 📍 <b>${esc(p.place)}</b>${p.names.length && p.names[0] !== p.place ? ` (${esc(p.names.slice(0, 3).join(", "))})` : ""}</p>${starLine(n)}
          <p><button type="button" class="big go nx">${i + 1 < items.length ? "Next place →" : say2("See my stars", "See my score")}</button></p>`;
        $(".nx", box).addEventListener("click", () => { i++; ask(); });
      });
    };
    ask();
  }

  // ---------------------------------------------------------------- Put it in order: a big story's events, from "The story so far"
  function order() {
    const g = { id: "order", run: order }, sets = shuffle(data.order).slice(0, 2), got = [];
    let i = 0;
    const ask = () => {
      if (i >= sets.length) {
        const n = Math.round(got.reduce((a, b) => a + b, 0) / got.length);
        ending(n, say2(got.every((x) => x === 3) ? "Every one in order! 🎉" : "Well done! 🎉", `${got.filter((x) => x === 3).length} of ${got.length} in order first time.`), g);
        return;
      }
      const t = sets[i], k = t.events.length, locked = new Set();
      let cur = shuffle([...Array(k).keys()]), tries = 0;
      while (cur.every((v, j) => v === j)) cur = shuffle(cur);   // never start already solved
      const move = (pos, step) => {                          // swap with the nearest card that isn't fixed yet
        let j = pos + step; while (locked.has(j)) j += step;
        if (j < 0 || j >= k) return;
        [cur[pos], cur[j]] = [cur[j], cur[pos]]; draw();
        const b = $(`[data-mv="${j}"][data-step="${step}"]`, box) || $(`[data-mv="${j}"]`, box); if (b) b.focus();
      };
      const draw = () => {
        box.innerHTML = `${back()}<p class="qn">Big story ${i + 1} of ${sets.length} · ${esc(t.title)}</p>
          <p class="q">${say2("What happened first? Put them in order, oldest at the top.", "Put these events in the order they happened, oldest first.")}</p>
          <ol class="ord">${cur.map((ev, pos) => `<li class="${locked.has(pos) ? "ok" : ""}"><span class="n">${pos + 1}</span><span class="tx">${esc(t.events[ev].text)}</span>
            <span class="mv">${locked.has(pos) ? "✓" : `<button type="button" data-mv="${pos}" data-step="-1" aria-label="Move up"${pos === 0 ? " disabled" : ""}>▲</button>
            <button type="button" data-mv="${pos}" data-step="1" aria-label="Move down"${pos === k - 1 ? " disabled" : ""}>▼</button>`}</span></li>`).join("")}</ol>
          <div class="fb" role="status"></div><p><button type="button" class="big go chk">${say2("Check my order", "Check")}</button></p>`;
        wireBack();
        $$("[data-mv]", box).forEach((b) => b.addEventListener("click", () => move(+b.dataset.mv, +b.dataset.step)));
        $(".chk", box).addEventListener("click", check);
      };
      const check = () => {
        const right = cur.map((v, j) => v === j);
        if (right.every(Boolean)) return done(tries === 0 ? 3 : 2);
        if (tries === 0) {                                     // the right ones stay put, then one more go
          tries++; hinted();
          right.forEach((ok, j) => { if (ok) locked.add(j); });
          draw();
          $(".fb", box).innerHTML = `<p class="why hint"><b>${say2("Nearly!", "Not quite.")}</b> ${locked.size
            ? say2(`The green ${locked.size === 1 ? "one is" : "ones are"} in the right place. Move the others and check again.`, `${locked.size} in place. Reorder the rest and check again.`)
            : say2("None are in the right place yet. Think about which came first, then try again.", "None in place yet. One more try.")}</p>`;
          return;
        }
        done(1);
      };
      const done = (n) => {
        got.push(n); if (n === 3) firstHit("ord3", key + "|" + t.title);
        logAnswer(t.card, n === 3, { q: "In order: " + t.title, a: t.events.map((e) => e.text).join(" → "), why: "" });
        const day = (e) => e.when || new Date(e.date + "T12:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short" });
        box.innerHTML = `${back()}<p class="qn">Big story ${i + 1} of ${sets.length} · ${esc(t.title)}</p>
          <p class="why"><b>${n === 3 ? say2("All in order! 🎯", "All in order.") : n === 2 ? say2("Got it on the second go!", "Correct on the second try.") : say2("Here's the right order.", "The right order:")}</b></p>
          <ol class="ord done">${t.events.map((e) => `<li class="ok"><span class="n">${esc(day(e))}</span><span class="tx">${esc(e.text)}</span></li>`).join("")}</ol>
          ${starLine(n)}<p><a href="${esc(t.href)}">📖 ${say2("Read the whole story so far", "The story so far")}</a></p>
          <p><button type="button" class="big go nx">${i + 1 < sets.length ? "Next big story →" : say2("See my stars", "See my score")}</button></p>`;
        wireBack();
        $(".nx", box).addEventListener("click", () => { i++; ask(); });
      };
      draw();
    };
    ask();
  }

  // ---------------------------------------------------------------- Guess the number
  const show1 = (v, it, exact) => (it.prefix || "") + Number(v).toLocaleString("en", { maximumFractionDigits: exact || v < 10 ? 2 : v < 100 ? 1 : 0 })
    + (it.unit === "times" ? "×" : it.unit ? (it.unit === "%" ? "" : " ") + it.unit : "");
  const sig2 = (v) => { if (v <= 0) return v; const p = Math.pow(10, Math.floor(Math.log10(v)) - 1); return Math.round(v / p) * p; };
  function numbers() {
    const g = { id: "numbers", run: numbers }, items = data.numbers.slice(0, 3), got = [], nt = stepUp();
    let i = 0;
    const ask = () => {
      if (i >= items.length) {
        const n = Math.round(got.reduce((a, b) => a + b, 0) / got.length);
        ending(n, say2(`${got.filter((x) => x === 3).length} of ${got.length} spot on! 🎉`,
          `${got.filter((x) => x === 3).length} of ${got.length} within 10%.`), g);
        return;
      }
      const it = items[i], done = (n, guess) => {
        got.push(n); if (n === 3) firstHit("num3", key + "|" + i);
        logAnswer(it.card, n >= 2, { q: it.q, a: show1(it.answer, it, true), why: it.why });
        const top = Math.max(it.answer, guess || 0) || 1;
        $(".fb", box).innerHTML = `<p class="why"><b>${n === 3 ? say2("Spot on! 🎯", "Within 10%.") : n === 2 ? say2("Close!", "Within 25%.") : say2("Good try!", "Some way off.")}</b>
          It was <b>${esc(show1(it.answer, it, true))}</b>. ${esc(it.why)}</p>
          ${guess === null ? "" : `<div class="nbars"><div><i style="width:${Math.max(3, 100 * guess / top)}%"></i><span>${grown ? "Your estimate" : "Your guess"}: ${esc(show1(guess, it))}</span></div>
          <div class="ans"><i style="width:${Math.max(3, 100 * it.answer / top)}%"></i><span>The answer: ${esc(show1(it.answer, it, true))}</span></div></div>`}
          ${starLine(n)}<p><button type="button" class="big go nx">${i + 1 < items.length ? "Next →" : say2("See my stars", "See my score")}</button></p>`;
        $(".nx", box).addEventListener("click", () => { i++; ask(); });
      };
      const head = `${back()}<p class="qn">${say2("Guess the number", "Estimate")} · ${i + 1} of ${items.length}</p>${young ? speakBtn(it.q) : ""}<p class="q">${esc(it.q)}</p>`;
      if (nt === 0) {                                      // ages 6–8: pick from three, ten times apart
        const opts = shuffle([it.answer, sig2(it.answer / 10), sig2(it.answer * 10)]);
        box.innerHTML = head + `<div class="opts nums">${opts.map((v) => `<button type="button" data-v="${v}">${esc(show1(v, it, v === it.answer))}</button>`).join("")}</div><div class="fb" role="status"></div>`;
        wireBack();
        let tries = 0;
        $$(".nums button", box).forEach((b) => b.addEventListener("click", () => {
          const v = +b.dataset.v; tries++;
          if (v !== it.answer && tries === 1) {
            b.disabled = true; b.classList.add("no"); hinted();
            $(".fb", box).innerHTML = `<p class="why hint"><b>${v < it.answer ? "Bigger!" : "Smaller!"}</b> Have another go.</p>`;
            return;
          }
          $$(".nums button", box).forEach((x) => { x.disabled = true; if (+x.dataset.v === it.answer) x.classList.add("ok"); });
          if (v !== it.answer) b.classList.add("no");
          done(v === it.answer ? (tries === 1 ? 3 : 2) : 1, null);
        }));
        return;
      }
      const log = it.min > 0 && it.max / it.min >= 50;    // a wide range slides in steps of "times", not "plus"
      const at = (f) => sig2(log ? it.min * Math.pow(it.max / it.min, f) : it.min + (it.max - it.min) * f);
      box.innerHTML = head + `<div class="slide"><output class="val"></output><input type="range" min="0" max="1000" value="500" aria-label="Your guess">
        <div class="ends"><span>${esc(show1(it.min, it))}</span><span>${esc(show1(it.max, it))}</span></div></div>
        <p><button type="button" class="big go check">${grown ? "Submit estimate" : "Check my guess"}</button></p><div class="fb" role="status"></div>`;
      wireBack();
      const r = $("input", box), out = $(".val", box), upd = () => { out.textContent = show1(at(r.value / 1000), it); };
      let start = 500;                                     // start somewhere clearly away from the answer
      for (let k = 0; k < 30; k++) { start = 100 + Math.floor(Math.random() * 800); if (Math.abs(at(start / 1000) - it.answer) / it.answer > 0.35) break; }
      r.value = start;
      r.addEventListener("input", upd); upd();
      let tries = 0;
      $(".check", box).addEventListener("click", () => {
        const v = at(r.value / 1000), off = Math.abs(v - it.answer) / it.answer;
        tries++;
        if (nt === 1 && off > 0.1 && tries < 3) {            // ages 9–11: higher or lower, up to three goes
          if (tries === 1) hinted();
          $(".fb", box).innerHTML = `<p class="why hint"><b>${v < it.answer ? "Higher!" : "Lower!"}</b> ${tries === 1 ? "Try again." : "One more go."}</p>`;
          return;
        }
        r.disabled = true; $(".check", box).remove();
        const n = nt === 1 ? (off <= 0.1 ? Math.max(1, 4 - tries) : 1) : off <= 0.1 ? 3 : off <= 0.25 ? 2 : 1;
        done(n, v);
      });
    };
    ask();
  }
  if (location.hash === "#play") tab("play");
  else if (location.hash.startsWith("#s-")) {               // from a pin on the lobby's map
    const c = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (c && show) show(cards.indexOf(c)); else if (c) setTimeout(() => c.scrollIntoView({ block: "start" }), 50);
  }
})();
"""
CSS += brief.CSS
JS += brief.JS


JS += story_timeline.JS
