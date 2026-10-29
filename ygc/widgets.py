"""Public, non-personal widget feed. Questions are copied, never invented."""
import datetime as dt
import html
import json
import re
from pathlib import Path

from . import checks


def plain(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', '', str(value))).split())


def question(issue):
    # Prefer the paper's family discussion question; otherwise use its checked quiz.
    discussion = (issue.get('blocks') or {}).get('discussion') or {}
    body = discussion.get('body') or []
    if isinstance(body, str):
        body = [body]
    candidates = [(q, 'discussion') for q in body if isinstance(q, str)]
    candidates += [(q.get('q'), 'quiz') for q in (issue.get('play') or {}).get('quiz', []) if isinstance(q, dict)]
    return next(((plain(q), origin) for q, origin in candidates if q and 8 <= len(plain(q)) <= 240 and plain(q).endswith('?')), None)


def write(out, published):
    root = Path(out)
    entries = []
    for eid, (ed, date) in sorted(published.items()):
        source = Path(checks.issues_dir(ed)) / date[:4] / f'{date}.json'
        reader = f'play/{eid}/{date}.html'
        if not source.is_file() or not (root / reader).is_file():
            continue
        issue = json.loads(source.read_text(encoding='utf-8'))
        picked = question(issue)
        if not picked:
            continue
        text, origin = picked
        # Filename dates drive publication elsewhere too. No personal/device data.
        dt.date.fromisoformat(date)
        entries.append({'edition': eid, 'name': ed['name'], 'date': date, 'question': text,
                        'origin': origin, 'reader': reader,
                        'brief': f'play/briefs/{date}.json' if (ed.get('site') or {}).get('audio_brief') else None})
    feed = {'v': 1, 'editions': entries}
    (root / 'widgets.json').write_text(json.dumps(feed, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return feed
