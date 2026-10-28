"""Drawn graphics: rule, map, bar chart, editorial illustrations.

Carried over unchanged from template v3 so existing issues render identically.
Every graphic takes its column width from the caller.
"""
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Flowable
from reportlab.pdfbase.pdfmetrics import stringWidth

INK       = colors.HexColor("#1A1A1A")
ACCENT    = colors.HexColor("#A6192E")
SECONDARY = colors.HexColor("#0B3D5C")
MUTED     = colors.HexColor("#6B6B6B")
PAPER     = colors.HexColor("#FAF7F1")
LIGHTBG   = colors.HexColor("#F1EBDD")
COL_W     = 264.24   # two-column width; only a default, callers pass width


class HRule(Flowable):
    def __init__(self, width, thickness=1, color=INK):
        Flowable.__init__(self)
        self.width = width
        self.thickness = thickness
        self.color = color
        self.height = thickness + 2
    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 1, self.width, 1)


class StyledMap(Flowable):
    """Natural Earth locator map; legacy country labels resolve to real geometry."""
    def __init__(self, spec, width=COL_W, height=1.5*inch):
        Flowable.__init__(self)
        self.spec = spec or {}
        self.width = width
        self.height = height

    def draw(self):
        from .print_maps import draw
        draw(self.canv, self.spec, self.width, self.height)


class BarChart(Flowable):
    """Bar chart driven by real numbers from the day's reporting."""
    def __init__(self, spec, width=COL_W, height=1.7*inch):
        Flowable.__init__(self)
        self.spec = spec or {}
        self.width = width
        self.height = height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        s = self.spec
        c.setFillColor(PAPER); c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 7.5)
        c.drawString(6, h-12, s.get("title", "")[:46])
        c.setFont("Helvetica-Oblique", 6); c.setFillColor(MUTED)
        c.drawString(6, h-20, s.get("subtitle", "")[:52])
        margin_l, margin_b = 26, 24
        chart_w = w - margin_l - 8
        chart_h = h - margin_b - 32
        c.setStrokeColor(INK); c.setLineWidth(0.6)
        c.line(margin_l, margin_b, margin_l, margin_b + chart_h)
        c.line(margin_l, margin_b, margin_l + chart_w, margin_b)
        labels = s.get("labels", [])
        values = s.get("values", [])
        if not values:
            return
        max_v = s.get("max") or max(values)
        prefix = s.get("value_prefix", "")
        hi = s.get("highlight_after", -1)
        bar_w = chart_w / (len(values) * 1.8)
        gap = (chart_w - bar_w*len(values)) / (len(values)+1)
        for i, v in enumerate(values):
            x = margin_l + gap + i*(bar_w + gap)
            bar_h = (v / max_v) * chart_h
            c.setFillColor(ACCENT if i > hi else SECONDARY)
            c.rect(x, margin_b, bar_w, bar_h, stroke=0, fill=1)
            c.setFillColor(INK); c.setFont("Helvetica-Bold", 6)
            c.drawCentredString(x + bar_w/2, margin_b + bar_h + 2, f"{prefix}{v}")
            c.setFont("Helvetica", 5.5); c.setFillColor(MUTED)
            lab = labels[i] if i < len(labels) else ""
            c.drawCentredString(x + bar_w/2, margin_b - 8, lab.replace("\n", " ")[:14])
        c.setFillColor(MUTED); c.setFont("Helvetica", 5)
        for v in (0, max_v*0.5, max_v):
            y = margin_b + (v / max_v) * chart_h
            c.line(margin_l - 2, y, margin_l, y)
            c.drawRightString(margin_l - 3, y-1.5, f"{prefix}{int(v)}")
        c.setStrokeColor(INK); c.setLineWidth(0.5)
        c.rect(0, 0, w, h, stroke=1, fill=0)


class IllustrationCard(Flowable):
    """Drawn editorial illustration. Every registered motif paints a full
    scene edge-to-edge — there is no blank fallback. An unknown motif is a
    build-time error (see validate_content), never a blank card."""

    def __init__(self, spec, width=COL_W, height=1.15*inch):
        Flowable.__init__(self)
        self.spec = spec or {}
        self.width = width
        self.height = height

    # ---- shared scene helpers -------------------------------------
    @staticmethod
    def _sky(c, w, h, top="#BBD7E8", horizon=0.42, ground="#D8CFAE"):
        c.setFillColor(colors.HexColor(top))
        c.rect(0, h*horizon, w, h*(1-horizon), stroke=0, fill=1)
        c.setFillColor(colors.HexColor(ground))
        c.rect(0, 0, w, h*horizon, stroke=0, fill=1)

    @staticmethod
    def _sun(c, w, h, x=0.80, y=0.78, r=9, col="#E8A33C"):
        c.setFillColor(colors.HexColor(col))
        c.circle(w*x, h*y, r, stroke=0, fill=1)

    @staticmethod
    def _waves(c, w, h, tops, col="#FAF7F1"):
        c.setStrokeColor(colors.HexColor(col)); c.setLineWidth(0.7)
        for y in tops:
            x = 0
            while x < w:
                c.line(x, y, x+6, y+1.4); c.line(x+6, y+1.4, x+12, y)
                x += 12

    def _draw_talks(self, c, w, h):
        names = self.spec.get('participants', [])
        if not isinstance(names, list) or len(names) != 3 or any(not isinstance(n, str) for n in names):
            raise ValueError('talks diagram needs exactly three sourced participants')
        c.setFillColor(PAPER); c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(SECONDARY); c.setFont('Helvetica-Bold', 8)
        c.drawString(9, h - 15, "WHO'S INVOLVED?")
        gap, margin = 7, 9
        bw, by, bh = (w - margin * 2 - gap * 2) / 3, h * .43, 28
        c.setStrokeColor(MUTED); c.setLineWidth(.6)
        c.line(margin + bw / 2, by + bh / 2, w - margin - bw / 2, by + bh / 2)
        for i, name in enumerate(names):
            x = margin + i * (bw + gap)
            c.setFillColor(LIGHTBG); c.setStrokeColor(SECONDARY); c.roundRect(x, by, bw, bh, 3, stroke=1, fill=1)
            size = min(8, (bw - 8) / max(1, stringWidth(name, 'Helvetica-Bold', 1)))
            c.setFillColor(INK); c.setFont('Helvetica-Bold', size); c.drawCentredString(x + bw / 2, by + 10, name)
        c.setFont('Helvetica', 6.5); c.setFillColor(MUTED)
        c.drawCentredString(w / 2, 24, 'Trilateral means three parties')

    # ---- motifs ---------------------------------------------------
    def _draw_ship(self, c, w, h):
        self._sky(c, w, h, "#BBD7E8", 0.46, "#8FBCD4")
        self._sun(c, w, h)
        c.setFillColor(colors.HexColor("#1F2D3A"))
        c.rect(w*0.08, h*0.30, w*0.58, h*0.11, stroke=0, fill=1)
        p = c.beginPath()
        p.moveTo(w*0.66, h*0.30); p.lineTo(w*0.78, h*0.36)
        p.lineTo(w*0.66, h*0.41); p.close()
        c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#FAF7F1"))
        c.rect(w*0.14, h*0.41, w*0.11, h*0.12, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#A6192E"))
        c.rect(w*0.185, h*0.53, w*0.02, h*0.09, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#3A4A57"))
        for i in range(5):
            c.rect(w*(0.30+i*0.07), h*0.41, w*0.05, h*0.07, stroke=0, fill=1)
        self._waves(c, w, h, (h*0.10, h*0.20))

    def _draw_strait(self, c, w, h):
        c.setFillColor(colors.HexColor("#8FBCD4"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#C9B98C"))
        p = c.beginPath()
        p.moveTo(0, h); p.lineTo(w, h); p.lineTo(w, h*0.66)
        p.lineTo(w*0.66, h*0.60); p.lineTo(w*0.34, h*0.72); p.lineTo(0, h*0.68)
        p.close(); c.drawPath(p, stroke=0, fill=1)
        p = c.beginPath()
        p.moveTo(0, 0); p.lineTo(w, 0); p.lineTo(w, h*0.30)
        p.lineTo(w*0.62, h*0.36); p.lineTo(w*0.30, h*0.24); p.lineTo(0, h*0.30)
        p.close(); c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#7A6E4E"))
        p = c.beginPath()
        p.moveTo(w*0.16, h*0.68); p.lineTo(w*0.24, h*0.92); p.lineTo(w*0.32, h*0.68)
        p.close(); c.drawPath(p, stroke=0, fill=1)
        p = c.beginPath()
        p.moveTo(w*0.68, h*0.30); p.lineTo(w*0.76, h*0.08); p.lineTo(w*0.84, h*0.30)
        p.close(); c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1F2D3A"))
        c.rect(w*0.42, h*0.46, w*0.14, h*0.05, stroke=0, fill=1)
        self._waves(c, w, h, (h*0.40, h*0.56), "#E9F3F8")

    def _draw_border(self, c, w, h):
        self._sky(c, w, h, "#D9C9A8", 0.34, "#C4A97E")
        self._sun(c, w, h, 0.16, 0.80, 8, "#E8A33C")
        c.setStrokeColor(colors.HexColor("#4A4A4A")); c.setLineWidth(1.4)
        for i in range(6):
            x = w*(0.08 + i*0.17)
            c.line(x, h*0.34, x, h*0.80)
        c.setLineWidth(0.5)
        for j in range(9):
            y = h*(0.36 + j*0.05)
            c.line(w*0.05, y, w*0.95, y)
        c.setFillColor(colors.HexColor("#1F2D3A"))
        for i in range(11):
            x = w*(0.05 + i*0.085)
            c.circle(x, h*0.24, 3, stroke=0, fill=1)
            c.rect(x-2.5, h*0.06, 5, h*0.16, stroke=0, fill=1)

    def _draw_fire(self, c, w, h):
        c.setFillColor(colors.HexColor("#B14A2A"))
        c.rect(0, h*0.38, w, h*0.62, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E8A33C"))
        c.rect(0, h*0.38, w, h*0.22, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#3B2A22"))
        c.rect(0, 0, w, h*0.38, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1A1A1A"))
        for i in range(9):
            x = w*(0.04 + i*0.11)
            p = c.beginPath()
            p.moveTo(x-5, h*0.38); p.lineTo(x, h*0.38 + h*(0.16 + (i % 3)*0.05))
            p.lineTo(x+5, h*0.38); p.close()
            c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E8532A"))
        for i in range(7):
            x = w*(0.08 + i*0.14)
            p = c.beginPath()
            p.moveTo(x-4, h*0.30); p.lineTo(x, h*0.30 + h*(0.14 + (i % 2)*0.06))
            p.lineTo(x+4, h*0.30); p.close()
            c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#0E0C0A"))
        for i in range(3):
            x = w*(0.14 + i*0.30)
            c.rect(x, h*0.06, w*0.12, h*0.11, stroke=0, fill=1)
            p = c.beginPath()
            p.moveTo(x-3, h*0.17); p.lineTo(x + w*0.06, h*0.25)
            p.lineTo(x + w*0.12 + 3, h*0.17); p.close()
            c.drawPath(p, stroke=0, fill=1)

    def _draw_flood(self, c, w, h):
        self._sky(c, w, h, "#9BA9B4", 0.50, "#6E8A9C")
        c.setFillColor(colors.HexColor("#7E6A4E"))
        c.rect(0, h*0.50, w, h*0.06, stroke=0, fill=1)
        for i in range(3):
            x = w*(0.10 + i*0.30)
            c.setFillColor(colors.HexColor("#EDE5D2"))
            c.rect(x, h*0.36, w*0.14, h*0.20, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#A6192E"))
            p = c.beginPath()
            p.moveTo(x-3, h*0.56); p.lineTo(x + w*0.07, h*0.68)
            p.lineTo(x + w*0.14 + 3, h*0.56); p.close()
            c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#5C7C90"))
        c.rect(0, 0, w, h*0.42, stroke=0, fill=1)
        self._waves(c, w, h, (h*0.12, h*0.26, h*0.38), "#BBD7E8")
        c.setFillColor(colors.HexColor("#1F2D3A"))
        p = c.beginPath()
        p.moveTo(w*0.60, h*0.30); p.lineTo(w*0.82, h*0.30)
        p.lineTo(w*0.78, h*0.22); p.lineTo(w*0.64, h*0.22); p.close()
        c.drawPath(p, stroke=0, fill=1)

    def _draw_grid(self, c, w, h):
        c.setFillColor(colors.HexColor("#141C26"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#232F3D"))
        c.rect(0, 0, w, h*0.26, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#0A1119"))
        heights = [0.42, 0.30, 0.55, 0.38, 0.62, 0.34, 0.48]
        bw = w / len(heights)
        for i, hh in enumerate(heights):
            c.rect(i*bw, h*0.26, bw-2, h*hh, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E8A33C"))
        for (i, j) in ((0, 1), (2, 3), (4, 2), (6, 1)):
            c.rect(i*bw + 4, h*(0.30 + j*0.08), 3, 4, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#6B7C8C")); c.setLineWidth(1.2)
        cx = w*0.78
        c.line(cx-8, h*0.26, cx-3, h*0.88); c.line(cx+8, h*0.26, cx+3, h*0.88)
        for y in (0.40, 0.56, 0.72):
            c.line(cx-6.5, h*y, cx+6.5, h*y)
        c.setLineWidth(0.7)
        c.line(0, h*0.80, cx-4, h*0.86); c.line(cx+4, h*0.86, w, h*0.80)

    def _draw_ballot(self, c, w, h):
        c.setFillColor(colors.HexColor("#E8DFC2"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#0B3D5C"))
        c.rect(w*0.28, h*0.12, w*0.44, h*0.42, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#08293E"))
        c.rect(w*0.28, h*0.50, w*0.44, h*0.06, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1A1A1A"))
        c.rect(w*0.44, h*0.535, w*0.12, h*0.02, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#FAF7F1"))
        c.rect(w*0.42, h*0.56, w*0.16, h*0.24, stroke=0, fill=1)
        c.setStrokeColor(MUTED); c.setLineWidth(0.5)
        for j in range(4):
            c.line(w*0.445, h*(0.62 + j*0.04), w*0.555, h*(0.62 + j*0.04))
        c.setFillColor(ACCENT); c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(w*0.50, h*0.745, "X")
        c.setFillColor(colors.HexColor("#3A4A57"))
        for i in range(4):
            x = w*(0.06 + i*0.055)
            c.circle(x, h*0.34, 2.5, stroke=0, fill=1)
            c.rect(x-2, h*0.18, 4, h*0.14, stroke=0, fill=1)

    def _draw_airdefense(self, c, w, h):
        c.setFillColor(colors.HexColor("#101826"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1C2A3A"))
        c.rect(0, 0, w, h*0.22, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#4A5A68"))
        c.rect(w*0.10, h*0.16, w*0.20, h*0.10, stroke=0, fill=1)
        c.saveState()
        c.translate(w*0.20, h*0.26); c.rotate(52)
        c.setFillColor(colors.HexColor("#8A99A6"))
        c.rect(-4, 0, 8, h*0.34, stroke=0, fill=1)
        c.restoreState()
        c.setStrokeColor(colors.HexColor("#E8A33C")); c.setLineWidth(1.2)
        c.line(w*0.24, h*0.34, w*0.56, h*0.86)
        c.setStrokeColor(colors.HexColor("#A6192E")); c.setLineWidth(1.0); c.setDash(3, 2)
        for x0, y0 in ((0.98, 0.92), (0.86, 0.96), (0.72, 0.90)):
            c.line(w*x0, h*y0, w*(x0-0.28), h*(y0-0.52))
        c.setDash()
        c.setFillColor(colors.HexColor("#F2D06B"))
        c.circle(w*0.56, h*0.86, 5, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#FAF7F1"))
        c.circle(w*0.56, h*0.86, 2, stroke=0, fill=1)

    def _draw_rocket(self, c, w, h):
        c.setFillColor(colors.HexColor("#0B1626"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#FAF7F1"))
        for (x, y, r) in ((0.10, 0.86, 0.8), (0.28, 0.72, 0.6), (0.86, 0.80, 0.9),
                          (0.66, 0.92, 0.6), (0.44, 0.62, 0.5)):
            c.circle(w*x, h*y, r, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#D8D3C4"))
        p = c.beginPath()
        p.moveTo(w*0.50, h*0.92); p.lineTo(w*0.56, h*0.60)
        p.lineTo(w*0.44, h*0.60); p.close()
        c.drawPath(p, stroke=0, fill=1)
        c.rect(w*0.44, h*0.34, w*0.12, h*0.26, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        p = c.beginPath()
        p.moveTo(w*0.44, h*0.40); p.lineTo(w*0.36, h*0.28)
        p.lineTo(w*0.44, h*0.30); p.close(); c.drawPath(p, stroke=0, fill=1)
        p = c.beginPath()
        p.moveTo(w*0.56, h*0.40); p.lineTo(w*0.64, h*0.28)
        p.lineTo(w*0.56, h*0.30); p.close(); c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E8A33C"))
        p = c.beginPath()
        p.moveTo(w*0.45, h*0.34); p.lineTo(w*0.50, h*0.06)
        p.lineTo(w*0.55, h*0.34); p.close(); c.drawPath(p, stroke=0, fill=1)

    def _draw_podium(self, c, w, h):
        c.setFillColor(colors.HexColor("#E8DFC2"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#D6CBAF"))
        c.rect(0, 0, w, h*0.16, stroke=0, fill=1)
        blocks = ((0.14, 0.30, "#B08D57", "3"), (0.40, 0.52, "#C9A227", "1"),
                  (0.66, 0.40, "#9AA5AD", "2"))
        for x, bh, col, num in blocks:
            c.setFillColor(colors.HexColor(col))
            c.rect(w*x, h*0.16, w*0.20, h*bh, stroke=0, fill=1)
            c.setFillColor(colors.HexColor("#3A2E14")); c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(w*(x+0.10), h*0.22, num)
            c.setFillColor(colors.HexColor("#1F2D3A"))
            c.circle(w*(x+0.10), h*(0.16+bh)+9, 3.2, stroke=0, fill=1)
            c.rect(w*(x+0.10)-3, h*(0.16+bh), 6, 8, stroke=0, fill=1)
        c.setStrokeColor(ACCENT); c.setLineWidth(1)
        c.line(0, h*0.94, w, h*0.94)

    def _draw_cricket(self, c, w, h):
        c.setFillColor(colors.HexColor("#6FA96F"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#FAF7F1")); c.setLineWidth(1.4)
        c.circle(w*0.5, h*0.45, min(w, h)*0.52, stroke=1, fill=0)
        c.setFillColor(colors.HexColor("#D9C68A"))
        c.rect(w*0.44, h*0.14, w*0.12, h*0.62, stroke=0, fill=1)
        c.setStrokeColor(INK); c.setLineWidth(1)
        for x in (w*0.465, w*0.50, w*0.535):
            c.line(x, h*0.14, x, h*0.26)
            c.line(x, h*0.64, x, h*0.76)
        c.setFillColor(colors.HexColor("#1F2D3A"))
        c.circle(w*0.62, h*0.34, 3, stroke=0, fill=1)
        c.rect(w*0.605, h*0.16, 3, h*0.16, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#8A6A3A")); c.setLineWidth(2.2)
        c.line(w*0.63, h*0.30, w*0.70, h*0.16)
        c.setFillColor(ACCENT)
        c.circle(w*0.30, h*0.50, 3, stroke=0, fill=1)

    def _draw_skyline(self, c, w, h):
        self._sky(c, w, h, "#C6D9E8", 0.14, "#B4C4D2")
        c.setFillColor(colors.HexColor("#0B3D5C"))
        heights = [0.45, 0.32, 0.58, 0.40, 0.68, 0.36, 0.52, 0.30]
        bw = w / len(heights)
        for i, hh in enumerate(heights):
            c.rect(i*bw, h*0.14, bw-2, h*hh, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E8DFC2"))
        for i, hh in enumerate(heights):
            for j in range(int(hh*7)):
                if (i + j) % 3 == 0:
                    c.rect(i*bw + 4, h*(0.18 + j*0.07), 2.5, 3, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(w*0.505, h*0.72, 2, h*0.20, stroke=0, fill=1)
        c.circle(w*0.512, h*0.92, 3.5, stroke=0, fill=1)

    def _draw_capitol(self, c, w, h):
        self._sky(c, w, h, "#CBDCEA", 0.16, "#BFC9B4")
        c.setFillColor(colors.HexColor("#FAF7F1"))
        c.rect(w*0.08, h*0.16, w*0.84, h*0.22, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E0D9C2"))
        for i in range(8):
            c.rect(w*(0.14 + i*0.095), h*0.38, w*0.030, h*0.18, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#FAF7F1"))
        p = c.beginPath()
        p.moveTo(w*0.12, h*0.56); p.lineTo(w*0.88, h*0.56)
        p.lineTo(w*0.50, h*0.66); p.close(); c.drawPath(p, stroke=0, fill=1)
        c.circle(w*0.50, h*0.74, h*0.11, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E0D9C2"))
        c.rect(w*0.40, h*0.66, w*0.20, h*0.06, stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(w*0.495, h*0.84, w*0.01, h*0.10, stroke=0, fill=1)
        c.rect(w*0.505, h*0.88, w*0.05, h*0.05, stroke=0, fill=1)

    def _draw_robot(self, c, w, h):
        self._sky(c, w, h, "#DDE5EF", 0.20, "#C9C2AC")
        c.setFillColor(colors.HexColor("#0B3D5C"))
        c.rect(w*0.40, h*0.34, w*0.20, h*0.28, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#1A1A1A"))
        c.rect(w*0.42, h*0.64, w*0.16, h*0.16, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E8A33C"))
        c.circle(w*0.46, h*0.72, 2, stroke=0, fill=1)
        c.circle(w*0.54, h*0.72, 2, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#0B3D5C")); c.setLineWidth(3)
        c.line(w*0.40, h*0.58, w*0.26, h*0.46)
        c.line(w*0.60, h*0.58, w*0.74, h*0.64)
        c.line(w*0.45, h*0.34, w*0.34, h*0.20)
        c.line(w*0.55, h*0.34, w*0.66, h*0.20)
        c.setStrokeColor(colors.HexColor("#8A99A6")); c.setLineWidth(0.8)
        c.line(w*0.50, h*0.80, w*0.50, h*0.88)
        c.setFillColor(ACCENT); c.circle(w*0.50, h*0.89, 2, stroke=0, fill=1)
        c.setStrokeColor(MUTED); c.setLineWidth(0.6)
        for y in (0.42, 0.52, 0.62):
            c.line(w*0.04, h*y, w*0.18, h*y)

    def _draw_farm(self, c, w, h):
        self._sky(c, w, h, "#CFE0EC", 0.44, "#D4B96A")
        self._sun(c, w, h, 0.82, 0.80, 9, "#E8A33C")
        c.setStrokeColor(colors.HexColor("#A98F45")); c.setLineWidth(0.8)
        for i in range(14):
            x = w*(0.03 + i*0.072)
            c.line(x, 0, x, h*(0.16 + (i % 3)*0.05))
        c.setFillColor(colors.HexColor("#A6192E"))
        c.rect(w*0.08, h*0.44, w*0.20, h*0.16, stroke=0, fill=1)
        p = c.beginPath()
        p.moveTo(w*0.06, h*0.60); p.lineTo(w*0.18, h*0.72)
        p.lineTo(w*0.30, h*0.60); p.close(); c.drawPath(p, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#3B2A22"))
        c.rect(w*0.15, h*0.44, w*0.06, h*0.10, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#6B5A2A")); c.setLineWidth(1)
        c.line(0, h*0.44, w, h*0.44)

    def _draw_globe(self, c, w, h):
        c.setFillColor(colors.HexColor("#0B1626"))
        c.rect(0, 0, w, h, stroke=0, fill=1)
        r = min(w, h)*0.36
        c.setFillColor(colors.HexColor("#1E5A7A"))
        c.circle(w*0.50, h*0.50, r, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#4E8C5A"))
        c.circle(w*0.44, h*0.58, r*0.34, stroke=0, fill=1)
        c.circle(w*0.60, h*0.44, r*0.26, stroke=0, fill=1)
        c.circle(w*0.38, h*0.36, r*0.20, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#8FBCD4")); c.setLineWidth(0.5)
        c.circle(w*0.50, h*0.50, r, stroke=1, fill=0)
        for f in (0.35, 0.68):
            c.line(w*0.50 - r, h*0.50 - r + 2*r*f, w*0.50 + r, h*0.50 - r + 2*r*f)
        c.setStrokeColor(ACCENT); c.setLineWidth(0.9); c.setDash(3, 2)
        c.circle(w*0.50, h*0.50, r*1.28, stroke=1, fill=0); c.setDash()

    def _draw_court(self, c, w, h):
        self._sky(c, w, h, "#DDE5EF", 0.18, "#C4BCA6")
        c.setFillColor(colors.HexColor("#F2EDE0"))
        c.rect(w*0.10, h*0.18, w*0.80, h*0.20, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#E0D9C2"))
        for i in range(6):
            c.rect(w*(0.16 + i*0.125), h*0.38, w*0.035, h*0.24, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#F2EDE0"))
        p = c.beginPath()
        p.moveTo(w*0.12, h*0.62); p.lineTo(w*0.88, h*0.62)
        p.lineTo(w*0.50, h*0.76); p.close(); c.drawPath(p, stroke=0, fill=1)
        c.setStrokeColor(ACCENT); c.setLineWidth(1.2)
        c.line(w*0.50, h*0.80, w*0.50, h*0.94)
        c.line(w*0.38, h*0.92, w*0.62, h*0.92)
        c.line(w*0.38, h*0.92, w*0.38, h*0.86)
        c.line(w*0.62, h*0.92, w*0.62, h*0.86)
        c.setFillColor(ACCENT)
        c.circle(w*0.38, h*0.85, 2.6, stroke=0, fill=1)
        c.circle(w*0.62, h*0.85, 2.6, stroke=0, fill=1)

    def _draw_protest(self, c, w, h):
        self._sky(c, w, h, "#D3DCE4", 0.30, "#B9B3A2")
        c.setFillColor(colors.HexColor("#2A3744"))
        for i in range(13):
            x = w*(0.03 + i*0.076)
            c.circle(x, h*0.32 + (i % 3), 3.4, stroke=0, fill=1)
            c.rect(x-3, h*0.08, 6, h*0.22, stroke=0, fill=1)
        c.setStrokeColor(colors.HexColor("#4A4A4A")); c.setLineWidth(1)
        for x, ph in ((0.20, 0.62), (0.52, 0.70), (0.80, 0.58)):
            c.line(w*x, h*0.34, w*x, h*ph)
        c.setFillColor(colors.HexColor("#FAF7F1"))
        c.rect(w*0.13, h*0.62, w*0.16, h*0.14, stroke=0, fill=1)
        c.rect(w*0.45, h*0.70, w*0.16, h*0.14, stroke=0, fill=1)
        c.rect(w*0.73, h*0.58, w*0.16, h*0.14, stroke=0, fill=1)
        c.setStrokeColor(MUTED); c.setLineWidth(0.5)
        for bx, by in ((0.13, 0.62), (0.45, 0.70), (0.73, 0.58)):
            for j in range(3):
                c.line(w*(bx+0.02), h*(by+0.035+j*0.035),
                       w*(bx+0.14), h*(by+0.035+j*0.035))

    def _draw_hospital(self, c, w, h):
        self._sky(c, w, h, "#D8E6EF", 0.16, "#C2CBC4")
        c.setFillColor(colors.HexColor("#FAF7F1"))
        c.rect(w*0.14, h*0.16, w*0.72, h*0.58, stroke=0, fill=1)
        c.setFillColor(colors.HexColor("#BBD7E8"))
        for i in range(4):
            for j in range(3):
                c.rect(w*(0.20 + i*0.16), h*(0.24 + j*0.16), w*0.10, h*0.10,
                       stroke=0, fill=1)
        c.setFillColor(ACCENT)
        c.rect(w*0.46, h*0.78, w*0.08, h*0.16, stroke=0, fill=1)
        c.rect(w*0.42, h*0.82, w*0.16, h*0.08, stroke=0, fill=1)
        c.setStrokeColor(INK); c.setLineWidth(0.6)
        c.line(w*0.14, h*0.74, w*0.86, h*0.74)

    _MOTIFS = {
        "ship": _draw_ship,
        "strait": _draw_strait,
        "border": _draw_border,
        "fire": _draw_fire,
        "flood": _draw_flood,
        "grid": _draw_grid,
        "ballot": _draw_ballot,
        "airdefense": _draw_airdefense,
        "rocket": _draw_rocket,
        "cricket": _draw_cricket,
        "skyline": _draw_skyline,
        "capitol": _draw_capitol,
        "robot": _draw_robot,
        "farm": _draw_farm,
        "globe": _draw_globe,
        "court": _draw_court,
        "protest": _draw_protest,
        "hospital": _draw_hospital,
        "talks": _draw_talks,
    }

    @classmethod
    def known_motifs(cls):
        return sorted(cls._MOTIFS.keys())

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        motif = (self.spec or {}).get("motif", "")
        drawer = self._MOTIFS.get(motif)
        if drawer is None:
            raise ValueError(
                f"unknown illustration motif {motif!r}; "
                f"known: {', '.join(self.known_motifs())}")
        drawer(self, c, w, h)
        c.setStrokeColor(INK); c.setLineWidth(0.5)
        c.rect(0, 0, w, h, stroke=1, fill=0)
        title = (self.spec or {}).get("title", "")
        sub   = (self.spec or {}).get("subtitle", "Editorial illustration")
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.58))
        c.rect(0, 0, w, 14, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 6.5)
        c.drawString(5, 5, title[:44])
        c.setFont("Helvetica-Oblique", 5.5); c.setFillColor(colors.HexColor("#DEDEDE"))
        c.drawRightString(w-5, 5, sub[:26])
