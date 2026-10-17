import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

const origin = "https://p43-admin.test";
const html = readFileSync(new URL("../public/index.html", import.meta.url), "utf8").replace(/<body([^>]*)>/,
  '<body$1><div id="mock-evidence-label" style="position:fixed;bottom:8px;left:12px;z-index:10000;padding:6px 12px;background:#fff2b0;color:#161616;font:12px monospace;pointer-events:none">MOCK UI / NO REAL ACCESS OR D1</div>');
const scope = { appId: "trace", deviceModel: "e-track-at32f435" };
function release(id: string, versionCode: number) {
  return { ...scope, releaseId: id, versionCode, versionName: `2.8.${versionCode - 20800}`,
    releaseTag: `mcu-e-track-at32f435-v2.8.${versionCode - 20800}`, state: "ready", archived: false,
    releaseNotes: "Synthetic browser fixture, not a released firmware", targetImageSha256: "b".repeat(64), publishedChannels: [] as string[],
    assets: ["full", "patch", "recovery"].map(kind => ({ assetId: `${id}-${kind}`, kind,
      fileName: `${id}-${kind}.${kind === "recovery" ? "bin" : "etu"}`, sha256: "a".repeat(64), sizeBytes: 1024,
      r2State: "available", baseImageSha256: kind === "patch" ? "c".repeat(64) : null, baseVersionCode: kind === "patch" ? 20700 : 0 })) };
}

async function mockAdmin(page: Page, language = "en", role = "owner") {
  const data = {
    role, actor: `${role}@example.test`, mode: "normal", failReads: false, expireReplay: false,
    releases: [release("fw-new", 20803), release("fw-current", 20802), release("fw-old", 20801)],
    channels: ["stable", "beta"].map((channel, index) => ({ ...scope, channel, currentReleaseId: "fw-current",
      revision: 7 + index, disableLatest: false, disableDownloads: false, maintenanceMessage: null as string | null })),
    writes: [] as Array<{ path: string; body: Record<string, unknown>; key?: string }>,
    events: [] as string[], results: new Map<string, { fingerprint: string; result: Record<string, unknown> }>(), mutations: 0
  };
  const published = () => { for (const r of data.releases) r.publishedChannels = data.channels.filter(c => c.currentReleaseId === r.releaseId).map(c => c.channel); };
  published();
  await page.addInitScript(lang => localStorage.setItem("trace-admin-language", lang), language);
  let serial = 0;
  await page.route("**/*", async route => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin !== origin) { await route.abort(); return; }
    if (url.pathname === "/") { await route.fulfill({ contentType: "text/html", body: html }); return; }
    const requestId = `mock-request-${++serial}`;
    const reply = (body: object, status = 200, id = requestId) => route.fulfill({ status,
      contentType: "application/json", headers: { "X-Request-Id": id }, body: JSON.stringify(body) });
    const fail = (errorCode: string, status: number) => reply({ errorCode, message: `Mock ${errorCode}`, requestId }, status);
    data.events.push(`${request.method()} ${url.pathname}`);
    if (request.method() === "GET") {
      if (url.pathname === "/api/admin/session") {
        await reply({ ok: true, appId: "trace", environment: "MOCK", actor: data.actor, role: data.role, csrfToken: "mock-csrf" }); return;
      }
      if (url.pathname.startsWith("/api/admin/firmware/")) {
        if (data.failReads) { await fail("BACKEND_UNAVAILABLE", 503); return; }
        expect([...url.searchParams.keys()].sort()).toEqual(["appId", "deviceModel"]);
        expect(url.searchParams.get("deviceModel")).toBe(scope.deviceModel);
        published();
        await reply(url.pathname.endsWith("/channels") ? { ok: true, requestId, firmwareChannels: data.channels }
          : { ok: true, requestId, firmwareReleases: data.releases }); return;
      }
      await reply({ ok: true, channels: [], releases: [], announcements: [], storage: null }); return;
    }
    expect(request.method()).toBe("POST");
    expect(request.headers()["accept"]).toBe("application/json");
    expect(request.headers()["content-type"]).toBe("application/json");
    expect(request.headers()["x-csrf-token"]).toBe("mock-csrf");
    const body = request.postDataJSON() as Record<string, unknown>;
    expect(typeof body.reason).toBe("string");
    expect(String(body.reason).trim()).not.toBe("");
    expect(body.appId).toBe("trace"); expect(body.deviceModel).toBe(scope.deviceModel);
    data.writes.push({ path: url.pathname, body, key: request.headers()["idempotency-key"] });
    const segments = url.pathname.split("/"); const name = segments[5]; const action = segments[6];
    if (segments[4] === "channels") {
      const channel = data.channels.find(c => c.channel === name)!;
      const pointer = action === "publish" || action === "retract";
      const keys = ["appId", "deviceModel", "expectedRevision", "reason", ...(pointer ? ["releaseId"] : []),
        ...(Object.hasOwn(body, "maintenanceMessage") ? ["maintenanceMessage"] : [])].sort();
      expect(Object.keys(body).sort()).toEqual(keys);
      if (action.startsWith("resume")) expect(body).not.toHaveProperty("maintenanceMessage");
      if (data.mode === "conflict") { channel.revision++; data.mode = "normal"; await fail("CAS_CONFLICT", 409); return; }
      if (body.expectedRevision !== channel.revision) { await fail("CAS_CONFLICT", 409); return; }
      if (pointer) channel.currentReleaseId = String(body.releaseId);
      if (action.endsWith("latest")) channel.disableLatest = action.startsWith("stop");
      if (action.endsWith("downloads")) channel.disableDownloads = action.startsWith("stop");
      if (typeof body.maintenanceMessage === "string") channel.maintenanceMessage = body.maintenanceMessage;
      if (action.startsWith("resume") && !channel.disableLatest && !channel.disableDownloads) channel.maintenanceMessage = null;
      channel.revision++; data.mutations++; published();
      if (data.mode === "unknown-channel") { data.mode = "normal"; await route.abort("failed"); return; }
      if (data.mode === "refresh-failure") data.failReads = true;
      await reply({ ok: true, requestId, action: action.replaceAll("-", "_"), channel: name,
        revision: channel.revision, currentReleaseId: channel.currentReleaseId, disableLatest: channel.disableLatest,
        disableDownloads: channel.disableDownloads, maintenanceMessage: channel.maintenanceMessage, idempotent: false }); return;
    }
    expect(segments[4]).toBe("releases");
    expect(Object.keys(body).sort()).toEqual(["appId", "deviceModel", "reason"]);
    const key = request.headers()["idempotency-key"];
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    const fingerprint = JSON.stringify({ path: url.pathname, body });
    const existing = data.results.get(key);
    if (existing) {
      if (existing.fingerprint !== fingerprint) { await fail("IDEMPOTENCY_CONFLICT", 409); return; }
      if (data.expireReplay) { await fail("IDEMPOTENCY_RESULT_EXPIRED", 409); return; }
      await reply({ ...existing.result, idempotent: true }, 200, String(existing.result.requestId)); return;
    }
    const target = data.releases.find(r => r.releaseId === name)!;
    let result: Record<string, unknown>;
    if (action === "disable") {
      if (target.publishedChannels.length) { await fail("RELEASE_IN_USE", 409); return; }
      target.state = "disabled";
      result = { ok: true, requestId, action: "disable_release", releaseId: name, state: "disabled", idempotent: false };
    } else {
      expect(action).toBe("recovery-download");
      const asset = target.assets.find(a => a.kind === "recovery")!; const expiresAt = Math.floor(Date.now() / 1000) + 300;
      const query = new URLSearchParams({ tokenVersion: "2", assetId: asset.assetId, releaseId: name,
        kind: "recovery", purpose: "admin-recovery", expiresAt: String(expiresAt), keyVersion: "mock", signature: "mock-only-not-a-real-signature" });
      result = { ok: true, requestId, action: "issue_recovery_download", releaseId: name,
        assetId: asset.assetId, kind: asset.kind, fileName: asset.fileName, sha256: asset.sha256, sizeBytes: asset.sizeBytes,
        expiresAt, downloadUrl: `https://p43-download.test/api/public/firmware/download?${query}`, idempotent: false };
    }
    data.mutations++; data.results.set(key, { fingerprint, result });
    if (data.mode === "unknown-release") { data.mode = "normal"; await route.abort("failed"); return; }
    await reply(result);
  });
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(3);
  if ((page.viewportSize()?.width ?? 1440) < 700) await page.locator("#mobileMenu").click();
  await page.locator('[data-view-target="firmware"]').click();
  return data;
}

const channelButton = (page: Page, channel: string, action: string) => page.locator(
  `.firmware-channel-card[data-channel="${channel}"] [data-firmware-action="${action}"]`);
const releaseButton = (page: Page, id: string, action: string) => page.locator(
  `.firmware-release-card[data-release-id="${id}"] [data-firmware-action="${action}"]`);
async function fillConfirmation(page: Page, reason = " browser operator reason ") {
  if (await page.locator("#confirmInput").isVisible()) await page.locator("#confirmInput").fill("stable");
  if (await page.locator("#confirmReason").isVisible()) await page.locator("#confirmReason").fill(reason);
  await expect(page.locator("#confirmAccept")).toBeEnabled();
  await page.locator("#confirmAccept").click();
}
async function closeResult(page: Page) {
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await expect(page.locator("#refreshButton")).toBeEnabled();
}

for (const language of ["en", "zh"]) {
  test(`${language}: retract boundary, reason, cancel and fresh confirmation`, async ({ page }, info) => {
    const data = await mockAdmin(page, language);
    await expect(page.locator("#firmwareView")).not.toContainText("undefined");
    await releaseButton(page, "fw-old", "select").click();
    await page.screenshot({ path: info.outputPath(`${language}-mock-overview.png`), fullPage: true });
    await channelButton(page, "stable", "retract").click();
    await expect(page.locator("#confirmDetail")).toContainText(language === "zh" ? "已升级设备不会降级" : "Upgraded devices will not downgrade");
    await expect(page.locator("#confirmDetail")).toContainText("versionCode");
    await page.locator("#confirmInput").fill("stable");
    await expect(page.locator("#confirmAccept")).toBeDisabled();
    await page.locator("#confirmReason").fill("   ");
    await expect(page.locator("#confirmAccept")).toBeDisabled();
    await page.locator("#confirmReason").fill("operator cancellation fixture");
    await page.screenshot({ path: info.outputPath(`${language}-mock-confirm.png`), fullPage: true });
    await page.locator("#confirmCancel").click();
    await expect(page.locator("#confirmDialog")).toBeHidden();
    expect(data.writes).toHaveLength(0); expect(data.mutations).toBe(0);
    await page.screenshot({ path: info.outputPath(`${language}-mock-cancel.png`), fullPage: true });
    await channelButton(page, "stable", "retract").click();
    await fillConfirmation(page);
    await expect(page.locator("#confirmTitle")).toHaveText(language === "zh" ? "固件操作已确认" : "Firmware operation confirmed");
    expect(data.writes).toHaveLength(1);
    expect(data.writes[0].body).toEqual({ ...scope, releaseId: "fw-old", expectedRevision: 7, reason: " browser operator reason " });
    await page.screenshot({ path: info.outputPath(`${language}-mock-success.png`), fullPage: true });
    await closeResult(page);
    expect(data.channels[0].currentReleaseId).toBe("fw-old");
    expect(data.releases.find(r => r.releaseId === "fw-old")!.state).toBe("ready");
  });
  test(`${language}: CAS refresh never replays an old intent`, async ({ page }, info) => {
    const data = await mockAdmin(page, language); data.mode = "conflict";
    await releaseButton(page, "fw-old", "select").click();
    await channelButton(page, "stable", "retract").click(); await fillConfirmation(page);
    await expect(page.locator("#confirmMessage")).toContainText(language === "zh" ? "再次确认" : "confirm again");
    await page.screenshot({ path: info.outputPath(`${language}-mock-conflict.png`), fullPage: true });
    expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(0);
    await closeResult(page);
    await channelButton(page, "stable", "retract").click();
    await expect(page.locator("#confirmMessage")).toContainText("8");
    await expect(page.locator("#confirmReason")).toHaveValue("");
    expect(data.writes).toHaveLength(1);
    await fillConfirmation(page, "new confirmed intent");
    await expect(page.locator("#confirmTitle")).toHaveText(language === "zh" ? "固件操作已确认" : "Firmware operation confirmed");
    expect(data.writes[1].body.expectedRevision).toBe(8); expect(data.mutations).toBe(1);
  });
}

test("beta publisher controls are independent and stable/release actions stay owner-only", async ({ page }) => {
  const data = await mockAdmin(page, "en", "publisher");
  await expect(channelButton(page, "stable", "stop-latest")).toBeDisabled();
  await expect(releaseButton(page, "fw-new", "disable")).toBeDisabled();
  await expect(releaseButton(page, "fw-new", "recovery-download")).toBeDisabled();
  await channelButton(page, "beta", "stop-downloads").click();
  await expect(page.locator("#confirmInput")).toBeHidden();
  await page.locator("#confirmMaintenance").fill("download incident"); await fillConfirmation(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed"); await closeResult(page);
  expect(data.channels[1]).toMatchObject({ disableLatest: false, disableDownloads: true });
  await channelButton(page, "beta", "resume-downloads").click();
  await expect(page.locator("#confirmMaintenance")).toBeHidden(); await fillConfirmation(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  expect(data.writes[1].body).not.toHaveProperty("maintenanceMessage");
});

test("viewer and unavailable/reference-protected releases cannot write", async ({ page }) => {
  const data = await mockAdmin(page, "en", "viewer");
  await expect(channelButton(page, "beta", "stop-downloads")).toBeDisabled();
  await expect(releaseButton(page, "fw-new", "publish").first()).toBeDisabled();
  expect(data.writes).toHaveLength(0);
  data.role = "owner"; data.actor = "owner@example.test";
  data.releases[0].state = "draft"; data.releases[2].archived = true;
  await page.locator("#refreshButton").click();
  await expect(releaseButton(page, "fw-new", "publish").first()).toBeDisabled();
  await expect(releaseButton(page, "fw-old", "disable")).toBeDisabled();
  await expect(releaseButton(page, "fw-current", "disable")).toBeDisabled();
});

test("unknown channel result is read back but never automatically repeated", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-channel";
  await channelButton(page, "beta", "stop-latest").click(); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown");
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
  expect(data.events.at(-1)).toMatch(/^GET /);
  await closeResult(page);
  await expect(channelButton(page, "beta", "resume-latest")).toBeEnabled();
  expect(data.writes).toHaveLength(1);
});

test("unknown release result uses an explicit same-key/same-body reconciliation after reads", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-release";
  await releaseButton(page, "fw-new", "recovery-download").click(); await fillConfirmation(page, "original recovery reason");
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  expect(data.writes).toHaveLength(1);
  await expect(releaseButton(page, "fw-new", "disable")).toBeDisabled();
  const eventCount = data.events.length;
  await page.locator('[data-firmware-action="retry-release"]').click();
  await expect(page.locator("#confirmDetail")).toContainText("original recovery reason");
  expect(data.events.slice(eventCount).every(event => event.startsWith("GET "))).toBe(true);
  expect(data.writes).toHaveLength(1);
  await fillConfirmation(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  expect(data.writes).toHaveLength(2);
  expect(data.writes[1]).toEqual(data.writes[0]); expect(data.mutations).toBe(1);
  await expect(page.locator("#confirmDownload")).toBeVisible();
  await expect(page.locator("#confirmDownload")).toHaveAttribute("href", /purpose=admin-recovery/);
  await closeResult(page);
  await expect(page.locator("#confirmDownload")).not.toHaveAttribute("href");
});

test("an expired original key requires a newly confirmed operation, not an automatic new key", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-release";
  await releaseButton(page, "fw-new", "recovery-download").click(); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  data.expireReplay = true;
  await page.locator('[data-firmware-action="retry-release"]').click(); await fillConfirmation(page);
  await expect(page.locator("#confirmDetail")).toContainText("IDEMPOTENCY_RESULT_EXPIRED");
  expect(data.writes).toHaveLength(2); expect(data.writes[1].key).toBe(data.writes[0].key);
  await closeResult(page); data.expireReplay = false;
  await releaseButton(page, "fw-new", "recovery-download").click();
  expect(data.writes).toHaveLength(2); await fillConfirmation(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  expect(data.writes[2].key).not.toBe(data.writes[0].key);
});

test("owner identity changes cannot replay a pending request in another actor scope", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-release";
  await releaseButton(page, "fw-new", "disable").click(); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  data.actor = "different-owner@example.test";
  await page.locator('[data-firmware-action="retry-release"]').click();
  await expect(page.locator("#firmwareNotice")).toBeVisible();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
});

test("failed state refresh keeps writes locked until a successful manual read", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "refresh-failure";
  await channelButton(page, "beta", "stop-latest").click(); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("state refresh failed"); await closeResult(page);
  await expect(channelButton(page, "beta", "stop-latest")).toBeDisabled();
  expect(data.writes).toHaveLength(1);
  data.failReads = false;
  await page.locator('[data-firmware-action="refresh"]').click();
  await expect(channelButton(page, "beta", "resume-latest")).toBeEnabled();
  expect(data.writes).toHaveLength(1);
});

test("mobile firmware controls and confirmation fit the viewport", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockAdmin(page, "zh");
  await releaseButton(page, "fw-old", "select").click();
  await channelButton(page, "stable", "retract").click();
  await expect(page.locator("#confirmReason")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("zh-mobile-mock-confirm.png"), fullPage: true });
});
