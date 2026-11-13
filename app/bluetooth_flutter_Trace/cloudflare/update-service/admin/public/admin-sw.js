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
  let title = zh ? "差分任务有新结果" : "Delta task updated";
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
      title = latest.status === "ready" ? (zh ? "差分包已生成" : "Delta package ready") : (zh ? "差分生成失败" : "Delta build failed");
      body = `${latest.kind === "firmware" ? "MCU" : "App"} · ${latest.baseVersionCode} → ${latest.targetVersionCode}`;
      tag = `trace-delta-${latest.id}`; receipt = {actor:value.actor,id:latest.id};
    } else if (value.notifications.length && last >= value.notifications[0].id) {
      return;
    }
  } catch { /* An expired Access session gets a generic alert, never private task data. */ }
  await self.registration.showNotification(title,{body,tag,data:{url:"/?tasks=1"}});
  if (receipt) await remembered("put",receipt).catch(()=>{});
  for (const client of await self.clients.matchAll({type:"window",includeUncontrolled:true})) client.postMessage({type:"trace-delta-updated"});
})()));
self.addEventListener("notificationclick",event=>{
  event.notification.close();
  event.waitUntil((async()=>{
    for (const client of await self.clients.matchAll({type:"window",includeUncontrolled:true})) {
      if (new URL(client.url).origin === self.location.origin) {
        await client.focus(); client.postMessage({type:"trace-delta-open"}); return;
      }
    }
    await self.clients.openWindow("/?tasks=1");
  })());
});
