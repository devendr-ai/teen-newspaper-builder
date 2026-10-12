# The Big Question poster

A one-page companion to a paper's issue, made for the youngest readers (ages 6–8).
Children this age don't read columns of news. They learn from a picture, something
to do with their hands, and a conversation with a grown-up. So the poster takes
**one** story from the week and turns it into **one idea** they can keep.

The website offers it as a second download next to the issue ("Download poster").

```bash
python -m ygc new-poster little-explorers --date 2026-10-10   # skeleton in editions/<id>/posters/<year>/
python -m ygc poster editions/little-explorers/posters/2026/2026-10-10.json   # check, build PDF + page image
```

`poster` prints PASS or a located error ("talk tip is OVER by 7 pt"), the same way
`check` does for issues. Look at the page image before publishing.

## The layout (same every week)

| Field | What it is | Size |
|---|---|---|
| `question` | The headline, asked the way a child would ask it | 2 lines at most |
| `skill` | The thinking skill this poster practises, shown as a badge | 1–3 words |
| `happened` | What happened, the gentle version | 3–4 short sentences |
| `hero` | The big picture: `motif` and a short `caption` | caption ≤ 60 characters |
| `steps` | "How it works": exactly 3 pictures, each with `title`, `motif`, `text` | title ≤ 22 characters, text 1 sentence |
| `home` | "It reaches your home": a `chain` of 2–5 one-word boxes, then `text` | 2–3 sentences |
| `find_it` | A map (`title`, `label_top`, `label_bottom`, optional `footnote`) and an instruction | 1–2 sentences |
| `try_it` | Something to do at home: `title` and 2–4 `steps` | 1 sentence per step |
| `talk` | 2 `questions` for the child and a `tip` for the grown-up | tip ≤ 2 sentences |
| `next_week` | A guess to make now and check in next week's poster | 1–2 sentences |
| `sources` | URLs every fact came from (shown on the paper's web page, not printed) | at least 1 |

Motifs: `bottleneck` (a wide sea squeezed through a narrow gap, with ships queuing)
plus every illustration motif the papers use: airdefense, ballot, border, capitol,
court, cricket, farm, fire, flood, globe, grid, hospital, podium, protest, robot,
rocket, ship, skyline, strait.

## Writing rules

### Rule: One idea, not a digest.
Pick the week's biggest story, then find the lasting idea underneath it: a
bottleneck, a food chain, why ice floats, what a vote is. The news is the hook;
the idea is what the child keeps.

### Rule: Never lead with war, death or danger.
Take the *why* behind a hard story, not the frightening part. A war that closes a
sea route becomes "why do ships squeeze through one gap?", not missiles. Say what
happened honestly and briefly ("because of fighting nearby"), then move to the idea.

### Rule: Start from the child's world.
Connect the story to something on their table, in their pocket or on their street:
milk, a phone, a slide at the park. The `home` chain should end in their home.

### Rule: The picture explains first.
Choose motifs that show the idea before a word is read. The three steps should be a
little story: before, the change, the result.

### Rule: Name the thinking skill, and keep it simple.
Rotate through a small set so children recognise them: ripple effect, cause and
effect, compare, predict and check, see-think-wonder, describe with "because".

### Rule: The grown-up is part of the design.
`talk.tip` tells the parent, in under 30 seconds, how to have the conversation:
ask open questions, don't correct, add one more step to what the child says.

### Rule: Every fact comes from a source.
The same rule as the papers: figures, names and places come from a source you read,
and the URLs go in `sources`. Evergreen science in `try_it` may use well-established
facts. Use plain words a 6-year-old knows, or explain the one new word you need.

### Rule: Close the loop next week.
`next_week` asks for a guess. Next week's poster can open by checking it
("Last week you guessed... here is what happened").

Use only characters the PDF fonts can print: plain English punctuation plus • — “ ” é ü.
No arrows (→), no `…`.
