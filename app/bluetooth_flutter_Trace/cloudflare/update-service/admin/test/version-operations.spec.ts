import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { test, expect, type Page } from "@playwright/test";

const origin="https://version-operations.test";
const html=readFileSync(new URL("../public/index.html",import.meta.url),"utf8").replace("<body>",
  '<body><div style="position:fixed;bottom:4px;left:4px;z-index:10000;background:#fff2b0;padding:4px;font:11px monospace;pointer-events:none">MOCK UI / NO DEVICE OR CLOUD OPERATIONS</div>');
const css=readFileSync(new URL("../public/admin.css",import.meta.url),"utf8");
const hash="a".repeat(64);
type Job={id:string;baseReleaseId:string;baseVersionCode:number;targetVersionCode:number;status:string;enabled:boolean;revision:number;sizeBytes:number;runUrl:string;fileName:string;
  kind?:string;targetReleaseId?:string;phase?:string;createdAt?:number;updatedAt?:number;attempt?:number;
  ci?:{phase:string;approvalEnvironments:string[];errorCode?:string;checkedAt?:number}};

export async function setup(page:Page,language="zh",role="owner",push?:{publicKey:string;subscriptions:Array<{id:string;expiresAt:number}>}) {
  const data={role,dispatchConfigured:true,inventoryFails:false,abortCreate:false,inventoryReads:0,
    csrfToken:"version-csrf",sessionReads:0,sessionFails:false,sessionGate:null as Promise<void>|null,
    mutationAttempts:0,csrfRejections:0,rejectCsrf:false,
    refreshRequestedAt:0,refreshId:"initial",baseCount:4,jobs:[] as Job[],writes:[] as Array<{path:string;body:Record<string,unknown>}>,
    notifications:[] as Array<Record<string,unknown>>,unreadCount:0,activityReads:0,activityFails:false,pushPublicKey:null as string|null,
    pushSubscriptions:[] as Array<{id:string;expiresAt:number}>,pushRegisterFails:false,readFails:false,
    readGate:null as Promise<void>|null,activityGate:null as Promise<void>|null,createGate:null as Promise<void>|null,catalogueGate:null as Promise<void>|null};
  if(push){data.pushPublicKey=push.publicKey;data.pushSubscriptions=push.subscriptions;}
  await page.addInitScript(lang=>localStorage.setItem("trace-admin-language",lang),language);
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  let serial=0;
  await page.route("**/*",async route=>{
    const request=route.request(),url=new URL(request.url()),requestId=`operation-${++serial}`;
    if(url.origin!==origin){await route.abort();return;}
    if(url.pathname==="/"){await route.fulfill({contentType:"text/html",body:html});return;}
    if(url.pathname==="/admin.css"){await route.fulfill({contentType:"text/css",body:css});return;}
    if (["/sheet-gestures.js","/overlay-history.js","/delta-activity.js","/resource-usage.js"].includes(url.pathname)) {
      await route.fulfill({contentType:"text/javascript",body:readFileSync(new URL("../public"+url.pathname,import.meta.url),"utf8")}); return;
    }
    const reply=(body:object,status=200,headers:Record<string,string>={})=>route.fulfill({status,contentType:"application/json",headers:{"X-Request-Id":requestId,...headers},body:JSON.stringify({requestId,...body})});
    if(request.method()==="GET") {
      if(url.pathname==="/api/admin/channels" && data.catalogueGate) await data.catalogueGate;
      if(url.pathname==="/api/admin/delta/activity") {
        data.activityReads++;
        if(data.activityFails){await reply({ok:false,message:"Activity unavailable"},503);return;}
        const snapshot={ok:true,actor:`${data.role}@example.test`,scope:"own-jobs",jobs:structuredClone(data.jobs),notifications:structuredClone(data.notifications),
          unreadCount:data.unreadCount,pushPublicKey:data.pushPublicKey,pushSubscriptions:[...data.pushSubscriptions]};
        if(data.activityGate) await data.activityGate;
        await reply(snapshot);return;
      }
      if(url.pathname==="/api/admin/session") {
        data.sessionReads++;
        if(data.sessionGate) await data.sessionGate;
        if(data.sessionFails){await reply({ok:false,errorCode:"BACKEND_UNAVAILABLE",message:"Session unavailable"},503);return;}
        await reply({ok:true,role:data.role,actor:`${data.role}@example.test`,csrfToken:data.csrfToken,appId:"trace",environment:"MOCK"},200,
          {"Set-Cookie":`trace_admin_csrf=${data.csrfToken}; Path=/api/admin; HttpOnly; Secure; SameSite=Strict; Max-Age=3600`});return;
      }
      if(url.pathname==="/api/admin/version-inventory") {
        data.inventoryReads++;
        if(data.inventoryFails){await reply({ok:false,errorCode:"BACKEND_UNAVAILABLE",message:"inventory unavailable"},503);return;}
        const rows=Array.from({length:23},(_,index)=>({versionCode:99-index,versionName:`1.0.${99-index}`,imageSha256:index===0?hash:"b".repeat(64),
          active7:index===0?20:0,active30:index===0?40:0,active90:index===0?50:2,lastSeen:1794409200-index*86400}));
        await reply({ok:true,coverage:"reporting-installations-only",firmwareIdentityScope:"installation",uniqueDeviceCount:null,app:rows,firmware:rows,
          generatedAt:1794410000,refreshId:data.refreshId,refreshRequestedAt:data.refreshRequestedAt,refreshResponses:0});return;
      }
      if(url.pathname==="/api/admin/delta/candidates") {
        const kind=url.searchParams.get("kind"),targetId=url.searchParams.get("targetId");
        await reply({ok:true,kind,target:{releaseId:targetId,versionName:"1.0.74",versionCode:100,fullBytes:1000000},
          dispatchConfigured:data.dispatchConfigured,appSigningConfigured:true,distributionEnabled:true,
          bases:Array.from({length:data.baseCount},(_,index)=>({releaseId:`base-${index}`,versionName:`1.0.${99-index}`,versionCode:99-index,
            imageSha256:index===0?hash:"c".repeat(64),eligible:index!==3,reason:index===3?"hardware mismatch":undefined,existing:index===2,
            job:data.jobs.find(job=>job.baseReleaseId===`base-${index}`)??null})),jobs:data.jobs});return;
      }
      if(url.pathname.startsWith("/api/admin/firmware/")) {
        await reply({ok:true,firmwareChannels:[],firmwareReleases:[{appId:"trace",deviceModel:"e-track-at32f435",releaseId:"fw-target",versionName:"3.3.24",versionCode:30324,
          releaseTag:"mcu-e-track-at32f435-v3.3.24",state:"ready",archived:false,releaseNotes:"Original fixture",targetImageSha256:hash,publishedChannels:[],
          hardwareRevision:1,layoutId:1,minBootVersion:1,minAppVersionCode:86,minProtocolVersion:1,transport:"ble",assets:[{assetId:"full",kind:"full",fileName:"full.etu",
            sha256:hash,sizeBytes:100000,r2State:"available",baseVersionCode:0,baseImageSha256:""}]}]});return;
      }
      await reply({ok:true,channels:[],announcements:[],storage:null,releases:[{id:"app-target",app_id:"trace",platform:"android",version_code:100,version_name:"1.0.74",
        release_tag:"v1.0.74",state:"candidate",archived:0,release_notes:"Original App fixture",asset_count:2,r2_available_count:2,apk_count:1,manifest_count:1,patch_count:0}]});return;
    }
    expect(request.method()).toBe("POST");data.mutationAttempts++;
    const cookie=(await request.headerValue("cookie"))?.split(";").map(part=>part.trim())
      .find(part=>part.startsWith("trace_admin_csrf="))?.slice("trace_admin_csrf=".length);
    if(data.rejectCsrf || !cookie || cookie!==data.csrfToken || request.headers()["x-csrf-token"]!==cookie) {
      data.csrfRejections++;await reply({ok:false,errorCode:"TOKEN_INVALID",message:"CSRF token is invalid"},403);return;
    }
    expect(request.headers()["x-csrf-token"]).toBe(data.csrfToken);
    expect(request.headers()["content-type"]).toBe("application/json");
    const body=request.postDataJSON() as Record<string,unknown>;
    data.writes.push({path:url.pathname,body});
    if(url.pathname==="/api/admin/delta/notifications/subscribe") {
      if(data.pushRegisterFails){await reply({ok:false,errorCode:"BACKEND_UNAVAILABLE",message:"Subscription registration unavailable"},503);return;}
      const entry={id:createHash("sha256").update(String(body.endpoint)).digest("hex"),expiresAt:Math.floor(Date.now()/1000)+86400};
      data.pushSubscriptions=[entry];await reply({ok:true,...entry});return;
    }
    if(url.pathname==="/api/admin/delta/notifications/unsubscribe") {
      data.pushSubscriptions=data.pushSubscriptions.filter(row=>row.id!==body.id);await reply({ok:true});return;
    }
    if(url.pathname==="/api/admin/delta/notifications/read") {
      if(data.readGate) await data.readGate;
      if(data.readFails){await reply({ok:false,message:"Read acknowledgement unavailable"},503);return;}
      const readIds:number[]=[];
      for(const n of data.notifications) if(Array.isArray(body.ids)?body.ids.includes(n.id):Number(n.id)<=Number(body.throughId)) {
        if(n.unread) data.unreadCount--;n.unread=0;readIds.push(Number(n.id));
      }
      await reply(Array.isArray(body.ids)?{ok:true,readIds}:{ok:true,throughId:body.throughId});return;
    }
    if(url.pathname==="/api/admin/version-inventory/refresh") {
      expect(String(body.requestId)).toMatch(/^[0-9a-f-]{36}$/);data.refreshId=String(body.requestId);data.refreshRequestedAt=Math.floor(Date.now()/1000);
      await reply({ok:true,refreshId:data.refreshId});return;
    }
    if(url.pathname==="/api/admin/delta/jobs") {
      if(data.createGate) await data.createGate;
      expect(body.kind).toMatch(/^(android|firmware)$/);expect(String(body.reason).trim()).not.toBe("");
      data.jobs=(body.baseReleaseIds as string[]).map((id,index)=>({id:`delta-${index}`,baseReleaseId:id,baseVersionCode:99-index,targetVersionCode:100,
        status:data.abortCreate?"dispatch_unknown":"queued",enabled:false,revision:1,sizeBytes:5000,runUrl:`https://github.com/Eitan-S-23/${body.kind==="android"?"Trace":"E-Track"}/actions/runs/123456`,fileName:"delta.vcdiff",
        kind:String(body.kind),targetReleaseId:String(body.targetReleaseId),createdAt:Math.floor(Date.now()/1000),updatedAt:Math.floor(Date.now()/1000)}));
      if(data.abortCreate){await route.abort("failed");return;}
      await reply({ok:true,jobs:data.jobs});return;
    }
    expect(url.pathname).toMatch(/^\/api\/admin\/delta\/jobs\/[^/]+\/(enable|disable|retry|reconcile)$/);
    const job=data.jobs.find(job=>job.id===url.pathname.split("/")[5])!;
    expect(body.expectedRevision).toBe(job.revision);
    const action=url.pathname.split("/").at(-1);
    if(action==="enable"||action==="disable") job.enabled=action==="enable";
    if(action==="retry") job.status="queued";
    if(action==="reconcile") job.status="failed";
    job.revision++;
    await reply({ok:true,job});
  });
  await page.goto(origin,{waitUntil:"domcontentloaded"});
  await expect(page.locator("#refreshButton")).toBeEnabled();
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(1);
  return {data,errors};
}

for (const kind of ["android","firmware"]) {
  test(`candidate arrival ${kind} shows once and opens registered release details, not delta creation`,async({page})=>{
    const {data,errors}=await setup(page);
    await page.evaluate("state.appSection='inventory';state.firmwareSection='inventory';applyAppSection();applyFirmwareSection()");
    data.notifications=[{id:101,type:"candidate",kind,targetReleaseId:kind==="android"?"app-target":"fw-target",
      versionName:kind==="android"?"1.0.74":"3.3.24",targetVersionCode:kind==="android"?100:30324,status:"ready",createdAt:Math.floor(Date.now()/1000),unread:1}];
    data.unreadCount=1;
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#taskToast")).toContainText("新构建包已入库");
    await expect(page.locator("#taskToast")).toContainText(String(data.notifications[0].versionName));
    await page.locator("#taskToast button").click();
    await page.locator('[data-notification-id="101"]').click();
    await expect(page.locator(kind==="android"?"#quickActionSheet":"#firmwareDetailSheet")).toBeVisible();
    await expect(page.locator("#deltaSheet")).toBeHidden();
    expect(data.writes.every(row=>row.path.endsWith("/notifications/read"))).toBe(true);
    expect(errors).toEqual([]);
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#taskToast")).toBeHidden();
  });
}

test("candidate arrivals wait behind a dialog without stealing focus or losing the unread result",async({page})=>{
  const {data,errors}=await setup(page);
  await page.evaluate("void openResultDialog({title:'Active dialog',message:'Do not interrupt'})");
  await expect(page.locator("#confirmAccept")).toBeFocused();
  const focus=await page.evaluate("document.activeElement.id");
  data.notifications=[{id:102,type:"candidate",kind:"firmware",targetReleaseId:"fw-target",versionName:"3.3.24",status:"ready",createdAt:Math.floor(Date.now()/1000),unread:1}];
  data.unreadCount=1;await page.evaluate("taskActivity.refresh()");
  await expect(page.locator("#taskToast")).toBeHidden();
  expect(await page.evaluate("document.activeElement.id")).toBe(focus);
  expect(data.unreadCount).toBe(1);
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#taskToast")).toContainText("3.3.24");
  expect(errors).toEqual([]);
});

test("candidate detail lookup failure does not pretend to open a release or submit a build",async({page})=>{
  const {data,errors}=await setup(page);
  data.notifications=[{id:103,type:"candidate",kind:"android",targetReleaseId:"removed",versionName:"old",status:"ready",createdAt:Math.floor(Date.now()/1000),unread:1}];
  data.unreadCount=1;await page.evaluate("taskActivity.refresh()");
  await page.locator("#taskButton").click();await page.locator('[data-notification-id="103"]').click();
  await expect(page.locator("#taskContent")).toContainText("此构建包已移除");
  await expect(page.locator("#quickActionSheet")).toBeHidden();
  expect(data.writes.every(row=>row.path.endsWith("/notifications/read"))).toBe(true);expect(errors).toEqual([]);
});

test("provider usage is loaded on demand and distinguishes zero, unavailable and stale data on mobile",async({page})=>{
  const {errors}=await setup(page);await page.setViewportSize({width:360,height:760});
  let calls=0,fail=false;
  const now=Math.floor(Date.now()/1000);
  await page.route("**/api/admin/resource-usage",async route=>{
    calls++;
    if(fail){await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({message:"Offline"})});return;}
    await route.fulfill({contentType:"application/json",body:JSON.stringify({ok:true,checkedAt:now,nextRefreshAt:now+900,
      safeguards:{clientReportsPerUtcDay:8,backendReportsPerUtcDay:1000},metrics:[
        {key:"workerRequests",group:"workers",used:0,unit:"requests",state:"ok",scope:"test-worker",periodStart:now-3600,periodEnd:now-300,periodRolloverAt:now+3600,lastSuccessAt:now,sampledAt:null},
        {key:"workerCpu",group:"workers",used:null,unit:"ms",state:"permission_denied",scope:"test-worker",periodStart:now-3600,periodEnd:now-300,lastSuccessAt:null,sampledAt:null}
      ]})});
  });
  expect(calls).toBe(0);await page.locator("#resourceOrb").click();
  await expect(page.locator('[data-usage-key="workerRequests"] strong')).toHaveText("0 requests");
  await expect(page.locator('[data-usage-key="workerCpu"]')).toContainText("无读取权限");
  await expect(page.locator('[data-usage-key="workerCpu"] strong')).toHaveText("未知");
  await expect(page.locator("#providerUsage")).toContainText("套餐、额度及剩余：未知");
  await expect(page.locator("#providerUsage")).toContainText("GitHub Actions");
  expect(await page.locator("#resourcePanel").evaluate(node=>node.scrollWidth<=node.clientWidth+1)).toBe(true);
  fail=true;await page.locator("[data-usage-refresh]").click();
  await expect(page.locator('[data-usage-key="workerRequests"]')).toHaveAttribute("data-state","stale");
  await expect(page.locator('[data-usage-key="workerRequests"] strong')).toHaveText("0 requests");
  expect(errors).toEqual([]);
});
export async function firmwareView(page:Page) {
  if(await page.locator("#mobileMenu").isVisible()) await page.locator("#mobileMenu").click();
  await page.locator('[data-view-target="firmware"]').click();
}
export async function openDelta(page:Page,kind="android") {
  if(kind==="firmware") {
    await firmwareView(page);
    await page.locator('#firmwareReleaseList [data-firmware-action="select"]').click();
    await page.locator('[data-firmware-action="delta"]').click();
  } else {
    await page.locator('#versionStrip [data-release-id="app-target"]').click();
    await page.locator('[data-action="delta"]').click();
  }
  await expect(page.locator("#deltaSheet")).toBeVisible();
  await expect(page.locator('[data-delta-base="base-0"]')).toBeVisible();
}
async function dismissError(page:Page) {
  await expect(page.locator('#confirmDialog[role="alertdialog"]')).toBeVisible();
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmDialog")).toBeHidden();
}
async function confirm(page:Page,reason=false,failure=false) {
  await expect(page.locator("#confirmDialog")).toBeVisible();
  if(reason) await page.locator("#confirmReason").fill("Operator selected this action");
  await page.locator("#confirmAccept").click();
  if (failure) await dismissError(page);
  await expect(page.locator("#confirmDialog")).toBeHidden();
}

for(const kind of ["android","firmware"]) for(const condition of ["expiry","another tab"]) {
  test(`CSRF ${condition} refreshes ${kind} before submitting the confirmed delta exactly once`,async({page})=>{
    const {data,errors}=await setup(page);await openDelta(page,kind);
    await page.locator('[data-delta-base="base-0"]').check();
    await page.locator("#deltaReason").fill("Keep this confirmed delta selection");
    data.csrfToken="renewed-csrf";
    if(condition==="expiry") await page.context().clearCookies({name:"trace_admin_csrf"});
    else await page.context().addCookies([{name:"trace_admin_csrf",value:data.csrfToken,domain:new URL(origin).hostname,
      path:"/api/admin",httpOnly:true,secure:true,sameSite:"Strict"}]);
    const reads=data.sessionReads;
    await page.locator('[data-version-operation="delta-create"]').click();await confirm(page);
    await expect.poll(()=>data.writes.length).toBe(1);
    expect(data.sessionReads).toBe(reads+1);expect(data.mutationAttempts).toBe(1);expect(data.csrfRejections).toBe(0);
    expect(data.writes[0]).toEqual({path:"/api/admin/delta/jobs",body:{kind,targetReleaseId:kind==="android"?"app-target":"fw-target",
      baseReleaseIds:["base-0"],reason:"Keep this confirmed delta selection"}});
    expect(data.jobs).toHaveLength(1);expect(errors).toEqual([]);
  });
}

test("CSRF refresh failure sends no mutation and retains the draft for an explicit new confirmation",async({page})=>{
  const {data,errors}=await setup(page);await openDelta(page,"firmware");
  await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Retain this firmware request");
  data.sessionFails=true;
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page,false,true);
  await expect(page.locator("#deltaSheet")).toContainText("Session unavailable");
  await expect(page.locator('[data-version-operation="delta-create"]')).toBeEnabled();
  expect(data.mutationAttempts).toBe(0);expect(data.writes).toHaveLength(0);
  await expect(page.locator('[data-delta-base="base-0"]')).toBeChecked();
  await expect(page.locator("#deltaReason")).toHaveValue("Retain this firmware request");
  data.sessionFails=false;
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page);
  await expect.poll(()=>data.writes.length).toBe(1);expect(data.mutationAttempts).toBe(1);expect(errors).toEqual([]);
});

test("CSRF rejection after refresh is not replayed and does not consume the selected base",async({page})=>{
  const {data,errors}=await setup(page);await openDelta(page,"firmware");
  await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Do not replay this request");
  data.rejectCsrf=true;
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page,false,true);
  await expect(page.locator("#deltaSheet")).toContainText("TOKEN_INVALID: CSRF token is invalid");
  await expect(page.locator("#deltaSheet")).toContainText("Request ID:");
  await expect(page.locator("#deltaSheet")).toContainText("不会自动重发");
  await expect(page.locator('[data-version-operation="delta-create"]')).toBeEnabled();
  await page.evaluate("loadDelta(state.delta)");
  expect(data.mutationAttempts).toBe(1);expect(data.csrfRejections).toBe(1);expect(data.writes).toHaveLength(0);expect(data.jobs).toHaveLength(0);
  await expect(page.locator('[data-delta-base="base-0"]')).toBeChecked();
  await expect(page.locator("#deltaReason")).toHaveValue("Do not replay this request");expect(errors).toEqual([]);
});

test("CSRF refresh shares an in-flight session read between concurrent distinct mutations",async({page})=>{
  const {data,errors}=await setup(page);
  let release!:()=>void;data.sessionGate=new Promise<void>(resolve=>{release=resolve;});
  const reads=data.sessionReads;
  const pending=page.evaluate("Promise.all([mutate('/api/admin/delta/notifications/read',{ids:[1]}),mutate('/api/admin/delta/notifications/read',{ids:[2]})])");
  await expect.poll(()=>data.sessionReads).toBe(reads+1);expect(data.mutationAttempts).toBe(0);
  data.sessionGate=null;release();await pending;
  expect(data.sessionReads).toBe(reads+1);expect(data.mutationAttempts).toBe(2);expect(data.csrfRejections).toBe(0);
  expect(data.writes.map(row=>row.body)).toEqual([{ids:[1]},{ids:[2]}]);expect(errors).toEqual([]);
});

test("CSRF refresh does not submit an old confirmation under a changed account",async({page})=>{
  const {data,errors}=await setup(page);await openDelta(page,"firmware");
  await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Confirmed by the original account");
  data.role="publisher";
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page,false,true);
  await expect(page.locator("#deltaSheet")).toContainText("登录账号已变化");
  expect(data.mutationAttempts).toBe(0);expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
});

test("CSRF refresh rejects an unusable session response before sending the mutation",async({page})=>{
  const {data,errors}=await setup(page);await openDelta(page,"firmware");
  await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Require a valid session");
  data.csrfToken="";
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page,false,true);
  await expect(page.locator("#deltaSheet")).toContainText("有效的管理会话");
  expect(data.mutationAttempts).toBe(0);expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
});

for(const language of ["zh","en"]) for(const width of [1440,390,320]) {
  test(`inventory and pinned delta close ${language} ${width}`,async({page},info)=>{
    await page.setViewportSize({width,height:844});const {data,errors}=await setup(page,language);
    expect(data.inventoryReads).toBe(0);
    await page.locator("#appInventoryTab").click();
    await expect(page.locator("#appInventoryPanel tbody tr")).toHaveCount(10);
    await page.locator('#appInventoryPanel [data-version-operation="inventory-next"]').click();
    await expect(page.locator("#appInventoryPanel tbody tr").first()).toContainText("89");
    await page.locator("#searchInput").fill("1.0.99");
    await expect(page.locator("#appInventoryPanel tbody tr")).toHaveCount(1);
    await page.locator("#appReleasesTab").click();
    data.baseCount=80;await openDelta(page);
    const close=page.locator("#deltaClose"),start=(await close.boundingBox())!;
    await page.locator("#deltaScroll").evaluate(node=>{node.scrollTop=node.scrollHeight;});
    await expect(close).toBeInViewport({ratio:1});const end=(await close.boundingBox())!;
    expect(Math.abs(start.y-end.y)).toBeLessThan(1);expect(Math.abs(start.x-end.x)).toBeLessThan(1);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.screenshot({path:info.outputPath(`delta-fixed-close-${width}-${language}-mock.png`),animations:"disabled"});
    await close.click();await expect(page.locator("#deltaSheet")).toBeHidden();
    await expect(page.locator('#versionStrip [data-release-id="app-target"]')).toBeFocused();
    await firmwareView(page);await page.locator("#firmwareInventoryTab").click();
    await expect(page.locator("#firmwareInventoryPanel tbody tr")).toHaveCount(10);
    expect(errors).toEqual([]);expect(data.writes).toHaveLength(0);
  });
}
for(const kind of ["android","firmware"]) test(`selects only reported eligible ${kind} bases and submits once after confirmation`,async({page})=>{
  const {data,errors}=await setup(page);await openDelta(page,kind);
  await page.locator('[data-version-operation="delta-recommend"]').click();
  await expect(page.locator('[data-delta-base="base-0"]')).toBeChecked();
  await expect(page.locator('[data-delta-base="base-1"]')).not.toBeChecked();
  await expect(page.locator('[data-delta-base="base-2"]')).toBeDisabled();
  await expect(page.locator('[data-delta-base="base-3"]')).toBeDisabled();
  await page.locator("#deltaReason").fill("Generate for reported installations");
  await page.locator('[data-version-operation="delta-create"]').click();
  await page.locator("#confirmCancel").click();expect(data.writes).toHaveLength(0);
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page);
  await expect.poll(()=>data.writes.length).toBe(1);
  expect(data.writes[0].body).toEqual({kind,targetReleaseId:kind==="android"?"app-target":"fw-target",baseReleaseIds:["base-0"],reason:"Generate for reported installations"});
  await expect(page.locator('[data-delta-base="base-0"]')).toBeDisabled();
  await expect(page.locator('.delta-job-row a')).toHaveAttribute('href',`https://github.com/Eitan-S-23/${kind==="android"?"Trace":"E-Track"}/actions/runs/123456`);
  expect(errors).toEqual([]);
});
test("refresh explicitly requests future reports rather than pretending all phones replied",async({page})=>{
  const {data}=await setup(page);await page.locator("#appInventoryTab").click();
  await page.locator('#appInventoryPanel [data-version-operation="inventory-refresh"]').click();await confirm(page);
  await expect.poll(()=>data.writes.length).toBe(1);
  await expect(page.locator('#appInventoryPanel [data-version-operation="inventory-refresh"]')).toBeDisabled();
  await expect(page.locator("#appInventoryPanel")).toContainText("本次已响应：0");
});
test("unknown create outcome is reconciled without automatic redispatch",async({page})=>{
  const {data}=await setup(page);data.abortCreate=true;await openDelta(page);
  await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Retain uncertain attempt");
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page,false,true);
  await expect(page.locator("#deltaContent")).toContainText("不会自动重发");
  await expect(page.locator('[data-version-operation="delta-reconcile"]')).toBeVisible();
  await page.locator('[data-version-operation="delta-reload"]').click();
  expect(data.writes).toHaveLength(1);
});
test("ready deltas remain disabled until an owner enables them, with CAS on every change",async({page})=>{
  const {data}=await setup(page);data.jobs=[{id:"ready",baseReleaseId:"base-0",baseVersionCode:99,targetVersionCode:100,status:"ready",enabled:false,revision:7,sizeBytes:5000,runUrl:"",fileName:"delta.vcdiff"}];
  await openDelta(page);await expect(page.locator("#deltaContent")).toContainText("已验证，未启用");
  await page.locator('[data-version-operation="delta-enable"]').click();await confirm(page,true);
  await expect(page.locator('[data-version-operation="delta-disable"]')).toBeVisible();
  expect(data.writes[0].body.expectedRevision).toBe(7);
  await page.locator('[data-version-operation="delta-disable"]').click();await confirm(page,true);
  await expect(page.locator('[data-version-operation="delta-enable"]')).toBeVisible();
  expect(data.writes[1].body.expectedRevision).toBe(8);
  expect(data.writes.every(write=>!write.path.includes("/channels/"))).toBe(true);
});
test("missing dispatch configuration and stale inventory never authorize automatic selection",async({page})=>{
  const {data}=await setup(page);data.dispatchConfigured=false;data.inventoryFails=true;
  await openDelta(page);
  await expect(page.locator('[data-version-operation="delta-create"]')).toBeDisabled();
  await expect(page.locator('[data-version-operation="delta-recommend"]')).toBeDisabled();
  await expect(page.locator("#deltaContent")).toContainText("配置未就绪");
  expect(data.writes).toHaveLength(0);
});
test("viewer can read distribution and jobs but cannot submit or enable",async({page})=>{
  const {data}=await setup(page,"en","viewer");await page.locator("#appInventoryTab").click();
  await expect(page.locator('#appInventoryPanel [data-version-operation="inventory-refresh"]')).toBeDisabled();
  await page.locator("#appReleasesTab").click();await openDelta(page);
  await expect(page.locator('[data-delta-base="base-0"]')).toBeDisabled();
  await expect(page.locator('[data-version-operation="delta-create"]')).toBeDisabled();
  expect(data.writes).toHaveLength(0);
});

async function swipe(page:Page,selector:string,dx:number,dy:number) {
  const box=(await page.locator(selector).boundingBox())!;
  const x=box.x+Math.min(160,box.width/2), y=box.y+Math.min(30,box.height/3);
  const session=await page.context().newCDPSession(page);
  await session.send("Input.dispatchTouchEvent",{type:"touchStart",touchPoints:[{x,y}]});
  for(let i=1;i<=10;i++) {
    await session.send("Input.dispatchTouchEvent",{type:"touchMove",touchPoints:[{x:x+dx*i/10,y:y+dy*i/10}]});
    await page.waitForTimeout(18);
  }
  await session.send("Input.dispatchTouchEvent",{type:"touchEnd",touchPoints:[]});
  await session.detach();
}
test.describe("sheet touch and navigation",()=>{
  test.use({hasTouch:true,viewport:{width:390,height:844}});
  for(const kind of ["app","firmware","delta"]) test(`${kind} drags down or sideways from its header without stealing body scrolling`,async({page})=>{
    const {data,errors}=await setup(page);data.baseCount=70;
    const open=async()=>{
      if(kind==="delta") await openDelta(page);
      else if(kind==="firmware") {await firmwareView(page);await page.locator('#firmwareReleaseList [data-firmware-action="select"]').click();}
      else await page.locator('#versionStrip [data-release-id="app-target"]').click();
    };
    const id=kind==="app"?"quickAction":kind==="firmware"?"firmwareDetail":"delta";
    const sheet=`#${id}Sheet`,scroll=`#${id}Scroll`;
    await open(); await swipe(page,`${sheet} .quick-sheet-header`,0,24);
    await expect(page.locator(sheet)).toBeVisible();
    await expect(page.locator(sheet)).not.toHaveClass(/sheet-dragging/);
    await swipe(page,scroll,110,0);await expect(page.locator(sheet)).toBeVisible();
    await swipe(page,`${sheet} .quick-sheet-header`,0,180);await expect(page.locator(sheet)).toBeHidden();
    await open();await swipe(page,`${sheet} .quick-sheet-header`,180,0);await expect(page.locator(sheet)).toBeHidden();
    await open();await swipe(page,`${sheet} .quick-sheet-header`,-140,0);await expect(page.locator(sheet)).toBeHidden();
    expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
  });
  test("long content retains native scrolling; the header still dismisses at any scroll position",async({page})=>{
    const {data}=await setup(page);data.baseCount=80;await openDelta(page);
    await page.locator("#deltaScroll").evaluate(node=>{node.scrollTop=300;});
    await swipe(page,"#deltaScroll",0,170);await expect(page.locator("#deltaSheet")).toBeVisible();
    await swipe(page,"#deltaSheet .quick-sheet-header",0,180);await expect(page.locator("#deltaSheet")).toBeHidden();
    await openDelta(page);await page.locator("#deltaReason").fill("Retain this unsent draft");
    await swipe(page,"#deltaReason",0,140);await expect(page.locator("#deltaSheet")).toBeVisible();
    await page.locator("#deltaClose").click();await openDelta(page);
    await expect(page.locator("#deltaReason")).toHaveValue("Retain this unsent draft");
    expect(data.writes).toHaveLength(0);
  });
  test("Back cancels the top confirmation, then closes details, never submits",async({page})=>{
    const {data}=await setup(page);await openDelta(page);
    await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Back must not submit");
    await page.locator('[data-version-operation="delta-create"]').click();await expect(page.locator("#confirmDialog")).toBeVisible();
    await page.goBack();await expect(page.locator("#confirmDialog")).toBeHidden();await expect(page.locator("#deltaSheet")).toBeVisible();
    await page.goBack();await expect(page.locator("#deltaSheet")).toBeHidden();expect(data.writes).toHaveLength(0);
    await expect(page.locator('#versionStrip [data-release-id="app-target"]')).toBeFocused();
  });
  test("button and gesture closure leave no extra Back step before the previous page",async({page})=>{
    await setup(page);await page.goto(origin+"/previous");await page.goto(origin);
    await expect(page.locator("#refreshButton")).toBeEnabled();await openDelta(page);
    await page.locator("#deltaClose").click();
    await expect.poll(()=>page.evaluate(()=>history.state?.traceAdminOverlay??null)).toBeNull();
    await page.goBack();await expect(page).toHaveURL(origin+"/previous");
  });
  test("Back and swipes cannot hide an in-flight submission",async({page})=>{
    const {data}=await setup(page);let finish!:()=>void;data.createGate=new Promise<void>(resolve=>{finish=resolve;});
    await openDelta(page);await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Pending submit");
    await page.locator('[data-version-operation="delta-create"]').click();await confirm(page);
    await expect.poll(()=>data.writes.length).toBe(1);
    await swipe(page,"#deltaSheet .quick-sheet-header",0,180);await expect(page.locator("#deltaSheet")).toBeVisible();
    await page.goBack();await expect(page.locator("#deltaSheet")).toBeVisible();
    finish();await expect(page.locator(".delta-job-row")).toHaveCount(1);
    await page.locator("#deltaClose").click();await expect(page.locator("#deltaSheet")).toBeHidden();expect(data.writes).toHaveLength(1);
  });
});
for(const kind of ["android","firmware"]) test(`${kind} completion survives closed dialog, background return and page reload`,async({page})=>{
  const {data,errors}=await setup(page);await openDelta(page,kind);
  await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Background completion");
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page);
  await expect(page.locator(".delta-job-row")).toHaveCount(1);await page.locator("#deltaClose").click();
  data.jobs[0].status="ready";data.jobs[0].phase="ready";data.unreadCount=1;
  data.notifications=[{id:1,kind,targetReleaseId:kind==="android"?"app-target":"fw-target",baseVersionCode:99,targetVersionCode:100,status:"ready",createdAt:Math.floor(Date.now()/1000),unread:1}];
  await page.evaluate(()=>document.dispatchEvent(new Event("visibilitychange")));
  await expect(page.locator("#taskToast")).toBeVisible();await expect(page.locator(".task-badge")).toHaveText("1");
  await page.locator("#taskButton").click();await expect(page.locator("#taskContent")).toContainText("差分包已生成");
  await expect(page.locator("#taskContent")).toContainText("待启用");
  await expect(page.locator(".task-notification.unread")).toHaveCount(0);await page.locator("#taskClose").click();
  await page.reload();await expect(page.locator("#taskButton")).toBeEnabled();
  await page.locator("#taskButton").click();await expect(page.locator(".task-notification.unread")).toHaveCount(0);
  await expect(page.locator(".task-badge")).toBeHidden();
  expect(data.writes.filter(write=>write.path==="/api/admin/delta/jobs")).toHaveLength(1);
  expect(data.writes.some(write=>write.path.includes("/channels/")||write.path.endsWith("/enable"))).toBe(false);expect(errors).toEqual([]);
});
test("activity failures retain the last task and recover without redispatch",async({page})=>{
  const {data}=await setup(page);data.jobs=[{id:"progress",kind:"firmware",targetReleaseId:"fw-target",baseReleaseId:"base-0",baseVersionCode:99,targetVersionCode:100,status:"running",phase:"uploading",enabled:false,revision:1,sizeBytes:0,runUrl:"",fileName:""}];
  await page.locator("#taskButton").click();await expect(page.locator("#taskContent")).toContainText("上传差分文件");
  data.activityFails=true;await page.locator('[data-task-action="refresh"]').click();await expect(page.locator("#taskContent .error")).toContainText("上次状态已保留");
  await dismissError(page);
  await expect(page.locator(".task-job")).toHaveCount(1);
  data.activityFails=false;data.jobs[0].status="failed";data.jobs[0].phase="failed";
  await page.evaluate(()=>window.dispatchEvent(new Event("online")));await expect(page.locator("#taskContent")).toContainText("生成失败");
  expect(data.writes).toHaveLength(0);
});

function notification(id:number,kind="android") {
  return {id,kind,targetReleaseId:kind==="android"?"app-target":"fw-target",baseVersionCode:99,targetVersionCode:100,
    status:"ready",createdAt:Math.floor(Date.now()/1000),unread:1};
}
async function requestTasksFromWorker(page:Page) {
  return page.evaluate(()=>new Promise(resolve=>{
    const channel=new MessageChannel();
    channel.port1.onmessage=event=>{channel.port1.close();channel.port2.close();resolve(event.data.type);};
    navigator.serviceWorker.dispatchEvent(new MessageEvent("message",{data:{type:"trace-delta-open"},ports:[channel.port2]}));
  }));
}
for(const kind of ["android","firmware"]) test(`viewed ${kind} notifications become durably read without consuming unseen pages`,async({page})=>{
  const {data,errors}=await setup(page);data.notifications=Array.from({length:10},(_,i)=>notification(10-i,kind));data.unreadCount=10;
  await page.evaluate(()=>window.dispatchEvent(new Event("online")));
  await expect(page.locator(".task-badge")).toHaveText("10");await page.waitForTimeout(650);
  expect(data.writes).toHaveLength(0);
  await page.locator("#taskButton").click();await page.locator('[data-notification-id="10"]').click();
  await expect(page.locator("#deltaSheet")).toBeVisible();
  await expect.poll(()=>data.notifications.find(n=>n.id===10)?.unread).toBe(0);
  expect(data.notifications.find(n=>n.id===1)?.unread).toBe(1);
  expect(data.writes.every(write=>write.path==="/api/admin/delta/notifications/read" &&
    (write.body.ids as number[]).every(id=>id>=5))).toBe(true);
  await page.locator("#deltaClose").click();await page.locator("#taskButton").click();
  await page.locator('[data-task-action="notice-next"]').click();
  await page.locator('[data-notification-id="1"]').scrollIntoViewIfNeeded();
  await expect.poll(()=>data.notifications.find(n=>n.id===1)?.unread).toBe(0);
  await page.reload();await page.locator("#taskButton").click();
  await expect(page.locator('[data-notification-id="10"]')).not.toHaveClass(/unread/);
  expect(errors).toEqual([]);
});
test("a background task panel does not consume new notifications or confuse running jobs with unread",async({page})=>{
  const {data}=await setup(page);
  data.jobs=[{id:"running",kind:"android",targetReleaseId:"app-target",baseReleaseId:"base-0",baseVersionCode:99,targetVersionCode:100,
    status:"running",phase:"building",enabled:false,revision:1,sizeBytes:0,runUrl:"",fileName:""}];
  await page.locator("#taskButton").click();await expect(page.locator("#taskButton")).toHaveAttribute("data-running","true");
  await expect(page.locator(".task-badge")).toBeHidden();
  await page.evaluate(()=>{Object.defineProperty(document,"hidden",{configurable:true,value:true});document.dispatchEvent(new Event("visibilitychange"));});
  data.notifications=[notification(1)];data.unreadCount=1;await page.evaluate(()=>window.dispatchEvent(new Event("online")));
  await expect(page.locator(".task-badge")).toHaveText("1");await page.waitForTimeout(650);expect(data.writes).toHaveLength(0);
  await page.evaluate(()=>{Object.defineProperty(document,"hidden",{configurable:true,value:false});document.dispatchEvent(new Event("visibilitychange"));});
  await expect(page.locator(".task-badge")).toBeHidden();
  await expect(page.locator("#taskButton")).toHaveAttribute("data-running","true");
  await expect(page.locator("#taskButton")).toHaveAttribute("aria-label",/1 进行中, 0 未读/);
});
test("failed read acknowledgement retains unread state until an explicit refresh recovers",async({page})=>{
  const {data}=await setup(page);data.notifications=[notification(1)];data.unreadCount=1;data.readFails=true;
  await page.locator("#taskButton").click();await expect(page.locator("#taskContent")).toContainText("已读状态保存失败");
  await expect(page.locator(".task-badge")).toHaveText("1");await page.waitForTimeout(1100);
  expect(data.writes).toHaveLength(1);expect(data.unreadCount).toBe(1);
  await dismissError(page);
  data.readFails=false;await page.locator('[data-task-action="refresh"]').click();
  await expect(page.locator(".task-badge")).toBeHidden();expect(data.unreadCount).toBe(0);
});
test("an activity response captured before a read acknowledgement cannot resurrect unread results",async({page})=>{
  const {data}=await setup(page);data.notifications=[notification(1)];data.unreadCount=1;
  let releaseRead!:()=>void,releaseActivity!:()=>void;
  data.readGate=new Promise<void>(resolve=>{releaseRead=resolve;});
  await page.locator("#taskButton").click();await expect.poll(()=>data.writes.length).toBe(1);
  data.activityGate=new Promise<void>(resolve=>{releaseActivity=resolve;});
  const before=data.activityReads;await page.evaluate(()=>window.dispatchEvent(new Event("online")));
  await expect.poll(()=>data.activityReads).toBeGreaterThan(before);
  data.readGate=null;releaseRead();await expect(page.locator(".task-badge")).toBeHidden();
  await page.evaluate(()=>{
    const badge=document.querySelector(".task-badge")!,regressions:Array<string|null>=[];Object.assign(window,{unreadRegressions:regressions});
    new MutationObserver(()=>{if(!badge.hasAttribute("hidden")) regressions.push(badge.textContent);}).observe(badge,{attributes:true,childList:true});
  });
  data.activityGate=null;releaseActivity();await expect.poll(()=>data.activityReads).toBeGreaterThan(before+1);
  await expect(page.locator('[data-task-action="refresh"]')).toBeEnabled();
  await expect(page.locator(".task-badge")).toBeHidden();expect(await page.evaluate("unreadRegressions")).toEqual([]);
  expect(data.writes).toHaveLength(1);
});
test("mark all read uses the observed boundary and does not consume a later result",async({page})=>{
  const {data}=await setup(page);data.notifications=[notification(3),notification(2),notification(1)];data.unreadCount=3;
  let releaseRead!:()=>void;data.readGate=new Promise<void>(resolve=>{releaseRead=resolve;});
  await page.locator("#taskButton").click();await page.locator('[data-task-action="read"]').click();
  await expect.poll(()=>data.writes.length).toBe(1);expect(data.writes[0].body).toEqual({throughId:3});
  await page.locator("#taskClose").click();data.notifications.unshift(notification(4));data.unreadCount++;
  data.readGate=null;releaseRead();await expect.poll(()=>data.unreadCount).toBe(1);
  await expect(page.locator(".task-badge")).toHaveText("1");expect(data.notifications[0].unread).toBe(1);
});
test("notification navigation survives loading and consumes its cold-start URL only after opening",async({page})=>{
  const {data,errors}=await setup(page);
  let release!:()=>void;data.catalogueGate=new Promise<void>(resolve=>{release=resolve;});
  await page.locator("#refreshButton").click();await expect(page.locator("#refreshButton")).toBeDisabled();
  expect(await requestTasksFromWorker(page)).toBe("trace-delta-open-accepted");
  await expect(page.locator("#taskSheet")).toBeHidden();
  data.catalogueGate=null;release();await expect(page.locator("#taskSheet")).toBeVisible();
  await page.locator("#taskClose").click();await page.goto(origin+"/?tasks=1");
  await expect(page.locator("#taskSheet")).toBeVisible();await expect(page).not.toHaveURL(/tasks=1/);
  await page.locator("#taskClose").click();await page.reload();await expect(page.locator("#taskButton")).toBeEnabled();
  await expect(page.locator("#taskSheet")).toBeHidden();expect(errors).toEqual([]);expect(data.writes).toHaveLength(0);
});
test("notification navigation waits for confirmation without losing the current delta draft",async({page})=>{
  const {data}=await setup(page);await openDelta(page);await page.locator('[data-delta-base="base-0"]').check();
  await page.locator("#deltaReason").fill("Keep my unsent draft");
  await page.locator('[data-version-operation="delta-create"]').click();await expect(page.locator("#confirmDialog")).toBeVisible();
  expect(await requestTasksFromWorker(page)).toBe("trace-delta-open-accepted");
  await expect(page.locator("#taskSheet")).toBeHidden();await expect(page.locator("#confirmDialog")).toBeVisible();
  await page.locator("#confirmCancel").click();await expect(page.locator("#taskSheet")).toBeVisible();
  await page.locator("#taskClose").click();await openDelta(page);
  await expect(page.locator("#deltaReason")).toHaveValue("Keep my unsent draft");
  await expect(page.locator('[data-delta-base="base-0"]')).toBeChecked();expect(data.writes).toHaveLength(0);
});

test("notification permission is requested only by a click and denial never starts a subscription or build",async({page})=>{
  await page.addInitScript(()=>{
    Object.defineProperty(window,"Notification",{configurable:true,value:{permission:"default",requestPermission(){this.permission="denied";return Promise.resolve("denied");}}});
  });
  const {data}=await setup(page);data.pushPublicKey="B".repeat(87);
  await page.locator("#taskButton").click();await expect(page.locator('[data-task-action="push-on"]')).toBeEnabled();
  expect(await page.evaluate(()=>Notification.permission)).toBe("default");
  await page.locator('[data-task-action="push-on"]').click();
  await expect(page.locator("#taskContent")).toContainText("浏览器已阻止通知");
  await expect(page.locator('[data-task-action="push-on"]')).toBeDisabled();expect(data.writes).toHaveLength(0);
});

const pushEndpoint="https://fcm.googleapis.com/fcm/send/mock-enrollment";
const pushPublicKey="B".repeat(87);
const pushId=createHash("sha256").update(pushEndpoint).digest("hex");
async function mockBrowserPush(page:Page,existing=false,fail=false) {
  await page.addInitScript(({endpoint,publicKey,existing,fail})=>{
    const calls={register:0,subscribe:0,unsubscribe:0,permission:0,update:0};
    const state={pause:false,release:null as (()=>void)|null};
    let present=existing;
    const subscription={endpoint,options:{applicationServerKey:Uint8Array.from(atob(publicKey+"="),c=>c.charCodeAt(0)).buffer},
      unsubscribe:async()=>{calls.unsubscribe++;present=false;return true;}};
    const registration={active:{state:"activated",scriptURL:location.origin+"/admin-sw.js"},update:async()=>{calls.update++;},pushManager:{getSubscription:async()=>present?subscription:null,
      subscribe:async()=>{calls.subscribe++;if(state.pause) await new Promise<void>(resolve=>{state.release=resolve;});
        if(fail) throw new DOMException("Registration failed - push service error","AbortError");present=true;return subscription;}}};
    Object.defineProperty(window,"Notification",{configurable:true,value:{permission:"granted",
      requestPermission:async()=>{calls.permission++;return "granted";}}});
    Object.defineProperty(window,"PushManager",{configurable:true,value:function(){}});
    Object.defineProperty(navigator,"serviceWorker",{configurable:true,value:{
      ready:Promise.resolve(registration),register:async()=>{calls.register++;return registration;},getRegistration:async()=>registration,addEventListener(){}}});
    Object.assign(window,{pushMockCalls:calls,pushMockState:state});
  },{endpoint:pushEndpoint,publicKey:pushPublicKey,existing,fail});
}

test("push enrollment restores a registered browser without relying on local storage",async({page})=>{
  await mockBrowserPush(page,true);const {data,errors}=await setup(page);data.pushPublicKey=pushPublicKey;
  data.pushSubscriptions=[{id:pushId,expiresAt:Math.floor(Date.now()/1000)+86400}];
  await page.locator("#taskButton").click();await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  expect(await page.evaluate("pushMockCalls")).toMatchObject({register:0,subscribe:0,unsubscribe:0,permission:0});
  expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
});
test("existing notification workers update in place without changing the working subscription",async({page})=>{
  await mockBrowserPush(page,true);const {data}=await setup(page,"zh","owner",{publicKey:pushPublicKey,subscriptions:[{id:pushId,expiresAt:Math.floor(Date.now()/1000)+86400}]});
  await page.locator("#taskButton").click();await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  await page.locator('[data-task-action="refresh"]').click();await expect(page.locator('[data-task-action="refresh"]')).toBeEnabled();
  expect(await page.evaluate("pushMockCalls")).toMatchObject({update:1,register:0,subscribe:0,unsubscribe:0,permission:0});
  expect(data.writes).toHaveLength(0);
});

test("push enrollment reuses a live browser subscription when the server registration is missing",async({page})=>{
  await mockBrowserPush(page,true,true);const {data}=await setup(page);data.pushPublicKey=pushPublicKey;
  await page.locator("#taskButton").click();await page.locator('[data-task-action="push-on"]').click();
  await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  expect(await page.evaluate("pushMockCalls")).toMatchObject({subscribe:0,unsubscribe:0});
  expect(data.writes.map(row=>row.path)).toEqual(["/api/admin/delta/notifications/subscribe"]);
});

test("push enrollment ignores an activity response captured before successful registration",async({page})=>{
  await mockBrowserPush(page);const {data}=await setup(page);data.pushPublicKey=pushPublicKey;
  await page.locator("#taskButton").click();await expect(page.locator('[data-task-action="push-on"]')).toBeEnabled();
  let release!:()=>void;data.activityGate=new Promise<void>(resolve=>{release=resolve;});
  const before=data.activityReads;await page.evaluate(()=>window.dispatchEvent(new Event("online")));
  await expect.poll(()=>data.activityReads).toBeGreaterThan(before);
  await page.locator('[data-task-action="push-on"]').click();await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  data.activityGate=null;release();await expect(page.locator('[data-task-action="refresh"]')).toBeEnabled();
  await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  expect(await page.evaluate("pushMockCalls")).toMatchObject({subscribe:1,unsubscribe:0});
  expect(data.writes).toHaveLength(1);
});

test("push enrollment reports provider registration failure separately and retains it on task refresh",async({page})=>{
  await mockBrowserPush(page,false,true);const {data}=await setup(page);data.pushPublicKey=pushPublicKey;
  await page.locator("#taskButton").click();await page.locator('[data-task-action="push-on"]').click();
  const error=page.locator('.task-notification-settings [role="alert"]');
  await expect(error).toContainText("Registration failed - push service error");
  await expect(error).toContainText("推送服务");await expect(error).not.toContainText("上次状态已保留");
  await dismissError(page);
  await page.locator('[data-task-action="refresh"]').click();await expect(error).toContainText("Registration failed");
  await expect(page.locator('[data-task-action="push-off"]')).toHaveCount(0);
  expect(data.writes).toHaveLength(0);
});

test("push enrollment does not trust a cached enabled flag when the browser subscription disappeared",async({page})=>{
  await mockBrowserPush(page);await page.addInitScript(({id})=>localStorage.setItem("trace-admin-tasks:owner@example.test:push",
    JSON.stringify({id,expiresAt:Math.floor(Date.now()/1000)+86400})),{id:pushId});
  const {data}=await setup(page,"zh","owner",{publicKey:pushPublicKey,subscriptions:[{id:pushId,expiresAt:Math.floor(Date.now()/1000)+86400}]});
  await page.locator("#taskButton").click();await expect(page.locator('[data-task-action="refresh"]')).toBeEnabled();
  await expect(page.locator('[data-task-action="push-off"]')).toHaveCount(0);
  expect(await page.evaluate("pushMockCalls")).toMatchObject({subscribe:0,unsubscribe:0});expect(data.writes).toHaveLength(0);
});

test("push enrollment keeps a pending setup locked while task refresh finishes",async({page})=>{
  await mockBrowserPush(page);const {data}=await setup(page);data.pushPublicKey=pushPublicKey;
  await page.locator("#taskButton").click();await page.evaluate("pushMockState.pause=true");
  await page.locator('[data-task-action="push-on"]').click();await expect.poll(()=>page.evaluate("pushMockCalls.subscribe")).toBe(1);
  const reads=data.activityReads;await page.locator('[data-task-action="refresh"]').click();
  await expect.poll(()=>data.activityReads).toBeGreaterThan(reads);await expect(page.locator('[data-task-action="refresh"]')).toBeEnabled();
  await expect(page.locator('[data-task-action="push-on"]')).toBeDisabled();
  await page.evaluate("pushMockState.release()");await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  expect(data.writes).toHaveLength(1);
});

test("push enrollment preserves the browser subscription when server registration fails",async({page})=>{
  await mockBrowserPush(page,true,true);const {data}=await setup(page);data.pushPublicKey=pushPublicKey;data.pushRegisterFails=true;
  await page.locator("#taskButton").click();await page.locator('[data-task-action="push-on"]').click();
  await expect(page.locator('.task-notification-settings [role="alert"]')).toContainText("浏览器订阅已保留");
  await dismissError(page);
  data.pushRegisterFails=false;await page.locator('[data-task-action="push-on"]').click();
  await expect(page.locator('[data-task-action="push-off"]')).toBeVisible();
  expect(await page.evaluate("pushMockCalls")).toMatchObject({subscribe:0,unsubscribe:0});
  expect(data.writes.every(row=>row.path==="/api/admin/delta/notifications/subscribe")).toBe(true);
});

test("push enrollment removes a subscription only after an explicit turn-off action",async({page})=>{
  await mockBrowserPush(page,true);const {data}=await setup(page,"zh","owner",{publicKey:pushPublicKey,
    subscriptions:[{id:pushId,expiresAt:Math.floor(Date.now()/1000)+86400}]});
  await page.locator("#taskButton").click();await expect(page.locator('[data-task-action="push-off"]')).toBeEnabled();
  await page.locator('[data-task-action="push-off"]').click();await expect(page.locator('[data-task-action="push-on"]')).toBeEnabled();
  expect(await page.evaluate("pushMockCalls")).toMatchObject({subscribe:0,unsubscribe:1});
  expect(data.writes.map(row=>row.path)).toEqual(["/api/admin/delta/notifications/unsubscribe"]);
});

for(const language of ["zh","en"]) for(const width of [320,390]) test(`mobile task toolbar stays on one row ${language} ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:844});await setup(page,language);
  const controls=await page.locator('#mobileMenu, #languageToggle, #refreshButton, #taskButton').evaluateAll(nodes=>nodes.map(node=>{
    const box=node.getBoundingClientRect();return {top:box.top,bottom:box.bottom,left:box.left,right:box.right};
  }));
  expect(Math.max(...controls.map(r=>r.top))-Math.min(...controls.map(r=>r.top))).toBeLessThan(2);
  for(const box of controls){expect(box.left).toBeGreaterThanOrEqual(0);expect(box.right).toBeLessThanOrEqual(width);}
  for(let i=1;i<controls.length;i++)expect(controls[i].left).toBeGreaterThanOrEqual(controls[i-1].right);
  await expect(page.locator('#taskButton .task-label')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  await page.screenshot({path:info.outputPath('mobile-task-toolbar.png'),animations:'disabled'});
});

function approvalJob(): Job {
  return { id:"approval-job", kind:"firmware", targetReleaseId:"fw-target", baseReleaseId:"base-0",
    baseVersionCode:30324, targetVersionCode:30325, status:"queued", phase:"awaiting_approval", enabled:false,
    revision:1, attempt:1, sizeBytes:0, fileName:"", runUrl:"https://github.com/Eitan-S-23/E-Track/actions/runs/12345",
    ci:{phase:"awaiting_approval",approvalEnvironments:["firmware-rehearsal"],checkedAt:Math.floor(Date.now()/1000)} };
}

for (const language of ["zh", "en"]) test(`new MCU delta selection has no obsolete approval requirement in ${language}`,async({page})=>{
  const {data,errors}=await setup(page,language);
  await openDelta(page,"firmware");
  await expect(page.locator("#deltaSheet")).not.toContainText("固件差分需要 GitHub 仓库审批人手动审批");
  await expect(page.locator("#deltaSheet")).not.toContainText("Firmware deltas require a GitHub repository reviewer's approval");
  await expect(page.locator("#deltaReason")).toBeVisible();
  await expect(page.locator('[data-version-operation="delta-create"]')).toBeVisible();
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
});

test.describe("visible operation feedback", () => {
  test.use({hasTouch:true,viewport:{width:390,height:844}});
  for (const direction of [-140,140]) test(`CSRF errors open above the current sheet and swipe ${direction} only dismisses`,async({page})=>{
    const {data,errors}=await setup(page);data.baseCount=45;
    await openDelta(page,"firmware");
    await page.locator('[data-delta-base="base-0"]').check();
    await page.locator("#deltaReason").fill("Preserve this MCU request");
    data.rejectCsrf=true;
    await page.locator('[data-version-operation="delta-create"]').click();
    await page.locator("#confirmAccept").click();
    const dialog=page.locator('#confirmDialog[role="alertdialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("CSRF token is invalid");
    await expect(dialog).toContainText("Request ID:");
    await expect(dialog).toContainText("不会自动重发");
    await expect(page.locator("#confirmAccept")).toBeFocused();
    expect(await page.locator("#deltaSheet").evaluate(node=>node.inert)).toBe(true);
    const rect=(await dialog.boundingBox())!;
    expect(rect.y).toBeGreaterThanOrEqual(0);expect(rect.y+rect.height).toBeLessThanOrEqual(844);
    await swipe(page,"#confirmDialog .confirm-head",direction,0);
    await expect(page.locator("#confirmDialog")).toBeHidden();
    await expect(page.locator("#deltaSheet")).toBeVisible();
    await expect(page.locator("#deltaReason")).toHaveValue("Preserve this MCU request");
    await expect(page.locator('[data-delta-base="base-0"]')).toBeChecked();
    expect(data.mutationAttempts).toBe(1);expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
  });
  for (const direction of [-140,140]) test(`real approval state opens a safe run link and swipe ${direction} never approves`,async({page})=>{
    const {data,errors}=await setup(page);data.jobs=[approvalJob()];
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#confirmTitle")).toHaveText("差分构建等待审批");
    await expect(page.locator("#confirmExternal")).toHaveAttribute("href",data.jobs[0].runUrl);
    await expect(page.locator("#confirmExternal")).toHaveAttribute("rel","noopener noreferrer");
    await expect(page.locator("#confirmMessage")).toContainText("Review deployments");
    await swipe(page,"#confirmDialog .confirm-head",direction,0);
    await expect(page.locator("#confirmDialog")).toBeHidden();
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#confirmDialog")).toBeHidden();
    await page.locator("#taskButton").click();
    await expect(page.locator("#taskContent")).toContainText("等待 GitHub 手动审批");
    await expect(page.locator('#taskContent a[href*="/actions/runs/12345"]')).toHaveText("前往 GitHub 审批");
    expect(data.writes).toHaveLength(0);expect(errors).toEqual([]);
  });
  test("queueing does not invent a review requirement and provider failures are separate",async({page})=>{
    const {data}=await setup(page);
    data.jobs=[{...approvalJob(),phase:"ci_queued",ci:{phase:"ci_queued",approvalEnvironments:[]}}];
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#confirmDialog")).toBeHidden();
    data.jobs[0].phase="ci_unavailable";
    data.jobs[0].ci={phase:"ci_unavailable",approvalEnvironments:[],errorCode:"GITHUB_HTTP_503"};
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator('#confirmDialog[role="alertdialog"]')).toContainText("GITHUB_HTTP_503");
    await expect(page.locator("#confirmExternal")).toBeHidden();
    expect(data.jobs[0].status).toBe("queued");expect(data.writes).toHaveLength(0);
  });
  test("approval waits behind an active confirmation without replacing the draft",async({page})=>{
    const {data}=await setup(page);await openDelta(page,"firmware");
    await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Keep my draft");
    await page.locator('[data-version-operation="delta-create"]').click();
    const title=await page.locator("#confirmTitle").textContent();
    data.jobs=[approvalJob()];await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#confirmTitle")).toHaveText(title!);
    await expect(page.locator("#confirmAccept")).toBeFocused();
    await page.locator("#confirmCancel").click();
    await expect(page.locator("#confirmTitle")).toHaveText("差分构建等待审批");
    await page.locator("#confirmAccept").click();
    await expect(page.locator("#deltaReason")).toHaveValue("Keep my draft");
    expect(data.writes).toHaveLength(0);
  });
  test("an obsolete queued approval reminder disappears when the run has moved on",async({page})=>{
    const {data}=await setup(page);await page.evaluate("void openResultDialog({title:'Current dialog'})");
    data.jobs=[approvalJob()];await page.evaluate("taskActivity.refresh()");
    data.jobs=[{...approvalJob(),status:"running",phase:"building",ci:undefined}];
    await page.evaluate("taskActivity.refresh()");await page.locator("#confirmAccept").click();
    await expect(page.locator("#confirmDialog")).toBeHidden();expect(data.writes).toHaveLength(0);
  });
  test("repeated polling errors are shown once until the connection recovers",async({page})=>{
    const {data}=await setup(page);data.activityFails=true;
    await page.evaluate("taskActivity.refresh()");await expect(page.locator("#confirmMessage")).toContainText("Activity unavailable");
    await page.locator("#confirmAccept").click();await expect(page.locator("#confirmDialog")).toBeHidden();
    await page.evaluate("taskActivity.refresh()");await expect(page.locator("#confirmDialog")).toBeHidden();
    data.activityFails=false;await page.evaluate("taskActivity.refresh()");
    data.activityFails=true;await page.evaluate("taskActivity.refresh()");
    await expect(page.locator('#confirmDialog[role="alertdialog"]')).toBeVisible();expect(data.writes).toHaveLength(0);
  });
  test("a background error is surfaced on return without replaying the operation",async({page})=>{
    const {data}=await setup(page);
    await page.evaluate(()=>Object.defineProperty(document,"hidden",{configurable:true,get:()=>true}));
    data.activityFails=true;await page.evaluate("taskActivity.refresh()");await expect(page.locator("#confirmDialog")).toBeHidden();
    await page.evaluate(()=>{Object.defineProperty(document,"hidden",{configurable:true,get:()=>false});document.dispatchEvent(new Event("visibilitychange"));});
    await expect(page.locator('#confirmDialog[role="alertdialog"]')).toBeVisible();expect(data.writes).toHaveLength(0);
  });
  test("unsafe approval links and another account's queued error are not displayed",async({page})=>{
    const {data}=await setup(page);data.jobs=[{...approvalJob(),runUrl:"https://evil.example/actions/runs/12345"}];
    await page.evaluate("taskActivity.refresh()");await expect(page.locator("#confirmDialog")).toBeHidden();
    await page.evaluate("state.busy=true;showErrorDialog('previous-account-private-detail');state.session={...state.session,actor:'another@example.test'};state.busy=false;flushFeedback()");
    await expect(page.locator("#confirmDialog")).toBeHidden();expect(data.writes).toHaveLength(0);
  });
  test("old noticed failures do not reopen alerts, while a fresh failed result does",async({page})=>{
    await page.addInitScript(()=>localStorage.setItem("trace-admin-tasks:owner@example.test:noticed","100"));
    const {data}=await setup(page);
    data.notifications=[{...notification(90),jobId:"old-job",attempt:1,status:"failed",errorCode:"CI_BUILD_FAILED"}];
    data.unreadCount=1;await page.evaluate("taskActivity.refresh()");
    await expect(page.locator("#confirmDialog")).toBeHidden();
    data.notifications=[{...notification(101),jobId:"new-job",attempt:1,status:"failed",errorCode:"CI_BUILD_FAILED"}];
    await page.evaluate("taskActivity.refresh()");
    await expect(page.locator('#confirmDialog[role="alertdialog"]')).toContainText("CI_BUILD_FAILED");
    expect(data.unreadCount).toBe(1);expect(data.writes).toHaveLength(0);
  });
  test("a confirmation swipe cancels rather than submitting the requested mutation",async({page})=>{
    const {data}=await setup(page);await openDelta(page,"firmware");
    await page.locator('[data-delta-base="base-0"]').check();await page.locator("#deltaReason").fill("Unsubmitted request");
    await page.locator('[data-version-operation="delta-create"]').click();
    await swipe(page,"#confirmDialog .confirm-head",140,0);await expect(page.locator("#confirmDialog")).toBeHidden();
    expect(data.mutationAttempts).toBe(0);await expect(page.locator("#deltaReason")).toHaveValue("Unsubmitted request");
  });
});
