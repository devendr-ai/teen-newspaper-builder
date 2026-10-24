"""Build free Kokoro recordings for the exact sentences rendered by Read & Play.

Run AFTER `ygc site`: python -m ygc.narration --site _site
Only this optional publishing step needs requirements-narration.txt and ffmpeg.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request
import wave
from html.parser import HTMLParser

ENGINE = 'kokoro-onnx-0.4.8-v1.0-int8-pcm-v1'
VOICE = 'af_heart'
RELEASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'
MODEL_SHA256 = {
    'kokoro-v1.0.int8.onnx': 'ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c',
    'voices-v1.0.bin': 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d',
}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
MARKER = re.compile(r'<script id="narration" type="application/json">.*?</script>', re.S)


class Sentences(HTMLParser):
    """Keep DOM sentence indexes, including hidden original/easier versions."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        parent = self.stack[-1] if self.stack else {}
        card = parent.get('card')
        if 'card' in classes:
            card = len(self.cards)
            self.cards.append([])
        variant = ('easy' if 'v-easy' in classes else 'original' if 'v-orig' in classes
                   else parent.get('variant', 'both'))
        sentence = parent.get('sentence')
        if 's' in classes and card is not None:
            sentence = {'index': len(self.cards[card]), 'variant': variant, 'text': ''}
            self.cards[card].append(sentence)
        if tag == 'br' and sentence is not None:
            sentence['text'] += ' '
        if tag not in VOID:
            self.stack.append(dict(tag=tag, card=card, variant=variant, sentence=sentence))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.stack and self.stack[-1].get('sentence') is not None:
            self.stack[-1]['sentence']['text'] += data


def normalized(text):
    return ' '.join(text.split())


def tracks(source):
    parser = Sentences()
    parser.feed(source)
    return {str(i): {variant: [{'index': s['index'], 'text': normalized(s['text'])}
                             for s in card if s['variant'] in ('both', variant) and normalized(s['text'])]
                     for variant in ('original', 'easy')}
            for i, card in enumerate(parser.cards) if card}


def fingerprint(text, voice):
    return hashlib.sha256((ENGINE + '\0' + voice + '\0' + normalized(text)).encode()).hexdigest()


def download(url, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        temp = dest.with_suffix(dest.suffix + '.part')
        try:
            urllib.request.urlretrieve(url, temp)
            temp.replace(dest)
        finally:
            temp.unlink(missing_ok=True)


class KokoroEngine:
    def __init__(self, model_dir):
        # Imported only for publishing. The newspaper builder and tests stay lightweight.
        import numpy as np
        import onnxruntime as ort
        from kokoro_onnx import Kokoro
        ort.disable_telemetry_events()
        self.np = np
        model_dir = Path(model_dir)
        for name in ('kokoro-v1.0.int8.onnx', 'voices-v1.0.bin'):
            download(RELEASE + name, model_dir / name)
        for name, expected in MODEL_SHA256.items():
            with (model_dir / name).open('rb') as model:
                if hashlib.file_digest(model, 'sha256').hexdigest() != expected:
                    raise ValueError(f'Unexpected model checksum: {name}; remove it from {model_dir} and retry')
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(model_dir / 'kokoro-v1.0.int8.onnx'), sess_options=options,
                                      providers=['CPUExecutionProvider'])
        self.engine = Kokoro.from_session(session, str(model_dir / 'voices-v1.0.bin'))
        # This pinned export declares speed as float, while the engine's input_ids
        # path constructs int32. Honor the model schema at the inference boundary.
        class ModelSession:
            def get_inputs(self):
                return session.get_inputs()

            def run(inner, outputs, inputs):
                inputs = dict(inputs)
                speed_type = next(x.type for x in session.get_inputs() if x.name == 'speed')
                dtype = np.float32 if speed_type == 'tensor(float)' else np.int32
                inputs['speed'] = np.asarray(inputs['speed'], dtype=dtype)
                return session.run(outputs, inputs)
        self.engine.sess = ModelSession()

    def synthesize(self, text, voice):
        samples, rate = self.engine.create(text, voice=voice, speed=1.0, lang='en-us')
        pcm = (self.np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
        if not pcm:
            raise ValueError('Kokoro returned empty audio')
        return pcm, rate


def sentence_wav(text, voice, cache, engine):
    path = cache / 'sentences' / (fingerprint(text, voice) + '.wav')
    if not path.exists():
        pcm, rate = engine().synthesize(text, voice)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp')
        with wave.open(str(temp), 'wb') as out:
            out.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
            out.writeframes(pcm)
        temp.replace(path)
    return path


def recording(parts, voice, cache, engine, ffmpeg):
    # Include sentence boundaries in the hash, so corrected segmentation invalidates audio too.
    key = fingerprint(json.dumps([p['text'] for p in parts], ensure_ascii=False), voice)
    mp3, timing = cache / 'recordings' / (key + '.mp3'), cache / 'recordings' / (key + '.json')
    if mp3.exists() and timing.exists():
        times = json.loads(timing.read_text())
    else:
        mp3.parent.mkdir(parents=True, exist_ok=True)
        times, cursor = [], 0
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / 'track.wav'
            with wave.open(str(wav), 'wb') as out:
                rate = None
                for part in parts:
                    with wave.open(str(sentence_wav(part['text'], voice, cache, engine)), 'rb') as src:
                        if rate is None:
                            rate = src.getframerate()
                            out.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
                        if src.getframerate() != rate or src.getnchannels() != 1 or src.getsampwidth() != 2:
                            raise ValueError('Unexpected narration audio format')
                        frames = src.readframes(src.getnframes())
                    duration = len(frames) / (2 * rate)
                    times.append({'start': round(cursor, 4), 'end': round(cursor + duration, 4)})
                    out.writeframes(frames)
                    # A short sentence pause, without starting a separate media element on mobile.
                    out.writeframes(b'\0\0' * int(rate * .12))
                    cursor += duration + .12
            temp = Path(tmp) / 'track.mp3'
            subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-i', str(wav),
                            '-codec:a', 'libmp3lame', '-b:a', '64k', str(temp)], check=True)
            shutil.copyfile(temp, mp3)
        timing.write_text(json.dumps(times))
    if len(times) != len(parts):
        raise ValueError('Narration timing does not match the story')
    return mp3, [dict(t, index=p['index']) for p, t in zip(parts, times)]


def build(site, cache, voice=VOICE, model_dir=None, engine_factory=None, ffmpeg='ffmpeg', log=print):
    site, cache = Path(site), Path(cache)
    if not (site / 'play').is_dir():
        raise ValueError('Build the website first: python -m ygc site --out _site')
    model_dir = model_dir or cache / 'model'
    instance = None

    def engine():
        nonlocal instance
        if instance is None:
            instance = engine_factory() if engine_factory else KokoroEngine(model_dir)
        return instance

    audio_dir = site / 'play' / 'audio'
    audio_dir.mkdir(exist_ok=True)
    count = 0
    live_sentences, live_recordings = set(), set()
    # Newest issues first; content-addressed sentence and track files are shared across editions.
    pages = sorted((site / 'play').rglob('*.html'), key=lambda p: p.name, reverse=True)
    for page in pages:
        source = MARKER.sub('', page.read_text(encoding='utf-8'))
        manifest = {}
        for card, variants in tracks(source).items():
            manifest[card] = {}
            for variant, parts in variants.items():
                if not parts:
                    continue
                live_sentences.update(fingerprint(part['text'], voice) for part in parts)
                mp3, segments = recording(parts, voice, cache, engine, ffmpeg)
                live_recordings.add(mp3.stem)
                shutil.copyfile(mp3, audio_dir / mp3.name)
                src = os.path.relpath(audio_dir / mp3.name, page.parent).replace(os.sep, '/')
                manifest[card][variant] = {'src': src, 'segments': segments}
                count += 1
        if manifest:
            payload = json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
            script = '<script id="narration" type="application/json">' + payload + '</script>'
            page.write_text(source.replace('</head>', script + '</head>'), encoding='utf-8')
            log(f'  narration {page.relative_to(site)}: {len(manifest)} sections')
    # Bound the persistent cache to the retained reading window, not every historical issue.
    for folder, live in (('sentences', live_sentences), ('recordings', live_recordings)):
        for old in (cache / folder).glob('*'):
            if old.is_file() and old.stem not in live:
                old.unlink()
    # Credit the actual model and engine; no claim that a human recorded these readings.
    (audio_dir / 'README.txt').write_text(
        'AI narration generated locally with Kokoro-82M v1.0 (Apache-2.0 model weights)\n'
        'https://huggingface.co/hexgrad/Kokoro-82M\n'
        'Engine: kokoro-onnx (MIT) https://github.com/thewh1teagle/kokoro-onnx\n'
        f'Voice: {voice}. No paid speech service or API key is used.\n')
    log(f'  narration ready: {count} section versions')
    return count


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', default='_site')
    p.add_argument('--cache', default='.cache/narration')
    p.add_argument('--voice', default=VOICE, choices=['af_heart', 'af_bella'])
    p.add_argument('--model-dir')
    args = p.parse_args()
    build(args.site, args.cache, args.voice, args.model_dir)


if __name__ == '__main__':
    main()
