# Search pages

How News Pebbles gets found. Parents do not search for "kids newspaper."
They search for a grade, a printable, or news that is not scary. Each of
those searches needs its own page, written from a paper that has already
passed the usual checks. This folder is the list of those pages. It does
not publish them yet.

The homepage stays the age picker. It is not the page that should rank.

## The pages

[`pages.yaml`](pages.yaml) is the fixed list. One page, one search phrase.
An agent must not invent a new phrase on the day. It picks the page whose
edition just published, and fills that page from the issue. No new facts.

Story pages are the other half. A printed issue is a PDF, and Google barely
reads a PDF. Each lead story also lives as HTML at `/stories/<date>/<slug>`,
with the map or chart, the sources, and the talk-about-it line. Yesterday's
story stays up. That is what gets indexed.

## What each page must contain

- A title that is the search phrase, not the paper's name.
- A first sentence that repeats the phrase in plain words.
- One real story from a published issue, in HTML.
- The map or chart from that issue, if it has one.
- A link to that issue's PDF, and the age band.
- No "AI-generated" in the title or the first paragraph. That stays on
  How it's made.

## When it runs

After the morning publish, and only if that publish passed:

1. Read `pages.yaml`.
2. For each page whose `edition` published today, update that page from
   the new issue.
3. Add a story page for the lead.
4. Add both URLs to the sitemap.

Do not rewrite the homepage. Do not post to Reddit or email anyone from
this job. Those are separate, and a person sends them.

## What not to chase

Ranking for "news" or "kids app." Paying for a keyword tool. Changing the
title of the homepage every day. Putting the same story only inside a PDF.
