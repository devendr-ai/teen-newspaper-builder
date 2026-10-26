# Search pages

How News Pebbles gets found. Parents do not search for "kids newspaper."
They search for a grade, a printable, or news that is not scary. Each of
those searches needs its own page, written from a paper that has already
passed the usual checks.

Nothing outside this folder is part of that. The papers, the publisher, and
the live site are unchanged. These files are not on newspebbles.com yet.
Putting them there would mean changing the publisher, which this folder
does not do.

## What is here

- [`pages.yaml`](pages.yaml) is the fixed list. One page, one search phrase.
  An agent must not invent a new phrase on the day.
- [`build_pages.py`](build_pages.py) reads published issues and writes HTML
  only into [`site/`](site/). Run `python3 seo/build_pages.py` from the
  repo root after new issues exist.
- [`site/`](site/) is the built bundle: seven guide pages, one HTML page per
  lead story, `sitemap.xml`, and `robots.txt`.

The guide pages link to the story pages. They do not repeat the full story.
Each story page has the headline, the deck, the paragraphs, the sources, and
a link to the existing PDF on newspebbles.com.

Canonical URLs use `https://newspebbles.com/find/`. That path is the intended
public location of `site/`. It is not live.

## When it runs

After the morning publish, and only if that publish passed, re-run
`python3 seo/build_pages.py`. It will refresh the guide pages and add a
story page for each new lead. Commit the result under `seo/` only.

Do not rewrite the homepage. Do not post to Reddit or email anyone from
this job.

## What not to chase

Ranking for "news" or "kids app." Paying for a keyword tool. Changing the
title of the homepage every day. Putting the same story only inside a PDF.
Adding more URLs than `pages.yaml` lists.
