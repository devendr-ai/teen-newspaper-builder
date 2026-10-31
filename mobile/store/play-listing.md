# Google Play listing and submission pack

Everything to enter in Google Play Console, in the order you'll meet it. The images are in
[play/](play/), made from the live app pack with
`NODE_PATH=$(npm root -g) node tools/app_screenshots.cjs https://newspebbles.com/app/ mobile/store/play play`
(phone 1080 × 1920, 7" tablet 1200 × 1920, 10" tablet 1600 × 2560, the 1024 × 500 feature graphic and the
512 × 512 icon). Privacy answers follow [app-privacy.md](app-privacy.md), translated to Play's Data safety form below.

One developer account can hold several apps; each has its own listing, tracks, review and signing key.

---

## 1. Create app (Play Console → Create app)

| Field | Value |
| --- | --- |
| App name (30 max) | `News Pebbles: News for Kids` |
| Default language | English (United States) – en-US |
| App or game | App |
| Free or paid | Free (this can't be changed to paid later) |
| Declarations | Tick the Developer Program Policies and US export laws boxes |

## 2. Main store listing (Grow users → Store presence → Main store listing)

**Short description (80 max):**

```
Daily newspapers for ages 6–18: read, play and listen. Free, no ads, offline.
```

**Full description (4000 max):**

```
Help your child understand the world in 15 minutes a day.

News Pebbles is a set of free daily and weekly newspapers written for children and teenagers, each for one age group: 6–8, 9–11, 12–14 and 15+. They're short, calm and accurate: honest about hard news without graphic detail, and built only from sources you can check.

READ
• Today's papers for your child's age, one story at a time
• An easier version of each story with one tap, and text size and night mode
• "The story so far" for big ongoing stories, so nothing comes out of nowhere

PLAY
• A quick quiz, Fact or Fiction, word games and a map hunt for every paper
• Pebbles, badges and a reading streak that grows into a garden
• Certificates to print and keep

LISTEN
• Every paper read aloud, story by story
• The car-ride brief: two friendly hosts talk through the day's news in a few minutes
• Keeps playing with the screen off, with controls on the lock screen and in the car

OFFLINE
• The last 7 days of papers and recordings are saved on the device each morning: the bus, the car, a plane

FOR GROWN-UPS
• Print any paper for the breakfast table
• A morning reminder at the time you choose
• Links out, sharing, printing, email sign-up and the grown-ups' tools ask a grown-up a quick question first

PRIVATE BY DESIGN
• No accounts, no ads, no tracking, nothing counted in the app
• Reading progress stays on the device

The papers are written and fact-checked by AI from verified news sources, then checked automatically. Every issue lists its sources, and corrections are published at newspebbles.com/corrections.html.
```

**Graphics:** app icon `play/icon-512.png`; feature graphic `play/feature-graphic.png`; phone screenshots
`play/phone-1…5`; 7-inch tablet `play/tablet7-1…5`; 10-inch tablet `play/tablet10-1…5`.

## 3. Store settings (Grow users → Store presence → Store settings)

| Field | Value |
| --- | --- |
| App category | Education (if the News apps declaration below asks for **News & Magazines**, use that instead) |
| Tags | Education, News, Kids |
| Email | `info@newspebbles.com` |
| Website | `https://newspebbles.com/` |
| Phone | Leave empty |

## 4. App content (Policy and programs → App content)

**Privacy policy:** `https://newspebbles.com/privacy.html`

**App access:** All functionality is available without special access. (There is no sign-in; the grown-up
question is a sum anyone can answer, e.g. "What is sixteen multiplied by four?", answer 64.)

**Ads:** No, the app doesn't contain ads.

**Content rating** (IARC questionnaire): category **Reference, News or Educational**. Answer as for the App
Store: no violence shown, but news reports mention real conflicts and disasters in calm, non-graphic words;
no sexual content, profanity, drugs, gambling or user-to-user communication; no purchases; no location
sharing.

**Target audience and content:**
- Age groups: **6–8, 9–12, 13–15, 16–17** (add 18+ too if you want adults to find the 15+ paper)
- Because under-13s are included, the app follows the **Families policy**: no ads, no analytics or
  tracking SDKs, no account, and a grown-up question before links out, sharing, printing, email sign-up, the reminder
  setting, and the grown-ups' tools (Design your own, the progress report). Answer "Could your store listing unintentionally appeal to children?" with **Yes** (it is meant to).

**News apps:** **Yes**. It publishes daily news. The publisher contact is `info@newspebbles.com` and
`https://newspebbles.com/about.html`; sources are listed in every issue.

**Data safety:**

| Question | Answer |
| --- | --- |
| Does your app collect or share any of the required user data types? | **Yes** |
| Is all of the user data collected by your app encrypted in transit? | **Yes** (HTTPS only) |
| Do you provide a way for users to request that their data is deleted? | **Yes**: the unsubscribe link in every email, or `privacy@newspebbles.com` |
| Personal info → **Email address** | Collected, **not shared** (Cloudflare and Resend process it for us as service providers). Optional. Purpose: **App functionality** (sending the chosen paper) |
| App activity → **Other user-generated content** | Collected, not shared. Optional. Purpose: **App functionality** (anonymous You Make the Call answers, ages 12+, kept up to 90 days) |
| Everything else (location, contacts, photos, audio, files, calendar, identifiers, app info and performance, financial, health, messages, web history) | **Not collected** |

**Foreground service (media playback):** the app plays the papers' narration and the car-ride brief with
the screen off, started by the user. Play asks for a short video of this: record the Listen tab, tap a
paper, lock the phone, and show the lock-screen controls.

**Government app:** No. **Financial features:** None. **Health:** No.

## 5. Closed testing (needed before production on a new personal account)

Google requires at least **12 testers opted in for 14 days in a row** in a closed test before the app can
be published. Internal testing doesn't count.

1. Testing → **Closed testing** → Create track (or use **Alpha**) → Testers: an email list of 12 or more
   Google accounts (Gmail addresses of the Android phones), or a Google Group.
2. Build: `npx eas-cli@latest build --platform android --profile production` (from `mobile/`; the first
   build creates the signing key and EAS keeps it). Download the `.aab`.
3. Create release → upload the `.aab` (the **first upload must be done by hand** in Play Console) →
   release name `1.0.0 (1)` → release notes `First test of News Pebbles.` → Review → Start rollout.
4. Share the **opt-in link** from the track's Testers tab. Each tester opens it on their Android phone,
   taps Become a tester, then installs from Play. They should keep it installed for the 14 days.
5. After 14 days: Dashboard → **Apply for production** and answer the questions about the test.

New builds during the test are fine: build again, upload, roll out. Later uploads can go through
`npx eas-cli@latest submit --platform android --latest` once a Google service account key is set up
(`eas.json` sends them to the closed testing track as a draft).

**Feedback email for testers:** `info@newspebbles.com`.

## Build and upload a new version

From `mobile/` on the Mac:

1. Try it first: `npx expo start` and scan the QR code with **Expo Go** on an Android phone, or
   `npx eas-cli@latest build --platform android --profile preview` for an `.apk` to install directly.
2. Build: `npx eas-cli@latest build --platform android --profile production`
3. Upload the `.aab` to the testing track (or `eas-cli submit --platform android --latest`), then roll out.

New papers don't need a new version: the app downloads them every day.
