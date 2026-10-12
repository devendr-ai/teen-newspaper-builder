// "Start from": the papers on the newsstand, as builder choices.
const PRESETS = {
  "little-explorers": { label: "The Little Explorer · 6–8", name: "The Little Explorer", pages: 2, age: "6-8", purpose: "family", depth: "quick",
    geos: ["World"], topics: ["science", "climate"], cadence: "weekly", language: "en",
    modules: { sports: false, watchlist: false, discussion: false, dyk: false, quote: false } },
  "junior-daily": { label: "The Junior Daily · 9–11", name: "The Junior Daily", pages: 1, age: "9-11", purpose: "global", depth: "quick",
    geos: ["World"], topics: [], cadence: "daily", language: "en", modules: { vocab: false, dyk: false, sports: false, quote: false } },
  "breakfast-table": { label: "The Breakfast Table · family", name: "The Breakfast Table", pages: 2, age: "9-11", purpose: "family", depth: "balanced",
    geos: ["World"], topics: ["science", "sports"], cadence: "daily", language: "en", modules: { vocab: false, dyk: false } },
  "young-global-citizen": { label: "The Young Global Citizen · 12–14", name: "The Young Global Citizen Daily", subtitle: "DAILY", pages: 2, age: "12-14", exactAge: "13",
    profile: "A curious middle-schooler, reading once, at breakfast.", purpose: "global", depth: "balanced",
    geos: ["World", "India", "United States"], topics: ["world", "politics", "science", "economics"], cadence: "two_day",
    language: "en", modules: {} },
  "lab-notebook": { label: "The Lab Notebook · science", name: "The Lab Notebook", pages: 4, age: "12-14", purpose: "school", depth: "balanced",
    geos: ["World"], topics: ["science", "climate", "health", "history"], cadence: "weekly", language: "en", modules: {} },
  "current-affairs-digest": { label: "The Current Affairs Digest · 15+", name: "The Current Affairs Digest", pages: 4, age: "15-18", purpose: "exam", depth: "balanced",
    geos: ["India", "World"], topics: ["politics", "economics", "science", "history"], cadence: "daily", language: "en", modules: {} },
};
if (typeof module !== "undefined") module.exports = PRESETS;
