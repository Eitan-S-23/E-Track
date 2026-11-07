import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

const origin = "https://p51-app-admin.test";
const html = readFileSync(new URL("../public/index.html", import.meta.url), "utf8").replace(/<body([^>]*)>/,
  '<body$1><div style="position:fixed;bottom:8px;left:12px;z-index:10000;padding:6px 12px;background:#fff2b0;color:#161616;font:12px monospace;pointer-events:none">MOCK UI / NO REAL ACCESS OR D1</div>');

function release(id: string, versionCode: number) {
  return { id, app_id: "trace", platform: "android", version_code: versionCode,
    version_name: `1.0.${versionCode - 26}`, release_tag: `mock-app-${versionCode}`,
    state: "candidate", archived: 0, fallback_only: 0, release_notes: "Synthetic App browser fixture",
    created_at: "2026-11-08T00:00:00Z", published_channels: "", asset_count: 2,
    r2_available_count: 2, apk_count: 1, manifest_count: 1, patch_count: 0 };
}

async function mockApp(page: Page, language = "en", role = "owner") {
  const data = {
    role, conflict: false, mutations: 0,
    releases: [release("app-new", 100), release("app-current", 99), release("app-old", 98)],
    channels: ["stable", "beta"].map((name, index) => ({ name, app_id: "trace", platform: "android",
      current_release_id: "app-current" as string | null, revision: 7 + index,
      disable_latest: 0, version_code: 99 as number | null, release_tag: "mock-app-99" })),
    writes: [] as Array<{ path: string; body: Record<string, unknown> }>
  };
  const sync = () => {
    for (const row of data.channels) {
      const current = data.releases.find(r => r.id === row.current_release_id);
      row.version_code = current?.version_code ?? null;
      row.release_tag = current?.release_tag ?? "";
    }
    for (const item of data.releases) item.published_channels = data.channels.filter(c => c.current_release_id === item.id).map(c => c.name).join(",");
  };
  await page.addInitScript(lang => localStorage.setItem("trace-admin-language", lang), language);
  let serial = 0;
  await page.route("**/*", async route => {
    const request = route.request(); const url = new URL(request.url());
    if (url.origin !== origin) { await route.abort(); return; }
    if (url.pathname === "/") { await route.fulfill({ contentType: "text/html", body: html }); return; }
    const requestId = `mock-app-request-${++serial}`;
    const reply = (body: object, status = 200) => route.fulfill({ status, contentType: "application/json",
      headers: { "X-Request-Id": requestId }, body: JSON.stringify(body) });
    const fail = (errorCode: string, status = 409) => reply({ errorCode, message: `Mock ${errorCode}` }, status);
    if (request.method() === "GET") {
      sync();
      if (url.pathname === "/api/admin/session") {
        await reply({ ok: true, appId: "trace", environment: "MOCK", actor: `${data.role}@example.test`, role: data.role, csrfToken: "mock-csrf" }); return;
      }
      if (url.pathname.startsWith("/api/admin/firmware/")) {
        await reply({ ok: true, requestId, firmwareChannels: [], firmwareReleases: [] }); return;
      }
      await reply({ ok: true, channels: data.channels, releases: data.releases, announcements: [], storage: null }); return;
    }
    expect(request.method()).toBe("POST");
    expect(request.headers()["content-type"]).toBe("application/json");
    expect(request.headers()["x-csrf-token"]).toBe("mock-csrf");
    expect(url.pathname).toMatch(/^\/api\/admin\/channels\/(stable|beta)\/publish$/);
    const body = request.postDataJSON() as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["appId", "expectedRevision", "platform", "releaseId", "rollback"]);
    expect(body.appId).toBe("trace"); expect(body.platform).toBe("android");
    data.writes.push({ path: url.pathname, body });
    const channel = data.channels.find(c => c.name === url.pathname.split("/")[4])!;
    if (data.role === "viewer" || (channel.name === "stable" && data.role !== "owner")) { await fail("ROLE_FORBIDDEN", 403); return; }
    if (data.conflict) { channel.revision++; data.conflict = false; await fail("CAS_CONFLICT"); return; }
    if (body.expectedRevision !== channel.revision || channel.disable_latest) { await fail("CAS_CONFLICT"); return; }
    const target = data.releases.find(r => r.id === body.releaseId)!;
    if (target.state === "disabled" || target.archived) { await fail("RELEASE_DISABLED"); return; }
    if (channel.current_release_id && target.version_code <= Number(channel.version_code) && body.rollback !== true) {
      await fail("VERSION_REGRESSION"); return;
    }
    channel.current_release_id = target.id; channel.revision++; data.mutations++; sync();
    await reply({ ok: true, revision: channel.revision });
  });
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(3);
  await expect(page.locator("#refreshButton")).toBeEnabled();
  return data;
}

const action = (page: Page, channel: string) => page.locator(`[data-action="publish"][data-channel="${channel}"]:visible`);
async function closeActions(page: Page) {
  if (await page.locator("#quickActionSheet").isVisible()) {
    await page.locator("#quickActionClose").click();
    await expect(page.locator("#quickActionSheet")).toBeHidden();
  }
}
async function select(page: Page, id: string) {
  await closeActions(page);
  await page.locator(`#versionStrip .version-card[data-release-id="${id}"]`).click();
  await expect(action(page, "beta")).toBeVisible();
}
async function confirm(page: Page) {
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  if (await page.locator("#confirmInput").isVisible()) await page.locator("#confirmInput").fill("stable");
  await page.locator("#confirmAccept").click();
}
async function closeResult(page: Page) {
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await expect(page.locator("#refreshButton")).toBeEnabled();
}

test("App rollback flag reaches the existing API", async ({ page }) => {
  const data = await mockApp(page);
  await select(page, "app-old"); await action(page, "beta").click(); await confirm(page);
  await expect.poll(() => data.writes.length).toBe(1);
  expect(data.writes[0].body).toEqual({ appId: "trace", platform: "android", releaseId: "app-old", expectedRevision: 8, rollback: true });
  await expect(page.locator("#confirmTitle")).toHaveText("Rollback completed");
  expect(data.mutations).toBe(1);
});

for (const language of ["en", "zh"]) for (const channel of ["stable", "beta"]) {
  test(`App ${language} ${channel}: explicit rollback, typed confirmation and cancel`, async ({ page }, info) => {
    const data = await mockApp(page, language);
    await select(page, "app-old");
    await expect(action(page, channel)).toContainText(language === "zh" ? "回退到" : "Roll back");
    await action(page, channel).click();
    await expect(page.locator("#confirmMessage")).toContainText("mock-app-98");
    await expect(page.locator("#confirmDetail")).toContainText(language === "zh" ? "已升级的客户端不会降级" : "Already-updated clients will not downgrade");
    if (channel === "stable") {
      await expect(page.locator("#confirmAccept")).toBeDisabled();
      await page.locator("#confirmInput").fill("Stable");
      await expect(page.locator("#confirmAccept")).toBeDisabled();
      await page.locator("#confirmInput").fill("stable");
      await expect(page.locator("#confirmAccept")).toBeEnabled();
    }
    await page.screenshot({ path: info.outputPath(`${language}-${channel}-app-mock-rollback.png`), fullPage: true });
    await page.locator("#confirmCancel").click();
    await expect(page.locator("#confirmDialog")).toBeHidden();
    expect(data.writes).toHaveLength(0); expect(data.mutations).toBe(0);
  });
}

for (const channel of ["stable", "beta"]) {
  test(`App ${channel}: forward publication never sets rollback`, async ({ page }) => {
    const data = await mockApp(page);
    await select(page, "app-new"); await expect(action(page, channel)).toContainText("Publish to");
    await action(page, channel).click(); await confirm(page);
    await expect(page.locator("#confirmTitle")).toHaveText("Publish completed");
    expect(data.writes).toHaveLength(1); expect(data.writes[0].body.rollback).toBe(false);
    expect(data.mutations).toBe(1); await closeResult(page);
  });
}

test("App labels reset on selection and language changes; current version stays locked", async ({ page }) => {
  const data = await mockApp(page);
  await select(page, "app-old"); await expect(action(page, "beta")).toContainText("Roll back");
  await closeActions(page);
  await page.locator("#languageToggle").click();
  await select(page, "app-old");
  await expect(action(page, "beta")).toContainText("回退到");
  await select(page, "app-new"); await expect(action(page, "beta")).toContainText("发布到");
  await select(page, "app-current");
  await expect(action(page, "beta")).toBeDisabled(); await expect(action(page, "stable")).toBeDisabled();
  expect(data.writes).toHaveLength(0);
});

for (const role of ["viewer", "publisher"]) {
  test(`App rollback keeps ${role} role boundaries`, async ({ page }) => {
    const data = await mockApp(page, "en", role); await select(page, "app-old");
    await expect(action(page, "stable")).toBeDisabled();
    if (role === "viewer") await expect(action(page, "beta")).toBeDisabled();
    else {
      await expect(action(page, "beta")).toBeEnabled();
      await action(page, "beta").click(); await confirm(page);
      await expect(page.locator("#confirmTitle")).toHaveText("Rollback completed");
    }
    expect(data.writes).toHaveLength(role === "viewer" ? 0 : 1);
  });
}

for (const condition of ["disabled", "archived", "missing-current", "equal-code", "stopped"]) {
  test(`App unavailable rollback is locked: ${condition}`, async ({ page }) => {
    const data = await mockApp(page);
    if (condition === "disabled") data.releases[2].state = "disabled";
    if (condition === "archived") data.releases[2].archived = 1;
    if (condition === "equal-code") data.releases[2].version_code = 99;
    if (condition === "missing-current") for (const row of data.channels) row.current_release_id = "unavailable";
    if (condition === "stopped") for (const row of data.channels) row.disable_latest = 1;
    await page.locator("#refreshButton").click(); await expect(page.locator("#refreshButton")).toBeEnabled();
    await select(page, "app-old");
    await expect(action(page, "stable")).toBeDisabled(); await expect(action(page, "beta")).toBeDisabled();
    expect(data.writes).toHaveLength(0);
  });
}

test("App CAS conflict never repeats rollback without fresh confirmation", async ({ page }) => {
  const data = await mockApp(page); data.conflict = true;
  await select(page, "app-old"); await action(page, "beta").click(); await confirm(page);
  await expect(page.locator("#confirmDetail")).toContainText("CAS_CONFLICT");
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(0); await closeResult(page);
  await page.locator("#refreshButton").click(); await expect(page.locator("#refreshButton")).toBeEnabled();
  await select(page, "app-old");
  await action(page, "beta").click(); expect(data.writes).toHaveLength(1); await confirm(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Rollback completed");
  expect(data.writes[1].body.expectedRevision).toBe(9); expect(data.mutations).toBe(1);
});

test("App initial empty channel uses ordinary publication", async ({ page }) => {
  const data = await mockApp(page); data.channels[1].current_release_id = null;
  await page.locator("#refreshButton").click(); await expect(page.locator("#refreshButton")).toBeEnabled();
  await select(page, "app-old"); await expect(action(page, "beta")).toContainText("Publish to");
  await action(page, "beta").click(); await confirm(page);
  await expect(page.locator("#confirmTitle")).toHaveText("Publish completed");
  expect(data.writes[0].body.rollback).toBe(false);
});

test("App mobile rollback confirmation fits and cancel writes nothing", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const data = await mockApp(page, "zh"); await select(page, "app-old");
  await expect(action(page, "stable")).toContainText("回退到"); await action(page, "stable").click();
  await expect(page.locator("#confirmDetail")).toContainText("已升级的客户端不会降级");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("zh-mobile-app-mock-rollback.png"), fullPage: true });
  await page.locator("#confirmCancel").click(); expect(data.writes).toHaveLength(0);
});
