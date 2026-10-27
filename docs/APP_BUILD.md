# The News Pebbles app (iPhone and iPad)

The app is the website's own pages, saved on the phone, plus what only an app can do. It starts on the
same home page; Listen takes Design's place in the tab bar. The code is in `mobile/` (Expo).

| What | How |
|---|---|
| **The pages** | The app build of the site (`--kids`, below), served nightly at `https://newspebbles.com/app/` |
| **Offline** | Each time the app opens it downloads `app/manifest.json` and fetches only the files that changed (`mobile/src/content.ts`). The last 7 days of papers and recordings stay on the phone |
| **Listen tab** (app only) | `play/listen.html`: the car-ride briefs and each paper read aloud. Replaces the Design tab; Design is in For parents and opens the website |
| **Audio with the screen locked** | The brief and the Listen tab play in the phone's own player (`mobile/src/player.ts`, expo-audio): lock screen, Control Center, car, next story |
| **Morning reminder** | For parents → This app: a daily notification the phone sets for itself (`mobile/src/reminder.ts`). No push server |
| **Print and share** | After the Parental Gate, the iPhone's print sheet (PDFs, the certificate) and share sheet |
| **iPad** | The same pages; they already lay out for tablets |

### How a page talks to the app (`assets/app/app.js`)

Every page of the app build loads `app.js` first. Inside the app (`window.ReactNativeWebView`) it adds
`window.NPApp` and sends JSON messages; the app answers by calling `window.__np(message)`.

| Page → app | Meaning |
|---|---|
| `{t:"page", url, bg, dark}` | a page opened (the app colours the status bar to match) |
| `{t:"audio", op:"list", id, title, tracks:[{src,title}]}` | play these tracks in the phone's player; also `play`, `pause`, `toggle`, `next`, `seek`, `rate` |
| `{t:"claim", id}` | this page shows its own player for `id` (`"*"` on Listen), so the app hides its mini-player |
| `{t:"print", url}` / `{t:"printHtml", html}` | print a PDF, or a page with its styles built in (the certificate) |
| `{t:"share", title, text, url}` | the share sheet |
| `{t:"settings?"}` / `{t:"reminder", on, time}` | For parents → This app |

| App → page | Meaning |
|---|---|
| `{t:"status", s}` | what's playing: `{id, title, track, index, count, playing, time, duration, ended}` |
| `{t:"settings", reminder, offline}` | fills in This app |
| `{t:"go", href}` | open a page (the mini-player opens Listen) |

The brief's player uses `NPApp.audio()`, which behaves like an `<audio>` element but plays in the phone.
In a browser `NPApp.native` is false: Listen plays its tracks itself and everything else is the website.
Links out, email and anything else that isn't a saved page open outside the app (Safari, Mail), after the gate.

### The offline pack (`ygc/apppack.py`)

Both deploys (`pages.yml`, `daily.yml`) run `tools/app_pack.sh` after the website's narration:

```sh
python -m ygc site --kids --keep 7 --out _app_build
python -u -m ygc.narration --site _app_build --latest-only    # recordings come from the cache
python -m ygc app-pack --site _app_build                     # trims it, writes manifest.json
```

`app-pack` leaves out what the app doesn't use (the Design engine and `builder.html`, link-preview
pictures, the podcast feed, `404.html`), points any link to `builder.html` at the website, and writes
`manifest.json`: `{"v": 1, "id", "built", "start": "index.html", "files": {path: [sha256 prefix, bytes]}}`.
The narration step also writes `play/listen.json` for the Listen tab (`ygc/listen.py`). If the pack
fails, the website still publishes and phones keep what they saved. About 20 MB of pages plus the
day's recordings.

### Try it, build it, ship it

On a Mac, from `mobile/`:

1. **Try it on your iPhone (free, no build):** `npm install`, then `npx expo start` and scan the QR code
   with the Expo Go app. It loads the live pack from newspebbles.com.
2. **TestFlight:** `npx eas-cli@latest build --platform ios --profile production`, then
   `npx eas-cli@latest submit --platform ios --latest`. The first build asks to sign in to the Apple
   Developer account and creates the certificates; EAS keeps them.
3. **The App Store:** everything to paste into App Store Connect is in `mobile/store/`.

Checks: `npm run typecheck`, `npm run lint`, and `npx expo export --platform ios` (bundles the app).
`tests/test_app.py` checks the website side, including `tests/app-bridge.cjs` in a real browser with a
stand-in for the app.

---

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
