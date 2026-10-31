# App Store listing and submission pack

Everything to paste into App Store Connect, in the order you'll meet it. Privacy answers are in
[app-privacy.md](app-privacy.md). Screenshots: [screenshots/](screenshots/), made from the live app pack
with `NODE_PATH=$(npm root -g) node tools/app_screenshots.cjs https://newspebbles.com/app/ mobile/store/screenshots`
(6.9" iPhone 1320 × 2868 and 13" iPad 2064 × 2752, the two sizes Apple requires for an app that runs on iPad).

Don't add the app in App Store Connect until you're ready: the developer name shown on the App Store is fixed
when the first app is added (for an individual account it is the account holder's legal name).

## Submission checklist

In App Store Connect (signed in as the account holder), app **News Pebbles**:

1. **TestFlight:** the build you'll submit is installed and checked on an iPhone: papers open, Listen
   keeps playing with the screen locked, the reminder asks for permission, the widget adds and opens
   its issue, and papers open with no internet.
2. **App Information** (section 1 below): subtitle, categories, content rights, age rating
   (section 3), privacy policy URL.
3. **App Privacy** ([app-privacy.md](app-privacy.md)): the answers, then **Publish**.
4. **Pricing and Availability** (section 2): Free; all countries except China mainland.
5. **iOS App → 1.0 Prepare for Submission** (section 4): screenshots from [screenshots/](screenshots/)
   (iPhone 6.9" and iPad 13"), promotional text, description, keywords, support and marketing URLs,
   copyright; under **Build**, pick the TestFlight build.
6. **App Review Information** (section 5): sign-in not required, contact details, the notes.
7. **Version Release:** *Manually release this version*, so you choose the launch moment after approval.
8. **Add for Review**, then **Submit to App Review**. Review usually takes 1–2 days; Apple emails the result.

If Apple asks questions, they appear in App Store Connect under **App Review**; reply there.


---

## 1. App Information

| Field | Value |
| --- | --- |
| Name (30 max) | `News Pebbles: News for Kids` |
| Subtitle (30 max) | `Daily papers to read & hear` |
| Bundle ID | `com.newspebbles.app` |
| SKU | `newspebbles-ios` |
| Primary language | English (U.S.) |
| Primary category | Education |
| Secondary category | News |
| Content rights | Yes, it contains third-party content, and we have the rights: every paper is our own writing; news sources are linked, not reproduced; maps are Natural Earth (public domain); typefaces are under the SIL Open Font License |
| Privacy Policy URL | `https://newspebbles.com/privacy.html` |
| Support URL | `https://newspebbles.com/feedback.html` |
| Marketing URL | `https://newspebbles.com/` |
| Copyright | `2026` and the developer account's legal name |
| Kids Category | No (the papers cover ages 6–18; the app still follows the Kids Category rules: no ads, no tracking, a grown-up question before links out, sharing, printing, email sign-up, the reminder and widget settings, and the grown-ups' tools (Design your own, the progress report)) |

## 2. Pricing and Availability

**Price:** Free. No in-app purchases.

**Countries:** all, except **China mainland** (news apps there need a government licence).

## 3. Age Rating

Answer the questionnaire honestly. The papers report real news (conflicts, disasters, elections) calmly
and without graphic detail:

- Cartoon or fantasy violence: **None**
- Realistic violence: **Infrequent/Mild** (news reports of attacks and wars, never graphic)
- Mature or suggestive themes, sexual content, nudity, profanity, horror, drugs, alcohol, tobacco, gambling, contests: **None**
- Medical or treatment information: **None**
- Unrestricted web access: **No** (links open in Safari, and only after a grown-up answers a question)
- User-generated content, messaging or chat: **No**
- Parental controls: **Yes** (the grown-up question)
- Age assurance: **No**
- Advertising: **No**

Expect **9+**. The Little Explorer (6–8) is written for younger children; parents choose.

## 4. Version page (1.0)

**Promotional text (170 max, can change any time without review):**

```
Today's news, written for your child's age. Read it, play it, or listen in the car. Free, no ads, no account, and it works offline.
```

**Description:**

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
• Keeps playing with the screen locked, with next-story controls on the lock screen and in the car

OFFLINE
• The last 7 days of papers and recordings are saved on the device each morning: the bus, the car, a plane

FOR GROWN-UPS
• Print any paper (US Letter) for the breakfast table
• A morning reminder at the time you choose
• An optional home-screen widget with a question from your chosen paper, to talk about together
• Links out, sharing, printing, email sign-up and the grown-ups' tools ask a grown-up a quick question first

PRIVATE BY DESIGN
• No accounts, no ads, no tracking, nothing counted in the app
• Reading progress stays on the device

The papers are written and fact-checked by AI from verified news sources, then checked automatically. Every issue lists its sources, and corrections are published at newspebbles.com/corrections.html.
```

**Keywords (100 max):**

```
kids news,newspaper,current affairs,children,daily news,world,geography,reading,school,podcast
```

**Support URL / Marketing URL:** as in section 1.

**Version:** 1.0.0 · **Build:** pick the build uploaded by `eas submit`.

## 5. App Review Information

**Sign-in required:** No (the app has no accounts).

**Contact:** your name, phone number and `info@newspebbles.com`.

**Notes (paste as-is):**

```
News Pebbles has no accounts or sign-in. On first launch it downloads the day's papers from newspebbles.com (please allow a few seconds on the first open); after that everything works offline.

How to test:
1. Home: choose an age (e.g. 9–11) and open a paper. Read & Play shows today's papers; tap Read or Play.
2. Listen tab: tap the car-ride brief or any paper. Audio keeps playing with the screen locked; the lock screen shows play/pause and next story.
3. Grown-up question: links out, sharing, printing, email sign-up, the reminder and widget settings, and the grown-ups' tools (Design your own, the progress report) ask a sum written in words, e.g. "What is sixteen multiplied by four?" (answer 64). Three wrong answers pause it for 30 seconds. The For parents tab itself opens without it, so parents can read about the papers.
4. For parents → This app: turn on the morning reminder and pick a time (after the grown-up question; a local notification, there is no push server).
5. Print: on a paper's page, "Print this paper" opens the iOS print sheet after the grown-up question.
6. For parents → This app → A question to share: choose a paper and turn it on, then add the News Pebbles widget from the Home Screen or Lock Screen widget picker. Tapping it opens that issue.
7. For parents → Design your own (opens after the grown-up question): parents build a custom paper with their own AI chatbot. Opening the chatbot leaves the app for Safari, so it asks again; the finished PDF opens the share sheet.

There are no ads, no analytics, no tracking and no third-party SDKs beyond Expo's own libraries. Links out open in Safari. Optional email delivery and anonymous "You Make the Call" responses (ages 12+) are sent only after the grown-up question.
```

## 6. TestFlight (before the App Store)

| Field | Value |
| --- | --- |
| Beta App Description | `Try News Pebbles before release: today's papers for your child's age, to read, play and listen to, offline. Please tell us what's confusing.` |
| Feedback email | `info@newspebbles.com` |
| What to Test | `Open a paper for your child's age. Try the Listen tab with the screen locked and in the car. Turn on the morning reminder in For parents. Try it once without internet.` |
| Sign-in required | No |

Internal testers (people you add as App Store Connect users) can install immediately. For friends,
create an **External** group, add the build and turn on **Public Link**. The first build goes through
Beta App Review (usually under a day).

---

## Build and upload a new version

From `mobile/` on the Mac:

1. Build: `npx eas-cli@latest build --platform ios --profile production` (EAS has the certificates; the first
   build asks to sign in to the Apple Developer account)
2. Upload: `npx eas-cli@latest submit --platform ios --latest`
3. In App Store Connect, pick the new build on the version page and submit for review.

New papers don't need a new version: the app downloads them every day.
