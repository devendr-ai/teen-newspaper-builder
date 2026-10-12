"""The website builds every listed edition, with downloadable PDFs and visible sources."""
import os
import re
import shutil

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
    assert (ygc / "latest.pdf").exists() and (ygc / "2026-10-10.pdf").exists()
    assert 'href="e/young-global-citizen/latest.pdf"' in index
    page = (ygc / "index.html").read_text(encoding="utf-8")
    assert "aljazeera.com" in page                       # sources are shown to readers
    assert (out / "about.html").exists() and (out / "builder.html").exists() and (out / ".nojekyll").exists()
    for facet in ("Ages 6–8", "Ages 12–14", "Ages 15+", "1 page", "3–4 pages", "Weekly", "Exam preparation"):
        assert f'data-v="{facet}"' in index
    assert 'data-v="Adults"' not in index and 'data-v="Professionals"' not in index   # a site for ages 6-15+
    assert 'class="intro"' in index and "Pick your child" in index            # the parents' intro from site.yaml
    le = out / "e" / "little-explorers"                     # the Big Question poster is a second download
    assert (le / "latest-poster.pdf").exists() and (le / "2026-10-10-poster.pdf").exists()
    assert 'href="e/little-explorers/latest-poster.pdf"' in index
    assert (le / "poster-cover.png").exists() or not shutil.which("pdftoppm")
    assert 'href="2026-10-10-poster.pdf"' in (le / "index.html").read_text(encoding="utf-8")


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
