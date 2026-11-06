// Real normal packaging of synthetic App bytes; never a device candidate.
import { spawnSync } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { captureBuildInputs, digest, prepareFirmwareRelease } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { outputPath, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";

const root = path.resolve(fileURLToPath(new URL("../../", import.meta.url)));
const dir = outputPath(root, process.argv[2]);
const headerOnly = process.argv[3] === "header-only";
const python = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");
const bsdiff = process.env.BSDIFF_EXE ?? path.join(root, "bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe");
await mkdir(dir);
const raw = Buffer.alloc(8192);
let state = 0x12345678;
for (let i = 0; i < raw.length; i++) {
  state ^= state << 13; state ^= state >>> 17; state ^= state << 5;
  raw[i] = state & 0xff;
}
raw.writeUInt32LE(0x20057ff0, 0); raw.writeUInt32LE(0x08010501, 4);
raw.fill(0xff, 0x400, 0x460);
const app = path.join(dir, "X-Track-App-GCC.bin"), boot = path.join(dir, "X-Track-Boot.bin");
const old = Buffer.from(raw);
if (!headerOnly) old[0x500] ^= 0x19;
const placeholder = path.join(dir, "old-placeholder.bin"), baseFile = path.join(dir, "base.bin");
await writeOutput(root, app, raw);
await writeOutput(root, boot, Buffer.from("synthetic Boot, not installable"));
await writeOutput(root, placeholder, old);
const argv = ["-B", path.join(root, "Tools/etu_pack.py"), "finalize", "--app", placeholder,
  "--out", baseFile, "--ver-name", "2.8.0", "--build-ts", "1786320000"];
const setup = spawnSync(python, argv, { cwd: dir, env: process.env, encoding: "utf8", windowsHide: true, timeout: 30000 });
await writeOutput(root, path.join(dir, "base-finalize.stdout"), setup.stdout ?? "");
await writeOutput(root, path.join(dir, "base-finalize.stderr"), setup.stderr ?? "");
await writeOutput(root, path.join(dir, "base-finalize.json"), JSON.stringify({ argv, cwd: dir, exit: setup.status }));
if (setup.status !== 0) throw new Error("Fixture base finalization failed; inspect retained outputs");
const release = JSON.parse(await readFile(path.join(root,
  "app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/fixtures/firmware-release-v2.json"), "utf8"));
delete release.assets;
const bytes = await readFile(baseFile);
const repository = "Eitan-S-23/Trace";
const base = { isFormalRelease: true, kind: "app", versionName: "2.8.0", versionCode: 20800,
  releaseTag: "mcu-e-track-at32f435-v2.8.0", commitSha: "2".repeat(40), imageSha256: digest(bytes),
  sourceSha256: digest(bytes), sourceSizeBytes: bytes.length,
  sourceUrl: `https://github.com/${repository}/releases/download/mcu-e-track-at32f435-v2.8.0/X-Track-App-GCC.bin` };
const build = await captureBuildInputs({ app, boot, commitSha: release.commitSha,
  versionName: release.versionName, buildTimestamp: 1786320000 });
const result = await prepareFirmwareRelease({ root, app, boot, build, release, repository, base, baseFile,
  outputDir: path.join(dir, "prepared"), aesKey: "01".repeat(16), bsdiff, python });
await writeOutput(root, path.join(dir, "DEVELOPMENT-ONLY.json"), JSON.stringify({
  installable: false, publishable: false, scope: "synthetic host fixture, not real source provenance",
  headerOnly, output: result.outputDir }));
process.stdout.write(JSON.stringify({ prepared: result.outputDir, tool: path.resolve(bsdiff) }) + "\n");
