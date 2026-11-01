"""Version 2: two sourced news stories, real geography and a small newsroom strip.

Historical posters retain their original renderer. Every new word is typeset, and
all news, map and comic evidence is tied to the accompanying checked issue.
"""
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from . import checks, edition, print_maps, visuals
from .graphics import INK, ACCENT, MUTED, PAPER, LIGHTBG, StyledMap

M, W, GAP = 28, 556, 10
BODY = ParagraphStyle('news-poster-body', fontName='Times-Roman', fontSize=11.5, leading=14)
HEAD = ParagraphStyle('news-poster-head', fontName='Times-Bold', fontSize=25, leading=27)
DECK = ParagraphStyle('news-poster-deck', parent=BODY, fontSize=12, leading=14)
SMALL = ParagraphStyle('news-poster-small', fontName='Helvetica', fontSize=8, leading=10)
DIALOGUE = ParagraphStyle('news-poster-dialogue', fontName='Helvetica', fontSize=10, leading=12)
ART_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'poster'


def skeleton(ed, date):
    return {
        'version': 2, 'edition': ed['id'], 'date': date, 'question': '',
        'stories': [dict(block='', kicker='', headline='', deck='', body=['', '', ''],
                         evidence=['', '', ''], why='', sources=[],
                         visual={'type': 'steps', 'title': '', 'caption': '', 'source_url': '',
                                 'items': [dict(label='', evidence='') for _ in range(3)]}) for _ in range(2)],
        'find_it': {'story_block': '', 'map': {'title': 'WHERE IN THE WORLD?', 'countries': []},
                    'text': '', 'evidence': ''},
        'comic': {'story_block': '', 'panels': [dict(speaker=s, text='', evidence='')
                                               for s in ('Leo', 'Tara', 'Leo')]},
        'sources': [],
    }


def _urls(obj):
    values = obj.get('sources')
    if not isinstance(values, list):
        return []
    return [s.get('url', '') if isinstance(s, dict) else s for s in values
            if isinstance(s, (str, dict))]


def _text(story):
    return ' '.join([story.get('deck', '')] + story.get('body', []))


def asset(spec):
    """Only reviewed local art; never fetch a remote image during a build."""
    path = (ART_DIR / spec['file']).resolve()
    if not path.is_relative_to(ART_DIR.resolve()) or path.suffix.lower() not in ('.png', '.jpg'):
        raise ValueError('art must be a PNG/JPG inside assets/poster')
    if hashlib.sha256(path.read_bytes()).hexdigest() != spec.get('sha256'):
        raise ValueError('art changed; review the image and update its sha256')
    return path


def check(ed, spec, path):
    r = checks.Report()
    def fail(msg): r.err(msg)
    def need(value, where, limit=500):
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            fail(f'{where}: needs 1-{limit} characters')
    if spec.get('edition') != ed['id']:
        fail('poster.edition must match its edition')
    try:
        day = dt.date.fromisoformat(spec.get('date', ''))
    except (ValueError, TypeError):
        fail('poster.date must be an ISO date'); return r
    if Path(path).name != f'{day}.json':
        fail('file name must be the poster date, YYYY-MM-DD.json')
    issue_path = Path(ed['_dir']) / 'issues' / str(day.year) / f'{day}.json'
    try:
        issue = json.loads(issue_path.read_text())
    except (OSError, ValueError):
        fail('news poster needs its accompanying issue on the same date'); return r
    need(spec.get('question'), 'question', 110)
    stories = spec.get('stories')
    if not isinstance(stories, list) or len(stories) != 2 or not all(isinstance(s, dict) for s in stories):
        fail('stories: exactly two news story objects'); return r
    blocks = issue.get('blocks', {})
    chosen, used_urls = {}, set()
    for i, s in enumerate(stories):
        loc = f'stories[{i}]'
        block = s.get('block')
        original = blocks.get(block, {}) if isinstance(block, str) else {}
        if not original.get('headline') or not isinstance(original.get('body'), list):
            fail(f'{loc}.block must name a story in this issue'); continue
        if block in chosen:
            fail('stories must cover two different issue blocks')
        chosen[block] = original
        for key, limit in [('kicker', 55), ('headline', 90), ('deck', 145), ('why', 165)]:
            need(s.get(key), f'{loc}.{key}', limit)
        body = s.get('body')
        evidence = s.get('evidence')
        if not isinstance(body, list) or not 2 <= len(body) <= 3 or not all(isinstance(p, str) and p.strip() for p in body):
            fail(f'{loc}.body: 2-3 short news paragraphs')
        if not isinstance(evidence, list) or not body or len(evidence) != len(body):
            fail(f'{loc}.evidence: one exact issue excerpt per paragraph')
        else:
            for e in evidence:
                if not isinstance(e, str) or len(e) < 12 or e not in _text(original):
                    fail(f'{loc}.evidence must be exact excerpts from its issue story')
        urls = _urls(s)
        if not urls or any(u not in _urls(original) for u in urls):
            fail(f'{loc}.sources must cite the selected issue story')
        used_urls.update(u for u in urls if isinstance(u, str))
        if s.get('visual') and isinstance(body, list) and all(isinstance(p, str) for p in body):
            for err in visuals.validate(s): fail(f'{loc}.{err}')
        elif i == 1:
            fail(f'{loc}.visual: the second story needs an explanatory diagram')
        if s.get('art'):
            try:
                asset(s['art'])
                need(s['art'].get('caption'), f'{loc}.art.caption', 100)
            except (OSError, ValueError, TypeError, KeyError) as e:
                fail(f'{loc}.art: {e}')
    loc = spec.get('find_it')
    if not isinstance(loc, dict) or not isinstance(loc.get('map'), dict):
        fail('find_it and find_it.map must be objects'); return r
    original = chosen.get(loc.get('story_block'), {}) if isinstance(loc.get('story_block'), str) else {}
    mp = loc['map']
    countries = mp.get('countries')
    if not original or loc.get('story_block') != stories[0].get('block'):
        fail('find_it.story_block must be the first selected story')
    if not isinstance(countries, list) or not 1 <= len(countries) <= 3 or any(not isinstance(n, str) for n in countries):
        fail('find_it.map.countries: 1-3 named countries')
    elif len(print_maps.places(mp)[0]) != len(countries):
        fail('find_it.map: every country must resolve to real geography')
    else:
        for name in countries:
            if name.casefold() not in _text(original).casefold():
                fail('find_it.map: countries must be named in the selected issue story')
    need(loc.get('text'), 'find_it.text', 110)
    if not isinstance(loc.get('evidence'), str) or len(loc['evidence']) < 12 or loc['evidence'] not in _text(original):
        fail('find_it.evidence must be an exact issue excerpt')
    comic = spec.get('comic')
    if not isinstance(comic, dict):
        fail('comic must be an object'); return r
    original = chosen.get(comic.get('story_block'), {}) if isinstance(comic.get('story_block'), str) else {}
    if not original: fail('comic.story_block must be one of the two selected stories')
    panels = comic.get('panels')
    if not isinstance(panels, list) or len(panels) != 3 or not all(isinstance(p, dict) for p in panels):
        fail('comic.panels: exactly three dialogue panels')
    else:
        for i, p in enumerate(panels):
            if p.get('speaker') != ('Leo', 'Tara', 'Leo')[i]:
                fail(f'comic.panels[{i}].speaker must match the newsroom artwork')
            need(p.get('text'), f'comic.panels[{i}].text', 95)
            if not isinstance(p.get('evidence'), str) or len(p['evidence']) < 12 or p['evidence'] not in _text(original):
                fail(f'comic.panels[{i}].evidence must be an exact issue excerpt')
    if set(_urls(spec)) != used_urls:
        fail('sources must include exactly the two stories\' source URLs')
    for where, text in checks.walk(spec, 'poster'):
        if any(not checks._printable(ch) or ch == '…' for ch in text):
            fail(f'{where}: the PDF fonts cannot print one or more characters')
    if not r.errors:
        problems = []
        try: draw(Canvas(io.BytesIO(), pagesize=letter), ed, spec, problems)
        except Exception as e: fail(f'could not draw the news poster: {e}')
        r.errors.extend(problems)
    return r


def para(c, text, style, x, top, width, room, where, problems):
    p = Paragraph(escape(text), style)
    _, height = p.wrap(width, 10000)
    if height > room + .5:
        problems.append(f'{where} is OVER by {height-room:.0f} pt; shorten the text')
    p.drawOn(c, x, top-height)
    return height


def label(c, text, x, y, size=9):
    c.setFillColor(ACCENT); c.setFont('Helvetica-Bold', size); c.drawString(x, y, text)


def _story(c, story, top, height, lead, locate, problems):
    bottom = top-height
    label(c, story['kicker'].upper(), M, top-10)
    h = para(c, story['headline'], HEAD, M, top-20, W, 56, 'story headline', problems)
    y = top-20-h-5
    h = para(c, story['deck'], DECK, M, y, W, 29, 'story deck', problems)
    y -= h+11
    body_w = 233 if lead else 255
    floor = bottom+36
    ty = y
    for j, p in enumerate(story['body']):
        used = para(c, p, BODY, M, ty, body_w, ty-floor, f"{story['block']} paragraph {j+1}", problems)
        ty -= used+6
    vx, vw = M+body_w+GAP, W-body_w-GAP
    vh = y-floor
    if lead:
        # A reviewed editorial illustration may accompany the REAL locator map.
        art = story.get('art')
        mw = 145 if art else vw
        if art:
            aw = vw-mw-8
            image = ImageReader(str(asset(art)))
            iw, ih = image.getSize()
            scale = min(aw/iw, (vh-28)/ih)
            c.drawImage(image, vx+(aw-iw*scale)/2, y-ih*scale, width=iw*scale, height=ih*scale)
            para(c, art['caption'], SMALL, vx, y-ih*scale-4, aw, 28, 'art caption', problems)
        mx = vx+vw-mw
        mp = StyledMap(locate['map'], mw, max(50, vh-28))
        mp.canv = c; c.saveState(); c.translate(mx, y-(vh-28)); mp.draw(); c.restoreState()
        para(c, locate['text'], SMALL, mx, floor+23, mw, 23, 'map caption', problems)
    else:
        v = story['visual']
        graphic = visuals.StoryVisual(v, vw, min(vh-25, vw*150/340))
        graphic.canv = c
        c.saveState(); c.translate(vx, y-graphic.height); graphic.draw(); c.restoreState()
        para(c, v['caption'], SMALL, vx, y-graphic.height-5, vw, max(18, vh-graphic.height-5), 'visual caption', problems)
    c.setFillColor(LIGHTBG); c.rect(M, bottom+4, W, 27, stroke=0, fill=1)
    label(c, 'WHY IT MATTERS', M+7, bottom+14, 8)
    para(c, story['why'], SMALL, M+104, bottom+24, W-112, 22, 'why it matters', problems)
    c.setStrokeColor(INK); c.setLineWidth(.7); c.line(M, bottom-3, M+W, bottom-3)


def draw(c, ed, spec, problems, credit=None):
    c.setFillColor(PAPER); c.rect(0, 0, 612, 792, fill=1, stroke=0)
    c.setFillColor(INK); c.setFont('Times-Bold', 38)
    c.drawCentredString(306, 744, 'NEWS PEBBLES')
    day = dt.date.fromisoformat(spec['date'])
    c.setFont('Helvetica-Bold', 8.5)
    c.drawCentredString(306, 727, f"THE LITTLE EXPLORER  •  WEEKEND NEWS POSTER  •  AGES {ed['reader']['age']}")
    c.setFont('Helvetica', 8); c.drawCentredString(306, 713, f'{day:%A, %d %B %Y}  |  Two stories. A world to discover.')
    c.setStrokeColor(INK); c.setLineWidth(1); c.line(M, 706, M+W, 706)
    _story(c, spec['stories'][0], 698, 280, True, spec['find_it'], problems)
    _story(c, spec['stories'][1], 405, 239, False, spec['find_it'], problems)
    label(c, 'THE PEBBLE REPORTERS', M, 150, 8.5)
    c.drawImage(ImageReader(str(ART_DIR/'pebble-reporters.jpg')), M, 43, width=W, height=100)
    pw = W/3
    for i, p in enumerate(spec['comic']['panels']):
        para(c, p['speaker'] + ': ' + p['text'], DIALOGUE, M+i*pw+8, 137, pw-16, 41,
             f'comic panel {i+1}', problems)
    c.setFillColor(MUTED); c.setFont('Helvetica', 6.5)
    c.drawString(M, 33, 'Tara & Leo are fictional reporters. Illustrations explain the news; they are not photographs.')
    c.setFont('Helvetica', 6.5)
    c.drawCentredString(306, 20, 'News Pebbles • ' + spec['date'] + ' • Sources on the paper\'s web page • ' + (credit or 'AI-assisted; checked against sources'))
