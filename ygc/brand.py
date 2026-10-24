"""News Pebbles' owl: one drawing (assets/owl.svg) for the website, the app icons,
the builder page and the printed masthead.

`draw()` puts the same owl on a PDF page. It reads the SVG itself, so the print and the
screen can't drift apart; it understands only what owl.svg uses (paths with M L H V C Z,
circles and rounded rectangles).
"""
import functools
import html
import os
import re
from xml.etree import ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SVG = os.path.join(ASSETS, "owl.svg")
NS = "{http://www.w3.org/2000/svg}"


@functools.lru_cache(maxsize=1)
def owl_svg():
    return open(SVG, encoding="utf-8").read().strip()


def inline(cls="logo", label=""):
    """The owl as inline SVG for a web page: decorative unless given a label."""
    a11y = f'role="img" aria-label="{label}"' if label else 'aria-hidden="true" focusable="false"'
    return owl_svg().replace("<svg ", f'<svg class="{cls}" {a11y} ', 1)


PEBBLES = ("#8E9AA0", "#D9C7A3", "#9DB48A")      # slate, sand, moss: the three stones under the name


def wordmark(title):
    """The name as a logo: the last word in coral, with three small pebbles underneath."""
    words = str(title).split()
    head, last = " ".join(words[:-1]), words[-1] if words else ""
    stones = "".join(f'<i style="background:{c}"></i>' for c in PEBBLES)
    return (f'<span class="wm"><span class="wt">{html.escape(head)} <b>{html.escape(last)}</b></span>'
            f'<span class="stones" aria-hidden="true">{stones}</span></span>')


def _path(p, d):
    """Trace an SVG path (absolute M L H V C Z only) onto a ReportLab path."""
    toks = re.findall(r"[MLHVCZ]|-?\d*\.?\d+", d)
    x = y = 0.0
    i, cmd = 0, None
    while i < len(toks):
        t = toks[i]
        if t in "MLHVCZ":
            cmd = t
            i += 1
            if cmd == "Z":
                p.close()
            continue
        n = lambda k: [float(v) for v in toks[i:i + k]]
        if cmd == "M":
            x, y = n(2); p.moveTo(x, y); i += 2; cmd = "L"
        elif cmd == "L":
            x, y = n(2); p.lineTo(x, y); i += 2
        elif cmd == "H":
            x = n(1)[0]; p.lineTo(x, y); i += 1
        elif cmd == "V":
            y = n(1)[0]; p.lineTo(x, y); i += 1
        elif cmd == "C":
            a = n(6); p.curveTo(*a); x, y = a[4], a[5]; i += 6
        else:
            raise ValueError(f"owl.svg: path command {cmd!r} isn't supported")


def draw(canv, x, y, size):
    """The owl on a PDF canvas, `size` points square, its bottom-left corner at (x, y)."""
    from reportlab.lib.colors import HexColor

    def colour(v):                                       # "#fff" means "#ffffff"
        return HexColor("#" + "".join(ch * 2 for ch in v[1:]) if len(v) == 4 else v)
    canv.saveState()
    canv.translate(x, y + size)
    canv.scale(size / 100, -size / 100)                 # SVG units, y down

    def walk(el, style):
        style = dict(style, **{k: v for k, v in el.attrib.items()
                               if k in ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin")})
        tag = el.tag.replace(NS, "")
        fill = style.get("fill", "#000") != "none"
        stroke = style.get("stroke", "none") != "none"
        if fill:
            canv.setFillColor(colour(style.get("fill", "#000")))
        if stroke:
            canv.setStrokeColor(colour(style["stroke"]))
            canv.setLineWidth(float(style.get("stroke-width", 1)))
            canv.setLineCap(1 if style.get("stroke-linecap") == "round" else 0)
            canv.setLineJoin(1 if style.get("stroke-linejoin") == "round" else 0)
        g = lambda k: float(el.get(k, 0))
        if tag == "path":
            p = canv.beginPath()
            _path(p, el.get("d"))
            canv.drawPath(p, stroke=int(stroke), fill=int(fill))
        elif tag == "circle":
            canv.circle(g("cx"), g("cy"), g("r"), stroke=int(stroke), fill=int(fill))
        elif tag == "rect":
            canv.roundRect(g("x"), g("y"), g("width"), g("height"), g("rx"), stroke=int(stroke), fill=int(fill))
        for child in el:
            walk(child, style)

    walk(ElementTree.fromstring(owl_svg()), {})
    canv.restoreState()
