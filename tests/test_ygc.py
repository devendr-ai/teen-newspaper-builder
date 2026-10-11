"""python -m pytest -q"""
import copy
import glob
import json
import os
import shutil

import pytest
from pypdf import PdfReader

from ygc import checks, edition, prompt, render, skeleton
from ygc.__main__ import main

ROOT = edition.ROOT
EDITIONS = edition.list_editions()
ISSUES = sorted(glob.glob(os.path.join(ROOT, "editions", "*", "issues", "**", "*.json"), recursive=True)
                + glob.glob(os.path.join(ROOT, "editions", "*", "examples", "*.json")))
YGC_EX = os.path.join(ROOT, "editions", "young-global-citizen", "examples", "2026-08-20.json")


def load(p):
    return json.load(open(p, encoding="utf-8"))


@pytest.fixture
def ygc():
    return edition.load("young-global-citizen")


@pytest.fixture
def ex():
    return copy.deepcopy(load(YGC_EX))


def errors(ed, issue, path=YGC_EX, archive=True):
    return checks.check_issue(ed, issue, path, archive=archive).errors


# ------------------------------------------------ everything committed is valid
@pytest.mark.parametrize("eid", EDITIONS)
def test_edition_loads(eid):
    edition.load(eid)


@pytest.mark.parametrize("eid", EDITIONS)
def test_prompt_is_up_to_date(eid):
    ed = edition.load(eid)
    assert open(prompt.path_for(ed), encoding="utf-8").read() == prompt.generate(ed), \
        f"run: python -m ygc prompt {eid}"


@pytest.mark.parametrize("path", ISSUES, ids=lambda p: os.path.relpath(p, ROOT))
def test_archived_issue_passes_and_builds(path, tmp_path):
    assert main(["check", path, "--archive", "--out", str(tmp_path)]) == 0


# ------------------------------------------------ the engine is configurable
def test_page_plan_is_config_not_code(ygc, tmp_path):
    """Same content, re-planned onto 3 pages with a 3-column page: no code change."""
    ed = copy.deepcopy(ygc)
    ed["pages"] = [
        {"masthead": True, "columns": [["lead"], ["world"]]},
        {"banner": "<b>HOME FRONT</b>", "columns": [["india"], ["us"]]},
        {"banner": "<b>LEARN</b>", "columns": [["briefs", "vocab"], ["did_you_know", "sports"],
                                                ["watchlist", "quote", "sign_off"]]},
    ]
    assert edition.validate(ed, "young-global-citizen") == []
    issue = load(os.path.join(ROOT, "editions", "young-global-citizen", "issues", "2026", "2026-10-10.json"))
    pdf = render.build(ed, issue, str(tmp_path / "x.pdf"))
    assert len(PdfReader(pdf).pages) == 3
    assert all(m["over"] < 0.5 for m in render.measure(ed, issue))


def test_type_scale_changes_fit(ygc, ex):
    big = copy.deepcopy(ygc)
    big["style"]["type_scale"] = 1.3
    assert any(m["over"] > 0 for m in render.measure(big, ex))


def test_skeleton_matches_edition(ygc):
    sk = skeleton.make(ygc, "2026-10-12", 171)
    assert set(sk["blocks"]) == {b for b in edition.placed_blocks(ygc) if b != "sign_off"}
    assert len(sk["blocks"]["vocab"]["items"]) == ygc["blocks"]["vocab"]["count"]


# ------------------------------------------------ edition validation catches mistakes
@pytest.mark.parametrize("mutate,needle", [
    (lambda e: e["pages"][1]["columns"][0].append("ghost"), "undeclared block"),
    (lambda e: e["pages"][1]["columns"][1].append("lead"), "more than once"),
    (lambda e: e["blocks"].update(extra={"type": "quote"}), "not placed"),
    (lambda e: e["blocks"]["us"].update(desk="mars"), "not a declared desk"),
    (lambda e: e["pages"][1].update(masthead=True), "only the first page"),
    (lambda e: e["pages"][0]["columns"].extend([[], []]), "1 to 3 columns"),
    (lambda e: e["cadence"].update(timezone="Mars/Olympus"), "timezone"),
    (lambda e: e["style"].update(type_scale=3), "type_scale"),
])
def test_edition_validation(ygc, mutate, needle):
    ed = copy.deepcopy(ygc)
    mutate(ed)
    errs = edition.validate(ed, "young-global-citizen")
    assert any(needle in x for x in errs), errs


# ------------------------------------------------ every issue gate catches its failure
@pytest.mark.parametrize("mutate,needle", [
    (lambda c: c["blocks"]["us"]["chart"].update(labels=["Fiscal 2016", "Fiscal 2021", "Fiscal 2026"]), "keep labels"),
    (lambda c: c["blocks"]["briefs"]["items"].__setitem__(0, "Czechia: floods in Děčín."), "cannot print"),
    (lambda c: c["blocks"]["lead"].update(why=c["blocks"]["lead"]["why"] + " And so…"), "'…'"),
    (lambda c: c["blocks"]["world"]["illustration"].update(motif="volcano"), "motif"),
    (lambda c: c["blocks"]["world"]["illustration"].update(subtitle="A corridor drawn across a territory"), "subtitle"),
    (lambda c: c["blocks"]["vocab"]["items"][0].update({"def": "Rules about trade."}), "Today:"),
    (lambda c: c["blocks"]["vocab"]["items"].pop(), "expected 4"),
    (lambda c: c["blocks"]["lead"].pop("map"), "map is required"),
    (lambda c: c["blocks"]["us"].pop("analyst"), "analyst is required"),
    (lambda c: c["blocks"].update(ghost={}), "not a block"),
    (lambda c: c["blocks"]["lead"].update(headline="A " * 60), "more than 3 lines"),
    (lambda c: c["blocks"]["us"].update(why=c["blocks"]["us"]["why"] * 3), "is OVER"),
    (lambda c: c.update(date="2026-08-21"), "does not match"),
])
def test_issue_gate(ygc, ex, mutate, needle):
    mutate(ex)
    errs = errors(ygc, ex)
    assert any(needle in e for e in errs), errs


def test_bullets_dashes_and_quotes_are_printable(ygc, ex):
    ex["blocks"]["briefs"]["items"][0] = "China: a court — finally — ruled “guilty” • again."
    assert errors(ygc, ex) == []


def test_new_issue_needs_sources_and_todays_date(ygc, ex, monkeypatch):
    monkeypatch.setattr(checks, "today", lambda ed: checks.dt.date(2026, 8, 20))
    errs = errors(ygc, ex, archive=False)
    assert any("no sources" in e for e in errs)
    monkeypatch.setattr(checks, "today", lambda ed: checks.dt.date(2026, 8, 21))
    assert any("take the date from the device" in e for e in errors(ygc, ex, archive=False))


def test_numbering_and_no_repeat(ygc, ex, tmp_path):
    ed = copy.deepcopy(ygc)
    ed["_dir"] = str(tmp_path)
    (tmp_path / "issues" / "2026").mkdir(parents=True)
    (tmp_path / "issues" / "2026" / "2026-08-20.json").write_text(json.dumps(ex), encoding="utf-8")
    nxt = copy.deepcopy(ex)
    nxt.update(date="2026-08-22", issue=147)
    path = str(tmp_path / "issues" / "2026" / "2026-08-22.json")
    errs = checks.check_issue(ed, nxt, path, archive=True).errors
    assert any("expected No. 146" in e for e in errs)
    assert any("already used" in e for e in errs)
    assert any("Did You Know" in e for e in errs)


# ------------------------------------------------ CLI round trips
def test_create_edition_and_new_issue(tmp_path, monkeypatch):
    monkeypatch.setattr(edition, "EDITIONS", str(tmp_path / "editions"))
    shutil.copytree(os.path.join(ROOT, "editions", "junior-explorer"),
                    tmp_path / "editions" / "junior-explorer")
    assert main(["create-edition", "my-paper", "--from", "junior-explorer"]) == 0
    assert edition.load("my-paper")["id"] == "my-paper"
    assert main(["new", "junior-explorer", "--date", "2026-10-17"]) == 0
    new = load(tmp_path / "editions" / "junior-explorer" / "issues" / "2026" / "2026-10-17.json")
    assert new["issue"] == 2


# ------------------------------------------------ first-run experience
def test_checking_the_empty_skeleton_explains_instead_of_crashing(ygc, tmp_path):
    sk = skeleton.make(ygc, "2026-08-20", 1)
    p = tmp_path / "2026-08-20.json"
    p.write_text(json.dumps(sk), encoding="utf-8")
    r = checks.check_issue(ygc, sk, str(p), archive=True)
    assert any("still empty" in e for e in r.errors)
    assert any("placeholder numbers" in e for e in r.errors)
    assert any("pick one motif" in e for e in r.errors)
    assert main(["check", str(p), "--archive", "--out", str(tmp_path)]) == 1   # no traceback


def test_source_objects_are_accepted(ygc, ex):
    for b in ("lead", "world", "india", "us"):
        ex["blocks"][b]["sources"] = [{"outlet": "AP", "title": "x", "url": "https://apnews.com/a"}]
    assert not any("no sources" in e for e in errors(ygc, ex, archive=True))


def test_prompt_only_mentions_sections_the_edition_has(ygc):
    ed = copy.deepcopy(ygc)
    for b in ("vocab", "did_you_know"):
        del ed["blocks"][b]
        ed["pages"][1]["columns"][0].remove(b)
    assert "No repeats" not in prompt.generate(ed)
    assert "No repeats" in prompt.generate(ygc)
