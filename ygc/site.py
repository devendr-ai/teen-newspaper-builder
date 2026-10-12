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

from . import checks, edition, poster, render

ROOT = edition.ROOT
E = html.escape


def site_config():
    p = os.path.join(ROOT, "site.yaml")
    cfg = yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    cfg.setdefault("title", "The Newsstand")
    cfg.setdefault("tagline", "Printable newspapers, written for each reader.")
    cfg.setdefault("base_url", "")
    cfg.setdefault("contact", "")
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
:root{--paper:#F3F5F4;--surface:#fff;--ink:#16232B;--muted:#56646C;--line:#CDD5D3;--cyan:#007C89;--cyan-t:#E1F1F2;--mag:#B8336A;
--display:"Bricolage Grotesque","Avenir Next","Segoe UI",system-ui,sans-serif;--text:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;
box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#11181C;--surface:#182226;--ink:#E5ECEA;--muted:#9AA8AE;--line:#2D3A40;--cyan:#41B6C1;--cyan-t:#173438}}
*,*::before,*::after{box-sizing:inherit}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--text)}
a{color:var(--cyan)}h1,h2,h3{font-family:var(--display);line-height:1.1;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding:28px 20px 70px}
header.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;border-bottom:1.5px solid var(--ink);padding-bottom:14px;margin-bottom:22px}
header.top h1{font-size:clamp(1.9rem,4.4vw,3rem);font-weight:800;letter-spacing:-.02em}
header.top h1 a{color:inherit;text-decoration:none}header.top p{margin:4px 0 0;color:var(--muted);max-width:60ch}
nav a{margin-left:16px;font-weight:700;text-decoration:none}
.filters{display:grid;gap:10px;margin:0 0 22px}.frow{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.frow span{color:var(--muted);font-size:.9rem;min-width:84px}
.frow button{font:inherit;font-size:.9rem;border:1.5px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:5px 12px;cursor:pointer}
.frow button[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
button:focus-visible,a:focus-visible{outline:3px solid var(--cyan);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr));gap:22px}
[hidden]{display:none!important}
.card{background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:9px}
.cover{display:block;aspect-ratio:8.5/11;background:#FAF7F1;border:1px solid #B9C3C1;overflow:hidden}
.cover img{width:100%;height:100%;object-fit:cover;object-position:top;display:block}
.cover.soon{display:grid;place-items:center;color:#56646C;font-size:.9rem;text-align:center;padding:16px}
.card h2{font-size:1.2rem}.card p{margin:0;font-size:.93rem;color:var(--muted)}
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
.intro{background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:18px 20px;margin:0 0 24px}
.intro h2{font-size:1.45rem;margin-bottom:6px}.intro p{margin:0 0 12px;max-width:72ch}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:12px;margin:0;padding:0;list-style:none;counter-reset:s}
.steps li{counter-increment:s;padding-left:34px;position:relative;font-size:.95rem}
.steps li::before{content:counter(s);position:absolute;left:0;top:-1px;width:24px;height:24px;border-radius:50%;background:var(--cyan);color:var(--paper);font-weight:700;display:grid;place-items:center;font-size:.85rem}
footer{margin-top:40px;color:var(--muted);font-size:.86rem;border-top:1px solid var(--line);padding-top:14px}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&display=swap" rel="stylesheet">')


def page(cfg, title, body, root="", head_extra=""):
    contact = f' · Corrections: <a href="mailto:{E(cfg["contact"])}">{E(cfg["contact"])}</a>' if cfg.get("contact") else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="{E(cfg['tagline'])}">{FONTS}{head_extra}<style>{CSS}</style></head>
<body><div class="wrap"><header class="top"><div><h1><a href="{root}index.html">{E(cfg['title'])}</a></h1><p>{E(cfg['tagline'])}</p></div>
<nav><a href="{root}index.html">Papers</a><a href="{root}builder.html">Design your own</a><a href="{root}about.html">How it's made</a></nav></header>
{body}<footer>Written by AI from verified news sources, then checked automatically. Every issue lists its sources{contact}.</footer></div></body></html>"""


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
                poster.build(ed, spec, os.path.join(edir, f"{date}-poster.pdf"))
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
                render.build(ed, issue, os.path.join(edir, pdf))
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
        dl = (f'<a class="btn" href="e/{eid}/latest.pdf" download="{eid}-{latest[0]}.pdf">Download latest PDF</a>'
              if latest else "")
        cards.append((latest is None, FACET_ORDER.get(audience(ed), 50), ed["name"], f'''<article class="card" data-audience="{E(audience(ed))}" data-length="{E(length_band(n))}" data-focus="{E(focus)}" data-frequency="{E(frequency(ed))}">
{cover}<h2>{E(ed['name'])}</h2><p>{E(blurb)}</p><div class="meta">{E(meta)}{f" · latest {dt.date.fromisoformat(latest[0]):%d %b}" if latest else ""}</div>
<div class="actions">{dl}<a class="btn ghost" href="e/{eid}/index.html">All issues</a></div></article>'''))
        if latest_poster:                          # the poster gets its own card, thumbnail and download
            if has_png:
                subprocess.run(["pdftoppm", "-png", "-r", "60", "-singlefile", os.path.join(edir, "latest-poster.pdf"),
                                os.path.join(edir, "poster-cover")], check=False)
            pq = posters[latest_poster]["question"]
            pcover = (f'<a class="cover" href="e/{eid}/latest-poster.pdf"><img src="e/{eid}/poster-cover.png" '
                      f'alt="The latest Big Question poster: {E(pq)}" loading="lazy"></a>' if has_png
                      else f'<a class="cover soon" href="e/{eid}/latest-poster.pdf">{E(pq)}</a>')
            pmeta = f"{audience(ed)} · 1-page poster · {frequency(ed)} · latest {dt.date.fromisoformat(latest_poster):%d %b}"
            cards.append((False, FACET_ORDER.get(audience(ed), 50), ed["name"] + " poster", f'''<article class="card" data-audience="{E(audience(ed))}" data-length="1 page" data-focus="{E(focus)}" data-frequency="{E(frequency(ed))}">
{pcover}<span class="tag">Poster</span><h2>The Big Question</h2><p>One big idea from this week's news on a single page: a picture to explore, something to try at home and questions to talk about together. This week: &ldquo;{E(pq)}&rdquo;</p><div class="meta">{E(pmeta)} · from {E(ed["name"])}</div>
<div class="actions"><a class="btn poster" href="e/{eid}/latest-poster.pdf" download="{eid}-{latest_poster}-poster.pdf">Download poster</a><a class="btn ghost" href="e/{eid}/index.html">All posters</a></div></article>'''))
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

    cards = [c[3] for c in sorted(cards)]
    # front page with filters
    def facet(name, label, values):
        vals = sorted(set(values), key=lambda v: (FACET_ORDER.get(v, 50), v))
        return (f'<div class="frow" role="group" aria-label="{label}"><span>{label}</span><button type="button" data-f="{name}" data-v="" aria-pressed="true">All</button>'
                + "".join(f'<button type="button" data-f="{name}" data-v="{E(v)}" aria-pressed="false">{E(v)}</button>' for v in vals) + "</div>")
    import re as _re
    attrs = lambda k: _re.findall(rf'data-{k}="([^"]*)"', "".join(cards))
    filters = ('<div class="filters">' + facet("audience", "Reader", attrs("audience")) + facet("length", "Length", attrs("length"))
               + facet("focus", "Focus", attrs("focus")) + facet("frequency", "How often", attrs("frequency")) + "</div>")
    script = """<script>
const st={audience:"",length:"",focus:"",frequency:""};
document.querySelectorAll('.frow button').forEach(b=>b.addEventListener('click',()=>{
  st[b.dataset.f]=b.dataset.v;
  document.querySelectorAll(`.frow button[data-f="${b.dataset.f}"]`).forEach(x=>x.setAttribute('aria-pressed',String(x===b)));
  let shown=0;document.querySelectorAll('.card').forEach(c=>{const ok=Object.entries(st).every(([k,v])=>!v||c.dataset[k]===v);c.hidden=!ok;if(ok)shown++;});
  document.getElementById('none').hidden=shown>0;}));
</script>"""
    intro = ""
    if cfg["intro_title"] or cfg["intro"]:
        heading = f'<h2>{E(cfg["intro_title"])}</h2>' if cfg["intro_title"] else ""
        text = f'<p>{E(cfg["intro"])}</p>' if cfg["intro"] else ""
        steps = "".join(f"<li>{E(x)}</li>" for x in cfg["steps"])
        steps = f'<ol class="steps">{steps}</ol>' if steps else ""
        intro = f'<section class="intro">{heading}{text}{steps}</section>'
    body = intro + filters + f'<div class="grid">{"".join(cards)}</div><p id="none" class="empty" hidden>No paper matches all of those. Try removing a filter.</p>' + script
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page(cfg, cfg["title"], body))
    about = f"""<h2 style="font-size:2rem;margin-bottom:10px">How it's made</h2><div style="max-width:68ch">
<p>Each paper is written for one kind of reader: their age, what the paper is for, which countries and topics it covers, how long it is and how often it comes out.</p>
<p><b>Written for their age.</b> Age changes the vocabulary, the explanations and the size of the type, never the standard of accuracy. Hard news such as wars and disasters is reported honestly but without graphic detail; papers for the youngest readers say what happened and who is helping. New words are explained, and many papers end with questions to talk about together.</p>
<p><b>Built from verified research.</b> An AI research desk (Claude, by Anthropic) searches the news for each topic. Only facts that point to a page the search actually returned are kept, and each paper is written from that research alone.</p>
<p><b>Checked before it is published.</b> Automatic checks confirm every section is complete, the layout fits the printed page, nothing is cut off, and every story lists its sources. A separate fact-check compares each claim with the research. An issue that fails isn't published, and the previous issue stays up.</p>
<p><b>It can still be wrong.</b> AI makes mistakes and early reports change. Every issue lists its sources on its paper's page, so you can check anything before handing it over.{f' To report an error, email <a href="mailto:{E(cfg["contact"])}">{E(cfg["contact"])}</a>.' if cfg.get("contact") else ""}</p>
<p>You can also <a href="builder.html">design a paper for your own child</a>: the page writes instructions for your own AI chatbot, then checks its reply and prints it with the same engine. The engine is open source.</p></div>"""
    open(os.path.join(out, "about.html"), "w", encoding="utf-8").write(page(cfg, "How it's made", about))
    b = os.path.join(ROOT, "tools", "newspaper-builder.html")
    if os.path.exists(b):
        shutil.copy(b, os.path.join(out, "builder.html"))
        engine_zip(os.path.join(out, "builder-engine.zip"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    log(f"site written to {out}")
    return out


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
