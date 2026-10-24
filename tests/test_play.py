"""Read & Play: the children's side of the site, built from the same issues as the PDFs."""
import html
import json
import os
import re

import pytest

from ygc import edition, play, site

ROOT = edition.ROOT


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    play.build(str(out), site.site_config(), keep=2, log=lambda *a: None)
    return out / "play"


def test_lobby_has_a_tile_per_paper_with_issues_and_age_buttons(built):
    lobby = (built / "index.html").read_text(encoding="utf-8")
    papers = [e for e in edition.list_editions() if site.issues_of(edition.load(e))]
    assert lobby.count('class="tile"') == len(papers)
    for band in ("6–8", "9–11", "12–14", "15+"):
        assert f'data-band="Ages {band}"' in lobby
    assert 'href="../play/play.css?v=' in lobby and (built / "play.css").exists() and (built / "play.js").exists()


def test_lobby_fits_the_first_screen(built):
    """Each paper is a short row with Read and Play; streaks are chips; phones get a bottom bar."""
    lobby = (built / "index.html").read_text(encoding="utf-8")
    rows = re.findall(r'<article class="tile" data-band="[^"]+" data-key="([^"]+)">(.*?)</article>', lobby, re.S)
    assert rows and all('class="thumb' in r and ">Read</a>" in r and ">Play</a>" in r for _, r in rows)
    assert all(re.fullmatch(r"[a-z0-9-]+-\d{4}-\d{2}-\d{2}", k) for k, _ in rows)    # matches the "read" key
    assert lobby.count('<span class="new">NEW</span>') >= 1
    assert 'class="mini"' in lobby                                          # a little real map for a story's place
    assert "function tower(" in (built / "play.js").read_text(encoding="utf-8")    # the streak is a pebble tower
    assert 'id="chips"' in lobby and 'class="pick"' in lobby and 'class="hello" hidden' in lobby
    tabs = re.search(r'<nav class="tabbar"[^>]*>(.*?)</nav>', lobby, re.S).group(1)
    for anchor in re.findall(r'href="#([a-z]+)"', tabs):
        assert f'id="{anchor}"' in lobby
    assert 'href="../index.html"' in tabs                                     # a way back to the grown-ups' home page


def test_a_young_readers_issue_reads_one_story_per_screen_with_words_to_tap(built):
    ed = edition.load("little-explorers")
    date = site.issues_of(ed)[0][0]
    page = (built / "little-explorers" / f"{date}.html").read_text(encoding="utf-8")
    assert 'data-mode="cards"' in page and 'class="read"' in page and 'id="game"' in page
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert len(data["vocab"]) == 3 and all(v["meaning"] and "Today" not in v["meaning"] for v in data["vocab"])
    assert page.count('class="w"') >= 1                              # new words highlighted in the stories
    assert "For grown-ups: sources" in page and 'href="../../play/play.css?v=' in page
    assert 'href="../../e/little-explorers/index.html"' in page          # back to the print side
    assert '<svg class="scene"' in page and 'class="where"' in page              # a moving picture, a real map
    assert 'src="../../play/world.js?v=' in page and (built / "world.js").exists()
    assert 'class="trail"' in page and 'class="desk"' in page


def test_older_readers_scroll_and_papers_without_new_words_get_story_match(built):
    ed = edition.load("junior-daily")                                  # no vocabulary section
    date = site.issues_of(ed)[0][0]
    page = (built / "junior-daily" / f"{date}.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert data["vocab"] == [] and len(data["stories"]) >= 2 and all(s["first"] for s in data["stories"])
    ygc = edition.load("young-global-citizen")
    page = (built / "young-global-citizen" / f"{site.issues_of(ygc)[0][0]}.html").read_text(encoding="utf-8")
    assert 'data-mode="scroll"' in page


def test_text_is_made_safe_for_the_web():
    assert play.clean('AT&amp;T <b>bold</b> <script>x</script>') == "AT&amp;T <b>bold</b> &lt;script&gt;x&lt;/script&gt;"
    used = set()
    out = play._highlight('A <b>hurricane</b> and hurricanes', [{"word": "Hurricane"}], used)
    assert out.count('class="w"') == 1 and used == {0} and "<b><mark" in out


PLAY = {"quiz": [{"q": "Which ocean?", "options": ["Atlantic", "Pacific", "Indian"], "answer": 1, "why": "It says Pacific.", "story": "lead"},
                 {"q": "Her job?", "options": ["Judge", "Driver", "Pilot"], "answer": 0, "why": "A judge.", "story": "world"},
                 {"q": "Where do hurricanes grow?", "options": ["Snow", "Warm sea", "Desert"], "answer": 1, "why": "Warm sea.", "story": "us"}],
        "fact_or_fiction": [{"claim": "Isaias was the first hurricane.", "true": True, "why": "It says so.", "story": "us"},
                            {"claim": "You can see them without a microscope.", "true": False, "why": "You need one.", "story": "science_and_technology"}]}


def _little(play_section):
    import copy
    ed = edition.load("little-explorers")
    issue = json.load(open(site.issues_of(ed)[-1][1], encoding="utf-8"))
    issue["play"] = copy.deepcopy(play_section)
    return ed, issue


def test_the_play_section_is_checked():
    from ygc import checks
    ed, issue = _little(PLAY)
    assert not [e for e in checks.check_issue(ed, issue, "x/2026-10-10.json", archive=True).errors if "play" in e]
    ed, bad = _little(PLAY)
    bad["play"]["quiz"][0].update(answer=3, options=["A", "a", ""])
    bad["play"]["quiz"].pop()
    for f in bad["play"]["fact_or_fiction"]:
        f["true"] = True
    bad["play"]["fact_or_fiction"][0]["story"] = "mars"
    errs = " ".join(e for e in checks.check_issue(ed, bad, "x/2026-10-10.json", archive=True).errors if "play" in e)
    for needle in ("expected 3 questions", "answer must be 0, 1 or 2", "3 different", "'mars'", "one that isn't true"):
        assert needle in errs, needle


def test_skeleton_and_instructions_ask_for_play_but_not_for_parents_chatbots():
    from ygc import chat, prompt, skeleton
    ed = edition.load("little-explorers")
    assert len(skeleton.make(ed, "2026-10-17", 2)["play"]["quiz"]) == 3          # ages 6-8: 3 questions
    assert [w["story"] for w in skeleton.make(ed, "2026-10-17", 2)["play"]["where"]] == edition.story_blocks(ed)
    assert "play" not in skeleton.make(ed, "2026-10-17", 2, play=False)
    assert "**Play (online only" in prompt.generate(ed)
    assert "**Play (online only" not in chat.instructions(ed, "2026-10-17") and '"play"' not in chat.instructions(ed, "2026-10-17")
    assert skeleton.play_counts(edition.load("current-affairs-digest")) == (8, 4)


def test_the_page_carries_the_games_and_links_answers_to_their_story():
    ed, issue = _little(PLAY)
    secs, data, _ = play.sections(ed, issue, "2026-10-10")
    assert [q["answer"] for q in data["quiz"]] == [1, 0, 1] and [f["true"] for f in data["facts"]] == [True, False]
    bids = [b for _, b, _, _ in secs]
    assert data["quiz"][0]["card"] == bids.index("lead") and data["facts"][1]["card"] == bids.index("science_and_technology")
    _, plain_data, _ = play.sections(*_little({})[0:2], "2026-10-10")
    assert plain_data["quiz"] == [] and plain_data["facts"] == []


# ------------------------------------------------------------------ pictures that move, charts that grow, maps
def test_the_lobby_has_a_map_of_todays_stories(built):
    lobby = (built / "index.html").read_text(encoding="utf-8")
    pins = json.loads(html.unescape(re.search(r'data-pins="([^"]*)"', lobby).group(1)))
    assert pins and all(-90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180 and p["place"] and "#s-" in p["u"] for p in pins)
    for p in pins:                                                     # each pin opens its story's card
        page, bid = p["u"].split("#")
        assert f'id="{bid}"' in (built / page).read_text(encoding="utf-8")
    assert "India's official maps" in lobby


def test_every_printed_picture_has_a_moving_one():
    from xml.etree import ElementTree
    from ygc import scenes
    from ygc.graphics import IllustrationCard
    assert set(IllustrationCard.known_motifs()) <= set(scenes.SCENES)
    for motif in scenes.SCENES:
        svg = ElementTree.fromstring(scenes.scene(motif, "A & B"))     # well-formed, labelled
        assert svg.get("aria-label") == "A & B" and svg.get("viewBox") == "0 0 340 150"
    assert 'aria-label="mystery"' in scenes.scene("mystery", "mystery")       # an unknown motif still draws
    ElementTree.fromstring(scenes.sketch_map({"label_top": "R&D <here>"}))
    assert "prefers-reduced-motion" in scenes.CSS


def test_charts_grow_from_the_printed_numbers():
    out = play.chart_html({"title": "POLL", "labels": ["Yes", "No"], "values": [52, 38.5], "max": 60, "value_prefix": "$",
                           "highlight_after": 0, "caption": "Oct 5"})
    assert out.count('<div class="bc"') + out.count('<div class="bc hi"') == 2 and 'class="bc hi"' in out and "--h:86.7\"" in out
    assert 'data-v="52"' in out and 'data-v="38.5"' in out and "$<b" in out and "Yes: $52; No: $38.5" in out
    assert play.chart_html({"values": []}) == ""


def test_sections_get_a_colour_and_an_icon():
    assert play.desk("TOP STORY  •  SAUDI ARABIA AND YEMEN", "lead")[1:] == ("⭐", "coral")
    assert play.desk("SCIENCE & TECH  •  PHYSICS")[1:] == ("🔬", "violet")
    assert play.desk("WORLD  •  RUSSIA AND UKRAINE") == ("World", "🌍", "teal")
    assert play.desk("", "mystery_section")[1] == "📰"
    assert play.nice("SAUDI ARABIA AND YEMEN") == "Saudi Arabia and Yemen" and play.nice("El Niño") == "El Niño"


def test_the_world_map_shows_indias_borders_as_indias_maps_do():
    from ygc import world
    india = world.by_name()["India"]
    assert india["d"] and india["box"][1] < world.project(77, 36.5)[1]          # all of Jammu and Kashmir
    assert "Antarctica" not in world.by_name() and len(world.countries()) > 200
    x, y = world.project(0, 0)
    assert abs(x - world.W / 2) < 1e-6 and abs(y - world.H / 2) < 1e-6
    data = json.loads(world.world_js()[len("window.WORLD="):-2])
    assert data["w"] == 1000 and len(data["c"]) > 150 and ["Delhi", "India", 28.61, 77.21] in data["cities"]


@pytest.mark.parametrize("text, countries, place", [
    ("TOP STORY  •  SAUDI ARABIA AND YEMEN", ["Saudi Arabia", "Yemen"], None),
    ("US tariffs hit Indian rice; talks in New Delhi", ["United States", "India"], "Delhi"),
    ("Storm heads for New Mexico and the Indian Ocean", [], "Indian Ocean"),
    ("Join us at the UK science fair", ["United Kingdom"], None),
    ("A Thanksgiving turkey and a sweet chile", [], None),
    ("Ships queue at the Strait of Hormuz", [], "Strait of Hormuz"),
    ("Rain again in Seattle", ["United States"], "Seattle"),
])
def test_places_named_in_the_news_are_found(text, countries, place):
    from ygc import world
    assert world.find(text) == (countries, place)


def test_a_storys_place_comes_from_play_where_or_its_words():
    w = play.where_of({"kicker": "WORLD  •  RUSSIA AND UKRAINE", "headline": "Talks"})
    assert w["countries"] == ["Russia", "Ukraine"] and w["place"] == ""
    w = play.where_of({"headline": "Anything"}, {"place": "Red Sea", "lat": 20, "lon": 38.5, "countries": ["Saudi Arabia", "Narnia"]})
    assert (w["place"], w["lat"], w["lon"], w["countries"]) == ("Red Sea", 20, 38.5, ["Saudi Arabia"])
    assert play.where_of({"headline": "A new robot can fold laundry"}) is None
    page = play.where_html(play.where_of({"headline": "Rain in Mumbai"}), heading=True)
    assert 'data-lat="19.08"' in page and "Mumbai" in page and "Where in the world?" in page


def test_play_where_is_checked():
    from ygc import checks
    good = dict(PLAY, where=[{"story": "lead", "place": "Pacific Ocean", "lat": 5, "lon": -160, "countries": []}])
    ed, issue = _little(good)
    r = checks.check_issue(ed, issue, "x/2026-10-10.json", archive=True)
    assert not [e for e in r.errors if "play" in e]
    ed, bad = _little(dict(PLAY, where=[{"story": "lead", "place": "", "lat": 95, "lon": "east", "countries": ["Narnia"]},
                                        {"story": "lead", "place": "Oslo", "lat": 59.9, "lon": 10.7, "countries": ["Norway"]},
                                        {"story": "mars", "place": "Mars", "lat": 0, "lon": 0}]))
    r = checks.check_issue(ed, bad, "x/2026-10-10.json", archive=True)
    errs = " ".join(r.errors)
    for needle in ("place is empty", "lat must be", "lon must be", "listed twice", "'mars'"):
        assert needle in errs, needle
    assert any("Narnia" in n for n in r.notes)


# ------------------------------------------------------------------ the printed QR code, the app, streaks and badges
def test_new_printed_papers_carry_a_qr_code_to_read_and_play(tmp_path):
    from pypdf import PdfReader
    from ygc import render
    cfg = dict(site.site_config(), base_url="https://example.org/news/", qr_from="2026-10-16")
    assert site.qr_url(cfg, "junior-daily", "2026-10-15") is None                  # published before: unchanged
    assert site.qr_url(cfg, "junior-daily", "2026-10-16") == "https://example.org/news/play/junior-daily/2026-10-16.html"
    assert site.qr_url(dict(cfg, base_url=""), "junior-daily", "2026-10-16") is None
    assert site.qr_url(dict(cfg, qr_from=""), "junior-daily", "2026-10-16") is None
    ed = edition.load("current-affairs-digest")                                     # the longest masthead
    issue = json.load(open(site.issues_of(ed)[0][1], encoding="utf-8"))
    with_qr = render.build(ed, issue, str(tmp_path / "a.pdf"), qr=site.qr_url(cfg, ed["id"], "2026-10-16"))
    without = render.build(ed, issue, str(tmp_path / "b.pdf"))
    first = lambda p: PdfReader(p).pages[0].extract_text()
    assert "SCAN TO READ & PLAY" in first(with_qr) and "SCAN TO READ" not in first(without)
    assert len(PdfReader(with_qr).pages) == len(PdfReader(without).pages)          # the code never moves a story


def test_older_papers_qr_codes_open_the_newest(tmp_path):
    play.build(str(tmp_path), site.site_config(), keep=1, log=lambda *a: None)
    ed = edition.load("young-global-citizen")
    (newest, _), (older, _) = site.issues_of(ed)[:2]
    page = (tmp_path / "play" / ed["id"] / f"{older}.html").read_text(encoding="utf-8")
    assert f'href="{newest}.html"' in page and "keeps the last week" in page and 'class="issue"' not in page


def test_read_and_play_installs_like_an_app_and_works_offline(built):
    from PIL import Image
    m = json.loads((built / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert m["display"] == "standalone" and m["start_url"] == "./index.html" and m["short_name"] == site.site_config()["title"]
    for i in m["icons"]:
        n = int(i["sizes"].split("x")[0])
        assert Image.open(built / i["src"]).size == (n, n)
    sw = (built / "sw.js").read_text(encoding="utf-8")
    core = json.loads(re.search(r"CORE = (\[.*?\]);", sw).group(1))
    assert re.search(r'const V = "rp-[0-9a-f]{12}"', sw) and "index.html" in core
    assert all((built / f.split("?")[0]).exists() for f in core)                    # every kept file is really there
    assert f"play.js?v={play.asset_version()}" in core
    assert sum("/" in f for f in core) == len([e for e in edition.list_editions() if site.issues_of(edition.load(e))])
    lobby = (built / "index.html").read_text(encoding="utf-8")
    assert 'rel="manifest"' in lobby and 'class="install"' in lobby and 'id="badges"' in lobby


def test_finishing_a_paper_shows_the_streak(built):
    ed = edition.load("little-explorers")
    page = (built / ed["id"] / f"{site.issues_of(ed)[0][0]}.html").read_text(encoding="utf-8")
    assert 'class="streak"' in page and 'href="../index.html#badges"' in page
    js = (built / "play.js").read_text(encoding="utf-8")
    for badge in ("First paper", "On fire", "Map explorer", "Word wizard", "Quiz champ"):
        assert badge in js


# ------------------------------------------------------------------ the easier version (papers for 12+)
EASY = {"headline": "Oil costs more", "body": [
    "The price of oil went above $110 for one barrel. A barrel is a big drum that holds oil. "
    "Most oil ships pass through a narrow sea called the Strait of Hormuz.",
    "Fewer ships are getting through right now. When less oil arrives, it costs more. "
    "That can make petrol and many other things cost more too, all around the world."]}


def _gcp():
    import copy
    ed = edition.load("global-citizen-plus")
    path = next(p for d, p in site.issues_of(ed) if d == "2026-10-18")
    issue = copy.deepcopy(json.load(open(path, encoding="utf-8")))
    issue.setdefault("play", {}).pop("easy", None)
    return ed, issue, path


def test_only_papers_for_twelve_and_up_ask_for_easier_versions():
    from ygc import prompt, skeleton
    young, older = edition.load("junior-daily"), edition.load("global-citizen-plus")
    assert not skeleton.wants_easy(young) and skeleton.wants_easy(older)
    assert "easy" not in skeleton.make(young, "2026-10-20", 9)["play"]
    assert set(skeleton.make(older, "2026-10-20", 9)["play"]["easy"]) == set(edition.story_blocks(older))
    assert "**Easier versions" in prompt.generate(older) and "**Easier versions" not in prompt.generate(young)


def test_easier_versions_keep_to_the_storys_facts():
    from ygc import checks
    ed, issue, path = _gcp()
    issue["play"]["easy"] = {"lead": EASY}
    errs = [e for e in checks.check_issue(ed, issue, path, archive=True).errors if "easy" in e]
    assert errs == [], errs                                               # $110 rounds the story's $109.86
    bad = json.loads(json.dumps(EASY))
    bad["body"][1] += " Prices rose 55 percent in a week."
    issue["play"]["easy"] = {"lead": bad, "mars": EASY, "world": {"headline": "x", "body": ["Too short."]}}
    errs = " ".join(checks.check_issue(ed, issue, path, archive=True).errors)
    for needle in ("number 55 isn't in the story", "easy.mars: not a story", "easy.world.body: 2 to 5"):
        assert needle in errs, needle
    long = {"headline": "Oil", "body": [" ".join(["This sentence goes on and on without a single stop"] * 3) + ".",
                                        "It keeps going on and on and on and on and on and on and on and on and on."]}
    issue["play"]["easy"] = {"lead": long}
    assert any("sentences average" in e for e in checks.check_issue(ed, issue, path, archive=True).errors)


def test_a_story_with_an_easier_version_gets_the_button():
    ed, issue, _ = _gcp()
    issue["play"]["easy"] = {"lead": EASY}
    secs, _, _ = play.sections(ed, issue, "2026-10-18")
    html_ = {b: h for _, b, h, _ in secs}
    lead, other = html_["lead"], html_[next(b for b in html_ if b not in ("lead", "briefs", "words")
                                            and "class=\"easy\"" not in html_[b])]
    assert 'class="easy" aria-pressed="false"' in lead and 'class="v-easy" hidden' in lead
    assert '<div class="text v-easy" hidden>' in lead and 'class="text v-orig"' in lead
    assert "Oil costs more" in lead and 'class="easy"' not in other and "v-orig" not in other


def test_new_games_get_their_data_and_numbers_are_checked(built):
    """Map hunt plays from play.where, Guess the number from play.numbers; both reach the page."""
    from ygc import checks
    ed = edition.load("breakfast-table")
    date, path = site.issues_of(ed)[0]
    page = (built / "breakfast-table" / f"{date}.html").read_text(encoding="utf-8")
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert 'data-band="Ages 9–11"' in page
    assert data["where"] and all({"lat", "lon", "place", "countries", "names", "h"} <= set(w) for w in data["where"])
    assert data["numbers"] and all(n["min"] < n["answer"] < n["max"] for n in data["numbers"])
    issue = json.load(open(path, encoding="utf-8"))
    stories = set(edition.story_blocks(ed))
    r = checks.Report()
    checks.check_numbers(issue, issue["play"]["numbers"], stories, r)
    assert not r.errors
    bad = json.loads(json.dumps(issue["play"]["numbers"]))
    bad[0]["answer"] = 9999                                   # not in the story, and outside the slider
    bad[1]["min"], bad[1]["max"] = bad[1]["answer"] - 0.01, bad[1]["answer"] * 100
    r = checks.Report()
    checks.check_numbers(issue, bad, stories, r)
    assert any("isn't a number in the story" in e or "min < answer < max" in e for e in r.errors)
    assert any("well inside the range" in e for e in r.errors)


def test_badges_come_with_a_certificate_page(built):
    cert = (built / "certificate.html").read_text(encoding="utf-8")
    assert 'class="certpage"' in cert and 'class="cert"' in cert and "Print certificate" in cert
    js = (built / "play.js").read_text(encoding="utf-8")
    for badge in ("pins", "nums", "set1", "set5", "clean"):                   # the new games' badges
        assert f'B("{badge}"' in js
    assert "function hunt()" in js and "function numbers()" in js and "unproj(" in js
