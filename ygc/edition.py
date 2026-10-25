"""Load and validate an edition: editions/<id>/edition.yaml.

An edition is everything that makes one paper different from another: who
reads it, why, which desks (countries and topics) it covers, how often it comes
out, and the page plan. Nothing about a specific paper is hard-coded in Python.
"""
import copy
import os

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITIONS = os.path.join(ROOT, "editions")

BLOCK_TYPES = {"story", "feature", "briefs", "vocab", "did_you_know", "sports",
               "watchlist", "quote", "sign_off"}
BUILTIN_BLOCKS = {"rule"}                 # usable in a page plan without declaring
GRAPHICS = {"map", "illustration", "chart"}
EXTRAS = {"why", "connect", "analyst"}
STORY_SIZES = {"lead", "standard", "compact"}

DEFAULTS = {
    "style": {"type_scale": 1.0},
    "labels": {
        "why": "WHY THIS MATTERS",
        "connect": "CONNECT THE DOTS",
        "analyst": "THINK LIKE AN ANALYST",
        "briefs": "ONE-LINE BRIEFS",
        "vocab_tag": "VOCABULARY BUILDER",
        "vocab_title": "Words that unlock today's news",
        "did_you_know": "DID YOU KNOW?",
        "sports": "SPORTS CORNER",
        "watchlist": "WHAT TO WATCH NEXT",
        "byline": "Written with AI",
    },
    "teaching": {
        "repeat_window": 2,          # issues in which vocab / DYK must not repeat
        "vocab_today": True,         # each definition shows the word in this issue
        "chart_label_limits": {2: 15, 3: 10, 4: 8},
    },
    "sources_required": True,
    "rules": [],
}


class EditionError(ValueError):
    pass


def edition_dir(edition_id):
    return os.path.join(EDITIONS, edition_id)


def list_editions():
    if not os.path.isdir(EDITIONS):
        return []
    return sorted(d for d in os.listdir(EDITIONS)
                  if os.path.isfile(os.path.join(EDITIONS, d, "edition.yaml")))


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(edition_id):
    path = os.path.join(edition_dir(edition_id), "edition.yaml")
    if not os.path.isfile(path):
        raise EditionError(f"no edition {edition_id!r} (looked for {path}); "
                           f"available: {', '.join(list_editions()) or 'none'}")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    ed = _merge(DEFAULTS, raw)
    ed["teaching"]["chart_label_limits"] = {
        int(k): int(v) for k, v in ed["teaching"]["chart_label_limits"].items()}
    errors = validate(ed, edition_id)
    if errors:
        raise EditionError(f"{path}:\n  - " + "\n  - ".join(errors))
    ed["_dir"] = edition_dir(edition_id)
    return ed


def validate(ed, edition_id):
    e = []
    if ed.get("id") != edition_id:
        e.append(f"id must equal the folder name {edition_id!r}")
    for key in ("name", "masthead", "reader", "purpose", "voice", "cadence",
                "desks", "blocks", "pages"):
        if not ed.get(key):
            e.append(f"missing required key: {key}")
    if e:
        return e

    m = ed["masthead"]
    for k in ("title", "location"):
        if not m.get(k):
            e.append(f"masthead.{k} is required")
    r = ed["reader"]
    if not isinstance(r.get("age"), (int, str)):
        e.append("reader.age is required (a number, or a range like '12-14')")
    if not r.get("profile"):
        e.append("reader.profile is required: who reads this paper, in a sentence")
    c = ed["cadence"]
    for k in ("every_days", "window_hours", "timezone"):
        if k not in c:
            e.append(f"cadence.{k} is required")
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(c.get("timezone", "UTC"))
    except Exception:
        e.append(f"cadence.timezone {c.get('timezone')!r} is not a valid IANA timezone")
    scale = ed["style"].get("type_scale", 1.0)
    if not 0.8 <= float(scale) <= 1.6:
        e.append("style.type_scale must be between 0.8 and 1.6")

    desk_ids = set()
    for i, d in enumerate(ed["desks"]):
        if not d.get("id") or not d.get("label") or not d.get("scope"):
            e.append(f"desks[{i}] needs id, label and scope")
        desk_ids.add(d.get("id"))

    blocks = ed["blocks"]
    for bid, b in blocks.items():
        t = b.get("type")
        if t not in BLOCK_TYPES:
            e.append(f"blocks.{bid}.type {t!r} must be one of {sorted(BLOCK_TYPES)}")
            continue
        if t in ("story", "feature") and b.get("desk") and b["desk"] not in desk_ids:
            e.append(f"blocks.{bid}.desk {b['desk']!r} is not a declared desk")
        if t == "story":
            if not b.get("desk"):
                e.append(f"blocks.{bid}: a story needs a desk")
            if b.get("size", "standard") not in STORY_SIZES:
                e.append(f"blocks.{bid}.size must be one of {sorted(STORY_SIZES)}")
            for g in b.get("graphics", []):
                if g not in GRAPHICS:
                    e.append(f"blocks.{bid}.graphics: {g!r} must be one of {sorted(GRAPHICS)}")
            for x in b.get("extras", []):
                if x not in EXTRAS:
                    e.append(f"blocks.{bid}.extras: {x!r} must be one of {sorted(EXTRAS)}")
        if t in ("briefs", "vocab", "watchlist") and not isinstance(b.get("count"), int):
            e.append(f"blocks.{bid}.count (a number) is required for {t}")
        if t == "sign_off" and not b.get("text"):
            e.append(f"blocks.{bid}.text is required for sign_off")

    used = []
    pages = ed["pages"]
    for p, page in enumerate(pages):
        cols = page.get("columns") or []
        if not 1 <= len(cols) <= 3:
            e.append(f"pages[{p}] needs 1 to 3 columns")
        if page.get("masthead") and p != 0:
            e.append(f"pages[{p}]: only the first page can carry the masthead")
        if page.get("masthead") and page.get("banner"):
            e.append(f"pages[{p}]: a page has a masthead or a banner, not both")
        for col in cols:
            for bid in col:
                if bid in BUILTIN_BLOCKS:
                    continue
                if bid not in blocks:
                    e.append(f"pages[{p}] uses undeclared block {bid!r}")
                used.append(bid)
    auto = ed.get("automation") or {}
    if auto and not isinstance(auto.get("enabled", False), bool):
        e.append("automation.enabled must be true or false")
    if auto and not isinstance(auto.get("poster", False), bool):
        e.append("automation.poster must be true or false")
    if auto.get("weekday") and str(auto["weekday"]).lower() not in (
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
        e.append("automation.weekday must be a day name, e.g. saturday")
    site = ed.get("site") or {}
    for k in ("audience", "focus", "blurb"):
        if k in site and not isinstance(site[k], str):
            e.append(f"site.{k} must be text")
    if pages and not pages[0].get("masthead"):
        e.append("pages[0] must set masthead: true")
    dup = {b for b in used if used.count(b) > 1}
    if dup:
        e.append(f"blocks placed more than once: {sorted(dup)}")
    unused = set(blocks) - set(used)
    if unused:
        e.append(f"blocks declared but not placed on any page: {sorted(unused)}")
    return e


def story_blocks(ed):
    """Declared blocks that are news stories, in page order."""
    return [b for b in placed_blocks(ed) if ed["blocks"][b]["type"] == "story"]


def placed_blocks(ed):
    out = []
    for page in ed["pages"]:
        for col in page["columns"]:
            out += [b for b in col if b not in BUILTIN_BLOCKS]
    return out


def desk(ed, desk_id):
    return next(d for d in ed["desks"] if d["id"] == desk_id)
