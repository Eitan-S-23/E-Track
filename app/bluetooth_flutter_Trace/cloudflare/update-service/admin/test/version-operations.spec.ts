import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

const origin="https://version-operations.test";
const html=readFileSync(new URL("../public/index.html",import.meta.url),"utf8").replace("<body>",
  '<body><div style="position:fixed;bottom:4px;left:4px;z-index:10000;background:#fff2b0;padding:4px;font:11px monospace;pointer-events:none">MOCK UI / NO DEVICE OR CLOUD OPERATIONS</div>');
const css=readFileSync(new URL("../public/admin.css",import.meta.url),"utf8");
const hash="a".repeat(64);
type Job={id:string;baseReleaseId:string;baseVersionCode:number;targetVersionCode:number;status:string;enabled:boolean;revision:number;sizeBytes:number;runUrl:string;fileName:string};

async function setup(page:Page,language="zh",role="owner") {
  const data={role,dispatchConfigured:true,inventoryFails:false,abortCreate:false,inventoryReads:0,
    refreshRequestedAt:0,refreshId:"initial",baseCount:4,jobs:[] as Job[],writes:[] as Array<{path:string;body:Record<string,unknown>}>};
  await page.addInitScript(lang=>localStorage.setItem("trace-admin-language",lang),language);
  const errors:string[]=[];page.on("pageerror",error=>errors.push(error.message));
  let serial=0;
  await page.route("**/*",async route=>{
    const request=route.request(),url=new URL(request.url()),requestId=`operation-${++serial}`;
    if(url.origin!==origin){await route.abort();return;}
    if(url.pathname==="/"){await route.fulfill({contentType:"text/html",body:html});return;}
    if(url.pathname==="/admin.css"){await route.fulfill({contentType:"text/css",body:css});return;}
    const reply=(body:object,status=200)=>route.fulfill({status,contentType:"application/json",headers:{"X-Request-Id":requestId},body:JSON.stringify({requestId,...body})});
    if(request.method()==="GET") {
      if(url.pathname==="/api/admin/session"){await reply({ok:true,role:data.role,actor:`${data.role}@example.test`,csrfToken:"version-csrf",appId:"trace",environment:"MOCK"});return;}
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
    expect(request.method()).toBe("POST");expect(request.headers()["x-csrf-token"]).toBe("version-csrf");
    expect(request.headers()["content-type"]).toBe("application/json");
    const body=request.postDataJSON() as Record<string,unknown>;
    data.writes.push({path:url.pathname,body});
    if(url.pathname==="/api/admin/version-inventory/refresh") {
      expect(String(body.requestId)).toMatch(/^[0-9a-f-]{36}$/);data.refreshId=String(body.requestId);data.refreshRequestedAt=Math.floor(Date.now()/1000);
      await reply({ok:true,refreshId:data.refreshId});return;
    }
    if(url.pathname==="/api/admin/delta/jobs") {
      expect(body.kind).toMatch(/^(android|firmware)$/);expect(String(body.reason).trim()).not.toBe("");
      data.jobs=(body.baseReleaseIds as string[]).map((id,index)=>({id:`delta-${index}`,baseReleaseId:id,baseVersionCode:99-index,targetVersionCode:100,
        status:data.abortCreate?"dispatch_unknown":"queued",enabled:false,revision:1,sizeBytes:5000,runUrl:"https://github.com/Eitan-S-23/E-Track/actions/runs/123456",fileName:"delta.vcdiff"}));
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
async function firmwareView(page:Page) {
  if(await page.locator("#mobileMenu").isVisible()) await page.locator("#mobileMenu").click();
  await page.locator('[data-view-target="firmware"]').click();
}
async function openDelta(page:Page,kind="android") {
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
async function confirm(page:Page,reason=false) {
  await expect(page.locator("#confirmDialog")).toBeVisible();
  if(reason) await page.locator("#confirmReason").fill("Operator selected this action");
  await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmDialog")).toBeHidden();
}
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
  await page.locator('[data-version-operation="delta-create"]').click();await confirm(page);
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
