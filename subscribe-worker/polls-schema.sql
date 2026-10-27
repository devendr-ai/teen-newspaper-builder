-- Additive: existing subscribers and delivery history remain untouched.
CREATE TABLE IF NOT EXISTS poll_votes (
  poll_id TEXT NOT NULL,
  receipt_hash TEXT NOT NULL,
  choice INTEGER NOT NULL CHECK(choice IN (0,1)),
  created_at INTEGER NOT NULL,
  PRIMARY KEY(poll_id, receipt_hash)
);
CREATE INDEX IF NOT EXISTS poll_votes_expiry ON poll_votes(created_at);
