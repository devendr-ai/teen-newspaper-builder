"""python -m ygc <command>

  editions                          list editions
  new <edition> [--date D]          start today's issue from a skeleton
  check <issue.json> [--archive] [--pool P]   the quality gate: content, fit, build, page images
  build <issue.json>                build the PDF only (no checks)
  prompt <edition> [--stdout]       regenerate the edition's PROMPT.md
  create-edition <new-id> --from <id>   copy an edition as a starting point
  migrate <v3.json> --edition <id>  convert a template-v3 issue to this format
  due [--date D] [--json]           what is due today: issue numbers, files, research desks, words to avoid
  auto [--dry-run] [--only id,id]   research, write, check and save every due edition (needs ANTHROPIC_API_KEY)
  site [--out _site]                build the website: every edition, latest PDFs, archives, RSS
  new-poster <edition> [--date D]   start a "Big Question" poster from a skeleton
  poster <poster.json> [--pool P]   check a poster and build its PDF and page image

  --pool data/pools/<date>.json also fails any source URL that is not in that research pool.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

import yaml

from . import checks, edition, migrate, prompt, render, skeleton

OUT = os.path.join(edition.ROOT, "build")


def _load_issue(path):
    issue = json.load(open(path, encoding="utf-8"))
    if "edition" not in issue:
        sys.exit(f"{path}: no 'edition' key. Old template-v3 file? Convert it with "
                 f"`python -m ygc migrate {path} --edition <id>`.")
    return issue, edition.load(issue["edition"])


def _pdf_name(ed, issue):
    return f"{ed['id']}_{issue['date']}"


def _render_pngs(pdf, stem, out):
    if not shutil.which("pdftoppm"):
        return False
    subprocess.run(["pdftoppm", "-png", "-r", "110", pdf, os.path.join(out, stem + "_page")],
                   check=False)
    return True


def cmd_editions(a):
    for eid in edition.list_editions():
        try:
            ed = edition.load(eid)
            n = len(ed['pages'])
            print(f"{eid:28} {n} page{'s' if n != 1 else ''} · age {ed['reader']['age']} · "
                  f"desks: {', '.join(d['id'] for d in ed['desks'])} · "
                  f"every {ed['cadence']['every_days']}d")
        except edition.EditionError as e:
            print(f"{eid:28} INVALID\n{e}")


def cmd_new(a):
    ed = edition.load(a.edition)
    d = dt.date.fromisoformat(a.date) if a.date else checks.today(ed)
    prev = checks.archived(ed, d, n=1)
    number = prev[0][2]["issue"] + 1 if prev else 1
    volume = prev[0][2].get("volume", 1) if prev else 1
    path = os.path.join(checks.issues_dir(ed), str(d.year), f"{d.isoformat()}.json")
    if os.path.exists(path):
        sys.exit(f"{path} already exists")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(skeleton.make(ed, d.isoformat(), number, volume),
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"created {path}  (No. {number}{'' if prev else ', the first in the archive'})")
    print(f"next: give editions/{ed['id']}/PROMPT.md to an AI tool with web search, save the JSON it\n"
          f"      returns over this file, then run: python -m ygc check {os.path.relpath(path, edition.ROOT)}")


def _pool_errors(pool_file, urls, where):
    """Source URLs missing from a saved research pool (data/pools/<date>.json)."""
    from .auto.llm import norm_url
    from .auto.research import pool_urls
    allowed = pool_urls(json.load(open(pool_file, encoding="utf-8")))
    return [f"{w}: {u} is not in the research pool; cite only pool sources"
            for w, u in zip(where, urls) if norm_url(u) not in allowed]


def cmd_check(a):
    issue, ed = _load_issue(a.issue)
    r = checks.check_issue(ed, issue, a.issue, archive=a.archive)
    if a.pool:
        found = [(f"blocks.{bid}.sources", s.get("url", "") if isinstance(s, dict) else str(s))
                 for bid, b in issue.get("blocks", {}).items() if isinstance(b, dict)
                 for s in b.get("sources", []) or []]
        r.errors += _pool_errors(a.pool, [u for _, u in found], [w for w, _ in found])
    pdf = None
    if a.no_build:
        pass
    elif checks.unbuildable(r):
        r.note("PDF not built yet: fill in the fields above first")
    else:
        os.makedirs(a.out, exist_ok=True)
        stem = _pdf_name(ed, issue)
        try:
            pdf = render.build(ed, issue, os.path.join(a.out, stem + ".pdf"))
            from pypdf import PdfReader
            n = len(PdfReader(pdf).pages)
            if n != len(ed["pages"]):
                r.err(f"PDF has {n} pages; the edition plans {len(ed['pages'])}")
            if _render_pngs(pdf, stem, a.out):
                r.note(f"now LOOK at build/{stem}_page-*.png: checks cannot judge whether it reads well")
            else:
                r.note("pdftoppm not found (install poppler) — page images not rendered")
        except Exception as e:
            r.err(f"the PDF could not be built: {e}. Fix the errors above and run check again")
    n = len(ed["pages"])
    print(f"\n{a.issue}  [{ed['name']}, {n} page{'s' if n != 1 else ''}]")
    try:
        if checks.unbuildable(r):
            raise ValueError
        for m in render.measure(ed, issue):
            state = (f"OVER {m['over']:.0f}pt" if m["over"] > 0.5
                     else f"{m['free_lines']:.0f} lines free")
            print(f"  fit      p{m['page']} c{m['column']}  {state:16} {', '.join(m['blocks'])}")
    except Exception:
        pass
    for e in r.errors:
        print(f"  ERROR    {e}")
    for n in r.notes:
        print(f"  note     {n}")
    if pdf:
        print(f"  pdf      {pdf}")
    print("  RESULT   " + ("PASS" if r.ok else "FAIL"))
    return 0 if r.ok else 1


def cmd_build(a):
    issue, ed = _load_issue(a.issue)
    os.makedirs(a.out, exist_ok=True)
    print(render.build(ed, issue, os.path.join(a.out, _pdf_name(ed, issue) + ".pdf")))


def cmd_prompt(a):
    ed = edition.load(a.edition)
    text = prompt.generate(ed)
    if a.stdout:
        print(text)
    elif a.verify:
        cur = open(prompt.path_for(ed), encoding="utf-8").read() if os.path.exists(prompt.path_for(ed)) else ""
        if cur != text:
            print(f"{prompt.path_for(ed)} is out of date: run `python -m ygc prompt {ed['id']}`")
            return 1
        print(f"{ed['id']}: PROMPT.md up to date")
    else:
        open(prompt.path_for(ed), "w", encoding="utf-8").write(text)
        print(f"wrote {prompt.path_for(ed)}")
    return 0


def cmd_create_edition(a):
    src = edition.load(a.source)
    dst = edition.edition_dir(a.new_id)
    if os.path.exists(dst):
        sys.exit(f"{dst} already exists")
    os.makedirs(os.path.join(dst, "issues"))
    text = open(os.path.join(src["_dir"], "edition.yaml"), encoding="utf-8").read()
    text = text.replace(f"id: {src['id']}", f"id: {a.new_id}", 1)
    open(os.path.join(dst, "edition.yaml"), "w", encoding="utf-8").write(text)
    print(f"created {dst}/edition.yaml — edit reader, purpose, desks and pages, then run\n"
          f"  python -m ygc prompt {a.new_id}\n  python -m ygc new {a.new_id}")


def cmd_migrate(a):
    old = json.load(open(a.file, encoding="utf-8"))
    new = migrate.v3_to_v4(old, a.edition)
    ed = edition.load(a.edition)
    out = a.out or os.path.join(checks.issues_dir(ed), new["date"][:4], new["date"] + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(new, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"wrote {out}")


def cmd_due(a):
    from .auto import research, run, writer
    out = []
    for eid in edition.list_editions():
        ed = edition.load(eid)
        d = dt.date.fromisoformat(a.date) if a.date else checks.today(ed)
        if not run.is_due(ed, d):
            continue
        number, volume = run.next_number(ed, d)
        vocab, dyk, heads = writer._avoid_list(ed, d)
        out.append({"edition": eid, "name": ed["name"], "date": d.isoformat(), "issue": number,
                    "volume": volume,
                    "file": os.path.relpath(os.path.join(checks.issues_dir(ed), str(d.year), f"{d}.json"),
                                            edition.ROOT),
                    "poster": bool((ed.get("automation") or {}).get("poster")),
                    "avoid_vocab": vocab, "avoid_did_you_know": dyk, "previous_headlines": heads[:8]})
    eds = [edition.load(x["edition"]) for x in out]
    desks = {k: {"label": g["label"], "hours": g["hours"], "scopes": g["scopes"], "editions": g["editions"]}
             for k, g in research.desk_groups(eds).items()}
    if a.json:
        print(json.dumps({"due": out, "research_desks": desks}, ensure_ascii=False, indent=1))
        return 0
    if not out:
        print("Nothing is due.")
    for x in out:
        print(f"{x['edition']:24} No. {x['issue']:<5} {x['file']}" + ("   + poster" if x["poster"] else ""))
    for k, g in desks.items():
        print(f"research  {g['label']:12} {g['hours']}h  for {', '.join(g['editions'])}")
    return 0


def cmd_auto(a):
    from .auto import run
    if not a.dry_run and not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Add it as a repository secret (see docs/PUBLISHING.md, step 5),\n"
              "or run with --dry-run to see what's due without calling the API.", file=sys.stderr)
        return 2
    rep = run.run(only=a.only.split(",") if a.only else None, date_override=a.date, dry_run=a.dry_run,
                  budget=a.budget)
    return 0 if a.dry_run or rep.get("editions") is None or \
        any(r["status"] == "passed" for r in rep.get("editions", {}).values()) or not rep.get("editions") else 1


def cmd_new_poster(a):
    from . import poster
    ed = edition.load(a.edition)
    d = a.date or checks.today(ed).isoformat()
    path = poster.path_for(ed, d)
    if os.path.exists(path):
        sys.exit(f"{path} already exists")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(poster.skeleton(ed, d), open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"created {path}\nnext: fill it in following docs/POSTERS.md, then run: "
          f"python -m ygc poster {os.path.relpath(path, edition.ROOT)}")


def cmd_poster(a):
    from . import poster
    ed, p = poster.load(a.poster)
    r = poster.check(ed, p, a.poster)
    if a.pool:
        urls = [u.get("url", "") if isinstance(u, dict) else str(u) for u in p.get("sources", [])]
        r.errors += _pool_errors(a.pool, urls, ["sources"] * len(urls))
    pdf = None
    if r.ok:
        os.makedirs(a.out, exist_ok=True)
        stem = f"{ed['id']}_{p['date']}_poster"
        pdf = poster.build(ed, p, os.path.join(a.out, stem + ".pdf"))
        if _render_pngs(pdf, stem, a.out):
            r.note(f"now LOOK at {os.path.relpath(a.out, edition.ROOT)}/{stem}_page-1.png: checks cannot judge whether it reads well")
    print(f"\n{a.poster}  [{ed['name']}, Big Question poster]")
    for e in r.errors:
        print(f"  ERROR    {e}")
    for n in r.notes:
        print(f"  note     {n}")
    if pdf:
        print(f"  pdf      {pdf}")
    print("  RESULT   " + ("PASS" if r.ok else "FAIL"))
    return 0 if r.ok else 1


def cmd_site(a):
    from . import site
    site.build(a.out, keep=a.keep)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m ygc", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("editions")
    p = sub.add_parser("new"); p.add_argument("edition"); p.add_argument("--date")
    p = sub.add_parser("check"); p.add_argument("issue"); p.add_argument("--archive", action="store_true")
    p.add_argument("--out", default=OUT); p.add_argument("--no-build", action="store_true")
    p.add_argument("--pool")
    p = sub.add_parser("build"); p.add_argument("issue"); p.add_argument("--out", default=OUT)
    p = sub.add_parser("prompt"); p.add_argument("edition")
    p.add_argument("--stdout", action="store_true"); p.add_argument("--verify", action="store_true")
    p = sub.add_parser("create-edition"); p.add_argument("new_id"); p.add_argument("--from", dest="source", required=True)
    p = sub.add_parser("migrate"); p.add_argument("file"); p.add_argument("--edition", required=True)
    p.add_argument("--out")
    p = sub.add_parser("auto"); p.add_argument("--dry-run", action="store_true"); p.add_argument("--only")
    p.add_argument("--date"); p.add_argument("--budget", type=float)
    p = sub.add_parser("site"); p.add_argument("--out", default=os.path.join(edition.ROOT, "_site"))
    p.add_argument("--keep", type=int)
    p = sub.add_parser("new-poster"); p.add_argument("edition"); p.add_argument("--date")
    p = sub.add_parser("poster"); p.add_argument("poster"); p.add_argument("--out", default=OUT)
    p.add_argument("--pool")
    p = sub.add_parser("due"); p.add_argument("--date"); p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        return {"editions": cmd_editions, "new": cmd_new, "check": cmd_check, "build": cmd_build,
                "prompt": cmd_prompt, "create-edition": cmd_create_edition,
                "migrate": cmd_migrate, "auto": cmd_auto, "site": cmd_site,
                "new-poster": cmd_new_poster, "poster": cmd_poster, "due": cmd_due}[a.cmd](a) or 0
    except edition.EditionError as e:
        print(f"edition error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
