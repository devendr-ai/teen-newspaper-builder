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
