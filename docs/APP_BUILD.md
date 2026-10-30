# The News Pebbles app (iPhone, iPad and Android)

The app is the website's own pages, saved on the phone, plus what only an app can do. It starts on the
same home page; Listen takes Design's place in the tab bar. The code is in `mobile/` (Expo).

| What | How |
|---|---|
| **The pages** | The app build of the site (`--kids`, below), served nightly at `https://newspebbles.com/app/` |
| **Offline** | Each time the app opens it downloads `app/manifest.json` and fetches only the files that changed (`mobile/src/content.ts`). The last 7 days of papers and recordings stay on the phone |
| **Listen tab** (app only) | `play/listen.html`: the car-ride briefs and each paper read aloud. Replaces the Design tab; Design is in For parents, inside the app (one grown-up question when opening Design) |
| **Design your own** | Works offline in the app: its engine is in the pack. The finished PDF opens the share sheet (print, Files, send) |
| **Audio with the screen locked** | The brief and the Listen tab play in the phone's own player (`mobile/src/player.ts`, expo-audio): lock screen, Control Center, car, next story |
| **Morning reminder** | For parents → This app: a daily notification the phone sets for itself (`mobile/src/reminder.ts`). No push server |
| **Print and share** | After the Parental Gate, the iPhone's print sheet (PDFs, the certificate) and share sheet |
| **iPad** | The same pages; they already lay out for tablets |
| **Android** | The same app. Differences: the back button and gesture go back a page (`BackHandler`); a paper's PDF opens in the phone's PDF viewer, since Android's WebView can't show PDFs (`openPdf`); the Design PDF goes to the share sheet through expo-sharing; the reminder has its own notification channel; a strip under the tab bar keeps it clear of the system navigation bar |

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

### Email signup and optional reader responses

The saved pages have a `file:` origin. They must not POST directly to the Worker from the WebView:
the Worker's browser CORS allowlist deliberately excludes `null`. In the installed app,
`NPApp.parentPost(url, payload)` uses the existing grown-up authorization **before posting any message**,
then `mobile/src/parent-api.ts` sends the request using native networking. The reply returns to the
same form/game. Cancelling or a missing gate sends nothing; offline failures leave a retryable error.
Ordinary website and browser kids builds keep their existing fetch and gate paths.

For parents opens without an entry check. Signup asks once, on submission, with no additional inline
sum. Reminder changes and resetting reading data ask at the action too. Design, Feedback and the
monthly report retain their page-entry checks. `npGate.parent()` reads the gate's private page-unlock
state on those gated pages; it does not trust a CSS class or persist a device-wide unlock. External
links and sharing to other apps retain their separate always-ask checks. Public website forms retain
their inline sum.

The native handler permits only `/api/subscribe` from local parents/archive pages and
`/api/polls/vote` from local dated reader pages. It validates the source directory, exact service URL,
payload fields and size; there is no arbitrary URL/header/method proxy and no secret in the app.
The native request identifies the first-party site with `Origin: https://newspebbles.com`;
this header is CORS compatibility, **not authentication**. Server validation, rate limits and email
double opt-in still apply. Changing the service URL in site.yaml also requires updating the native
allowlist. Worker CORS and deployed backend settings are unchanged.

Reload the updated Expo project (or install a new native build) as well as refreshing the content
pack: older shells do not implement this message and fail closed after a timeout. A content-only
update cannot add native handlers. Run `npm run test:parent-api` in `mobile/` for the handler's
network/source/payload checks; browser bridge tests cover approval and cancellation without real sends.

### The offline pack (`ygc/apppack.py`)

Both deploys (`pages.yml`, `daily.yml`) run `tools/app_pack.sh` after the website's narration:

```sh
python -m ygc site --kids --keep 7 --out _app_build
python -u -m ygc.narration --site _app_build --latest-only    # recordings come from the cache
python -m ygc app-pack --site _app_build                     # trims it, writes manifest.json
```

`app-pack` leaves out what the app doesn't use (link-preview pictures, the podcast feed, `404.html`)
and the recordings of older issues: it keeps each paper's newest issue and everything on the Listen
tab, and older issues read aloud with the phone's own voice. It writes
`manifest.json`: `{"v": 1, "id", "built", "start": "index.html", "files": {path: [sha256 prefix, bytes]}}`.
The narration step also writes `play/listen.json` for the Listen tab (`ygc/listen.py`). If the pack
fails, the website still publishes and phones keep what they saved. About 80 MB on the first open
(about half of it recordings, 16 MB the Design engine), then only what changed each day.

### Try it, build it, ship it

On a Mac, from `mobile/`:

1. **Try it on your iPhone (free, no build):** `npm install`, then `npm start` (`expo start --go`) and scan
   the QR code with the Expo Go app. It loads the live pack from newspebbles.com. Plain `npx expo start`
   serves a development build instead, because `expo-dev-client` is installed (for the widgets): Expo Go
   can't open that. Widgets need a development build: `npx eas-cli@latest build --profile development`,
   then `npm run start:dev`.
2. **TestFlight:** `npx eas-cli@latest build --platform ios --profile production`, then
   `npx eas-cli@latest submit --platform ios --latest`. The first build asks to sign in to the Apple
   Developer account and creates the certificates; EAS keeps them.
3. **The App Store:** everything to paste into App Store Connect is in `mobile/store/listing.md`.
4. **Android:** try it with Expo Go on an Android phone (same QR code), or
   `npx eas-cli@latest build --platform android --profile preview` for an `.apk` to install. For Google
   Play, `--profile production` makes the `.aab`; the listing, Data safety answers and the closed-testing
   steps are in `mobile/store/play-listing.md`, the images in `mobile/store/play/`.

Checks: `npm run typecheck`, `npm run lint`, and `npx expo export --platform ios` / `--platform android`
(bundles the app).
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
- **parents' pages** (`kids.GATE_PAGES`: Feedback, Design your own, the monthly
  report), which stay hidden until the sum is answered.

The unlock is only in the open page's memory: leaving the page (or coming back to it from the
back button) asks again. One exception: a link from an unlocked parents' page straight to another
(`data-gate-pages` on every page's `<html>`; Feedback → Design your own) doesn't ask twice. The dialog is an accessible modal: labelled, keyboard-trapped, Escape and
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
