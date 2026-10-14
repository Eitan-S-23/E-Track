import { CliError } from "./firmware-cli.mjs";
import { FIRMWARE_MODEL, parseFirmwareRegistration, versionCodeFor } from "./firmware-schema.mjs";
import { digest, validateBaseDescriptor } from "./prepare-firmware-release.mjs";

const conflict = message => new CliError(message, "RELEASE_CONFLICT", 1);
const unavailable = message => new CliError(message, "BACKEND_UNAVAILABLE", 1);

export function firmwareGitHub({ repository, token, fetcher = fetch, signal }) {
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository ?? "") || !token) throw new CliError("Explicit GitHub repository/token required");
  const base = `https://api.github.com/repos/${repository}`;
  async function request(url, { timeoutMs = 15000, ...options } = {}) {
    signal?.throwIfAborted();
    return fetcher(url, { ...options, redirect: options.redirect ?? "error", signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)]) : AbortSignal.timeout(timeoutMs),
      headers: { Accept: "application/vnd.github+json", Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28", ...options.headers } });
  }
  async function json(endpoint, options = {}, allowMissing = false) {
    const response = await request(base + endpoint, options);
    if (allowMissing && response.status === 404) return null;
    if (!response.ok) throw unavailable(`GitHub operation failed: HTTP ${response.status}`);
    return response.json();
  }
  async function list(endpoint) {
    const result = [];
    for (let page = 1; page <= 100; page++) {
      const batch = await json(`${endpoint}?per_page=100&page=${page}`);
      if (!Array.isArray(batch)) throw unavailable("Invalid GitHub listing");
      result.push(...batch);
      if (batch.length < 100) return result;
    }
    throw unavailable("GitHub inventory exceeds bounded complete listing");
  }
  async function tagCommit(tag, allowMissing = false) {
    const ref = await json(`/git/ref/tags/${encodeURIComponent(tag)}`, {}, allowMissing);
    if (ref === null) return null;
    let object = ref.object;
    for (let depth = 0; depth < 8; depth++) {
      if (!/^[0-9a-f]{40}$/.test(object?.sha)) throw conflict("Invalid tag identity");
      if (object.type === "commit") return object.sha;
      if (object.type !== "tag") break;
      object = (await json(`/git/tags/${object.sha}`)).object;
    }
    throw conflict("Tag does not resolve to the required commit");
  }
  async function download(asset, expected) {
    if (!Number.isSafeInteger(asset.id) || asset.id <= 0 || asset.state !== "uploaded"
      || asset.name !== expected.fileName || asset.size !== expected.sizeBytes
      || (asset.digest && asset.digest !== `sha256:${expected.sha256}`)) throw conflict("GitHub asset identity mismatch");
    let response = await request(`${base}/releases/assets/${asset.id}`, {
      redirect: "manual", timeoutMs: 300000, headers: { Accept: "application/octet-stream" } });
    // The redirect carries its own short-lived signature. Never forward the
    // repository token to the signed asset host or log that URL.
    if ([301, 302, 303, 307, 308].includes(response.status)) {
      const location = new URL(response.headers.get("Location"));
      if (location.protocol !== "https:" || location.username || location.password
        || !["release-assets.githubusercontent.com", "objects.githubusercontent.com"].includes(location.hostname)) {
        throw unavailable("Untrusted GitHub asset redirect");
      }
      response = await fetcher(location.href, { redirect: "error", signal: signal
        ? AbortSignal.any([signal, AbortSignal.timeout(300000)]) : AbortSignal.timeout(300000) });
    }
    if (!response.ok || !response.body) throw unavailable("GitHub full asset readback failed");
    const reader = response.body.getReader();
    const chunks = []; let size = 0;
    try {
      for (;;) {
        const part = await reader.read();
        if (part.done) break;
        size += part.value.byteLength;
        if (size > expected.sizeBytes) throw conflict("GitHub asset readback length mismatch");
        chunks.push(Buffer.from(part.value));
      }
    } finally { await reader.cancel(); }
    const bytes = Buffer.concat(chunks);
    if (size !== expected.sizeBytes || digest(bytes) !== expected.sha256) throw conflict("GitHub asset full readback digest mismatch");
    return bytes;
  }
  async function formalBase(descriptor, targetVersion) {
    validateBaseDescriptor(descriptor, targetVersion, repository);
    const target = versionCodeFor(targetVersion);
    const releases = await list("/releases");
    const prefix = `mcu-${FIRMWARE_MODEL}-v`;
    const versions = releases.filter(r => !r.draft && !r.prerelease && r.tag_name?.startsWith(prefix)).map(r => {
      try { return { ...r, code: versionCodeFor(r.tag_name.slice(prefix.length)) }; } catch { return null; }
    }).filter(Boolean);
    if (versions.some(r => r.code > target)) throw conflict("Target is behind an existing formal firmware Release");
    const previous = versions.filter(r => r.code < target).sort((a, b) => b.code - a.code)[0];
    if (!previous || previous.tag_name !== descriptor.releaseTag) throw conflict("Descriptor is not the preceding formal Release");
    if (await tagCommit(descriptor.releaseTag) !== descriptor.commitSha) throw conflict("Formal base tag commit mismatch");
    const assets = await list(`/releases/${previous.id}/assets`);
    const fileName = new URL(descriptor.sourceUrl).pathname.split("/").at(-1);
    const matches = assets.filter(a => a.name === fileName);
    if (matches.length !== 1) throw conflict("Formal finalized App source asset is missing or ambiguous");
    const bytes = await download(matches[0], { fileName, sizeBytes: descriptor.sourceSizeBytes, sha256: descriptor.sourceSha256 });
    return { bytes, evidence: { releaseId: previous.id, releaseTag: previous.tag_name,
      commitSha: descriptor.commitSha, assetId: matches[0].id, sourceSha256: digest(bytes), sourceSizeBytes: bytes.length } };
  }
  async function publish(metadata, bytesByName) {
    metadata = parseFirmwareRegistration(metadata, repository, false);
    for (const asset of metadata.assets) {
      const bytes = bytesByName.get(asset.fileName);
      if (!bytes || bytes.length !== asset.sizeBytes || digest(bytes) !== asset.sha256) throw conflict("Local GitHub asset identity mismatch");
    }
    let release = await json(`/releases/tags/${metadata.releaseTag}`, {}, true);
    if (!release) {
      // The by-tag endpoint returns published releases. An interrupted draft
      // must be found through the complete listing, even before its tag exists.
      const matches = (await list("/releases")).filter(r => r.tag_name === metadata.releaseTag);
      if (matches.length > 1) throw conflict("Ambiguous GitHub draft identity");
      release = matches[0];
      if (release && release.draft !== true) throw conflict("Published GitHub Release lookup is inconsistent");
    }
    if (!release) {
      const existingCommit = await tagCommit(metadata.releaseTag, true);
      if (existingCommit !== null && existingCommit !== metadata.commitSha) throw conflict("Existing tag commit differs; do not retarget it");
      release = await json("/releases", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tag_name: metadata.releaseTag, target_commitish: metadata.commitSha,
          name: metadata.releaseTag, body: metadata.releaseNotes, draft: true, prerelease: false }) });
      if (release.draft !== true) throw conflict("New GitHub Release must remain a draft");
    }
    if (!Number.isSafeInteger(release.id) || release.id <= 0) throw unavailable("Invalid GitHub Release identity");
    if (release.tag_name !== metadata.releaseTag || release.prerelease !== false || release.body !== metadata.releaseNotes
      || typeof release.draft !== "boolean" || (release.draft && release.target_commitish !== metadata.commitSha)) {
      throw conflict("Existing GitHub Release identity differs");
    }
    const existingCommit = await tagCommit(metadata.releaseTag, release.draft);
    if (existingCommit !== null && existingCommit !== metadata.commitSha) throw conflict("Existing GitHub Release tag commit differs");
    const before = await list(`/releases/${release.id}/assets`);
    if (before.some(a => !metadata.assets.some(expected => expected.fileName === a.name))
      || new Set(before.map(a => a.name)).size !== before.length) throw conflict("Unexpected or duplicate GitHub assets");
    // Validate every existing asset before adding any missing object.
    for (const asset of before) await download(asset, metadata.assets.find(a => a.fileName === asset.name));
    for (const asset of metadata.assets) {
      if (before.some(a => a.name === asset.fileName)) continue;
      if (!release.draft) throw conflict("Published Release is incomplete; do not append to immutable published assets");
      const bytes = bytesByName.get(asset.fileName);
      const response = await request(`https://uploads.github.com/repos/${repository}/releases/${release.id}/assets?name=${encodeURIComponent(asset.fileName)}`,
        { method: "POST", timeoutMs: 300000, headers: { "Content-Type": asset.kind === "recovery" ? "application/octet-stream" : "application/vnd.e-track.etu",
          "Content-Length": String(bytes.length) }, body: bytes });
      if (response.status !== 201) throw unavailable(`GitHub asset upload failed: HTTP ${response.status}`);
      await download(await response.json(), asset);
    }
    if (release.draft) {
      const commit = await tagCommit(metadata.releaseTag, true);
      if (commit !== null && commit !== metadata.commitSha) throw conflict("GitHub tag changed before draft publication");
      await json(`/releases/${release.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ draft: false }) });
    }
    const after = await json(`/releases/${release.id}`);
    if (after.id !== release.id || after.draft !== false || after.prerelease !== false || after.tag_name !== metadata.releaseTag || after.body !== metadata.releaseNotes
      || await tagCommit(metadata.releaseTag) !== metadata.commitSha) throw conflict("Published Release identity mismatch");
    const inventory = await list(`/releases/${release.id}/assets`);
    if (inventory.length !== metadata.assets.length || new Set(inventory.map(a => a.name)).size !== metadata.assets.length) {
      throw conflict("Published Release asset set differs from metadata");
    }
    for (const expected of metadata.assets) {
      const asset = inventory.find(a => a.name === expected.fileName);
      if (!asset) throw conflict("Published Release asset is missing");
      await download(asset, expected);
    }
    return { releaseId: release.id, assetCount: inventory.length, fullReadbackVerified: true };
  }
  return { formalBase, publish, json };
}
