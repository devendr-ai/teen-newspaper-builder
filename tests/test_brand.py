"""The owl: one drawing for the website, the app icons, the builder page and print."""
import io
import os
from xml.etree import ElementTree

from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from ygc import brand, play, site


def test_the_owl_is_one_drawing_used_everywhere(tmp_path):
    svg = ElementTree.fromstring(brand.owl_svg())
    assert svg.get("viewBox") == "0 0 100 100"
    assert 'class="logo" aria-hidden="true"' in brand.inline()
    assert 'role="img" aria-label="The owl"' in brand.inline("owl", "The owl")
    html = open(os.path.join(brand.ROOT, "tools", "newspaper-builder.html"), encoding="utf-8").read()
    assert brand.owl_svg().split(">", 1)[1][:200] in html                         # the builder page carries it
    assert brand.inline() in site.page(site.site_config(), "t", "")              # every grown-ups' page
    cfg = site.site_config()
    assert brand.wordmark(cfg["title"]) in site.page(cfg, "t", "")                # the name, with its three pebbles
    assert brand.wordmark("News Pebbles").count("<i ") == 3 and "<b>Pebbles</b>" in brand.wordmark("News Pebbles")
    assert site.credit({"title": "News Pebbles", "domain": ""}) == "A News Pebbles paper  ·  Written and fact-checked by AI"
    assert site.credit({"title": "News Pebbles", "domain": "newspebbles.com", "corrections_email": "c@n.com"}) == \
        "A News Pebbles paper  ·  newspebbles.com  ·  Written and fact-checked by AI  ·  Corrections: c@n.com"
    for n in (180, 192, 512):
        assert Image.open(os.path.join(brand.ASSETS, f"owl-icon-{n}.png")).size == (n, n)
    assert Image.open(os.path.join(brand.ASSETS, "owl-32.png")).size == (32, 32)


def test_the_printed_owl_reads_the_same_svg():
    out = io.BytesIO()
    c = Canvas(out, pagesize=(120, 120))
    brand.draw(c, 10, 10, 100)                       # every element of owl.svg is understood
    c.save()
    assert out.getvalue().startswith(b"%PDF")


def test_the_site_ships_the_owl_as_its_tab_icon(tmp_path):
    play.build(str(tmp_path), site.site_config(), keep=1, log=lambda *a: None)
    assert (tmp_path / "play" / "owl.svg").read_bytes() == open(brand.SVG, "rb").read()
    assert open(tmp_path / "play" / "icon-192.png", "rb").read() == open(os.path.join(brand.ASSETS, "owl-icon-192.png"), "rb").read()
    lobby = (tmp_path / "play" / "index.html").read_text(encoding="utf-8")
    assert 'href="../play/owl.svg"' in lobby and 'class="owl"' in lobby


def test_printed_papers_say_how_they_are_made_not_a_made_up_editor(tmp_path):
    import json
    from pypdf import PdfReader
    from ygc import edition, render
    cfg = site.site_config()
    assert "Editor-in-Chief" not in edition.DEFAULTS["labels"]["byline"]
    for eid in ("young-global-citizen", "current-affairs-digest"):     # one of them still stores the old byline
        ed = edition.load(eid)
        date, p = next((d, p) for d, p in site.issues_of(ed) if d == "2026-10-10") if eid == "young-global-citizen" \
            else site.issues_of(ed)[0]
        out = tmp_path / f"{eid}.pdf"
        render.build(ed, json.load(open(p, encoding="utf-8")), str(out), credit=site.credit(cfg),
                     byline=site.byline(cfg), author=cfg["title"])
        pdf = PdfReader(str(out))
        text = " ".join(pg.extract_text() for pg in pdf.pages)
        assert "Editor-in-Chief" not in text and "Written and fact-checked by AI · News Pebbles" in text
        assert f"Corrections: {cfg['corrections_email']}" in text and pdf.metadata.author == "News Pebbles"
