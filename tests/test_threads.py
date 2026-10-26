"""The story so far: big ongoing stories, one page each, for younger and older readers."""
import copy
import datetime as dt
import json
import os
import re
import subprocess
import sys

import pytest
from pypdf import PdfReader

from ygc import checks, edition, play, render, site, threads

ROOT = edition.ROOT


def test_every_thread_passes_its_checks():
    ts = threads.load_all()
    assert {t["id"] for t in ts} >= {"yemen-war", "russia-ukraine"}
    for t in ts:
        assert os.path.exists(threads.path(t["id"]))
        r = threads.check(t)
        assert r.ok, (t["id"], r.errors)
    out = subprocess.run([sys.executable, "-m", "ygc", "thread"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0 and "PASS" in out.stdout


def test_thread_checks_catch_mistakes():
    t = copy.deepcopy(json.load(open(threads.path("yemen-war"), encoding="utf-8")))
    t["id"] = "Yemen War"
    del t["older"]
    t["younger"]["one_minute"] = "word " * 80
    t["younger"]["who"] = t["younger"]["who"][:1]
    t["timeline"] = t["timeline"][::-1]
    t["timeline"][0]["reported"] = "2001-01-01"
    t["timeline"].append({"date": "2999-01-01", "older": "Far future."})
    t["sources"] = []
    errs = " ".join(threads.check(t, as_of=dt.date(2026, 10, 15)).errors)
    for needle in ("lower-case words", "older: missing", "one_minute: 80 words", "2 to 6", "oldest first",
                   "reported", "in the future", "sources"):
        assert needle in errs, needle


def _issue(eid="junior-daily"):
    ed = edition.load(eid)
    date, p = next((d, p) for d, p in site.issues_of(ed) if d == "2026-10-15")
    return ed, json.load(open(p, encoding="utf-8")), p


def test_an_issue_links_stories_to_threads(tmp_path):
    ed, issue, p = _issue()
    issue["threads"] = {"lead": "yemen-war"}
    r = checks.check_issue(ed, issue, p, archive=True)
    assert not [e for e in r.errors if "threads" in e]
    issue["threads"] = {"lead": "no-such-thread", "vocab": "yemen-war"}
    errs = " ".join(checks.check_issue(ed, issue, p, archive=True).errors)
    assert "no thread 'no-such-thread'" in errs and "threads.vocab: not a story" in errs


def test_a_linked_story_prints_a_pointer_to_the_story_so_far(tmp_path):
    ed, issue, _ = _issue()
    plain = render.build(ed, issue, str(tmp_path / "a.pdf"))
    issue["threads"] = {"lead": "yemen-war"}
    linked = render.build(ed, issue, str(tmp_path / "b.pdf"))
    text = lambda p: " ".join(pg.extract_text() for pg in PdfReader(p).pages)
    assert "The story so far" in text(linked) and "The story so far" not in text(plain)


def test_levels_and_activity():
    assert threads.level_of("Ages 6–8") == threads.level_of("Ages 9–11") == "younger"
    assert threads.level_of("Ages 12–14") == threads.level_of("Ages 15+") == "older"
    t = {"timeline": [{"date": "2026-10-01"}], "opened": "2026-10-01"}
    assert threads.is_active(t, "2026-10-08") and not threads.is_active(t, "2026-10-09")
    assert threads.is_active(t, "2026-10-20", ["2026-10-15"])                 # a linked story keeps it going
    idx = threads.story_index([("junior-daily", "2026-10-16", {"threads": {"lead": "yemen-war"}})])
    assert idx[("junior-daily", "2026-10-16", "lead")] == "yemen-war"
    assert idx[("current-affairs-digest", "2026-10-10", "lead")] == "yemen-war"   # from the thread's own list


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    play.build(str(out), site.site_config(), keep=1000, log=lambda *a: None)   # every page, so dated tests stay valid
    return out / "play"


def test_read_and_play_has_a_page_per_thread_and_level(built):
    for tid in ("yemen-war", "russia-ukraine"):
        young = (built / "threads" / f"{tid}.html").read_text(encoding="utf-8")
        older = (built / "threads" / f"{tid}-more.html").read_text(encoding="utf-8")
        t = json.load(open(threads.path(tid), encoding="utf-8"))
        assert play.clean(t["younger"]["one_minute"])[:60] in young and play.clean(t["older"]["one_minute"])[:60] in older
        assert 'href="' + tid + '-more.html"' in young and 'href="' + tid + '.html"' in older   # Easier / More detail
        assert 'class="where"' in young and "Show earlier days" in young and "If this news worries you" in young
        for page in (young, older):                                   # every Read it opens a kept story card
            for href in re.findall(r'href="\.\./([a-z-]+/[\d-]+\.html)#(s-[a-z_]+)"', page):
                assert f'id="{href[1]}"' in (built / href[0]).read_text(encoding="utf-8")
    assert "Big stories" in (built / "threads" / "index.html").read_text(encoding="utf-8")


def test_linked_stories_show_the_way_in_at_the_readers_level(built):
    jd = (built / "junior-daily" / "2026-10-15.html").read_text(encoding="utf-8")       # ages 9-11
    ygc = (built / "young-global-citizen" / "2026-10-15.html").read_text(encoding="utf-8")  # 12-14
    assert 'class="tchip" href="../threads/yemen-war.html"' in jd
    assert 'class="tchip" href="../threads/yemen-war-more.html"' in ygc
    lobby = (built / "index.html").read_text(encoding="utf-8")
    shown = re.findall(r'data-old="threads/([a-z0-9-]+)-more\.html"', lobby)        # the active threads, older readers' links
    assert len(shown) <= threads.MAX_ACTIVE and all(threads.exists(t) for t in shown)


def _coverage(paper, date, headline, linked=False):
    issue = {"blocks": {"world": {"headline": headline, "body": ["Published report."]}}}
    if linked:
        issue["threads"] = {"world": "elections"}
    return paper, date, issue


def test_recurring_review_counts_distinct_days_not_editions_or_future_reports():
    same_day = [_coverage(f"paper-{i}", "2026-10-26", "Early voting grows") for i in range(5)]
    assert threads.recurring_gaps(same_day, "2026-10-26", index={}) == []
    reports = [_coverage("paper", "2026-10-20", "Early voting starts"),
               _coverage("paper", "2026-10-23", "Early voting grows"),
               _coverage("paper", "2026-10-26", "Early voting expands"),
               _coverage("paper", "2026-10-19", "Early voting opens"),
               _coverage("paper", "2026-10-27", "Early voting continues")]
    result = threads.recurring_gaps(reports, "2026-10-26", index={})
    assert len(result) == 1 and result[0]["topic_hint"] == "early voting"
    assert result[0]["days_in_last_seven"] == 3 and result[0]["unlinked_stories"] == 3
    assert result[0]["first_report"] == "2026-10-20" and result[0]["latest_report"] == "2026-10-26"
    assert result[0]["existing_threads"] == []


def test_recurring_review_suggests_existing_threads_and_never_assigns_topics():
    reports = [_coverage("paper", f"2026-10-{day}", f"Early voting {word}")
               for day, word in [(21, "starts"), (23, "grows"), (26, "expands")]]
    before = copy.deepcopy(reports)
    linked = {("paper", "2026-10-21", "world"): "us-midterms-2026"}
    rows = threads.recurring_gaps(reports, "2026-10-26", index=linked)
    assert rows[0]["existing_threads"] == ["us-midterms-2026"]
    assert rows[0]["unlinked_stories"] == 2
    assert reports == before
    fully_linked = {(p, d, "world"): "us-midterms-2026" for p, d, _ in reports}
    assert threads.recurring_gaps(reports, "2026-10-26", index=fully_linked) == []


def test_election_thread_links_published_reports_at_all_four_reading_bands():
    t = next(t for t in threads.load_all() if t["id"] == "us-midterms-2026")
    bands = set()
    for reference in t["stories"]:
        ed = edition.load(reference["paper"])
        path = next(path for date, path in site.issues_of(ed) if date == reference["date"])
        issue = json.load(open(path, encoding="utf-8"))
        assert issue["blocks"][reference["block"]]["headline"]
        bands.add(site.audience(ed))
    assert bands == {"Ages 6–8", "Ages 9–11", "Ages 12–14", "Ages 15+"}
    assert {s["date"] for s in t["stories"] if "2026-10-20" <= s["date"] <= "2026-10-26"} >= {"2026-10-21", "2026-10-23", "2026-10-26"}


def test_election_thread_badge_is_built_for_secondary_and_younger_stories(built):
    for paper, date, block in [("breakfast-table", "2026-10-26", "us"),
                               ("little-explorers", "2026-10-24", "us"),
                               ("junior-explorer", "2026-10-24", "lead")]:
        page = (built / paper / f"{date}.html").read_text(encoding="utf-8")
        assert f'class="follow-thread" data-thread="{block}"' in page
        assert "US midterm elections" in page
    assert (built / "threads/us-midterms-2026.html").exists()
    assert (built / "threads/us-midterms-2026-more.html").exists()
