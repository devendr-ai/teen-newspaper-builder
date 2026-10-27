# News Pebbles delivery backend — Phase 1

A separate Cloudflare Worker + D1 database for parent subscriptions. The main site remains entirely static. No browser UI, public privacy text, newspaper generation, Pages deployment or publication workflow is changed by this phase. Nothing sends until the operator configures accounts and explicitly enables delivery.

## What the backend uses

The existing site already publishes an edition's successfully built PDFs in `/e/<slug>/feed.xml`. The Worker takes the newest dated PDF link from that feed, checks that `/play/<slug>/<date>.html` is a full reader (not an archived stub), and uses the existing dated cover. No additional public manifest is needed. `editions.json` is the allowlist of the current nine editions and their display names/ages; update it when adding or changing an edition.

The attached PDF is downloaded from the dated URL and compared byte-for-byte by SHA-256 against `/e/<slug>/latest.pdf` before the first send. It must have a PDF signature and be **strictly below 5,000,000 bytes**. It is attached directly as base64 with a descriptive dated filename. Links also point to that same dated issue; readers never silently receive a newer paper when reopening an old email. A deployment mismatch defers sending. Oversized/invalid PDFs are held for investigation, never silently delivered without the promised attachment.

**Why individual REST sends:** [Resend's batch endpoint does not support attachments](https://resend.com/docs/dashboard/emails/attachments). This implements the approved protected-dispatch alternative, using `fetch` directly against `/emails`, up to two messages per invocation, paced at least 1.1 seconds apart. There are no runtime npm dependencies or email SDKs. The two-message cap keeps dispatch below D1’s [50-query free-plan invocation limit](https://developers.cloudflare.com/d1/platform/limits/), including a scan across all nine editions. Cloudflare’s [free Worker CPU allowance](https://developers.cloudflare.com/workers/platform/limits/#cpu-time) is also tight: measure actual PDF delivery CPU during activation, especially near 5 MB; local tests do not prove production free-tier performance.

## Set up (one time)

### News Pebbles production configuration

`wrangler.jsonc` now points to the production `newspebbles-subscriptions` D1 database and `https://newspebbles-subscribe.devendr.workers.dev`. The sending domain is `mail.newspebbles.com`, verified in Resend through its DKIM, SPF and return-path MX records. Secrets live only in Cloudflare; the repository contains no secret values. Do not recreate the production database when redeploying this installation.

Production setup was tested with one owner-authorized confirmation and one welcome PDF. Repeating the pipeline dispatch sent no duplicate. Gmail received the welcome in the inbox, opened its two-page PDF attachment, and reported SPF, DKIM and DMARC PASS. The passing `mail.newspebbles.com` DKIM signature covered both `List-Unsubscribe` and `List-Unsubscribe-Post`; the message carried the HTTPS unsubscribe URL and `List-Unsubscribe=One-Click`. A one-click POST and repeated GET each returned 200 without redirects, leaving the test entry unsubscribed.

Asset fetches use Workers-compatible `redirect: "manual"`; non-2xx responses are rejected before parsing or attaching content. Node's `redirect: "error"` is unsupported in the Workers runtime.

Production delivery is enabled, with a five-minute cron polling the published issue feeds and recovering pending deliveries. The frontend signup flag and Worker URL are configured separately in `site.yaml`. Every-issue subscribers receive newly published issue dates; weekend subscribers are eligible Saturday from 08:00 through Sunday in `America/Los_Angeles`, once per weekend and only when an issue is newer than their last delivery. Confirmation still sends the latest issue immediately. No publication workflow secret is required for cron dispatch. Repeat the received-message authentication check when changing email providers or sender configuration; the Resend API payload alone does not prove DKIM header coverage.

### Installing another environment

Requirements: Node 24+, Python 3.11+, Cloudflare Workers/D1 account, Resend account and a verified sending domain. Use a dedicated sending subdomain such as `mail.newspebbles.com` so its email DNS records can be configured without changing the website's GitHub Pages records. Replace the sender with a verified address for the new environment. Disable open/click tracking in Resend if maintaining tracking-free delivery is desired. Provider quotas still apply; this project does not promise unlimited free sending.

From this folder:

```sh
npm ci --ignore-scripts
npm test
npm run check
npm run db:local
npx wrangler login
npx wrangler d1 create newspebbles-subscriptions
```

Copy the returned account and database IDs into `wrangler.jsonc` for that environment. Then:

```sh
npm run db:remote
npx wrangler secret put RESEND_API_KEY
npx wrangler secret put DISPATCH_SECRET
```

Enter secrets only in the secure prompts; never commit `.dev.vars`, paste credentials in chat, or put them in workflow logs. Use a long randomly generated dispatch secret. Set `PUBLIC_BASE_URL` to the actual HTTPS Worker origin, with no path, and `RESEND_FROM` to a verified sender. Deploy initially with `DELIVERY_ENABLED` **false**:

```sh
npm run deploy
```

After configuration is reviewed, set `DELIVERY_ENABLED` to `true`, deploy, and use an address you control for the first explicit subscription/confirmation test. Once that succeeds, optionally enable `"crons": ["*/5 * * * *"]` and redeploy. The cron invokes the same dispatcher and drains/retries the outbox. It is UTC; **weekly eligibility is independently evaluated in `WEEKEND_TIMEZONE`**, default `America/Los_Angeles`, from Saturday 08:00 through Sunday 23:59, with daylight-saving support. One weekend delivery per subscriber; no resend when the issue date has not changed. Everyone receives the current latest issue immediately after verification, including a weekly subscriber joining on a weekday. A weekend welcome counts as that weekend's delivery.

For a new environment, set `DELIVERY_ENABLED` to false and clear cron before deployment. Account setup and an owner-controlled delivery test are required before activating that environment.

## API

All responses have `Cache-Control: no-store` and `Referrer-Policy: no-referrer`. Do not enable request/query logging that captures tokens or addresses. CORS accepts exactly `https://newspebbles.com` and `http://localhost`. Ports and other subdomains are intentionally excluded by the requested policy. Subscribe requires one of those browser origins. Token links and secret-authenticated dispatch also work without an Origin header. CORS does not authenticate a client; confirmation, tokens and rate limiting provide the actual controls.

### `POST /api/subscribe`

JSON, under 8 KB:

```json
{"email":"parent@example.com","edition_slug":"little-explorers","cadence":"every_issue","website":""}
```

`cadence`: `every_issue` or `weekly_weekend`. `website` is the hidden honeypot; keep it empty. A filled honeypot receives the generic success response but creates no subscription and sends no email. Confirmation requests are limited to three per normalized email and fifteen per connecting IP per hour. Rate keys are hashed with the dispatch secret; raw IPs are not stored. Limits apply even if the email is already subscribed. Invalid fields return 400, throttled requests 429, disabled service 503, accepted requests 202 with a generic message.

One `(email, edition_slug)` row allows a parent to subscribe to different editions. Existing active subscriptions cannot be altered by an unverified request. Existing pending subscriptions reuse their confirmation for 24 hours. New/restarted subscriptions must confirm again. Previous issue-delivery history is retained when resubscribing, so a paper already delivered is not sent again.

### `GET /api/verify?token=…`

Single-use 256-bit token, expires 24 hours after the confirmation was queued. Activates the subscription, queues the latest welcome paper and attempts immediate delivery; redirects to `https://newspebbles.com/?subscribed=true`. If publication assets/provider are temporarily unavailable, activation succeeds and scheduled/explicit dispatch recovers the welcome. Expired/consumed/unknown tokens return 400. A redirect means the subscription is active; it does not guarantee provider delivery.

### `GET` or `POST /api/unsubscribe?token=…`

Immediately unsubscribes this edition and cancels unsent jobs. Both return a polite HTML confirmation; repeated requests are safe. No login or form submission is required. An email already accepted by Resend cannot be recalled; an unsubscribe racing an in-flight provider request may still receive that one email. Every email, including confirmation, includes `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`, a visible unsubscribe link, and text/HTML bodies. GET changes are deliberate per the requested API: an aggressive link scanner could follow verification/unsubscribe links. A later confirmation-screen design would require changing those semantics.

### `POST /api/dispatch`

`Authorization: Bearer <DISPATCH_SECRET>`, JSON:

```json
{"editions":["little-explorers"],"limit":2,"dry_run":true,"expected_issue_dates":{"little-explorers":"2026-10-25"}}
```

All fields optional; editions default to the full allowlist, limit is capped at two. `dry_run` inspects eligibility without queueing or sending; it is permitted while delivery is disabled. Expected dates prevent a build hook dispatching before its expected deployed version is visible. The response reports counts, issue dates and safe error codes; no subscriber addresses. Examine `errors`, `delivery.held`, `delivery.deferred` and `delivery.busy`, not just HTTP 200. Repeated calls drain larger lists. Cron and manual dispatch share the same durable outbox and lock.

## Build-pipeline CLI

From the repository root (standard library only):

```sh
export SUBSCRIBE_WORKER_URL='https://your-worker.your-account.workers.dev'
# Supply DISPATCH_SECRET via your secret manager or a protected CI secret.
python tools/dispatch_delivery.py --edition little-explorers --dry-run
python tools/dispatch_delivery.py --edition little-explorers --passes 20
```

The script reads deployed feeds, passes their dates to the protected dispatcher and prints counts only. It refuses redirects for requests carrying the bearer secret. Retries are bounded; deferred/busy responses stop draining so cron can respect pauses and daily limits. An error/held result returns a failing exit code. A deferred response is recoverable, not proof that all mail has been delivered.

**No publication hook is enabled in Phase 1.** For later activation, invoke this after successful GitHub Pages deployment, scoped to the newly published editions, using protected `SUBSCRIBE_WORKER_URL`/`DISPATCH_SECRET` configuration. Use cron as a fallback. An every-issue subscription observes the latest published issue at dispatch time; this is not a historical catch-up queue. If multiple editions of the same paper publish between dispatches, only the newest is selected. Publishing must dispatch each new date if every intermediate issue is required.

## Durable state and recovery

`schema.sql` creates the requested `subscribers` columns and unique `(email, edition_slug)` constraint, plus:

- `deliveries`: frozen message payload, attachment hash, unique subscriber/issue and subscriber/weekend records, retry/held state and provider ID. PDF bytes are not stored in D1.
- `send_control`: one global lease, provider pause, pacing and a conservative daily API-attempt counter (default 90 UTC; tune to actual account quota).
- `rate_limits`: short-lived hashed form-abuse counters; scheduled dispatch removes expired entries.

Delivery state and `last_sent_issue_date` are committed together after provider acceptance. Lease checks serialize sends across Worker isolates; deterministic Resend idempotency keys recover from an accepted request whose response/database acknowledgement was lost. Retries preserve the exact message and attachment hash. Changed attachment bytes are held rather than resending different content under the same key.

[Resend retains idempotency keys for 24 hours](https://resend.com/docs/dashboard/emails/idempotency-keys). Ambiguous jobs stop automatically after 23 hours and become `held` (`ambiguous_send_expired`), rather than risk a duplicate outside that window. This favors duplicate prevention over automatic retries forever; it is not a claim of unconditional exactly-once email delivery. Check the Resend dashboard/provider ID before manually repairing a held delivery. Do not delete or reset sent/ambiguous records while their issue could be eligible. A 429 respects `Retry-After` globally; unknown responses/5xx retry with the same key; permanent 4xx are held. Provider acceptance is not inbox delivery, and a bounce does not trigger an automatic resend.

Monitor held jobs and provider failures before expanding signups. This phase has no bounce/complaint webhook; manage Resend suppression lists in its dashboard. Confirm sender-domain verification and inbox behavior during activation. Database backups/exports contain parent emails and capability tokens: restrict access, do not commit them, and establish a deletion/retention policy before public signups. Website privacy copy and subscription UI are a later phase; no public subscription form is added here.

Existing website retention still applies to emailed links: the reader currently keeps seven full issues per edition and the PDF archive thirty. Attachments remain in the recipient's email even after a website link ages out.

## Verification

```sh
cd subscribe-worker
npm test
npm run check
npm run db:local
cd ..
python -m unittest discover -s tests -p test_dispatch_delivery.py
```

Tests use in-memory SQLite with a D1-shaped adapter and simulated HTTP/Resend responses. They cover CORS, schema uniqueness, validation/honeypot, confirmation/verification, both unsubscribe methods, immediate welcome, weekend/DST timing, newer-date selection, concurrent dispatch, lost send/DB acknowledgements, stable retries, 429 pacing, daily limits, attachment size/signature/mutation, CLI authentication/date guards and catalog consistency. The dedicated backend CI runs tests, bundles the Worker and applies schema to a local D1 instance. No test sends real email. Wrangler's dev-only HTTP dependency is pinned to a patched `undici` release via `overrides` pending upstream adoption; no such dependency is bundled into the Worker.

### Analyst responses

`POST /api/polls/vote` is independent of email delivery and uses no subscriber data.
Apply the additive `polls-schema.sql` migration before deploying this version. Set
`POLLS_ENABLED` to `false` to disable sharing without affecting subscriptions.
The static build writes `play/polls.json`; only question IDs in that manifest can
receive responses. Question IDs include a content hash, so edited choices never
reuse earlier counts. There is no browser request on load, on choosing an option,
or on completing a game. The reader must explicitly share; kids mode calls the
existing parental gate before decoding the endpoint or making the request.

Each question has its own random browser receipt. The server stores a hash of that
receipt and the response, never a name/email or a cross-question identifier. A
repeat receipt updates its previous choice. This is best-effort browser duplicate
protection, not proof of unique people. Secret-hashed, hourly network rate limits
expire after two hours. Receipts/choices expire after 90 days; aggregate splits
are withheld until five responses. Results are not a representative survey.
No vote is generated by tests or deployment, and no poll response sends email.
