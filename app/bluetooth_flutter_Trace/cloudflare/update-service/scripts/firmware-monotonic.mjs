import { canonicalJson } from "./firmware-schema.mjs";

export class FirmwareMonotonicError extends Error {
  constructor(message) { super(message); this.name = "FirmwareMonotonicError"; this.code = "RELEASE_CONFLICT"; }
}

export async function verifyMonotonic(db, metadata) {
  const fail = message => new FirmwareMonotonicError(message);
  const unresolved = await db.prepare("SELECT COUNT(*) AS count FROM firmware_channels WHERE app_id=? AND device_model=? AND legacy_current_release_id IS NOT NULL")
    .bind(metadata.appId, metadata.deviceModel).first();
  if (!unresolved || unresolved.count !== 0) throw fail("Unresolved legacy firmware channel prevents publication");
  const legacy = await db.prepare("SELECT MAX(version_code) AS version_code FROM firmware_releases_legacy WHERE app_id=? AND device_model=?")
    .bind(metadata.appId, metadata.deviceModel).first();
  if (!legacy || (legacy.version_code !== null && (!Number.isSafeInteger(legacy.version_code) || legacy.version_code >= metadata.versionCode))) {
    throw fail("Target must exceed legacy firmware versions");
  }
  const current = await db.prepare("SELECT version_code,registration_json FROM firmware_releases WHERE app_id=? AND device_model=? ORDER BY version_code DESC LIMIT 1")
    .bind(metadata.appId, metadata.deviceModel).first();
  const projected = { ...metadata, assets: metadata.assets.map(asset => ({ ...asset, r2Verified: true })) };
  if (current && (!Number.isSafeInteger(current.version_code) || current.version_code > metadata.versionCode
    || (current.version_code === metadata.versionCode && current.registration_json !== canonicalJson(projected)))) {
    throw fail("Target must increase D1 version or exactly replay the same canonical registration");
  }
  return { maxVersionCode: current?.version_code ?? null, legacyMaxVersionCode: legacy.version_code, unresolvedLegacyChannels: 0 };
}
