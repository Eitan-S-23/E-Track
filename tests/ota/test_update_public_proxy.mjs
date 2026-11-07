import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../../app/bluetooth_flutter_Trace/cloudflare/update-service/firmware-public/site/_worker.js', import.meta.url));
const { default: worker } = await import('data:text/javascript;base64,' + source.toString('base64'));

for (const pathname of ['/healthz', '/api/public/latest', '/api/public/download',
  '/api/public/github-fallback', '/api/public/announcements',
  '/api/public/firmware/latest', '/api/public/firmware/download']) {
  test(`forwards ${pathname} without changing the public origin or response`, async () => {
    const request = new Request('https://public.example.invalid' + pathname + '?opaque=fixture');
    const response = new Response(new Uint8Array([0, 1, 255]), { headers: { 'x-source': 'fixture' } });
    let calls = 0;
    const result = await worker.fetch(request, { FIRMWARE_SERVICE: { fetch(actual) {
      calls += 1;
      assert.equal(actual, request);
      return response;
    } } });
    assert.equal(calls, 1);
    assert.equal(result, response);
    assert.equal(result.headers.get('x-source'), 'fixture');
    assert.deepEqual(new Uint8Array(await result.arrayBuffer()), new Uint8Array([0, 1, 255]));
  });
}

for (const [method, pathname] of [['POST', '/api/public/latest'], ['POST', '/api/ci/releases'],
  ['GET', '/api/admin/session'], ['GET', '/api/ci/releases'], ['GET', '/api/public/unknown'],
  ['GET', '/api/public/latest/']]) {
  test(`rejects ${method} ${pathname} without forwarding`, async () => {
    let calls = 0;
    const result = await worker.fetch(new Request('https://public.example.invalid' + pathname, { method }),
      { FIRMWARE_SERVICE: { fetch() { calls += 1; throw new Error('must not forward'); } } });
    assert.equal(result.status, 404);
    assert.equal(calls, 0);
  });
}

test('retains the non-cacheable upstream error response', async () => {
  const original = console.error;
  const diagnostics = [];
  console.error = (message) => diagnostics.push(message);
  try {
    const result = await worker.fetch(new Request('https://public.example.invalid/healthz'),
      { FIRMWARE_SERVICE: { fetch() { throw new Error('fixture'); } } });
    assert.equal(result.status, 503);
    assert.equal(result.headers.get('cache-control'), 'no-store');
    assert.deepEqual(diagnostics, ['FIRMWARE_PUBLIC_UPSTREAM_UNAVAILABLE']);
  } finally {
    console.error = original;
  }
});
