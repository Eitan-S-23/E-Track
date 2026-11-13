import {readFileSync,writeFileSync} from "node:fs";
import {createServer} from "node:http";
import {test,expect} from "@playwright/test";

test("service worker handles push, closed pages and expired Access with an explicit mock OS notification sink",async({browser},info)=>{
  const source=readFileSync(new URL("../public/admin-sw.js",import.meta.url),"utf8");
  let expired=false;
  const diagnostics:unknown[]=[];
  const notifications=[{id:1,kind:"android",baseVersionCode:86,targetVersionCode:102,status:"ready",unread:1}];
  const server=createServer((request,response)=>{
    diagnostics.push({request:request.url});
    if(request.url==="/admin-sw.js") {response.writeHead(200,{"Content-Type":"text/javascript","Cache-Control":"no-store"});response.end(source);return;}
    if(request.url==="/api/admin/delta/activity") {
      if(expired) {response.writeHead(302,{Location:"/login"});response.end();return;}
      response.writeHead(200,{"Content-Type":"application/json"});response.end(JSON.stringify({ok:true,actor:"mock-owner",notifications}));return;
    }
    response.writeHead(200,{"Content-Type":"text/html"});response.end("<!doctype html><title>MOCK notification test</title><p>No cloud operations</p>");
  });
  await new Promise<void>(resolve=>server.listen(0,"127.0.0.1",resolve));
  const address=server.address();if(!address||typeof address==="string") throw new Error("Missing local test server");
  const origin=`http://127.0.0.1:${address.port}`;
  const context=await browser.newContext({serviceWorkers:"allow"});
  context.on("weberror",event=>diagnostics.push({error:event.error().message}));
  context.on("console",event=>diagnostics.push({console:event.text()}));
  try {
    const monitor=await context.newPage(),cdp=await context.newCDPSession(monitor);
    let registrationId="";
    cdp.on("ServiceWorker.workerRegistrationUpdated",event=>{
      registrationId=event.registrations.find(row=>row.scopeURL===origin+"/")?.registrationId??registrationId;
    });
    await cdp.send("ServiceWorker.enable");
    let page=await context.newPage();await page.goto(origin);
    await page.evaluate(async()=>{await navigator.serviceWorker.register("/admin-sw.js");await navigator.serviceWorker.ready;});
    const worker=context.serviceWorkers()[0]??await context.waitForEvent("serviceworker");
    // Headless Shell does not implement notification permission. Only the OS
    // boundary is replaced; the push event, fetch, IndexedDB and script are real.
    await worker.evaluate("self.testNotifications=[];self.registration.showNotification=async(title,options)=>{self.testNotifications.push({title,...options})}");
    const tags=()=>worker.evaluate("self.testNotifications.map(n=>n.tag)");
    await expect.poll(()=>registrationId).not.toBe("");
    const push=()=>cdp.send("ServiceWorker.deliverPushMessage",{origin,registrationId,data:""});
    await push();
    await expect.poll(tags).toContain("trace-delta-1");
    await expect.poll(()=>worker.evaluate("remembered('get','mock-owner')")).toBe(1);
    await push();
    await page.waitForTimeout(150);
    expect(await tags()).toEqual(["trace-delta-1"]);
    await page.close();
    notifications.unshift({id:2,kind:"firmware",baseVersionCode:30320,targetVersionCode:30324,status:"failed",unread:1});
    await push();
    page=await context.newPage();await page.goto(origin);
    await expect.poll(tags).toContain("trace-delta-2");
    expired=true;await push();
    await expect.poll(tags).toContain("trace-delta-update");
    const generic=await worker.evaluate("self.testNotifications.find(n=>n.tag==='trace-delta-update').body");
    expect(generic).not.toContain("30320");expect(generic).not.toContain("102");
  } finally {writeFileSync(info.outputPath("notification-diagnostics.json"),JSON.stringify(diagnostics,null,2));await context.close();await new Promise<void>(resolve=>server.close(()=>resolve()));}
});
