"""One installed app for the newsstand, reader and design pages."""
import html
import json


def head(cfg, root=""):
    return f'''<link rel="manifest" href="{root}manifest.webmanifest">
<meta name="theme-color" content="#E2584D">
<link rel="apple-touch-icon" href="{root}play/icon-180.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{html.escape(cfg['title'])}">'''


def manifest(cfg, legacy_reader=False):
    # The old /play/ manifest remains available to existing reader installations.
    # Its scope expands to the site root; new installs share the root manifest.
    root = "../" if legacy_reader else "./"
    icons = "" if legacy_reader else "play/"
    return json.dumps({
        "id": root + "index.html",
        "name": cfg["title"], "short_name": cfg["title"],
        "description": "Today's news for children: read it, hear it, play a game.",
        "start_url": "./index.html", "scope": root, "display": "standalone",
        "background_color": "#FFF8EE", "theme_color": "#E2584D",
        "icons": [{"src": f"{icons}icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any maskable"}
                  for n in (192, 512)]}, ensure_ascii=False, indent=1)


def tablet_prompt():
    """A tablet-only invitation; no requests, libraries or changes to phone/desktop layouts."""
    return TABLET_PROMPT


TABLET_PROMPT = r'''
<style>
#np-tablet-install[hidden],#np-install-help:not([open]){display:none!important}
#np-tablet-install{box-sizing:border-box;display:flex;align-items:center;gap:8px;min-height:44px;padding:0 12px;margin:0;background:#E3EEEE;color:#1D2D34;font:13px/1.4 system-ui,sans-serif}
#np-tablet-install>span{flex:1}
#np-tablet-install button{box-sizing:border-box;font:700 13px/1.4 system-ui,sans-serif;min-height:44px;border:0;background:transparent;color:#007782;padding:6px 10px;cursor:pointer;white-space:nowrap}
#np-tablet-install .np-install-dismiss{min-width:44px;color:#58686E;padding:0}
#np-install-help{box-sizing:border-box;width:380px;max-width:calc(100% - 32px);max-height:calc(100% - 32px);overflow:auto;padding:22px;border:1px solid #DED9CD;border-radius:16px;background:#FFFDF7;color:#1D2D34;font:16px/1.5 system-ui,sans-serif;box-shadow:0 10px 40px #0003}
#np-install-help::backdrop{background:#17252D70}
#np-install-help h2{font:700 21px/1.25 system-ui,sans-serif;margin:0 0 14px}
#np-install-help ol{padding-left:22px;margin:10px 0 18px}
#np-install-help li{margin:10px 0}
#np-install-help p{font-size:14px;margin:10px 0}
#np-install-help .np-install-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
#np-install-help button{font:700 14px/1.4 system-ui,sans-serif;min-height:44px;padding:8px 12px;border:1px solid #D5D4CB;border-radius:8px;background:#FFFDF7;color:#007782;cursor:pointer}
#np-install-help button[data-installed]{background:#007782;color:#FFF;border-color:#007782}
#np-tablet-install button:focus-visible,#np-install-help button:focus-visible{outline:3px solid #007782;outline-offset:2px}
:root[data-theme="night"] #np-tablet-install{background:#263F40;color:#EDF0EA}
:root[data-theme="night"] #np-tablet-install button{color:#89DCDE}
@media print{#np-tablet-install,#np-install-help{display:none!important}}
</style>
<aside id="np-tablet-install" aria-label="Install News Pebbles" hidden>
<span>Keep News Pebbles handy.</span><button type="button" data-install-open>Add to Home Screen ↗</button>
<button type="button" class="np-install-dismiss" aria-label="Dismiss install prompt for 30 days">×</button>
</aside>
<dialog id="np-install-help" aria-labelledby="np-install-title">
<h2 id="np-install-title">Add News Pebbles to Home Screen</h2>
<div data-install-ipad hidden><p>In Safari:</p><ol><li>Tap <strong>Share ↥</strong> in the browser toolbar.</li><li>Choose <strong>Add to Home Screen</strong>. You may need to tap <strong>More</strong> or scroll.</li><li>Keep <strong>Open as Web App</strong> on if shown, then tap <strong>Add</strong>.</li></ol></div>
<div data-install-android hidden><p>Open your browser's <strong>⋮ menu</strong>, then choose <strong>Install app</strong> or <strong>Add to Home screen</strong> and confirm.</p></div>
<p>Already added it? Tell us below and this prompt won't appear again in this browser.</p>
<div class="np-install-actions"><button type="button" data-install-close>Not now</button><button type="button" data-installed>I've added it</button></div>
</dialog>
<script>
(() => {
  const ua = navigator.userAgent, ipad = /iPad/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const android = /Android/i.test(ua) && !/Mobile/i.test(ua) && Math.min(screen.width, screen.height) >= 600;
  if (!ipad && !android) return;
  document.documentElement.setAttribute('data-tablet-install', '');
  const bar = document.getElementById('np-tablet-install'), help = document.getElementById('np-install-help');
  const open = bar.querySelector('[data-install-open]'), key = 'np-app-installed', later = 'np-app-install-dismissed-until';
  const mode = matchMedia('(display-mode: standalone)');
  const get = k => { try { return localStorage.getItem(k); } catch (_) { return null; } };
  const set = (k, v) => { try { localStorage.setItem(k, v); } catch (_) {} };
  let prompt = null, installed = get(key) === 'true', snoozed = Number(get(later)) || 0;
  const hide = () => { bar.hidden = true; if (help.open) help.close(); };
  const markInstalled = () => { installed = true; set(key, 'true'); prompt = null; hide(); };
  const refresh = () => {
    if (mode.matches || navigator.standalone) { markInstalled(); return; }
    if (get(key) === 'true') installed = true;
    snoozed = Math.max(snoozed, Number(get(later)) || 0);
    bar.hidden = installed || snoozed > Date.now();
    if (bar.hidden && help.open) help.close();
  };
  help.querySelector(ipad ? '[data-install-ipad]' : '[data-install-android]').hidden = false;
  if (android) { bar.firstElementChild.textContent = 'News Pebbles, one tap away.'; open.textContent = 'Install app ↓'; }
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); prompt = event; refresh();
  });
  window.addEventListener('appinstalled', markInstalled);
  mode.addEventListener('change', refresh);
  window.addEventListener('pageshow', refresh);
  window.addEventListener('storage', refresh);
  open.addEventListener('click', async () => {
    if (installed) return;
    if (android && prompt) {
      const request = prompt; prompt = null; open.disabled = true;
      try {
        await request.prompt();
        if ((await request.userChoice).outcome === 'accepted') markInstalled();
      } catch (_) { if (!installed) help.showModal(); }
      finally { open.disabled = false; }
      return;
    }
    help.showModal();
  });
  const dismiss = () => { snoozed = Date.now() + 30 * 86400000; set(later, String(snoozed)); hide(); };
  bar.querySelector('.np-install-dismiss').addEventListener('click', dismiss);
  help.querySelector('[data-install-close]').addEventListener('click', dismiss);
  help.querySelector('[data-installed]').addEventListener('click', markInstalled);
  help.addEventListener('cancel', dismiss);
  refresh();
})();
</script>'''
