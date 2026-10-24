"""The "Big Question" poster: one printed page that turns one news story into one idea.

A companion to an edition's issue, made for the youngest readers (6-8), who learn
from a picture and a conversation rather than from columns of text. Same layout
every week: a question, a big drawing, what happened, how it works in three
pictures, how it reaches your home, something to try, somewhere to find on a map,
questions to talk about, and a guess to check next week.

Every word is typeset here, never painted into a picture, so nothing can be
misspelt by an image generator. Every box is measured: text that doesn't fit is a
located error, never cut off.

Files live next to the edition's issues:  editions/<id>/posters/<year>/<date>.json
"""
import datetime as dt
import glob
import io
import json
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from . import checks, edition
from .graphics import IllustrationCard, StyledMap

PAGE_W, PAGE_H = letter
M = 0.4 * inch                       # page margin
GAP = 9                              # space between boxes
W = PAGE_W - 2 * M

INK = colors.HexColor("#1F2D3A")
TEAL = colors.HexColor("#0E7C86")
CORAL = colors.HexColor("#E2584D")
SUN = colors.HexColor("#F2B134")
TINTS = {"sky": "#E3F1F5", "sun": "#FDF1D6", "rose": "#FBE3E0", "leaf": "#E5F2E1", "sand": "#F6EFE2"}

FNAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")
HERO_MOTIFS = ["bottleneck"] + IllustrationCard.known_motifs()

BODY = ParagraphStyle("pbody", fontName="Helvetica", fontSize=11.5, leading=14.6, textColor=INK)
SMALL = ParagraphStyle("psmall", parent=BODY, fontSize=10, leading=12.6)
TIP = ParagraphStyle("ptip", parent=SMALL, fontName="Helvetica-Oblique", textColor=colors.HexColor("#4A5A66"))
QUESTION = ParagraphStyle("pq", fontName="Helvetica-Bold", fontSize=25, leading=28, textColor=colors.white)
STEP = ParagraphStyle("pstep", parent=SMALL, alignment=TA_CENTER)


# ------------------------------------------------------------------ files
def posters_dir(ed):
    return os.path.join(ed["_dir"], "posters")


def path_for(ed, date):
    return os.path.join(posters_dir(ed), date[:4], f"{date}.json")


def posters_of(ed):
    """[(date, path)] newest first."""
    out = []
    for p in glob.glob(os.path.join(posters_dir(ed), "**", "*.json"), recursive=True):
        m = FNAME_RE.search(os.path.basename(p))
        if m:
            out.append((m.group(1), p))
    return sorted(out, reverse=True)


def skeleton(ed, date):
    return {
        "edition": ed["id"], "date": date,
        "question": "", "skill": "",
        "happened": "",
        "hero": {"motif": "|".join(HERO_MOTIFS), "caption": ""},
        "steps": [{"title": "", "motif": "", "text": ""} for _ in range(3)],
        "home": {"chain": ["", "", "", ""], "text": ""},
        "find_it": {"map": {"title": "", "label_top": "", "label_bottom": "", "footnote": ""}, "text": ""},
        "try_it": {"title": "", "steps": ["", "", ""]},
        "talk": {"questions": ["", ""], "tip": ""},
        "next_week": "",
        "sources": [],
    }


# ------------------------------------------------------------------ drawing helpers
def _box(c, x, y, w, h, tint, title=None, title_col=TEAL):
    c.setFillColor(colors.HexColor(TINTS[tint])); c.setStrokeColor(colors.HexColor("#D3CBBC")); c.setLineWidth(0.8)
    c.roundRect(x, y, w, h, 9, stroke=1, fill=1)
    if title:
        c.setFillColor(title_col); c.setFont("Helvetica-Bold", 12.5)
        c.drawString(x + 11, y + h - 19, title.upper())
        return h - 26                # room left under the title
    return h


def _para(c, text, style, x, top, w, room, where, problems):
    """Draw a wrapped paragraph from `top` downwards; report if it needs more than `room`."""
    p = Paragraph(text, style)
    _, ph = p.wrap(w, 10_000)
    if ph > room + 0.5:
        problems.append(f"{where} is OVER by {ph - room:.0f} pt — cut about {(ph - room) / style.leading:.1f} lines")
    p.drawOn(c, x, top - ph)
    return ph


def _arrow(c, x1, x2, y, col=CORAL):
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(2)
    c.line(x1, y, x2 - 6, y)
    p = c.beginPath(); p.moveTo(x2, y); p.lineTo(x2 - 7, y + 4.5); p.lineTo(x2 - 7, y - 4.5); p.close()
    c.drawPath(p, stroke=0, fill=1)


def _number(c, x, y, n, r=11, col=CORAL):
    c.setFillColor(col); c.circle(x, y, r, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12); c.drawCentredString(x, y - 4.3, str(n))


def _draw_bottleneck(c, w, h):
    """A wide sea squeezed through a narrow gap: ships queue on one side."""
    c.setFillColor(colors.HexColor("#9CCBE0")); c.rect(0, 0, w, h, stroke=0, fill=1)
    land = colors.HexColor("#D9C99E"); c.setFillColor(land)
    mid, gap = w * 0.56, h * 0.085
    top = c.beginPath(); top.moveTo(0, h); top.lineTo(0, h * 0.86)
    top.curveTo(w * 0.30, h * 0.86, w * 0.42, h * 0.80, mid - w * 0.05, 0.5 * h + gap + 4)
    top.curveTo(mid, 0.5 * h + gap - 2, mid + w * 0.06, 0.5 * h + gap + 6, mid + w * 0.12, h * 0.72)
    top.curveTo(w * 0.80, h * 0.86, w * 0.92, h * 0.84, w, h * 0.86); top.lineTo(w, h); top.close()
    c.drawPath(top, stroke=0, fill=1)
    bot = c.beginPath(); bot.moveTo(0, 0); bot.lineTo(0, h * 0.14)
    bot.curveTo(w * 0.30, h * 0.14, w * 0.42, h * 0.20, mid - w * 0.05, 0.5 * h - gap - 4)
    bot.curveTo(mid, 0.5 * h - gap + 2, mid + w * 0.06, 0.5 * h - gap - 6, mid + w * 0.12, h * 0.28)
    bot.curveTo(w * 0.80, h * 0.14, w * 0.92, h * 0.16, w, h * 0.14); bot.lineTo(w, 0); bot.close()
    c.drawPath(bot, stroke=0, fill=1)
    # little hills and trees for a friendly landscape
    c.setFillColor(colors.HexColor("#8DB580"))
    for fx, fy, r in [(0.10, 0.93, 9), (0.17, 0.94, 7), (0.82, 0.94, 8), (0.90, 0.92, 10), (0.12, 0.06, 8), (0.86, 0.07, 9)]:
        c.circle(w * fx, h * fy, r, stroke=0, fill=1)
    # waves
    c.setStrokeColor(colors.white); c.setLineWidth(0.8)
    for wx, wy in [(0.06, 0.66), (0.20, 0.36), (0.33, 0.64), (0.72, 0.62), (0.86, 0.40), (0.10, 0.30)]:
        x0, y0 = w * wx, h * wy
        c.line(x0, y0, x0 + 6, y0 + 2); c.line(x0 + 6, y0 + 2, x0 + 12, y0)

    def ship(x, y, s, hull="#2E4A62"):
        c.setFillColor(colors.HexColor(hull))
        p = c.beginPath(); p.moveTo(x, y); p.lineTo(x + 34 * s, y); p.lineTo(x + 40 * s, y + 7 * s)
        p.lineTo(x - 2 * s, y + 7 * s); p.close(); c.drawPath(p, stroke=0, fill=1)
        for i, col in enumerate(["#E2584D", "#F2B134", "#0E7C86", "#E2584D"]):
            c.setFillColor(colors.HexColor(col)); c.rect(x + (3 + 7 * i) * s, y + 7 * s, 6 * s, 5 * s, stroke=0, fill=1)
        c.setFillColor(colors.white); c.rect(x + 30 * s, y + 7 * s, 5 * s, 8 * s, stroke=0, fill=1)
    s = 0.9 * min(1.0, w / 300.0)                                # ships shrink with the picture
    for x, y in [(0.04, 0.55), (0.04, 0.40), (0.17, 0.62), (0.17, 0.47), (0.17, 0.32), (0.30, 0.54), (0.30, 0.39)]:
        ship(w * x, h * y, s)
    ship(mid - 20 * s / 0.9, 0.5 * h - 6 * s / 0.9, s)           # the one squeezing through
    ship(w * 0.80, h * 0.46, s, hull="#3D5F7A")
    # traffic-jam marks
    c.setStrokeColor(CORAL); c.setLineWidth(1.6 * s / 0.9)
    for dy in (-7, 0, 7):
        c.line(mid - 34 * s / 0.9, 0.5 * h + dy * s / 0.9, mid - 27 * s / 0.9, 0.5 * h + dy * s / 0.9)


def _hero(c, spec, x, y, w, h):
    c.saveState(); c.translate(x, y)
    p = c.beginPath(); p.roundRect(0, 0, w, h, 9); c.clipPath(p, stroke=0)
    if spec["motif"] == "bottleneck":
        _draw_bottleneck(c, w, h)
    else:
        card = IllustrationCard({"motif": spec["motif"], "title": "", "subtitle": ""}, w, h)
        card.canv = c; IllustrationCard._MOTIFS[spec["motif"]](card, c, w, h)
    c.restoreState()
    c.setStrokeColor(INK); c.setLineWidth(1); c.roundRect(x, y, w, h, 9, stroke=1, fill=0)
    if spec.get("caption"):
        c.setFillColor(colors.Color(0.12, 0.18, 0.23, alpha=0.82)); c.roundRect(x + 8, y + 8, w - 16, 20, 6, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 10); c.drawString(x + 15, y + 14.5, spec["caption"])


def _mini(c, motif, x, y, w, h):
    card = IllustrationCard({"motif": motif}, w, h)
    c.saveState(); c.translate(x, y)
    p = c.beginPath(); p.roundRect(0, 0, w, h, 6); c.clipPath(p, stroke=0)
    if motif == "bottleneck":
        _draw_bottleneck(c, w, h)
    else:
        card.canv = c; IllustrationCard._MOTIFS[motif](card, c, w, h)
    c.restoreState()


# ------------------------------------------------------------------ page
def draw(c, ed, poster, problems, credit=None):
    top = PAGE_H - M

    # ---- header band: paper name, the question, this week's skill
    hh = 86
    c.setFillColor(TEAL); c.roundRect(M, top - hh, W, hh, 12, stroke=0, fill=1)
    d = dt.date.fromisoformat(poster["date"])
    c.setFillColor(colors.HexColor("#CFEDEF")); c.setFont("Helvetica-Bold", 9.5)
    c.drawString(M + 14, top - 17, f"{ed['name'].upper()}  •  THE BIG QUESTION  •  {d:%B} {d.day}, {d.year}")
    _para(c, poster["question"], QUESTION, M + 14, top - 24, W - 175, hh - 30, "question", problems)
    pill = f"SKILL: {poster['skill'].upper()}"
    c.setFont("Helvetica-Bold", 10); pw = c.stringWidth(pill) + 24
    c.setFillColor(SUN); c.roundRect(M + W - pw - 14, top - hh + 14, pw, 24, 12, stroke=0, fill=1)
    c.setFillColor(INK); c.drawCentredString(M + W - 14 - pw / 2, top - hh + 22, pill)
    y = top - hh - GAP

    # ---- hero picture + what happened
    rh = 142
    hw = W * 0.57
    _hero(c, poster["hero"], M, y - rh, hw, rh)
    bx, bw = M + hw + GAP, W - hw - GAP
    room = _box(c, bx, y - rh, bw, rh, "sun", "What happened")
    _para(c, poster["happened"], BODY, bx + 11, y - rh + room - 2, bw - 22, room - 10, "what happened", problems)
    y -= rh + GAP

    # ---- how it works: three numbered pictures
    sh = 132
    room = _box(c, M, y - sh, W, sh, "sky", "How it works")
    pw = (W - 22 - 2 * 14) / 3
    for i, st in enumerate(poster["steps"]):
        px = M + 11 + i * (pw + 14)
        img_h = 54
        iy = y - 26 - img_h
        _mini(c, st["motif"], px, iy, pw, img_h)
        _number(c, px + 12, iy + img_h - 12, i + 1)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 10.5); c.drawCentredString(px + pw / 2, iy - 13, st["title"].upper())
        _para(c, st["text"], STEP, px, iy - 17, pw, sh - 26 - img_h - 17 - 8, f"step {i + 1}", problems)
        if i < 2:
            _arrow(c, px + pw + 2, px + pw + 13, iy + img_h / 2, TEAL)
    y -= sh + GAP

    # ---- it reaches your home (a chain) + find it (a map)
    rh = 140
    lw = W * 0.55
    room = _box(c, M, y - rh, lw, rh, "rose", "It reaches your home", CORAL)
    chain = poster["home"]["chain"]
    n = len(chain)
    cw = (lw - 22 - (n - 1) * 16) / n
    cy = y - 30 - 34
    c.setFont("Helvetica-Bold", 10)
    for i, word in enumerate(chain):
        cx = M + 11 + i * (cw + 16)
        c.setFillColor(colors.white); c.setStrokeColor(CORAL); c.setLineWidth(1.2)
        c.roundRect(cx, cy, cw, 30, 8, stroke=1, fill=1)
        c.setFillColor(INK)
        if c.stringWidth(word, "Helvetica-Bold", 10) > cw - 6:
            problems.append(f"home chain word {word!r} is too wide for its box; keep it to about {int(cw / 6)} characters")
        c.drawCentredString(cx + cw / 2, cy + 11, word)
        if i < n - 1:
            _arrow(c, cx + cw + 2, cx + cw + 14, cy + 15)
    _para(c, poster["home"]["text"], BODY, M + 11, cy - 8, lw - 22, cy - 8 - (y - rh) - 8, "home", problems)
    fx, fw = M + lw + GAP, W - lw - GAP
    room = _box(c, fx, y - rh, fw, rh, "leaf", "Find it on a map")
    mh = 60
    mp = StyledMap(poster["find_it"]["map"], fw - 22, mh)
    mp.canv = c; c.saveState(); c.translate(fx + 11, y - 26 - mh); mp.draw(); c.restoreState()
    _para(c, poster["find_it"]["text"], SMALL, fx + 11, y - 26 - mh - 6, fw - 22, rh - 26 - mh - 6 - 8, "find it", problems)
    y -= rh + GAP

    # ---- try it + talk together
    rh = y - (M + 12 + 42 + GAP)
    lw = W * 0.47
    room = _box(c, M, y - rh, lw, rh, "sand", "Try it: " + poster["try_it"]["title"], CORAL)
    ty = y - 28
    for i, s in enumerate(poster["try_it"]["steps"]):
        _number(c, M + 22, ty - 8, i + 1, r=9, col=SUN)
        used = _para(c, s, SMALL, M + 37, ty, lw - 48, ty - (y - rh) - 8, f"try it step {i + 1}", problems)
        ty -= max(used, 18) + 5
    tx, tw = M + lw + GAP, W - lw - GAP
    room = _box(c, tx, y - rh, tw, rh, "sky", "Talk together")
    qy = y - 28
    for i, q in enumerate(poster["talk"]["questions"]):
        used = _para(c, f"<b>{i + 1}.</b> {q}", SMALL, tx + 11, qy, tw - 22, qy - (y - rh) - 8, f"talk question {i + 1}", problems)
        qy -= used + 5
    _para(c, "<b>For grown-ups:</b> " + poster["talk"]["tip"], TIP, tx + 11, qy, tw - 22, qy - (y - rh) - 8, "talk tip", problems)
    y -= rh + GAP

    # ---- next week: a guess to check
    nh = 42
    c.setFillColor(colors.HexColor(TINTS["sun"])); c.setStrokeColor(SUN); c.setLineWidth(1.4)
    c.roundRect(M, y - nh, W, nh, 10, stroke=1, fill=1)
    c.setFillColor(CORAL); c.setFont("Helvetica-Bold", 12.5); c.drawString(M + 12, y - 19, "NEXT WEEK")
    _para(c, poster["next_week"], BODY, M + 100, y - 9, W - 112 - 150, nh - 12, "next week", problems)
    c.setStrokeColor(INK); c.setLineWidth(0.8); c.line(M + W - 150, y - nh + 15, M + W - 14, y - nh + 15)
    c.setFillColor(colors.HexColor("#4A5A66")); c.setFont("Helvetica-Oblique", 9); c.drawString(M + W - 150, y - nh + 4, "Your guess")

    # ---- footer
    c.setFillColor(colors.HexColor("#7A8790")); c.setFont("Helvetica", 7.5)
    c.drawCentredString(PAGE_W / 2, M - 2, f"{ed['name']}  •  The Big Question  •  {d:%A, %B} {d.day}, {d.year}"
                                           "  •  Written by AI from verified sources, listed on the paper's web page"
                                           + (f"  •  {credit}" if credit else ""))


# ------------------------------------------------------------------ checks + build
def check(ed, poster, path):
    """Return a checks.Report with errors and notes, like checks.check_issue."""
    r = checks.Report()
    if poster.get("edition") != ed["id"]:
        r.err(f"poster.edition is {poster.get('edition')!r}, expected {ed['id']!r}")
    m = FNAME_RE.search(os.path.basename(path))
    try:
        dt.date.fromisoformat(poster.get("date", ""))
    except ValueError:
        r.err("poster.date must be an ISO date like 2026-10-10"); return r
    if not m or m.group(1) != poster["date"]:
        r.err("file name must be the poster's date, YYYY-MM-DD.json")
    if not os.path.exists(os.path.join(checks.issues_dir(ed), poster["date"][:4], poster["date"] + ".json")):
        r.note("no issue of the paper on this date; the poster is offered on its own")

    def need(v, where):
        if not (isinstance(v, str) and v.strip()):
            r.err(f"{where} is empty")
    need(poster.get("question"), "question"); need(poster.get("skill"), "skill"); need(poster.get("happened"), "happened")
    need(poster.get("next_week"), "next_week")
    hero = poster.get("hero") or {}
    if hero.get("motif") not in HERO_MOTIFS:
        r.err(f"hero.motif {hero.get('motif')!r}: choose one of {', '.join(HERO_MOTIFS)}")
    if len(hero.get("caption", "")) > 60:
        r.err("hero.caption: keep it to 60 characters")
    steps = poster.get("steps") or []
    if len(steps) != 3:
        r.err("steps: exactly 3 pictures")
    for i, s in enumerate(steps):
        need(s.get("title"), f"steps[{i}].title"); need(s.get("text"), f"steps[{i}].text")
        if len(s.get("title", "")) > 22:
            r.err(f"steps[{i}].title: keep it to 22 characters")
        if s.get("motif") not in HERO_MOTIFS:
            r.err(f"steps[{i}].motif {s.get('motif')!r}: choose one of {', '.join(HERO_MOTIFS)}")
    chain = (poster.get("home") or {}).get("chain") or []
    if not 2 <= len(chain) <= 5 or not all(isinstance(x, str) and x.strip() for x in chain):
        r.err("home.chain: 2 to 5 short words, from the news to your home")
    need((poster.get("home") or {}).get("text"), "home.text")
    mp = (poster.get("find_it") or {}).get("map") or {}
    for k in ("title", "label_top", "label_bottom"):
        need(mp.get(k), f"find_it.map.{k}")
    need((poster.get("find_it") or {}).get("text"), "find_it.text")
    tr = poster.get("try_it") or {}
    need(tr.get("title"), "try_it.title")
    if not 2 <= len(tr.get("steps") or []) <= 4:
        r.err("try_it.steps: 2 to 4 steps")
    talk = poster.get("talk") or {}
    if len(talk.get("questions") or []) != 2:
        r.err("talk.questions: exactly 2")
    need(talk.get("tip"), "talk.tip")
    urls = [u.get("url", "") if isinstance(u, dict) else str(u) for u in poster.get("sources", [])]
    if not [u for u in urls if re.match(r"https?://", u)]:
        r.err("sources: list the URLs the poster's facts came from")
    for where, s in checks.walk(poster, "poster"):
        if "…" in s:
            r.err(f"{where}: contains '…'")
        bad = sorted({ch for ch in s if ch != "…" and not checks._printable(ch)})
        if bad:
            r.err(f"{where}: the PDF fonts cannot print {' '.join(bad)} (black boxes)")
    if r.errors:
        return r
    problems = []
    try:
        draw(Canvas(io.BytesIO(), pagesize=letter), ed, poster, problems)
    except Exception as e:                                   # a drawing failure is a check failure
        r.err(f"could not draw the poster: {e!r}")
    for p in problems:
        r.err(p)
    return r


def build(ed, poster, out_pdf, credit=None):
    problems = []
    c = Canvas(out_pdf, pagesize=letter)
    c.setTitle(f"{ed['name']}: {poster['question']}")
    c.setAuthor(ed["name"])
    draw(c, ed, poster, problems, credit)
    c.showPage(); c.save()
    return out_pdf


def load(path):
    poster = json.load(open(path, encoding="utf-8"))
    ed = edition.load(poster.get("edition") or os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path)))))
    return ed, poster
