"""Parents' own chatbot: the instructions it gets, and the checks its reply must pass
before the builder page prints it (the same checks and PDF as published issues)."""
import copy
import json
import os
import subprocess
import shutil

import pytest
from pypdf import PdfReader

from ygc import chat, edition

ROOT = edition.ROOT
JD = os.path.join(ROOT, "editions", "junior-daily", "issues", "2026", "2026-10-12.json")
POSTER = os.path.join(ROOT, "editions", "little-explorers", "posters", "2026", "2026-10-10.json")


def reply(obj):
    return "Here is today's paper!\n```json\n" + json.dumps(obj) + "\n```\nEnjoy reading."


def test_instructions_state_the_date_and_require_web_search():
    ed = edition.load("junior-daily")
    t = chat.instructions(ed, "2026-10-12", 7)
    assert "Today is Monday 12 October 2026. Write issue No. 7, dated 2026-10-12" in t
    assert "Search the web" in t and "never from memory" in t and "can't search the web" in t
    assert "python -m ygc" not in t and "device clock" not in t
    assert '"date": "2026-10-12"' in t and '"issue": 7' in t
    assert chat.instructions(ed, "2026-10-12") != open(os.path.join(ROOT, "editions", "junior-daily", "PROMPT.md")).read()


def test_a_good_reply_prints_the_same_paper(tmp_path):
    ed = edition.load("junior-daily")
    issue = json.load(open(JD, encoding="utf-8"))
    res = chat.check_paper(ed, reply(issue), "2026-10-12", issue["issue"], out_pdf=str(tmp_path / "p.pdf"))
    assert res["ok"], res["errors"]
    assert len(PdfReader(res["pdf"]).pages) == 1 and res["fix"] == ""


def test_what_the_page_cannot_fix_gets_a_fix_list(tmp_path):
    """Far too long (more than half would have to go) or missing content: back to the chatbot."""
    ed = edition.load("junior-daily")
    issue = json.load(open(JD, encoding="utf-8"))
    long, empty = copy.deepcopy(issue), copy.deepcopy(issue)
    long["blocks"]["lead"]["body"] = long["blocks"]["lead"]["body"] * 3
    empty["blocks"]["world"]["deck"] = ""
    for bad, needle in ((long, "OVER"), (empty, "still empty")):
        res = chat.check_paper(ed, reply(bad), "2026-10-12", issue["issue"], out_pdf=str(tmp_path / "p.pdf"))
        assert not res["ok"] and "pdf" not in res
        assert needle in res["fix"] and "complete corrected JSON" in res["fix"]
        assert "to fix before it can print" in res["problem"]


@pytest.mark.parametrize("text,needle", [("Sorry, I cannot search the web right now.", "Turn on web search"),
                                         ("Here you go: {\"edition\": ", "paste it again")])
def test_replies_that_are_not_a_paper_are_explained(text, needle):
    res = chat.check_paper(edition.load("junior-daily"), text, "2026-10-12")
    assert not res["ok"] and needle in res["problem"]


def test_poster_instructions_and_checks(tmp_path):
    ed = edition.load("little-explorers")
    t = chat.poster_instructions(ed, "2026-10-10")
    assert "Two news stories" in t and "Automatic posters" not in t and '"version": 2' in t
    spec = json.load(open(POSTER, encoding="utf-8"))
    assert chat.check_poster(ed, reply(spec), "2026-10-10", out_pdf=str(tmp_path / "p.pdf"))["ok"]
    spec["hero"]["motif"] = "dragon"
    res = chat.check_poster(ed, reply(spec), "2026-10-10")
    assert not res["ok"] and "hero.motif" in res["fix"]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_a_builder_edition_installs_and_gets_instructions(tmp_path, monkeypatch):
    monkeypatch.setattr(edition, "EDITIONS", str(tmp_path))
    js = ('const G=require(process.argv[1]);const r=G.generate({name:"Aanya\'s Morning News",pages:2,age:"6-8",'
          'purpose:"family",depth:"quick",cadence:"weekly",geos:["World"],topics:["animals"],childName:"Aanya",'
          'tone:{gentle:true},modules:{try_home:true},location:"Pune, India",timezone:"Asia/Kolkata"});console.log(r.yaml)')
    y = subprocess.run(["node", "-e", js, os.path.join(ROOT, "tools", "builder", "generator.js")],
                       capture_output=True, text=True, check=True).stdout
    ed = chat.install(y)
    assert ed["id"] == "aanya-s-morning-news" and os.path.exists(tmp_path / ed["id"] / "edition.yaml")
    t = chat.instructions(ed, "2026-10-17")
    assert "Gentle mode" in t and "TRY THIS AT HOME" in t and "Keep exploring, Aanya" not in t


@pytest.mark.parametrize("eid", ["little-explorers", "junior-daily", "young-global-citizen", "lab-notebook",
                                 "current-affairs-digest"])
def test_length_guide_fits_the_page(eid):
    """A paper written to the word budgets in the instructions fits every column."""
    ed = edition.load(eid)
    guide = chat.length_guide(ed)
    stories = [b for b in edition.placed_blocks(ed) if ed["blocks"][b]["type"] == "story"]
    assert set(stories) <= set(guide) and all(40 <= guide[b] <= 700 for b in stories), guide
    assert chat.layout_problems(ed) == []
    sk = chat._probe(ed)
    for b, n in guide.items():
        sk["blocks"][b]["body"] = chat._words(int(n * 0.9), paras=5 if b in stories else 3)
    from ygc import render
    assert all(m["over"] <= 0.5 for m in render.measure(ed, sk))
    text = chat.instructions(ed, "2026-10-12")
    assert "**Field rules.**" in text and "**Length.**" in text and text.index("**Length.**") < text.index("**Output.**")
    real = json.load(open(sorted(__import__("glob").glob(os.path.join(ROOT, "editions", eid, "issues", "2026", "*.json")))[-1]))
    for b, n in ((b, guide[b]) for b in stories):   # published issues, which fit, sit close to the budget
        v = real["blocks"][b]
        words = len(" ".join(v["body"]).split()) + sum(len(str(v.get(k, "")).split()) for k in ("why", "connect", "analyst"))
        boxes = sum(1 for k in ("why", "connect", "analyst") if k in v)
        assert 0.5 <= words / (n + chat.BOX_WORDS * boxes) <= 1.15, (b, words, n)


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_a_layout_that_cannot_fit_is_caught_before_copying(tmp_path, monkeypatch):
    """A 2-page big story for ages 6-8 with every section on can't fit: say so up front."""
    monkeypatch.setattr(edition, "EDITIONS", str(tmp_path))
    js = ('const G=require(process.argv[1]+"/generator.js"),P=require(process.argv[1]+"/presets.js");'
          'const b=Object.assign({},P["little-explorers"],{format:"big_story",pages:+process.argv[2],location:"Pune",timezone:"Asia/Kolkata"});'
          'const m=Object.assign({},G.PURPOSES[b.purpose].modules,b.modules,{quiz:true,discussion:true,dyk:true,quote:true});'
          'console.log(G.generate(Object.assign({},b,{modules:m})).yaml)')
    for pages, ok in ((2, False), (3, True)):
        y = subprocess.run(["node", "-e", js, os.path.join(ROOT, "tools", "builder"), str(pages)],
                           capture_output=True, text=True, check=True).stdout
        problems = chat.layout_problems(chat.install(y.replace("id: ", f"id: p{pages}-", 1)))
        assert (problems == []) == ok, problems
        if not ok:
            assert problems[0].startswith("Page 2, column") and "too full" in problems[0]


def test_sentences_keep_abbreviations_together():
    assert chat.sentences('The U.S. President spoke. Then Dr. Rao left. "We are safe," she said.') == [
        "The U.S. President spoke.", "Then Dr. Rao left.", '"We are safe," she said.']


def test_a_slightly_long_reply_is_trimmed_to_fit_like_a_sub_editor(tmp_path):
    ed = edition.load("junior-daily")
    issue = json.load(open(JD, encoding="utf-8"))
    long = copy.deepcopy(issue)
    extra = chat.sentences(" ".join(issue["blocks"]["lead"]["body"]))[:3]
    long["blocks"]["lead"]["body"] = issue["blocks"]["lead"]["body"] + [" ".join(extra)]
    assert chat.check_paper(ed, reply(issue), "2026-10-12", issue["issue"], out_pdf=str(tmp_path / "a.pdf"))["trimmed"] == []
    res = chat.check_paper(ed, reply(long), "2026-10-12", issue["issue"], out_pdf=str(tmp_path / "b.pdf"))
    assert res["ok"], res["errors"]
    assert res["trimmed"] and "the top story" in res["trimmed"][0]
    printed = json.loads(res["issue"])["blocks"]["lead"]["body"]
    assert printed[0] == issue["blocks"]["lead"]["body"][0]          # trimmed from the end, the start kept
    assert len(" ".join(printed).split()) < len(" ".join(long["blocks"]["lead"]["body"]).split())


@pytest.mark.parametrize("eid", ["junior-daily", "young-global-citizen", "little-explorers"])
def test_mechanical_mistakes_are_repaired_without_a_round_trip(eid, tmp_path):
    """Empty kicker details, long picture and chart labels, numbers written as text, symbols the
    fonts can't print, a body as one string, extra items and unknown blocks: all fixed on the page."""
    ed = edition.load(eid)
    real = sorted(__import__("glob").glob(os.path.join(ROOT, "editions", eid, "issues", "2026", "*.json")))[-1]
    issue = json.load(open(real, encoding="utf-8"))
    bad = copy.deepcopy(issue)
    for v in bad["blocks"].values():
        if isinstance(v, dict) and "kicker" in v:
            v["kicker"] = v["kicker"].split("•")[0] + "•  "
        if isinstance(v, dict) and "illustration" in v:
            v["illustration"].update(title="A very long illustration title that goes on and on beyond the limit",
                                     subtitle="and a subtitle that is far too long", motif="dragon")
        if isinstance(v, dict) and "chart" in v:
            v["chart"].update(values=[f"{x}%" for x in v["chart"]["values"]], max=0,
                              labels=[f"{x} plus extra words" for x in v["chart"]["labels"]])
        if isinstance(v, dict) and "map" in v:
            v["map"]["label_top"] += " AND A VERY LONG NEIGHBOURING REGION NAME"
    bad["blocks"]["lead"]["headline"] += " → now"
    bad["blocks"]["lead"]["body"] = "\n\n".join(bad["blocks"]["lead"]["body"])
    if "briefs" in bad["blocks"]:
        bad["blocks"]["briefs"]["items"] += ["Extra one.", "Extra two."]
    bad["blocks"]["not_a_block"] = {"title": "x"}
    res = chat.check_paper(ed, reply(bad), issue["date"], issue["issue"], out_pdf=str(tmp_path / "p.pdf"))
    assert res["ok"], res["errors"]
    assert "replaced symbols the printer can't print" in res["repaired"]
    printed = json.loads(res["issue"])["blocks"]
    assert "→" not in printed["lead"]["headline"] and " to now" in printed["lead"]["headline"]
    assert isinstance(printed["lead"]["body"], list) and len(printed["lead"]["body"]) > 1
    assert "not_a_block" not in printed
