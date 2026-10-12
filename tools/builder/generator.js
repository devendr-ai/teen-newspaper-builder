/* ygc edition generator: reader choices -> a valid editions/<id>/edition.yaml.
 * Pure function, no DOM. Embedded in the configurator page and tested with node
 * against the real Python validator (python -m ygc). */
(function (root) {
  "use strict";

  const AGES = {
    "6-8":   { label: "Ages 6–8", scale: 1.35, wpm: 90, vocab: 3, kid: true,
               level: "Early reader (grades 1–3). Very short sentences, one idea each. Explain every new word.",
               voice: "Warm, gentle and concrete, like reading aloud together. Honest about sad news but never frightening or graphic: say what happened and who is helping.",
               profile: "A curious young child, reading with a parent." },
    "9-11":  { label: "Ages 9–11", scale: 1.25, wpm: 130, vocab: 4, kid: true,
               level: "Upper elementary. Short sentences. Explain every new word the first time it appears.",
               voice: "Warm, simple and exact, like a favourite teacher. Honest about hard news without graphic detail.",
               profile: "A curious upper-elementary reader." },
    "12-14": { label: "Ages 12–14", scale: 1.0, wpm: 180, vocab: 4, kid: false,
               level: "Elevated middle school. Never childish; explain without dumbing down.",
               voice: "Clear, engaging and intelligent. Use analogies a middle-schooler knows. Where people genuinely disagree, give each side in its own terms.",
               profile: "A middle-school reader, reading once at breakfast." },
    "15-18": { label: "Ages 15+", scale: 0.95, wpm: 220, vocab: 4, kid: false,
               level: "High school. Adult news vocabulary, with technical terms defined on first use.",
               voice: "Direct and analytical. Show the evidence, name the trade-offs and present competing arguments fairly.",
               profile: "A high-school student building a serious understanding of the world." },
  };

  const PURPOSES = {
    global: { label: "Global awareness and learning",
      lines: ["Strong general knowledge of the world and the regions it covers.",
              "Early political and economic awareness.",
              "Curiosity and independent thinking.",
              "The habit of connecting events to history, geography and cause and effect."],
      modules: { vocab: true, dyk: true, watchlist: true, quote: true, sports: true, explainer: false, quiz: false, discussion: false } },
    school: { label: "School curriculum and current affairs",
      lines: ["Connections between the news and school subjects: history, geography, science, civics and economics.",
              "Confident use of subject vocabulary.",
              "Questions worth discussing in class."],
      modules: { vocab: true, dyk: true, watchlist: false, quote: true, sports: false, explainer: true, quiz: true, discussion: true } },
    exam: { label: "Exam preparation and general knowledge",
      lines: ["Facts worth remembering: names, dates, places and numbers, stated precisely.",
              "Understanding of why events matter, not just what happened.",
              "Regular self-testing through quizzes."],
      modules: { vocab: true, dyk: true, watchlist: true, quote: false, sports: false, explainer: true, quiz: true, discussion: false } },
    family: { label: "Family-friendly daily briefing",
      lines: ["A shared picture of the day's news for every age at the table.",
              "Something to talk about together.",
              "Calm, accurate understanding of hard news."],
      modules: { vocab: true, dyk: true, watchlist: true, quote: true, sports: true, explainer: false, quiz: false, discussion: true } },
  };

  const DEPTHS = {
    quick:    { label: "Quick facts and key implications",
                rule: "Keep each story to its essentials: what happened, the key numbers and why it matters." },
    balanced: { label: "News plus context and explanation",
                rule: "Give each story enough context that the reader could explain it to someone else." },
    deep:     { label: "Background, evidence, competing perspectives",
                rule: "Give background, the evidence behind each claim, and the strongest version of each competing perspective." },
  };

  const TOPICS = {
    world:     { label: "WORLD", name: "World affairs", world: true },
    politics:  { label: "POLITICS & CIVICS", name: "Politics and civics", scope: "How power and government work, shown through the window's most important political story." },
    science:   { label: "SCIENCE & TECH", name: "Science and technology", scope: "The most significant discovery, research result or technology development of the window.", rules: ["Prefer peer-reviewed findings and official data over company announcements."] },
    economics: { label: "ECONOMY", name: "Economics", scope: "The economic story with the widest effect on households: prices, jobs, trade, interest rates or public money." },
    business:  { label: "BUSINESS & MARKETS", name: "Business and markets", scope: "The most consequential company, industry or market development of the window." },
    history:   { label: "HISTORY & GEOGRAPHY", name: "History and geography", scope: "A current story whose roots in history or geography are worth explaining." },
    climate:   { label: "CLIMATE & ENVIRONMENT", name: "Climate and environment", scope: "The most significant climate, weather or environmental story, with evidence and scale." },
    health:    { label: "HEALTH", name: "Health", scope: "The most significant public-health or medical-science story, reported with care and evidence." },
    sports:    { label: "SPORTS", name: "Sports", sports: true },
    arts:      { label: "ARTS & CULTURE", name: "Arts and culture", scope: "A significant story from books, film, music, art or heritage." },
    education: { label: "EDUCATION", name: "Education", scope: "The most significant story about schools, universities, exams or learning." },
    local:     { label: "LOCAL", name: "My city", local: true },
    space:     { label: "SPACE", name: "Space and astronomy", group: "nature", scope: "The most exciting space or astronomy story of the window: a mission, a discovery or something to see in the sky.", rules: ["Prefer space agencies, observatories and peer-reviewed findings over company announcements."] },
    animals:   { label: "ANIMALS & NATURE", name: "Animals and nature", group: "nature", scope: "The most interesting story about animals, plants or wild places in the window: a discovery, a rescue or a conservation effort." },
    tech_ai:   { label: "TECH & AI", name: "Technology and AI", group: "nature", scope: "The most significant technology or artificial-intelligence story of the window: what it does, who it affects and what to be careful about." },
    inventions:{ label: "INVENTIONS", name: "Inventions and how things work", group: "nature", scope: "A new invention, machine or feat of engineering in the news, with how it works explained simply." },
    money:     { label: "MONEY", name: "Money for kids", group: "nature", scope: "A money story from the window explained for a young reader: prices, saving, jobs, or how shops and businesses work." },
    cricket:   { label: "CRICKET", name: "Cricket", group: "sport", scope: "The most important cricket news of the window: results, records and players, with one rule or tactic explained." },
    football:  { label: "FOOTBALL", name: "Football (soccer)", group: "sport", scope: "The most important football (soccer) news of the window: results, records and players, with one rule or tactic explained." },
    f1:        { label: "FORMULA 1", name: "Formula 1", group: "sport", scope: "The most important Formula 1 news of the window: race results, the standings and the engineering behind the cars." },
    olympics:  { label: "OLYMPIC SPORTS", name: "Olympic sports", group: "sport", scope: "The most important news from Olympic sports in the window, such as athletics, swimming or gymnastics." },
    tennis:    { label: "TENNIS", name: "Tennis", group: "sport", scope: "The most important tennis news of the window: tournaments, results and players." },
  };

  // How the paper feels. Each adds an edition rule; gentle and good news also steer the lead.
  const TONES = {
    gentle:     { label: "Gentle mode", desc: "No war or disaster stories leading; hard news only briefly, with who is helping",
                  rule: "Gentle mode: no war, disaster, crime or death story leads the paper or gets a story of its own. Mention hard news only briefly, in the briefs, saying calmly what happened and who is helping.",
                  lead: "Choose the most important story that is not about war, disaster, crime or death." },
    good_news:  { label: "Good news paper", desc: "Only hopeful stories: discoveries, rescues, records, kindness",
                  rule: "Good news paper: every story is hopeful, such as a discovery, a rescue, a record, an act of kindness or real progress. Leave out conflict, disaster and crime entirely, even in the briefs.",
                  lead: "Choose the most important hopeful story of the window." },
    both_sides: { label: "Both sides", desc: "Every disputed story gives each side in its own words",
                  rule: "Both sides: whenever people disagree about a story, give each side's strongest case in its own words and say which facts both sides accept. Never tell the reader which side is right." },
    solutions:  { label: "Solutions lens", desc: "Every problem comes with who is working on fixing it",
                  rule: "Solutions lens: every story about a problem also reports who is working to fix it, what they are doing and what evidence there is that it works." },
  };

  // Learning sections: feature boxes the writer fills from the issue. fixed = share of a column at type scale 1.
  const EXTRA_SECTIONS = {
    on_this_day:    { name: "On this day", label: "ON THIS DAY", fixed: 0.2, sources: true,
                      brief: "One event that happened on today's date in history, linked to this issue if possible: what happened and why it still matters." },
    number_of_day:  { name: "Number of the day", label: "NUMBER OF THE DAY", fixed: 0.16, sources: true,
                      brief: "One number from this issue's news as the title, then what it measures and why it matters, with a comparison the reader can picture." },
    fact_fiction:   { name: "Fact or fiction?", label: "FACT OR FICTION?", fixed: 0.18, sources: false,
                      brief: "Two short claims linked to this issue's stories, one true and one false. The last paragraph gives the answer and how we know." },
    spot_clue:      { name: "Spot the clue", label: "SPOT THE CLUE", fixed: 0.22, sources: false,
                      brief: "Media literacy: take one claim from this issue and show how we know it: who said it, how they know, and what would make us more or less sure. End with one question for the reader." },
    jobs:           { name: "Jobs behind the news", label: "JOBS BEHIND THE NEWS", fixed: 0.22, sources: false,
                      brief: "One job that made a story in this issue happen, such as a pilot, scientist, judge or engineer: what they do, what they learned to do it, and one thing that is hard about it." },
    try_home:       { name: "Try this at home", label: "TRY THIS AT HOME", fixed: 0.26, sources: false,
                      brief: "One safe, simple activity or experiment with things found at home, linked to a story in this issue: 3 or 4 short steps, then what to notice. Never heat, sharp tools or chemicals." },
    map_challenge:  { name: "Map challenge", label: "MAP CHALLENGE", fixed: 0.16, sources: false,
                      brief: "Three places from this issue to find on a map or globe, each with one clue such as its continent, a neighbour or a nearby sea." },
  };

  // "One big story": the whole paper explains a single story. Features carry the depth.
  const BIG = {
    background: { label: "HOW WE GOT HERE", sources: true, brief: "The background to the big story: what led up to it, in plain steps." },
    timeline:   { label: "TIMELINE", sources: true, brief: "5 to 7 key moments of the big story in order, one per paragraph, each starting with its date." },
    people:     { label: "WHO'S WHO", sources: true, brief: "The main people, places and groups in the big story, one short paragraph each." },
    sides:      { label: "WHAT PEOPLE THINK", sources: true, brief: "How different people see the big story, each view in its own terms and attributed. Never say which view is right." },
    next:       { label: "WHAT HAPPENS NEXT", sources: true, brief: "What to watch for next in the big story, with dates where they are known." },
  };

  const GEOS = ["World", "United States", "India", "United Kingdom", "Canada", "China",
                "Europe", "Middle East", "Australia", "Japan"];

  const CADENCE = {
    daily:   { every_days: 1, window_hours: 24, subtitle: "DAILY", watch: "TOMORROW'S WATCHLIST", see: "See you tomorrow." },
    two_day: { every_days: 2, window_hours: 48, subtitle: "DAILY", watch: "WHAT TO WATCH NEXT", see: "See you in two days." },
    weekly:  { every_days: 7, window_hours: 168, subtitle: "WEEKLY", watch: "COMING UP", see: "See you next week." },
  };

  // Share of one column each fixed-size block uses at type scale 1.0, calibrated
  // by measuring real issues (Young Global Citizen and Junior Explorer). Stories
  // are elastic: writers fill them to whatever their column leaves.
  const FIXED = { rule: 0.017, did_you_know: 0.1, sports: 0.12, quote: 0.04, sign_off: 0.035,
                  explainer: 0.36, quiz: 0.42, discussion: 0.2, analysis: 0.48 };
  const STORY_MIN = 0.42;          // a story squeezed below this reads as a brief

  const SHORT = { "united states": "us", "united kingdom": "uk", "usa": "us", "uk": "uk" };
  const slug = (s) => SHORT[s.toLowerCase()] || s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const idSlug = (s) => s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const q = (s) => JSON.stringify(String(s));            // double-quoted YAML scalar
  const printable = (s) => /^[\x20-\x7E\u00A0-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\u2022\u2026\u20AC]*$/.test(s);

  function storyCount(pages) {
    if (pages <= 1) return 2;
    if (pages === 2) return 4;
    if (pages <= 6) return 2 * (pages - 1);
    return 2 * (pages - 2);
  }

  function generate(o) {
    const errors = [], warnings = [];
    const age = AGES[o.age], purpose = PURPOSES[o.purpose], depth = DEPTHS[o.depth];
    const cad = CADENCE[o.cadence];
    const pages = Math.max(1, Math.min(12, parseInt(o.pages, 10) || 2));
    if (!age || !purpose || !depth || !cad) errors.push("Choose a reader, purpose, depth and frequency.");
    if (o.language && o.language !== "en")
      errors.push("Hindi and bilingual editions need the Unicode font upgrade, which the engine doesn't have yet. Choose English for now.");
    const name = (o.name || "").trim();
    if (!name) errors.push("Give the paper a name.");
    if (name && !printable(name)) errors.push("The paper's name uses characters the PDF fonts can't print.");
    const geos = (o.geos || []).filter(Boolean);
    const topics = (o.topics || []).filter((t) => TOPICS[t]);
    if (!geos.length && !topics.length) errors.push("Choose at least one country, region or topic to cover.");
    for (const g of geos) if (!printable(g)) errors.push(`"${g}" uses characters the PDF fonts can't print.`);
    if (o.purpose === "exam" && (o.age === "6-8"))
      warnings.push("Exam preparation for ages 6–8 is unusual; the quiz will be kept short and gentle.");
    const big = o.format === "big_story";
    if (big && pages < 2) errors.push("One big story needs at least two pages.");
    if (big && pages > 4) errors.push("One big story works on two to four pages.");
    const tones = Object.keys(TONES).filter((t) => (o.tone || {})[t]);
    const child = (o.childName || "").trim(), fav = (o.favourite || "").trim(), city = (o.city || "").trim();
    for (const [what, v] of [["The child's name", child], ["The favourite team or player", fav], ["The city", city]])
      if (v && !printable(v)) errors.push(`${what} uses characters the PDF fonts can't print.`);
    if (errors.length) return { errors, warnings };
    const scale = age ? Math.min(1.6, Math.round(age.scale * (o.largePrint ? 1.15 : 1) * 100) / 100) : 1;

    // ---- modules: purpose defaults, then the reader's overrides, then age limits
    const m = Object.assign({}, purpose.modules, o.modules || {});
    if (topics.includes("sports")) m.sports = true;
    const sportDesks = topics.filter((t) => TOPICS[t].group === "sport");
    if (fav && !sportDesks.length) m.sports = true;
    if (big) { m.sports = false; m.watchlist = false; }
    if (age.vocab === 0) m.vocab = false;
    if (o.purpose === "exam") m.quiz = true;

    // ---- desks
    const desks = [];
    const worldWanted = geos.includes("World") || topics.includes("world");
    const where = geos.filter((g) => g !== "World");
    const coverage = [worldWanted ? "the world" : null, ...where].filter(Boolean);
    const leadRules = tones.map((t) => TONES[t].lead).filter(Boolean);
    if (big && topics.length)
      leadRules.push(`Prefer a story about ${listJoin(topics.map((t) => TOPICS[t].name.toLowerCase()))} when one is among the most important of the window.`);
    desks.push({ id: "top", label: big ? "THE BIG STORY" : "TOP STORY",
      scope: `The single most important story of the window for this reader${coverage.length ? `, from ${listJoin(coverage)}` : ""}.`
             + (big ? " The whole paper explains this one story in depth." : ""),
      rules: [...leadRules, "If a running story is still the biggest, it leads again, written as the new development."] });
    if (big) desks.push({ id: "numbers", label: "BY THE NUMBERS",
      scope: "The numbers behind the big story: one key measurement or comparison, explained, with a chart built only from sourced numbers." });
    const order = [];
    if (worldWanted) { desks.push({ id: "world", label: "WORLD", scope: "The next most important world story, from a region or field the lead doesn't cover." }); order.push("world"); }
    for (const g of where) {
      const id = slug(g);
      desks.push({ id, label: g.toUpperCase(), scope: `The most important story from ${g} in the window: one that teaches something, not filler.` });
      order.push(id);
    }
    for (const t of topics) {
      const T = TOPICS[t];
      if (T.world || T.sports) continue;
      if (T.local) {
        desks.push({ id: "local", label: city ? city.toUpperCase() : "LOCAL", scope: `The most important community story from around ${city || o.location || "the reader's home"}.` });
      } else {
        desks.push(Object.assign({ id: slug(T.name) }, { label: T.label, scope: T.scope }, T.rules ? { rules: T.rules } : {}));
      }
      order.push(T.local ? "local" : slug(T.name));
    }
    if (!order.length) order.push("top");

    // ---- blocks
    const kid = age.kid;
    const briefsCount = pages <= 2 ? 2 : pages <= 4 ? 4 : pages <= 6 ? 5 : 6;
    const vocabCount = Math.max(age.vocab, 0);
    const blocks = {};
    const tail = [];   // non-story modules, in reading order
    if (!big) tail.push(["briefs", { type: "briefs", count: briefsCount }]);
    if (m.vocab && vocabCount) tail.push(["vocab", { type: "vocab", count: vocabCount }]);
    if (m.dyk) tail.push(["did_you_know", { type: "did_you_know" }]);
    const featurePage = pages >= 7;
    if (!big && (m.explainer || featurePage || (o.depth === "deep" && pages >= 6))) tail.push(["explainer", { type: "feature", label: kid ? "HOW IT WORKS" : "EXPLAINER",
      brief: "Background behind one of this issue's stories, from well-established facts.", sources: false }]);
    if (!big && (featurePage || o.depth === "deep" && pages >= 4)) tail.push(["analysis", { type: "feature", label: "THE BIG PICTURE",
      brief: "Analysis connecting several of this issue's stories, with the evidence and the strongest competing perspectives." }]);
    const quizN = o.purpose === "exam" || pages >= 6 ? 8 : 5;
    if (m.quiz) tail.push(["quiz", { type: "feature", label: "QUIZ",
      brief: `${quizN} multiple-choice questions on ${big ? "the big story" : "this issue"}, with the answers at the end.`, sources: false, questions: quizN }]);
    if (m.discussion) tail.push(["discussion", { type: "feature", label: kid ? "TALK ABOUT IT" : "DISCUSS",
      brief: "Three open questions about this issue for discussion at home or in class. Questions only, never answers.", sources: false }]);
    for (const [k, x] of Object.entries(EXTRA_SECTIONS))
      if (m[k]) tail.push([k, Object.assign({ type: "feature", label: x.label, brief: x.brief }, x.sources ? {} : { sources: false })]);
    if (m.sports) tail.push(["sports", { type: "sports" }]);
    if (m.watchlist) tail.push(["watchlist", { type: "watchlist", count: pages >= 4 ? 3 : 2, title: cad.watch }]);
    if (m.quote) tail.push(["quote", { type: "quote" }]);
    const signText = kid ? `Keep exploring${child ? `, ${child}` : ""}. ${cad.see}`
                         : `You are not just reading the news — you are learning to think about it. ${cad.see}`;
    tail.push(["sign_off", { type: "sign_off", text: signText }]);
    for (const [id, b] of tail) blocks[id] = b;
    const tailIds = tail.map((t) => t[0]);

    const ELASTIC = big ? ["explainer", ...Object.keys(BIG)] : ["explainer", "analysis"];
    let slots = [], unplaced = [];
    const plan = [], notes = [];
    const colOf = {}, colFixed = {};
    const measureCols = () => plan.forEach((pg, p) => pg.columns.forEach((col, c) => {
      const f = col.reduce((a, id) => a + fixedOf(id, blocks[id]), 0) * scale * scale;
      col.forEach((id) => { colOf[id] = `${p}:${c}`; });
      colFixed[`${p}:${c}`] = f;
    }));
    if (!big) {
    // A closing page whose sections fill under one column gets one more story instead of white space.
    const tailFixedOn = (ids) => ids.reduce((a, id) => a + (ELASTIC.includes(id) ? 0.3 : fixedOf(id, blocks[id])), 0) * scale * scale;
    const closingIds = tailIds.filter((id) => !(pages >= 7 && ELASTIC.includes(id)));
    const tailSize = tailFixedOn(closingIds);
    const closingStories = pages < 3 ? 0 : tailSize < 0.55 ? 2 : tailSize < 0.95 ? 1 : 0;

    // ---- story slots
    const nStories = storyCount(pages) + closingStories;
    slots = [{ id: "lead", desk: "top", size: "lead" }];
    const storyBlocks = () => slots.forEach((x) => { if (!blocks[x.id]) blocks[x.id] = { type: "story", desk: x.desk }; });
    const used = {};
    for (let i = 0; slots.length < nStories; i++) {
      const d = order[i % order.length];
      used[d] = (used[d] || 0) + 1;
      slots.push({ id: used[d] > 1 ? `${d}_${used[d]}` : d, desk: d, size: pages === 1 ? "compact" : "standard" });
    }
    unplaced = order.filter((d) => !slots.some((s) => s.desk === d));
    const geoIds = where.map(slug).concat(worldWanted ? ["world"] : []);
    const lostGeo = unplaced.filter((d) => geoIds.includes(d)), lostTopic = unplaced.filter((d) => !geoIds.includes(d));
    const nm = (ids) => listJoin(ids.map((d) => titleCase(desks.find((x) => x.id === d).label)));
    if (lostGeo.length)
      warnings.push(`${nm(lostGeo)} won't get ${lostGeo.length === 1 ? "its" : "their"} own story at ${pages} page${pages > 1 ? "s" : ""}, only briefs. Add pages or remove a region.`);
    if (lostTopic.length)
      notes.push(`${nm(lostTopic)} will be covered as angles within other stories and in briefs, not as stories of ${lostTopic.length === 1 ? "its" : "their"} own. Add pages to give ${lostTopic.length === 1 ? "it its" : "each its"} own story.`);
    if (pages >= 4 && order.length < nStories / 2)
      warnings.push(`${nStories} stories but only ${order.length} desk${order.length > 1 ? "s" : ""}: most desks will carry two or more stories. Add countries or topics, or choose fewer pages.`);

    storyBlocks();
    // keep stories first in the YAML for readability
    for (const id of tailIds) { const b = blocks[id]; delete blocks[id]; blocks[id] = b; }

    // ---- page plan
    const s = slots.map((x) => x.id);
    const take = (ids) => ids.filter((id) => tailIds.includes(id));
    if (pages === 1) {
      plan.push({ masthead: true, columns: [[s[0]], [s[1], ...take(["briefs", "vocab", "watchlist", "sign_off"])]] });
      const dropped = tailIds.filter((id) => !["briefs", "vocab", "watchlist", "sign_off"].includes(id));
      dropped.forEach((id) => delete blocks[id]);
      if (dropped.length) warnings.push(`A one-page paper has no room for: ${listJoin(dropped.map(nice))}.`);
    } else if (pages === 2) {
      plan.push({ masthead: true, columns: [[s[0]], [s[1]]] });
      const left = [s[2]], right = [s[3]];
      const leftMods = ["briefs", "vocab", "did_you_know", "explainer", "discussion"];
      left.push(...take(leftMods));
      const rightMods = tailIds.filter((id) => !leftMods.includes(id));
      right.push("rule", ...rightMods);
      // at large type the left column can't hold its story plus every module: move modules across
      const sq = scale * scale, cap = 1 - STORY_MIN;
      const fx = (col) => col.reduce((a, id) => a + fixedOf(id, blocks[id]), 0) * sq;
      while (left.length > 2 && fx(left) > cap) right.splice(1, 0, left.pop());
      plan.push({ banner: banner(2, [blocks[s[2]].desk, blocks[s[3]].desk], desks), columns: [left, right] });
    } else {
      const storyPages = featurePage ? pages - 2 : pages - 1;
      for (let p = 0; p < storyPages; p++) {
        const pair = [s[2 * p], s[2 * p + 1]];
        plan.push(Object.assign(p === 0 ? { masthead: true } : { banner: banner(p + 1, pair.map((id) => blocks[id].desk), desks) },
          { columns: [[pair[0]], [pair[1]]] }));
      }
      let mods = tailIds.slice();
      if (featurePage) {
        plan.push({ banner: `<b>PAGE ${storyPages + 1}</b>  •  ${kid ? "Go deeper" : "Analysis"}`, columns: [["explainer"], ["analysis"]] });
        mods = mods.filter((id) => id !== "explainer" && id !== "analysis");
      }
      const closingBanner = `<b>PAGE ${pages}</b>  •  ${kid ? "Learn and play" : "Your toolkit"}`;
      let closing;
      if (closingStories === 2) {
        const [a, b] = balance(mods.filter((id) => id !== "rule"), blocks);
        closing = [[s[s.length - 2], ...a], [s[s.length - 1], ...b]];
      } else if (closingStories === 1) closing = [[s[s.length - 1]], mods];
      else closing = balance(mods, blocks);
      plan.push({ banner: closingBanner, columns: closing });
    }

    // ---- graphics, extras and "also" lists, now that we know who shares a column
    measureCols();
    const roomy = (s) => (colFixed[colOf[s.id]] || 0) <= 0.4;
    const chartDesks = ["economics", "business_and_markets", "us"];
    let chartGiven = false;
    slots.forEach((s, i) => {
      if (i === 0) s.graphics = [worldWanted ? "map" : "illustration"];
      else if (!roomy(s)) s.graphics = [];
      else if (chartDesks.includes(s.desk) && !chartGiven) { s.graphics = ["chart"]; chartGiven = true; }
      else s.graphics = ["illustration"];
    });
    if (!chartGiven) {
      const c = slots.slice(2).reverse().find((s) => s.graphics.length) || slots.slice(1).find((s) => s.graphics.length);
      if (c) { c.graphics = ["chart"]; chartGiven = true; }
    }
    slots.forEach((s, i) => {
      if (i === 0) s.extras = o.depth === "deep" ? ["why", "analyst"] : ["why"];
      else if (i === 1 && o.depth !== "quick") s.extras = ["connect"];
      else if (s.graphics[0] === "chart" && o.depth !== "quick") s.extras = ["why", "analyst"];
      else s.extras = o.depth === "deep" && i % 2 === 0 ? ["why", "analyst"] : ["why"];
    });
    if (pages <= 2) {
      const c = slots.find((s, i) => i >= 2 && where.map(slug).includes(s.desk) && s.graphics[0] !== "chart");
      if (c) c.also = { count: 2, title: `Also in ${where.find((g) => slug(g) === c.desk)}` };
    }
    } else {
      // ---- one big story: the lead tells it, a chart story gives the numbers, features explain it
      slots = [{ id: "lead", desk: "top", size: "lead", graphics: [worldWanted || where.length ? "map" : "illustration"],
                 extras: o.depth === "deep" ? ["why", "analyst"] : ["why"] },
               { id: "numbers", desk: "numbers", size: "standard", graphics: ["chart"], extras: ["why"] }];
      for (const x of slots) blocks[x.id] = { type: "story", desk: x.desk };
      const parts = ["background", "timeline", "people"].concat(pages >= 3 ? ["sides", "next"] : []);
      for (const k of parts) blocks[k] = Object.assign({ type: "feature", label: BIG[k].label, brief: BIG[k].brief });
      blocks.explainer = { type: "feature", label: kid ? "HOW IT WORKS" : "EXPLAINER", sources: false,
        brief: "The one idea the reader needs to understand the big story, such as how a vote, a vaccine or a trade route works, from well-established facts." };
      for (const id of ["lead", "numbers", ...parts, "explainer", ...tailIds]) { const b = blocks[id]; delete blocks[id]; blocks[id] = b; }
      const pb = (n, t) => `<b>PAGE ${n}</b>  •  ${t}`;
      const closingBanner = pb(pages, kid ? "Learn and play" : "Your toolkit");
      plan.push({ masthead: true, columns: [["lead"], ["timeline", "people"]] });
      if (pages === 2) plan.push({ banner: pb(2, "The big story, explained"), columns: [["numbers", "background"], ["explainer", ...tailIds]] });
      else if (pages === 3) {
        plan.push({ banner: pb(2, "The big story, explained"), columns: [["numbers", "background"], ["explainer", "sides", "next"]] });
        plan.push({ banner: closingBanner, columns: balance(tailIds, blocks) });
      } else {
        plan.push({ banner: pb(2, "How we got here"), columns: [["numbers"], ["background"]] });
        plan.push({ banner: pb(3, "What it means"), columns: [["explainer"], ["sides", "next"]] });
        plan.push({ banner: closingBanner, columns: balance(tailIds, blocks) });
      }
      measureCols();
    }
    for (const s of slots) {
      const b = blocks[s.id];
      if (s.size !== "standard") b.size = s.size;
      if (s.graphics.length) b.graphics = s.graphics;
      b.extras = s.extras;
      if (s.also) b.also = s.also;
    }

    // ---- fill estimate per column: fixed blocks plus the elastic story share
    const fill = plan.map((pg, p) => pg.columns.map((col, c) => {
      const elasticHere = col.filter((id) => ELASTIC.includes(id));
      const fixed = (colFixed[`${p}:${c}`] - elasticHere.reduce((a, id) => a + fixedOf(id, blocks[id]), 0) * scale * scale)
                    * (pg.masthead ? 1.13 : 1) + (slots.some((s) => s.id === col[0] && s.also) ? 0.07 : 0);
      const story = col.some((id) => blocks[id] && blocks[id].type === "story") || elasticHere.length > 0;
      return { fixed: Math.min(fixed, 1.5), story: story ? Math.max(0, 1 - fixed) : 0, hasStory: story };
    }));
    fill.forEach((cols, p) => cols.forEach((f, c) => {
      const where = `Page ${p + 1}, column ${c + 1}`;
      if (f.hasStory && f.fixed > 1 - STORY_MIN)
        warnings.push(`${where} leaves too little room for its story. Turn off a section or add a page.`);
      else if (!f.hasStory && f.fixed > 1.02)
        warnings.push(`${where} probably overflows at this type size. Turn off a section or add a page.`);
      else if (!f.hasStory && f.fixed < 0.55)
        warnings.push(`${where} will look sparse. Turn on more sections or choose fewer pages.`);
    }));

    // ---- thumbnail geometry for previews: fixed blocks at their size, stories share what's left
    const NICE = { briefs: "Briefs", vocab: "Vocabulary", did_you_know: "Did you know", explainer: "Explainer",
                   analysis: "Big picture", quiz: "Quiz", discussion: kid ? "Talk about it" : "Discuss", sports: "Sports",
                   watchlist: "Watchlist", quote: "Quote", sign_off: "Sign-off", background: "How we got here",
                   timeline: "Timeline", people: "Who's who", sides: "What people think", next: "What happens next" };
    for (const [k, x] of Object.entries(EXTRA_SECTIONS)) NICE[k] = x.name;
    const thumbs = plan.map((pg, p) => ({ masthead: !!pg.masthead, banner: pg.banner ? pg.banner.replace(/<[^>]+>/g, "") : "",
      columns: pg.columns.map((col, c) => {
        const items = col.filter((id) => id !== "rule").map((id) => {
          const b = blocks[id];
          if (b.type === "story") {
            const d = desks.find((x) => x.id === b.desk);
            return { id, kind: id === "lead" ? "lead" : "story", label: d ? titleCase(d.label) : id,
                     graphic: (b.graphics || [])[0] || "", h: 0 };
          }
          return { id, kind: b.type === "feature" ? "feature" : "module", label: NICE[id] || id,
                   h: fixedOf(id, b) * scale * scale };
        });
        items.forEach((x) => { if (ELASTIC.includes(x.id)) x.h = 0; });
        const fixed = items.reduce((a, x) => a + x.h, 0);
        const stories = items.filter((x) => x.kind === "lead" || x.kind === "story" || ELASTIC.includes(x.id));
        stories.forEach((x) => { x.h = Math.max(STORY_MIN, 1 - fixed) / stories.length; });
        return items;
      }) }));

    // ---- reading time
    const words = Math.round(pages * 700 / (scale * scale));
    const minutes = Math.max(2, Math.round(words / age.wpm));

    // ---- YAML
    const id = idSlug(o.id || name) || "my-paper";
    // The name is used exactly as typed. The masthead drops a trailing "Daily"/"Weekly" because the
    // subtitle line carries it; a paper every two days gets no misleading subtitle unless asked for.
    const fullName = name;
    const mastTitle = name.replace(/\s+(Daily|Weekly)$/i, "").toUpperCase();
    const subtitle = o.subtitle !== undefined ? o.subtitle : (o.cadence === "daily" ? "DAILY" : o.cadence === "weekly" ? "WEEKLY" : "");
    const y = [];
    y.push("# yaml-language-server: $schema=../../schema/edition.schema.json");
    y.push(`# Generated by the ygc configurator. Edit freely, then run:`);
    y.push(`#   python -m ygc editions && python -m ygc prompt ${id}`);
    y.push("");
    y.push(`id: ${id}`);
    y.push(`name: ${q(fullName)}`);
    y.push("");
    y.push("masthead:");
    y.push(`  title: ${q(mastTitle)}`);
    if (subtitle) y.push(`  subtitle: ${subtitle}`);
    y.push(`  tagline: ${q(o.tagline || defaultTagline(o.purpose, o.cadence))}`);
    y.push(`  location: ${q(o.location || (o.city || "").trim() || "Washington, USA")}`);
    y.push("");
    y.push("reader:");
    y.push(`  age: ${q(o.exactAge || o.age)}`);
    y.push(`  profile: ${q(o.profile || age.profile)}`);
    y.push(`  reading_level: ${q(age.level)}`);
    y.push("");
    y.push("purpose:");
    for (const l of purpose.lines) y.push(`  - ${q(l)}`);
    y.push("");
    y.push(`voice: ${q(age.voice)}`);
    y.push("");
    y.push("cadence:");
    y.push(`  every_days: ${cad.every_days}`);
    y.push(`  window_hours: ${cad.window_hours}`);
    y.push(`  timezone: ${o.timezone || "America/Los_Angeles"}`);
    y.push("");
    y.push("style:");
    y.push(`  type_scale: ${scale}`);
    y.push("");
    if (kid) {
      y.push("labels:");
      y.push(`  why: "WHY IT MATTERS"`); y.push(`  vocab_title: "New words this time"`);
      y.push("");
    }
    y.push("teaching:");
    y.push(`  repeat_window: ${cad.every_days >= 7 ? 4 : 2}`);
    y.push(`  vocab_today: ${m.vocab ? "true" : "false"}`);
    y.push("");
    y.push("sources_required: true");
    y.push("");
    y.push("desks:");
    for (const d of desks) {
      if (d.id !== "top" && !Object.values(blocks).some((b) => b.desk === d.id)) continue;
      y.push(`  - id: ${d.id}`);
      y.push(`    label: ${q(d.label)}`);
      y.push(`    scope: ${q(d.scope)}`);
      if (d.rules) { y.push("    rules:"); for (const r of d.rules) y.push(`      - ${q(r)}`); }
    }
    y.push("");
    y.push("blocks:");
    for (const [bid, b] of Object.entries(blocks)) {
      const parts = Object.entries(b).filter(([k]) => k !== "questions").map(([k, v]) => `${k}: ${yamlInline(v)}`);
      y.push(`  ${bid}: {${parts.join(", ")}}`);
    }
    y.push("");
    y.push("pages:");
    for (const pg of plan) {
      y.push(pg.masthead ? "  - masthead: true" : `  - banner: ${q(pg.banner)}`);
      y.push("    columns:");
      for (const col of pg.columns) y.push(`      - [${col.join(", ")}]`);
    }
    y.push("");
    y.push("rules:");
    const rules = [
      big ? "One big story per issue: the lead tells it, and every other section explains part of it. Choose it on news value."
          : `${slots.length} stories per issue, one per story block, each chosen on news value against its desk's scope.`,
      depth.rule,
      "Age and purpose change vocabulary, explanation and emphasis, never the standard of accuracy or sourcing.",
      "Graphics are formatting requirements, not selection criteria: choose the story first, then fit the graphic.",
    ];
    for (const t of tones) rules.push(TONES[t].rule);
    if (fav) rules.push(`When ${fav} is in the news in the window, cover it in ${sportDesks.length ? "the matching sports story or " : ""}the sports section. Don't force it when there is no news.`);
    if (unplaced.length) rules.push(`Also follow ${listJoin(unplaced.map((d) => TOPIC_NAME(d, desks)))}: cover them in briefs, or as angles within other stories, when the news warrants.`);
    for (const r of rules) y.push(`  - ${q(r)}`);

    return { errors, warnings, notes, id, yaml: y.join("\n") + "\n", plan, blocks, desks, fill, thumbs,
             stats: { pages, stories: slots.length, words, minutes, desks: big ? 1 : order.length, big } };
  }

  function fixedOf(id, b) {
    if (id === "rule") return FIXED.rule;
    if (!b || b.type === "story") return b && b.also ? 0.07 : 0;
    if (b.type === "vocab") return 0.06 + 0.058 * b.count;
    if (b.type === "briefs") return 0.03 + 0.036 * b.count;
    if (b.type === "watchlist") return 0.04 + 0.026 * b.count;
    if (id === "quiz") return 0.1 + 0.064 * (b.questions || 5);
    if (EXTRA_SECTIONS[id]) return EXTRA_SECTIONS[id].fixed;
    return FIXED[id] != null ? FIXED[id] : 0.3;
  }

  function balance(ids, blocks) {
    // keep order, split where the two columns come closest to even
    const w = ids.map((id) => fixedOf(id, blocks[id]));
    const total = w.reduce((a, b) => a + b, 0);
    let best = 1, bestDiff = Infinity, run = 0;
    for (let i = 0; i < ids.length - 1; i++) {
      run += w[i];
      const diff = Math.abs(total - 2 * run);
      if (diff < bestDiff) { bestDiff = diff; best = i + 1; }
    }
    const left = ids.slice(0, best), right = ids.slice(best);
    const r = right.length ? right : [];
    const k = r.findIndex((id) => ["sports", "watchlist", "quote"].includes(id));
    if (k > 0) r.splice(k, 0, "rule");          // divider between features and the closing run
    return [left, r.length ? r : ["sign_off"]];
  }

  function banner(n, deskIds, desks) {
    const names = [...new Set(deskIds)].map((d) => {
      const n = titleCase(desks.find((x) => x.id === d).label);
      return /^(United |Middle East|Netherlands|Philippines|Gulf)/.test(n) ? "the " + n : n;
    });
    const t = listJoin(names);
    return `<b>PAGE ${n}</b>  •  ${t.charAt(0).toUpperCase()}${t.slice(1)}`;
  }

  function TOPIC_NAME(id, desks) { return titleCase(desks.find((x) => x.id === id).label).replace(/^(United )/, "the $1"); }
  function titleCase(s) {
    return s.toLowerCase().replace(/(^|[\s&-])([a-z])/g, (a, b, c) => b + c.toUpperCase())
            .replace(/\bAnd\b/g, "and").replace(/ & /g, " and ");
  }
  function listJoin(a) { return a.length <= 1 ? (a[0] || "") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1]; }
  function nice(id) { return id.replace(/_/g, " "); }
  function defaultTagline(p, cadence) {
    return { global: "News that helps you think like a global thinker.", school: "The news, connected to what you learn.",
             exam: "The news you need to know, and remember.",
             family: cadence === "daily" ? "The day's news, for everyone at the table." : "The news, for everyone at the table." }[p];
  }
  function yamlInline(v) {
    if (Array.isArray(v)) return `[${v.join(", ")}]`;
    if (v && typeof v === "object") return `{${Object.entries(v).map(([k, x]) => `${k}: ${yamlInline(x)}`).join(", ")}}`;
    if (typeof v === "string") return /^[a-z_]+$/.test(v) ? v : q(v);
    return String(v);
  }

  const api = { generate, AGES, PURPOSES, DEPTHS, TOPICS, GEOS, CADENCE, TONES, EXTRA_SECTIONS };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.YGC = api;
})(typeof window !== "undefined" ? window : globalThis);
