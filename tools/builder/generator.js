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
    "15-18": { label: "Ages 15–18", scale: 0.95, wpm: 220, vocab: 4, kid: false,
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
    local:     { label: "LOCAL", name: "Local community news", local: true },
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
    if (errors.length) return { errors, warnings };

    // ---- modules: purpose defaults, then the reader's overrides, then age limits
    const m = Object.assign({}, purpose.modules, o.modules || {});
    if (topics.includes("sports")) m.sports = true;
    if (age.vocab === 0) m.vocab = false;
    if (o.purpose === "exam") m.quiz = true;

    // ---- desks
    const desks = [];
    const worldWanted = geos.includes("World") || topics.includes("world");
    const where = geos.filter((g) => g !== "World");
    const coverage = [worldWanted ? "the world" : null, ...where].filter(Boolean);
    desks.push({ id: "top", label: "TOP STORY",
      scope: `The single most important story of the window for this reader${coverage.length ? `, from ${listJoin(coverage)}` : ""}.`,
      rules: ["If a running story is still the biggest, it leads again, written as the new development."] });
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
        desks.push({ id: "local", label: "LOCAL", scope: `The most important community story from around ${o.location || "the reader's home"}.` });
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
    tail.push(["briefs", { type: "briefs", count: briefsCount }]);
    if (m.vocab && vocabCount) tail.push(["vocab", { type: "vocab", count: vocabCount }]);
    if (m.dyk) tail.push(["did_you_know", { type: "did_you_know" }]);
    const featurePage = pages >= 7;
    if (m.explainer || featurePage || (o.depth === "deep" && pages >= 6)) tail.push(["explainer", { type: "feature", label: kid ? "HOW IT WORKS" : "EXPLAINER",
      brief: "Background behind one of this issue's stories, from well-established facts.", sources: false }]);
    if (featurePage || o.depth === "deep" && pages >= 4) tail.push(["analysis", { type: "feature", label: "THE BIG PICTURE",
      brief: "Analysis connecting several of this issue's stories, with the evidence and the strongest competing perspectives." }]);
    const quizN = o.purpose === "exam" || pages >= 6 ? 8 : 5;
    if (m.quiz) tail.push(["quiz", { type: "feature", label: "QUIZ",
      brief: `${quizN} multiple-choice questions on this issue, with the answers at the end.`, sources: false, questions: quizN }]);
    if (m.discussion) tail.push(["discussion", { type: "feature", label: kid ? "TALK ABOUT IT" : "DISCUSS",
      brief: "Three open questions about this issue for discussion at home or in class. Questions only, never answers.", sources: false }]);
    if (m.sports) tail.push(["sports", { type: "sports" }]);
    if (m.watchlist) tail.push(["watchlist", { type: "watchlist", count: pages >= 4 ? 3 : 2, title: cad.watch }]);
    if (m.quote) tail.push(["quote", { type: "quote" }]);
    const signText = kid ? `Keep exploring. ${cad.see}` : `You are not just reading the news — you are learning to think about it. ${cad.see}`;
    tail.push(["sign_off", { type: "sign_off", text: signText }]);
    for (const [id, b] of tail) blocks[id] = b;
    const tailIds = tail.map((t) => t[0]);

    // A closing page whose sections fill under one column gets one more story instead of white space.
    const ELASTIC = ["explainer", "analysis"];
    const tailFixedOn = (ids) => ids.reduce((a, id) => a + (ELASTIC.includes(id) ? 0.3 : fixedOf(id, blocks[id])), 0) * age.scale * age.scale;
    const closingIds = tailIds.filter((id) => !(pages >= 7 && ELASTIC.includes(id)));
    const tailSize = tailFixedOn(closingIds);
    const closingStories = pages < 3 ? 0 : tailSize < 0.55 ? 2 : tailSize < 0.95 ? 1 : 0;

    // ---- story slots
    const nStories = storyCount(pages) + closingStories;
    const slots = [{ id: "lead", desk: "top", size: "lead" }];
    const storyBlocks = () => slots.forEach((x) => { if (!blocks[x.id]) blocks[x.id] = { type: "story", desk: x.desk }; });
    const used = {};
    for (let i = 0; slots.length < nStories; i++) {
      const d = order[i % order.length];
      used[d] = (used[d] || 0) + 1;
      slots.push({ id: used[d] > 1 ? `${d}_${used[d]}` : d, desk: d, size: pages === 1 ? "compact" : "standard" });
    }
    const notes = [];
    const unplaced = order.filter((d) => !slots.some((s) => s.desk === d));
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
    const plan = [];
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
      const sq = age.scale * age.scale, cap = 1 - STORY_MIN;
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
    const colOf = {}, colFixed = {};
    plan.forEach((pg, p) => pg.columns.forEach((col, c) => {
      const f = col.reduce((a, id) => a + fixedOf(id, blocks[id]), 0) * age.scale * age.scale;
      col.forEach((id) => { colOf[id] = `${p}:${c}`; });
      colFixed[`${p}:${c}`] = f;
    }));
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
      const fixed = (colFixed[`${p}:${c}`] - elasticHere.reduce((a, id) => a + fixedOf(id, blocks[id]), 0) * age.scale * age.scale)
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
                   watchlist: "Watchlist", quote: "Quote", sign_off: "Sign-off" };
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
                   h: fixedOf(id, b) * age.scale * age.scale };
        });
        items.forEach((x) => { if (ELASTIC.includes(x.id)) x.h = 0; });
        const fixed = items.reduce((a, x) => a + x.h, 0);
        const stories = items.filter((x) => x.kind === "lead" || x.kind === "story" || ELASTIC.includes(x.id));
        stories.forEach((x) => { x.h = Math.max(STORY_MIN, 1 - fixed) / stories.length; });
        return items;
      }) }));

    // ---- reading time
    const words = Math.round(pages * 700 / (age.scale * age.scale));
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
    y.push(`  location: ${q(o.location || "Washington, USA")}`);
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
    y.push(`  type_scale: ${age.scale}`);
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
      `${slots.length} stories per issue, one per story block, each chosen on news value against its desk's scope.`,
      depth.rule,
      "Age and purpose change vocabulary, explanation and emphasis, never the standard of accuracy or sourcing.",
      "Graphics are formatting requirements, not selection criteria: choose the story first, then fit the graphic.",
    ];
    if (unplaced.length) rules.push(`Also follow ${listJoin(unplaced.map((d) => TOPIC_NAME(d, desks)))}: cover them in briefs, or as angles within other stories, when the news warrants.`);
    for (const r of rules) y.push(`  - ${q(r)}`);

    return { errors, warnings, notes, id, yaml: y.join("\n") + "\n", plan, blocks, desks, fill, thumbs,
             stats: { pages, stories: slots.length, words, minutes, desks: order.length } };
  }

  function fixedOf(id, b) {
    if (id === "rule") return FIXED.rule;
    if (!b || b.type === "story") return b && b.also ? 0.07 : 0;
    if (b.type === "vocab") return 0.06 + 0.058 * b.count;
    if (b.type === "briefs") return 0.03 + 0.036 * b.count;
    if (b.type === "watchlist") return 0.04 + 0.026 * b.count;
    if (id === "quiz") return 0.1 + 0.064 * (b.questions || 5);
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

  const api = { generate, AGES, PURPOSES, DEPTHS, TOPICS, GEOS, CADENCE };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.YGC = api;
})(typeof window !== "undefined" ? window : globalThis);
