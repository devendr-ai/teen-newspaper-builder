"""Delivery CLI tests use fake HTTP only; no emails or external requests."""
import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import urllib.error
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import dispatch_delivery as delivery


class DispatchTests(unittest.TestCase):
    def test_worker_origin(self):
        self.assertEqual(delivery.worker_origin('https://worker.example/'), 'https://worker.example')
        for url in ('http://worker.example', 'https://worker.example/path', 'https://user:pass@worker.example',
                    'https://worker.example/?token=secret', 'https://worker.example:443'):
            with self.assertRaises(delivery.DeliveryError):
                delivery.worker_origin(url)

    def test_feed_date_and_host_validation(self):
        for link, valid in [('https://newspebbles.com/e/little-explorers/2026-10-25.pdf', True),
                            ('https://evil.com/2026-10-25.pdf', False),
                            ('https://newspebbles.com/e/little-explorers/2026-02-30.pdf', False)]:
            with patch.object(delivery, 'fetch', return_value=f'<rss><channel><item><link>{link}</link></item></channel></rss>'.encode()):
                if valid:
                    self.assertEqual(delivery.latest_date('little-explorers'), '2026-10-25')
                else:
                    with self.assertRaises(delivery.DeliveryError):
                        delivery.latest_date('little-explorers')

    def test_dispatch_payload_and_secret_env_only(self):
        result = {'queued': 0, 'eligible': 1, 'issues': {'little-explorers': '2026-10-25'}, 'errors': {}, 'dry_run': True}
        with patch.dict('os.environ', {'DISPATCH_SECRET': 'secret-never-print'}), patch.object(delivery, 'latest_date', return_value='2026-10-25'), patch.object(delivery, 'fetch', return_value=json.dumps(result).encode()) as send, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(delivery.run(['--worker-url', 'https://worker.example', '--edition', 'little-explorers', '--dry-run']), 0)
            self.assertNotIn('secret-never-print', out.getvalue())
            self.assertEqual(send.call_args.kwargs['payload']['expected_issue_dates'], {'little-explorers': '2026-10-25'})
            self.assertEqual(send.call_args.kwargs['secret'], 'secret-never-print')

    def test_invalid_slug_no_network_and_missing_secret(self):
        with patch.dict('os.environ', {'DISPATCH_SECRET': 'safe'}), patch.object(delivery, 'fetch') as send, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(delivery.run(['--worker-url', 'https://worker.example', '--edition', '../escape']), 1)
            send.assert_not_called()
        with patch.dict('os.environ', {'DISPATCH_SECRET': ''}), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(delivery.run(['--worker-url', 'https://worker.example']), 1)

    def test_provider_errors_do_not_leak_bearer(self):
        error = urllib.error.HTTPError('https://worker.example', 401, 'secret-value', {}, None)
        with self.assertRaisesRegex(delivery.DeliveryError, 'HTTP 401') as caught:
            delivery.fetch('https://worker.example', payload={}, secret='secret-value', opener=lambda *a, **k: (_ for _ in ()).throw(error))
        self.assertNotIn('secret-value', str(caught.exception))

    def test_429_retry_after(self):
        replies = [urllib.error.HTTPError('https://worker.example', 429, '', {'Retry-After': '12'}, None), io.BytesIO(b'{}')]
        def opener(*args, **kwargs):
            value = replies.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        with patch.object(delivery.time, 'sleep') as sleep:
            self.assertEqual(delivery.fetch('https://worker.example', payload={}, secret='safe', opener=opener), b'{}')
            sleep.assert_called_once_with(12)

    def test_response_size_limit(self):
        with self.assertRaisesRegex(delivery.DeliveryError, 'too large'):
            delivery.fetch('https://worker.example', opener=lambda *a, **k: io.BytesIO(b'x' * (delivery.MAX_RESPONSE + 1)))

    def test_catalog_matches_published_editions(self):
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads(delivery.CATALOG_PATH.read_text())
        actual = {p.parent.name for p in (root / 'editions').glob('*/edition.yaml')}
        self.assertEqual(set(catalog), actual)


if __name__ == '__main__':
    unittest.main()
