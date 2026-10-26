"""Inline thread history: publication dates, age safety and continuous reading."""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ygc import edition, narration, play, site, story_timeline, threads


def report(date, headline=None, paper="paper", band="Ages 9–11", block="lead"):
    return {"paper": paper, "block": block, "band": band, "date": date, "edition": paper,
            "headline": headline or date, "deck": "A published summary.", "body": ["The original report."], "sources": []}


def recent(reports, **kwargs):
    return story_timeline.recent(reports, kwargs.pop("thread", {}), "paper", "lead", "Ages 9–11",
                                 "2026-10-26", "younger", **kwargs)


def test_history_is_thirty_days_of_publication_with_no_future_or_wrong_age():
    items = [report("2026-09-26"), report("2026-09-27"), report("2026-10-26"), report("2026-10-27"),
             report("2026-10-20", band="Ages 6–8"), report("2026-10-21", band="Ages 12–14")]
    result = recent(items)
    assert [r["date"] for r in result] == ["2026-09-27", "2026-10-26"]
    assert result[-1]["current"]
    assert recent([report("2026-10-26")]) == []


def test_prefers_same_edition_and_story_and_collapses_repeated_headlines():
    items = [report("2026-10-01", "Earlier"), report("2026-10-20", "Repeated"),
             report("2026-10-21", "Repeated"), report("2026-10-26", "Wrong edition", paper="aaa"),
             report("2026-10-26", "Wrong block", block="world"), report("2026-10-26", "This story")]
    result = recent(items)
    assert [r["headline"] for r in result] == ["Earlier", "Repeated", "This story"]
    assert result[1]["date"] == "2026-10-21"
    assert recent([report("2026-10-01", "Same"), report("2026-10-26", "Same")]) == []


def test_limits_history_preserves_first_latest_and_uses_only_edited_age_matched_changes():
    items = [report(f"2026-10-{i:02d}") for i in range(1, 27)]
    thread = {"timeline": [{"date": "2026-10-01", "reported": "2026-10-26",
                            "younger": "An edited development.", "older": "Older-only text."}]}
    result = recent(items, thread=thread)
    assert len(result) == 6
    assert result[0]["date"] == "2026-10-01" and result[-1]["date"] == "2026-10-26"
    assert result[-1]["change"] == "An edited development."
    assert not any(r["change"] for r in result[:-1])


def test_only_explicit_editorial_thread_membership_enters_the_catalog():
    issue = {"blocks": {"lead": {"headline": "Linked", "body": ["Facts."]},
                         "world": {"headline": "Similar words but not linked", "body": ["Facts."]}}}
    result = story_timeline.catalog([("paper", "2026-10-26", issue)], {("paper", "2026-10-26", "lead"): "topic"},
                                   {"paper": "Ages 9–11"}, {"paper": "A paper"})
    assert list(result) == ["topic"] and len(result["topic"]) == 1
    assert result["topic"][0]["headline"] == "Linked"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("timeline-site")
    play.build(str(out), site.site_config(), keep=2, log=lambda *a: None)
    return out


def test_secondary_story_has_its_own_closed_thread_and_old_reports_are_not_stubs(built):
    markup = (built / "play/current-affairs-digest/2026-10-26.html").read_text()
    assert 'class="follow-thread" data-thread="lead"' in markup
    assert 'class="follow-thread" data-thread="world"' in markup
    assert not re.search(r'<details class="follow-thread"[^>]*\bopen\b', markup)
    assert not re.search(r'<details class="follow-thread" data-thread="science_and_technology"', markup)
    # Older than the two retained full issue pages, but the original text is available inline.
    dates = re.findall(r'data-thread-date="([\d-]+)"', markup)
    assert min(dates) < "2026-10-25"
    assert "data-thread-report hidden" in markup and "Earlier report · Published" in markup
    assert 'data-mode="scroll"' in markup
    assert markup.count('id="s-world"') == 1 and markup.count('id="s-lead"') == 1


def test_timeline_does_not_change_narration_sentences_or_story_order():
    ed = edition.load("current-affairs-digest")
    date, path = site.issues_of(ed)[0]
    issue = json.loads(Path(path).read_text())
    chip = {"title": "A thread", "href": "../threads/topic.html",
            "updates": recent([report("2026-10-01"), report("2026-10-26")])}
    before, _ = play.issue_page(site.site_config(), ed, site.audience(ed), issue, date, [date])
    after, _ = play.issue_page(site.site_config(), ed, site.audience(ed), issue, date, [date], {"lead": chip, "world": chip})
    parsers = [narration.Sentences(), narration.Sentences()]
    parsers[0].feed(before); parsers[1].feed(after)
    assert parsers[0].cards == parsers[1].cards
    assert re.findall(r'id="s-([^"]+)"', before) == re.findall(r'id="s-([^"]+)"', after)
    malicious = copy.deepcopy(chip)
    malicious["updates"][0]["headline"] = '<script>alert("x")</script>'
    malicious["updates"][0]["sources"] = ["javascript:alert(1)"]
    html = story_timeline.render(malicious, "world")
    assert '<script>' not in html and 'href="javascript:' not in html


def test_reader_timeline_in_browser(built):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    env = dict(os.environ)
    try:
        subprocess.run([node, "-e", "require('playwright')"], env=env, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pytest.skip("Playwright not installed")
    handler = partial(SimpleHTTPRequestHandler, directory=str(built))
    handler.log_message = lambda *args: None
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        result = subprocess.run([node, str(Path(__file__).with_name("story-timeline.cjs")), f"http://127.0.0.1:{port}/"],
                                env=env, text=True, capture_output=True, timeout=180)
    finally:
        server.shutdown()
    assert result.returncode == 0, result.stdout + result.stderr
