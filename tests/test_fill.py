"""A printed page must not be left half empty: from FILL_FROM, `check` fails a story column that ends
more than FILL_LIMIT lines short (docs/CRAFT_RULES.md). Published papers and families' own papers
(Design your own) only get a note."""
import datetime as dt
import json
import os

from ygc import checks, edition

ROOT = edition.ROOT
SHORT = os.path.join(ROOT, "editions", "global-citizen-plus", "issues", "2026", "2026-10-28.json")
FULL = os.path.join(ROOT, "editions", "junior-daily", "issues", "2026", "2026-10-28.json")
NEW = checks.FILL_FROM


def fit(eid, path, d, archive=False):
    r = checks.Report()
    checks.check_fit(edition.load(eid), json.load(open(path, encoding="utf-8")), r, d, archive)
    return r


def test_a_half_empty_story_column_fails_from_the_start_date():
    errs = [e for e in fit("global-citizen-plus", SHORT, NEW).errors if "lines short" in e]
    assert errs and all("room for about" in e and "Never invent" in e for e in errs)
    assert any("(lead)" in e for e in errs)


def test_earlier_papers_and_the_archive_only_get_notes():
    for d, archive in ((NEW - dt.timedelta(days=1), False), (NEW, True), (None, False)):
        r = fit("global-citizen-plus", SHORT, d, archive)
        assert not [e for e in r.errors if "lines short" in e]
        assert [n for n in r.notes if "lines short" in n]


def test_a_full_paper_passes():
    assert not [e for e in fit("junior-daily", FULL, NEW).errors if "lines short" in e]


def test_design_your_own_is_never_held_to_it(tmp_path):
    ed = edition.load("global-citizen-plus")
    issue = json.load(open(SHORT, encoding="utf-8"))
    issue["date"] = NEW.isoformat()
    path = os.path.join(str(tmp_path), "global-citizen-plus", "issues", "2026", f"{NEW}.json")
    held = checks.check_issue(ed, issue, path, as_of=NEW)
    own = checks.check_issue(ed, issue, path, as_of=NEW, require_fill=False)
    assert [e for e in held.errors if "lines short" in e] and not [e for e in own.errors if "lines short" in e]
