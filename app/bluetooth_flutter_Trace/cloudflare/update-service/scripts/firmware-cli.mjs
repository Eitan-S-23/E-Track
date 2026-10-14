import { existsSync, lstatSync, realpathSync } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";

export class CliError extends Error {
  constructor(message, code = "INVALID_PARAMETER", exitCode = 2, requestId) { super(message); this.code = code; this.exitCode = exitCode; this.requestId = requestId; }
}
export function args(argv, allowed, flags = []) {
  const result = {};
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i].slice(2);
    if (!argv[i].startsWith("--") || !allowed.includes(key) || Object.hasOwn(result, key)) throw new CliError("Unknown or duplicate CLI option");
    if (flags.includes(key)) { result[key] = true; continue; }
    if (!argv[i + 1] || argv[i + 1].startsWith("--")) throw new CliError(`Missing --${key} value`);
    result[key] = argv[++i];
  }
  return result;
}
export function required(options, key, envName) {
  const value = options[key] ?? (envName ? process.env[envName] : undefined);
  if (!value) throw new CliError(`Missing --${key}${envName ? ` or ${envName}` : ""}`);
  return value;
}
export function projectRoot() {
  return realpathSync.native(execFileSync("git", ["rev-parse", "--show-toplevel"],
    { cwd: process.cwd(), encoding: "utf8", windowsHide: true }).trim());
}
export function outputPath(root, value) {
  const target = path.resolve(value);
  let parent = target;
  while (!existsSync(parent)) parent = path.dirname(parent);
  const real = path.join(realpathSync.native(parent), path.relative(parent, target));
  const relative = path.relative(root, real);
  if (relative === ".." || relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) throw new CliError("Output escapes the active project");
  for (let p = target; p !== path.dirname(p); p = path.dirname(p)) {
    if (existsSync(p) && lstatSync(p).isSymbolicLink()) throw new CliError("Output parent is a link/reparse point");
  }
  return target;
}
export async function writeOutput(root, value, bytes) {
  const target = outputPath(root, value);
  await mkdir(path.dirname(target), { recursive: true });
  outputPath(root, target);
  await writeFile(target, bytes);
}
export function failure(error, requestId = error?.requestId ?? crypto.randomUUID()) {
  const allowed = ["INVALID_PARAMETER", "FORMAL_RELEASE_REQUIRED", "R2_OBJECT_CONFLICT", "R2_VERIFY_FAILED", "BACKEND_UNAVAILABLE",
    "RELEASE_CONFLICT", "RELEASE_INCOMPLETE", "TOKEN_INVALID", "TOKEN_EXPIRED", "RATE_LIMITED"];
  const errorCode = allowed.includes(error?.code) ? error.code : "BACKEND_UNAVAILABLE";
  // Never print a server body, URL, Authorization header, credential or stack.
  const message = error instanceof CliError || error?.name === "FirmwareSchemaError"
    ? error.message : "Firmware operation failed; no verified result was committed";
  process.stderr.write(JSON.stringify({ errorCode, message, requestId }) + "\n");
  process.exitCode = error instanceof CliError ? error.exitCode : 1;
}
