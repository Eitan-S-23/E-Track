import { execFileSync, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, open, readFile, stat, unlink } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { args, CliError, failure, outputPath, projectRoot, required, writeOutput } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-cli.mjs";
import { versionCodeFor } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-schema.mjs";
import { captureBuildInputs, digest } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs";
import { approvedFirmwareKey, DEVELOPMENT_PACKAGING_KEY, firmwareKeyBinding, firmwareKeyHeader } from "../../app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-key.mjs";

function ownerIdentity(env) {
  if (!/^[0-9a-f]{40}$/.test(env.GITHUB_SHA ?? "") || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ID ?? "")
    || !/^[1-9][0-9]*$/.test(env.GITHUB_RUN_ATTEMPT ?? "")) throw new CliError("A key build requires exact source/run ownership");
  return { commitSha: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, runAttempt: env.GITHUB_RUN_ATTEMPT };
}

export async function cleanupPrivateBuildKey({ root, buildDir, env = process.env }) {
  const owner = ownerIdentity(env);
  buildDir = outputPath(root, path.resolve(root, buildDir));
  const header = outputPath(root, path.join(buildDir, "private-key.h"));
  if (!existsSync(header)) return;
  const recorded = JSON.parse(await readFile(outputPath(root, path.join(buildDir, "key-build-owner.json")), "utf8"));
  if (JSON.stringify(recorded) !== JSON.stringify(owner)) throw new CliError("Refusing to clean a different key-build owner");
  await unlink(header);
  if (existsSync(header)) throw new CliError("Private build key cleanup did not complete", "INVALID_PARAMETER", 1);
}

export async function buildKeyedFirmware({ root, buildDir, evidenceDir, versionName, commitSha, buildTimestamp,
  env = process.env, development = false, execute = spawnSync, writePrivateHeader = (handle, bytes) => handle.writeFile(bytes) }) {
  const owner = ownerIdentity(env);
  versionCodeFor(versionName);
  if (!/^[0-9a-f]{40}$/.test(commitSha) || commitSha !== env.GITHUB_SHA || !Number.isSafeInteger(buildTimestamp)
    || buildTimestamp < 0 || buildTimestamp > 0xffffffff) throw new CliError("Invalid key-bound build source identity");
  if (env.CLOUDFLARE_API_TOKEN || env.TRACE_DEPLOY_TOKEN || env.GITHUB_TOKEN) throw new CliError("Key-bound compilation must not receive cloud or publishing credentials");
  let key, keyBinding;
  if (development) {
    if (env.OTA_AES_KEY) throw new CliError("Development compilation must not receive release key configuration");
    key = DEVELOPMENT_PACKAGING_KEY;
    keyBinding = firmwareKeyBinding(key, "development-ci-key-v1");
  } else {
    const mode = env.FIRMWARE_RELEASE_MODE;
    if (env.GITHUB_EVENT_NAME !== "workflow_dispatch" || !["rehearsal", "production"].includes(mode)
      || env.INPUT_CHECK_BINDINGS === "true" || env.OTA_BOOT_CHAIN_READY !== (mode === "production" ? "true" : "false")
      || (mode === "production" ? env.INPUT_PUBLISH !== "true" || env.INPUT_REHEARSAL === "true"
        : env.INPUT_REHEARSAL !== "true" || env.INPUT_PUBLISH === "true")) throw new CliError("Key-bound compilation requires the gated protected release context");
    keyBinding = approvedFirmwareKey(env); key = env.OTA_AES_KEY;
  }
  buildDir = outputPath(root, path.resolve(root, buildDir)); evidenceDir = outputPath(root, path.resolve(root, evidenceDir));
  if (existsSync(buildDir) || existsSync(evidenceDir)) throw new CliError("Key-bound builds require fresh build and evidence directories");
  const contains = (parent, child) => { const relative = path.relative(parent, child); return !relative || (!relative.startsWith(`..${path.sep}`) && relative !== ".." && !path.isAbsolute(relative)); };
  if (contains(buildDir, evidenceDir) || contains(evidenceDir, buildDir)) throw new CliError("Build and evidence directories must be separate");
  const header = outputPath(root, path.join(buildDir, "private-key.h"));
  const ownerFile = outputPath(root, path.join(buildDir, "key-build-owner.json"));
  const temp = outputPath(root, path.join(buildDir, "tmp"));
  const targets = [["app-gcc", "app", "X-Track-App-GCC"], ["boot", "boot", "X-Track-Boot"]];
  for (const [, dir, name] of targets) for (const extension of ["bin", "elf", "hex", "map"]) outputPath(root, path.join(evidenceDir, dir, `${name}.${extension}`));
  for (const file of ["gcc-build-inputs.json", "keyed-build-evidence.json", "DEVELOPMENT-ONLY.json", "steps.json",
    "CMakeCache.txt", "compiler-launchers.ninja",
    "steps/configure.stdout.txt", "steps/configure.stderr.txt", "steps/build.stdout.txt", "steps/build.stderr.txt",
    "steps/size.stdout.txt", "steps/size.stderr.txt"]) outputPath(root, path.join(evidenceDir, file));
  await mkdir(temp, { recursive: true }); await mkdir(evidenceDir, { recursive: true });
  await writeOutput(root, ownerFile, JSON.stringify(owner));
  const childEnv = { ...env, SOURCE_DATE_EPOCH: "1786320000", TEMP: temp, TMP: temp, TMPDIR: temp };
  for (const name of Object.keys(childEnv)) if (/^(OTA_|CLOUDFLARE_|CF_|TRACE_|GH_|GITHUB_TOKEN|CCACHE_|SCCACHE_)/.test(name)) delete childEnv[name];
  const redact = text => [key, ...key.match(/.{8}/g)].reduce((value, secret) =>
    value.replaceAll(secret.toLowerCase(), "[REDACTED_KEY]").replaceAll(secret.toUpperCase(), "[REDACTED_KEY]"), text);
  const steps = [];
  async function run(label, executable, argv) {
    const result = await execute(executable, argv, { cwd: root, env: childEnv, encoding: "utf8", windowsHide: true,
      timeout: 600000, maxBuffer: 16 * 1024 * 1024 });
    const stdout = redact(result.stdout ?? ""), stderr = redact(result.stderr ?? "");
    await writeOutput(root, path.join(evidenceDir, "steps", `${label}.stdout.txt`), stdout);
    await writeOutput(root, path.join(evidenceDir, "steps", `${label}.stderr.txt`), stderr);
    steps.push({ label, executable, argv, exitCode: result.status,
      warningLines: (stdout + "\n" + stderr).split(/\r?\n/).filter(line => /warning:/i.test(line)).length,
      errorLines: (stdout + "\n" + stderr).split(/\r?\n/).filter(line => /error:/i.test(line)).length,
      stdoutSha256: digest(Buffer.from(stdout)), stderrSha256: digest(Buffer.from(stderr)) });
    await writeOutput(root, path.join(evidenceDir, "steps.json"), JSON.stringify(steps, null, 2) + "\n");
    process.stdout.write(stdout); process.stderr.write(stderr);
    if (result.error || result.status !== 0) throw new CliError(`Key-bound GCC ${label} failed; sanitized diagnostics preserved`, "INVALID_PARAMETER", 1);
  }
  let headerCreated = false;
  try {
    const handle = await open(header, "wx", 0o600); headerCreated = true;
    try { await writePrivateHeader(handle, firmwareKeyHeader(key)); }
    finally { await handle.close(); }
    await run("configure", "cmake", ["-S", path.join(root, "MDK-ARM_F435/cmake-generated"), "-B", buildDir,
      "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_OBJECT_PATH_MAX=1024", "-DKEIL_GCC_COMPILER_CACHE:STRING=OFF",
      `-DCMAKE_C_FLAGS=-include \"${header.replaceAll("\\", "/")}\"`]);
    const cache = await readFile(path.join(buildDir, "CMakeCache.txt"));
    const rules = await readFile(path.join(buildDir, "CMakeFiles/rules.ninja"));
    if (!/^KEIL_GCC_COMPILER_CACHE:STRING=OFF\r?$/m.test(cache.toString())
      || /(?:^|[\\/\s])(?:sccache|ccache)(?:\.exe)?(?:\s|$)/im.test(rules.toString())) {
      throw new CliError("Private-key builds must not use a compiler cache", "INVALID_PARAMETER", 1);
    }
    await writeOutput(root, path.join(evidenceDir, "CMakeCache.txt"), cache);
    await writeOutput(root, path.join(evidenceDir, "compiler-launchers.ninja"), rules);
    const commands = JSON.parse(await readFile(path.join(buildDir, "compile_commands.json"), "utf8"));
    const keyCommands = commands.filter(entry => entry.file.replaceAll("\\", "/").endsWith("/Libraries/OTA/ota_keys.c")
      && entry.command.replaceAll("\\", "/").includes("CMakeFiles/X_Track_App_GCC.dir/"));
    const escapedHeader = header.replaceAll("\\", "/").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const includesHeader = new RegExp(`(?:^|\\s)-include\\s+(?:"${escapedHeader}"|${escapedHeader})(?:\\s|$)`);
    if (keyCommands.length !== 1 || !includesHeader.test(keyCommands[0].command.replaceAll("\\", "/"))
      || /-D\s*OTA_AES_KEY_1_WORD/.test(keyCommands[0].command)) {
      throw new CliError("GCC App key source does not consume the private key header", "INVALID_PARAMETER", 1);
    }
    await run("build", "cmake", ["--build", buildDir, "--target", "X_Track_App_GCC", "X_Track_Boot", "--parallel"]);
    if (digest(await readFile(header)) !== keyBinding.headerSha256) throw new CliError("Compiled key input changed during build");
    await cleanupPrivateBuildKey({ root, buildDir, env }); headerCreated = false;
    await run("size", "arm-none-eabi-size", ["--format=berkeley", ...targets.map(([dir, , name]) => path.join(buildDir, dir, `${name}.elf`))]);
    const artifacts = [];
    for (const [sourceDir, dir, name] of targets) for (const extension of ["bin", "elf", "hex", "map"]) {
      const source = path.join(buildDir, sourceDir, `${name}.${extension}`), bytes = await readFile(source);
      if (!bytes.length) throw new CliError("Key-bound GCC artifact is empty", "INVALID_PARAMETER", 1);
      await writeOutput(root, path.join(evidenceDir, dir, `${name}.${extension}`), bytes);
      artifacts.push({ path: `${dir}/${name}.${extension}`, sizeBytes: bytes.length, sha256: digest(bytes), modifiedAt: (await stat(source)).mtime.toISOString() });
    }
    const build = await captureBuildInputs({ app: path.join(evidenceDir, "app/X-Track-App-GCC.bin"),
      boot: path.join(evidenceDir, "boot/X-Track-Boot.bin"), commitSha, versionName, buildTimestamp, keyBinding });
    await writeOutput(root, path.join(evidenceDir, "gcc-build-inputs.json"), JSON.stringify(build, null, 2) + "\n");
    await writeOutput(root, path.join(evidenceDir, "keyed-build-evidence.json"), JSON.stringify({ commitSha, versionName,
      keyBinding, keyCompileCommand: keyCommands[0], artifacts, steps, sourceDateEpoch: childEnv.SOURCE_DATE_EPOCH,
      compilerCache: "DISABLED", compilerCacheConfigSha256: digest(cache), compilerLaunchersSha256: digest(rules),
      bootKeyConsumer: false, note: "App decrypts ETU; matching Boot is built in the same invocation, not an AES consumer" }, null, 2) + "\n");
    if (development) await writeOutput(root, path.join(evidenceDir, "DEVELOPMENT-ONLY.json"), JSON.stringify({
      installable: false, publishable: false, keySource: "development-ci-key-v1", rehearsal: "NOT_RUN" }) + "\n");
    return build;
  } finally { if (headerCreated) await cleanupPrivateBuildKey({ root, buildDir, env }); }
}

async function main() {
  if (process.argv[2] === "cleanup") {
    const options = args(process.argv.slice(3), ["build-dir"]);
    await cleanupPrivateBuildKey({ root: projectRoot(), buildDir: required(options, "build-dir") });
    process.stdout.write(JSON.stringify({ privateBuildKeyAbsent: true }) + "\n");
    return;
  }
  const options = args(process.argv.slice(2), ["build-dir", "evidence-dir", "version", "development"], ["development"]);
  const root = projectRoot();
  const git = argv => execFileSync("git", argv, { cwd: root, encoding: "utf8", windowsHide: true }).trim();
  const commitSha = git(["rev-parse", "HEAD"]);
  const build = await buildKeyedFirmware({ root, buildDir: required(options, "build-dir"), evidenceDir: required(options, "evidence-dir"),
    versionName: required(options, "version"), commitSha, buildTimestamp: Number(git(["show", "-s", "--format=%ct", "HEAD"])), development: options.development === true });
  process.stdout.write(JSON.stringify({ ok: true, commitSha, versionName: build.versionName, keyBinding: build.keyBinding,
    app: build.app, boot: build.boot, developmentOnly: options.development === true }) + "\n");
}
if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) main().catch(failure);
