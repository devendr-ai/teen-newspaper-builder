"""Static website: every listed edition, its latest PDF, an archive with sources, RSS.

    python -m ygc site --out _site
"""
import datetime as dt
import glob
import html
import json
import os
import shutil
import subprocess

import yaml

from . import brand, checks, edition, poster, render

ROOT = edition.ROOT
E = html.escape


def site_config():
    p = os.path.join(ROOT, "site.yaml")
    cfg = yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    cfg.setdefault("title", "The Newsstand")
    cfg.setdefault("tagline", "Printable newspapers, written for each reader.")
    cfg.setdefault("description", cfg["tagline"])
    cfg.setdefault("domain", "")
    cfg.setdefault("base_url", "")
    cfg.setdefault("contact", "")
    cfg.setdefault("feedback_url", "")
    cfg.setdefault("keep_issues", 30)
    cfg.setdefault("intro_title", "")
    cfg.setdefault("intro", "")
    cfg.setdefault("steps", [])
    return cfg


def audience(ed):
    s = ed.get("site") or {}
    if s.get("audience"):
        return s["audience"]
    a = str(ed["reader"]["age"])
    try:
        n = int(a.split("-")[0])
        return "Ages 6–8" if n <= 8 else "Ages 9–11" if n <= 11 else "Ages 12–14" if n <= 14 else "Ages 15+"
    except ValueError:
        return "Ages 15+"


def length_band(n):
    return "1 page" if n == 1 else "2 pages" if n == 2 else "3–4 pages" if n <= 4 else "5+ pages"


def frequency(ed):
    d = ed["cadence"]["every_days"]
    return "Daily" if d == 1 else "Every 2 days" if d == 2 else "Weekly" if d == 7 else f"Every {d} days"


def issues_of(ed):
    out = []
    for p in glob.glob(os.path.join(checks.issues_dir(ed), "**", "*.json"), recursive=True):
        m = checks.FNAME_RE.search(os.path.basename(p))
        if m:
            out.append((m.group(1), p))
    return sorted(out, reverse=True)


def sources_of(issue):
    seen, out = set(), []
    for b in issue.get("blocks", {}).values():
        for s in (b.get("sources", []) if isinstance(b, dict) else []):
            url = s.get("url") if isinstance(s, dict) else s
            if url and url not in seen:
                seen.add(url)
                out.append(s if isinstance(s, dict) else {"url": s})
    for s in issue.get("sources", []) or []:
        url = s.get("url") if isinstance(s, dict) else s
        if url and url not in seen:
            seen.add(url)
            out.append(s if isinstance(s, dict) else {"url": s})
    return out


def lead_headline(ed, issue):
    for bid in edition.story_blocks(ed):
        b = issue.get("blocks", {}).get(bid)
        if b and b.get("headline"):
            return b["headline"]
    return ""


CSS = """
:root{--paper:#F4F1EA;--surface:#fff;--ink:#1E2A32;--muted:#5B6870;--line:#DDD5C6;--cyan:#00727E;--cyan-t:#DDEFF0;--mag:#B8336A;--coral:#E2584D;
--display:"Bricolage Grotesque","Avenir Next","Segoe UI",system-ui,sans-serif;--text:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#11181C;--surface:#182226;--ink:#E5ECEA;--muted:#9AA8AE;--line:#2D3A40;--cyan:#41B6C1;--cyan-t:#173438}}
*,*::before,*::after{box-sizing:inherit}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--text)}
a{color:var(--cyan)}h1,h2,h3{font-family:var(--display);line-height:1.1;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding:14px 20px 70px}
header.top{display:flex;align-items:center;gap:8px 16px;flex-wrap:wrap;border-bottom:1.5px solid var(--ink);padding-bottom:10px;margin-bottom:12px}
header.top h1{font-size:clamp(1.25rem,3vw,1.8rem);font-weight:800;letter-spacing:-.02em}
header.top h1 a{color:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:.3em}
header.top h1 .logo{width:1.6em;height:1.6em;flex:none;margin:-.2em 0}
.wm{display:inline-flex;flex-direction:column;line-height:1}.wm b{color:var(--coral)}
.stones{display:flex;gap:.12em;margin-top:.16em}
.stones i{display:block;height:.3em;width:.62em;border:.07em solid var(--ink);border-radius:58% 42% 55% 45%/52% 58% 42% 48%}
.stones i:nth-child(2){width:.46em}.stones i:nth-child(3){width:.54em}
nav{margin-left:auto;display:flex;flex-wrap:wrap;gap:4px 18px}nav a{font-weight:700;text-decoration:none}
.menu{display:none;margin-left:auto;font:inherit;font-weight:700;border:1.5px solid var(--line);background:var(--surface);color:var(--ink);border-radius:10px;padding:5px 10px;min-height:40px;cursor:pointer}
@media (max-width:999px){.js .menu{display:block}.js header.top nav{display:none;width:100%;flex-direction:column;gap:0;margin:0}
  .js header.top.open nav{display:flex}.js header.top nav a{padding:10px 2px;border-top:1px solid var(--line)}}
.intro{margin:0 0 6px}.intro .motto{margin:2px 0 0;font-family:var(--display);font-weight:800;font-size:clamp(1.25rem,2.6vw,1.6rem);letter-spacing:-.01em}.intro .lede{display:inline;margin:0 8px 0 0;color:var(--muted)}.how{display:inline}.how summary{display:inline}
.how summary{color:var(--cyan);font-weight:700;cursor:pointer;list-style:none}.how summary::-webkit-details-marker{display:none}
.how summary::after{content:" ›"}.how[open] summary::after{content:" ‹"}
.how[open]{display:block;margin-top:2px}.how .box{background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:14px 18px;margin:8px 0 6px}
.how h2{font-size:1.3rem;margin-bottom:6px}.how p{margin:0 0 12px;max-width:72ch}
.agebar{position:sticky;top:0;z-index:5;background:var(--paper);display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:8px 0 10px;margin:0 0 12px;border-bottom:1px solid var(--line)}
.agebar .lbl{font-weight:700;font-size:.92rem}
.seg{display:flex;background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:3px}
.seg button{font:inherit;font-weight:700;border:0;background:none;color:var(--ink);border-radius:9px;padding:7px 16px;min-height:40px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.agebar .count{color:var(--muted);font-size:.86rem}
.agebar .more{margin-left:auto;font:inherit;font-size:.92rem;font-weight:700;color:var(--cyan);background:none;border:0;cursor:pointer;padding:6px 0}
.agebar .more::after{content:" ▾"}.agebar .more[aria-expanded="true"]::after{content:" ▴"}
@media (max-width:640px){.agebar .lbl{width:100%}.seg{flex:1 1 100%}.seg button{flex:1;padding:7px 4px}.agebar .more{margin-left:auto}}
.filters{display:grid;gap:10px;margin:0 0 16px}.frow{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.frow span{color:var(--muted);font-size:.9rem;min-width:84px}
.frow button{font:inherit;font-size:.9rem;border:1.5px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:5px 12px;cursor:pointer}
.frow button[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
button:focus-visible,a:focus-visible{outline:3px solid var(--cyan);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr));gap:18px}
[hidden]{display:none!important}
.card{background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:9px}
.cover{display:block;aspect-ratio:8.5/11;background:#FAF7F1;border:1px solid #B9C3C1;overflow:hidden}
.cover img{width:100%;height:100%;object-fit:cover;object-position:top;display:block}
.cover.soon{display:grid;place-items:center;color:#56646C;font-size:.9rem;text-align:center;padding:16px}
.card h2{font-size:1.2rem}.card p{margin:0;font-size:.93rem;color:var(--muted)}
.card .cover{aspect-ratio:8.5/8}@media (min-width:641px) and (max-width:999px){.card .cover{aspect-ratio:8.5/6.5}}
.new{display:inline-block;background:var(--cyan-t);color:var(--cyan);font-family:var(--text);font-size:.62em;font-weight:700;letter-spacing:.04em;border-radius:6px;padding:1px 6px;margin-left:6px;vertical-align:.2em}
.card.rp .cover{display:grid;place-items:center;background:#FFF8EE}.card.rp .cover img{width:46%;height:auto;object-fit:contain}
@media (max-width:640px){
  .grid{gap:10px}
  .card{display:grid;grid-template-columns:84px minmax(0,1fr);gap:3px 12px;padding:10px;align-content:start}
  .card>*{grid-column:2}.card .cover{grid-column:1;grid-row:1/span 6;align-self:start;aspect-ratio:8.5/11}
  .card h2{font-size:1.08rem}.card p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.88rem}
  .card .tag{margin-bottom:2px}.card .actions{margin-top:6px;gap:6px}.card .btn{font-size:.86rem;padding:7px 10px}}
.meta{font-size:.84rem;color:var(--muted)}
.btn{display:inline-block;text-align:center;font-weight:700;background:var(--ink);color:var(--paper);text-decoration:none;border-radius:8px;padding:9px 12px}
.btn.ghost{background:transparent;color:var(--ink);border:1.5px solid var(--ink)}
.btn.poster{background:#E2584D;color:#fff}
.tag{align-self:flex-start;background:#E2584D;color:#fff;font-size:.75rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-radius:999px;padding:2px 10px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}.empty{color:var(--muted);padding:30px 0}
table{width:100%;border-collapse:collapse;font-size:.95rem}td,th{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
details summary{cursor:pointer;color:var(--cyan)}details ul{margin:6px 0 0;padding-left:18px;font-size:.88rem}
.lede{display:grid;grid-template-columns:minmax(0,240px) minmax(0,1fr);gap:24px;margin-bottom:28px;align-items:start}
@media (max-width:640px){.lede{grid-template-columns:minmax(0,1fr)}}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:12px;margin:0;padding:0;list-style:none;counter-reset:s}
.steps li{counter-increment:s;padding-left:34px;position:relative;font-size:.95rem}
.steps li::before{content:counter(s);position:absolute;left:0;top:-1px;width:24px;height:24px;border-radius:50%;background:var(--cyan);color:var(--paper);font-weight:700;display:grid;place-items:center;font-size:.85rem}
.tabbar{display:none}
@media (max-width:699px){
  header.top nav,.js .menu{display:none!important}
  .wrap{padding-bottom:110px}
  .tabbar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--surface);border-top:1.5px solid var(--line);
    padding:4px 4px calc(4px + env(safe-area-inset-bottom,0px))}
  .tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:52px;font-size:12px;font-weight:700;
    line-height:1.2;color:var(--muted);text-decoration:none;border-radius:10px;text-align:center}
  .tabbar a span{font-size:21px;line-height:1.15}
  .tabbar a[aria-current="page"]{color:var(--ink);background:var(--cyan-t)}}
footer{margin-top:40px;color:var(--muted);font-size:.86rem;border-top:1px solid var(--line);padding-top:14px}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&display=swap" rel="stylesheet">')


def feedback_nav(cfg, root=""):
    return f'<a href="{root}feedback.html">Feedback</a>' if cfg.get("feedback_url") else ""


def tabbar(cfg, root, here):
    """The phone's bottom bar: the same links as the header, one tap from anywhere on the page."""
    tabs = [("papers", "index.html", "📰", "Papers"), ("play", "play/index.html", "🎧", "Read &amp; Play"),
            ("design", "builder.html", "✏️", "Design"), ("about", "about.html", "ℹ️", "How it's made")]
    if cfg.get("feedback_url"):
        tabs.append(("feedback", "feedback.html", "💬", "Feedback"))
    now = ' aria-current="page"'
    return ('<nav class="tabbar" aria-label="Pages">' + "".join(
        f'<a href="{root}{href}"{now if k == here else ""}><span aria-hidden="true">{icon}</span>{label}</a>'
        for k, href, icon, label in tabs) + "</nav>")


def page(cfg, title, body, root="", head_extra="", here="papers"):
    contact = f' · Corrections: <a href="mailto:{E(cfg["contact"])}">{E(cfg["contact"])}</a>' if cfg.get("contact") else ""
    if cfg.get("feedback_url"):
        contact += f' · Spotted a mistake, or have an idea? <a href="{root}feedback.html">Tell us</a>'

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="{E(cfg['tagline'] if cfg['description'] == cfg['tagline'] else cfg['tagline'] + ' ' + cfg['description'])}">
<link rel="icon" href="{root}owl.svg" type="image/svg+xml"><link rel="icon" href="{root}favicon.png" sizes="32x32">
<link rel="apple-touch-icon" href="{root}play/icon-180.png">{FONTS}{head_extra}<style>{CSS}</style>
<script>document.documentElement.classList.add("js")</script></head>
<body><div class="wrap"><header class="top"><h1><a href="{root}index.html" aria-label="{E(cfg['title'])}">{brand.inline()}{brand.wordmark(cfg['title'])}</a></h1>
<button type="button" class="menu" aria-expanded="false" aria-controls="nav">☰ Menu</button>
<nav id="nav"><a href="{root}index.html">Papers</a><a href="{root}play/index.html">Read &amp; Play</a><a href="{root}builder.html">Design your own</a><a href="{root}about.html">How it's made</a>{feedback_nav(cfg, root)}</nav></header>
<script>(function(){{const h=document.querySelector("header.top"),b=h.querySelector(".menu");
b.addEventListener("click",()=>b.setAttribute("aria-expanded",String(h.classList.toggle("open"))));}})()</script>
{body}<footer>Written by AI from verified news sources, then checked automatically. Every issue lists its sources{contact}.</footer></div>
{tabbar(cfg, root, here)}</body></html>"""


def credit(cfg):
    """The line every printed page ends with: who publishes it, and where to find more."""
    return f"A {cfg['title']} paper" + (f"  ·  {cfg['domain']}" if cfg.get("domain") else "")


def qr_url(cfg, eid, date):
    """Where an issue's printed QR code goes: its Read & Play page. Papers from before
    `qr_from` (site.yaml) were published without one and stay as they were."""
    start = str(cfg.get("qr_from") or "")
    if not start or not cfg.get("base_url") or date < start:
        return None
    return f"{cfg['base_url'].rstrip('/')}/play/{eid}/{date}.html"


def build(out, keep=None, log=print):
    cfg = site_config()
    keep = keep or int(cfg["keep_issues"])
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    has_png = bool(shutil.which("pdftoppm"))
    cards = []          # (has_issue, audience order, name, html)
    for eid in edition.list_editions():
        ed = edition.load(eid)
        s = ed.get("site") or {}
        if s.get("listed") is False:
            continue
        edir = os.path.join(out, "e", eid)
        os.makedirs(edir, exist_ok=True)
        rows, items, latest = [], [], None
        posters, latest_poster = {}, None          # "Big Question" posters, a companion download
        for date, p in poster.posters_of(ed)[:keep]:
            spec = json.load(open(p, encoding="utf-8"))
            try:
                poster.build(ed, spec, os.path.join(edir, f"{date}-poster.pdf"), credit=credit(cfg))
            except Exception as e:
                log(f"  ! {eid} poster {date}: {e}"); continue
            posters[date] = spec
            if latest_poster is None:
                latest_poster = date
                shutil.copy(os.path.join(edir, f"{date}-poster.pdf"), os.path.join(edir, "latest-poster.pdf"))
        for date, p in issues_of(ed)[:keep]:
            issue = json.load(open(p, encoding="utf-8"))
            pdf = f"{date}.pdf"
            try:
                render.build(ed, issue, os.path.join(edir, pdf), qr=qr_url(cfg, eid, date), credit=credit(cfg))
            except Exception as e:
                log(f"  ! {eid} {date}: {e}"); continue
            if latest is None:
                latest = (date, issue)
                shutil.copy(os.path.join(edir, pdf), os.path.join(edir, "latest.pdf"))
                if has_png:
                    subprocess.run(["pdftoppm", "-png", "-r", "60", "-f", "1", "-l", "1", "-singlefile",
                                    os.path.join(edir, pdf), os.path.join(edir, "cover")], check=False)
            d = dt.date.fromisoformat(date)
            srcs = "".join(f'<li><a href="{E(x.get("url", ""))}" rel="noopener">{E(x.get("title") or x.get("url", ""))}</a>'
                           f'{" — " + E(x["outlet"]) if x.get("outlet") else ""}</li>'
                           for x in sources_of({"sources": sources_of(issue) + sources_of(posters.get(date, {}))}))
            ptd = f' <a class="btn ghost" href="{date}-poster.pdf" download>Poster</a>' if date in posters else ""
            rows.append(f'<tr><td>{d:%a %d %b %Y}</td><td>No. {issue.get("issue", "")}</td>'
                        f'<td>{E(lead_headline(ed, issue))}<details><summary>Sources</summary><ul>{srcs}</ul></details></td>'
                        f'<td><a class="btn ghost" href="{pdf}" download>PDF</a>{ptd}</td></tr>')
            link = f'{cfg["base_url"].rstrip("/")}/e/{eid}/{pdf}' if cfg["base_url"] else pdf
            items.append(f"<item><title>{E(ed['name'])}, No. {issue.get('issue', '')}: {E(lead_headline(ed, issue))}</title>"
                         f"<link>{E(link)}</link><guid>{E(link)}</guid>"
                         f"<pubDate>{d:%a, %d %b %Y} 06:00:00 GMT</pubDate></item>")
        n = len(ed["pages"])
        meta = f"{audience(ed)} · {n} page{'s' if n != 1 else ''} · {frequency(ed)}"
        blurb = s.get("blurb") or ed["reader"]["profile"]
        focus = s.get("focus") or "World affairs"
        cover = (f'<a class="cover" href="e/{eid}/index.html"><img src="e/{eid}/cover.png" alt="Front page of the latest {E(ed["name"])}" loading="lazy"></a>'
                 if latest and has_png else f'<a class="cover soon" href="e/{eid}/index.html">{"Latest issue" if latest else "First issue coming soon"}</a>')
        dl = (f'<a class="btn" href="e/{eid}/latest.pdf" download="{eid}-{latest[0]}.pdf">Download PDF</a>'
              if latest else "")
        cards.append((latest is None, FACET_ORDER.get(audience(ed), 50), ed["name"], f'''<article class="card" data-kind="paper" data-audience="{E(audience(ed))}" data-length="{E(length_band(n))}" data-focus="{E(focus)}" data-frequency="{E(frequency(ed))}">
{cover}<h2>{E(ed['name'])}<!--NEW--></h2><p>{E(blurb)}</p><div class="meta">{E(meta)}{f" · latest {dt.date.fromisoformat(latest[0]):%d %b}" if latest else ""}</div>
<div class="actions">{dl}<a class="btn ghost" href="e/{eid}/index.html">All issues</a></div></article>''', latest and latest[0]))
        if latest_poster:                          # the poster gets its own card, thumbnail and download
            if has_png:
                subprocess.run(["pdftoppm", "-png", "-r", "60", "-singlefile", os.path.join(edir, "latest-poster.pdf"),
                                os.path.join(edir, "poster-cover")], check=False)
            pq = posters[latest_poster]["question"]
            pcover = (f'<a class="cover" href="e/{eid}/latest-poster.pdf"><img src="e/{eid}/poster-cover.png" '
                      f'alt="The latest Big Question poster: {E(pq)}" loading="lazy"></a>' if has_png
                      else f'<a class="cover soon" href="e/{eid}/latest-poster.pdf">{E(pq)}</a>')
            pmeta = f"{audience(ed)} · 1-page poster · {frequency(ed)} · latest {dt.date.fromisoformat(latest_poster):%d %b}"
            cards.append((False, FACET_ORDER.get(audience(ed), 50), ed["name"] + " poster", f'''<article class="card" data-kind="poster" data-audience="{E(audience(ed))}" data-length="1 page" data-focus="{E(focus)}" data-frequency="{E(frequency(ed))}">
{pcover}<span class="tag">Poster</span><h2>The Big Question<!--NEW--></h2><p>One big idea from this week's news on a single page: a picture to explore, something to try at home and questions to talk about together. This week: &ldquo;{E(pq)}&rdquo;</p><div class="meta">{E(pmeta)} · from {E(ed["name"])}</div>
<div class="actions"><a class="btn poster" href="e/{eid}/latest-poster.pdf" download="{eid}-{latest_poster}-poster.pdf">Download poster</a><a class="btn ghost" href="e/{eid}/index.html">All posters</a></div></article>''', latest_poster))
        # edition page
        desks = ", ".join(d["label"].title() for d in ed["desks"] if d["id"] != "top")
        top = (f'<a class="btn" href="latest.pdf" download="{eid}-{latest[0]}.pdf">Download the latest issue (PDF)</a>'
               if latest else '<p class="empty">The first issue hasn\'t been published yet.</p>')
        if latest_poster:
            q = posters[latest_poster]["question"]
            top += (f' <a class="btn poster" href="latest-poster.pdf" download="{eid}-{latest_poster}-poster.pdf">Download the poster (PDF)</a>'
                    f'<p class="meta">Also this week: a one-page <b>Big Question</b> poster, &ldquo;{E(q)}&rdquo;, with pictures, '
                    f'something to try and questions to talk about together.</p>')
        img = f'<img src="cover.png" alt="" style="width:100%;border:1px solid #B9C3C1">' if latest and has_png else ""
        body = (f'<section class="lede"><div>{img}</div><div><h2 style="font-size:2rem">{E(ed["name"])}</h2>'
                f'<p>{E(blurb)}</p><p class="meta">{E(meta)}<br>Covers: {E(desks)}</p><p>{top}</p>'
                f'<p class="meta"><a href="feed.xml">RSS feed</a> for new issues.</p></div></section>'
                + (f'<h2 style="font-size:1.3rem;margin-bottom:6px">Issues</h2><table><tr><th>Date</th><th>Issue</th><th>Top story</th><th></th></tr>{"".join(rows)}</table>' if rows else ""))
        open(os.path.join(edir, "index.html"), "w", encoding="utf-8").write(page(cfg, ed["name"], body, root="../../",
             head_extra=f'<link rel="alternate" type="application/rss+xml" href="feed.xml" title="{E(ed["name"])}">'))
        open(os.path.join(edir, "feed.xml"), "w", encoding="utf-8").write(
            f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{E(ed["name"])}</title>'
            f'<link>{E(cfg["base_url"])}</link><description>{E(blurb)}</description>{"".join(items)}</channel></rss>')
        log(f"  {eid}: {len(rows)} issue(s)")

    newest = max((c[4] for c in cards if c[4]), default="")
    cards = [c[3].replace("<!--NEW-->", ' <span class="new">NEW</span>' if c[4] and c[4] == newest else "")
             for c in sorted(cards, key=lambda c: c[:3])]
    cards.append(f'''<article class="card rp" data-always="1"><a class="cover" href="play/index.html"><img src="owl.svg" alt="" loading="lazy"></a>
<h2>Read &amp; Play</h2><p>The latest papers on screen for children: read aloud if they like, with a game at the end.</p>
<div class="actions"><a class="btn poster" href="play/index.html">Open Read &amp; Play</a></div></article>''')
    # front page with filters
    def facet(name, label, values):
        vals = sorted(set(values), key=lambda v: (FACET_ORDER.get(v, 50), v))
        return (f'<div class="frow" role="group" aria-label="{label}"><span>{label}</span><button type="button" data-f="{name}" data-v="" aria-pressed="true">All</button>'
                + "".join(f'<button type="button" data-f="{name}" data-v="{E(v)}" aria-pressed="false">{E(v)}</button>' for v in vals) + "</div>")
    import re as _re
    attrs = lambda k: _re.findall(rf'data-{k}="([^"]*)"', "".join(cards))
    ages = sorted(set(attrs("audience")), key=lambda v: (FACET_ORDER.get(v, 50), v))
    agebar = ('<div class="agebar"><span class="lbl" id="agel">Your child\'s age</span><div class="seg" role="group" aria-labelledby="agel">'
              '<button type="button" data-f="audience" data-v="" aria-pressed="true">All</button>'
              + "".join(f'<button type="button" data-f="audience" data-v="{E(v)}" aria-pressed="false">{E(v.replace("Ages ", ""))}</button>' for v in ages)
              + '</div><span class="count" aria-live="polite"></span>'
              '<button type="button" class="more" aria-expanded="false" aria-controls="filters">More filters</button></div>')
    filters = agebar + ('<div class="filters" id="filters" hidden>' + facet("length", "Length", attrs("length"))
                        + facet("focus", "Focus", attrs("focus")) + facet("frequency", "How often", attrs("frequency")) + "</div>")
    # The age is remembered on this device, and shared with Read & Play (its "rp-band").
    script = """<script>
(function(){
const st={audience:"",length:"",focus:"",frequency:""},$$=(s)=>[...document.querySelectorAll(s)],count=document.querySelector('.agebar .count');
const plural=(n,w)=>n+" "+w+(n===1?"":"s");
function set(f,v){
  st[f]=v;
  $$(`button[data-f="${f}"]`).forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.v===v)));
  let papers=0,posters=0;$$('.card').forEach(c=>{const ok=c.dataset.always||Object.entries(st).every(([k,v])=>!v||c.dataset[k]===v);
    c.hidden=!ok;if(ok&&c.dataset.kind==="paper")papers++;if(ok&&c.dataset.kind==="poster")posters++;});
  count.textContent=plural(papers,"paper")+(posters?" · "+plural(posters,"poster"):"");
  document.getElementById('none').hidden=papers+posters>0;
}
$$('button[data-f]').forEach(b=>b.addEventListener('click',()=>{set(b.dataset.f,b.dataset.v);
  if(b.dataset.f==="audience")try{localStorage.setItem("rp-band",JSON.stringify(b.dataset.v));}catch(e){}}));
let age="";try{age=JSON.parse(localStorage.getItem("rp-band")||'""')||"";}catch(e){}
set("audience",$$(`button[data-f="audience"]`).some(b=>b.dataset.v===age)?age:"");
const more=document.querySelector('.agebar .more'),box=document.getElementById('filters');
more.addEventListener('click',()=>{box.hidden=!box.hidden;more.setAttribute('aria-expanded',String(!box.hidden));});
})();
</script>"""
    how = ""
    if cfg["intro_title"] or cfg["intro"]:                 # the parents' intro, one tap away
        heading = f'<h2>{E(cfg["intro_title"])}</h2>' if cfg["intro_title"] else ""
        text = f'<p>{E(cfg["intro"])}</p>' if cfg["intro"] else ""
        steps = "".join(f"<li>{E(x)}</li>" for x in cfg["steps"])
        steps = f'<ol class="steps">{steps}</ol>' if steps else ""
        how = f'<details class="how"><summary>How it works</summary><div class="box">{heading}{text}{steps}</div></details>'
    intro = (f'<section class="intro"><p class="motto">{E(cfg["tagline"])}</p>'
             f'<p class="lede">{E(cfg["description"])}</p>{how}</section>')
    body = intro + filters + f'<div class="grid">{"".join(cards)}</div><p id="none" class="empty" hidden>No paper matches all of those. Try removing a filter.</p>' + script
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page(cfg, cfg["title"], body))
    about = f"""<h2 style="font-size:2rem;margin-bottom:10px">How it's made</h2><div style="max-width:68ch">
<p>Each paper is written for one kind of reader: their age, what the paper is for, which countries and topics it covers, how long it is and how often it comes out.</p>
<p><b>Written for their age.</b> Age changes the vocabulary, the explanations and the size of the type, never the standard of accuracy. Hard news such as wars and disasters is reported honestly but without graphic detail; papers for the youngest readers say what happened and who is helping. New words are explained, and many papers end with questions to talk about together.</p>
<p><b>Built from verified research.</b> An AI research desk (Claude, by Anthropic) searches the news for each topic. Only facts that point to a page the search actually returned are kept, and each paper is written from that research alone.</p>
<p><b>Checked before it is published.</b> Automatic checks confirm every section is complete, the layout fits the printed page, nothing is cut off, and every story lists its sources. A separate fact-check compares each claim with the research. An issue that fails isn't published, and the previous issue stays up.</p>
<p><b>It can still be wrong.</b> AI makes mistakes and early reports change. Every issue lists its sources on its paper's page, so you can check anything before handing it over.{f' To report an error, email <a href="mailto:{E(cfg["contact"])}">{E(cfg["contact"])}</a>.' if cfg.get("contact") else ""}</p>
<p>You can also <a href="builder.html">design a paper for your own child</a>: the page writes instructions for your own AI chatbot, then checks its reply and prints it with the same engine. The engine is open source.</p></div>"""
    open(os.path.join(out, "about.html"), "w", encoding="utf-8").write(page(cfg, "How it's made", about, here="about"))
    shutil.copy(brand.SVG, os.path.join(out, "owl.svg"))                    # the logo, and the browser-tab icon
    shutil.copy(os.path.join(brand.ASSETS, "owl-32.png"), os.path.join(out, "favicon.png"))
    b = os.path.join(ROOT, "tools", "newspaper-builder.html")
    if os.path.exists(b):
        html = open(b, encoding="utf-8").read().replace("<!--FEEDBACK-->", feedback_nav(cfg))
        open(os.path.join(out, "builder.html"), "w", encoding="utf-8").write(html)
        engine_zip(os.path.join(out, "builder-engine.zip"))
    if cfg.get("feedback_url"):
        open(os.path.join(out, "feedback.html"), "w", encoding="utf-8").write(
            page(cfg, "Feedback", feedback_body(cfg["feedback_url"]), here="feedback"))
    from . import play                      # the children's side: read online and play
    play.build(out, cfg, keep=min(keep, int(cfg.get("play_keep", 7))), log=log)
    open(os.path.join(out, ".nojekyll"), "w").close()
    log(f"site written to {out}")
    return out


def feedback_body(url):
    """The feedback page: a Google Form shown on the page, or a button to any other form."""
    full = "docs.google.com/forms/" in url
    src = (url.split("?")[0].replace("/edit", "/viewform") + "?embedded=true") if full else url
    form = (f'<iframe src="{E(src)}" title="Feedback form" style="width:100%;min-height:1100px;border:0" loading="lazy">'
            f'Loading…</iframe>' if full else "")
    return f"""<h2 style="font-size:2rem;margin-bottom:10px">Feedback</h2><div style="max-width:68ch">
<p>Tell us what works, what doesn't, and what you'd like next: a mistake in a paper, an idea for a section, a
paper for an age we don't cover yet, or a problem with <i>Design your own</i>. We read everything.</p>
<p>Please don't include your child's full name or anything that identifies them. Leave an email only if you'd like a reply.</p>
<p><a class="btn" href="{E(url)}" target="_blank" rel="noopener">Open the feedback form</a></p></div>{form}"""


def engine_zip(path):
    """The engine for the builder page, which runs it in the browser (Pyodide): the ygc
    package, the craft rules and poster guide its chatbot instructions quote, and the
    pure-Python ReportLab it draws with (the same version as the published papers)."""
    import zipfile
    import reportlab
    rl = os.path.dirname(reportlab.__file__)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, rel_to, keep in ((os.path.join(ROOT, "ygc"), ROOT, (".py",)),
                                   (rl, os.path.dirname(rl), (".py",))):
            for d, dirs, files in os.walk(base):      # papers use only the built-in PDF fonts
                dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", "fonts"))
                for f in sorted(files):
                    if f.endswith(keep):
                        full = os.path.join(d, f)
                        z.write(full, os.path.relpath(full, rel_to))
        for f in ("CRAFT_RULES.md", "POSTERS.md"):
            z.write(os.path.join(ROOT, "docs", f), f"docs/{f}")
    return path


FACET_ORDER = {"Ages 6–8": 1, "Ages 9–11": 2, "Ages 12–14": 3, "Ages 15+": 4,
               "1 page": 1, "2 pages": 2, "3–4 pages": 3, "5+ pages": 4, "Daily": 1, "Every 2 days": 2, "Weekly": 3}
