"""Tablet install invitation and its persistent, device-specific lifecycle."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from ygc import play, pwa, site


def test_tablet_prompt_is_on_parent_pages_and_reader_lobby_only():
    cfg = site.site_config()
    for root in ("", "../../"):
        markup = site.page(cfg, "Paper", "<main>Paper</main>", root=root)
        assert markup.count('id="np-tablet-install"') == 1
        assert 'id="np-tablet-install" aria-label="Install News Pebbles" hidden' in markup
    lobby = play.shell(cfg, "Today", '<header class="bar lb"></header>', root="../")
    article = play.shell(cfg, "Story", '<header class="bar"></header>', root="../../")
    assert 'id="np-tablet-install"' in lobby
    assert 'id="np-tablet-install"' not in article
    assert 'hasAttribute(\'data-tablet-install\')' in play.JS


def test_tablet_install_lifecycle_in_browser():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js not installed")
    env = dict(os.environ)
    try:
        subprocess.run([node, "-e", "require('playwright')"], env=env, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pytest.skip("Playwright not installed")
    result = subprocess.run([node, str(Path(__file__).with_name("tablet-install.cjs"))],
                            input=pwa.tablet_prompt(), text=True, capture_output=True, env=env, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
