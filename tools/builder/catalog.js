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
 ["current-affairs-digest", {name:"The Current Affairs Digest", pages:4, age:"15-18", purpose:"exam", depth:"balanced", cadence:"daily",
   geos:["India","World"], topics:["politics","economics","science","history"], location:"New Delhi, India", timezone:"Asia/Kolkata",
   profile:"A student preparing for Indian competitive and board exams."},
   {focus:"Exam preparation", blurb:"Daily current affairs for Indian exam preparation: precise facts, key terms and an 8-question quiz."}],
 ["breakfast-table", {name:"The Breakfast Table", pages:2, age:"9-11", purpose:"family", depth:"balanced", cadence:"daily",
   geos:["World","United States","India"], topics:["science","sports"], modules:{vocab:false, dyk:false}, profile:"A family reading together at breakfast, youngest about nine."},
   {focus:"Family", blurb:"A daily family paper: calm, accurate news with something to talk about together."}],
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
