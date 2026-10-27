"""The app's content pack: the app build trimmed to what the phone keeps, plus manifest.json.

    python -m ygc site --kids --keep 7 --out _site/app
    python -m ygc.narration --site _site/app --latest-only
    python -m ygc app-pack --site _site/app

The website then serves it at <base_url>/app/. Each morning the app downloads manifest.json, fetches only
the files whose hash changed and deletes the ones that are gone, so everything works offline
(docs/APP_BUILD.md). Left out: what the app doesn't use (the Design engine, which opens the website instead;
link-preview pictures; the podcast feed; files only a web host needs).
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil

DROP = ("builder.html", "builder-engine.zip", "vendor", "share", "sitemap.xml", "robots.txt", "CNAME", "404.html",
        "play/podcast.xml", "play/sw.js")
ON_WEBSITE = ("builder.html",)                  # pages left out whose links open the website instead (behind the gate)
MANIFEST = "manifest.json"
VERSION = 1


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:20]


def pack(site, log=print):
    """Trim `site` (an app build) and write its manifest.json. Returns the manifest."""
    for rel in DROP:
        p = os.path.join(site, rel)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    from .site import site_config
    base = (site_config().get("base_url") or "").rstrip("/") + "/"
    links = re.compile(r'href="(?:\.\./)*(' + "|".join(re.escape(p) for p in ON_WEBSITE) + r')"')
    for dp, _, fs in os.walk(site):
        for f in fs:
            if f.endswith(".html"):
                p = os.path.join(dp, f)
                doc = open(p, encoding="utf-8").read()
                new = links.sub(lambda m: f'href="{base}{m.group(1)}"', doc)
                if new != doc:
                    open(p, "w", encoding="utf-8").write(new)
    files = {}
    for dp, dirs, fs in os.walk(site):
        dirs.sort()
        for f in sorted(fs):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, site).replace(os.sep, "/")
            if rel == MANIFEST:
                continue
            files[rel] = [digest(p), os.path.getsize(p)]
    whole = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {"v": VERSION, "id": whole, "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "start": "index.html", "files": files}
    with open(os.path.join(site, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, separators=(",", ":"))
    size = sum(s for _, s in files.values())
    log(f"  app pack: {len(files)} files, {size / 1e6:.1f} MB, id {whole}")
    return manifest
