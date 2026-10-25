"""Shared screen-navigation visuals, matching the approved mobile mock-up.

Lucide icons are bundled in assets/navigation with their upstream license.
"""
from functools import lru_cache
from pathlib import Path

from .edition import ROOT


@lru_cache(maxsize=8)
def icon(name):
    svg = (Path(ROOT) / "assets" / "navigation" / f"{name}.svg").read_text(encoding="utf-8")
    return svg.replace('<svg', '<svg class="ui-icon" aria-hidden="true" focusable="false"', 1)


STYLE = """
.ui-icon{display:inline-block;width:20px;height:20px;vertical-align:-.2em;flex:none}
.tabbar{--nav-active:#00727E;--nav-active-bg:#DDEFF0;background:var(--surface,var(--card));gap:4px;
 padding:8px 7px calc(8px + env(safe-area-inset-bottom,0px));border-top:1px solid var(--line)}
.tabbar a{gap:5px;min-width:0;min-height:58px;padding:7px 2px;border-radius:10px;
 font-size:12px;font-weight:700;line-height:1.2;color:var(--muted);text-align:center}
.tabbar a span{display:flex;align-items:center;justify-content:center;line-height:1}
.tabbar .ui-icon{display:block;width:22px;height:22px;stroke-width:2}
.tabbar a[aria-current="page"]{color:var(--nav-active);background:var(--nav-active-bg)}
.tabbar a:focus-visible{outline:3px solid var(--nav-active);outline-offset:2px}
@media(prefers-color-scheme:dark){:root:not([data-theme]) .tabbar{--nav-active:#62C6CD;--nav-active-bg:#203D40}}
:root[data-theme="night"] .tabbar,:root[data-theme="dark"] .tabbar{--nav-active:#62C6CD;--nav-active-bg:#203D40}
"""
