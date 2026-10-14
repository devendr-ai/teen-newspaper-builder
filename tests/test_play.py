"""Read & Play: the children's side of the site, built from the same issues as the PDFs."""
import json
import os
import re
import shutil

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
    assert 'href="../play/play.css"' in lobby and (built / "play.css").exists() and (built / "play.js").exists()


def test_a_young_readers_issue_reads_one_story_per_screen_with_words_to_tap(built):
    ed = edition.load("little-explorers")
    date = site.issues_of(ed)[0][0]
    page = (built / "little-explorers" / f"{date}.html").read_text(encoding="utf-8")
    assert 'data-mode="cards"' in page and 'class="read"' in page and 'id="game"' in page
    data = json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', page, re.S).group(1))
    assert len(data["vocab"]) == 3 and all(v["meaning"] and "Today" not in v["meaning"] for v in data["vocab"])
    assert page.count('class="w"') >= 1                              # new words highlighted in the stories
    assert "For grown-ups: sources" in page and 'href="../../play/play.css"' in page
    assert 'href="../../e/little-explorers/index.html"' in page          # back to the print side
    if shutil.which("pdftoppm"):
        assert any(f.endswith(".png") for f in os.listdir(built / "little-explorers"))


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
    assert "play" not in skeleton.make(ed, "2026-10-17", 2, play=False)
    assert "**Play (online only" in prompt.generate(ed)
    assert "**Play (online only" not in chat.instructions(ed, "2026-10-17") and '"play"' not in chat.instructions(ed, "2026-10-17")
    assert skeleton.play_counts(edition.load("current-affairs-digest")) == (8, 4)


def test_the_page_carries_the_games_and_links_answers_to_their_story(tmp_path):
    ed, issue = _little(PLAY)
    secs, data = play.sections(ed, issue, "2026-10-10", str(tmp_path))
    assert [q["answer"] for q in data["quiz"]] == [1, 0, 1] and [f["true"] for f in data["facts"]] == [True, False]
    bids = [b for _, b, _ in secs]
    assert data["quiz"][0]["card"] == bids.index("lead") and data["facts"][1]["card"] == bids.index("science_and_technology")
    _, plain_data = play.sections(*_little({})[0:2], "2026-10-10", str(tmp_path))
    assert plain_data["quiz"] == [] and plain_data["facts"] == []
