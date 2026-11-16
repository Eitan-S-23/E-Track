import { env } from "cloudflare:workers";
import { beforeEach, expect, it } from "vitest";
import { candidateArrival, deltaActivity, dismissNotifications, hideCompletedJobs, readNotifications } from "../src/admin_notifications";
import { handleAnnouncements } from "../src/announcements";
import { retainInputs } from "./notification-fixture";

beforeEach(async()=>{
  await env.DB.batch(["admin_hidden_delta_jobs","admin_notification_deliveries","admin_notifications","admin_candidate_events",
    "admin_push_deliveries","delta_notifications","admin_notification_reads","delta_job_events","delta_job_attempts","delta_jobs"]
    .map(table=>env.DB.prepare(`DELETE FROM ${table}`)));
});
async function candidate(n:number) {
  await candidateArrival(env,{appId:"trace",kind:"android",releaseId:`ux-release-${n}`,versionName:`1.0.${n}`,
    versionCode:n,commitSha:"a".repeat(40),runId:String(n)}).run();
}
const activity=async(actor="owner")=>(await deltaActivity(env,actor)).json<{
  notifications:Array<{id:number;unread:number}>;unreadCount:number;jobs:Array<{id:string;attempt:number}>}>();

it("dismissed candidates do not reappear through backfill or affect another actor",async()=>{
  await candidate(1);
  const first=await activity(),id=first.notifications[0].id;
  await dismissNotifications(env,"owner",{ids:[id]});
  expect((await activity()).notifications).toEqual([]);
  expect((await activity()).unreadCount).toBe(0);
  expect((await activity("other")).notifications).toHaveLength(1);
  expect(await env.DB.prepare("SELECT dismissed_at FROM admin_notifications WHERE id=?").bind(id).first("dismissed_at")).not.toBeNull();
});

it("clear-read retains unread, future and foreign messages",async()=>{
  await candidate(1);await candidate(2);
  const first=await activity(),viewed=first.notifications[1].id,throughId=first.notifications[0].id;
  await readNotifications(env,"owner",{ids:[viewed]});
  await candidate(3);await activity();
  await dismissNotifications(env,"owner",{mode:"read",throughId});
  const remaining=await activity();
  expect(remaining.notifications).toHaveLength(2);expect(remaining.unreadCount).toBe(2);
  expect((await activity("other")).notifications).toHaveLength(3);
  await expect(dismissNotifications(env,"owner",{ids:[1,1]})).rejects.toThrow();
});

it("hiding a completed attempt keeps history and does not hide a subsequent retry",async()=>{
  await retainInputs("android","ux-hide-target","ux-hide-base");
  await env.DB.prepare(`INSERT INTO delta_jobs(id,kind,target_release_id,base_release_id,target_sha256,base_sha256,base_version_code,target_version_code,
    status,input_json,input_sha256,workflow_commit,workflow_ref,actor,reason,created_at,updated_at)
    VALUES('ux-hide','android','ux-hide-target','ux-hide-base',?,?,1,2,'failed','{}',?,?,'dev/test','owner','test',1,1)`)
    .bind("a".repeat(64),"b".repeat(64),"c".repeat(64),"d".repeat(40)).run();
  await expect(hideCompletedJobs(env,"other",{ids:["ux-hide"],attempts:{"ux-hide":1}})).rejects.toThrow();
  await expect(hideCompletedJobs(env,"owner",{ids:["ux-hide"],attempts:{"ux-hide":2}})).rejects.toMatchObject({code:"CAS_CONFLICT"});
  await hideCompletedJobs(env,"owner",{ids:["ux-hide"],attempts:{"ux-hide":1}});
  expect((await activity()).jobs).toEqual([]);
  expect(await env.DB.prepare("SELECT id FROM delta_jobs WHERE id='ux-hide'").first()).not.toBeNull();
  await env.DB.prepare("UPDATE delta_jobs SET status='dispatching',attempt=2 WHERE id='ux-hide'").run();
  expect((await activity()).jobs[0].attempt).toBe(2);
  await expect(hideCompletedJobs(env,"owner",{ids:["ux-hide"],attempts:{"ux-hide":2}})).rejects.toThrow();
});

it("iOS can read manual notices without receiving Android release announcements",async()=>{
  const response=await handleAnnouncements(new Request("https://example.test/api/public/announcements?platform=ios"),env,"ux-ios");
  expect(response.status).toBe(200);
  const body=await response.json<{platform:string;announcements:Array<{type:string}>}>();
  expect(body.platform).toBe("ios");
  expect(body.announcements.every(item=>item.type!=="release")).toBe(true);
});
