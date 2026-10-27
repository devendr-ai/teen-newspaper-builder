# News Pebbles for iPhone and iPad

The website's own pages (the app build, `python -m ygc site --kids`), saved on the phone, plus offline
papers, audio with the screen locked, a morning reminder, and the phone's print and share sheets.
See [docs/APP_BUILD.md](../docs/APP_BUILD.md) for how it works, and [store/](store/) for App Store Connect.

```sh
npm install
npx expo start                                                     # try it in Expo Go
npm run typecheck && npm run lint
npx eas-cli@latest build --platform ios --profile production       # then: eas-cli submit --platform ios --latest
```

| File | What it does |
|---|---|
| `App.tsx` | The pages in a WebView, the first download, the mini-player, messages from `assets/app/app.js` |
| `src/content.ts` | Keeps the phone's copy of `https://newspebbles.com/app/` up to date |
| `src/player.ts` | The phone's player (expo-audio): lock screen, background, next story |
| `src/reminder.ts` | The daily "Today's papers are ready" notification |
| `src/MiniPlayer.tsx` | What's playing, on pages without their own player |
