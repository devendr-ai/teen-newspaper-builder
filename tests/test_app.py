"""The iPhone/iPad app's side of the website: the app build's Listen tab, For parents → This app, the
bridge (assets/app/app.js), listen.json from the narration step, and the offline pack (ygc/apppack.py)."""
import json
import os
import re
import socket
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ygc import apppack, edition, listen, narration, site

ROOT = edition.ROOT


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


class Tone:
    def synthesize(self, text, voice):
        return b"\x10\x00" * 2400, 24000


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg needed for audio encoding")
    tmp = tmp_path_factory.mktemp("app")
    real = site.issues_of
    mp = pytest.MonkeyPatch()
    mp.setattr(site, "issues_of", lambda ed: real(ed)[:2])
    web, app = tmp / "web", tmp / "app"
    site.build(str(web), log=lambda *a: None)
    site.build(str(app), keep=2, log=lambda *a: None, kids=True)
    mp.undo()
    narration.build(app, tmp / "cache", engine_factory=Tone, log=lambda *a: None, latest_only=True)
    return web, app


def test_the_app_build_has_listen_and_the_website_does_not(builds):
    web, app = builds
    home, lobby = (app / "index.html").read_text(encoding="utf-8"), (app / "play" / "index.html").read_text(encoding="utf-8")
    assert 'href="play/listen.html"' in home and 'href="builder.html"' not in home.split('<nav class="tabbar"')[1]
    assert 'href="../play/listen.html" data-view="listen"' in lobby
    assert (app / "play" / "listen.html").exists() and (app / "app.js").exists()
    assert '<script src="app.js"></script>' in home
    whome = (web / "index.html").read_text(encoding="utf-8")
    assert "listen.html" not in whome and "app.js" not in whome and 'href="builder.html"' in whome
    assert not (web / "play" / "listen.html").exists() and not (web / "app.js").exists()
    assert 'data-view="listen"' not in (web / "play" / "index.html").read_text(encoding="utf-8")


def test_for_parents_has_the_app_box_only_in_the_app(builds):
    web, app = builds
    doc = (app / "parents.html").read_text(encoding="utf-8")
    assert '<section class="np-appbox" id="np-app" hidden' in doc and 'id="np-rem-on"' in doc
    assert 'class="parent-link" href="builder.html"' in doc                 # Design stays in the app
    assert 'data-gate-pages="feedback.html builder.html play/report.html"' in doc
    assert "np-appbox" not in (web / "parents.html").read_text(encoding="utf-8")


def test_listen_json_lists_the_recorded_briefs_and_papers(builds):
    _, app = builds
    data = json.loads((app / "play" / "listen.json").read_text(encoding="utf-8"))
    assert data["briefs"] and data["briefs"][0]["audio"].startswith("audio/") and data["briefs"][0]["chapters"]
    assert data["papers"] and all(p["tracks"] for p in data["papers"])
    for p in data["papers"]:
        assert (app / "play" / p["href"]).exists() and p["band"].startswith("Ages ")
        for t in p["tracks"]:
            assert (app / "play" / t["src"]).exists() and t["title"] and t["duration"] > 0
    first = data["papers"][0]
    page = (app / "play" / first["href"]).read_text(encoding="utf-8")
    assert first["tracks"][0]["title"].lower() in re.sub(r"<[^>]+>", "", page).lower()


def test_card_titles_follow_the_page():
    src = ('<section class="card story" data-i="0"><h2>One</h2></section><section class="card feature">'
           '<h2 class="x">TALK <b>ABOUT</b> IT</h2></section><section class="card end"></section>')
    assert listen.card_titles(src) == ["One", "TALK ABOUT IT", ""]


def test_the_pack_trims_and_lists_every_file(builds, tmp_path):
    import shutil
    _, app = builds
    pack = tmp_path / "pack"
    shutil.copytree(app, pack)
    (pack / "play" / "audio" / ("0" * 64 + ".mp3")).write_bytes(b"an older issue's recording")
    m = apppack.pack(str(pack), log=lambda *a: None)
    for gone in ("share", "404.html", "play/podcast.xml"):
        assert not (pack / gone).exists() and gone not in m["files"]
    assert "builder.html" in m["files"] and any(f.startswith("vendor/pyodide/") for f in m["files"])   # Design works offline
    data = json.loads((pack / "play" / "listen.json").read_text(encoding="utf-8"))
    heard = {b["audio"] for b in data["briefs"]} | {t["src"] for p in data["papers"] for t in p["tracks"]}
    kept = {f[len("play/"):] for f in m["files"] if f.startswith("play/audio/") and f.endswith(".mp3")}
    assert heard <= kept and ("audio/" + "0" * 64 + ".mp3") not in kept      # older issues' audio left out
    on_disk = {str(p.relative_to(pack)).replace(os.sep, "/") for p in pack.rglob("*") if p.is_file()} - {"manifest.json"}
    assert set(m["files"]) == on_disk and m["start"] == "index.html" and m["v"] == 1
    rel, (h, size) = next(iter(m["files"].items()))
    assert size == (pack / rel).stat().st_size and h == apppack.digest(pack / rel)
    assert json.loads((pack / "manifest.json").read_text())["id"] == m["id"]
    missing = []                                       # every link inside the app goes to a file the app has
    for page in pack.rglob("*.html"):
        for u in re.findall(r'(?:href|src)="([^"#?]+)', page.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", u) or "${" in u:
                continue
            if not (page.parent / u).resolve().exists():
                missing.append((str(page.relative_to(pack)), u))
    assert not missing, missing[:10]
    assert apppack.pack(str(pack), log=lambda *a: None)["id"] == m["id"]     # the same files, the same id


def test_the_bridge_in_a_real_browser(builds):
    from test_kids_mode import _browser
    found = _browser()
    if not found:
        pytest.skip("Playwright with Chromium isn't installed")
    node, env = found
    _, app = builds
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(Quiet, directory=str(app)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        r = subprocess.run([node, os.path.join(ROOT, "tests", "app-bridge.cjs"), f"http://127.0.0.1:{port}/"],
                           env=env, capture_output=True, text=True, timeout=300)
    finally:
        server.shutdown()
    report = json.loads(r.stdout[r.stdout.index("["):]) if "[" in r.stdout else []
    failed = [x for x in report if not x["pass"]]
    assert r.returncode == 0 and report and not failed, (failed, r.stderr[-1500:])


def test_the_deploys_build_the_pack():
    for wf in ("pages.yml", "daily.yml"):
        text = Path(ROOT, ".github", "workflows", wf).read_text(encoding="utf-8")
        assert "bash tools/app_pack.sh" in text
    script = Path(ROOT, "tools", "app_pack.sh").read_text(encoding="utf-8")
    assert "site --kids --keep 7" in script and "app-pack" in script and "_site/app" in script


def test_the_app_points_at_the_pack():
    src = Path(ROOT, "mobile", "src", "content.ts").read_text(encoding="utf-8")
    base = re.search(r"BASE = '([^']+)'", src).group(1)
    assert base == site.site_config()["base_url"].rstrip("/") + "/app/"
    cfg = json.loads(Path(ROOT, "mobile", "app.json").read_text(encoding="utf-8"))["expo"]
    assert cfg["name"] == "News Pebbles" and cfg["ios"]["supportsTablet"] is True
    audio = next(p for p in cfg["plugins"] if isinstance(p, list) and p[0] == "expo-audio")[1]
    assert audio["enableBackgroundPlayback"] is True and audio["microphonePermission"] is False
    assert cfg["android"]["package"] == cfg["ios"]["bundleIdentifier"] == "com.newspebbles.app"
    assert "android.permission.RECORD_AUDIO" in cfg["android"]["blockedPermissions"]


def test_the_app_builds_for_google_play():
    eas = json.loads(Path(ROOT, "mobile", "eas.json").read_text(encoding="utf-8"))
    assert eas["build"]["production"]["android"]["buildType"] == "app-bundle"
    assert eas["build"]["preview"]["android"]["buildType"] == "apk"
    assert eas["submit"]["production"]["android"]["track"] == "alpha"          # closed testing
    app = Path(ROOT, "mobile", "App.tsx").read_text(encoding="utf-8")
    assert "hardwareBackPress" in app and "case 'openPdf'" in app and "Sharing.shareAsync" in app
    listing = Path(ROOT, "mobile", "store", "play-listing.md").read_text(encoding="utf-8")
    short = re.search(r"Short description \(80 max\):\*\*\n\n```\n(.+)\n```", listing).group(1)
    assert len(short) <= 80 and "Data safety" in listing and "12 testers" in listing
