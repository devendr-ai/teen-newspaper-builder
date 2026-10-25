#!/usr/bin/env python3
"""Dispatch deployed News Pebbles issues; standard library only, no email SDK."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SITE = 'https://newspebbles.com'
CATALOG_PATH = Path(__file__).resolve().parents[1] / 'subscribe-worker' / 'editions.json'
MAX_RESPONSE = 250_000


class DeliveryError(Exception):
    """A safe message that never includes credentials or subscriber information."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, *, payload=None, secret=None, opener=None):
    headers = {'Accept': 'application/json' if payload is not None else 'application/rss+xml',
               'Cache-Control': 'no-cache', 'User-Agent': 'NewsPebbles-Delivery/1.0'}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
        headers['Authorization'] = 'Bearer ' + secret
    request = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                                     headers=headers, method='POST' if payload is not None else 'GET')
    transport = opener or urllib.request.build_opener(NoRedirect()).open
    for attempt in range(3):
        try:
            with transport(request, timeout=60) as response:
                body = response.read(MAX_RESPONSE + 1)
                if len(body) > MAX_RESPONSE:
                    raise DeliveryError('Response too large.')
                return body
        except urllib.error.HTTPError as error:
            if error.code == 429 or error.code >= 500:
                if attempt < 2:
                    try:
                        delay = max(1, min(60, int(error.headers.get('Retry-After', '5'))))
                    except (TypeError, ValueError):
                        delay = 5
                    time.sleep(delay)
                    continue
            raise DeliveryError(f'Delivery service returned HTTP {error.code}.') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise DeliveryError('Delivery service could not be reached.') from None
    raise DeliveryError('Delivery service could not be reached.')


def worker_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.port):
        raise DeliveryError('Worker URL must be a plain HTTPS origin with no path or credentials.')
    return value.rstrip('/')


def latest_date(slug):
    try:
        root = ET.fromstring(fetch(f'{SITE}/e/{slug}/feed.xml'))
        link = root.findtext('./channel/item/link', '').strip()
        prefix = f'{SITE}/e/{slug}/'
        if not link.startswith(prefix) or not link.endswith('.pdf'):
            raise ValueError
        value = link[len(prefix):-4]
        if dt.date.fromisoformat(value).isoformat() != value:
            raise ValueError
        return value
    except (ET.ParseError, ValueError):
        raise DeliveryError(f'No valid published issue in {slug} feed.') from None


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-url', default=os.getenv('SUBSCRIBE_WORKER_URL', ''))
    parser.add_argument('--edition', action='append', help='Edition slug; repeat for several. Default: all.')
    parser.add_argument('--limit', type=int, default=2, choices=range(1, 3), metavar='1..2')
    parser.add_argument('--passes', type=int, default=1, choices=range(1, 101), metavar='1..100',
                        help='Bounded dispatch calls, useful for draining larger subscriber lists.')
    parser.add_argument('--dry-run', action='store_true', help='Inspect eligibility without queueing or sending.')
    args = parser.parse_args(argv)
    try:
        origin = worker_origin(args.worker_url)
        secret = os.getenv('DISPATCH_SECRET', '')
        if not secret or '\n' in secret or '\r' in secret:
            raise DeliveryError('Set DISPATCH_SECRET securely in the environment.')
        catalog = json.loads(CATALOG_PATH.read_text())
        slugs = list(dict.fromkeys(args.edition or catalog))
        if any(slug not in catalog for slug in slugs):
            raise DeliveryError('Unknown edition slug.')
        dates = {slug: latest_date(slug) for slug in slugs}
        failed = False
        for _ in range(1 if args.dry_run else args.passes):
            data = json.loads(fetch(origin + '/api/dispatch', payload={
                'editions': slugs, 'expected_issue_dates': dates,
                'limit': args.limit, 'dry_run': args.dry_run}, secret=secret))
            # Print only counters, dates and safe error codes, never arbitrary server content.
            summary = {key: data.get(key) for key in ('queued', 'eligible', 'issues', 'errors', 'dry_run', 'delivery')}
            print(json.dumps(summary, sort_keys=True))
            delivery = data.get('delivery') or {}
            failed = failed or bool(data.get('errors')) or bool(delivery.get('held'))
            if delivery.get('deferred') or delivery.get('busy'):
                break  # Let scheduled recovery respect the provider's pause/daily cap.
            if not data.get('queued') and not delivery.get('sent'):
                break
        return 1 if failed else 0
    except (DeliveryError, ValueError, KeyError, TypeError):
        # Deliberately exclude raw transport/JSON messages: they may contain secrets.
        error = sys.exc_info()[1]
        print(str(error) if isinstance(error, DeliveryError) else 'Invalid delivery service response or configuration.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(run())
