---
name: publish-today
description: Publish today's due newspapers, plus The Little Explorer's Big Question poster on its day, to the News Pebbles website without the API. Research each desk once with web search, write and check every due paper, write and check the poster, then publish. Use when asked to "publish today's papers", or when the daily Routine runs.
---

# Publish today's papers

You are the whole newsroom for one day: research desk, writers, checkers and
publisher. Papers for children are printed and handed to them, so accuracy
comes before everything, including finishing. **A paper that cannot pass its
checks is skipped, never forced.** Skipping a paper is a normal outcome;
publishing a wrong one is not.

The date is the **India date** (the Routine runs at about 02:00 IST). Every
command below runs with `YGC_TZ=Asia/Kolkata`, which overrides the timezone
in each paper's prompt ("take today's date from the device clock in ...").

## 0. Set up

```bash
export YGC_TZ=Asia/Kolkata
D=$(TZ=Asia/Kolkata date +%F)
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY -c "import reportlab, pypdf, yaml, pytest" 2>/dev/null || $PY -m pip install -q -r requirements.txt pytest
git fetch origin main && git checkout -B <your designated branch> origin/main
$PY -m ygc due
```

`ygc due` lists every paper due today (by each paper's cadence), its issue
number and file, whether it gets a poster, and the research desks needed.
`$PY -m ygc due --json` adds the vocabulary words, Did You Know facts and
previous headlines each paper must not repeat. **If nothing is due, stop:
say so and publish nothing.**

## 1. Research, once per desk

For each desk in `research_desks` (`ygc due --json`), search the web
(WebSearch, several queries per desk) for the most important stories in its
window (`hours` up to today), covering its `scopes`. Then save everything to
`data/pools/$D.json` in this shape (the same file the API pipeline writes):

```json
{
  "world": {
    "label": "WORLD", "hours": 24, "dropped_unverified": 0,
    "stories": [{
      "id": "short-slug", "headline": "plain factual headline",
      "what_happened": "2-3 sentences", "why_it_matters": "1-2 sentences",
      "importance": 9, "suitable_for_children": true,
      "key_facts": [{"fact": "...", "source_url": "https://..."}],
      "numbers": [{"label": "...", "value": 0, "unit": "...", "source_url": "https://..."}],
      "geography": "places involved, and any coast, strait, river or island that matters",
      "sources": [{"outlet": "...", "title": "...", "url": "https://...", "published": "YYYY-MM-DD"}]
    }]
  }
}
```

Rules for the pool (these are what make the papers trustworthy):
- **Only URLs your searches actually returned.** Never type a URL from
  memory, never guess one, never "fix" one. A fact goes in only if a page
  you saw supports it. A story with no such source is left out.
- Never rely on memory for any fact, figure, name or date, however sure you are.
  Records and "firsts" must be stated by a source, never worked out.
- Prefer original reporting and official sources; note each source's date and
  stay inside the window.
- Mark `"suitable_for_children": false` when the core facts are too graphic
  for ages 6–14. Those stories are never used in papers for under-15s.
- Use the desk keys exactly as `research_desks` gives them (`world`, `india`,
  `science & tech`, ...). Five stories per desk is plenty.
- **Search results count as sources.** WebSearch returns each page's URL with
  text taken from that page. A fact stated in that text may go in the pool,
  cited to that URL. Opening the full page (WebFetch) is better when it works,
  but in the cloud it often fails (DNS errors). That is normal and is **not**
  a reason to skip a paper or the day. What stays out: a fact that no search
  result's text actually states.
- When sources disagree, use the most recent and most official source, or leave
  the detail out. Don't drop the whole story.
- **Running stories count.** A big story that was in an earlier issue can lead
  again when there's a genuinely new development (the paper's PROMPT.md allows
  it). Check the `previous_headlines` and write the new part.
- Skip a paper only after really trying to write it. Never skip the whole day
  before you've written and checked each due paper.

## 2. Write and check each due paper

For each paper in `ygc due`, one at a time:

1. `$PY -m ygc new <id> --date $D` creates the skeleton with the right number.
2. Read `editions/<id>/PROMPT.md` (that paper's full instructions: reader,
   voice, sections, graphics, JSON shape) and `docs/CRAFT_RULES.md`. Follow
   them, with these overrides: the date is `$D`; **use only facts in the
   research pool**; each block's `sources` are `{"outlet","title","url"}`
   copied from the pool; respect the avoid lists from `ygc due --json`.
3. Write the JSON over the skeleton, then check it against the pool:
   ```bash
   $PY -m ygc check editions/<id>/issues/<year>/$D.json --pool data/pools/$D.json
   ```
   Fix every ERROR in the content (never edit the engine, the edition or the
   tests to get a pass). The `play` section is part of the paper: the games,
   `where` for the maps, `numbers` for Guess the number (2 numbers the stories
   give, with a slider range around each) and, for papers for 12 and up, `easy`
   (an easier version of each story, using only that story's facts). Fill columns that show free lines. Open the page PNGs
   in `build/` and look at them.
4. Fact-check before calling it done: reread every figure, name, place, date
   and claim against the pool entry it came from, and remove anything the
   pool doesn't support.
5. After about 5 failed attempts, give up on that paper: delete its JSON and
   move on. Commit each paper as soon as it passes
   (`git add editions/<id> && git commit -m "<Paper name>, $D"`).

## 2b. The story so far (after the papers)

Big ongoing stories each have a thread in `threads/<id>.json`: one page a child can
read to catch up, written for younger (6–11) and older (12+) readers. See
`docs/STORY_SO_FAR.md` for the full shape. `$PY -m ygc thread` checks them all.

1. **Link today's stories.** For each story you published today that continues an
   existing thread, add `"threads": {"<story id>": "<thread id>"}` to that issue and
   run `ygc check` on it again: the printed story gains a one-line pointer, so trim
   if a column is now over.
2. **Add today's news to each thread with news.** Append one timeline line per new
   development: `date` (when it happened), `reported` (`$D`), and one short
   sentence each in `younger` and `older`. Update `one_minute`, `who` and
   `questions` only if the picture changed, and add the new source URLs (from the
   pool) to `sources`. Same rules as the papers: only facts in the pool or in
   papers already published, nothing graphic, gentle wording for younger readers.
3. **Open a new thread** only for a story that has run in the papers on at least 3
   of the last 7 days (check `previous_headlines` in `ygc due --json`) and has no
   thread yet. Write both levels, a `where`, a short timeline from the published
   stories, and a `worry` note for wars and disasters; then link today's stories.
   At most three threads should be active; don't open one for a single event.
4. `$PY -m ygc thread` must pass. Commit threads with the papers. If a thread can't
   pass, leave it unchanged (and remove today's `threads` links to it): a thread
   never blocks a paper.

## 3. The poster (papers with `+ poster`, after their issue passes)

```bash
$PY -m ygc new-poster <id> --date $D
# fill it in following docs/POSTERS.md, from the same research pool
$PY -m ygc poster editions/<id>/posters/<year>/$D.json --pool data/pools/$D.json
```

Every rule in `docs/POSTERS.md` applies: one idea, never lead with war or
danger, start from the child's world, `sources` are URL strings from the pool.
If last week's poster asked for a guess (`next_week`) and the research answers
it, open `happened` by checking it. Look at the page PNG. If it can't pass
after about 5 attempts, delete the file: **a failed poster never blocks
the paper.**

## 4. Publish

Only issues and posters that passed are left in the working tree.

1. Write `data/runs/$D.json`:
   `{"date": "$D", "by": "claude-code", "editions": {"<id>": {"status": "passed" | "failed" | "skipped", "reason": "...", "poster": "passed" | "failed" | null}}}`.
2. Run the full test suite: `$PY -m pytest -q`. It checks every archived
   issue and poster again. If it fails because of a file you added today
   (the failure names today's paper, poster or thread, or `ygc check` fails
   on it), fix or remove that file; never change tests or code to make it
   pass. If a test fails for a reason that isn't today's content (it
   expects an older date or file, or fails the same way with today's files
   left out), keep the papers that passed `ygc check`: publish them, and put
   the failing test's name and message in the pull request so the owner can
   fix the test. A passing paper is never dropped for someone else's test.
3. Commit (`Papers for $D`), push your branch, open a pull request to `main`
   titled `Papers for $D` with one line per paper (passed / skipped and why),
   then **merge it straight away** with the GitHub tools: the owner has asked
   for papers to publish without review. Pass the full 40-character head SHA
   (`git rev-parse HEAD`) as `expectedHeadSha`.
4. Merging to `main` starts the "Deploy the website" workflow
   (`.github/workflows/pages.yml`). Check that it started, and that it
   succeeded if it finishes while you're still running.

If you get close to your usage limit, stop starting new papers and publish
what has passed so far: a partial day is fine; a lost day is worse.

## 5. Report

End with a short summary: papers published (with issue numbers), papers and
posters skipped and why, the PR link, and the website:
https://devendr-ai.github.io/teen-newspaper-builder/

## Never

- Never change an issue or poster from an earlier date.
- Never edit `ygc/`, `editions/*/edition.yaml`, `tests/`, workflows or docs
  during a publishing run. A problem there is reported in the summary, not fixed.
- Never publish a paper or poster that hasn't passed `check`/`poster` with `--pool`.
- Never publish the owner's email address or personal details.
