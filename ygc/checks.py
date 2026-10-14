"""Quality gate for one issue, driven entirely by its edition.

Nothing here knows how many pages, which countries or which sections a paper
has: it reads the edition and checks the issue against it.
"""
import datetime as dt
import glob
import json
import os
import re

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph

from . import render
from .edition import placed_blocks, desk, story_blocks
from .graphics import IllustrationCard
from .styles import make_styles

FNAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")


class Report:
    def __init__(self):
        self.errors, self.notes = [], []

    def err(self, m):
        self.errors.append(m)

    def note(self, m):
        self.notes.append(m)

    @property
    def ok(self):
        return not self.errors


# ------------------------------------------------------------------ helpers
def today(ed):
    from zoneinfo import ZoneInfo
    tz = os.environ.get("YGC_TZ") or ed["cadence"]["timezone"]
    return dt.datetime.now(ZoneInfo(tz)).date()


def issues_dir(ed):
    return os.path.join(ed["_dir"], "issues")


def archived(ed, before, exclude=None, n=None):
    found = []
    for p in glob.glob(os.path.join(issues_dir(ed), "**", "*.json"), recursive=True):
        if exclude and os.path.abspath(p) == os.path.abspath(exclude):
            continue
        m = FNAME_RE.search(os.path.basename(p))
        if m and dt.date.fromisoformat(m.group(1)) < before:
            found.append((dt.date.fromisoformat(m.group(1)), p))
    found.sort(reverse=True)
    found = found[:n] if n else found
    return [(d, p, json.load(open(p, encoding="utf-8"))) for d, p in found]


def walk(node, path="$"):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")


def _printable(ch):
    try:
        ch.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


def _lines(text, style, w):
    _, h = Paragraph(text, style).wrap(w, 10 ** 6)
    return round(h / style.leading)


def _block_width(ed, bid):
    for p, page in enumerate(ed["pages"]):
        for col in page["columns"]:
            if bid in col:
                return render.col_width(len(page["columns"]))
    return render.col_width(2)


# ------------------------------------------------------------------ checks
def check_identity(ed, issue, path, r, archive, as_of=None):
    if issue.get("edition") != ed["id"]:
        r.err(f"issue.edition is {issue.get('edition')!r}, expected {ed['id']!r}")
    try:
        d = render.date_of(issue)
    except Exception:
        r.err("issue.date must be an ISO date like 2026-10-10")
        return None
    m = FNAME_RE.search(os.path.basename(path))
    if not m:
        r.err("file name must be YYYY-MM-DD.json")
    elif m.group(1) != issue["date"]:
        r.err(f"file name date {m.group(1)} does not match issue.date {issue['date']}")
    now = as_of or today(ed)
    if not archive and d != now:
        r.err(f"issue.date is {d} but today in {ed['cadence']['timezone']} is {now} "
              f"(take the date from the device, never from the prompt)")
    if not isinstance(issue.get("issue"), int):
        r.err("issue.issue (the issue number) must be an integer")
        return d
    prev = archived(ed, d, exclude=path, n=1)
    if prev:
        pd, _, old = prev[0]
        if old.get("issue") is not None and issue["issue"] != old["issue"] + 1:
            r.err(f"issue No. {issue['issue']}, but the previous issue ({pd}) is "
                  f"No. {old['issue']}; expected No. {old['issue'] + 1}")
        gap = (d - pd).days
        if gap != ed["cadence"]["every_days"] and not archive:
            r.note(f"{gap} days since the previous issue; cadence is every "
                   f"{ed['cadence']['every_days']} day(s)")
    else:
        r.note("no earlier issue in the archive: numbering and repetition not checked")
    return d


def check_blocks(ed, issue, r):
    blocks = issue.get("blocks", {})
    placed = placed_blocks(ed)
    for bid in blocks:
        if bid not in ed["blocks"]:
            r.err(f"blocks.{bid}: not a block in this edition (choose from {placed})")
    S = make_styles(float(ed["style"].get("type_scale", 1.0)))
    for bid in placed:
        cfg = ed["blocks"][bid]
        t = cfg["type"]
        s = blocks.get(bid)
        if s is None:
            if t != "sign_off":
                r.err(f"blocks.{bid} ({t}) is missing")
            continue
        w = _block_width(ed, bid)
        where = f"blocks.{bid}"
        if t == "story":
            for k in ("kicker", "headline"):
                if k not in s:
                    r.err(f"{where}.{k} is missing")
            if "body" not in s or not s["body"]:
                r.err(f"{where}.body needs at least one paragraph")
            label = desk(ed, cfg["desk"])["label"]
            if s.get("kicker") and not s["kicker"].upper().startswith(label.upper()):
                r.note(f"{where}.kicker should start with its desk label {label!r}")
            size = cfg.get("size", "standard")
            head = {"lead": "headline_big", "standard": "headline_med",
                    "compact": "headline_sm"}[size]
            if s.get("headline") and _lines(s["headline"], S[head], w) > 3:
                r.err(f"{where}.headline runs to more than 3 lines; shorten it")
            if s.get("kicker") and _lines(s["kicker"], S["section_tag"], w) > 1:
                r.err(f"{where}.kicker wraps; keep it to one line")
            for g in cfg.get("graphics", []):
                if g not in s:
                    r.err(f"{where}.{g} is required by the edition")
            for x in cfg.get("extras", []):
                if x not in s:
                    r.err(f"{where}.{x} is required by the edition")
            if cfg.get("also"):
                n = cfg["also"]["count"]
                if len(s.get("also", [])) != n:
                    r.err(f"{where}.also: expected {n} items")
            check_graphics(ed, s, where, w, r)
        elif t == "feature":
            if not s.get("title") or not s.get("body"):
                r.err(f"{where} needs a title and body")
            check_graphics(ed, s, where, w, r)
        elif t in ("briefs", "watchlist"):
            if len(s.get("items", [])) != cfg["count"]:
                r.err(f"{where}.items: expected {cfg['count']}, found {len(s.get('items', []))}")
        elif t == "vocab":
            items = s.get("items", [])
            if len(items) != cfg["count"]:
                r.err(f"{where}.items: expected {cfg['count']} words, found {len(items)}")
            if ed["teaching"]["vocab_today"]:
                for v in items:
                    if "Today:" not in v.get("def", ""):
                        r.err(f"{where}: {v.get('word')!r} must show the word in this issue "
                              f"after 'Today:'")
        elif t == "did_you_know" and not s.get("text"):
            r.err(f"{where}.text is empty")
        elif t == "sports" and not (s.get("title") and s.get("body")):
            r.err(f"{where} needs a title and body")
        elif t == "quote" and not s.get("text"):
            r.err(f"{where}.text is empty")


def check_graphics(ed, s, where, W, r):
    ch = s.get("chart")
    if ch:
        labels, values = ch.get("labels", []), ch.get("values", [])
        n = len(values)
        if len(labels) != n:
            r.err(f"{where}.chart: {len(labels)} labels but {n} values")
        if not 2 <= n <= 4:
            r.err(f"{where}.chart: {n} bars; use 2-4")
        if values and not all(isinstance(v, (int, float)) for v in values):
            r.err(f"{where}.chart.values must be numbers")
        elif values and ch.get("max") is not None and ch["max"] < max(values):
            r.err(f"{where}.chart.max {ch['max']} is below the largest value {max(values)}")
        for k, lim in (("title", 46), ("subtitle", 52)):
            if len(ch.get(k, "")) > lim:
                r.err(f"{where}.chart.{k}: {len(ch[k])} chars; the chart cuts it at {lim}")
        if n:
            house = ed["teaching"]["chart_label_limits"].get(n, 8)
            chart_w = W - 26 - 8
            bar_w = chart_w / (n * 1.8)
            pitch = bar_w + (chart_w - bar_w * n) / (n + 1)
            for lab in labels:
                if len(lab) > house:
                    r.err(f"{where}.chart label {lab!r}: keep labels to {house} chars with {n} bars")
                if len(lab) > 14 or stringWidth(lab, "Helvetica", 5.5) > pitch - 4:
                    r.err(f"{where}.chart label {lab!r} collides with its neighbour")
    mp = s.get("map")
    if mp:
        for k, font, size, room in (("title", "Helvetica-Bold", 6.5, 0.90),
                                    ("label_top", "Helvetica-Bold", 7, 0.90),
                                    ("label_bottom", "Helvetica-Bold", 7, 0.90),
                                    ("footnote", "Helvetica-Oblique", 6, 0.94)):
            if mp.get(k) and stringWidth(mp[k], font, size) > W * room:
                r.err(f"{where}.map.{k} runs past the edge of the map")
    il = s.get("illustration")
    if il:
        if il.get("motif") not in IllustrationCard._MOTIFS:
            r.err(f"{where}.illustration.motif {il.get('motif')!r}: choose one of "
                  f"{', '.join(IllustrationCard.known_motifs())}")
        t, sub = il.get("title", ""), il.get("subtitle", "")
        if len(t) > 44 or len(sub) > 25:
            r.err(f"{where}.illustration: title max 44 chars, subtitle max 25")
        if stringWidth(t, "Helvetica-Bold", 6.5) + stringWidth(sub, "Helvetica-Oblique", 5.5) > W - 20:
            r.err(f"{where}.illustration: title and subtitle overlap")


def check_unfilled(ed, issue, r):
    """The skeleton's placeholders must all be replaced before anything else matters."""
    empty = [p for p, s in walk(issue.get("blocks", {}), "blocks")
             if not s.strip() and not p.endswith(".by") and not p.endswith(".value_prefix")]
    if empty:
        shown = ", ".join(empty[:6]) + (f" and {len(empty) - 6} more" if len(empty) > 6 else "")
        r.err(f"{len(empty)} field(s) still empty: {shown}")
    for bid, b in issue.get("blocks", {}).items():
        if not isinstance(b, dict):
            continue
        if isinstance(b.get("kicker"), str) and b["kicker"].rstrip().endswith("•"):
            r.err(f"blocks.{bid}.kicker needs its detail after the desk label, e.g. 'WORLD  •  NOBEL PRIZE'")
        ch = b.get("chart")
        if isinstance(ch, dict) and (not ch.get("max") or not any(ch.get("values") or [])):
            r.err(f"blocks.{bid}.chart still has placeholder numbers (values and max must be real)")
        il = b.get("illustration")
        if isinstance(il, dict) and "|" in str(il.get("motif", "")):
            r.err(f"blocks.{bid}.illustration.motif: pick one motif from the list")


def unbuildable(r):
    return any(k in e for e in r.errors for k in ("is missing", "still empty", "placeholder", "pick one motif",
                                                   "must be numbers", "labels but"))


def check_text(issue, r):
    for path, s in walk(issue.get("blocks", {}), "blocks"):
        if "…" in s:
            r.err(f"{path}: contains '…'")
        bad = sorted({c for c in s if c != "…" and not _printable(c)})
        if bad:
            r.err(f"{path}: the PDF fonts cannot print {' '.join(bad)} (black boxes)")


def check_repetition(ed, issue, path, d, r):
    n = ed["teaching"]["repeat_window"]
    if not n or d is None:
        return
    blocks = issue.get("blocks", {})
    vocab_ids = [b for b, c in ed["blocks"].items() if c["type"] == "vocab"]
    dyk_ids = [b for b, c in ed["blocks"].items() if c["type"] == "did_you_know"]

    def words(t):
        return set(re.findall(r"[a-z]{4,}", t.lower()))

    mine_v = {v["word"].strip().lower() for b in vocab_ids
              for v in blocks.get(b, {}).get("items", [])}
    mine_d = words(" ".join(blocks.get(b, {}).get("text", "") for b in dyk_ids))
    for od, _, old in archived(ed, d, exclude=path, n=n):
        ob = old.get("blocks", {})
        old_v = {v["word"].strip().lower() for b in vocab_ids for v in ob.get(b, {}).get("items", [])}
        for w in sorted(mine_v & old_v):
            r.err(f"vocab word {w!r} was already used on {od}")
        old_d = words(" ".join(ob.get(b, {}).get("text", "") for b in dyk_ids))
        if mine_d and old_d and len(mine_d & old_d) / len(mine_d | old_d) > 0.45:
            r.err(f"Did You Know looks like the one used on {od}")


def check_play(ed, issue, r):
    """The online-only `play` section behind Read & Play's quiz and fact-or-fiction games."""
    p = issue.get("play")
    if p is None:
        r.note("no play section: Read & Play offers word games only for this issue")
        return
    if not isinstance(p, dict):
        r.err("play must be an object with quiz and fact_or_fiction")
        return
    from .skeleton import play_counts
    nq, nf = play_counts(ed)
    stories = set(story_blocks(ed))
    quiz, facts = p.get("quiz") or [], p.get("fact_or_fiction") or []
    if len(quiz) != nq:
        r.err(f"play.quiz: expected {nq} questions, found {len(quiz)}")
    if len(facts) != nf:
        r.err(f"play.fact_or_fiction: expected {nf} claims, found {len(facts)}")
    for kind, items in (("quiz", quiz), ("fact_or_fiction", facts)):
        for i, q in enumerate(items):
            w = f"play.{kind}[{i}]"
            if not isinstance(q, dict):
                r.err(f"{w} must be an object")
                continue
            if not str(q.get("q" if kind == "quiz" else "claim", "")).strip():
                r.err(f"{w}.{'q' if kind == 'quiz' else 'claim'} is empty")
            if not str(q.get("why", "")).strip():
                r.err(f"{w}.why is empty: say in one sentence where the paper shows it")
            if q.get("story") and q["story"] not in stories:
                r.err(f"{w}.story {q['story']!r}: use one of {', '.join(sorted(stories))}")
            if kind == "quiz":
                opts = [str(o).strip() for o in q.get("options") or []]
                if len(opts) != 3 or not all(opts) or len({o.lower() for o in opts}) != 3:
                    r.err(f"{w}.options: exactly 3 different, non-empty answers")
                if q.get("answer") not in (0, 1, 2) or isinstance(q.get("answer"), bool):
                    r.err(f"{w}.answer must be 0, 1 or 2: the position of the right option")
            elif not isinstance(q.get("true"), bool):
                r.err(f"{w}.true must be true or false")
    if len(facts) >= 2 and len({f.get("true") for f in facts if isinstance(f, dict)}) < 2:
        r.err("play.fact_or_fiction: include at least one true claim and one that isn't true")


def check_sources(ed, issue, r, archive):
    if not ed.get("sources_required"):
        return
    for bid in placed_blocks(ed):
        cfg = ed["blocks"][bid]
        if cfg["type"] not in ("story", "feature") or cfg.get("sources") is False:
            continue
        s = issue.get("blocks", {}).get(bid) or {}
        urls = [u.get("url", "") if isinstance(u, dict) else str(u) for u in s.get("sources", [])]
        if not [u for u in urls if re.match(r"https?://", u)]:
            (r.note if archive else r.err)(f"blocks.{bid}: no sources listed")


def check_fit(ed, issue, r):
    for m in render.measure(ed, issue):
        where = f"page {m['page']} column {m['column']} ({', '.join(m['blocks'])})"
        if m["over"] > 0.5:
            r.err(f"{where} is OVER by {m['over']:.0f} pt — cut about "
                  f"{m['over_lines']:.1f} lines (~{m['over_chars']} characters)")
        elif m["free_lines"] > 4:
            r.note(f"{where} ends {m['free_lines']:.0f} lines short; add a sentence "
                   f"or rebalance")


def check_issue(ed, issue, path, archive=False, as_of=None):
    r = Report()
    d = check_identity(ed, issue, path, r, archive, as_of)
    check_unfilled(ed, issue, r)
    check_blocks(ed, issue, r)
    check_text(issue, r)
    check_repetition(ed, issue, path, d, r)
    check_sources(ed, issue, r, archive)
    check_play(ed, issue, r)
    if not unbuildable(r):
        try:
            check_fit(ed, issue, r)
        except Exception as e:
            r.err(f"could not lay out the issue: {e!r}")
    return r
