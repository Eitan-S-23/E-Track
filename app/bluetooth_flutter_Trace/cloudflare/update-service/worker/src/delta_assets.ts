import type { FirmwareAssetRow, PatchRow, SecurityPayload, WorkerEnv } from "./types";
import type { DeltaJob } from "./delta_jobs";

interface Result {
  assetId: string; fileName: string; sha256: string; sizeBytes: number; key: string; etag: string;
  securityPayload: SecurityPayload; payloadSignature: Record<string, unknown>;
}
function firmwareAsset(job: DeltaJob): FirmwareAssetRow {
  const r = JSON.parse(job.result_json!) as Result;
  return { id: r.assetId, release_id: job.target_release_id, kind: "patch", file_name: r.fileName,
    sha256: r.sha256, size_bytes: r.sizeBytes, r2_key: r.key, r2_etag: r.etag, r2_state: "available",
    base_image_sha256: job.base_sha256, base_vcode: job.base_version_code,
    github_url: `https://github.com/Eitan-S-23/E-Track/actions/runs/${job.run_id}` };
}
export async function supplementalFirmwareAssets(db: D1Database, releaseId: string): Promise<FirmwareAssetRow[]> {
  const jobs = await db.prepare("SELECT * FROM delta_jobs WHERE kind='firmware' AND target_release_id=? AND status='ready' AND enabled=1")
    .bind(releaseId).all<DeltaJob>();
  return jobs.results.map(firmwareAsset);
}
export async function supplementalFirmwareAsset(db: D1Database, assetId: string, releaseId: string): Promise<FirmwareAssetRow | null> {
  if (!/^asset_delta_[0-9a-f]{64}$/.test(assetId)) return null;
  const job = await db.prepare("SELECT * FROM delta_jobs WHERE id=? AND kind='firmware' AND target_release_id=? AND status='ready' AND enabled=1")
    .bind(assetId.slice(6), releaseId).first<DeltaJob>();
  return job ? firmwareAsset(job) : null;
}

export async function supplementalAppManifest(env: Pick<WorkerEnv, "DB">, releaseId: string, versionCode: number, sourceSha?: string | null) {
  const jobs = await env.DB.prepare(`SELECT j.* FROM delta_jobs j JOIN release_assets a ON a.id='asset_'||j.id
    WHERE j.kind='android' AND j.target_release_id=? AND j.base_version_code=? AND j.status='ready' AND j.enabled=1
      AND a.disabled=0 AND a.r2_state='available'`)
    .bind(releaseId,versionCode).all<DeltaJob>();
  const matches = sourceSha ? jobs.results.filter(j=>j.base_sha256===sourceSha) : jobs.results;
  // Older clients without a source hash retain the original manifest on ambiguity.
  if (matches.length!==1) return null;
  const job=matches[0], result=JSON.parse(job.result_json!) as Result;
  const patch: PatchRow={id:job.id,app_id:"trace",platform:"android",to_release_id:releaseId,asset_id:result.assetId,
    from_version_code:job.base_version_code,old_sha256:job.base_sha256,patch_format:"vcdiff",patch_sha256:result.sha256,
    patch_size_bytes:result.sizeBytes,output_sha256:job.target_sha256,output_size_bytes:result.securityPayload.apkSize,disabled:0,file_name:result.fileName};
  return { cacheKey:`${job.id}:${job.revision}`, securityPayload:result.securityPayload,payloadSignature:result.payloadSignature,patch };
}
