"""Empty, correctly shaped issue for an edition: the starting point for an editor."""
from .edition import desk, placed_blocks, story_blocks
from .graphics import IllustrationCard


def _story(ed, cfg):
    s = {"kicker": desk(ed, cfg["desk"])["label"] + "  •  ", "headline": "", "deck": "",
         "body": ["", "", ""]}
    g = cfg.get("graphics", [])
    if "map" in g:
        s["map"] = {"title": "", "label_top": "", "label_bottom": "", "footnote": "", "caption": ""}
    if "illustration" in g:
        s["illustration"] = {"title": "", "subtitle": "",
                             "motif": "|".join(IllustrationCard.known_motifs()), "caption": ""}
    if "chart" in g:
        s["chart"] = {"title": "", "subtitle": "", "labels": ["", ""], "values": [0, 0],
                      "max": 0, "value_prefix": "", "highlight_after": 0, "caption": ""}
    for x in cfg.get("extras", []):
        s[x] = ""
    if cfg.get("also"):
        s["also"] = [""] * cfg["also"]["count"]
    s["sources"] = []
    return s


def play_counts(ed):
    """(quiz questions, fact-or-fiction claims) for the website's games, by the reader's age."""
    age = reader_age(ed)
    return (3, 2) if age <= 8 else (4, 3) if age <= 11 else (5, 3) if age <= 14 else (8, 4)


def reader_age(ed):
    try:
        return int(str(ed["reader"]["age"]).split("-")[0])
    except ValueError:
        return 15


def wants_easy(ed):
    """Papers for 12 and up offer an easier version of each story online, for readers who find one hard."""
    return reader_age(ed) >= 12


def play_skeleton(ed):
    nq, nf = play_counts(ed)
    return {"quiz": [{"q": "", "options": ["", "", ""], "answer": 0, "why": "", "story": ""} for _ in range(nq)],
            "fact_or_fiction": [{"claim": "", "true": True, "why": "", "story": ""} for _ in range(nf)],
            "where": [{"story": bid, "place": "", "lat": None, "lon": None, "countries": []} for bid in story_blocks(ed)],
            **({"easy": {bid: {"headline": "", "body": ["", ""]} for bid in story_blocks(ed)}} if wants_easy(ed) else {})}


def make(ed, date, number, volume=1, play=True):
    blocks = {}
    for bid in placed_blocks(ed):
        cfg = ed["blocks"][bid]
        t = cfg["type"]
        if t == "story":
            blocks[bid] = _story(ed, cfg)
        elif t == "feature":
            blocks[bid] = {"title": "", "body": ["", ""], "sources": []}
        elif t in ("briefs", "watchlist"):
            blocks[bid] = {"items": [""] * cfg["count"]}
        elif t == "vocab":
            blocks[bid] = {"items": [{"word": "", "def": "Definition. Today: ..."}
                                     for _ in range(cfg["count"])]}
        elif t == "did_you_know":
            blocks[bid] = {"text": ""}
        elif t == "sports":
            blocks[bid] = {"title": "", "body": "", "sources": []}
        elif t == "quote":
            blocks[bid] = {"text": "", "by": ""}
    out = {"edition": ed["id"], "date": date, "volume": volume, "issue": number,
           "blocks": blocks, "sources": []}
    if play:                    # online only: the quiz and fact-or-fiction games on Read & Play
        out["play"] = play_skeleton(ed)
    return out
