"""Read & Play: the children's side of the website.

The newsstand is for grown-ups (choose, download, print). Read & Play is for the
child, on a tablet or phone: each recent issue as a web page, one story per
screen for younger readers, read aloud with the sentence lit up, new words to
tap, bigger text and a night mode, and a game made from the issue. Built from
the same issue files as the PDFs, by `python -m ygc site`. Nothing is tracked:
settings and stars stay in the browser.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess

from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas

from . import edition
from .chat import sentences
from .graphics import BarChart, IllustrationCard, StyledMap

E = html.escape
BANDS = ["Ages 6–8", "Ages 9–11", "Ages 12–14", "Ages 15+"]
CARD_BANDS = {"Ages 6–8", "Ages 9–11"}          # one story per screen
GRAPHICS = (("map", StyledMap, 1.7), ("illustration", IllustrationCard, 1.4), ("chart", BarChart, 1.8))
SKIP = {"quote", "watchlist", "sign_off"}       # print-only sections


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


# ------------------------------------------------------------------ pictures
def picture(kind, spec, path):
    """Draw a story's map, illustration or chart as a PNG (needs pdftoppm)."""
    if not shutil.which("pdftoppm"):
        return False
    cls, h = next((c, h) for k, c, h in GRAPHICS if k == kind)
    w, h = 3.4 * inch, h * inch
    pdf = path[:-4] + ".pdf"
    try:
        f = cls(spec, width=w, height=h)
        c = Canvas(pdf, pagesize=(w, h))
        f.wrapOn(c, w, h)
        f.drawOn(c, 0, 0)
        c.save()
        subprocess.run(["pdftoppm", "-png", "-r", "150", "-singlefile", pdf, path[:-4]], check=True,
                       capture_output=True)
        return os.path.exists(path)
    except Exception:
        return False
    finally:
        if os.path.exists(pdf):
            os.remove(pdf)


# ------------------------------------------------------------------ one issue
def sections(ed, issue, date, imgdir):
    """[(kind, html)] in reading order, plus the data the games need."""
    blocks = issue.get("blocks", {})
    vocab = vocab_of(issue)
    used = set()
    out, stories = [], []
    briefs = []
    for bid in edition.placed_blocks(ed):
        cfg, b = ed["blocks"][bid], blocks.get(bid)
        t = cfg["type"]
        if not isinstance(b, dict) or t in SKIP or bid == "quiz":
            continue
        if t == "story":
            kicker = plain(b.get("kicker", "")).split("•")[-1].strip() or plain(b.get("kicker", ""))
            img = ""
            for kind, _, _ in GRAPHICS:
                if b.get(kind):
                    fn = f"{date}-{bid}-{kind}.png"
                    if picture(kind, b[kind], os.path.join(imgdir, fn)):
                        cap = plain(b[kind].get("caption", ""))
                        img = f'<figure><img src="{fn}" alt="{E(cap or kind)}" loading="lazy"><figcaption>{E(cap)}</figcaption></figure>'
                    break
            body = "".join(f"<p>{_sentences(p, vocab, used)}</p>" for p in b.get("body", []) if str(p).strip())
            boxes = "".join(
                f'<aside class="box"><h3>{E(ed["labels"][x].capitalize())}</h3><p>{_sentences(b[x], vocab, used)}</p></aside>'
                for x in ("why", "connect", "analyst") if b.get(x))
            src = "".join(f'<li><a href="{E(s.get("url", "") if isinstance(s, dict) else s)}" rel="noopener" target="_blank">'
                          f'{E((s.get("title") or s.get("outlet") or s.get("url", "")) if isinstance(s, dict) else s)}</a></li>'
                          for s in b.get("sources", []) or [])
            out.append(("story", bid, f'''<p class="kicker">{E(kicker)}</p>
<h2><span class="s">{clean(b.get("headline", ""))}</span></h2>
{f'<p class="deck"><span class="s">{clean(b["deck"])}</span></p>' if b.get("deck") else ""}
{img}<div class="text">{body}</div>{boxes}
{f'<details class="grown"><summary>For grown-ups: sources</summary><ul>{src}</ul></details>' if src else ""}'''))
            first = plain(b.get("body", [""])[0]) if b.get("body") else ""
            stories.append({"headline": plain(b.get("headline", "")), "first": (sentences(first) or [""])[0]})
        elif t == "feature":
            body = "".join(f"<p>{_sentences(p, vocab, used)}</p>" for p in b.get("body", []) if str(p).strip())
            out.append(("feature", bid, f'<p class="kicker">{E(cfg.get("label", "").title())}</p>'
                                   f'<h2><span class="s">{clean(b.get("title", ""))}</span></h2><div class="text">{body}</div>'))
        elif t == "did_you_know" and b.get("text"):
            out.append(("fact", bid, f'<p class="kicker">Did you know?</p><h2 class="big"><span class="s">{clean(b["text"])}</span></h2>'))
        elif t == "sports" and b.get("body"):
            out.append(("feature", bid, f'<p class="kicker">Sport</p><h2><span class="s">{clean(b.get("title", ""))}</span></h2>'
                                   f'<div class="text"><p>{_sentences(b["body"], vocab, used)}</p></div>'))
        elif t == "briefs":
            briefs += [x for x in b.get("items", []) if str(x).strip()]
    if briefs:
        out.append(("briefs", "briefs", '<p class="kicker">In brief</p><h2><span class="s">More news</span></h2><ul class="text">'
                    + "".join(f"<li>{_sentences(x, vocab, used)}</li>" for x in briefs) + "</ul>"))
    if vocab:
        out.append(("words", "words", '<p class="kicker">New words</p><h2><span class="s">Words from this issue</span></h2><dl class="words">'
                    + "".join(f'<dt><span class="s">{E(v["word"])}</span></dt><dd><span class="s">{E(v["meaning"])}</span>'
                              + (f' <i>Today: {E(v["today"])}</i>' if v["today"] else "") + "</dd>" for v in vocab) + "</dl>"))
    at = {bid: i for i, (_, bid, _) in enumerate(out)}
    play = issue.get("play") if isinstance(issue.get("play"), dict) else {}
    quiz = [{"q": plain(q["q"]), "options": [plain(o) for o in q["options"]], "answer": q["answer"],
             "why": plain(q.get("why", "")), "card": at.get(q.get("story"), -1)}
            for q in play.get("quiz") or [] if isinstance(q, dict) and q.get("q") and len(q.get("options") or []) == 3
            and q.get("answer") in (0, 1, 2)]
    facts = [{"claim": plain(f["claim"]), "true": bool(f["true"]), "why": plain(f.get("why", "")),
              "card": at.get(f.get("story"), -1)}
             for f in play.get("fact_or_fiction") or [] if isinstance(f, dict) and f.get("claim") and isinstance(f.get("true"), bool)]
    return out, {"vocab": vocab, "stories": [s for s in stories if s["headline"] and s["first"]], "quiz": quiz, "facts": facts}


def issue_page(cfg, ed, band, issue, date, imgdir, others):
    secs, data = sections(ed, issue, date, imgdir)
    cards = "".join(f'<section class="card {k}" data-i="{i}" data-b="{E(b)}"><button type="button" class="read" aria-label="Read this to me">'
                    f'<span aria-hidden="true">🔊</span> Read it to me</button>{h}</section>' for i, (k, b, h) in enumerate(secs))
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
<div class="dots" aria-hidden="true"></div>
{cards}
<section class="card end" data-i="{len(secs)}"><h2>You read today's paper! 🎉</h2><p>Ready for a game?</p>
<button type="button" class="big go" data-tab="play">Play now</button></section>
<div class="steps"><button type="button" class="big prev">← Back</button><button type="button" class="big next">Next →</button></div>
</div>
<div id="play" role="tabpanel" hidden><div id="game"></div></div>
<p class="older"><label>Other days: <select onchange="location.href=this.value">{earlier}</select></label>
· <a href="../../e/{E(ed['id'])}/index.html">Print this paper (for grown-ups)</a></p>
</main>
<div id="pop" role="dialog" aria-modal="false" hidden><button type="button" class="x" aria-label="Close">✕</button><h3></h3><p class="m"></p><p class="t"></p>
<button type="button" class="say">🔊 Say it</button></div>
<script id="data" type="application/json">{json.dumps(data, ensure_ascii=False).replace("</", "<\\/")}</script>'''
    return shell(cfg, f"{ed['name']}, {d:%d %b} · Read & Play", body, root="../../")


# ------------------------------------------------------------------ the space
def shell(cfg, title, body, root=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="Read today's news, hear it read aloud and play a game. For children, from {E(cfg['title'])}.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}play/play.css"></head><body>{body}<script src="{root}play/play.js"></script></body></html>"""


def build(out, cfg, keep=7, log=print):
    """Write out/play/: the Who's reading? page, and a page per recent issue of every listed paper."""
    from .site import audience, issues_of, lead_headline
    pdir = os.path.join(out, "play")
    os.makedirs(pdir, exist_ok=True)
    open(os.path.join(pdir, "play.css"), "w", encoding="utf-8").write(CSS)
    open(os.path.join(pdir, "play.js"), "w", encoding="utf-8").write(JS)
    tiles = []
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
        lead_img, latest = "", None
        for date, path in issues_of(ed)[:keep]:
            issue = json.load(open(path, encoding="utf-8"))
            try:
                html_ = issue_page(cfg, ed, band, issue, date, edir, dates)
            except Exception as e:
                log(f"  ! play {eid} {date}: {e}")
                continue
            open(os.path.join(edir, f"{date}.html"), "w", encoding="utf-8").write(html_)
            if date == dates[0]:
                imgs = sorted(f for f in os.listdir(edir) if f.startswith(f"{date}-lead-") and f.endswith(".png"))
                lead_img = f'<img src="{eid}/{imgs[0]}" alt="" loading="lazy">' if imgs else ""
                latest = (date, lead_headline(ed, issue))
        if not latest:
            continue
        tiles.append((BANDS.index(band) if band in BANDS else 9, ed["name"], f'''<article class="tile" data-band="{E(band)}">
{lead_img}<h2>{E(ed["name"])}</h2><p class="when">{E(band)} · {dt.date.fromisoformat(latest[0]):%a %d %b}</p>
<p>{E(latest[1])}</p><div class="go2"><a class="big go" href="{eid}/{latest[0]}.html">Read</a><a class="big" href="{eid}/{latest[0]}.html#play">Play</a></div></article>'''))
        log(f"  play {eid}: {len(dates)} issue(s)")
    who = "".join(f'<button type="button" class="who" data-band="{E(b)}">{E(b.replace("Ages ", ""))}</button>' for b in BANDS)
    body = f'''<header class="bar"><a class="home" href="../index.html">← {E(cfg["title"])} (grown-ups)</a></header>
<main class="lobby"><h1>Read &amp; Play</h1><p class="lede">Today's news, read to you if you like, with a game at the end.</p>
<h2>Who's reading? <span>How old are you?</span></h2><div class="whos">{who}<button type="button" class="who" data-band="">Show all</button></div>
<div class="tiles">{"".join(t[2] for t in sorted(tiles))}</div>
<p class="note">For grown-ups: nothing here is tracked. Settings and stars stay on this device.</p></main>'''
    open(os.path.join(pdir, "index.html"), "w", encoding="utf-8").write(shell(cfg, f"Read & Play · {cfg['title']}", body, root="../"))


CSS = r"""
:root{--bg:#FFF8EE;--card:#FFFFFF;--ink:#1E2A32;--muted:#5B6870;--line:#E7DCCB;--coral:#E2584D;--teal:#007C89;--sun:#F4B400;
--sun-t:#FFE9A8;--leaf:#2E7D4F;--leaf-t:#DDF2E4;--rose-t:#FBE1DE;--fs:19px;--lh:1.7;
--display:"Bricolage Grotesque","Avenir Next","Segoe UI",system-ui,sans-serif;--text:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;
box-sizing:border-box}
:root[data-theme="night"]{--bg:#12181C;--card:#1B242A;--ink:#E8EEEC;--muted:#A3B0B6;--line:#2C3940;--sun-t:#5A4A12;--leaf-t:#173326;--rose-t:#3B2224}
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
.issue,.lobby{max-width:760px;margin:0 auto;padding:16px 16px 60px}
.title h1{font-size:clamp(1.6rem,6vw,2.4rem)}.title p{margin:2px 0 10px;color:var(--muted);font-size:16px}
.tabs{display:flex;gap:8px;margin:6px 0 14px}
.tabs button{flex:1;min-height:52px;border:2px solid var(--line);background:var(--card);border-radius:14px;font-weight:700;font-size:18px;cursor:pointer}
.tabs button[aria-selected="true"]{background:var(--teal);border-color:var(--teal);color:#fff}
.card{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:18px 18px 20px;margin:0 0 16px;position:relative}
.card h2{font-size:1.45em;margin:4px 0 8px}.card h2.big{font-size:1.3em;line-height:1.35}
.kicker{margin:0;font-size:.72em;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--coral)}
.deck{color:var(--muted);margin:0 0 10px}
.text p{margin:0 0 .8em}.text li{margin:0 0 .5em}
figure{margin:10px 0 14px}figure img{width:100%;height:auto;border-radius:12px;border:1px solid var(--line);background:#fff}
figcaption{font-size:.75em;color:var(--muted);margin-top:4px}
.box{background:var(--leaf-t);border-radius:14px;padding:12px 14px;margin:10px 0}.box h3{font-size:.8em;text-transform:uppercase;letter-spacing:.06em;color:var(--leaf)}
.box p{margin:4px 0 0}
.read{display:inline-flex;gap:6px;align-items:center;margin:0 0 10px;min-height:44px;border:2px solid var(--coral);background:var(--card);color:var(--coral);border-radius:999px;padding:4px 14px;font-weight:700;font-size:16px;cursor:pointer}
.read[aria-pressed="true"]{background:var(--coral);color:#fff}
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
.dots{display:none;gap:6px;justify-content:center;margin:0 0 10px}[data-mode="cards"] .dots{display:flex}
.dots i{width:10px;height:10px;border-radius:50%;background:var(--line)}.dots i.on{background:var(--coral)}
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
.lobby h1{font-size:clamp(2.2rem,9vw,3.4rem);color:var(--coral)}.lede{font-size:1.1em;margin:4px 0 18px}
.lobby h2{font-size:1.3em;margin:10px 0 8px}.lobby h2 span{font-family:var(--text);font-weight:400;color:var(--muted);font-size:.75em}
.whos{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px}
.who{min-height:56px;min-width:84px;border:2px solid var(--line);background:var(--card);border-radius:16px;font-weight:800;font-size:20px;cursor:pointer;padding:6px 14px}
.who[aria-pressed="true"]{background:var(--teal);border-color:var(--teal);color:#fff}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:14px}
.tile{background:var(--card);border:2px solid var(--line);border-radius:20px;padding:14px;display:flex;flex-direction:column;gap:6px}
.tile img{width:100%;border-radius:12px;border:1px solid var(--line);background:#fff}
.tile h2{font-size:1.25em;margin:4px 0 0}.tile p{margin:0}.tile .when{font-size:15px;color:var(--muted)}
.go2{display:flex;gap:8px;margin-top:auto;padding-top:8px}.go2 .big{flex:1;text-align:center}
.note{font-size:14px;color:var(--muted);margin-top:28px}
"""

JS = r"""
(function () {
  const $ = (s, el) => (el || document).querySelector(s), $$ = (s, el) => [...(el || document).querySelectorAll(s)];
  const store = { get(k, d) { try { const v = localStorage.getItem("rp-" + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
                  set(k, v) { try { localStorage.setItem("rp-" + k, JSON.stringify(v)); } catch (e) {} } };
  const root = document.documentElement;
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

  // ---------------------------------------------------------------- the lobby: who's reading?
  const whos = $$(".who");
  if (whos.length) {
    const pick = (band) => {
      store.set("band", band);
      whos.forEach((w) => w.setAttribute("aria-pressed", String(w.dataset.band === band)));
      $$(".tile").forEach((t) => { t.hidden = !!band && t.dataset.band !== band; });
    };
    whos.forEach((w) => w.addEventListener("click", () => pick(w.dataset.band)));
    pick(store.get("band", ""));
    return;
  }

  const main = $(".issue");
  if (!main) return;
  const data = JSON.parse($("#data").textContent);

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
    const parts = $$(".s", card);
    reading = card; btn.setAttribute("aria-pressed", "true"); btn.lastChild.textContent = " Stop";
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

  // ---------------------------------------------------------------- tap a word
  const pop = $("#pop");
  let popWord = null;
  function openWord(i) {
    const v = data.vocab[i]; if (!v) return;
    popWord = v;
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
  let at = 0;
  const dots = $(".dots");
  if (main.dataset.mode === "cards") {
    dots.innerHTML = cards.map(() => "<i></i>").join("");
    const show = (n) => {
      stop(); at = Math.max(0, Math.min(cards.length - 1, n));
      cards.forEach((c, i) => c.classList.toggle("on", i === at));
      $$("i", dots).forEach((d, i) => d.classList.toggle("on", i === at));
      $(".prev").style.visibility = at ? "visible" : "hidden";
      $(".next").style.visibility = at < cards.length - 1 ? "visible" : "hidden";
      window.scrollTo({ top: 0 });
    };
    document.addEventListener("rp-show", (e) => show(e.detail));
    $(".prev").addEventListener("click", () => show(at - 1));
    $(".next").addEventListener("click", () => show(at + 1));
    let x0 = null;
    $("#read").addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    $("#read").addEventListener("touchend", (e) => {
      if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; x0 = null;
      if (Math.abs(dx) > 60) show(at + (dx < 0 ? 1 : -1));
    });
    document.addEventListener("keydown", (e) => {
      if ($("#read").hidden) return;
      if (e.key === "ArrowRight") show(at + 1); if (e.key === "ArrowLeft") show(at - 1);
    });
    show(0);
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
  const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const starsFor = (right, total) => (right === total ? 3 : right / total >= 0.6 ? 2 : 1);
  const best = (name) => store.get("stars-" + main.dataset.key + "-" + name, 0);
  const keep = (name, n) => store.set("stars-" + main.dataset.key + "-" + name, Math.max(n, best(name)));
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
    if (main.dataset.mode === "cards") { $$("#read .card")[i] && document.dispatchEvent(new CustomEvent("rp-show", { detail: i })); }
    else { const c = $$("#read .card")[i]; if (c) c.scrollIntoView({ behavior: "smooth" }); }
  });
  function finishText(right, total, name) {
    const n = starsFor(right, total); keep(name, n);
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
})();
"""
