import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import worker from "../site/_worker.js";

const origin = "https://e-track-firmware-p41-public.pages.dev";

for (const path of ["/healthz", "/api/public/firmware/latest", "/api/public/firmware/download"]) {
  test(`forwards GET ${path} without changing the public origin or request`, async () => {
    const request = new Request(`${origin}${path}?token=opaque&x=1&x=2`, {
      headers: { "CF-Connecting-IP": "192.0.2.1", Range: "bytes=0-15" }
    });
    const response = new Response("upstream", { headers: { "X-Request-Id": "original" } });
    let calls = 0;
    const result = await worker.fetch(request, { FIRMWARE_SERVICE: { fetch: async (input) => {
      calls++;
      assert.equal(input, request);
      assert.equal(input.url, request.url);
      return response;
    } } });
    assert.equal(calls, 1);
    assert.equal(result, response);
  });
}

for (const [method, path] of [
  ["POST", "/api/ci/firmware/releases"], ["POST", "/api/ci/firmware/preflight"],
  ["GET", "/api/admin/firmware"], ["GET", "/api/public/latest"],
  ["GET", "/api/public/firmware/latest/extra"], ["GET", "/api/public/firmware/%6catest"],
  ["GET", "//api/public/firmware/latest"], ["POST", "/api/public/firmware/latest"],
  ["HEAD", "/healthz"], ["OPTIONS", "/api/public/firmware/latest"]
]) {
  test(`rejects ${method} ${path} before calling the service`, async () => {
    const result = await worker.fetch(new Request(origin + path, { method }), {
      FIRMWARE_SERVICE: { fetch: () => assert.fail("private route reached upstream") }
    });
    assert.equal(result.status, 404);
    assert.equal((await result.json()).errorCode, "NOT_FOUND");
  });
}

test("preserves upstream errors, rate-limit headers and download streams", async () => {
  for (const status of [200, 206, 401, 409, 429, 503]) {
    const stream = new ReadableStream({ start(controller) {
      controller.enqueue(new Uint8Array([0, 255, 1]));
      controller.close();
    } });
    const response = new Response(stream, { status, headers: { "Retry-After": "60" } });
    const result = await worker.fetch(new Request(origin + "/api/public/firmware/download"), {
      FIRMWARE_SERVICE: { fetch: async () => response }
    });
    assert.equal(result, response);
    assert.equal(result.body, stream);
    assert.equal(result.status, status);
    assert.equal(result.headers.get("Retry-After"), "60");
    assert.deepEqual(new Uint8Array(await result.arrayBuffer()), new Uint8Array([0, 255, 1]));
  }
});

test("upstream rejection is a sanitized non-cacheable failure, not a healthy response", async () => {
  const result = await worker.fetch(new Request(origin + "/healthz"), {
    FIRMWARE_SERVICE: { fetch: async () => { throw new Error("private backend details"); } }
  });
  assert.equal(result.status, 503);
  assert.equal(result.headers.get("Cache-Control"), "no-store");
  assert.deepEqual(await result.json(), {
    errorCode: "BACKEND_UNAVAILABLE", message: "Firmware service unavailable"
  });
});

test("the isolated public project binds only the existing firmware test service", () => {
  const config = JSON.parse(readFileSync(new URL("../wrangler.jsonc", import.meta.url), "utf8"));
  assert.equal(config.name, "e-track-firmware-p41-public");
  assert.equal(config.pages_build_output_dir, "./site");
  assert.deepEqual(config.services, [{ binding: "FIRMWARE_SERVICE", service: "e-track-firmware-p41-test" }]);
  for (const key of ["d1_databases", "r2_buckets", "kv_namespaces", "vars"]) {
    assert.equal(config[key], undefined);
  }
});
