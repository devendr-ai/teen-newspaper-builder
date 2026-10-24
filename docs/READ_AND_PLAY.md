# Read & Play: the children's side of the site

The newsstand is for grown-ups: choose a paper, download it, print it. **Read &
Play** (`/play/` on the site, built by `ygc/play.py` as part of `python -m ygc
site`) is for the child, on a tablet or phone, from the same issue files.

- **Who's reading?** The lobby asks the child's age (6–8, 9–11, 12–14, 15+) once,
  then shows "Hi! Papers for ages 9–11 · Change age". Each paper is one short row:
  a little picture (the lead story's moving picture, or a small real map zoomed to
  where it happens), the headline, and **Read** and **Play**, with ✓ once read.
  The age is remembered on the device and shared with the grown-ups' page, so
  choosing it on either one sets both.
- **One screen.** The streak and badges are two chips at the top (tap them for "My
  reading"). On a laptop the papers sit on the left, with Big stories and the news
  map on the right; on an iPad held upright Big stories and the map sit side by
  side under the papers. On a phone Big stories swipe sideways and a bottom bar
  jumps to Papers, Big stories, Map and Me. Same link on every device: the page
  picks its layout from the screen's width.
- **Read.** Each of the last 7 issues of every paper becomes a page. For ages
  6–11 it shows one story per screen (swipe, or Next and Back); older readers
  scroll. Every story and section has **Read it to me**, which uses the device's
  own voice as a fallback, or the published Kokoro recording when available, and lights up each sentence as it's read. New words from the issue
  are underlined; tapping one shows its meaning and how it's used today, and can
  say it aloud. Text size, night mode and reading speed are remembered on the
  device. Sources sit behind **For grown-ups**.
- **Pictures that move.** Each printed illustration (ship, rocket, flood, cricket
  and the rest) has a screen version that moves: the ship bobs, the rocket lifts
  off, flames flicker. They are drawn once in `ygc/scenes.py`, so every story
  that uses a motif gets them free. Printed charts become bars that grow, with
  numbers that count up, when they scroll into view. Each section has its own
  colour and icon (World, India, Science, Money...). Younger readers see a 🚀
  trail across the top as they move through the paper, and confetti at the end
  and for three stars. A phone set to "reduce motion" gets still pictures and no
  confetti.
- **Where in the world?** A story that happens somewhere gets a real world map:
  it zooms in from the whole world, colours the countries, drops a pin on the
  place, and draws a line from the reader's city with the distance ("about 3,100
  km, about 4 hours by plane"). The reader picks their city once; it's guessed
  from the device's time zone until they do. The lobby has a map of all today's
  stories; tapping a pin lists them and opens the story.
- **Play.** A menu of up to five games, each with 1 to 3 stars kept on the device, no
  timer and no losing. **The first try is what counts.** A game's first try starts with its
  first answer; its stars are kept, shown beside the best so far ("1st try ★★☆ · Now ★★★"
  in the menu and on the last screen), and are the only stars that earn pebbles and count
  towards badges, quests and My progress. Replays are practice, as many as you like: they
  can raise the best stars but never earn anything, so tapping through to see the answers
  and replaying for three stars gains nothing. A first try left unfinished counts as 0. Each game's level and tone follow the reader's age: playful
  with the owl and confetti for 6–11, plainer and harder for 12–14, exam-style for 15+.
  - *Word match*: tap a word, then its meaning. Papers without new words get
    *Story match*: tap a headline, then the sentence that starts its story.
  - *Quiz*: one question per screen, three answers. A first wrong answer gets a hint
    (the story the answer is in) and a second try, worth half a point. After that the
    right answer shows, with why and **Read it again**. Ages 6–8 can hear each question.
  - **Adaptive quiz.** Two answers right first time in a row bring a ⭐ *stretch question*;
    a miss steps back down, to an *easier question* if there is one. Stretch questions are the
    same day's quiz questions (within a day) from papers one age band older, matched to a
    story in this paper by its place or two headline words; easier ones come from a band
    younger. Older papers' questions that mention deaths or injuries are never offered to a
    younger reader. Each shows which paper it comes from, and its hint points to this
    paper's story.
  - **Levels across days: Pebble, Stone, Boulder.** A reader moves up after 10 of their last 12
    answers are right first time, over at least 2 days, and quietly back down after 3 or fewer
    of the last 8. At Stone every third quiz question is a stretch; at Boulder the quiz starts
    stretched, and Map hunt and Guess the number play one age step older (a 9-year-old gets
    one estimate instead of three hints). The level shows in the quiz, the Garden and My
    progress.
  - *Map hunt*: "Where did this happen?" Tap the world map; the real place, the
    distance and the story's countries appear. A tap that is far off gets a hint (the countries it's in)
    and one more tap, worth 2 stars at most. Ages 6–8 are asked for a country, and a
    tap anywhere in it counts. Stars for distance: within 1,000 km (6–8) or 500 km
    (9 and up) earns 3; within 2,500 km (6–8), 1,500 km (9–11) or 1,000 km (12+) earns 2.
  - *Put it in order*: a big story's events, from its "story so far" timeline at the reader's
    level, to sort oldest first with ▲ ▼ buttons: 3 events for 6–8, 4 for 9–14, 5 for 15+, each on a
    different day so there is one right order, spread over its latest news. A first wrong check
    keeps the right ones in place (green) for one more go; then the right order shows with dates
    and a link to the whole story so far. It appears when a story in the paper is linked to a big
    story; lines about deaths or injuries are left out, and ages 6–8 don't get war or disaster
    timelines as a game.
  - *Guess the number*: a number from today's news. Ages 6–8 pick from three cards,
    ten times apart, with "Bigger!" or "Smaller!" after a miss; 9–11 slide to a guess
    with up to three "Higher!/Lower!" hints; 12 and up get one estimate, scored by how
    close it is (within 10% for 3 stars, 25% for 2). Then the answer, what it means, and
    a bar comparing the guess with it.
  - *Fact or fiction?*: a claim about the issue; tap **True** or **Not true**.

- **Easier version.** On papers for 12 and up, each story has a "🪶 Easier version" button
  next to "Read it to me". It swaps the story for a simpler one (a plain headline and two to
  four short paragraphs, written for about age 10), and "Original version" swaps it back. The
  choice is remembered on the device, and "Read it to me" reads whichever version is showing.
  The easier versions are written each night with the paper (`play.easy`) from that story's
  facts only: `ygc check` fails any number that isn't in the story (rounding is fine).
- **The story so far.** Big ongoing stories (a war, an election) get one page each to catch
  up on, for younger and older readers: in one minute, a map, what happened, who's who. See
  `docs/STORY_SO_FAR.md`.
- **From paper to screen.** Papers dated from `qr_from` in `site.yaml` (16
  October 2026) print a small QR code in the masthead, "Scan to read & play". It
  opens that issue's Read & Play page. Read & Play keeps a week of papers, so an
  older paper's code opens a page that links to the newest one. Papers printed
  before that date are left exactly as they were.
- **On the home screen.** Read & Play can be added to a phone or tablet's home
  screen (Android and computers get an **Add to home screen** button; iPhone and
  iPad get a tip). It then opens full-screen, like an app, and the newest issue
  of every paper works without the internet. A service worker (`play/sw.js`)
  keeps those pages, plus any page already read; it shows the newest version
  whenever there's a connection.
- **Streaks and badges.** Reading a whole paper (reaching the last card) counts
  as reading that day. The lobby shows the reading streak as a **pebble tower** (one
  pebble for each day in a row; a pebble chip at the top shows the number) and
  how many papers have been read, and 17 badges to earn: First paper, Bookworm
  (10 papers), On fire (3 days), Super week (7), News champion (30), Map explorer
  (stories in 10 countries), Word wizard (15 new words), Good listener (5
  stories read aloud), Quiz champ, Fact detective and Perfect match (3 stars
  on three different papers' games), Map master (10 places found), Number ninja
  (10 spot-on guesses), Time keeper (5 big stories in order first time), Full set (every game in a paper), Super set (5 full sets)
  and First try (a full set with no hints). Readers 12 and up see plainer names
  ("Achievements": Cartographer, Data detective, Set complete, Clean sheet...).
  Locked badges show how close they are ("6 of 10"). A new badge pops up when it's
  earned, and a game's last screen celebrates a **Full set** when every game of the
  paper has been played.
- **Pebbles and the Pebble Garden (ages 6–11).** Reading a whole paper earns 3 pebbles,
  each star on a game's first try 1, and a Full set 2. The **Garden** button in the bottom bar opens a
  riverbank to spend them on: daisies (3) up to a rainbow (20), each in its own spot, with the
  owl and the pebble tower. Children can drag anything they own to a new spot (or use the
  arrow keys); the layout is kept on the device. A **weekly quest** (from Monday: read 5 papers, stories from 5
  countries, 2 full sets, 5 places in Map hunt, 10 new words or 3 numbers spot on) unlocks an
  animal that can't be bought, plus 5 pebbles. **My passport** colours in every country read
  about.
- **My progress (ages 12 and up).** The same button reads **Progress**: reading streak,
  answers right in the last 7 days, papers read, countries; the reader's level (Pebble, Stone,
  Boulder) and how close the next one is; right answers by topic, with
  any under 60% marked "practise"; the countries map; and a **revision list** of questions
  missed first time, with the answer, until "Got it".
- **Monthly report** (`play/report.html`). One page to print or save as a PDF, for this month
  or the two before: days and papers read, answers right, longest streak, the papers, the
  strongest and weakest topics, badges earned and the countries map, with the reader's name.
  Linked from Progress, and from the Garden "for grown-ups".
- **Certificates.** Every badge earned has a certificate to print
  (`play/certificate.html?b=<badge>`): the owl, the reader's name, the badge and what
  it was for, and the date. The name is typed on the page and kept on the device;
  "Save as PDF" in the print window keeps a copy.

Settings, stars, streaks and badges are kept in the browser and never leave the
device. If the site's anonymous visit counts are switched on (`goatcounter` in
`site.yaml`), Read & Play adds a few events with no ID: see the Privacy page and
`ygc/stats.py`.

## The map

The countries come from Natural Earth's **India point-of-view** edition, so
India's borders appear as on India's official maps (all of Jammu and Kashmir,
including Gilgit-Baltistan and Aksai Chin). `data/world/README.md` says how the
file was made. `ygc/world.py` draws it in the Equal Earth projection and writes
`play/world.js` (about 33 KB to download, once).

A story's place comes from `play.where` (below). Issues written before it
existed get a place from the countries, cities and seas named in the kicker,
headline, deck or printed map, or else the first one in the story's opening
paragraphs. A story that names nowhere gets no map.

## The `play` section

The quiz and fact-or-fiction games come from a `play` section that each issue
carries alongside its `blocks`. It is never printed. The skeleton and every
paper's `PROMPT.md` ask for it, sized by the reader's age (ages 6–8: 3 questions
and 2 claims; 9–11: 4 and 3; 12–14: 5 and 3; 15+: 8 and 4):

```json
"play": {
  "quiz": [{"q": "Which ocean is running a fever?", "options": ["The Atlantic", "The Pacific", "The Indian"],
            "answer": 1, "why": "The top story says warm water is spreading across the Pacific.", "story": "lead"}],
  "fact_or_fiction": [{"claim": "Isaias was the first hurricane of the year.", "true": true,
                       "why": "The hurricane story says so.", "story": "us"}],
  "where": [{"story": "lead", "place": "Pacific Ocean", "lat": 5, "lon": -160, "countries": ["Australia"]}],
  "numbers": [{"story": "india", "q": "On Friday morning, what was Delhi's air quality index?", "answer": 223,
               "prefix": "", "unit": "", "min": 0, "max": 500, "why": "It was 223, in the “poor” group."}]
}
```

`numbers` feeds Guess the number: 1 to 4 questions whose `answer` is a number the story
itself gives (`ygc check` fails one that isn't, within 1%), shown with `prefix` ("$",
"Rs ") and `unit` ("km", "%", "million", "times"). The slider runs from `min` to `max`,
which must leave the answer well inside (not in the first or last tenth), and spans at
most 1,000 times; a range wider than 50 times slides in "times" rather than "plus". Any
number in `q` or `why` must also be in the story. Map hunt needs no new data: it uses
`where`.

Papers for 12 and up also carry `easy`: `{"<story id>": {"headline": "...", "body": ["...", "..."]}}`,
60 to 170 words with short sentences (14 words on average).

`where` has one entry for each story that happens in a particular place (stories
that don't are left out): the place as a child would name it, its latitude and
longitude, and the countries the story is about.

`python -m ygc check` makes sure each question has three different answers and
one right one, every claim says true or not, there is at least one of each, and
`story` names a story in the issue. For `where` it checks the place is named,
the latitude and longitude are real numbers, and no story is listed twice; a
country the map doesn't know gets a note. Issues written before the section existed
get a note, not an error, and keep Word match. Papers from *Design your own*
don't ask the parent's chatbot for it.

## Natural read-aloud narration (free)

The GitHub Pages publishers generate Kokoro recordings **after** building the
site. No speech API, account, GPU or subscription is required. Standard Linux
GitHub-hosted runners are free for public repositories, subject to GitHub usage
and storage limits. Publishing generates the newest issue of every paper first
(`--latest-only`), including original and easier versions. Older issues and
story-so-far pages reuse any recordings already in the Actions cache and otherwise
use the device voice. This keeps archive generation from delaying publication.
Omit `--latest-only` for a full archive backfill. Later builds reuse unchanged
sentence audio and complete recordings from the Actions cache.

The default voice is **Heart** (`af_heart`); **Bella** (`af_bella`) is also supported.
To audition them locally:

```sh
# Install ffmpeg and espeak-ng using your system package manager first.
pip install -r requirements.txt -r requirements-narration.txt
python -m ygc site --out _site
python -m ygc.narration --site _site --voice af_heart
# To compare the other voice, rerun with --voice af_bella.
python -m http.server --directory _site 8000
```

The model and voice files download once to `.cache/narration/model` from the
pinned kokoro-onnx release and are checked against SHA-256 checksums. They never
ship to readers. MP3s and timing indexes are content-addressed by exact text,
voice and engine revision. A correction or a new voice invalidates the affected
recordings. Original and easier versions are generated separately from the exact
visible sentence spans, including headline, deck and explanatory boxes.

The existing Read it to me / Stop button uses a single MP3 per section, preserves
Slow / Normal / Fast playback, and highlights sentences from the accompanying
timings. Switching story or easier version cancels playback. A small AI narration
label identifies generated recordings. Vocabulary pop-ups and quiz prompts still
use the device voice. If a recording cannot load, reading falls back to that voice
without blocking the page. An online listen saves the complete recording for
offline replay when browser storage is available; merely opening the issue does
not download every audio file. Browser storage may be evicted by the device.

Only recordings referenced by current pages are copied into the published site;
the larger intermediate WAVs and model remain in the build cache. Never commit
`.cache/` or `_site/`. To disable narration, remove the narration steps from both
`.github/workflows/pages.yml` and `.github/workflows/daily.yml`. Normal local site
builds and tests work without installing the speech model.

Model: [Kokoro-82M v1.0](https://huggingface.co/hexgrad/Kokoro-82M), Apache-2.0.
CPU engine: [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx), MIT.
Phonemization runs on the publishing machine using eSpeak NG; it is not bundled
in the website. This feature adds no third-party speech requests from readers.
