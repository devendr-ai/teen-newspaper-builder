# The story so far

Some news goes on for days: a war, an election, a big storm. A child who missed last week
meets "the truce has collapsed" without knowing what truce. **The story so far** gives each
big ongoing story one page to catch up on, in Read & Play.

## What readers see

- **On the Read & Play front page:** "🧵 Big stories right now", at most three, newest first,
  with "NEW TODAY" when today's papers carry news on them. Each opens the page at the reader's
  level (the age chosen under "Who's reading?").
- **In a story:** one purple link under the headline, "New to this story? Read the story so
  far", only on stories that belong to a thread.
- **On the printed paper:** one line at the end of such a story, "New to this story? Catch up
  with The story so far on Read & Play."
- **The page itself** (`play/threads/<id>.html` for ages 6–11, `<id>-more.html` for 12+, with a
  switch between them): "In one minute", a map, "What happened" (the newest three lines, then
  "Show earlier days"), and folded sections for "Who's who", questions people ask, and "If this
  news worries you". Sources sit behind "For grown-ups". "Read it" on a timeline line opens the
  story that reported it.

A thread is **active** while it has news in the last 7 days. After that it rests on the
"All the big stories" page, so "what happened with...?" always has an answer.

## The file: `threads/<id>.json`

```json
{
  "id": "yemen-war",
  "title": "The war in Yemen",
  "opened": "2026-10-10",
  "where": {"place": "Yemen and Saudi Arabia", "lat": 18.5, "lon": 45.5, "countries": ["Yemen", "Saudi Arabia"]},
  "younger": {
    "one_minute": "Yemen is a country next to Saudi Arabia. ...",
    "who": [{"name": "The Houthis", "about": "A group that runs the north of Yemen."}],
    "questions": [{"q": "Why are they fighting?", "a": "..."}],
    "worry": "It's okay to feel worried when you read about war. ..."
  },
  "older": { "one_minute": "...", "who": [...], "questions": [...], "worry": "..." },
  "timeline": [
    {"date": "2014-01-01", "when": "2014", "younger": "...", "older": "..."},
    {"date": "2026-10-13", "reported": "2026-10-15", "younger": "...", "older": "..."}
  ],
  "stories": [{"paper": "junior-daily", "date": "2026-10-15", "block": "lead"}],
  "sources": ["https://..."]
}
```

- `younger` is for ages 6–11, `older` for 12 and up. Both are required.
- `timeline` runs oldest first. `date` is when it happened (`when` replaces it on the page,
  for "2014" or "February 2022"); `reported` is the date of the papers that reported it, so
  "Read it" opens the right story. `younger` may be left out of a line that's only for older
  readers.
- Stories join a thread through their issue's `"threads": {"<story id>": "<thread id>"}`
  (what the nightly run writes), or through the thread's own `stories` list (used for papers
  published before threads existed).
- `worry` is for wars and disasters; leave it out otherwise.

## Checks

`python -m ygc thread` checks every thread: both levels, 2 to 6 people in "who's who", short
answers and timeline lines (word limits in `ygc/threads.py`), dates in order and not in the
future, `reported` not before the event, and sources. `python -m ygc check` makes sure an
issue's `threads` names real stories and real threads.

## Every night

The `publish-today` skill keeps threads up to date after writing the papers: it links today's
stories, adds a timeline line for each new development (facts only from the research pool or
published papers), and opens a new thread only for a story that has run on at least 3 of the
last 7 days. A thread that can't pass its checks is left as it was; it never blocks a paper.
