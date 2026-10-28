"""Explanatory graphics replace a slot without fabricating the explanation or breaking layout."""
import copy
import io
import json
from pathlib import Path
from xml.etree import ElementTree

import pytest
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from ygc import checks, edition, play, render, visuals

SAMPLE = Path(edition.ROOT) / 'editions/global-citizen-plus/issues/2026/2026-10-28.json'


def story(bid='lead'):
    return json.loads(SAMPLE.read_text())['blocks'][bid]


@pytest.mark.parametrize('bid', ['lead', 'economics', 'science_and_technology'])
def test_evidence_linked_visuals_render_in_both_formats(bid):
    s = story(bid); v = s['visual']
    assert visuals.validate(s) == []
    svg = visuals.svg(v)
    ElementTree.fromstring(svg)
    assert visuals.summary(v) in __import__('html').unescape(svg)
    assert 'explanatory' in play.top_figure(s, None)
    output = io.BytesIO(); canvas = Canvas(output)
    visuals.StoryVisual(v, 260, 122).drawOn(canvas, 10, 10); canvas.save()
    text = PdfReader(output).pages[0].extract_text()
    assert v['title'] in text
    if v['type'] == 'bars':
        assert all(str(i['value']) in text for i in v['items'])
        assert 'zero baseline' in text
    if v['type'] == 'seats':
        dots = [p for p in visuals.commands(v) if p[0] == 'circle']
        assert len(dots) == 120 and sum(p[-1] == visuals.TEAL for p in dots) == 61
        assert 'not election results' in text


@pytest.mark.parametrize('change', [
    {'total': 0}, {'threshold': 60}, {'threshold': True}, {'source_url': 'https://made-up.test'},
    {'total_evidence': 'The invented parliament has 120 seats'}, {'title': 'W'*44},
    {'type': 'mystery'},
])
def test_bad_seats_and_unsupported_evidence_fail(change):
    s = story(); s['visual'].update(change)
    assert visuals.validate(s)


def test_bar_numbers_need_evidence_and_valid_units():
    s = story('economics'); v = s['visual']
    for value in (-1, True, float('nan'), float('inf'), 96):
        bad = copy.deepcopy(s); bad['visual']['items'][0]['value'] = value
        assert visuals.validate(bad)
    v['unit'] = ''
    assert visuals.validate(s)


def test_large_parliament_uses_proportional_seat_bar():
    v = dict(story()['visual'], total=650, threshold=326)
    assert not any(p[0] == 'circle' for p in visuals.commands(v))
    rects = [p for p in visuals.commands(v) if p[0] == 'rect']
    assert rects[-1][3] / rects[-2][3] == pytest.approx(326/650)


def test_replacements_are_required_checked_and_preserve_page_count(tmp_path):
    iss = json.loads(SAMPLE.read_text()); ed = edition.load(iss['edition'])
    result = checks.check_issue(ed, iss, str(SAMPLE), archive=True)
    assert result.errors == []
    assert all(m['over'] < .5 for m in render.measure(ed, iss))
    assert len(PdfReader(render.build(ed, iss, str(tmp_path / 'paper.pdf'))).pages) == 4
    iss['blocks']['lead']['visual']['threshold'] = 62
    assert any('majority threshold' in err for err in checks.check_issue(ed, iss, str(SAMPLE), archive=True).errors)
    # Without a replacement, edition-required graphics still apply.
    iss['blocks']['lead'].pop('visual')
    assert any('map is required' in err for err in checks.check_issue(ed, iss, str(SAMPLE), archive=True).errors)


def test_legacy_illustrations_and_charts_keep_working():
    assert 'class="bc' in play.top_figure({'chart': {'title':'x','labels':['A','B'],'values':[1,2],'max':2}},None)
    assert 'scene' in play.top_figure({'illustration':{'motif':'globe'}},None)


def test_chart_labels_do_not_silently_round_source_numbers():
    s = story('economics')
    s['body'].append('The comparison value is 123456.789 in this test.')
    s['visual']['items'][0].update(value=123456.789, evidence='The comparison value is 123456.789 in this test.')
    assert visuals.validate(s) == []
    assert '123456.789' in visuals.svg(s['visual'])


def test_podium_cannot_be_selected_as_a_metaphor_for_talks_or_awards():
    from ygc.graphics import IllustrationCard
    from ygc import prompt
    assert 'podium' not in IllustrationCard.known_motifs()
    for p in Path(edition.ROOT).glob('editions/*/issues/*/*.json'):
        issue = json.loads(p.read_text())
        assert all(b.get('illustration', {}).get('motif') != 'podium'
                   for b in issue['blocks'].values() if isinstance(b, dict)), str(p)
    s = story(); s.pop('visual')
    s['illustration'] = dict(motif='podium',title='Three-way talks',subtitle='Three sides',caption='Talks')
    result = checks.Report()
    checks.check_graphics(edition.load('global-citizen-plus'), s, 'world', 260, result)
    assert any('podium' in err for err in result.errors)
    assert 'medal ranks or confetti' in prompt.generate(edition.load('europe-explained'))
