import { invalidParameter } from "./errors";
import type { ChannelName, Platform } from "./types";

export function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw invalidParameter(`${field} is required`);
  }
  return value.trim();
}

export function optionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() !== "" ? value.trim() : undefined;
}

export function requireInt(value: unknown, field: string): number {
  const parsed =
    typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw invalidParameter(`${field} must be a non-negative integer`);
  }
  return parsed;
}

export function requireSha256(value: unknown, field: string): string {
  const text = requireString(value, field).toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(text)) {
    throw invalidParameter(`${field} must be a SHA-256 hex digest`);
  }
  return text;
}

export function parsePlatform(value: unknown): Platform {
  if (value === "android" || value === "windows") return value;
  throw invalidParameter("platform must be android or windows");
}

export function parseChannel(value: unknown): ChannelName {
  if (value === "stable" || value === "beta") return value;
  throw invalidParameter("channel must be stable or beta");
}

export function parseJsonArray(value: string): string[] {
  const parsed = JSON.parse(value) as unknown;
  return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
}

export function parseCapabilities(value: string | null): string[] {
  if (!value) return [];
  return value
    .split(",")
    .map((capability) => capability.trim())
    .filter((capability) => capability.length > 0);
}

export function parseJsonObject(value: string | null): Record<string, unknown> {
  if (!value) return {};
  const parsed = JSON.parse(value) as unknown;
  return parsed && typeof parsed === "object" && !Array.isArray(parsed)
    ? (parsed as Record<string, unknown>)
    : {};
}
