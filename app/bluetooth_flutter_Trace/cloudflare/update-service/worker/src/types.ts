import type { RateLimiter } from "./rate_limiter";

export type Platform = "android" | "windows";
export type ChannelName = "stable" | "beta";
export type ActorType = "ci" | "access" | "system" | "test";
export type ReleaseState = "candidate" | "disabled";

export interface WorkerEnv {
  DB: D1Database;
  MANIFEST_CACHE: KVNamespace;
  RELEASES_BUCKET: R2Bucket;
  RATE_LIMITER: DurableObjectNamespace<RateLimiter>;
  ENVIRONMENT: string;
  APP_ID: string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  MANIFEST_CACHE_TTL_SECONDS: string;
  DOWNLOAD_TOKEN_TTL_SECONDS: string;
  DOWNLOAD_TOKEN_KEY_VERSION: string;
  DOWNLOAD_TOKEN_PREVIOUS_KEY_VERSION?: string;
  RATE_LIMIT_WINDOW_SECONDS: string;
  RATE_LIMIT_MAX_REQUESTS: string;
  ENABLE_DIRECT_ADMIN_API: string;
  DEPLOY_TOKEN_SHA256?: string;
  DOWNLOAD_HMAC_KEY_CURRENT?: string;
  DOWNLOAD_HMAC_KEY_PREVIOUS?: string;
}

export interface AppConfigRow {
  app_id: string;
  default_channel: ChannelName;
  min_supported_client_version_code: number;
  emergency_manifest_url: string | null;
  disable_all_latest: number;
  disable_all_downloads: number;
  maintenance_message: string | null;
}

export interface ReleaseRow {
  id: string;
  app_id: string;
  platform: Platform;
  version_name: string;
  version_code: number;
  release_tag: string;
  commit_sha: string;
  run_id: string;
  state: ReleaseState;
  payload_signature_json: string | null;
  security_payload_json: string;
  release_notes: string;
  min_client_version_code: number;
  capabilities_json: string;
  archived: number;
  fallback_only: number;
}

export interface AssetRow {
  id: string;
  release_id: string;
  app_id: string;
  platform: Platform;
  asset_type: "apk" | "windows_zip" | "windows_exe" | "manifest" | "patch";
  file_name: string;
  sha256: string;
  size_bytes: number;
  r2_key: string | null;
  r2_state: "not_uploaded" | "available" | "r2_deleted" | "archived";
  github_url: string;
  disabled: number;
}

export interface PatchRow {
  id: string;
  app_id: string;
  platform: Platform;
  to_release_id: string;
  asset_id: string;
  from_version_code: number;
  old_sha256: string;
  patch_format: "tracepatch" | "vcdiff";
  patch_sha256: string;
  patch_size_bytes: number;
  output_sha256: string;
  output_size_bytes: number;
  disabled: number;
  file_name: string;
}

export interface FirmwareReleaseRow {
  id: string;
  app_id: string;
  device_model: string;
  version_name: string;
  version_code: number;
  release_tag: string;
  commit_sha: string;
  run_id: string;
  state: ReleaseState;
  release_notes: string;
  file_name: string;
  sha256: string;
  size_bytes: number;
  r2_key: string | null;
  r2_state: "not_uploaded" | "available" | "r2_deleted" | "archived";
  github_url: string;
  target_hardware: string | null;
  transport: string;
  min_app_version_code: number;
  archived: number;
}

export interface FirmwareChannelRow {
  id: string;
  app_id: string;
  device_model: string;
  name: ChannelName;
  current_release_id: string | null;
  revision: number;
  disable_latest: number;
  disable_downloads: number;
  maintenance_message: string | null;
}

export interface ChannelRow {
  id: string;
  app_id: string;
  platform: Platform;
  name: ChannelName;
  current_release_id: string | null;
  revision: number;
  disable_latest: number;
  disable_downloads: number;
  maintenance_admin_only: number;
  maintenance_message: string | null;
}

export interface Actor {
  actor: string;
  actorType: ActorType;
  requestId: string;
  ip?: string;
  userAgent?: string;
}

export interface SecurityPayload {
  appId: string;
  platform: Platform;
  versionName: string;
  versionCode: number;
  releaseTag: string;
  apkAssetName: string;
  apkSha256: string;
  apkSize: number;
  patches: Array<Record<string, unknown>>;
  assetHashes: Array<Record<string, unknown>>;
  minClientVersionCode: number;
  capabilities: string[];
}
