import {
  SITE,
  ALLOWED_ORIGINS,
  token,
  hash,
  baseURL,
  constantEqual,
  enabled,
  defaults,
  esc,
  safeError,
  bounded,
} from "./common.js";
import { catalog, latestIssue } from "./issues.js";
import {
  queueConfirmation,
  queueIssue,
  flushOutbox,
  dispatch,
} from "./delivery.js";
const generic = {
  ok: true,
  message:
    "If this address can subscribe, a confirmation email will arrive shortly.",
};
const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
const page = (title, text, status = 200) =>
  new Response(
    `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(title)} · News Pebbles</title><body style="background:#f4f1ea;color:#1e2d33;font:18px/1.6 Arial,sans-serif;padding:24px"><main style="max-width:540px;margin:40px auto"><h1>${esc(title)}</h1><p>${esc(text)}</p><a href="${SITE}/">Back to News Pebbles</a></main></body></html>`,
    { status, headers: { "Content-Type": "text/html; charset=utf-8" } },
  );
async function bodyJSON(request) {
  if (
    !request.headers
      .get("Content-Type")
      ?.toLowerCase()
      .startsWith("application/json")
  )
    throw Error("json_required");
  const bytes = await bounded(
    new Response(request.body, { headers: request.headers }),
    8193,
  );
  return JSON.parse(new TextDecoder().decode(bytes));
}
async function throttle(env, request, email, s) {
  const now = s.now(),
    hour = Math.floor(now / 3_600_000),
    ip = request.headers.get("CF-Connecting-IP") || "unknown";
  for (const [prefix, value, max] of [
    ["email", email, 3],
    ["ip", ip, 15],
  ]) {
    const key = await hash(`${env.DISPATCH_SECRET}/${prefix}/${value}/${hour}`);
    const row = await env.DB.prepare(
      `INSERT INTO rate_limits(key,count,expires_at) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1 RETURNING count`,
    )
      .bind(key, (hour + 2) * 3_600_000)
      .first();
    if (row.count > max) return false;
  }
  return true;
}
async function subscribe(request, env, s) {
  if (!enabled(env))
    return json({ error: "Subscriptions are not enabled yet." }, 503);
  baseURL(env);
  let data;
  try {
    data = await bodyJSON(request);
  } catch {
    return json({ error: "Send a small JSON request." }, 400);
  }
  if (!data || typeof data !== "object" || Array.isArray(data))
    return json({ error: "Invalid form." }, 400);
  if (typeof data.website === "string" && data.website.trim())
    return json(generic, 202);
  if (data.website !== undefined && typeof data.website !== "string")
    return json({ error: "Invalid form." }, 400);
  const email =
    typeof data.email === "string" ? data.email.trim().toLowerCase() : "";
  if (
    email.length > 254 ||
    email.split("@")[0].length > 64 ||
    email.startsWith(".") ||
    email.split("@")[0].endsWith(".") ||
    (email.includes("@") &&
      email
        .split("@")[1]
        .split(".")
        .some(
          (label) => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i.test(label),
        )) ||
    !/^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}$/i.test(
      email,
    ) ||
    email.includes("..")
  )
    return json({ error: "Enter a valid parent email address." }, 400);
  if (
    typeof data.edition_slug !== "string" ||
    !Object.hasOwn(catalog, data.edition_slug) ||
    !["every_issue", "weekly_weekend"].includes(data.cadence)
  )
    return json(
      { error: "Choose a valid edition and delivery frequency." },
      400,
    );
  if (!(await throttle(env, request, email, s)))
    return json(
      { error: "Please wait before requesting another confirmation." },
      429,
    );
  const existing = await env.DB.prepare(
    "SELECT * FROM subscribers WHERE email=? AND edition_slug=?",
  )
    .bind(email, data.edition_slug)
    .first();
  if (existing?.status === "active") return json(generic, 202);
  if (existing?.status === "pending") {
    const sent = await env.DB.prepare(
      "SELECT created_at FROM deliveries WHERE subscriber_id=? AND kind='confirmation' ORDER BY created_at DESC LIMIT 1",
    )
      .bind(existing.id)
      .first();
    if (sent && s.now() - sent.created_at < 86_400_000) {
      await flushOutbox(env, s, { subscriberId: existing.id, limit: 1 });
      return json(generic, 202);
    }
  }
  const sub = {
    id: existing?.id || crypto.randomUUID(),
    email,
    edition_slug: data.edition_slug,
    cadence: data.cadence,
    status: "pending",
    verify_token: token(),
    unsubscribe_token: token(),
    created_at: existing?.created_at || s.now(),
  };
  await env.DB.batch([
    env.DB.prepare(
      "UPDATE deliveries SET state='cancelled',last_error='new_confirmation_requested' WHERE subscriber_id=? AND state!='sent' AND EXISTS(SELECT 1 FROM subscribers WHERE id=? AND status!='active')",
    ).bind(sub.id, sub.id),
    env.DB.prepare(
      `INSERT INTO subscribers(id,email,edition_slug,cadence,status,verify_token,unsubscribe_token,created_at) VALUES(?,?,?,?,'pending',?,?,?) ON CONFLICT(email,edition_slug) DO UPDATE SET cadence=excluded.cadence,status='pending',verify_token=excluded.verify_token,unsubscribe_token=excluded.unsubscribe_token WHERE subscribers.status!='active'`,
    ).bind(
      sub.id,
      email,
      sub.edition_slug,
      sub.cadence,
      sub.verify_token,
      sub.unsubscribe_token,
      sub.created_at,
    ),
  ]);
  const actual = await env.DB.prepare(
    "SELECT * FROM subscribers WHERE email=? AND edition_slug=?",
  )
    .bind(email, sub.edition_slug)
    .first();
  if (actual.status === "pending") {
    await queueConfirmation(env, actual, s);
    await flushOutbox(env, s, { subscriberId: actual.id, limit: 1 });
  }
  return json(generic, 202);
}
async function verify(url, env, s) {
  const value = url.searchParams.get("token");
  if (!/^[a-f0-9]{64}$/.test(value || ""))
    return page(
      "That link is not valid",
      "Please request a new confirmation email.",
      400,
    );
  const sub = await env.DB.prepare(
    "SELECT * FROM subscribers WHERE verify_token=? AND status='pending'",
  )
    .bind(value)
    .first();
  if (!sub)
    return page(
      "That link is no longer active",
      "It may already have been used. You can request a new confirmation if needed.",
      400,
    );
  const confirmation = await env.DB.prepare(
    "SELECT created_at FROM deliveries WHERE id=?",
  )
    .bind("confirm-" + (await hash(value)))
    .first();
  if (!confirmation || s.now() - confirmation.created_at >= 86_400_000)
    return page(
      "That link has expired",
      "Please request a fresh confirmation email.",
      400,
    );
  if (!enabled(env))
    return page(
      "Please try again shortly",
      "Email delivery is temporarily paused.",
      503,
    );
  const activated = await env.DB.prepare(
    "UPDATE subscribers SET status='active',verify_token=NULL WHERE id=? AND status='pending' AND verify_token=?",
  )
    .bind(sub.id, value)
    .run();
  if (activated.meta.changes) {
    sub.status = "active";
    try {
      await queueIssue(env, sub, await latestIssue(sub.edition_slug, s), s, {
        welcome: true,
      });
      await flushOutbox(env, s, { subscriberId: sub.id, limit: 2 });
    } catch {
      /* Cron/dispatch recovers an active subscriber with no welcome delivery. */
    }
  }
  return new Response(null, {
    status: 302,
    headers: { Location: SITE + "/?subscribed=true" },
  });
}
async function unsubscribe(url, env) {
  const value = url.searchParams.get("token");
  if (!/^[a-f0-9]{64}$/.test(value || ""))
    return page(
      "That link is not valid",
      "Please use the unsubscribe link in your email.",
      400,
    );
  const sub = await env.DB.prepare(
    "SELECT id FROM subscribers WHERE unsubscribe_token=?",
  )
    .bind(value)
    .first();
  if (!sub)
    return page(
      "That link is not valid",
      "Please use the unsubscribe link in your email.",
      400,
    );
  await env.DB.batch([
    env.DB.prepare(
      "UPDATE subscribers SET status='unsubscribed',verify_token=NULL WHERE id=?",
    ).bind(sub.id),
    env.DB.prepare(
      "UPDATE deliveries SET state='cancelled',last_error='unsubscribed' WHERE subscriber_id=? AND state NOT IN ('sent','cancelled')",
    ).bind(sub.id),
  ]);
  return page(
    "You’re unsubscribed",
    "You won’t receive any more emails for this newspaper. Thank you for making room for a little world discovery. You can subscribe again whenever you like.",
  );
}
export function createWorker(overrides = {}) {
  const s = defaults(overrides);
  return {
    async fetch(request, env) {
      const origin = request.headers.get("Origin"),
        url = new URL(request.url);
      let response;
      try {
        if (origin && !ALLOWED_ORIGINS.has(origin))
          response = json({ error: "Origin not allowed." }, 403);
        else if (request.method === "OPTIONS") {
          const method = request.headers.get("Access-Control-Request-Method"),
            headers = (
              request.headers.get("Access-Control-Request-Headers") || ""
            )
              .split(",")
              .map((x) => x.trim().toLowerCase())
              .filter(Boolean);
          response =
            !origin ||
            !["GET", "POST"].includes(method) ||
            headers.some((x) => !["content-type", "authorization"].includes(x))
              ? json({ error: "Preflight not allowed." }, 403)
              : new Response(null, {
                  status: 204,
                  headers: {
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers":
                      "Content-Type, Authorization",
                    "Access-Control-Max-Age": "600",
                  },
                });
        } else if (
          url.pathname === "/api/subscribe" &&
          request.method === "POST"
        )
          response = !origin
            ? json({ error: "Origin required." }, 403)
            : await subscribe(request, env, s);
        else if (url.pathname === "/api/verify" && request.method === "GET")
          response = await verify(url, env, s);
        else if (
          url.pathname === "/api/unsubscribe" &&
          ["GET", "POST"].includes(request.method)
        )
          response = await unsubscribe(url, env);
        else if (
          url.pathname === "/api/dispatch" &&
          request.method === "POST"
        ) {
          if (
            !env.DISPATCH_SECRET ||
            !constantEqual(
              request.headers.get("Authorization") || "",
              `Bearer ${env.DISPATCH_SECRET}`,
            )
          )
            response = json({ error: "Unauthorized." }, 401);
          else {
            let data;
            try {
              data = await bodyJSON(request);
            } catch {
              data = null;
            }
            if (
              !data ||
              typeof data !== "object" ||
              Array.isArray(data) ||
              (data.dry_run !== undefined && typeof data.dry_run !== "boolean")
            )
              response = json(
                { error: "Send a JSON object with a boolean dry_run." },
                400,
              );
            else if (!enabled(env) && !data.dry_run)
              response = json({ error: "Delivery is disabled." }, 503);
            else response = json(await dispatch(env, s, data));
          }
        } else response = json({ error: "Not found." }, 404);
      } catch (error) {
        response = json(
          { error: safeError(error) },
          error.message === "invalid_editions" ? 400 : 503,
        );
      }
      const h = new Headers(response.headers);
      h.set("Cache-Control", "no-store");
      h.set("Referrer-Policy", "no-referrer");
      h.set("X-Content-Type-Options", "nosniff");
      h.set("Vary", "Origin");
      if (origin && ALLOWED_ORIGINS.has(origin))
        h.set("Access-Control-Allow-Origin", origin);
      return new Response(response.body, {
        status: response.status,
        headers: h,
      });
    },
    async scheduled(event, env, ctx) {
      if (enabled(env))
        ctx.waitUntil(
          (async () => {
            await env.DB.prepare("DELETE FROM rate_limits WHERE expires_at<?")
              .bind(s.now())
              .run();
            await dispatch(env, s);
          })(),
        );
    },
  };
}
export default createWorker();
