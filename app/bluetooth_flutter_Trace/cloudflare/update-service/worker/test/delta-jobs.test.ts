import { env } from "cloudflare:workers";
import { createExecutionContext } from "cloudflare:test";
import { createHash, generateKeyPairSync, sign } from "node:crypto";
import { beforeEach, describe, expect, it, vi } from "vitest";
import worker from "../src/index";
import { canonicalJson, sha256Hex } from "../src/crypto";
import { createDeltaJobs, deltaCandidates, deltaJobAction, jobView, workflowLocation } from "../src/delta_jobs";
import type { DeltaJob, DeltaKind, DeltaSpec } from "../src/delta_jobs";
import { supplementalAppManifest, supplementalFirmwareAssets } from "../src/delta_assets";
import type { SecurityPayload, WorkerEnv } from "../src/types";
import { registered } from "./firmware-fixture";

let sequence = 1000;
let configured: WorkerEnv;
const keys = generateKeyPairSync("ed25519");
const publicKey = keys.publicKey.export({format:"der",type:"spki"}).subarray(-32).toString("base64");
const dispatch = vi.fn<typeof fetch>(async () => new Response(null,{status:204}));
const patchBytes = new TextEncoder().encode("verified-delta-fixture");
const bytesHash = (bytes: Uint8Array) => createHash("sha256").update(bytes).digest("hex");

beforeEach(async () => {
  await env.DB.batch(["delta_job_events","delta_job_attempts","delta_jobs"].map(t => env.DB.prepare(`DELETE FROM ${t}`)));
  configured = {...env, DELTA_GITHUB_TOKEN:"scoped-dispatch-test", DELTA_WORKFLOW_COMMIT:"c".repeat(40),
    DELTA_WORKFLOW_REF:"dev/admin/delta-test", DELTA_APP_PUBLIC_KEY_BASE64:publicKey, DELTA_ASSETS_ENABLED:"true",
    DELTA_APP_WORKFLOW_REF:"dev/admin/original-delta-test", DELTA_APP_WORKFLOW_COMMIT:"c".repeat(40),
    FIRMWARE_DEPLOY_TOKEN_SHA256:await sha256Hex("firmware-test-token")};
  dispatch.mockReset(); dispatch.mockResolvedValue(new Response(null,{status:204}));
});

async function original(kind: DeltaKind, version?: number) {
  const n=++sequence, bytes=new TextEncoder().encode(`original-${n}`.repeat(20));
  if(kind==="firmware") {
    const r=await registered(false,{targetImageSha256:await sha256Hex(`image-${n}`)},{full:bytes});
    return r.releaseId;
  }
  const code=version ?? n, id=`inventory_app_${n}`, tag=`vdelta-${n}`, sha=bytesHash(bytes);
  const payload:SecurityPayload={appId:"trace",platform:"android",versionName:`2.0.${n}`,versionCode:code,releaseTag:tag,
    apkAssetName:"app.apk",apkSha256:sha,apkSize:bytes.length,patches:[],
    assetHashes:[{assetType:"apk",fileName:"app.apk",sha256:sha,size:bytes.length}],minClientVersionCode:41,
    capabilities:["patch","full","payloadSignature","vcdiff"]};
  await env.DB.prepare("INSERT OR IGNORE INTO apps(id,name) VALUES ('trace','trace')").run();
  await env.DB.prepare(`INSERT INTO releases(id,app_id,platform,version_name,version_code,release_tag,commit_sha,run_id,security_payload_json,capabilities_json)
    VALUES (?,'trace','android',?,?,?,'original',?,?,?)`).bind(id,payload.versionName,code,tag,id,JSON.stringify(payload),JSON.stringify(payload.capabilities)).run();
  await env.DB.prepare("UPDATE releases SET payload_signature_json=? WHERE id=?").bind(JSON.stringify({algorithm:"ed25519",keyVersion:"test",
    signature:sign(null,Buffer.from(canonicalJson(payload)),keys.privateKey).toString("base64")}),id).run();
  await env.RELEASES_BUCKET.put(id,bytes);
  await env.DB.prepare(`INSERT INTO release_assets(id,release_id,app_id,platform,asset_type,file_name,sha256,size_bytes,r2_key,r2_state,github_url)
    VALUES (?,?,'trace','android','apk','app.apk',?,?,?,'available',?)`)
    .bind(`${id}_full`,id,sha,bytes.length,id,`https://github.com/Eitan-S-23/E-Track/releases/download/${tag}/app.apk`).run();
  return id;
}
async function pair(kind:DeltaKind="firmware") {return {kind,base:await original(kind),target:await original(kind)};}
async function create(p:Awaited<ReturnType<typeof pair>>) {
  const response=await createDeltaJobs(configured,"owner",{kind:p.kind,targetReleaseId:p.target,baseReleaseIds:[p.base],reason:"operator test"},dispatch);
  const body=await response.json<{jobs:Array<{id:string}>}>();
  return (await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(body.jobs[0].id).first<DeltaJob>())!;
}
function binding(job:DeltaJob) {return {attempt:job.attempt,workflowCommit:job.workflow_commit,workflowRepository:workflowLocation(job).repository,runId:String(parseInt(job.id.slice(6,18),16))};}
async function ci(job:DeltaJob, action:string, body:unknown=binding(job), token?:string) {
  return worker.fetch(new Request(`https://example.com/api/ci/delta/jobs/${job.id}/${action}`,{
    method:action==="spec"?"GET":"POST",headers:{Accept:"application/json","Content-Type":"application/json",
      Authorization:`Bearer ${token ?? (job.kind==="firmware"?"firmware-test-token":"test-deploy-token")}`},
    body:action==="spec"?undefined:JSON.stringify(body)}),configured,createExecutionContext());
}
async function upload(job:DeltaJob, bytes=patchBytes, sha?:string, length=bytes.length) {
  return worker.fetch(new Request(`https://example.com/api/ci/delta/jobs/${job.id}/asset`,{method:"POST",body:bytes,
    headers:{Authorization:`Bearer ${job.kind==="firmware"?"firmware-test-token":"test-deploy-token"}`,
      "Content-Length":String(length),"X-Delta-Attempt":String(job.attempt),"X-Delta-Run":binding(job).runId,
      "X-Delta-Commit":job.workflow_commit,"X-Delta-Repository":workflowLocation(job).repository,"X-Delta-Sha256":sha ?? bytesHash(bytes)}}),configured,createExecutionContext());
}
async function completion(job:DeltaJob, size=patchBytes.length) {
  const input=JSON.parse(job.input_json) as DeltaSpec, sha=bytesHash(patchBytes);
  const value:Record<string,unknown>={...binding(job),inputSha256:job.input_sha256,baseImageSha256:job.base_sha256,
    targetImageSha256:job.target_sha256,reconstructedSha256:job.target_sha256,byteEqual:true,sha256:sha,sizeBytes:size};
  if(job.kind==="android") {
    const fileName=`delta-${input.base.versionCode}-${input.target.versionCode}-${job.base_sha256.slice(0,12)}.vcdiff`;
    const payload={...input.target.securityPayload!,patches:[{fromVersionCode:input.base.versionCode,toVersionCode:input.target.versionCode,
      assetName:fileName,sha256:sha,size,oldSha256:job.base_sha256,newSha256:job.target_sha256}],
      assetHashes:[...input.target.securityPayload!.assetHashes,{fileName,assetType:"patch",sha256:sha,size}]};
    value.securityPayload=payload;
    value.payloadSignature={algorithm:"ed25519",keyVersion:"test",signature:sign(null,Buffer.from(canonicalJson(payload)),keys.privateKey).toString("base64")};
  }
  return value;
}
async function ready(kind:DeltaKind="firmware") {
  const p=await pair(kind),job=await create(p);
  expect((await ci(job,"claim")).status).toBe(200);
  expect((await upload(job)).status).toBe(200);
  const body=await completion(job);
  const done=await ci(job,"complete",body);
  expect(done.status,await done.clone().text()).toBe(200);
  return {p,job:(await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(job.id).first<DeltaJob>())!,body};
}
async function action(job:DeltaJob,name:string,revision=job.revision) {
  return deltaJobAction(configured,"owner",job.id,name,{expectedRevision:revision,reason:"operator decision"},dispatch);
}

describe("operator-selected supplemental delta jobs",()=>{
  it("dispatches original APK jobs to their signing repository, not the MCU test repository",async()=>{
    const job=await create(await pair("android"));
    expect(job.workflow_ref).toBe("Eitan-S-23/Trace@dev/admin/original-delta-test");
    expect(String(dispatch.mock.calls[0][0])).toContain("/repos/Eitan-S-23/Trace/actions/workflows/");
    expect(JSON.parse(String(dispatch.mock.calls[0][1]?.body)).ref).toBe("dev/admin/original-delta-test");
    expect(jobView({...job,run_id:"123456"}).runUrl).toBe("https://github.com/Eitan-S-23/Trace/actions/runs/123456");
    expect((await ci(job,"spec")).status).toBe(200);
    expect((await ci(job,"claim",{...binding(job),workflowRepository:"Eitan-S-23/E-Track"})).status).toBe(409);
  });
  it("requires explicit original-App workflow bindings without disabling MCU dispatch",async()=>{
    delete configured.DELTA_APP_WORKFLOW_REF;
    const app=await pair("android");
    await expect(create(app)).rejects.toMatchObject({code:"BACKEND_UNAVAILABLE"});
    expect(dispatch).not.toHaveBeenCalled();
    expect((await create(await pair())).status).toBe("queued");
  });
  it("rejects a test signing key that does not verify the original published App",async()=>{
    const p=await pair("android");
    configured.DELTA_APP_PUBLIC_KEY_BASE64=generateKeyPairSync("ed25519").publicKey.export({format:"der",type:"spki"}).subarray(-32).toString("base64");
    const candidates=await (await deltaCandidates(configured,"android",p.target)).json<{appSigningConfigured:boolean}>();
    expect(candidates.appSigningConfigured).toBe(false);
    await expect(create(p)).rejects.toMatchObject({code:"SIGNING_REQUIRED"});
    expect(dispatch).not.toHaveBeenCalled();
  });
  it("retains a legacy App attempt's repository when an explicit retry moves to Trace",async()=>{
    const created=await create(await pair("android"));
    await env.DB.prepare("DELETE FROM delta_job_attempts WHERE job_id=?").bind(created.id).run();
    await env.DB.prepare("DELETE FROM delta_jobs WHERE id=?").bind(created.id).run();
    const legacy={...created,status:"failed",workflow_ref:"dev/admin/old-app-test",run_id:"123456"};
    const fields=Object.keys(legacy);
    await env.DB.prepare(`INSERT INTO delta_jobs(${fields.join(",")}) VALUES (${fields.map(()=>"?").join(",")})`).bind(...Object.values(legacy)).run();
    expect(jobView(legacy).runUrl).toBe("https://github.com/Eitan-S-23/E-Track/actions/runs/123456");
    configured.DELTA_APP_WORKFLOW_COMMIT="d".repeat(40);
    await action(legacy,"retry");
    const attempts=await env.DB.prepare("SELECT attempt,workflow_ref,workflow_commit FROM delta_job_attempts WHERE job_id=? ORDER BY attempt").bind(legacy.id).all();
    expect(attempts.results).toEqual([
      {attempt:1,workflow_ref:"dev/admin/old-app-test",workflow_commit:"c".repeat(40)},
      {attempt:2,workflow_ref:"Eitan-S-23/Trace@dev/admin/original-delta-test",workflow_commit:"d".repeat(40)}]);
  });
  it("never accepts an arbitrary repository or runs firmware in the App repository",()=>{
    expect(()=>workflowLocation({kind:"android",workflow_ref:"attacker/other@main"})).toThrow();
    expect(()=>workflowLocation({kind:"firmware",workflow_ref:"Eitan-S-23/Trace@main"})).toThrow();
  });
  it("accepts MCU originals without requiring an APK signature",async()=>{
    const p=await pair(),job=await create(p);
    expect(job.status).toBe("queued"); expect(dispatch).toHaveBeenCalledTimes(1);
    expect(dispatch.mock.calls[0][1]?.redirect).toBe("manual");
    const sent=JSON.parse(String(dispatch.mock.calls[0][1]?.body));
    expect(sent).toEqual({ref:configured.DELTA_WORKFLOW_REF,inputs:{job_id:job.id,attempt:"1",kind:"firmware"}});
    const candidates=await (await deltaCandidates(configured,p.kind,p.target)).json<{bases:Array<{releaseId:string;eligible:boolean}>}>();
    expect(candidates.bases.find(b=>b.releaseId===p.base)?.eligible).toBe(true);
  });
  it("reuses a duplicate request without another dispatch",async()=>{
    const p=await pair(); expect((await create(p)).id).toBe((await create(p)).id);
    expect(dispatch).toHaveBeenCalledTimes(1);
  });
  it.each([302,307])("does not follow a GitHub dispatch redirect (%i) or forward its token",async(status)=>{
    dispatch.mockImplementationOnce(async(input,init)=>{
      const request=new Request(input,init);
      expect(request.redirect).toBe("manual");
      return new Response(null,{status,headers:{Location:"https://other.example/dispatch"}});
    });
    const job=await create(await pair());
    expect(job.status).toBe("failed");
    expect(job.error_code).toBe(`GITHUB_HTTP_${status}`);
    expect(dispatch).toHaveBeenCalledTimes(1);
  });
  it("does not dispatch anything for an invalid base selection",async()=>{
    const p=await pair();
    await expect(createDeltaJobs(configured,"owner",{kind:p.kind,targetReleaseId:p.target,baseReleaseIds:[p.base,p.target],reason:"test"},dispatch)).rejects.toMatchObject({code:"VERSION_REGRESSION"});
    expect(dispatch).not.toHaveBeenCalled();
  });
  it("rejects old APK decoders and mismatched original manifests",async()=>{
    const base=await original("android",40),target=await original("android");
    await expect(create({kind:"android",base,target})).rejects.toMatchObject({code:"CLIENT_TOO_OLD"});
    await env.DB.prepare("UPDATE releases SET security_payload_json='{}' WHERE id=?").bind(target).run();
    await expect(deltaCandidates(configured,"android",target)).rejects.toMatchObject({code:"RELEASE_INCOMPLETE"});
  });
  it("does not treat an uncertain dispatch as a known failed build",async()=>{
    dispatch.mockRejectedValue(new TypeError("network interrupted"));
    const job=await create(await pair()); expect(job.status).toBe("dispatch_unknown");
    await expect(action(job,"retry")).rejects.toMatchObject({code:"RELEASE_CONFLICT"});
    expect(dispatch).toHaveBeenCalledTimes(1);
    expect((await ci(job,"claim")).status).toBe(200);
  });
  it("reconciles a uniquely bound failed GitHub run without dispatching again",async()=>{
    dispatch.mockRejectedValueOnce(new TypeError("lost dispatch response"));
    const job=await create(await pair());
    const runs=vi.fn<typeof fetch>(async()=>Response.json({workflow_runs:[{id:123456,event:"workflow_dispatch",head_sha:job.workflow_commit,
      display_title:`delta:${job.id}:${job.attempt}`,status:"completed",conclusion:"failure"}]}));
    await deltaJobAction(configured,"owner",job.id,"reconcile",{expectedRevision:job.revision,reason:"Read actual run"},runs);
    expect(runs).toHaveBeenCalledTimes(1);
    expect(runs.mock.calls[0][1]?.method).toBeUndefined();
    expect(runs.mock.calls[0][1]?.redirect).toBe("manual");
    expect(dispatch).toHaveBeenCalledTimes(1);
    const stored=await env.DB.prepare("SELECT status,run_id FROM delta_jobs WHERE id=?").bind(job.id).first();
    expect(stored).toEqual({status:"failed",run_id:"123456"});
  });
  it("does not follow a reconciliation redirect or resolve an unknown dispatch",async()=>{
    dispatch.mockRejectedValueOnce(new TypeError("lost dispatch response"));
    const job=await create(await pair());
    const runs=vi.fn<typeof fetch>(async(input,init)=>{
      expect(new Request(input,init).redirect).toBe("manual");
      return new Response(null,{status:302,headers:{Location:"https://other.example/runs"}});
    });
    await expect(deltaJobAction(configured,"owner",job.id,"reconcile",{expectedRevision:job.revision,reason:"Read actual run"},runs))
      .rejects.toMatchObject({code:"BACKEND_UNAVAILABLE"});
    expect(runs).toHaveBeenCalledTimes(1);
    expect(dispatch).toHaveBeenCalledTimes(1);
    expect((await env.DB.prepare("SELECT status FROM delta_jobs WHERE id=?").bind(job.id).first())?.status).toBe("dispatch_unknown");
  });
  it("does not resolve unknown dispatch using a different workflow commit",async()=>{
    dispatch.mockRejectedValueOnce(new TypeError("lost dispatch response"));
    const job=await create(await pair());
    const runs=vi.fn<typeof fetch>(async()=>Response.json({workflow_runs:[{id:123456,event:"workflow_dispatch",head_sha:"d".repeat(40),
      display_title:`delta:${job.id}:1`,status:"completed",conclusion:"failure"}]}));
    await expect(deltaJobAction(configured,"owner",job.id,"reconcile",{expectedRevision:job.revision,reason:"Read actual run"},runs)).rejects.toMatchObject({code:"RELEASE_CONFLICT"});
    expect((await env.DB.prepare("SELECT status FROM delta_jobs WHERE id=?").bind(job.id).first())?.status).toBe("dispatch_unknown");
  });
  it("records retry workflow identity per attempt and rejects old callbacks",async()=>{
    dispatch.mockResolvedValueOnce(new Response(null,{status:422}));
    const job=await create(await pair()); expect(job.status).toBe("failed");
    configured.DELTA_WORKFLOW_COMMIT="d".repeat(40);
    await action(job,"retry");
    const attempts=await env.DB.prepare("SELECT * FROM delta_job_attempts WHERE job_id=? ORDER BY attempt").bind(job.id).all();
    expect(attempts.results).toMatchObject([{attempt:1,status:"failed",workflow_commit:"c".repeat(40)},
      {attempt:2,status:"queued",workflow_commit:"d".repeat(40)}]);
    expect((await ci(job,"claim")).status).toBe(409);
  });
  it("keeps App and MCU CI tokens separate and requires the bound attempt",async()=>{
    const job=await create(await pair());
    expect((await ci(job,"claim",binding(job),"test-deploy-token")).status).toBe(401);
    expect((await ci(job,"claim",{...binding(job),workflowCommit:"f".repeat(40)})).status).toBe(409);
    expect((await ci(job,"claim")).status).toBe(200);
    expect((await ci(job,"claim",{...binding(job),runId:"99999"})).status).toBe(409);
  });
  it("enforces streamed size and SHA rather than trusting upload metadata",async()=>{
    const job=await create(await pair()); await ci(job,"claim");
    expect((await upload(job,patchBytes,"0".repeat(64))).status).toBe(409);
    expect((await upload(job,patchBytes,undefined,patchBytes.length+1)).status).not.toBe(200);
    expect((await upload(job)).status).toBe(200);
    expect((await upload(job)).status).toBe(200);
    expect((await upload(job,new TextEncoder().encode("other bytes"))).status).toBe(409);
  });
  it("rejects false reconstruction and changed duplicate completion bodies",async()=>{
    const job=await create(await pair()); await ci(job,"claim"); await upload(job);
    const body=await completion(job);
    expect((await ci(job,"complete",{...body,byteEqual:false})).status).toBe(409);
    expect((await ci(job,"complete",body)).status).toBe(200);
    expect((await ci(job,"complete",body)).status).toBe(200);
    expect((await ci(job,"complete",{...body,reconstructedSha256:"0".repeat(64)})).status).toBe(409);
  });
  it("appends a disabled MCU patch, then enables/withdraws without changing channels or sealed originals",async()=>{
    const {p,job}=await ready();
    const snapshot=async()=>(await env.DB.prepare("SELECT * FROM firmware_release_assets WHERE release_id=?").bind(p.target).all()).results;
    const before=await snapshot(), channels=(await env.DB.prepare("SELECT * FROM firmware_channels").all()).results;
    expect(await supplementalFirmwareAssets(env.DB,p.target)).toHaveLength(0);
    await action(job,"enable");
    expect(await supplementalFirmwareAssets(env.DB,p.target)).toHaveLength(1);
    await expect(action(job,"disable")).rejects.toMatchObject({code:"CAS_CONFLICT"});
    expect(await supplementalFirmwareAssets(env.DB,p.target)).toHaveLength(1);
    await action(job,"disable",job.revision+1);
    expect(await supplementalFirmwareAssets(env.DB,p.target)).toHaveLength(0);
    expect(await snapshot()).toEqual(before);
    expect((await env.DB.prepare("SELECT * FROM firmware_channels").all()).results).toEqual(channels);
  });
  it("uses a signed per-base App manifest while leaving the original full manifest unchanged",async()=>{
    const {p,job}=await ready("android");
    const original=(await env.DB.prepare("SELECT security_payload_json FROM releases WHERE id=?").bind(p.target).first())!;
    expect(await supplementalAppManifest(env,p.target,job.base_version_code)).toBeNull();
    await action(job,"enable");
    const manifest=await supplementalAppManifest(env,p.target,job.base_version_code);
    expect(manifest?.patch.old_sha256).toBe(job.base_sha256);
    expect(manifest?.securityPayload.apkSha256).toBe(job.target_sha256);
    expect(await supplementalAppManifest(env,p.target,job.base_version_code,"0".repeat(64))).toBeNull();
    expect(await env.DB.prepare("SELECT security_payload_json FROM releases WHERE id=?").bind(p.target).first()).toEqual(original);
    await action(job,"disable",job.revision+1);
    expect(await supplementalAppManifest(env,p.target,job.base_version_code)).toBeNull();
    expect(await env.DB.prepare("SELECT disabled FROM release_assets WHERE id=?").bind(`asset_${job.id}`).first()).toEqual({disabled:1});
  });
  it("a losing concurrent owner CAS cannot alter assets or log a successful mutation",async()=>{
    const {job}=await ready("android");
    const attempts=await Promise.allSettled([action(job,"enable"),action(job,"disable")]);
    expect(attempts.filter(result=>result.status==="fulfilled")).toHaveLength(1);
    const stored=await env.DB.prepare("SELECT enabled FROM delta_jobs WHERE id=?").bind(job.id).first<{enabled:number}>();
    const asset=await env.DB.prepare("SELECT disabled FROM release_assets WHERE id=?").bind(`asset_${job.id}`).first<{disabled:number}>();
    expect(asset!.disabled).toBe(1-stored!.enabled);
    const events=await env.DB.prepare("SELECT action FROM delta_job_events WHERE job_id=? AND action IN ('enable','disable')").bind(job.id).all();
    expect(events.results).toHaveLength(1);
  });
  it("rejects an APK payload signed by another key",async()=>{
    const job=await create(await pair("android")); await ci(job,"claim"); await upload(job);
    const body=await completion(job);
    body.payloadSignature={algorithm:"ed25519",keyVersion:"test",signature:Buffer.alloc(64).toString("base64")};
    expect((await ci(job,"complete",body)).status).toBe(409);
  });
  it("does not enable an unprofitable or missing artifact",async()=>{
    const {job}=await ready(); const result=JSON.parse(job.result_json!);
    await env.RELEASES_BUCKET.delete(result.key);
    await expect(action(job,"enable")).rejects.toMatchObject({code:"R2_VERIFY_FAILED"});
  });
  it("leaves a changed or archived target out of distribution",async()=>{
    const {job,p}=await ready("android");
    await env.DB.prepare("UPDATE releases SET archived=1 WHERE id=?").bind(p.target).run();
    await expect(action(job,"enable")).rejects.toMatchObject({code:"RELEASE_NOT_READY"});
  });
});
