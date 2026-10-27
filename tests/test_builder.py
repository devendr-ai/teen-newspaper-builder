"""The web configurator must only ever produce editions the engine accepts.

Runs the configurator's own generator (tools/builder/generator.js) under node,
for every preset and a few hundred random combinations, and validates each
result with the real engine. Skipped if node isn't installed.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest
from pypdf import PdfReader

from ygc import edition, prompt, render, skeleton, checks

ROOT = edition.ROOT
BUILDER = os.path.join(ROOT, "tools", "builder")
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node not installed")

SCRIPT = r"""
const G = require(process.argv[1] + "/generator.js"), P = require(process.argv[1] + "/presets.js");
const ages = Object.keys(G.AGES), purposes = Object.keys(G.PURPOSES), depths = Object.keys(G.DEPTHS),
      cads = Object.keys(G.CADENCE), topics = Object.keys(G.TOPICS);
let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const pick = (a) => a[Math.floor(rnd() * a.length)], some = (a, k) => a.filter(() => rnd() < k);
const cases = Object.entries(P).map(([id, o]) => Object.assign({ id }, o));
for (let i = 0; i < 150; i++) cases.push({ id: `rand-${i}`, name: `Paper ${i}`,
  pages: pick([1, 2, 3, 4, 5, 6, 7, 8, 12]), age: pick(ages), purpose: pick(purposes), depth: pick(depths),
  cadence: pick(cads), language: "en", geos: some(G.GEOS.concat(["Kenya", "São Paulo"]), 0.3),
  topics: some(topics, 0.3), location: "Pune, India", timezone: "Asia/Kolkata",
  modules: { vocab: rnd() < .7, dyk: rnd() < .6, quiz: rnd() < .4, sports: rnd() < .4, explainer: rnd() < .4 } });
cases.push({ id: "bad-lang", name: "X", pages: 2, age: "12-14", purpose: "global", depth: "quick", cadence: "daily",
             language: "hi", geos: ["India"], topics: [] });
cases.push({ id: "bad-empty", name: "X", pages: 2, age: "12-14", purpose: "global", depth: "quick", cadence: "daily", geos: [], topics: [] });
console.log(JSON.stringify(cases.map((o) => { const r = G.generate(o); return { id: o.id, pages: o.pages, errors: r.errors, yaml: r.yaml }; })));
"""


@pytest.fixture(scope="module")
def generated():
    out = subprocess.run(["node", "-e", SCRIPT, BUILDER], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_page_is_up_to_date():
    subprocess.run([sys.executable, os.path.join(BUILDER, "build.py"), "--verify"], check=True)


def test_every_generated_edition_validates_and_builds(generated, tmp_path, monkeypatch):
    monkeypatch.setattr(edition, "EDITIONS", str(tmp_path))
    ok = [g for g in generated if not g["errors"]]
    assert len(ok) > 140
    for g in ok:
        d = tmp_path / g["id"]
        (d / "issues").mkdir(parents=True)
        (d / "edition.yaml").write_text(g["yaml"], encoding="utf-8")
        ed = edition.load(g["id"])
        prompt.generate(ed)
        sk = skeleton.make(ed, "2026-10-12", 1)
        for b in sk["blocks"].values():
            if "illustration" in b:
                b["illustration"]["motif"] = "globe"
            if "chart" in b:
                b["chart"].update(labels=["A", "B"], values=[1, 2], max=3)
        pdf = render.build(ed, sk, str(tmp_path / "x.pdf"))
        assert len(PdfReader(pdf).pages) == min(max(int(g["pages"]), 1), 12), g["id"]


@pytest.mark.parametrize("case,needle", [("bad-lang", "Unicode font"), ("bad-empty", "at least one")])
def test_bad_configurations_are_refused(generated, case, needle):
    g = next(x for x in generated if x["id"] == case)
    assert any(needle in e for e in g["errors"]), g["errors"]


def test_young_global_citizen_preset_is_a_drop_in(generated, tmp_path, monkeypatch):
    """The configurator's preset must run the real archived issues unchanged."""
    g = next(x for x in generated if x["id"] == "young-global-citizen")
    monkeypatch.setattr(edition, "EDITIONS", str(tmp_path))
    (tmp_path / "young-global-citizen" / "issues").mkdir(parents=True)
    (tmp_path / "young-global-citizen" / "edition.yaml").write_text(g["yaml"], encoding="utf-8")
    ed = edition.load("young-global-citizen")
    for rel in ("issues/2026/2026-10-10.json", "examples/2026-08-20.json"):
        issue = json.load(open(os.path.join(ROOT, "editions", "young-global-citizen", rel), encoding="utf-8"))
        assert checks.check_issue(ed, issue, os.path.join(str(tmp_path), "young-global-citizen", rel),
                                  archive=True).errors == []


NEW_OPTIONS = r"""
const G = require(process.argv[1] + "/generator.js");
let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
const pick = (a) => a[Math.floor(rnd() * a.length)], some = (a, k) => a.filter(() => rnd() < k);
const cases = [];
for (let i = 0; i < 120; i++) {
  const big = rnd() < 0.4;
  cases.push({ id: `new-${i}`, name: pick(["Aanya's Morning News", "The Explorer", "Ravi's Weekly"]),
    format: big ? "big_story" : "news", pages: big ? pick([2, 3, 4]) : pick([1, 2, 3, 4, 6]),
    age: pick(Object.keys(G.AGES)), purpose: pick(Object.keys(G.PURPOSES)), depth: pick(Object.keys(G.DEPTHS)),
    cadence: pick(Object.keys(G.CADENCE)), language: "en", geos: some(G.GEOS, 0.25),
    topics: some(Object.keys(G.TOPICS), 0.25).concat(["space"]), city: pick(["", "Pune", "Leeds"]),
    childName: pick(["", "Aanya", "Zoë"]), favourite: pick(["", "Mumbai Indians", "Lionel Messi"]),
    largePrint: rnd() < 0.3, tone: Object.fromEntries(some(Object.keys(G.TONES), 0.3).map((t) => [t, true])),
    modules: Object.fromEntries(Object.keys(G.EXTRA_SECTIONS).map((k) => [k, rnd() < 0.3])),
    location: "Pune, India", timezone: "Asia/Kolkata" });
}
console.log(JSON.stringify(cases.map((o) => { const r = G.generate(o); return { id: o.id, o, errors: r.errors, yaml: r.yaml }; })));
"""


def test_new_options_always_make_a_printable_edition(tmp_path, monkeypatch):
    """Formats, tones, learning sections and personal touches: every combination the
    builder allows must validate, get chatbot instructions and print the planned pages."""
    from ygc import chat
    out = subprocess.run(["node", "-e", NEW_OPTIONS, BUILDER], capture_output=True, text=True, check=True)
    cases = json.loads(out.stdout)
    monkeypatch.setattr(edition, "EDITIONS", str(tmp_path))
    ok = [c for c in cases if not c["errors"]]
    assert len(ok) == len(cases), [c["errors"] for c in cases if c["errors"]][:3]
    seen = set()
    for c in ok:
        ed = chat.install(c["yaml"].replace("id: ", f"id: {c['id']}-", 1))
        text = chat.instructions(ed, "2026-10-17")
        o = c["o"]
        if o["format"] == "big_story":
            assert "THE BIG STORY" in text and "TIMELINE" in text and "`numbers`" in text
            seen.add("big")
        for t, x in (("gentle", "Gentle mode"), ("good_news", "Good news paper"), ("both_sides", "Both sides"),
                     ("solutions", "Solutions lens")):
            if o["tone"].get(t):
                assert x in text
                seen.add(t)
        if o["favourite"] and o["pages"] > 1:
            assert o["favourite"] in text
        sk = skeleton.make(ed, "2026-10-17", 1)
        for b in sk["blocks"].values():
            if "illustration" in b:
                b["illustration"]["motif"] = "globe"
            if "chart" in b:
                b["chart"].update(labels=["A", "B"], values=[1, 2], max=3)
        pdf = render.build(ed, sk, str(tmp_path / "x.pdf"))
        assert len(PdfReader(pdf).pages) == o["pages"], c["id"]
    assert seen >= {"big", "gentle", "good_news", "both_sides", "solutions"}
