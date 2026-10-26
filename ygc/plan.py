"""The day's angle plan: data/plans/<date>.json, written after research and before any paper.

    {"date": "2026-10-27",
     "papers": {"breakfast-table": {"lead": "<pool story id>", "angle": "What the airport reopening means for families who fly"},
                "europe-explained": {"lead": "<pool story id>", "angle": "Why traders price in risk before any oil is lost"}}}

Each due paper names its lead story (an id from data/pools/<date>.json) and the angle it will take, from its
`lens` in edition.yaml. The biggest story may lead several papers (news value first), but papers that share a
lead must take different angles, and each angle needs facts in the pool. `ygc plan` checks the plan;
`ygc check --plan` holds an issue to it. See docs/ANGLES.md.
"""
import json
import re

ANGLE_CHARS = 240


def _norm(t):
    return re.sub(r"[^a-z0-9]+", " ", str(t).lower()).strip()


def pool_stories(pool):
    return {s["id"]: s for desk in pool.values() if isinstance(desk, dict)
            for s in desk.get("stories", []) if isinstance(s, dict) and s.get("id")}


def check(plan, pool=None, due=None):
    """Errors and notes for a plan; `due` is the list of paper ids due that day."""
    errors, notes = [], []
    papers = plan.get("papers") if isinstance(plan, dict) else None
    if not isinstance(papers, dict) or not papers:
        return ["plan.papers must map each due paper to {lead, angle}"], notes
    stories = pool_stories(pool) if pool else None
    by_lead = {}
    for eid, p in papers.items():
        at = f"papers.{eid}"
        if not isinstance(p, dict):
            errors.append(f"{at} must be {{lead, angle}}")
            continue
        lead, angle = str(p.get("lead", "")).strip(), str(p.get("angle", "")).strip()
        if not lead:
            errors.append(f"{at}.lead: name the lead story's id from the research pool")
        elif stories is not None and lead not in stories:
            errors.append(f"{at}.lead: {lead!r} is not a story id in the research pool")
        if not angle:
            errors.append(f"{at}.angle: say in one sentence how this paper will tell its lead")
        elif len(angle) > ANGLE_CHARS:
            errors.append(f"{at}.angle: at most {ANGLE_CHARS} characters")
        by_lead.setdefault(lead, []).append((eid, _norm(angle)))
    for lead, rows in by_lead.items():
        seen = {}
        for eid, a in rows:
            if a and a in seen:
                errors.append(f"papers.{eid}.angle is the same as papers.{seen[a]}.angle; papers that share a lead "
                              f"take different angles (each from its lens)")
            seen.setdefault(a, eid)
        if len(rows) >= 4:
            notes.append(f"{len(rows)} papers lead with {lead!r}; fine if it is clearly the day's biggest story")
    if due is not None:
        for eid in sorted(set(due) - set(papers)):
            errors.append(f"papers.{eid}: missing; every paper due today needs a lead and an angle")
    return errors, notes


def lead_errors(plan, pool, eid, issue, lead_block):
    """`ygc check --plan`: the issue's lead must be the planned story (it cites one of that story's sources)."""
    from .auto.llm import norm_url
    p = (plan.get("papers") or {}).get(eid)
    if not p:
        return [f"this paper is not in the day's plan; add it to data/plans/{plan.get('date', '<date>')}.json"]
    story = pool_stories(pool).get(p.get("lead"))
    if not story:
        return []
    want = {norm_url(s.get("url", "")) for s in story.get("sources", [])} | \
           {norm_url(f.get("source_url", "")) for f in story.get("key_facts", [])}
    block = (issue.get("blocks") or {}).get(lead_block) or {}
    have = {norm_url(s.get("url", "") if isinstance(s, dict) else str(s)) for s in block.get("sources", []) or []}
    if not want & have:
        return [f"blocks.{lead_block}: the plan says this paper leads with {p['lead']!r}, but the lead cites none of "
                f"that story's sources"]
    return []


def load(path):
    return json.load(open(path, encoding="utf-8"))
