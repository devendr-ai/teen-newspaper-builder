"""The "Big Question" poster: every committed poster passes its checks and prints on one page,
and the checks catch the mistakes that would spoil a printed poster."""
import copy
import glob
import json
import os

import pytest
from pypdf import PdfReader

from ygc import edition, poster

ROOT = edition.ROOT
POSTERS = sorted(glob.glob(os.path.join(ROOT, "editions", "*", "posters", "*", "*.json")))
SAMPLE = os.path.join(ROOT, "editions", "little-explorers", "posters", "2026", "2026-10-10.json")


@pytest.mark.parametrize("path", POSTERS, ids=lambda p: os.path.relpath(p, ROOT))
def test_committed_poster_passes_and_builds_one_page(path, tmp_path):
    ed, p = poster.load(path)
    r = poster.check(ed, p, path)
    assert r.errors == [], r.errors
    pdf = poster.build(ed, p, str(tmp_path / "p.pdf"))
    assert len(PdfReader(pdf).pages) == 1


def _broken(change):
    ed, p = poster.load(SAMPLE)
    p = copy.deepcopy(p)
    change(p)
    return poster.check(ed, p, SAMPLE).errors


def test_text_that_does_not_fit_is_a_located_error():
    errs = _broken(lambda p: p.update(happened=p["happened"] * 3))
    assert any(e.startswith("what happened is OVER") for e in errs), errs


def test_bad_motif_missing_sources_and_unprintable_characters_are_refused():
    errs = _broken(lambda p: (p["hero"].update(motif="dragon"), p.update(sources=[]),
                              p.update(question=p["question"] + " →")))
    assert any("hero.motif" in e for e in errs)
    assert any(e.startswith("sources") for e in errs)
    assert any("cannot print" in e for e in errs)


def test_skeleton_is_refused_until_filled_in():
    ed = edition.load("little-explorers")
    errs = poster.check(ed, poster.skeleton(ed, "2026-10-10"), SAMPLE).errors
    assert any("question is empty" in e for e in errs) and any("motif" in e for e in errs)
