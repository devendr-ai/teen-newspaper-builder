"""Public website app showcase. No native app or --kids content is changed."""
from html import escape as E
from urllib.parse import urlsplit, parse_qs

from . import navigation


def store_url(value, store):
    """Only explicit official store destinations become live links."""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    try:
        p = urlsplit(value)
        if p.scheme != 'https' or p.username or p.password or p.port or p.fragment:
            return ''
    except ValueError:
        return ''
    if store == 'apple' and p.hostname == 'apps.apple.com' and '/app/' in p.path and '/id' in p.path:
        return value
    if store == 'google' and p.hostname == 'play.google.com' and p.path == '/store/apps/details' and parse_qs(p.query).get('id'):
        return value
    return ''


def downloads(cfg):
    settings = cfg.get('mobile_app') or {}
    choices = [('apple', 'app_store_url', 'App Store', 'For iPhone & iPad'),
               ('google', 'google_play_url', 'Google Play', 'For Android phones & tablets')]
    cards = []
    for store, key, title, platforms in choices:
        url = store_url(settings.get(key), store)
        content = (navigation.icon('smartphone') + f'<span><strong>{title}</strong>'
                   + f'<small>{platforms}</small><span class="store-state">'
                   + ('View in store' if url else 'Coming soon') + '</span></span>')
        cards.append(f'<a class="app-store" href="{E(url)}" rel="noopener" target="_blank">{content}</a>' if url
                     else f'<div class="app-store pending" aria-label="{title}: coming soon">{content}</div>')
    waiting = any(not store_url(settings.get(key), store) for store, key, *_ in choices)
    note = '<p class="app-approval">Store links will appear here after approval.</p>' if waiting else ''
    return '<div class="app-downloads" aria-label="Download options">' + ''.join(cards) + '</div>' + note


def _icon(name):
    paths = {
        'car': '<path d="m5 7 2-4h10l2 4M3 8h18v10H3zM3 12h18M6 18v3M18 18v3"/><circle cx="7" cy="15" r="1"/><circle cx="17" cy="15" r="1"/>',
        'plane': '<path d="m2 13 8-3V4a2 2 0 0 1 4 0v6l8 3v3l-8-2v5l3 2v1l-5-1-5 1v-1l3-2v-5l-8 2z"/>',
        'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',
    }
    return ('<svg class="app-feature-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + paths[name] + '</svg>')


def body(cfg):
    return f'''<main class="app-showcase">
<section class="app-hero" aria-labelledby="app-heading">
<div class="app-intro"><p class="app-eyebrow">THE NEWS PEBBLES APP</p>
<h2 id="app-heading">A little world news.<br>Wherever you go.</h2>
<p class="app-lede">Your family’s newspaper — with offline reading, screen-locked listening and a gentle morning reminder.</p>
{downloads(cfg)}
<a class="app-paper-link" href="index.html">Prefer paper? Explore printable editions <span aria-hidden="true">→</span></a></div>
<div class="app-preview" aria-label="Screenshots from the News Pebbles app">
<figure class="app-phone app-today"><img src="app-showcase/today.jpg" width="1320" height="2868" alt="The app’s Today view, with age selection, a car-ride brief and newspaper reading choices."></figure>
<figure class="app-phone app-listen"><img src="app-showcase/listen.jpg" width="1320" height="2868" alt="The app’s Listen view, with car-ride briefs, playback controls and the Listen tab."></figure>
</div></section>
<section class="app-benefits" aria-labelledby="app-benefits-heading"><h2 id="app-benefits-heading">Made for real family days</h2>
<div class="app-features">
<article>{_icon('car')}<div><h3>Listen with the screen locked</h3><p>Play the 3–5 minute car-ride brief, then put the phone away. Audio keeps playing with the screen locked.</p></div></article>
<article>{_icon('plane')}<div><h3>Seven days of papers offline</h3><p>Open the app online to save the latest papers and available audio. Read and listen later, even without a connection.</p></div></article>
<article>{_icon('clock')}<div><h3>A reminder, without tracking</h3><p>Choose a morning reminder in For parents. It’s set on your device, with no tracking or advertising.</p></div></article>
</div></section>
<section class="app-print-band" aria-labelledby="app-paper-heading">{navigation.icon('newspaper')}<div><h2 id="app-paper-heading">Still a newspaper at heart.</h2><p>Print it. Leave it at breakfast. Discover something together.</p></div><a href="index.html">Find your paper <span aria-hidden="true">→</span></a></section>
<p class="app-mobile-paper"><a href="index.html">Explore printable papers <span aria-hidden="true">→</span></a></p>
</main>'''


def teaser():
    return f'''<aside class="app-teaser" aria-label="News Pebbles app">{navigation.icon('smartphone')}<p><b>Take News Pebbles with you.</b> Offline papers, listening and a gentle morning reminder.</p><a href="app.html">Explore the app <span aria-hidden="true">→</span></a></aside>'''


TEASER_CSS = '''
.app-teaser{display:flex;align-items:center;gap:12px;margin:18px 0;padding:14px 18px;border:1.5px solid var(--line);border-radius:14px;background:var(--surface)}
.app-teaser>.ui-icon{width:28px;height:28px;color:var(--cyan)}.app-teaser p{margin:0;flex:1;font-size:.95rem}
.app-teaser b{color:var(--ink)}.app-teaser a{display:inline-flex;align-items:center;min-height:44px;font-weight:700;white-space:nowrap}
@media(max-width:600px){.app-teaser{flex-wrap:wrap;gap:4px 10px;padding:12px 14px}.app-teaser p{flex-basis:calc(100% - 40px)}.app-teaser a{margin-left:38px;white-space:normal}}
'''

CSS = '''
.app-showcase{padding:22px 0 0}.app-hero{display:grid;grid-template-columns:1.1fr 1fr;gap:30px;align-items:center;padding:12px 0 36px}
.app-eyebrow{color:var(--cyan);font-size:.85rem;font-weight:800;letter-spacing:.04em;margin:0 0 18px}
.app-intro h2{font-size:clamp(2.1rem,4.8vw,3.45rem);line-height:1.07;letter-spacing:-.035em;overflow-wrap:break-word}
.app-lede{font-size:1.2rem;line-height:1.5;color:var(--muted);max-width:42ch;margin:22px 0}
.app-downloads{display:flex;flex-wrap:wrap;gap:12px}.app-store{display:flex;gap:10px;align-items:center;min-height:88px;padding:12px 16px;border:1.5px solid var(--line);border-radius:12px;background:var(--surface);color:var(--ink);text-decoration:none;flex:1;min-width:175px;max-width:245px}
.app-store .ui-icon{width:28px;height:28px}.app-store strong,.app-store small,.store-state{display:block}.app-store strong{font:800 1.05rem var(--display)}.app-store small{font-size:.75rem;color:var(--muted);line-height:1.4}
.store-state{font-size:.8rem;color:var(--cyan);font-weight:700;margin-top:2px}.app-store.pending .store-state{color:var(--muted)}
a.app-store:hover{border-color:var(--cyan)}.app-approval{font-size:.85rem;color:var(--muted);margin:10px 0 18px}
.app-paper-link{display:inline-flex;align-items:center;min-height:44px;font-weight:700;gap:5px}
.app-preview{position:relative;min-height:500px;margin:0;max-width:450px;width:100%;justify-self:center}
.app-phone{margin:0;border:8px solid #1E2A32;border-radius:30px;background:var(--paper);overflow:hidden;box-shadow:0 10px 20px #0002;line-height:0}
.app-phone img{display:block;width:100%;height:auto}.app-today{width:235px;position:relative;z-index:1}.app-listen{position:absolute;right:0;bottom:8px;width:192px;z-index:2}
.app-benefits{border-top:1px solid var(--line);padding:26px 0 30px}.app-benefits>h2{font-size:1.7rem;margin-bottom:18px}
.app-features{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.app-features article{display:flex;gap:14px;align-items:flex-start;padding:20px 16px;border:1.5px solid var(--line);border-radius:14px;background:var(--surface)}
.app-feature-icon{width:32px;height:32px;flex:none;color:var(--cyan)}.app-features h3{font-size:1.1rem;line-height:1.25}.app-features p{color:var(--muted);font-size:.95rem;line-height:1.5;margin:10px 0 0}
.app-print-band{display:flex;gap:18px;align-items:center;border-top:1px solid var(--line);padding:24px 0 12px}.app-print-band>.ui-icon{width:42px;height:42px;color:var(--cyan)}.app-print-band h2{font-size:1.35rem}.app-print-band p{margin:5px 0;color:var(--muted)}.app-print-band a{margin-left:auto;display:inline-flex;align-items:center;min-height:44px;font-weight:700;white-space:nowrap}
.app-mobile-paper{display:none}.app-showcase :focus-visible{outline:3px solid var(--cyan);outline-offset:4px}
@media(max-width:999px){.app-hero{gap:20px;grid-template-columns:1.05fr 1fr}.app-preview{min-height:430px;max-width:355px}.app-today{width:200px}.app-listen{width:165px}.app-features article{padding:16px 12px;gap:9px}.app-feature-icon{width:26px;height:26px}}
@media(max-width:699px){.app-showcase{padding-top:12px}.app-hero{display:flex;flex-direction:column;gap:24px;padding:4px 0 24px}.app-intro{width:100%}.app-intro h2{font-size:clamp(2rem,8vw,2.6rem)}.app-lede{font-size:1.05rem;margin:16px 0}.app-eyebrow{font-size:.8rem;margin-bottom:12px}.app-downloads{gap:8px}.app-store{min-width:0;max-width:none;min-height:92px;padding:10px;gap:6px}.app-store .ui-icon{width:21px;height:21px}.app-store strong{font-size:.95rem}.app-store small{font-size:.7rem}.app-approval{margin-bottom:10px}
.app-preview{min-height:0;max-width:190px}.app-today{display:none}.app-listen{position:relative;right:auto;bottom:auto;width:100%}.app-phone{border-width:6px;border-radius:25px}
.app-benefits{padding:22px 0 10px}.app-benefits>h2{font-size:1.4rem}.app-features{grid-template-columns:1fr;gap:10px}.app-features article{padding:16px;gap:14px}.app-feature-icon{width:30px;height:30px}.app-features p{margin-top:5px;font-size:.93rem}.app-print-band{display:none}.app-mobile-paper{display:block;margin:8px 0 0}.app-mobile-paper a{min-height:44px;display:inline-flex;align-items:center;font-weight:700}}
@media(min-width:700px) and (max-width:820px){.app-features{grid-template-columns:1fr}.app-features article{padding:18px}}
@media print{.app-preview,.app-downloads,.app-approval{display:none}.app-hero{display:block}}
'''
