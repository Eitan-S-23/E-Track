# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: firmware-ui.spec.ts >> en: retract boundary, reason, cancel and fresh confirmation
- Location: test/firmware-ui.spec.ts:147:3

# Error details

```
Error: expect(locator).toBeEnabled() failed

Locator:  locator('#confirmAccept')
Expected: enabled
Received: disabled
Timeout:  5000ms

Call log:
  - Expect "toBeEnabled" locator('#confirmAccept') with timeout 5000ms
  - waiting for locator('#confirmAccept')
    14 × locator resolved to <button disabled type="button" id="confirmAccept" data-i18n="dialog.confirm" class="confirm-button stable">Retract</button>
       - unexpected value "disabled"

```

```yaml
- button "Retract" [disabled]
```

# Test source

```ts
  37  |     const reply = (body: object, status = 200, id = requestId) => route.fulfill({ status,
  38  |       contentType: "application/json", headers: { "X-Request-Id": id }, body: JSON.stringify(body) });
  39  |     const fail = (errorCode: string, status: number) => reply({ errorCode, message: `Mock ${errorCode}`, requestId }, status);
  40  |     data.events.push(`${request.method()} ${url.pathname}`);
  41  |     if (request.method() === "GET") {
  42  |       if (url.pathname === "/api/admin/session") {
  43  |         await reply({ ok: true, appId: "trace", environment: "MOCK", actor: data.actor, role: data.role, csrfToken: "mock-csrf" }); return;
  44  |       }
  45  |       if (url.pathname.startsWith("/api/admin/firmware/")) {
  46  |         if (data.failReads) { await fail("BACKEND_UNAVAILABLE", 503); return; }
  47  |         expect([...url.searchParams.keys()].sort()).toEqual(["appId", "deviceModel"]);
  48  |         expect(url.searchParams.get("deviceModel")).toBe(scope.deviceModel);
  49  |         published();
  50  |         await reply(url.pathname.endsWith("/channels") ? { ok: true, requestId, firmwareChannels: data.channels }
  51  |           : { ok: true, requestId, firmwareReleases: data.releases }); return;
  52  |       }
  53  |       await reply({ ok: true, channels: [], releases: [], announcements: [], storage: null }); return;
  54  |     }
  55  |     expect(request.method()).toBe("POST");
  56  |     expect(request.headers()["accept"]).toBe("application/json");
  57  |     expect(request.headers()["content-type"]).toBe("application/json");
  58  |     expect(request.headers()["x-csrf-token"]).toBe("mock-csrf");
  59  |     const body = request.postDataJSON() as Record<string, unknown>;
  60  |     expect(typeof body.reason).toBe("string");
  61  |     expect(String(body.reason).trim()).not.toBe("");
  62  |     expect(body.appId).toBe("trace"); expect(body.deviceModel).toBe(scope.deviceModel);
  63  |     data.writes.push({ path: url.pathname, body, key: request.headers()["idempotency-key"] });
  64  |     const segments = url.pathname.split("/"); const name = segments[5]; const action = segments[6];
  65  |     if (segments[4] === "channels") {
  66  |       const channel = data.channels.find(c => c.channel === name)!;
  67  |       const pointer = action === "publish" || action === "retract";
  68  |       const keys = ["appId", "deviceModel", "expectedRevision", "reason", ...(pointer ? ["releaseId"] : []),
  69  |         ...(Object.hasOwn(body, "maintenanceMessage") ? ["maintenanceMessage"] : [])].sort();
  70  |       expect(Object.keys(body).sort()).toEqual(keys);
  71  |       if (action.startsWith("resume")) expect(body).not.toHaveProperty("maintenanceMessage");
  72  |       if (data.mode === "conflict") { channel.revision++; data.mode = "normal"; await fail("CAS_CONFLICT", 409); return; }
  73  |       if (body.expectedRevision !== channel.revision) { await fail("CAS_CONFLICT", 409); return; }
  74  |       if (pointer) channel.currentReleaseId = String(body.releaseId);
  75  |       if (action.endsWith("latest")) channel.disableLatest = action.startsWith("stop");
  76  |       if (action.endsWith("downloads")) channel.disableDownloads = action.startsWith("stop");
  77  |       if (typeof body.maintenanceMessage === "string") channel.maintenanceMessage = body.maintenanceMessage;
  78  |       if (action.startsWith("resume") && !channel.disableLatest && !channel.disableDownloads) channel.maintenanceMessage = null;
  79  |       channel.revision++; data.mutations++; published();
  80  |       if (data.mode === "unknown-channel") { data.mode = "normal"; await route.abort("failed"); return; }
  81  |       if (data.mode === "refresh-failure") data.failReads = true;
  82  |       await reply({ ok: true, requestId, action: action.replaceAll("-", "_"), channel: name,
  83  |         revision: channel.revision, currentReleaseId: channel.currentReleaseId, disableLatest: channel.disableLatest,
  84  |         disableDownloads: channel.disableDownloads, maintenanceMessage: channel.maintenanceMessage, idempotent: false }); return;
  85  |     }
  86  |     expect(segments[4]).toBe("releases");
  87  |     expect(Object.keys(body).sort()).toEqual(["appId", "deviceModel", "reason"]);
  88  |     const key = request.headers()["idempotency-key"];
  89  |     expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  90  |     const fingerprint = JSON.stringify({ path: url.pathname, body });
  91  |     if (data.releaseFailure) {
  92  |       const failure = data.releaseFailure;
  93  |       await reply({ errorCode: failure.code, message: `Mock ${failure.code}`,
  94  |         ...(failure.correlation === "missing" ? {} : { requestId }) }, failure.status,
  95  |       failure.correlation === "mismatch" ? "mismatched-error-request" : requestId);
  96  |       return;
  97  |     }
  98  |     const existing = data.results.get(key);
  99  |     if (existing) {
  100 |       if (existing.fingerprint !== fingerprint) { await fail("IDEMPOTENCY_CONFLICT", 409); return; }
  101 |       if (data.expireReplay) { await fail("IDEMPOTENCY_RESULT_EXPIRED", 409); return; }
  102 |       await reply({ ...existing.result, idempotent: true }, 200, String(existing.result.requestId)); return;
  103 |     }
  104 |     const target = data.releases.find(r => r.releaseId === name)!;
  105 |     let result: Record<string, unknown>;
  106 |     if (action === "disable") {
  107 |       if (target.publishedChannels.length) { await fail("RELEASE_IN_USE", 409); return; }
  108 |       target.state = "disabled";
  109 |       result = { ok: true, requestId, action: "disable_release", releaseId: name, state: "disabled", idempotent: false };
  110 |     } else {
  111 |       expect(action).toBe("recovery-download");
  112 |       const asset = target.assets.find(a => a.kind === "recovery")!; const expiresAt = Math.floor(Date.now() / 1000) + 300;
  113 |       const query = new URLSearchParams({ tokenVersion: "2", assetId: asset.assetId, releaseId: name,
  114 |         kind: "recovery", purpose: "admin-recovery", expiresAt: String(expiresAt), keyVersion: "mock", signature: "mock-only-not-a-real-signature" });
  115 |       result = { ok: true, requestId, action: "issue_recovery_download", releaseId: name,
  116 |         assetId: asset.assetId, kind: asset.kind, fileName: asset.fileName, sha256: asset.sha256, sizeBytes: asset.sizeBytes,
  117 |         expiresAt, downloadUrl: `https://p43-download.test/api/public/firmware/download?${query}`, idempotent: false };
  118 |     }
  119 |     data.mutations++; data.results.set(key, { fingerprint, result });
  120 |     if (data.mode === "unknown-release") { data.mode = "normal"; await route.abort("failed"); return; }
  121 |     await reply(result);
  122 |   });
  123 |   await page.goto(origin, { waitUntil: "domcontentloaded" });
  124 |   await expect(page.locator("#firmwareReleaseList .firmware-release-card")).toHaveCount(3);
  125 |   if ((page.viewportSize()?.width ?? 1440) < 700) await page.locator("#mobileMenu").click();
  126 |   await page.locator('[data-view-target="firmware"]').click();
  127 |   return data;
  128 | }
  129 | 
  130 | const channelButton = (page: Page, channel: string, action: string) => page.locator(
  131 |   `.firmware-channel-card[data-channel="${channel}"] [data-firmware-action="${action}"]`);
  132 | const releaseButton = (page: Page, id: string, action: string) => page.locator(
  133 |   `.firmware-release-card[data-release-id="${id}"] [data-firmware-action="${action}"]`);
  134 | async function fillConfirmation(page: Page, reason = " browser operator reason ") {
  135 |   if (await page.locator("#confirmInput").isVisible()) await page.locator("#confirmInput").fill("stable");
  136 |   if (await page.locator("#confirmReason").isVisible()) await page.locator("#confirmReason").fill(reason);
> 137 |   await expect(page.locator("#confirmAccept")).toBeEnabled();
      |                                                ^ Error: expect(locator).toBeEnabled() failed
  138 |   await page.locator("#confirmAccept").click();
  139 | }
  140 | async function closeResult(page: Page) {
  141 |   await page.locator("#confirmAccept").click();
  142 |   await expect(page.locator("#confirmDialog")).toBeHidden();
  143 |   await expect(page.locator("#refreshButton")).toBeEnabled();
  144 | }
  145 | 
  146 | for (const language of ["en", "zh"]) {
  147 |   test(`${language}: retract boundary, reason, cancel and fresh confirmation`, async ({ page }, info) => {
  148 |     const data = await mockAdmin(page, language);
  149 |     await expect(page.locator("#firmwareView")).not.toContainText("undefined");
  150 |     await releaseButton(page, "fw-old", "select").click();
  151 |     await page.screenshot({ path: info.outputPath(`${language}-mock-overview.png`), fullPage: true });
  152 |     await channelButton(page, "stable", "retract").click();
  153 |     await expect(page.locator("#confirmDetail")).toContainText(language === "zh" ? "已升级设备不会降级" : "Upgraded devices will not downgrade");
  154 |     await expect(page.locator("#confirmDetail")).toContainText("versionCode");
  155 |     await page.locator("#confirmInput").fill("stable");
  156 |     await expect(page.locator("#confirmAccept")).toBeDisabled();
  157 |     await page.locator("#confirmReason").fill("   ");
  158 |     await expect(page.locator("#confirmAccept")).toBeDisabled();
  159 |     await page.locator("#confirmReason").fill("operator cancellation fixture");
  160 |     await page.screenshot({ path: info.outputPath(`${language}-mock-confirm.png`), fullPage: true });
  161 |     await page.locator("#confirmCancel").click();
  162 |     await expect(page.locator("#confirmDialog")).toBeHidden();
  163 |     expect(data.writes).toHaveLength(0); expect(data.mutations).toBe(0);
  164 |     await page.screenshot({ path: info.outputPath(`${language}-mock-cancel.png`), fullPage: true });
  165 |     await channelButton(page, "stable", "retract").click();
  166 |     await fillConfirmation(page);
  167 |     await expect(page.locator("#confirmTitle")).toHaveText(language === "zh" ? "固件操作已确认" : "Firmware operation confirmed");
  168 |     expect(data.writes).toHaveLength(1);
  169 |     expect(data.writes[0].body).toEqual({ ...scope, releaseId: "fw-old", expectedRevision: 7, reason: " browser operator reason " });
  170 |     await page.screenshot({ path: info.outputPath(`${language}-mock-success.png`), fullPage: true });
  171 |     await closeResult(page);
  172 |     expect(data.channels[0].currentReleaseId).toBe("fw-old");
  173 |     expect(data.releases.find(r => r.releaseId === "fw-old")!.state).toBe("ready");
  174 |   });
  175 |   test(`${language}: CAS refresh never replays an old intent`, async ({ page }, info) => {
  176 |     const data = await mockAdmin(page, language); data.mode = "conflict";
  177 |     await releaseButton(page, "fw-old", "select").click();
  178 |     await channelButton(page, "stable", "retract").click(); await fillConfirmation(page);
  179 |     await expect(page.locator("#confirmMessage")).toContainText(language === "zh" ? "再次确认" : "confirm again");
  180 |     await page.screenshot({ path: info.outputPath(`${language}-mock-conflict.png`), fullPage: true });
  181 |     expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(0);
  182 |     await closeResult(page);
  183 |     await channelButton(page, "stable", "retract").click();
  184 |     await expect(page.locator("#confirmMessage")).toContainText("8");
  185 |     await expect(page.locator("#confirmReason")).toHaveValue("");
  186 |     expect(data.writes).toHaveLength(1);
  187 |     await fillConfirmation(page, "new confirmed intent");
  188 |     await expect(page.locator("#confirmTitle")).toHaveText(language === "zh" ? "固件操作已确认" : "Firmware operation confirmed");
  189 |     expect(data.writes[1].body.expectedRevision).toBe(8); expect(data.mutations).toBe(1);
  190 |   });
  191 | }
  192 | 
  193 | test("beta publisher controls are independent and stable/release actions stay owner-only", async ({ page }) => {
  194 |   const data = await mockAdmin(page, "en", "publisher");
  195 |   await expect(channelButton(page, "stable", "stop-latest")).toBeDisabled();
  196 |   await expect(releaseButton(page, "fw-new", "disable")).toBeDisabled();
  197 |   await expect(releaseButton(page, "fw-new", "recovery-download")).toBeDisabled();
  198 |   await channelButton(page, "beta", "stop-downloads").click();
  199 |   await expect(page.locator("#confirmInput")).toBeHidden();
  200 |   await page.locator("#confirmMaintenance").fill("download incident"); await fillConfirmation(page);
  201 |   await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed"); await closeResult(page);
  202 |   expect(data.channels[1]).toMatchObject({ disableLatest: false, disableDownloads: true });
  203 |   await channelButton(page, "beta", "resume-downloads").click();
  204 |   await expect(page.locator("#confirmMaintenance")).toBeHidden(); await fillConfirmation(page);
  205 |   await expect(page.locator("#confirmTitle")).toHaveText("Firmware operation confirmed");
  206 |   expect(data.writes[1].body).not.toHaveProperty("maintenanceMessage");
  207 | });
  208 | 
  209 | test("viewer and unavailable/reference-protected releases cannot write", async ({ page }) => {
  210 |   const data = await mockAdmin(page, "en", "viewer");
  211 |   await expect(channelButton(page, "beta", "stop-downloads")).toBeDisabled();
  212 |   await expect(releaseButton(page, "fw-new", "publish").first()).toBeDisabled();
  213 |   expect(data.writes).toHaveLength(0);
  214 |   data.role = "owner"; data.actor = "owner@example.test";
  215 |   data.releases[0].state = "draft"; data.releases[2].archived = true;
  216 |   await page.locator("#refreshButton").click();
  217 |   await expect(releaseButton(page, "fw-new", "publish").first()).toBeDisabled();
  218 |   await expect(releaseButton(page, "fw-old", "disable")).toBeDisabled();
  219 |   await expect(releaseButton(page, "fw-current", "disable")).toBeDisabled();
  220 | });
  221 | 
  222 | test("unknown channel result is read back but never automatically repeated", async ({ page }) => {
  223 |   const data = await mockAdmin(page); data.mode = "unknown-channel";
  224 |   await channelButton(page, "beta", "stop-latest").click(); await fillConfirmation(page);
  225 |   await expect(page.locator("#confirmMessage")).toContainText("network result is unknown");
  226 |   expect(data.writes).toHaveLength(1); expect(data.mutations).toBe(1);
  227 |   expect(data.events.at(-1)).toMatch(/^GET /);
  228 |   await closeResult(page);
  229 |   await expect(channelButton(page, "beta", "resume-latest")).toBeEnabled();
  230 |   expect(data.writes).toHaveLength(1);
  231 | });
  232 | 
  233 | test("unknown release result uses an explicit same-key/same-body reconciliation after reads", async ({ page }) => {
  234 |   const data = await mockAdmin(page); data.mode = "unknown-release";
  235 |   await releaseButton(page, "fw-new", "recovery-download").click(); await fillConfirmation(page, "original recovery reason");
  236 |   await expect(page.locator("#confirmMessage")).toContainText("network result is unknown"); await closeResult(page);
  237 |   expect(data.writes).toHaveLength(1);
```