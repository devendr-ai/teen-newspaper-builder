"""The public app promotion must never change the submitted app's navigation."""
import re
from urllib.parse import urljoin

import pytest

from ygc import app_showcase, play, site


def test_store_links_stay_unavailable_until_configured():
    html = app_showcase.downloads({})
    assert html.count('Coming soon') == 2
    assert '<a ' not in html
    assert 'Store links will appear here after approval' in html
    cfg = {'mobile_app': {'app_store_url': 'https://apps.apple.com/us/app/news-pebbles/id123456789',
                          'google_play_url': 'https://play.google.com/store/apps/details?id=com.newspebbles.app'}}
    html = app_showcase.downloads(cfg)
    assert html.count('class="app-store" href=') == 2 and 'Coming soon' not in html


@pytest.mark.parametrize('value', ['javascript:alert(1)', 'http://apps.apple.com/app/id123',
    'https://apps.apple.com.evil.test/us/app/id123', 'https://apps.apple.com@evil.test/app/id123',
    'https://play.google.com/redirect', 'https://example.test', 'https://apps.apple.com:444/app/id123'])
def test_untrusted_store_destinations_never_become_download_links(value):
    assert not app_showcase.store_url(value, 'apple')
    assert not app_showcase.store_url(value, 'google')


def test_read_and_play_navigation_has_public_app_last_at_every_depth():
    for root, location in [('../', 'play/index.html'), ('../../', 'play/paper/date.html'),
                           ('../../', 'play/threads/example.html')]:
        nav = play.child_nav(root)
        links = re.findall(r'href="([^"]+)" data-view="([^"]+)"', nav)
        assert [k for _, k in links] == ['home', 'today', 'explore', 'me', 'app']
        assert urljoin('https://example.test/' + location, links[-1][0]) == 'https://example.test/app.html'
    native = play.child_nav('../', app=True)
    assert 'app.html' not in native
    assert re.findall(r'data-view="([^"]+)"', native) == ['home', 'today', 'explore', 'listen', 'me']


def test_parent_header_and_bottom_navigation_preserve_app_build():
    for kids in (False, True):
        cfg = {**site.site_config(), 'kids_mode': kids}
        page = site.page(cfg, 'Example', '<main>Content</main>', here='app')
        header = re.search(r'<nav id="nav">(.*?)</nav>', page, re.S).group(1)
        bottom = site.tabbar(cfg, '', 'app')
        assert ('href="app.html"' in header) is not kids
        assert ('href="app.html"' in bottom) is not kids
        expected = ['index.html', 'play/index.html', 'play/listen.html' if kids else 'builder.html']
        expected += ([] if kids else ['app.html']) + ['parents.html']
        assert re.findall(r'href="([^"]+)"', header) == expected
        assert re.findall(r'href="([^"]+)"', bottom) == expected
        if not kids:
            assert 'href="app.html" aria-current="page"' in header


def test_showcase_uses_local_images_and_does_not_add_background_requests():
    html = app_showcase.body(site.site_config())
    assert re.findall(r'<img[^>]+src="([^"]+)"', html) == ['app-showcase/today.jpg', 'app-showcase/listen.jpg']
    assert '<script' not in html and '<iframe' not in html
    assert 'Seven days of papers offline' in html
    assert 'Open the app online' in html
