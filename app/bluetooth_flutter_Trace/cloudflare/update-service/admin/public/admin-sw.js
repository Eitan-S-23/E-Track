/* No fetch handler: never cache the authenticated Admin or its API responses. */
self.addEventListener("install",event=>event.waitUntil(self.skipWaiting()));
self.addEventListener("activate",event=>event.waitUntil(self.clients.claim()));

function remembered(action, value) {
  return new Promise((resolve,reject)=>{
    const request = indexedDB.open("trace-admin-notification-receipts",1);
    request.onupgradeneeded = ()=>request.result.createObjectStore("receipts");
    request.onerror = ()=>reject(request.error);
    request.onsuccess = ()=>{
      const db = request.result, transaction = db.transaction("receipts",action === "get" ? "readonly" : "readwrite");
      const store = transaction.objectStore("receipts");
      const op = action === "get" ? store.get(value) : store.put(value.id,value.actor);
      let result;
      op.onsuccess = ()=>{ result = op.result; };
      transaction.oncomplete = ()=>{ db.close(); resolve(result); };
      transaction.onerror = ()=>{ db.close(); reject(transaction.error); };
    };
  });
}
self.addEventListener("push",event=>event.waitUntil((async()=>{
  const zh = self.navigator.language.startsWith("zh");
  let title = zh ? "后台有新结果" : "Admin update available";
  let body = zh ? "打开后台查看。若登录已过期，请重新登录。" : "Open Admin to review. Sign in again if your session expired.";
  let tag = "trace-delta-update", receipt = null;
  try {
    const response = await fetch("/api/admin/delta/activity",{credentials:"include",cache:"no-store",redirect:"error",signal:AbortSignal.timeout(10000)});
    if (!response.ok || !response.headers.get("Content-Type")?.includes("application/json")) throw new Error("Session unavailable");
    const value = await response.json();
    if (value.ok !== true || !Array.isArray(value.notifications) || typeof value.actor !== "string") throw new Error("Invalid activity");
    const last = Number(await remembered("get",value.actor).catch(()=>0) ?? 0);
    const latest = value.notifications.find(n=>n.id>last && n.unread);
    if (latest) {
      title = latest.type === "candidate" ? (zh ? "新构建包已入库" : "New candidate registered")
        : latest.status === "ready" ? (zh ? "差分包已生成" : "Delta package ready") : (zh ? "差分生成失败" : "Delta build failed");
      body = `${latest.kind === "firmware" ? "MCU" : latest.kind === "windows" ? "Windows App" : "Android App"} · ${latest.type === "candidate" ? latest.versionName : `${latest.baseVersionCode} → ${latest.targetVersionCode}`}`;
      tag = `trace-delta-${latest.id}`; receipt = {actor:value.actor,id:latest.id};
    } else if (value.notifications.length && last >= value.notifications[0].id) {
      return;
    }
  } catch { /* An expired Access session gets a generic alert, never private task data. */ }
  await self.registration.showNotification(title,{body,tag,data:{url:"/?tasks=1"}});
  if (receipt) await remembered("put",receipt).catch(()=>{});
  for (const client of await self.clients.matchAll({type:"window",includeUncontrolled:true})) client.postMessage({type:"trace-delta-updated"});
})()));
function requestTaskPanel(client) {
  return new Promise(resolve=>{
    const channel = new MessageChannel();
    const finish = accepted=>{
      clearTimeout(timeout); channel.port1.close(); channel.port2.close(); resolve(accepted);
    };
    const timeout = setTimeout(()=>finish(false),600);
    channel.port1.onmessage = event=>finish(event.data?.type === "trace-delta-open-accepted");
    try { client.postMessage({type:"trace-delta-open"},[channel.port2]); }
    catch { finish(false); }
  });
}

self.addEventListener("notificationclick",event=>{
  event.notification.close();
  event.waitUntil((async()=>{
    const windows = await self.clients.matchAll({type:"window",includeUncontrolled:true}).catch(()=>[]);
    const candidates = windows.filter(client=>{
      const url = new URL(client.url);
      return url.origin === self.location.origin && ["/","/index.html"].includes(url.pathname);
    }).sort((a,b)=>Number(b.focused)-Number(a.focused));
    for (const client of candidates.slice(0,2)) {
      try {
        await client.focus();
        if (await requestTaskPanel(client)) return;
      } catch { /* A closed/frozen client must not swallow the notification click. */ }
    }
    // Never reload an existing Admin tab: it may contain an unsaved draft.
    await self.clients.openWindow(new URL("/?tasks=1",self.location.origin).href);
  })());
});
