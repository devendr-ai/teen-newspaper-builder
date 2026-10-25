"""Usage counts: privacy-first, no cookies, nothing about the child.

Every page gets a tiny counter that loads GoatCounter's 1x1 counting image
(https://www.goatcounter.com/help/pixel) with the page path and title, and
nothing else: no cookie, no referrer, no screen size, no ID. Read & Play adds
a few anonymous events (a reader today, a paper finished, came back a day or a
week after the first visit); the dates those need stay on the device.

The counter is off until `goatcounter` in site.yaml names a GoatCounter site
(its code, or the full /count URL of a self-hosted one). It never counts when
the browser asks not to be tracked, when a test robot drives it, on a
developer's own machine, or after "Don't count this device" on the privacy page.
"""
import json


def endpoint(cfg):
    if cfg.get("kids_mode"):                     # the app build counts nothing (ygc/kids.py)
        return ""
    code = str(cfg.get("goatcounter") or "").strip()
    if not code:
        return ""
    return code if "://" in code else f"https://{code}.goatcounter.com/count"


def snippet(cfg, root=""):
    """The counter for the head of a page; `root` is the page's way back to the site's top."""
    url = endpoint(cfg)
    if not url:
        return ""
    return ("<script>(function(){var U=" + json.dumps(url) + ",R=" + json.dumps(root or "./") + ";"
            "function off(){try{if(localStorage.getItem(\"np-nocount\")===\"1\")return true}catch(e){}"
            "return navigator.doNotTrack===\"1\"||navigator.globalPrivacyControl===true||navigator.webdriver===true"
            "||/^(localhost|127\\.|0\\.0\\.0\\.0|\\[::1\\]|)$/.test(location.hostname)}"
            "var base=new URL(R,location.href).pathname;"
            "window.npCount=function(p,t,ev){if(off())return;var i=new Image();i.referrerPolicy=\"no-referrer\";"
            "i.src=U+\"?p=\"+encodeURIComponent(p)+\"&t=\"+encodeURIComponent(t||\"\")+(ev?\"&e=true\":\"\")"
            "+\"&rnd=\"+Math.random().toString(36).slice(2)};"
            "var p=location.pathname;p=\"/\"+(p.indexOf(base)===0?p.slice(base.length):p).replace(/(^|\\/)index\\.html$/,\"$1\");"
            "npCount(p,document.title);"
            "document.addEventListener(\"click\",function(e){var a=e.target.closest&&e.target.closest(\"a[download]\");"
            "if(a){var q=new URL(a.href).pathname;npCount(\"download\"+(q.indexOf(base)===0?\"/\"+q.slice(base.length):q),"
            "\"Downloaded: \"+(a.getAttribute(\"download\")||q),true)}})})()</script>")
