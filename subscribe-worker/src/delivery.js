import { hash, token, safeError, enabled } from "./common.js";
import { catalog, latestIssue, issueAttachment } from "./issues.js";
import { confirmationEmail, issueEmail } from "./emails.js";
const changes = (r) => Number(r.meta?.changes || 0),
  MAX_BATCH = 2,
  SAFE_RETRY_WINDOW = 23 * 60 * 60 * 1000;
const formatters = new Map();
export function weekendKey(now, timezone = "America/Los_Angeles") {
  if (!formatters.has(timezone))
    formatters.set(
      timezone,
      new Intl.DateTimeFormat("en-US", {
        timeZone: timezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        weekday: "short",
        hour: "2-digit",
        hourCycle: "h23",
      }),
    );
  const p = Object.fromEntries(
    formatters
      .get(timezone)
      .formatToParts(new Date(now))
      .map((x) => [x.type, x.value]),
  );
  if (
    !["Sat", "Sun"].includes(p.weekday) ||
    (p.weekday === "Sat" && Number(p.hour) < 8)
  )
    return null;
  const d = new Date(`${p.year}-${p.month}-${p.day}T12:00:00Z`);
  if (p.weekday === "Sun") d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}
export async function queueConfirmation(env, sub, s) {
  const id = "confirm-" + (await hash(sub.verify_token)),
    payload = {
      mail: confirmationEmail(env, sub, catalog[sub.edition_slug].name),
      verify_token: sub.verify_token,
    };
  await env.DB.prepare(
    `INSERT OR IGNORE INTO deliveries(id,subscriber_id,kind,payload_json,created_at) VALUES(?,?,'confirmation',?,?)`,
  )
    .bind(id, sub.id, JSON.stringify(payload), s.now())
    .run();
  return id;
}
export async function queueIssue(env, sub, issue, s, { welcome = false } = {}) {
  if (
    sub.status !== "active" ||
    (sub.last_sent_issue_date && sub.last_sent_issue_date >= issue.date)
  )
    return false;
  const slot =
    sub.cadence === "weekly_weekend"
      ? weekendKey(s.now(), env.WEEKEND_TIMEZONE)
      : null;
  if (sub.cadence === "weekly_weekend" && !welcome && !slot) return false;
  if (
    await env.DB.prepare(
      "SELECT id FROM deliveries WHERE subscriber_id=? AND kind='issue' AND issue_date=?",
    )
      .bind(sub.id, issue.date)
      .first()
  )
    return false;
  if (
    slot &&
    (await env.DB.prepare(
      "SELECT id FROM deliveries WHERE subscriber_id=? AND weekend_key=?",
    )
      .bind(sub.id, slot)
      .first())
  )
    return false;
  const id = "issue-" + (await hash(`${sub.id}/${issue.date}`)),
    payload = { mail: issueEmail(env, sub, issue), issue };
  return (
    changes(
      await env.DB.prepare(
        `INSERT OR IGNORE INTO deliveries(id,subscriber_id,kind,issue_date,weekend_key,payload_json,attachment_url,created_at) VALUES(?,?,'issue',?,?,?,?,?)`,
      )
        .bind(
          id,
          sub.id,
          issue.date,
          slot,
          JSON.stringify(payload),
          issue.pdf,
          s.now(),
        )
        .run(),
    ) === 1
  );
}
async function cancel(env, id, reason) {
  await env.DB.prepare(
    "UPDATE deliveries SET state='cancelled',last_error=? WHERE id=? AND state!='sent'",
  )
    .bind(reason, id)
    .run();
}
export async function flushOutbox(
  env,
  s,
  { subscriberId = null, limit = MAX_BATCH } = {},
) {
  const result = { sent: 0, deferred: 0, held: 0, cancelled: 0 };
  if (!enabled(env)) return { ...result, disabled: true };
  const owner = token(),
    now = s.now();
  if (
    !changes(
      await env.DB.prepare(
        "UPDATE send_control SET owner=?,lease_until=? WHERE id=1 AND lease_until<=?",
      )
        .bind(owner, now + 60_000, now)
        .run(),
    )
  )
    return { ...result, busy: true };
  try {
    const started = s.now();
    for (let i = 0; i < Math.min(MAX_BATCH, Math.max(1, limit)); i++) {
      if (s.now() - started > 20_000) break;
      const ctl = await env.DB.prepare(
        "SELECT * FROM send_control WHERE id=1 AND owner=?",
      )
        .bind(owner)
        .first();
      if (!ctl) break;
      if (ctl.pause_until > s.now()) {
        result.deferred++;
        break;
      }
      const today = new Date(s.now()).toISOString().slice(0, 10),
        cap = Math.max(1, Number(env.DAILY_EMAIL_LIMIT) || 90);
      if (ctl.daily_date === today && ctl.daily_count >= cap) {
        result.deferred++;
        break;
      }
      const row = await env.DB.prepare(
        `SELECT * FROM deliveries WHERE state IN ('pending','retry','sending') AND next_attempt_at<=?${subscriberId ? " AND subscriber_id=?" : ""} ORDER BY created_at,id LIMIT 1`,
      )
        .bind(...[s.now(), ...(subscriberId ? [subscriberId] : [])])
        .first();
      if (!row) break;
      const sub = await env.DB.prepare("SELECT * FROM subscribers WHERE id=?")
          .bind(row.subscriber_id)
          .first(),
        p = JSON.parse(row.payload_json);
      if (
        !sub ||
        (row.kind === "confirmation"
          ? sub.status !== "pending" || sub.verify_token !== p.verify_token
          : sub.status !== "active")
      ) {
        await cancel(env, row.id, "subscription_inactive");
        result.cancelled++;
        continue;
      }
      if (
        row.kind === "issue" &&
        sub.last_sent_issue_date &&
        sub.last_sent_issue_date >= row.issue_date
      ) {
        await cancel(env, row.id, "issue_already_sent");
        result.cancelled++;
        continue;
      }
      if (
        row.first_attempt_at !== null &&
        s.now() - row.first_attempt_at >= SAFE_RETRY_WINDOW
      ) {
        await env.DB.prepare(
          "UPDATE deliveries SET state='held',last_error='ambiguous_send_expired' WHERE id=?",
        )
          .bind(row.id)
          .run();
        result.held++;
        continue;
      }
      let mail = p.mail;
      if (row.kind === "issue") {
        try {
          const asset = await issueAttachment(p.issue, s, {
            retry: !!row.attachment_sha256,
            expectedHash: row.attachment_sha256,
          });
          if (!row.attachment_sha256)
            await env.DB.prepare(
              "UPDATE deliveries SET attachment_sha256=? WHERE id=?",
            )
              .bind(asset.digest, row.id)
              .run();
          mail = { ...mail, attachments: [asset.attachment] };
        } catch (e) {
          const reason = safeError(e),
            hold = [
              "attachment_changed",
              "asset_too_large",
              "invalid_pdf",
            ].includes(reason);
          await env.DB.prepare(
            "UPDATE deliveries SET state=?,next_attempt_at=?,last_error=? WHERE id=?",
          )
            .bind(hold ? "held" : "retry", s.now() + 300_000, reason, row.id)
            .run();
          result[hold ? "held" : "deferred"]++;
          continue;
        }
      }
      const current = await env.DB.prepare(
        "SELECT status,verify_token FROM subscribers WHERE id=?",
      )
        .bind(sub.id)
        .first();
      if (
        current.status !== (row.kind === "issue" ? "active" : "pending") ||
        (row.kind === "confirmation" && current.verify_token !== p.verify_token)
      ) {
        await cancel(env, row.id, "subscription_inactive");
        result.cancelled++;
        continue;
      }
      if (ctl.next_send_at > s.now())
        await s.sleep(Math.min(3000, ctl.next_send_at - s.now()));
      const renewed = await env.DB.prepare(
        "UPDATE send_control SET lease_until=?,daily_date=?,daily_count=CASE WHEN daily_date=? THEN daily_count+1 ELSE 1 END,next_send_at=? WHERE id=1 AND owner=? AND lease_until>?",
      )
        .bind(s.now() + 60_000, today, today, s.now() + 1100, owner, s.now())
        .run();
      if (!changes(renewed)) break;
      await env.DB.prepare(
        "UPDATE deliveries SET state='sending',first_attempt_at=COALESCE(first_attempt_at,?),attempts=attempts+1 WHERE id=?",
      )
        .bind(s.now(), row.id)
        .run();
      let accepted = false;
      try {
        const response = await s.fetch("https://api.resend.com/emails", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.RESEND_API_KEY}`,
            "Content-Type": "application/json",
            "Idempotency-Key": row.id,
          },
          body: JSON.stringify(mail),
          signal: AbortSignal.timeout(10000),
        });
        if (response.ok) {
          accepted = true;
          const data = await response.json();
          if (typeof data.id !== "string" || !data.id)
            throw Error("missing_provider_id");
          const writes = [
            env.DB.prepare(
              "UPDATE deliveries SET state='sent',provider_message_id=?,last_error=NULL WHERE id=?",
            ).bind(data.id, row.id),
          ];
          if (row.kind === "issue")
            writes.push(
              env.DB.prepare(
                "UPDATE subscribers SET last_sent_issue_date=CASE WHEN last_sent_issue_date IS NULL OR last_sent_issue_date<? THEN ? ELSE last_sent_issue_date END WHERE id=?",
              ).bind(row.issue_date, row.issue_date, sub.id),
            );
          await env.DB.batch(writes);
          result.sent++;
        } else {
          const seconds = Number(response.headers.get("Retry-After")),
            delay =
              Number.isFinite(seconds) && seconds > 0
                ? Math.min(seconds * 1000, 86_400_000)
                : 60_000;
          if (response.status === 429) {
            await env.DB.prepare(
              "UPDATE send_control SET pause_until=? WHERE id=1 AND owner=?",
            )
              .bind(s.now() + delay, owner)
              .run();
            // Do not erase a previous ambiguous attempt just because a replay was rate-limited.
            await env.DB.prepare(
              "UPDATE deliveries SET state='retry',first_attempt_at=?,next_attempt_at=?,last_error='provider_rate_limit' WHERE id=?",
            )
              .bind(row.first_attempt_at, s.now() + delay, row.id)
              .run();
            result.deferred++;
            break;
          }
          const permanent =
            response.status >= 400 &&
            response.status < 500 &&
            ![408, 409].includes(response.status);
          await env.DB.prepare(
            "UPDATE deliveries SET state=?,next_attempt_at=?,last_error=? WHERE id=?",
          )
            .bind(
              permanent ? "held" : "retry",
              s.now() + delay,
              `provider_http_${response.status}`,
              row.id,
            )
            .run();
          result[permanent ? "held" : "deferred"]++;
        }
      } catch {
        await env.DB.prepare(
          "UPDATE deliveries SET state='retry',next_attempt_at=?,last_error=? WHERE id=?",
        )
          .bind(
            s.now() + 60_000,
            accepted ? "acknowledgement_lost" : "send_result_unknown",
            row.id,
          )
          .run();
        result.deferred++;
      }
    }
  } finally {
    await env.DB.prepare(
      "UPDATE send_control SET owner=NULL,lease_until=0 WHERE id=1 AND owner=?",
    )
      .bind(owner)
      .run();
  }
  return result;
}
export async function dispatch(env, s, options = {}) {
  const slugs = options.editions || Object.keys(catalog);
  if (
    !Array.isArray(slugs) ||
    !slugs.length ||
    slugs.length > 20 ||
    slugs.some((x) => typeof x !== "string" || !Object.hasOwn(catalog, x))
  )
    throw Error("invalid_editions");
  const limit = Number.isInteger(options.limit)
    ? Math.max(1, Math.min(MAX_BATCH, options.limit))
    : MAX_BATCH;
  const result = {
    queued: 0,
    eligible: 0,
    issues: {},
    errors: {},
    dry_run: !!options.dry_run,
  };
  for (const slug of [...new Set(slugs)]) {
    if (result.eligible >= limit) break;
    if (
      !(await env.DB.prepare(
        "SELECT id FROM subscribers WHERE status='active' AND edition_slug=? LIMIT 1",
      )
        .bind(slug)
        .first())
    )
      continue;
    try {
      const issue = await latestIssue(slug, s);
      result.issues[slug] = issue.date;
      if (
        options.expected_issue_dates?.[slug] &&
        options.expected_issue_dates[slug] !== issue.date
      )
        throw Error("deployed_date_mismatch");
      const slot = weekendKey(s.now(), env.WEEKEND_TIMEZONE);
      const rows = await env.DB.prepare(
        `SELECT s.* FROM subscribers s WHERE s.status='active' AND s.edition_slug=? AND (s.last_sent_issue_date IS NULL OR s.last_sent_issue_date<?) AND (s.cadence='every_issue' OR s.last_sent_issue_date IS NULL OR ? IS NOT NULL) AND NOT EXISTS(SELECT 1 FROM deliveries d WHERE d.subscriber_id=s.id AND d.kind='issue' AND d.issue_date=?) AND (s.cadence!='weekly_weekend' OR NOT EXISTS(SELECT 1 FROM deliveries d WHERE d.subscriber_id=s.id AND d.weekend_key=?)) ORDER BY s.created_at,s.id LIMIT ?`,
      )
        .bind(slug, issue.date, slot, issue.date, slot, limit - result.eligible)
        .all();
      for (const sub of rows.results) {
        result.eligible++;
        if (
          !options.dry_run &&
          (await queueIssue(env, sub, issue, s, {
            welcome: !sub.last_sent_issue_date,
          }))
        )
          result.queued++;
      }
    } catch (e) {
      result.errors[slug] = safeError(e);
    }
  }
  if (!options.dry_run) result.delivery = await flushOutbox(env, s, { limit });
  return result;
}
