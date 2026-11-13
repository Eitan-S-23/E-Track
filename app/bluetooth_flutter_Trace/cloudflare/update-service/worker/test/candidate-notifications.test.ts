import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { candidateArrival, deltaActivity, readNotifications } from "../src/admin_notifications";
import { metadata, register, uploadFixture } from "./firmware-fixture";

beforeEach(async()=>{
  await env.DB.batch(["admin_notification_deliveries","admin_notifications","admin_candidate_events","admin_push_deliveries",
    "delta_notifications","admin_notification_reads","admin_push_subscriptions"].map(table=>env.DB.prepare(`DELETE FROM ${table}`)));
});
afterEach(()=>vi.useRealTimers());
type Activity = {unreadCount:number;notifications:Array<{id:number;type:string;kind:string;versionName:string;targetReleaseId:string;unread:number}>};
const activity = async(actor="owner")=>(await deltaActivity(env,actor)).json<Activity>();
let sequence = 0;
async function appCandidate(upload = true) {
  const n = ++sequence, releaseTag = `v30.0.${n}`, fileName = "candidate.apk", body = new TextEncoder().encode("candidate bytes");
  const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",body)),b=>b.toString(16).padStart(2,"0")).join("");
  const input = { appId:"trace",platform:"android",releaseTag,runId:`candidate-${n}`,commitSha:"a".repeat(40),
    versionName:`30.0.${n}`,versionCode:300000+n,releaseNotes:"candidate",minClientVersionCode:0,capabilities:[],
    payloadSignature:{signature:"c2ln"},isFormalRelease:true,fixedSigningConfigured:true,patches:[],
    assets:[{assetType:"apk",fileName,sha256,sizeBytes:body.length,r2Verified:true,
      r2Key:`trace/releases/${300000+n}-${releaseTag}/android/${fileName}`,
      githubUrl:`https://github.com/Eitan-S-23/Trace/releases/download/${releaseTag}/${fileName}`}] };
  if (upload) await env.RELEASES_BUCKET.put(input.assets[0].r2Key,body,{customMetadata:{sha256}});
  return input;
}
const registerApp = (input:unknown)=>SELF.fetch("https://example.test/api/ci/releases",{method:"POST",
  headers:{Authorization:"Bearer test-deploy-token","Content-Type":"application/json"},body:JSON.stringify(input)});
const event = (releaseId="candidate-direct")=>candidateArrival(env,{appId:"trace",kind:"android",releaseId,
  versionName:"30.0.1",versionCode:300001,commitSha:"a".repeat(40),runId:"test"});

describe("CI candidate arrivals",()=>{
  it("notifies after verified App registration without publishing, and deduplicates callbacks",async()=>{
    const input = await appCandidate();
    expect((await activity()).unreadCount).toBe(0);
    const response=await registerApp(input), body=await response.json<{releaseId:string}>();
    expect(response.status).toBe(201);
    expect((await registerApp(input)).status).toBe(200);
    const result=await activity();
    expect(result.notifications).toHaveLength(1);
    expect(result.notifications[0]).toMatchObject({type:"candidate",kind:"android",versionName:input.versionName,targetReleaseId:body.releaseId});
    expect(await env.DB.prepare("SELECT id FROM channels WHERE current_release_id=?").bind(body.releaseId).first()).toBeNull();
  });
  it("does not confuse compile success, failed upload, metadata mismatch or rejected registration with arrival",async()=>{
    const input=await appCandidate(false);
    expect((await activity()).unreadCount).toBe(0);
    expect((await registerApp(input)).status).toBe(400);
    const valid=await appCandidate();valid.assets[0].sizeBytes++;
    expect((await registerApp(valid)).status).toBe(400);
    valid.isFormalRelease=false;
    expect((await registerApp(valid)).status).toBe(403);
    expect((await activity()).notifications).toEqual([]);
  });
  it("records MCU arrival only after object validation and the ready transaction",async()=>{
    const input=metadata();
    expect((await register(input)).status).not.toBe(201);
    expect((await activity()).notifications).toEqual([]);
    await uploadFixture(input);
    const response=await register(input),body=await response.json<{releaseId:string}>();
    expect(response.status).toBe(201);expect((await register(input)).status).toBe(200);
    expect((await activity()).notifications).toMatchObject([{type:"candidate",kind:"firmware",versionName:input.versionName,targetReleaseId:body.releaseId}]);
    expect(await env.DB.prepare("SELECT id FROM firmware_channels WHERE current_release_id=?").bind(body.releaseId).first()).toBeNull();
  });
  it("rolls back both event and outbox if the registration transaction fails",async()=>{
    const now=Math.floor(Date.now()/1000);
    await env.DB.prepare("INSERT INTO admin_push_subscriptions VALUES ('test','owner','https://fcm.googleapis.com/fcm/send/test',?,?)").bind(now-1,now+3600).run();
    await expect(env.DB.batch([event(),env.DB.prepare("INSERT INTO apps(id,name) VALUES (NULL,NULL)")])).rejects.toThrow();
    expect((await activity()).notifications).toEqual([]);
    expect(await env.DB.prepare("SELECT event_id FROM admin_notification_deliveries").first()).toBeNull();
  });
  it("retains arrivals for non-subscribers, with independent read state and no retrospective push enrollment",async()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date("2026-11-14T12:00:00Z"));
    await event().run();
    const own=await activity();expect(own.unreadCount).toBe(1);
    await readNotifications(env,"owner",{ids:[own.notifications[0].id]});
    expect((await activity()).unreadCount).toBe(0);
    vi.setSystemTime(Date.now()+2000);
    const now=Math.floor(Date.now()/1000);
    await env.DB.prepare("INSERT INTO admin_push_subscriptions VALUES ('test','viewer','https://fcm.googleapis.com/fcm/send/test',?,?)").bind(now,now+3600).run();
    expect((await activity("viewer")).unreadCount).toBe(1);
    expect(await env.DB.prepare("SELECT event_id FROM admin_notification_deliveries").first()).toBeNull();
    await event("candidate-next").run();
    expect((await activity("viewer")).unreadCount).toBe(2);
    expect((await env.DB.prepare("SELECT event_id FROM admin_notification_deliveries").all()).results).toHaveLength(1);
  });
  it("does not fan out unrelated apps or turn a historical idempotent registration into a new arrival",async()=>{
    await candidateArrival(env,{appId:"other",kind:"android",releaseId:"foreign",versionName:"1",versionCode:1,commitSha:"a",runId:"r"}).run();
    expect((await activity()).notifications).toEqual([]);
    const input=await appCandidate();expect((await registerApp(input)).status).toBe(201);
    // Simulates a release already present when the event migration was deployed.
    await env.DB.prepare("DELETE FROM admin_candidate_events").run();
    expect((await registerApp(input)).status).toBe(200);
    expect((await activity()).notifications).toEqual([]);
  });
});
