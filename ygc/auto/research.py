"""Stage 1: research each desk once for all due editions, keeping only facts
whose source URL a web search actually returned."""
import json

from ..edition import desk
from .llm import extract_json, norm_url, retrieved_urls

SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 10}

SYSTEM = """You are the research desk of a newsroom that writes printed newspapers for young and adult readers.
Search the web and report the most important verified stories for one desk. Rules:
- Use only information from pages your searches returned. Never rely on memory for any fact, figure, name or date.
- Every fact and number cites the URL of a page your search returned, and that page must support it.
- Prefer original reporting and official sources (wire services, major newspapers, government and institutional sites).
- Stay inside the time window; note the publication date of each source.
- Classify enrichment_kind: mechanism for science/technology needing how-it-works detail; context for complex world, policy or economic developments; none for scores, results, routine announcements or stories already sufficiently explained.
- Mark a source primary:true only for official first-hand material or original reporting, not aggregators.
- Write facts in your own words. No quote longer than 15 words.
- Reply with one JSON object only, no other text."""

SHAPE = """{
  "stories": [
    {
      "id": "short-slug",
      "headline": "plain factual headline",
      "what_happened": "2-3 sentences",
      "why_it_matters": "1-2 sentences",
      "importance": 1-10,
      "suitable_for_children": true,
      "key_facts": [{"fact": "...", "source_url": "https://..."}],
      "numbers": [{"label": "...", "value": 0, "unit": "...", "source_url": "https://..."}],
      "geography": "places involved, and any coast, strait, river or island that matters",
      "enrichment_kind": "mechanism | context | none",
      "sources": [{"outlet": "...", "title": "...", "url": "https://...", "published": "YYYY-MM-DD", "primary": true}]
    }
  ]
}"""


def desk_groups(eds):
    """{group_key: {"label", "scopes", "hours", "editions"}} for every story desk in these editions."""
    groups = {}
    for ed in eds:
        hours = ed["cadence"]["window_hours"]
        for bid, b in ed["blocks"].items():
            if b["type"] not in ("story", "feature") or not b.get("desk"):
                continue
            d = desk(ed, b["desk"])
            key = "world" if d["id"] in ("top", "world") else d["label"].lower()
            g = groups.setdefault(key, {"label": "WORLD" if key == "world" else d["label"],
                                        "scopes": [], "hours": 0, "editions": []})
            if d["scope"] not in g["scopes"]:
                g["scopes"].append(d["scope"])
            g["hours"] = max(g["hours"], hours)
            if ed["id"] not in g["editions"]:
                g["editions"].append(ed["id"])
    return groups


def research_group(client, key, g, date, stories=5):
    scopes = "\n".join(f"- {s}" for s in g["scopes"][:6])
    user = (f"Today is {date}. Desk: {g['label']}. Time window: the {g['hours']} hours up to today.\n"
            f"What this desk covers:\n{scopes}\n\n"
            f"Find the {stories} most important stories for this desk in the window, most important first. "
            f"Mark suitable_for_children false for stories whose core facts are too graphic for ages 6-14.\n\n"
            f"Reply with JSON shaped exactly like:\n{SHAPE}")
    blocks, text, _ = client.create(SYSTEM, [{"role": "user", "content": user}], tools=[SEARCH_TOOL],
                                    max_tokens=12000)
    seen = retrieved_urls(blocks)
    data = extract_json(text)
    kept, dropped = [], 0
    for st in data.get("stories", []):
        st["key_facts"] = [f for f in st.get("key_facts", []) if norm_url(f.get("source_url", "")) in seen]
        st["numbers"] = [n for n in st.get("numbers", []) if norm_url(n.get("source_url", "")) in seen]
        st["sources"] = [s for s in st.get("sources", []) if norm_url(s.get("url", "")) in seen]
        if st["sources"] and st["key_facts"]:
            st["desk_group"] = key
            kept.append(st)
        else:
            dropped += 1
    return {"label": g["label"], "hours": g["hours"], "stories": kept, "dropped_unverified": dropped,
            "retrieved_urls": sorted(seen)}


def pool_for_edition(pool, ed, limit_per_group=5):
    """The slice of the shared research an edition may use: its desks' groups, plus the
    world group for the lead and briefs."""
    keys = set(desk_groups([ed]).keys()) | {"world"}
    out = {k: dict(pool[k], stories=pool[k]["stories"][:limit_per_group], retrieved_urls=None)
           for k in keys if k in pool}
    for v in out.values():
        v.pop("retrieved_urls", None)
    return out


def pool_urls(pool_slice):
    return {norm_url(s["url"]) for g in pool_slice.values() for st in g["stories"] for s in st.get("sources", [])}


def dumps(x):
    return json.dumps(x, ensure_ascii=False, indent=1)
