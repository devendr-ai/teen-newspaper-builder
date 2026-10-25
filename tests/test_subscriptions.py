"""Static parent signup UI: config, published placement, privacy and scoped JS gate."""
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import pytest

from ygc import edition, site


def config_with(**settings):
    cfg = site.site_config()
    cfg['subscriptions'] = dict(enabled=True, api_base_url='https://subscribe.newspebbles.com', whatsapp_channel_url='')
    cfg['subscriptions'].update(settings)
    return cfg


@pytest.mark.parametrize('base,expected', [
    ('https://subscribe.newspebbles.com', 'https://subscribe.newspebbles.com/api/subscribe'),
    ('https://subscribe.newspebbles.com/', 'https://subscribe.newspebbles.com/api/subscribe'),
    ('https://newspebbles.com/api', 'https://newspebbles.com/api/subscribe'),
    ('https://newspebbles.com/mail/api/', 'https://newspebbles.com/mail/api/subscribe'),
    ('', ''), ('javascript:alert(1)', ''), ('http://subscribe.newspebbles.com', ''),
    ('https://user:password@newspebbles.com/api', ''), ('https://newspebbles.com/api?token=secret', ''),
    ('https://replace-with-your-worker.workers.dev', ''), ('https://example.com:bad', ''),
])
def test_api_base_normalization_and_fail_closed_configuration(base, expected):
    assert site.subscription_endpoint(config_with(api_base_url=base)) == expected


def test_disabled_and_unconfigured_forms_are_not_offered():
    ed = edition.load('little-explorers')
    for settings in ({'enabled': False}, {'enabled': 'true'}, {'api_base_url': ''}):
        cfg = config_with(**settings)
        assert site.subscription_form(cfg, ed) == ''
        assert 'data-gate-form=' not in site.parents_body(cfg)
        assert 'data-gate-form=' not in site.recommendations({ed['id']: (ed, '2026-10-24')}, False, cfg)
    assert isinstance(site.site_config()['subscriptions']['enabled'], bool)


@pytest.mark.parametrize('channel', ['', None, 'javascript:alert(1)', 'https://evil.com/channel/abc', 'https://whatsapp.com/chat/abc'])
def test_optional_channel_hides_without_removing_issue_share(channel):
    cfg = config_with(whatsapp_channel_url=channel)
    html = site.subscription_form(cfg, edition.load('little-explorers'), date='2026-10-24')
    assert 'Follow our WhatsApp Channel' not in html
    assert 'Send this issue to WhatsApp' in html and 'https://wa.me/?text=' in html
    assert 'parent@example.com' not in html


def test_channel_is_opt_in_and_same_with_or_without_api_prefix():
    cfg = config_with(whatsapp_channel_url='https://whatsapp.com/channel/123456')
    form = site.subscription_form(cfg, edition.load('little-explorers'))
    assert 'Follow our WhatsApp Channel' in form
    assert 'https://whatsapp.com/channel/123456' in form


class Markup(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_recommendations_and_parent_selector_are_accessible_and_unique():
    cfg = config_with()
    published = {slug: (edition.load(slug), '2026-10-24') for slug, _, _ in site.RECOMMENDED.values()}
    html = site.recommendations(published, False, cfg)
    markup = Markup(html)
    forms = [a for t, a in markup.tags if t == 'form']
    assert len(forms) == 4
    assert all(a['data-gate-form'] == 'subscribe' and a['method'] == 'dialog' for a in forms)
    ids = [a['id'] for _, a in markup.tags if 'id' in a]
    assert len(ids) == len(set(ids))
    assert all(a['for'] in ids for t, a in markup.tags if t == 'label' and 'for' in a)
    assert len([a for t, a in markup.tags if t == 'fieldset' and 'disabled' in a]) == 4
    assert len([a for t, a in markup.tags if t == 'input' and a.get('name') == 'website' and a['tabindex'] == '-1']) == 4
    assert 'role="status"' in html and 'role="alert"' in html and '<noscript>' in html
    parents = site.parents_body(cfg, published)
    assert '<select' in parents
    for slug in edition.list_editions():
        assert f'<option value="{slug}"' in parents
    assert 'Want this paper to print itself automatically?' in parents
    assert 'forwarding-address verification' in parents
    assert 'method="dialog"' in parents  # No native GET/POST of an email if JS cannot run.


def test_banners_are_hidden_initially_and_do_not_contain_any_personal_data():
    banner = site.subscription_banner()
    assert 'data-subscription-banner' in banner and 'role="region"' in banner
    assert 'aria-label="Dismiss email delivery confirmation"' in banner
    assert 'data-subscription-confirmed hidden' in banner and 'data-subscription-unsubscribed hidden' in banner
    assert 'Want this paper to print itself automatically?' in banner


def test_frontend_behavior_no_background_requests_and_scoped_gate():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js needed for subscription behavior checks')
    result = subprocess.run([node, str(Path(__file__).with_name('subscriptions.cjs'))],
        input=site.SUBSCRIPTION_SCRIPT, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('enabled', [True, False])
def test_built_signup_placements_and_reader_has_no_forms(tmp_path, monkeypatch, enabled):
    cfg = config_with(enabled=enabled)
    real = site.issues_of
    monkeypatch.setattr(site, 'site_config', lambda: cfg)
    monkeypatch.setattr(site, 'issues_of', lambda ed: real(ed)[:1] if ed['id'] == 'little-explorers' else [])
    out = tmp_path / 'site'
    site.build(str(out), keep=1, log=lambda *args: None)
    home = (out / 'index.html').read_text()
    parents = (out / 'parents.html').read_text()
    archive = (out / 'e/little-explorers/index.html').read_text()
    for html in (home, parents, archive):
        # Count rendered forms, not the selector in the inline script.
        assert bool([a for t, a in Markup(html).tags if t == 'form' and a.get('data-gate-form') == 'subscribe']) is enabled
        assert 'Follow our WhatsApp Channel' not in html
    if enabled:
        assert 'name="edition_slug"' in parents
    else:
        assert 'Choose your paper' not in parents
    if enabled:
        assert '../../privacy.html#email-delivery' in archive
        assert 'data-subscribe-endpoint="https://subscribe.newspebbles.com/api/subscribe"' in archive
        privacy = (out / 'privacy.html').read_text()
        assert 'id="email-delivery"' in privacy and 'Cloudflare D1' in privacy and 'Resend' in privacy
    for path in (out / 'play').rglob('*.html'):
        assert 'data-gate-form=' not in path.read_text(), path
        assert 'data-subscribe-endpoint' not in path.read_text(), path


def test_missing_site_settings_default_to_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(site, 'ROOT', str(tmp_path))
    assert site.site_config()['subscriptions'] == dict(enabled=False, api_base_url='', whatsapp_channel_url='')
