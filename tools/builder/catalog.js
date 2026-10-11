const G = require(process.argv[2] + "/tools/builder/generator.js");
const base = { language: "en", location: "Washington, USA", timezone: "America/Los_Angeles", modules: {} };
const C = [
 ["little-explorers", {name:"The Little Explorer", pages:2, age:"6-8", purpose:"family", depth:"quick", cadence:"weekly",
   geos:["World","United States"], topics:["science","climate"], modules:{sports:false, watchlist:false, discussion:false, dyk:false, quote:false},
   profile:"A curious six-to-eight-year-old, reading with a grown-up at the weekend."},
   {focus:"Science and nature", blurb:"Two gentle pages a week: a big story, a science wonder and new words, for ages 6–8 reading with a grown-up.", weekday:"saturday"}],
 ["junior-daily", {name:"The Junior Daily", pages:1, age:"9-11", purpose:"global", depth:"quick", cadence:"daily",
   geos:["World","United States"], topics:[], modules:{vocab:false, dyk:false, sports:false, quote:false}, profile:"A curious nine-to-eleven-year-old who reads before school."},
   {focus:"World affairs", blurb:"The day's two biggest stories on one page, explained for ages 9–11."}],
 ["global-citizen-plus", {name:"The Global Citizen Plus", pages:4, age:"12-14", purpose:"school", depth:"balanced", cadence:"two_day",
   geos:["World","India","United States"], topics:["science","economics","politics"],
   profile:"A middle-schooler with family in India and the US who wants more than the headlines."},
   {focus:"World affairs", blurb:"Four pages on the world, India and the US, with science, economics, a quiz and an explainer."}],
 ["lab-notebook", {name:"The Lab Notebook", pages:4, age:"12-14", purpose:"school", depth:"balanced", cadence:"weekly",
   geos:["World"], topics:["science","climate","health","history"], profile:"A science-curious middle-schooler."},
   {focus:"Science and nature", blurb:"A weekly science paper: discoveries, climate, health and the history behind them, with a quiz.", weekday:"saturday"}],
 ["world-brief-teen", {name:"The World Brief", pages:2, age:"15-18", purpose:"global", depth:"deep", cadence:"daily",
   geos:["World","United States","United Kingdom","Europe","China"], topics:["politics","economics"],
   profile:"A high-school student who wants to understand the world, not just follow it."},
   {focus:"World affairs", blurb:"A daily two-page briefing for teens, with the evidence and the competing arguments."}],
 ["current-affairs-digest", {name:"The Current Affairs Digest", pages:4, age:"15-18", purpose:"exam", depth:"balanced", cadence:"daily",
   geos:["India","World"], topics:["politics","economics","science","history"], location:"New Delhi, India", timezone:"Asia/Kolkata",
   profile:"A student preparing for Indian competitive and board exams."},
   {focus:"Exam preparation", blurb:"Daily current affairs for Indian exam preparation: precise facts, key terms and an 8-question quiz."}],
 ["planet-weekly", {name:"Planet Weekly", pages:2, age:"15-18", purpose:"school", depth:"balanced", cadence:"weekly",
   geos:["World"], topics:["climate","science","health"], modules:{quiz:false, discussion:false}, profile:"A teenager who cares about climate and the planet."},
   {focus:"Science and nature", blurb:"The week in climate, environment and health science, with the evidence explained.", weekday:"sunday"}],
 ["breakfast-table", {name:"The Breakfast Table", pages:2, age:"9-11", purpose:"family", depth:"balanced", cadence:"daily",
   geos:["World","United States","India"], topics:["science","sports"], modules:{vocab:false, dyk:false}, profile:"A family reading together at breakfast, youngest about nine."},
   {focus:"Family", blurb:"A daily family paper: calm, accurate news with something to talk about together."}],
 ["the-bridge", {name:"The Bridge", pages:2, age:"adult", purpose:"global", depth:"balanced", cadence:"two_day",
   geos:["India","United States","World"], topics:["economics","business"], profile:"An Indian-American adult following both countries."},
   {focus:"India and the US", blurb:"India and the United States, side by side, every two days: politics, economy and the ties between them."}],
 ["global-ledger", {name:"The Global Ledger", pages:6, age:"adult", purpose:"global", depth:"deep", cadence:"weekly",
   geos:["World","United States","United Kingdom","Europe","China","Middle East"], topics:["politics","economics","business"],
   modules:{sports:false, vocab:false}, profile:"An adult who wants the week's world news in depth."},
   {focus:"World affairs", blurb:"Six pages every week: the world's biggest stories in depth, with analysis and an explainer.", weekday:"sunday"}],
 ["asia-watch", {name:"Asia Watch", pages:4, age:"adult", purpose:"pro", depth:"balanced", cadence:"weekly",
   geos:["China","Japan","India","Australia"], topics:["business","economics"], location:"Seattle, USA",
   profile:"A professional who follows Asia's economies and politics."},
   {focus:"Business and markets", blurb:"A weekly four-page brief on Asia's politics, markets and business.", weekday:"friday"}],
 ["morning-signal", {name:"The Morning Signal", pages:2, age:"pro", purpose:"pro", depth:"quick", cadence:"daily",
   geos:["United States","World","China"], topics:["business","economics","science"], location:"Seattle, USA"},
   {focus:"Business and markets", blurb:"Two pages before your first meeting: what changed, and what it means."}],
 ["europe-explained", {name:"Europe Explained", pages:2, age:"12-14", purpose:"global", depth:"balanced", cadence:"two_day",
   geos:["United Kingdom","Europe","World"], topics:["politics","science"], location:"London, UK", timezone:"Europe/London",
   profile:"A middle-schooler in the UK or Europe."},
   {focus:"World affairs", blurb:"The UK, Europe and the world for ages 12–14, every two days."}],
];
const out = {};
for (const [id, o, site] of C) {
  const r = G.generate(Object.assign({}, base, o, { id }));
  if (r.errors.length) { console.error(id, r.errors); process.exit(1); }
  out[id] = { yaml: r.yaml, site, warnings: r.warnings };
}
console.log(JSON.stringify(out));
