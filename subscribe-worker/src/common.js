export const SITE = "https://newspebbles.com";
export const PDF_LIMIT = 5_000_000; // Strictly less than 5 MB, before base64 encoding.
export const ALLOWED_ORIGINS = new Set([SITE, "http://localhost"]);
export const esc = (value) =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export const token = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(32)), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
export async function hash(value) {
  const bytes =
    typeof value === "string" ? new TextEncoder().encode(value) : value;
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    (b) => b.toString(16).padStart(2, "0"),
  ).join("");
}
export function constantEqual(a, b) {
  const x = new TextEncoder().encode(a),
    y = new TextEncoder().encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++)
    diff |= (x[i] || 0) ^ (y[i] || 0);
  return diff === 0;
}
export function baseURL(env) {
  const u = new URL(env.PUBLIC_BASE_URL);
  if (
    u.protocol !== "https:" ||
    u.username ||
    u.password ||
    u.pathname !== "/" ||
    u.search ||
    u.hash ||
    u.hostname.startsWith("replace-")
  )
    throw Error("worker_not_configured");
  return u.origin;
}
export function enabled(env) {
  return (
    env.DELIVERY_ENABLED === "true" &&
    !!env.RESEND_API_KEY &&
    !!env.DISPATCH_SECRET
  );
}
export async function bounded(response, limit) {
  if (!response.ok) throw Error("asset_http_" + response.status);
  const declared = Number(response.headers.get("content-length"));
  if (declared >= limit) {
    await response.body?.cancel();
    throw Error("asset_too_large");
  }
  const reader = response.body?.getReader();
  if (!reader) throw Error("asset_empty");
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size >= limit) throw Error("asset_too_large");
      chunks.push(value);
    }
  } catch (e) {
    await reader.cancel();
    throw e;
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}
export const b64 = (bytes) => {
  if (typeof bytes.toBase64 === "function") return bytes.toBase64();
  const parts = [];
  for (let i = 0; i < bytes.length; i += 16384)
    parts.push(String.fromCharCode(...bytes.subarray(i, i + 16384)));
  return btoa(parts.join(""));
};
export function safeError(error) {
  return /^[a-z0-9_]+$/.test(error?.message || "")
    ? error.message
    : "temporary_failure";
}
export function defaults(overrides = {}) {
  return {
    fetch: (...args) => fetch(...args),
    now: () => Date.now(),
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
    ...overrides,
  };
}
