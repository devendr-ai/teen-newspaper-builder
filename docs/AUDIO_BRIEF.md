# The car-ride brief

A three-minute, two-host audio version of **The Breakfast Table**, on Read & Play
only (not the home page). It is a test: we keep it if families start and finish it.

## How it is made

1. **Script.** The nightly run writes `play.brief.lines` in each Breakfast Table issue,
   following `editions/breakfast-table/PROMPT.md`. Each line is
   `{"who": "maya" | "sam", "text": "...", "chapter": "Riyadh & oil"}`; `chapter`
   marks the first line of each story. Maya explains; Sam asks what a curious
   nine-year-old would ask.
2. **Check.** `ygc check` runs `ygc/brief.py: check()`. It requires both hosts, 300 to
   600 words, 2 to 6 short chapter labels, turns of at most 70 words, no web
   addresses, and **no number that the issue itself doesn't give** (rounding allowed).
   A paper opts in with `site: {audio_brief: true}` in its `edition.yaml`.
3. **Site build.** `ygc site` writes the script to `play/briefs/<date>.json`, and the
   lobby gets an empty `#brief` slot under *Today's papers*.
4. **Audio.** The publishing step `python -m ygc.narration` (`briefs()`) reads the
   newest script aloud with two Kokoro voices (Maya `af_heart`, Sam `am_michael`), adds a
   short chime between stories, and writes `play/audio/<hash>.mp3`, the line and chapter
   timings, `play/briefs/latest.json` and the podcast feed `play/podcast.xml`. Recordings
   are cached in `.cache/narration` like story narration, so a rebuild costs nothing. A new
   brief adds a few minutes to the deploy.

## The player (`ygc/brief.py`: `CSS`, `JS`)

One compact row at the top of *Today's papers*: artwork, "Car-ride brief · 3 min", title,
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
