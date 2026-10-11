"""The automatic pipeline, end to end, against a simulated Claude API.

The fake API behaves like the real one where it matters: research turns pause
mid-search (pause_turn) and cite a URL search never returned; the first draft
fails the checker; the repair passes; the fact-check runs; costs are counted."""
import copy
import json
import os
import shutil

import pytest

from ygc import edition, checks
from ygc.auto import llm, run, research

ROOT = edition.ROOT
REAL = os.path.join(ROOT, "editions", "young-global-citizen", "issues", "2026", "2026-10-10.json")
GOOD_URLS = ["https://www.aljazeera.com/news/2026/10/10/attack-on-airport-in-saudi-capital-riyadh-leaves-several-injured",
             "https://www.arabnews.com/world/isaias-makes-landfall-as-hurricane-hammering-us-gulf-coast-with-powerful-winds-dangerous-flooding-3005572"]


class FakeAPI:
    def __init__(self, first_draft_broken=True):
        self.calls = []
        self.writes = 0
        self.first_draft_broken = first_draft_broken

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
        # writer: reuse the real published issue, citing only pool sources
        self.writes += 1
        issue = json.load(open(REAL, encoding="utf-8"))
        for b in issue["blocks"].values():
            if isinstance(b, dict) and "sources" in b:
                b["sources"] = [{"outlet": "Al Jazeera", "title": "Attack", "url": GOOD_URLS[0]}]
        issue["blocks"]["vocab"]["items"] = [{"word": w, "def": f"Meaning of {w.lower()}. Today: used in the news."}
                                             for w in ("Envoy", "Coalition", "Monsoon", "Tribunal")]
        issue["blocks"]["did_you_know"]["text"] = "Octopuses have three hearts and blue blood, which carries oxygen well in cold water."
        if self.first_draft_broken and self.writes == 1:
            issue["blocks"]["vocab"]["items"][0]["def"] = "A definition without the example."
            issue["blocks"]["lead"]["sources"] = [{"url": "https://not-in-pool.example/x"}]
        return {"stop_reason": "end_turn", "usage": usage,
                "content": [{"type": "text", "text": "Here is the issue:\n```json\n" + json.dumps(issue) + "\n```"}]}


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    eds = tmp_path / "editions"
    shutil.copytree(os.path.join(ROOT, "editions", "young-global-citizen"), eds / "young-global-citizen")
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


def test_nothing_due_twice_on_the_same_day(sandbox):
    run.run(only=["young-global-citizen"], date_override="2026-10-12", transport=FakeAPI(), log=lambda *a: None)
    ed = edition.load("young-global-citizen")
    assert not run.is_due(ed, run.dt.date(2026, 10, 12))
    assert not run.is_due(ed, run.dt.date(2026, 10, 13))             # every two days
    assert run.is_due(ed, run.dt.date(2026, 10, 14))


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
