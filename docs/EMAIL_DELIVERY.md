# Parent email signup (Phase 2)

The public site can offer email signup on its recommended paper cards, each edition archive, and For parents. Read & Play (`play/`) has no signup form. The backend and setup instructions are in [`subscribe-worker/README.md`](../subscribe-worker/README.md).

## Activate after the Worker is ready

`site.yaml` defaults to:

```yaml
subscriptions:
  enabled: false
  api_base_url: ""
  whatsapp_channel_url: ""
```

After verifying the Worker sender, database, secrets, and a test delivery, set `enabled: true` and the real HTTPS API location. Rebuild and publish the static site through the normal process.

- Worker origin: `https://your-worker.your-account.workers.dev` → `/api/subscribe`.
- Same-site API base: `https://newspebbles.com/api` → `/api/subscribe`.
- Subdomain origin: `https://subscribe.newspebbles.com` → `/api/subscribe`.
- A custom prefix ending in `/api` also works; do not supply the final `/subscribe` endpoint.

A custom domain or same-site route must actually be configured in Cloudflare first; changing this YAML alone does not create a proxy/route on GitHub Pages. The Phase 1 Worker allows the browser origin `https://newspebbles.com` (and exactly `http://localhost`). CORS checks the origin of the static page, not the API's hostname. Use the production origin for an owner-controlled end-to-end test, or adjust development configuration deliberately; do not weaken production CORS.

Missing, disabled, placeholder or invalid API configuration hides all signup forms. No real endpoint is assumed in the checked-in settings. Forms appear only when the flag is a YAML boolean `true` and the API is configured. Existing print, download, share and Read & Play features remain available.

Add an official `https://whatsapp.com/channel/...` URL only when the channel exists. An empty/missing/invalid channel hides that link. “Send this issue to WhatsApp” remains available independently on published issues, using their public dated PDF and Read & Play links. On For parents, choosing a newspaper updates that share link locally without a network lookup. No email address or local reading data is put in a WhatsApp link.

## Form behaviour and future compliance integration

Each form has `data-gate-form="subscribe"`. Its own submit listener prevents the browser's native submission, validates required fields, and checks a locally generated grown-up multiplication question before sending one JSON POST. The hidden `website` honeypot is passed to the Worker. The math answer stays on the device. This check adds friction for casual child use; it is not identity verification or a server-side security boundary. Email confirmation and server limits still protect subscriptions.

There is no request on page load, age selection, cadence change or newspaper selection. No local reading preferences/progress are read or transmitted. A pending submit disables the button and suppresses repeat submissions; success and errors are announced inline. Failed/finished requests require a fresh math answer. Requests omit cookies, refuse redirects, use no referrer, and time out after 20 seconds.

Without JavaScript, the form fields remain disabled and a note explains that printing still works. `method="dialog"` also avoids a native GET/POST containing an address if the script cannot initialize. This form method is deliberately used outside a dialog to keep native submission network-free; all intended submission is through the scoped JS handler.

The global compliance gate can intercept/cancel the submit event in capture phase using the data attribute. The local handler respects an already-prevented event. This change does **not** add `gate.js`, `npGate`, `--kids`, global outbound-link handling or store-compliance claims. Those remain a separate workstream. When `kids_mode` is true, subscription submission additionally calls the existing `window.npGate("link", onPass, onCancel)` before any POST. It fails closed if the gate is unavailable or cancelled. The public build uses only the scoped inline math check.

## Confirmations, privacy and printing

The home page displays a dismissible banner for exactly `?subscribed=true` or `?unsubscribed=true`. These are informational return flags, not proof of a subscription or new backend actions. Dismissing removes only those flags and preserves other URL parameters/hash. The current Worker returns unsubscribe confirmation directly; the home-page unsubscribe banner supports a later redirect.

When signup is enabled, the Privacy page explains parent addresses, edition/cadence choices, Cloudflare D1, Resend, anti-abuse counters, unsubscribe, delivery records and deletion contact. The form links to this section.

The collapsible Auto-Print Magic guide appears on For parents when delivery signup is enabled and inside the subscribed banner. It covers supported HP ePrint/Epson Email Print addresses, sender-and-attachment filters in Gmail/Outlook, approved senders, a test print and attachments-only settings. Gmail forwarding requires address verification; not every printer can complete it. Outlook rules should forward the original message with its PDF, rather than wrapping it as `.eml`. The guide links to official provider instructions and keeps manual PDF printing available.

## Tests

```sh
python -m pytest -q tests/test_subscriptions.py tests/test_site.py tests/test_share.py
```

Python tests cover enabled/disabled/unconfigured builds, API normalization, optional WhatsApp links, scoped forms and labels, all placements, privacy text and absence of forms in `play/`. The Node VM harness covers zero initial/selection requests, wrong answers, validity checks, cancellation by a future gate, minimal payload, loading and double-submit handling, errors/timeouts, share selection and confirmation dismissal. Actual browser review checks the phone/desktop layout and a blocked wrong answer without sending a real email.
