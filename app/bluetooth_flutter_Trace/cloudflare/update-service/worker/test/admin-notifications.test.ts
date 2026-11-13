import { env } from "cloudflare:workers";
import { beforeEach, afterEach, describe, it, expect, vi } from "vitest";
import { deltaActivity, deliverNotifications, pushEndpoint, readNotifications, subscribeNotifications, unsubscribeNotifications, vapidAuthorization } from "../src/admin_notifications";
import type { WorkerEnv } from "../src/types";

let config: WorkerEnv;
const endpoint = "https://fcm.googleapis.com/fcm/send/unit-test-endpoint";
const encode = (bytes: ArrayBuffer) => Buffer.from(bytes).toString("base64url");
let verificationKey: CryptoKey;
beforeEach(async()=>{
  await env.DB.batch(["admin_notification_deliveries","admin_notifications","admin_candidate_events","admin_push_deliveries","delta_notifications","admin_notification_reads","admin_push_subscriptions","delta_job_events","delta_job_attempts","delta_jobs"]
    .map(table=>env.DB.prepare(`DELETE FROM ${table}`)));
  const keys = await crypto.subtle.generateKey({name:"ECDSA",namedCurve:"P-256"},true,["sign","verify"]);
  verificationKey = keys.publicKey;
  config = {...env,ADMIN_PUSH_PUBLIC_KEY:encode(await crypto.subtle.exportKey("raw",keys.publicKey)),
    ADMIN_PUSH_PRIVATE_JWK:JSON.stringify(await crypto.subtle.exportKey("jwk",keys.privateKey)),ADMIN_PUSH_SUBJECT:"https://admin.example.test"};
});
afterEach(()=>vi.useRealTimers());
async function insert(actor="owner",kind="android",number=1) {
  const id = "delta_"+String(number).padStart(64,"0"), now=Math.floor(Date.now()/1000), hash="a".repeat(64);
  await env.DB.prepare(`INSERT INTO delta_jobs(id,kind,target_release_id,base_release_id,target_sha256,base_sha256,base_version_code,target_version_code,
    status,input_json,input_sha256,workflow_commit,workflow_ref,actor,reason,created_at,updated_at)
    VALUES(?,?,?,'base',?,?,86,102,'running','{}',?,?,?,?,'test',?,?)`)
    .bind(id,kind,`target-${number}`,hash,hash,hash,"b".repeat(40),"dev/test",actor,now,now).run();
  return id;
}
async function finish(id:string,status="ready") {
  await env.DB.prepare("UPDATE delta_jobs SET status=?,updated_at=? WHERE id=?").bind(status,Math.floor(Date.now()/1000),id).run();
}
async function subscribe(actor="owner",url=endpoint) {
  return (await subscribeNotifications(config,actor,{endpoint:url,applicationServerKey:config.ADMIN_PUSH_PUBLIC_KEY})).json<{id:string}>();
}
describe("durable Admin notifications",()=>{
  it("records only real terminal transitions and isolates the actor's history",async()=>{
    const job=await insert(); await insert("other","firmware",2);
    expect((await (await deltaActivity(config,"owner")).json<{notifications:unknown[]}>()).notifications).toHaveLength(0);
    await finish(job);
    const body=await (await deltaActivity(config,"owner")).json<{jobs:unknown[];notifications:Array<{id:number;status:string}>;unreadCount:number}>();
    expect(body.jobs).toHaveLength(1);expect(body.notifications).toHaveLength(1);expect(body.notifications[0].status).toBe("ready");expect(body.unreadCount).toBe(1);
    expect((await (await deltaActivity(config,"other")).json<{unreadCount:number}>()).unreadCount).toBe(0);
    await env.DB.prepare("UPDATE delta_jobs SET enabled=1 WHERE id=?").bind(job).run();
    expect((await (await deltaActivity(config,"owner")).json<{notifications:unknown[]}>()).notifications).toHaveLength(1);
  });
  it("read cursors are monotonic, actor-bound, and cannot mark future results read",async()=>{
    await finish(await insert(),"failed");
    await readNotifications(config,"owner",{throughId:Number.MAX_SAFE_INTEGER});
    await readNotifications(config,"owner",{throughId:0});
    await finish(await insert("owner","firmware",2));
    const body=await (await deltaActivity(config,"owner")).json<{unreadCount:number}>();expect(body.unreadCount).toBe(1);
    await expect(readNotifications(config,"owner",{throughId:-1})).rejects.toThrow();
  });
  it("validates push destinations and prevents subscription theft",async()=>{
    for(const value of ["http://fcm.googleapis.com/fcm/send/x","https://localhost/","https://fcm.googleapis.com.evil.test/fcm/send/x",
      "https://fcm.googleapis.com:444/fcm/send/x","https://a:b@fcm.googleapis.com/fcm/send/x","https://fcm.googleapis.com/fcm/send/x#secret"]) expect(()=>pushEndpoint(value)).toThrow();
    expect(pushEndpoint("https://web.push.apple.com/example")).toContain("apple.com");
    expect(pushEndpoint("https://updates.push.services.mozilla.com/wpush/v2/example")).toContain("mozilla.com");
    const result=await subscribe();
    await expect(subscribe("other")).rejects.toMatchObject({status:409});
    await unsubscribeNotifications(config,"other",{id:result.id});
    expect(await env.DB.prepare("SELECT id FROM admin_push_subscriptions").first()).not.toBeNull();
    await unsubscribeNotifications(config,"owner",{id:result.id});
    expect(await env.DB.prepare("SELECT id FROM admin_push_subscriptions").first()).toBeNull();
  });
  it("marks only the viewed App or MCU result, preserving unseen, foreign and future results",async()=>{
    await finish(await insert("owner","android",1));
    await finish(await insert("owner","firmware",2));
    await finish(await insert("other","android",3));
    const activity = async(actor="owner")=>(await deltaActivity(config,actor)).json<{unreadCount:number;notifications:Array<{id:number;unread:number}>}>();
    const own = await activity(), foreign = await activity("other"), viewed = own.notifications[0].id;
    const body = await (await readNotifications(config,"owner",{ids:[viewed,foreign.notifications[0].id,Number.MAX_SAFE_INTEGER]})).json<{readIds:number[]}>();
    expect(body.readIds).toEqual([viewed]);
    expect((await activity()).unreadCount).toBe(1);
    expect((await activity()).notifications.map(n=>n.unread)).toEqual([0,1]);
    expect((await activity("other")).unreadCount).toBe(1);
    await readNotifications(config,"owner",{ids:[viewed]});
    expect((await activity()).unreadCount).toBe(1);
    await finish(await insert("owner","android",4));
    expect((await activity()).unreadCount).toBe(2);
    await readNotifications(config,"owner",{throughId:viewed});
    expect((await activity()).unreadCount).toBe(1);
  });
  it("rejects malformed or unbounded per-result reads without changing any read state",async()=>{
    await finish(await insert());
    for (const ids of [[],[0],[-1],[1.5],["1"],[1,1],Array.from({length:31},(_,i)=>i+1)]) {
      await expect(readNotifications(config,"owner",{ids})).rejects.toThrow();
    }
    await expect(readNotifications(config,"owner",{ids:[1],throughId:1})).rejects.toThrow();
    expect((await (await deltaActivity(config,"owner")).json<{unreadCount:number}>()).unreadCount).toBe(1);
  });
  it("caps active browser subscriptions without replaying old notifications",async()=>{
    await finish(await insert());
    for(let i=0;i<5;i++) await subscribe("owner",endpoint+i);
    await expect(subscribe("owner",endpoint+"six")).rejects.toMatchObject({status:429});
    expect((await env.DB.prepare("SELECT * FROM admin_notification_deliveries").all()).results).toHaveLength(0);
  });
  it("signs valid ES256 VAPID claims and sends no task data in the push body",async()=>{
    const header=await vapidAuthorization(config,endpoint);
    const token=header.match(/^vapid t=([^,]+)/)![1],parts=token.split(".");
    const claims=JSON.parse(Buffer.from(parts[1],"base64url").toString());
    expect(claims.aud).toBe("https://fcm.googleapis.com");expect(claims.exp).toBeGreaterThan(Date.now()/1000);
    expect(await crypto.subtle.verify({name:"ECDSA",hash:"SHA-256"},verificationKey,Buffer.from(parts[2],"base64url"),new TextEncoder().encode(parts[0]+"."+parts[1]))).toBe(true);
    await subscribe(); await finish(await insert());
    const send=vi.fn<typeof fetch>(async()=>new Response(null,{status:201}));
    await deliverNotifications(config,send);await deliverNotifications(config,send);
    expect(send).toHaveBeenCalledTimes(1);expect(send.mock.calls[0][1]?.body).toBeUndefined();
    expect(send.mock.calls[0][1]?.redirect).toBe("manual");
    expect((await env.DB.prepare("SELECT status FROM admin_notification_deliveries").first<{status:string}>())?.status).toBe("sent");
  });
  it("retains results and bounds push retries when the push service is offline",async()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-13T00:00:00Z"));
    await subscribe();await finish(await insert("owner","firmware"),"failed");
    const send=vi.fn<typeof fetch>(async()=>new Response(null,{status:503}));
    for(let i=0;i<6;i++) {await deliverNotifications(config,send);vi.setSystemTime(Date.now()+301000);}
    expect(send).toHaveBeenCalledTimes(5);
    expect((await env.DB.prepare("SELECT status FROM admin_notification_deliveries").first<{status:string}>())?.status).toBe("failed");
    expect((await (await deltaActivity(config,"owner")).json<{unreadCount:number}>()).unreadCount).toBe(1);
  });
  it("expired subscriptions are removed without losing the completion event",async()=>{
    await subscribe();await finish(await insert());
    await deliverNotifications(config,async()=>new Response(null,{status:410}));
    expect(await env.DB.prepare("SELECT id FROM admin_push_subscriptions").first()).toBeNull();
    expect((await (await deltaActivity(config,"owner")).json<{unreadCount:number}>()).unreadCount).toBe(1);
  });
});
