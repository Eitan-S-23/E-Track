import { env } from "cloudflare:workers";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { onRequest } from "../../public/functions/[[path]]";

const enabled = { ...env, VERSION_INVENTORY_ENABLED: "true" };

function page(path: string, init: RequestInit = {}, asset = new Response("site asset")) {
  const next = vi.fn(async () => asset);
  const response = onRequest({
    request: new Request(`https://public.example.com${path}`, init), env: { ...enabled, ASSETS: { fetch: next } },
    params: {}, data: {}, functionPath: "/", next, waitUntil() {}, passThroughOnException() {}
  } as Parameters<typeof onRequest>[0]);
  return { response, next };
}

beforeEach(async () => {
  await env.DB.batch([
    env.DB.prepare("DELETE FROM version_inventory_installations"),
    env.DB.prepare("DELETE FROM version_inventory_budget"),
    env.DB.prepare("UPDATE version_inventory_control SET refresh_id='initial',requested_at=0,daily_limit=5000 WHERE id=1")
  ]);
});

describe("public Pages static and API boundary", () => {
  const paths = ["/", "/index.html", "/favicon.ico", "/favicon.png", "/favicon.svg"];
  it.each(paths)("serves the actual static asset for GET %s with a version query", async path => {
    const asset = new Response("unchanged asset bytes", { headers: { "Content-Type": "image/png", ETag: "asset-etag" } });
    const result = page(`${path}?v=20261114`, {}, asset);
    const response = await result.response;
    expect(result.next).toHaveBeenCalledExactlyOnceWith();
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("image/png");
    expect(response.headers.get("ETag")).toBe("asset-etag");
    expect(await response.text()).toBe("unchanged asset bytes");
  });

  it.each(paths)("preserves an empty HEAD response for %s", async path => {
    const result = page(path, { method: "HEAD" }, new Response(null, { headers: { "Content-Length": "123" } }));
    const response = await result.response;
    expect(result.next).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Length")).toBe("123");
    expect(await response.text()).toBe("");
  });

  it.each(["/api/admin/session", "/api/ci/releases", "/api/public/missing", "/missing", "/favicon.ico/extra"])(
    "keeps %s a JSON 404 rather than exposing the static fallback", async path => {
      const result = page(path);
      const response = await result.response;
      expect(response.status).toBe(404);
      expect(await response.json()).toMatchObject({ errorCode: "INVALID_PARAMETER" });
      expect(result.next).not.toHaveBeenCalled();
    });

  it.each(paths)("does not hand POST %s to static assets", async path => {
    const result = page(path, { method: "POST" });
    expect((await result.response).status).toBe(404);
    expect(result.next).not.toHaveBeenCalled();
  });

  it("keeps health and inventory control on their existing API handlers", async () => {
    for (const path of ["/healthz", "/api/public/version-inventory/control?appId=trace"]) {
      const result = page(path, { headers: { "CF-Connecting-IP": crypto.randomUUID() } });
      const response = await result.response;
      expect(response.status).toBe(200);
      expect(await response.json()).toMatchObject({ ok: true });
      expect(result.next).not.toHaveBeenCalled();
    }
  });

  it("exposes the shared duplicate acknowledgement through the actual public router", async () => {
    const payload = { appId: "trace", platform: "android", sequence: 1, versionCode: 100,
      versionName: "1.0.74", imageSha256: "b".repeat(64), devices: [] };
    const send = (sequence: number) => page("/api/public/version-inventory", {
      method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${"a".repeat(64)}`,
        "CF-Connecting-IP": crypto.randomUUID() }, body: JSON.stringify({ ...payload, sequence })
    });
    const first = send(1);
    const firstResponse = await first.response;
    expect(firstResponse.status).toBe(200);
    const receipt = await firstResponse.json<{ reportedAt: number }>();
    expect(receipt).toMatchObject({ accepted: true, acknowledged: true, sequence: 1 });
    const duplicate = send(2);
    const response = await duplicate.response;
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ accepted: false, acknowledged: true,
      reportedAt: receipt.reportedAt, sequence: 1, refreshId: "initial" });
    expect(first.next).not.toHaveBeenCalled();
    expect(duplicate.next).not.toHaveBeenCalled();
  });
});
