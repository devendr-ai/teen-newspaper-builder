"""Static website: every listed edition, its latest PDF, an archive with sources, RSS.

    python -m ygc site --out _site
"""
import datetime as dt
import glob
import html
import json
import os
import re
import shutil
import subprocess
from urllib.parse import quote

import yaml

from . import brand, checks, edition, poster, render, stats, pwa, navigation, weekend

ROOT = edition.ROOT
E = html.escape


def site_config():
    p = os.path.join(ROOT, "site.yaml")
    cfg = yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    cfg.setdefault("title", "The Newsstand")
    cfg.setdefault("tagline", "Printable newspapers, written for each reader.")
    cfg.setdefault("description", cfg["tagline"])
    cfg.setdefault("home_headline", cfg["tagline"])
    cfg.setdefault("domain", "")
    cfg.setdefault("base_url", "")
    cfg.setdefault("contact", "")
    cfg.setdefault("feedback_url", "")
    cfg.setdefault("keep_issues", 30)
    cfg.setdefault("intro_title", "")
    cfg.setdefault("intro", "")
    cfg.setdefault("steps", [])
    cfg.setdefault("subscriptions", {"enabled": False, "api_base_url": "", "whatsapp_channel_url": ""})
    return cfg


def subscription_endpoint(cfg):
    """A disabled/unconfigured UI never offers a form which cannot deliver."""
    settings = cfg.get("subscriptions") or {}
    if settings.get("enabled") is not True:
        return ""
    base = settings.get("api_base_url")
    if not isinstance(base, str) or not base.strip():
        return ""
    from urllib.parse import urlsplit
    try:
        url = urlsplit(base.strip())
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in base)
                or url.hostname.startswith("replace-") or url.hostname.endswith(".example")):
            return ""
        url.port  # Validate malformed ports as well.
    except ValueError:
        return ""
    # Accept either a Worker origin or an API base such as /api or /mail/api.
    return base.strip().rstrip("/") + ("/api" if url.path in ("", "/") else "") + "/subscribe"


def whatsapp_channel(cfg):
    from urllib.parse import urlsplit
    value = (cfg.get("subscriptions") or {}).get("whatsapp_channel_url") or ""
    if not isinstance(value, str):
        return ""
    try:
        url = urlsplit(value)
        if (url.scheme != "https" or url.hostname not in ("whatsapp.com", "www.whatsapp.com") or not url.path.startswith("/channel/")
                or not url.path.removeprefix("/channel/") or url.username or url.password or url.port
                or url.query or url.fragment or any(c.isspace() for c in value)):
            return ""
    except ValueError:
        return ""
    return f'<a href="{E(value)}" target="_blank" rel="noopener noreferrer">Follow our WhatsApp Channel</a>'


def subscription_share_url(cfg, ed, date):
    from urllib.parse import quote
    if not date:
        return ""
    base = cfg.get("base_url", "").rstrip("/")
    text = (f'{ed["name"]} · {audience(ed)} · {date}\n'
            f'Read & Play: {base}/play/{ed["id"]}/{date}.html\n'
            f'Printable PDF: {base}/e/{ed["id"]}/{date}.pdf')
    return "https://wa.me/?text=" + quote(text, safe="")


def subscription_link(cfg, ed):
    if not subscription_endpoint(cfg):
        return ""
    href = f'parents.html?edition={quote(ed["id"], safe="")}#subscribe-parents-title'
    return (f'<p class="recommended-note"><a class="recommended-archive subscription-signup" href="{E(href)}">'
            'Get this paper by email (free)</a></p>')


def subscription_form(cfg, ed=None, *, root="", context="parents", date=None, published=None):
    endpoint = subscription_endpoint(cfg)
    if not endpoint:
        return ""
    ident = "subscribe-" + context + ("-" + ed["id"] if ed else "")
    if ed:
        choice = f'<input type="hidden" name="edition_slug" value="{E(ed["id"])}">'
        subject = f'<p class="subscription-paper">{E(ed["name"])}</p>'
        share_url = subscription_share_url(cfg, ed, date)
    else:
        options = []
        for slug in edition.list_editions():
            paper = edition.load(slug)
            if (paper.get("site") or {}).get("listed") is False:
                continue
            latest = (published or {}).get(slug)
            url = subscription_share_url(cfg, paper, latest[1] if latest else None)
            options.append(f'<option value="{E(slug)}" data-share-url="{E(url)}">{E(paper["name"])} · {E(audience(paper))}</option>')
        choice = (f'<label for="{ident}-edition">Choose your paper</label><select id="{ident}-edition" name="edition_slug" required>'
                  '<option value="">Choose a newspaper</option>' + "".join(options) + '</select>')
        subject, share_url = "", ""
    share = (f'<a data-subscription-share href="{E(share_url)}" target="_blank" rel="noopener noreferrer"'
             f'{"" if share_url else " hidden"}>Send this issue to WhatsApp</a>')
    math_check = '' if cfg.get('kids_mode') else f'''<div class="subscription-math"><label for="{ident}-answer">For grown-ups: <span data-math-question>loading…</span></label>
<input id="{ident}-answer" type="text" name="grownup_answer" inputmode="numeric" pattern="[0-9]+" autocomplete="off" required aria-describedby="{ident}-math-help" size="6">
<small id="{ident}-math-help">A quick check before we send an email. Ask a grown-up to help.</small></div>'''
    return f'''<section class="subscription-box" aria-labelledby="{ident}-title">
<h3 id="{ident}-title">Get this paper by email (free)</h3>{subject}
<p class="subscription-summary">A printable PDF and a Read &amp; Play link, delivered to a grown-up’s inbox.</p>
<form method="dialog" data-gate-form="subscribe" data-subscribe-endpoint="{E(endpoint)}" data-subscribe-kids="{str(bool(cfg.get("kids_mode"))).lower()}" aria-describedby="{ident}-privacy">
<fieldset class="subscription-fields" disabled><legend class="subscription-sr">Email delivery preferences</legend>
{choice}<fieldset class="subscription-cadence"><legend>Delivery</legend>
<label><input type="radio" name="cadence" value="every_issue" checked> Every new issue</label>
<label><input type="radio" name="cadence" value="weekly_weekend"> Weekend digest</label></fieldset>
<label for="{ident}-email">Grown-up’s email address</label>
<div class="subscription-email"><input id="{ident}-email" type="email" name="email" required maxlength="254" autocomplete="email" inputmode="email" autocapitalize="none" spellcheck="false" placeholder="you@example.com"></div>
<div hidden aria-hidden="true"><label for="{ident}-website">Leave this field empty</label><input id="{ident}-website" type="text" name="website" tabindex="-1" autocomplete="off"></div>
{math_check}
<button type="submit" class="btn">Send confirmation email</button></fieldset>
<p class="subscription-status" role="status" aria-live="polite" aria-atomic="true"></p><p class="subscription-error" role="alert" aria-atomic="true"></p>
<p id="{ident}-privacy" class="subscription-privacy">For parents and carers. Confirm by email first. Unsubscribe any time. <a href="{root}privacy.html#email-delivery">Email privacy</a>.</p>
<noscript><p>Turn on JavaScript to use the grown-up check and subscribe. You can still download every paper.</p></noscript>
</form><p class="subscription-links">{share}{whatsapp_channel(cfg)}</p></section>'''


def autoprint_guide():
    return '''<details class="autoprint-guide"><summary>Want this paper to print itself automatically?</summary>
<p>Auto-Print Magic works with a supported printer’s email-to-print service. Set it up once, then test with one issue.</p>
<ol><li><b>Find your printer’s email address.</b> Enable HP ePrint or Epson Email Print on a compatible printer. Keep its address private and add your forwarding email address and our issue sender to its approved senders list.</li>
<li><b>Create a rule for our issue emails.</b> Copy the sender address from your first News Pebbles paper email. In Gmail, add and verify your printer as a forwarding address, then create a filter for that sender with an attachment and choose “Forward it to”. In Outlook, use Settings → Mail → Rules: match that sender and an attachment, then “Forward to” your printer’s address. Keep the PDF attached; don’t forward the whole message as an .eml attachment.</li>
<li><b>Test, then leave it running.</b> Forward one paper and check the printout. Where supported, choose attachments only so the email body doesn’t print too. Turn the rule off any time to stop automatic printing.</li></ol>
<p class="subscription-privacy">Gmail requires forwarding-address verification; some printer addresses cannot complete it. Printer support and account forwarding rules vary. If setup isn’t supported, download and print the attached PDF as usual.</p>
<p class="subscription-privacy">Setup help: <a href="https://support.google.com/mail/answer/10957" target="_blank" rel="noopener noreferrer">Gmail</a> · <a href="https://support.microsoft.com/en-us/outlook/mail/use-rules-to-automatically-forward-messages" target="_blank" rel="noopener noreferrer">Outlook</a> · <a href="https://support.hp.com/sg-en/document/ish_2060244-1929404-16" target="_blank" rel="noopener noreferrer">HP ePrint</a> · <a href="https://www.epsonconnect.com/guide/en/html/uses_1.htm" target="_blank" rel="noopener noreferrer">Epson Email Print</a></p></details>'''


def subscription_banner():
    return f'''<section class="subscription-banner" data-subscription-banner role="region" aria-label="Email delivery confirmation" hidden>
<button type="button" class="subscription-dismiss" aria-label="Dismiss email delivery confirmation">Dismiss ×</button>
<div data-subscription-confirmed hidden><h2 tabindex="-1">You’re subscribed. Welcome to News Pebbles!</h2><p>Your latest paper is on its way. Check your inbox for the printable PDF and Read &amp; Play link.</p>{autoprint_guide()}</div>
<div data-subscription-unsubscribed hidden><h2 tabindex="-1">You’re unsubscribed</h2><p>You won’t receive more emails for this paper. You can still print and read every issue here.</p></div></section>'''


SUBSCRIPTION_STYLE = """
.subscription-box,.subscription-banner{border:1px solid var(--line);border-radius:12px;background:var(--surface);padding:18px;margin:18px 0}
.subscription-box h3{font-size:1.1rem;margin:0 0 6px;scroll-margin-top:90px}.subscription-box p{margin:6px 0;font-size:.9rem}
.subscription-paper{font-weight:700}.subscription-summary{color:var(--muted)}
.subscription-fields,.subscription-cadence{border:0;padding:0;margin:0;min-width:0}
.subscription-fields>label,.subscription-cadence legend,.subscription-math>label{display:block;font-weight:700;margin:12px 0 6px;font-size:.9rem}
.subscription-fields input:not([type=radio]),.subscription-fields select{box-sizing:border-box;font:inherit;font-size:16px;border:1.5px solid var(--line);border-radius:8px;padding:10px;min-height:44px;max-width:100%;background:var(--surface);color:var(--ink)}
.subscription-email input,.subscription-fields select{width:100%}.subscription-cadence label{display:inline-flex;align-items:center;gap:6px;min-height:44px;margin-right:14px;font-size:.9rem;cursor:pointer}
.subscription-cadence input{width:18px;height:18px;accent-color:var(--cyan)}
.subscription-math{margin-bottom:14px}.subscription-math input{width:100px}.subscription-math small{display:block;color:var(--muted);font-size:.8rem;margin-top:5px}
.subscription-fields button{font:inherit;min-height:44px;cursor:pointer}.subscription-fields button:disabled{cursor:wait;opacity:.7}
.subscription-box .subscription-privacy,.autoprint-guide .subscription-privacy{font-size:.8rem;color:var(--muted)}
.subscription-status{color:var(--cyan);font-weight:700}.subscription-error{color:#9a3128;font-weight:700}
.subscription-links{display:flex;flex-wrap:wrap;gap:8px 18px}.subscription-links a{font-size:.82rem}
.subscription-box :focus-visible,.subscription-banner :focus-visible{outline:3px solid var(--cyan);outline-offset:3px}
.subscription-sr{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap;border:0}
.subscription-banner{background:var(--cyan-t)}.subscription-banner h2{font-size:1.2rem;margin:0 0 8px}.subscription-dismiss{display:block;margin:0 0 10px auto;border:0;background:transparent;font:inherit;font-size:.85rem;min-height:44px;cursor:pointer;color:var(--ink)}
.autoprint-guide{margin:18px 0;padding:14px;border:1px solid var(--line);border-radius:10px;font-size:.9rem}.autoprint-guide summary{font-weight:700;cursor:pointer}.autoprint-guide li{margin:10px 0}.autoprint-guide ol{padding-left:22px}
@media(max-width:480px){.subscription-box{padding:14px}.subscription-cadence label{display:flex;margin:0}.subscription-fields button{width:100%}}
@media print{.subscription-box,.subscription-banner,.autoprint-guide{display:none!important}}
"""


SUBSCRIPTION_SCRIPT = r'''<script>
(function(){
'use strict';
// No subscription requests on load/change. Each submit owns its own math check.
document.querySelectorAll('form[data-gate-form="subscribe"]').forEach(form=>{
 const fields=form.querySelector('.subscription-fields'),button=form.querySelector('button[type="submit"]'),
 status=form.querySelector('.subscription-status'),error=form.querySelector('.subscription-error'),
 answer=form.elements.namedItem('grownup_answer'),question=form.querySelector('[data-math-question]');
 const isKids=form.dataset.subscribeKids==='true';
 let expected=0,busy=false,authorizing=false;
 function challenge(){if(isKids)return;const a=12+Math.floor(Math.random()*8),b=3+Math.floor(Math.random()*6);expected=a*b;question.textContent=a+' × '+b+' = ?';answer.value='';answer.removeAttribute('aria-invalid');}
 form.addEventListener('submit',async event=>{
  if(event.defaultPrevented)return;event.preventDefault();if(busy||authorizing)return;
  status.textContent='';error.textContent='';
  if(!form.reportValidity())return;
  if(!isKids&&(!/^\d+$/.test(answer.value.trim())||Number(answer.value)!==expected)){
   error.textContent='Please ask a grown-up to check the answer before subscribing.';answer.setAttribute('aria-invalid','true');answer.focus();return;
  }
  const nativeParent=window.NPApp&&window.NPApp.native;
  // Native parentPost owns its gate; web kids builds use the existing browser gate.
  if(isKids&&!nativeParent){
   if(typeof window.npGate!=='function'){error.textContent='Please wait for the grown-up check to load, then try again.';return;}
   authorizing=true;let allowed=false;
   try{allowed=await new Promise(resolve=>{const yes=()=>resolve(true),no=()=>resolve(false);if(window.npGate.parent)window.npGate.parent(yes,no);else window.npGate('link',yes,no);});}
   finally{authorizing=false;}
   if(!allowed)return;
  }
  const payload={email:form.elements.namedItem('email').value.trim(),edition_slug:form.elements.namedItem('edition_slug').value,cadence:form.elements.namedItem('cadence').value,website:form.elements.namedItem('website').value};
  busy=true;button.disabled=true;form.setAttribute('aria-busy','true');button.textContent='Sending…';status.textContent='Sending your confirmation email…';
  const controller=new AbortController(),timer=nativeParent?null:setTimeout(()=>controller.abort(),20000);
  try{
   const response=nativeParent?await window.NPApp.parentPost(form.dataset.subscribeEndpoint,payload):await fetch(form.dataset.subscribeEndpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),credentials:'omit',cache:'no-store',redirect:'error',referrerPolicy:'no-referrer',signal:controller.signal});
   if(!response)return; // The grown-up cancelled; no request was sent.
   if(!response.ok){error.textContent=response.status===429?'Too many requests. Please wait a while before trying again.':response.status===503?'Email delivery is temporarily unavailable. Please try again later.':'We couldn’t request your subscription. Check your email and try again.';return;}
   const result=await response.json();if(result.ok!==true)throw Error('invalid_response');
   status.textContent="Check your inbox to confirm — we'll send the latest issue right away!";form.elements.namedItem('email').value='';form.elements.namedItem('website').value='';
  }catch(e){error.textContent='We couldn’t reach email delivery. Check your connection and try again.';}
  finally{clearTimeout(timer);status.textContent=status.textContent==='Sending your confirmation email…'?'':status.textContent;if(error.textContent)status.textContent='';challenge();busy=false;button.disabled=false;button.textContent='Send confirmation email';form.removeAttribute('aria-busy');}
 });
 challenge();fields.disabled=false; // Fail closed without JS or if setup cannot finish.
 const editions=form.elements.namedItem('edition_slug'),share=form.closest('.subscription-box').querySelector('[data-subscription-share]');
 if(editions.tagName==='SELECT'){
  const requested=new URL(location.href).searchParams.get('edition');
  if(requested&&Array.from(editions.options).some(option=>option.value===requested))editions.value=requested;
  const update=()=>{const url=editions.selectedOptions[0]?.dataset.shareUrl||'';share.hidden=!url;if(url)share.href=url;else share.removeAttribute('href');};
  editions.addEventListener('change',update);update();
 }
});
const banner=document.querySelector('[data-subscription-banner]');
if(banner){
 const url=new URL(location.href),confirmed=url.searchParams.get('subscribed')==='true',removed=url.searchParams.get('unsubscribed')==='true';
 if(confirmed||removed){
  banner.hidden=false;banner.querySelector('[data-subscription-confirmed]').hidden=!confirmed||removed;
  banner.querySelector('[data-subscription-unsubscribed]').hidden=!removed;
  banner.querySelector('.subscription-dismiss').addEventListener('click',()=>{
   banner.hidden=true;url.searchParams.delete('subscribed');url.searchParams.delete('unsubscribed');
   try{history.replaceState(null,'',url.href);}catch(e){}
  });
 }
}
})();
</script>'''


SUBSCRIPTION_BANNER_SCRIPT = "<script>(function(){const banner=" + SUBSCRIPTION_SCRIPT.split("const banner=", 1)[1]


def audience(ed):
    s = ed.get("site") or {}
    if s.get("audience"):
        return s["audience"]
    a = str(ed["reader"]["age"])
    try:
        n = int(a.split("-")[0])
        return "Ages 6–8" if n <= 8 else "Ages 9–11" if n <= 11 else "Ages 12–14" if n <= 14 else "Ages 15+"
    except ValueError:
        return "Ages 15+"


# Editorial starting points, with approximate reading times agreed for each age.
RECOMMENDED = {
    "Ages 6–8": ("little-explorers", "8–10", "A gentle first newspaper, with a big story, a science discovery and new words."),
    "Ages 9–11": ("breakfast-table", "10–15", "A good place to start: a short family paper with world news and something to talk about together."),
    "Ages 12–14": ("global-citizen-plus", "12–15", "A broader view of the world, with science, economics, an explainer and a quiz."),
    "Ages 15+": ("current-affairs-digest", "12–15", "For readers interested in Indian exam preparation: current affairs, key terms and a quiz."),
}


def weekend_choice(pdf):
    """Only called for variants successfully rendered in this build."""
    puzzles = pdf[:-4] + '-puzzles.pdf'
    return (f'<div class="weekend-download" data-news="{E(pdf)}" data-puzzles="{E(puzzles)}">'
            '<fieldset class="weekend-choice"><legend>Weekend paper</legend>'
            '<label><input type="radio" value="news" checked> News only</label>'
            '<label><input type="radio" value="puzzles"> News + Puzzles</label></fieldset>'
            '<p class="weekend-note" aria-live="polite">2 news pages. Optional extra: a story comic, word hunt and drawing.</p>')


WEEKEND_SCRIPT = """<script>
(()=>{
 const groups=[...document.querySelectorAll('.weekend-download')];if(!groups.length)return;
 const key='np-weekend-print';let selected='news';try{if(localStorage.getItem(key)==='puzzles')selected='puzzles';}catch(e){}
 function apply(value){groups.forEach((g,i)=>{
  g.querySelectorAll('input[type=radio]').forEach(r=>{r.name='weekend-print-'+i;r.checked=r.value===value;});
  const a=g.querySelector('a[data-weekend-pdf]');a.href=value==='puzzles'?g.dataset.puzzles:g.dataset.news;
  if(a.hasAttribute('download'))a.download=a.href.split('/').pop();
  g.querySelector('.weekend-note').textContent=value==='puzzles'?'3 pages: 2 news pages + 1 comic and puzzles page.':'2 news pages. Optional extra: a story comic, word hunt and drawing.';
 });}
 apply(selected);groups.forEach(g=>g.addEventListener('change',e=>{if(!e.target.matches('input[type=radio]'))return;apply(e.target.value);try{localStorage.setItem(key,e.target.value);}catch(err){}}));
})();
</script>"""


def weekend_link(pdf, label='Download PDF'):
    return (weekend_choice(pdf) + f'<a class="btn" data-weekend-pdf href="{E(pdf)}" download>{E(label)}</a>'
            + f'<noscript> <a data-weekend-fallback href="{E(pdf[:-4] + "-puzzles.pdf")}" download>News + Puzzles (3 pages)</a></noscript></div>')


def paper_actions(pdf, link, title, puzzles=False):
    actions = (f'<div class="edition-actions"><a class="btn recommended-print" href="{E(pdf)}" target="_blank" rel="noopener">'
            f'{navigation.icon("printer")} Print this paper</a>'
            f'<a class="btn ghost edition-share" href="{E(link)}" data-share-title="{E(title)}" '
            f'aria-label="Share this edition" title="Share this edition">{navigation.icon("share-2")}</a></div>'
            '<div class="share-feedback" hidden><p role="status"></p>'
            '<input type="text" readonly aria-label="Edition link to copy" hidden></div>')
    if puzzles:
        return weekend_choice(pdf) + actions.replace('class="btn recommended-print"', 'class="btn recommended-print" data-weekend-pdf') + f'<noscript><a data-weekend-fallback href="{E(pdf[:-4] + "-puzzles.pdf")}">News + Puzzles (3 pages)</a></noscript></div>'
    return actions


SHARE_SCRIPT = '''<script>
document.addEventListener('click',async event=>{
 const link=event.target.closest('a.edition-share');if(!link)return;
 event.preventDefault();
 const box=link.closest('.edition-actions').nextElementSibling,status=box.querySelector('[role="status"]'),input=box.querySelector('input');
 const url=link.href,title=link.dataset.shareTitle;
 box.hidden=true;input.hidden=true;status.textContent='';
 if(navigator.share){
  try{await navigator.share({title,text:title+' · Free newspaper to print and read together.',url});return;}
  catch(error){if(error.name==='AbortError')return;}
 }
 try{await navigator.clipboard.writeText(url);box.hidden=false;status.textContent='Edition link copied. Share it with another parent.';}
 catch(error){box.hidden=false;status.textContent='Copy this edition link to share it:';input.hidden=false;input.value=url;input.focus();input.select();}
});
</script>'''


def issue_landing(cfg, ed, date, issue, preview, puzzles=False):
    """A dated print/share destination; never redirects a recipient to a newer issue."""
    from . import share
    eid, n = ed['id'], len(ed['pages'])
    d = dt.date.fromisoformat(date)
    title = f'{ed["name"]} · {d:%d %B %Y} · {audience(ed)}'
    desc = f'{audience(ed)} · {n} pages · {d:%d %B %Y}. Free newspaper to preview and print.'
    cover = (f'<a href="{date}.pdf" target="_blank" rel="noopener"><img class="recommended-cover" src="{date}.png" '
             f'alt="Front page of {E(ed["name"])} on {d:%d %B %Y}"></a>' if preview else '')
    minutes = next((m for _, (ident, m, _) in RECOMMENDED.items() if ident == eid), None)
    body = (f'<article class="recommended shared-edition">{cover}<div class="recommended-copy">'
            f'<p class="recommended-label">{E(audience(ed))}</p><h2>{E(ed["name"])}</h2>'
            f'<p class="recommended-date">{d:%A %d %B %Y}</p>'
            f'<p class="recommended-facts">{n} page{"s" if n != 1 else ""}'
            + (f' · About {minutes} minutes to read' if minutes else '') + '</p>'
            f'<p class="recommended-reason">{E(lead_headline(ed, issue))}</p>'
            + paper_actions(f'{date}.pdf', f'{date}.html', title, puzzles)
            + f'<p class="recommended-note">Free PDF · US Letter. Use your device’s print controls.</p>'
            f'<a class="recommended-archive" href="{date}.pdf" target="_blank" rel="noopener">Preview this paper (PDF)</a>'
            '<br><a class="recommended-archive" href="../../index.html">Find more papers for your child</a></div></article>')
    return page(cfg, title, body, root='../../', here='papers',
                head_extra=share.tags(cfg, f'e/{eid}/{date}.html', title, desc, 'share/site.png', cfg['title']))


def recommendations(published, has_png, cfg=None):
    """Only recommend an edition whose PDF was successfully published in this build."""
    sections = []
    for band, (eid, minutes, reason) in RECOMMENDED.items():
        if eid not in published:
            continue
        ed, date = published[eid]
        cover = (f'<img class="recommended-cover" src="e/{eid}/cover.png" alt="Front page of {E(ed["name"])}">'
                 if has_png else "")
        n = len(ed["pages"])
        sections.append(f'''<article class="recommended" data-band="{E(band)}" data-edition="{eid}" hidden>
{cover}<div class="recommended-copy"><p class="recommended-label">A good place to start · {E(band)}</p>
<h2>{E(ed["name"])}</h2><p class="recommended-date">Latest issue · {dt.date.fromisoformat(date):%A %d %B %Y}</p>
<p class="recommended-facts">{n} page{'s' if n != 1 else ''} · About {minutes} minutes to read</p>
<p class="recommended-reason">{E(reason)}</p>{paper_actions(f'e/{eid}/{date}.pdf', f'e/{eid}/{date}.html', ed['name'] + ' · ' + band + ' · ' + date, (eid, date) in (cfg or {}).get('_weekend_pdfs', set()))}
<p class="recommended-note">Free PDF · US Letter. Use your device’s print controls.</p>
<a class="recommended-archive" href="e/{eid}/index.html">See past issues</a>{subscription_link(cfg or {}, ed)}</div></article>''')
    return ('<p id="age-memory" class="age-memory" role="status" hidden></p>'
            '<section id="recommendation" aria-label="Recommended paper" hidden>' + "".join(sections) + '</section>'
            '<div class="catalogue-heading"><h2 id="catalogue-title">Browse the newspapers</h2>'
            '<button type="button" id="browse-all" hidden>Browse all ages</button></div>')


def length_band(n):
    return "1 page" if n == 1 else "2 pages" if n == 2 else "3–4 pages" if n <= 4 else "5+ pages"


def frequency(ed):
    d = ed["cadence"]["every_days"]
    return "Daily" if d == 1 else "Every 2 days" if d == 2 else "Weekly" if d == 7 else f"Every {d} days"


def issues_of(ed):
    out = []
    for p in glob.glob(os.path.join(checks.issues_dir(ed), "**", "*.json"), recursive=True):
        m = checks.FNAME_RE.search(os.path.basename(p))
        if m:
            out.append((m.group(1), p))
    return sorted(out, reverse=True)


def sources_of(issue):
    seen, out = set(), []
    for b in issue.get("blocks", {}).values():
        for s in (b.get("sources", []) if isinstance(b, dict) else []):
            url = s.get("url") if isinstance(s, dict) else s
            if url and url not in seen:
                seen.add(url)
                out.append(s if isinstance(s, dict) else {"url": s})
    for s in issue.get("sources", []) or []:
        url = s.get("url") if isinstance(s, dict) else s
        if url and url not in seen:
            seen.add(url)
            out.append(s if isinstance(s, dict) else {"url": s})
    return out


def corrections():
    """data/corrections.yaml: fixes made to papers after they were published, newest first."""
    p = os.path.join(ROOT, "data", "corrections.yaml")
    rows = (yaml.safe_load(open(p, encoding="utf-8")) or []) if os.path.exists(p) else []
    rows = [{k: str(v) for k, v in r.items()} for r in rows]
    return sorted(rows, key=lambda r: (r["fixed"], r["issue"]), reverse=True)


def lead_headline(ed, issue):
    for bid in edition.story_blocks(ed):
        b = issue.get("blocks", {}).get(bid)
        if b and b.get("headline"):
            return b["headline"]
    return ""


CSS = """
:root{--paper:#F4F1EA;--surface:#fff;--ink:#1E2A32;--muted:#5B6870;--line:#DDD5C6;--cyan:#00727E;--cyan-t:#DDEFF0;--mag:#B8336A;--coral:#E2584D;
--display:"Bricolage Grotesque","Avenir Next","Segoe UI",system-ui,sans-serif;--text:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;
box-sizing:border-box;padding-bottom:env(safe-area-inset-bottom,0px)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#11181C;--surface:#182226;--ink:#E5ECEA;--muted:#9AA8AE;--line:#2D3A40;--cyan:#41B6C1;--cyan-t:#173438}}
*,*::before,*::after{box-sizing:inherit}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--text)}
a{color:var(--cyan)}h1,h2,h3{font-family:var(--display);line-height:1.1;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding:14px 20px 70px}
header.top{display:flex;align-items:center;gap:8px 16px;flex-wrap:wrap;border-bottom:1.5px solid var(--ink);margin:-14px -20px 12px;
  padding:calc(12px + env(safe-area-inset-top,0px)) 20px 10px;position:sticky;top:0;z-index:7;background:var(--paper)}
header.top h1{font-size:clamp(1.25rem,3vw,1.8rem);font-weight:800;letter-spacing:-.02em}
header.top h1 a{color:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:.3em}
.brandline{margin:3px 0 0;font-size:.75rem;line-height:1.3;color:var(--muted)}
header.top h1 .logo{width:1.6em;height:1.6em;flex:none;margin:-.2em 0}
.wm{display:inline-flex;flex-direction:column;line-height:1}.wm b{color:var(--coral)}
.stones{display:flex;gap:.12em;margin-top:.16em}
.stones i{display:block;height:.3em;width:.62em;border:.07em solid var(--ink);border-radius:58% 42% 55% 45%/52% 58% 42% 48%}
.stones i:nth-child(2){width:.46em}.stones i:nth-child(3){width:.54em}
nav{margin-left:auto;display:flex;flex-wrap:wrap;gap:4px 18px}nav a{font-weight:700;text-decoration:none}
.menu{display:none;margin-left:auto;font:inherit;font-weight:700;border:1.5px solid var(--line);background:var(--surface);color:var(--ink);border-radius:10px;padding:5px 10px;min-height:40px;cursor:pointer}
@media (max-width:999px){.js .menu{display:block}.js header.top nav{display:none;width:100%;flex-direction:column;gap:0;margin:0}
  .js header.top.open nav{display:flex}.js header.top nav a{padding:10px 2px;border-top:1px solid var(--line)}}
.intro{margin:0 0 6px}.intro .motto{margin:2px 0 0;font-family:var(--display);font-weight:800;font-size:clamp(1.25rem,2.6vw,1.6rem);letter-spacing:-.01em}.intro .lede{display:inline;margin:0 8px 0 0;color:var(--muted)}.how{display:inline}.how summary{display:inline}
.how summary{color:var(--cyan);font-weight:700;cursor:pointer;list-style:none}.how summary::-webkit-details-marker{display:none}
.how summary::after{content:" ›"}.how[open] summary::after{content:" ‹"}
.how[open]{display:block;margin-top:2px}.how .box{background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:14px 18px;margin:8px 0 6px}
.how h2{font-size:1.3rem;margin-bottom:6px}.how p{margin:0 0 12px;max-width:72ch}
.agebar{position:sticky;top:var(--hh,0px);z-index:5;background:var(--paper);display:flex;flex-wrap:wrap;align-items:center;gap:6px 14px;padding:8px 0 10px;margin:0 0 12px;border-bottom:1px solid var(--line)}
.agebar .lbl{font-weight:700;font-size:.92rem}
.seg{display:flex;background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:3px}
.seg button{font:inherit;font-weight:700;border:0;background:none;color:var(--ink);border-radius:9px;padding:7px 16px;min-height:40px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--paper)}
.agebar .count{color:var(--muted);font-size:.86rem}
.agebar .more{margin-left:auto;font:inherit;font-size:.92rem;font-weight:700;color:var(--cyan);background:none;border:0;cursor:pointer;padding:6px 0}
.agebar .more::after{content:" ▾"}.agebar .more[aria-expanded="true"]::after{content:" ▴"}
@media (max-width:699px){.agebar{position:static}}
@media (max-width:640px){.agebar .lbl{width:100%}.seg{flex:1 1 100%}.seg button{flex:1;padding:7px 4px}.agebar .more{margin-left:auto}}
.filters{display:grid;gap:10px;margin:0 0 16px}.frow{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.frow span{color:var(--muted);font-size:.9rem;min-width:84px}
.frow button{font:inherit;font-size:.9rem;border:1.5px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:5px 12px;cursor:pointer}
.frow button[aria-pressed="true"]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
button:focus-visible,a:focus-visible{outline:3px solid var(--cyan);outline-offset:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,250px),1fr));gap:18px}
[hidden]{display:none!important}
.card{background:var(--surface);border:1.5px solid var(--line);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:9px}
.cover{display:block;aspect-ratio:8.5/11;background:#FAF7F1;border:1px solid #B9C3C1;overflow:hidden}
.cover img{width:100%;height:100%;object-fit:cover;object-position:top;display:block}
.cover.soon{display:grid;place-items:center;color:#56646C;font-size:.9rem;text-align:center;padding:16px}
.card h2{font-size:1.2rem}.card p{margin:0;font-size:.93rem;color:var(--muted)}
.card .cover{aspect-ratio:8.5/8}@media (min-width:641px) and (max-width:999px){.card .cover{aspect-ratio:8.5/6.5}}
.new{display:inline-block;background:var(--cyan-t);color:var(--cyan);font-family:var(--text);font-size:.62em;font-weight:700;letter-spacing:.04em;border-radius:6px;padding:1px 6px;margin-left:6px;vertical-align:.2em}
.card.rp .cover{display:grid;place-items:center;background:#FFF8EE}.card.rp .cover img{width:46%;height:auto;object-fit:contain}
@media (max-width:640px){
  .grid{gap:10px}
  .card{display:grid;grid-template-columns:84px minmax(0,1fr);gap:3px 12px;padding:10px;align-content:start}
  .card>*{grid-column:2}.card .cover{grid-column:1;grid-row:1/span 6;align-self:start;aspect-ratio:8.5/11}
  .card h2{font-size:1.08rem}.card p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.88rem}
  .card .tag{margin-bottom:2px}.card .actions{margin-top:6px;gap:6px}.card .btn{font-size:.86rem;padding:7px 10px}}

.age-memory{font-size:.78rem;color:var(--muted);margin:0 0 14px}
.recommended{display:grid;grid-template-columns:180px minmax(0,1fr);gap:26px;background:var(--surface);border:1.5px solid var(--line);border-top:4px solid var(--cyan);border-radius:14px;padding:22px;margin:0 0 22px}
.recommended-cover{width:100%;height:auto;border:1px solid var(--line);align-self:start}
.recommended:not(:has(.recommended-cover)){grid-template-columns:1fr}
.recommended-label{font-size:.76rem;letter-spacing:.06em;text-transform:uppercase;font-weight:700;color:var(--cyan);margin:0 0 8px}
.recommended h2{font-size:clamp(1.5rem,3vw,2rem);margin:0 0 10px}
.recommended-date{font-size:.86rem;color:var(--muted);margin:0 0 10px}
.recommended-facts{font-size:.9rem;font-weight:700;margin:0 0 10px}
.recommended-reason{margin:0 0 18px;max-width:60ch}
.weekend-choice{border:0;padding:0;margin:12px 0 4px;display:flex;flex-wrap:wrap;gap:8px}.weekend-choice legend{font-weight:700;font-size:.8rem;margin-bottom:6px}.weekend-choice label{display:inline-flex;align-items:center;gap:6px;border:1px solid #B9C3C1;border-radius:8px;padding:8px 10px;font-size:.85rem;cursor:pointer;min-height:44px}.weekend-choice label:has(input:checked){background:#DDEFF0;border-color:#007D87}.weekend-choice input{accent-color:#007D87}.weekend-note{font-size:.78rem;color:#5C6970;margin:6px 0 12px}.weekend-download{max-width:100%}
.recommended-print{padding:12px 22px;min-height:48px}
.edition-actions{display:flex;align-items:stretch;gap:8px;clear:both}
.edition-share{display:inline-flex;align-items:center;justify-content:center;width:48px;min-width:48px;min-height:48px;padding:10px;font:inherit}
.edition-share:focus-visible{outline:3px solid var(--cyan);outline-offset:3px}
.share-feedback{font-size:.84rem;color:var(--cyan);margin-top:8px}
.share-feedback p{margin:0 0 6px}.share-feedback input{width:100%;min-width:0;min-height:44px;font:inherit;padding:8px}
.shared-edition{margin-top:24px}.shared-edition>.recommended-copy{min-width:0}
.shared-edition>a:has(.recommended-cover){align-self:start}
.recommended-note{font-size:.76rem;color:var(--muted);margin:8px 0}
.recommended-archive{display:inline-block;font-size:.84rem;font-weight:700;padding:7px 0;text-underline-offset:3px}
.catalogue-heading{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin:0 0 14px;padding-top:16px;border-top:1px solid var(--line)}
.catalogue-heading h2{font-size:1.15rem}
#browse-all{font:inherit;font-size:.84rem;font-weight:700;color:var(--cyan);background:none;border:0;cursor:pointer;min-height:44px;padding:7px 0;text-decoration:underline;text-underline-offset:3px}
@media(max-width:640px){
 .recommended{display:block;padding:16px}.recommended-cover{float:right;width:92px;margin:0 0 14px 14px}
 .recommended-copy{display:contents}.recommended-label{font-size:.7rem}.recommended-date{font-size:.78rem}
 .recommended-facts{clear:both;padding-top:8px;font-size:.85rem}.recommended-reason{font-size:.9rem}
 .recommended-print{display:block;flex:1;min-width:0}.recommended-note{font-size:.72rem}
 .catalogue-heading h2{font-size:1.05rem}
}

.meta{font-size:.84rem;color:var(--muted)}
.btn{display:inline-block;text-align:center;font-weight:700;background:var(--ink);color:var(--paper);text-decoration:none;border-radius:8px;padding:9px 12px}
.btn.ghost{background:transparent;color:var(--ink);border:1.5px solid var(--ink)}
.btn.poster{background:#E2584D;color:#fff}
.tag{align-self:flex-start;background:#E2584D;color:#fff;font-size:.75rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-radius:999px;padding:2px 10px}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:auto}.empty{color:var(--muted);padding:30px 0}
table{width:100%;border-collapse:collapse;font-size:.95rem}td,th{text-align:left;padding:9px 8px;border-bottom:1px solid var(--line);vertical-align:top}
details summary{cursor:pointer;color:var(--cyan)}details ul{margin:6px 0 0;padding-left:18px;font-size:.88rem}
.lede{display:grid;grid-template-columns:minmax(0,240px) minmax(0,1fr);gap:24px;margin-bottom:28px;align-items:start}
@media (max-width:640px){.lede{grid-template-columns:minmax(0,1fr)}}
.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:12px;margin:0;padding:0;list-style:none;counter-reset:s}
.steps li{counter-increment:s;padding-left:34px;position:relative;font-size:.95rem}
.steps li::before{content:counter(s);position:absolute;left:0;top:-1px;width:24px;height:24px;border-radius:50%;background:var(--cyan);color:var(--paper);font-weight:700;display:grid;place-items:center;font-size:.85rem}
.tabbar{display:none}
@media (max-width:699px){
  header.top nav,.js .menu{display:none!important}
  header.top .home-masthead h1{font-size:clamp(1.625rem,3.9vw,2.34rem)}
  .home-masthead .brandline{font-size:.9rem}
  .wrap{padding-bottom:110px}
  .tabbar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--surface);border-top:1.5px solid var(--line);
    padding:4px 4px calc(4px + env(safe-area-inset-bottom,0px))}
  .tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:52px;font-size:12px;font-weight:700;
    line-height:1.2;color:var(--muted);text-decoration:none;border-radius:10px;text-align:center}
  .tabbar a span{font-size:21px;line-height:1.15}
  .tabbar a[aria-current="page"]{color:var(--ink);background:var(--cyan-t)}}
footer{margin-top:40px;color:var(--muted);font-size:.86rem;border-top:1px solid var(--line);padding-top:14px}
footer .owner{margin:6px 0 0;font-size:.8rem}footer .owner a{color:var(--muted)}footer .links{margin:8px 0 0}footer .links a{color:var(--muted);font-weight:700}
#reading-data button{font:inherit;min-height:44px}
.doc{max-width:68ch}.doc h3{font-size:1.15rem;margin:22px 0 4px}.doc ul{padding-left:20px}.doc li{margin:4px 0}
.doc ul.fixes{list-style:none;padding:0}.doc ul.fixes li{border-top:1px solid var(--line);padding:12px 0}
.meta.fixed{color:#9A3B2E;margin:4px 0 0}
"""

def fonts(root=""):
    """The site's fonts, served from this site (assets/fonts/web, copied to fonts/): no outside requests."""
    return (f'<link rel="preload" href="{root}fonts/BricolageGrotesque-latin.woff2" as="font" type="font/woff2" crossorigin>'
            f'<link rel="stylesheet" href="{root}fonts/fonts.css">')


GOOGLE_FONTS = re.compile(r'<link rel="preconnect" href="https://fonts\.(?:googleapis|gstatic)\.com"[^>]*>\s*'
                          r'|<link href="https://fonts\.googleapis\.com/css2\?[^"]*" rel="stylesheet">')


def self_host_assets(html, root=""):
    """A page written elsewhere (the builder) switched to this site's fonts and Pyodide."""
    from . import vendor
    out = GOOGLE_FONTS.sub("", html)
    out = out.replace("</head>", fonts(root) + "</head>", 1)
    return re.sub(r'const PYODIDE = "https://cdn\.jsdelivr\.net/pyodide/v[^"]*/full/";',
                  f'const PYODIDE = "{root}{vendor.SITE_DIR}";', out)


CSS += """
.parents{max-width:850px}.parents>h2{font-size:2rem;margin:8px 0 12px}
.parent-links{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:14px;margin:24px 0}
.parent-link{display:block;border:1.5px solid var(--line);background:var(--surface);padding:16px;border-radius:12px;text-decoration:none;color:var(--ink)}
.parent-link b{display:block;color:var(--cyan);margin-bottom:6px}.parent-link span{font-size:.9rem;color:var(--muted)}
"""


CSS += navigation.STYLE + SUBSCRIPTION_STYLE


def feedback_nav(cfg, root=""):
    return f'<a href="{root}feedback.html">Feedback</a>' if cfg.get("feedback_url") else ""


def tabbar(cfg, root, here):
    """The phone's bottom bar: the same links as the header, one tap from anywhere on the page."""
    tabs = [("papers", "index.html", "house", "Home"), ("play", "play/index.html", "headphones", "Read &amp; Play"),
            ("design", "builder.html", "pencil", "Design"), ("parents", "parents.html", "users", "For parents")]
    if cfg.get("kids_mode"):                    # the app: Listen instead of Design (which is in For parents)
        tabs[1:3] = [("play", "play/index.html", "newspaper", "Read &amp; Play"),
                     ("listen", "play/listen.html", "headphones", "Listen")]
    if here in ("about", "feedback"):
        here = "parents"
    now = ' aria-current="page"'
    return ('<nav class="tabbar" aria-label="Pages">' + "".join(
        f'<a href="{root}{href}"{now if k == here else ""}><span aria-hidden="true">{navigation.icon(icon)}</span>{label}</a>'
        for k, href, icon, label in tabs) + "</nav>")


LICENSES = {"CC BY-NC 4.0": "https://creativecommons.org/licenses/by-nc/4.0/"}


def owner_line(cfg, root=""):
    """Who makes the site, what people may do with the papers, and how to reach us: the footer's last line."""
    bits = []
    if cfg.get("publisher"):
        bits.append(f"© {dt.date.today().year} {E(cfg['publisher'])}")
    if cfg.get("license"):
        link = LICENSES.get(cfg["license"])
        bits.append(f'Papers free to print and share, not to sell (<a href="{link}" rel="noopener license">{E(cfg["license"])}</a>)'
                    if link else E(cfg["license"]))
    if cfg.get("info_email"):
        bits.append(f'Contact: <a href="mailto:{E(cfg["info_email"])}">{E(cfg["info_email"])}</a>')
    return f'<p class="owner">{" · ".join(bits)}</p>' if bits else ""


def page(cfg, title, body, root="", head_extra="", here="papers"):
    contact = f' · Corrections: <a href="mailto:{E(cfg["contact"])}">{E(cfg["contact"])}</a>' if cfg.get("contact") else ""
    if cfg.get("feedback_url"):
        contact += f' · Spotted a mistake, or have an idea? <a href="{root}feedback.html">Tell us</a>'

    brandline = f'<p class="brandline">{E(cfg["tagline"])}</p>' if here == "papers" and not root else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{E(title)}</title><meta name="description" content="{E(cfg['tagline'] if cfg['description'] == cfg['tagline'] else cfg['tagline'] + ' ' + cfg['description'])}">
<link rel="icon" href="{root}owl.svg" type="image/svg+xml"><link rel="icon" href="{root}favicon.png" sizes="32x32">
{pwa.head(cfg, root)}{fonts(root)}{head_extra}<style>{CSS}</style>{stats.snippet(cfg, root)}
<script>document.documentElement.classList.add("js")</script></head>
<body><div class="wrap"><header class="top"><div class="masthead{' home-masthead' if brandline else ''}"><h1><a href="{root}index.html" aria-label="{E(cfg['title'])} · Free Kids Newspaper and Daily Newsletter">{brand.inline()}{brand.wordmark(cfg['title'])}</a></h1>{brandline}</div>
<button type="button" class="menu" aria-expanded="false" aria-controls="nav">☰ Menu</button>
<nav id="nav"><a href="{root}index.html">Home</a><a href="{root}play/index.html">Read &amp; Play</a>{f'<a href="{root}play/listen.html">Listen</a>' if cfg.get("kids_mode") else f'<a href="{root}builder.html">Design</a>'}<a href="{root}parents.html">For parents</a></nav></header>
{pwa.tablet_prompt()}
<script>(function(){{const h=document.querySelector("header.top"),b=h.querySelector(".menu");
b.addEventListener("click",()=>b.setAttribute("aria-expanded",String(h.classList.toggle("open"))));
const hh=()=>document.documentElement.style.setProperty("--hh",h.offsetHeight+"px");hh();
if(window.ResizeObserver)new ResizeObserver(hh).observe(h);else addEventListener("resize",hh);}})()</script>
{body}<footer>Written by AI from verified news sources, then checked automatically. Every issue lists its sources{contact}.
<p class="links"><a href="{root}about.html">How it's made</a> · <a href="{root}standards.html">Editorial standards</a> · <a href="{root}corrections.html">Corrections</a> · <a href="{root}privacy.html">Privacy</a> · <a href="{root}terms.html">Terms</a></p>{owner_line(cfg, root)}</footer></div>
{tabbar(cfg, root, here)}{WEEKEND_SCRIPT if 'class="weekend-download"' in body else ''}{SHARE_SCRIPT if 'data-share-title=' in body else ''}{SUBSCRIPTION_SCRIPT if 'data-gate-form=' in body else SUBSCRIPTION_BANNER_SCRIPT if 'data-subscription-banner' in body else ''}</body></html>"""


def credit(cfg):
    """The line every printed page ends with: who publishes it, how it's made, and where to report a mistake."""
    return (f"A {cfg['title']} paper" + (f"  ·  {cfg['domain']}" if cfg.get("domain") else "")
            + "  ·  Written and fact-checked by AI"
            + (f"  ·  Corrections: {cfg['corrections_email']}" if cfg.get("corrections_email") else ""))


def byline(cfg):
    """The lead story's byline on the site's papers: no person writes or checks them, so none is named."""
    return f"Written and fact-checked by AI · {cfg['title']}"


def qr_url(cfg, eid, date):
    """Where an issue's printed QR code goes: its Read & Play page. Papers from before
    `qr_from` (site.yaml) were published without one and stay as they were."""
    start = str(cfg.get("qr_from") or "")
    if not start or not cfg.get("base_url") or date < start:
        return None
    return f"{cfg['base_url'].rstrip('/')}/play/{eid}/{date}.html"


def home_json_ld(cfg):
    """Structured data (Schema.org JSON-LD) for search engines without changing visual content."""
    base = cfg.get("base_url", "https://newspebbles.com/").rstrip("/")
    org_id = f"{base}/#organization"
    items = [
        {
            "@type": "WebSite",
            "@id": f"{base}/#website",
            "url": f"{base}/",
            "name": cfg.get("title", "News Pebbles"),
            "alternateName": [
                "News Pebbles Kids Newspaper",
                "News Pebbles Daily Kids Newsletter",
                "News Pebbles Children's Newspaper",
                "Free Kids Newspaper"
            ],
            "description": cfg.get("description", ""),
            "inLanguage": "en-US",
            "publisher": {"@id": org_id}
        },
        {
            "@type": "NewsMediaOrganization",
            "@id": org_id,
            "name": cfg.get("title", "News Pebbles"),
            "url": f"{base}/",
            "logo": f"{base}/share/site.png",
            "publishingPrinciples": f"{base}/standards.html",
            "correctionsPolicy": f"{base}/corrections.html",
            "ethicsPolicy": f"{base}/standards.html",
            "knowsAbout": [
                "Kids Newspaper",
                "Kids Newsletter",
                "Children's News",
                "Current Events for Kids",
                "Printable Student Newspaper",
                "Elementary Education",
                "Middle School Current Affairs"
            ],
            "about": [
                {
                    "@type": "Thing",
                    "name": "Children's newspaper",
                    "sameAs": "https://en.wikipedia.org/wiki/Children%27s_newspaper"
                },
                {
                    "@type": "Thing",
                    "name": "Newsletter",
                    "sameAs": "https://en.wikipedia.org/wiki/Newsletter"
                }
            ]
        }
    ]
    scripts = []
    for item in items:
        obj = {"@context": "https://schema.org"}
        obj.update(item)
        scripts.append(f'<script type="application/ld+json">{json.dumps(obj, ensure_ascii=False)}</script>')
    return "\n".join(scripts)


def build(out, keep=None, log=print, kids=False):
    """The website in `out`. kids=True: the app build (ygc/kids.py): Parental Gate, no visit counting."""
    cfg = site_config()
    cfg["kids_mode"] = bool(kids)
    keep = keep or int(cfg["keep_issues"])
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    shutil.copy(os.path.join(ROOT, "assets", "navigation", "LICENSE"), os.path.join(out, "navigation-icons-LICENSE.txt"))
    has_png = bool(shutil.which("pdftoppm"))
    cards = []          # (has_issue, audience order, name, html)
    fixes, names = corrections(), {}
    published = {}
    cfg["_weekend_pdfs"] = set()
    for eid in edition.list_editions():
        ed = edition.load(eid)
        names[eid] = ed["name"]
        s = ed.get("site") or {}
        if s.get("listed") is False:
            continue
        edir = os.path.join(out, "e", eid)
        os.makedirs(edir, exist_ok=True)
        rows, items, latest = [], [], None
        posters, latest_poster = {}, None          # "Big Question" posters, a companion download
        for date, p in poster.posters_of(ed)[:keep]:
            spec = json.load(open(p, encoding="utf-8"))
            try:
                poster.build(ed, spec, os.path.join(edir, f"{date}-poster.pdf"), credit=credit(cfg), author=cfg["title"])
            except Exception as e:
                log(f"  ! {eid} poster {date}: {e}"); continue
            posters[date] = spec
            if latest_poster is None:
                latest_poster = date
                shutil.copy(os.path.join(edir, f"{date}-poster.pdf"), os.path.join(edir, "latest-poster.pdf"))
        for date, p in issues_of(ed)[:keep]:
            issue = json.load(open(p, encoding="utf-8"))
            pdf = f"{date}.pdf"
            try:
                render.build(ed, issue, os.path.join(edir, pdf), qr=qr_url(cfg, eid, date), credit=credit(cfg),
                             byline=byline(cfg), author=cfg["title"])
            except Exception as e:
                log(f"  ! {eid} {date}: {e}"); continue
            extras = False
            if (cfg.get("weekend_puzzles") or {}).get("enabled") is True:
                try:
                    extras = weekend.build(ed, date, issue, os.path.join(edir, pdf), os.path.join(edir, f"{date}-puzzles.pdf"))
                except Exception as error:
                    log(f"  ! {eid} weekend {date}: {error}; news only")
                if extras:
                    cfg['_weekend_pdfs'].add((eid, date))
            preview = os.path.join(edir, f"{date}.png")
            if has_png:
                subprocess.run(["pdftoppm", "-png", "-r", "60", "-f", "1", "-l", "1", "-singlefile",
                                os.path.join(edir, pdf), os.path.join(edir, date)], check=False)
            open(os.path.join(edir, f"{date}.html"), "w", encoding="utf-8").write(
                issue_landing(cfg, ed, date, issue, os.path.exists(preview), extras))
            if latest is None:
                latest = (date, issue)
                if extras:
                    shutil.copy(os.path.join(edir, f"{date}-puzzles.pdf"), os.path.join(edir, "latest-puzzles.pdf"))
                shutil.copy(os.path.join(edir, pdf), os.path.join(edir, "latest.pdf"))
                if os.path.exists(preview):
                    shutil.copy(preview, os.path.join(edir, "cover.png"))
            d = dt.date.fromisoformat(date)
            srcs = "".join(f'<li><a href="{E(x.get("url", ""))}" rel="noopener">{E(x.get("title") or x.get("url", ""))}</a>'
                           f'{" — " + E(x["outlet"]) if x.get("outlet") else ""}</li>'
                           for x in sources_of({"sources": sources_of(issue) + sources_of(posters.get(date, {}))}))
            ptd = f' <a class="btn ghost" href="{date}-poster.pdf" download>Poster</a>' if date in posters else ""
            fixed = "".join(f'<p class="meta fixed">Corrected {dt.date.fromisoformat(c["fixed"]):%d %b}: {E(c["what"])} '
                            f'<a href="../../corrections.html">All corrections</a></p>'
                            for c in fixes if c["paper"] == eid and c["issue"] == date)
            download = weekend_link(pdf) if extras else f'<a class="btn ghost" href="{pdf}" download>PDF</a>'
            rows.append(f'<tr><td>{d:%a %d %b %Y}</td><td>No. {issue.get("issue", "")}</td>'
                        f'<td>{E(lead_headline(ed, issue))}{fixed}<details><summary>Sources</summary><ul>{srcs}</ul></details></td>'
                        f'<td>{download}{ptd}</td></tr>')
            link = f'{cfg["base_url"].rstrip("/")}/e/{eid}/{pdf}' if cfg["base_url"] else pdf
            items.append(f"<item><title>{E(ed['name'])}, No. {issue.get('issue', '')}: {E(lead_headline(ed, issue))}</title>"
                         f"<link>{E(link)}</link><guid>{E(link)}</guid>"
                         f"<pubDate>{d:%a, %d %b %Y} 06:00:00 GMT</pubDate></item>")
        if latest:
            published[eid] = (ed, latest[0])
        n = len(ed["pages"])
        meta = f"{audience(ed)} · {n} page{'s' if n != 1 else ''} · {frequency(ed)}"
        blurb = s.get("blurb") or ed["reader"]["profile"]
        focus = s.get("focus") or "World affairs"
        cover = (f'<a class="cover" href="e/{eid}/index.html"><img src="e/{eid}/cover.png" alt="Front page of the latest {E(ed["name"])} kids newspaper edition" loading="lazy"></a>'
                 if latest and has_png else f'<a class="cover soon" href="e/{eid}/index.html">{"Latest issue" if latest else "First issue coming soon"}</a>')
        dl = (f'<a class="btn" href="e/{eid}/latest.pdf" download="{eid}-{latest[0]}.pdf">Download PDF</a>'
              if latest else "")
        if latest and (eid, latest[0]) in cfg['_weekend_pdfs']:
            dl = weekend_link(f'e/{eid}/{latest[0]}.pdf')
        cards.append((latest is None, FACET_ORDER.get(audience(ed), 50), ed["name"], f'''<article class="card" data-kind="paper" data-edition="{E(eid)}" data-audience="{E(audience(ed))}" data-length="{E(length_band(n))}" data-focus="{E(focus)}" data-frequency="{E(frequency(ed))}">
{cover}<h2>{E(ed['name'])}<!--NEW--></h2><p>{E(blurb)}</p><div class="meta">{E(meta)}{f" · latest {dt.date.fromisoformat(latest[0]):%d %b}" if latest else ""}</div>
<div class="actions">{dl}<a class="btn ghost" href="e/{eid}/index.html">All issues</a></div></article>''', latest and latest[0]))
        if latest_poster:                          # the poster gets its own card, thumbnail and download
            if has_png:
                subprocess.run(["pdftoppm", "-png", "-r", "60", "-singlefile", os.path.join(edir, "latest-poster.pdf"),
                                os.path.join(edir, "poster-cover")], check=False)
            pq = posters[latest_poster]["question"]
            pcover = (f'<a class="cover" href="e/{eid}/latest-poster.pdf"><img src="e/{eid}/poster-cover.png" '
                      f'alt="The latest Big Question poster: {E(pq)}" loading="lazy"></a>' if has_png
                      else f'<a class="cover soon" href="e/{eid}/latest-poster.pdf">{E(pq)}</a>')
            pmeta = f"{audience(ed)} · 1-page poster · {frequency(ed)} · latest {dt.date.fromisoformat(latest_poster):%d %b}"
            cards.append((False, FACET_ORDER.get(audience(ed), 50), ed["name"] + " poster", f'''<article class="card" data-kind="poster" data-audience="{E(audience(ed))}" data-length="1 page" data-focus="{E(focus)}" data-frequency="{E(frequency(ed))}">
{pcover}<span class="tag">Poster</span><h2>The Big Question<!--NEW--></h2><p>One big idea from this week's news on a single page: a picture to explore, something to try at home and questions to talk about together. This week: &ldquo;{E(pq)}&rdquo;</p><div class="meta">{E(pmeta)} · from {E(ed["name"])}</div>
<div class="actions"><a class="btn poster" href="e/{eid}/latest-poster.pdf" download="{eid}-{latest_poster}-poster.pdf">Download poster</a><a class="btn ghost" href="e/{eid}/index.html">All posters</a></div></article>''', latest_poster))
        # edition page
        desks = ", ".join(d["label"].title() for d in ed["desks"] if d["id"] != "top")
        top = (f'<a class="btn" href="latest.pdf" download="{eid}-{latest[0]}.pdf">Download the latest issue (PDF)</a>'
               if latest else '<p class="empty">The first issue hasn\'t been published yet.</p>')
        if latest and (eid, latest[0]) in cfg['_weekend_pdfs']:
            top = weekend_link(f'{latest[0]}.pdf', 'Download the latest issue (PDF)')
        if latest_poster:
            q = posters[latest_poster]["question"]
            top += (f' <a class="btn poster" href="latest-poster.pdf" download="{eid}-{latest_poster}-poster.pdf">Download the poster (PDF)</a>'
                    f'<p class="meta">Also this week: a one-page <b>Big Question</b> poster, &ldquo;{E(q)}&rdquo;, with pictures, '
                    f'something to try and questions to talk about together.</p>')
        img = f'<img src="cover.png" alt="" style="width:100%;border:1px solid #B9C3C1">' if latest and has_png else ""
        body = (f'<section class="lede"><div>{img}</div><div><h2 style="font-size:2rem">{E(ed["name"])}</h2>'
                f'<p>{E(blurb)}</p><p class="meta">{E(meta)}<br>Covers: {E(desks)}</p><div>{top}</div>'
                f'<p class="meta"><a href="feed.xml">RSS feed</a> for new issues.</p></div></section>'
                + subscription_form(cfg, ed, root='../../', context='archive', date=latest[0] if latest else None)
                + (f'<h2 style="font-size:1.3rem;margin-bottom:6px">Issues</h2><table><tr><th>Date</th><th>Issue</th><th>Top story</th><th></th></tr>{"".join(rows)}</table>' if rows else ""))
        open(os.path.join(edir, "index.html"), "w", encoding="utf-8").write(page(cfg, ed["name"], body, root="../../",
             head_extra=f'<link rel="alternate" type="application/rss+xml" href="feed.xml" title="{E(ed["name"])}">'))
        open(os.path.join(edir, "feed.xml"), "w", encoding="utf-8").write(
            f'<?xml version="1.0" encoding="utf-8"?><rss version="2.0"><channel><title>{E(ed["name"])}</title>'
            f'<link>{E(cfg["base_url"])}</link><description>{E(blurb)}</description>{"".join(items)}</channel></rss>')
        log(f"  {eid}: {len(rows)} issue(s)")

    newest = max((c[4] for c in cards if c[4]), default="")
    cards = [c[3].replace("<!--NEW-->", ' <span class="new">NEW</span>' if c[4] and c[4] == newest else "")
             for c in sorted(cards, key=lambda c: c[:3])]
    cards.append(f'''<article class="card rp" data-always="1"><a class="cover" href="play/index.html"><img src="owl.svg" alt="" loading="lazy"></a>
<h2>Read &amp; Play</h2><p>The latest papers on screen for children: read aloud if they like, with a game at the end.</p>
<div class="actions"><a class="btn poster" href="play/index.html">Open Read &amp; Play</a></div></article>''')
    # front page with filters
    def facet(name, label, values):
        vals = sorted(set(values), key=lambda v: (FACET_ORDER.get(v, 50), v))
        return (f'<div class="frow" role="group" aria-label="{label}"><span>{label}</span><button type="button" data-f="{name}" data-v="" aria-pressed="true">All</button>'
                + "".join(f'<button type="button" data-f="{name}" data-v="{E(v)}" aria-pressed="false">{E(v)}</button>' for v in vals) + "</div>")
    import re as _re
    attrs = lambda k: _re.findall(rf'data-{k}="([^"]*)"', "".join(cards))
    ages = sorted(set(attrs("audience")), key=lambda v: (FACET_ORDER.get(v, 50), v))
    agebar = ('<div class="agebar"><span class="lbl" id="agel">Choose your child\'s age to find their paper</span><div class="seg" role="group" aria-labelledby="agel">'
              '<button type="button" data-f="audience" data-v="" aria-pressed="true">All</button>'
              + "".join(f'<button type="button" data-f="audience" data-v="{E(v)}" aria-pressed="false">{E(v.replace("Ages ", ""))}</button>' for v in ages)
              + '</div><span class="count" aria-live="polite"></span>'
              '<button type="button" class="more" aria-expanded="false" aria-controls="filters">More filters</button></div>')
    filters = agebar + ('<div class="filters" id="filters" hidden>' + facet("length", "Length", attrs("length"))
                        + facet("focus", "Focus", attrs("focus")) + facet("frequency", "How often", attrs("frequency")) + "</div>")
    # The age is remembered on this device, and shared with Read & Play (its "rp-band").
    script = """<script>
(function(){
const st={audience:"",length:"",focus:"",frequency:""},$$=(s)=>[...document.querySelectorAll(s)],count=document.querySelector('.agebar .count');
const plural=(n,w)=>n+" "+w+(n===1?"":"s");
let remembered=false,returning=false;
function saveAge(){try{localStorage.setItem("rp-band",JSON.stringify(st.audience));remembered=!!st.audience;}catch(e){remembered=false;}}
function apply(){
  $$('button[data-f]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.v===st[b.dataset.f])));
  let papers=0,posters=0;$$('.grid .card').forEach(c=>{const ok=c.dataset.always||Object.entries(st).every(([k,v])=>!v||c.dataset[k]===v);
    c.hidden=!ok;if(ok&&c.dataset.kind==="paper")papers++;if(ok&&c.dataset.kind==="poster")posters++;});
  count.textContent=plural(papers,"paper")+(posters?" · "+plural(posters,"poster"):"");
  document.getElementById('none').hidden=papers+posters>0;
  let featured=false;$$('.recommended').forEach(r=>{
    const card=$$('.grid .card[data-kind="paper"]').find(c=>c.dataset.edition===r.dataset.edition);
    const show=r.dataset.band===st.audience&&card&&!card.hidden;
    r.hidden=!show;if(show){card.hidden=true;featured=true;}
  });
  document.getElementById('recommendation').hidden=!featured;
  const age=st.audience.replace('Ages ','');
  document.getElementById('catalogue-title').textContent=featured&&papers+posters===1?'Explore more':age?(featured?'More choices for ages ':'Papers for ages ')+age:'Browse the newspapers';
  document.getElementById('browse-all').hidden=!Object.values(st).some(Boolean);
  const memory=document.getElementById('age-memory');memory.hidden=!age;
  memory.textContent=remembered?(returning?'Your saved age: '+age+'. Change it any time.':'Age saved on this device. Change it any time.'):'For ages '+age+'. Change your choice any time.';
}
function set(f,v){st[f]=v;apply();}
$$('button[data-f]').forEach(b=>b.addEventListener('click',()=>{
  if(b.dataset.f==="audience"){st.audience=b.dataset.v;returning=false;saveAge();}
  set(b.dataset.f,b.dataset.v);
}));
let age="";try{age=JSON.parse(localStorage.getItem("rp-band")||'""')||"";}catch(e){}
remembered=returning=!!age;
set("audience",$$('button[data-f="audience"]').some(b=>b.dataset.v===age)?age:"");
document.getElementById('browse-all').addEventListener('click',()=>{
  Object.keys(st).forEach(k=>st[k]="");returning=false;saveAge();apply();
});
const more=document.querySelector('.agebar .more'),box=document.getElementById('filters');
more.addEventListener('click',()=>{box.hidden=!box.hidden;more.setAttribute('aria-expanded',String(!box.hidden));});
})();
</script>"""
    how = ""
    if cfg["intro_title"] or cfg["intro"]:                 # the parents' intro, one tap away
        heading = f'<h2>{E(cfg["intro_title"])}</h2>' if cfg["intro_title"] else ""
        text = f'<p>{E(cfg["intro"])}</p>' if cfg["intro"] else ""
        steps = "".join(f"<li>{E(x)}</li>" for x in cfg["steps"])
        steps = f'<ol class="steps">{steps}</ol>' if steps else ""
        how = f'<details class="how"><summary>How it works</summary><div class="box">{heading}{text}{steps}</div></details>'
    intro = (f'<section class="intro"><p class="motto">{E(cfg["home_headline"])}</p>'
             f'<p class="lede">{E(cfg["description"])}</p>{how}</section>')
    body = subscription_banner() + intro + filters + recommendations(published, has_png, cfg) + f'<div class="grid">{"".join(cards)}</div><p id="none" class="empty" hidden>No paper matches all of those. Try removing a filter.</p>' + script
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(page(cfg, cfg["title"], body, head_extra=home_json_ld(cfg)))
    trust_pages(cfg, out, names, fixes)
    open(os.path.join(out, "parents.html"), "w", encoding="utf-8").write(
        page(cfg, f"For parents · {cfg['title']}", parents_body(cfg, published), here="parents"))
    shutil.copytree(os.path.join(brand.ASSETS, "fonts", "web"), os.path.join(out, "fonts"), dirs_exist_ok=True)
    for lic in ("OFL-AtkinsonHyperlegible.txt", "OFL-BricolageGrotesque.txt"):
        shutil.copy(os.path.join(brand.ASSETS, "fonts", lic), os.path.join(out, "fonts", lic))
    shutil.copy(brand.SVG, os.path.join(out, "owl.svg"))                    # the logo, and the browser-tab icon
    shutil.copy(os.path.join(brand.ASSETS, "owl-32.png"), os.path.join(out, "favicon.png"))
    for f in glob.glob(os.path.join(brand.ASSETS, "google*.html")):
        shutil.copy(f, os.path.join(out, os.path.basename(f)))
    for txt in ("llms.txt", "llms-full.txt"):
        src = os.path.join(brand.ASSETS, txt)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(out, txt))
    find_src = os.path.join(ROOT, "seo", "site")
    if os.path.isdir(find_src):
        shutil.copytree(find_src, os.path.join(out, "find"), dirs_exist_ok=True)
    b = os.path.join(ROOT, "tools", "newspaper-builder.html")
    if os.path.exists(b):
        html = (open(b, encoding="utf-8").read().replace("<!--FEEDBACK-->", feedback_nav(cfg))
                .replace("<!--PARENT_NAV-->", tabbar(cfg, "", "design"))
                .replace("</head>", pwa.head(cfg) + "<style>" + BUILDER_NAV_CSS + navigation.STYLE + "</style>" + stats.snippet(cfg) + "</head>", 1))
        open(os.path.join(out, "builder.html"), "w", encoding="utf-8").write(self_host_assets(html))
        engine_zip(os.path.join(out, "builder-engine.zip"))
        from . import vendor                 # Pyodide, for the builder page only
        vendor.copy_into(out, log=log)
    if cfg.get("feedback_url"):
        open(os.path.join(out, "feedback.html"), "w", encoding="utf-8").write(
            page(cfg, "Feedback", feedback_body(cfg["feedback_url"], cfg), here="feedback"))
    from . import play                      # the children's side: read online and play
    play.build(out, cfg, keep=min(keep, int(cfg.get("play_keep", 7))), log=log)
    from . import share                     # how links look when shared; sitemap, robots.txt, 404
    share.build(out, cfg, log=log)
    if cfg["kids_mode"]:
        from . import kids
        kids.finish(out, cfg, log=log)
    open(os.path.join(out, ".nojekyll"), "w").close()
    log(f"site written to {out}")
    return out


BUILDER_NAV_CSS = """
.tabbar{display:none}
@media(max-width:699px){
 .wrap{padding-bottom:180px}.site nav{display:none}
 .bar{bottom:calc(78px + env(safe-area-inset-bottom,0px))}
 .tabbar{position:fixed;display:flex;left:0;right:0;bottom:0;z-index:6;background:var(--surface);border-top:1.5px solid var(--line);padding:4px 6px calc(4px + env(safe-area-inset-bottom,0px))}
 .tabbar a{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:58px;font-size:12px;line-height:1.2;font-weight:700;color:var(--muted);text-decoration:none;border-radius:10px}
 .tabbar a span{font-size:22px}.tabbar a[aria-current="page"]{color:var(--cyan);background:var(--cyan-tint)}
}
@media print{.tabbar{display:none!important}}
"""


def reading_data_controls():
    return '''<section id="reading-data" class="doc" style="margin-top:28px;scroll-margin-top:calc(var(--hh,90px) + 16px)"><h3>Reading data on this device</h3>
<p>You can reset the age choice, reading and game progress, pebbles, badges, garden, saved listening position,
reading settings, and any saved name or city in this browser on this device. Your paper designs and visit-counting choice are kept.</p>
<button type="button" class="btn ghost" id="reading-reset">Reset this device’s reading data</button>
<div id="reading-reset-confirm" hidden><p><b>Reset all reading data in this browser?</b> This cannot be undone.
Other open News Pebbles reading pages will reload. Data in other browsers or on other devices is not affected.</p>
<button type="button" class="btn" id="reading-reset-yes">Reset reading data</button>
<button type="button" class="btn ghost" id="reading-reset-cancel">Cancel</button></div>
<p id="reading-reset-status" role="status"></p></section>
<script>(function(){
const start=document.getElementById('reading-reset'),box=document.getElementById('reading-reset-confirm'),
yes=document.getElementById('reading-reset-yes'),cancel=document.getElementById('reading-reset-cancel'),status=document.getElementById('reading-reset-status');
start.addEventListener('click',()=>{box.hidden=false;start.hidden=true;status.textContent='';cancel.focus();});
cancel.addEventListener('click',()=>{box.hidden=true;start.hidden=false;start.focus();});
yes.addEventListener('click',()=>{
 try{
  const keys=[];for(let i=0;i<localStorage.length;i++){const key=localStorage.key(i);if(key&&key.startsWith('rp-'))keys.push(key);}
  keys.forEach(key=>localStorage.removeItem(key));
  localStorage.setItem('np-reading-reset',String(Date.now()));
  status.textContent='Reading data reset in this browser. Your paper designs and visit-counting choice have been kept.';
 }catch(e){status.textContent='Some reading data could not be cleared. Try again, or clear News Pebbles data in your browser settings.';}
 box.hidden=true;start.hidden=false;start.focus();
});
})();</script>'''


# The app build's settings on For parents: filled in and shown by app.js only inside the app.
APP_BOX = """<style>.np-appbox{background:var(--surface);border:1.5px solid var(--line);border-radius:16px;padding:14px 16px 4px;margin:14px 0 20px}
.np-appbox h3{margin:0 0 4px;font-size:1.3rem}
.np-row{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--line)}
.np-row>label,.np-row>span:first-child{display:flex;flex-direction:column}.np-row span span,.np-row label span{color:var(--muted);font-size:.92rem}
.np-ctl{display:flex;align-items:center;gap:10px;flex:none}
.np-ctl input[type=time]{font:inherit;font-weight:700;border:1.5px solid var(--line);border-radius:10px;padding:6px 8px;background:var(--paper);color:var(--ink);min-height:44px}
.np-switch{appearance:none;-webkit-appearance:none;width:51px;height:31px;border-radius:16px;background:#C9C3B8;position:relative;cursor:pointer;margin:0;flex:none;transition:background .2s}
.np-switch::after{content:"";position:absolute;left:2px;top:2px;width:27px;height:27px;border-radius:50%;background:#fff;box-shadow:0 1px 3px #0003;transition:left .2s}
.np-switch:checked{background:#34C759}.np-switch:checked::after{left:22px}
.np-switch:focus-visible{outline:3px solid var(--cyan);outline-offset:2px}
.np-ok{color:#2E7D4F;white-space:nowrap}.np-note{color:var(--muted);font-size:.9rem;margin:10px 0}</style>
<section class="np-appbox" id="np-app" hidden aria-labelledby="np-app-h"><h3 id="np-app-h">This app</h3>
<div class="np-row"><label for="np-rem-on"><b>Morning reminder</b><span>&ldquo;Today&rsquo;s papers are ready&rdquo;, at</span></label>
<span class="np-ctl"><input type="time" id="np-rem-time" value="07:00" aria-label="Reminder time">
<input type="checkbox" id="np-rem-on" class="np-switch" role="switch"></span></div>
<div class="np-row"><span><b>Saved for offline</b><span id="np-off-what">Papers and audio from the last 7 days</span></span>
<b class="np-ok" id="np-off-state"></b></div>
<p class="np-note" id="np-off-note"></p></section>"""



def parents_body(cfg, published=None):
    feedback = '<a class="parent-link" href="feedback.html"><b>Corrections &amp; feedback</b><span>Report a mistake or share an idea.</span></a>' if cfg.get("feedback_url") else ''
    app = bool(cfg.get("kids_mode"))
    return f'''<section class="parents"><h2>For parents</h2>{APP_BOX if app else ""}
<p>Help your child understand the world, on paper and together.</p>
<p><a class="btn" href="index.html">{navigation.icon("printer")} Choose and print a paper</a></p>
{subscription_form(cfg, published=published)}{autoprint_guide() if subscription_endpoint(cfg) else ""}
<div class="parent-links">
<a class="parent-link" href="builder.html"><b>Design your own paper</b><span>Make a printable newspaper for your family.</span></a>
<a class="parent-link" href="play/index.html#today"><b>Reading settings</b><span>Choose an age in Read &amp; Play. Text size, night mode and narration speed are available inside each paper and stay on this device.</span></a>
<a class="parent-link" href="about.html"><b>How it’s made</b><span>How the papers are researched, written and checked.</span></a>
<a class="parent-link" href="standards.html"><b>Editorial standards</b><span>Our approach to sources, accuracy and age-appropriate news.</span></a>
<a class="parent-link" href="corrections.html"><b>Corrections</b><span>See changes made to published papers.</span></a>
{feedback}<a class="parent-link" href="privacy.html"><b>Privacy</b><span>What is saved on this device and how the site works.</span></a>
<a class="parent-link" href="terms.html"><b>Terms</b><span>What you may do with the papers, and what we promise.</span></a>
</div>{reading_data_controls()}</section>'''


def feedback_body(url, cfg=None):
    """The feedback page: a Google Form shown on the page, or a button to any other form. In the app build
    (kids mode) nothing loads from Google: the same form opens from a button, and email works too."""
    cfg = cfg or {}
    full = "docs.google.com/forms/" in url
    src = (url.split("?")[0].replace("/edit", "/viewform") + "?embedded=true") if full else url
    form = (f'<iframe src="{E(src)}" title="Feedback form" style="width:100%;min-height:1100px;border:0" loading="lazy">'
            f'Loading…</iframe>' if full else "")
    if cfg.get("kids_mode"):
        mails = [f'<a href="mailto:{E(cfg[k])}">{E(cfg[k])}</a> {what}' for k, what in
                 (("contact", "for a mistake in a paper"), ("info_email", "for anything else")) if cfg.get(k)]
        form = f'<p>Or email us: {" or ".join(mails)}.</p>' if mails else ""
    return f"""<h2 style="font-size:2rem;margin-bottom:10px">Feedback</h2><div style="max-width:68ch">
<p>Tell us what works, what doesn't, and what you'd like next: a mistake in a paper, an idea for a section, a
paper for an age we don't cover yet, or a problem with <i>Design your own</i>. We read everything.</p>
<p>Please don't include your child's full name or anything that identifies them. Leave an email only if you'd like a reply.</p>
<p><a class="btn" href="{E(url)}" target="_blank" rel="noopener">Open the feedback form</a></p>{form if cfg.get("kids_mode") else ""}</div>{"" if cfg.get("kids_mode") else form}"""


# ------------------------------------------------------------------ how it's made, standards, corrections, privacy
def _doc(title, html):
    return f'<h2 style="font-size:2rem;margin-bottom:10px">{E(title)}</h2><div class="doc">{html}</div>'


def report_line(cfg, root=""):
    """How a reader tells us about a mistake: the feedback form, and the email when site.yaml gives one."""
    ways = []
    if cfg.get("feedback_url"):
        ways.append(f'use the <a href="{root}feedback.html">feedback form</a>')
    if cfg.get("contact"):
        ways.append(f'email <a href="mailto:{E(cfg["contact"])}">{E(cfg["contact"])}</a>')
    return f"To report a mistake, {' or '.join(ways)}." if ways else ""


def who_makes(cfg):
    if not cfg.get("publisher"):
        return ""
    ask = f' Questions: <a href="mailto:{E(cfg["info_email"])}">{E(cfg["info_email"])}</a>.' if cfg.get("info_email") else ""
    return (f'<h3>Who makes News Pebbles</h3><p>{E(cfg["title"])} is made by <b>{E(cfg["publisher"])}</b>, which is responsible for '
            f'everything published here.{ask} {report_line(cfg)}</p>')


def about_body(cfg):
    return _doc("How it's made", f"""
<p>Every paper here is written and checked by AI, automatically, overnight. Here is exactly what happens.</p>
{who_makes(cfg)}
<h3>1. Research</h3>
<p>Each night an AI research desk (Claude, made by Anthropic) searches the news for every topic the day's papers cover. It keeps a
fact only if it can point to a page the search actually found, and it notes that page. It never fills a gap from memory, and records
and &ldquo;firsts&rdquo; go in only when a source says them. Stories too graphic for younger readers are marked, and never used in
papers for under-15s.</p>
<h3>2. Writing</h3>
<p>Each paper due that day is written from that research alone, following its own instructions: the reader's age, what the paper is
for, which countries and topics it covers, and how long it is. All papers follow the same <a href="standards.html">editorial
standards</a>. Age changes the words and explanations, never the standard of accuracy.</p>
<h3>3. Checking</h3>
<p>Before anything is published, automatic checks confirm every section is complete, the date is right, the layout fits the printed
page with nothing cut off, the games are complete, and every story lists its sources. The AI then rereads every figure, name,
place and date against its research and removes anything the research doesn't support. A paper that still fails after several tries
isn't published, and the previous issue stays up.</p>
<h3>4. Publishing</h3>
<p>Papers that pass go up on this site straight away, as a printable PDF and in Read &amp; Play. <b>No person reads each paper before
it goes up.</b> We read every piece of feedback and fix mistakes as soon as we hear about them, and list every fix on the
<a href="corrections.html">corrections page</a>.</p>
<h3>It can still be wrong</h3>
<p>AI makes mistakes, and early reports change. Every issue lists its sources on its paper's page, so you can check anything before
handing it over. {report_line(cfg)}</p>
<p>You can also <a href="builder.html">design a paper for your own child</a>: the page writes instructions for your own AI chatbot, then
checks its reply and prints it with the same engine as our papers.</p>""")


def standards_body(cfg):
    return _doc("Editorial standards", f"""
<p>These are the rules every paper is written to. They are part of the instructions the AI follows each night, and the automatic
checks enforce the ones a computer can test.</p>
<h3>Accurate at every age</h3>
<ul><li>Every figure, name and date comes from a source the research actually found, and every story lists its sources.</li>
<li>Nothing is filled in from memory. Records and &ldquo;firsts&rdquo; appear only when a source states them.</li>
<li>When sources disagree, we use the most recent and most official one, or leave the detail out.</li>
<li>Age changes the vocabulary, the explanations and the size of the type. It never changes the facts.</li></ul>
<h3>Honest about hard news, without graphic detail</h3>
<ul><li>Wars, disasters and crime are reported honestly, without graphic or frightening detail.</li>
<li>Papers for the youngest readers say what happened and who is helping.</li>
<li>Stories whose core facts are too graphic for children are never used in papers for under-15s.</li>
<li>Read &amp; Play's games for 6&ndash;8s leave out stories about war and disaster.</li></ul>
<h3>Fair</h3>
<ul><li>Disputed claims are reported as the claims of whoever made them, with the other side's answer in its own terms.</li>
<li>Quotes are short and used only when the exact words matter, such as a threat, a promise or a legal claim.</li>
<li>Stories report what happened and what each side says. Questions at the end ask readers what they think; the papers don't tell
them what to think.</li>
<li>A story is chosen for how much it matters, never to suit a map or a chart.</li></ul>
<h3>Clear</h3>
<ul><li>New words are explained, and so is the background a story depends on.</li>
<li>Readers are never left to do the arithmetic: comparisons are stated, not implied.</li>
<li>Each paragraph leads into the next, so a young reader can follow the whole story.</li></ul>
<h3>Independent</h3>
<ul><li>There are no ads and no sponsors. Nobody pays to be in a paper.</li>
<li>We don't collect anything about your child. See <a href="privacy.html">privacy</a>.</li></ul>
<h3>When we get it wrong</h3>
<p>We fix the paper, and say on the <a href="corrections.html">corrections page</a> and next to the issue what was wrong and what it
now says. {report_line(cfg)}</p>""")


def corrections_body(cfg, names, fixes):
    if fixes:
        rows = "".join(
            f'<li><b><a href="e/{E(c["paper"])}/index.html">{E(names.get(c["paper"], c["paper"]))}</a>, '
            f'{dt.date.fromisoformat(c["issue"]):%d %B %Y}</b><br>{E(c["what"])}'
            f'<br><span class="meta">Corrected {dt.date.fromisoformat(c["fixed"]):%d %B %Y}</span></li>' for c in fixes)
        listing = f'<ul class="fixes">{rows}</ul>'
    else:
        listing = '<p class="empty">No corrections yet.</p>'
    return _doc("Corrections", f"""
<p>When a published paper turns out to be wrong, we fix it and list the fix here, newest first. Each fix also shows next to the issue
on its paper's page, and the corrected PDF replaces the old one. {report_line(cfg)}</p>{listing}""")


def privacy_contact(cfg):
    if not cfg.get("privacy_email"):
        return ""
    by = f" {E(cfg['title'])} is made by {E(cfg['publisher'])}." if cfg.get("publisher") else ""
    return (f'<h3>Questions about privacy</h3><p>Email <a href="mailto:{E(cfg["privacy_email"])}">{E(cfg["privacy_email"])}</a>.'
            f'{by}</p>')


def privacy_body(cfg):
    counting = bool(stats.endpoint(cfg))
    counts = ("""<h3>What we count</h3>
<p>To learn whether the papers are useful, the site counts visits with <a href="https://www.goatcounter.com" rel="noopener">GoatCounter</a>,
a small, privacy-first counter. It uses no cookies, and we send it only which page was opened, and these anonymous events:</p>
<ul><li>a paper was opened in Read &amp; Play today (once per device per day);</li>
<li>a device opened its first paper, or came back the day after, or 7 days after, its first paper;</li>
<li>a paper was read to the end;</li><li>the car-ride brief was started, or played to near its end;</li><li>a PDF was downloaded.</li></ul>
<p>We never send a name, an age, an answer, a score or any ID. GoatCounter keeps only totals for each day, such as &ldquo;opened a paper
today: 40&rdquo;, plus broad facts like browser, country and language. To avoid counting the same visit twice it holds the visitor's
network address and browser type in memory for up to 8 hours, and never stores them (see
<a href="https://www.goatcounter.com/help/privacy" rel="noopener">its privacy policy</a>).</p>
<p>Nothing is counted when your browser asks sites not to track you (Do Not Track or Global Privacy Control), or after you press this
button:</p>
<p><button type="button" class="btn" id="nocount">Don't count this device</button> <span id="nocount-state" class="meta"></span></p>
<script>(function(){var b=document.getElementById("nocount"),st=document.getElementById("nocount-state");
function get(){try{return localStorage.getItem("np-nocount")==="1"}catch(e){return false}}
function show(){var off=get();b.textContent=off?"Count this device again":"Don't count this device";
st.textContent=off?"This device isn't counted.":"This device is counted.";}
b.addEventListener("click",function(){try{if(get())localStorage.removeItem("np-nocount");else localStorage.setItem("np-nocount","1")}catch(e){}show();});show();})()</script>"""
              if counting else "<h3>What we count</h3><p>Nothing: visits aren't counted at the moment.</p>")
    return _doc("Privacy", f"""
<p><b>The short version:</b> no accounts, no ads, no cookies, and children never need to identify themselves. Children never need to give
a name, an email or their age.</p>
<h3>What stays on your device</h3>
<p>News Pebbles remembers your chosen age band in this browser on this device. Read &amp; Play also remembers text size, night mode,
narration speed, the last story and listening position for up to 80 recent editions, the reading streak, pebbles, badges and garden,
game stars, recent answers (for the progress page), the date of the first paper read, your selected city, and a name only if one is
typed on a certificate or report. These choices and progress stay on this device; we do not send them to ourselves or anyone else.</p>
<p>To remove this reading data, use <a href="parents.html#reading-data">Reset this device’s reading data</a> in For parents.
This keeps your paper designs and visit-counting choice. You can also clear all News Pebbles data in your browser settings.</p>
{counts}
{('<h3 id="email-delivery">Optional email delivery for grown-ups</h3><p>Only a parent or carer needs to give an email address. If you subscribe, we store that address, your chosen newspaper and delivery frequency, confirmation/unsubscribe tokens and delivery records in Cloudflare D1. Resend processes the address and sends confirmation and paper emails. We do not send reading progress, age selections saved on your device, game answers or garden data with a subscription. A hashed email/network-address counter limits repeated requests.</p><p>Confirm by email before delivery begins. Every message has an unsubscribe link, which stops future emails for that paper. Delivery history is kept to prevent duplicate sends. For deletion of your subscription information, contact us using the privacy address below. Email links shared through WhatsApp contain the paper’s public links, not your email address. Choosing WhatsApp opens that service; it is optional.</p>') if subscription_endpoint(cfg) else ''}
<h3>Optional analyst responses (ages 12+)</h3>
<p>You Make the Call first saves a choice on this device. Only pressing “Add my response” sends that choice, the public
question identifier and a random receipt for that question to our Cloudflare Worker. No name, account or email is requested.
The receipt prevents ordinary repeat submissions from this browser and lets a changed choice update the same response.
It is not a verified count of unique people. The server stores the choice and a hashed receipt for up to 90 days;
short-lived, secret-hashed network counters limit abuse and expire after two hours. The hosting provider handles network
addresses when serving requests. Aggregate results appear only after five responses and are not a representative survey.</p>
<p>In the kids app a grown-up must unlock sharing before any voting request. Sharing is optional and does not affect
completion or rewards. Resetting this device’s reading data clears local choices and receipts; it does not retract a
previously shared anonymous response. Server records expire automatically.</p>
<h3>Other services the site uses</h3>
<ul>{f'<li><b>Inside the app</b>, every page, picture, recording and typeface is saved on the device. On its own it fetches only each day&rsquo;s papers, from {E(cfg.get("domain") or "our website")} (GitHub Pages, which like any web host sees the device&rsquo;s network address). Optional response sharing contacts Cloudflare only after the grown-up question. Links to other websites, email and sharing open only after a grown-up answers a question.</li>' if cfg.get("kids_mode") else '<li><b>GitHub Pages</b> hosts the site. Like any web host, it sees the address of each device that visits.</li>'}
<li><b>Typefaces and the Design-your-own engine</b> are served from {E(cfg["title"])} itself, not from Google or other font and code services.</li>
<li><b>Read aloud</b> normally plays pre-generated AI recordings made with Kokoro. They are generated during publishing and served
as audio files from this site, rather than generated from a child's voice or reading activity. Your browser may cache recordings
for offline playback. If a recording is unavailable, or for short definitions and game prompts, we use a device or browser voice.
The car-ride brief on Read &amp; Play is made the same way, with two AI voices; its podcast link lets a podcast app fetch the recordings
from this site, and sends us nothing about who listens.
Some browser voices use an online service, so the text being spoken may be sent to that voice provider. Your microphone is not used.
Saved listening positions stay in this browser on this device.</li>
{('<li><b>The feedback form</b> is a Google Form' + (', which opens in your browser only after the grown-up question' if cfg.get("kids_mode") else '') + '. Please don&rsquo;t include your child&rsquo;s full name or anything that identifies them.</li>') if cfg.get("feedback_url") else ""}</ul>
<h3>The News Pebbles app (iPhone and iPad)</h3>
<p>The app shows these same pages. When it opens, it downloads the day&rsquo;s papers and recordings from {E(cfg.get("domain") or "this website")}
and keeps the last 7 days on the device, so they work offline. It counts nothing, has no ads and no account, and sends nothing else to us
or anyone else. The morning reminder is a notification the device sets for itself, at the time a grown-up chooses in For parents.
Reading data in the app stays on the device; deleting the app deletes it.</p>
<h3>Printed papers</h3>
<p>The QR code on a printed paper opens that paper's page in Read &amp; Play. It carries nothing about who scanned it.</p>
{privacy_contact(cfg)}""")


def terms_body(cfg):
    who = E(cfg.get("publisher") or cfg["title"])
    lic = cfg.get("license") or ""
    link = LICENSES.get(lic)
    if link:
        use = (f'<p>The papers, posters and Read &amp; Play stories are licensed under <a href="{link}" rel="noopener license">{E(lic)}</a>. '
               f'In short: you may print, copy and share them, at home, in a classroom or online, as long as you say they come from '
               f'{E(cfg["title"])} ({E(cfg.get("domain") or "")}) and you don\'t sell them or use them to make money. You may adapt them '
               f'for your own children or class, under the same terms.</p>')
    else:
        use = "<p>You may print and share the papers for personal, family and classroom use. Please don't sell them.</p>"
    contact = f'<a href="mailto:{E(cfg["info_email"])}">{E(cfg["info_email"])}</a>' if cfg.get("info_email") else ""
    return _doc("Terms", f"""
<p>{E(cfg["title"])} is made by <b>{who}</b>. By using this site you agree to these terms. They are short on purpose.</p>
<h3>Free to use</h3>
<p>Everything here is free: no accounts, no ads, no payments.</p>
<h3>Printing and sharing</h3>
{use}
<p>Not included: the {E(cfg["title"])} name and owl logo (please don't use them to suggest we made something we didn't), and the
articles, pictures and data of the outside sources each issue lists, which belong to their owners. The site's fonts and map data
keep their own open licences.</p>
<h3>Written and checked by AI</h3>
<p>The papers are researched, written and checked by AI, and <b>no person reviews each paper before it is published</b> (see
<a href="about.html">How it's made</a>). We work hard to make them accurate and right for each age, but they can contain mistakes,
and news changes. Every issue lists its sources so you can check anything before handing it to a child. The papers are for
learning and conversation; they aren't professional, legal, medical or financial advice.</p>
<h3>Children</h3>
<p>The papers are written for children to read, ideally with a grown-up. Children don't need to give any personal information to
use the site. A parent or teacher decides which paper suits their child. See <a href="privacy.html">Privacy</a> for what is stored
on the device.</p>
<h3>Other websites</h3>
<p>Links to sources and other sites are there so you can check what we wrote. We don't control those sites and aren't responsible
for them.</p>
<h3>No guarantee</h3>
<p>We provide the site and papers as they are. We don't promise they will always be available, complete or error-free, and to the
extent the law allows, {who} isn't liable for losses that come from using them.</p>
<h3>Mistakes and questions</h3>
<p>{report_line(cfg)} We list every fix on the <a href="corrections.html">corrections page</a>.{f" Anything else: {contact}." if contact else ""}</p>
<h3>Changes</h3>
<p>We may update these terms; the date below shows the latest version. Continuing to use the site means you accept the update.</p>
<p class="meta">Last updated {TERMS_UPDATED.day} {TERMS_UPDATED:%B %Y}.</p>""")


TERMS_UPDATED = dt.date(2026, 10, 25)


def trust_pages(cfg, out, names, fixes):
    for fn, title, body in (("about.html", "How it's made", about_body(cfg)),
                            ("terms.html", "Terms", terms_body(cfg)),
                            ("standards.html", "Editorial standards", standards_body(cfg)),
                            ("corrections.html", "Corrections", corrections_body(cfg, names, fixes)),
                            ("privacy.html", "Privacy", privacy_body(cfg))):
        open(os.path.join(out, fn), "w", encoding="utf-8").write(page(cfg, f"{title} · {cfg['title']}", body, here="about"))


def engine_zip(path):
    """The engine for the builder page, which runs it in the browser (Pyodide): the ygc
    package, the craft rules and poster guide its chatbot instructions quote, and the
    pure-Python ReportLab it draws with (the same version as the published papers)."""
    import zipfile
    import reportlab
    rl = os.path.dirname(reportlab.__file__)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for base, rel_to, keep in ((os.path.join(ROOT, "ygc"), ROOT, (".py",)),
                                   (rl, os.path.dirname(rl), (".py",))):
            for d, dirs, files in os.walk(base):      # papers use only the built-in PDF fonts
                dirs[:] = sorted(x for x in dirs if x not in ("__pycache__", "fonts"))
                for f in sorted(files):
                    if f.endswith(keep):
                        full = os.path.join(d, f)
                        z.write(full, os.path.relpath(full, rel_to))
        z.write(os.path.join(ROOT, "data", "world", "countries.topo.json"), "data/world/countries.topo.json")
        for f in ("CRAFT_RULES.md", "POSTERS.md"):
            z.write(os.path.join(ROOT, "docs", f), f"docs/{f}")
    return path


FACET_ORDER = {"Ages 6–8": 1, "Ages 9–11": 2, "Ages 12–14": 3, "Ages 15+": 4,
               "1 page": 1, "2 pages": 2, "3–4 pages": 3, "5+ pages": 4, "Daily": 1, "Every 2 days": 2, "Weekly": 3}
