"""The app build (python -m ygc site --kids) for Apple's Kids Category and Google Play Families:
no request to any other host, and a Parental Gate before links out, email, share, print and the
parents' pages. The public website must be exactly as before: no gate, visit counting on, the
embedded feedback form. Both builds serve their own fonts and Pyodide."""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ygc import edition, kids, site, vendor

ROOT = edition.ROOT
OUTSIDE = re.compile(r"fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr|goatcounter\.com/count|<iframe")


@pytest.fixture(scope="module")
def builds(tmp_path_factory):
    real = site.issues_of
    mp = pytest.MonkeyPatch()
    mp.setattr(site, "issues_of", lambda ed: real(ed)[:2])           # two issues a paper: every page type, quickly
    out = {}
    for mode in ("web", "kids"):
        out[mode] = tmp_path_factory.mktemp(mode) / "site"
        site.build(str(out[mode]), keep=2, log=lambda *a: None, kids=(mode == "kids"))
    mp.undo()
    return out


def pages(root):
    for dp, _, fs in os.walk(root):
        for f in fs:
            if f.endswith((".html", ".css", ".js")):
                p = os.path.join(dp, f)
                yield os.path.relpath(p, root).replace(os.sep, "/"), open(p, encoding="utf-8", errors="ignore").read()


def loads_elsewhere(doc):
    """Requests a page makes by itself when it loads: src=, <link> (not canonical/alternate), CSS url()."""
    hits = re.findall(r'<(?:script|img|iframe|source|audio|video|embed)\b[^>]*\bsrc="((?:https?:)?//[^"]+)"', doc)
    for tag in re.findall(r"<link\b[^>]*>", doc):
        h, r = re.search(r'href="((?:https?:)?//[^"]+)"', tag), re.search(r'rel="([^"]+)"', tag)
        if h and r and r.group(1) not in ("canonical", "alternate"):
            hits.append(h.group(1))
    return hits + re.findall(r'url\(\s*["\']?((?:https?:)?//[^"\')]+)', doc)


def test_the_app_build_asks_nothing_of_other_hosts(builds):
    for rel, doc in pages(builds["kids"]):
        assert not loads_elsewhere(doc), (rel, loads_elsewhere(doc))
        if rel.startswith("vendor/"):        # Pyodide's own code names its CDN for use under Node, never in a
            continue                         # browser given indexURL; the real-browser test proves no request
        assert not OUTSIDE.search(doc), (rel, OUTSIDE.search(doc).group(0))
    privacy = (builds["kids"] / "privacy.html").read_text(encoding="utf-8")
    assert "visits aren't counted" in privacy and "Inside the app" in privacy and "Google Fonts" not in privacy


def test_the_app_build_puts_the_gate_on_every_page_and_marks_grown_up_things(builds):
    k = builds["kids"]
    for rel, doc in pages(k):
        if rel.endswith(".html") and "</head>" in doc:
            assert "gate/gate.js" in doc and "gate/gate.css" in doc, rel
            assert doc.count("gate/gate.js") == 1, rel
    for rel in kids.GATE_PAGES:
        assert re.match(r"<!doctype html>\s*<html data-gate-page", (k / rel).read_text(encoding="utf-8")), rel
    assert 'href="/gate/gate.js"' in (k / "404.html").read_text(encoding="utf-8").replace("src=", "href=")
    index = (k / "index.html").read_text(encoding="utf-8")
    assert '<a data-gate="always" data-gate-reason="share" class="btn ghost edition-share"' in index
    assert '<a data-gate data-gate-reason="print" class="btn recommended-print"' in index
    cert = (k / "play" / "certificate.html").read_text(encoding="utf-8")
    assert '<button data-gate data-gate-reason="print" type="button" class="big go print"' in cert
    issue = next(p for p in (k / "play").glob("*/*.html") if "Print this paper (for grown-ups)" in p.read_text(encoding="utf-8"))
    assert re.search(r'<a data-gate data-gate-reason="print" href="[^"]+">Print this paper', issue.read_text(encoding="utf-8"))
    builder = (k / "builder.html").read_text(encoding="utf-8")
    assert builder.count('data-gate="always" data-gate-reason="link" type="button" class="btn go" data-bot=') == 3
    assert (k / "gate" / "gate.js").exists() and (k / "gate" / "gate.css").exists()


def test_the_app_build_keeps_every_feature(builds):
    """Nothing is removed: the same pages, the same links (sources, licence, email), the builder and its engine.
    The app adds its bridge and the Listen tab (tests/test_app.py)."""
    w, k = builds["web"], builds["kids"]
    files = lambda root: {rel for rel, _ in pages(root)} - {"gate/gate.js", "gate/gate.css", "app.js", "play/listen.html"}
    assert files(w) == files(k)
    links = lambda root: sorted(h for rel, doc in pages(root) if rel.endswith(".html")
                                for h in re.findall(r'<a\b[^>]*href="(https?://[^"]+|mailto:[^"]+)"', doc)
                                if "goatcounter.com" not in h)            # the app counts nothing, so has no counter to link to
    web_links, kid_links = links(w), links(k)
    assert set(web_links) <= set(kid_links)                                # every source, licence and email link is still there
    fb = (k / "feedback.html").read_text(encoding="utf-8")
    url = site.site_config()["feedback_url"]
    assert "<iframe" not in fb and f'href="{url}"' in fb and fb.count("mailto:") >= 2
    assert '<iframe src="https://docs.google.com/forms/' in (w / "feedback.html").read_text(encoding="utf-8")


def test_enabled_subscriptions_keep_the_app_gate_on_all_parent_forms(builds):
    if not site.site_config()['subscriptions']['enabled']:
        pytest.skip('Subscription UI is disabled in site.yaml')
    endpoint = site.subscription_endpoint(site.site_config())
    for mode, root in builds.items():
        home = (root / 'index.html').read_text(encoding='utf-8')
        assert 'class="recommended-archive subscription-signup"' in home
        assert 'parents.html?edition=little-explorers#subscribe-parents-title' in home
        assert '<form' not in home and 'fetch(' not in home
        for rel in ('parents.html', 'e/little-explorers/index.html'):
            doc = (root / rel).read_text(encoding='utf-8')
            forms = re.findall(r'<form\b[^>]*data-gate-form="subscribe"[^>]*>', doc)
            assert forms, (mode, rel)
            assert all(f'data-subscribe-endpoint="{endpoint}"' in form for form in forms)
            assert all(f'data-subscribe-kids="{str(mode == "kids").lower()}"' in form for form in forms)
        for path in (root / 'play').rglob('*.html'):
            assert 'data-subscribe-endpoint=' not in path.read_text(encoding='utf-8'), path


def test_the_website_is_unchanged_apart_from_its_own_fonts_and_pyodide(builds):
    w = builds["web"]
    for rel, doc in pages(w):
        if rel.startswith("vendor/"):        # Pyodide's own code (see above)
            continue
        # Subscription forms carry their scoped hook in both builds; only the
        # app gets global parental-gate attributes and scripts.
        assert "gate/gate.js" not in doc, rel
        assert not re.search(r"\bdata-gate(?:-page|-reason)?(?:[\s=>])", doc), rel
        assert not re.search(r"fonts\.googleapis|fonts\.gstatic|cdn\.jsdelivr", doc), rel
    cfg = site.site_config()
    if cfg.get("goatcounter"):
        assert "goatcounter.com/count" in (w / "index.html").read_text(encoding="utf-8")
        assert "npCount" in (w / "play" / "index.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["web", "kids"])
def test_fonts_and_pyodide_come_from_the_site(builds, mode):
    root = builds[mode]
    css = (root / "fonts" / "fonts.css").read_text(encoding="utf-8")
    for f in re.findall(r"url\(([^)]+\.woff2)\)", css):
        assert (root / "fonts" / f).stat().st_size > 1000, f
    assert '<link rel="stylesheet" href="fonts/fonts.css">' in (root / "index.html").read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../../fonts/fonts.css">' in next((root / "play").glob("*/20*.html")).read_text(encoding="utf-8")
    builder = (root / "builder.html").read_text(encoding="utf-8")
    assert 'const PYODIDE = "vendor/pyodide/";' in builder and 'fonts/fonts.css' in builder
    pin = vendor.pin()
    for name, meta in pin["files"].items():
        assert (root / "vendor" / "pyodide" / name).stat().st_size == meta["size"], name
    lock = json.load(open(root / "vendor" / "pyodide" / "pyodide-lock.json", encoding="utf-8"))
    for pkg in pin["packages"]:                                           # every package the builder loads is served
        assert (root / "vendor" / "pyodide" / lock["packages"][pkg]["file_name"]).exists(), pkg
    play = (root / "play" / "index.html").read_text(encoding="utf-8")
    assert "vendor/pyodide" not in play and "vendor/pyodide" not in (root / "index.html").read_text(encoding="utf-8")


def _browser():
    node = shutil.which("node")
    if not node:
        return None
    env = dict(os.environ)
    try:
        env.setdefault("NODE_PATH", subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip())
        subprocess.run([node, "-e", "require('playwright')"], env=env, check=True, capture_output=True)
    except Exception:
        return None
    for chrome in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",):
        if os.path.exists(chrome):
            env.setdefault("CHROME", chrome)
    return node, env


@pytest.mark.parametrize("mode", ["kids", "web"])
def test_in_a_real_browser(builds, mode):
    """tools/kids_check.cjs: every page type, every gated action, zero outside requests (kids)."""
    found = _browser()
    if not found:
        pytest.skip("Playwright with Chromium isn't installed")
    node, env = found
    handler = partial(SimpleHTTPRequestHandler, directory=str(builds[mode]))
    handler.log_message = lambda *a: None
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        r = subprocess.run([node, os.path.join(ROOT, "tools", "kids_check.cjs"), f"http://127.0.0.1:{port}/", mode],
                           env=env, capture_output=True, text=True, timeout=600)
    finally:
        server.shutdown()
    out = r.stdout
    report = json.loads(out[out.index("{"):]) if "{" in out else {"failed": -1, "results": [], "error": r.stderr[-2000:]}
    failed = [x for x in report["results"] if not x["pass"]]
    assert r.returncode == 0 and not failed, (failed, report.get("error"), r.stderr[-1500:])
