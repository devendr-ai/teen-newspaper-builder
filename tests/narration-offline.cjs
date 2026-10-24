const assert = require('node:assert/strict');
const vm = require('node:vm');
let source = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', c => source += c);
process.stdin.on('end', async () => {
  const events = {};
  let cached = true, network = 0;
  const ctx = {
    URL, Response, location: new URL('https://example.test/paper/play/sw.js'),
    self: {addEventListener(k, fn) { events[k] = fn; }},
    caches: {match: async () => cached ? new Response(new Uint8Array([10,20,30,40,50])) : undefined},
    fetch: async () => { network++; return new Response('network'); }
  };
  vm.runInNewContext(source, ctx);
  async function request(range) {
    let result;
    events.fetch({request: new Request('https://example.test/paper/play/audio/story.mp3', {headers:{Range:range}}),
      respondWith(promise) { result = promise; }});
    return result;
  }
  const response = await request('bytes=1-3');
  assert.equal(response.status, 206);
  assert.equal(response.headers.get('content-range'), 'bytes 1-3/5');
  assert.deepEqual([...new Uint8Array(await response.arrayBuffer())], [20,30,40]);
  assert.equal((await request('bytes=9-')).status, 416);
  cached = false;
  assert.equal(await (await request('bytes=1-')).text(), 'network');
  assert.equal(network, 1);
  console.log('Offline narration: cached byte ranges and network fallback passed');
});
