"""News remains primary, the printout fits, and the scheduled writer has evidence."""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

from ygc import edition, poster
from ygc.auto import poster_writer, run

SAMPLE = Path(edition.ROOT) / 'editions/little-explorers/posters/2026/2026-10-31.json'


def spec():
    return json.loads(SAMPLE.read_text())


def errors(change):
    ed = edition.load('little-explorers')
    p = spec()
    change(p)
    return poster.check(ed, p, str(SAMPLE)).errors


def test_two_sourced_stories_and_small_comic_print_on_one_page(tmp_path):
    ed = edition.load('little-explorers')
    p = spec()
    assert not poster.check(ed, p, str(SAMPLE)).errors
    pdf = poster.build(ed, p, str(tmp_path/'poster.pdf'))
    reader = PdfReader(pdf)
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    for s in p['stories']:
        assert s['headline'] in text
        assert s['deck'] in text
    assert 'THE PEBBLE REPORTERS' in text
    assert 'THE LITTLE EXPLORER' in text
    assert 'Colour' not in text and 'SKILL:' not in text


def test_two_distinct_topics_and_exact_evidence_are_required():
    assert any('two different' in e for e in errors(lambda p: p['stories'][1].update(block='lead')))
    assert any('evidence' in e for e in errors(lambda p: p['stories'][0]['evidence'].__setitem__(0, 'Invented research findings.')))
    assert any('sources' in e for e in errors(lambda p: p['stories'][0].update(sources=['https://invented.example'])))
    assert any('exactly two' in e for e in errors(lambda p: p['stories'].pop()))


def test_real_map_and_source_matched_comic_are_required():
    assert any('real geography' in e for e in errors(lambda p: p['find_it']['map'].update(countries=['Atlantis'])))
    assert any('named in' in e for e in errors(lambda p: p['find_it']['map'].update(countries=['Japan'])))
    assert any('first selected' in e for e in errors(lambda p: p['find_it'].update(story_block='science_and_technology')))
    assert any('exact issue excerpt' in e for e in errors(lambda p: p['comic']['panels'][0].update(evidence='A story that never happened.')))


def test_overflow_and_changed_art_block_publication(tmp_path):
    assert any('OVER' in e for e in errors(lambda p: p['stories'][0]['body'].__setitem__(0, 'Too much text. '*100)))
    assert any('art changed' in e for e in errors(lambda p: p['stories'][0]['art'].update(sha256='wrong')))
    assert any('inside assets/poster' in e for e in errors(lambda p: p['stories'][0]['art'].update(file='../../site.yaml')))
    p = spec(); p['comic']['panels'][0]['text'] = 'Too much text '*100
    with pytest.raises(ValueError, match='Invalid news poster'):
        poster.build(edition.load('little-explorers'), p, str(tmp_path/'bad.pdf'))


def test_no_optional_art_still_builds_a_real_map(tmp_path):
    p = spec(); del p['stories'][0]['art']
    ed = edition.load('little-explorers')
    assert not poster.check(ed, p, str(SAMPLE)).errors
    poster.build(ed, p, str(tmp_path/'poster.pdf'))


def test_saturday_schedule_preserved(tmp_path):
    ed = copy.deepcopy(edition.load('little-explorers'))
    assert ed['automation'] == dict(enabled=True, weekday='saturday', poster=True)
    assert ed['cadence']['every_days'] == 7
    ed['_dir'] = str(tmp_path)
    folder = tmp_path/'issues/2026'; folder.mkdir(parents=True)
    original = Path(edition.ROOT)/'editions/little-explorers/issues/2026/2026-10-31.json'
    (folder/original.name).write_bytes(original.read_bytes())
    assert not run.is_due(ed, dt.date(2026, 11, 6))
    assert run.is_due(ed, dt.date(2026, 11, 7))
    assert not run.is_due(ed, dt.date(2026, 11, 8))


def test_scheduled_writer_receives_full_issue_and_version_two_shape():
    ed = edition.load('little-explorers')
    issue = json.loads((Path(ed['_dir'])/'issues/2026/2026-10-31.json').read_text())
    pool = json.loads((Path(edition.ROOT)/'data/pools/2026-10-31.json').read_text())
    class Client:
        def __init__(self): self.calls = []
        def create(self, system, messages, **kwargs):
            self.calls.append((system, messages))
            return None, json.dumps({'unsupported': []} if system.startswith('You are a fact-checker') else spec()), None
    client = Client()
    result, report = poster_writer.write_poster(client, ed, dt.date(2026, 10, 31), issue, pool)
    assert report['status'] == 'passed' and result['version'] == 2
    system, messages = client.calls[0]
    assert 'TWO different stories' in system
    assert '"version": 2' in system
    assert issue['blocks']['lead']['body'][2] in messages[0]['content']
    assert issue['blocks']['science_and_technology']['body'][2] in messages[0]['content']
