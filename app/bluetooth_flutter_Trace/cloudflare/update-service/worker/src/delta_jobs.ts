import { canonicalJson, verifyBearerToken } from "./crypto";
import { ApiError, invalidParameter } from "./errors";
import { json } from "./http";
import { boundedJson, sha256Text } from "./version_inventory";
import type { AssetRow, FirmwareAssetRow, FirmwareReleaseRow, ReleaseRow, SecurityPayload, WorkerEnv } from "./types";

export type DeltaKind = "android" | "firmware";
export type DeltaEnv = Pick<WorkerEnv, "DB" | "RELEASES_BUCKET" | "APP_ID" | "DELTA_GITHUB_TOKEN" |
  "DELTA_WORKFLOW_REF" | "DELTA_WORKFLOW_COMMIT" | "DELTA_APP_WORKFLOW_REF" | "DELTA_APP_WORKFLOW_COMMIT" |
  "DELTA_APP_PUBLIC_KEY_BASE64" | "DELTA_ASSETS_ENABLED">;
interface FilePin { id: string; key: string; fileName: string; sha256: string; bytes: number }
export interface DeltaInput {
  releaseId: string; versionCode: number; versionName: string; imageSha256: string; file: FilePin;
  hardwareRevision?: number; layoutId?: number; securityPayload?: SecurityPayload;
}
export interface DeltaSpec { schema: "operator-delta-v1"; kind: DeltaKind; target: DeltaInput; base: DeltaInput }
export interface DeltaJob {
  id: string; kind: DeltaKind; target_release_id: string; base_release_id: string;
  target_sha256: string; base_sha256: string; base_version_code: number; target_version_code: number;
  status: string; enabled: number; attempt: number; revision: number; input_json: string;
  input_sha256: string; workflow_commit: string; workflow_ref: string; mutation_id: string;
  run_id: string | null; result_json: string | null;
  actor: string; reason: string; error_code: string | null; created_at: number; updated_at: number;
  progress_phase?: "building" | "uploading" | "verifying";
}
const REPOSITORY = "Eitan-S-23/E-Track";
const APP_REPOSITORY = "Eitan-S-23/Trace";
const WORKFLOW = "admin-delta-build.yml";
const HEX = /^[0-9a-f]{64}$/;
const ID = /^[A-Za-z0-9_-]{1,160}$/;
const nowSeconds = () => Math.floor(Date.now()/1000);

function kindOf(value: unknown): DeltaKind {
  if (value !== "android" && value !== "firmware") throw invalidParameter("Invalid delta kind");
  return value;
}
function idOf(value: unknown): string {
  if (typeof value !== "string" || !ID.test(value)) throw invalidParameter("Invalid release/job ID");
  return value;
}
function reasonOf(value: unknown): string {
  if (typeof value !== "string" || !value.trim() || value.length > 500) throw invalidParameter("A reason of at most 500 characters is required");
  return value.trim();
}
function configuredWorkflow(env: DeltaEnv, kind: DeltaKind) {
  const ref = kind === "android" ? env.DELTA_APP_WORKFLOW_REF : env.DELTA_WORKFLOW_REF;
  const commit = kind === "android" ? env.DELTA_APP_WORKFLOW_COMMIT : env.DELTA_WORKFLOW_COMMIT;
  return { ref: ref ?? "", commit: commit ?? "", storedRef: kind === "android" ? `${APP_REPOSITORY}@${ref ?? ""}` : ref ?? "" };
}
export function deltaDispatchConfigured(env: DeltaEnv, kind: DeltaKind = "firmware"): boolean {
  const workflow = configuredWorkflow(env, kind);
  return !!env.DELTA_GITHUB_TOKEN && /^[0-9a-f]{40}$/.test(workflow.commit)
    && /^(?:main|dev\/[a-zA-Z0-9/_.-]+)$/.test(workflow.ref);
}
export function workflowLocation(job: Pick<DeltaJob, "kind" | "workflow_ref">) {
  // Qualified refs retain each attempt's repository without rewriting legacy rows.
  const app = job.workflow_ref.startsWith(`${APP_REPOSITORY}@`);
  const ref = app ? job.workflow_ref.slice(APP_REPOSITORY.length + 1) : job.workflow_ref;
  if ((app && job.kind !== "android") || !/^(?:main|dev\/[a-zA-Z0-9/_.-]+)$/.test(ref)) {
    throw invalidParameter("Invalid bound delta workflow repository/ref");
  }
  return { repository: app ? APP_REPOSITORY : REPOSITORY, ref };
}
export function jobView(job: DeltaJob) {
  const result = job.result_json ? JSON.parse(job.result_json) as Record<string, unknown> : null;
  return { id: job.id, kind: job.kind, targetReleaseId: job.target_release_id, baseReleaseId: job.base_release_id,
    baseVersionCode: job.base_version_code, targetVersionCode: job.target_version_code, baseImageSha256: job.base_sha256,
    status: job.status, enabled: job.enabled===1, attempt: job.attempt, revision: job.revision, errorCode: job.error_code,
    createdAt: job.created_at, updatedAt: job.updated_at, fileName: result?.fileName ?? null,
    phase: job.status === "running" ? job.progress_phase ?? "building" : job.status,
    sizeBytes: result?.sizeBytes ?? null, sha256: result?.sha256 ?? null,
    runUrl: job.run_id ? `https://github.com/${workflowLocation(job).repository}/actions/runs/${job.run_id}` : null };
}
async function getJob(env: DeltaEnv, id: string): Promise<DeltaJob> {
  const job = await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(idOf(id)).first<DeltaJob>();
  if (!job) throw new ApiError("RELEASE_NOT_FOUND", "Delta job not found", 404);
  return job;
}
async function appSignatureValid(env: DeltaEnv, payload: SecurityPayload, signature: string): Promise<boolean> {
  try {
    const raw=Uint8Array.from(atob(env.DELTA_APP_PUBLIC_KEY_BASE64??""),c=>c.charCodeAt(0));
    const key=await crypto.subtle.importKey("raw",raw,{name:"Ed25519"},false,["verify"]);
    return await crypto.subtle.verify("Ed25519",key,Uint8Array.from(atob(signature),c=>c.charCodeAt(0)),new TextEncoder().encode(canonicalJson(payload)));
  } catch { return false; }
}
async function originalAppSigningConfigured(env: DeltaEnv, target: DeltaInput): Promise<boolean> {
  const row=await env.DB.prepare("SELECT payload_signature_json FROM releases WHERE id=?").bind(target.releaseId)
    .first<{payload_signature_json:string|null}>();
  try {
    const signature=JSON.parse(row?.payload_signature_json??"null") as {algorithm:string;signature:string}|null;
    return !!target.securityPayload && signature?.algorithm==="ed25519"
      && typeof signature.signature==="string" && await appSignatureValid(env,target.securityPayload,signature.signature);
  } catch { return false; }
}
async function loadInput(env: DeltaEnv, kind: DeltaKind, id: string, verifyObject = true): Promise<DeltaInput> {
  let input: DeltaInput;
  if (kind === "firmware") {
    const r = await env.DB.prepare("SELECT * FROM firmware_releases WHERE id=? AND app_id=? AND device_model='e-track-at32f435' AND state='ready' AND archived=0")
      .bind(idOf(id), env.APP_ID).first<FirmwareReleaseRow>();
    if (!r) throw new ApiError("RELEASE_NOT_READY", "Firmware source is not a ready original release", 409);
    const a = await env.DB.prepare("SELECT * FROM firmware_release_assets WHERE release_id=? AND kind='full' AND r2_state='available'")
      .bind(id).first<FirmwareAssetRow>();
    if (!a?.r2_key) throw new ApiError("RELEASE_INCOMPLETE", "Original full firmware file is unavailable", 409);
    input = { releaseId: id, versionCode: r.version_code, versionName: r.version_name, imageSha256: r.target_image_sha256,
      hardwareRevision: r.hardware_rev, layoutId: r.layout_id,
      file: { id: a.id, key: a.r2_key, fileName: a.file_name, sha256: a.sha256, bytes: a.size_bytes } };
  } else {
    const r = await env.DB.prepare("SELECT * FROM releases WHERE id=? AND app_id=? AND platform='android' AND state='candidate' AND archived=0")
      .bind(idOf(id), env.APP_ID).first<ReleaseRow>();
    if (!r) throw new ApiError("RELEASE_NOT_READY", "APK source is disabled, missing, or archived", 409);
    const a = await env.DB.prepare("SELECT * FROM release_assets WHERE release_id=? AND asset_type='apk' AND disabled=0 AND r2_state='available'")
      .bind(id).first<AssetRow>();
    if (!a?.r2_key) throw new ApiError("RELEASE_INCOMPLETE", "Original APK file is unavailable", 409);
    input = { releaseId: id, versionCode: r.version_code, versionName: r.version_name, imageSha256: a.sha256,
      securityPayload: JSON.parse(r.security_payload_json) as SecurityPayload,
      file: { id: a.id, key: a.r2_key, fileName: a.file_name, sha256: a.sha256, bytes: a.size_bytes } };
    if (input.securityPayload?.apkSha256!==a.sha256 || input.securityPayload?.versionCode!==r.version_code
      || input.securityPayload?.apkSize!==a.size_bytes || input.securityPayload?.appId!==env.APP_ID) {
      throw new ApiError("RELEASE_INCOMPLETE","APK manifest does not match its original file",409);
    }
  }
  if (!HEX.test(input.imageSha256) || !HEX.test(input.file.sha256) || input.file.bytes<=0 || input.file.bytes>256*1024*1024) {
    throw new ApiError("RELEASE_INCOMPLETE", "Invalid original file binding", 409);
  }
  if (verifyObject) {
    const head = await env.RELEASES_BUCKET.head(input.file.key);
    if (!head || head.size !== input.file.bytes) throw new ApiError("R2_VERIFY_FAILED", "Original file is no longer available", 409);
  }
  return input;
}
function validatePair(kind: DeltaKind, target: DeltaInput, base: DeltaInput) {
  if (base.versionCode >= target.versionCode) throw new ApiError("VERSION_REGRESSION", "Delta base must precede target", 409);
  if (kind === "android" && base.versionCode < 41) throw new ApiError("CLIENT_TOO_OLD", "This APK predates safe VCDIFF support", 409);
  if (kind === "firmware" && (base.hardwareRevision !== target.hardwareRevision || base.layoutId !== target.layoutId)) {
    throw new ApiError("HARDWARE_INCOMPATIBLE", "Firmware hardware and layout must match", 409);
  }
  if (kind === "firmware" && (target.hardwareRevision !== 1 || target.layoutId !== 1)) {
    throw new ApiError("HARDWARE_INCOMPATIBLE", "Existing F435 packer supports hardware/layout 1 only", 409);
  }
}
async function existingPatch(env: DeltaEnv, kind: DeltaKind, target: string, base: DeltaInput): Promise<boolean> {
  const query = kind === "firmware"
    ? "SELECT id FROM firmware_release_assets WHERE release_id=? AND kind='patch' AND base_image_sha256=? AND r2_state='available'"
    : "SELECT p.id FROM patches p JOIN release_assets a ON a.id=p.asset_id WHERE p.to_release_id=? AND p.old_sha256=? AND a.r2_state='available'";
  return !!await env.DB.prepare(query).bind(target, base.imageSha256).first();
}

export async function deltaCandidates(env: DeltaEnv, kind: DeltaKind, targetId: string): Promise<Response> {
  const target = await loadInput(env, kind, targetId);
  const sourceRows = await env.DB.prepare(kind === "firmware"
    ? `SELECT r.id,r.version_code,r.version_name,r.target_image_sha256 AS image_sha256,r.hardware_rev,r.layout_id,r.state,r.archived,
       a.r2_key,a.r2_state,a.size_bytes FROM firmware_releases r LEFT JOIN firmware_release_assets a ON a.release_id=r.id AND a.kind='full'
       WHERE r.app_id=? AND r.device_model='e-track-at32f435' AND r.version_code<? ORDER BY r.version_code DESC LIMIT 200`
    : `SELECT r.id,r.version_code,r.version_name,a.sha256 AS image_sha256,NULL AS hardware_rev,NULL AS layout_id,r.state,r.archived,
       a.r2_key,a.r2_state,a.size_bytes FROM releases r LEFT JOIN release_assets a ON a.release_id=r.id AND a.asset_type='apk' AND a.disabled=0
       WHERE r.app_id=? AND r.platform='android' AND r.version_code<? ORDER BY r.version_code DESC LIMIT 200`)
    .bind(env.APP_ID, target.versionCode).all<{id:string;version_code:number;version_name:string;image_sha256:string;
      hardware_rev:number;layout_id:number;state:string;archived:number;r2_key:string|null;r2_state:string;size_bytes:number}>();
  const patches=await env.DB.prepare(kind==="firmware"
    ? "SELECT base_image_sha256 AS sha FROM firmware_release_assets WHERE release_id=? AND kind='patch' AND r2_state='available'"
    : "SELECT p.old_sha256 AS sha FROM patches p JOIN release_assets a ON a.id=p.asset_id WHERE p.to_release_id=? AND a.r2_state='available'")
    .bind(targetId).all<{sha:string}>();
  const patchBases=new Set(patches.results.map(p=>p.sha));
  const jobs = (await env.DB.prepare("SELECT * FROM delta_jobs WHERE kind=? AND target_release_id=? ORDER BY created_at DESC")
    .bind(kind, targetId).all<DeltaJob>()).results;
  const bases = [];
  for (const row of sourceRows.results) {
    try {
      if (row.archived || row.state!==(kind==="firmware"?"ready":"candidate") || !row.r2_key || row.r2_state!=="available" || !HEX.test(row.image_sha256??"")) {
        throw new ApiError("RELEASE_NOT_READY","Original source file is unavailable",409);
      }
      if (kind==="android" && row.version_code<41) throw new ApiError("CLIENT_TOO_OLD","VCDIFF requires source versionCode 41 or later",409);
      if (kind==="firmware" && (row.hardware_rev!==target.hardwareRevision || row.layout_id!==target.layoutId)) throw new ApiError("HARDWARE_INCOMPATIBLE","Hardware or layout mismatch",409);
      if (kind==="firmware" && (row.hardware_rev!==1 || row.layout_id!==1)) throw new ApiError("HARDWARE_INCOMPATIBLE","Existing packer supports hardware/layout 1 only",409);
      const job = jobs.find(j => j.base_sha256 === row.image_sha256);
      bases.push({ releaseId: row.id, versionCode: row.version_code, versionName: row.version_name,
        imageSha256: row.image_sha256, bytes: row.size_bytes, eligible: true,
        existing: patchBases.has(row.image_sha256), job: job ? jobView(job) : null });
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      bases.push({ releaseId: row.id, versionCode: row.version_code, versionName: row.version_name,
        imageSha256: row.image_sha256, eligible: false, reason: error.message });
    }
  }
  return json({ ok: true, kind, target: { releaseId: targetId, versionName: target.versionName,
    versionCode: target.versionCode, imageSha256: target.imageSha256, fullBytes: target.file.bytes }, bases,
    jobs: jobs.map(jobView), dispatchConfigured: deltaDispatchConfigured(env, kind),
    appSigningConfigured: kind === "android" ? await originalAppSigningConfigured(env,target) : false,
    distributionEnabled: env.DELTA_ASSETS_ENABLED === "true",
    maximumBases: 5, truncated: sourceRows.results.length === 200 });
}

async function dispatch(env: DeltaEnv, job: DeltaJob, fetcher: typeof fetch): Promise<void> {
  const workflow = workflowLocation(job);
  // Dispatch once. A transport failure is an unknown outcome, never an automatic retry.
  try {
    const response = await fetcher(`https://api.github.com/repos/${workflow.repository}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST", headers: { Authorization: `Bearer ${env.DELTA_GITHUB_TOKEN}`, Accept: "application/vnd.github+json",
        "Content-Type": "application/json", "User-Agent": "E-Track-Admin-Delta" },
      body: JSON.stringify({ ref: workflow.ref, inputs: { job_id: job.id, attempt: String(job.attempt), kind: job.kind } }),
      // Workers rejects redirect:"error" before sending; manual never forwards the token.
      signal: AbortSignal.timeout(15000), redirect: "manual"
    });
    await response.body?.cancel();
    if (response.status !== 204) {
      const status = response.status >= 500 ? "dispatch_unknown" : "failed";
      await env.DB.prepare("UPDATE delta_jobs SET status=?,error_code=?,revision=revision+1,updated_at=? WHERE id=? AND status='dispatching' AND attempt=?")
        .bind(status, `GITHUB_HTTP_${response.status}`, nowSeconds(), job.id, job.attempt).run();
      return;
    }
    await env.DB.prepare("UPDATE delta_jobs SET status='queued',revision=revision+1,updated_at=? WHERE id=? AND status='dispatching' AND attempt=?")
      .bind(nowSeconds(), job.id, job.attempt).run();
  } catch {
    await env.DB.prepare("UPDATE delta_jobs SET status='dispatch_unknown',error_code='DISPATCH_OUTCOME_UNKNOWN',revision=revision+1,updated_at=? WHERE id=? AND status='dispatching' AND attempt=?")
      .bind(nowSeconds(), job.id, job.attempt).run();
  }
}

export async function createDeltaJobs(env: DeltaEnv, actor: string, body: Record<string, unknown>, fetcher = fetch): Promise<Response> {
  const kind = kindOf(body.kind), targetId = idOf(body.targetReleaseId), reason = reasonOf(body.reason);
  if (!deltaDispatchConfigured(env, kind)) throw new ApiError("BACKEND_UNAVAILABLE", "Project-scoped GitHub delta dispatcher is not configured", 503);
  const workflow = configuredWorkflow(env, kind);
  if (kind === "android" && !env.DELTA_APP_PUBLIC_KEY_BASE64) throw new ApiError("SIGNING_REQUIRED", "APK delta signing key binding is not configured", 503);
  if (!Array.isArray(body.baseReleaseIds) || !body.baseReleaseIds.length || body.baseReleaseIds.length>5) throw invalidParameter("Select one to five base releases");
  const ids = body.baseReleaseIds.map(idOf);
  if (new Set(ids).size !== ids.length) throw invalidParameter("Duplicate delta base");
  const target = await loadInput(env, kind, targetId);
  if (kind === "android" && !await originalAppSigningConfigured(env,target)) {
    throw new ApiError("SIGNING_REQUIRED", "Delta verification key does not match the original App manifest", 503);
  }
  const plans = [];
  for (const id of ids) {
    const base = await loadInput(env, kind, id);
    validatePair(kind, target, base);
    plans.push({ base, exists: await existingPatch(env, kind, targetId, base) });
  }
  const result = [];
  for (const { base, exists } of plans) {
    if (exists) { result.push({ baseReleaseId: base.releaseId, status: "existing" }); continue; }
    const id = `delta_${await sha256Text(`${kind}:${targetId}:${base.imageSha256}`)}`;
    const old = await env.DB.prepare("SELECT * FROM delta_jobs WHERE id=?").bind(id).first<DeltaJob>();
    if (old) { result.push(jobView(old)); continue; }
    const spec: DeltaSpec = { schema: "operator-delta-v1", kind, target, base };
    const text = canonicalJson(spec), hash = await sha256Text(text), now = nowSeconds();
    try {
      const inserted = await env.DB.prepare(`INSERT OR IGNORE INTO delta_jobs
        (id,kind,target_release_id,base_release_id,target_sha256,base_sha256,base_version_code,target_version_code,
         status,input_json,input_sha256,workflow_commit,workflow_ref,actor,reason,created_at,updated_at)
         VALUES (?,?,?,?,?,?,?,?,'dispatching',?,?,?,?,?,?,?,?)`)
        .bind(id,kind,targetId,base.releaseId,target.imageSha256,base.imageSha256,base.versionCode,target.versionCode,
          text,hash,workflow.commit,workflow.storedRef,actor,reason,now,now).run();
      if (inserted.meta.changes) await dispatch(env, await getJob(env,id), fetcher);
    } catch (error) {
      if (String(error).includes("daily budget")) throw new ApiError("RATE_LIMITED", "Daily delta job limit reached", 429);
      throw error;
    }
    result.push(jobView(await getJob(env,id)));
  }
  return json({ ok: true, jobs: result });
}

export async function deltaJobAction(env: DeltaEnv, actor: string, id: string, action: string, body: Record<string, unknown>, fetcher = fetch): Promise<Response> {
  const job = await getJob(env,id);
  const reason = reasonOf(body.reason);
  if (body.expectedRevision !== job.revision) throw new ApiError("CAS_CONFLICT", "Delta job changed; reload", 409);
  const spec = JSON.parse(job.input_json) as DeltaSpec;
  if (action === "reconcile") {
    if (["ready","failed"].includes(job.status)) return json({ok:true,job:jobView(job)});
    if (!env.DELTA_GITHUB_TOKEN) throw new ApiError("BACKEND_UNAVAILABLE","Project GitHub read access is not configured",503);
    const workflow=workflowLocation(job);
    const response=await fetcher(`https://api.github.com/repos/${workflow.repository}/actions/workflows/${WORKFLOW}/runs?event=workflow_dispatch&branch=${encodeURIComponent(workflow.ref)}&per_page=100`,{
      headers:{Authorization:`Bearer ${env.DELTA_GITHUB_TOKEN}`,Accept:"application/vnd.github+json","User-Agent":"E-Track-Admin-Delta"},
      redirect:"manual",signal:AbortSignal.timeout(15000)});
    if (!response.ok) {await response.body?.cancel();throw new ApiError("BACKEND_UNAVAILABLE","GitHub run reconciliation failed",503);}
    const data=await boundedJson({headers:new Headers({"Content-Type":"application/json"}),body:response.body},2*1024*1024);
    const runs=Array.isArray(data.workflow_runs)?data.workflow_runs as Array<Record<string,unknown>>:[];
    const matches=runs.filter(run=>run.event==="workflow_dispatch" && run.head_sha===job.workflow_commit
      && run.display_title===`delta:${job.id}:${job.attempt}` && /^[1-9][0-9]{0,19}$/.test(String(run.id)));
    if (matches.length!==1 || (job.run_id && job.run_id!==String(matches[0].id))) {
      throw new ApiError("RELEASE_CONFLICT","No unique bound GitHub run found; nothing was redispatched",409);
    }
    const run=matches[0], mutation=crypto.randomUUID();
    const status=run.status==="completed"?"failed":job.status;
    const code=run.status==="completed"?(run.conclusion==="success"?"CI_RESULT_MISSING":"CI_BUILD_FAILED"):job.error_code;
    const changed=await env.DB.batch([
      env.DB.prepare("UPDATE delta_jobs SET status=?,run_id=?,error_code=?,mutation_id=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?")
        .bind(status,String(run.id),code,mutation,nowSeconds(),id,job.revision),
      eventStatement(env,id,mutation,"reconcile",actor,reason,job.revision+1)
    ]);
    if (!changed[0].meta.changes) throw new ApiError("CAS_CONFLICT","Delta reconciliation changed",409);
  } else if (action === "retry") {
    if (job.status !== "failed") throw new ApiError("RELEASE_CONFLICT", "Only known failed jobs may retry; reconcile unknown dispatches first", 409);
    if (!deltaDispatchConfigured(env,job.kind)) throw new ApiError("RELEASE_CONFLICT", "Workflow binding is unavailable", 409);
    const workflow=configuredWorkflow(env,job.kind);
    const currentTarget = await loadInput(env,job.kind,job.target_release_id);
    const currentBase = await loadInput(env,job.kind,job.base_release_id);
    if (canonicalJson(currentTarget)!==canonicalJson(spec.target) || canonicalJson(currentBase)!==canonicalJson(spec.base)) throw new ApiError("RELEASE_CONFLICT", "Original source binding changed",409);
    if (job.kind==="android" && !await originalAppSigningConfigured(env,currentTarget)) {
      throw new ApiError("SIGNING_REQUIRED","Delta verification key does not match the original App manifest",503);
    }
    const mutation = crypto.randomUUID();
    let changed: D1Result[];
    try { changed = await env.DB.batch([
      env.DB.prepare("UPDATE delta_jobs SET status='dispatching',attempt=attempt+1,workflow_commit=?,workflow_ref=?,mutation_id=?,run_id=NULL,error_code=NULL,result_json=NULL,revision=revision+1,updated_at=? WHERE id=? AND revision=? AND status='failed'")
        .bind(workflow.commit,workflow.storedRef,mutation,nowSeconds(),id,job.revision),
      eventStatement(env, id, mutation, "retry", actor, reason, job.revision+1)
    ]); } catch (error) {
      if (String(error).includes("daily budget")) throw new ApiError("RATE_LIMITED","Daily delta attempt limit reached",429);
      throw error;
    }
    if (!changed[0].meta.changes) throw new ApiError("CAS_CONFLICT","Delta job changed",409);
    await dispatch(env,await getJob(env,id),fetcher);
  } else if (action === "enable" || action === "disable") {
    if (job.status !== "ready" || !job.result_json) throw new ApiError("RELEASE_NOT_READY","Delta is not verified",409);
    const result = JSON.parse(job.result_json) as { sizeBytes: number; key: string; sha256: string; assetId: string };
    if (action === "enable") {
      if (env.DELTA_ASSETS_ENABLED!=="true") throw new ApiError("BACKEND_UNAVAILABLE","Supplemental distribution is not enabled",503);
      const current = await loadInput(env,job.kind,job.target_release_id);
      if (canonicalJson(current)!==canonicalJson(spec.target) || result.sizeBytes >= spec.target.file.bytes) throw new ApiError("RELEASE_NOT_READY","Target changed or delta is not smaller than the full package",409);
      const object = await env.RELEASES_BUCKET.head(result.key);
      if (!object || object.size!==result.sizeBytes || object.customMetadata?.sha256!==result.sha256) throw new ApiError("R2_VERIFY_FAILED","Delta object binding is unavailable",409);
    }
    const mutation = crypto.randomUUID();
    const statements = [env.DB.prepare("UPDATE delta_jobs SET enabled=?,mutation_id=?,revision=revision+1,updated_at=? WHERE id=? AND revision=? AND status='ready'")
      .bind(action==="enable"?1:0,mutation,nowSeconds(),id,job.revision)];
    if (job.kind==="android") statements.push(env.DB.prepare("UPDATE release_assets SET disabled=? WHERE id=? AND EXISTS(SELECT 1 FROM delta_jobs WHERE id=? AND mutation_id=?)")
      .bind(action==="enable"?0:1,result.assetId,id,mutation));
    statements.push(eventStatement(env,id,mutation,action,actor,reason,job.revision+1));
    const changed=await env.DB.batch(statements);
    if (!changed[0].meta.changes) throw new ApiError("CAS_CONFLICT","Delta job changed",409);
  } else throw invalidParameter("Unsupported delta action");
  return json({ok:true,job:jobView(await getJob(env,id))});
}

function eventStatement(env: DeltaEnv, id: string, mutation: string, action: string, actor: string, reason: string, revision: number) {
  // The nonce prevents a losing CAS request from applying another request's side effects.
  return env.DB.prepare("INSERT INTO delta_job_events(id,job_id,action,actor,reason,revision,created_at) SELECT ?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM delta_jobs WHERE id=? AND mutation_id=?)")
    .bind(crypto.randomUUID(),id,action,actor,reason,revision,nowSeconds(),id,mutation);
}

async function ciJob(request: Request, env: WorkerEnv, id: string): Promise<DeltaJob> {
  const job = await getJob(env,id);
  const expected = job.kind==="firmware" ? env.FIRMWARE_DEPLOY_TOKEN_SHA256 : env.DEPLOY_TOKEN_SHA256;
  if (!await verifyBearerToken(request.headers.get("Authorization")?.match(/^Bearer (.+)$/)?.[1] ?? null, expected)) {
    throw new ApiError("TOKEN_INVALID","Delta CI credential rejected",401);
  }
  return job;
}
function checkAttempt(job: DeltaJob, body: Record<string,unknown>) {
  if ((body.workflowRepository??REPOSITORY)!==workflowLocation(job).repository || body.attempt!==job.attempt
    || body.workflowCommit!==job.workflow_commit || !/^[1-9][0-9]{0,19}$/.test(String(body.runId))) {
    throw new ApiError("RELEASE_CONFLICT","Delta attempt or workflow binding changed",409);
  }
  if (job.run_id && job.run_id!==String(body.runId)) throw new ApiError("RELEASE_CONFLICT","Delta run changed",409);
}
function outputKey(job: DeltaJob) { return `trace/delta/v1/${job.kind}/${job.id}/${job.attempt}/patch`; }

export async function deltaCi(request: Request, env: WorkerEnv): Promise<Response> {
  const match = new URL(request.url).pathname.match(/^\/api\/ci\/delta\/jobs\/(delta_[0-9a-f]{64})\/(spec|base|target|claim|asset|complete|fail)$/);
  if (!match) throw invalidParameter("Unknown delta CI route");
  const job=await ciJob(request,env,match[1]), action=match[2], spec=JSON.parse(job.input_json) as DeltaSpec;
  if (request.method==="GET" && action==="spec") return json({ok:true,jobId:job.id,attempt:job.attempt,status:job.status,
    workflowCommit:job.workflow_commit,workflowRepository:workflowLocation(job).repository,inputSha256:job.input_sha256,input:spec});
  if (request.method==="GET" && (action==="base" || action==="target")) {
    checkAttempt(job,{attempt:Number(request.headers.get("X-Delta-Attempt")),runId:request.headers.get("X-Delta-Run"),workflowCommit:request.headers.get("X-Delta-Commit"),workflowRepository:request.headers.get("X-Delta-Repository")});
    if (job.status!=="running") throw new ApiError("RELEASE_CONFLICT","Claim the job before reading inputs",409);
    const file=spec[action].file, object=await env.RELEASES_BUCKET.get(file.key);
    if (!object || object.size!==file.bytes) throw new ApiError("R2_VERIFY_FAILED","Original input unavailable",409);
    return new Response(object.body,{headers:{"Content-Type":"application/octet-stream","Content-Length":String(file.bytes),"Cache-Control":"no-store"}});
  }
  if (request.method!=="POST") throw invalidParameter("Delta CI requires POST");
  if (action==="asset") {
    const header={attempt:Number(request.headers.get("X-Delta-Attempt")),runId:request.headers.get("X-Delta-Run"),workflowCommit:request.headers.get("X-Delta-Commit"),workflowRepository:request.headers.get("X-Delta-Repository")};
    checkAttempt(job,header);
    if (job.status!=="running") throw new ApiError("RELEASE_CONFLICT","Delta job is not running",409);
    const length=Number(request.headers.get("Content-Length")), sha=request.headers.get("X-Delta-Sha256")??"";
    if (!Number.isSafeInteger(length) || length<=0 || length>256*1024*1024 || !HEX.test(sha) || !request.body) throw invalidParameter("Invalid delta upload");
    const key=outputKey(job), previous=await env.RELEASES_BUCKET.head(key);
    if (previous) {
      if (previous.size!==length || previous.customMetadata?.sha256!==sha) throw new ApiError("R2_OBJECT_CONFLICT","Existing delta bytes differ",409);
      await request.body.cancel();
      return json({ok:true,sha256:sha,sizeBytes:length,idempotent:true});
    }
    await env.DB.prepare("UPDATE delta_jobs SET progress_phase='uploading',updated_at=? WHERE id=? AND status='running' AND attempt=? AND progress_phase='building'")
      .bind(nowSeconds(),job.id,job.attempt).run();
    const stream=new FixedLengthStream(length), abort=new AbortController();
    const upload=request.body.pipeTo(stream.writable,{signal:abort.signal});
    const writing=env.RELEASES_BUCKET.put(key,stream.readable,{onlyIf:{etagDoesNotMatch:"*"},sha256:sha,
      customMetadata:{sha256:sha},httpMetadata:{contentType:"application/octet-stream"}})
      .then(object=>{if(!object) abort.abort();return object;},error=>{abort.abort();throw error;});
    const [piped,written]=await Promise.allSettled([upload,writing]);
    if (written.status==="rejected") throw new ApiError("R2_VERIFY_FAILED","Delta upload checksum or storage validation failed",409);
    const object=written.value;
    if (piped.status==="rejected" && object) throw invalidParameter("Delta length mismatch");
    if (!object || object.size!==length) throw new ApiError("R2_OBJECT_CONFLICT","Delta upload did not complete",409);
    await env.DB.prepare("UPDATE delta_jobs SET progress_phase='verifying',updated_at=? WHERE id=? AND status='running' AND attempt=?")
      .bind(nowSeconds(),job.id,job.attempt).run();
    return json({ok:true,sha256:sha,sizeBytes:length,idempotent:false});
  }
  const body=await boundedJson(request,65536);
  checkAttempt(job,body);
  if (action==="claim") {
    if (job.status==="running") return json({ok:true,job:jobView(job),idempotent:true});
    if (!["dispatching","queued","dispatch_unknown"].includes(job.status)) throw new ApiError("RELEASE_CONFLICT","Delta job cannot be claimed",409);
    const result=await env.DB.prepare("UPDATE delta_jobs SET status='running',progress_phase='building',run_id=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?")
      .bind(String(body.runId),nowSeconds(),job.id,job.revision).run();
    if (!result.meta.changes) throw new ApiError("CAS_CONFLICT","Delta claim changed",409);
    return json({ok:true});
  }
  if (action==="fail") {
    if (job.status==="ready") return json({ok:true,alreadyReady:true});
    if (job.status!=="running") throw new ApiError("RELEASE_CONFLICT","Unclaimed delta failure",409);
    const code=body.errorCode==="DELTA_NOT_SMALLER"?"DELTA_NOT_SMALLER":"CI_BUILD_FAILED";
    const changed=await env.DB.prepare("UPDATE delta_jobs SET status='failed',error_code=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?")
      .bind(code,nowSeconds(),job.id,job.revision).run();
    if (!changed.meta.changes) throw new ApiError("CAS_CONFLICT","Delta failure state changed",409);
    return json({ok:true});
  }
  if (action!=="complete") throw invalidParameter("Invalid delta action");
  const completionHash=await sha256Text(canonicalJson(body));
  if (job.status==="ready") {
    const prior=JSON.parse(job.result_json!) as {completionHash:string};
    if (prior.completionHash!==completionHash) throw new ApiError("IDEMPOTENCY_CONFLICT","Delta completion bytes changed",409);
    return json({ok:true,job:jobView(job),idempotent:true});
  }
  if (job.status!=="running" || body.inputSha256!==job.input_sha256 || body.baseImageSha256!==job.base_sha256
    || body.targetImageSha256!==job.target_sha256 || body.reconstructedSha256!==job.target_sha256 || body.byteEqual!==true) {
    throw new ApiError("RELEASE_CONFLICT","Delta reconstruction proof does not match the job",409);
  }
  const sha=String(body.sha256), size=body.sizeBytes;
  if (!HEX.test(sha) || typeof size!=="number" || !Number.isSafeInteger(size) || size<=0) throw invalidParameter("Invalid delta result identity");
  const object=await env.RELEASES_BUCKET.head(outputKey(job));
  if (!object || object.size!==size || object.customMetadata?.sha256!==sha) throw new ApiError("R2_VERIFY_FAILED","Uploaded delta does not match completion proof",409);
  const currentTarget=await loadInput(env,job.kind,job.target_release_id);
  const currentBase=await loadInput(env,job.kind,job.base_release_id);
  if (canonicalJson(currentTarget)!==canonicalJson(spec.target) || canonicalJson(currentBase)!==canonicalJson(spec.base)) {
    throw new ApiError("RELEASE_CONFLICT","Original source binding changed",409);
  }
  const fileName=`delta-${spec.base.versionCode}-${spec.target.versionCode}-${job.base_sha256.slice(0,12)}.${job.kind==="android"?"vcdiff":"etu"}`;
  const assetId=`asset_${job.id}`;
  const result: Record<string,unknown>={sha256:sha,sizeBytes:size,key:outputKey(job),etag:object.etag,fileName,assetId,
    inputSha256:job.input_sha256,reconstructedSha256:job.target_sha256,byteEqual:true,completionHash};
  if (job.kind==="android") {
    const payload=body.securityPayload as SecurityPayload | undefined;
    const signature=body.payloadSignature as {algorithm?:string;keyVersion?:string;signature?:string}|undefined;
    const original=spec.target.securityPayload!;
    const expectedPatch={fromVersionCode:spec.base.versionCode,toVersionCode:spec.target.versionCode,assetName:fileName,
      sha256:sha,size,oldSha256:job.base_sha256,newSha256:job.target_sha256};
    const expected={...original,patches:[expectedPatch],assetHashes:[...original.assetHashes.filter(a=>a.assetType!=="patch"),
      {fileName,assetType:"patch",sha256:sha,size}]};
    if (!payload || canonicalJson(payload)!==canonicalJson(expected) || signature?.algorithm!=="ed25519"
      || typeof signature.signature!=="string" || typeof signature.keyVersion!=="string" || !/^[\w.-]{1,64}$/.test(signature.keyVersion)) {
      throw new ApiError("SIGNING_REQUIRED","Signed per-base APK manifest does not match original target",409);
    }
    if (!await appSignatureValid(env,payload,signature.signature) || !await originalAppSigningConfigured(env,currentTarget)) {
      throw new ApiError("SIGNING_REQUIRED","APK delta manifest signature rejected",409);
    }
    result.securityPayload=payload;result.payloadSignature=signature;
  }
  const mutation=crypto.randomUUID();
  const statements=[env.DB.prepare("UPDATE delta_jobs SET status='ready',enabled=0,result_json=?,mutation_id=?,revision=revision+1,updated_at=? WHERE id=? AND revision=? AND status='running'")
    .bind(JSON.stringify(result),mutation,nowSeconds(),job.id,job.revision)];
  if (job.kind==="android") statements.push(env.DB.prepare(`INSERT INTO release_assets
    (id,release_id,app_id,platform,asset_type,file_name,sha256,size_bytes,r2_key,r2_state,github_url,disabled)
    SELECT ?,?,?,'android','patch',?,?,?,?,'available',?,1 WHERE EXISTS(SELECT 1 FROM delta_jobs WHERE id=? AND mutation_id=? AND status='ready')`)
    .bind(assetId,job.target_release_id,env.APP_ID,fileName,sha,size,outputKey(job),`https://github.com/${workflowLocation(job).repository}/actions/runs/${job.run_id}`,job.id,mutation));
  statements.push(eventStatement(env,job.id,mutation,"complete","github-actions",`Verified run ${job.run_id}`,job.revision+1));
  const changed=await env.DB.batch(statements);
  if (!changed[0].meta.changes) throw new ApiError("CAS_CONFLICT","Delta completion changed",409);
  return json({ok:true,job:jobView(await getJob(env,job.id)),channelPublished:false});
}
