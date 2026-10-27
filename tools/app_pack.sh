#!/usr/bin/env bash
# The app's offline pack, served at <base_url>/app/ (docs/APP_BUILD.md). Run after the website's own
# narration step, so the recordings come from the cache. If this fails, the website still publishes and
# phones keep the papers they already saved.
set -euo pipefail
tmp=_app_build
rm -rf "$tmp"
python -m ygc site --kids --keep 7 --out "$tmp"
python -u -m ygc.narration --site "$tmp" --latest-only
python -m ygc app-pack --site "$tmp"
rm -rf _site/app
mv "$tmp" _site/app
