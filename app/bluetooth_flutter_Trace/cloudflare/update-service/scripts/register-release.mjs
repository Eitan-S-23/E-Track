#!/usr/bin/env node

import { readFile } from "node:fs/promises";

const serviceUrl = process.env.TRACE_UPDATE_SERVICE_URL;
const deployToken = process.env.TRACE_DEPLOY_TOKEN;
const metadataPath = process.argv[2] ?? process.env.TRACE_RELEASE_METADATA_JSON;
const registerRetries = parsePositiveInteger(process.env.TRACE_REGISTER_RETRIES ?? "3", "TRACE_REGISTER_RETRIES");
const registerTimeoutMs = parsePositiveInteger(
  process.env.TRACE_REGISTER_TIMEOUT_MS ?? "30000",
  "TRACE_REGISTER_TIMEOUT_MS"
);

if (!serviceUrl || !deployToken || !metadataPath) {
  process.stderr.write(
    "Usage: TRACE_UPDATE_SERVICE_URL=<url> TRACE_DEPLOY_TOKEN=<token> node scripts/register-release.mjs metadata.json\n"
  );
  process.exit(2);
}

const metadata = JSON.parse(await readFile(metadataPath, "utf8"));
const response = await fetchWithRetry(new URL("/api/ci/releases", serviceUrl), {
  method: "POST",
  headers: {
    Authorization: `Bearer ${deployToken}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(metadata)
});

const body = await response.text();
if (!response.ok) {
  process.stderr.write(`Cloudflare candidate registration failed: HTTP ${response.status}\n`);
  process.stderr.write(`${body}\n`);
  process.exit(1);
}

process.stdout.write(`${body}\n`);

async function fetchWithRetry(url, init) {
  let lastError;
  for (let attempt = 1; attempt <= registerRetries; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), registerTimeoutMs);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } catch (error) {
      lastError = error;
      if (attempt >= registerRetries) break;
      const delayMs = 1500 * attempt;
      process.stderr.write(`Cloudflare candidate registration attempt ${attempt} failed; retrying in ${delayMs}ms...\n`);
      await sleep(delayMs);
    } finally {
      clearTimeout(timeout);
    }
  }
  throw lastError;
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function parsePositiveInteger(value, fieldName) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isInteger(parsed) || parsed < 1 || String(parsed) !== String(value)) {
    process.stderr.write(`${fieldName} must be a positive integer\n`);
    process.exit(2);
  }
  return parsed;
}
