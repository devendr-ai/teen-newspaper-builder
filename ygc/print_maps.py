"""Print-sized locator maps from the same Natural Earth geometry as Read & Play.

Labels identify places, never define an invented coastline, border or route. Old issues' country
labels are resolved for compatibility. Unresolved locations produce an honest text card, not a map.
"""
import functools
import re

from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

from . import world


def places(spec):
    names = spec.get('countries')
    if not isinstance(names, list):
        names = [spec.get('label_top', ''), spec.get('label_bottom', '')]
    countries = list(dict.fromkeys(n for v in names if (n := world.country_name(v))))
    if not countries:
        countries, _ = world.find(spec.get('title', ''))
    known = {n.casefold(): n for n, *_ in world.CITIES + world.WATERS}
    known.update({alias.casefold(): name for alias, name in {**world.CITY_ALIASES, **world.WATER_ALIASES}.items()})
    wanted = str(spec.get('place') or spec.get('title') or '').strip()
    place = known.get(re.sub(r'^the ', '', wanted, flags=re.I).casefold())
    return countries, place


@functools.lru_cache(maxsize=1)
def geometry():
    """Decode the existing M/relative-l/z SVG paths, preserving their rings and geography."""
    out = []
    for country in world.countries():
        rings, ring, x, y, command = [], [], 0, 0, None
        tokens = iter(re.findall(r'[Mlz]|-?(?:\d+(?:\.\d*)?|\.\d+)', country['d']))
        for token in tokens:
            if token == 'z':
                if ring:
                    rings.append(tuple(ring))
                ring, command = [], None
                continue
            if token in ('M', 'l'):
                command, token = token, next(tokens)
            a, b = float(token), float(next(tokens))
            x, y = (a, b) if command == 'M' else (x + a, y + b)
            ring.append((x, y))
        out.append((country, [(r, (min(p[0] for p in r), min(p[1] for p in r),
                                  max(p[0] for p in r), max(p[1] for p in r))) for r in rings]))
    return out


def viewport(names, place, width, height):
    boxes = [world.by_name()[name]['box'] for name in names]
    if place:
        lat, lon = world.city(place)
        x, y = world.project(lon, lat)
        boxes.append((x - 4, y - 4, x + 4, y + 4))
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw, bh = max(12, (x1 - x0) * 1.25), max(9, (y1 - y0) * 1.30)
    # Fit without stretching geography. Extra width shows neighbouring countries for context.
    scale = min(width / bw, height / bh)
    bw, bh = width / scale, height / scale
    return cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2


def _intersects(a, b):
    return a[0] <= b[2] and a[2] >= b[0] and a[1] <= b[3] and a[3] >= b[1]


def draw(canvas, spec, width, height):
    c, w, h = canvas, width, height
    names, place = places(spec)
    c.setFillColor(colors.HexColor('#FAF7F1')); c.rect(0, 0, w, h, stroke=0, fill=1)
    c.setFillColor(colors.HexColor('#1A1A1A')); c.setFont('Helvetica-Bold', 7)
    title = spec.get('title') or 'WHERE IN THE WORLD?'
    while stringWidth(title, 'Helvetica-Bold', 7) > w - 12 and len(title) > 2:
        title = title[:-2] + '\u2026'
    c.drawString(6, h - 11, title)
    if not names and not place:
        c.setFont('Helvetica', 8); c.drawCentredString(w / 2, h / 2, 'Location not specified')
        c.setFont('Helvetica-Oblique', 6); c.drawCentredString(w / 2, h / 2 - 12, 'No geographic map is shown.')
    else:
        frame = (1, 14, w - 2, h - 31)
        fx, fy, fw, fh = frame
        box = viewport(names, place, fw, fh)
        scale = fw / (box[2] - box[0])
        def xy(point):
            return fx + (point[0] - box[0]) * scale, fy + fh - (point[1] - box[1]) * scale
        c.setFillColor(colors.HexColor('#DCECF0')); c.rect(*frame, stroke=0, fill=1)
        c.saveState()
        clip = c.beginPath(); clip.rect(*frame); c.clipPath(clip, stroke=0, fill=0)
        c.translate(fx - box[0] * scale, fy + fh + box[1] * scale); c.scale(scale, -scale)
        for country, rings in geometry():
            visible = [r for r, bounds in rings if _intersects(bounds, box)]
            if not visible:
                continue
            p = c.beginPath()
            for ring in visible:
                p.moveTo(*ring[0])
                for point in ring[1:]:
                    p.lineTo(*point)
                p.close()
            c.setFillColor(colors.HexColor('#137B89' if country['name'] in names else '#E5DFCF'))
            c.setStrokeColor(colors.HexColor('#FFFFFF')); c.setLineWidth(.35 / scale)
            c.drawPath(p, stroke=1, fill=1, fillMode=0)
        c.restoreState()
        occupied = []
        candidates = sorted(world.countries(), key=lambda cc: (cc['name'] not in names,
                            -(cc['box'][2]-cc['box'][0]) * (cc['box'][3]-cc['box'][1])))
        for country in candidates:
            lon, lat = country['label']; x, y = xy(world.project(lon, lat))
            if not (fx + 5 <= x <= fx + fw - 5 and fy + 5 <= y <= fy + fh - 5):
                continue
            target = country['name'] in names
            label = world.DISPLAY.get(country['name'], country['name'])
            font, size = ('Helvetica-Bold', 6.5) if target else ('Helvetica', 5.5)
            tw = stringWidth(label, font, size)
            for dx, dy in ((0, 0), (0, 9), (0, -9), (tw/2 + 5, 0), (-tw/2 - 5, 0)):
                lx, ly = x + dx, y + dy
                bounds = (lx - tw/2 - 2, ly - 2, lx + tw/2 + 2, ly + size + 2)
                if bounds[0] < fx+2 or bounds[2] > fx+fw-2 or bounds[1] < fy+1 or bounds[3] > fy+fh-1:
                    continue
                if any(_intersects(bounds, previous) for previous in occupied):
                    continue
                if dx or dy:
                    c.setStrokeColor(colors.HexColor('#687777')); c.setLineWidth(.35); c.line(x, y, lx, ly)
                c.setFillColor(colors.Color(1, 1, 1, alpha=.90)); c.rect(bounds[0], bounds[1], bounds[2]-bounds[0], bounds[3]-bounds[1], stroke=0, fill=1)
                c.setFillColor(colors.HexColor('#123F48' if target else '#4D5658')); c.setFont(font, size)
                c.drawCentredString(lx, ly, label); occupied.append(bounds)
                break
            if len(occupied) >= 8:
                break
        if place:
            lat, lon = world.city(place); x, y = xy(world.project(lon, lat))
            c.setFillColor(colors.HexColor('#A6192E')); c.circle(x, y, 2, stroke=0, fill=1)
        c.setFillColor(colors.HexColor('#6B6B6B')); c.setFont('Helvetica', 5.5)
        c.drawString(6, 5, 'Locator map | Natural Earth')
        if place and stringWidth(place, 'Helvetica', 5.5) + stringWidth('Locator map | Natural Earth', 'Helvetica', 5.5) < w - 18:
            c.drawRightString(w - 6, 5, place)
    c.setStrokeColor(colors.HexColor('#77746D')); c.setLineWidth(.5); c.rect(0, 0, w, h, stroke=1, fill=0)
