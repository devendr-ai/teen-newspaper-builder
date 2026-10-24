"""One installed app for the newsstand, reader and design pages."""
import html
import json


def head(cfg, root=""):
    return f'''<link rel="manifest" href="{root}manifest.webmanifest">
<meta name="theme-color" content="#E2584D">
<link rel="apple-touch-icon" href="{root}play/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{html.escape(cfg['title'])}">'''


def manifest(cfg, legacy_reader=False):
    # The old /play/ manifest remains available to existing reader installations.
    # Its scope expands to the site root; new installs share the root manifest.
    root = "../" if legacy_reader else "./"
    icons = "" if legacy_reader else "play/"
    return json.dumps({
        "id": root + "index.html",
        "name": cfg["title"], "short_name": cfg["title"],
        "description": "Today's news for children: read it, hear it, play a game.",
        "start_url": "./index.html", "scope": root, "display": "standalone",
        "background_color": "#FFF8EE", "theme_color": "#E2584D",
        "icons": [{"src": f"{icons}icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any maskable"}
                  for n in (192, 512)]}, ensure_ascii=False, indent=1)
