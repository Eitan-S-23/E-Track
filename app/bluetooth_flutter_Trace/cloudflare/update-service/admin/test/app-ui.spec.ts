import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

const css = readFileSync(new URL("../public/admin.css", import.meta.url), "utf8");
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

async function mockApp(page: Page, language = "en", role = "owner", firmwareFailure = false) {
  const data = {
    role, conflict: false, notesFailure: false, announcementFailure: false, mutations: 0, firmwareFailure,
    announcements: [] as Array<{ id: string; title: string; body: string; published: number; pinned: number; created_at: string; updated_at: string }>,
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
    if (url.pathname === "/admin.css") { await route.fulfill({ contentType: "text/css", body: css }); return; }
    if (["/sheet-gestures.js","/overlay-history.js","/delta-activity.js"].includes(url.pathname)) {
      await route.fulfill({contentType:"text/javascript",body:readFileSync(new URL("../public"+url.pathname,import.meta.url),"utf8")}); return;
    }
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
        if (data.firmwareFailure) {
          await reply({ errorCode: "BACKEND_UNAVAILABLE", message: "Firmware migration unavailable", requestId }, 503); return;
        }
        await reply({ ok: true, requestId, firmwareChannels: [], firmwareReleases: [] }); return;
      }
      await reply({ ok: true, channels: data.channels, releases: data.releases, announcements: data.announcements, storage: { r2: { totalSizeBytes: 83886080, objectCount: 6, byType: [] }, tracked: { releaseCount: 3, totalSizeBytes: 83886080, objectCount: 6 } } }); return;
    }
    expect(request.method()).toBe("POST");
    expect(request.headers()["content-type"]).toBe("application/json");
    expect(request.headers()["x-csrf-token"]).toBe("mock-csrf");
    if (/^\/api\/admin\/releases\/[^/]+\/notes$/.test(url.pathname)) {
      const body = request.postDataJSON() as Record<string, unknown>;
      expect(Object.keys(body)).toEqual(["releaseNotes"]);
      data.writes.push({ path: url.pathname, body });
      if (data.notesFailure) { await fail("BACKEND_UNAVAILABLE", 503); return; }
      if (data.role === "viewer") { await fail("ROLE_FORBIDDEN", 403); return; }
      const selected = data.releases.find(row => row.id === url.pathname.split("/")[4])!;
      selected.release_notes = String(body.releaseNotes);
      data.mutations++;
      await reply({ ok: true }); return;
    }
    if (url.pathname.startsWith("/api/admin/announcements")) {
      const body = request.postDataJSON() as Record<string, unknown>;
      data.writes.push({ path: url.pathname, body });
      if (data.announcementFailure) { await fail("BACKEND_UNAVAILABLE", 503); return; }
      if (data.role === "viewer") { await fail("ROLE_FORBIDDEN", 403); return; }
      const id = url.pathname.split("/")[4] ?? "notice-created";
      if (url.pathname.endsWith("/delete")) {
        expect(body).toEqual({});
        data.announcements = data.announcements.filter(row => row.id !== id);
        data.mutations++;
        await reply({ ok: true }); return;
      }
      expect(Object.keys(body).sort()).toEqual(["appId", "body", "pinned", "published", "title"]);
      expect(body.appId).toBe("trace");
      expect(String(body.title).trim()).not.toBe(""); expect(String(body.body).trim()).not.toBe("");
      const value = { id, title: String(body.title), body: String(body.body),
        published: body.published ? 1 : 0, pinned: body.pinned ? 1 : 0,
        created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z" };
      const index = data.announcements.findIndex(row => row.id === id);
      if (index < 0) data.announcements.push(value); else data.announcements[index] = value;
      data.mutations++;
      await reply({ ok: true, announcementId: id }); return;
    }
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

for (const language of ["en", "zh"]) for (const width of [1440, 390, 320]) {
  test(`pinned close App ${language} ${width}px remains clickable after scrolling to the bottom`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const data = await mockApp(page, language);
    data.releases[0].release_notes = "Long release notes with enough content to require independent scrolling. ".repeat(60);
    await refreshApp(page);
    await select(page, "app-new");
    const sheet = page.locator("#quickActionSheet"), content = page.locator("#quickActionScroll");
    const close = page.locator("#quickActionClose");
    await expect.poll(() => sheet.evaluate(node => Number(getComputedStyle(node).opacity))).toBe(1);
    const start = (await close.boundingBox())!;
    expect((await content.boundingBox())!.y).toBeGreaterThanOrEqual(start.y + start.height);
    const background = await page.evaluate(() => scrollY);
    await content.evaluate(node => { node.scrollTop = node.scrollHeight; });
    expect(await content.evaluate(node => node.scrollTop)).toBeGreaterThan(0);
    await expect(close).toBeInViewport({ ratio: 1 });
    const end = (await close.boundingBox())!;
    expect((await content.boundingBox())!.y).toBeGreaterThanOrEqual(end.y + end.height);
    expect(Math.abs(end.x - start.x)).toBeLessThan(1);
    expect(Math.abs(end.y - start.y)).toBeLessThan(1);
    const point = { x: end.x + end.width / 2, y: end.y + end.height / 2 };
    expect(await page.evaluate(p => document.elementFromPoint(p.x, p.y)?.closest("button")?.id, point)).toBe("quickActionClose");
    expect(await page.evaluate(() => scrollY)).toBe(background);
    await page.screenshot({ path: info.outputPath(`app-close-at-bottom-${language}-${width}-mock.png`), animations: "disabled" });
    await page.mouse.click(point.x, point.y);
    await expect(sheet).toBeHidden();
    await expect(page.locator('#versionStrip .version-card[data-release-id="app-new"]')).toBeFocused();
    await select(page, "app-new");
    expect(await content.evaluate(node => node.scrollTop)).toBe(0);
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
    expect(data.writes).toHaveLength(0);
  });
}

test("firmware read failure cannot take down the existing App manager", async ({ page }) => {
  const data = await mockApp(page, "zh", "owner", true);
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(3);
  await select(page, "app-new");
  await expect(action(page, "beta")).toBeEnabled();
  await closeActions(page);
  await page.locator('[data-view-target="firmware"]').click();
  await expect(page.locator("#firmwareNotice")).toContainText("手机软件管理仍可使用");
  expect(data.writes).toHaveLength(0);
  data.firmwareFailure = false;
  await page.locator('[data-firmware-action="refresh"]').click();
  await expect(page.locator("#firmwareNotice")).toBeHidden();
  await page.locator('[data-view-target="phone"]').click();
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(3);
  await select(page, "app-new");
  await expect(action(page, "beta")).toBeEnabled();
});
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



for (const language of ["en", "zh"]) for (const width of [1440, 1024, 768, 390, 320]) {
  test("design App " + language + " " + width + "px has readable compact list, toolbar and modal", async ({ page }, info) => {
    const errors: string[] = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.setViewportSize({ width, height: 1000 });
    const data = await mockApp(page, language);
    await expect(page.locator("link[rel=stylesheet]")).toHaveAttribute("href", "/admin.css");
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue("--paper").trim())).toBe("#faf9f6");
    await expect(page.locator("#resourceOrb")).toBeVisible();
    await expect(page.locator(".resource-water-svg")).toHaveCount(1);
    await page.screenshot({ path: info.outputPath("app-minimal-mock.png"), fullPage: true, animations: "disabled" });
    data.releases[0].release_tag = "release-with-long-identity-".repeat(6);
    await page.locator("#refreshButton").click();
    await expect(page.locator("#refreshButton")).toBeEnabled();
    const clipped = await page.locator("#phoneView").evaluate(root => [...root.querySelectorAll<HTMLElement>(
      ".filter-chip, .version-card, .version-card h3, .version-summary, .version-health, .panel, .announcement-editor, textarea")]
      .filter(el => el.getClientRects().length > 0)
      .filter(el => el.scrollWidth > el.clientWidth + 2 || el.getBoundingClientRect().right > innerWidth + 1)
      .map(el => el.className || el.id));
    expect(clipped).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await select(page, "app-new");
    await expect(page.locator("#quickActionSheet")).toBeVisible();
    await expect(page.locator("#quickActionTitle")).toHaveText(data.releases[0].release_tag);
    const modal = await page.locator("#quickActionSheet").boundingBox();
    expect(modal!.x).toBeGreaterThanOrEqual(-1);
    expect(modal!.x + modal!.width).toBeLessThanOrEqual(width + 1);
    expect(await page.locator("#quickActionSheet").evaluate(el => el.scrollWidth <= el.clientWidth + 2)).toBe(true);
    await page.screenshot({ path: info.outputPath("app-details-minimal-mock.png"), animations: "disabled" });
    expect(errors).toEqual([]);
    expect(data.writes).toHaveLength(0);
  });
}

test("design App cancel Enter cannot publish and dialogs retain keyboard ownership", async ({ page }) => {
  const data = await mockApp(page);
  await select(page, "app-old");
  await page.locator("#quickActionClose").focus();
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator("#gate > summary")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.locator("#quickActionClose")).toBeFocused();
  expect(await page.locator(".workspace").evaluate(el => (el as HTMLElement).inert)).toBe(true);
  await action(page, "beta").click();
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  await page.locator("#confirmAccept").focus();
  await page.keyboard.press("Tab");
  await expect(page.locator("#confirmCancel")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await expect(page.locator('#versionStrip [data-release-id="app-old"]')).toBeFocused();
  expect(data.writes).toHaveLength(0);
  await page.keyboard.press("ArrowUp");
  await expect(page.locator('#versionStrip [data-release-id="app-current"]')).toBeFocused();
  await expect(page.locator("#quickActionSheet")).toBeHidden();
  await page.keyboard.press("/");
  await expect(page.locator("#searchInput")).toBeFocused();
});

test("design App note drafts survive close, selection, language and scroll but clear after save", async ({ page }) => {
  const data = await mockApp(page);
  const notes = "## Unsaved notes\n- Keep the operator's text.";
  await select(page, "app-new");
  await page.locator("#releaseNotes").fill(notes);
  await expect(page.locator("#notesDraftStatus")).toBeVisible();
  await page.locator("#versionStrip").evaluate(el => el.dispatchEvent(new Event("scroll")));
  await expect(page.locator("#releaseNotes")).toHaveValue(notes);
  await expect(page.locator("#quickActionTitle")).toHaveText("mock-app-100");
  await select(page, "app-old");
  await expect(page.locator("#releaseNotes")).toHaveValue(data.releases[2].release_notes);
  await select(page, "app-new");
  await expect(page.locator("#releaseNotes")).toHaveValue(notes);
  await closeActions(page);
  await page.locator("#languageToggle").click();
  await select(page, "app-new");
  await expect(page.locator("#releaseNotes")).toHaveValue(notes);
  await page.locator("#saveNotes").click();
  await expect(page.locator("body")).toHaveClass(/\bconfirm-open\b/);
  expect(data.writes).toHaveLength(1);
  expect(data.writes[0]).toEqual({ path: "/api/admin/releases/app-new/notes", body: { releaseNotes: notes } });
  await page.keyboard.press("Escape");
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await expect(page.locator("#quickActionSheet")).toBeVisible();
  await expect(page.locator("#refreshButton")).toBeEnabled();
  await expect(page.locator("#notesDraftStatus")).toBeHidden();
  await expect(page.locator("#saveNotes")).toBeDisabled();
  expect(data.releases[0].release_notes).toBe(notes);
  expect(data.mutations).toBe(1);
});

test("design failed App notes keep the draft, require explicit retry and allow discard", async ({ page }) => {
  const data = await mockApp(page);
  data.notesFailure = true;
  await select(page, "app-new");
  await page.locator("#releaseNotes").fill("A draft after a failed request");
  await page.locator("#saveNotes").click();
  await expect(page.locator("#confirmDetail")).toContainText("BACKEND_UNAVAILABLE");
  await closeResult(page);
  await expect(page.locator("#releaseNotes")).toHaveValue("A draft after a failed request");
  await expect(page.locator("#notesDraftStatus")).toBeVisible();
  expect(data.writes).toHaveLength(1);
  expect(data.mutations).toBe(0);
  await page.locator("#discardNotes").click();
  await expect(page.locator("#releaseNotes")).toHaveValue(data.releases[0].release_notes);
  await expect(page.locator("#notesDraftStatus")).toBeHidden();
  await expect(page.locator("#saveNotes")).toBeDisabled();
  expect(data.writes).toHaveLength(1);
});

test("design App drafts never cross actor identity and viewer editor is read-only", async ({ page }) => {
  const data = await mockApp(page);
  await select(page, "app-new");
  await page.locator("#releaseNotes").fill("Owner-only local draft");
  await closeActions(page);
  data.role = "viewer";
  await page.locator("#refreshButton").click();
  await expect(page.locator("#refreshButton")).toBeEnabled();
  await select(page, "app-new");
  await expect(page.locator("#releaseNotes")).toHaveValue(data.releases[0].release_notes);
  await expect(page.locator("#releaseNotes")).toBeDisabled();
  await expect(page.locator("#saveNotes")).toBeDisabled();
  await expect(page.locator("#notesDraftStatus")).toBeHidden();
  expect(data.writes).toHaveLength(0);
});

test("delayed-resource-frame cannot expose an unpositioned panel or steal focus after Escape", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 844 });
  const data = await mockApp(page);
  await page.evaluate(() => {
    const original = window.requestAnimationFrame, frames: FrameRequestCallback[] = [];
    window.requestAnimationFrame = callback => frames.push(callback);
    Object.assign(window, { releaseResourceFrames: () => {
      window.requestAnimationFrame = original;
      for (const frame of frames) frame(performance.now());
    } });
    document.querySelector<HTMLButtonElement>("#resourceOrb")!.click();
  });
  const panel = (await page.locator("#resourcePanel").boundingBox())!;
  expect(panel.x).toBeGreaterThanOrEqual(0); expect(panel.x + panel.width).toBeLessThanOrEqual(1440);
  expect(panel.y).toBeGreaterThanOrEqual(0); expect(panel.y + panel.height).toBeLessThanOrEqual(844);
  await expect(page.locator("#resourceClose")).toBeFocused();
  await page.keyboard.press("Escape");
  await page.evaluate("releaseResourceFrames()");
  await expect(page.locator("#resourcePanel")).toBeHidden();
  await expect(page.locator("#resourceOrb")).toBeFocused();
  expect(data.writes).toHaveLength(0);
});

test("design mobile navigation, storage Escape and reduced motion stay usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  const data = await mockApp(page, "zh");
  expect(await page.locator("#phoneView").evaluate(el => getComputedStyle(el).animationName)).toBe("none");
  await page.locator("#mobileMenu").click();
  await expect(page.locator("#mobileMenu")).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#closeNav")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(page.locator(".session-link")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator("#mobileMenu")).toBeFocused();
  await expect(page.locator("#mobileMenu")).toHaveAttribute("aria-expanded", "false");
  await page.locator("#resourceOrb").click();
  await expect(page.locator("#storageSummary")).toContainText("80 MiB");
  await page.keyboard.press("Escape");
  await expect(page.locator("#resourcePanel")).toBeHidden();
  await expect(page.locator("#resourceOrb")).toBeFocused();
  await page.locator("#mobileMenu").click();
  await page.locator('[data-view-target="firmware"]').click();
  await expect(page.locator("#firmwareView")).toBeVisible();
  await expect(page.locator("#drawerBackdrop")).toBeHidden();
  await expect(page.locator("#resourceOrb")).toBeVisible();
  expect(data.writes).toHaveLength(0);
});



function notice(index: number) {
  return { id: "notice-" + index, title: "Notice " + index, body: "Message for announcement " + index,
    published: 1, pinned: 0, created_at: "2026-11-11T00:00:00Z", updated_at: "2026-11-11T00:00:00Z" };
}
async function refreshApp(page: Page) {
  await page.locator("#refreshButton").click();
  await expect(page.locator("#refreshButton")).toBeEnabled();
}
async function appTab(page: Page, section: "releases" | "announcements") {
  await page.locator('[data-app-section="' + section + '"]').click();
  await expect(page.locator('[data-app-section="' + section + '"]')).toHaveAttribute("aria-selected", "true");
}

for (const language of ["en", "zh"]) for (const width of [1440, 390]) {
  test("interaction " + language + " " + width + "px bounds sixty versions and pins tools and peer tabs", async ({ page }, info) => {
    await page.setViewportSize({ width, height: 800 });
    const errors: string[] = []; page.on("pageerror", error => errors.push(error.message));
    const data = await mockApp(page, language);
    data.releases = Array.from({ length: 60 }, (_, i) => release("many-" + i, 1000 + i));
    data.announcements = Array.from({ length: 20 }, (_, i) => notice(i));
    await refreshApp(page);
    await expect(page.locator("#versionStrip .version-card")).toHaveCount(6);
    await expect(page.locator("#releasePageStatus")).toContainText("60");
    await expect(page.locator("#announcements")).toBeHidden();
    const list = await page.locator("#versionStrip").boundingBox();
    expect(list!.height).toBeLessThanOrEqual(width <= 720 ? 340 : 440);
    const height60 = await page.evaluate(() => document.documentElement.scrollHeight);
    data.releases = Array.from({ length: 600 }, (_, i) => release("many-" + i, 1000 + i));
    await refreshApp(page);
    await expect(page.locator("#versionStrip .version-card")).toHaveCount(6);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBeLessThanOrEqual(height60 + 8);
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect.poll(async () => Math.abs((await page.locator(".topbar").boundingBox())!.y)).toBeLessThan(1);
    for (const selector of ["#searchInput", "#languageToggle", "#refreshButton", "#appAnnouncementsTab"]) {
      await expect(page.locator(selector)).toBeInViewport();
    }
    await expect.poll(async () => {
      const bar = (await page.locator(".topbar").boundingBox())!;
      const tabs = (await page.locator("#appTabs").boundingBox())!;
      return Math.abs(tabs.y - bar.y - bar.height);
    }).toBeLessThan(1);
    await page.screenshot({ path: info.outputPath("many-versions-sticky-mock.png"), animations: "disabled" });
    await appTab(page, "announcements");
    await expect(page.locator("#appReleasesPanel")).toBeHidden();
    await expect(page.locator("#announcements")).toBeVisible();
    await expect(page.locator("#newAnnouncement")).toBeInViewport();
    await expect(page.locator("#announcementCount")).toHaveText("(20)");
    expect((await page.locator("#announcementList").boundingBox())!.height).toBeLessThanOrEqual(520);
    await page.screenshot({ path: info.outputPath("peer-announcements-mock.png"), fullPage: true, animations: "disabled" });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(errors).toEqual([]); expect(data.writes).toHaveLength(0);
  });
}

test("interaction pagination reaches the last page and filters/search/sort reset it correctly", async ({ page }) => {
  const data = await mockApp(page);
  data.releases = Array.from({ length: 14 }, (_, i) => release("many-" + i, 200 + i));
  data.releases[0].state = "disabled";
  await refreshApp(page);
  const rows = page.locator("#versionStrip .version-card");
  await expect(rows).toHaveCount(6);
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-13");
  await expect(page.locator("#releasePagePrev")).toBeDisabled();
  await page.locator("#releasePageNext").click();
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-7");
  await page.locator("#releasePageNext").click();
  await expect(rows).toHaveCount(2);
  await expect(rows.last()).toHaveAttribute("data-release-id", "many-0");
  await expect(page.locator("#releasePageNext")).toBeDisabled();
  await page.locator('[data-filter-value="disabled"]').click();
  await expect(rows).toHaveCount(1);
  await expect(page.locator("#releasePagination")).toBeHidden();
  await page.locator('[data-filter-value="all"]').click();
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-13");
  await page.locator("#searchInput").fill("mock-app-207");
  await expect(rows).toHaveCount(1); await expect(rows.first()).toHaveAttribute("data-release-id", "many-7");
  await page.locator("#searchInput").fill("");
  await page.locator("#sortTrigger").click();
  await page.locator('[data-sort-value="version_code:asc"]').click();
  await expect(rows.first()).toHaveAttribute("data-release-id", "many-0");
  expect(data.writes).toHaveLength(0);
});

test("interaction keyboard selection crosses page boundaries and returns to that page after details", async ({ page }) => {
  const data = await mockApp(page);
  data.releases = Array.from({ length: 13 }, (_, i) => release("many-" + i, 300 + i));
  await refreshApp(page);
  await page.locator("#versionStrip .version-card").last().focus();
  await page.keyboard.press("Enter");
  await closeActions(page);
  await page.keyboard.press("ArrowDown");
  await expect(page.locator('#versionStrip [data-release-id="many-6"]')).toBeFocused();
  await expect(page.locator("#releasePageStatus")).toContainText("7-12");
  await page.keyboard.press("Enter");
  await expect(page.locator("#quickActionTitle")).toHaveText("mock-app-306");
  await expect(page.locator("#resourceOrb")).toBeHidden();
  await page.keyboard.press("Escape");
  await expect(page.locator('#versionStrip [data-release-id="many-6"]')).toBeFocused();
  await expect(page.locator("#resourceOrb")).toBeVisible();
  expect(data.writes).toHaveLength(0);
});

test("interaction App tabs support arrow keys and independent search without losing announcement drafts", async ({ page }) => {
  const data = await mockApp(page);
  data.announcements = Array.from({ length: 12 }, (_, i) => notice(i));
  await refreshApp(page);
  await page.locator("#searchInput").fill("mock-app-100");
  await page.locator("#appReleasesTab").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#appAnnouncementsTab")).toBeFocused();
  await expect(page.locator("#searchInput")).toHaveValue("");
  await page.locator("#searchInput").fill("Notice 7");
  await expect(page.locator("#announcementList .announcement-card")).toHaveCount(1);
  await page.locator('[data-announcement-id="notice-7"]').click();
  await page.locator("#announcementTitle").fill("Edited local title");
  await page.locator("#announcementBody").fill("Unsaved message\nSecond line");
  await page.locator("#announcementPinned").check();
  await appTab(page, "releases");
  await expect(page.locator("#searchInput")).toHaveValue("mock-app-100");
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(1);
  await appTab(page, "announcements");
  await expect(page.locator("#searchInput")).toHaveValue("Notice 7");
  await page.locator("#languageToggle").click();
  await expect(page.locator("#announcementTitle")).toHaveValue("Edited local title");
  await expect(page.locator("#announcementBody")).toHaveValue("Unsaved message\nSecond line");
  await expect(page.locator("#announcementPinned")).toBeChecked();
  await expect(page.locator("#announcementDraftStatus")).toBeVisible();
  await page.locator('[data-view-target="firmware"]').click();
  await expect(page.locator("#searchInput")).toHaveValue("");
  await page.locator("#searchInput").fill("A firmware-only search");
  await page.locator('[data-view-target="phone"]').click();
  await expect(page.locator("#searchInput")).toHaveValue("Notice 7");
  await expect(page.locator("#announcementBody")).toHaveValue("Unsaved message\nSecond line");
  expect(data.writes).toHaveLength(0);
});

test("interaction announcements edit/create/delete use the existing API and cancel makes no write", async ({ page }) => {
  const data = await mockApp(page);
  data.announcements = [notice(1), notice(2)];
  await refreshApp(page);
  const releases = structuredClone(data.releases);
  await appTab(page, "announcements");
  await page.locator('[data-announcement-id="notice-1"]').click();
  await page.locator("#announcementBody").fill("Updated message");
  await page.locator("#saveAnnouncement").click();
  await expect(page.locator("#confirmDialog")).toBeVisible();
  await closeResult(page);
  expect(data.writes[0]).toEqual({ path: "/api/admin/announcements/notice-1",
    body: { appId: "trace", title: "Notice 1", body: "Updated message", pinned: false, published: true } });
  await expect(page.locator("#announcementDraftStatus")).toBeHidden();
  await page.locator("#deleteAnnouncement").click();
  await page.locator("#confirmCancel").click();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(data.writes).toHaveLength(1);
  await page.locator("#deleteAnnouncement").click();
  await confirm(page); await closeResult(page);
  expect(data.writes[1]).toEqual({ path: "/api/admin/announcements/notice-1/delete", body: {} });
  await page.locator("#newAnnouncement").click();
  await page.locator("#announcementTitle").fill("New message");
  await page.locator("#announcementBody").fill("New announcement body");
  await page.locator("#saveAnnouncement").click();
  await expect(page.locator("#confirmDialog")).toBeVisible(); await closeResult(page);
  expect(data.writes[2].path).toBe("/api/admin/announcements");
  expect(data.mutations).toBe(3);
  expect(data.releases).toEqual(releases);
  await expect(page.locator("#announcementTitle")).toHaveValue("New message");
});

test("interaction announcement failures retain edits without replay and actor changes clear local drafts", async ({ page }) => {
  const data = await mockApp(page);
  data.announcements = [notice(1)]; data.announcementFailure = true;
  await refreshApp(page); await appTab(page, "announcements");
  await page.locator('[data-announcement-id="notice-1"]').click();
  await page.locator("#announcementBody").fill("Keep after failed save");
  await page.locator("#saveAnnouncement").click();
  await expect(page.locator("#confirmDetail")).toContainText("BACKEND_UNAVAILABLE");
  await closeResult(page);
  await appTab(page, "releases"); await appTab(page, "announcements");
  await expect(page.locator("#announcementBody")).toHaveValue("Keep after failed save");
  expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(0);
  data.role = "viewer";
  await refreshApp(page);
  await expect(page.locator("#announcementBody")).toHaveValue("Message for announcement 1");
  await expect(page.locator("#announcementBody")).toBeDisabled();
  await expect(page.locator("#saveAnnouncement")).toBeDisabled();
  await expect(page.locator("#deleteAnnouncement")).toBeDisabled();
  await expect(page.locator("#announcementDraftStatus")).toBeHidden();
  expect(data.writes).toHaveLength(1);
});

for (const width of [1440, 390]) {
  test("interaction resource ball drag, click and saved position at " + width + "px", async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    const data = await mockApp(page);
    const ball = page.locator("#resourceOrb");
    const original = (await ball.boundingBox())!;
    const target = width > 720 ? { x: 700, y: 400 } : { x: 55, y: 230 };
    await page.mouse.move(original.x + original.width / 2, original.y + original.height / 2);
    await page.mouse.down();
    await page.mouse.move(target.x, target.y, { steps: 10 });
    await page.mouse.up();
    const placed = (await ball.boundingBox())!;
    expect(Math.abs(placed.x - original.x)).toBeGreaterThan(40);
    await expect(page.locator("#resourcePanel")).toBeHidden();
    await ball.click();
    await expect(page.locator("#resourcePanel")).toBeVisible();
    const panel = (await page.locator("#resourcePanel").boundingBox())!;
    expect(panel.x).toBeGreaterThanOrEqual(0); expect(panel.x + panel.width).toBeLessThanOrEqual(width);
    expect(panel.y).toBeGreaterThanOrEqual(0); expect(panel.y + panel.height).toBeLessThanOrEqual(844);
    await page.screenshot({ path: info.outputPath("restored-resource-ball-mock.png"), animations: "disabled" });
    await page.keyboard.press("Escape");
    await expect(ball).toBeFocused();
    await page.reload();
    await expect(page.locator("#refreshButton")).toBeEnabled();
    const restored = (await ball.boundingBox())!;
    expect(Math.abs(restored.x - placed.x)).toBeLessThan(1);
    expect(Math.abs(restored.y - placed.y)).toBeLessThan(1);
    await ball.focus();
    await page.keyboard.press("Shift+ArrowRight");
    expect((await ball.boundingBox())!.x).toBeGreaterThan(restored.x);
    expect(data.writes).toHaveLength(0);
  });
}

test("interaction invalid saved resource position is clamped and resize keeps it below sticky tools", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("trace-admin-resource-float-desktop", JSON.stringify({ left: 99999, top: -99999 })));
  const data = await mockApp(page);
  let ball = (await page.locator("#resourceOrb").boundingBox())!;
  let bar = (await page.locator(".topbar").boundingBox())!;
  expect(ball.x + ball.width).toBeLessThanOrEqual(1440);
  expect(ball.y).toBeGreaterThanOrEqual(bar.y + bar.height);
  await page.setViewportSize({ width: 390, height: 600 });
  ball = (await page.locator("#resourceOrb").boundingBox())!;
  bar = (await page.locator(".topbar").boundingBox())!;
  expect(ball.x + ball.width).toBeLessThanOrEqual(390);
  expect(ball.y + ball.height).toBeLessThanOrEqual(600);
  expect(ball.y).toBeGreaterThanOrEqual(bar.y + bar.height);
  expect(data.writes).toHaveLength(0);
});

test.describe("interaction touch resource control", () => {
  test.use({ hasTouch: true });
  test("touch drag does not open the panel and the next tap still works", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const data = await mockApp(page);
    const ball = (await page.locator("#resourceOrb").boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    try {
      await page.locator("#resourceOrb").tap();
      await expect(page.locator("#resourcePanel")).toBeVisible();
      await page.locator("#resourceClose").tap();
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: ball.x + 32, y: ball.y + 32 }] });
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: 180, y: 350 }] });
      await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
      await expect(page.locator("#resourcePanel")).toBeHidden();
      expect((await page.locator("#resourceOrb").boundingBox())!.x).toBeLessThan(ball.x - 40);
      await page.locator("#resourceOrb").tap();
      await expect(page.locator("#resourcePanel")).toBeVisible();
      await expect(page.locator("#resourceOrb")).toHaveAttribute("aria-expanded", "true");
      await page.locator("#resourceClose").tap();
      await expect(page.locator("#resourcePanel")).toBeHidden();
      await page.locator("#resourceOrb").focus();
      await page.keyboard.press("Enter");
      await expect(page.locator("#resourcePanel")).toBeVisible();
    } finally {
      await cdp.detach();
    }
    expect(data.writes).toHaveLength(0);
  });

  test("cancelled touch drag never activates the panel or consumes the next tap", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const data = await mockApp(page);
    const ball = (await page.locator("#resourceOrb").boundingBox())!;
    const cdp = await page.context().newCDPSession(page);
    try {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x: ball.x + 32, y: ball.y + 32 }] });
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x: 180, y: 350 }] });
      await cdp.send("Input.dispatchTouchEvent", { type: "touchCancel", touchPoints: [] });
      await expect(page.locator("#resourcePanel")).toBeHidden();
      await expect(page.locator("#storage")).not.toHaveClass(/dragging/);
      await page.locator("#resourceOrb").tap();
      await expect(page.locator("#resourcePanel")).toBeVisible();
      await expect(page.locator("#resourceOrb")).toHaveAttribute("aria-expanded", "true");
    } finally {
      await cdp.detach();
    }
    expect(data.writes).toHaveLength(0);
  });
});
