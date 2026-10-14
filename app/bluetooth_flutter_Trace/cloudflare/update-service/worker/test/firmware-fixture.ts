import { env } from "cloudflare:workers";
import { SELF } from "cloudflare:test";
import { expect } from "vitest";
import fixture from "./fixtures/firmware-release-v2.json";
import { assetFileName, canonicalJson, parseFirmwareRegistration, r2KeyFor } from "../../scripts/firmware-schema.mjs";
import type { FirmwareRegistration } from "../../scripts/firmware-schema.mjs";
import { firmwareReleaseInsert } from "../src/firmware";
import { publishFirmware } from "../src/firmware_admin";
import type { FirmwareChannelRow } from "../src/types";

export const SCHEMA_FIXTURE = parseFirmwareRegistration(fixture);
export const BASE_SHA = "11".repeat(32);
let sequence = 0;
export const bytesFor = (kind: string) => new TextEncoder().encode(`P4-2-${kind}-fixture\n`);
export function metadata(): FirmwareRegistration {
  const value = structuredClone(SCHEMA_FIXTURE);
  const n = ++sequence;
  value.versionName = `20.${Math.floor(n / 100)}.${n % 100}`;
  value.versionCode = 200000 + n;
  value.releaseTag = `mcu-e-track-at32f435-v${value.versionName}`;
  value.runId = `p42-${n}`;
  for (const asset of value.assets) {
    asset.fileName = assetFileName(asset.kind, value.versionName, asset.baseVersionCode);
    asset.r2Key = r2KeyFor(value, asset);
    asset.githubUrl = `https://github.com/Eitan-S-23/Trace/releases/download/${value.releaseTag}/${asset.fileName}`;
  }
  return value;
}
export async function uploadFixture(value: FirmwareRegistration) {
  for (const asset of value.assets) await env.RELEASES_BUCKET.put(asset.r2Key, bytesFor(asset.kind), {
    customMetadata: { sha256: asset.sha256, kind: asset.kind }, httpMetadata: {
      contentType: asset.kind === "recovery" ? "application/octet-stream" : "application/vnd.e-track.etu" } });
}
export function register(value: unknown, headers: Record<string, string> = {}) {
  return SELF.fetch("https://example.com/api/ci/firmware/releases", { method: "POST", headers: {
    Authorization: "Bearer test-deploy-token", "Content-Type": "application/json", Accept: "application/json", ...headers
  }, body: JSON.stringify(value) });
}
export async function registered(published = true, override: Partial<FirmwareRegistration> = {}) {
  const input = { ...metadata(), ...override };
  await uploadFixture(input);
  const response = await register(input);
  const body = await response.json<{ releaseId: string; errorCode?: string }>();
  expect(response.status, JSON.stringify(body)).toBe(201);
  if (published) {
    const channel = await env.DB.prepare("SELECT * FROM firmware_channels WHERE name='stable' AND app_id='trace' AND device_model='e-track-at32f435'").first<FirmwareChannelRow>();
    await publishFirmware(env, { email: "owner@example.com", requestId: crypto.randomUUID() }, "stable", {
      appId: input.appId, deviceModel: input.deviceModel, releaseId: body.releaseId, expectedRevision: channel!.revision, reason: "self-test publish" });
  }
  return { input, releaseId: body.releaseId };
}
export async function draft() {
  const input = metadata();
  const id = `draft_${crypto.randomUUID()}`;
  await env.DB.prepare("INSERT OR IGNORE INTO apps(id,name) VALUES ('trace','trace')").run();
  await firmwareReleaseInsert(env.DB, input, id, canonicalJson(input)).run();
  return { input, releaseId: id };
}
export function latest(extra: Record<string, string> = {}) {
  const query = new URLSearchParams({ appId: "trace", deviceModel: "e-track-at32f435", channel: "stable",
    currentVersionCode: "20800", currentImageSha: BASE_SHA, hardwareRevision: "1", layoutId: "1", bootVersion: "1",
    protocolVersion: "1", appVersionCode: "100", ...extra });
  return SELF.fetch(`https://example.com/api/public/firmware/latest?${query}`);
}
export interface LatestBody {
  schemaVersion: number; requestId: string; updateAvailable: boolean; errorCode?: string; releaseId: string;
  minAppVersionCode: number; targetImageSha256: string;
  asset: { assetId: string; kind: string; fileName: string; sha256: string; sizeBytes: number;
    baseImageSha256: string | null; baseVersionCode: number; downloadUrl: string; expiresAt: number };
}
