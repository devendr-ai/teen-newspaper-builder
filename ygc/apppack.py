"""The app's content pack: the app build trimmed to what the phone keeps, plus manifest.json.

    python -m ygc site --kids --keep 7 --out _site/app
    python -m ygc.narration --site _site/app --latest-only
    python -m ygc app-pack --site _site/app

The website then serves it at <base_url>/app/. Each morning the app downloads manifest.json, fetches only
the files whose hash changed and deletes the ones that are gone, so everything works offline
(docs/APP_BUILD.md). Left out: what the app doesn't use (link-preview pictures, the podcast feed, files only a
web host needs), and recordings of older issues (trim_audio).
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil

DROP = ("share", "sitemap.xml", "robots.txt", "CNAME", "404.html", "play/podcast.xml", "play/sw.js")
NARRATION = re.compile(r'<script id="narration" type="application/json">(.*?)</script>', re.S)
MANIFEST = "manifest.json"
VERSION = 1


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:20]


def trim_audio(site, log=print):
    """Keep the recordings the app plays: each paper's newest issue and the Listen tab. Older issues
    read aloud with the phone's own voice instead, which keeps the pack small."""
    play = os.path.join(site, "play")
    keep = set()
    for eid in os.listdir(play):
        pages = sorted(f for f in os.listdir(os.path.join(play, eid)) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", f)) \
            if os.path.isdir(os.path.join(play, eid)) else []
        if pages:
            m = NARRATION.search(open(os.path.join(play, eid, pages[-1]), encoding="utf-8").read())
            for variants in (json.loads(m.group(1)) if m else {}).values():
                keep |= {v["src"].rsplit("/", 1)[-1] for v in variants.values()}
    listen = os.path.join(play, "listen.json")
    if os.path.exists(listen):
        data = json.load(open(listen, encoding="utf-8"))
        keep |= {b["audio"].rsplit("/", 1)[-1] for b in data.get("briefs", [])}
        keep |= {t["src"].rsplit("/", 1)[-1] for p in data.get("papers", []) for t in p["tracks"]}
    audio, gone = os.path.join(play, "audio"), 0
    for f in os.listdir(audio) if os.path.isdir(audio) else []:
        if f.endswith(".mp3") and f not in keep:
            os.remove(os.path.join(audio, f))
            gone += 1
    log(f"  app pack: {len(keep)} recordings kept, {gone} older ones left to the phone's voice")


def pack(site, log=print):
    """Trim `site` (an app build) and write its manifest.json. Returns the manifest."""
    for rel in DROP:
        p = os.path.join(site, rel)
        if os.path.isdir(p):
            shutil.rmtree(p)
        elif os.path.exists(p):
            os.remove(p)
    trim_audio(site, log)
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
