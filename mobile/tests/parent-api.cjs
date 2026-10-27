// Run without a simulator: the actual native request handler, with a recording HTTP stand-in.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const context = { exports: {}, URL, AbortController, setTimeout, clearTimeout, fetch };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(require.resolve('../src/parent-api.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText, context);
const { parentRequest } = context.exports;
const root = 'file:///sandbox/site/';
const base = 'https://newspebbles-subscribe.devendr.workers.dev/api/';
const signup = { id: 'test-1', url: base + 'subscribe', body: {
  email: 'parent@example.com', edition_slug: 'little-explorers', cadence: 'every_issue', website: '',
} };
(async () => {
  const calls = [];
  const request = async (url, options) => { calls.push({ url, ...options }); return { status: 200, text: async () => '{"ok":true}' }; };
  const run = (m, page = root + 'parents.html') => parentRequest(m, page, root, request);
  assert.equal((await run(signup)).status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].headers.Origin, 'https://newspebbles.com');
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].credentials, 'omit');
  assert.equal(calls[0].redirect, 'error');
  assert.deepEqual(JSON.parse(calls[0].body), signup.body);
  assert.equal((await run(signup, root + 'e/little-explorers/index.html')).status, 200);
  const poll = { id: 'test-2', url: base + 'polls/vote', body: {
    poll_id: 'global-citizen-plus:2026-10-26:' + 'a'.repeat(24), choice: 1, receipt: 'b'.repeat(64),
  } };
  assert.equal((await run(poll, root + 'play/global-citizen-plus/2026-10-26.html')).status, 200);
  const before = calls.length;
  for (const [m, page] of [
    [{ ...signup, url: 'https://evil.example/api/subscribe' }],
    [{ ...signup, url: base + 'dispatch' }],
    [{ ...signup, url: base + 'subscribe?x=1' }],
    [{ ...signup, body: { ...signup.body, secret: 'extra' } }],
    [{ ...signup, body: { ...signup.body, cadence: 'bad' } }],
    [{ ...signup, body: { ...signup.body, email: 'bad' } }],
    [{ ...signup, body: { ...signup.body, website: 'x'.repeat(3000) } }],
    [signup, 'https://newspebbles.com/parents.html'],
    [signup, 'file:///sandbox/other/parents.html'],
    [signup, root + '../parents.html'],
    [signup, root + 'play/index.html'],
    [poll, root + 'parents.html'],
    [{ ...poll, body: { ...poll.body, choice: 2 } }, root + 'play/global-citizen-plus/2026-10-26.html'],
  ]) assert.equal((await run(m, page)).error, true);
  assert.equal(calls.length, before, 'invalid messages must never reach the network');
  const offline = await parentRequest(signup, root + 'parents.html', root, async () => { throw Error('offline'); });
  assert.equal(offline.error, true);
  const limited = await parentRequest(signup, root + 'parents.html', root, async () => ({ status: 429, text: async () => '{"error":"rate_limited"}' }));
  assert.equal(limited.status, 429);
  console.log('Native parent API: valid signup/poll, origin, source/path/payload restrictions, offline and HTTP errors passed.');
})().catch(e => { console.error(e); process.exitCode = 1; });
