"""Publishing tests use short PCM tones, so CI never downloads speech models."""
import json
import re
from pathlib import Path
import shutil

import pytest

from ygc import narration

PAGE = '''<!doctype html><html><head></head><body>
<section class="card"><button class="read">Read it to me</button>
<h2 class="v-orig"><span class="s">Oil &amp; gas.</span></h2>
<h2 class="v-easy" hidden><span class="s">Fuel news.</span></h2>
<p class="v-orig"><span class="s">A <mark class="w">ship</mark> arrived.</span></p>
<div class="v-easy" hidden><span class="s">A boat is here.</span></div>
<span class="s">Why it matters.</span></section>
<section class="card"><span class="s">A second story.</span></section>
<script src="../play.js"></script></body></html>'''


def manifest(page):
    return json.loads(re.search(r'<script id="narration" type="application/json">(.*?)</script>', page, re.S)[1])


def test_sentence_indexes_preserve_original_easy_and_inline_vocabulary():
    tracks = narration.tracks(PAGE)
    assert [p['index'] for p in tracks['0']['original']] == [0, 2, 4]
    assert [p['index'] for p in tracks['0']['easy']] == [1, 3, 4]
    assert [p['text'] for p in tracks['0']['original']] == ['Oil & gas.', 'A ship arrived.', 'Why it matters.']
    assert tracks['1']['original'][0]['text'] == 'A second story.'


class FakeEngine:
    def __init__(self):
        self.calls = []

    def synthesize(self, text, voice):
        self.calls.append((text, voice))
        return b'\x10\x00' * 2400, 24000


@pytest.fixture
def encoder():
    found = shutil.which('ffmpeg')
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pytest.skip('ffmpeg needed for audio encoding integration')


def test_publish_reuses_audio_and_invalidates_only_changed_sentences(tmp_path, encoder):
    site, cache = tmp_path / 'site', tmp_path / 'cache'
    page = site / 'play' / 'paper' / '2026-10-24.html'
    page.parent.mkdir(parents=True)
    page.write_text(PAGE)
    engine = FakeEngine()
    run = lambda voice='af_heart': narration.build(site, cache, voice=voice, engine_factory=lambda: engine,
                                                 ffmpeg=encoder, log=lambda *a: None)
    assert run() == 4
    first = page.read_text()
    assert first.index('id="narration"') < first.index('src="../play.js"')
    data = manifest(first)
    assert len(engine.calls) == 6  # identical sentences and variants share recordings
    for variant in data['0'].values():
        assert (page.parent / variant['src']).is_file()
        assert all(s['start'] < s['end'] for s in variant['segments'])
        assert variant['segments'][1]['start'] > variant['segments'][0]['end']
    run()
    assert len(engine.calls) == 6
    assert page.read_text().count('id="narration"') == 1
    page.write_text(PAGE.replace('A boat is here.', 'Two boats are here.'))
    run()
    changed = manifest(page.read_text())
    assert changed['0']['original']['src'] == data['0']['original']['src']
    assert changed['0']['easy']['src'] != data['0']['easy']['src']
    assert len(engine.calls) == 7
    run('af_bella')
    assert len(engine.calls) == 13
    assert manifest(page.read_text())['0']['original']['src'] != changed['0']['original']['src']


def test_missing_site_fails_before_loading_the_model(tmp_path):
    with pytest.raises(ValueError, match='Build the website first'):
        narration.build(tmp_path / 'missing', tmp_path / 'cache')


def test_player_audio_fallback_and_cancellation():
    import subprocess
    from ygc import play
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js needed for player behavior checks')
    result = subprocess.run([node, str(Path(__file__).with_name('narration-player.cjs'))], input=play.JS,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_offline_audio_byte_ranges():
    import subprocess
    from ygc import play
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js needed for service-worker checks')
    result = subprocess.run([node, str(Path(__file__).with_name('narration-offline.cjs'))], input=play.SW.replace('%CORE%', '[]'),
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
