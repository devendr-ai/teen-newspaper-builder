// Only the two explicitly parent-approved actions use native networking. Never a general fetch proxy.
const API = 'https://newspebbles-subscribe.devendr.workers.dev/api/';
const SITE = 'https://newspebbles.com';
type Result = { t: 'parent-result'; id: string; status?: number; data?: unknown; error?: boolean };

export async function parentRequest(
  message: unknown, source: string, root: string, request: typeof fetch = fetch,
): Promise<Result> {
  const m = message as { id?: unknown; url?: unknown; body?: unknown };
  const id = typeof m?.id === 'string' && /^[a-z0-9-]{1,100}$/.test(m.id) ? m.id : '';
  const failed: Result = { t: 'parent-result', id, error: true };
  if (!id || typeof m.url !== 'string' || !m.body || typeof m.body !== 'object' || Array.isArray(m.body)) return failed;
  let page: string;
  try {
    const u = new URL(source), base = new URL(root.endsWith('/') ? root : root + '/');
    if (u.protocol !== 'file:' || u.host !== base.host || !u.pathname.startsWith(base.pathname)) return failed;
    page = u.pathname.slice(base.pathname.length);
  } catch { return failed; }
  const body = m.body as Record<string, unknown>;
  if (JSON.stringify(body).length > 2048) return failed;
  if (m.url === API + 'subscribe') {
    if (!/^(?:parents\.html|e\/[a-z0-9-]+\/index\.html)$/.test(page)) return failed;
    if (Object.keys(body).sort().join(',') !== 'cadence,edition_slug,email,website' ||
        typeof body.email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(body.email) || body.email.length > 254 ||
        typeof body.edition_slug !== 'string' || !/^[a-z0-9-]{1,80}$/.test(body.edition_slug) ||
        !['every_issue', 'weekly_weekend'].includes(String(body.cadence)) ||
        typeof body.website !== 'string') return failed;
  } else if (m.url === API + 'polls/vote') {
    if (!/^play\/[a-z0-9-]+\/\d{4}-\d{2}-\d{2}\.html$/.test(page)) return failed;
    if (Object.keys(body).sort().join(',') !== 'choice,poll_id,receipt' ||
        typeof body.poll_id !== 'string' || !/^[a-z0-9-]+:\d{4}-\d{2}-\d{2}:[a-f0-9]{24}$/.test(body.poll_id) ||
        (body.choice !== 0 && body.choice !== 1) ||
        typeof body.receipt !== 'string' || !/^[a-f0-9]{64}$/.test(body.receipt)) return failed;
  } else return failed;
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 20000);
  try {
    // CORS governs browser origins, not native clients. Keep the Worker's strict browser allowlist;
    // the native client identifies the same first-party service. This is not an authentication secret.
    const response = await request(m.url, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Origin: SITE },
      body: JSON.stringify(body), credentials: 'omit', redirect: 'error', signal: controller.signal,
    });
    const text = await response.text();
    if (text.length > 8192) return failed;
    return { t: 'parent-result', id, status: response.status, data: JSON.parse(text) };
  } catch { return failed; }
  finally { clearTimeout(timer); }
}
