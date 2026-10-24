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
    assert site.credit({"title": "News Pebbles", "domain": ""}) == "A News Pebbles paper"
    assert site.credit({"title": "News Pebbles", "domain": "newspebbles.com"}).endswith("newspebbles.com")
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
