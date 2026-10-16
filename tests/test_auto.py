"""The automatic pipeline, end to end, against a simulated Claude API.

The fake API behaves like the real one where it matters: research turns pause
mid-search (pause_turn) and cite a URL search never returned; the first draft
fails the checker; the repair passes; the fact-check runs; costs are counted."""
import copy
import json
import os
import shutil

import pytest

from ygc import edition, checks, poster
from ygc.auto import llm, run, research

ROOT = edition.ROOT
REAL = os.path.join(ROOT, "editions", "young-global-citizen", "issues", "2026", "2026-10-10.json")
GOOD_URLS = ["https://www.aljazeera.com/news/2026/10/10/attack-on-airport-in-saudi-capital-riyadh-leaves-several-injured",
             "https://www.arabnews.com/world/isaias-makes-landfall-as-hurricane-hammering-us-gulf-coast-with-powerful-winds-dangerous-flooding-3005572"]


LE_ISSUE = os.path.join(ROOT, "editions", "little-explorers", "issues", "2026", "2026-10-10.json")
LE_POSTER = os.path.join(ROOT, "editions", "little-explorers", "posters", "2026", "2026-10-10.json")


class FakeAPI:
    def __init__(self, first_draft_broken=True, real=REAL, poster_broken=1):
        self.calls = []
        self.writes = 0
        self.posters = 0
        self.first_draft_broken = first_draft_broken
        self.real = real
        self.poster_broken = poster_broken      # how many poster drafts fail the checker

    def __call__(self, payload):
        self.calls.append(payload)
        system = payload["system"]
        usage = {"input_tokens": 20000, "output_tokens": 3000, "server_tool_use": {"web_search_requests": 0}}
        if system.startswith("You are the research desk"):
            paused = not any(m["role"] == "assistant" for m in payload["messages"])
            if paused:      # first leg: a search, then the API pauses the turn
                usage["server_tool_use"]["web_search_requests"] = 4
                return {"stop_reason": "pause_turn", "usage": usage, "content": [
                    {"type": "server_tool_use", "id": "s1", "name": "web_search", "input": {"query": "news"}},
                    {"type": "web_search_tool_result", "tool_use_id": "s1", "content": [
                        {"type": "web_search_result", "url": u, "title": "t"} for u in GOOD_URLS]}]}
            story = {"id": "riyadh", "headline": "Airport attack", "what_happened": "x", "why_it_matters": "y",
                     "importance": 9, "suitable_for_children": True,
                     "key_facts": [{"fact": "12 killed", "source_url": GOOD_URLS[0]},
                                   {"fact": "invented", "source_url": "https://made-up.example/never-searched"}],
                     "numbers": [], "geography": "Bab el-Mandeb",
                     "sources": [{"outlet": "Al Jazeera", "title": "Attack", "url": GOOD_URLS[0]},
                                 {"outlet": "Nowhere", "title": "Fake", "url": "https://made-up.example/never-searched"}]}
            ghost = {"id": "ghost", "headline": "Unverifiable", "key_facts": [{"fact": "x", "source_url": "https://nope.example"}],
                     "sources": [{"url": "https://nope.example"}]}
            return {"stop_reason": "end_turn", "usage": usage,
                    "content": [{"type": "text", "text": json.dumps({"stories": [story, ghost]})}]}
        if system.startswith("You are a fact-checker"):
            return {"stop_reason": "end_turn", "usage": usage, "content": [{"type": "text", "text": '{"unsupported": []}'}]}
        if system.startswith("# The Big Question poster"):
            # poster writer: the committed poster, re-sourced to the pool; early drafts break the checker
            self.posters += 1
            spec = json.load(open(LE_POSTER, encoding="utf-8"))
            spec["sources"] = [GOOD_URLS[0]]
            if self.posters <= self.poster_broken:
                spec["hero"]["motif"] = "dragon"
                spec["sources"] = ["https://not-in-pool.example/poster"]
            return {"stop_reason": "end_turn", "usage": usage, "content": [{"type": "text", "text": json.dumps(spec)}]}
        # writer: reuse the real published issue, citing only pool sources
        self.writes += 1
        issue = json.load(open(self.real, encoding="utf-8"))
        for b in issue["blocks"].values():
            if isinstance(b, dict) and "sources" in b:
                b["sources"] = [{"outlet": "Al Jazeera", "title": "Attack", "url": GOOD_URLS[0]}]
        words = ("Envoy", "Coalition", "Monsoon", "Tribunal")[:len(issue["blocks"]["vocab"]["items"])]
        issue["blocks"]["vocab"]["items"] = [{"word": w, "def": f"Meaning of {w.lower()}. Today: used in the news."}
                                             for w in words]
        if "did_you_know" in issue["blocks"]:
            issue["blocks"]["did_you_know"]["text"] = "Octopuses have three hearts and blue blood, which carries oxygen well in cold water."
        if self.first_draft_broken and self.writes == 1:
            issue["blocks"]["vocab"]["items"][0]["def"] = "A definition without the example."
            issue["blocks"]["lead"]["sources"] = [{"url": "https://not-in-pool.example/x"}]
        return {"stop_reason": "end_turn", "usage": usage,
                "content": [{"type": "text", "text": "Here is the issue:\n```json\n" + json.dumps(issue) + "\n```"}]}


ARCHIVE_AS_OF = "2026-10-16"     # these tests replay 12 and 17 October as they stood before the 17th was published


def archive_as_of(eds, cutoff=ARCHIVE_AS_OF):
    """Drop the copied papers and posters published after `cutoff`, so new nightly papers can't change the tests."""
    for f in eds.glob("*/*/*/*.json"):
        if f.parent.parent.name in ("issues", "posters") and f.stem > cutoff:
            f.unlink()


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    eds = tmp_path / "editions"
    for eid in ("young-global-citizen", "little-explorers"):
        shutil.copytree(os.path.join(ROOT, "editions", eid), eds / eid)
    archive_as_of(eds)
    monkeypatch.setattr(edition, "EDITIONS", str(eds))
    monkeypatch.setattr(run, "DATA", str(tmp_path / "data"))
    return tmp_path


def test_full_run_researches_repairs_and_publishes(sandbox):
    api = FakeAPI()
    rep = run.run(only=["young-global-citizen"], date_override="2026-10-12", transport=api, log=lambda *a: None)
    r = rep["editions"]["young-global-citizen"]
    assert r["status"] == "passed", r
    assert r["rounds"] >= 2 and r["factcheck_rounds"] == 1          # broken draft, then repaired
    saved = json.load(open(sandbox / "editions" / "young-global-citizen" / "issues" / "2026" / "2026-10-12.json"))
    assert saved["issue"] == 171 and saved["date"] == "2026-10-12"   # follows No. 170 in the archive
    feedback = [m["content"] for p in api.calls for m in p["messages"] if m["role"] == "user" and "ERRORS" in str(m["content"])]
    assert any("Today:" in f for f in feedback) and any("not in the research pool" in f for f in feedback)
    pool = json.load(open(sandbox / "data" / "pools" / "2026-10-12.json"))
    st = [s for g in pool.values() for s in g["stories"]]
    assert {s["id"] for s in st} == {"riyadh"} and all(g["dropped_unverified"] == 1 for g in pool.values())  # unverifiable story dropped on every desk
    assert all("made-up" not in f["source_url"] for f in st[0]["key_facts"])
    assert rep["usage"]["searches"] == 4 * len(pool) and rep["usage"]["usd"] > 0
    assert json.load(open(sandbox / "data" / "runs" / "2026-10-12.json"))["editions"]["young-global-citizen"]["status"] == "passed"
    assert "poster" not in r and not any(p["system"].startswith("# The Big Question") for p in api.calls)  # not opted in


def _run_little_explorer(sandbox, api):
    return run.run(only=["little-explorers"], date_override="2026-10-17", transport=api, log=lambda *a: None)


def test_poster_is_written_from_the_same_research_repaired_and_published(sandbox):
    api = FakeAPI(first_draft_broken=False, real=LE_ISSUE)
    rep = _run_little_explorer(sandbox, api)
    r = rep["editions"]["little-explorers"]
    assert r["status"] == "passed", r
    p = r["poster"]
    assert p["status"] == "passed" and p["rounds"] == 2 and p["factcheck_rounds"] == 1, p
    path = sandbox / "editions" / "little-explorers" / "posters" / "2026" / "2026-10-17.json"
    assert p["file"].endswith(os.path.join("little-explorers", "posters", "2026", "2026-10-17.json"))
    saved = json.load(open(path))
    assert saved["date"] == "2026-10-17" and saved["sources"] == [GOOD_URLS[0]]
    assert poster.check(edition.load("little-explorers"), saved, str(path)).errors == []
    asks = [p for p in api.calls if p["system"].startswith("# The Big Question")]
    first, repair = asks[0]["messages"][0]["content"], asks[-1]["messages"][-1]["content"]
    assert "RESEARCH POOL" in first and GOOD_URLS[0] in first            # same research as the paper
    assert "Last week's poster (2026-10-10)" in first                      # closes the loop
    assert "dragon" in repair and "not in the research pool" in repair      # checker errors fed back
    assert json.load(open(sandbox / "data" / "runs" / "2026-10-17.json"))["editions"]["little-explorers"]["poster"]["status"] == "passed"


def test_failed_poster_does_not_block_the_paper(sandbox):
    api = FakeAPI(first_draft_broken=False, real=LE_ISSUE, poster_broken=99)
    rep = _run_little_explorer(sandbox, api)
    r = rep["editions"]["little-explorers"]
    assert r["status"] == "passed" and r["poster"]["status"] == "failed"
    assert "dragon" in r["poster"]["last_feedback"]
    assert (sandbox / "editions" / "little-explorers" / "issues" / "2026" / "2026-10-17.json").exists()
    assert not (sandbox / "editions" / "little-explorers" / "posters" / "2026" / "2026-10-17.json").exists()


def test_nothing_due_twice_on_the_same_day(sandbox):
    run.run(only=["young-global-citizen"], date_override="2026-10-12", transport=FakeAPI(), log=lambda *a: None)
    ed = edition.load("young-global-citizen")
    assert not run.is_due(ed, run.dt.date(2026, 10, 12))
    assert not run.is_due(ed, run.dt.date(2026, 10, 13))             # every two days
    assert run.is_due(ed, run.dt.date(2026, 10, 14))


def test_off_day_issue_does_not_make_a_weekly_paper_skip_its_day(tmp_path):
    ed = copy.deepcopy(edition.load("little-explorers"))        # weekly, pinned to Saturday
    ed["_dir"] = str(tmp_path)
    os.makedirs(tmp_path / "issues" / "2026")
    (tmp_path / "issues" / "2026" / "2026-10-11.json").write_text('{"issue": 1}')   # a Sunday
    days = {d: run.is_due(ed, run.dt.date(2026, 10, d)) for d in range(11, 25)}
    assert [d for d, due in days.items() if due] == [17, 24]    # the following Saturdays, no skip


def test_budget_cap_stops_spending(sandbox):
    rep = run.run(only=["young-global-citizen"], date_override="2026-10-12", transport=FakeAPI(),
                  budget=0.05, log=lambda *a: None)
    assert "budget" in rep.get("stopped", "") and rep["editions"]["young-global-citizen"]["status"] == "skipped"


def test_dry_run_spends_nothing(sandbox):
    api = FakeAPI()
    rep = run.run(only=["young-global-citizen"], date_override="2026-10-12", dry_run=True, transport=api, log=lambda *a: None)
    assert rep["dry_run"] and api.calls == []


def test_json_extraction_survives_fences_prose_and_escapes():
    assert llm.extract_json('ok ```json\n{"a": "say \\"}\\" now", "b": [1]}\n``` done') == {"a": 'say "}" now', "b": [1]}
    with pytest.raises(ValueError):
        llm.extract_json('{"cut off": "mid')


def test_due_lists_what_to_write_today(sandbox, capsys):
    from ygc.__main__ import main
    assert main(["due", "--date", "2026-10-17", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    le = next(x for x in out["due"] if x["edition"] == "little-explorers")      # Saturday
    assert le["issue"] == 2 and le["poster"] and le["file"].endswith("little-explorers/issues/2026/2026-10-17.json")
    assert "Hurricane" in le["avoid_vocab"]
    assert "world" in out["research_desks"]
    assert main(["due", "--date", "2026-10-16", "--json"]) == 0              # a Friday: no weekly papers
    assert "little-explorers" not in {x["edition"] for x in json.loads(capsys.readouterr().out)["due"]}


def test_pool_option_fails_sources_outside_the_research(tmp_path, capsys):
    from ygc.__main__ import main
    spec = json.load(open(LE_POSTER, encoding="utf-8"))
    pool = {"world": {"label": "WORLD", "hours": 168, "stories": [
        {"id": "x", "sources": [{"url": u} for u in spec["sources"]]}]}}
    good = tmp_path / "good.json"; good.write_text(json.dumps(pool))
    pool["world"]["stories"][0]["sources"] = pool["world"]["stories"][0]["sources"][1:]
    bad = tmp_path / "bad.json"; bad.write_text(json.dumps(pool))
    out = str(tmp_path / "build")
    assert main(["poster", LE_POSTER, "--pool", str(good), "--out", out]) == 0
    assert main(["poster", LE_POSTER, "--pool", str(bad), "--out", out]) == 1
    assert "is not in the research pool" in capsys.readouterr().out
    issue_pool = {"world": {"stories": [{"sources": [{"url": "https://example.com/other"}]}]}}
    ip = tmp_path / "issue-pool.json"; ip.write_text(json.dumps(issue_pool))
    assert main(["check", LE_ISSUE, "--archive", "--no-build", "--pool", str(ip)]) == 1
    assert "blocks.lead.sources" in capsys.readouterr().out
