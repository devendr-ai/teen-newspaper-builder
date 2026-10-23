"""The website builds every listed edition, with downloadable PDFs and visible sources."""
import json
import os
import re
import shutil

import pytest

from ygc import edition, poster, site


def test_site_lists_every_edition_and_serves_latest_pdfs(tmp_path):
    out = tmp_path / "_site"
    site.build(str(out), keep=5, log=lambda *a: None)
    index = (out / "index.html").read_text(encoding="utf-8")
    eds = edition.list_editions()
    with_posters = [e for e in eds if poster.posters_of(edition.load(e))]
    assert index.count('class="card"') == len(eds) + len(with_posters)      # a poster has its own card
    assert index.count('data-audience="Ages 6–8"') == 2                      # the paper and its poster
    for eid in eds:
        assert (out / "e" / eid / "index.html").exists() and (out / "e" / eid / "feed.xml").exists()
    ygc = out / "e" / "young-global-citizen"
    dates = [d for d, _ in site.issues_of(edition.load("young-global-citizen"))]
    assert (ygc / "latest.pdf").exists() and all((ygc / f"{d}.pdf").exists() for d in dates[:5])
    assert not any((ygc / f"{d}.pdf").exists() for d in dates[5:])          # keep=5: older PDFs drop off
    assert 'href="e/young-global-citizen/latest.pdf"' in index
    page = (ygc / "index.html").read_text(encoding="utf-8")
    newest = json.load(open(site.issues_of(edition.load("young-global-citizen"))[0][1], encoding="utf-8"))
    url = next(x["url"] if isinstance(x, dict) else x for b in newest["blocks"].values() if isinstance(b, dict)
               for x in b.get("sources") or [])
    assert url.split("//")[-1].split("/")[0] in page                         # sources are shown to readers
    assert (out / "about.html").exists() and (out / "builder.html").exists() and (out / ".nojekyll").exists()
    assert 'href="play/index.html">Read &amp; Play</a>' in index and (out / "play" / "index.html").exists()
    import zipfile                                       # the builder page runs the engine in the browser
    names = zipfile.ZipFile(out / "builder-engine.zip").namelist()
    assert {"ygc/chat.py", "ygc/render.py", "ygc/auto/llm.py", "docs/CRAFT_RULES.md", "docs/POSTERS.md",
            "reportlab/__init__.py", "reportlab/platypus/__init__.py"} <= set(names)
    assert not any("__pycache__" in n or n.startswith("editions/") for n in names)
    for facet in ("Ages 6–8", "Ages 12–14", "Ages 15+", "1 page", "3–4 pages", "Weekly", "Exam preparation"):
        assert f'data-v="{facet}"' in index
    assert 'data-v="Adults"' not in index and 'data-v="Professionals"' not in index   # a site for ages 6-15+
    assert 'class="intro"' in index and "Pick your child" in index            # the parents' intro from site.yaml
    assert 'class="how"' in index and 'class="agebar"' in index and 'id="filters" hidden' in index
    assert 'class="menu"' in index and 'class="card rp"' in index and '<span class="new">NEW</span>' in index
    bar = re.search(r'<nav class="tabbar"[^>]*>(.*?)</nav>', index, re.S).group(1)       # the phone's bottom bar
    assert 'href="index.html" aria-current="page"' in bar and 'href="play/index.html"' in bar and 'href="builder.html"' in bar
    le = out / "e" / "little-explorers"                     # the Big Question poster is a second download
    newest_poster = poster.posters_of(edition.load("little-explorers"))[0][0]
    assert (le / "latest-poster.pdf").exists() and (le / f"{newest_poster}-poster.pdf").exists()
    assert 'href="e/little-explorers/latest-poster.pdf"' in index
    assert (le / "poster-cover.png").exists() or not shutil.which("pdftoppm")
    assert f'href="{newest_poster}-poster.pdf"' in (le / "index.html").read_text(encoding="utf-8")


def test_site_shows_a_placeholder_for_papers_without_issues(tmp_path, monkeypatch):
    real = site.issues_of
    monkeypatch.setattr(site, "issues_of", lambda ed: [] if ed["id"] == "junior-daily" else real(ed))
    out = tmp_path / "_site"
    site.build(str(out), keep=1, log=lambda *a: None)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "First issue coming soon" in index
    assert not (out / "e" / "junior-daily" / "latest.pdf").exists()


def test_filters_can_hide_cards(tmp_path):
    # The filter script sets `hidden` on cards; .card's display:flex would override the
    # browser default for [hidden] unless the stylesheet restores it.
    out = tmp_path / "_site"
    site.build(str(out), keep=1, log=lambda *a: None)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "[hidden]{display:none!important}" in index and "c.hidden=!ok" in index


@pytest.mark.parametrize("url", ["", "https://docs.google.com/forms/d/e/1FAIpQLSabc/viewform?usp=sf_link"])
def test_feedback_tab_appears_only_with_a_form(tmp_path, monkeypatch, url):
    cfg = site.site_config()
    monkeypatch.setattr(site, "site_config", lambda: dict(cfg, feedback_url=url))
    monkeypatch.setattr(site, "issues_of", lambda ed: [])          # fast: no PDFs needed here
    out = tmp_path / "site"
    site.build(str(out), keep=1, log=lambda *a: None)
    index = (out / "index.html").read_text(encoding="utf-8")
    builder = (out / "builder.html").read_text(encoding="utf-8")
    if not url:
        assert not (out / "feedback.html").exists() and 'href="feedback.html"' not in index + builder
        return
    fb = (out / "feedback.html").read_text(encoding="utf-8")
    assert 'href="feedback.html">Feedback</a>' in index and 'href="feedback.html">Feedback</a>' in builder
    assert "Tell us</a>" in index                                       # footer link on every page
    assert 'src="https://docs.google.com/forms/d/e/1FAIpQLSabc/viewform?embedded=true"' in fb
