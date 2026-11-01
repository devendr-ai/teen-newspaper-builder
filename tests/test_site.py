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
    builder = (out / "builder.html").read_text(encoding="utf-8")
    assert 'rel="manifest" href="manifest.webmanifest"' in builder
    assert 'rel="manifest" href="manifest.webmanifest"' in index
    import zipfile                                       # the builder page runs the engine in the browser
    names = zipfile.ZipFile(out / "builder-engine.zip").namelist()
    assert {"ygc/chat.py", "ygc/render.py", "ygc/auto/llm.py", "docs/CRAFT_RULES.md", "docs/POSTERS.md",
            "reportlab/__init__.py", "reportlab/platypus/__init__.py"} <= set(names)
    assert not any("__pycache__" in n or n.startswith("editions/") for n in names)
    for facet in ("Ages 6–8", "Ages 12–14", "Ages 15+", "1 page", "3–4 pages", "Weekly", "Exam preparation"):
        assert f'data-v="{facet}"' in index
    # A recommendation must link to a real, dated PDF from this build, not a stale latest alias.
    for band, (eid, minutes, _) in site.RECOMMENDED.items():
        rec = re.search(r'<article class="recommended"[^>]*data-edition="' + eid + r'".*?</article>', index, re.S).group(0)
        date = site.issues_of(edition.load(eid))[0][0]
        assert f'e/{eid}/{date}.pdf' in rec and (out / "e" / eid / f"{date}.pdf").exists()
        assert f"About {minutes} minutes to read" in rec
        assert f'{len(edition.load(eid)["pages"])} pages' in rec
        assert 'target="_blank" rel="noopener"' in rec
    assert 'Indian exam preparation' in index
    assert 'data-v="Adults"' not in index and 'data-v="Professionals"' not in index   # a site for ages 6-15+
    assert 'class="intro"' in index and "Pick your child" in index            # the parents' intro from site.yaml
    assert 'class="how"' in index and 'class="agebar"' in index and 'id="filters" hidden' in index
    assert 'class="menu"' in index and 'class="card rp"' in index and '<span class="new">NEW</span>' in index
    bar = re.search(r'<nav class="tabbar"[^>]*>(.*?)</nav>', index, re.S).group(1)       # the phone's bottom bar
    assert 'href="index.html" aria-current="page"' in bar and 'href="play/index.html"' in bar and 'href="builder.html"' in bar
    le = out / "e" / "little-explorers"                     # the Big Question poster is a second download
    newest_poster = poster.posters_of(edition.load("little-explorers"))[0][0]
    latest_spec = json.load(open(poster.posters_of(edition.load("little-explorers"))[0][1]))
    if latest_spec.get("version") == 2:
        assert '<h2>Weekend News Poster' in index
        assert 'Two stories from this week' in index
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
def test_feedback_is_available_from_parent_tools_only_with_a_form(tmp_path, monkeypatch, url):
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
    parents = (out / "parents.html").read_text(encoding="utf-8")
    assert 'href="feedback.html"' in parents and 'href="feedback.html">Feedback</a>' in builder
    assert 'href="parents.html"' in index
    assert "Tell us</a>" in index                                       # footer link on every page
    assert 'src="https://docs.google.com/forms/d/e/1FAIpQLSabc/viewform?embedded=true"' in fb


def test_how_its_made_standards_corrections_and_privacy_pages(tmp_path, monkeypatch):
    real = site.issues_of
    newest = real(edition.load("junior-daily"))[0][0]
    monkeypatch.setattr(site, "issues_of", lambda ed: real(ed)[:1] if ed["id"] == "junior-daily" else [])
    monkeypatch.setattr(site, "corrections", lambda: [{"fixed": newest, "paper": "junior-daily", "issue": newest,
                                                       "what": "It said the river was 40 km long. It is 4 km long."}])
    out = tmp_path / "site"
    site.build(str(out), keep=1, log=lambda *a: None)
    for page in ("index.html", "about.html", "standards.html", "corrections.html", "privacy.html"):
        html = (out / page).read_text(encoding="utf-8")       # every page links to all four from its footer
        assert all(f'href="{p}"' in html for p in ("about.html", "standards.html", "corrections.html", "privacy.html"))
    about = (out / "about.html").read_text(encoding="utf-8")
    assert "No person reads each paper before\nit goes up." in about                   # says plainly how it's made
    fixes = (out / "corrections.html").read_text(encoding="utf-8")
    assert "It is 4 km long." in fixes and 'href="e/junior-daily/index.html">The Junior Daily</a>' in fixes
    paper = (out / "e" / "junior-daily" / "index.html").read_text(encoding="utf-8")
    assert 'class="meta fixed">Corrected' in paper and "It is 4 km long." in paper   # and next to the issue itself


def test_the_corrections_log_names_real_papers_and_dates():
    import datetime as dt
    eds = set(edition.list_editions())
    rows = site.corrections()
    assert rows, "the log keeps the corrections already made"
    for r in rows:
        assert r["paper"] in eds and r["what"].strip()
        assert dt.date.fromisoformat(r["fixed"]) >= dt.date.fromisoformat(r["issue"])


@pytest.mark.parametrize("code", ["", "newspebbles"])
def test_visit_counts_are_off_until_a_goatcounter_site_is_set(tmp_path, monkeypatch, code):
    cfg = site.site_config()
    monkeypatch.setattr(site, "site_config", lambda: dict(cfg, goatcounter=code))
    monkeypatch.setattr(site, "issues_of", lambda ed: [])
    out = tmp_path / "site"
    site.build(str(out), keep=1, log=lambda *a: None)
    pages = [out / p for p in ("index.html", "privacy.html", "builder.html", "play/index.html")]
    privacy = (out / "privacy.html").read_text(encoding="utf-8")
    if not code:
        assert not any("goatcounter.com/count" in p.read_text(encoding="utf-8") for p in pages)
        assert "visits aren't counted at the moment" in privacy and 'id="nocount"' not in privacy
        return
    for p in pages:
        html = p.read_text(encoding="utf-8")
        assert '"https://newspebbles.goatcounter.com/count"' in html and "document.cookie" not in html
        assert 'np-nocount' in html and "doNotTrack" in html and 'referrerPolicy="no-referrer"' in html
    assert 'id="nocount"' in privacy and "never stores them" in privacy


def test_the_header_stays_pinned_like_read_and_plays_bar():
    # A pinned header with a solid background keeps the logo sharp under a phone's status bar
    # (Safari blurs ordinary page content there), and the age bar pins just below it.
    css = re.sub(r"\s+", " ", site.CSS)
    head = css[css.index("header.top{"):css.index("}", css.index("header.top{"))]
    assert "position:sticky" in head and "top:0" in head and "background:var(--paper)" in head
    assert "safe-area-inset-top" in head
    assert ".agebar{position:sticky;top:var(--hh,0px)" in css
    assert '"--hh"' in site.page(site.site_config(), "t", "")


def test_recommendations_skip_unpublished_pdfs():
    # Missing or failed publication must never leave a broken featured print link.
    assert 'class="recommended"' not in site.recommendations({}, True)
    ed = edition.load("breakfast-table")
    recs = site.recommendations({ed["id"]: (ed, "2026-10-24")}, False)
    assert 'e/breakfast-table/2026-10-24.pdf' in recs
    assert '<img' not in recs
    assert 'e/little-explorers/' not in recs


def test_parent_navigation_has_four_destinations_and_hub_links(tmp_path, monkeypatch):
    monkeypatch.setattr(site, 'issues_of', lambda ed: [])
    site.build(str(tmp_path), keep=1, log=lambda *a: None)
    for name in ('index.html', 'parents.html', 'builder.html', 'about.html', 'feedback.html'):
        page = (tmp_path / name).read_text(encoding='utf-8')
        nav = re.search(r'<nav class="tabbar"[^>]*>(.*?)</nav>', page, re.S).group(1)
        assert re.findall(r'href="([^"]+)"', nav) == ['index.html', 'play/index.html', 'builder.html', 'parents.html']
    hub = (tmp_path / 'parents.html').read_text(encoding='utf-8')
    for name in ('about.html', 'standards.html', 'privacy.html', 'corrections.html', 'feedback.html', 'builder.html'):
        assert f'href="{name}"' in hub


def test_reading_data_reset_requires_confirmation_and_keeps_other_data():
    import json
    import shutil
    import subprocess
    from pathlib import Path
    from ygc import play
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js needed for reset behavior checks')
    result = subprocess.run([node, str(Path(__file__).with_name('reading-data-reset.cjs'))],
                            input=json.dumps({'controls': site.reading_data_controls(), 'reader': play.JS}),
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_terms_publisher_licence_and_contact_addresses(tmp_path, monkeypatch):
    monkeypatch.setattr(site, "issues_of", lambda ed: [])
    out = tmp_path / "site"
    site.build(str(out), keep=1, log=lambda *a: None)
    cfg = site.site_config()
    terms = (out / "terms.html").read_text(encoding="utf-8")
    assert f"made by <b>{cfg['publisher']}</b>" in terms and "https://creativecommons.org/licenses/by-nc/4.0/" in terms
    assert "no person reviews each paper before it is published" in terms and f"mailto:{cfg['contact']}" in terms
    for page in ("index.html", "about.html", "privacy.html", "terms.html", "parents.html"):
        html = (out / page).read_text(encoding="utf-8")
        assert 'href="terms.html">Terms</a>' in html                                   # linked from every footer
        assert f"© " in html and cfg["publisher"] in html and f"mailto:{cfg['info_email']}" in html
    assert "Who makes News Pebbles" in (out / "about.html").read_text(encoding="utf-8")
    assert f"mailto:{cfg['privacy_email']}" in (out / "privacy.html").read_text(encoding="utf-8")
    assert "terms.html" in (out / "sitemap.xml").read_text(encoding="utf-8")
