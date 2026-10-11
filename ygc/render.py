"""Render an issue to PDF from its edition's page plan, and measure fit.

Each column is its own frame. `measure()` lays every column out with the same
ReportLab engine the real build uses, so it reports exactly how many points a
column is over (or short), before anything spills onto an extra page.
"""
import datetime as dt
import io

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer)

from .graphics import (INK, ACCENT, MUTED, PAPER, HRule, StyledMap, BarChart,
                       IllustrationCard)
from .styles import make_styles

PAGE_W, PAGE_H = letter
LEFT_M = RIGHT_M = TOP_M = BOT_M = 0.5 * inch
CONTENT_W = PAGE_W - LEFT_M - RIGHT_M
MAST_H = 1.55 * inch
BANNER_H = 0.42 * inch
GUTTER = 0.16 * inch


# ------------------------------------------------------------------ geometry
def col_width(ncols):
    return (CONTENT_W - (ncols - 1) * GUTTER) / float(ncols)


def page_geometry(ed):
    """[(banner_frame_or_None, [(x, y, w, h), ...]), ...] per page."""
    out = []
    for p, page in enumerate(ed["pages"]):
        n = len(page["columns"])
        w = col_width(n)
        banner = None
        if page.get("masthead"):
            h = PAGE_H - TOP_M - MAST_H - BOT_M - 0.08 * inch
        elif page.get("banner"):
            banner = (LEFT_M, PAGE_H - TOP_M - BANNER_H, CONTENT_W, BANNER_H)
            h = PAGE_H - TOP_M - BANNER_H - BOT_M - 0.10 * inch
        else:
            h = PAGE_H - TOP_M - BOT_M
        cols = [(LEFT_M + i * (w + GUTTER), BOT_M, w, h) for i in range(n)]
        out.append((banner, cols))
    return out


# ------------------------------------------------------------------ issue meta
def date_of(issue):
    return dt.date.fromisoformat(issue["date"])


def date_str(issue):
    d = date_of(issue)
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def vol_str(issue):
    return f"Vol. {issue.get('volume', 1)}  •  No. {issue['issue']}"


# ------------------------------------------------------------------ blocks
class Ctx:
    def __init__(self, ed, issue):
        self.ed, self.issue = ed, issue
        self.S = make_styles(float(ed["style"].get("type_scale", 1.0)))
        self.L = ed["labels"]
        self.scale = float(ed["style"].get("type_scale", 1.0))


def _extras(out, s, cfg, ctx):
    for key in cfg.get("extras", []):
        if s.get(key):
            out.append(Spacer(1, 4))
            out.append(Paragraph(ctx.L[key], ctx.S["why_title"]))
            out.append(Paragraph(s[key], ctx.S["why_body"]))


def r_story(s, cfg, ctx, w):
    S = ctx.S
    size = cfg.get("size", "standard")
    graphics = cfg.get("graphics", [])
    out = [Paragraph(s.get("kicker", ""), S["section_tag"])]
    head = {"lead": "headline_big", "standard": "headline_med", "compact": "headline_sm"}[size]
    out.append(Paragraph(s["headline"], S[head]))
    if s.get("deck"):
        out.append(Paragraph(s["deck"], S["deck"]))
    if size == "lead":
        out.append(Paragraph(s.get("byline", ctx.L["byline"]), S["byline"]))
    out.append(HRule(w, 0.5))
    out.append(Spacer(1, 3))
    for i, para in enumerate(s.get("body", [])):
        out.append(Paragraph(para, S["body_lead"] if i == 0 else S["body"]))
    if "map" in graphics and s.get("map"):
        out.append(Spacer(1, 3))
        out.append(StyledMap(s["map"], width=w, height=1.7 * inch))
        out.append(Paragraph(s["map"].get("caption", ""), S["caption"]))
    if "illustration" in graphics and s.get("illustration"):
        out.append(Spacer(1, 3))
        h = 1.25 * inch if size == "lead" else 1.40 * inch
        out.append(IllustrationCard(s["illustration"], width=w, height=h))
        out.append(Paragraph(s["illustration"].get("caption", ""), S["caption"]))
    if "chart" in graphics and s.get("chart"):
        out.append(Spacer(1, 4))
        out.append(BarChart(s["chart"], width=w, height=1.80 * inch))
        out.append(Paragraph(s["chart"].get("caption", ""), S["caption"]))
    _extras(out, s, cfg, ctx)
    if cfg.get("also") and s.get("also"):
        out.append(Spacer(1, 4))
        out.append(Paragraph(cfg["also"].get("title", "ALSO IN THE NEWS"), S["why_title"]))
        for line in s["also"]:
            out.append(Paragraph(f"• {line}", S["why_body"]))
    return out


def r_feature(s, cfg, ctx, w):
    S = ctx.S
    out = [Spacer(1, 5), Paragraph(cfg.get("label", s.get("label", "")), S["section_tag"]),
           Paragraph(s["title"], S["headline_med"]), HRule(w, 0.5), Spacer(1, 3)]
    for i, para in enumerate(s.get("body", [])):
        out.append(Paragraph(para, S["body_lead"] if i == 0 else S["body"]))
    if s.get("illustration"):
        out.append(Spacer(1, 3))
        out.append(IllustrationCard(s["illustration"], width=w, height=1.40 * inch))
        out.append(Paragraph(s["illustration"].get("caption", ""), S["caption"]))
    return out


def r_briefs(s, cfg, ctx, w):
    title = s.get("title") or cfg.get("title", ctx.L["briefs"])
    out = [Spacer(1, 6), Paragraph(title, ctx.S["why_title"])]
    out += [Paragraph(f"• {b}", ctx.S["why_body"]) for b in s.get("items", [])]
    return out


def r_vocab(s, cfg, ctx, w):
    S = ctx.S
    out = [Spacer(1, 7), HRule(w, 0.5), Spacer(1, 3),
           Paragraph(cfg.get("label", ctx.L["vocab_tag"]), S["section_tag"]),
           Paragraph(s.get("title") or cfg.get("title", ctx.L["vocab_title"]), S["headline_med"]),
           HRule(w, 0.5), Spacer(1, 3)]
    for v in s.get("items", []):
        out.append(Paragraph(f"<b>{v['word']}</b>", S["headline_sm"]))
        out.append(Paragraph(v["def"], S["why_body"]))
        out.append(Spacer(1, 2))
    return out


def r_dyk(s, cfg, ctx, w):
    return [Spacer(1, 5), Paragraph(cfg.get("label", ctx.L["did_you_know"]), ctx.S["section_tag"]),
            Paragraph(s.get("text", ""), ctx.S["why_body"])]


def r_sports(s, cfg, ctx, w):
    return [Spacer(1, 5), Paragraph(cfg.get("label", ctx.L["sports"]), ctx.S["section_tag"]),
            Paragraph(s.get("title", ""), ctx.S["headline_sm"]),
            Paragraph(s.get("body", ""), ctx.S["why_body"])]


def r_watchlist(s, cfg, ctx, w):
    title = s.get("title") or cfg.get("title", ctx.L["watchlist"])
    out = [Spacer(1, 5), Paragraph(title, ctx.S["section_tag"])]
    out += [Paragraph(f"• {x}", ctx.S["why_body"]) for x in s.get("items", [])]
    return out


def r_quote(s, cfg, ctx, w):
    q = f"<i>“{s['text']}”</i>"
    if s.get("by"):
        q += f"  — {s['by']}"
    return [Spacer(1, 5), HRule(w, 0.5), Paragraph(q, ctx.S["sign"]), HRule(w, 0.5)]


def r_sign_off(s, cfg, ctx, w):
    return [Spacer(1, 5), Paragraph((s or {}).get("text") or cfg["text"], ctx.S["sign"])]


def r_rule(ctx, w):
    return [Spacer(1, 7), HRule(w, 0.5), Spacer(1, 2)]


RENDERERS = {"story": r_story, "feature": r_feature, "briefs": r_briefs, "vocab": r_vocab,
             "did_you_know": r_dyk, "sports": r_sports, "watchlist": r_watchlist,
             "quote": r_quote, "sign_off": r_sign_off}


def column_flowables(block_ids, ctx, w):
    out = []
    for bid in block_ids:
        if bid == "rule":
            out += r_rule(ctx, w)
            continue
        cfg = ctx.ed["blocks"][bid]
        content = ctx.issue.get("blocks", {}).get(bid)
        if content is None and cfg["type"] != "sign_off":
            continue
        out += RENDERERS[cfg["type"]](content, cfg, ctx, w)
    return out


def banner_flowables(text, ctx):
    return [HRule(CONTENT_W, 1.2), Spacer(1, 2), Paragraph(text, ctx.S["banner"]),
            Spacer(1, 2), HRule(CONTENT_W, 0.5)]


# ------------------------------------------------------------------ page chrome
def _footer(canv, ed, issue, npages):
    canv.saveState()
    canv.setFillColor(PAPER)
    canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canv.setFont("Helvetica", 6.5)
    canv.setFillColor(MUTED)
    canv.drawCentredString(PAGE_W / 2, 0.32 * inch,
                           f"{ed['name']}  •  {date_str(issue)}  •  "
                           f"Page {canv.getPageNumber()} of {npages}")
    canv.restoreState()


def masthead_title_size(title, base=34):
    return min(base, base * (CONTENT_W - 8) / max(1, stringWidth(title, "Times-Bold", base)))


def _masthead(canv, ed, issue, npages):
    m = ed["masthead"]
    canv.saveState()
    cx = PAGE_W / 2
    y = PAGE_H - 0.5 * inch - 4
    canv.setStrokeColor(INK); canv.setLineWidth(0.6)
    canv.line(LEFT_M, y, PAGE_W - RIGHT_M, y)
    y -= 36
    canv.setFillColor(INK); canv.setFont("Times-Bold", masthead_title_size(m["title"]))
    canv.drawCentredString(cx, y, m["title"])
    y -= 22
    if m.get("subtitle"):
        canv.setFillColor(ACCENT); canv.setFont("Times-Italic", 18)
        canv.drawCentredString(cx, y, " ".join(m["subtitle"].replace(" ", "")))
    y -= 14
    if m.get("tagline"):
        canv.setFillColor(MUTED); canv.setFont("Times-Italic", 9.5)
        canv.drawCentredString(cx, y, f"“{m['tagline']}”")
    y -= 6
    canv.setStrokeColor(INK); canv.setLineWidth(1.5)
    canv.line(LEFT_M, y, PAGE_W - RIGHT_M, y)
    y -= 3; canv.setLineWidth(0.4)
    canv.line(LEFT_M, y, PAGE_W - RIGHT_M, y)
    y -= 10
    canv.setFillColor(INK); canv.setFont("Helvetica", 8)
    loc = issue.get("location") or m["location"]
    canv.drawCentredString(cx, y, f"{vol_str(issue)}  •  {date_str(issue)}  •  {loc}  •  "
                                  f"{npages} Page{'s' if npages != 1 else ''}")
    y -= 5; canv.setLineWidth(0.4)
    canv.line(LEFT_M, y, PAGE_W - RIGHT_M, y)
    canv.restoreState()


# ------------------------------------------------------------------ build
def build(ed, issue, path):
    ctx = Ctx(ed, issue)
    geo = page_geometry(ed)
    npages = len(geo)
    doc = BaseDocTemplate(path, pagesize=letter, leftMargin=LEFT_M, rightMargin=RIGHT_M,
                          topMargin=TOP_M, bottomMargin=BOT_M,
                          title=f"{ed['name']} — {date_str(issue)}",
                          author=f"Editor-in-Chief, {ed['name']}")
    templates = []
    for p, (banner, cols) in enumerate(geo):
        frames = []
        if banner:
            frames.append(Frame(*banner, id=f"p{p}_banner", leftPadding=0, rightPadding=0,
                                topPadding=0, bottomPadding=0))
        frames += [Frame(*c, id=f"p{p}_c{i}", leftPadding=0, rightPadding=0,
                         topPadding=0, bottomPadding=0) for i, c in enumerate(cols)]
        if ed["pages"][p].get("masthead"):
            def on_page(canv, doc, _p=p):
                _footer(canv, ed, issue, npages); _masthead(canv, ed, issue, npages)
        else:
            def on_page(canv, doc, _p=p):
                _footer(canv, ed, issue, npages)
        templates.append(PageTemplate(id=f"P{p}", frames=frames, onPage=on_page))
    doc.addPageTemplates(templates)

    story = []
    for p, page in enumerate(ed["pages"]):
        if p > 0:
            story += [NextPageTemplate(f"P{p}"), PageBreak()]
        w = geo[p][1][0][2]
        if page.get("banner"):
            story += banner_flowables(page["banner"], ctx)
            story.append(FrameBreak())
        for i, col in enumerate(page["columns"]):
            story += column_flowables(col, ctx, w)
            if i < len(page["columns"]) - 1:
                story.append(FrameBreak())
    doc.build(story)
    return path


# ------------------------------------------------------------------ measure
def _height(f, w):
    _, h = f.wrap(w, 10 ** 6)
    return h + f.getSpaceBefore() + f.getSpaceAfter()


def measure(ed, issue):
    """Per column: capacity, used and free points, and any overflow."""
    ctx = Ctx(ed, issue)
    body = ctx.S["body"]
    avg_char = stringWidth("the quick brown fox jumps over a lazy dog ", body.fontName,
                           body.fontSize) / 42.0
    out = []
    for p, (banner, cols) in enumerate(page_geometry(ed)):
        for i, (x, y, w, h) in enumerate(cols):
            fl = column_flowables(ed["pages"][p]["columns"][i], ctx, w)
            frame = Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0,
                          bottomPadding=0, showBoundary=0)
            canv = Canvas(io.BytesIO(), pagesize=letter)
            frame.addFromList(fl, canv)
            free = max(0.0, frame._y - frame._y1p)
            over = sum(_height(f, w) for f in fl) if fl else 0.0
            lines = over / body.leading
            out.append({
                "page": p + 1, "column": i + 1, "blocks": ed["pages"][p]["columns"][i],
                "capacity": h, "free": 0.0 if fl else free, "over": over,
                "over_lines": lines, "over_chars": int(lines * w / avg_char),
                "free_lines": (0.0 if fl else free) / body.leading,
            })
    return out
