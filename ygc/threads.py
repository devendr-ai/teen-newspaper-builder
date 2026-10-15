"""The story so far: one page per big ongoing story, so a child who missed last week isn't lost.

A thread lives in threads/<id>.json and grows each night: a line on its timeline for each new
development, "in one minute", who's who and questions people ask, written twice (younger readers,
ages 6-11, and older readers, 12+). Stories join a thread through their issue's `threads` field
({"lead": "yemen-war"}) or, for papers published before threads existed, the thread's own
`stories` list. Each timeline line says when it happened (`date`) and which day's papers reported it
(`reported`), so "Read it" opens the right story. A thread is active while it has news in the
last week; then it rests in the archive.
See docs/STORY_SO_FAR.md.
"""
import datetime as dt
import glob
import json
import os
import re

from .edition import ROOT

DIR = os.path.join(ROOT, "threads")
LEVELS = ("younger", "older")
ACTIVE_DAYS = 7         # a thread with news in the last week is "right now"
MAX_ACTIVE = 3          # the most the front page shows
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LIMITS = {               # words: (younger, older)
    "one_minute": (55, 85), "about": (14, 20), "a": (45, 70), "line": (25, 40), "worry": (70, 90),
}


def path(tid):
    return os.path.join(DIR, f"{tid}.json")


def exists(tid):
    return bool(tid) and ID_RE.match(str(tid)) is not None and os.path.exists(path(tid))


def load_all():
    out = []
    for p in sorted(glob.glob(os.path.join(DIR, "*.json"))):
        t = json.load(open(p, encoding="utf-8"))
        t.setdefault("id", os.path.basename(p)[:-5])
        out.append(t)
    return out


def level_of(band):
    """Read & Play's age band -> which version of a thread: ages 6-11 read the younger one."""
    return "younger" if band in ("Ages 6–8", "Ages 9–11") else "older"


def last_news(t, linked_dates=()):
    dates = [e["date"] for e in t.get("timeline", []) if e.get("date")] + list(linked_dates)
    return max(dates) if dates else t.get("opened", "")


def is_active(t, newest, linked_dates=()):
    last = last_news(t, linked_dates)
    try:
        return (dt.date.fromisoformat(newest) - dt.date.fromisoformat(last)).days <= ACTIVE_DAYS
    except ValueError:
        return False


def story_index(issues):
    """{(paper, date, block): thread id}, from issues' `threads` and threads' `stories` lists.
    `issues` is [(paper id, date, issue dict)]."""
    idx = {}
    for t in load_all():
        for s in t.get("stories") or []:
            idx[(s.get("paper"), s.get("date"), s.get("block"))] = t["id"]
    for eid, date, issue in issues:
        for bid, tid in (issue.get("threads") or {}).items():
            idx[(eid, date, bid)] = tid
    return idx


# ------------------------------------------------------------------ checks
def _words(s):
    return len(re.findall(r"\S+", str(s or "")))


def check(t, as_of=None):
    """Errors and notes for one thread file, as a checks.Report."""
    from .checks import Report
    from . import world
    r = Report()
    tid = t.get("id", "")
    if not ID_RE.match(str(tid)):
        r.err(f"id {tid!r}: lower-case words joined by hyphens, like 'yemen-war'")
    title = str(t.get("title", "")).strip()
    if not title or len(title) > 40:
        r.err("title: a short name for the story, at most 40 characters, like 'The war in Yemen'")
    try:
        dt.date.fromisoformat(t.get("opened", ""))
    except (TypeError, ValueError):
        r.err("opened: the date the thread began, YYYY-MM-DD")
    w = t.get("where")
    if w is not None:
        ok = isinstance(w, dict) and all(isinstance(w.get(k), (int, float)) and not isinstance(w.get(k), bool)
                                         for k in ("lat", "lon"))
        if not ok or not (-90 <= w["lat"] <= 90 and -180 <= w["lon"] <= 180):
            r.err("where: {place, lat, lon, countries} with lat -90..90 and lon -180..180")
        else:
            for c in w.get("countries") or []:
                if not world.country_name(c):
                    r.note(f"where: {c!r} isn't a country on the map, so it won't be coloured in")
    for li, level in enumerate(LEVELS):
        v = t.get(level)
        if not isinstance(v, dict):
            r.err(f"{level}: missing (every thread is written for younger and older readers)")
            continue
        if not str(v.get("one_minute", "")).strip():
            r.err(f"{level}.one_minute is empty")
        elif _words(v["one_minute"]) > LIMITS["one_minute"][li]:
            r.err(f"{level}.one_minute: {_words(v['one_minute'])} words, at most {LIMITS['one_minute'][li]}")
        who = v.get("who") or []
        if not 2 <= len(who) <= 6:
            r.err(f"{level}.who: 2 to 6 people or groups, found {len(who)}")
        for i, p in enumerate(who):
            if not (isinstance(p, dict) and str(p.get("name", "")).strip() and str(p.get("about", "")).strip()):
                r.err(f"{level}.who[{i}]: needs a name and an about")
            elif _words(p["about"]) > LIMITS["about"][li]:
                r.err(f"{level}.who[{i}].about: at most {LIMITS['about'][li]} words")
        qs = v.get("questions") or []
        if len(qs) > 4:
            r.err(f"{level}.questions: at most 4")
        for i, q in enumerate(qs):
            if not (isinstance(q, dict) and str(q.get("q", "")).strip() and str(q.get("a", "")).strip()):
                r.err(f"{level}.questions[{i}]: needs a q and an a")
            elif _words(q["a"]) > LIMITS["a"][li]:
                r.err(f"{level}.questions[{i}].a: at most {LIMITS['a'][li]} words")
        if v.get("worry") and _words(v["worry"]) > LIMITS["worry"][li]:
            r.err(f"{level}.worry: at most {LIMITS['worry'][li]} words")
    tl = t.get("timeline") or []
    if not tl:
        r.err("timeline: at least one dated line")
    last = None
    today = as_of or dt.date.today()
    for i, e in enumerate(tl):
        at = f"timeline[{i}]"
        try:
            d = dt.date.fromisoformat(e.get("date", ""))
        except (TypeError, ValueError, AttributeError):
            r.err(f"{at}.date: YYYY-MM-DD (use `when` to show 'July 2026' or '2014' instead)")
            continue
        if d > today + dt.timedelta(days=1):
            r.err(f"{at}.date {d} is in the future")
        if last and d < last:
            r.err(f"{at}: the timeline must run oldest first")
        last = d
        if not str(e.get("older", "")).strip():
            r.err(f"{at}.older is empty")
        if e.get("reported"):
            try:
                if dt.date.fromisoformat(e["reported"]) < d:
                    r.err(f"{at}.reported: the paper that reported it can't be older than the event")
            except (TypeError, ValueError):
                r.err(f"{at}.reported: the date of the papers that reported it, YYYY-MM-DD")
        for li, level in enumerate(LEVELS):
            if e.get(level) and _words(e[level]) > LIMITS["line"][li]:
                r.err(f"{at}.{level}: one short sentence, at most {LIMITS['line'][li]} words")
    for s in t.get("stories") or []:
        if not (isinstance(s, dict) and s.get("paper") and s.get("date") and s.get("block")):
            r.err("stories: each is {paper, date, block}")
    srcs = t.get("sources") or []
    if not srcs or not all(isinstance(u, str) and u.startswith(("http://", "https://")) for u in srcs):
        r.err("sources: the URLs the thread's facts come from (from the papers' own sources)")
    if "…" in json.dumps({k: t.get(k) for k in ("title", "younger", "older", "timeline")}, ensure_ascii=False):
        r.err("contains '…': end sentences properly")
    return r
