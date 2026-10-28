"""Printed locators must use the reader's actual geography, never decorative coastlines."""
import io
import zipfile

from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas

from ygc import checks, edition, print_maps, scenes, site, world
from ygc.graphics import StyledMap


def test_legacy_labels_resolve_and_regional_title_does_not_invent_a_pin():
    assert print_maps.places({'title': 'THE EASTERN MEDITERRANEAN', 'label_top': 'ISRAEL', 'label_bottom': 'EGYPT'}) == (['Israel', 'Egypt'], None)
    assert print_maps.places({'countries': ['USA', 'India'], 'place': 'New Delhi'}) == (['United States', 'India'], 'Delhi')
    assert print_maps.places({'title': 'SEA', 'label_top': 'LAND'}) == ([], None)


def test_geometry_preserves_country_rings_and_projection():
    countries = dict((c['name'], rings) for c, rings in print_maps.geometry())
    assert len(countries) == len(world.countries())
    assert all(len(r) >= 3 for rings in countries.values() for r, _ in rings)
    israel = world.project(*world.by_name()['Israel']['label'])
    egypt = world.project(*world.by_name()['Egypt']['label'])
    assert israel[0] > egypt[0] and israel[1] < egypt[1]
    box = print_maps.viewport(['Israel', 'Egypt'], None, 250, 90)
    assert abs((box[2]-box[0])/(box[3]-box[1]) - 250/90) < 1e-8
    for point in (israel, egypt):
        assert box[0] < point[0] < box[2] and box[1] < point[1] < box[3]


def pdf_text(spec):
    output = io.BytesIO()
    c = Canvas(output)
    StyledMap(spec, width=260, height=122).drawOn(c, 20, 20)
    c.save()
    return PdfReader(output).pages[0].extract_text()


def test_print_labels_credit_and_honest_unknown_fallback():
    text = pdf_text({'countries': ['Israel', 'Egypt'], 'title': 'THE EASTERN MEDITERRANEAN'})
    assert all(s in text for s in ('Israel', 'Egypt', 'Natural Earth'))
    text = pdf_text({'title': 'UNKNOWN', 'label_top': 'LAND'})
    assert 'No geographic map is shown' in text and 'Natural Earth' not in text


def test_talks_diagram_uses_story_participants_and_checks_grounding():
    from xml.etree import ElementTree
    spec = {'motif': 'talks', 'title': 'THREE-WAY TALKS', 'participants': ['Ukraine', 'Russia', 'United States']}
    svg = scenes.scene('talks', 'A & B', spec)
    ElementTree.fromstring(svg)
    assert all(name in svg for name in spec['participants'])
    ed = edition.load('global-citizen-plus')
    story = {'headline': 'Ukraine and Russia talk with the United States', 'illustration': spec}
    result = checks.Report()
    checks.check_graphics(ed, story, 'world', 260, result)
    assert result.errors == []
    story['headline'] = 'Ukraine and Russia talk'
    result = checks.Report()
    checks.check_graphics(ed, story, 'world', 260, result)
    assert any('United States' in err and 'named in the story' in err for err in result.errors)


def test_browser_builder_engine_includes_geography(tmp_path):
    with zipfile.ZipFile(site.engine_zip(str(tmp_path / 'engine.zip'))) as pack:
        assert pack.read('data/world/countries.topo.json')
        assert pack.read('ygc/print_maps.py')
