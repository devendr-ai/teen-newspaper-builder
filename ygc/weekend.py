"""Curated, issue-matched weekend supplements. No email or reader changes.

Art is reviewed with its evidence before it enters the repository. Missing art
means news only; we never recycle a previous issue's comic.
"""
import datetime as dt
import hashlib
import io
import json
import random
import re
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from . import edition

EDITION = 'little-explorers'


def load(ed, date, issue):
    if ed['id'] != EDITION or dt.date.fromisoformat(date).weekday() < 5:
        return None
    folder = Path(edition.ROOT) / 'editions' / EDITION / 'weekend'
    path = folder / f'{date}.json'
    if not path.exists():
        return None
    spec = json.loads(path.read_text())
    if spec.get('date') != date or spec.get('edition') != EDITION:
        raise ValueError('Weekend supplement must match its edition and date')
    story = issue['blocks'].get(spec.get('story_block'), {})
    body = story.get('body', '')
    if isinstance(body, list):
        body = '\n'.join(body)
    if spec.get('headline') != story.get('headline'):
        raise ValueError('Comic headline no longer matches its source story')
    urls = {s.get('url') for s in story.get('sources', [])}
    if not spec.get('source_url') or spec['source_url'] not in urls:
        raise ValueError('Comic needs the story source')
    panels = spec.get('panels', [])
    if len(panels) != 6 or any(not p.get('caption') or not p.get('evidence') or p['evidence'] not in body for p in panels):
        raise ValueError('Every comic panel needs exact evidence in this issue')
    words = spec.get('words', [])
    if len(words) != 3 or len(set(words)) != 3 or any(not re.fullmatch('[A-Z]{3,6}', w) or not re.search(r'\b' + re.escape(w) + r'\b', body, re.I) for w in words):
        raise ValueError('Use three short words from the source story')
    asset = (folder / spec['image']).resolve()
    if not asset.is_relative_to(folder.resolve()) or asset.suffix.lower() not in ('.jpg', '.png'):
        raise ValueError('Comic image must stay inside the weekend folder')
    if hashlib.sha256(asset.read_bytes()).hexdigest() != spec.get('image_sha256'):
        raise ValueError('Comic art changed; review it again')
    with Image.open(asset) as image:
        if image.width < 1200 or not 1.3 < image.width / image.height < 1.8:
            raise ValueError('Comic needs a high resolution landscape six-panel layout')
    for key in ('jumble_hint', 'drawing_prompt', 'discussion'):
        if not isinstance(spec.get(key), str) or not 1 <= len(spec[key]) <= 58:
            raise ValueError('Keep puzzle instructions short and reviewed')
    spec['_image'] = asset
    return spec


def word_grid(words, seed):
    """Six rows, left-to-right only: friendly to early readers, no ambiguity."""
    rng = random.Random(seed)
    for attempt in range(100):
        grid = [[rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ') for _ in range(6)] for _ in range(6)]
        rows = rng.sample(range(6), len(words))
        for word, row in zip(words, rows):
            start = rng.randrange(7 - len(word))
            grid[row][start:start + len(word)] = word
        lines = [''.join(row) for row in grid]
        if all(sum(line.count(w) for line in lines) == 1 for w in words):
            return lines
    raise ValueError('Could not make an unambiguous word hunt')


def build(ed, date, issue, news_pdf, output):
    spec = load(ed, date, issue)
    if spec is None:
        return False
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.setFillColorRGB(.976, .965, .933); c.rect(0, 0, 612, 792, fill=1, stroke=0)
    c.setFillColorRGB(.12, .17, .20)
    c.setFont('Times-Bold', 24); c.drawCentredString(306, 753, 'THE LITTLE EXPLORER')
    c.setFont('Helvetica-Bold', 11); c.drawCentredString(306, 732, 'THE WEEKEND EXPLORER  |  NEWS + PUZZLES')
    c.setLineWidth(.7); c.line(28, 720, 584, 720)
    # Art carries the complete story; captions remain inside the six panels.
    with Image.open(spec['_image']) as image:
        height = min(386, 556 * image.height / image.width)
    c.drawImage(ImageReader(str(spec['_image'])), 28, 710-height, width=556, height=height)
    c.setFont('Helvetica-Oblique', 8)
    c.drawString(28, 710-height-12, "See this issue's source notes for the facts behind the comic.")
    y = min(294, 710-height-35)
    c.line(28, y+14, 584, y+14)
    c.setFont('Times-Bold', 18); c.drawString(28, y-5, 'Find the story words')
    c.setFont('Helvetica', 10); c.drawString(28, y-23, 'Look across, from left to right. Circle each word.')
    grid = word_grid(spec['words'], date)
    cell, gx, gy = 23, 40, y-48
    c.setStrokeColorRGB(.65, .65, .61)
    for row, letters in enumerate(grid):
        for col, letter in enumerate(letters):
            x, top = gx + col*cell, gy-row*cell
            c.rect(x, top-cell, cell, cell, fill=0)
            c.setFont('Helvetica-Bold', 13); c.drawCentredString(x+cell/2, top-16, letter)
    c.setFont('Helvetica-Bold', 11); c.drawString(28, gy-6*cell-20, '  /  '.join(spec['words']))
    c.setFillColorRGB(.12, .17, .20)
    c.setFont('Times-Bold', 18); c.drawString(285, y-5, 'Unjumble it!')
    c.setFont('Helvetica', 11); c.drawString(285, y-25, spec['jumble_hint'])
    word = spec['words'][0]
    jumble = word[2:] + word[:2]
    c.setFont('Helvetica-Bold', 19); c.drawString(285, y-52, ' '.join(jumble))
    c.setFont('Helvetica', 15); c.drawString(285, y-78, '_  ' * len(word))
    c.setFont('Times-Bold', 18); c.drawString(285, y-110, 'Draw your own explorer')
    c.setFont('Helvetica', 10); c.drawString(285, y-128, spec['drawing_prompt'])
    c.rect(285, 72, 299, max(35, y-211), fill=0)
    c.setFont('Helvetica-Oblique', 8); c.drawString(28, 51, 'Talk together: ' + spec['discussion'])
    c.saveState(); c.translate(584, 40); c.rotate(180)
    c.setFont('Helvetica', 7); c.drawString(0, 0, 'Unjumble answer: ' + word + '. Word hunt: all words run left to right.'); c.restoreState()
    c.setFont('Helvetica', 7); c.drawCentredString(306, 23, f'{ed["name"]} | {date} | Weekend extra | newspebbles.com')
    c.showPage(); c.save(); buf.seek(0)
    writer = PdfWriter(); writer.append(str(news_pdf)); writer.append(PdfReader(buf))
    writer.add_metadata({'/Title': f'{ed["name"]} - {date} - News + Puzzles', '/Author': 'News Pebbles'})
    with open(output, 'wb') as stream:
        writer.write(stream)
    return True
