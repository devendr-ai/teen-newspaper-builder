"""The app build: `python -m ygc site --kids` (Apple Kids Category, Google Play Families).

The public website stays exactly as it is. The kids build is the same site with:
- no visit counting (stats.py stays silent: no pixel, no 404 count, no Read & Play events);
- the feedback page's embedded Google Form swapped for a button and email links (site.feedback_body);
- the Parental Gate (assets/gate/) on every page: links out, email, share and print ask a grown-up,
  and the parents' pages (GATE_PAGES) stay hidden until a grown-up answers;
- the app bridge (assets/app/app.js), the Listen tab (ygc/listen.py) and For parents → "This app".

Nothing is removed: every link, button and page still works, behind the gate where it leaves the
app or is meant for grown-ups. `finish()` runs last, over the built site.
"""
import os
import re
import shutil

from .edition import ROOT

GATE_SRC = os.path.join(ROOT, "assets", "gate")
APP_JS = os.path.join(ROOT, "assets", "app", "app.js")
GATE_PAGES = ("parents.html", "feedback.html", "builder.html", "play/report.html")

# Buttons and links that are for grown-ups but stay inside the app: [file pattern, tag pattern, reason, always]
MARKS = [
    (r".*", r'<a class="btn ghost edition-share"', "share", True),                  # share sheet / copy link
    (r".*", r'<a class="btn recommended-print"', "print", False),                   # "Print this paper"
    (r"^play/certificate\.html$", r'<button type="button" class="big go print"', "print", False),
    (r"^play/(?!threads/)[^/]+/[^/]+\.html$", r'<a href="[^"]*">(?=Print this paper \(for grown-ups\))', "print", False),
    (r"^builder\.html$", r'<button type="button" class="btn go" data-bot=', "link", True),   # the AI chatbots
]


def head(rel_root):
    return (f'<link rel="stylesheet" href="{rel_root}gate/gate.css">'
            f'<script src="{rel_root}gate/gate.js" defer></script>'
            f'<script src="{rel_root}app.js"></script>')             # the app bridge (assets/app/app.js): first


def _root_for(rel, site_root):
    if rel == "404.html":                       # served at any address: links from the site's root
        return site_root
    return "../" * rel.count("/")


def finish(out, cfg, log=print):
    """Add the gate to every page of the built site in `out`."""
    dst = os.path.join(out, "gate")
    os.makedirs(dst, exist_ok=True)
    for f in ("gate.js", "gate.css"):
        shutil.copy(os.path.join(GATE_SRC, f), os.path.join(dst, f))
    shutil.copy(APP_JS, os.path.join(out, "app.js"))
    site_root = re.sub(r"^https?://[^/]+", "", (cfg.get("base_url") or "/").rstrip("/") + "/") or "/"
    pages = marked = 0
    for dp, _, fs in os.walk(out):
        for f in fs:
            if not f.endswith(".html"):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, out).replace(os.sep, "/")
            doc = open(p, encoding="utf-8").read()
            if "</head>" not in doc or "gate/gate.js" in doc:
                continue
            doc = doc.replace("</head>", head(_root_for(rel, site_root)) + "</head>", 1)
            if rel in GATE_PAGES:
                doc = re.sub(r"<html\b", "<html data-gate-page", doc, count=1)
            for files, tag, reason, always in MARKS:
                if re.match(files, rel):
                    gate = ('data-gate="always"' if always else "data-gate") + f' data-gate-reason="{reason}"'
                    doc, n = re.subn(tag, lambda m: re.sub(r"^<(\w+)", r"<\1 " + gate, m.group(0)), doc)
                    marked += n
            open(p, "w", encoding="utf-8").write(doc)
            pages += 1
    log(f"  kids: Parental Gate on {pages} pages, {marked} grown-up buttons marked, gated pages: {', '.join(GATE_PAGES)}")
