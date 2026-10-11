# Getting started: from GitHub to a printed paper

This is the whole journey for someone new, tested step by step on a clean
machine. It takes about 15 minutes, plus however long the news research takes.

You need **Python 3.10 or newer**. Two optional extras: **poppler** turns each
PDF page into an image you can check (`brew install poppler` on macOS,
`sudo apt install poppler-utils` on Ubuntu or Debian), and **Node.js** is only
used by the test suite.

> **Windows:** use `py` where this guide says `python3`, and activate the
> environment with `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

## 1. Get the code

```bash
git clone https://github.com/devendr-ai/teen-newspaper-builder.git
cd teen-newspaper-builder
```

## 2. Install, inside a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The virtual environment matters: on current macOS and Linux, installing into
the system Python fails with an "externally-managed-environment" error. Run
`source .venv/bin/activate` again whenever you open a new terminal.

## 3. Check it works

```bash
python -m ygc editions
```

```
junior-explorer              3 pages · age 9 · desks: top, science, world · every 7d
young-global-citizen         2 pages · age 13 · desks: top, world, india, us · every 2d
```

## 4. Build a sample paper

```bash
python -m ygc check editions/junior-explorer/issues/2026/2026-10-10.json --archive
```

It ends with `RESULT PASS` and writes the PDF and page images to `build/`.
Open `build/junior-explorer_2026-10-10.pdf` to see what the engine makes.
(`--archive` is for past issues: it skips the "is the date today?" check.)

## 5. Design your paper

Open `tools/newspaper-builder.html` in any browser (double-click it). Choose
the length, reader, purpose, countries, topics, depth, sections and frequency,
and give the paper a name. Read the proof on the right:

- **Yellow** warnings mean a trade-off you should decide on, such as a region
  that won't get its own story, or a column that will overflow or look empty.
- **Grey** notes are for information only.

When you're happy, select **Copy edition file**.

## 6. Save the edition file

Paste it into `editions/<your-paper-id>/edition.yaml`. The builder shows the
exact path. For example:

```bash
mkdir -p editions/the-morning-compass
# paste into editions/the-morning-compass/edition.yaml
python -m ygc editions
```

Your paper now appears in the list. If the file has a mistake, this command
names the line and says what's wrong.

## 7. Generate the AI editor's instructions

```bash
python -m ygc prompt the-morning-compass
```

This writes `editions/the-morning-compass/PROMPT.md`: who the paper is for,
what each section must contain, the writing rules, and the exact JSON shape
to return. Re-run it whenever you change `edition.yaml`.

## 8. Start today's issue

```bash
python -m ygc new the-morning-compass
```

```
created editions/the-morning-compass/issues/2026/2026-10-10.json  (No. 1, the first in the archive)
next: give editions/the-morning-compass/PROMPT.md to an AI tool with web search, save the JSON it
      returns over this file, then run: python -m ygc check editions/the-morning-compass/issues/2026/2026-10-10.json
```

The date comes from your clock in the paper's timezone, and the number from
the previous issue. Running `check` now lists every field still to fill.
That's expected.

## 9. Write the issue

Paste `PROMPT.md` into an AI tool that can search the web (Claude, ChatGPT,
Gemini and so on) and ask for today's issue. Save the JSON it returns over the
file from step 8. You can also write or edit the file by hand. Every story
lists its sources, either as URLs or as `{"outlet", "title", "url"}`.

## 10. Check it, and fix what it finds

```bash
python -m ygc check editions/the-morning-compass/issues/2026/2026-10-10.json
```

```
  fit      p1 c1  14 lines free    lead
  fit      p1 c2  15 lines free    world, briefs, watchlist, sign_off
  note     page 1 column 1 (lead) ends 14 lines short; add a sentence or rebalance
  RESULT   PASS
```

Expect two or three rounds. **Errors** must be fixed: a column that's over
(it says by how much), a missing section, a chart label that will collide,
an unprintable character, a missing source. **Notes** are advice: above, the
copy was correct but too short, so add real reporting until each column is
within a few lines of full. Never fix anything by editing the engine.

## 11. Look at it

Open `build/<paper>_<date>_page-1.png` (and the other pages). The checks can't
judge whether a headline lands or a chart tells the right story. Your eyes can.

## 12. Print it, and keep it

Print `build/<paper>_<date>.pdf`, then commit the issue file:

```bash
git add editions/the-morning-compass
git commit -m "The Morning Compass No. 1"
git push
```

Only commit an issue once `check` prints `PASS`. CI checks every issue in the
archive, so committing a half-finished one turns the build red until it's
done. The archive is what makes the next issue's numbering and no-repeat
checks work.
On GitHub, CI re-checks every issue on each push and keeps the PDFs as a
downloadable artifact.

## The next issue

Only steps 8–12, every time:

```bash
python -m ygc new the-morning-compass
# AI writes the issue → save over the new file
python -m ygc check editions/the-morning-compass/issues/<year>/<date>.json
```
