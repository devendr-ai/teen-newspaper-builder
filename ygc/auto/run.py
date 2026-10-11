"""Orchestrator: which editions are due, shared research, writing, saving, report."""
import datetime as dt
import json
import os

from .. import checks, edition
from . import research, writer
from .llm import BudgetExceeded, Client, Usage

DATA = os.path.join(edition.ROOT, "data")


def local_today(ed):
    return checks.today(ed)


def is_due(ed, date):
    auto = ed.get("automation") or {}
    if not auto.get("enabled"):
        return False
    every = ed["cadence"]["every_days"]
    weekday = auto.get("weekday")          # weekly papers can pin a publishing day, e.g. "saturday"
    pinned = bool(weekday) and every >= 7
    # An issue published off its pinned day (by hand, or a retry) must not push the next
    # pinned day back a whole cycle, so pinned papers only need a gap of one day less.
    gap = every - 1 if pinned else every
    for d, _, _ in checks.archived(ed, date + dt.timedelta(days=1), n=1):
        if (date - d).days < gap:
            return False
    if pinned and date.strftime("%A").lower() != weekday.lower():
        return False
    return True


def next_number(ed, date):
    prev = checks.archived(ed, date, n=1)
    if prev:
        return prev[0][2]["issue"] + 1, prev[0][2].get("volume", 1)
    return (ed.get("automation") or {}).get("first_issue", 1), 1


def estimate(eds):
    """Rough cost before running: research per desk group plus writing per edition."""
    groups = research.desk_groups(eds)
    pages = sum(len(e["pages"]) for e in eds)
    return round(len(groups) * 0.30 + len(eds) * 0.25 + pages * 0.06, 2), len(groups)


def run(only=None, date_override=None, dry_run=False, budget=None, transport=None, log=print):
    eds = [edition.load(e) for e in edition.list_editions()]
    if only:
        eds = [e for e in eds if e["id"] in only]
    due = []
    for ed in eds:
        d = dt.date.fromisoformat(date_override) if date_override else local_today(ed)
        if is_due(ed, d) or (only and (ed.get("automation") or {}).get("enabled")):
            due.append((ed, d))
    est, ngroups = estimate([e for e, _ in due])
    log(f"{len(due)} edition(s) due, {ngroups} research desk(s), estimated ${est:.2f}")
    for ed, d in due:
        log(f"  - {ed['id']} ({d})")
    if dry_run or not due:
        return {"due": [e["id"] for e, _ in due], "estimate_usd": est, "dry_run": dry_run}

    budget = budget if budget is not None else float(os.environ.get("YGC_DAILY_BUDGET", 15))
    usage = Usage(budget_usd=budget)
    client = Client(usage=usage, transport=transport)
    run_date = max(d for _, d in due)
    report = {"date": run_date.isoformat(), "model": client.model, "editions": {}, "research": {}}

    # ---- stage 1: research, once per desk group
    pool = {}
    for key, g in research.desk_groups([e for e, _ in due]).items():
        log(f"research: {g['label']} ({g['hours']}h)")
        try:
            pool[key] = research.research_group(client, key, g, run_date)
            report["research"][key] = {"stories": len(pool[key]["stories"]),
                                       "dropped_unverified": pool[key]["dropped_unverified"]}
        except BudgetExceeded as e:
            report["stopped"] = str(e); break
        except Exception as e:
            report["research"][key] = {"error": str(e)[:300]}
    pool_path = os.path.join(DATA, "pools", f"{run_date.isoformat()}.json")
    os.makedirs(os.path.dirname(pool_path), exist_ok=True)
    json.dump(pool, open(pool_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---- stage 2: write each due edition
    for ed, d in due:
        if "stopped" in report:
            report["editions"][ed["id"]] = {"status": "skipped", "reason": report["stopped"]}
            continue
        number, volume = next_number(ed, d)
        path = os.path.join(checks.issues_dir(ed), str(d.year), f"{d.isoformat()}.json")
        log(f"write: {ed['id']} No. {number}")
        spent0 = usage.usd
        try:
            issue, rep = writer.write_edition(client, ed, d, number, volume, pool, path, log=log)
        except BudgetExceeded as e:
            report["stopped"] = str(e)
            issue, rep = None, {"status": "skipped", "reason": str(e)}
        except Exception as e:
            issue, rep = None, {"status": "failed", "reason": str(e)[:300]}
        rep["usd"] = round(usage.usd - spent0, 4)
        if issue:
            issue["pool"] = f"data/pools/{run_date.isoformat()}.json"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(issue, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            rep["file"] = os.path.relpath(path, edition.ROOT)
        report["editions"][ed["id"]] = rep
        log(f"  {rep['status']}" + (f" ({rep.get('reason') or ''})" if rep["status"] != "passed" else "")
            + f"  ${rep['usd']:.2f}")

    report["usage"] = usage.as_dict()
    rpath = os.path.join(DATA, "runs", f"{run_date.isoformat()}.json")
    os.makedirs(os.path.dirname(rpath), exist_ok=True)
    json.dump(report, open(rpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    ok = sum(1 for r in report["editions"].values() if r["status"] == "passed")
    log(f"done: {ok}/{len(due)} published, ${usage.usd:.2f} spent")
    for eid, r in report["editions"].items():
        if r["status"] != "passed" and os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning title={eid} not published::{r.get('reason') or r.get('last_feedback', '')[:300]}")
    return report
