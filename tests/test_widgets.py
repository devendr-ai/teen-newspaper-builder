"""Widgets only repeat published questions; never invent facts or leak private data."""
import json
from pathlib import Path

from ygc import edition, site, widgets


def test_question_prefers_discussion_and_never_generates_one():
    issue = {'blocks': {'discussion': {'body': ['Why does this matter?']}}, 'play': {'quiz': [{'q': 'Which option is right?'}]}}
    assert widgets.question(issue) == ('Why does this matter?', 'discussion')
    assert widgets.question({'blocks': {}, 'play': issue['play']}) == ('Which option is right?', 'quiz')
    assert widgets.question({'blocks': {}, 'play': {}}) is None
    assert widgets.question({'blocks': {'discussion': {'body': ['A fact, not a question.']}}}) is None


def test_public_feed_matches_published_issue_and_reader(tmp_path, monkeypatch):
    real = site.issues_of
    monkeypatch.setattr(site, 'issues_of', lambda ed: real(ed)[:1] if ed['id'] in ['breakfast-table', 'little-explorers'] else [])
    out = tmp_path/'site'
    site.build(str(out), keep=1, kids=True, log=lambda *a: None)
    feed = json.loads((out/'widgets.json').read_text())
    assert feed['v'] == 1 and len(feed['editions']) == 2
    for row in feed['editions']:
        ed = edition.load(row['edition'])
        date, source = real(ed)[0]
        issue = json.loads(Path(source).read_text())
        assert row['date'] == date and row['question'] == widgets.question(issue)[0]
        assert row['reader'] == f'play/{ed["id"]}/{date}.html'
        assert f'name="np-issue" content="{ed["id"]}/{date}"' in (out/row['reader']).read_text()
        assert row['brief'] == (f'play/briefs/{date}.json' if ed['id'] == 'breakfast-table' else None)
        assert not any(key in row for key in ['email', 'child', 'score', 'answer', 'name_of_child'])
    parents = (out/'parents.html').read_text()
    assert 'id="np-widget-panel" hidden' in parents
    assert 'np-widget-on' in parents and 'np-widget-edition' in parents
    js = (out/'app.js').read_text()
    assert "window.npGate.parent" in js and "authorize(function(){post(desired);}" in js


def test_unpublished_or_unavailable_paper_never_appears(tmp_path):
    ed = edition.load('breakfast-table')
    result = widgets.write(tmp_path, {'breakfast-table': (ed, '2026-10-26')})
    assert result['editions'] == []  # no published reader in this build
