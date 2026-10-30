# The car-ride brief

A **3–5 minute**, two-host conversation from **The Breakfast Table**, on Read & Play
and the app's Listen tab. Read it to me still narrates each article faithfully.

## How it is made

1. **Script.** Scheduled issue generation writes `play.brief.format: 2` with a warm
   welcome/curiosity hook (about 15 seconds), exactly three stories with a concrete
   sourced explanation each, two quiz questions and answers, one family discussion
   question and a cheerful close. Maya hosts; Sam asks purposeful questions. Target
   450–620 words. Story turns reference their issue block via `story`; chapters label
   the three story starts. See `ygc/brief.py: PROMPT` for the versioned fields.
2. **Grounding.** The writer uses the existing verified research pool. Its independent
   fact-check explicitly reviews every brief claim against both the referenced story
   and the pool. Mechanical checks enforce order, three distinct story references,
   two existing quiz items about covered stories, exact checked answers, the issue's
   discussion question, no added numbers, short turns and both hosts. These checks
   do not replace editorial review. Legacy archived scripts remain valid.
3. **Podcastfy + Kokoro.** `ygc/podcast.py` implements Podcastfy's `TTSProvider` with
   our existing local Kokoro engine and cache. Podcastfy parses its Person1/Person2
   transcript; a round-trip assertion prevents any dropped, reordered or added words,
   including consecutive same-host turns. Conversational Kokoro voices are Maya `af_bella` and
   Sam `am_michael`, synthesized at **1.06×**. Article narration and legacy briefs
   retain their original voices and cadence. Voice and speed are included in cache keys. No cloud speech API or extra LLM is invoked.
4. **Pacing.** Our assembler preserves line/chapter timings, adds a small story chime,
   inserts **four seconds of silence after each quiz question**, normalizes the MP3,
   and checks actual PCM duration is **180–300 seconds** before publication. It never
   speeds up or pads an unsuitable script to fake the target. A failed new episode
   is logged/skipped; older cached ready episodes can still be served.
5. **Delivery.** Site generation writes `play/briefs/<date>.json`; narration adds audio,
   timestamps, `latest.json` and the RSS feed. Public web and the app pack use the same
   recording. The current dated sample updates only `play.brief` in the 28 October
   issue; its printed articles and quiz are unchanged. Future scheduled issues use
   the new prompt automatically. Cached legacy recordings are reused unchanged.

Publishing prerequisites (Python 3.11+):

```sh
pip install -r requirements-narration.txt
pip install --no-deps -r requirements-podcast.txt
```

The second command pins Podcastfy 0.4.3 without its unused dependency tree. Only its
standard-library `podcastfy.tts.base` interface is imported; no cloud SDK, web-content
extraction or Podcastfy transcript generator is used. The existing issue writer
creates the grounded conversation. Both publishing workflows install this component;
there is no additional paid provider or account. FFmpeg and espeak-ng are still needed.

## The player (`ygc/brief.py`: `CSS`, `JS`)

One compact row at the top of *Today's papers*: artwork, "Car-ride brief" with its measured duration, title,
play and a ⋯ menu. While it plays, the title shows the current story ("Now: Cyclone
Arnab"), chapter buttons appear on wider screens, and a thin line along the bottom shows
progress. The ⋯ menu has **Read along** (the script with the current line highlighted;
tap a line to jump), **Jump to a story**, **Speed** (1×, 1.25×, 0.85×) and **Listen in
the car** (Add to Apple Podcasts, Copy podcast link). When the row scrolls out of view, a
mini-player stays above the bottom bar. Lock-screen and car controls come from the Media
Session API. The listening position is kept on the device. Nothing shows until the audio
exists.

## Measuring the test

GoatCounter events (anonymous, like the others): `brief/started` and `brief/finished`
(played past 90%). Compare finishes to starts, and starts to `reader/today`, over two to
three weeks. Spotify needs the owner to submit `https://newspebbles.com/play/podcast.xml`
once at podcasters.spotify.com; Apple Podcasts and other apps can subscribe to the link
directly.

## Tests

`tests/test_brief.py` (checks, audio and feed with test tones, the cache) and
`tests/brief-player.cjs` (the player in a real browser at laptop and phone sizes).
