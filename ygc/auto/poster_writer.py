"""Stage 3 (optional): the week's "Big Question" poster, written from the same
research as the issue it accompanies, checked like an issue, published only if
it passes. A failed poster never affects the paper."""
import json
import os

from .. import edition, poster
from .llm import extract_json, norm_url
from .research import dumps, pool_for_edition, pool_urls
from .writer import FACTCHECK_SYSTEM, MAX_ROUNDS

GUIDE = os.path.join(edition.ROOT, "docs", "POSTERS.md")

RULES = """

AUTOMATION RULES (these override anything above about commands or files):
- You are writing one poster as JSON. Use ONLY facts in the RESEARCH POOL for anything about the news:
  figures, names, places and dates. Evergreen science in try_it may use well-established facts.
- Build the poster on one story the accompanying issue covers (prefer its lead), and never on a story
  marked "suitable_for_children": false.
- "sources" is a list of URL strings, each copied exactly from a "url" in the pool's sources.
- hero.motif and every steps[].motif must be one of: {motifs}.
- Use only characters the PDF fonts can print: plain English punctuation plus • — “ ” é ü. No arrows, no "…".
- Reply with the poster JSON only, shaped exactly like:
{shape}"""


def _guide():
    with open(GUIDE, encoding="utf-8") as f:
        return f.read()


def _issue_summary(issue):
    lines = []
    for bid, b in (issue or {}).get("blocks", {}).items():
        if isinstance(b, dict) and b.get("headline"):
            lines.append(f"- {bid}: {b['headline']}" + (f" ({b['deck']})" if b.get("deck") else ""))
    return "\n".join(lines)


def _last_guess(ed, date):
    for d, path in poster.posters_of(ed):
        if d < date:
            try:
                return d, json.load(open(path, encoding="utf-8")).get("next_week", "")
            except (OSError, ValueError):
                return None
    return None


def _source_errors(spec, allowed):
    urls = [s.get("url", "") if isinstance(s, dict) else str(s) for s in spec.get("sources", []) or []]
    return [f"sources: {u} is not in the research pool; cite only pool sources" for u in urls
            if norm_url(u) not in allowed]


def write_poster(client, ed, date, issue, pool, log=print):
    """Returns (poster_or_None, report_dict). Never raises for a bad draft."""
    day = date.isoformat()
    slice_ = pool_for_edition(pool, ed)
    allowed = pool_urls(slice_)
    if not allowed:
        return None, {"status": "skipped", "reason": "no verified research for this paper"}
    shape = json.dumps(poster.skeleton(ed, day), ensure_ascii=False, indent=1)
    system = _guide() + RULES.format(motifs=", ".join(poster.HERO_MOTIFS), shape=shape)
    prev = _last_guess(ed, day)
    user = (f"Write the Big Question poster for {ed['name']} dated {day}.\n"
            f"Set \"edition\": \"{ed['id']}\", \"date\": \"{day}\".\n"
            f"This week's issue covers:\n{_issue_summary(issue)}\n"
            + (f"\nLast week's poster ({prev[0]}) asked children to guess: \"{prev[1]}\" "
               "If this week's research answers it, open \"happened\" by checking the guess.\n"
               if prev and prev[1] else "")
            + f"\nRESEARCH POOL:\n{dumps(slice_)}")
    path = poster.path_for(ed, day)
    msgs = [{"role": "user", "content": user}]
    report = {"rounds": 0, "factcheck_rounds": 0}
    spec, feedback, factchecks = None, "", 0
    for rnd in range(1, MAX_ROUNDS + 2):
        report["rounds"] = rnd
        _, text, _ = client.create(system, msgs, max_tokens=6000)
        msgs.append({"role": "assistant", "content": text})
        try:
            spec = extract_json(text)
        except ValueError as e:
            spec = None
            feedback = f"Your reply could not be read as JSON ({e})."
        if spec is not None:
            spec.update({"edition": ed["id"], "date": day})
            r = poster.check(ed, spec, path)
            errors = r.errors + _source_errors(spec, allowed)
            feedback = "ERRORS (each must be fixed):\n" + "\n".join(f"- {e}" for e in errors) if errors else ""
            if not feedback:
                if factchecks >= 2:      # published only after a clean fact-check
                    break
                factchecks += 1
                report["factcheck_rounds"] = factchecks
                _, ftext, _ = client.create(FACTCHECK_SYSTEM, [{"role": "user", "content":
                    f"RESEARCH POOL:\n{dumps(slice_)}\n\nPOSTER (try_it may use well-established "
                    f"everyday science):\n{json.dumps(spec, ensure_ascii=False)}"}],
                    max_tokens=4000, model=os.environ.get("YGC_CHECK_MODEL") or None)
                try:
                    bad = extract_json(ftext).get("unsupported", [])
                except ValueError:
                    bad = []
                if not bad:
                    report["status"] = "passed"
                    return spec, report
                feedback = "FACT-CHECK found claims the research pool does not support. Fix or remove each:\n" + \
                           "\n".join(f"- {b.get('where')}: \"{b.get('claim')}\" ({b.get('problem')})" for b in bad)
        log(f"    poster round {rnd}: {feedback.count(chr(10)) + 1} issue(s) to fix")
        if rnd > MAX_ROUNDS:
            break
        msgs.append({"role": "user", "content": feedback + "\n\nReply with the complete corrected poster JSON only."})
    report.update(status="failed", last_feedback=feedback[:2000] or "no valid JSON")
    return None, report
