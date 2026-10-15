import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { verifyWorkerEnvironment } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs";
import { verifyStoredFirmwareAsset, withFirmwareBucket } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";

const fixturePath = "docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15/operations/verified-metadata.json";
const target = Object.freeze({
  repository: "Eitan-S-23/E-Track", workerName: "e-track-firmware-p41-test",
  serviceUrl: "https://e-track-firmware-p41-test.tangjichentudou.workers.dev",
  bucketName: "e-track-firmware-p41-test-releases", databaseName: "e-track-firmware-p41-test",
  databaseId: "2617e1e1-956f-42ce-a465-da56d84abf06"
});

export function bindingsCheckConfig(env) {
  if (env.GITHUB_EVENT_NAME !== "workflow_dispatch" || env.INPUT_CHECK_BINDINGS !== "true"
    || env.INPUT_PUBLISH !== "false" || env.INPUT_REHEARSAL !== "false" || env.OTA_BOOT_CHAIN_READY !== "false") {
    throw new CliError("Bindings qualification requires an explicit check-only dispatch and a literally locked gate");
  }
  if (env.GITHUB_REPOSITORY !== target.repository || !/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "")
    || env.GITHUB_SHA !== env.FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT
    || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "") || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ATTEMPT ?? "")) {
    throw new CliError("Bindings qualification requires the exact protected reviewed commit and run identity");
  }
  if (env.TRACE_UPDATE_SERVICE_URL !== target.serviceUrl || env.TRACE_R2_BUCKET !== target.bucketName
    || env.TRACE_D1_DATABASE_ID !== target.databaseId || env.TRACE_D1_DATABASE_NAME !== target.databaseName
    || !/^[0-9a-f]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID ?? "")
    || !env.CLOUDFLARE_API_TOKEN || /\s/.test(env.CLOUDFLARE_API_TOKEN)) {
    throw new CliError("Bindings qualification requires the explicit isolated Worker, R2, D1 and credential configuration");
  }
  return { ...target, accountId: env.CLOUDFLARE_ACCOUNT_ID };
}

async function workerBindings(config, token, fetcher) {
  const url = `https://api.cloudflare.com/client/v4/accounts/${config.accountId}/workers/scripts/${config.workerName}/settings`;
  const response = await fetcher(url, { method: "GET", redirect: "error", signal: AbortSignal.timeout(20000),
    headers: { Authorization: `Bearer ${token}`, Accept: "application/json" } });
  if (!response.ok) throw new CliError("Cannot verify the isolated Worker bindings", "BACKEND_UNAVAILABLE", 1);
  const body = await response.json();
  const bindings = body.result?.bindings;
  if (body.success !== true || !Array.isArray(bindings)) {
    throw new CliError("Worker bindings are unavailable", "BACKEND_UNAVAILABLE", 1);
  }
  for (const [name, type, field, expected] of [["RELEASES_BUCKET", "r2_bucket", "bucket_name", config.bucketName],
    ["DB", "d1", "id", config.databaseId], ["ENVIRONMENT", "plain_text", "text", "staging"]]) {
    const matches = bindings.filter(b => b?.name === name);
    if (matches.length !== 1 || matches[0].type !== type || matches[0][field] !== expected) {
      throw new CliError("Worker bindings do not match the isolated qualification targets", "RELEASE_CONFLICT", 1);
    }
  }
}

async function databaseSnapshot(db) {
  if (!db) throw new CliError("Explicit D1 binding is unavailable", "BACKEND_UNAVAILABLE", 1);
  const counts = {};
  for (const table of ["firmware_releases", "firmware_releases_legacy", "firmware_release_assets", "firmware_channels", "audit_logs"]) {
    const row = await db.prepare(`SELECT COUNT(*) AS count FROM ${table}`).first();
    if (!Number.isSafeInteger(row?.count) || row.count < 0) throw new CliError("D1 count readback is invalid", "BACKEND_UNAVAILABLE", 1);
    counts[table] = row.count;
  }
  const channels = await db.prepare("SELECT id,name,current_release_id,legacy_current_release_id,revision FROM firmware_channels ORDER BY id LIMIT 9").all();
  if (!channels.success || !Array.isArray(channels.results) || channels.results.length > 8
    || channels.results.length !== counts.firmware_channels || (channels.meta?.rows_written ?? 0) !== 0) {
    throw new CliError("D1 channel readback is incomplete or unexpected", "BACKEND_UNAVAILABLE", 1);
  }
  return { counts, channels: channels.results };
}

export async function checkFirmwareBindings({ root, env, connect = withFirmwareBucket, fetcher = fetch }) {
  const config = bindingsCheckConfig(env);
  // These are existing synthetic qualification objects, never an approved firmware target.
  const bytes = await readFile(path.join(root, fixturePath));
  const metadata = parseFirmwareRegistration(JSON.parse(bytes), config.repository);
  await verifyWorkerEnvironment(config.serviceUrl, "rehearsal", fetcher);
  await workerBindings(config, env.CLOUDFLARE_API_TOKEN, fetcher);
  return connect({ root, accountId: config.accountId, bucketName: config.bucketName,
    databaseId: config.databaseId, databaseName: config.databaseName }, async (bucket, db) => {
    const before = await databaseSnapshot(db);
    const assets = [];
    for (const asset of metadata.assets) assets.push(await verifyStoredFirmwareAsset(metadata, asset.fileName, bucket));
    const after = await databaseSnapshot(db);
    if (canonicalJson(before) !== canonicalJson(after)) throw new CliError("D1 state changed during qualification", "RELEASE_CONFLICT", 1);
    return { ok: true, scope: "RUNTIME_BINDING_QUALIFICATION", canonicalRehearsal: "NOT_RUN", independentAcceptance: "NOT_RUN",
      repository: config.repository, commitSha: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT,
      fixturePath, fixtureSha256: digest(bytes), workerBindingsMatched: true, assets, database: { before, after },
      businessMutations: "NONE_REQUESTED", controlPlane: "WRANGLER_REMOTE_PREVIEW_SESSION" };
  });
}

async function main() {
  const options = args(process.argv.slice(2), ["output"]);
  const root = projectRoot();
  const output = outputPath(root, required(options, "output"));
  const result = await checkFirmwareBindings({ root, env: process.env });
  await writeOutput(root, output, JSON.stringify(result, null, 2) + "\n");
  process.stdout.write(JSON.stringify({ ok: true, scope: result.scope, assetCount: result.assets.length,
    canonicalRehearsal: result.canonicalRehearsal, independentAcceptance: result.independentAcceptance }) + "\n");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
