"""Optional print extras must never change the regular paper or mismatch an issue."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from pypdf import PdfReader
from ygc import edition, render, site, weekend


def sample():
    ed = edition.load('little-explorers')
    issue = json.loads((Path(edition.ROOT) / 'editions/little-explorers/issues/2026/2026-10-24.json').read_text())
    return ed, issue


def test_weekend_pdf_keeps_news_and_adds_one_matched_page(tmp_path):
    ed, issue = sample()
    news, combined = tmp_path/'news.pdf', tmp_path/'puzzles.pdf'
    render.build(ed, issue, str(news))
    before = news.read_bytes()
    assert weekend.build(ed, '2026-10-24', issue, news, combined)
    assert news.read_bytes() == before
    base, extra = PdfReader(news), PdfReader(combined)
    assert len(base.pages) == 2 and len(extra.pages) == 3
    assert [p.extract_text() for p in extra.pages[:2]] == [p.extract_text() for p in base.pages]
    text = extra.pages[2].extract_text()
    assert 'Unjumble it!' in text and 'ROVER' in text and 'Weekend extra' in text


def test_only_weekend_little_explorer_with_matching_reviewed_art():
    ed, issue = sample()
    assert weekend.load(ed, '2026-10-24', issue)
    assert weekend.load(dict(ed, id='breakfast-table'), '2026-10-24', issue) is None
    assert weekend.load(ed, '2026-10-26', issue) is None
    assert weekend.load(ed, '2026-10-31', issue) is None  # no previous comic reuse
    changed = copy.deepcopy(issue)
    changed['blocks']['science_and_technology']['headline'] = 'A new story'
    with pytest.raises(ValueError, match='headline'):
        weekend.load(ed, '2026-10-24', changed)
    changed = copy.deepcopy(issue)
    changed['blocks']['science_and_technology']['body'] = 'Unrelated facts.'
    with pytest.raises(ValueError, match='evidence'):
        weekend.load(ed, '2026-10-24', changed)


@pytest.mark.parametrize('mutation', ['path', 'hash', 'words', 'source'])
def test_rejects_unreviewed_or_unsafe_extras(tmp_path, monkeypatch, mutation):
    ed, issue = sample()
    root = Path(edition.ROOT)
    spec = json.loads((root/'editions/little-explorers/weekend/2026-10-24.json').read_text())
    dest = tmp_path/'editions/little-explorers/weekend'
    dest.mkdir(parents=True)
    import shutil
    shutil.copytree(root/'editions/little-explorers/weekend/assets', dest/'assets')
    if mutation == 'path': spec['image'] = '../../../../outside.jpg'
    if mutation == 'hash': spec['image_sha256'] = '0'*64
    if mutation == 'words': spec['words'] = ['FAKE', 'MARS', 'ROCK']
    if mutation == 'source': spec['source_url'] = 'https://example.com'
    (dest/'2026-10-24.json').write_text(json.dumps(spec))
    monkeypatch.setattr(edition, 'ROOT', str(tmp_path))
    with pytest.raises(ValueError): weekend.load(ed, '2026-10-24', issue)


def test_word_hunts_are_reproducible_and_solvable():
    for i in range(100):
        rows = weekend.word_grid(['ROVER', 'MARS', 'ROCK'], str(i))
        assert rows == weekend.word_grid(['ROVER', 'MARS', 'ROCK'], str(i))
        assert len(rows) == 6 and all(len(row) == 6 for row in rows)
        assert all(sum(row.count(w) for row in rows) == 1 for w in ['ROVER', 'MARS', 'ROCK'])


def test_all_committed_weekend_specs_are_valid():
    ed, _ = sample()
    for path in (Path(edition.ROOT)/'editions/little-explorers/weekend').glob('*.json'):
        issue_path = Path(edition.ROOT)/'editions/little-explorers/issues'/path.stem[:4]/path.name
        assert weekend.load(ed, path.stem, json.loads(issue_path.read_text()))


def test_print_choices_are_only_offered_for_successful_variants(tmp_path, monkeypatch):
    real = site.issues_of
    # The issue with the reviewed supplement, as the newest one; later Saturdays may not have one.
    monkeypatch.setattr(site, 'issues_of', lambda ed: [i for i in real(ed) if i[0] <= '2026-10-24'][:1] if ed['id'] == weekend.EDITION else [])
    out = tmp_path/'site'
    site.build(str(out), keep=1, log=lambda *a: None)
    index = (out/'index.html').read_text()
    assert 'data-weekend-pdf' in index and 'e/little-explorers/2026-10-24-puzzles.pdf' in index
    assert (out/'e/little-explorers/latest.pdf').read_bytes() == (out/'e/little-explorers/2026-10-24.pdf').read_bytes()
    assert len(PdfReader(out/'e/little-explorers/latest-puzzles.pdf').pages) == 3
    for path in ['e/little-explorers/index.html', 'e/little-explorers/2026-10-24.html']:
        assert 'data-weekend-pdf' in (out/path).read_text()
    assert not any('weekend-download' in p.read_text() for p in (out/'play').rglob('*.html'))
    cfg = site.site_config()
    monkeypatch.setattr(site, 'site_config', lambda: dict(cfg, weekend_puzzles={'enabled': False}))
    site.build(str(out), keep=1, log=lambda *a: None)
    assert 'class="weekend-download"' not in (out/'index.html').read_text()
    assert not (out/'e/little-explorers/latest-puzzles.pdf').exists()


def test_new_issue_never_inherits_old_supplement(tmp_path, monkeypatch):
    ed, issue = sample()
    later = copy.deepcopy(issue)
    later['date'] = '2026-10-31'
    source = tmp_path/'2026-10-31.json'
    source.write_text(json.dumps(later))
    old = Path(edition.ROOT)/'editions/little-explorers/issues/2026/2026-10-24.json'
    monkeypatch.setattr(site, 'issues_of', lambda e: [('2026-10-31', str(source)), ('2026-10-24', str(old))] if e['id'] == weekend.EDITION else [])
    out = tmp_path/'site'
    site.build(str(out), keep=2, log=lambda *a: None)
    assert (out/'e/little-explorers/2026-10-24-puzzles.pdf').exists()
    assert not (out/'e/little-explorers/latest-puzzles.pdf').exists()
    assert 'class="weekend-download"' not in (out/'index.html').read_text()
    assert 'class="weekend-download"' not in (out/'e/little-explorers/2026-10-31.html').read_text()


def test_every_new_download_link_is_gated_in_app(tmp_path):
    from ygc import kids
    import re
    body = site.weekend_link('2026-10-24.pdf') + site.paper_actions('2026-10-24.pdf', '2026-10-24.html', 'Paper', True)
    (tmp_path/'index.html').write_text(site.page(site.site_config(), 'Print', body))
    kids.finish(str(tmp_path), site.site_config(), log=lambda *a: None)
    doc = (tmp_path/'index.html').read_text()
    links = re.findall(r'<a\b[^>]+>', doc)
    new_links = [a for a in links if 'data-weekend-pdf' in a or 'data-weekend-fallback' in a]
    assert len(new_links) == 4
    assert all('data-gate' in a and 'data-gate-reason="print"' in a for a in new_links)
