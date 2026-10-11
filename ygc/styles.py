"""Paragraph styles. type_scale 1.0 reproduces template v3 exactly; larger
values set bigger type for younger readers (every size, leading and gap scales
together, so the page keeps its proportions)."""
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle

from .graphics import INK, ACCENT, SECONDARY, MUTED

_BASE = {
    # name: (font, size, leading, align, color, spaceAfter, extra)
    "section_tag":  ("Helvetica-Bold", 7.5, 9, TA_LEFT, ACCENT, 2, {"letterSpacing": 1.5}),
    "headline_big": ("Times-Bold", 19, 21, TA_LEFT, INK, 4, {}),
    "headline_med": ("Times-Bold", 13, 15, TA_LEFT, INK, 3, {}),
    "headline_sm":  ("Times-Bold", 10.5, 12, TA_LEFT, INK, 1, {}),
    "deck":         ("Times-Italic", 9.5, 12, TA_LEFT, SECONDARY, 5, {}),
    "byline":       ("Helvetica-Oblique", 7.5, 9, TA_LEFT, MUTED, 3, {}),
    "body":         ("Times-Roman", 9, 11.5, TA_JUSTIFY, INK, 4, {"firstLineIndent": 9}),
    "body_lead":    ("Times-Roman", 9, 11.5, TA_JUSTIFY, INK, 4, {}),
    "why_title":    ("Helvetica-Bold", 8, 10, TA_LEFT, ACCENT, 2, {"letterSpacing": 1}),
    "why_body":     ("Times-Roman", 8.5, 10.5, TA_LEFT, INK, 2, {}),
    "caption":      ("Helvetica-Oblique", 6.5, 8, TA_LEFT, MUTED, 2, {}),
    "sign":         ("Times-Italic", 7.5, 9.5, TA_CENTER, MUTED, 0, {}),
    "banner":       ("Helvetica-Bold", 10, 12, TA_CENTER, SECONDARY, 0, {}),
}


def make_styles(scale=1.0):
    out = {}
    for name, (font, size, lead, align, color, after, extra) in _BASE.items():
        kw = {k: (v * scale if isinstance(v, (int, float)) else v) for k, v in extra.items()}
        out[name] = ParagraphStyle(
            f"ygc_{name}_{scale}", fontName=font, fontSize=size * scale,
            leading=lead * scale, alignment=align, textColor=color,
            spaceAfter=after * scale, **kw)
    return out
