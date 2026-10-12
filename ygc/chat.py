"""Write a paper with your own chatbot.

The builder page runs this module in the browser (Pyodide): it writes the
instructions a parent pastes into ChatGPT, Claude or Gemini, then checks the
chatbot's reply with the same checks as every published issue and builds the
same PDF. A reply that fails gets a list of fixes to paste back.
"""
import datetime as dt
import json
import os

from . import checks, edition, poster, prompt, render
from .auto.llm import extract_json

FREE_LINES = 6          # a column with more empty lines than this is worth filling


def install(yaml_text):
    """Save an edition file from the builder and load it (validated) like any other."""
    import yaml
    eid = (yaml.safe_load(yaml_text) or {}).get("id")
    if not eid:
        raise edition.EditionError("the edition file has no id")
    d = edition.edition_dir(eid)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "edition.yaml"), "w", encoding="utf-8") as f:
        f.write(yaml_text)
    return edition.load(eid)


def instructions(ed, date, number=1):
    return prompt.generate(ed, chat={"date": date, "number": number})


def _parse(text):
    try:
        return extract_json(text), None
    except (ValueError, json.JSONDecodeError) as e:
        if "can't search the web" in text.lower() or "cannot search the web" in text.lower():
            return None, ("The chatbot says it can't search the web. Turn on web search (or use a chatbot "
                          "that has it) and ask again: a paper written from memory would be out of date.")
        return None, (f"This doesn't look like the chatbot's paper ({e}). Copy its whole reply, "
                      "including the code block, and paste it again.")


def _fix_message(kind, errors, name):
    items = "\n".join(f"- {e}" for e in errors)
    return (f"The {kind} doesn't pass the printing checks for {name} yet. Make every fix below, keep "
            f"everything else the same, and reply with the complete corrected JSON only.\n\n{items}")


def check_paper(ed, text, date, number=1, out_pdf=None):
    """Check a chatbot's reply. Returns a dict the page shows:
    ok, problem (a sentence for the parent), errors, fix (text to paste back to the chatbot),
    fill (optional text asking for fuller columns), pdf (path) and issue (the JSON, cleaned)."""
    issue, problem = _parse(text)
    if problem:
        return {"ok": False, "problem": problem, "errors": [], "fix": ""}
    issue.update({"edition": ed["id"], "date": date, "issue": int(number), "volume": issue.get("volume") or 1})
    path = os.path.join(checks.issues_dir(ed), date[:4], f"{date}.json")
    r = checks.check_issue(ed, issue, path, archive=False, as_of=dt.date.fromisoformat(date))
    res = {"ok": r.ok, "errors": r.errors, "issue": json.dumps(issue, ensure_ascii=False, indent=2),
           "problem": "", "fix": "", "fill": ""}
    if not r.ok:
        res["problem"] = (f"{len(r.errors)} thing{'s' if len(r.errors) != 1 else ''} to fix before it can print. "
                          "Copy the fix list below into the chatbot, then paste its new reply here.")
        res["fix"] = _fix_message("newspaper", r.errors, ed["name"])
        return res
    try:
        gaps = [m for m in render.measure(ed, issue) if m["free_lines"] > FREE_LINES]
    except Exception:
        gaps = []
    if gaps:
        res["fill"] = ("The paper prints, but some columns have empty space. If you'd like it fuller, add "
                       "sourced detail to the stories or sections in these columns and reply with the "
                       "complete JSON:\n\n" + "\n".join(
                           f"- page {m['page']} column {m['column']} ({', '.join(m['blocks'])}): about "
                           f"{m['free_lines']:.0f} empty lines" for m in gaps))
    res["pdf"] = render.build(ed, issue, out_pdf or f"/tmp/{ed['id']}_{date}.pdf")
    return res


# ------------------------------------------------------------------ the Big Question poster
POSTER_RULES = """

RULES FOR THIS CHAT (these override anything above about commands or files):
- Today is {today}. Search the web for this week's news first. Every news fact, name, place and number must
  come from a page you found in this search, never from memory. Evergreen science in try_it may use
  well-established facts. If you cannot search the web, reply only: "I can't search the web, so I can't
  write this week's poster." and stop.
- Write for {reader}.
- "sources" is a list of the URLs (strings) of the pages your facts came from.
- hero.motif and every steps[].motif must be one of: {motifs}.
- Use only characters the PDF fonts can print: plain English punctuation plus • — “ ” é ü. No arrows, no "…".
- Reply with the poster JSON only, in a single ```json code block, shaped exactly like this. If the grown-up
  sends back a list of fixes, make every fix and reply with the complete corrected JSON.
```json
{shape}
```"""


def _without_section(md, heading):
    start = md.find(heading)
    if start < 0:
        return md
    nxt = md.find("\n## ", start + len(heading))
    return md[:start] + (md[nxt + 1:] if nxt >= 0 else "")


def poster_instructions(ed, date):
    guide = open(os.path.join(edition.ROOT, "docs", "POSTERS.md"), encoding="utf-8").read()
    guide = _without_section(guide, "## Automatic posters")
    day = dt.date.fromisoformat(date)
    return guide + POSTER_RULES.format(
        today=f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}",
        reader=f"ages {ed['reader']['age']}: {ed['reader']['profile']}",
        motifs=", ".join(poster.HERO_MOTIFS),
        shape=json.dumps(poster.skeleton(ed, date), ensure_ascii=False, indent=1))


def check_poster(ed, text, date, out_pdf=None):
    spec, problem = _parse(text)
    if problem:
        return {"ok": False, "problem": problem, "errors": [], "fix": ""}
    spec.update({"edition": ed["id"], "date": date})
    r = poster.check(ed, spec, poster.path_for(ed, date))
    res = {"ok": r.ok, "errors": r.errors, "problem": "", "fix": "", "fill": ""}
    if not r.ok:
        res["problem"] = (f"{len(r.errors)} thing{'s' if len(r.errors) != 1 else ''} to fix before it can print. "
                          "Copy the fix list below into the chatbot, then paste its new reply here.")
        res["fix"] = _fix_message("poster", r.errors, ed["name"])
        return res
    res["pdf"] = poster.build(ed, spec, out_pdf or f"/tmp/{ed['id']}_{date}_poster.pdf")
    return res
