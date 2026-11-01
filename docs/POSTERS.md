# The Big Question poster — now the Weekend News Poster

A one-page, news-first companion to The Little Explorer for ages 6–8, including
second and third graders. Version 2 replaces the repetitive single-question
activity layout with **two news stories**, supporting visuals and a small comic.
Keep the newspaper character: the same `PAPER`, `INK` and burgundy `ACCENT` as
other editions, serif headlines and body text, fine rules, generous readable type.
No preschool mascots, colouring sheets or full-page comics.

```bash
python -m ygc new-poster little-explorers --date 2026-11-07
python -m ygc poster editions/little-explorers/posters/2026/2026-11-07.json --pool data/pools/2026-11-07.json
```

Every text box is measured. Inspect the rendered page before publishing. Existing
unversioned posters keep their historical layout and remain downloadable.

## Automatic posters

The existing daily Claude Code Routine runs `/publish-today`. **Keep the existing
Saturday schedule:** `automation.enabled: true`, `weekday: saturday`, `poster: true`
in `editions/little-explorers/edition.yaml`. Do not create a second scheduler.
The next regular poster after 31 October is Saturday **7 November 2026**.

After the Saturday issue passes, the Routine creates a version 2 skeleton, follows
this guide, checks with the same research pool, inspects the PNG and publishes.
The optional API pipeline uses this guide and the full checked issue as well;
it repairs validation errors and runs its independent fact-check. A failed
poster never blocks the paper. Publication rebuilds the existing dated PDF,
`latest-poster.pdf`, its homepage thumbnail and its archive download link.

## Two news stories

Choose **two distinct topics from the same dated issue**. Prefer one world or
current-affairs story and one science, nature or discovery story when suitable.
Never replace an important story with a cartoon simply because it is easier to
illustrate. Explain hard news calmly; never lead with frightening or graphic detail.

Each `stories[]` entry contains:

- `block`: the exact block ID in that issue; the two block IDs must differ.
- `kicker`, `headline`, `deck`: short newspaper headings, not baby talk.
- `body`: 2–3 short paragraphs, roughly 70–90 words total. Explain what happened,
  how it works and what is still unknown. Do not drop uncertainties.
- `evidence`: one exact excerpt from the issue body/deck per paragraph. Excerpts
  must support the adapted news text; inclusion alone does not prove a claim.
- `why`: one useful sentence explaining why the story matters.
- `sources`: URL strings copied from this story's issue sources and research pool.
- `visual`: use the evidence-linked visual schema below. Required on story 2.
- Optional `art`: reviewed local artwork only, with `file` under `assets/poster/`,
  its `sha256` and a short `caption`. Never invent a filename or hash. If no
  reviewed art is supplied, OMIT it: the first story still gets a real map.

Top-level `question` is a short descriptive title for the website card. Top-level
`sources` must be the union of the two stories' sources. Set `version: 2`.

## A visual that explains

The first story has `find_it`: `story_block`, `map` with 1–3 canonical `countries`,
`text`, and an exact issue `evidence` excerpt. Countries must be named in that
story. Natural Earth geometry supplies the real coastline and country shapes;
never paint or invent a map. Choose a first story with an identifiable country.

Story 2 has a `visual`: `type`, `title`, `caption`, `source_url` and the evidence
fields described by the standard issue visual schema (`ygc/visuals.py`).
Use `steps` for a sourced process, `positions` for different reported positions,
`bars` for comparable reported numbers, or `seats` for a majority threshold.
Evidence is copied exactly from the poster story's own body/deck. Its source URL
must occur in that story's sources. Never invent a number or causal sequence.
For `steps`, `items` is 2–4 objects with `label` (<=72 characters) and `evidence`.
Titles <=44 characters, captions <=220. The standard visual validator also runs.

Artwork is an explanation, not photographic proof. Caption it as an illustration;
never portray invented people, cave art, maps or machinery as documentary fact.
The current cave sample image is conceptual, not a depiction of the actual cave.

## A small supporting comic

`comic` has `story_block` and exactly three `panels`. Tara and Leo are fictional
school reporters; their reusable newsroom art is not a scene from the news.
Speakers are **Leo, Tara, Leo**, matching the reviewed artwork. Each panel has
`speaker`, `text` (<=95 characters) and an exact `evidence` excerpt from its selected
issue story. Dialogue must relate to that evidence. A question, a useful explanation
and a light response work well. Never invent quotes attributed to real people.
All dialogue is typeset, not baked into generated images. Keep it around the bottom
one-seventh of the page; the two news reports remain the priority.

## Historical posters

Unversioned/version 1 files use the old “One idea, not a digest” layout with hero
motifs (including `bottleneck`), steps and activities. Their renderer and checks
remain for archives only. Do not use that schema for new scheduled posters.

Use printable punctuation only, no emoji or arrows. Every news claim needs its
source, not a remembered fact. Before committing: check with `--pool`, inspect the
full-page PNG for readability, and confirm exactly one PDF page.
