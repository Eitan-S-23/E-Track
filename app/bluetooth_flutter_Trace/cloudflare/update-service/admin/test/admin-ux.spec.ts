import { readFileSync } from "node:fs";
import { test, expect, type Page } from "@playwright/test";

async function mount(page: Page) {
  const origin="https://ux-admin.test";
  const pageErrors:string[]=[];
  page.on('pageerror',error=>pageErrors.push(error.stack??error.message));
  const writes:Array<{path:string;body:Record<string,unknown>}>=[],reads:string[]=[];
  const state={failNotice:false,releaseIds:["one","two"],failDeleteIds:new Set<string>(),notices:[] as Array<Record<string,unknown>>,notifications:[{
    id:1,type:"candidate",kind:"android",targetReleaseId:"one",versionName:"1.0.1",status:"ready",unread:1,createdAt:1794652000}],
    jobs:[{id:"ux-job",kind:"android",targetReleaseId:"two",baseReleaseId:"one",baseVersionCode:1,targetVersionCode:2,
      status:"queued",phase:"ci_queued",attempt:1,revision:1,createdAt:1794652000,updatedAt:1794652000,
      runUrl:"https://github.com/Eitan-S-23/Trace/actions/runs/12345",cancelling:false}],
    removed:new Set<string>()};
  await page.addInitScript(()=>localStorage.setItem("trace-admin-language","en"));
  await page.route("**/*",async route=>{
    const req=route.request(),url=new URL(req.url());
    if(url.origin!==origin){await route.abort();return;}
    const reply=(body:object,status=200)=>route.fulfill({status,contentType:"application/json",
      headers:{"X-Request-Id":"ux-request"},body:JSON.stringify({requestId:"ux-request",...body})});
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
      if(url.pathname.endsWith("/delta/candidates")){await reply({ok:true,kind:"android",
        target:{releaseId:"two",versionName:"1.0.2",versionCode:2,fullBytes:100000},bases:[],jobs:state.jobs,
        dispatchConfigured:true,appSigningConfigured:true,distributionEnabled:true});return;}
      if(url.pathname.endsWith("/version-inventory")){await reply({ok:true,coverage:"reporting-installations-only",
        firmwareIdentityScope:"installation",uniqueDeviceCount:null,app:[],firmware:[],generatedAt:1794652000});return;}
      if(url.pathname.endsWith("/resource-usage")){await reply({ok:true,metrics:[],safeguards:{}});return;}
      if(url.pathname.includes("/firmware/")){await reply({ok:true,firmwareReleases:[],firmwareChannels:[]});return;}
      const platform=url.searchParams.get("platform")??"android";
      const releases=platform==="ios"?[]:state.releaseIds.filter(id=>!state.removed.has(id)).map((id,i)=>({id,app_id:"trace",platform,
        version_name:`1.0.${i+1}`,version_code:i+1,release_tag:`v-${id}`,state:"candidate",archived:0,release_notes:"Notes",created_at:"2026-11-17T00:00:00Z",
        published_channels:"",asset_count:2,r2_available_count:2,apk_count:platform==="android"?1:0,manifest_count:1,patch_count:0}));
      await reply({ok:true,releases,channels:[],announcements:state.notices,storage:null});return;
    }
    expect(req.method()).toBe("POST");expect(req.headers()["x-csrf-token"]).toBe("ux-csrf");
    const body=req.postDataJSON() as Record<string,unknown>;writes.push({path:url.pathname,body});
    if(url.pathname.startsWith("/api/admin/announcements")){
      if(url.pathname.endsWith("/delete")) {
        const id=url.pathname.split("/")[4];
        if(state.failDeleteIds.has(id)){await reply({errorCode:"RELEASE_CONFLICT",message:"Fixture deletion conflict"},409);return;}
        state.notices=state.notices.filter(row=>row.id!==id);await reply({ok:true});return;
      }
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
      const job=state.jobs.find(row=>row.id===url.pathname.split("/")[5])!;
      if(url.pathname.endsWith("/reconcile")) {
        Object.assign(job,{revision:job.revision+1,runUrl:"https://github.com/Eitan-S-23/Trace/actions/runs/12345",phase:"ci_queued"});
      } else if(url.pathname.endsWith("/delete")) {
        if(state.failDeleteIds.has(job.id)){await reply({errorCode:"R2_VERIFY_FAILED",message:"Fixture R2 deletion failure"},409);return;}
        Object.assign(job,{status:"deleted",phase:"deleted",assetState:"deleted",revision:job.revision+1});
      } else {job.cancelling=true;job.phase="cancelling";}
      await reply({ok:true,job});return;
    }
    if(url.pathname.endsWith("/delete")){
      const id=url.pathname.split("/")[4];
      if(id==="two"){await reply({errorCode:"RELEASE_IN_USE",message:"Fixture dependency protects this version"},409);return;}
      state.removed.add(id);await reply({ok:true,deletedD1Rows:1});return;
    }
    await reply({ok:true});
  });
  await page.goto(origin);expect(pageErrors).toEqual([]);
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(2);
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
  await page.locator('[data-bulk-action="enter"]').click();
  await page.locator('[data-select-version="one"]').check();
  await page.locator("#appPlatform").selectOption("windows");
  await expect.poll(()=>data.reads.some(r=>r.includes("releases?appId=trace&platform=windows"))).toBe(true);
  await expect(page.locator('[data-select-version]')).toHaveCount(0);
  await page.locator('[data-bulk-action="enter"]').click();
  await expect(page.locator('[data-select-version="one"]')).not.toBeChecked();
  await page.locator("#appPlatform").selectOption("ios");
  await expect(page.locator("#versionStrip .version-card")).toHaveCount(0);
  await expect(page.locator("#appPlatformHint")).toContainText("not configured");
  expect(data.writes).toHaveLength(0);
});

test("batch deletion confirms exact versions and keeps a protected failure selected",async({page})=>{
  const data=await mount(page);
  await page.locator('[data-bulk-action="enter"]').click();
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
  // A read acknowledgement/poll can replace the buttons while the finger is down.
  await page.locator('#taskContent [data-task-action="refresh"]').dispatchEvent("click");
  await expect(button).toHaveClass(/tooltip-visible/);
  const tooltip=page.getByRole("tooltip");
  await expect(tooltip).toContainText("original inputs");
  await expect(button).toHaveAttribute("aria-describedby","taskControlTooltip");
  const box=await tooltip.boundingBox();
  expect(box!.x).toBeGreaterThanOrEqual(0);expect(box!.x+box!.width).toBeLessThanOrEqual(390);
  expect(box!.y).toBeGreaterThanOrEqual(0);expect(box!.y+box!.height).toBeLessThanOrEqual(900);
  await page.screenshot({path:info.outputPath("task-icons-tooltip.png"),animations:"disabled"});
  await button.dispatchEvent("pointerup",{pointerId:1,pointerType:"touch",isPrimary:true});await button.dispatchEvent("click");
  expect(data.writes.filter(w=>w.path.includes("/delta/jobs/"))).toHaveLength(0);
  await expect(page.locator("#confirmDialog")).toBeHidden();
  await button.click();await page.locator("#confirmReason").fill("Restart this queued attempt");await page.locator("#confirmAccept").click();
  await expect.poll(()=>data.writes.filter(w=>w.path.endsWith("/cancel-restart")).length).toBe(1);
});

test("task explanations support hover and keyboard focus across a refresh",async({page})=>{
  const data=await mount(page);await page.locator("#taskButton").click();
  const button=page.locator('#taskContent [data-task-control="cancel"]');
  await button.hover();await expect(page.getByRole("tooltip")).toHaveText("Cancel this task");
  await page.mouse.move(0,0);await expect(page.getByRole("tooltip")).toBeHidden();
  await page.keyboard.press("Tab");await button.focus();
  await expect(page.getByRole("tooltip")).toHaveText("Cancel this task");
  await page.locator('#taskContent [data-task-action="refresh"]').dispatchEvent("click");
  await expect(button).toBeFocused();await expect(page.getByRole("tooltip")).toBeVisible();
  await page.keyboard.press("Escape");await expect(page.getByRole("tooltip")).toBeHidden();
  await expect(page.locator("#taskSheet")).toBeVisible();
  expect(data.writes.some(w=>w.path.includes("/delta/jobs/"))).toBe(false);
});

for(const ending of ["move","cancel"]) test(`touch ${ending} dismisses task help without executing an action`,async({page})=>{
  const data=await mount(page);await page.locator("#taskButton").click();
  const button=page.locator('#taskContent [data-task-control="cancel"]');
  const pointer={pointerId:4,pointerType:"touch",isPrimary:true,clientX:100,clientY:200};
  await button.dispatchEvent("pointerdown",pointer);
  await expect(page.getByRole("tooltip")).toBeVisible();
  await button.dispatchEvent(ending==="move"?"pointermove":"pointercancel",{...pointer,clientY:230});
  await expect(page.getByRole("tooltip")).toBeHidden();
  await button.dispatchEvent("pointerup",pointer);await button.dispatchEvent("click");
  await expect(page.locator("#confirmDialog")).toBeHidden();
  expect(data.writes.some(w=>w.path.includes("/delta/jobs/"))).toBe(false);
  await button.click();await expect(page.locator("#confirmDialog")).toBeVisible();
});

test("a failure callback during cancellation stays active and cannot expose retry or hide actions",async({page})=>{
  const data=await mount(page);
  Object.assign(data.state.jobs[0],{status:"failed",phase:"cancelling",cancelling:true});
  await page.locator("#taskButton").click();
  await page.locator('#taskContent [data-task-action="refresh"]').click();
  await expect(page.locator("#taskButton")).toHaveAttribute("aria-label",/1 active/);
  const controls=page.locator("#taskContent [data-task-control]");
  await expect(controls).toHaveCount(2);
  for(const button of await controls.all()) await expect(button).toHaveAttribute("aria-disabled","true");
  await expect(page.locator('[data-task-action="hide-job"]')).toHaveCount(0);
  await page.locator('#taskContent [data-task-target="two"]').click();
  await expect(page.locator('[data-version-operation="delta-retry"]')).toBeDisabled();
  await expect(page.locator("#deltaContent [data-task-control]")).toHaveCount(2);
  expect(data.writes.every(w=>!w.path.endsWith("/retry")&&!w.path.endsWith("/hide-jobs"))).toBe(true);
});

test("notification deletion does not cancel a task and stays deleted after refresh",async({page})=>{
  const data=await mount(page);await page.locator("#taskButton").click();
  await expect(page.locator('[data-select-notice]')).toHaveCount(0);
  await page.locator('[data-task-action="notice-enter"]').click();
  await page.locator('[data-task-action="notice-delete"]').click();await page.locator("#confirmAccept").click();
  await expect(page.locator(".task-notification-row")).toHaveCount(0);
  await page.locator('[data-task-action="refresh"]').click();await expect(page.locator(".task-notification-row")).toHaveCount(0);
  expect(data.writes.some(w=>w.path.includes("/delta/jobs/")||w.path.includes("/releases/"))).toBe(false);
});

for(const width of [1440,390]) test(`version deletion mode is hidden by default and adjacent to its list at ${width}px`,async({page},info)=>{
  await page.setViewportSize({width,height:900});const data=await mount(page);
  await expect(page.locator('[data-select-version]')).toHaveCount(0);
  await expect(page.locator('[data-bulk-action="select-page"]')).toHaveCount(0);
  const entry=page.locator('[data-bulk-action="enter"]');
  await expect(entry.locator('svg use')).toHaveAttribute('href','#i-trash');
  expect((await entry.textContent())?.trim()).toBe('');
  await entry.click();
  const list=await page.locator('#versionStrip').boundingBox(),bar=await page.locator('#releaseBulkActions').boundingBox();
  expect(list!.y-(bar!.y+bar!.height)).toBeGreaterThanOrEqual(0);
  expect(list!.y-(bar!.y+bar!.height)).toBeLessThanOrEqual(16);
  await expect(page.locator('[data-select-version]')).toHaveCount(2);
  await page.locator('[data-bulk-action="select-page"]').click();
  await expect(page.locator('#releaseBulkActions .selection-count')).toHaveText('Selected: 2');
  await page.screenshot({path:info.outputPath('version-delete-mode.png'),animations:'disabled'});
  await page.locator('[data-bulk-action="exit"]').click();
  await expect(page.locator('[data-select-version]')).toHaveCount(0);
  await entry.click();await expect(page.locator('[data-select-version="one"]')).not.toBeChecked();
  expect(data.writes).toHaveLength(0);
});

test('unbound task controls respond without a preliminary Sync click',async({page})=>{
  const data=await mount(page);Object.assign(data.state.jobs[0],{runUrl:'',phase:'ci_pending'});
  await page.locator('#taskButton').click();await page.locator('[data-task-action="refresh"]').click();
  await expect(page.locator('#taskContent')).toContainText('Looking up the build run');
  const cancel=page.locator('#taskContent [data-task-control="cancel"]');
  await expect(cancel).toHaveAttribute('aria-disabled','false');
  await cancel.click();await expect(page.locator('#confirmDialog')).toBeVisible();
  await page.locator('#confirmReason').fill('Cancel while build binding is being looked up');
  await page.locator('#confirmAccept').click();
  await expect.poll(()=>data.writes.filter(w=>w.path.endsWith('/cancel')).length).toBe(1);
  expect(data.writes.some(w=>w.path.endsWith('/reconcile'))).toBe(false);
});

test('Sync performs the exact job operation directly without a reason dialog',async({page})=>{
  const data=await mount(page);await page.locator('#taskButton').click();
  await page.locator('#taskContent [data-task-target="two"]').click();
  const sync=page.locator('[data-version-operation="delta-reconcile"]');
  await expect(sync).toHaveText('Sync');await sync.click();
  await expect.poll(()=>data.writes.filter(w=>w.path.endsWith('/reconcile')).length).toBe(1);
  await expect(page.locator('#confirmDialog')).toBeHidden();
  expect(data.writes.find(w=>w.path.endsWith('/reconcile'))?.body).toEqual({expectedRevision:1});
  await expect(page.locator('#deltaContent')).toContainText('Build results synchronized');
});

test('announcement batch deletion spans selected pages and retains failed items',async({page})=>{
  const data=await mount(page);
  data.state.notices=Array.from({length:8},(_,i)=>({id:`notice-${i}`,title:`Notice ${i}`,body:`Body ${i}`,published:1,pinned:0}));
  data.state.failDeleteIds.add('notice-2');await page.locator('#refreshButton').click();
  await page.locator('#appAnnouncementsTab').click();
  await expect(page.locator('.announcement-card')).toHaveCount(6);
  await expect(page.locator('[data-select-announcement]')).toHaveCount(0);
  await page.locator('[data-announcement-bulk="enter"]').click();
  await page.locator('[data-announcement-bulk="select-page"]').click();
  await page.locator('[data-announcement-page="1"]').click();
  await expect(page.locator('.announcement-card')).toHaveCount(2);
  await page.locator('[data-announcement-bulk="select-page"]').click();
  await expect(page.locator('#announcementBulkActions .selection-count')).toHaveText('Selected: 8');
  await page.locator('[data-announcement-bulk="delete"]').click();
  await page.locator('#confirmInput').fill('8');await page.locator('#confirmAccept').click();
  await expect(page.locator('#confirmDetail')).toContainText('Fixture deletion conflict');
  await page.locator('#confirmAccept').click();
  await expect(page.locator('.announcement-card')).toHaveCount(1);
  await expect(page.locator('[data-select-announcement="notice-2"]')).toBeChecked();
  expect(data.writes.filter(w=>w.path.startsWith('/api/admin/announcements/')&&w.path.endsWith('/delete'))).toHaveLength(8);
});

test('generated delta files support individual and bulk deletion without touching original packages',async({page})=>{
  const data=await mount(page);
  Object.assign(data.state.jobs[0],{status:'ready',phase:'ready',fileName:'one.vcdiff',sizeBytes:1200,enabled:false});
  data.state.jobs.push(Object.assign({...data.state.jobs[0]},{id:'second-delta',fileName:'two.vcdiff',baseVersionCode:3}));
  data.state.jobs.push(Object.assign({...data.state.jobs[0]},{id:'enabled-delta',fileName:'three.vcdiff',enabled:true}));
  data.state.failDeleteIds.add('second-delta');
  await page.locator('#taskButton').click();await page.locator('[data-task-action="refresh"]').click();
  await page.locator('#taskContent [data-task-target="two"]').first().click();
  await expect(page.locator('[data-delta-file]')).toHaveCount(0);
  await page.locator('[data-version-operation="delta-delete-enter"]').click();
  await expect(page.locator('[data-delta-file]')).toHaveCount(2);
  const first=page.locator('[data-delta-file="ux-job"]');await first.focus();
  await page.locator('[data-version-operation="delta-reload"]').dispatchEvent('click');
  await expect(page.locator('[data-version-operation="delta-reload"]')).toBeEnabled();await expect(first).toBeFocused();
  await page.locator('[data-version-operation="delta-delete-select"]').click();
  await page.locator('[data-version-operation="delta-delete-selected"]').click();
  await page.locator('#confirmReason').fill('Remove obsolete delta files');await page.locator('#confirmInput').fill('2');
  await page.locator('#confirmAccept').click();await expect(page.locator('#confirmDetail')).toContainText('Fixture R2 deletion failure');
  await page.locator('#confirmAccept').click();
  await expect(page.locator('[data-delta-file="second-delta"]')).toBeChecked();
  await expect(page.locator('[data-delta-file="ux-job"]')).toHaveCount(0);
  data.state.failDeleteIds.clear();
  await page.locator('[data-version-operation="delta-delete-selected"]').click();
  await page.locator('#confirmReason').fill('Retry the remaining deletion');await page.locator('#confirmInput').fill('1');
  await page.locator('#confirmAccept').click();await expect(page.locator('#confirmDetail')).toContainText('File deleted');
  expect(data.writes.filter(w=>w.path.endsWith('/delete')).map(w=>w.path)).toEqual([
    '/api/admin/delta/jobs/ux-job/delete','/api/admin/delta/jobs/second-delta/delete','/api/admin/delta/jobs/second-delta/delete']);
});

test('announcement deletion selection unlocks after refresh and resets on another list',async({page})=>{
  const data=await mount(page);data.state.notices=[{id:'notice',title:'Notice',body:'Body',published:1,pinned:0}];
  await page.locator('#refreshButton').click();await page.locator('#appAnnouncementsTab').click();
  await page.locator('[data-announcement-bulk="enter"]').click();
  const input=page.locator('[data-select-announcement="notice"]');await input.check();
  await page.locator('#refreshButton').click();await expect(page.locator('#refreshButton')).toBeEnabled();
  await expect(input).toBeEnabled();await expect(input).toBeChecked();await input.uncheck();
  await page.locator('#appReleasesTab').click();await page.locator('#appAnnouncementsTab').click();
  await expect(page.locator('[data-select-announcement]')).toHaveCount(0);
  expect(data.writes).toHaveLength(0);
});

test('notification selection retains keyboard focus across read-only polling',async({page})=>{
  const data=await mount(page);await page.locator('#taskButton').click();
  await page.locator('[data-task-action="notice-enter"]').click();
  const input=page.locator('[data-select-notice="1"]');await input.check();await input.focus();
  await page.locator('[data-task-action="refresh"]').dispatchEvent('click');
  await expect(page.locator('[data-task-action="refresh"]')).toBeEnabled();await expect(input).toBeFocused();
  await expect(input).toBeChecked();expect(data.writes.some(w=>w.path.endsWith('/dismiss'))).toBe(false);
});

test('scrolling beyond both ends of the version list moves the surrounding page',async({page})=>{
  await page.setViewportSize({width:390,height:700});const data=await mount(page);
  data.state.releaseIds=Array.from({length:12},(_,i)=>`version-${i}`);await page.locator('#refreshButton').click();
  const list=page.locator('#versionStrip');await list.scrollIntoViewIfNeeded();
  await list.evaluate(node=>node.scrollTop=node.scrollHeight);
  await expect.poll(()=>list.evaluate(node=>node.scrollHeight>node.clientHeight)).toBe(true);
  await list.hover();const before=await page.evaluate(()=>scrollY);await page.mouse.wheel(0,300);
  await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(before);
  await list.scrollIntoViewIfNeeded();await list.evaluate(node=>node.scrollTop=0);await list.hover();
  const top=await page.evaluate(()=>scrollY);expect(top).toBeGreaterThan(0);await page.mouse.wheel(0,-300);
  await expect.poll(()=>page.evaluate(()=>scrollY)).toBeLessThan(top);
});

test('continued touch swipes at version-list boundaries scroll outside without opening details',async({browser})=>{
  const context=await browser.newContext({viewport:{width:390,height:700},isMobile:true,hasTouch:true});
  try {
    const page=await context.newPage(),data=await mount(page);
    data.state.releaseIds=Array.from({length:12},(_,i)=>`touch-${i}`);await page.locator('#refreshButton').click();
    const list=page.locator('#versionStrip'),cdp=await context.newCDPSession(page);
    async function swipe(direction:number) {
      const box=(await list.boundingBox())!,x=box.x+box.width/2,y=box.y+box.height/2;
      await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});
      for(let step=1;step<=6;step++) {
        await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y+direction*step*18}]});
        await page.waitForTimeout(30);
      }
      await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    }
    await list.scrollIntoViewIfNeeded();await list.evaluate(node=>node.scrollTop=node.scrollHeight);
    const before=await page.evaluate(()=>scrollY);await swipe(-1);
    await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(before);
    await page.waitForTimeout(300);
    await list.scrollIntoViewIfNeeded();await list.evaluate(node=>node.scrollTop=0);
    const top=await page.evaluate(()=>scrollY);await swipe(1);
    await expect.poll(()=>page.evaluate(()=>scrollY)).toBeLessThan(top);
    await expect(page.locator('[role="dialog"]:visible')).toHaveCount(0);
    expect(data.writes).toHaveLength(0);
  } finally {await context.close();}
});
