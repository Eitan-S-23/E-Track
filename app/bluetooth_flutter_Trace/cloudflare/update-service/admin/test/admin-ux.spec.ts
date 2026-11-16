import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

async function mount(page: Page) {
  const origin="https://ux-admin.test";
  const writes:Array<{path:string;body:Record<string,unknown>}>=[],reads:string[]=[];
  const state={failNotice:false,notices:[] as Array<Record<string,unknown>>,notifications:[{
    id:1,type:"candidate",kind:"android",targetReleaseId:"one",versionName:"1.0.1",status:"ready",unread:1,createdAt:1794652000}],
    jobs:[{id:"ux-job",kind:"android",targetReleaseId:"two",baseReleaseId:"one",baseVersionCode:1,targetVersionCode:2,
      status:"queued",phase:"ci_queued",attempt:1,revision:1,createdAt:1794652000,updatedAt:1794652000,
      runUrl:"https://github.com/Eitan-S-23/Trace/actions/runs/12345",cancelling:false}],
    removed:new Set<string>()};
  await page.addInitScript(()=>localStorage.setItem("trace-admin-language","en"));
  await page.route("**/*",async route=>{
    const req=route.request(),url=new URL(req.url());
    if(url.origin!==origin){await route.abort();return;}
    const reply=(body:object,status=200)=>route.fulfill({status,contentType:"application/json",body:JSON.stringify(body)});
    if(url.pathname==="/"){await route.fulfill({contentType:"text/html",body:readFileSync(new URL("../public/index.html",import.meta.url),"utf8")});return;}
    if(/^\/[a-z-]+\.(js|css|svg|png|ico)$/.test(url.pathname)){
      await route.fulfill({contentType:url.pathname.endsWith(".js")?"text/javascript":url.pathname.endsWith(".css")?"text/css":"image/png",
        body:readFileSync(new URL("../public"+url.pathname,import.meta.url))});return;
    }
    if(req.method()==="GET"){
      reads.push(url.pathname+url.search);
      if(url.pathname.endsWith("/session")){await reply({ok:true,actor:"owner",role:"owner",appId:"trace",csrfToken:"ux-csrf",environment:"MOCK"});return;}
      if(url.pathname.endsWith("/delta/activity")){await reply({ok:true,actor:"owner",scope:"own-jobs",jobs:state.jobs,notifications:state.notifications,
        unreadCount:state.notifications.filter(n=>n.unread).length,pushPublicKey:null,pushSubscriptions:[]});return;}
      if(url.pathname.endsWith("/resource-usage")){await reply({ok:true,metrics:[],safeguards:{}});return;}
      if(url.pathname.includes("/firmware/")){await reply({ok:true,firmwareReleases:[],firmwareChannels:[]});return;}
      const platform=url.searchParams.get("platform")??"android";
      const releases=platform==="ios"?[]:["one","two"].filter(id=>!state.removed.has(id)).map((id,i)=>({id,app_id:"trace",platform,
        version_name:`1.0.${i+1}`,version_code:i+1,release_tag:`v-${id}`,state:"candidate",archived:0,release_notes:"Notes",created_at:"2026-11-17T00:00:00Z",
        published_channels:"",asset_count:2,r2_available_count:2,apk_count:platform==="android"?1:0,manifest_count:1,patch_count:0}));
      await reply({ok:true,releases,channels:[],announcements:state.notices,storage:null});return;
    }
    expect(req.method()).toBe("POST");expect(req.headers()["x-csrf-token"]).toBe("ux-csrf");
    const body=req.postDataJSON() as Record<string,unknown>;writes.push({path:url.pathname,body});
    if(url.pathname.startsWith("/api/admin/announcements")){
      if(state.failNotice){await reply({errorCode:"BACKEND_UNAVAILABLE",message:"Fixture save failure"},503);return;}
      state.notices=[{id:"notice-one",...body,published:body.published?1:0,pinned:body.pinned?1:0}];
      await reply({ok:true,announcementId:"notice-one"});return;
    }
    if(url.pathname.endsWith("/notifications/read")){
      const ids=(body.ids??[]) as number[];state.notifications.forEach(n=>{if(ids.includes(n.id))n.unread=0;});
      await reply({ok:true,readIds:ids,throughId:body.throughId});return;
    }
    if(url.pathname.endsWith("/notifications/dismiss")){
      const ids=(body.ids??state.notifications.filter(n=>!n.unread).map(n=>n.id)) as number[];
      state.notifications=state.notifications.filter(n=>!ids.includes(n.id));await reply({ok:true,dismissedIds:ids});return;
    }
    if(url.pathname.includes("/delta/jobs/")){
      state.jobs[0].cancelling=true;state.jobs[0].phase="cancelling";
      await reply({ok:true,job:state.jobs[0]});return;
    }
    if(url.pathname.endsWith("/delete")){
      const id=url.pathname.split("/")[4];
      if(id==="two"){await reply({errorCode:"RELEASE_IN_USE",message:"Fixture dependency protects this version"},409);return;}
      state.removed.add(id);await reply({ok:true,deletedD1Rows:1});return;
    }
    await reply({ok:true});
  });
  await page.goto(origin);await expect(page.locator("#versionStrip .version-card")).toHaveCount(2);
  await expect(page.locator("#refreshButton")).toBeEnabled();
  return {state,writes,reads};
}

for(const width of [1440,390]) test(`announcement editor is a matching modal at ${width}px and preserves a failed draft`,async({page},info)=>{
  await page.setViewportSize({width,height:900});const data=await mount(page);
  await page.locator("#appAnnouncementsTab").click();
  await expect(page.locator("#announcementTitle")).toBeHidden();
  await page.locator("#newAnnouncement").click();
  await expect(page.locator("#announcementSheet")).toBeVisible();
  await page.locator("#announcementTitle").fill("New notice");await page.locator("#announcementBody").fill("Preserve this draft");
  await page.locator("#announcementClose").click();await expect(page.locator("#confirmDialog")).toBeVisible();
  await page.locator("#confirmCancel").click();await expect(page.locator("#announcementBody")).toHaveValue("Preserve this draft");
  data.state.failNotice=true;await page.locator("#saveAnnouncement").click();
  await expect(page.locator("#confirmDetail")).toContainText("Fixture save failure");await page.locator("#confirmAccept").click();
  await expect(page.locator("#announcementBody")).toHaveValue("Preserve this draft");
  await page.screenshot({path:info.outputPath("announcement-editor.png"),animations:"disabled"});
  expect(data.writes.filter(w=>w.path.includes("announcements"))).toHaveLength(1);
});

test("platform selection scopes reads and clears cross-platform selections",async({page})=>{
  const data=await mount(page);
  await page.locator('[data-select-version="one"]').check();
  await page.locator("#appPlatform").selectOption("windows");
  await expect.poll(()=>data.reads.some(r=>r.includes("releases?appId=trace&platform=windows"))).toBe(true);
  await expect(page.locator('[data-select-version="one"]')).not.toBeChecked();
  await page.locator("#appPlatform").selectOption("ios");
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(0);
  await expect(page.locator("#appPlatformHint")).toContainText("not configured");
  expect(data.writes).toHaveLength(0);
});

test("batch deletion confirms exact versions and keeps a protected failure selected",async({page})=>{
  const data=await mount(page);
  await page.locator('[data-bulk-action="select-page"]').click();await page.locator('[data-bulk-action="delete"]').click();
  await expect(page.locator("#confirmDetail")).toContainText("v-one");await expect(page.locator("#confirmDetail")).toContainText("v-two");
  await page.locator("#confirmInput").fill("2");await page.locator("#confirmAccept").click();
  await expect(page.locator("#confirmDetail")).toContainText("Deleted");await expect(page.locator("#confirmDetail")).toContainText("dependency");
  await page.locator("#confirmAccept").click();await expect(page.locator('[data-select-version="two"]')).toBeChecked();
  expect(data.writes.filter(w=>w.path.endsWith("/delete")).map(w=>w.path)).toEqual(["/api/admin/releases/one/delete","/api/admin/releases/two/delete"]);
});

test("task controls use icons and long press never cancels or restarts",async({page},info)=>{
  await page.setViewportSize({width:390,height:900});const data=await mount(page);
  await page.locator("#taskButton").click();await expect(page.locator("#taskTitle")).toHaveText("Notification Center");
  const button=page.locator('#taskContent [data-task-control="cancel-restart"]');
  await expect(button.locator("svg use")).toHaveAttribute("href","#i-refresh");
  expect((await button.textContent())?.trim()).toBe("");
  await button.dispatchEvent("pointerdown",{pointerId:1,pointerType:"touch",isPrimary:true,clientX:100,clientY:200});
  await page.waitForTimeout(550);await expect(button).toHaveClass(/tooltip-visible/);
  await page.screenshot({path:info.outputPath("task-icons-tooltip.png"),animations:"disabled"});
  await button.dispatchEvent("pointerup",{pointerId:1,pointerType:"touch",isPrimary:true});await button.dispatchEvent("click");
  expect(data.writes.filter(w=>w.path.includes("/delta/jobs/"))).toHaveLength(0);
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await button.click();await page.locator("#confirmReason").fill("Restart this queued attempt");await page.locator("#confirmAccept").click();
  await expect.poll(()=>data.writes.filter(w=>w.path.endsWith("/cancel-restart")).length).toBe(1);
});

test("notification deletion does not cancel a task and stays deleted after refresh",async({page})=>{
  const data=await mount(page);await page.locator("#taskButton").click();
  await page.locator('[data-task-action="notice-delete"]').click();await page.locator("#confirmAccept").click();
  await expect(page.locator(".task-notification-row")).toHaveCount(0);
  await page.locator('[data-task-action="refresh"]').click();await expect(page.locator(".task-notification-row")).toHaveCount(0);
  expect(data.writes.some(w=>w.path.includes("/delta/jobs/")||w.path.includes("/releases/"))).toBe(false);
});
