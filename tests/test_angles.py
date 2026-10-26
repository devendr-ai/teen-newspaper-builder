"""Angles: each paper's lens, the day's plan, and the copy check (docs/ANGLES.md)."""
import copy
import datetime as dt
import json
import os
import subprocess
import sys

import pytest

from ygc import checks, edition, plan, prompt

ROOT = edition.ROOT
DAY = "2026-10-26"


def load(eid, d=DAY):
    return json.load(open(os.path.join(ROOT, "editions", eid, "issues", d[:4], f"{d}.json"), encoding="utf-8"))


def test_every_paper_but_the_little_explorer_has_a_lens_in_its_prompt():
    for eid in edition.list_editions():
        ed, text = edition.load(eid), prompt.generate(edition.load(eid))
        if eid == "little-explorers":
            assert "lens" not in ed and "This paper's angle." not in text
        else:
            assert ed["lens"].strip() and f"**This paper's angle.** {ed['lens'].strip()}" in text, eid
    assert "broad" in edition.load("current-affairs-digest")["lens"]
    assert "own angle and in its own words" in prompt.generate(edition.load("little-explorers"))   # the craft rule


def test_a_lens_must_be_text():
    ed = edition.load("junior-daily")
    bad = dict(ed, lens=["not", "text"])
    assert any("lens must be a sentence" in e for e in edition.validate(bad, "junior-daily"))


def place(tmp_path, monkeypatch, issues):
    """Put issues for a future date in a throwaway copy of the editions folder."""
    root = tmp_path / "root"
    for eid in edition.list_editions():
        src = os.path.join(ROOT, "editions", eid)
        dst = root / "editions" / eid
        (dst / "issues" / "2026").mkdir(parents=True)
        for f in ("edition.yaml",):
            (dst / f).write_text(open(os.path.join(src, f), encoding="utf-8").read(), encoding="utf-8")
    monkeypatch.setattr(edition, "ROOT", str(root))
    paths = {}
    for eid, issue in issues.items():
        p = root / "editions" / eid / "issues" / "2026" / f"{issue['date']}.json"
        p.write_text(json.dumps(issue), encoding="utf-8")
        paths[eid] = str(p)
    return paths


def copy_check(ed, issue, path):
    r = checks.Report()
    checks.check_copies(ed, issue, path, dt.date.fromisoformat(issue["date"]), r)
    return r.errors


def test_the_copy_check_catches_a_copied_lead_and_headline(tmp_path, monkeypatch):
    bt, jd = load("breakfast-table"), load("junior-daily")
    for i in (bt, jd):
        i["date"] = "2026-10-27"
    jd["blocks"]["lead"] = copy.deepcopy(bt["blocks"]["lead"])
    paths = place(tmp_path, monkeypatch, {"breakfast-table": bt, "junior-daily": jd})
    errs = copy_check(edition.load("junior-daily"), jd, paths["junior-daily"])
    assert any("repeats 100% of The Breakfast Table's lead" in e for e in errs), errs
    assert any("headline is the same as The Breakfast Table's lead" in e for e in errs)
    assert any("Where in the world" in e for e in errs)                     # names this paper's lens


def test_the_copy_check_lets_different_tellings_through(tmp_path, monkeypatch):
    bt, jd = load("breakfast-table"), load("junior-daily")
    for i in (bt, jd):
        i["date"] = "2026-10-27"
    paths = place(tmp_path, monkeypatch, {"breakfast-table": bt, "junior-daily": jd})
    assert copy_check(edition.load("junior-daily"), jd, paths["junior-daily"]) == []


def test_earlier_issues_are_left_alone():
    gcp = load("global-citizen-plus", "2026-10-24")
    path = os.path.join(ROOT, "editions", "global-citizen-plus", "issues", "2026", "2026-10-24.json")
    assert copy_check(edition.load("global-citizen-plus"), gcp, path) == []


def test_three_leads_running_on_one_story_get_a_note(tmp_path, monkeypatch):
    issues = {}
    root_issues = []
    for n, d in enumerate(("2026-10-27", "2026-10-28", "2026-10-29")):
        i = load("junior-daily")
        i.update(date=d, issue=20 + n, threads={"lead": "yemen-war"})
        root_issues.append(i)
    root = place(tmp_path, monkeypatch, {})
    folder = os.path.join(edition.ROOT, "editions", "junior-daily", "issues", "2026")
    for i in root_issues:
        json.dump(i, open(os.path.join(folder, f"{i['date']}.json"), "w"))
    last = root_issues[-1]
    r = checks.Report()
    checks.check_lead_streak(edition.load("junior-daily"), last, os.path.join(folder, "2026-10-29.json"),
                             dt.date(2026, 10, 29), r)
    assert any("led this paper three issues running" in n for n in r.notes) and not r.errors


POOL = {"world": {"stories": [
    {"id": "riyadh", "sources": [{"url": "https://example.com/riyadh"}], "key_facts": []},
    {"id": "oil", "sources": [{"url": "https://example.com/oil"}], "key_facts": []}]}}


def test_the_plan_needs_every_due_paper_a_real_lead_and_different_angles():
    good = {"date": "2026-10-27", "papers": {
        "breakfast-table": {"lead": "riyadh", "angle": "What the reopening means for families who fly"},
        "junior-daily": {"lead": "riyadh", "angle": "Where Riyadh is, and who is firing at it"},
        "europe-explained": {"lead": "oil", "angle": "Why traders price in risk before any oil is lost"}}}
    assert plan.check(good, POOL, ["breakfast-table", "junior-daily", "europe-explained"]) == ([], [])
    bad = copy.deepcopy(good)
    bad["papers"]["junior-daily"]["angle"] = "What the reopening means for families who fly!"
    bad["papers"]["europe-explained"]["lead"] = "made-up"
    errs, _ = plan.check(bad, POOL, ["breakfast-table", "junior-daily", "europe-explained", "lab-notebook"])
    assert any("same as papers.breakfast-table.angle" in e for e in errs)
    assert any("'made-up' is not a story id" in e for e in errs)
    assert any("papers.lab-notebook: missing" in e for e in errs)


def test_check_holds_the_lead_to_the_plan():
    issue = load("breakfast-table")
    p = {"date": DAY, "papers": {"breakfast-table": {"lead": "oil", "angle": "x"}}}
    assert plan.lead_errors(p, POOL, "breakfast-table", issue, "lead")         # cites none of the oil story's sources
    issue["blocks"]["lead"]["sources"] = [{"url": "https://example.com/oil"}]
    assert plan.lead_errors(p, POOL, "breakfast-table", issue, "lead") == []
    assert plan.lead_errors({"papers": {}}, POOL, "breakfast-table", issue, "lead")


def test_ygc_plan_command(tmp_path):
    f, pool = tmp_path / "plan.json", tmp_path / "pool.json"
    f.write_text(json.dumps({"papers": {"breakfast-table": {"lead": "riyadh", "angle": "At home"}}}))
    pool.write_text(json.dumps(POOL))
    r = subprocess.run([sys.executable, "-m", "ygc", "plan", str(f), "--pool", str(pool)], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0 and "PASS" in r.stdout, r.stdout + r.stderr
    f.write_text(json.dumps({"papers": {"breakfast-table": {"lead": "nope", "angle": ""}}}))
    r = subprocess.run([sys.executable, "-m", "ygc", "plan", str(f), "--pool", str(pool)], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 1 and "FAIL" in r.stdout


def test_due_lists_each_papers_lens():
    r = subprocess.run([sys.executable, "-m", "ygc", "due", "--date", "2030-01-07", "--json"], cwd=ROOT,
                       capture_output=True, text=True)
    due = json.loads(r.stdout)["due"]
    assert due and all("lens" in x for x in due)
    assert next(x for x in due if x["edition"] == "breakfast-table")["lens"].startswith("What it means at home")
