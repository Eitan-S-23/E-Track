import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { canonicalJson, parseFirmwareRegistration } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { digest } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { preflightFirmware } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-preflight-client.mjs";
import { s3Credentials } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-s3.mjs";
import { verifyStoredFirmwareAsset, withFirmwareBucket } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs";

const fixturePath = "docs/ota-exec-notes/P4-1-r2-registration-qualification-2026-10-15/operations/verified-metadata.json";
const target = Object.freeze({
  repository: "Eitan-S-23/E-Track",
  serviceUrl: "https://e-track-firmware-p41-test.tangjichentudou.workers.dev",
  bucketName: "e-track-firmware-p41-test-releases"
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
  s3Credentials(env);
  if (env.TRACE_UPDATE_SERVICE_URL !== target.serviceUrl || env.TRACE_R2_BUCKET !== target.bucketName
    || env.TRACE_D1_DATABASE_ID || env.TRACE_D1_DATABASE_NAME
    || !/^[0-9a-f]{32}$/.test(env.CLOUDFLARE_ACCOUNT_ID ?? "")
    || !env.TRACE_DEPLOY_TOKEN || /\s/.test(env.TRACE_DEPLOY_TOKEN)) {
    throw new CliError("Bindings qualification requires the explicit isolated Worker, R2 and credential configuration");
  }
  return { ...target, accountId: env.CLOUDFLARE_ACCOUNT_ID };
}

export async function checkFirmwareBindings({ root, env, connect = withFirmwareBucket, fetcher = fetch }) {
  const config = bindingsCheckConfig(env);
  // These are existing synthetic qualification objects, never an approved firmware target.
  const bytes = await readFile(path.join(root, fixturePath));
  const metadata = parseFirmwareRegistration(JSON.parse(bytes), config.repository);
  const check = () => preflightFirmware(metadata, { serviceUrl: config.serviceUrl,
    deployToken: env.TRACE_DEPLOY_TOKEN, mode: "rehearsal", fetcher });
  const before = await check();
  return connect({ root, accountId: config.accountId, bucketName: config.bucketName,
    env }, async (bucket) => {
    const assets = [];
    for (const asset of metadata.assets) assets.push(await verifyStoredFirmwareAsset(metadata, asset.fileName, bucket));
    const after = await check();
    const projection = ({ requestId, ...value }) => value;
    if (canonicalJson(projection(before)) !== canonicalJson(projection(after))) throw new CliError("Preflight state changed during qualification", "RELEASE_CONFLICT", 1);
    return { ok: true, scope: "READ_ONLY_RELEASE_PATH_QUALIFICATION", canonicalRehearsal: "NOT_RUN", independentAcceptance: "NOT_RUN",
      repository: config.repository, commitSha: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT,
      fixturePath, fixtureSha256: digest(bytes), assets, preflight: { before, after },
      businessMutations: "NONE_REQUESTED", controlPlane: "NONE", physicalBindingAttestation: "SEPARATE_DEPLOYMENT_REVIEW_REQUIRED" };
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
