# Older-reader game replacements

Ages 12–14 and 15+ use Domino Effect in place of Word/Story match, and You Make
the Call in place of Fact or fiction when the relevant content is valid. Quiz,
Map hunt, Guess the number and chronological Put it in order remain. Ages 6–11
are unchanged. A mode missing from a particular issue retains its old game.

Future publishing fills `play.analyst` following the generated edition prompt.
The two modes can be null independently; do not invent content to fill slots.
Domino requires four supported causal steps, three arrow explanations and explicit
qualifications. Every step/arrow has a short exact evidence passage from the linked
story. The mechanical checker validates shape and quoted evidence; the writer and
fact-checker must also check whether the causal inference really follows. Matching
words alone cannot prove causation. The opinion mode links the lead and provides
balanced options, each with benefits/costs. Hypothetical proposals must be labelled.

`data/analyst/<edition>/<date>.json` holds curated online-only additions to existing
issues without altering archived issue JSON or PDFs. Five current older issues have
an opinion exercise; two have defensible risk-pricing chains. Other slots fall back
to existing games. The build validates these additions and produces a content-hashed
poll manifest. Changing a poll creates a different ID rather than combining answers
to different questions. No historical reporting is modified.

Domino supports drag/drop and keyboard/touch up/down controls, first-attempt scoring,
source-story links and explanations. Opinion completion has no correctness, stars,
accuracy entry or majority reward; it contributes to set completion locally. Sharing
is optional. Both trade-offs appear before any shared results, and no numbers are
invented. When the service is unavailable the local activity still works. The static
frontend uses the existing Cloudflare Worker for optional aggregate responses; see
subscribe-worker/README.md and the public privacy page for retention and gating.
