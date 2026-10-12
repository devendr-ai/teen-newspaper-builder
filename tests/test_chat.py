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


def test_a_reply_that_overflows_gets_a_fix_list(tmp_path):
    ed = edition.load("junior-daily")
    issue = json.load(open(JD, encoding="utf-8"))
    bad = copy.deepcopy(issue)
    bad["blocks"]["lead"]["body"] = bad["blocks"]["lead"]["body"] * 2
    bad["blocks"]["lead"]["headline"] = "Ships wait at the Strait → again"
    res = chat.check_paper(ed, reply(bad), "2026-10-12", issue["issue"], out_pdf=str(tmp_path / "p.pdf"))
    assert not res["ok"] and "pdf" not in res
    assert "OVER" in res["fix"] and "cannot print" in res["fix"] and "complete corrected JSON" in res["fix"]
    assert res["problem"].startswith(f"{len(res['errors'])} things to fix")


@pytest.mark.parametrize("text,needle", [("Sorry, I cannot search the web right now.", "Turn on web search"),
                                         ("Here you go: {\"edition\": ", "paste it again")])
def test_replies_that_are_not_a_paper_are_explained(text, needle):
    res = chat.check_paper(edition.load("junior-daily"), text, "2026-10-12")
    assert not res["ok"] and needle in res["problem"]


def test_poster_instructions_and_checks(tmp_path):
    ed = edition.load("little-explorers")
    t = chat.poster_instructions(ed, "2026-10-10")
    assert "One idea, not a digest" in t and "Automatic posters" not in t and "bottleneck" in t
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
