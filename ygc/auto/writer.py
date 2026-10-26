"""Stage 2: write one edition from the shared research, then check, repair and
fact-check until it passes or the attempts run out."""
import json
import os

from .. import checks, prompt, render
from .llm import extract_json, norm_url
from .research import dumps, pool_for_edition, pool_urls

AUTOMATION_RULES = """

---

## Automated production rules (these override anything above about searching)

You are writing from a RESEARCH POOL that a research desk has already verified.
- Use ONLY facts, numbers, names and dates that appear in the research pool. Do not add facts from memory.
  Evergreen sections (Did You Know, explainers, vocabulary definitions) may use well-established general knowledge.
- Every story's `sources` must be copied from the pool's sources for the stories you used: {"outlet", "title", "url"}.
- Never use a story the pool marks "suitable_for_children": false in an edition for readers under 15.
- Enriched key_facts carry short source evidence. Use a concrete detail or a brief mechanism only when it helps this reader understand; keep existing page/word limits. Background must not sound like today's new development. Never invent scenes, dialogue, feelings or comparisons.
- Write in your own words. No quote longer than 15 words.
- Reply with the complete issue as one JSON object and nothing else.
"""

MAX_ROUNDS = int(os.environ.get("YGC_MAX_REPAIR_ROUNDS", 4))

FACTCHECK_SYSTEM = """You are a fact-checker. Compare a newspaper issue with the research pool it was written from.
List every specific claim in the news stories, briefs, watchlist and sports item (names, numbers, dates, places,
who said or did what) that the pool does not support, or that the pool contradicts. Ignore wording, style and
evergreen background facts. Check enriched claims against their evidence passages too; reject exaggeration or missing qualifiers. Reply with JSON only: {"unsupported": [{"where": "blocks.<id>...", "claim": "...", "problem": "..."}]}"""


def _avoid_list(ed, date):
    prev = checks.archived(ed, date, n=ed["teaching"]["repeat_window"] or 1)
    vocab, dyk, heads = [], [], []
    for _, _, iss in prev:
        for b in iss.get("blocks", {}).values():
            if isinstance(b, dict):
                vocab += [v.get("word") for v in b.get("items", []) if isinstance(v, dict) and v.get("word")]
                if b.get("text") and len(b["text"]) > 80:
                    dyk.append(b["text"][:160])
                if b.get("headline"):
                    heads.append(b["headline"])
    return vocab, dyk, heads


def _report_text(r, fit, ask_space=True):
    lines = []
    if r.errors:
        lines.append("ERRORS (must fix):")
        lines += [f"- {e}" for e in r.errors]
    shorts = [m for m in fit if m["over"] <= 0.5 and m["free_lines"] > 4] if ask_space else []
    if shorts:
        lines.append("SPACE (fill with more real reporting from the pool, not padding):")
        lines += [f"- page {m['page']} column {m['column']} ({', '.join(m['blocks'])}) has "
                  f"{m['free_lines']:.0f} empty lines" for m in shorts]
    return "\n".join(lines)


def _source_errors(issue, allowed):
    errs = []
    for bid, b in issue.get("blocks", {}).items():
        if not isinstance(b, dict):
            continue
        for s in b.get("sources", []) or []:
            url = s.get("url", "") if isinstance(s, dict) else str(s)
            if norm_url(url) not in allowed:
                errs.append(f"blocks.{bid}.sources: {url} is not in the research pool; cite only pool sources")
    return errs


def write_edition(client, ed, date, number, volume, pool, path, log=print):
    """Returns (issue_or_None, report_dict)."""
    slice_ = pool_for_edition(pool, ed)
    if not any(g["stories"] for g in slice_.values()):
        return None, {"status": "skipped", "reason": "no verified research for this edition's desks"}
    allowed = pool_urls(slice_)
    vocab, dyk, heads = _avoid_list(ed, date)
    system = prompt.generate(ed) + AUTOMATION_RULES
    user = (f"Write issue No. {number} (volume {volume}) dated {date.isoformat()}.\n"
            f"Set \"date\": \"{date.isoformat()}\", \"issue\": {number}, \"volume\": {volume}.\n"
            + (f"Vocabulary words already used recently (do not reuse): {', '.join(vocab)}\n" if vocab else "")
            + (f"Did You Know facts already used recently (do not reuse):\n" + "\n".join(f"- {x}" for x in dyk) + "\n" if dyk else "")
            + (f"Headlines of the previous issue (a story may continue only as a genuinely new development):\n"
               + "\n".join(f"- {h}" for h in heads[:8]) + "\n" if heads else "")
            + f"\nRESEARCH POOL:\n{dumps(slice_)}")
    msgs = [{"role": "user", "content": user}]
    report = {"rounds": 0, "factcheck_rounds": 0}
    issue, factchecks, asked_space = None, 0, False
    for rnd in range(1, MAX_ROUNDS + 2):
        report["rounds"] = rnd
        _, text, stop = client.create(system, msgs, max_tokens=20000)
        msgs.append({"role": "assistant", "content": text})
        try:
            issue = extract_json(text)
        except ValueError as e:
            feedback = f"Your reply could not be read as JSON ({e}). Reply with the complete issue JSON only."
            msgs.append({"role": "user", "content": feedback}); continue
        issue.update({"edition": ed["id"], "date": date.isoformat(), "issue": number, "volume": volume})
        r = checks.check_issue(ed, issue, path, archive=False, as_of=date)
        r.errors += _source_errors(issue, allowed)
        try:
            fit = render.measure(ed, issue) if not checks.unbuildable(r) else []
        except Exception:
            fit = []
        # Errors always block. Short columns get one request to fill them, then stop blocking.
        feedback = _report_text(r, fit, ask_space=not asked_space)
        if "SPACE" in feedback:
            asked_space = True
        if not feedback:
            # passes the mechanical checks: now an independent fact-check against the pool
            if factchecks >= 2:
                break
            factchecks += 1
            report["factcheck_rounds"] = factchecks
            _, ftext, _ = client.create(FACTCHECK_SYSTEM, [{"role": "user", "content":
                f"RESEARCH POOL:\n{dumps(slice_)}\n\nISSUE:\n{json.dumps(issue, ensure_ascii=False)}"}],
                max_tokens=6000, model=os.environ.get("YGC_CHECK_MODEL") or None)
            try:
                bad = extract_json(ftext).get("unsupported", [])
            except ValueError:
                bad = []
            if not bad:
                report["status"] = "passed"
                return issue, report
            feedback = "FACT-CHECK found claims the research pool does not support. Fix or remove each:\n" + \
                       "\n".join(f"- {b.get('where')}: \"{b.get('claim')}\" ({b.get('problem')})" for b in bad)
        log(f"    round {rnd}: {feedback.count(chr(10)) + 1} issue(s) to fix")
        if rnd > MAX_ROUNDS:
            break
        msgs.append({"role": "user", "content": feedback + "\n\nReply with the complete corrected issue JSON only."})
    report.update(status="failed", last_feedback=feedback[:2000] if issue else "no valid JSON")
    return None, report
