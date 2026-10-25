# The app build (Kids Category / Families)

`python -m ygc site --kids --out _kids` builds the same site for the News Pebbles app, ready for
Apple's Kids Category (Guideline 1.3) and Google Play's Families policy. The public website
(`python -m ygc site`) is unchanged by it.

| | Website | App build (`--kids`) |
|---|---|---|
| Fonts | served from the site (`fonts/`) | same |
| Design-your-own engine (Pyodide 0.27.7) | served from the site (`vendor/pyodide/`), loaded only by `builder.html` | same |
| Visit counting (GoatCounter) | on | off: no pixel, no 404 count, no Read & Play events |
| Feedback page | Google Form embedded | a button that opens the same form, plus email links |
| Parental Gate | none | on every page (below) |

## The Parental Gate (`assets/gate/`)

Before anything that leaves the app or is meant for grown-ups, a grown-up answers a sum written in
words: "What is sixteen multiplied by four?" or "What is twelve times three, plus five?". Three
wrong answers pause it for 30 seconds. One listener on each page covers:

- **links to other websites** (every news source, the licence, the builder's GitHub link) and
  **email** (`mailto:`), always, even on an unlocked parents' page;
- **share** ("Share this edition", `data-gate="always"`) and the builder's **AI helper** buttons;
- **print**: "Print this paper", the certificate's print button, Read & Play's "Print this paper
  (for grown-ups)";
- **parents' pages** (`kids.GATE_PAGES`: For parents, Feedback, Design your own, the monthly
  report), which stay hidden until the sum is answered.

The unlock is only in the open page's memory: leaving the page (or coming back to it from the
back button) asks again. The dialog is an accessible modal: labelled, keyboard-trapped, Escape and
"Go back" cancel, large targets, dark mode. Mark anything new with `data-gate` (and
`data-gate-reason="link|mail|share|print|page|grown"`), or call `npGate(reason, onPass)` from code.

## Checking a build

```sh
python -m ygc site --kids --out _kids
python -m http.server 8777 --directory _kids &
NODE_PATH=$(npm root -g) node tools/kids_check.cjs http://localhost:8777/ kids
```

`tools/kids_check.cjs` opens every page type in Chromium (phone size) and fails on any request to
another host; then it walks every gated action: wrong answers and the pause, a source link, email,
share, both "Print this paper" links, certificate printing, each parents' page (hidden, Go back,
unlock, asks again after leaving), the feedback form, and the builder (its engine loads from the
site, it makes a real PDF, "Open it", the AI helpers and GitHub). `web` instead of `kids` checks the
public site has no gate and no Google Fonts or CDN requests. `tests/test_kids_mode.py` runs both,
plus static checks of every page.

## Self-hosted files

- Fonts: `assets/fonts/web/` (WOFF2 and `fonts.css`), refreshed with `python tools/brand/fonts.py`.
- Pyodide: pinned in `assets/vendor/pyodide.json` (each file's SHA-256). `python -m ygc vendor`
  downloads and checks them into `.cache/vendor`; every site build copies them to `vendor/pyodide/`.
  The standalone `tools/newspaper-builder.html` still uses Google Fonts and the Pyodide CDN when
  opened on its own; the site build points it at the site's copies.
