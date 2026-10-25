"""Pyodide, served from this site so the builder page makes no outside requests.

The Design-your-own builder (builder.html) runs the engine in the browser with Pyodide. The files
it needs are pinned in assets/vendor/pyodide.json (version, the source they were taken from, and a
SHA-256 for each). `python -m ygc vendor` downloads them once into .cache/vendor and checks every
hash; the site build copies them to vendor/pyodide/, which only builder.html loads.
"""
import hashlib
import json
import os
import shutil
import urllib.request

from .edition import ROOT

PIN = os.path.join(ROOT, "assets", "vendor", "pyodide.json")
CACHE = os.path.join(ROOT, ".cache", "vendor")
SITE_DIR = "vendor/pyodide/"               # where builder.html finds it, from the site's root


def pin():
    return json.load(open(PIN, encoding="utf-8"))


def _ok(path, sha):
    if not os.path.exists(path):
        return False
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == sha


def ensure(log=print):
    """Every pinned file in the cache, downloaded and checked if missing. Returns the cache folder."""
    p = pin()
    folder = os.path.join(CACHE, f"pyodide-{p['version']}")
    os.makedirs(folder, exist_ok=True)
    for name, meta in p["files"].items():
        path = os.path.join(folder, name)
        if _ok(path, meta["sha256"]):
            continue
        log(f"  vendor: downloading {name}")
        tmp = path + ".part"
        with urllib.request.urlopen(p["source"] + name, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        if not _ok(tmp, meta["sha256"]):
            os.remove(tmp)
            raise RuntimeError(f"Pyodide file {name} doesn't match its pinned SHA-256 (assets/vendor/pyodide.json)")
        os.replace(tmp, path)
    return folder


def copy_into(out, log=print):
    """vendor/pyodide/ in the built site."""
    src = ensure(log)
    dst = os.path.join(out, *SITE_DIR.strip("/").split("/"))
    os.makedirs(dst, exist_ok=True)
    for name in pin()["files"]:
        shutil.copy(os.path.join(src, name), os.path.join(dst, name))
    return dst
