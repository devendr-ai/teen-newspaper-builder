# App Store Connect: App Privacy answers

Answers for **App Store Connect → your app → App Privacy**, based on what the app actually sends
(`mobile/src/`, `assets/app/app.js` and the app build of the site). Re-check this whenever a feature starts
sending new data.

What leaves the device:

- **Each day's papers** are downloaded from newspebbles.com (GitHub Pages). Nothing is sent with the
  request but the device's network address, which any web host sees. We keep nothing.
- **Optional email delivery** (For parents → "Get this paper by email", after the grown-up question): the
  grown-up's email address, chosen paper and frequency go to our subscription service (Cloudflare) and
  Resend sends the emails. This is the only data the app collects.
- Nothing else: no analytics, no ads, no crash reporting, no accounts, no third-party SDKs. Reading
  progress, ages, answers, pebbles and the reminder time stay on the device.

## Do you or your third-party partners collect data from this app?

**Yes** (only the optional email address).

| Apple category → type | What it is in News Pebbles | Purpose | Linked to user? | Used for tracking? |
| --- | --- | --- | --- | --- |
| Contact Info → **Email Address** | A grown-up's address, only if they subscribe to a paper by email | App Functionality | Yes | No |

## Do NOT declare (not collected)

Name, phone, physical address, health, financial info, location, sensitive info, contacts, user content,
browsing or search history, identifiers, purchases, usage data, diagnostics.

## Tracking

**No.** No advertising, no data brokers, no cross-app tracking, so no App Tracking Transparency prompt.

## URLs (App Store Connect → App Information)

- Privacy Policy: `https://newspebbles.com/privacy.html` (it has a section on the app)
- Support: `https://newspebbles.com/feedback.html`

## Notes

- The iOS privacy manifest (`ios.privacyManifests` in `app.json`) declares no tracking, the optional email
  address (App Functionality), and the standard reasons for the system APIs React Native uses. Check the generated
  `PrivacyInfo.xcprivacy` after the first `eas build`, and add entries if App Store Connect warns about
  missing reasons.
- If the email form should move to the website instead, the app would collect nothing and this page
  becomes **No, we do not collect data from this app**.
