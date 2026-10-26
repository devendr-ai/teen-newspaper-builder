"""Inline, age-matched history made only from published, explicitly linked reports."""
import datetime as dt
import html
import re


def plain(value):
    return re.sub(r"<[^>]+>", "", html.unescape(str(value or "")))


def catalog(issues, index, bands, names):
    result = {}
    for paper, date, issue in issues:
        for block, content in issue.get("blocks", {}).items():
            tid = index.get((paper, date, block))
            if not tid or not isinstance(content, dict) or not content.get("headline") or not isinstance(content.get("body"), list):
                continue
            result.setdefault(tid, []).append({
                "paper": paper, "block": block, "date": date, "band": bands[paper], "edition": names[paper],
                "headline": plain(content["headline"]), "deck": plain(content.get("deck")),
                "body": [plain(p) for p in content["body"] if str(p).strip()],
                "extras": [(label, plain(content[key])) for key, label in
                           (("why", "Why it matters"), ("connect", "Connect the dots"), ("analyst", "More to think about"))
                           if content.get(key)],
                "sources": content.get("sources") or [],
            })
    return result


def recent(history, thread, paper, block, band, as_of, level, limit=6):
    """One report per publication day, no future coverage, 30 days inclusive.

    Prefer this edition, then another edition in the exact same age band. Repeated
    headlines are collapsed; sampling keeps the first and latest distinct report.
    """
    end = dt.date.fromisoformat(as_of)
    start = end - dt.timedelta(days=29)
    by_date = {}
    for report in history:
        if report["band"] != band or not start.isoformat() <= report["date"] <= as_of:
            continue
        rank = (report["paper"] != paper, report["block"] != block, report["paper"], report["block"])
        previous = by_date.get(report["date"])
        if previous is None or rank < previous[0]:
            by_date[report["date"]] = (rank, report)
    reports = []
    for date in sorted(by_date):
        report = by_date[date][1]
        if reports and report["headline"].casefold() == reports[-1]["headline"].casefold():
            reports[-1] = report
        else:
            reports.append(report)
    if len(reports) < 2:
        return []
    if len(reports) > limit:
        reports = [reports[round(i * (len(reports) - 1) / (limit - 1))] for i in range(limit)]
    changes = {event.get("reported"): plain(event[level]) for event in thread.get("timeline", []) if event.get(level)}
    return [dict(r, change=changes.get(r["date"], ""), current=r["paper"] == paper and r["date"] == as_of and r["block"] == block)
            for r in reports]


def render(chip, block):
    """Use native details so each story starts closed, independently of its neighbours."""
    escape = html.escape
    if isinstance(chip, str):
        return f'<a class="tchip" href="{escape(chip)}">🧵 New to this story? Read the story so far →</a>'
    updates = chip.get("updates") or []
    if not updates:
        return render(chip["href"], block)
    uid = "thread-" + block
    nodes, entries = [], []
    for i, update in enumerate(updates):
        d = dt.date.fromisoformat(update["date"])
        label = f"{d.day} {d:%b}"
        entry_id = f"{uid}-{i}"
        current = i == len(updates) - 1
        nodes.append(f'<button type="button" class="thread-node" data-thread-index="{i}" '
                     f'aria-controls="{escape(entry_id)}" aria-pressed="{str(current).lower()}" '
                     f'aria-label="{escape(label + ": " + update["headline"])}"><i aria-hidden="true"></i>'
                     f'<span>{label}</span>{"<small>Latest</small>" if current else ""}</button>')
        source_items = []
        for source in update["sources"]:
            url = source.get("url", "") if isinstance(source, dict) else source
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                continue
            title = (source.get("title") or source.get("outlet") or url) if isinstance(source, dict) else url
            source_items.append(f'<li><a href="{escape(url)}" rel="noopener" target="_blank">{escape(str(title))}</a></li>')
        sources = ('<details class="grown"><summary>For grown-ups: original sources</summary><ul>'
                   + "".join(source_items) + '</ul></details>') if source_items else ''
        summary = update["deck"] or (update["body"][0] if update["body"] else "")
        change = f'<p><strong>What changed?</strong> {escape(update["change"])}</p>' if update["change"] else ''
        entries.append(f'''<div class="thread-entry" id="{escape(entry_id)}" data-thread-date="{escape(update['date'])}"{' hidden' if not current else ''}>
<div data-thread-preview><p class="thread-date">{escape(label)} {d.year} · Published report</p>
<h4>{escape(update['headline'])}</h4><p>{escape(summary)}</p>{change}
<p class="thread-edition">{escape(update['edition'])} · {escape(update['band'])}</p>
<button type="button" class="thread-read" data-thread-read{' data-thread-current' if update['current'] else ''}>{'Back to this story ↓' if update['current'] else 'Read this report →'}</button></div>
<div class="thread-report" data-thread-report hidden><button type="button" data-thread-return>← Back to timeline</button>
<p class="thread-date">Earlier report · Published {escape(label)} {d.year}</p><h4>{escape(update['headline'])}</h4>
<p class="thread-edition">{escape(update['edition'])} · {escape(update['band'])}</p>
{('<p>' + escape(update['deck']) + '</p>') if update['deck'] else ''}
{''.join('<p>' + escape(p) + '</p>' for p in update['body'])}
{''.join('<h5>' + escape(label) + '</h5><p>' + escape(value) + '</p>' for label, value in update.get('extras', []))}{sources}
<button type="button" data-thread-return>← Back to timeline</button></div></div>''')
    return f'''<details class="follow-thread" data-thread="{escape(block)}">
<summary>🧵 Follow the thread <span>· {len(updates)} updates</span></summary>
<div class="thread-panel" role="region" aria-label="{escape(chip['title'])} timeline">
<div class="thread-heading"><div><h3>{escape(chip['title'])}</h3><p>Selected reports · last 30 days · oldest → newest</p></div>
<button type="button" data-thread-close aria-label="Close timeline">×</button></div>
<div class="thread-rail" role="group" aria-label="Choose a published update">{''.join(nodes)}</div>
<div class="thread-entries">{''.join(entries)}</div>
<div class="thread-paging"><button type="button" data-thread-previous aria-label="Previous timeline update">←</button>
<span data-thread-count aria-live="polite">{len(updates)} of {len(updates)}</span>
<button type="button" data-thread-next aria-label="Next timeline update" disabled>→</button></div>
<a class="tchip" href="{escape(chip['href'])}">More background: the story so far →</a>
</div></details>'''


CSS = r'''
.follow-thread{margin:10px 0 18px;min-width:0}
.follow-thread>summary{display:inline-flex;align-items:center;gap:6px;flex-wrap:wrap;min-height:44px;padding:8px 14px;border-radius:24px;background:#E7E3FA;color:#4D3FB0;font-size:16px;font-weight:700;list-style:none;cursor:pointer}
.follow-thread>summary::-webkit-details-marker{display:none}
.follow-thread>summary span{font-size:.85em}
.thread-panel{margin-top:14px;padding:16px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);min-width:0}
.thread-heading{display:flex;align-items:flex-start;gap:8px}.thread-heading>div{flex:1;min-width:0}.thread-heading h3{font-size:1em;margin:0}.thread-heading p{font-size:13px;color:var(--muted);margin:4px 0}
.thread-heading button,.thread-paging button{min-height:44px;min-width:44px;border:0;background:transparent;color:var(--teal);font:inherit;cursor:pointer}
.thread-heading button{font-size:24px}
.thread-rail{position:relative;display:flex;gap:6px;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x proximity;padding:10px 2px 14px;min-width:0}
.thread-node{position:relative;flex:1 0 76px;display:flex;flex-direction:column;align-items:center;gap:5px;min-height:76px;padding:4px;border:0;border-radius:8px;background:transparent;color:var(--muted);font:inherit;font-size:13px;cursor:pointer;scroll-snap-align:center}
.thread-node:before{content:'';position:absolute;height:2px;top:17px;left:-6px;right:-6px;background:var(--line)}.thread-node:first-child:before{left:50%}.thread-node:last-child:before{right:50%}
.thread-node i{position:relative;display:block;width:15px;height:15px;margin:6px 0 0;background:var(--line);border:3px solid var(--card);border-radius:50%;box-shadow:0 0 0 1px var(--line)}
.thread-node[aria-pressed=true]{background:#DDEFF0;color:var(--teal)}.thread-node[aria-pressed=true] i{background:var(--teal);box-shadow:0 0 0 1px var(--teal)}.thread-node small{font-size:11px;font-weight:700;color:var(--coral)}
.thread-entry{padding:16px;background:#EAF3F2;border-radius:12px;font-size:16px;overflow-wrap:anywhere}.thread-entry h4{font-family:var(--display);font-size:1.2em;line-height:1.25;margin:6px 0 12px}.thread-entry p{margin:10px 0}.thread-entry .thread-date{font-size:12px;color:var(--teal);font-weight:700;margin:0}.thread-entry .thread-edition{font-size:12px;color:var(--muted)}
.thread-read,.thread-report>button{min-height:44px;padding:8px 12px;border:1px solid var(--line);border-radius:9px;background:var(--card);color:var(--teal);font:inherit;font-size:14px;font-weight:700;cursor:pointer}
.thread-paging{display:flex;align-items:center;justify-content:flex-end;gap:8px;font-size:13px;margin:4px 0}.thread-paging button:disabled{opacity:.35;cursor:default}
.follow-thread .tchip{display:inline-block;background:transparent;padding:4px 0;margin:0;min-height:44px;font-size:14px;text-decoration:underline}
.thread-report{font-size:1em}.thread-report>button:first-child{margin-bottom:12px}.thread-report .grown{font-size:14px}
.follow-thread button:focus-visible,.follow-thread>summary:focus-visible{outline:3px solid var(--teal);outline-offset:2px}
:root[data-theme="night"] .follow-thread>summary{background:#302B4B;color:#D4CAFF}
:root[data-theme="night"] .thread-entry,:root[data-theme="night"] .thread-node[aria-pressed=true]{background:#203D40}
@media print{.follow-thread{display:none!important}}
'''


JS = r'''
(function () {
  const main = document.querySelector('.issue');
  if (!main) return;
  let reset = false;
  document.addEventListener('rp-reading-reset', () => { reset = true; });
  document.querySelectorAll('.follow-thread').forEach(thread => {
    const summary = thread.querySelector('summary'), rail = thread.querySelector('.thread-rail');
    const nodes = [...thread.querySelectorAll('[data-thread-index]')], entries = [...thread.querySelectorAll('.thread-entry')];
    const previous = thread.querySelector('[data-thread-previous]'), next = thread.querySelector('[data-thread-next]');
    const key = 'rp-thread-' + main.dataset.key + '-' + thread.dataset.thread;
    let at = entries.length - 1, returnY = 0;
    try { const date = localStorage.getItem(key); const found = entries.findIndex(entry => entry.dataset.threadDate === date); if (found >= 0) at = found; } catch (_) {}
    const remember = () => { if (!reset) try { localStorage.setItem(key, entries[at].dataset.threadDate); } catch (_) {} };
    function align() {
      if (!thread.open) return;
      const node = nodes[at];
      rail.scrollLeft = node.offsetLeft - rail.offsetLeft - (rail.clientWidth - node.offsetWidth) / 2;
    }
    function preview(entry) {
      entry.querySelector('[data-thread-preview]').hidden = false;
      entry.querySelector('[data-thread-report]').hidden = true;
    }
    function select(index, focus = false) {
      at = Math.max(0, Math.min(entries.length - 1, index));
      entries.forEach((entry, i) => { entry.hidden = i !== at; preview(entry); });
      nodes.forEach((node, i) => node.setAttribute('aria-pressed', String(i === at)));
      previous.disabled = at === 0; next.disabled = at === entries.length - 1;
      thread.querySelector('[data-thread-count]').textContent = `${at + 1} of ${entries.length}`;
      if (focus) nodes[at].focus({preventScroll:true});
      align();
    }
    select(at);
    thread.addEventListener('toggle', () => { if (thread.open) requestAnimationFrame(align); });
    thread.querySelector('[data-thread-close]').addEventListener('click', () => { thread.open = false; summary.focus({preventScroll:true}); });
    nodes.forEach((node, i) => {
      node.addEventListener('click', () => { select(i); remember(); });
      node.addEventListener('keydown', event => {
        const delta = event.key === 'ArrowLeft' ? -1 : event.key === 'ArrowRight' ? 1 : 0;
        if (delta) { event.preventDefault(); event.stopPropagation(); select(at + delta, true); remember(); }
      });
    });
    previous.addEventListener('click', () => { select(at - 1, true); remember(); });
    next.addEventListener('click', () => { select(at + 1, true); remember(); });
    entries.forEach(entry => {
      const read = entry.querySelector('[data-thread-read]');
      read.addEventListener('click', () => {
        if (read.hasAttribute('data-thread-current')) { thread.open = false; summary.focus({preventScroll:true}); return; }
        document.dispatchEvent(new Event('rp-thread-report'));
        returnY = window.scrollY;
        entry.querySelector('[data-thread-preview]').hidden = true;
        entry.querySelector('[data-thread-report]').hidden = false;
        entry.querySelector('[data-thread-return]').focus({preventScroll:true});
        const reportTop = entry.querySelector('[data-thread-report]').getBoundingClientRect().top;
        const headerBottom = document.querySelector('header.bar')?.getBoundingClientRect().bottom || 0;
        window.scrollBy({top:reportTop - headerBottom - 12});
        remember();
      });
      entry.querySelectorAll('[data-thread-return]').forEach(button => button.addEventListener('click', () => {
        preview(entry); read.focus({preventScroll:true}); window.scrollTo({top:returnY});
      }));
    });
  });
})();
'''
