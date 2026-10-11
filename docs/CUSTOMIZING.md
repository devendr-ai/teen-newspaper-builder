# Customizing a paper

Everything that makes one paper different from another lives in a single file,
`editions/<id>/edition.yaml`. You never edit Python to change a paper. After any
change:

```bash
python -m ygc editions             # validates every edition, with plain-English errors
python -m ygc prompt <id>          # regenerates the AI instructions from the YAML
python -m ygc check <issue.json>   # shows how the content now fits, column by column
```

The fastest start is the **newspaper builder**, `tools/newspaper-builder.html`.
Open it in any browser and choose:

| Choice | What it sets |
|---|---|
| Length (1–12 pages) | Number of stories, page plan, briefs and quiz size; 7+ pages add an analysis page |
| Reader (ages 6–8 to professional) | Reading level, voice, type size, vocabulary count, labels |
| Purpose | Purpose lines in the prompt and default sections (quiz, explainer, discussion…) |
| Countries and regions (any, including custom) | One desk per place |
| Topics | One desk per topic; topics that don't get their own story become angles and briefs |
| Depth | Which stories carry "why", "connect the dots" and "think like an analyst" |
| Sections | Turn vocabulary, quiz, explainer, sports and the rest on or off |
| How often | Cadence, news window, sign-off and watchlist wording |

It draws a proof of every page, estimates reading time, flags contradictions
(a professional brief for six-year-olds) and columns likely to overflow or look
sparse, and gives you the `edition.yaml`. Its generator lives in
`tools/builder/`; after editing it, run `python tools/builder/build.py`.

Or copy an existing edition:

```bash
python -m ygc create-edition my-paper --from young-global-citizen
```

Two editions ship as worked examples. They differ in almost every setting:

| | `young-global-citizen` | `junior-explorer` |
|---|---|---|
| Reader | 13, US-based, Indian origin | 9, US fourth-grader |
| Pages | 2 | 3 |
| Cadence | every 2 days, 48-hour window | weekly, 7-day window |
| Desks | top, world, India, US | big story, science, around the world |
| Type size | 1.0 | 1.3 |
| Graphics | map, illustration, chart | chart, illustrations |
| Extra sections | briefs, sports, vocab ×4 | briefs ×5, explorer challenge, how-it-works explainer |

---

## Change the reader's age or reading level

```yaml
reader:
  age: 16
  profile: A high-school junior in Toronto preparing for university.
  reading_level: Adult news, with jargon defined on first use.
style:
  type_scale: 0.95
```

`reader` and `voice` go straight into the AI prompt. `type_scale` resizes every
font, line and gap together: around 1.25–1.35 suits ages 8–10, 1.0 suits 12–15,
and 0.9–0.95 suits older teens and adults. Larger type holds fewer words, so run
`check` and trim or add pages as needed.

## Change the purpose and voice

```yaml
purpose:
  - Financial literacy: how money, prices and markets touch daily life.
  - Reading the news critically: who says so, and how do they know?
voice: >-
  Plain, direct and a little wry. Treat the reader as smart and busy.
```

Each purpose line becomes a bullet in the prompt's "every issue should build"
list. Be specific: these lines steer story choice and the angle of every "why
this matters".

## Change the countries and topics covered (desks)

A **desk** is a beat: a country, a region or a subject. Each story block is
assigned to a desk.

```yaml
desks:
  - id: uk
    label: UNITED KINGDOM
    scope: The most important UK story of the window, national rather than London-only.
  - id: tech
    label: SCIENCE & TECH
    scope: A discovery or technology story with real-world consequences.
    rules:
      - Prefer peer-reviewed findings over company announcements.
```

- `label` is the kicker prefix printed above the headline (`check` warns if a
  story's kicker doesn't start with it).
- `scope` tells the editor what belongs on the desk and the bar it must meet.
- `rules` are desk-specific instructions, copied into the prompt.

To drop India and cover Kenya instead, rename the desk and point the story
block at it. Nothing else changes.

## Add or remove sections (blocks)

Blocks are the pieces of an issue. Declare each one once, then place it on a page.

| Type | What it is | Options |
|---|---|---|
| `story` | A news story | `desk` (required), `size: lead \| standard \| compact`, `graphics: [map, illustration, chart]`, `extras: [why, connect, analyst]`, `also: {count, title}` |
| `feature` | A titled piece that isn't breaking news: explainer, activity, profile, column | `label`, `brief` (tells the AI what to write), `sources: false` for evergreen pieces |
| `briefs` | One-line news items | `count`, `title` |
| `vocab` | Vocabulary words with definitions | `count` |
| `did_you_know` | One surprising fact | |
| `sports` | One sports item | |
| `watchlist` | Things to watch before the next issue | `count`, `title` |
| `quote` | A closing line | |
| `sign_off` | The paper's goodbye line | `text` (required) |

`rule` is built in: put it in a column to draw a divider.

```yaml
blocks:
  money:
    type: feature
    label: MONEY MATTERS
    brief: Explain one price, wage or market figure from this window's news.
```

## Add pages or change columns

The page plan is a list of pages. Each page has 1–3 columns, and each column is
a list of block ids from top to bottom.

```yaml
pages:
  - masthead: true                       # page 1 only
    columns:
      - [lead]
      - [world]
  - banner: "<b>PAGE 2</b>  •  HOME FRONT"
    columns:
      - [uk]
      - [tech]
  - banner: "<b>PAGE 3</b>  •  YOUR TOOLKIT"
    columns:                             # three narrower columns
      - [briefs, vocab]
      - [money, did_you_know]
      - [watchlist, quote, sign_off]
```

Columns never flow into each other: each one is laid out on its own and
`check` reports its exact fit:

```
fit      p2 c1  OVER 19pt        uk
fit      p3 c2  6 lines free     money, did_you_know
```

An overflow is an error, with how much to cut. A column more than 4 lines short
gets a note. Graphics keep their height at every column width, so a
three-column page suits short blocks better than graphics-heavy stories.

## Change how often it comes out

```yaml
cadence:
  every_days: 7          # weekly
  window_hours: 168      # cover the last 7 days
  timezone: Europe/London
```

"Today" is always computed in this timezone, never from a prompt or a server
clock. Update `sign_off.text` and the watchlist title to match ("See you next
week", "COMING UP").

## Rename labels and tune the teaching rules

```yaml
labels:                  # any section heading can be renamed
  why: WHY IT MATTERS
  sports: GAME TIME
  vocab_title: New words this week
teaching:
  repeat_window: 4       # vocab and Did You Know can't repeat within 4 issues
  vocab_today: true      # each definition must show the word in this issue
  chart_label_limits: {2: 15, 3: 10, 4: 8}
sources_required: true
rules:                   # edition-wide editorial rules, copied into the prompt
  - Every number is compared with something the reader already knows.
```

Writing rules that apply to *every* paper (paragraph hand-offs, attribution,
sourcing) live in [CRAFT_RULES.md](CRAFT_RULES.md), not in editions.

## Limits worth knowing

- **Paper size** is US Letter.
- **Fonts** are the built-in Times and Helvetica, which use Windows-1252
  characters: no `₹`, no accented Eastern European letters, and no non-Latin
  scripts such as Devanagari, Chinese or Arabic. An edition in another script
  needs embedded fonts, which is a planned engine change, not a setting.
- **Map** is stylised: two land areas split by water. It suits straits, coasts
  and islands, not landlocked stories.
- **Illustrations** come from a fixed set of drawn motifs. Adding one means
  adding a drawing function in `ygc/graphics.py`.
