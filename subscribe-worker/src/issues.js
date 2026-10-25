import catalog from "../editions.json" with { type: "json" };
import { SITE, PDF_LIMIT, bounded, hash, b64 } from "./common.js";
export { catalog };
async function asset(url, services) {
  return services.fetch(url, {
    headers: { "Cache-Control": "no-cache" },
    // Workers supports manual/follow only. bounded() rejects any 3xx response.
    redirect: "manual",
    signal: AbortSignal.timeout(10000),
  });
}
export async function latestIssue(slug, services) {
  if (!Object.hasOwn(catalog, slug)) throw Error("invalid_edition");
  const rss = new TextDecoder().decode(
    await bounded(await asset(`${SITE}/e/${slug}/feed.xml`, services), 250_000),
  );
  const item = /<item>([\s\S]*?)<\/item>/.exec(rss)?.[1];
  const link = /<link>([^<]+)<\/link>/.exec(item || "")?.[1]?.trim();
  const prefix = `${SITE}/e/${slug}/`;
  if (!link?.startsWith(prefix)) throw Error("no_published_issue");
  const date = link
    .slice(prefix.length)
    .match(/^(\d{4}-\d{2}-\d{2})\.pdf$/)?.[1];
  if (!date || new Date(date).toISOString().slice(0, 10) !== date)
    throw Error("invalid_issue_date");
  const reader = `${SITE}/play/${slug}/${date}.html`;
  const html = new TextDecoder().decode(
    await bounded(await asset(reader, services), 2_000_000),
  );
  if (!/<main\b[^>]*class="issue"/.test(html))
    throw Error("reader_not_available");
  return {
    ...catalog[slug],
    slug,
    date,
    pdf: link,
    latest_pdf: `${prefix}latest.pdf`,
    reader,
    cover: `${prefix}${date}.png`,
  };
}
export async function issueAttachment(
  issue,
  services,
  { retry = false, expectedHash = null } = {},
) {
  // Pin the bytes of latest.pdf to the RSS issue date. If a deployment races this
  // request, defer instead of attaching a different day's paper to the links.
  const dated = await bounded(await asset(issue.pdf, services), PDF_LIMIT);
  if (new TextDecoder().decode(dated.subarray(0, 5)) !== "%PDF-")
    throw Error("invalid_pdf");
  const digest = await hash(dated);
  if (expectedHash && digest !== expectedHash)
    throw Error("attachment_changed");
  if (!retry) {
    const current = await bounded(
      await asset(issue.latest_pdf, services),
      PDF_LIMIT,
    );
    if ((await hash(current)) !== digest)
      throw Error("publication_in_progress");
  }
  return {
    digest,
    attachment: {
      filename: `${issue.slug}-${issue.date}.pdf`,
      content: b64(dated),
    },
  };
}
