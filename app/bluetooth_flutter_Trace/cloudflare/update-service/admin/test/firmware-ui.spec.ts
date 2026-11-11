import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

const css = readFileSync(new URL("../public/admin.css", import.meta.url), "utf8");
const origin = "https://p43-admin.test";
const html = readFileSync(new URL("../public/index.html", import.meta.url), "utf8").replace(/<body([^>]*)>/,
  '<body$1><div id="mock-evidence-label" style="position:fixed;bottom:8px;left:12px;z-index:10000;padding:6px 12px;background:#fff2b0;color:#161616;font:12px monospace;pointer-events:none">MOCK UI / NO REAL ACCESS OR D1</div>');
const scope = { appId: "trace", deviceModel: "e-track-at32f435" };
function manyFirmware(count: number) {
  return Array.from({ length: count }, (_, index) => ({
    ...release("many-" + index, 40000 + index), createdAt: "2026-11-11 10:00:00"
  }));
}
async function refreshMcu(page: Page) {
  await page.locator("#refreshButton").click();
  await expect(page.locator("#refreshButton")).toBeEnabled();
}

for (const language of ["en", "zh"]) for (const width of [1440, 390]) {
  test("mcu interaction " + language + " " + width + "px bounds hundreds of versions and keeps peer navigation visible", async ({ page }, info) => {
    await page.setViewportSize({ width, height: 800 });
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    const data = await mockAdmin(page, language);
    data.channels.forEach(channel => { channel.currentReleaseId = null; });
    data.releases = manyFirmware(60);
    data.history = Array.from({ length: 20 }, (_, index) => ({
      id: "mcu-history-" + index, action: "edit_notes", actor: "owner@example.test",
      createdAt: "2026-11-11 10:00:00", releaseId: "many-59", releaseTag: "MCU candidate",
      reason: "Recorded operation " + index, requestId: "mock-history-" + index, before: {}, after: {}
    }));
    await refreshMcu(page);
    await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(6);
    const height60 = await page.evaluate(() => document.documentElement.scrollHeight);
    data.releases = manyFirmware(600);
    await refreshMcu(page);
    await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(6);
    await expect(page.locator("#firmwarePageStatus")).toContainText("600");
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(height60 + 8);
    expect((await page.locator("#firmwareReleaseList").boundingBox())!.height).toBeLessThanOrEqual(width <= 720 ? 330 : 440);
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect.poll(async () => Math.abs((await page.locator(".topbar").boundingBox())!.y)).toBeLessThan(1);
    await expect.poll(async () => {
      const toolbar = (await page.locator(".topbar").boundingBox())!;
      return Math.abs((await page.locator("#firmwareTabs").boundingBox())!.y - toolbar.y - toolbar.height);
    }).toBeLessThan(1);
    for (const id of ["searchInput", "languageToggle", "refreshButton", "firmwareVersionsTab", "firmwareChannelsTab", "firmwareHistoryTab"]) {
      await expect(page.locator("#" + id)).toBeInViewport();
    }
    await page.screenshot({ path: info.outputPath("mcu-paged-sticky-mock.png"), animations: "disabled" });
    await firmwareTab(page, "channels");
    await expect(page.locator("#firmwareVersionsPanel")).toBeHidden();
    await expect(page.locator("#firmwareChannelsPanel")).toBeVisible();
    await expect(page.locator("#firmwareChannelList .firmware-channel-card")).toHaveCount(2);
    await page.screenshot({ path: info.outputPath("mcu-channels-peer-mock.png"), animations: "disabled" });
    await firmwareTab(page, "history");
    await expect(page.locator("#firmwareChannelsPanel")).toBeHidden();
    await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(20);
    expect((await page.locator("#firmwareHistoryList").boundingBox())!.height).toBeLessThanOrEqual(640);
    await page.screenshot({ path: info.outputPath("mcu-history-peer-mock.png"), animations: "disabled" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    expect(data.writes).toHaveLength(0);
  });
}

test("mcu interaction pagination, keyboard and filters keep selection on the displayed page", async ({ page }) => {
  const data = await mockAdmin(page);
  data.releases = manyFirmware(14);
  data.channels.forEach(channel => { channel.currentReleaseId = null; });
  data.releases[0].state = "disabled";
  await refreshMcu(page);
  const rows = page.locator("#firmwareReleaseList .firmware-release-card");
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-13");
  await expect(page.locator("#firmwarePagePrev")).toBeDisabled();
  await releaseButton(page, "many-8", "select").focus();
  await page.keyboard.press("ArrowDown");
  await expect(releaseButton(page, "many-7", "select")).toBeFocused();
  await expect(page.locator("#firmwareDetail")).toHaveAttribute("data-release-id", "many-7");
  await expect(page.locator("#firmwarePageStatus")).toContainText("7-12");
  await page.keyboard.press("ArrowUp");
  await expect(releaseButton(page, "many-8", "select")).toBeFocused();
  await page.locator("#firmwarePageNext").click();
  await page.locator("#firmwarePageNext").click();
  await expect(rows).toHaveCount(2);
  await expect(page.locator("#firmwarePageNext")).toBeDisabled();
  await page.locator("#searchInput").fill("many-7-patch");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-7");
  await expect(page.locator("#firmwarePagination")).toBeHidden();
  await page.locator('[data-firmware-action="clear-filters"]').click();
  await page.locator("#firmwareSort").selectOption("version-asc");
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-0");
  await page.locator("#firmwareStatusFilter").selectOption("disabled");
  await expect(rows).toHaveCount(1);
  await expect(page.locator("#firmwareDetail")).toHaveAttribute("data-release-id", "many-0");
  expect(data.writes).toHaveLength(0);
});

test("mcu interaction tabs preserve draft and target while searches remain independent", async ({ page }) => {
  const data = await mockAdmin(page);
  data.history = [{ id: "history-note", action: "edit_notes", actor: "owner@example.test",
    createdAt: "2026-11-11 10:00:00", releaseId: "fw-new", releaseTag: data.releases[0].releaseTag,
    reason: "Reviewed reason", requestId: "history-note-request", before: {}, after: {} }];
  expect(data.events.some(event => event.endsWith("/history"))).toBe(false);
  await page.locator("#searchInput").fill("fw-new-patch");
  await page.locator('[data-firmware-action="notes-edit"]').click();
  await page.locator("#firmwareNotesEditor").fill("Unsaved MCU notes");
  await page.locator("#firmwareVersionsTab").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#firmwareChannelsTab")).toBeFocused();
  await expect(page.locator("#searchInput")).toHaveValue("");
  await expect(page.locator("#firmwareChannelTarget")).toContainText(data.releases[0].releaseTag);
  await page.locator("#searchInput").fill("stable");
  await expect(page.locator("#firmwareChannelList .firmware-channel-card")).toHaveCount(1);
  await expect(page.locator("#firmwareChannelTarget")).toContainText(data.releases[0].releaseTag);
  await page.locator("#firmwareChannelsTab").focus();
  await page.keyboard.press("End");
  await expect(page.locator("#firmwareHistoryTab")).toBeFocused();
  await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(1);
  await expect(page.locator("#searchInput")).toHaveValue("");
  await page.locator("#searchInput").fill("not-present");
  await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(0);
  await page.locator("#searchInput").fill("Reviewed reason");
  await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(1);
  await page.locator("#languageToggle").click();
  await expect(page.locator("#searchInput")).toHaveValue("Reviewed reason");
  await page.locator("#firmwareHistoryTab").focus();
  await page.keyboard.press("Home");
  await expect(page.locator("#firmwareVersionsTab")).toBeFocused();
  await expect(page.locator("#searchInput")).toHaveValue("fw-new-patch");
  await expect(page.locator("#firmwareNotesEditor")).toHaveValue("Unsaved MCU notes");
  await firmwareTab(page, "channels");
  await expect(page.locator("#searchInput")).toHaveValue("stable");
  await page.locator('[data-firmware-action="choose-version"]').click();
  await expect(page.locator("#firmwareVersionsPanel")).toBeVisible();
  await expect(page.locator("#firmwareNotesEditor")).toHaveValue("Unsaved MCU notes");
  expect(data.writes).toHaveLength(0);
});

for (const language of ["en", "zh"]) {
  test("mcu interaction " + language + " empty catalogue explains registration without inventing releases or hiding read failures", async ({ page }, info) => {
    const data = await mockAdmin(page, language);
    await page.locator("#searchInput").fill("no-such-version");
    await expect(page.locator("#firmwareSetup")).toHaveCount(0);
    await page.locator('[data-firmware-action="clear-filters"]').first().click();
    data.releases = [];
    data.channels.forEach(channel => { channel.currentReleaseId = null; });
    await refreshMcu(page);
    await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(0);
    await expect(page.locator("#firmwareSetup")).toBeVisible();
    await expect(page.locator("#firmwareSetup")).toContainText("BLE V2");
    await expect(page.locator("#firmwareSetup a")).toHaveAttribute("href",
      "https://github.com/Eitan-S-23/E-Track/actions/workflows/firmware-build.yml");
    await expect(page.locator("#firmwareSetup a")).toHaveAttribute("rel", "noopener noreferrer");
    await expect(page.locator("#firmwarePagination")).toBeHidden();
    await page.screenshot({ path: info.outputPath("mcu-empty-registration-mock.png"), animations: "disabled" });
    await firmwareTab(page, "channels");
    await expect(channelButton(page, "stable", "retract")).toBeDisabled();
    await expect(channelButton(page, "beta", "retract")).toBeDisabled();
    await firmwareTab(page, "history");
    await expect(page.locator('#firmwareHistoryScope option[value="selected"]')).toHaveJSProperty("disabled", true);
    await firmwareTab(page, "releases");
    data.failReads = true;
    await refreshMcu(page);
    await expect(page.locator("#firmwareNotice")).toBeVisible();
    await expect(page.locator("#firmwareSetup")).toHaveCount(0);
    await expect(page.locator("#firmwareDetail")).toContainText(language === "zh" ? "不能据此判断版本库为空" : "before deciding whether this catalogue is empty");
    expect(data.writes).toHaveLength(0);
  });
}
type ReleaseFailure = { status: number; code: string; correlation?: "missing" | "mismatch" };
function release(id: string, versionCode: number) {
  return { ...scope, releaseId: id, versionCode, versionName: `2.8.${versionCode - 20800}`,
    releaseTag: `mcu-e-track-at32f435-v2.8.${versionCode - 20800}`, state: "ready", archived: false,
    releaseNotes: "Synthetic browser fixture, not a released firmware", targetImageSha256: "b".repeat(64), publishedChannels: [] as string[],
    createdAt: `2026-07-${String(versionCode - 20800 + 1).padStart(2, "0")} 12:30:00`, updatedAt: "2026-07-09 12:30:00",
    commitSha: "d".repeat(40), runId: "12345678", hardwareRevision: 1, layoutId: 1,
    minBootVersion: 1, minProtocolVersion: 1, minAppVersionCode: 86, targetHardware: "AT32F435", transport: "ble",
    assets: ["full", "patch", "recovery"].map(kind => ({ assetId: `${id}-${kind}`, kind,
      fileName: `${id}-${kind}.${kind === "recovery" ? "bin" : "etu"}`, sha256: "a".repeat(64), sizeBytes: 1024,
      r2State: "available", baseImageSha256: kind === "patch" ? "c".repeat(64) : null, baseVersionCode: kind === "patch" ? 20700 : 0 })) };
}

async function mockAdmin(page: Page, language = "en", role = "owner") {
  const data = {
    role, actor: `${role}@example.test`, mode: "normal", failReads: false, expireReplay: false,
    releaseFailure: null as ReleaseFailure | null,
    releases: [release("fw-new", 20803), release("fw-current", 20802), release("fw-old", 20801)],
    channels: ["stable", "beta"].map((channel, index) => ({ ...scope, channel, currentReleaseId: "fw-current" as string | null,
      revision: 7 + index, disableLatest: false, disableDownloads: false, maintenanceMessage: null as string | null })),
    writes: [] as Array<{ path: string; body: Record<string, unknown>; key?: string }>,
    events: [] as string[], results: new Map<string, { fingerprint: string; result: Record<string, unknown> }>(), mutations: 0,
    history: [] as Array<Record<string, unknown>>, failHistory: false, recoveryDownload: true
  };
  const published = () => { for (const r of data.releases) r.publishedChannels = data.channels.filter(c => c.currentReleaseId === r.releaseId).map(c => c.channel); };
  published();
  await page.addInitScript(lang => localStorage.setItem("trace-admin-language", lang), language);
  let serial = 0;
  await page.route("**/*", async route => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin !== origin) { await route.abort(); return; }
    if (url.pathname === "/") { await route.fulfill({ contentType: "text/html", body: html }); return; }
    if (url.pathname === "/admin.css") { await route.fulfill({ contentType: "text/css", body: css }); return; }
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
        if (url.pathname.endsWith("/history")) {
          if (data.failHistory) { await fail("BACKEND_UNAVAILABLE", 503); return; }
          const rows = data.history.filter(row => !url.searchParams.has("releaseId") || row.releaseId === url.searchParams.get("releaseId"));
          const cursor = url.searchParams.get("cursor");
          const start = cursor ? rows.findIndex(row => `${row.createdAt}|${row.id}` === cursor) + 1 : 0;
          const limit = Number(url.searchParams.get("limit") ?? 25);
          const selected = rows.slice(start, start + limit); const last = selected.at(-1);
          await reply({ ok: true, requestId, history: selected,
            nextCursor: start + limit < rows.length && last ? `${last.createdAt}|${last.id}` : null }); return;
        }
        expect([...url.searchParams.keys()].sort()).toEqual(["appId", "deviceModel"]);
        expect(url.searchParams.get("deviceModel")).toBe(scope.deviceModel);
        published();
        await reply(url.pathname.endsWith("/channels") ? { ok: true, requestId, firmwareChannels: data.channels }
          : { ok: true, requestId, firmwareReleases: data.releases, capabilities: { recoveryDownload: data.recoveryDownload } }); return;
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
    if (action === "notes") {
      expect(Object.keys(body).sort()).toEqual(["appId", "deviceModel", "expectedNotes", "reason", "releaseNotes"]);
      const target = data.releases.find(r => r.releaseId === name)!;
      if (data.mode === "notes-conflict") {
        data.mode = "normal"; target.releaseNotes = "Saved by another operator";
        await fail("CAS_CONFLICT", 409); return;
      }
      if (body.expectedNotes !== target.releaseNotes) { await fail("CAS_CONFLICT", 409); return; }
      target.releaseNotes = String(body.releaseNotes); data.mutations++;
      data.history.unshift({ id: `notes-${serial}`, action: "edit_notes", actor: data.actor,
        createdAt: "2026-11-11 10:00:00", reason: body.reason, releaseId: name, releaseTag: target.releaseTag,
        requestId, before: { releaseNotes: body.expectedNotes }, after: { releaseNotes: body.releaseNotes } });
      if (data.mode === "unknown-notes") { data.mode = "normal"; await route.abort("failed"); return; }
      await reply({ ok: true, requestId, action: "edit_notes", releaseId: name, releaseNotes: target.releaseNotes, idempotent: false }); return;
    }
    expect(Object.keys(body).sort()).toEqual(["appId", "deviceModel", "reason"]);
    if (action === "delete") {
      const target = data.releases.find(r => r.releaseId === name)!;
      expect(target.state).toBe("disabled"); expect(target.publishedChannels).toHaveLength(0);
      target.archived = true;
      if (data.mode === "partial-delete") {
        data.mode = "normal"; await fail("BACKEND_UNAVAILABLE", 503); return;
      }
      target.assets.forEach(a => a.r2State = "r2_deleted"); data.mutations++;
      await reply({ ok: true, requestId, action: "delete_files", releaseId: name,
        state: "disabled", archived: true, retainedHistory: true, idempotent: false }); return;
    }
    const key = request.headers()["idempotency-key"];
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    const fingerprint = JSON.stringify({ path: url.pathname, body });
    if (data.releaseFailure) {
      const failure = data.releaseFailure;
      await reply({ errorCode: failure.code, message: `Mock ${failure.code}`,
        ...(failure.correlation === "missing" ? {} : { requestId }) }, failure.status,
      failure.correlation === "mismatch" ? "mismatched-error-request" : requestId);
      return;
    }
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
  if (await page.locator("#mobileMenu").isVisible()) await page.locator("#mobileMenu").click();
  await page.locator('[data-view-target="firmware"]').click();
  return data;
}

const channelButton = (page: Page, channel: string, action: string) => page.locator(
  `.firmware-channel-card[data-channel="${channel}"] [data-firmware-action="${action}"]`);
const releaseButton = (page: Page, id: string, action: string) => page.locator(action === "select"
  ? `#firmwareReleaseList .firmware-release-card[data-release-id="${id}"] [data-firmware-action="select"]`
  : `#firmwareDetail[data-release-id="${id}"] [data-firmware-action="${action}"]`);
async function firmwareTab(page: Page, section: "releases" | "channels" | "history") {
  const tab = page.locator('[data-firmware-section="' + section + '"]');
  if (await tab.getAttribute("aria-selected") !== "true") await tab.click();
  await expect(tab).toHaveAttribute("aria-selected", "true");
}
async function clickRelease(page: Page, id: string, action: string) {
  await firmwareTab(page, "releases");
  await releaseButton(page, id, action).click();
}
async function clickChannel(page: Page, channel: string, action: string) {
  await firmwareTab(page, "channels");
  if (await page.locator("#firmwareChannelPanel").getAttribute("open") === null) {
    await page.locator("#firmwareChannelPanel > summary").click();
  }
  await channelButton(page, channel, action).click();
}
async function fillConfirmation(page: Page, reason = " browser operator reason ") {
  await expect(page.locator("#confirmDialog")).toBeVisible();
  // This class is set by the animation frame that applies the initial autofocus.
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  const input = page.locator("#confirmInput");
  const reasonInput = page.locator("#confirmReason");
  const needsText = await input.isVisible();
  const needsReason = await reasonInput.isVisible();
  if (needsText) await input.fill("stable");
  if (needsReason) await reasonInput.fill(reason);
  if (needsText) await expect(input).toHaveValue("stable");
  if (needsReason) await expect(reasonInput).toHaveValue(reason);
  await expect(page.locator("#confirmAccept")).toBeEnabled();
  await page.locator("#confirmAccept").click();
}
async function closeResult(page: Page) {
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await expect(page.locator("#refreshButton")).toBeEnabled();
}

for (const language of ["en", "zh"]) for (const width of [1440, 390]) {
  test(`workspace ${language} normal ${width}px starts with versions and compact channel controls`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 1000 });
    const data = await mockAdmin(page, language, "owner");
    const panel = page.locator("#firmwareChannelPanel");
    await expect(page.locator("#firmwareChannelsPanel")).toBeHidden();
    await expect(page.locator("#firmwareChannelSummary")).toContainText(data.releases[1].versionName);
    await expect(channelButton(page, "stable", "stop-latest")).toBeHidden();
    await expect(releaseButton(page, "fw-new", "select")).toBeInViewport();
    await expect(page.locator("#resourceOrb")).toBeVisible();
    await expect(page.locator("#drawerBackdrop")).toBeHidden();
    await page.screenshot({ path: info.outputPath(`workspace-normal-${language}-${width}-mock.png`), fullPage: false, animations: "disabled" });
    await page.locator("#firmwareChannelsTab").focus();
    await page.keyboard.press("Enter");
    await expect(channelButton(page, "stable", "stop-latest")).toBeVisible();
    await panel.locator("summary").click();
    await expect(channelButton(page, "stable", "stop-latest")).toBeHidden();
    await firmwareTab(page, "releases");
    await page.locator("#resourceOrb").click();
    await expect(page.locator("#resourcePanel")).toBeVisible();
    await page.locator("#resourceClose").click();
    await expect(page.locator("#resourcePanel")).toBeHidden();
    expect(data.writes).toHaveLength(0);
  });
}

test("workspace filters, sorting, selection and comparison use actual version data", async ({ page }) => {
  const data = await mockAdmin(page);
  await page.locator("#firmwareStatusFilter").selectOption("candidate");
  await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(2);
  await page.locator("#firmwareSort").selectOption("version-asc");
  await expect(page.locator("#firmwareReleaseList .firmware-release-card").first()).toHaveAttribute("data-release-id", "fw-old");
  await clickRelease(page, "fw-old", "select");
  await expect(page.locator("#firmwareDetail")).toHaveAttribute("data-release-id", "fw-old");
  await page.locator("#firmwareCompare").selectOption("fw-new");
  await expect(page.locator("#firmwareComparison")).toContainText("20801");
  await expect(page.locator("#firmwareComparison")).toContainText("20803");
  await expect(page.locator("#firmwareComparison .changed")).not.toHaveCount(0);
  await page.locator("#searchInput").fill("fw-old-patch");
  await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(1);
  await page.locator('[data-firmware-action="clear-filters"]').click();
  await page.locator("#firmwareChannelFilter").selectOption("stable");
  await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(1);
  await expect(page.locator("#firmwareDetail")).toHaveAttribute("data-release-id", "fw-current");
  expect(data.writes).toHaveLength(0);
});

test("workspace update notes save through the real-shaped API and retain immutable identity", async ({ page }) => {
  const data = await mockAdmin(page); const original = structuredClone(data.releases[0]);
  await page.locator('[data-firmware-action="notes-edit"]').click();
  await page.locator("#firmwareNotesEditor").fill("## New notes\n- Current firmware behavior");
  await page.locator('[data-firmware-action="notes-save"]').click();
  await page.locator("#confirmCancel").click();
  expect(data.writes).toHaveLength(0);
  await page.locator('[data-firmware-action="notes-save"]').click(); await fillConfirmation(page, "correct operator-facing description");
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed"); await closeResult(page);
  expect(data.writes[0].body).toMatchObject({ expectedNotes: original.releaseNotes, releaseNotes: "## New notes\n- Current firmware behavior" });
  expect(data.releases[0].assets).toEqual(original.assets);
  expect(data.releases[0].targetImageSha256).toBe(original.targetImageSha256);
  await firmwareTab(page, "history");
  await expect(page.locator("#firmwareHistoryList")).toContainText("Edited update notes");
  await expect(page.locator("#firmwareDetail .firmware-notes")).toContainText("Current firmware behavior");
});

test("workspace notes conflict preserves draft and requires an explicit new confirmation", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "notes-conflict";
  await page.locator('[data-firmware-action="notes-edit"]').click();
  await page.locator("#firmwareNotesEditor").fill("My unsaved description");
  await page.locator('[data-firmware-action="notes-save"]').click(); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("draft is preserved"); await closeResult(page);
  await expect(page.locator("#firmwareNotesEditor")).toHaveValue("My unsaved description");
  await expect(page.locator("#firmwareDetail")).toContainText("Saved by another operator");
  await expect(page.locator('[data-firmware-action="notes-save"]')).toBeDisabled();
  expect(data.writes).toHaveLength(1);
  await page.locator('[data-firmware-action="notes-rebase"]').click();
  expect(data.writes).toHaveLength(1);
  await page.locator('[data-firmware-action="notes-save"]').click(); await fillConfirmation(page, "reviewed competing notes");
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  expect(data.writes[1].body.expectedNotes).toBe("Saved by another operator");
});

test("workspace unknown notes outcome never repeats a write and preserves the draft", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-notes";
  await page.locator('[data-firmware-action="notes-edit"]').click();
  await page.locator("#firmwareNotesEditor").fill("Committed but response lost");
  await page.locator('[data-firmware-action="notes-save"]').click(); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  await expect(page.locator("#firmwareNotesEditor")).toHaveValue("Committed but response lost");
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
  await page.locator('[data-firmware-action="notes-rebase"]').click();
  await expect(page.locator('[data-firmware-action="notes-save"]')).toBeDisabled();
  expect(data.writes).toHaveLength(1);
});

test("workspace history paginates, filters by version and isolates read failures", async ({ page }) => {
  const data = await mockAdmin(page);
  data.history = Array.from({ length: 30 }, (_, index) => ({ id: `history-${index}`, action: "edit_notes",
    actor: "owner@example.test", createdAt: "2026-11-11 10:00:00", releaseId: "fw-new", releaseTag: data.releases[0].releaseTag,
    reason: `Operation ${index}`, requestId: `history-request-${index}`, before: { releaseNotes: "before" }, after: { releaseNotes: "after" } }));
  await firmwareTab(page, "history");
  await page.locator('[data-firmware-action="history-refresh"]').click();
  await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(25);
  await page.locator("#firmwareHistoryMore").click();
  await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(30);
  await expect(page.locator("#firmwareHistoryMore")).toBeHidden();
  await page.locator("#firmwareHistoryScope").selectOption("selected");
  await clickRelease(page, "fw-old", "select");
  await firmwareTab(page, "history");
  await expect(page.locator("#firmwareHistoryList .firmware-history-item")).toHaveCount(0);
  data.failHistory = true;
  await firmwareTab(page, "history");
  await page.locator('[data-firmware-action="history-refresh"]').click();
  await expect(page.locator("#firmwareHistoryStatus")).toContainText("could not be loaded");
  await clickRelease(page, "fw-new", "select");
  await expect(releaseButton(page, "fw-new", "publish").first()).toBeEnabled();
  expect(data.writes).toHaveLength(0);
});

test("workspace unavailable recovery and read-only notes explain why actions are disabled", async ({ page }) => {
  const data = await mockAdmin(page, "en", "viewer");
  await expect(page.locator('[data-firmware-action="notes-edit"]')).toBeDisabled();
  data.role = "owner"; data.actor = "owner@example.test"; data.recoveryDownload = false;
  await page.locator("#refreshButton").click();
  await expect(releaseButton(page, "fw-new", "recovery-download")).toBeDisabled();
  await expect(page.locator("#firmwareDetail")).toContainText("Recovery download is not configured");
  expect(data.writes).toHaveLength(0);
});

test("workspace deletion history uses the actual audit action and readable package count", async ({ page }) => {
  const data = await mockAdmin(page);
  data.history = [{ id: "deleted-files", action: "delete_firmware_files", actor: "owner@example.test",
    createdAt: "2026-11-11 10:00:00", releaseId: "fw-old", releaseTag: data.releases[2].releaseTag,
    reason: "Delete unused firmware files", requestId: "history-deletion", before: {}, after: { assetCount: 3 } }];
  await firmwareTab(page, "history");
  await page.locator('[data-firmware-action="history-refresh"]').click();
  await expect(page.locator("#firmwareHistoryList")).toContainText("Deleted package files");
  await page.locator("#firmwareHistoryList summary").click();
  await expect(page.locator("#firmwareHistoryList .firmware-meta-grid p strong")).toHaveText("Packages");
  await expect(page.locator("#firmwareHistoryList")).not.toContainText("delete_firmware_files");
  expect(data.writes).toHaveLength(0);
});

for (const language of ["en", "zh"]) {
  for (const width of [1440, 1024, 768, 390, 320]) {
    test(`workspace ${language} populated layout fits ${width}px without text clipping or floating obstruction`, async ({ page }, info) => {
      await page.setViewportSize({ width, height: 1000 });
      const data = await mockAdmin(page, language);
      data.releases[0].releaseTag += "-" + "long-release-tag".repeat(7);
      data.releases[0].assets[0].fileName = "package-name-".repeat(8) + ".etu";
      data.releases[0].releaseNotes = "# " + (language === "zh" ? "较长的固件更新说明" : "Long firmware update description ").repeat(8)
        + "\n- " + "LongUnbrokenIdentifier".repeat(15) + "\n<img src=x onerror=alert(1)>";
      data.channels[0].maintenanceMessage = (language === "zh" ? "这是需要完整展示的维护说明。" : "A maintenance message that must remain fully readable. ").repeat(6);
      await page.locator("#refreshButton").click();
      await expect(page.locator("#firmwareDetail")).toContainText("LongUnbrokenIdentifier");
      await page.locator("#firmwareCompare").selectOption("fw-old");
      await expect(page.locator("#resourceOrb")).toBeVisible();
      await expect(page.locator("#firmwareDetail img")).toHaveCount(0);
      for (const section of ["releases", "channels"] as const) {
        await firmwareTab(page, section);
        const overflow = await page.locator("#firmwareView").evaluate(root => {
          const width = document.documentElement.clientWidth;
          return [...root.querySelectorAll<HTMLElement>(".firmware-panel, .firmware-release-card, .firmware-channel-card, .firmware-meta-grid strong, .firmware-notes, .firmware-compare-row, button")]
            .filter(element => element.getClientRects().length > 0)
            .filter(element => { const box = element.getBoundingClientRect();
              return box.left < -1 || box.right > width + 1 || element.scrollWidth > element.clientWidth + 2; })
            .map(element => ({ tag: element.tagName, class: element.className, text: element.textContent?.slice(0, 80) }));
        });
        expect(overflow).toEqual([]);
        await page.screenshot({ path: info.outputPath(`workspace-${section}-${language}-${width}-mock.png`), fullPage: true });
      }
      expect(data.writes).toHaveLength(0);
    });
  }
}

for (const language of ["en", "zh"]) {
  test(`${language}: retract boundary, reason, cancel and fresh confirmation`, async ({ page }, info) => {
    const data = await mockAdmin(page, language);
    await expect(page.locator("#firmwareView")).not.toContainText("undefined");
    await clickRelease(page, "fw-old", "select");
    await page.screenshot({ path: info.outputPath(`${language}-mock-overview.png`), fullPage: true });
    await clickChannel(page, "stable", "retract");
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
    await clickChannel(page, "stable", "retract");
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
    await clickRelease(page, "fw-old", "select");
    await clickChannel(page, "stable", "retract"); await fillConfirmation(page);
    await expect(page.locator("#confirmMessage")).toContainText(language === "zh" ? "再次确认" : "confirm again");
    await page.screenshot({ path: info.outputPath(`${language}-mock-conflict.png`), fullPage: true });
    expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(0);
    await closeResult(page);
    await clickChannel(page, "stable", "retract");
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
  await clickChannel(page, "beta", "stop-downloads");
  await expect(page.locator("#confirmInput")).toBeHidden();
  await page.locator("#confirmMaintenance").fill("download incident"); await fillConfirmation(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed"); await closeResult(page);
  expect(data.channels[1]).toMatchObject({ disableLatest: false, disableDownloads: true });
  await clickChannel(page, "beta", "resume-downloads");
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
  await clickRelease(page, "fw-old", "select");
  await expect(releaseButton(page, "fw-old", "disable")).toBeDisabled();
  await clickRelease(page, "fw-current", "select");
  await expect(releaseButton(page, "fw-current", "disable")).toBeDisabled();
});

for (const language of ["en", "zh"]) {
  test(`${language}: delete is separate from disable, requires typed tag, and retains history`, async ({ page }) => {
    const data = await mockAdmin(page, language);
    await clickRelease(page, "fw-current", "select");
    await expect(releaseButton(page, "fw-current", "delete")).toBeDisabled();
    await clickRelease(page, "fw-new", "select");
    await expect(releaseButton(page, "fw-new", "delete")).toBeDisabled();
    data.releases[0].state = "disabled";
    await page.locator("#refreshButton").click();
    await clickRelease(page, "fw-new", "delete");
    await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
    await page.locator("#confirmReason").fill("remove disposable files");
    await expect(page.locator("#confirmAccept")).toBeDisabled();
    await page.locator("#confirmInput").fill(data.releases[0].releaseTag);
    await expect(page.locator("#confirmAccept")).toBeEnabled();
    await page.locator("#confirmCancel").click();
    expect(data.writes).toHaveLength(0);
    await clickRelease(page, "fw-new", "delete");
    await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
    await page.locator("#confirmInput").fill(data.releases[0].releaseTag);
    await page.locator("#confirmReason").fill("confirmed file deletion");
    await page.locator("#confirmAccept").click();
    await expect(page.locator("#confirmTitle")).toHaveText(language === "zh" ? "固件操作已确认" : "Firmware operation confirmed");
    expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
    await closeResult(page);
    await expect(page.locator('.firmware-release-card[data-release-id="fw-new"]')).toBeVisible();
    await expect(releaseButton(page, "fw-new", "delete")).toBeDisabled();
    await expect(releaseButton(page, "fw-new", "delete")).toHaveText(language === "zh" ? "文件已删除，历史记录保留" : "Files deleted; history retained");
  });
}

test("partial file deletion requires a fresh explicit confirmation instead of automatic retry", async ({ page }) => {
  const data = await mockAdmin(page);
  data.releases[0].state = "disabled"; data.mode = "partial-delete";
  await page.locator("#refreshButton").click();
  await clickRelease(page, "fw-new", "delete");
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  await page.locator("#confirmInput").fill(data.releases[0].releaseTag);
  await page.locator("#confirmReason").fill("delete disposable files");
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation not confirmed");
  await closeResult(page);
  expect(data.writes).toHaveLength(1);
  await expect(releaseButton(page, "fw-new", "delete")).toHaveText("Continue file deletion");
  await clickRelease(page, "fw-new", "delete");
  await expect(page.locator("#confirmInput")).toHaveValue("");
  await expect(page.locator("#confirmReason")).toHaveValue("");
  await page.locator("#confirmCancel").click();
  expect(data.writes).toHaveLength(1);
});

test("unknown channel result is read back but never automatically repeated", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-channel";
  await clickChannel(page, "beta", "stop-latest"); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown");
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
  expect(data.events.at(-1)).toMatch(/^GET /);
  await closeResult(page);
  await expect(channelButton(page, "beta", "resume-latest")).toBeEnabled();
  expect(data.writes).toHaveLength(1);
});

test("unknown release result uses an explicit same-key/same-body reconciliation after reads", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-release";
  await clickRelease(page, "fw-new", "recovery-download"); await fillConfirmation(page, "original recovery reason");
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
  await clickRelease(page, "fw-new", "recovery-download"); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  data.expireReplay = true;
  await page.locator('[data-firmware-action="retry-release"]').click(); await fillConfirmation(page);
  await expect(page.locator("#confirmDetail")).toContainText("IDEMPOTENCY_RESULT_EXPIRED");
  expect(data.writes).toHaveLength(2); expect(data.writes[1].key).toBe(data.writes[0].key);
  await closeResult(page); data.expireReplay = false;
  await clickRelease(page, "fw-new", "recovery-download");
  expect(data.writes).toHaveLength(2); await fillConfirmation(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  expect(data.writes[2].key).not.toBe(data.writes[0].key);
});

const interruptedReplayFailures: ReleaseFailure[] = [
  { status: 401, code: "TOKEN_EXPIRED" },
  { status: 403, code: "CSRF_INVALID" },
  { status: 403, code: "ROLE_FORBIDDEN" },
  { status: 429, code: "RATE_LIMITED" },
  { status: 503, code: "BACKEND_UNAVAILABLE" },
  { status: 409, code: "IDEMPOTENCY_CONFLICT" },
  { status: 410, code: "RELEASE_DISABLED" },
  { status: 409, code: "IDEMPOTENCY_RESULT_EXPIRED", correlation: "missing" },
  { status: 409, code: "IDEMPOTENCY_RESULT_EXPIRED", correlation: "mismatch" },
  { status: 403, code: "IDEMPOTENCY_RESULT_EXPIRED" }
];
for (const action of ["recovery-download", "disable"]) for (const failure of interruptedReplayFailures) {
  test(`${action}: interrupted reconciliation preserves intent after ${failure.status}/${failure.code}/${failure.correlation ?? "valid"}`, async ({ page }) => {
    const data = await mockAdmin(page); data.mode = "unknown-release";
    await clickRelease(page, "fw-new", action); await fillConfirmation(page, "original unresolved intent");
    await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
    const original = data.writes[0]; const result = data.results.get(original.key!)!.result;
    expect(data.mutations).toBe(1);
    data.releaseFailure = failure;
    for (let attempt = 0; attempt < 2; attempt++) {
      const events = data.events.length; const writes = data.writes.length;
      await page.locator('[data-firmware-action="retry-release"]').click();
      await expect(page.locator("#confirmDetail")).toContainText("original unresolved intent");
      expect(data.events.slice(events).every(event => event.startsWith("GET "))).toBe(true);
      expect(data.writes).toHaveLength(writes);
      await fillConfirmation(page);
      await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation not confirmed");
      await expect(page.locator("#confirmDownload")).toBeHidden(); await closeResult(page);
      expect(data.writes.at(-1)).toEqual(original); expect(data.mutations).toBe(1);
      await expect(page.locator('[data-firmware-action="retry-release"]')).toBeVisible();
      await expect(channelButton(page, "beta", "stop-latest")).toBeDisabled();
      await clickRelease(page, "fw-old", "select");
      await expect(releaseButton(page, "fw-old", "recovery-download")).toBeDisabled();
      await expect(releaseButton(page, "fw-old", "disable")).toBeDisabled();
      await page.locator("#refreshButton").click(); await expect(page.locator("#refreshButton")).toBeEnabled();
      await expect(page.locator('[data-firmware-action="retry-release"]')).toBeVisible();
      await expect(releaseButton(page, "fw-old", "recovery-download")).toBeDisabled();
      expect(data.writes).toHaveLength(writes + 1); expect(data.results.size).toBe(1);
    }
    data.releaseFailure = null;
    await page.locator('[data-firmware-action="retry-release"]').click();
    expect(data.writes).toHaveLength(3); await fillConfirmation(page);
    await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
    await expect(page.locator("#confirmDetail")).toContainText(String(result.requestId));
    if (action === "recovery-download") await expect(page.locator("#confirmDownload")).toHaveAttribute("href", String(result.downloadUrl));
    expect(data.writes).toHaveLength(4); expect(data.writes[3]).toEqual(original);
    expect(data.mutations).toBe(1); expect(data.results.size).toBe(1);
    await closeResult(page);
    await expect(page.locator('[data-firmware-action="retry-release"]')).toBeHidden();
    await expect(channelButton(page, "beta", "stop-latest")).toBeEnabled();
  });
}

for (const failure of interruptedReplayFailures.slice(0, 4)) {
  test(`a first definitive ${failure.status}/${failure.code} rejection permits a separately confirmed intent`, async ({ page }) => {
    const data = await mockAdmin(page); data.releaseFailure = failure;
    await clickRelease(page, "fw-new", "recovery-download"); await fillConfirmation(page, "rejected first intent");
    await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation not confirmed"); await closeResult(page);
    expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(0); expect(data.results.size).toBe(0);
    await expect(page.locator('[data-firmware-action="retry-release"]')).toBeHidden();
    await expect(releaseButton(page, "fw-new", "recovery-download")).toBeEnabled();
    data.releaseFailure = null;
    await clickRelease(page, "fw-new", "recovery-download");
    expect(data.writes).toHaveLength(1); await fillConfirmation(page, "new confirmed intent after restoring access");
    await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
    expect(data.writes).toHaveLength(2); expect(data.writes[1].key).not.toBe(data.writes[0].key);
    expect(data.mutations).toBe(1);
  });
}

test("owner identity changes cannot replay a pending request in another actor scope", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "unknown-release";
  await clickRelease(page, "fw-new", "disable"); await fillConfirmation(page);
  await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  data.actor = "different-owner@example.test";
  await page.locator('[data-firmware-action="retry-release"]').click();
  await expect(page.locator("#firmwareNotice")).toBeVisible();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
});

test("failed state refresh keeps writes locked until a successful manual read", async ({ page }) => {
  const data = await mockAdmin(page); data.mode = "refresh-failure";
  await clickChannel(page, "beta", "stop-latest"); await fillConfirmation(page);
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
  await clickRelease(page, "fw-old", "select");
  await clickChannel(page, "stable", "retract");
  await expect(page.locator("#confirmReason")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("zh-mobile-mock-confirm.png"), fullPage: true });
});



test("design firmware reason Enter adds a newline and Cancel Enter never submits", async ({ page }) => {
  const data = await mockAdmin(page);
  await clickRelease(page, "fw-old", "select");
  await clickChannel(page, "beta", "retract");
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  await page.locator("#confirmReason").fill("First line");
  await page.locator("#confirmReason").press("End");
  await page.keyboard.press("Enter");
  await page.keyboard.type("Second line");
  await expect(page.locator("#confirmReason")).toHaveValue("First line\nSecond line");
  await expect(page.locator("#confirmDialog")).toBeVisible();
  expect(data.writes).toHaveLength(0);
  await page.locator("#confirmCancel").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(data.writes).toHaveLength(0);
  await expect(page.locator("#firmwareChannelsTab")).toBeFocused();
  await clickChannel(page, "beta", "retract");
  await fillConfirmation(page, "First line\nSecond line");
  await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  expect(data.writes).toHaveLength(1);
  expect(data.writes[0].body.reason).toBe("First line\nSecond line");
});

test("design firmware confirmation traps Tab and Escape does not alter selection", async ({ page }) => {
  const data = await mockAdmin(page);
  await clickRelease(page, "fw-old", "select");
  await clickChannel(page, "stable", "retract");
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  await page.locator("#confirmInput").fill("stable");
  await page.locator("#confirmReason").fill("Explicit reason");
  await page.locator("#confirmAccept").focus();
  await page.keyboard.press("Tab");
  await expect(page.locator("#confirmInput")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator("#confirmAccept")).toBeFocused();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#firmwareDetail")).toHaveAttribute("data-release-id", "fw-old");
  await page.keyboard.press("Escape");
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(await page.locator(".workspace").evaluate(el => (el as HTMLElement).inert)).toBe(false);
  expect(data.writes).toHaveLength(0);
});

for (const language of ["en", "zh"]) {
  test("design firmware " + language + " mobile selects details and returns to the chosen version", async ({ page }, info) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const data = await mockAdmin(page, language, "owner");
    await clickRelease(page, "fw-old", "select");
    await expect(page.locator("#firmwareDetail")).toBeFocused();
    await expect(page.locator("#firmwareDetail")).toHaveAttribute("data-release-id", "fw-old");
    await expect(page.locator(".firmware-back")).toBeInViewport();
    await page.screenshot({ path: info.outputPath("firmware-mobile-details-mock.png"), animations: "disabled" });
    await page.locator(".firmware-back").click();
    await expect(releaseButton(page, "fw-old", "select")).toBeFocused();
    await expect(releaseButton(page, "fw-old", "select")).toBeInViewport();
    expect(data.writes).toHaveLength(0);
  });
}

for (const language of ["en", "zh"]) {
  test("design firmware " + language + " normal desktop workspace keeps channels and packages readable", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    const data = await mockAdmin(page, language, "owner");
    await page.screenshot({ path: info.outputPath("firmware-minimal-mock.png"), fullPage: true, animations: "disabled" });
    await firmwareTab(page, "channels");
    const labels = await page.locator(".firmware-meta-grid > div > span").evaluateAll(nodes => nodes
      .filter(el => el.getClientRects().length > 0)
      .filter(el => el.scrollWidth > el.clientWidth + 1)
      .map(el => el.textContent));
    expect(labels).toEqual([]);
    await page.locator("#resourceOrb").click();
    await expect(page.locator("#resourcePanel")).toBeVisible();
    const trigger = await page.locator("#resourceOrb").boundingBox();
    const viewport = page.viewportSize()!;
    expect(trigger!.x).toBeGreaterThanOrEqual(0);
    expect(trigger!.y).toBeGreaterThanOrEqual(0);
    expect(trigger!.x + trigger!.width).toBeLessThanOrEqual(viewport.width);
    expect(trigger!.y + trigger!.height).toBeLessThanOrEqual(viewport.height);
    expect(errors).toEqual([]);
    expect(data.writes).toHaveLength(0);
  });
}
