# Changelog

## Unreleased — 2026-10-11: a site for children and their parents

- Catalog narrowed to readers aged 6 to 15 and up: nine papers. The adult and
  professional papers (The Bridge, The Global Ledger, Asia Watch, The Morning
  Signal) and two 15–18 papers (The World Brief, Planet Weekly) are removed;
  The Current Affairs Digest stays as the one larger paper for ages 15+.
- Website: "The Kids' Newsstand", a parents' introduction (`intro_title`,
  `intro` and `steps` in `site.yaml`), a parent-facing "How it's made" page,
  and age bands 6–8, 9–11, 12–14 and 15+. Fixed the filters, which never hid
  any card.
- Builder: adult and professional readers and the professional purpose
  removed; at most four pages from the tiles; family papers that are not daily
  no longer get the "The day's news" tagline by default.
- "Big Question" posters (`ygc/poster.py`, `docs/POSTERS.md`): a one-page
  companion for ages 6–8 that turns one story into one idea, with a big drawing,
  three how-it-works pictures, a chain to the child's home, a map, a hands-on
  activity, questions for the grown-up and a guess to check next week. Checked
  like issues (every box measured), built by `python -m ygc poster`, and offered
  on the website as its own card, with a thumbnail and "Download poster". First poster: The Little Explorer,
  10 October ("Why do so many big ships squeeze through one tiny gap?").
- New craft rule: records and "firsts" must be stated by a source.
- Weekly papers pinned to a weekday no longer skip a week after an off-day issue.

## 5.0.0 — 2026-10-10: automatic publishing and the website

- `python -m ygc auto`: research each desk once (Claude with web search, facts
  kept only if their cited page was actually retrieved), write every due
  edition from that research, check, repair (up to 4 rounds), fact-check,
  save. Daily budget cap, cost tracking, run reports and research pools in
  `data/`.
- `python -m ygc site`: static website with filters (reader, length, focus,
  frequency), cover images, a stable latest-PDF link per paper, archives with
  sources shown, RSS per paper, "How it's made", and the builder.
- Workflows: `daily.yml` (scheduled publish and deploy, optional review mode)
  and `pages.yml` (redeploy on changes).
- Catalog of 15 editions, from ages 6–8 to professionals, 1 to 6 pages,
  daily to weekly; all generated with the builder and free of layout warnings.
- Builder: names used as typed, honest mastheads, and sections move between
  columns when large type needs it.
- `docs/PUBLISHING.md`: ten-step setup.

## 4.2.0 — 2026-10-10: tested first-run experience

Found by walking a new user from a fresh clone to a printed paper:
- `docs/GETTING_STARTED.md`: the twelve steps, with real output.
- README install uses a virtual environment (plain `pip install` fails on
  current macOS and Linux).
- `check` never shows a Python traceback: unfilled skeleton fields, placeholder
  chart numbers and motif lists are named as errors, and the PDF waits until
  they're filled.
- `new` says what to do next; "1 page" instead of "1 pages".
- Generated prompts only mention the no-repeat rule for sections the edition
  has, and say exactly what the AI must return.
- Sources may be URLs or `{"outlet", "title", "url"}` objects.
- `migrate` keeps extra top-level keys such as `editorial_note`.

## 4.1.0 — 2026-10-10: newspaper builder

- `tools/newspaper-builder.html`: choose length, reader, purpose, countries,
  topics, depth, sections and cadence; get a page-by-page proof and a valid
  `edition.yaml`. Six presets, including one that reproduces the Young Global
  Citizen edition as a drop-in.
- Fill estimates calibrated against measured issues: stories are elastic,
  modules are fixed; stories sharing a column with modules carry no graphic.
- Tests run the builder's generator on every preset and 150 random
  configurations and validate each result with the engine.

## 4.0.0 — 2026-10-10: configurable editions

- New engine (`ygc/`) driven by `editions/<id>/edition.yaml`: reader age and
  profile, purpose, voice, desks (countries and topics), sections, page count,
  1–3 columns per page, type scale, cadence, timezone and labels.
- Exact per-column fit measurement replaces character budgets and page-3
  diagnosis.
- AI prompts generated per edition from YAML plus `docs/CRAFT_RULES.md`; tests
  fail if a prompt is stale.
- `python -m ygc` commands: editions, new, check, build, prompt,
  create-edition, migrate.
- Second edition, *The Junior Explorer* (age 9, 3 pages, weekly), as a worked
  example of how far an edition can differ.
- *The Young Global Citizen Daily* renders pixel-identical to template v3.
- Removed `_template.py` and the replication pack; issue files moved to
  `editions/young-global-citizen/` in the new format.
- Stories carry unprinted `sources`; printable-character rule corrected to
  Windows-1252.

## 2026-09-01 — every-two-days cadence

- Publish every two days, covering the last 48 hours; date taken from the
  device, never the prompt.

## 2026-08-13 — writing and selection rules

- Paragraph hand-offs; news value beats novelty; US story held to the lead's bar.

## 2026-08-12 — template v3: two columns
