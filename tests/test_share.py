"""Shared links show a picture, a title and a description; search engines get a sitemap; lost visitors a 404 page."""
import datetime as dt
import json
import re

from PIL import Image

from ygc import edition, share, site


def test_every_page_gets_preview_tags_and_the_site_gets_a_sitemap_robots_and_404(tmp_path, monkeypatch):
    real = site.issues_of
    monkeypatch.setattr(site, "issues_of", lambda ed: real(ed)[:1] if ed["id"] == "little-explorers" else [])
    out = tmp_path / "site"
    site.build(str(out), keep=1, log=lambda *a: None)
    cfg = site.site_config()
    base = cfg["base_url"].rstrip("/") + "/"
    im = Image.open(out / "share" / "site.png")
    assert im.size == (1200, 630)

    home = (out / "index.html").read_text(encoding="utf-8")
    assert f'<meta property="og:image" content="{base}share/site.png">' in home
    assert f'<link rel="canonical" href="{base}">' in home and 'name="twitter:card" content="summary_large_image"' in home
    for p in out.rglob("*.html"):                                   # every page, once
        assert p.read_text(encoding="utf-8").count('property="og:title"') == 1, p

    date = real(edition.load("little-explorers"))[0][0]
    # Sharing goes to a dated, independently printable edition, not a moving latest alias.
    landing = (out / "e" / "little-explorers" / f"{date}.html").read_text(encoding="utf-8")
    assert f'href="e/little-explorers/{date}.html"' in home
    assert 'aria-label="Share this edition"' in home
    assert 'Ages 6–8' in landing and date[:4] in landing
    assert f'href="{date}.pdf"' in landing and 'Preview this paper (PDF)' in landing
    assert 'latest.pdf' not in landing and f'{date}.png' in landing
    assert 'Print this paper' in landing and 'data-share-title=' in landing
    issue = (out / "play" / "little-explorers" / f"{date}.html").read_text(encoding="utf-8")
    head = json.load(open(real(edition.load("little-explorers"))[0][1], encoding="utf-8"))["blocks"]
    lead = next(head[b]["headline"] for b in edition.story_blocks(edition.load("little-explorers")) if b in head)
    assert re.search(r'og:title" content="[^"]*' + re.escape(lead.split()[0]), issue)
    assert f'share/little-explorers-{date}.jpg' in issue and Image.open(out / "share" / f"little-explorers-{date}.jpg").size == (1200, 630)

    robots = (out / "robots.txt").read_text()
    assert "Allow: /" in robots and f"Sitemap: {base}sitemap.xml" in robots
    assert "User-agent: GPTBot" in robots and "User-agent: PerplexityBot" in robots
    sm = (out / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>{base}</loc><lastmod>" in sm and f"<loc>{base}play/little-explorers/{date}.html</loc><lastmod>{date}</lastmod>" in sm
    assert "404.html" not in sm
    assert (out / "llms.txt").exists() and (out / "llms-full.txt").exists()
    assert 'application/ld+json' in home and 'NewsMediaOrganization' in home
    assert 'name="twitter:title"' in home and 'name="twitter:image"' in home

    lost = (out / "404.html").read_text(encoding="utf-8")       # served at any address, so its links start at the root
    assert "We can't find that page" in lost and 'href="/index.html"' in lost and 'href="/play/index.html"' in lost
    assert 'rel="canonical"' not in lost


def test_edition_sharing_native_copy_and_manual_fallback():
    import shutil
    import subprocess
    from pathlib import Path
    import pytest
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js needed for sharing behavior checks')
    result = subprocess.run([node, str(Path(__file__).with_name('share-edition.cjs'))],
                            input=site.SHARE_SCRIPT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_stories_picture_has_its_map_and_still_works_without_one(tmp_path):
    cfg = site.site_config()
    where = {"place": "Aldabra", "lat": -9.42, "lon": 46.42, "countries": ["Seychelles"]}
    m = share.draw_map(where, (500, 380))
    assert m.size == (500, 380)
    assert share.draw_map({"place": "Nowhere"}, (500, 380)) is None
    for w, name in ((where, "a.jpg"), (None, "b.jpg")):
        share.issue_card(cfg, "The Little Explorer", "Ages 6–8", dt.date(2026, 10, 24),
                         "A very long headline about giant tortoises coming back to an island far away in the ocean",
                         "An island has more tortoises than people.", w, str(tmp_path / name))
        assert Image.open(tmp_path / name).size == (1200, 630)
    share.paper_card(cfg, "The Little Explorer", "Ages 6–8 · Weekly · 2 pages", dt.date(2026, 10, 24), None, str(tmp_path / "c.jpg"))
    assert Image.open(tmp_path / "c.jpg").size == (1200, 630)
