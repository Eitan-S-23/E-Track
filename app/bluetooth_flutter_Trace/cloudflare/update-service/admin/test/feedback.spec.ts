import { readFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";

async function mount(page: Page, role = "owner") {
  const origin = "https://feedback-admin.test";
  const errors: string[] = [], writes: Array<{ id: number; body: Record<string, unknown> }> = [];
  const data = { actor: "owner@example.test", role, fail: false, stale: false, hold: null as Promise<void> | null,
    rows: Array.from({ length: 25 }, (_, index) => ({ id: 25 - index, clientId: `message-${index}`, body: index === 0
      ? '<img src=x onerror="window.feedbackInjection=true"> literal text' : `Issue ${25 - index}`,
    receivedAt: 1794996000, clientCreatedAt: 1794995900, platform: "android", versionName: "1.0.82", versionCode: 108,
    status: "pending", note: "", revision: 1, updatedAt: 1794996000, updatedBy: "app" })) };
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem("trace-admin-language", "en"));
  await page.route("**/*", async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.origin !== origin) { await route.abort(); return; }
    const reply = (body: object, status = 200) => route.fulfill({ status, contentType: "application/json",
      headers: { "X-Request-Id": "feedback-fixture" }, body: JSON.stringify({ requestId: "feedback-fixture", ...body }) });
    if (url.pathname === "/") { await route.fulfill({ contentType: "text/html", body: readFileSync(new URL("../public/index.html", import.meta.url)) }); return; }
    if (/^\/[a-z-]+\.(js|css|svg|png|ico)$/.test(url.pathname)) {
      await route.fulfill({ contentType: url.pathname.endsWith(".js") ? "text/javascript" : url.pathname.endsWith(".css") ? "text/css" : "image/png",
        body: readFileSync(new URL("../public" + url.pathname, import.meta.url)) }); return;
    }
    if (url.pathname === "/api/admin/session") { await reply({ ok: true, actor: data.actor, role: data.role, appId: "trace", csrfToken: "feedback-csrf", environment: "MOCK" }); return; }
    if (url.pathname === "/api/admin/feedback") {
      let rows = data.rows.filter(row => (!url.searchParams.get("before") || row.id < Number(url.searchParams.get("before"))) &&
        (url.searchParams.get("status") === "all" || row.status === url.searchParams.get("status")) &&
        row.body.toLowerCase().includes((url.searchParams.get("q") ?? "").toLowerCase()));
      const cursor = rows.length > 20 ? rows[19].id : null; rows = rows.slice(0, 20);
      await reply({ ok: true, feedback: rows, nextCursor: cursor }); return;
    }
    if (url.pathname.startsWith("/api/admin/feedback/")) {
      const id = Number(url.pathname.split("/").at(-1)), row = data.rows.find(item => item.id === id)!;
      if (req.method() === "POST") {
        expect(req.headers()["x-csrf-token"]).toBe("feedback-csrf");
        const body = req.postDataJSON() as Record<string, unknown>; writes.push({ id, body });
        if (data.fail) { await reply({ ok: false, errorCode: "BACKEND_UNAVAILABLE", message: "fixture failure" }, 503); return; }
        if (data.stale || body.revision !== row.revision) { await reply({ ok: false, errorCode: "CAS_CONFLICT", message: "fixture conflict" }, 409); return; }
        Object.assign(row, body, { revision: row.revision + 1, updatedBy: data.actor });
      }
      const value = structuredClone(row);
      if (data.hold) await data.hold;
      await reply({ ok: true, feedback: value, history: value.revision > 1 ? [{ revision: value.revision,
        status: value.status, note: value.note, actor: value.updatedBy, createdAt: value.updatedAt }] : [] }); return;
    }
    if (url.pathname.endsWith("/delta/activity")) { await reply({ ok: true, actor: data.actor, scope: "own-jobs", jobs: [], notifications: [], unreadCount: 0, pushSubscriptions: [] }); return; }
    if (url.pathname.endsWith("/resource-usage")) { await reply({ ok: true, metrics: [], safeguards: {} }); return; }
    await reply({ ok: true, releases: [], channels: [], announcements: [], storage: null, firmwareReleases: [], firmwareChannels: [] });
  });
  await page.goto(origin); await expect(page.locator("#refreshButton")).toBeEnabled();
  await page.locator("#appFeedbackTab").click();
  await expect(page.locator("[data-feedback-id]")).toHaveCount(20);
  expect(errors).toEqual([]);
  return { data, writes, errors };
}

for (const width of [1440, 390]) test(`feedback read/process flow at ${width}px renders text safely`, async ({ page }, info) => {
  await page.setViewportSize({ width, height: 1000 }); const fixture = await mount(page);
  await page.locator('[data-feedback-id="25"]').click();
  await expect(page.locator("#feedbackBody")).toContainText("<img");
  await expect(page.locator("#feedbackBody img")).toHaveCount(0);
  await page.locator("#feedbackState").selectOption("processing");
  await page.locator("#feedbackNote").fill("Investigating the navigation issue");
  await page.locator("#feedbackSave").click();
  await expect(page.locator("#feedbackNotice")).toHaveText("Outcome saved");
  await expect(page.locator(".feedback-history")).toContainText("Investigating the navigation issue");
  expect(fixture.writes).toHaveLength(1); expect(fixture.writes[0].body.revision).toBe(1);
  await page.locator("#feedbackFilter").selectOption("processing");
  await expect(page.locator("[data-feedback-id]")).toHaveCount(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath("feedback.png"), animations: "disabled" });
  expect(fixture.errors).toEqual([]);
});

test("feedback pagination, query and viewer controls are bounded", async ({ page }) => {
  const fixture = await mount(page, "viewer");
  await page.locator("#feedbackMore").click(); await expect(page.locator("[data-feedback-id]")).toHaveCount(25);
  await page.locator("#searchInput").fill("Issue 3"); await expect(page.locator("[data-feedback-id]")).toHaveCount(1);
  await page.locator('[data-feedback-id="3"]').click();
  await expect(page.locator("#feedbackNote")).toBeDisabled(); await expect(page.locator("#feedbackSave")).toBeDisabled();
  expect(fixture.writes).toHaveLength(0);
});

test("failed saves and concurrent edits preserve operator drafts", async ({ page }) => {
  const fixture = await mount(page);
  await page.locator('[data-feedback-id="24"]').click(); await page.locator("#feedbackNote").fill("Keep this draft");
  fixture.data.fail = true; await page.locator("#feedbackSave").click();
  await expect(page.locator("#feedbackNotice")).toContainText("Save was not confirmed");
  await expect(page.locator("#feedbackNote")).toHaveValue("Keep this draft");
  fixture.data.fail = false; fixture.data.stale = true; await page.locator("#feedbackSave").click();
  await expect(page.locator("#feedbackNotice")).toContainText("changed elsewhere");
  await expect(page.locator("#feedbackNote")).toHaveValue("Keep this draft");
  await page.locator('[data-feedback-id="23"]').click(); await expect(page.locator("#confirmDialog")).toBeVisible();
  await page.locator("#confirmCancel").click(); await expect(page.locator("#feedbackNote")).toHaveValue("Keep this draft");
});

test("actor changes discard private drafts and ignore outstanding detail responses", async ({ page }) => {
  const fixture = await mount(page);
  let release!: () => void;
  fixture.data.hold = new Promise<void>(resolve => { release = resolve; });
  await page.locator('[data-feedback-id="24"]').click();
  await expect(page.locator("#feedbackNotice")).toContainText("Loading detail");
  fixture.data.actor = "another@example.test"; fixture.data.role = "viewer";
  await page.locator("#refreshButton").click(); await expect(page.locator("#refreshButton")).toBeEnabled();
  release(); fixture.data.hold = null;
  await expect(page.locator("#feedbackDetail")).toBeHidden();
  await page.locator('[data-feedback-id="23"]').click(); await expect(page.locator("#feedbackNote")).toBeDisabled();
  expect(fixture.errors).toEqual([]);
});
