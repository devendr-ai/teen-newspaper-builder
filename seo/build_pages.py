"""Build the search pages into seo/site/. Reads editions. Writes only under seo/."""
import glob
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")
ORIGIN = "https://newspebbles.com"
# Public path these files are meant to occupy. Not wired into the publisher.
BASE = ORIGIN + "/find"

EDITIONS = {
    "breakfast-table": "9–11",
    "junior-daily": "9–11",
    "little-explorers": "6–8",
    "junior-explorer": "9–11",
    "current-affairs-digest": "15+",
}


def esc(s):
    return html.escape(s or "", quote=True)


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:60] or "story"


def edition_name(eid):
    path = os.path.join(ROOT, "editions", eid, "edition.yaml")
    text = open(path, encoding="utf-8").read()
    m = re.search(r'^name:\s*"?(.+?)"?\s*$', text, re.M)
    return m.group(1).strip().strip('"') if m else eid


def issues(eid):
    out = []
    for path in sorted(glob.glob(os.path.join(ROOT, "editions", eid, "issues", "*", "*.json"))):
        out.append(json.load(open(path, encoding="utf-8")))
    return out


def lead(issue):
    return (issue.get("blocks") or {}).get("lead") or {}


def paras(block):
    body = block.get("body") or []
    if isinstance(body, str):
        return [body]
    return [p for p in body if isinstance(p, str) and p.strip()]


def sources(block):
    rows = []
    for s in block.get("sources") or []:
        if isinstance(s, str):
            rows.append(("", s))
        elif isinstance(s, dict) and s.get("url"):
            rows.append((s.get("outlet") or s.get("title") or "", s["url"]))
    return rows


def story_rel(issue, block):
    return f"stories/{issue['date']}/{slug(block.get('headline'))}.html"


def page(title, description, canonical, body, depth):
    root = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="top">
<a class="mark" href="{root}index.html">News Pebbles · Find</a>
<nav>
<a href="{root}grades/5th-grade.html">5th grade</a>
<a href="{root}grades/6th-grade.html">6th grade</a>
<a href="{root}printable.html">Printable</a>
<a href="{root}calm.html">Not scary</a>
<a href="{root}homeschool.html">Homeschool</a>
<a href="{root}india.html">India</a>
<a href="{root}archive.html">Stories</a>
</nav>
</header>
<main>
{body}
</main>
<footer>
<p>Printed papers live on <a href="{ORIGIN}/">newspebbles.com</a>. These pages are the searchable text of stories that have already been published.</p>
</footer>
</body>
</html>
"""


def write(rel, html_text):
    path = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(html_text)
    return rel


def story_html(eid, issue):
    block = lead(issue)
    name = edition_name(eid)
    age = EDITIONS[eid]
    headline = block.get("headline") or name
    deck = block.get("deck") or ""
    date = issue["date"]
    rel = story_rel(issue, block)
    pdf = f"{ORIGIN}/e/{eid}/{date}.pdf"
    bits = [f"<p class='kicker'>{esc(name)} · ages {esc(age)} · {esc(date)}</p>",
            f"<h1>{esc(headline)}</h1>"]
    if deck:
        bits.append(f"<p class='deck'>{esc(deck)}</p>")
    for p in paras(block):
        bits.append(f"<p>{esc(p)}</p>")
    why = block.get("why")
    if isinstance(why, str) and why.strip():
        bits.append(f"<h2>Why it matters</h2><p>{esc(why)}</p>")
    elif isinstance(why, dict) and why.get("body"):
        bits.append("<h2>Why it matters</h2>")
        for p in paras({"body": why["body"]}):
            bits.append(f"<p>{esc(p)}</p>")
    graphic = block.get("map") or block.get("chart")
    if isinstance(graphic, dict) and (graphic.get("caption") or graphic.get("title")):
        bits.append(f"<p class='note'>{esc(graphic.get('title') or 'Picture')}. {esc(graphic.get('caption') or '')}</p>")
    srcs = sources(block)
    if srcs:
        bits.append("<h2>Sources</h2><ul>")
        for label, url in srcs:
            bits.append(f"<li><a href='{esc(url)}'>{esc(label or url)}</a></li>")
        bits.append("</ul>")
    bits.append(f"<p><a class='btn' href='{esc(pdf)}'>Print this issue (PDF)</a></p>")
    desc = deck or (paras(block)[0][:150] if paras(block) else headline)
    return rel, page(f"{headline} · news for ages {age}", desc, f"{BASE}/{rel}", "\n".join(bits), depth=2), headline, deck, date


def guide(rel, title, description, intro, eid, catalog):
    name = edition_name(eid)
    age = EDITIONS[eid]
    rows = catalog[eid][:5]
    items = []
    for rel_story, headline, deck, date in rows:
        items.append(
            f"<li><a href='{rel_story}'>{esc(headline)}</a> "
            f"<span>{esc(date)}</span><p>{esc(deck)}</p></li>"
        )
    latest = rows[0] if rows else None
    pdf = f"{ORIGIN}/e/{eid}/{latest[3]}.pdf" if latest else ORIGIN
    body = f"""
<p class="kicker">Ages {esc(age)} · {esc(name)}</p>
<h1>{esc(title)}</h1>
<p class="deck">{esc(description)}</p>
{intro}
<p><a class="btn" href="{esc(pdf)}">Print the latest issue (PDF)</a></p>
<h2>Recent stories</h2>
<ul class="stories">
{''.join(items)}
</ul>
<p>The full wording of each story is on its own page, so this page does not repeat it.</p>
"""
    # depth 1 for grades/*, depth 0 for top-level
    depth = rel.count("/")
    write(rel, page(title, description, f"{BASE}/{rel}", body, depth))


def main():
    catalog = {eid: [] for eid in EDITIONS}
    urls = []
    for eid in EDITIONS:
        for issue in issues(eid):
            if not lead(issue).get("headline"):
                continue
            rel, doc, headline, deck, date = story_html(eid, issue)
            write(rel, doc)
            catalog[eid].append(( "../" + rel if False else rel, headline, deck, date))
            urls.append(rel)
        catalog[eid].sort(key=lambda r: r[3], reverse=True)

    def href(from_rel, story_rel_path):
        return os.path.relpath(story_rel_path, os.path.dirname(from_rel)).replace(os.sep, "/")

    def cat(from_rel, eid):
        return [(href(from_rel, r), h, d, dt) for r, h, d, dt in catalog[eid]]

    guide("grades/5th-grade.html",
          "Current events for 5th grade, printable",
          "A short printable paper of current events for 5th grade, ages 9 to 11, with sources a parent can check.",
          "<p>Each issue is one or two pages for ages 9 to 11. Read it at breakfast, then print it on US Letter paper. Hard news is included. Graphic detail is not.</p>",
          "breakfast-table", {k: cat("grades/5th-grade.html", k) for k in catalog})
    guide("grades/6th-grade.html",
          "Current events for 6th grade",
          "The day's main stories explained for 6th grade, on one printable page, with sources listed.",
          "<p>This page follows The Junior Daily: the day's biggest stories on one page for ages 9 to 11.</p>",
          "junior-daily", {k: cat("grades/6th-grade.html", k) for k in catalog})
    guide("printable.html",
          "Printable current events for kids",
          "Print today's kids' news on US Letter paper. No account. The PDF is the paper; the story text is on this site.",
          "<p>Open the PDF, choose US Letter, and print. Leave it on the table. There is no login and no app to install.</p>",
          "breakfast-table", {k: cat("printable.html", k) for k in catalog})
    guide("calm.html",
          "News for kids without scary content",
          "Short news for ages 6 to 8 that stays calm: no graphic detail, sources listed, one story a grown-up can read aloud.",
          "<p>Stories for the youngest readers leave out graphic detail. What happened is still said plainly. The standard is on <a href='https://newspebbles.com/standards.html'>the standards page</a>.</p>",
          "little-explorers", {k: cat("calm.html", k) for k in catalog})
    guide("homeschool.html",
          "Homeschool current events for middle school",
          "A weekly current-events paper for homeschool middle school: one big story, a science note, and questions to discuss.",
          "<p>Use the weekly paper when you want one sitting, not a daily. The questions at the end are the lesson.</p>",
          "junior-explorer", {k: cat("homeschool.html", k) for k in catalog})
    guide("compare.html",
          "A printable alternative to classroom kids news",
          "How this printable paper differs from classroom kids news: one age band, a PDF you print, and sources listed on the story.",
          "<p>Classroom sites are built for a whole class and a login. This paper is one age band, a couple of pages, and a link to the source of every figure. It is not a copy of those sites.</p>",
          "breakfast-table", {k: cat("compare.html", k) for k in catalog})
    guide("india.html",
          "Current affairs for kids in India",
          "Daily current affairs written for older students in India: precise facts, key terms, and a short quiz, plus a paper for ages 12 to 14.",
          "<p>The daily digest is for ages 15 and up. For ages 12 to 14, use <a href='https://newspebbles.com/'>The Global Citizen Plus</a> on the main site.</p>",
          "current-affairs-digest", {k: cat("india.html", k) for k in catalog})

    # archive
    items = []
    for eid, rows in catalog.items():
        for rel, headline, deck, date in rows:
            items.append((date, f"<li><a href='{rel}'>{esc(headline)}</a> <span>{esc(edition_name(eid))} · {esc(date)}</span></li>"))
    items.sort(reverse=True)
    write("archive.html", page(
        "News stories for kids, by date",
        "Every lead story from the published kids' papers, as a page you can read and cite.",
        f"{BASE}/archive.html",
        "<h1>Stories</h1><ul class='stories'>" + "".join(h for _, h in items) + "</ul>",
        0))
    write("index.html", page(
        "Find a kids' news story by grade",
        "Printable current events for 5th grade, 6th grade, homeschool, and India, with the full story in HTML.",
        f"{BASE}/index.html",
        """<h1>Find a paper by what you searched</h1>
<ul class="stories">
<li><a href="grades/5th-grade.html">Current events for 5th grade</a><p>Printable, ages 9–11.</p></li>
<li><a href="grades/6th-grade.html">Current events for 6th grade</a><p>The day's stories on one page.</p></li>
<li><a href="printable.html">Printable current events for kids</a><p>US Letter, no account.</p></li>
<li><a href="calm.html">News for kids without scary content</a><p>Ages 6–8.</p></li>
<li><a href="homeschool.html">Homeschool current events</a><p>A weekly middle-school paper.</p></li>
<li><a href="compare.html">Compared with classroom kids news</a><p>Print, one age, sources listed.</p></li>
<li><a href="india.html">Current affairs for kids in India</a><p>Ages 15+ digest.</p></li>
<li><a href="archive.html">All stories</a><p>One page per lead story.</p></li>
</ul>""",
        0))

    css = """body{margin:0;font:18px/1.5 Georgia,serif;color:#1c1915;background:#faf7f1}
a{color:#0f3d36} .top{display:flex;flex-wrap:wrap;gap:12px 20px;align-items:center;
justify-content:space-between;padding:16px 20px;border-bottom:1px solid #d9d0c3;background:#fff}
.mark{font-weight:700;text-decoration:none;color:#1c1915}
nav{display:flex;flex-wrap:wrap;gap:10px 14px} nav a{font:14px/1.3 system-ui,sans-serif}
main{max-width:40rem;margin:0 auto;padding:28px 20px 48px} h1{font-size:2rem;line-height:1.15;margin:0 0 12px}
h2{font-size:1.25rem;margin:28px 0 8px} .kicker{font:13px/1.3 system-ui,sans-serif;letter-spacing:.04em;
text-transform:uppercase;color:#5c564c;margin:0 0 8px} .deck{font-size:1.15rem}
.btn{display:inline-block;margin-top:8px;background:#9d2c2c;color:#fff;text-decoration:none;
padding:10px 14px;border-radius:8px;font:600 16px/1 system-ui,sans-serif}
.stories{list-style:none;padding:0} .stories li{margin:0 0 16px;padding-bottom:12px;border-bottom:1px solid #eadfce}
.stories span{display:block;font:13px system-ui,sans-serif;color:#5c564c} .note{font-size:.95rem;color:#3d3832}
footer{border-top:1px solid #d9d0c3;padding:16px 20px 32px;font:14px/1.4 system-ui,sans-serif;color:#5c564c}
footer p{max-width:40rem;margin:0 auto}
"""
    write("style.css", css)
    locs = ["index.html", "archive.html", "grades/5th-grade.html", "grades/6th-grade.html",
            "printable.html", "calm.html", "homeschool.html", "compare.html", "india.html"] + urls
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for rel in locs:
        body.append(f"<url><loc>{BASE}/{rel}</loc></url>")
    body.append("</urlset>\n")
    write("sitemap.xml", "\n".join(body))
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    print(f"wrote {len(locs)} urls under seo/site")


if __name__ == "__main__":
    main()
