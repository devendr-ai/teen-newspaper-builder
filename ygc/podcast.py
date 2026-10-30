"""Podcastfy's transcript/provider interface with our cached, local Kokoro voices.

Only podcastfy.tts.base is loaded: no cloud provider, URL extractor, or LLM client.
Install the pinned package with --no-deps (requirements-podcast.txt).
"""
from html import escape
import io
import wave


def turns(lines, cache, engine):
    from podcastfy.tts.base import TTSProvider
    from .brief import HOSTS
    from .narration import sentence_wav

    class KokoroTTS(TTSProvider):
        def generate_audio(self, text, voice, model="kokoro", voice2=None):
            self.validate_parameters(text, voice, model)
            return sentence_wav(text, voice, cache, engine).read_bytes()

    provider = KokoroTTS()
    # Explicit empty counterparts preserve consecutive same-host turns. Never let
    # Podcastfy insert a filler or an ending message into the checked script.
    transcript = "".join(
        f'<Person1>{escape(ln["text"]) if ln["who"] == "maya" else ""}</Person1>'
        f'<Person2>{escape(ln["text"]) if ln["who"] == "sam" else ""}</Person2>'
        for ln in lines)
    pairs = provider.split_qa(transcript, ending_message="", supported_tags=[])
    from html import unescape
    parsed = [(who, unescape(text)) for pair in pairs
              for who, text in zip(("maya", "sam"), pair) if text]
    expected = [(ln["who"], " ".join(ln["text"].split())) for ln in lines]
    if parsed != expected:
        raise ValueError("Podcastfy changed the checked transcript")
    for who, text in parsed:
        raw = provider.generate_audio(text, HOSTS[who]["voice"])
        with wave.open(io.BytesIO(raw), "rb") as src:
            if src.getnchannels() != 1 or src.getsampwidth() != 2:
                raise ValueError("Unexpected podcast audio format")
            yield src.readframes(src.getnframes()), src.getframerate()
