export const FIRMWARE_MODEL = "e-track-at32f435";
export const U32_MAX = 4294967295;
export const APP_VERSION_MAX = 2100000000;

export class FirmwareSchemaError extends Error {
  constructor(message, code = "INVALID_PARAMETER") {
    super(message);
    this.name = "FirmwareSchemaError";
    this.code = code;
  }
}

export function exactObject(value, keys, label = "body") {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new FirmwareSchemaError(`${label} must be an object`);
  }
  for (const key of Object.keys(value)) {
    if (!keys.includes(key)) throw new FirmwareSchemaError(`Unknown ${label} field: ${key}`);
  }
  return value;
}

export function text(value, label, allowEmpty = false) {
  if (typeof value !== "string" || (!allowEmpty && !value.trim()) || /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value)) {
    throw new FirmwareSchemaError(`${label} must be a valid string`);
  }
  if (/[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(value)) {
    throw new FirmwareSchemaError(`${label} contains invalid Unicode`);
  }
  return value;
}

export function integer(value, label, max = Number.MAX_SAFE_INTEGER, min = 0) {
  if (!Number.isSafeInteger(value) || value < min || value > max) {
    throw new FirmwareSchemaError(`${label} must be an integer in ${min}..${max}`);
  }
  return value;
}

export function sha256(value, label) {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/.test(value)) {
    throw new FirmwareSchemaError(`${label} must be 64 lowercase hex characters`);
  }
  return value;
}

export function versionCodeFor(version) {
  if (typeof version !== "string" || !/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)$/.test(version)) {
    throw new FirmwareSchemaError("versionName must be a canonical firmware version");
  }
  const [major, minor, patch] = version.split(".").map(Number);
  return integer(major * 10000 + minor * 100 + patch, "versionCode", U32_MAX);
}

export function versionNameFor(code) {
  integer(code, "baseVersionCode", U32_MAX);
  return `${Math.floor(code / 10000)}.${Math.floor(code / 100) % 100}.${code % 100}`;
}

export function assetFileName(kind, targetVersion, baseVersionCode = 0) {
  versionCodeFor(targetVersion);
  if (kind === "full") return `${FIRMWARE_MODEL}-v${targetVersion}-full.etu`;
  if (kind === "recovery") return `recovery-v${targetVersion}.bin`;
  if (kind === "patch") return `${FIRMWARE_MODEL}-v${versionNameFor(baseVersionCode)}-to-v${targetVersion}-patch.etu`;
  throw new FirmwareSchemaError("Unknown asset kind");
}

export function r2KeyFor(release, asset) {
  return `${release.appId}/firmware/${release.deviceModel}/${release.versionCode}-${release.releaseTag}/${asset.fileName}`;
}

export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

export function contentDigest(hex) {
  sha256(hex, "sha256");
  return `sha-256=:${btoa(String.fromCharCode(...hex.match(/../g).map((v) => parseInt(v, 16))))}:`;
}

export function parseFirmwareRegistration(value, repository, requireVerified = true) {
  const input = exactObject(value, ["schemaVersion", "appId", "deviceModel", "releaseTag", "runId", "commitSha",
    "versionName", "versionCode", "releaseNotes", "targetImageSha256", "hardwareRevision", "layoutId",
    "minBootVersion", "minProtocolVersion", "targetHardware", "transport", "minAppVersionCode",
    "isFormalRelease", "assets"]);
  if (input.schemaVersion !== 2) throw new FirmwareSchemaError("schemaVersion must be 2");
  if (input.appId !== "trace" || input.deviceModel !== FIRMWARE_MODEL) {
    throw new FirmwareSchemaError("Unsupported firmware appId/deviceModel");
  }
  if (input.isFormalRelease !== true) throw new FirmwareSchemaError("Formal firmware release required", "FORMAL_RELEASE_REQUIRED");
  text(input.releaseTag, "releaseTag");
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(input.releaseTag) || input.releaseTag.includes("..")) {
    throw new FirmwareSchemaError("releaseTag is not a safe immutable path component");
  }
  text(input.runId, "runId");
  if (typeof input.commitSha !== "string" || !/^[0-9a-f]{40}$/.test(input.commitSha)) {
    throw new FirmwareSchemaError("commitSha must be 40 lowercase hex characters");
  }
  if (versionCodeFor(input.versionName) !== integer(input.versionCode, "versionCode", U32_MAX)) {
    throw new FirmwareSchemaError("versionName/versionCode mismatch");
  }
  text(input.releaseNotes, "releaseNotes", true);
  sha256(input.targetImageSha256, "targetImageSha256");
  integer(input.hardwareRevision, "hardwareRevision", 65535);
  for (const key of ["layoutId", "minBootVersion", "minProtocolVersion"]) integer(input[key], key, 255);
  text(input.targetHardware, "targetHardware");
  if (input.transport !== "ble") throw new FirmwareSchemaError("transport must be ble");
  integer(input.minAppVersionCode, "minAppVersionCode", APP_VERSION_MAX);
  if (!Array.isArray(input.assets) || input.assets.length === 0) throw new FirmwareSchemaError("assets must be a nonempty array");
  const identities = new Set();
  const names = new Set();
  const assets = input.assets.map((value) => {
    const asset = exactObject(value, ["kind", "fileName", "sha256", "sizeBytes", "baseImageSha256",
      "baseVersionCode", "githubUrl", "r2Key", "r2Verified"], "asset");
    if (!["full", "patch", "recovery"].includes(asset.kind)) throw new FirmwareSchemaError("Unknown asset kind");
    integer(asset.baseVersionCode, "baseVersionCode", U32_MAX);
    if (asset.kind === "patch") {
      sha256(asset.baseImageSha256, "baseImageSha256");
      if (asset.baseVersionCode <= 0 || asset.baseVersionCode >= input.versionCode) {
        throw new FirmwareSchemaError("patch base must precede target");
      }
    } else if (asset.baseImageSha256 !== "" || asset.baseVersionCode !== 0) {
      throw new FirmwareSchemaError("full/recovery require empty base SHA and zero base version");
    }
    if (typeof asset.fileName !== "string" || asset.fileName.length > 128
      || asset.fileName !== assetFileName(asset.kind, input.versionName, asset.baseVersionCode)) {
      throw new FirmwareSchemaError("asset fileName does not match the canonical naming policy");
    }
    const identity = `${asset.kind}:${asset.baseImageSha256}`;
    if (identities.has(identity) || names.has(asset.fileName)) throw new FirmwareSchemaError("Duplicate asset kind/base or fileName");
    identities.add(identity);
    names.add(asset.fileName);
    sha256(asset.sha256, "asset.sha256");
    integer(asset.sizeBytes, "asset.sizeBytes", Number.MAX_SAFE_INTEGER, 1);
    if (typeof asset.r2Verified !== "boolean" || (requireVerified && !asset.r2Verified)) {
      throw new FirmwareSchemaError("Every asset must have verified R2 readback");
    }
    if (asset.r2Key !== r2KeyFor(input, asset)) throw new FirmwareSchemaError("Unexpected firmware R2 key");
    let url;
    try { url = new URL(asset.githubUrl); } catch { throw new FirmwareSchemaError("Invalid GitHub asset URL"); }
    const parts = url.pathname.split("/");
    const repo = repository ?? `${parts[1]}/${parts[2]}`;
    if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo)
      || asset.githubUrl !== `https://github.com/${repo}/releases/download/${encodeURIComponent(input.releaseTag)}/${encodeURIComponent(asset.fileName)}`) {
      throw new FirmwareSchemaError("GitHub URL must bind repository, releaseTag and fileName");
    }
    return { ...asset };
  });
  if (assets.filter((a) => a.kind === "full").length !== 1 || assets.filter((a) => a.kind === "recovery").length !== 1) {
    throw new FirmwareSchemaError("Formal registration requires exactly one full and one recovery");
  }
  assets.sort((a, b) => (a.kind < b.kind ? -1 : a.kind > b.kind ? 1 : 0)
    || a.baseVersionCode - b.baseVersionCode || (a.fileName < b.fileName ? -1 : a.fileName > b.fileName ? 1 : 0));
  return { ...input, assets };
}
