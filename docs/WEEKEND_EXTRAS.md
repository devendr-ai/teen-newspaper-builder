# Little Explorer weekend printing

The public site offers **News only** (the default, two pages) or **News + Puzzles**
(three pages) for a Saturday/Sunday Little Explorer issue with a reviewed supplement.
Parents choose on the home recommendation/catalogue, dated print page or edition
archive. The choice is remembered locally on that device. The original news PDF,
RSS, emailed attachments and Read & Play are unchanged.

`site.yaml` → `weekend_puzzles.enabled: false` removes the controls and extra PDFs.
No other edition is eligible. No new service, paid API or browser dependency is used.

## Preparing the next weekend

1. Finish and fact-check the issue first. Choose an approachable story with a
   clear visual explanation. Create one landscape image containing six short,
   sequential comic panels, with **the story and captions inside the image**.
   Use the first supplement as a style reference: rounded cartoon rover, pale
   colours, limited ink, newspaper feel. Label it an illustrated explanation,
   never a photograph. Do not invent quotes, people, numbers, maps or scenes
   presented as eyewitness reporting. Review the final image and its text.
2. Add `editions/little-explorers/weekend/YYYY-MM-DD.json` and its local image
   under `weekend/assets/`. Use the first JSON as the schema example. Record the
   exact issue date, story block/headline, source URL, six captions and exact
   supporting quotations from that story, plus the reviewed image's SHA-256.
   Three distinct 3–6 letter story words populate the easy, left-to-right word
   hunt. The **first** word is the jumble answer; write its short definition in
   `jumble_hint`. Add short `drawing_prompt` and `discussion` text. Check these
   instructions fit and make sense for ages 6–8. The source must appear in that
   issue's story sources; image paths must remain within the weekend folder.
3. Run `python -m pytest tests/test_weekend.py -q`, then build the site and
   visually inspect **all three pages** of the combined PDF at print size.
   Verify the comic matches the source, the puzzles are solvable, labels fit,
   and the regular PDF is still two pages. Publish through the normal workflow.

The build automatically appends the reviewed page to that date's news PDF and
creates `YYYY-MM-DD-puzzles.pdf`. `latest-puzzles.pdf` exists only if the **latest
news issue itself** has a matching supplement. Regular `latest.pdf` remains news
only. The two news pages keep their original numbering; the third is explicitly
labelled **Weekend extra**, like a newspaper supplement.

Missing, invalid or unreviewed artwork falls back to news only and is logged.
CI validates all committed supplement specs. Never reuse an older comic with a
new issue. Art creation is an editorial step; this release does **not** claim to
automatically generate and fact-check future artwork. Scheduling and ordinary
news publication continue independently when a supplement is unavailable.

## Browser check

With the site served locally, run `node tools/weekend_check.cjs http://localhost:8000`
(with Playwright available and `CHROME` pointing to Chrome if needed). It checks
phone/tablet/desktop, saved choice, synced controls and correct PDF links.
