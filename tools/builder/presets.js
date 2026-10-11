const PRESETS = {
  "young-global-citizen": { label: "Young Global Citizen", name: "The Young Global Citizen Daily", subtitle: "DAILY", pages: 2, age: "12-14", exactAge: "13",
    profile: "A US-based reader of Indian origin, reading once, at breakfast.", purpose: "global", depth: "balanced",
    geos: ["World", "India", "United States"], topics: ["world", "politics", "science", "economics"], cadence: "two_day",
    language: "en", location: "Washington, USA", timezone: "America/Los_Angeles", modules: {} },
  "junior-explorer": { label: "Junior Explorer", name: "The Junior Explorer", pages: 3, age: "9-11", exactAge: "9",
    profile: "A curious US fourth-grader, reading with a parent at the weekend.", purpose: "school", depth: "balanced",
    geos: ["World", "United States"], topics: ["science", "climate"], cadence: "weekly", language: "en",
    location: "Washington, USA", timezone: "America/Los_Angeles", modules: { sports: true, discussion: false, quiz: false } },
  "science-learner": { label: "Science learner", name: "The Lab Notebook", pages: 4, age: "12-14", purpose: "school", depth: "balanced",
    geos: ["World"], topics: ["science", "climate", "health", "history"], cadence: "weekly", language: "en",
    location: "Washington, USA", timezone: "America/Los_Angeles", modules: {} },
  "exam-prep-india": { label: "Exam prep, India", name: "The Current Affairs Digest", pages: 4, age: "15-18", purpose: "exam", depth: "balanced",
    geos: ["India", "World"], topics: ["politics", "economics", "science", "history"], cadence: "daily", language: "en",
    location: "New Delhi, India", timezone: "Asia/Kolkata", modules: {} },
};
if (typeof module !== "undefined") module.exports = PRESETS;
