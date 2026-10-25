import { test } from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { createWorker } from "../src/index.js";
import {
  dispatch,
  flushOutbox,
  weekendKey,
  queueIssue,
} from "../src/delivery.js";
import { latestIssue, issueAttachment, catalog } from "../src/issues.js";
import { bounded } from "../src/common.js";
class D1 {
  db = new DatabaseSync(":memory:");
  failAck = false;
  constructor() {
    this.db.exec(
      readFileSync(new URL("../schema.sql", import.meta.url), "utf8"),
    );
  }
  prepare(sql) {
    const db = this.db;
    return {
      bind(...args) {
        return {
          async first() {
            return db.prepare(sql).get(...args) || null;
          },
          async all() {
            return { results: db.prepare(sql).all(...args) };
          },
          async run() {
            const r = db.prepare(sql).run(...args);
            return { meta: { changes: Number(r.changes) } };
          },
        };
      },
      async run() {
        const r = db.prepare(sql).run();
        return { meta: { changes: Number(r.changes) } };
      },
    };
  }
  async batch(rows) {
    this.db.exec("BEGIN");
    try {
      if (this.failAck) {
        this.failAck = false;
        throw Error("database outage");
      }
      const r = [];
      for (const row of rows) r.push(await row.run());
      this.db.exec("COMMIT");
      return r;
    } catch (e) {
      this.db.exec("ROLLBACK");
      throw e;
    }
  }
}
function fixture() {
  const f = {
    now: Date.parse("2026-10-26T16:00:00Z"),
    date: "2026-10-25",
    calls: [],
    pdf: "%PDF-1.7\nfixture",
    alias: null,
    stub: false,
    provider: null,
  };
  f.env = {
    DB: new D1(),
    PUBLIC_BASE_URL: "https://newspebbles-subscribe.example.workers.dev",
    RESEND_FROM: "News Pebbles <papers@mail.newspebbles.com>",
    RESEND_API_KEY: "test-only",
    DISPATCH_SECRET: "test-secret",
    DELIVERY_ENABLED: "true",
    WEEKEND_TIMEZONE: "America/Los_Angeles",
    DAILY_EMAIL_LIMIT: "90",
  };
  f.services = {
    now: () => f.now,
    sleep: async (ms) => {
      f.now += ms;
    },
    fetch: async (url, opts = {}) => {
      if (url === "https://api.resend.com/emails") {
        const call = {
          body: JSON.parse(opts.body),
          key: opts.headers["Idempotency-Key"],
          at: f.now,
        };
        f.calls.push(call);
        return f.provider
          ? f.provider(call)
          : Response.json({ id: "provider-" + call.key });
      }
      assert.ok(url.startsWith("https://newspebbles.com/"));
      assert.equal(opts.redirect, "manual");
      if (url.endsWith("/feed.xml")) {
        const slug = url.split("/")[4];
        return new Response(
          `<rss><channel><item><link>https://newspebbles.com/e/${slug}/${f.date}.pdf</link></item></channel></rss>`,
        );
      }
      if (url.endsWith(".html"))
        return new Response(
          `<main class="${f.stub ? "stub" : "issue"}">An issue</main>`,
        );
      if (url.endsWith(".pdf"))
        return new Response(
          url.endsWith("/latest.pdf") ? (f.alias ?? f.pdf) : f.pdf,
        );
      throw Error("unexpected url");
    },
  };
  f.worker = createWorker(f.services);
  f.req = async (
    path,
    data,
    { origin = "https://newspebbles.com", method = "POST", headers = {} } = {},
  ) =>
    f.worker.fetch(
      new Request("https://worker.test" + path, {
        method,
        headers: {
          ...(origin ? { Origin: origin } : {}),
          ...(data !== undefined ? { "Content-Type": "application/json" } : {}),
          ...headers,
        },
        ...(data !== undefined ? { body: JSON.stringify(data) } : {}),
      }),
      f.env,
    );
  f.subscribe = async (
    email = "parent@example.com",
    slug = "little-explorers",
    cadence = "every_issue",
  ) => {
    const r = await f.req("/api/subscribe", {
      email,
      edition_slug: slug,
      cadence,
      website: "",
    });
    assert.equal(r.status, 202);
    return f.env.DB.db
      .prepare("SELECT * FROM subscribers WHERE email=? AND edition_slug=?")
      .get(email.toLowerCase(), slug);
  };
  f.verify = async (sub) =>
    f.req("/api/verify?token=" + sub.verify_token, undefined, {
      method: "GET",
      origin: null,
    });
  f.sub = () => f.env.DB.db.prepare("SELECT * FROM subscribers LIMIT 1").get();
  f.send = (options) => dispatch(f.env, f.services, options);
  return f;
}
test("strict CORS, preflight, dispatch authentication, disabled switch", async () => {
  const f = fixture();
  for (const origin of [
    "https://evil.com",
    "https://newspebbles.com.evil.com",
    "null",
    "http://localhost:3000",
  ])
    assert.equal((await f.req("/api/subscribe", {}, { origin })).status, 403);
  for (const origin of ["https://newspebbles.com", "http://localhost"]) {
    const r = await f.req("/api/subscribe", undefined, {
      origin,
      method: "OPTIONS",
      headers: {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
      },
    });
    assert.equal(r.status, 204);
    assert.equal(r.headers.get("Access-Control-Allow-Origin"), origin);
  }
  assert.equal(
    (await f.req("/api/subscribe", {}, { origin: null })).status,
    403,
  );
  assert.equal((await f.req("/api/dispatch", {})).status, 401);
  f.env.DELIVERY_ENABLED = "false";
  assert.equal((await f.req("/api/subscribe", {})).status, 503);
  assert.equal(f.calls.length, 0);
  assert.equal(
    (
      await f.req(
        "/api/dispatch",
        { dry_run: true },
        { headers: { Authorization: "Bearer test-secret" } },
      )
    ).status,
    200,
  );
});
test("input validation and honeypot never create rows or send", async () => {
  const f = fixture(),
    valid = {
      email: "parent@example.com",
      edition_slug: "little-explorers",
      cadence: "every_issue",
    };
  for (const change of [
    { email: "bad" },
    { email: ".bad@example.com" },
    { email: "bad.@example.com" },
    { email: "bad@foo-.com" },
    { edition_slug: ["little-explorers"] },
    { email: "a..b@example.com" },
    { edition_slug: "__proto__" },
    { cadence: "daily" },
    { website: 3 },
  ])
    assert.equal(
      (await f.req("/api/subscribe", { ...valid, ...change })).status,
      400,
    );
  assert.equal(
    (await f.req("/api/subscribe", { ...valid, website: "bot.example" }))
      .status,
    202,
  );
  assert.equal(
    f.env.DB.db.prepare("SELECT count(*) AS n FROM subscribers").get().n,
    0,
  );
  assert.equal(f.calls.length, 0);
  assert.equal(
    (await f.req("/api/subscribe", { ...valid, padding: "x".repeat(9000) }))
      .status,
    400,
  );
});
test("unique email + edition, pending confirmation only once, different editions allowed", async () => {
  const f = fixture();
  await f.subscribe("Parent@Example.com");
  await f.subscribe();
  await f.subscribe("parent@example.com", "breakfast-table");
  assert.equal(f.calls.length, 2);
  assert.equal(
    f.env.DB.db.prepare("SELECT count(*) AS n FROM subscribers").get().n,
    2,
  );
  for (const call of f.calls) {
    assert.ok(
      call.body.headers["List-Unsubscribe"].includes("/api/unsubscribe?token="),
    );
    assert.equal(
      call.body.headers["List-Unsubscribe-Post"],
      "List-Unsubscribe=One-Click",
    );
    assert.equal(call.body.attachments, undefined);
  }
});
for (const cadence of ["every_issue", "weekly_weekend"])
  test(`verification sends weekday welcome with PDF (${cadence})`, async () => {
    const f = fixture(),
      sub = await f.subscribe(
        "parent@example.com",
        "little-explorers",
        cadence,
      );
    assert.equal(f.sub().status, "pending");
    assert.equal(f.calls.length, 1);
    const r = await f.verify(sub);
    assert.equal(r.status, 302);
    assert.equal(
      r.headers.get("Location"),
      "https://newspebbles.com/?subscribed=true",
    );
    assert.equal(f.sub().status, "active");
    assert.equal(f.sub().last_sent_issue_date, f.date);
    const mail = f.calls[1].body;
    assert.ok(
      mail.html.indexOf("Open in Read &amp; Play (Audio + Quiz)") <
        mail.html.indexOf("Download Printable PDF"),
    );
    assert.ok(mail.html.includes("https://wa.me/?text="));
    assert.ok(mail.html.includes(`/play/little-explorers/${f.date}.html`));
    assert.equal(
      Buffer.from(mail.attachments[0].content, "base64").toString(),
      f.pdf,
    );
    assert.ok(mail.headers["List-Unsubscribe"]);
    assert.equal((await f.verify(sub)).status, 400);
    await f.send();
    assert.equal(f.calls.length, 2);
    await f.subscribe();
    assert.equal(f.sub().status, "active");
    assert.equal(f.calls.length, 2);
  });
test("verification expires after 24 hours", async () => {
  const f = fixture(),
    sub = await f.subscribe();
  f.now += 86400000;
  assert.equal((await f.verify(sub)).status, 400);
  assert.equal(f.sub().status, "pending");
});
test("dispatch only newer dates, no duplicates, expected deployed date guard and dry-run", async () => {
  const f = fixture();
  await f.verify(await f.subscribe());
  f.date = "2026-10-26";
  let r = await f.send({ dry_run: true });
  assert.equal(r.eligible, 1);
  assert.equal(f.calls.length, 2);
  r = await f.send({
    expected_issue_dates: { "little-explorers": "2026-10-27" },
  });
  assert.equal(r.errors["little-explorers"], "deployed_date_mismatch");
  assert.equal(f.calls.length, 2);
  await Promise.all([f.send(), f.send()]);
  assert.equal(f.calls.length, 3);
  assert.equal(f.sub().last_sent_issue_date, "2026-10-26");
  f.pdf = "%PDF-1.7\ncorrected";
  await f.send();
  assert.equal(f.calls.length, 3);
  f.date = "2026-10-24";
  await f.send();
  assert.equal(f.calls.length, 3);
});
test("weekly delivery: Saturday after 8am, once per weekend, no duplicate Sunday", async () => {
  const f = fixture();
  await f.verify(
    await f.subscribe("p@example.com", "little-explorers", "weekly_weekend"),
  );
  f.date = "2026-10-26";
  await f.send();
  assert.equal(f.calls.length, 2);
  f.now = Date.parse("2026-10-31T14:59:00Z");
  await f.send();
  assert.equal(f.calls.length, 2);
  f.now += 60000;
  await f.send();
  assert.equal(f.calls.length, 3);
  f.date = "2026-10-27";
  f.now = Date.parse("2026-11-01T17:00:00Z");
  await f.send();
  assert.equal(f.calls.length, 3);
  assert.equal(weekendKey(f.now), "2026-10-31");
  assert.equal(weekendKey(Date.parse("2026-11-07T16:00:00Z")), "2026-11-07");
});
for (const method of ["GET", "POST"])
  test(`unsubscribe ${method} cancels queued deliveries and is edition scoped`, async () => {
    const f = fixture(),
      one = await f.subscribe();
    await f.verify(one);
    const two = await f.subscribe("parent@example.com", "breakfast-table");
    await f.verify(two);
    f.date = "2026-10-26";
    const issue = await latestIssue(one.edition_slug, f.services);
    await queueIssue(f.env, f.sub(), issue, f.services);
    const r = await f.req(
      "/api/unsubscribe?token=" + one.unsubscribe_token,
      undefined,
      { method, origin: null },
    );
    assert.equal(r.status, 200);
    assert.ok((await r.text()).includes("You’re unsubscribed"));
    assert.equal(f.sub().status, "unsubscribed");
    await f.send();
    assert.equal(
      f.calls.filter(
        (x) =>
          x.body.to[0] === "parent@example.com" &&
          x.body.attachments?.[0].filename.startsWith("little-explorers"),
      ).length,
      1,
    );
    assert.equal(
      f.env.DB.db
        .prepare(
          "SELECT status FROM subscribers WHERE edition_slug='breakfast-table'",
        )
        .get().status,
      "active",
    );
    assert.equal(
      (
        await f.req(
          "/api/unsubscribe?token=" + one.unsubscribe_token,
          undefined,
          { method, origin: null },
        )
      ).status,
      200,
    );
  });
test("ambiguous provider response retries with stable key and identical payload, expires safely", async () => {
  const f = fixture();
  await f.verify(await f.subscribe());
  f.date = "2026-10-26";
  f.provider = () => {
    throw Error("accepted but response lost");
  };
  await f.send();
  const original = f.calls.at(-1);
  assert.equal(f.sub().last_sent_issue_date, "2026-10-25");
  f.now += 61000;
  f.provider = () => Response.json({ id: "accepted-original" });
  await f.send();
  assert.deepEqual(f.calls.at(-1).body, original.body);
  assert.equal(f.calls.at(-1).key, original.key);
  assert.equal(f.sub().last_sent_issue_date, "2026-10-26");
  f.date = "2026-10-27";
  f.provider = () => {
    throw Error("unknown");
  };
  await f.send();
  const count = f.calls.length;
  f.now += 23 * 3600000;
  await f.send();
  assert.equal(f.calls.length, count);
  assert.equal(
    f.env.DB.db
      .prepare(
        "SELECT last_error FROM deliveries WHERE issue_date='2026-10-27'",
      )
      .get().last_error,
    "ambiguous_send_expired",
  );
});
test("lost database acknowledgement reuses provider key", async () => {
  const f = fixture();
  await f.verify(await f.subscribe());
  f.date = "2026-10-26";
  f.provider = () => {
    f.env.DB.failAck = true;
    return Response.json({ id: "accepted" });
  };
  await f.send();
  const key = f.calls.at(-1).key;
  f.provider = null;
  f.now += 61000;
  await f.send();
  assert.equal(f.calls.at(-1).key, key);
  assert.equal(f.sub().last_sent_issue_date, f.date);
});
test("429 pauses all sends and respects Retry-After; global pacing and daily cap", async () => {
  const f = fixture();
  f.provider = () =>
    new Response("", { status: 429, headers: { "Retry-After": "120" } });
  await f.subscribe();
  assert.equal(f.calls.length, 1);
  await f.subscribe("second@example.com");
  assert.equal(f.calls.length, 1);
  f.now += 120001;
  f.provider = null;
  await flushOutbox(f.env, f.services);
  assert.equal(f.calls.length, 3);
  assert.ok(f.calls[2].at - f.calls[1].at >= 1100);
  f.env.DAILY_EMAIL_LIMIT = "1";
  await f.subscribe("third@example.com");
  assert.equal(f.calls.length, 3);
});
test("PDF validation, size limit, mutable latest alias and reader availability", async () => {
  const f = fixture(),
    issue = await latestIssue("little-explorers", f.services);
  f.alias = "%PDF-other";
  await assert.rejects(
    issueAttachment(issue, f.services),
    /publication_in_progress/,
  );
  f.alias = null;
  f.pdf = "not PDF";
  await assert.rejects(issueAttachment(issue, f.services), /invalid_pdf/);
  f.pdf = "%PDF-" + "x".repeat(4_999_995);
  await assert.rejects(issueAttachment(issue, f.services), /asset_too_large/);
  await assert.rejects(
    bounded(new Response(new Uint8Array(10)), 10),
    /asset_too_large/,
  );
  f.stub = true;
  await assert.rejects(
    latestIssue("little-explorers", f.services),
    /reader_not_available/,
  );
  await assert.rejects(latestIssue("__proto__", f.services), /invalid_edition/);
});
test("attachment changed during ambiguous retry is held, never resent with different bytes", async () => {
  const f = fixture();
  await f.verify(await f.subscribe());
  f.date = "2026-10-26";
  f.provider = () => {
    throw Error("unknown");
  };
  await f.send();
  const count = f.calls.length;
  f.pdf = "%PDF-changed";
  f.now += 61000;
  await f.send();
  assert.equal(f.calls.length, count);
  assert.equal(
    f.env.DB.db
      .prepare("SELECT state FROM deliveries WHERE issue_date=?")
      .get(f.date).state,
    "held",
  );
});
test("asset redirects are rejected without following them or sending mail", async () => {
  const f = fixture();
  for (const suffix of ["/feed.xml", ".html", ".pdf", "/latest.pdf"]) {
    const requested = [];
    const services = {
      ...f.services,
      fetch: async (url, opts) => {
        requested.push(url);
        assert.equal(opts.redirect, "manual");
        if (url.endsWith(suffix))
          return new Response(null, {
            status: 302,
            headers: { Location: "https://untrusted.example/asset" },
          });
        return f.services.fetch(url, opts);
      },
    };
    await assert.rejects(async () => {
      const issue = await latestIssue("little-explorers", services);
      await issueAttachment(issue, services);
    }, /asset_http_302/);
    assert.ok(requested.every(url => url.startsWith("https://newspebbles.com/")));
    assert.equal(f.calls.length, 0);
  }
});

test("edition catalog has the nine existing edition slugs", () =>
  assert.equal(Object.keys(catalog).length, 9));

test("weekend welcome counts as that weekend delivery", async () => {
  const f = fixture();
  f.now = Date.parse("2026-10-31T16:00:00Z");
  await f.verify(
    await f.subscribe("p@example.com", "little-explorers", "weekly_weekend"),
  );
  f.date = "2026-10-26";
  f.now += 86400000;
  await f.send();
  assert.equal(f.calls.length, 2);
});
test("weekly subscribers already served do not starve later eligible subscribers", async () => {
  const f = fixture();
  await f.verify(
    await f.subscribe(
      "first@example.com",
      "little-explorers",
      "weekly_weekend",
    ),
  );
  f.now = Date.parse("2026-10-31T16:00:00Z");
  f.date = "2026-10-26";
  await f.send();
  await f.verify(await f.subscribe("second@example.com"));
  const count = f.calls.length;
  f.date = "2026-10-27";
  await f.send({ limit: 1 });
  assert.equal(f.calls.length, count + 1);
  assert.equal(f.calls.at(-1).body.to[0], "second@example.com");
});
test("expired send lease recovers a sending row with the same idempotency key", async () => {
  const f = fixture();
  await f.verify(await f.subscribe());
  f.date = "2026-10-26";
  const issue = await latestIssue("little-explorers", f.services);
  await queueIssue(f.env, f.sub(), issue, f.services);
  f.env.DB.db
    .prepare(
      "UPDATE deliveries SET state='sending',first_attempt_at=? WHERE issue_date=?",
    )
    .run(f.now, f.date);
  f.env.DB.db
    .prepare("UPDATE send_control SET owner='dead-worker',lease_until=?")
    .run(f.now + 60000);
  const count = f.calls.length;
  await f.send();
  assert.equal(f.calls.length, count);
  f.now += 60001;
  await f.send();
  assert.equal(f.calls.length, count + 1);
  assert.equal(f.sub().last_sent_issue_date, f.date);
});
test("429 after an uncertain send preserves the original retry deadline", async () => {
  const f = fixture();
  await f.verify(await f.subscribe());
  f.date = "2026-10-26";
  f.provider = () => {
    throw Error("unknown");
  };
  await f.send();
  const first = f.env.DB.db
    .prepare("SELECT first_attempt_at FROM deliveries WHERE issue_date=?")
    .get(f.date).first_attempt_at;
  f.now += 61000;
  f.provider = () => new Response("", { status: 429 });
  await f.send();
  assert.equal(
    f.env.DB.db
      .prepare("SELECT first_attempt_at FROM deliveries WHERE issue_date=?")
      .get(f.date).first_attempt_at,
    first,
  );
});
test("all-edition dispatch stays below free D1 query limit and caps sends at two", async () => {
  const f = fixture(),
    slugs = Object.keys(catalog);
  for (const [i, slug] of slugs.entries())
    f.env.DB.db
      .prepare(
        "INSERT INTO subscribers(id,email,edition_slug,cadence,status,unsubscribe_token,last_sent_issue_date,created_at) VALUES(?,?,?,'every_issue','active',?,?,?)",
      )
      .run(
        String(i),
        `p${i}@example.com`,
        slug,
        String(i).padStart(64, "0"),
        i === slugs.length - 1 ? null : f.date,
        i,
      );
  f.env.DB.db
    .prepare(
      "INSERT INTO subscribers(id,email,edition_slug,cadence,status,unsubscribe_token,created_at) VALUES('last','extra@example.com',?,'every_issue','active',?,99)",
    )
    .run(slugs.at(-1), "f".repeat(64));
  let queries = 0;
  const original = f.env.DB.prepare.bind(f.env.DB);
  f.env.DB.prepare = (sql) => {
    queries++;
    return original(sql);
  };
  const r = await f.send({ limit: 500 });
  assert.equal(r.delivery.sent, 2);
  assert.ok(queries < 50, `used ${queries} queries`);
});

test("resubscribe recovers an unattempted welcome but never repeats a sent paper", async () => {
  const f = fixture(),
    sub = await f.subscribe();
  f.env.DAILY_EMAIL_LIMIT = "1";
  await f.verify(sub);
  assert.equal(f.calls.length, 1);
  await f.req("/api/unsubscribe?token=" + sub.unsubscribe_token, undefined, {
    origin: null,
    method: "POST",
  });
  f.env.DAILY_EMAIL_LIMIT = "90";
  const again = await f.subscribe();
  await f.verify(again);
  assert.equal(f.calls.length, 3);
  assert.equal(f.sub().last_sent_issue_date, f.date);
  await f.req("/api/unsubscribe?token=" + again.unsubscribe_token, undefined, {
    origin: null,
    method: "POST",
  });
  f.now += 3600001;
  const third = await f.subscribe();
  await f.verify(third);
  assert.equal(f.calls.length, 4);
  assert.equal(f.calls.filter((c) => c.body.attachments).length, 1);
});
