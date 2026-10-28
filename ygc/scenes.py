"""Moving pictures for Read & Play: each printed illustration motif, drawn again for the screen.

Every scene is a small inline SVG, 340 x 150, in the site's colours. The motion is CSS (play.css: .bob,
.waves, .flick, ...) so a phone set to "reduce motion" gets a still picture, and a scene only moves while
it is on screen. Moving parts sit in their own <g class="..."> because a CSS animation replaces an
element's own transform.
"""
import html

E = html.escape
SKY, SKY2, SUN, CORAL, TEAL, LEAF, SAND, INK, WHITE = ("#BFE3F2", "#DDF1F9", "#F4B400", "#E2584D", "#007C89",
                                                        "#2E7D4F", "#E9D9B0", "#1E2A32", "#FFFFFF")
GRASS, SEA, SEA2, NIGHT = "#8CC46B", "#5BB3D0", "#3D97B8", "#1D2D50"


# ------------------------------------------------------------------ pieces
def _sky(top=SKY, ground=None, horizon=105):
    out = f'<rect width="340" height="150" fill="{top}"/>'
    if ground:
        out += f'<rect y="{horizon}" width="340" height="{150 - horizon}" fill="{ground}"/>'
    return out


def _sun(x=290, y=30, r=13, rays=True):
    ray = "".join(f'<rect x="-1.5" y="{-r - 10}" width="3" height="6" rx="1.5" fill="{SUN}" transform="rotate({a})"/>'
                  for a in range(0, 360, 45)) if rays else ""
    return (f'<g transform="translate({x} {y})"><g class="spin" style="animation-duration:18s">{ray}</g>'
            f'<circle r="{r}" fill="{SUN}"/></g>')


def _start(x, dur):
    """The delay that puts something drifting across (from -60 to 400) at x when the page opens."""
    return f"animation-duration:{dur}s;animation-delay:-{dur * (x + 60) / 460:.1f}s"


def _cloud(x, y, s=1.0, dur=46, delay=0, fill=WHITE):
    return (f'<g class="drift" style="{_start(x, dur)}">'
            f'<g transform="translate(0 {y}) scale({s})" fill="{fill}" opacity=".95">'
            f'<ellipse cx="0" cy="0" rx="18" ry="9"/><ellipse cx="14" cy="-5" rx="13" ry="10"/>'
            f'<ellipse cx="27" cy="1" rx="14" ry="8"/></g></g>')


def _waves(y, fill, amp=4, dur=4, delay=0):
    d = f"M0 {y}" + f"q10 {-amp} 20 0t20 0" * 11 + f"V150H0z"
    return f'<g class="waves" style="animation-duration:{dur}s;animation-delay:-{delay}s"><path d="{d}" fill="{fill}"/></g>'


def _bird(x, y, dur=14, delay=0, s=1.0):
    return (f'<g class="drift" style="{_start(x, dur)}"><g transform="translate(0 {y}) scale({s})">'
            f'<g class="flap"><path d="M-7 0q3.5-4 7 0q3.5-4 7 0" fill="none" stroke="{INK}" stroke-width="1.6" '
            f'stroke-linecap="round"/></g></g></g>')


def _puffs(x, y, n=3, dur=2.4, fill="#F2F2F2", r=6):
    return "".join(f'<g class="puff" style="animation-duration:{dur}s;animation-delay:-{i * dur / n:.2f}s">'
                   f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/></g>' for i in range(n))


def _person(x, y, shirt, skin="#C68B59", s=1.0):
    return (f'<g transform="translate({x} {y}) scale({s})"><rect x="-6" y="-2" width="12" height="18" rx="5" fill="{shirt}"/>'
            f'<circle cy="-8" r="6" fill="{skin}"/></g>')


# ------------------------------------------------------------------ scenes
def ship():
    containers = "".join(f'<rect x="{-40 + i * 13}" y="{-14 - 9 * (j)}" width="12" height="8" fill="{c}"/>'
                         for i, cs in enumerate([[CORAL, TEAL], [SUN, CORAL], [TEAL, LEAF], [LEAF, SUN], [CORAL, TEAL]])
                         for j, c in enumerate(cs))
    return (_sky() + _sun() + _cloud(40, 30) + _cloud(180, 22, .8, 60, 20) + _bird(120, 40, 18, 4)
            + _waves(100, SEA, 3, 5)
            + f'<g transform="translate(170 104)"><g class="bob">{_puffs(32, -46, 3, 2.6, "#E8E8E8", 5)}'
              f'<rect x="26" y="-44" width="9" height="16" fill="{INK}"/><rect x="26" y="-44" width="9" height="4" fill="{CORAL}"/>'
              f'{containers}<rect x="22" y="-30" width="22" height="16" fill="{WHITE}"/>'
              f'<rect x="25" y="-27" width="16" height="4" fill="{SKY}"/>'
              f'<path d="M-62-6H62L52 14H-50z" fill="{INK}"/><path d="M-62-6H62L60 0H-60z" fill="{CORAL}"/></g></g>'
            + _waves(112, SEA2, 4, 3.5, 1))


def strait():
    return (_sky(SEA) + _waves(64, "#6EC0DA", 2, 6)
            + f'<path d="M0 0H340V38L300 44 250 34 200 50 170 58 140 48 90 40 40 46 0 40z" fill="{SAND}"/>'
              f'<path d="M0 150H340V112L290 104 230 112 190 96 170 92 150 98 100 108 50 102 0 110z" fill="{SAND}"/>'
              f'<path d="M10 75C90 75 120 74 170 74S260 76 330 75" fill="none" stroke="{CORAL}" stroke-width="2.4" class="flow"/>'
              f'<g transform="translate(170 74)"><g class="pulse"><circle r="7" fill="none" stroke="{CORAL}" stroke-width="2"/></g>'
              f'<circle r="4" fill="{CORAL}"/></g>'
              f'<g class="sail" style="animation-duration:16s"><g transform="translate(0 70)">'
              f'<path d="M-14 0H14L10 7H-10z" fill="{INK}"/><rect x="-10" y="-6" width="14" height="6" fill="{TEAL}"/>'
              f'<rect x="5" y="-9" width="5" height="9" fill="{WHITE}"/></g></g>'
              f'<g class="sail" style="animation-duration:16s;animation-delay:-8s"><g transform="translate(0 80) scale(.8)">'
              f'<path d="M-14 0H14L10 7H-10z" fill="{INK}"/><rect x="-10" y="-6" width="14" height="6" fill="{SUN}"/></g></g>')


def border():
    posts = "".join(f'<rect x="{x}" y="70" width="4" height="40" fill="#6B5B45"/>' for x in range(14, 340, 36))
    wires = "".join(f'<path d="M0 {y}H340" stroke="#8D8D8D" stroke-width="1.2" stroke-dasharray="3 2"/>' for y in (76, 88, 100))
    return (_sky(SKY, "#D8C79A", 108) + _sun(46, 30) + _cloud(200, 26)
            + f'<path d="M0 108Q85 92 170 108T340 108V150H0z" fill="#CDBB8A"/>{posts}{wires}'
              f'<g transform="translate(270 40)"><rect x="-6" y="0" width="12" height="70" fill="#7A6A52"/>'
              f'<rect x="-14" y="-12" width="28" height="14" fill="{INK}"/><g class="blink"><circle cx="0" cy="-17" r="4" fill="{SUN}"/></g></g>'
              f'<g transform="translate(60 40)"><rect x="0" y="0" width="2.5" height="70" fill="{INK}"/>'
              f'<g class="wave-flag"><rect x="2.5" y="0" width="26" height="16" fill="{TEAL}"/></g></g>'
              f'<g transform="translate(140 40)"><rect x="0" y="0" width="2.5" height="70" fill="{INK}"/>'
              f'<g class="wave-flag" style="animation-delay:-.5s"><rect x="2.5" y="0" width="26" height="16" fill="{CORAL}"/></g></g>'
            + _bird(80, 30, 16) + _bird(40, 46, 20, 7, .8))


def fire():
    trees = "".join(f'<g transform="translate({x} {y})"><rect x="-2" y="0" width="4" height="12" fill="#5A4636"/>'
                    f'<path d="M0-22L11 2H-11z" fill="{c}"/></g>'
                    for x, y, c in ((30, 96, "#3E6B48"), (62, 100, "#47784F"), (290, 98, "#3E6B48"), (318, 102, "#47784F")))
    flames = "".join(f'<g transform="translate({x} 112)"><g class="flick" style="animation-delay:-{d}s">'
                     f'<path d="M0 0C-16 0-18-18-6-34C-6-22 2-24 0-40C14-28 16-10 10 0z" fill="{CORAL}"/>'
                     f'<path d="M0 0C-8 0-9-10-3-18C-2-12 4-14 3-22C10-14 10-4 6 0z" fill="{SUN}"/></g></g>'
                     for x, d in ((130, 0), (170, .3), (210, .15), (245, .45)))
    return (_sky("#F8D7A8", "#B88A5A", 110) + _sun(300, 28, 11, False)
            + f'<path d="M0 110Q90 80 170 104T340 96V150H0z" fill="#9C7650"/>{trees}'
            + _puffs(160, 60, 4, 3, "#9E9E9E", 9) + _puffs(215, 56, 4, 3.4, "#B5B5B5", 8) + flames
            + f'<rect y="112" width="340" height="38" fill="#7D5C3C"/>')


def flood():
    rain = "".join(f'<g class="fall" style="animation-delay:-{(i * 37 % 12) / 10:.1f}s">'
                   f'<path d="M{x} {y}l-3 9" stroke="#5D7B8C" stroke-width="1.6" stroke-linecap="round"/></g>'
                   for i, (x, y) in enumerate((x, (x * 7) % 40) for x in range(12, 340, 17)))
    houses = "".join(f'<g transform="translate({x} 70)"><rect x="-18" y="0" width="36" height="34" fill="{c}"/>'
                     f'<path d="M-22 0L0-18 22 0z" fill="{CORAL}"/><rect x="-6" y="8" width="12" height="10" fill="{SKY2}"/></g>'
                     for x, c in ((70, "#F1E3C6"), (170, "#E9D3A9"), (270, "#F1E3C6")))
    return (_sky("#A9B8C2") + _cloud(30, 22, 1.2, 70, 0, "#8E9DA8") + _cloud(200, 18, 1.4, 80, 30, "#8E9DA8")
            + rain + houses + _waves(92, "#7FA7B5", 3, 6)
            + f'<g transform="translate(120 96)"><g class="bob"><path d="M-14 0H14L9 7H-9z" fill="{CORAL}"/>'
              f'<path d="M0 0V-14L9-3z" fill="{WHITE}"/></g></g>' + _waves(104, "#6693A3", 4, 4, 2))


def grid():
    def pylon(x):
        return (f'<g transform="translate({x} 40)" stroke="{INK}" stroke-width="2" fill="none">'
                f'<path d="M-12 70L0 0 12 70M-8 46H8M-5 26H5M-16 12H16"/></g>')
    lines = "".join(f'<path d="M30 {y}Q100 {y + 10} 170 {y}T310 {y}" fill="none" stroke="{c}" stroke-width="{w}"{a}/>'
                    for y in (52, 60) for c, w, a in ((INK, 1, ""), (SUN, 2.4, ' class="flow"')))
    return (_sky() + _cloud(60, 26, .9, 55, 10) + f'<rect y="110" width="340" height="40" fill="{GRASS}"/>'
            + pylon(30) + pylon(170) + pylon(310) + lines
            + f'<g transform="translate(250 110)"><rect x="-26" y="-30" width="20" height="30" fill="#9AA5AD"/>'
              f'<rect x="-2" y="-46" width="8" height="46" fill="#7E8A93"/><rect x="10" y="-22" width="22" height="22" fill="#9AA5AD"/>'
              f'</g>' + _puffs(252, 58, 3, 2.8, "#E3E3E3", 6)
            + f'<g transform="translate(95 110)"><rect x="-1.5" y="-56" width="3" height="56" fill="{WHITE}"/>'
              f'<g transform="translate(0 -56)"><g class="spin" style="animation-duration:3s">'
              + "".join(f'<path d="M0 0L-3-26Q0-30 3-26z" fill="{WHITE}" stroke="#C9D3D9" transform="rotate({a})"/>'
                        for a in (0, 120, 240))
              + f'</g><circle r="3" fill="{INK}"/></g></g>')


def ballot():
    bunting = "".join(f'<path d="M{x} 6l10 14 10-14" fill="{c}"/>'
                      for x, c in zip(range(0, 340, 22), [CORAL, SUN, TEAL, LEAF] * 4))
    return (_sky(SKY2, "#E6D8BB", 118) + f'<path d="M0 6Q170 22 340 6" stroke="{INK}" fill="none"/>{bunting}'
            + f'<g transform="translate(170 118)"><rect x="-44" y="-50" width="88" height="50" rx="4" fill="{TEAL}"/>'
              f'<rect x="-24" y="-52" width="48" height="5" rx="2" fill="{INK}"/>'
              f'<path d="M-18-26l9 9 18-18" stroke="{WHITE}" stroke-width="6" fill="none" stroke-linecap="round"/></g>'
              f'<g transform="translate(170 54)"><g class="drop"><rect x="-12" y="-8" width="24" height="16" rx="2" fill="{WHITE}" '
              f'stroke="#C9C9C9"/><path d="M-6 0l4 4 8-8" stroke="{CORAL}" stroke-width="2" fill="none"/></g></g>'
              f'<g transform="translate(80 110)"><g class="hop">{_person(0, 0, CORAL)}</g></g>'
              f'<g transform="translate(260 110)"><g class="hop" style="animation-delay:-.7s">{_person(0, 0, LEAF)}</g></g>')


def airdefense():
    stars = "".join(f'<g class="blink" style="animation-delay:-{i * .37:.2f}s"><circle cx="{x}" cy="{y}" r="1.4" fill="{WHITE}"/></g>'
                    for i, (x, y) in enumerate(((30, 20), (80, 40), (130, 14), (200, 30), (250, 12), (310, 36), (290, 64), (60, 70))))
    return (_sky(NIGHT, "#2F3B2E", 116) + stars + f'<circle cx="300" cy="28" r="12" fill="#F3EBC8"/>'
            + f'<g transform="translate(110 116)"><rect x="-40" y="-14" width="80" height="14" rx="3" fill="#56624F"/>'
              f'<circle cx="-24" cy="0" r="7" fill="{INK}"/><circle cx="24" cy="0" r="7" fill="{INK}"/>'
              f'<g transform="translate(0 -14)"><rect x="-3" y="-20" width="6" height="20" fill="#7B8775"/>'
              f'<g class="sway" style="animation-duration:3s"><path d="M-22-44A26 26 0 0 0 22-44L0-22z" fill="#C8D0C2"/></g></g></g>'
              f'<g transform="translate(250 86)"><circle r="30" fill="#163A2B" stroke="#4FD18B" stroke-width="2"/>'
              f'<circle r="18" fill="none" stroke="#2E7D4F"/><circle r="8" fill="none" stroke="#2E7D4F"/>'
              f'<g class="spin" style="animation-duration:3s"><path d="M0 0L0-30A30 30 0 0 1 21-21z" fill="#4FD18B" opacity=".45"/></g>'
              f'<g class="blink"><circle cx="12" cy="-14" r="2.4" fill="#4FD18B"/></g>'
              f'<g class="blink" style="animation-delay:-1s"><circle cx="-16" cy="8" r="2.4" fill="#4FD18B"/></g></g>')


def rocket():
    stars = "".join(f'<g class="blink" style="animation-delay:-{i * .41:.2f}s"><circle cx="{x}" cy="{y}" r="1.3" fill="{WHITE}"/></g>'
                    for i, (x, y) in enumerate(((24, 18), (70, 44), (120, 16), (230, 22), (280, 50), (318, 14), (40, 80))))
    return (_sky(NIGHT, "#3A3F4B", 124) + stars + f'<circle cx="290" cy="34" r="14" fill="#F3EBC8"/><circle cx="285" cy="30" r="3" fill="#DCD3AE"/>'
            + f'<g transform="translate(170 124)"><rect x="-40" y="-8" width="80" height="8" fill="#5B6270"/>'
              f'<rect x="26" y="-90" width="6" height="82" fill="#5B6270"/></g>'
            + _puffs(152, 116, 4, 2.6, "#D9D9D9", 10) + _puffs(188, 116, 4, 2.2, "#E6E6E6", 10)
            + f'<g class="rise"><g transform="translate(170 108)">'
              f'<g class="flick" style="animation-duration:.25s"><path d="M-7 0Q0 26 7 0z" fill="{SUN}"/><path d="M-4 0Q0 14 4 0z" fill="{CORAL}"/></g>'
              f'<path d="M-10 0V-48Q0-74 10-48V0z" fill="{WHITE}"/><path d="M-10-48Q0-74 10-48z" fill="{CORAL}"/>'
              f'<circle cy="-34" r="4.5" fill="{SKY}" stroke="{INK}"/><path d="M-10-12L-18 2H-10zM10-12L18 2H10z" fill="{CORAL}"/>'
              f'</g></g>')


def podium():
    confetti = "".join(f'<g class="fall" style="animation-duration:{2 + (i % 3) * .5}s;animation-delay:-{(i * 0.29) % 2:.2f}s">'
                       f'<rect x="{x}" y="{(i * 13) % 30}" width="4" height="7" fill="{c}" transform="rotate({i * 37} {x} {(i * 13) % 30})"/></g>'
                       for i, (x, c) in enumerate(zip(range(12, 340, 19), [CORAL, SUN, TEAL, LEAF] * 5)))
    return (_sky(SKY2) + confetti
            + f'<g transform="translate(170 150)"><rect x="-30" y="-60" width="60" height="60" fill="{SUN}"/>'
              f'<rect x="-90" y="-40" width="60" height="40" fill="#C9D3D9"/><rect x="30" y="-28" width="60" height="28" fill="#D9A066"/>'
              f'<text y="-30" text-anchor="middle" font-size="22" font-weight="800" fill="{WHITE}">1</text>'
              f'<text x="-60" y="-14" text-anchor="middle" font-size="18" font-weight="800" fill="{WHITE}">2</text>'
              f'<text x="60" y="-8" text-anchor="middle" font-size="16" font-weight="800" fill="{WHITE}">3</text></g>'
              f'<g transform="translate(170 64)"><path d="M-14-28H14V-16Q14 0 0 2Q-14 0-14-16z" fill="{SUN}"/>'
              f'<rect x="-3" y="2" width="6" height="12" fill="{SUN}"/><rect x="-12" y="14" width="24" height="6" fill="#B07D1A"/>'
              f'<path d="M-14-24Q-26-24-24-12Q-22-6-12-8M14-24Q26-24 24-12Q22-6 12-8" fill="none" stroke="{SUN}" stroke-width="3"/>'
              f'<g class="blink"><path d="M-6-22l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="{WHITE}"/></g></g>'
              f'<g transform="translate(110 46)"><g class="swing"><path d="M0 0L0 20" stroke="{TEAL}" stroke-width="3"/>'
              f'<circle cy="26" r="8" fill="#C9D3D9"/></g></g>'
              f'<g transform="translate(230 58)"><g class="swing" style="animation-delay:-1s"><path d="M0 0L0 20" stroke="{CORAL}" stroke-width="3"/>'
              f'<circle cy="26" r="8" fill="#D9A066"/></g></g>')


def cricket():
    return (_sky(SKY, "#7DBB5A", 100) + _sun(300, 26) + _cloud(60, 26, .9)
            + f'<ellipse cx="170" cy="128" rx="150" ry="20" fill="#9CCB74"/><rect x="140" y="110" width="60" height="34" fill="#D9C48F"/>'
              f'<g transform="translate(150 120)" fill="{WHITE}"><rect x="-8" y="-26" width="3" height="26"/><rect x="-2" y="-26" width="3" height="26"/>'
              f'<rect x="4" y="-26" width="3" height="26"/><rect x="-9" y="-28" width="17" height="2.5" fill="#D9A066"/></g>'
              f'<g transform="translate(190 120)">{_person(0, -20, TEAL, s=1.2)}'
              f'<g transform="translate(6 -26)"><g class="bat"><rect x="-2" y="0" width="5" height="26" rx="2" fill="#D9A066"/></g></g></g>'
              f'<g class="flyx"><g class="flyy"><circle cx="196" cy="100" r="3.6" fill="{CORAL}"/></g></g>')


def skyline():
    out = []
    for i, (x, w, h, c) in enumerate(((10, 40, 70, "#4F6D7A"), (55, 34, 95, "#3D5A66"), (95, 46, 60, "#5C7B87"),
                                      (146, 30, 110, "#2F4A55"), (182, 50, 80, "#4F6D7A"), (238, 36, 100, "#3D5A66"),
                                      (280, 50, 66, "#5C7B87"))):
        out.append(f'<rect x="{x}" y="{140 - h}" width="{w}" height="{h}" fill="{c}"/>')
        for r in range(140 - h + 8, 132, 12):
            for col in range(x + 5, x + w - 6, 10):
                k = (r * 7 + col * 3 + i) % 5
                lit = f' class="blink" style="animation-delay:-{k * .6:.1f}s;animation-duration:{3 + k}s"' if k < 2 else ""
                out.append(f'<g{lit}><rect x="{col}" y="{r}" width="5" height="6" fill="{SUN if k < 3 else "#9FB5BE"}"/></g>')
    return (_sky("#FBD9B6") + _sun(70, 40, 16, False) + _cloud(200, 22, 1, 50, 5)
            + f'<g class="sail" style="animation-duration:20s"><g transform="translate(0 30)"><path d="M-16 0H12Q18 0 18 3T12 6H-16z" '
              f'fill="{WHITE}"/><path d="M-4 3L-12 14H-6L4 3z" fill="#C9D3D9"/><path d="M-16 0L-20-7H-15L-10 0z" fill="{CORAL}"/></g></g>'
            + "".join(out) + f'<rect y="140" width="340" height="10" fill="#2B3B42"/>')


def capitol():
    cols = "".join(f'<rect x="{x}" y="92" width="6" height="34" fill="{WHITE}"/>' for x in range(120, 222, 14))
    return (_sky() + _cloud(30, 24, 1, 50) + _cloud(230, 34, .8, 60, 25) + _bird(250, 30, 15, 3)
            + f'<rect y="126" width="340" height="24" fill="{GRASS}"/><rect x="100" y="122" width="140" height="8" fill="#E8E2D2"/>'
              f'<rect x="110" y="86" width="120" height="8" fill="#E8E2D2"/>{cols}'
              f'<rect x="140" y="70" width="60" height="16" fill="#F2EEE3"/><path d="M140 70A30 30 0 0 1 200 70z" fill="#F2EEE3"/>'
              f'<rect x="168" y="30" width="4" height="12" fill="#F2EEE3"/><rect x="169" y="16" width="2" height="16" fill="{INK}"/>'
              f'<g transform="translate(171 16)"><g class="wave-flag"><rect width="22" height="13" fill="{CORAL}"/></g></g>')


def robot():
    gear = (lambda x, y, r, d, rev: f'<g transform="translate({x} {y})"><g class="spin" style="animation-duration:{d}s'
            f'{";animation-direction:reverse" if rev else ""}">' + "".join(
                f'<rect x="-3" y="{-r - 5}" width="6" height="8" fill="#B9C6CC" transform="rotate({a})"/>' for a in range(0, 360, 45))
            + f'<circle r="{r}" fill="#B9C6CC"/><circle r="{r / 3:.1f}" fill="{SKY2}"/></g></g>')
    return (_sky(SKY2, "#D6E2E7", 128) + gear(60, 50, 20, 8, False) + gear(96, 80, 13, 6, True) + gear(286, 60, 16, 7, True)
            + f'<g transform="translate(180 128)"><g class="hop" style="animation-duration:2.4s">'
              f'<rect x="-30" y="-58" width="60" height="50" rx="10" fill="{TEAL}"/><rect x="-18" y="-46" width="36" height="22" rx="6" fill="{WHITE}"/>'
              f'<g class="eyes"><circle cx="-8" cy="-35" r="4" fill="{INK}"/><circle cx="8" cy="-35" r="4" fill="{INK}"/></g>'
              f'<rect x="-8" y="-24" width="16" height="3" rx="1.5" fill="{TEAL}" opacity=".5"/>'
              f'<rect x="-2" y="-72" width="4" height="14" fill="{INK}"/><g class="blink"><circle cy="-75" r="5" fill="{CORAL}"/></g>'
              f'<rect x="-22" y="-8" width="10" height="8" fill="{INK}"/><rect x="12" y="-8" width="10" height="8" fill="{INK}"/>'
              f'<rect x="-44" y="-50" width="14" height="8" rx="4" fill="{TEAL}"/>'
              f'<g transform="translate(30 -46)"><g class="wave-arm"><rect x="0" y="-4" width="24" height="8" rx="4" fill="{TEAL}"/>'
              f'<circle cx="26" cy="0" r="6" fill="{SUN}"/></g></g></g></g>')


def farm():
    rows = "".join(f'<path d="M0 {y}Q170 {y - 8} 340 {y}" stroke="{c}" stroke-width="6" fill="none"/>'
                   for y, c in ((112, "#B9D47F"), (124, "#9CC46A"), (136, "#B9D47F"), (148, "#9CC46A")))
    crops = "".join(f'<g transform="translate({x} 106)"><g class="sway" style="animation-delay:-{(x % 7) / 3:.1f}s">'
                    f'<path d="M0 0V-14M0-8L-5-12M0-10L5-14" stroke="{LEAF}" stroke-width="2" fill="none"/></g></g>'
                    for x in range(18, 330, 22))
    return (_sky(SKY, "#A8CF73", 104) + _sun(60, 30) + _cloud(170, 24)
            + f'<path d="M0 104Q100 88 200 100T340 96V150H0z" fill="#8FBF5F"/>{rows}{crops}'
            + f'<g transform="translate(270 100)"><path d="M-6 0L-3-50H3L6 0z" fill="{WHITE}"/>'
              f'<g transform="translate(0 -50)"><g class="spin" style="animation-duration:5s">'
              + "".join(f'<rect x="-3" y="-30" width="6" height="30" fill="{CORAL}" transform="rotate({a})"/>' for a in (0, 90, 180, 270))
              + f'</g><circle r="4" fill="{INK}"/></g></g>'
            + f'<g class="sail" style="animation-duration:26s"><g transform="translate(0 112)"><rect x="-14" y="-14" width="22" height="12" fill="{CORAL}"/>'
              f'<rect x="-2" y="-24" width="12" height="12" fill="{CORAL}"/><rect x="0" y="-22" width="8" height="7" fill="{SKY2}"/>'
              f'<circle cx="-8" cy="0" r="6" fill="{INK}"/><circle cx="8" cy="2" r="4" fill="{INK}"/></g></g>')


def globe():
    land = ("M0 30q20-14 40-4t30 10-6 24-26 10-30-14z M90 10q24-6 40 8t-4 30-30 6-14-24z "
            "M150 50q16-6 26 6t-6 22-20-2-4-18z M30 80q14-4 20 6t-8 14-14-8z")
    return (_sky(NIGHT) + "".join(f'<g class="blink" style="animation-delay:-{i * .5}s"><circle cx="{x}" cy="{y}" r="1.3" fill="{WHITE}"/></g>'
                                  for i, (x, y) in enumerate(((30, 20), (60, 110), (280, 24), (310, 120), (250, 70), (90, 60))))
            + f'<defs><clipPath id="rp-globe"><circle cx="170" cy="75" r="56"/></clipPath></defs>'
              f'<circle cx="170" cy="75" r="56" fill="{SEA}"/>'
              f'<g clip-path="url(#rp-globe)"><g class="roll"><g transform="translate(110 40)" fill="{GRASS}">'
              f'<path d="{land}"/><path d="{land}" transform="translate(180 0)"/></g></g></g>'
              f'<circle cx="170" cy="75" r="56" fill="none" stroke="{WHITE}" stroke-opacity=".5" stroke-width="2"/>'
              f'<g transform="translate(170 75)"><g class="spin" style="animation-duration:9s">'
              f'<g transform="translate(78 0)"><rect x="-4" y="-3" width="8" height="6" fill="#C9D3D9"/>'
              f'<rect x="-14" y="-2" width="8" height="4" fill="{TEAL}"/><rect x="6" y="-2" width="8" height="4" fill="{TEAL}"/></g></g></g>')


def court():
    cols = "".join(f'<rect x="{x}" y="70" width="8" height="52" fill="{WHITE}"/>' for x in range(46, 150, 20))
    return (_sky(SKY2) + _cloud(240, 24, .9, 55, 15)
            + f'<rect y="122" width="340" height="28" fill="#D9CDB4"/><path d="M36 70L100 40 164 70z" fill="#EFE8D8"/>'
              f'<rect x="36" y="66" width="128" height="6" fill="#EFE8D8"/>{cols}<rect x="30" y="118" width="140" height="6" fill="#EFE8D8"/>'
              f'<g transform="translate(250 60)"><rect x="-2" y="0" width="4" height="56" fill="{INK}"/><rect x="-16" y="54" width="32" height="6" fill="{INK}"/>'
              f'<g class="swing" style="animation-duration:3.2s"><rect x="-34" y="-2" width="68" height="3" fill="{INK}"/>'
              f'<path d="M-30 0L-40 22H-20zM30 0L20 22H40z" fill="none" stroke="{INK}"/>'
              f'<path d="M-42 22A12 6 0 0 0-18 22z" fill="{SUN}"/><path d="M18 22A12 6 0 0 0 42 22z" fill="{SUN}"/></g></g>'
              f'<rect x="196" y="128" width="50" height="10" rx="2" fill="#8B5E3C"/>'
              f'<g transform="translate(240 126)"><g class="tap"><rect x="-30" y="-8" width="22" height="10" rx="3" fill="#8B5E3C"/>'
              f'<rect x="-10" y="-5" width="26" height="4" fill="#6B4A2E"/></g></g>')


def protest():
    people = []
    for i, (x, c, sign) in enumerate(((50, CORAL, SUN), (100, TEAL, WHITE), (150, LEAF, CORAL), (200, SUN, TEAL),
                                      (250, CORAL, WHITE), (300, TEAL, SUN))):
        people.append(f'<g transform="translate({x} 118)"><g class="hop" style="animation-delay:-{i * .23:.2f}s">'
                      f'<rect x="-1.5" y="-56" width="3" height="34" fill="#6B5B45"/><rect x="-16" y="-70" width="32" height="20" rx="3" fill="{sign}" stroke="{INK}"/>'
                      f'<path d="M-8-60h16" stroke="{INK}" stroke-width="2.4" stroke-linecap="round"/>'
                      f'{_person(0, -6, c)}</g></g>')
    return _sky(SKY, "#CFC6B4", 118) + _sun(300, 24, 10) + _cloud(120, 20, .8, 50, 10) + "".join(people)


def hospital():
    win = "".join(f'<rect x="{x}" y="{y}" width="12" height="10" fill="{SKY}"/>' for x in range(82, 200, 22) for y in (74, 94))
    return (_sky(SKY2, "#D6E2E7", 124) + _cloud(260, 24, .9, 50)
            + f'<rect x="70" y="50" width="140" height="74" fill="{WHITE}" stroke="#C9D3D9"/>{win}'
              f'<rect x="126" y="104" width="28" height="20" fill="{TEAL}"/>'
              f'<g transform="translate(140 34)"><g class="beat"><rect x="-5" y="-14" width="10" height="28" fill="{CORAL}"/>'
              f'<rect x="-14" y="-5" width="28" height="10" fill="{CORAL}"/></g></g>'
              f'<path d="M222 70h20l6-14 8 26 6-12h40" fill="none" stroke="{CORAL}" stroke-width="2.4" class="flow"/>'
              f'<g class="sail" style="animation-duration:14s"><g transform="translate(0 124)"><rect x="-22" y="-20" width="34" height="18" rx="3" fill="{WHITE}" stroke="{INK}"/>'
              f'<path d="M12-16h8l6 8v6h-14z" fill="{WHITE}" stroke="{INK}"/><rect x="-10" y="-14" width="10" height="3" fill="{CORAL}"/>'
              f'<rect x="-6.5" y="-17.5" width="3" height="10" fill="{CORAL}"/><g class="blink" style="animation-duration:.8s">'
              f'<rect x="-4" y="-24" width="8" height="4" fill="#3A7BD5"/></g>'
              f'<circle cx="-12" cy="0" r="4" fill="{INK}"/><circle cx="16" cy="0" r="4" fill="{INK}"/></g></g>')


def chart_free_map(spec):
    """A printed map with no country we can find: the same sketch, moving."""
    s = spec or {}
    return (strait()
            + f'<text x="330" y="22" text-anchor="end" font-size="11" font-weight="700" fill="{INK}">{E(s.get("label_top", ""))}</text>'
              f'<text x="10" y="140" font-size="11" font-weight="700" fill="{INK}">{E(s.get("label_bottom", ""))}</text>')


def talks(spec=None):
    names = (spec or {}).get("participants", [])
    boxes = ''.join(f'<rect x="{8+i*112}" y="45" width="100" height="45" rx="6" fill="{WHITE}" stroke="{TEAL}"/><text x="{58+i*112}" y="72" text-anchor="middle" font-size="11" fill="{INK}">{E(n)}</text>' for i,n in enumerate(names))
    return f'<rect width="340" height="150" fill="#FAF7F1"/>{boxes}<text x="170" y="120" text-anchor="middle" font-size="12" fill="{INK}">Trilateral means three parties</text>'


SCENES = {"ship": ship, "strait": strait, "border": border, "fire": fire, "flood": flood, "grid": grid, "ballot": ballot,
          "airdefense": airdefense, "rocket": rocket, "podium": podium, "cricket": cricket, "skyline": skyline,
          "capitol": capitol, "robot": robot, "farm": farm, "globe": globe, "court": court, "protest": protest,
          "hospital": hospital, "talks": talks}


def scene(motif, label="", spec=None):
    """The moving picture for a motif, as inline SVG (an unknown motif gets the globe)."""
    draw = SCENES.get(motif, globe)
    return (f'<svg class="scene" viewBox="0 0 340 150" role="img" aria-label="{E(label or motif)}" '
            f'font-family="Atkinson Hyperlegible, sans-serif">{talks(spec) if motif == "talks" else draw()}</svg>')


def sketch_map(spec, label=""):
    return (f'<svg class="scene" viewBox="0 0 340 150" role="img" aria-label="{E(label or "map")}" '
            f'font-family="Atkinson Hyperlegible, sans-serif">{chart_free_map(spec)}</svg>')


# The motion. Most parts turn or grow about their own (0, 0), which is SVG's default origin.
CSS = r"""
.scene{display:block;width:100%;height:auto;border-radius:14px;overflow:hidden}
.scene .drift{animation:rp-drift 46s linear infinite}
@keyframes rp-drift{from{transform:translateX(-60px)}to{transform:translateX(400px)}}
.scene .sail{animation:rp-drift 16s linear infinite}
.scene .waves{animation:rp-waves 4s linear infinite}
@keyframes rp-waves{to{transform:translateX(-40px)}}
.scene .bob{animation:rp-bob 3s ease-in-out infinite}
@keyframes rp-bob{50%{transform:translateY(3px) rotate(1.5deg)}}
.scene .flap{animation:rp-flap .45s ease-in-out infinite alternate}
@keyframes rp-flap{to{transform:scaleY(.3)}}
.scene .spin{animation:rp-spin 6s linear infinite}
@keyframes rp-spin{to{transform:rotate(360deg)}}
.scene .puff{transform-box:fill-box;transform-origin:center;animation:rp-puff 2.4s ease-out infinite}
@keyframes rp-puff{0%{transform:translateY(0) scale(.3);opacity:.9}100%{transform:translateY(-26px) scale(1.7);opacity:0}}
.scene .pulse{animation:rp-pulse 1.8s ease-out infinite}
@keyframes rp-pulse{0%{transform:scale(.6);opacity:1}100%{transform:scale(2.6);opacity:0}}
.scene .flow{stroke-dasharray:7 6;animation:rp-flow .9s linear infinite}
@keyframes rp-flow{to{stroke-dashoffset:-13}}
.scene .blink{animation:rp-blink 2.2s steps(1) infinite}
@keyframes rp-blink{50%{opacity:.2}}
.scene .flick{animation:rp-flick .5s ease-in-out infinite alternate}
@keyframes rp-flick{to{transform:scale(.86,1.14)}}
.scene .fall{animation:rp-fall 1.4s linear infinite}
@keyframes rp-fall{0%{transform:translateY(-20px);opacity:0}10%{opacity:1}100%{transform:translateY(140px);opacity:.9}}
.scene .hop{animation:rp-hop 1.3s ease-in-out infinite}
@keyframes rp-hop{50%{transform:translateY(-7px)}}
.scene .sway{animation:rp-sway 2.4s ease-in-out infinite alternate}
@keyframes rp-sway{from{transform:rotate(-6deg)}to{transform:rotate(6deg)}}
.scene .swing{animation:rp-swing 2s ease-in-out infinite alternate}
@keyframes rp-swing{from{transform:rotate(-9deg)}to{transform:rotate(9deg)}}
.scene .bat{animation:rp-bat 2.6s ease-in-out infinite}
@keyframes rp-bat{0%{transform:rotate(40deg)}8%{transform:rotate(-80deg)}30%,100%{transform:rotate(40deg)}}
.scene .flyx{animation:rp-flyx 2.6s linear infinite}
@keyframes rp-flyx{0%,8%{transform:translateX(0);opacity:1}90%{opacity:1}100%{transform:translateX(170px);opacity:0}}
.scene .flyy{animation:rp-flyy 1.3s ease-out infinite alternate}
@keyframes rp-flyy{to{transform:translateY(-80px)}}
.scene .rise{animation:rp-rise 6s ease-in infinite}
@keyframes rp-rise{0%,25%{transform:translateY(0);opacity:1}75%{transform:translateY(-190px);opacity:1}
  76%{transform:translateY(-190px);opacity:0}77%{transform:translateY(0);opacity:0}100%{opacity:1}}
.scene .drop{animation:rp-drop 2.4s ease-in infinite}
@keyframes rp-drop{0%{transform:translateY(-24px);opacity:0}20%{opacity:1}65%{transform:translateY(14px);opacity:1}
  80%,100%{transform:translateY(16px);opacity:0}}
.scene .eyes{transform-box:fill-box;transform-origin:center;animation:rp-eyes 4s infinite}
@keyframes rp-eyes{0%,90%,100%{transform:scaleY(1)}94%{transform:scaleY(.1)}}
.scene .wave-arm{animation:rp-arm 1.2s ease-in-out infinite alternate}
@keyframes rp-arm{from{transform:rotate(-35deg)}to{transform:rotate(15deg)}}
.scene .wave-flag{animation:rp-flag .9s ease-in-out infinite alternate}
@keyframes rp-flag{to{transform:skewY(7deg) scaleX(.92)}}
.scene .roll{animation:rp-roll 14s linear infinite}
@keyframes rp-roll{to{transform:translateX(-180px)}}
.scene .beat{animation:rp-beat 1.2s ease-in-out infinite}
@keyframes rp-beat{0%,40%,100%{transform:scale(1)}20%{transform:scale(1.18)}}
.scene .tap{animation:rp-tap 1.6s ease-in infinite}
@keyframes rp-tap{0%,55%,100%{transform:rotate(0)}30%{transform:rotate(28deg)}}
.scene.still *,.paused .scene *{animation-play-state:paused!important}
@media (prefers-reduced-motion:reduce){.scene *{animation:none!important}}
"""
