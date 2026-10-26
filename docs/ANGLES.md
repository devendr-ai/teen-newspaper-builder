# Angles: the same big story, a different paper

Many families read more than one paper. Before 27 October 2026 the papers often led with
the same story in nearly the same words: on 24 October three papers printed the same
lead word for word, and The Breakfast Table and The Junior Daily shared most of theirs.
News value still decides the lead (`docs/CRAFT_RULES.md`); what changes is the angle.

## 1. Each paper's lens (`lens:` in `editions/<id>/edition.yaml`)

One sentence, added to that paper's prompt. Change it in the YAML, then run
`python -m ygc prompt <id>`.

| Paper | Lens |
|---|---|
| The Little Explorer (6–8) | *none*: the only paper and poster for 6–8, kept as a mix of world news and discoveries |
| Junior Explorer (9) | How it works: the science, engineering or nature behind the story |
| The Breakfast Table (9–11) | What it means at home, and something to talk about together |
| The Junior Daily (9–11) | Where in the world and who is involved |
| Europe Explained (12–14) | How it reaches the UK and Europe |
| Global Citizen Plus (12–14) | Links to school subjects: history, geography, science |
| Lab Notebook (12–14) | The science and technology in the story |
| The Young Global Citizen (13) | What it means for families in the United States and India |
| The Current Affairs Digest (15–18) | The full picture, kept broad: names, numbers, dates and the systems behind them |

## 2. The day's plan (`data/plans/<date>.json`, `ygc/plan.py`)

Written by the nightly run after research, before any paper (`publish-today`, step 1c):

```json
{"date": "2026-10-27",
 "papers": {"breakfast-table": {"lead": "riyadh-airport", "angle": "What the reopening means for families who fly"},
            "europe-explained": {"lead": "oil-six-month-high", "angle": "Why traders price in risk before any oil is lost"}}}
```

`python -m ygc plan data/plans/<date>.json --pool data/pools/<date>.json` fails a plan that
misses a due paper, names a lead that isn't in the pool, or gives two papers with the same
lead the same angle. Each angle must rest on facts in the pool; the research step adds them
when an angle needs one. Because the plan is written each day from that day's pool, the
angles follow the day's top news, and a running story is told through what is new.

## 3. Checks in `ygc check`

- `--plan data/plans/<date>.json`: the lead must be the planned story (it cites one of
  that story's sources).
- **Copies** (issues dated 27 October 2026 on): a story fails if more than 35% of its
  four-word runs appear in another paper's story the same day, or if its headline is the
  same. The message names the other paper and this paper's lens.
- **Repeat leads** (a note, not an error): when the same big story (`threads`) has led
  a paper three issues running, lead with the new development through this paper's angle,
  or with another story if one is close in news value.

`ygc auto` (the API pipeline) gets the lenses through the prompts and the copy check
through `ygc check`; the plan is part of the Claude Code nightly run.

Tests: `tests/test_angles.py`.
