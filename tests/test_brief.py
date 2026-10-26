"""The car-ride brief: a two-host script in The Breakfast Table, its audio and podcast feed, and the
compact player on Read & Play (never on the home page)."""
import copy
import json
import os
import re
import shutil
import socket
import subprocess
import threading
import xml.etree.ElementTree as ET
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ygc import brief, checks, edition, narration, play, prompt, site, skeleton

ROOT = edition.ROOT
ISSUE = os.path.join(ROOT, "editions", "breakfast-table", "issues", "2026", "2026-10-26.json")


def issue():
    return json.load(open(ISSUE, encoding="utf-8"))


def errors(i):
    r = checks.Report()
    brief.check(i, i["play"]["brief"], r)
    return r.errors


def test_only_papers_that_opt_in_get_a_brief():
    bt, jd = edition.load("breakfast-table"), edition.load("junior-daily")
    assert brief.wants(bt) and not brief.wants(jd)
    assert "brief" in skeleton.play_skeleton(bt) and "brief" not in skeleton.play_skeleton(jd)
    assert "Car-ride brief" in prompt.generate(bt) and "Car-ride brief" not in prompt.generate(jd)


def test_the_published_brief_passes_and_uses_only_the_issues_facts():
    assert errors(issue()) == []


@pytest.mark.parametrize("change, message", [
    (lambda b: b["lines"][6].update(text="Brent closed at $999 a barrel."), "the number 999 isn't in this issue"),
    (lambda b: [ln.update(who="maya") for ln in b["lines"]], "both hosts"),
    (lambda b: b["lines"][1].update(who="bob"), "who must be one of"),
    (lambda b: b["lines"][1].update(text="word " * 80), "keep each turn"),
    (lambda b: b["lines"][2].update(chapter="A chapter label that is far too long"), "at most 22 characters"),
    (lambda b: [ln.pop("chapter", None) for ln in b["lines"]], "chapters"),
    (lambda b: b.update(lines=b["lines"][:8]), "words; write 300 to 600"),
    (lambda b: b["lines"][3].update(text="See www.example.com for more."), "no web addresses"),
])
def test_the_check_catches_a_bad_script(change, message):
    i = copy.deepcopy(issue())
    change(i["play"]["brief"])
    assert any(message in e for e in errors(i)), errors(i)


def test_the_full_check_runs_the_brief_check():
    i = copy.deepcopy(issue())
    i["play"]["brief"]["lines"][6]["text"] = "Brent closed at $999 a barrel."
    r = checks.Report()
    checks.check_play(edition.load("breakfast-table"), i, r)
    assert any("999" in e for e in r.errors)


class Tone:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, voice):
        self.calls.append(voice)
        return b"\x10\x00" * 2400, 24000


@pytest.fixture
def encoder():
    found = shutil.which("ffmpeg")
    if not found:
        pytest.skip("ffmpeg needed for audio encoding")
    return found


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    play.build(str(out), site.site_config(), keep=2, log=lambda *a: None)
    return out


def test_read_and_play_has_the_slot_and_the_script_but_not_the_home_page(built):
    lobby = (built / "play" / "index.html").read_text(encoding="utf-8")
    assert '<section class="brief" id="brief" data-src="briefs/latest.json"' in lobby
    assert lobby.index('id="brief"') > lobby.index('id="h-today"')
    data = json.loads((built / "play" / "briefs" / "2026-10-26.json").read_text(encoding="utf-8"))
    assert data["name"] == "The Breakfast Table" and data["chapters"][0] == "Riyadh & oil"
    assert {ln["name"] for ln in data["lines"]} == {"Maya", "Sam"}
    js = (built / "play" / "play.js").read_text(encoding="utf-8")
    assert "Car-ride brief" in js and "mediaSession" in js and "brief/started" in js and "brief/finished" in js


def test_audio_latest_and_podcast_feed(tmp_path, built, encoder):
    s = tmp_path / "site"
    shutil.copytree(built, s)
    (s / "play" / "audio").mkdir(exist_ok=True)
    cache, tone = tmp_path / "cache", Tone()
    _, recordings, made = narration.briefs(s, cache, lambda: tone, encoder, latest_only=True, log=lambda *a: None)
    assert made == 1 and set(tone.calls) == {"af_heart", "am_michael"}
    latest = json.loads((s / "play" / "briefs" / "latest.json").read_text(encoding="utf-8"))
    assert (s / "play" / latest["audio"]).stat().st_size == latest["bytes"] > 0
    starts = [ln["start"] for ln in latest["lines"]]
    assert starts == sorted(starts) and starts[0] > 0                     # a chime first, then each line in order
    assert [m["title"] for m in latest["marks"]] == latest["chapters"] and latest["duration"] > starts[-1]
    rss = ET.parse(s / "play" / "podcast.xml").getroot()
    item = rss.find("channel/item")
    assert item.find("enclosure").get("url").endswith(latest["audio"].split("/")[-1])
    assert item.find("enclosure").get("type") == "audio/mpeg" and "Riyadh & oil" in item.find("title").text
    assert rss.find("channel/title").text.endswith("The Breakfast Table Brief")
    calls = len(tone.calls)                                                 # a rebuild reuses the cached recording
    narration.briefs(s, cache, lambda: tone, encoder, latest_only=True, log=lambda *a: None)
    assert len(tone.calls) == calls and recordings


def test_narration_keeps_brief_audio_in_the_cache(tmp_path, built, encoder):
    s = tmp_path / "site"
    shutil.copytree(built, s)
    cache, tone = tmp_path / "cache", Tone()
    for f in (s / "play").rglob("*.html"):            # no story narration here: only the brief
        f.write_text("<html><head></head><body></body></html>", encoding="utf-8")
    narration.build(s, cache, engine_factory=lambda: tone, ffmpeg=encoder, log=lambda *a: None, latest_only=True)
    assert list((cache / "sentences").glob("*.wav")) and list((cache / "recordings").glob("*.mp3"))
    assert (s / "play" / "briefs" / "latest.json").exists()


class Ranges(SimpleHTTPRequestHandler):
    """Like a real web host: the audio can be seeked (HTTP range requests)."""
    def log_message(self, *a):
        pass

    def send_head(self):
        rng, path = self.headers.get("Range"), self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m, size = re.match(r"bytes=(\d*)-(\d*)", rng), os.path.getsize(path)
        start, end = int(m[1] or 0), min(int(m[2]) if m[2] else size - 1, size - 1)
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.left = end - start + 1
        return f

    def copyfile(self, src, out):
        left = getattr(self, "left", None)
        if left is None:
            return super().copyfile(src, out)
        while left > 0:
            chunk = src.read(min(65536, left))
            if not chunk:
                break
            out.write(chunk)
            left -= len(chunk)


def test_the_player_in_a_real_browser(tmp_path, encoder):
    from test_kids_mode import _browser
    found = _browser()
    if not found:
        pytest.skip("Playwright with Chromium isn't installed")
    node, env = found
    out = tmp_path / "site"
    real = site.issues_of
    mp = pytest.MonkeyPatch()
    mp.setattr(site, "issues_of", lambda ed: real(ed)[:2])
    site.build(str(out), keep=2, log=lambda *a: None)
    mp.undo()
    narration.briefs(out, tmp_path / "cache", lambda: Tone(), encoder, latest_only=True, log=lambda *a: None)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Ranges, directory=str(out)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        r = subprocess.run([node, os.path.join(ROOT, "tests", "brief-player.cjs"), f"http://127.0.0.1:{port}/"],
                           env=env, capture_output=True, text=True, timeout=300)
    finally:
        server.shutdown()
    report = json.loads(r.stdout[r.stdout.index("["):]) if "[" in r.stdout else []
    failed = [x for x in report if not x["pass"]]
    assert r.returncode == 0 and report and not failed, (failed, r.stderr[-1500:])
