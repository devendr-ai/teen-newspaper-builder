PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS subscribers (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL COLLATE NOCASE,
  edition_slug TEXT NOT NULL,
  cadence TEXT NOT NULL CHECK (cadence IN ('every_issue', 'weekly_weekend')),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'unsubscribed')),
  verify_token TEXT UNIQUE,
  unsubscribe_token TEXT NOT NULL UNIQUE,
  last_sent_issue_date TEXT,
  created_at INTEGER NOT NULL,
  UNIQUE (email, edition_slug)
);
CREATE INDEX IF NOT EXISTS subscribers_dispatch ON subscribers(status, edition_slug, id);

-- An outbox is needed in addition to last_sent_issue_date: a crash after Resend
-- accepts a message must not cause the next dispatcher to send it again.
CREATE TABLE IF NOT EXISTS deliveries (
  id TEXT PRIMARY KEY,
  subscriber_id TEXT NOT NULL REFERENCES subscribers(id),
  kind TEXT NOT NULL CHECK (kind IN ('confirmation', 'issue')),
  issue_date TEXT,
  weekend_key TEXT,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'sending', 'retry', 'sent', 'held', 'cancelled')),
  payload_json TEXT NOT NULL,
  attachment_url TEXT,
  attachment_sha256 TEXT,
  provider_message_id TEXT,
  first_attempt_at INTEGER,
  next_attempt_at INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at INTEGER NOT NULL,
  UNIQUE(subscriber_id, kind, issue_date),
  UNIQUE(subscriber_id, weekend_key)
);
CREATE INDEX IF NOT EXISTS deliveries_pending ON deliveries(state, next_attempt_at, created_at);

CREATE TABLE IF NOT EXISTS rate_limits (
  key TEXT PRIMARY KEY,
  count INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);

-- Serializes sends across isolates, not just within one JavaScript process.
CREATE TABLE IF NOT EXISTS send_control (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  owner TEXT,
  lease_until INTEGER NOT NULL DEFAULT 0,
  next_send_at INTEGER NOT NULL DEFAULT 0,
  pause_until INTEGER NOT NULL DEFAULT 0,
  daily_date TEXT NOT NULL DEFAULT '',
  daily_count INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO send_control(id) VALUES (1);
-- Additive: existing subscribers and delivery history remain untouched.
CREATE TABLE IF NOT EXISTS poll_votes (
  poll_id TEXT NOT NULL,
  receipt_hash TEXT NOT NULL,
  choice INTEGER NOT NULL CHECK(choice IN (0,1)),
  created_at INTEGER NOT NULL,
  PRIMARY KEY(poll_id, receipt_hash)
);
CREATE INDEX IF NOT EXISTS poll_votes_expiry ON poll_votes(created_at);
