# Read & Play: the children's side of the site

The newsstand is for grown-ups: choose a paper, download it, print it. **Read &
Play** (`/play/` on the site, built by `ygc/play.py` as part of `python -m ygc
site`) is for the child, on a tablet or phone, from the same issue files.

- **Who's reading?** The lobby asks the child's age (6–8, 9–11, 12–14, 15+) and
  shows that age's papers, each with **Read** and **Play**. The choice is
  remembered on the device.
- **Read.** Each of the last 7 issues of every paper becomes a page. For ages
  6–11 it shows one story per screen (swipe, or Next and Back); older readers
  scroll. Every story and section has **Read it to me**, which uses the device's
  own voice and lights up each sentence as it's read. New words from the issue
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
- **Play.** A menu of up to three games, each with stars kept on the device, no
  timer and no losing:
  - *Word match*: tap a word, then its meaning. Papers without new words get
    *Story match*: tap a headline, then the sentence that starts its story.
  - *Quiz*: one question per screen, three answers. A wrong answer shows the right
    one, why, and **Read it again**, which opens the story it came from. Ages 6–8
    can hear each question.
  - *Fact or fiction?*: a claim about the issue; tap **True** or **Not true**.

Nothing is tracked and nothing leaves the device.

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
  "where": [{"story": "lead", "place": "Pacific Ocean", "lat": 5, "lon": -160, "countries": ["Australia"]}]
}
```

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
