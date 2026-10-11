# Producing an issue

The same routine for every edition. `<id>` is the edition, e.g. `young-global-citizen`.

## 1. Start from a skeleton

```bash
python -m ygc new <id>
```

This takes today's date from the device clock in the edition's timezone,
numbers the issue (previous issue + 1, read from the archive), and writes an
empty, correctly shaped file at `editions/<id>/issues/<year>/<date>.json`.

## 2. Read the last issues

Open the most recent issues in the archive and note their vocabulary words and
Did You Know facts: those can't repeat within the edition's `repeat_window`.
(`check` enforces it; knowing up front saves a rewrite.)

## 3. Gather the news

Search across every desk in `edition.yaml` for the cadence window. For each
chosen story, read the primary articles, not just search snippets. Collect
exact figures, short quotes, dates and places, and keep every URL.

## 4. Choose the stories

One per story block, chosen on news value against its desk's `scope` and
`rules`. Then confirm each graphic the block requires has real material: water
geography for a map, real numbers for a chart.

## 5. Write

Fill the skeleton. Put each story's URLs in its `sources`. Write to the space,
not to a character count: step 6 tells you exactly where you stand.

## 6. Check

```bash
python -m ygc check editions/<id>/issues/<year>/<date>.json
```

```
fit      p1 c1  2 lines free     lead
fit      p2 c2  OVER 19pt        us, rule, sports, watchlist, quote, sign_off
ERROR    page 2 column 2 (...) is OVER by 19 pt — cut about 1.7 lines (~116 characters)
```

`check` validates the content against the edition (required sections, counts,
graphics limits, printable characters, date, numbering, repeats, sources), lays
out every column, builds the PDF and renders each page to PNG in `build/`.
Fix every `ERROR` in the content. Never fix it by editing the engine.

## 7. Look at every page

Open the PNGs. Checks cannot judge whether a headline lands, a chart tells the
right story, or the page feels balanced. Rebalance and re-run step 6.

## 8. Ship

Print the PDF and commit the issue JSON. CI re-checks every archived issue on
each push.

## Using an AI editor

Give it `editions/<id>/PROMPT.md`. It is generated from the edition, so it
always describes the current desks, sections, counts and rules. If the tool can
run code, give it this repository and require `check` to print `PASS`.
