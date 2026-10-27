"""Generate an edition's AI system prompt from its edition.yaml.

The prompt is a build product: edit edition.yaml or docs/CRAFT_RULES.md, then
regenerate. CI fails if a committed PROMPT.md is out of date.
"""
import json
import os
import re

from .edition import ROOT, desk, placed_blocks
from . import skeleton

CRAFT = os.path.join(ROOT, "docs", "CRAFT_RULES.md")
RULE_RE = re.compile(r"^###\s+Rule:\s*(.+)$", re.M)


def craft_rules():
    return RULE_RE.findall(open(CRAFT, encoding="utf-8").read())


def _graphic_note(g):
    return {"map": "a map (two land areas split by water: pick the water geography that "
                   "genuinely matters to the story)",
            "illustration": "an illustration (choose a motif from the fixed list)",
            "chart": "a 2-4 bar chart built only from real, sourced numbers"}[g]


def generate(ed, chat=None):
    """The edition's system prompt. With chat={"date": "YYYY-MM-DD", "number": n} it is
    written for pasting into a chatbot: the date is stated, web search is required, and
    the reply is checked by the builder page instead of `python -m ygc check`."""
    r, c = ed["reader"], ed["cadence"]
    npages = len(ed["pages"])
    L = []
    if not chat:
        L.append(f"# System prompt: Editor-in-Chief, {ed['name']}\n")
        L.append(f"<!-- Generated from editions/{ed['id']}/edition.yaml by "
                 f"`python -m ygc prompt {ed['id']}`. Edit the YAML, not this file. -->\n")
        L.append("Paste everything below the line into any AI tool that can search the web.\n")
        L.append("---\n")
    art = "an" if str(npages)[0] == "8" or npages in (11, 18) else "a"
    pages_word = "one-page" if npages == 1 else f"{npages}-page"
    art = "a" if npages == 1 else art
    L.append(f"You are the Editor-in-Chief of *{ed['name']}*, {art} {pages_word} printed "
             f"newspaper. You are a world-class educator and journalist in one: you are not "
             f"summarising the news, you are training a thinker.\n")
    L.append(f"**Reader.** Age {r['age']}. {r['profile']}"
             + (f" Reading level: {r['reading_level']}" if r.get("reading_level") else "") + "\n")
    L.append("**Purpose.** Every issue should build:")
    L += [f"- {p}" for p in ed["purpose"]]
    L.append("")
    L.append(f"**Voice.** {ed['voice']}\n")
    every = "every day" if c["every_days"] == 1 else f"every {c['every_days']} days"
    if chat:
        import datetime as dt
        day = dt.date.fromisoformat(chat["date"])
        L.append(f"**Today.** Today is {day.strftime('%A')} {day.day} {day.strftime('%B %Y')}. Write issue "
                 f"No. {chat['number']}, dated {chat['date']}, covering the last {c['window_hours']} hours of news. "
                 f"One issue comes out {every}.\n")
        L.append(f"**Research first.** Search the web for the news of the last {c['window_hours']} hours before you write anything. Every fact, "
                 "number, name and date must come from a page you found in this search, never from memory. "
                 "If you cannot search the web, reply only: \"I can't search the web, so I can't write today's "
                 "paper.\" and stop.\n")
    else:
        L.append(f"**Cadence.** One issue {every}, covering the last {c['window_hours']} hours "
                 f"of news. Take today's date from the device clock in {c['timezone']}, never "
                 f"from this prompt. The issue number is the previous issue's number plus one.\n")

    L.append("**Stories.** Choose each on news value alone, then fit its graphic. "
             "Read the primary articles, not just search snippets, and list every URL "
             "you used in the story's `sources`.\n")
    if ed.get("lens"):
        L.append(f"**This paper's angle.** {ed['lens'].strip()} When a story also runs in other papers the same "
                 "day, tell it through this angle and in your own words, using facts from your research; the "
                 "biggest story can still lead.\n")
    for bid in placed_blocks(ed):
        cfg = ed["blocks"][bid]
        if cfg["type"] != "story":
            continue
        d = desk(ed, cfg["desk"])
        parts = [f"- **`{bid}`** — {d['label']}. {d['scope']}"]
        for rule in d.get("rules", []):
            parts.append(f"  - {rule}")
        need = [_graphic_note(g) for g in cfg.get("graphics", [])]
        lab = {k: ed["labels"][k].capitalize() for k in ("why", "connect", "analyst")}
        extras = {"why": f'"{lab["why"]}"',
                  "connect": f'"{lab["connect"]}" (link to history, geography, economics or sport)',
                  "analyst": f'"{lab["analyst"]}" (questions only, never answers)'}
        need += [extras[x] for x in cfg.get("extras", [])]
        if cfg.get("also"):
            need.append(f"{cfg['also']['count']} one-line \"{cfg['also'].get('title', 'also')}\" items")
        if need:
            parts.append(f"  - Carries: {'; '.join(need)}.")
        L += parts
    L.append("")

    others = []
    for bid in placed_blocks(ed):
        cfg = ed["blocks"][bid]
        t = cfg["type"]
        if t == "feature":
            others.append(f"- **`{bid}`** — {cfg.get('label', bid)}: {cfg.get('brief', 'a short feature')}")
        elif t == "briefs":
            others.append(f"- **`{bid}`** — {cfg['count']} one-sentence briefs, each starting with a country or topic.")
        elif t == "vocab":
            today = (" Each definition then shows the word in this issue's news after "
                     "\"Today:\".") if ed["teaching"]["vocab_today"] else ""
            others.append(f"- **`{bid}`** — {cfg['count']} vocabulary words drawn from this issue.{today}")
        elif t == "did_you_know":
            others.append(f"- **`{bid}`** — one surprising, true fact connected to the issue.")
        elif t == "sports":
            others.append(f"- **`{bid}`** — one sports item; only this field may use <b>bold</b> tags.")
        elif t == "watchlist":
            others.append(f"- **`{bid}`** — {cfg['count']} things to watch before the next issue.")
        elif t == "quote":
            others.append(f"- **`{bid}`** — one short closing line (original, or attributed in `by`).")
    if others:
        L.append("**Other sections.**")
        L += others
        L.append("")
    if not chat:
        from .skeleton import play_counts
        nq, nf = play_counts(ed)
        L.append(f"**Play (online only, never printed).** Fill `play` for the website's games, using only facts in "
                 f"this issue and words the reader knows. `quiz`: {nq} multiple-choice questions a reader can answer "
                 f"from this issue alone, each with exactly 3 different `options`, `answer` the position (0, 1 or 2) of "
                 f"the right one (vary it), `why` one short sentence saying what the paper says, and `story` the id of "
                 f"the story it comes from. `fact_or_fiction`: {nf} short claims about this issue, at least one true "
                 f"and one not true (`true`: true or false), each with `why` and `story`. A claim that isn't true "
                 f"changes one detail of the story; it is never a scary or silly invention. `where`, for the maps: one "
                 f"entry for each story that happens in a particular place (delete the others): `place` as a child "
                 f"would name it (a city, sea or region, e.g. \"Strait of Hormuz\"), `lat` and `lon` of that place in "
                 f"decimal degrees, and `countries`, the countries the story is about, in plain English names. "
                 f"`numbers`, for Guess the number: 2 questions whose `answer` is a number a story gives (as the "
                 f"story writes it: 16 for \"16 million\", with `unit` \"million\"), with `prefix` (\"$\", \"Rs \" or "
                 f"empty) and `unit` (\"km\", \"years\", \"%\"...) for showing it, a slider from `min` to `max` "
                 f"that leaves room on both sides of the answer, `why` one sentence saying what the number means, and "
                 f"`story`. Pick numbers worth guessing (sizes, prices, distances, counts), not dates.\n")
        from . import analyst
        if analyst.wants(ed):
            L.append(analyst.PROMPT)
        if skeleton.wants_easy(ed):
            L.append("**Easier versions (online only).** Fill `play.easy` with an easier version of every story, for "
                     "a reader who finds it hard: a plain `headline` and a `body` of 2 to 4 short paragraphs (60 to "
                     "170 words), as you'd write for a 9-to-11-year-old. Short sentences (14 words on average), one "
                     "idea each; explain any hard word or idea in passing; keep the most important facts and drop the "
                     "rest. Use only facts already in that story: every number must also appear in the story "
                     "(rounding is fine, like $110 for $109.86).\n")
        from . import brief
        if brief.wants(ed):
            L.append(brief.PROMPT)
        L.append("**Ongoing stories (optional).** If a story continues one of the site's big ongoing stories "
                 "(a file in `threads/`, such as `yemen-war`), add `\"threads\": {\"<story id>\": \"<thread id>\"}` "
                 "at the top level of the issue. The printed story then ends with a one-line pointer to \"The story so "
                 "far\" on Read & Play, so leave room for it.\n")
    n = ed["teaching"]["repeat_window"]
    types = {ed["blocks"][b]["type"] for b in placed_blocks(ed)}
    things = [x for t, x in (("vocab", "Vocabulary words"), ("did_you_know", "Did You Know facts")) if t in types]
    if n and things and chat:
        L.append(f"**No repeats.** If earlier issues of this paper appear in this conversation, "
                 f"{' and '.join(things).lower()} never repeat theirs. Stories may continue if still important.\n")
    elif n and things:
        L.append(f"**No repeats.** {' and '.join(things)} never repeat anything from the last {n} "
                 f"issues. Stories may continue if still important.\n")
    if ed.get("rules"):
        L.append("**Edition rules.**")
        L += [f"- {x}" for x in ed["rules"]]
        L.append("")
    L.append("**Craft rules.**")
    for x in craft_rules():
        if chat and "device clock" in x:       # a chatbot can't read the clock: the date is stated above
            x = f"Use the date stated above, {chat['date']}, never one from memory or an assumption."
        L.append(f"- {x}")
    L.append("")
    if chat:
        L.append("**Output.** Reply with only one JSON object in a single ```json code block, with "
                 "nothing before or after it, shaped exactly like this skeleton: fill every empty "
                 "string, replace the zeros and keep every key. Each source may be a URL or "
                 "{\"outlet\", \"title\", \"url\"}.\n")
        sk = skeleton.make(ed, date=chat["date"], number=chat["number"], play=False)
    else:
        L.append("**Output.** Reply with only one JSON object, shaped exactly like this skeleton: "
                 "fill every empty string, replace the zeros, keep every key, and set `date` and "
                 "`issue`. Each source may be a URL or {\"outlet\", \"title\", \"url\"}.\n")
        sk = skeleton.make(ed, date="YYYY-MM-DD", number=0)
    L.append("```json\n" + json.dumps(sk, ensure_ascii=False, indent=2) + "\n```\n")
    if chat:
        L.append("Use only characters the PDF fonts can print: plain English punctuation plus "
                 "• — “ ” é ü. No ₹, ł or Devanagari, and never `…`. Length is set by space, not "
                 "character counts. A grown-up will paste your reply into a page that measures every "
                 "column of the printed paper. If they send you back a list of fixes, make every fix and "
                 "reply with the complete corrected JSON.")
    else:
        L.append("Use only characters the PDF fonts can print: plain English punctuation plus "
                 "• — “ ” é ü. No ₹, ł or Devanagari, and never `…`. Length is set by space, "
                 "not character counts: if you can run code, the issue is done only when "
                 f"`python -m ygc check editions/{ed['id']}/issues/<year>/<date>.json` prints "
                 "PASS and you have looked at every page image.")
    return "\n".join(L) + "\n"


def path_for(ed):
    return os.path.join(ed["_dir"], "PROMPT.md")
