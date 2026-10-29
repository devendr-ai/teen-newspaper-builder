# Issue-based question widgets

First release: iPhone home screen (`systemMedium`), iPhone Lock Screen
(`accessoryRectangular`), and Android home screen (resizable 4×2). Fact of the Day,
Live Activities and dedicated desktop widgets are outside this release.

## Parent experience

In the installed app, open **For parents → This app → A question to share**.
Choose a paper and turn the widget on. Setting changes pass the existing parent
check; they make no email or PII submission. Add News Pebbles through the phone's
widget picker (instructions are in the same panel). One paper selection applies
to every News Pebbles question widget on that device.

The widget copies the first suitable family discussion question from the latest
published issue. If the edition has no discussion block, it uses its first
suitable checked quiz question. No new question or fact is generated. Both widget
sizes show the issue date; the Lock Screen uses a shortened, ellipsized version
when necessary. No child's name, email, badge or reading history leaves the app.

Tap opens that **specific** issue, with its saved car-ride brief ready in the
native mini-player when available. Playback waits for Play; an already-playing
matching brief continues. If audio is unavailable, the same issue opens for
reading. Missing/expired issue pages do not silently redirect to a newer issue:
the parent gets an update/connect message instead. Another issue's audio is
stopped when falling back to the story.

## Updates, offline use and switching off

- `ygc/widgets.py` writes a small `widgets.json` on each website/app build, using
  only editions and readers actually published in that build. It is included in
  the ordinary offline pack. The native app reads the local pack first.
- Refreshes use only `https://newspebbles.com/app/widgets.json`, with no personal
  parameters, cookies or device identifiers. No extra widget request is made
  until a parent enables the feature.
- iOS uses Expo BackgroundTask, minimum interval 60 minutes. Android's widget
  provider requests an hourly update. The OS controls actual timing: this is
  **not** an exact-time daily delivery guarantee. iOS stops background work if
  the user force-quits the app. Opening the app refreshes the local content.
- Offline or failed updates keep the last validated question and its issue date.
  The lightweight question feed may get ahead of downloaded audio; a tap tries
  the normal content sync, then falls back to the matching saved story.
- Turning off clears the displayed question and stops further widget fetches.
  Remove the widget through the phone's usual UI if desired.

## Native setup and testing

Expo Go cannot host these widgets. Its widget controls are disabled with a clear
explanation, and startup avoids loading unavailable widget native modules.
A new development/preview/store binary is required; a website deploy alone does
not add widgets to an already-installed app.

- iOS: `expo-widgets`, `@expo/ui`, target `com.newspebbles.app.widgets`, app group
  `group.com.newspebbles.app`. The config plugin generates both widget targets
  inside one extension and the matching shared-container entitlements.
- Android: `react-native-android-widget` supplies a real `OPEN_URI` pending-intent
  action so tapping works even when the app process is closed. Expo's current
  Android widget buttons only deliver callback/broadcast interactions, so they
  are not used for this cold-launch requirement.
- Expo Router wraps the existing WebView app with `/` and `/widget` routes.
  Incoming edition/date parameters are validated and only exact downloaded
  reader pages bearing an `np-issue` marker can open. Audio must match both
  edition and date and be a local MP3 listed in the content pack.
- Configurations live in `mobile/app.json`; native projects are generated with
  Expo Prebuild and remain untracked. Widget settings/cache use document files;
  no new backend or account system is introduced.

Checks: `python -m pytest tests/test_widgets.py`; in `mobile/`, run
`npm run test:widgets`, `npm run test:parent-api`, `npm run typecheck`, and
`npm run lint`. Bundle both platforms and validate generated native targets with
Expo Prebuild. CI runs the widget tests, typecheck and lint alongside parent API
checks. Physical-widget behaviour still requires installed-build testing:

1. Enable, add home/lock widgets, verify selected paper/date and full/short text.
2. Tap with the app closed and open; confirm exact issue and ready paused brief.
3. Test an edition with no brief and a stale/expired issue link.
4. Test flight mode, background refresh, phone restart and switching off.
5. Check large text, VoiceOver/TalkBack, dark mode and tinted iPhone widgets.
6. Confirm Expo Go and existing non-widget app builds still open normally.

Build profiles: `simulator` for an unsigned iOS Simulator test; `preview` for an
installable Android APK; `development` for a development-client build. An iPhone
build requires Apple signing and a registered device/TestFlight setup. Cloud
builds do not submit to either app store automatically.

For a browser-level parent setup check, serve a kids build locally and run
`node tools/widget_settings_check.cjs http://localhost:8000/` with Playwright
available. It simulates only the native bridge, uses the real parent gate, and
checks one approval when enabling, blocked wrong answers, the chosen edition,
zero outside requests and phone layout.
