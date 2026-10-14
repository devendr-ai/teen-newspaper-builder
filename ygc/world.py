"""Where in the world? The country map behind Read & Play's maps, and the places a story names.

The shapes are Natural Earth's India point-of-view countries (see data/world/README.md), drawn in the
Equal Earth projection so no country looks too big or too small. The website gets them once, as
play/world.js; each story only says which countries to colour and where to put the pin.
"""
import functools
import json
import math
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "data", "world", "countries.topo.json")

# Equal Earth (Šavrič, Patterson and Jenny, 2018). play.js has the same numbers.
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2
W = 1000                                     # map width, in SVG units


def _ee(lon, lat):
    t = math.asin(M * math.sin(math.radians(lat)))
    t2 = t * t
    t6 = t2 * t2 * t2
    x = math.radians(lon) * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2)))
    y = t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x, y


S = W / (2 * _ee(180, 0)[0])                 # scale: the whole world is W wide
H = 2 * _ee(0, 90)[1] * S
TOP, BOTTOM = H / 2 - _ee(0, 84)[1] * S, H / 2 - _ee(0, -57)[1] * S   # no Antarctica


def project(lon, lat):
    x, y = _ee(lon, lat)
    return W / 2 + x * S, H / 2 - y * S


# ------------------------------------------------------------------ shapes
@functools.lru_cache(maxsize=1)
def countries():
    """[{name, a2, label (lon, lat), d (SVG path), box (x0, y0, x1, y1) of its main land}]"""
    topo = json.load(open(SOURCE, encoding="utf-8"))
    (sx, sy), (tx, ty) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append(project(x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(ids):
        pts = []
        for i in ids:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts += a[1:] if pts else a
        return pts

    out = []
    geoms = next(iter(topo["objects"].values()))["geometries"]
    for g in geoms:
        p = g["properties"]
        polys = [] if g.get("type") not in ("Polygon", "MultiPolygon") else [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        x, y = project(p["LABEL_X"], p["LABEL_Y"])
        d, main, best = [], (x, y, x, y), -1      # too small to draw (Malta, the Maldives): a pin only
        for poly in polys:
            rings = [ring(r) for r in poly]
            for r in rings:
                d.append(_path(r))
            xs, ys = [p[0] for p in rings[0]], [p[1] for p in rings[0]]
            area = abs(sum(xs[i] * ys[i - 1] - xs[i - 1] * ys[i] for i in range(len(xs)))) / 2
            if area > best:
                best, main = area, (min(xs), min(ys), max(xs), max(ys))
        out.append({"name": p["NAME"], "a2": p.get("ISO_A2") or "", "label": (p["LABEL_X"], p["LABEL_Y"]),
                    "d": "".join(d), "box": tuple(round(v, 1) for v in main)})
    return out


def _path(pts):
    """One closed ring as a short SVG path: absolute start, then relative steps of 0.1 unit."""
    q = [(round(x * 10), round(y * 10)) for x, y in pts]
    out, last = [f"M{q[0][0] / 10:g} {q[0][1] / 10:g}"], q[0]
    steps = []
    for p in q[1:]:
        if p == last:
            continue
        steps.append(f"{(p[0] - last[0]) / 10:g} {(p[1] - last[1]) / 10:g}".replace(" -", "-"))
        last = p
    if steps:
        out.append("l" + " ".join(steps).replace(" -", "-"))
    return "".join(out) + "z"


@functools.lru_cache(maxsize=1)
def by_name():
    return {c["name"]: c for c in countries()}


def world_js():
    """play/world.js: every country, plus the numbers the page needs to put pins on the same map."""
    data = {"w": W, "h": round(H, 2), "s": S, "top": round(TOP, 1), "bottom": round(BOTTOM, 1),
            "c": [{"n": c["name"], "d": c["d"], "b": c["box"]} for c in countries() if c["d"]],
            "cities": [[n, cc, lat, lon] for n, cc, lat, lon in CITIES]}
    return "window.WORLD=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"


# ------------------------------------------------------------------ places a story names
# Other ways the news names a country, and what people from there are called.
ALIASES = {
    "United States": ["United States of America", "USA", "U.S.A.", "U.S.", "US", "America", "American", "Americans"],
    "United Kingdom": ["UK", "U.K.", "Britain", "Great Britain", "British", "England", "English", "Scotland",
                       "Scottish", "Wales", "Welsh", "Northern Ireland"],
    "Dem. Rep. Korea": ["North Korea", "North Korean"],
    "Republic of Korea": ["South Korea", "South Korean"],
    "Democratic Republic of the Congo": ["DR Congo", "DRC", "Congo"],
    "Republic of the Congo": ["Congo-Brazzaville"],
    "United Arab Emirates": ["UAE", "U.A.E.", "Emirates", "Emirati"],
    "Czechia": ["Czech Republic", "Czech"],
    "Côte d'Ivoire": ["Ivory Coast"],
    "Bosnia and Herz.": ["Bosnia", "Bosnia and Herzegovina"],
    "Central African Rep.": ["Central African Republic"],
    "S. Sudan": ["South Sudan"],
    "Dominican Rep.": ["Dominican Republic"],
    "Eq. Guinea": ["Equatorial Guinea"],
    "Palestine": ["Gaza", "West Bank", "Palestinian", "Palestinians"],
    "Netherlands": ["Holland", "Dutch"],
    "Myanmar": ["Burma"],
    "eSwatini": ["Eswatini", "Swaziland"],
    "Turkey": ["Türkiye", "Turkish"],
    "India": ["Indian", "Indians", "Jammu and Kashmir", "Kashmir", "Ladakh"],
    "China": ["Chinese"], "Japan": ["Japanese"], "Russia": ["Russian", "Russians"],
    "Ukraine": ["Ukrainian", "Ukrainians"], "Israel": ["Israeli", "Israelis"], "Iran": ["Iranian", "Iranians"],
    "Pakistan": ["Pakistani"], "France": ["French"], "Germany": ["German"], "Italy": ["Italian"],
    "Spain": ["Spanish"], "Brazil": ["Brazilian"], "Australia": ["Australian"], "Canada": ["Canadian"],
    "Mexico": ["Mexican"], "Egypt": ["Egyptian"], "Saudi Arabia": ["Saudi"], "Afghanistan": ["Afghan"],
    "Nepal": ["Nepali", "Nepalese"], "Bangladesh": ["Bangladeshi"], "Sri Lanka": ["Sri Lankan"],
    "Kenya": ["Kenyan"], "Nigeria": ["Nigerian"], "South Africa": ["South African"], "Lebanon": ["Lebanese"],
    "Syria": ["Syrian"], "Iraq": ["Iraqi"], "Greece": ["Greek"], "Sweden": ["Swedish"], "Norway": ["Norwegian"],
    "Poland": ["Polish"], "Indonesia": ["Indonesian"], "Thailand": ["Thai"], "Vietnam": ["Vietnamese"],
    "Philippines": ["Filipino"], "Malaysia": ["Malaysian"], "Argentina": ["Argentine", "Argentinian"],
    "Chile": ["Chilean"], "Peru": ["Peruvian"], "Colombia": ["Colombian"], "Venezuela": ["Venezuelan"],
    "Cuba": ["Cuban"], "Ethiopia": ["Ethiopian"], "Sudan": ["Sudanese"], "Yemen": ["Yemeni"],
    "Qatar": ["Qatari"], "Oman": ["Omani"], "Bhutan": ["Bhutanese"], "Maldives": ["Maldivian"],
    "Taiwan": ["Taiwanese"], "New Zealand": ["New Zealander"], "Ireland": ["Irish"], "Portugal": ["Portuguese"],
    "Switzerland": ["Swiss"], "Austria": ["Austrian"], "Belgium": ["Belgian"], "Denmark": ["Danish"],
    "Finland": ["Finnish"], "Hungary": ["Hungarian"], "Romania": ["Romanian"], "Mongolia": ["Mongolian"],
}
# How a child would write the map's shortened names.
DISPLAY = {"Dem. Rep. Korea": "North Korea", "Republic of Korea": "South Korea", "Bosnia and Herz.": "Bosnia and Herzegovina",
           "Central African Rep.": "Central African Republic", "S. Sudan": "South Sudan", "Dominican Rep.": "Dominican Republic",
           "Eq. Guinea": "Equatorial Guinea", "eSwatini": "Eswatini", "Democratic Republic of the Congo": "DR Congo",
           "Republic of the Congo": "Congo", "Solomon Is.": "Solomon Islands", "Falkland Is.": "Falkland Islands",
           "Fr. Polynesia": "French Polynesia", "Antigua and Barb.": "Antigua and Barbuda", "Marshall Is.": "Marshall Islands"}
# Names that are also everyday words or people's names: only an explicit `where` uses them.
AMBIGUOUS = {"Jersey", "Guernsey", "Chad", "Jordan", "Georgia", "Niger", "Guinea", "Isle of Man", "Dominica",
             "Monaco", "Akrotiri", "Dhekelia", "Saint Helena", "Aruba", "Montserrat", "Vatican"}
# Written exactly so, never in lower case ("us" is a word).
EXACT = {"US", "USA", "U.S.", "U.S.A.", "UK", "U.K.", "UAE", "U.A.E.", "DRC", "Turkey", "Turkish", "Chile", "Arctic",
         "Pacific", "Atlantic"}

# Cities a story may name, and that a reader can choose as home: (name, country, lat, lon).
CITIES = [
    ("Delhi", "India", 28.61, 77.21), ("Mumbai", "India", 19.08, 72.88), ("Bengaluru", "India", 12.97, 77.59),
    ("Chennai", "India", 13.08, 80.27), ("Kolkata", "India", 22.57, 88.36), ("Hyderabad", "India", 17.39, 78.49),
    ("Pune", "India", 18.52, 73.86), ("Ahmedabad", "India", 23.02, 72.57), ("Jaipur", "India", 26.91, 75.79),
    ("Lucknow", "India", 26.85, 80.95), ("Chandigarh", "India", 30.73, 76.78), ("Kochi", "India", 9.93, 76.27),
    ("Thiruvananthapuram", "India", 8.52, 76.94), ("Bhopal", "India", 23.26, 77.41), ("Patna", "India", 25.59, 85.14),
    ("Guwahati", "India", 26.14, 91.74), ("Srinagar", "India", 34.08, 74.80), ("Indore", "India", 22.72, 75.86),
    ("Nagpur", "India", 21.15, 79.09), ("Bhubaneswar", "India", 20.30, 85.82), ("Visakhapatnam", "India", 17.69, 83.22),
    ("Goa", "India", 15.50, 73.83), ("Dehradun", "India", 30.32, 78.03), ("Ranchi", "India", 23.34, 85.31),
    ("Kathmandu", "Nepal", 27.72, 85.32), ("Dhaka", "Bangladesh", 23.81, 90.41), ("Colombo", "Sri Lanka", 6.93, 79.86),
    ("Thimphu", "Bhutan", 27.47, 89.64), ("Malé", "Maldives", 4.18, 73.51), ("Karachi", "Pakistan", 24.86, 67.01),
    ("Islamabad", "Pakistan", 33.68, 73.05), ("Kabul", "Afghanistan", 34.56, 69.21),
    ("Dubai", "United Arab Emirates", 25.20, 55.27), ("Abu Dhabi", "United Arab Emirates", 24.45, 54.38),
    ("Doha", "Qatar", 25.29, 51.53), ("Riyadh", "Saudi Arabia", 24.71, 46.68), ("Muscat", "Oman", 23.59, 58.41),
    ("Tehran", "Iran", 35.69, 51.39), ("Baghdad", "Iraq", 33.31, 44.36), ("Jerusalem", "Israel", 31.77, 35.21),
    ("Tel Aviv", "Israel", 32.09, 34.78), ("Beirut", "Lebanon", 33.89, 35.50), ("Damascus", "Syria", 33.51, 36.28),
    ("Amman", "Jordan", 31.95, 35.93), ("Istanbul", "Turkey", 41.01, 28.98), ("Cairo", "Egypt", 30.04, 31.24),
    ("Nairobi", "Kenya", -1.29, 36.82), ("Addis Ababa", "Ethiopia", 9.03, 38.74), ("Lagos", "Nigeria", 6.52, 3.38),
    ("Johannesburg", "South Africa", -26.20, 28.05), ("Cape Town", "South Africa", -33.92, 18.42),
    ("Khartoum", "Sudan", 15.50, 32.56), ("London", "United Kingdom", 51.51, -0.13), ("Paris", "France", 48.86, 2.35),
    ("Berlin", "Germany", 52.52, 13.40), ("Madrid", "Spain", 40.42, -3.70), ("Rome", "Italy", 41.90, 12.50),
    ("Brussels", "Belgium", 50.85, 4.35), ("Amsterdam", "Netherlands", 52.37, 4.90), ("Geneva", "Switzerland", 46.20, 6.14),
    ("Vienna", "Austria", 48.21, 16.37), ("Stockholm", "Sweden", 59.33, 18.07), ("Oslo", "Norway", 59.91, 10.75),
    ("Warsaw", "Poland", 52.23, 21.01), ("Athens", "Greece", 37.98, 23.73), ("Lisbon", "Portugal", 38.72, -9.14),
    ("Dublin", "Ireland", 53.35, -6.26), ("Moscow", "Russia", 55.76, 37.62), ("Kyiv", "Ukraine", 50.45, 30.52),
    ("Beijing", "China", 39.90, 116.41), ("Shanghai", "China", 31.23, 121.47), ("Hong Kong", "Hong Kong", 22.32, 114.17),
    ("Taipei", "Taiwan", 25.03, 121.57), ("Tokyo", "Japan", 35.68, 139.69), ("Seoul", "Republic of Korea", 37.57, 126.98),
    ("Singapore", "Singapore", 1.35, 103.82), ("Kuala Lumpur", "Malaysia", 3.14, 101.69),
    ("Bangkok", "Thailand", 13.76, 100.50), ("Jakarta", "Indonesia", -6.21, 106.85), ("Manila", "Philippines", 14.60, 120.98),
    ("Hanoi", "Vietnam", 21.03, 105.85), ("Sydney", "Australia", -33.87, 151.21), ("Melbourne", "Australia", -37.81, 144.96),
    ("Auckland", "New Zealand", -36.85, 174.76), ("New York", "United States", 40.71, -74.01),
    ("Washington", "United States", 38.91, -77.04), ("Los Angeles", "United States", 34.05, -118.24),
    ("San Francisco", "United States", 37.77, -122.42), ("Seattle", "United States", 47.61, -122.33), ("Chicago", "United States", 41.88, -87.63),
    ("Houston", "United States", 29.76, -95.37), ("Toronto", "Canada", 43.65, -79.38), ("Vancouver", "Canada", 49.28, -123.12),
    ("Mexico City", "Mexico", 19.43, -99.13), ("São Paulo", "Brazil", -23.55, -46.63),
    ("Rio de Janeiro", "Brazil", -22.91, -43.17), ("Buenos Aires", "Argentina", -34.60, -58.38),
    ("Lima", "Peru", -12.05, -77.04), ("Bogotá", "Colombia", 4.71, -74.07),
]
# Seas, straits and other places the news names that aren't in one country: (name, lat, lon).
WATERS = [
    ("Pacific Ocean", 5.0, -160.0), ("Atlantic Ocean", 15.0, -38.0), ("Indian Ocean", -15.0, 78.0),
    ("Arctic Ocean", 78.0, 10.0), ("Southern Ocean", -55.0, 90.0), ("Red Sea", 20.0, 38.5),
    ("Strait of Hormuz", 26.6, 56.3), ("Persian Gulf", 26.8, 51.5), ("Arabian Sea", 15.0, 64.0),
    ("Bay of Bengal", 15.0, 88.0), ("South China Sea", 12.0, 114.0), ("Mediterranean Sea", 35.0, 18.0),
    ("Black Sea", 43.0, 34.0), ("Caribbean Sea", 15.0, -75.0), ("Gulf of Mexico", 25.0, -90.0),
    ("Suez Canal", 30.5, 32.35), ("Panama Canal", 9.1, -79.7), ("Himalayas", 28.5, 84.0),
    ("Mount Everest", 27.99, 86.93), ("Amazon rainforest", -3.5, -62.0), ("Sahara", 23.0, 13.0),
    ("Great Barrier Reef", -18.0, 147.0), ("Western Ghats", 13.0, 75.3),
]
WATER_ALIASES = {"Pacific": "Pacific Ocean", "Atlantic": "Atlantic Ocean", "Arctic": "Arctic Ocean",
                 "Mediterranean": "Mediterranean Sea", "Caribbean": "Caribbean Sea", "the Gulf": "Persian Gulf",
                 "Hormuz": "Strait of Hormuz", "Amazon River": "Amazon rainforest",
                 "Himalaya": "Himalayas", "Everest": "Mount Everest", "Sahara Desert": "Sahara"}
CITY_ALIASES = {"New Delhi": "Delhi", "Bangalore": "Bengaluru", "Bombay": "Mumbai", "Calcutta": "Kolkata",
                "Madras": "Chennai", "Kiev": "Kyiv", "Sao Paulo": "São Paulo", "Bogota": "Bogotá"}


@functools.lru_cache(maxsize=1)
def _finder():
    """Two patterns, longest name first: one case-sensitive, one not."""
    names = {}
    for c in countries():
        if c["name"] not in AMBIGUOUS and len(c["name"]) > 3:
            names[c["name"]] = ("country", c["name"])
    for real, alts in ALIASES.items():
        for a in alts:
            names[a] = ("country", real)
    for n, cc, lat, lon in CITIES:
        names[n] = ("city", n)
    for a, n in CITY_ALIASES.items():
        names[a] = ("city", n)
    for n, _, _ in WATERS:
        names[n] = ("water", n)
    for a, n in WATER_ALIASES.items():
        names[a] = ("water", n)
    # "New Mexico", "South American", "Indian Ocean": these are not the country.
    before, after = r"(?<![\w.])(?<!New )(?<!South )(?<!North )(?<!Latin )", r"(?![\w])(?!\s+Ocean)(?!-American)"

    def pattern(keys, flags):
        alts = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
        return re.compile(f"{before}({alts}){after}", flags)

    exact = {k for k in names if k in EXACT}
    loose = set(names) - exact
    lookup = {k.lower(): v for k, v in names.items() if k not in exact}
    lookup.update({k: v for k, v in names.items() if k in exact})
    return pattern(loose, re.I), pattern(exact, 0), lookup


def find(*texts):
    """The places these texts name, in order: (countries, the first city or sea named, or None)."""
    loose, exact, lookup = _finder()
    found = []
    for t in texts:
        t = re.sub(r"<[^>]+>", " ", str(t or ""))
        hits = [(m.start(), lookup[m.group(1).lower()]) for m in loose.finditer(t)]
        hits += [(m.start(), lookup[m.group(1)]) for m in exact.finditer(t)]
        found += [h for _, h in sorted(hits)]
    city = next((n for kind, n in found if kind in ("city", "water")), None)
    ccs = []
    cities = {n: cc for n, cc, _, _ in CITIES}
    for kind, n in found:
        cc = cities[n] if kind == "city" else n
        if cc in by_name() and cc not in ccs:
            ccs.append(cc)
    return ccs, city


def country_name(text):
    """The map's name for a country, however the news writes it; None if it isn't one."""
    t = str(text or "").strip()
    if t in by_name():
        return t
    for real, alts in ALIASES.items():
        if t in alts or t.lower() in (a.lower() for a in alts if a not in EXACT):
            return real
    low = {n.lower(): n for n in by_name()}
    return low.get(t.lower())


def city(name):
    """(lat, lon) of a city or sea on our lists."""
    return next(((lat, lon) for n, _, lat, lon in CITIES if n == name), None) or \
        next(((lat, lon) for n, lat, lon in WATERS if n == name), None)
