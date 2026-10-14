import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, failure, projectRoot, required, writeOutput } from "./firmware-cli.mjs";
import { assetFileName, canonicalJson, FIRMWARE_MODEL, parseFirmwareRegistration, r2KeyFor, versionCodeFor } from "./firmware-schema.mjs";

export async function buildFirmwareMetadata({ release, assetsDir, finalImage, patchBases = [], repository = "Eitan-S-23/Trace" }) {
  // No artifact writes, uploads or packaging. Image identity comes from final
  // app.bin bytes, never from the full/patch/recovery file digest.
  const image = await readFile(finalImage);
  if (!image.byteLength) throw new Error("Empty final image");
  const base = { ...release, schemaVersion: 2, appId: "trace", deviceModel: FIRMWARE_MODEL,
    versionCode: versionCodeFor(release.versionName), transport: "ble", isFormalRelease: true,
    targetImageSha256: createHash("sha256").update(image).digest("hex") };
  const entries = [{ kind: "full", baseImageSha256: "", baseVersionCode: 0 },
    ...patchBases.map((v) => ({ ...v, kind: "patch" })), { kind: "recovery", baseImageSha256: "", baseVersionCode: 0 }];
  const assets = [];
  for (const entry of entries) {
    const fileName = assetFileName(entry.kind, base.versionName, entry.baseVersionCode);
    const filePath = path.join(assetsDir, fileName);
    const bytes = await readFile(filePath);
    if ((await stat(filePath)).size !== bytes.length || !bytes.length) throw new Error("Asset file changed or empty");
    const asset = { ...entry, fileName, sha256: createHash("sha256").update(bytes).digest("hex"), sizeBytes: bytes.length,
      githubUrl: `https://github.com/${repository}/releases/download/${encodeURIComponent(base.releaseTag)}/${fileName}`,
      r2Key: r2KeyFor(base, { fileName }), r2Verified: false };
    assets.push(asset);
  }
  return parseFirmwareRegistration({ ...base, assets }, repository, false);
}

async function main() {
  const options = args(process.argv.slice(2), ["assets-dir", "release-tag", "run-id", "commit-sha", "version-name",
    "release-notes", "target-hardware", "hardware-revision", "layout-id", "min-boot-version", "min-protocol-version",
    "min-app-version-code", "final-image", "patch-bases", "repository", "output"]);
  const release = {
    releaseTag: required(options, "release-tag", "GITHUB_REF_NAME"), runId: required(options, "run-id", "GITHUB_RUN_ID"),
    commitSha: required(options, "commit-sha", "GITHUB_SHA"), versionName: required(options, "version-name", "TRACE_FIRMWARE_VERSION_NAME"),
    releaseNotes: options["release-notes"] ?? "", targetHardware: required(options, "target-hardware"),
    hardwareRevision: Number(required(options, "hardware-revision")), layoutId: Number(required(options, "layout-id")),
    minBootVersion: Number(required(options, "min-boot-version")), minProtocolVersion: Number(required(options, "min-protocol-version")),
    minAppVersionCode: Number(required(options, "min-app-version-code"))
  };
  const assetsDir = path.resolve(required(options, "assets-dir", "TRACE_FIRMWARE_ASSETS_DIR"));
  const metadata = await buildFirmwareMetadata({ release, assetsDir, finalImage: required(options, "final-image"),
    patchBases: options["patch-bases"] ? JSON.parse(await readFile(options["patch-bases"], "utf8")) : [],
    repository: options.repository ?? process.env.GITHUB_REPOSITORY ?? "Eitan-S-23/Trace" });
  const output = path.resolve(options.output ?? path.join(assetsDir, "cloudflare-firmware-release-metadata.json"));
  await writeOutput(projectRoot(), output, canonicalJson(metadata) + "\n");
  process.stdout.write(JSON.stringify({ ok: true, output, assetsPrepared: metadata.assets.length, r2Verified: false }) + "\n");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
