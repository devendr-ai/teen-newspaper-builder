"""How the site looks when a link to it is shared, and how search engines find it.

After the site is built, `build(out, cfg)`:
- draws the pictures a shared link shows (1200 x 630, Open Graph): one for the whole site,
  one for each paper (its latest front page) and one for each Read & Play paper (its top
  story and that story's map);
- gives every page its preview tags (title, description, picture) and its canonical address;
- writes sitemap.xml, robots.txt and the "page not found" page (404.html).

The pictures are drawn with Pillow (installed with ReportLab) in the site's own fonts,
which are kept in assets/fonts (SIL Open Font License).
"""
import datetime as dt
import functools
import html
import os
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import brand, world

E = html.escape
W, H = 1200, 630
FONTS = os.path.join(brand.ASSETS, "fonts")
OWL = os.path.join(brand.ASSETS, "owl-share.png")
INK, MUTED, CORAL, TEAL, LINE = "#1E2A32", "#5B6870", "#E2584D", "#00727E", "#DDD5C6"
PAPER, PLAYBG, CARDLINE = "#F4F1EA", "#FFF8EE", "#E7DCCB"
STONES = ("#8E9AA0", "#D9C7A3", "#9DB48A")


# ------------------------------------------------------------------ drawing helpers
@functools.lru_cache(maxsize=None)
def disp(size, weight=800):
    """Bricolage Grotesque, the site's display face (a variable font: optical size, weight, width)."""
    f = ImageFont.truetype(os.path.join(FONTS, "BricolageGrotesque-Variable.ttf"), size)
    f.set_variation_by_axes([96, weight, 100])
    return f


@functools.lru_cache(maxsize=None)
def text(size, bold=False):
    """Atkinson Hyperlegible, the site's text face."""
    return ImageFont.truetype(os.path.join(FONTS, f"AtkinsonHyperlegible-{'Bold' if bold else 'Regular'}.ttf"), size)


@functools.lru_cache(maxsize=None)
def owl(size):
    return Image.open(OWL).convert("RGBA").resize((size, size), Image.LANCZOS)


def wrap(d, s, font, width, lines=99):
    """Words into lines no wider than `width`; the last line ends in … if it had to be cut."""
    out, cur = [], ""
    for w in s.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    if len(out) > lines:
        out = out[:lines]
        while out[-1] and d.textlength(out[-1] + "…", font=font) > width:
            out[-1] = out[-1].rsplit(" ", 1)[0] if " " in out[-1] else out[-1][:-1]
        out[-1] = out[-1].rstrip(",;:·-– ") + "…"
    return out


def fit(d, s, sizes, width, lines, weight=800):
    """The biggest display size at which `s` fits in `lines` lines."""
    for z in sizes:
        f = disp(z, weight)
        got = wrap(d, s, f, width)
        if len(got) <= lines:
            return f, got
    f = disp(sizes[-1], weight)
    return f, wrap(d, s, f, width, lines)


def pill(d, x, y, label, font, fill, ink, border=None, pad=(22, 10), width=3):
    """A rounded label; returns its right edge."""
    w = d.textlength(label, font=font)
    a, b = font.getmetrics()
    h = a + b + 2 * pad[1]
    d.rounded_rectangle((x, y, x + w + 2 * pad[0], y + h), radius=h // 2, fill=fill, outline=border, width=width if border else 0)
    d.text((x + pad[0], y + pad[1]), label, font=font, fill=ink)
    return x + w + 2 * pad[0]


def wordmark(d, x, y, size, stones=True):
    """News Pebbles, the way the site's header writes it; returns its width."""
    f = disp(size)
    d.text((x, y), "News ", font=f, fill=INK)
    x2 = x + d.textlength("News ", font=f)
    d.text((x2, y), "Pebbles", font=f, fill=CORAL)
    if stones:
        top = y + f.getbbox("News")[3] + 0.16 * size
        sx = x
        for c, w in zip(STONES, (0.62, 0.46, 0.54)):
            d.ellipse((sx, top, sx + w * size, top + 0.3 * size), fill=c, outline=INK, width=max(2, round(0.07 * size)))
            sx += (w + 0.12) * size
    return x2 + d.textlength("Pebbles", font=f) - x


def save(img, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = img.convert("RGB")
    if path.endswith(".jpg"):
        img.save(path, quality=86, optimize=True, progressive=True)
    else:
        img.save(path, optimize=True)


# ------------------------------------------------------------------ the map on a story's picture
@functools.lru_cache(maxsize=1)
def shapes():
    """[(name, [rings of (x, y) in map units], (x0, y0, x1, y1))] from the site's world map."""
    out = []
    for c in world.countries():
        rings = []
        for part in c["d"].split("M")[1:]:
            nums = [float(n) for n in re.findall(r"-?\d*\.?\d+", part)]
            if len(nums) < 2:
                continue
            x, y = nums[0], nums[1]
            pts = [(x, y)]
            for i in range(2, len(nums) - 1, 2):
                x += nums[i]
                y += nums[i + 1]
                pts.append((x, y))
            rings.append(pts)
        if rings:
            xs = [p[0] for r in rings for p in r]
            ys = [p[1] for r in rings for p in r]
            out.append((c["name"], rings, (min(xs), min(ys), max(xs), max(ys))))
    return out


def draw_map(where, size):
    """A map zoomed on a story's place: its countries in coral and a pin. None if there's no place."""
    if not where or where.get("lat") is None or where.get("lon") is None:
        return None
    w, h = size
    k = 2                                                   # drawn at twice the size, then smoothed
    names = {world.country_name(c) for c in where.get("countries") or []} - {None}
    px, py = world.project(float(where["lon"]), float(where["lat"]))
    x0, y0, x1, y1 = px, py, px, py
    for c in world.countries():
        if c["name"] in names:
            bx = c["box"]
            x0, y0, x1, y1 = min(x0, bx[0]), min(y0, bx[1]), max(x1, bx[2]), max(y1, bx[3])
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    vw = max(150, (x1 - x0) * 1.8, (y1 - y0) * 1.8 * w / h)
    vw = min(vw, world.W)
    vh = vw * h / w
    left, top = cx - vw / 2, cy - vh / 2
    sc = w * k / vw
    img = Image.new("RGB", (w * k, h * k), "#CFE8F3")
    d = ImageDraw.Draw(img)
    for name, rings, (bx0, by0, bx1, by1) in shapes():
        if bx1 < left or bx0 > left + vw or by1 < top or by0 > top + vh:
            continue
        fill = CORAL if name in names else "#EADFC4"
        for r in rings:
            pts = [((x - left) * sc, (y - top) * sc) for x, y in r]
            if len(pts) > 2:
                d.polygon(pts, fill=fill, outline="#FFFFFF", width=k)
    qx, qy = (px - left) * sc, (py - top) * sc
    r = 15 * k
    d.ellipse((qx - r - 5 * k, qy - r - 5 * k, qx + r + 5 * k, qy + r + 5 * k), fill="#FFFFFF")
    d.ellipse((qx - r, qy - r, qx + r, qy + r), fill=CORAL)
    return img.resize((w, h), Image.LANCZOS)


def rounded(img, radius, border=None, width=3):
    """The image with rounded corners (and a border), on a transparent background."""
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), m)
    if border:
        ImageDraw.Draw(out).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius=radius, outline=border, width=width)
    return out


def headphones(d, x, y, s, ink):
    d.arc((x, y, x + s, y + s), 180, 360, fill=ink, width=max(3, s // 7))
    for bx in (x - 1, x + s - s // 3 + 1):
        d.rounded_rectangle((bx, y + s // 2, bx + s // 3, y + s), radius=s // 8, fill=ink)


def gamepad(d, x, y, s, ink):
    d.rounded_rectangle((x, y + s // 5, x + s * 1.3, y + s), radius=s // 3, fill=ink)
    c, t = (x + s * 0.38, y + s * 0.6), max(2, s // 9)
    d.rectangle((c[0] - s * 0.18, c[1] - t, c[0] + s * 0.18, c[1] + t), fill="#FFFFFF")
    d.rectangle((c[0] - t, c[1] - s * 0.18, c[0] + t, c[1] + s * 0.18), fill="#FFFFFF")
    for dx in (0.88, 1.06):
        d.ellipse((x + s * dx - t * 1.4, y + s * 0.6 - t * 1.4, x + s * dx + t * 1.4, y + s * 0.6 + t * 1.4), fill="#FFFFFF")


# ------------------------------------------------------------------ the three pictures
def site_card(cfg, path):
    """A: the whole site."""
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    img.paste(owl(280), (70, 150), owl(280))
    x, y = 400, 92
    wordmark(d, x, y, 96)
    y += 96 + 0.16 * 96 + 0.3 * 96 + 40
    d.text((x, y), cfg["tagline"], font=disp(46), fill=INK)
    y += 70
    for line in wrap(d, "Free newspapers to print, read and talk about together, written for your child's age.", text(29), 750, 2):
        d.text((x, y), line, font=text(29), fill=MUTED)
        y += 39
    y += 20
    for age in ("6–8", "9–11", "12–14", "15+"):
        x = pill(d, x, y, age, disp(28), "#FFFFFF", INK, border=INK) + 14
    url = cfg.get("domain") or "newspebbles.com"
    d.text((W - 56 - d.textlength(url, font=text(26, True)), H - 44 - 30), url, font=text(26, True), fill=TEAL)
    for i, c in enumerate(STONES):
        d.rectangle((i * W // 3, H - 16, (i + 1) * W // 3, H), fill=c)
    save(img, path)


def paper_card(cfg, name, meta, latest, cover, path):
    """B: a paper's page: its latest front page, its name, who it's for, and free to print."""
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    if cover and os.path.exists(cover):
        c = Image.open(cover).convert("RGB")
        cw = 380
        c = c.resize((cw, round(c.size[1] * cw / c.size[0])), Image.LANCZOS)
        c = c.crop((0, 0, cw, min(c.size[1], 500)))
        framed = Image.new("RGB", (c.size[0] + 4, c.size[1] + 4), "#B9C3C1")
        framed.paste(c, (2, 2))
        shadow = Image.new("RGBA", (framed.size[0] + 80, framed.size[1] + 80), (0, 0, 0, 0))
        ImageDraw.Draw(shadow).rectangle((40, 52, 40 + framed.size[0], 52 + framed.size[1]), fill=(30, 42, 50, 70))
        shadow = shadow.filter(ImageFilter.GaussianBlur(16))
        tilt = framed.convert("RGBA").rotate(3, expand=True, resample=Image.BICUBIC)
        shadow = shadow.rotate(3, expand=True, resample=Image.BICUBIC)
        img.paste(shadow, (52, 30), shadow)
        img.paste(tilt, (82, 58), tilt)
    else:
        img.paste(owl(300), (120, 160), owl(300))
    x = 560
    img.paste(owl(66), (x, 80), owl(66))
    wordmark(d, x + 80, 96, 34, stones=False)
    f, lines = fit(d, name, (76, 66, 58), W - x - 50, 2)
    y = 186
    for line in lines:
        d.text((x, y), line, font=f, fill=INK)
        y += round(f.size * 1.04)
    y += 18
    pill(d, x, y, meta, text(30, True), "#FFFFFF", INK, border=LINE)
    y += 78
    if latest:
        d.text((x, y), f"Latest: {latest:%A} {latest.day} {latest:%B}", font=text(28), fill=MUTED)
    label, f2 = "Free to print", disp(32)
    bw = d.textlength(label, font=f2) + 30 + 60
    by = H - 56 - 64
    d.rounded_rectangle((x, by, x + bw, by + 64), radius=32, fill=INK)
    d.text((x + 30, by + 13), label, font=f2, fill="#FFFFFF")
    ax, ay = x + 30 + d.textlength(label, font=f2) + 16, by + 18          # a down arrow, drawn
    d.line((ax + 11, ay, ax + 11, ay + 24), fill="#FFFFFF", width=5)
    d.polygon(((ax, ay + 16), (ax + 22, ay + 16), (ax + 11, ay + 29)), fill="#FFFFFF")
    save(img, path)


def issue_card(cfg, name, band, date, headline, deck, where, path):
    """C: a Read & Play paper: its top story, that story's map, and what's inside."""
    img = Image.new("RGB", (W, H), PLAYBG)
    d = ImageDraw.Draw(img)
    x = 70
    kick = "READ & PLAY" + (f" · {band.upper()}" if band else "")
    pill(d, x, 64, kick, text(25, True), CORAL, "#FFFFFF", pad=(20, 8))
    m = draw_map(where, (500, 380))
    tw = 540 if m else W - 2 * x
    f, lines = fit(d, headline, (78, 68, 60, 52), tw, 3)
    y = 140
    for line in lines:
        d.text((x, y), line, font=f, fill=INK)
        y += round(f.size * 1.04)
    y += 14
    for line in wrap(d, deck, text(32), tw, 2 if len(lines) < 3 else 1):
        d.text((x, y), line, font=text(32), fill=MUTED)
        y += 42
    if m:
        img.paste(rounded(m, 26, CARDLINE), (650, 84), rounded(m, 26, CARDLINE))
    else:
        img.paste(owl(300), (830, 120), owl(300))
    img.paste(owl(58), (x, H - 52 - 58), owl(58))
    d.text((x + 72, H - 52 - 44), f"{name} · {date.day} {date:%b}", font=text(28, True), fill=INK)
    r = W - 50
    for label, icon in (("Games", gamepad), ("Listen", headphones)):
        f3 = text(26, True)
        w = d.textlength(label, font=f3) + 40 + 34
        d.rounded_rectangle((r - w, H - 56 - 50, r, H - 56), radius=25, fill="#FFFFFF", outline=CARDLINE, width=3)
        icon(d, r - w + 18, H - 56 - 37, 24, INK)
        d.text((r - w + 18 + 36, H - 56 - 41), label, font=f3, fill=INK)
        r -= w + 12
    save(img, path)


# ------------------------------------------------------------------ the site
def url(cfg, rel):
    """A page's full address; index.html pages as their folder."""
    base = (cfg.get("base_url") or "").rstrip("/") + "/"
    rel = re.sub(r"(^|/)index\.html$", r"\1", rel)
    return base + rel


def tags(cfg, rel, title, desc, image, alt):
    base = (cfg.get("base_url") or "").rstrip("/") + "/"
    out = []
    if cfg.get("base_url") and rel != "404.html":
        out.append(f'<link rel="canonical" href="{E(url(cfg, rel))}"><meta property="og:url" content="{E(url(cfg, rel))}">')
    out.append(f'<meta property="og:type" content="website"><meta property="og:site_name" content="{E(cfg["title"])}">'
               f'<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}">'
               f'<meta name="twitter:card" content="summary_large_image">')
    if cfg.get("base_url") and image:
        out.append(f'<meta property="og:image" content="{E(base + image)}"><meta property="og:image:width" content="{W}">'
                   f'<meta property="og:image:height" content="{H}"><meta property="og:image:alt" content="{E(alt)}">')
    return "".join(out)


def strip(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(str(s or "")))).strip()


def lead(ed, issue):
    """(headline, deck, place) of an issue's top story."""
    from . import edition
    blocks = issue.get("blocks") or {}
    where = [w for w in ((issue.get("play") or {}).get("where") or []) if isinstance(w, dict)]
    for b in edition.story_blocks(ed):
        s = blocks.get(b)
        if isinstance(s, dict) and s.get("headline"):
            place = next((w for w in where if w.get("story") == b), None)
            return strip(s["headline"]), strip(s.get("deck")), place
    return None, None, None


def not_found(cfg):
    """The page GitHub Pages shows for an address that doesn't exist. Its links start from the
    site's root, since it is served at whatever address was asked for."""
    from . import site
    root = re.sub(r"^https?://[^/]+", "", (cfg.get("base_url") or "/").rstrip("/") + "/") or "/"
    body = f"""<section class="lost"><div class="lostowl">{brand.inline("logo")}<span aria-hidden="true">?</span></div>
<h2>We can't find that page</h2>
<p>The link may be mistyped, or it may be an older paper: each paper keeps its last {int(cfg.get("keep_issues", 30))} issues online.</p>
<p class="lostgo"><a class="btn" href="{root}index.html">See today's papers</a><a class="btn ghost" href="{root}play/index.html">Open Read &amp; Play</a></p>
{f'<p class="meta">Expected something here? <a href="{root}feedback.html">Tell us</a></p>' if cfg.get("feedback_url") else ""}
<script>window.npCount&&npCount("404"+location.pathname,"Page not found",true)</script></section>"""
    head = ("<style>.lost{max-width:34rem;margin:28px auto 10px;text-align:center}.lost h2{font-size:1.8rem;margin:14px 0 8px}"
            ".lost p{color:var(--muted);line-height:1.5}.lostowl{position:relative;display:inline-block}.lostowl .logo{width:140px;height:140px}"
            ".lostowl span{position:absolute;right:-22px;top:-8px;font-family:var(--display);font-weight:800;font-size:3.2rem;color:var(--coral)}"
            ".lostgo{display:flex;flex-direction:column;gap:10px;align-items:center;margin:20px 0}.lostgo .btn{min-width:240px;text-align:center}</style>")
    return site.page(cfg, f"Page not found · {cfg['title']}", body, root=root, head_extra=head, here="")


def build(out, cfg, log=print):
    """Pictures, preview tags, sitemap.xml, robots.txt and 404.html for the built site in `out`."""
    from . import edition, site
    pics = os.path.join(out, "share")
    site_card(cfg, os.path.join(pics, "site.png"))
    special = {"index.html": (f"{cfg['title']}: {cfg['tagline']}", cfg["description"], "share/site.png",
                              f"{cfg['title']}: {cfg['tagline']}")}
    lastmod = {}
    for eid in edition.list_editions():
        ed = edition.load(eid)
        issues = site.issues_of(ed)
        if not os.path.exists(os.path.join(out, "e", eid, "index.html")):
            continue
        s = ed.get("site") or {}
        aud, n = site.audience(ed), len(ed["pages"])
        latest = dt.date.fromisoformat(issues[0][0]) if issues else None
        meta = f"{aud} · {site.frequency(ed)} · {n} page{'s' if n != 1 else ''}"
        paper_card(cfg, ed["name"], meta, latest, os.path.join(out, "e", eid, "cover.png"), os.path.join(pics, f"{eid}.jpg"))
        blurb = strip(s.get("blurb") or ed["reader"]["profile"])
        special[f"e/{eid}/index.html"] = (f"{ed['name']} · {aud}", f"{blurb} Free to print.", f"share/{eid}.jpg",
                                          f"The front page of {ed['name']}")
        if latest:
            lastmod[f"e/{eid}/index.html"] = latest.isoformat()
        for date, p in issues:
            page = os.path.join(out, "play", eid, f"{date}.html")
            if not os.path.exists(page):
                continue
            lastmod[f"play/{eid}/{date}.html"] = date
            if 'class="issue"' not in open(page, encoding="utf-8").read():      # a paper that has left Read & Play
                special[f"play/{eid}/{date}.html"] = special[f"e/{eid}/index.html"]
                continue
            import json
            issue = json.load(open(p, encoding="utf-8"))
            head, deck, where = lead(ed, issue)
            if not head:
                continue
            d = dt.date.fromisoformat(date)
            band = aud if aud.startswith("Ages") else ""
            issue_card(cfg, ed["name"], band, d, head, deck or "", where, os.path.join(pics, f"{eid}-{date}.jpg"))
            special[f"play/{eid}/{date}.html"] = (
                f"{head} · {ed['name']}",
                f"Read it, hear it read aloud, then play today's games. {('For ' + aud.lower() + ', ') if band else ''}{d.day} {d:%B}.",
                f"share/{eid}-{date}.jpg", f"{head}, from {ed['name']} on Read & Play")
    open(os.path.join(out, "404.html"), "w", encoding="utf-8").write(not_found(cfg))

    pages = []
    for dp, _, fs in os.walk(out):
        for f in fs:
            if f.endswith(".html"):
                pages.append(os.path.relpath(os.path.join(dp, f), out).replace(os.sep, "/"))
    for rel in sorted(pages):
        p = os.path.join(out, rel)
        doc = open(p, encoding="utf-8").read()
        if "og:title" in doc or "</head>" not in doc:
            continue
        if rel in special:
            title, desc, image, alt = special[rel]
        else:
            m = re.search(r"<title>(.*?)</title>", doc, re.S)
            dm = re.search(r'<meta name="description" content="([^"]*)"', doc)
            title = html.unescape(m.group(1)).strip() if m else cfg["title"]
            desc = html.unescape(dm.group(1)) if dm else cfg["description"]
            image, alt = "share/site.png", f"{cfg['title']}: {cfg['tagline']}"
        doc = doc.replace("</head>", tags(cfg, rel, title, desc, image, alt) + "</head>", 1)
        open(p, "w", encoding="utf-8").write(doc)

    if cfg.get("base_url"):
        listed = [r for r in sorted(pages) if r != "404.html" and 'class="stub"' not in open(os.path.join(out, r), encoding="utf-8").read()]
        rows = "".join(f"<url><loc>{E(url(cfg, r))}</loc>{f'<lastmod>{lastmod[r]}</lastmod>' if r in lastmod else ''}</url>"
                       for r in listed)
        open(os.path.join(out, "sitemap.xml"), "w", encoding="utf-8").write(
            '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + rows + "</urlset>\n")
        open(os.path.join(out, "robots.txt"), "w", encoding="utf-8").write(
            f"User-agent: *\nAllow: /\n\nSitemap: {(cfg['base_url'].rstrip('/'))}/sitemap.xml\n")
    log(f"  share: {len(os.listdir(pics))} pictures, preview tags on {len(pages)} pages")
