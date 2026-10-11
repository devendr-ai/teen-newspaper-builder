"""Convert a template-v3 issue (lead / p1_stories / p2_stories) to the v4 format."""
import re


def v3_to_v4(old, edition_id="young-global-citizen"):
    meta = old["meta"]
    from datetime import datetime
    d = datetime.strptime(meta["date_str"], "%A, %B %d, %Y").date()
    m = re.search(r"Vol\.\s*(\d+).*?No\.\s*(\d+)", meta["vol_str"])
    lead = dict(old["lead"])
    world = dict(old["p1_stories"][0])
    india, us = (dict(s) for s in old["p2_stories"][:2])
    india.pop("also_title", None)
    learn = old.get("learn", {})
    blocks = {
        "lead": lead, "world": world, "india": india, "us": us,
        "briefs": {"items": old.get("briefs", [])},
        "vocab": {"title": learn.get("vocab_title"), "items": learn.get("vocab", [])},
        "did_you_know": {"text": learn.get("did_you_know", "")},
        "sports": old.get("sports", {}),
        "watchlist": {"items": old.get("watchlist", [])},
        "quote": {"text": learn.get("quote", "")},
    }
    if learn.get("quote_by"):
        blocks["quote"]["by"] = learn["quote_by"]
    if not blocks["vocab"]["title"]:
        blocks["vocab"].pop("title")
    # Preserve exactly what v3 printed: it defaulted to daily wording.
    blocks["watchlist"]["title"] = meta.get("watchlist_title", "TOMORROW'S WATCHLIST")
    blocks["sign_off"] = {"text": meta.get(
        "sign_off", "You are not just reading the news — you are learning to think "
                    "about it. See you tomorrow.")}
    new = {"edition": edition_id, "date": d.isoformat(), "volume": int(m.group(1)),
           "issue": int(m.group(2)), "location": meta.get("location"), "blocks": blocks}
    if old.get("sources"):
        new["sources"] = old["sources"]
    known = {"meta", "lead", "p1_stories", "p2_stories", "briefs", "learn", "sports", "watchlist", "sources"}
    for k, v in old.items():
        if k not in known:
            new[k] = v
    if not new["location"]:
        new.pop("location")
    return new
