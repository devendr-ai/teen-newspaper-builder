"""Evidence-linked explanatory visuals, shared by print and Read & Play.

Editors choose the explanation; renderers never infer numbers or causal links from prose.
"""
import html
import math
import re
import textwrap

from reportlab.lib.colors import HexColor
from reportlab.platypus import Flowable
from reportlab.pdfbase.pdfmetrics import stringWidth

PROMPT = '''**Choose a visual that explains the story.** A story may supply `visual` instead of its
fixed map/illustration/chart slots (omit those slots when replacing them). Elections: use a
majority-seat threshold diagram, clearly distinguished from results. Economics: use a bar
comparison when the story supplies comparable numbers with the same unit. Science: use a
short explanation of the observed mechanism or discovery process. Geography stories keep
real locator maps. Never force a chart when data are missing; use a sourced explanation or
locator instead. Decorative globes/skylines must not stand in for an explanation.
`visual` schema: {"type":"seats|bars|steps", "title":"short title", "caption":"what it shows",
"source_url":"one of this story's source URLs"}. All evidence fields must be exact excerpts
from the story body/deck, which must itself be grounded in the research sources.
- seats: add `total`, `threshold` (integer seats), `total_evidence`, `threshold_evidence`.
  This is ONLY a majority threshold, never party results, exit polls or a prediction.
- bars: add `unit` (one shared unit, <=28 characters), `items` (2-4 objects each with
  `label` <=22 characters, non-negative numeric `value`, and `evidence` containing that number).
  Compare like with like, distinguish estimates from confirmed numbers in the caption.
  The chart always starts at zero. Never mix currencies, units or probabilities with counts.
- steps: add `items` (2-4 objects with `label` <=72 characters and `evidence`). The order
  must be supported by the article; no invented step, causal claim or guaranteed outcome.
Titles <=44 characters, captions <=220. Cite the graphic's numbers and claims in the story
before drawing them. Do not invent statistics to fill a visual. The fact-checker checks visuals too.
'''


def validate(story):
    v = story.get('visual')
    errors = []
    def fail(message): errors.append('visual: ' + message)
    if not isinstance(v, dict):
        return ['visual: must be an object']
    for key, limit in (('title', 44), ('caption', 220)):
        if not isinstance(v.get(key), str) or not 1 <= len(v[key]) <= limit:
            fail(f'{key} needs 1-{limit} characters')
    if isinstance(v.get('title'), str) and stringWidth(v['title'], 'Helvetica-Bold', 11) > 316:
        fail('title is too wide; shorten it')
    urls = [s.get('url') if isinstance(s, dict) else s for s in story.get('sources', [])]
    if not v.get('source_url') or v['source_url'] not in urls:
        fail('source_url must be one of this story\'s sources')
    text = ' '.join([story.get('deck', '')] + (story.get('body') or []))
    def evidence(quote, number=None):
        if not isinstance(quote, str) or len(quote) < 12 or quote not in text:
            fail('evidence must be an exact excerpt from the story (at least 12 characters)')
        elif number is not None:
            nums = [float(n.replace(',', '')) for n in re.findall(r'(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])', quote)]
            if number not in nums:
                fail('numeric value must appear in its evidence excerpt')
    def numeric(n): return type(n) in (int, float) and math.isfinite(n) and n >= 0
    kind = v.get('type')
    if kind == 'seats':
        total, threshold = v.get('total'), v.get('threshold')
        if type(total) is not int or not 2 <= total <= 2000 or type(threshold) is not int or threshold != total // 2 + 1:
            fail('seats needs integer total 2-2000 and a simple majority threshold (total // 2 + 1)')
        evidence(v.get('total_evidence'), total)
        evidence(v.get('threshold_evidence'), threshold)
    elif kind in ('bars', 'steps'):
        items = v.get('items')
        if not isinstance(items, list) or not 2 <= len(items) <= 4 or not all(isinstance(i, dict) for i in items):
            fail('needs 2-4 item objects')
            return errors
        for item in items:
            limit = 22 if kind == 'bars' else 72
            if not isinstance(item.get('label'), str) or not 1 <= len(item['label']) <= limit:
                fail(f'item label needs 1-{limit} characters')
            if kind == 'bars' and not numeric(item.get('value')):
                fail('bar values must be finite non-negative numbers')
            elif kind == 'bars' and stringWidth(str(item['value']), 'Helvetica-Bold', 11) > 288 / len(items) - 6:
                fail('bar value is too wide; use an appropriately sourced display unit')
            if isinstance(item.get('label'), str):
                lines = textwrap.wrap(item['label'], 13 if kind == 'bars' else 50)
                max_width = 288 / len(items) - 6 if kind == 'bars' else 276
                if len(lines) > 2 or any(stringWidth(line, 'Helvetica', 9 if kind == 'bars' else 10) > max_width for line in lines):
                    fail('item label is too wide; shorten it')
            evidence(item.get('evidence'), item.get('value') if kind == 'bars' else None)
        if kind == 'bars':
            if not isinstance(v.get('unit'), str) or not 1 <= len(v['unit']) <= 28:
                fail('bars needs one shared unit (1-28 characters)')
            if not any(numeric(i.get('value')) and i['value'] > 0 for i in items):
                fail('bars needs at least one positive value')
    else:
        fail('type must be seats, bars or steps')
    return errors


INK, TEAL, PAPER, LIGHT, MUTED = '#1F2D33', '#137B89', '#FAF7F1', '#E5DFCF', '#60696C'


def commands(v):
    """A 340x150 diagram in top-down coordinates; both outputs use this layout."""
    out = [('rect', 0, 0, 340, 150, PAPER)]
    def text(x, y, label, size=10, color=INK, anchor='start', bold=False):
        out.append(('text', x, y, str(label), size, color, anchor, bold))
    text(12, 18, v['title'], 11, bold=True)
    if v['type'] == 'seats':
        total, threshold = v['total'], v['threshold']
        text(12, 34, f'{threshold} needed for a majority of {total} seats', 10)
        if total <= 200:
            cols = 20
            rows = math.ceil(total / cols)
            pitch = min(10, 66 / rows)
            for i in range(total):
                out.append(('circle', 20 + (i % cols) * 15.7, 48 + (i // cols) * pitch, min(3.1, pitch*.35), TEAL if i < threshold else LIGHT))
        else:
            out.append(('rect', 12, 55, 316, 38, LIGHT))
            out.append(('rect', 12, 55, 316*threshold/total, 38, TEAL))
            text(12, 109, f'{threshold} of {total} seats', 11)
        text(12, 127, 'Teal marks the seats needed for a majority.', 9, TEAL)
        text(12, 142, 'Threshold diagram - not election results.', 9, MUTED)
    elif v['type'] == 'bars':
        items = v['items']; top = max(i['value'] for i in items)
        text(12, 34, v['unit'] + ' | zero baseline', 9, MUTED)
        out.append(('line', 28, 115, 328, 115, MUTED))
        text(20, 118, '0', 8, MUTED, 'end')
        pitch = 288 / len(items)
        for i, item in enumerate(items):
            x = 36 + pitch*i + pitch/2; height = 62*item['value']/top
            out.append(('rect', x-pitch*.28, 115-height, pitch*.56, height, TEAL))
            text(x, 109-height, str(item['value']), 11, anchor='middle', bold=True)
            for j, line in enumerate(textwrap.wrap(item['label'], 13)):
                text(x, 129+j*10, line, 9, anchor='middle')
    else:
        items = v['items']; pitch = 112/len(items)
        for i, item in enumerate(items):
            y = 27+i*pitch
            out.append(('rect', 12, y, 316, pitch-5, LIGHT))
            text(23, y+(pitch-5)/2+3, str(i+1), 10, TEAL, bold=True)
            lines = textwrap.wrap(item['label'], 50)
            for j, line in enumerate(lines):
                text(43, y+(pitch-5)/2+3+(j-(len(lines)-1)/2)*11, line, 10)
            if i < len(items)-1:
                # Reading order, not an inferred causal arrow.
                out.append(('line', 29, y+pitch-5, 29, y+pitch, MUTED))
    return out


class StoryVisual(Flowable):
    def __init__(self, spec, width, height):
        super().__init__(); self.spec, self.width, self.height = spec, width, height

    def draw(self):
        c = self.canv; scale = min(self.width/340, self.height/150)
        c.saveState(); c.translate((self.width-340*scale)/2, (self.height-150*scale)/2); c.scale(scale, scale)
        for item in commands(self.spec):
            kind, *p = item
            if kind == 'rect':
                x,y,w,h,color=p; c.setFillColor(HexColor(color)); c.rect(x,150-y-h,w,h,stroke=0,fill=1)
            elif kind == 'circle':
                x,y,r,color=p; c.setFillColor(HexColor(color)); c.circle(x,150-y,r,stroke=0,fill=1)
            elif kind == 'line':
                x,y,x2,y2,color=p; c.setStrokeColor(HexColor(color)); c.setLineWidth(.6); c.line(x,150-y,x2,150-y2)
            else:
                x,y,label,size,color,anchor,bold=p
                c.setFillColor(HexColor(color)); c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
                {'middle': c.drawCentredString, 'end': c.drawRightString}.get(anchor,c.drawString)(x,150-y,label)
        c.restoreState()


def summary(v):
    if v['type'] == 'seats':
        detail = f"{v['threshold']} seats needed for a majority of {v['total']}. Threshold, not results."
    elif v['type'] == 'bars':
        detail = '; '.join(f"{i['label']}: {i['value']} {v['unit']}" for i in v['items']) + '. Zero baseline.'
    else:
        detail = '; '.join(f"{n+1}. {i['label']}" for n,i in enumerate(v['items']))
    return v['title'] + '. ' + detail


def svg(v):
    E = lambda value: html.escape(str(value), quote=True)
    parts = [f'<svg class="scene explanatory" viewBox="0 0 340 150" role="img" aria-label="{E(summary(v))}" font-family="Atkinson Hyperlegible, sans-serif"><title>{E(v["title"])}</title><desc>{E(v["caption"])}</desc>']
    for kind, *p in commands(v):
        if kind == 'rect':
            x,y,w,h,color=p; parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{color}"/>')
        elif kind == 'circle':
            x,y,r,color=p; parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>')
        elif kind == 'line':
            x,y,x2,y2,color=p; parts.append(f'<path d="M{x},{y} L{x2},{y2}" fill="none" stroke="{color}"/>')
        else:
            x,y,label,size,color,anchor,bold=p; parts.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{700 if bold else 400}">{E(label)}</text>')
    return ''.join(parts)+'</svg>'


def height(graphics, size):
    return 1.7*72 if 'map' in graphics else (1.25 if size == 'lead' else 1.4)*72 if 'illustration' in graphics else 1.8*72
