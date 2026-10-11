"""Empty, correctly shaped issue for an edition: the starting point for an editor."""
from .edition import desk, placed_blocks
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


def make(ed, date, number, volume=1):
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
    return {"edition": ed["id"], "date": date, "volume": volume, "issue": number,
            "blocks": blocks, "sources": []}
