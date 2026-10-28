"""Write a paper with your own chatbot.

The builder page runs this module in the browser (Pyodide): it writes the
instructions a parent pastes into ChatGPT, Claude or Gemini, then checks the
chatbot's reply with the same checks as every published issue and builds the
same PDF. A reply that fails gets a list of fixes to paste back.
"""
import copy
import datetime as dt
import io
import json
import os
import re
import unicodedata

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Frame

from . import checks, edition, poster, prompt, render
from .auto.llm import extract_json

FREE_LINES = 6          # a column with more empty lines than this is worth filling


def install(yaml_text):
    """Save an edition file from the builder and load it (validated) like any other."""
    import yaml
    eid = (yaml.safe_load(yaml_text) or {}).get("id")
    if not eid:
        raise edition.EditionError("the edition file has no id")
    d = edition.edition_dir(eid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "edition.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_text)
    return edition.load(eid)


def instructions(ed, date, number=1):
    text = prompt.generate(ed, chat={"date": date, "number": number})
    extra = field_rules(ed) + "\n" + length_text(ed) + "\n"
    return text.replace("**Output.**", extra + "**Output.**", 1)


def field_rules(ed):
    """The format rules the checker enforces, stated up front so a chatbot's first draft can pass."""
    used = {g for b in edition.placed_blocks(ed) for g in ed["blocks"][b].get("graphics", [])}
    lim = ed["teaching"]["chart_label_limits"]
    L = ["**Field rules.** The page that prints your reply checks these exactly:",
         "- `kicker`: keep the desk label, then add a short topic after it in capitals, "
         "e.g. \"WORLD  •  NOBEL PRIZE\". One line.",
         "- `headline`: at most about 10 words. `body`: a list of paragraphs."]
    if "illustration" in used:
        L.append(f"- `illustration`: `title` at most 44 characters, `subtitle` at most 25; `motif` is exactly one "
                 "word from the list in the skeleton.")
    if "map" in used:
        L.append("- `map`: `title` names the water (e.g. \"STRAIT OF HORMUZ\"); `label_top` and `label_bottom` are the "
                 "two land areas on either side, one or two words each in capitals; `footnote` may be empty.")
    if "chart" in used:
        L.append(f"- `chart`: 2 to 4 bars from real, sourced numbers. `labels` at most {lim.get(2, 15)} characters with "
                 f"2 bars, {lim.get(3, 10)} with 3, {lim.get(4, 8)} with 4; `values` are plain numbers; `max` is at least "
                 "the largest value; `title` at most 46 characters and `subtitle` at most 52.")
    if any(ed["blocks"][b]["type"] == "vocab" for b in edition.placed_blocks(ed)) and ed["teaching"]["vocab_today"]:
        L.append("- `vocab`: each `def` gives the meaning, then \"Today:\" and how the word is used in this issue's news.")
    L.append("- Every story and every section that has `sources` lists at least one URL of a page you found today.")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------ length guide
_FILL = "people said the new plan would help schools across the country after months of careful work".split()
BOX_WORDS = 40          # each "why it matters" / "connect the dots" / "think like an analyst" box


def _words(n, paras=5):
    words = [_FILL[i % len(_FILL)] for i in range(n)]
    k = max(1, min(paras, n // 25 or 1))
    size = -(-n // k) if n else 1
    return [" ".join(words[i:i + size]) for i in range(0, n, size)] or [""]


def _probe(ed):
    """An issue with every fixed section at a typical length and empty story bodies."""
    w = lambda n: " ".join(["word"] * n)
    sk = render_ready(ed, prompt.skeleton.make(ed, "2026-01-01", 1, play=False))
    for bid, b in sk["blocks"].items():
        t = ed["blocks"][bid]["type"]
        if t == "story":
            b.update(kicker=b["kicker"] + "TOPIC", headline=w(8), deck=w(18), body=[""])
            for x in ("why", "connect", "analyst"):
                if x in b:
                    b[x] = w(BOX_WORDS)
            if "also" in b:
                b["also"] = [w(10)] * len(b["also"])
        elif t == "feature":
            n = 110 if bid == "quiz" else 70
            b.update(title=w(4), body=[w(n // 2), w(n - n // 2)])
        elif t in ("briefs", "watchlist"):
            b["items"] = [w(18 if t == "briefs" else 14)] * len(b["items"])
        elif t == "vocab":
            b["items"] = [{"word": "Word", "def": w(16) + " Today: x"}] * len(b["items"])
        elif t == "did_you_know":
            b["text"] = w(28)
        elif t == "sports":
            b.update(title=w(5), body=w(45))
        elif t == "quote":
            b.update(text=w(12), by="X")
    return sk


def render_ready(ed, sk):
    """Fill a skeleton's graphics with valid stand-ins so it can be laid out."""
    for b in sk["blocks"].values():
        if "map" in b:
            b["map"].update(title="SEA", label_top="LAND", label_bottom="LAND", caption="A short caption about the map.")
        if "illustration" in b:
            b["illustration"].update(title="Title", subtitle="Subtitle", motif="globe", caption="A short caption.")
        if "chart" in b:
            b["chart"].update(title="Title", subtitle="Subtitle", labels=["A", "B", "C"], values=[1, 2, 3], max=4,
                              caption="A short caption.")
    return sk


# Sections that stretch to fill their column, like stories (the rest have a typical length).
ELASTIC_FEATURES = {"explainer", "analysis", "background", "timeline", "people", "sides", "next"}
FEATURE_WORDS = {"quiz": 110}           # typical length of a fixed section; others 70


def length_guide(ed):
    """{block: words of body} for every story and section, measured by laying out the page:
    stories and stretching sections share what their column leaves after typical-length extras.
    A column of sections only shares its whole height between them."""
    sk = _probe(ed)
    out = {}
    for p, (_, cols) in enumerate(render.page_geometry(ed)):
        for i, (x, y, w, h) in enumerate(cols):
            ids = ed["pages"][p]["columns"][i]
            kind = lambda b: ed["blocks"].get(b, {}).get("type")
            elastic = [b for b in ids if kind(b) == "story" or (kind(b) == "feature" and b in ELASTIC_FEATURES)]
            if not elastic:
                elastic = [b for b in ids if kind(b) == "feature"]
            for b in ids:
                if kind(b) == "feature" and b not in elastic:
                    out[b] = FEATURE_WORDS.get(b, 70)
            if not elastic:
                continue

            def fits(n):
                for b in elastic:
                    sk["blocks"][b]["body"] = _words(n, paras=5 if kind(b) == "story" else 3)
                fl = render.column_flowables(ids, render.Ctx(ed, sk), w)
                Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
                      ).addFromList(fl, Canvas(io.BytesIO(), pagesize=letter))
                return not fl
            lo, hi = 0, 1500
            while hi - lo > 5:
                mid = (lo + hi) // 2
                lo, hi = (mid, hi) if fits(mid) else (lo, mid)
            fits(lo)
            for b in elastic:
                out[b] = lo
    return out


MIN_WORDS = 30          # a story or section with less room than this means the layout can't fit


def layout_problems(ed):
    """Plain-English reasons the chosen layout can't fit the page, whatever the chatbot writes."""
    full = []
    for b, n in length_guide(ed).items():
        if n < MIN_WORDS and (ed["blocks"][b]["type"] == "story" or b in ELASTIC_FEATURES):
            where = next(f"Page {p + 1}, column {c + 1}" for p, pg in enumerate(ed["pages"])
                         for c, col in enumerate(pg["columns"]) if b in col)
            if where not in full:
                full.append(where)
    return [f"{w} is too full to leave room for its writing." for w in full]


def length_text(ed):
    try:
        g = length_guide(ed)
    except Exception:
        return ""
    if not g:
        return ""
    words = lambda n: max(20, round(n * 0.9 / 10) * 10)
    stories = [b for b in g if ed["blocks"][b]["type"] == "story"]
    lines = ["**Length.** Everything must fit the printed page, so aim for about this many words in each `body`. "
             "Put the most important facts first in every story and section: if one runs long, the page trims its "
             "last sentences to fit."]
    lines += [f"- `{b}`: about {words(n)} words" + (f" (3 to 5 paragraphs), plus about {BOX_WORDS} in each of its boxes"
                                                    if b in stories else "") for b, n in g.items()]
    return "\n".join(lines) + "\n"


def _parse(text):
    try:
        return extract_json(text), None
    except (ValueError, json.JSONDecodeError) as e:
        if "can't search the web" in text.lower() or "cannot search the web" in text.lower():
            return None, ("The chatbot says it can't search the web. Turn on web search (or use a chatbot "
                          "that has it) and ask again: a paper written from memory would be out of date.")
        return None, (f"This doesn't look like the chatbot's paper ({e}). Copy its whole reply, "
                      "including the code block, and paste it again.")


def _fix_message(kind, errors, name):
    items = "\n".join(f"- {e}" for e in errors)
    return (f"The {kind} doesn't pass the printing checks for {name} yet. Make every fix below, keep "
            f"everything else the same, and reply with the complete corrected JSON only.\n\n{items}")


# ------------------------------------------------------------------ fitting: trim like a sub-editor
TRIM_LIMIT = 0.35       # the most of a column's story and section writing the page may cut to fit
_ABBREV = re.compile(r"(\b[A-Z]\.|\b(?:Mr|Mrs|Ms|Dr|St|Mt|No|vs|etc|e\.g|i\.e|U\.S|U\.K|U\.N|Jr|Sr|Inc|Ltd|Co))\.?$")


def sentences(text):
    """Split a paragraph into sentences, keeping abbreviations such as U.S. and Dr. intact."""
    out, start = [], 0
    for m in re.finditer(r"(?<=[.!?])[\"”’)]?\s+(?=[\"“(A-Z0-9])", text):
        head = text[start:m.start()].rstrip("\"”’)")
        if _ABBREV.search(head):
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    out.append(text[start:].strip())
    return [x for x in out if x]


def _name(ed, b):
    cfg = ed["blocks"][b]
    if b == "lead":
        return "the top story"
    if cfg["type"] == "story":
        return f"the {edition.desk(ed, cfg['desk'])['label'].title()} story".replace(" And ", " and ")
    return f"\"{cfg.get('label', b).capitalize()}\""


def _column_fits(ed, issue, p, i, geo):
    x, y, w, h = geo
    fl = render.column_flowables(ed["pages"][p]["columns"][i], render.Ctx(ed, issue), w)
    Frame(x, y, w, h, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
          ).addFromList(fl, Canvas(io.BytesIO(), pagesize=letter))
    return not fl


def fit(ed, issue, limit=TRIM_LIMIT):
    """Trim whole sentences from the end of the stories and stretching sections in each
    overflowing column, as a sub-editor would, up to TRIM_LIMIT of their words. Columns that
    still don't fit are left untouched. Returns (issue, {block: sentences cut})."""
    issue = copy.deepcopy(issue)
    cut = {}
    try:
        over = [(m["page"] - 1, m["column"] - 1) for m in render.measure(ed, issue) if m["over"] > 0.5]
    except Exception:
        return issue, cut
    geos = [cols for _, cols in render.page_geometry(ed)]
    for p, i in over:
        ids = ed["pages"][p]["columns"][i]
        elastic = [b for b in ids if isinstance((issue["blocks"].get(b) or {}).get("body"), list) and (
            ed["blocks"][b]["type"] == "story" or b in ELASTIC_FEATURES)]
        words = lambda b: len(" ".join(issue["blocks"][b]["body"]).split())
        budget = limit * sum(words(b) for b in elastic)
        trial = copy.deepcopy(issue)
        done, removed, ok = {}, 0, False
        while True:
            if _column_fits(ed, trial, p, i, geos[p][i]):
                ok = True
                break
            paras = {b: [sentences(x) for x in trial["blocks"][b]["body"] if x.strip()] for b in elastic}
            can = [b for b in elastic if sum(len(x) for x in paras[b]) > 2]
            if not can:
                break
            b = max(can, key=lambda b: sum(len(" ".join(x).split()) for x in paras[b]))
            last = paras[b][-1].pop()
            removed += len(last.split())
            if removed > budget:
                break
            trial["blocks"][b]["body"] = [" ".join(x) for x in paras[b] if x]
            done[b] = done.get(b, 0) + 1
        if ok:
            issue = trial
            for b, n in done.items():
                cut[b] = cut.get(b, 0) + n
    return issue, cut


# ------------------------------------------------------------------ repair: mechanical fixes, no round trip
CHAT_TRIM_LIMIT = 0.5   # replies from a chatbot may be trimmed further than the daily pipeline's
_SWAP = {"→": " to ", "←": " from ", "↔": " and ", "…": "...", "₹": "Rs ", "−": "-", "‐": "-", "‑": "-",
         "‒": "-", "≈": "about ", "≥": "at least ", "≤": "at most ", "′": "'", "″": '"', "\u00a0": " ",
         "\u200b": "", "\u2009": " ", "\u202f": " "}


def _printable_text(t):
    if all(checks._printable(c) for c in t) and "…" not in t:
        return t
    for a, b in _SWAP.items():
        t = t.replace(a, b)
    out = []
    for c in t:
        if checks._printable(c):
            out.append(c)
        else:
            base = "".join(x for x in unicodedata.normalize("NFKD", c) if checks._printable(x) and not unicodedata.combining(x))
            out.append(base)
    return re.sub(r"  +", " ", "".join(out))


def _clean(node, changed):
    if isinstance(node, str):
        new = _printable_text(node)
        if new != node:
            changed.append(1)
        return new
    if isinstance(node, dict):
        return {k: _clean(v, changed) for k, v in node.items()}
    if isinstance(node, list):
        return [_clean(v, changed) for v in node]
    return node


def _shorter(t):
    """One step shorter: drop the last word, or the last character of a single word."""
    words = t.split()
    return " ".join(words[:-1]).rstrip(",;:-–—") if len(words) > 1 else t[:-1]


def _number(v):
    if isinstance(v, (int, float)):
        return v
    try:
        return float(re.sub(r"[^0-9.\-]", "", str(v)))
    except ValueError:
        return v


def repair(ed, issue):
    """Fix what a chatbot most often gets mechanically wrong, using the checker's own rules,
    so the parent never has to go back to the chatbot for it. Returns (issue, notes)."""
    issue = copy.deepcopy(issue)
    notes = []
    changed = []
    issue["blocks"] = _clean(issue.get("blocks") or {}, changed)
    if changed:
        notes.append("replaced symbols the printer can't print")
    blocks = issue["blocks"]
    for bid in [b for b in blocks if b not in ed["blocks"]]:
        del blocks[bid]
    for bid, b in blocks.items():
        if not isinstance(b, dict):
            continue
        cfg = ed["blocks"][bid]
        t = cfg["type"]
        if isinstance(b.get("body"), str) and t in ("story", "feature"):
            b["body"] = [x for x in re.split(r"\n\s*\n", b["body"]) if x.strip()] or [b["body"]]
        if t == "story":
            label = edition.desk(ed, cfg["desk"])["label"]
            k = (b.get("kicker") or "").strip()
            if not k or k.endswith("•"):
                b["kicker"] = label
            r = checks.Report()
            checks.check_blocks(ed, {"blocks": {bid: b}}, r)
            if any(f"blocks.{bid}.kicker wraps" in e for e in r.errors):
                b["kicker"] = label
            if cfg.get("also") and isinstance(b.get("also"), list) and len(b["also"]) > cfg["also"]["count"]:
                b["also"] = b["also"][:cfg["also"]["count"]]
        elif t in ("briefs", "watchlist", "vocab") and isinstance(b.get("items"), list) and len(b["items"]) > cfg["count"]:
            b["items"] = b["items"][:cfg["count"]]
            notes.append("dropped extra items")
        fixed = _repair_graphics(ed, bid, b)
        if fixed:
            notes.append(fixed)
    return issue, sorted(set(notes))


def _repair_graphics(ed, bid, b):
    w = checks._block_width(ed, bid)

    def errs():
        r = checks.Report()
        checks.check_graphics(ed, b, f"blocks.{bid}", w, r)
        return r.errors
    did = []
    ch = b.get("chart")
    if isinstance(ch, dict):
        vals = [_number(v) for v in ch.get("values") or []]
        labels = [str(x) for x in ch.get("labels") or []]
        n = min(len(vals), len(labels), 4)
        if (vals, labels) != (vals[:n], labels[:n]) or vals != ch.get("values"):
            did.append("tidied a chart")
        ch["values"], ch["labels"] = vals[:n], labels[:n]
        nums = [v for v in ch["values"] if isinstance(v, (int, float))]
        if nums and len(nums) == len(ch["values"]) and (not isinstance(ch.get("max"), (int, float)) or ch["max"] < max(nums)):
            ch["max"] = max(nums)
            did.append("tidied a chart")
    il = b.get("illustration")
    if isinstance(il, dict) and il.get("motif") not in render.IllustrationCard._MOTIFS:
        il["motif"] = "globe"
        did.append("chose a picture")
    for _ in range(200):
        e = errs()
        hit = False
        for k in ("title", "subtitle"):
            if isinstance(ch, dict) and any(f"chart.{k}:" in x for x in e):
                ch[k] = _shorter(ch[k]); hit = True
        if isinstance(ch, dict):
            for i, lab in enumerate(ch.get("labels", [])):
                if any(f"chart label {lab!r}" in x for x in e):
                    ch["labels"][i] = _shorter(lab); hit = True
        mp = b.get("map")
        if isinstance(mp, dict):
            for k in ("title", "label_top", "label_bottom", "footnote"):
                if any(f"map.{k} runs past" in x for x in e):
                    mp[k] = _shorter(mp[k]); hit = True
        if isinstance(il, dict) and any("illustration:" in x for x in e):
            if len(il.get("title", "")) > 44:
                il["title"] = _shorter(il["title"])
            elif len(il.get("subtitle", "")) > 25 or len(il.get("subtitle", "").split()) > 1:
                il["subtitle"] = _shorter(il["subtitle"])
            else:
                il["title"] = _shorter(il["title"])
            hit = True
        if not hit:
            break
        did.append("shortened a label that didn't fit")
    return did[0] if did else ""


def check_paper(ed, text, date, number=1, out_pdf=None):
    """Check a chatbot's reply. Returns a dict the page shows:
    ok, problem (a sentence for the parent), errors, fix (text to paste back to the chatbot),
    fill (optional text asking for fuller columns), trimmed (what was cut to fit), pdf (path)
    and issue (the JSON as printed)."""
    issue, problem = _parse(text)
    if problem:
        return {"ok": False, "problem": problem, "errors": [], "fix": ""}
    issue.update({"edition": ed["id"], "date": date, "issue": int(number), "volume": issue.get("volume") or 1})
    issue, fixed = repair(ed, issue)
    issue, cut = fit(ed, issue, limit=CHAT_TRIM_LIMIT)
    path = os.path.join(checks.issues_dir(ed), date[:4], f"{date}.json")
    r = checks.check_issue(ed, issue, path, archive=False, as_of=dt.date.fromisoformat(date), require_fill=False)
    res = {"ok": r.ok, "errors": r.errors, "issue": json.dumps(issue, ensure_ascii=False, indent=2),
           "problem": "", "fix": "", "fill": "",
           "trimmed": [f"{n} sentence{'s' if n > 1 else ''} from the end of {_name(ed, b)}" for b, n in cut.items()],
           "repaired": fixed}
    if not r.ok:
        res["problem"] = (f"{len(r.errors)} thing{'s' if len(r.errors) != 1 else ''} to fix before it can print. "
                          "Copy the fix list below into the chatbot, then paste its new reply here.")
        res["fix"] = _fix_message("newspaper", r.errors, ed["name"])
        return res
    try:
        gaps = [m for m in render.measure(ed, issue) if m["free_lines"] > FREE_LINES]
    except Exception:
        gaps = []
    if gaps:
        res["fill"] = ("The paper prints, but some columns have empty space. If you'd like it fuller, add "
                       "sourced detail to the stories or sections in these columns and reply with the "
                       "complete JSON:\n\n" + "\n".join(
                           f"- page {m['page']} column {m['column']} ({', '.join(m['blocks'])}): about "
                           f"{m['free_lines']:.0f} empty lines" for m in gaps))
    res["pdf"] = render.build(ed, issue, out_pdf or f"/tmp/{ed['id']}_{date}.pdf")
    return res


# ------------------------------------------------------------------ the Big Question poster
POSTER_RULES = """

RULES FOR THIS CHAT (these override anything above about commands or files):
- Today is {today}. Search the web for this week's news first. Every news fact, name, place and number must
  come from a page you found in this search, never from memory. Evergreen science in try_it may use
  well-established facts. If you cannot search the web, reply only: "I can't search the web, so I can't
  write this week's poster." and stop.
- Write for {reader}.
- "sources" is a list of the URLs (strings) of the pages your facts came from.
- hero.motif and every steps[].motif must be one of: {motifs}.
- Use only characters the PDF fonts can print: plain English punctuation plus • — “ ” é ü. No arrows, no "…".
- Reply with the poster JSON only, in a single ```json code block, shaped exactly like this. If the grown-up
  sends back a list of fixes, make every fix and reply with the complete corrected JSON.
```json
{shape}
```"""


def _without_section(md, heading):
    start = md.find(heading)
    if start < 0:
        return md
    nxt = md.find("\n## ", start + len(heading))
    return md[:start] + (md[nxt + 1:] if nxt >= 0 else "")


def poster_instructions(ed, date):
    guide = open(os.path.join(edition.ROOT, "docs", "POSTERS.md"), encoding="utf-8").read()
    guide = _without_section(guide, "## Automatic posters")
    day = dt.date.fromisoformat(date)
    return guide + POSTER_RULES.format(
        today=f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}",
        reader=f"ages {ed['reader']['age']}: {ed['reader']['profile']}",
        motifs=", ".join(poster.HERO_MOTIFS),
        shape=json.dumps(poster.skeleton(ed, date), ensure_ascii=False, indent=1))


def check_poster(ed, text, date, out_pdf=None):
    spec, problem = _parse(text)
    if problem:
        return {"ok": False, "problem": problem, "errors": [], "fix": ""}
    spec.update({"edition": ed["id"], "date": date})
    r = poster.check(ed, spec, poster.path_for(ed, date))
    res = {"ok": r.ok, "errors": r.errors, "problem": "", "fix": "", "fill": ""}
    if not r.ok:
        res["problem"] = (f"{len(r.errors)} thing{'s' if len(r.errors) != 1 else ''} to fix before it can print. "
                          "Copy the fix list below into the chatbot, then paste its new reply here.")
        res["fix"] = _fix_message("poster", r.errors, ed["name"])
        return res
    res["pdf"] = poster.build(ed, spec, out_pdf or f"/tmp/{ed['id']}_{date}_poster.pdf")
    return res
