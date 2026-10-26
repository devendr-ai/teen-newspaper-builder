# Craft rules

Rules for *how* to write, true for every edition whatever its reader, purpose
or coverage. Each `### Rule:` heading below is copied word for word into every
edition's generated prompt, so edit the heading to change what the AI is told,
and keep the reason underneath so nobody removes a rule they don't understand.

Edition-specific rules (what to cover, for whom) live in each
`editions/<id>/edition.yaml`.

### Rule: Every paragraph hands off to the next: each paragraph's first sentence connects to the previous paragraph's last.

*Set 2026-08-13.* A health story jumped between ideas without context and was
confusing to read. Test before shipping: if a paragraph could be deleted
without the reader noticing a gap, the transitions are doing no work.

### Rule: Never open on a noun the reader has not been given; set up a dispute before naming it.

*Set 2026-08-13.* Same failure as above, at sentence level.

### Rule: Explain the human context before leaning on it; never assume the reader supplies a missing premise.

*Set 2026-08-13.* Stigma, history and the reason people are angry must be on
the page, not assumed.

### Rule: Never make the reader do arithmetic; state results, after establishing what they compare.

*Set 2026-08-13.* "Removes 363 chances to forget" made the reader reverse-engineer
the subtraction. Write "a pill every day" versus "two injections a year" first.

### Rule: Attribute contested claims to whoever made them, and give the other side's answer in its own terms.

Disputed findings (genocide determinations, election-rigging accusations)
are reported as conclusions of named bodies, with the denial alongside.

### Rule: Keep quotes under 15 words and use them only when the exact wording matters.

Threats, promises and legal claims earn a quote; everything else is paraphrased.

### Rule: Every figure, name and date in a news story must come from a source you actually read, and every story lists its URLs in `sources`.

Evergreen sections (Did You Know, explainers) may use well-established facts. Sources are never printed. They let a parent or editor verify any figure in
thirty seconds, which is what makes the paper trustworthy for a young reader.

### Rule: Records and firsts ("the first since", "the largest ever", "a record") must be stated by a source you read; never work them out yourself.

*Set 2026-10-11.* An issue said a Nobel laureate was the first person since
1991 to win the physics prize alone; Georges Charpak won it alone in 1992.
Superlatives are the facts most often wrong and the ones readers repeat, so
if no source says it, describe what happened without the superlative.

### Rule: News value beats novelty: a running story that is still the biggest leads again, written as the new development.

*Set 2026-08-13.* A lead was once demoted only because it had run before.
Novelty breaks ties between stories of similar weight; it never demotes the
actual headline.

### Rule: Graphics are formatting requirements, not selection criteria: choose the story first, then fit the graphic.

A story must never be picked, or bent, to suit the map or the chart.

### Rule: Take today's date from the device clock, never from a prompt or an assumption.

*Set 2026-09-01.* A session's built-in date said August 25 while the real date
was September 1; an issue went out a week stale and misnumbered. `check`
enforces this in the edition's timezone.

### Rule: When a story runs in several papers on the same day, tell it through this paper's own angle and in its own words.

*Set 2026-10-26.* On 24 October three papers for different ages printed the same lead
word for word, and two papers for 9 to 11 shared most of theirs. Families with more than
one child read clones. The biggest story may still lead everywhere; what changes is the
angle (each paper's `lens`), and `ygc check` fails a story that repeats another paper's.
