import assert from "node:assert/strict";
import { test } from "node:test";
import worker from "../../Tools/ota/p51-acceptance/public/site/_worker.js";

const origin = "https://e-track-p51-benchmark.pages.dev";
const upstream = "https://fixed-upstream.trycloudflare.com";
const env = { P51_UPSTREAM_ORIGIN: upstream };
const latest = "/api/public/firmware/latest";
const download = "/api/public/firmware/download";

test("only the two exact GET routes reach the configured upstream", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response("body"));
  for (const path of [latest, download]) {
    assert.equal((await worker.fetch(new Request(origin + path), env)).status, 200);
    assert.equal(fetch.mock.calls.at(-1).arguments[0].url, upstream + path);
  }
  for (const path of ["/", "/healthz", "/api/public/latest", latest + "/", download + "/x", "/api%2fpublic/firmware/latest"]) {
    const response = await worker.fetch(new Request(origin + path), env);
    assert.equal(response.status, 404);
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
  for (const method of ["HEAD", "POST", "PUT", "DELETE", "OPTIONS"]) {
    assert.equal((await worker.fetch(new Request(origin + latest, { method }), env)).status, 404);
  }
  assert.equal(fetch.mock.callCount(), 2);
});

test("unbound, non-HTTPS and non-exact upstreams never reach fetch", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", () => { throw new Error("must not fetch"); });
  for (const value of [undefined, null, 42, "", "http://fixed-upstream.trycloudflare.com",
    upstream + "/", upstream + "?x=1", upstream + "#fragment", upstream + "\n",
    upstream + ":443", "https://user@fixed-upstream.trycloudflare.com",
    "https://fixed-upstream.trycloudflare.com.other.test", "https://127.0.0.1",
    "https://-invalid.trycloudflare.com", "https://invalid-.trycloudflare.com"]) {
    const response = await worker.fetch(new Request(origin + latest), { P51_UPSTREAM_ORIGIN: value });
    assert.equal(response.status, 503, String(value));
    assert.equal(response.headers.get("cache-control"), "no-store");
  }
  assert.equal(fetch.mock.callCount(), 0);
});

test("raw duplicate/signed query, Range and If-Range survive without cookies", async (t) => {
  const query = "?asset=x&asset=y&sig=A%2fb%2B%3D&space=one+two&empty=&dest=https%3A%2F%2Fother.test";
  const fetch = t.mock.method(globalThis, "fetch", async () => new Response("partial", { status: 206 }));
  const response = await worker.fetch(new Request(origin + download + query, {
    headers: { Range: "bytes=40-91", "If-Range": '"etag"', Accept: "application/octet-stream",
      Cookie: "private-browser-cookie", Authorization: "private-browser-authorization" }
  }), env);
  assert.equal(response.status, 206);
  const forwarded = fetch.mock.calls[0].arguments[0];
  assert.equal(forwarded.url, upstream + download + query);
  assert.equal(forwarded.redirect, "manual");
  assert.equal(forwarded.headers.get("range"), "bytes=40-91");
  assert.equal(forwarded.headers.get("if-range"), '"etag"');
  assert.equal(forwarded.headers.get("accept"), "application/octet-stream");
  assert.equal(forwarded.headers.get("cookie"), null);
  assert.equal(forwarded.headers.get("authorization"), null);
  assert.equal(fetch.mock.callCount(), 1);
});

for (const status of [200, 206, 400, 401, 409, 410, 416, 429, 503]) {
  test(`upstream ${status} status, headers and unread stream pass through unchanged`, async (t) => {
    const original = new Response("upstream original bytes", { status, headers: {
      "Content-Type": "application/octet-stream", "ETag": '"package-hash"',
      "Content-Range": "bytes 40-91/1048576", "Retry-After": "60", "Cache-Control": "no-store"
    } });
    t.mock.method(globalThis, "fetch", async () => original);
    const response = await worker.fetch(new Request(origin + download), env);
    assert.equal(response, original);
    assert.equal(original.bodyUsed, false);
    assert.equal(await response.text(), "upstream original bytes");
  });
}

for (const status of [301, 302, 307, 308]) {
  test(`upstream ${status} is rejected without following or leaking Location`, async (t) => {
    const original = new Response("do not forward", {
      status, headers: { Location: "https://other.test/private?signature=secret" }
    });
    const fetch = t.mock.method(globalThis, "fetch", async () => original);
    const response = await worker.fetch(new Request(origin + download), env);
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("location"), null);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal((await response.text()).includes("secret"), false);
    assert.equal(fetch.mock.callCount(), 1);
    assert.equal(original.bodyUsed, true);
  });
}

test("a connection exception remains a sanitized failure without retry or logging", async (t) => {
  const fetch = t.mock.method(globalThis, "fetch", async () => {
    throw new Error("private upstream address and signed token");
  });
  const log = t.mock.method(console, "error", () => {});
  const response = await worker.fetch(new Request(origin + download), env);
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), {
    errorCode: "BACKEND_UNAVAILABLE", message: "Benchmark firmware service unavailable"
  });
  assert.equal(fetch.mock.callCount(), 1);
  assert.equal(log.mock.callCount(), 0);
});
