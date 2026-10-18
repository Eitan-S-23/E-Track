import assert from "node:assert/strict";
import { readFileSync, realpathSync } from "node:fs";
import path from "node:path";
import { before, after, test } from "node:test";
import { fileURLToPath } from "node:url";

assert.equal(process.platform, "linux", "Run this native bundle smoke check in the approved Linux CI, not Windows workerd");
assert.ok(process.env.P43_ADMIN_BUNDLE_DIR, "A checked bundle directory is required");
const root = realpathSync(fileURLToPath(new URL("../../../../../", import.meta.url)));
const bundle = realpathSync(process.env.P43_ADMIN_BUNDLE_DIR);
function contained(file) {
  const actual = realpathSync(file);
  const relative = path.relative(root, actual);
  assert.ok(relative !== ".." && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative), "Bundle path escapes the worktree");
  return actual;
}
const entry = contained(path.join(bundle, "public/_worker.js/index.js"));
const html = readFileSync(contained(path.join(bundle, "public/index.html")), "utf8");
const sourceHtml = readFileSync(new URL("./public/index.html", import.meta.url), "utf8");
let runtime;
before(async () => {
  const { Miniflare, Response } = await import("miniflare");
  runtime = new Miniflare({
    modules: true,
    scriptPath: entry,
    // The compiled artifact is outside the package cwd; module names cannot start with "..".
    modulesRoot: path.dirname(entry),
    compatibilityDate: "2026-06-28",
    compatibilityFlags: ["nodejs_compat"],
    bindings: {
      ENVIRONMENT: "staging",
      APP_ID: "trace",
      ACCESS_JWT_ISSUER: "https://bundle-smoke.cloudflareaccess.com",
      ACCESS_JWT_AUD: "bundle-smoke-audience",
      ADMIN_OWNER_EMAILS: "owner@example.test"
    },
    serviceBindings: { ASSETS: () => new Response(html, { headers: { "Content-Type": "text/html" } }) },
    outboundService: () => new Response("Outbound disabled in bundle smoke", { status: 503 })
  });
  await runtime.ready;
});
after(async () => { await runtime?.dispose(); });

test("compiled Pages router preserves the exact static UI through ASSETS", async () => {
  assert.equal(html, sourceHtml);
  const response = await runtime.dispatchFetch("https://bundle-smoke.test/");
  assert.equal(response.status, 200);
  assert.equal(await response.text(), sourceHtml);
});

for (const method of ["GET", "POST"]) {
  test(`compiled ${method} Admin route rejects an absent Access assertion before data access`, async () => {
    const route = method === "GET" ? "/api/admin/session" : "/api/admin/firmware/channels/stable/retract";
    const response = await runtime.dispatchFetch(`https://bundle-smoke.test${route}`, {
      method, headers: { Accept: "application/json", "Content-Type": "application/json" }
    });
    assert.equal(response.status, 401);
    const body = await response.json();
    assert.equal(body.errorCode, "TOKEN_INVALID");
    assert.equal(typeof body.requestId, "string");
    assert.equal(response.headers.get("X-Request-Id"), body.requestId);
  });
}
