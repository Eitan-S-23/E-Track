# Trace Cloudflare Update Service

Phase 2 staging implements and verifies the update control plane plus R2 primary distribution path. It still does not deploy production services.

## Scope

- Worker public API decides latest release from D1 channel state.
- Downloads are gated by Worker HMAC tokens and D1 state checks.
- Primary download endpoints stream verified R2 objects when `release_assets.r2_state = 'available'`.
- GitHub fallback endpoints redirect only to approved immutable GitHub tag asset URLs after token and D1 state checks.
- KV is used only for origin/key-version/revision-keyed manifest render cache: `manifest:{origin}:{downloadKeyVersion}:{appId}:{platform}:{channel}:{revision}`.
- Durable Object handles coarse public rate limiting. KV is not used as a rate-limit counter.
- CI registration creates `candidate` releases only. It requires a formal release intent and fixed Android signing.
- Direct Worker admin mutation routes are disabled. Admin mutations are exposed through the Access-protected Pages Functions facade.
- The optional public Pages facade exposes only `/healthz` and `/api/public/*` for client networks where `workers.dev` is unreliable.

## Local Commands

Run from `cloudflare/update-service/worker`:

```bash
npm install
npm run cf-typegen
npm run check
npm test
```

These are non-build validation commands. Do not run production deploys until Cloudflare account, Access, D1, KV, R2, DO, and secret values are confirmed.

## Staging Bootstrap

Use the staging guide when you are ready to create real Cloudflare staging resources:

```text
cloudflare/update-service/docs/STAGING-SETUP.md
```

The bootstrap scripts are:

```text
cloudflare/update-service/scripts/bootstrap-staging.ps1
cloudflare/update-service/scripts/bootstrap-staging.mjs
```

They are staging-only and require an explicit `-Yes` / `--yes` flag before creating Cloudflare resources or deploying the Worker.

## GitHub Release Candidate Registration

Formal GitHub Release jobs register Android Cloudflare `candidate` releases after release assets are uploaded. This runs for normal pushes to `main` / `master` when `pubspec.yaml` contains a new version, for `v*` tag builds, and for `workflow_dispatch publish_release=true`.

The GitHub repository must define:

- `TRACE_UPDATE_SERVICE_URL`
- `TRACE_PUBLIC_UPDATE_SERVICE_URL`
- `TRACE_DEPLOY_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`
- Fixed Android release signing secrets

Use the local config wrapper instead of adding these by hand:

```powershell
Copy-Item `
  .\cloudflare\update-service\github-actions-secrets.staging.example.json `
  .\cloudflare\update-service\.github-actions-secrets.staging.local.json

.\cloudflare\update-service\scripts\configure-github-actions-secrets.ps1 -DryRun
.\cloudflare\update-service\scripts\configure-github-actions-secrets.ps1 -Yes
```

The `.local.json` file is ignored by git. Blank values keep existing GitHub settings when the name is already present; otherwise the script fails before writing.

The workflow uses:

```text
cloudflare/update-service/scripts/build-github-release-metadata.mjs
cloudflare/update-service/scripts/upload-r2-assets.mjs
cloudflare/update-service/scripts/register-release.mjs
```

Phase 2 candidate registration uploads APK/manifest/patch assets to R2, verifies them by read-back SHA-256, writes `r2Key` and `r2Verified: true` into the metadata, and registers the candidate in D1. It does not publish the candidate to `stable` or `beta`.

Pushes to `main` / `master` now derive the release tag from `pubspec.yaml`, create the GitHub Release with `--latest=false`, upload release assets to R2, and register a Cloudflare candidate automatically. If `TRACE_UPDATE_SERVICE_AUTO_DEPLOY=true` is set as a repository variable and the Cloudflare token has D1/Workers permissions, the workflow first applies pending staging D1 migrations and deploys the update Worker. If the derived tag already exists, the automatic candidate preparation is skipped; bump `pubspec.yaml` to prepare a new candidate.

### Automatic Candidate Preparation Contract

Future agents must preserve this release boundary:

- Code changes alone are not enough to prepare a new update candidate. Bump `pubspec.yaml` to a new version/build number before pushing release-intended code, for example `1.0.13+39`.
- `git push` prepares a candidate; it does not approve or publish it. Clients see the update only after an operator publishes the D1 candidate to `stable` or `beta` through the Access-protected admin UI or `publish-staging-release.ps1`.
- Existing tags are immutable for normal automation. If the derived release tag already exists, the workflow intentionally skips GitHub Release creation, R2 upload, metadata generation, and D1 registration. Do not bypass this by replacing assets under the same tag unless the user explicitly requests a staging-only replacement.
- Same-tag APK replacement can break incremental updates because installed clients may hold an APK hash that no longer has a matching patch. The correct fix is to bump `pubspec.yaml` and create a new tag.
- `TRACE_UPDATE_SERVICE_URL` must stay pointed at the Worker because CI registration posts to `/api/ci/releases`. `TRACE_PUBLIC_UPDATE_SERVICE_URL` is the Pages origin compiled into the Android app for `/api/public/latest`.
- `TRACE_UPDATE_SERVICE_AUTO_DEPLOY=true` is optional. Without it, CI still uploads R2 assets and registers candidates when the Cloudflare token has R2/CI registration prerequisites; Worker deploy and D1 migrations must be handled separately when release-service code changes require them.

Minimum verification after a push-intended release:

```powershell
gh run list --repo Eitan-S-23/Trace --workflow build.yml --limit 3

Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npx wrangler d1 execute trace-update-staging --env staging --remote --command "SELECT id, release_tag, version_code, state, run_id FROM releases ORDER BY created_at DESC LIMIT 3;"
npx wrangler d1 execute trace-update-staging --env staging --remote --command "SELECT asset_type, file_name, size_bytes, r2_state FROM release_assets WHERE release_id='<release-id>' ORDER BY asset_type, file_name;"
Set-Location D:\github\my\bluetooth_flutter_Trace
```

Android release metadata uses standard VCDIFF (`.vcdiff`) patches only for source versions that already contain the patched VCDIFF client. `1.0.14` / versionCode `40` and older clients contain the upstream Dart `vcdiff_decoder` address-cache bug (`Near cache slot ... is uninitialized`) and must use one full APK transition. Keep `TRACE_VCDIFF_MIN_SOURCE_VERSION_CODE` at `41` or newer unless a new compatibility audit proves otherwise.

VCDIFF patches generated by xdelta3 must be stripped of the top-level `VCD_APPHEADER` application header before upload. The client decoder rejects unsupported header features, and `create_vcdiff_patch.py` owns this compatibility normalization and must keep asserting that generated patches do not contain `VCD_APPHEADER`.

Detailed VCDIFF incident notes, version boundaries, and validation commands live in:

```text
cloudflare/update-service/docs/VCDIFF-COMPATIBILITY.md
```

`TRACE_UPDATE_SERVICE_URL` remains the Worker base URL used by CI registration (`/api/ci/releases`). `TRACE_PUBLIC_UPDATE_SERVICE_URL` is the non-secret client base URL compiled into APKs for `/api/public/latest`; in staging it should be `https://trace-update-public-staging.pages.dev`.

`upload-r2-assets.mjs` and `register-release.mjs` include bounded retries for transient network failures. Operators can tune slow staging networks with:

```text
TRACE_R2_UPLOAD_RETRIES=3
TRACE_R2_OPERATION_TIMEOUT_MS=600000
TRACE_REGISTER_RETRIES=5
TRACE_REGISTER_TIMEOUT_MS=60000
```

Existing Phase 1 releases can be backfilled into R2 without rebuilding local APKs:

```powershell
.\cloudflare\update-service\scripts\backfill-r2-release.ps1 -ReleaseTag v1.0.5 -Yes
```

The backfill script downloads existing immutable GitHub Release assets, uploads them to R2, read-back verifies SHA-256, and calls the CI registration endpoint with `r2Backfill: true`. The Worker only updates an existing release when the release tag, commit SHA, asset IDs, sizes, and SHA-256 values match D1.

For staging-only end-to-end release testing, use the one-command wrapper:

```powershell
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.6 -Channels stable,beta -Yes
```

It wraps R2 backfill, D1 candidate registration, channel CAS publish, latest manifest verification, signed patch download verification, and GitHub fallback immutability checks. It does not run local build or packaging commands. The wrapper is intentionally staging-only and refuses non-staging D1 targets by default.

Staging `v1.0.5` has been backfilled and verified: all seven Android update assets are in `trace-update-staging-releases`, D1 stores `r2_state = available`, primary patch download returns `X-Trace-Asset-Source: r2`, and fallback redirects remain tag-specific GitHub Release URLs under `/releases/download/v1.0.5/...`.

Staging `v1.0.7` is published to `stable` and `beta` for current phone testing from `1.0.5 (31)`: the Linux GitHub Actions release run uploaded the APK, manifest, and seven Android patch assets to R2, read-back verified them, registered the candidate in D1, and the staging publish wrapper verified the `31 -> 33` primary patch download from R2. The matching fallback remains Worker-gated and redirects only to the immutable tag-specific GitHub Release URL under `/releases/download/v1.0.7/...`.

Staging now also has a standalone public Pages endpoint at `https://trace-update-public-staging.pages.dev`. It uses the same D1/KV/R2 state as the Worker, but signs and serves public download URLs from the Pages origin so Android clients no longer need to reach `workers.dev`.

Do not rebuild or re-upload assets for an existing release tag after clients may have installed it. If a same-tag APK was overwritten before this guard existed, old clients with the replaced APK hash may not have a matching patch and should use the full APK once. Future releases must bump `pubspec.yaml` and use a new tag.

Staging `v1.0.9` is the first release built after the public Pages split. GitHub Actions run `28383587466` built `1.0.9+35` with `TRACE_PUBLIC_UPDATE_SERVICE_URL=https://trace-update-public-staging.pages.dev`, uploaded assets to R2, registered the Cloudflare candidate, and the staging publish wrapper published it to Android `stable` and `beta`. The public Pages latest endpoint returns `v1.0.9`, and the `34 -> 35` primary patch download returns `X-Trace-Asset-Source: r2`.

Until a real `TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64` signing secret and matching client public key are configured, CI emits a staging-only placeholder `payloadSignature`. Do not publish those candidates to clients; the placeholder is intended to fail closed if accidentally exposed.

Generate payload signing keys with:

```text
cloudflare/update-service/scripts/generate-payload-signing-key.mjs
```

## Admin Facade

The Phase 1 admin facade lives in:

```text
cloudflare/update-service/admin
```

It exposes Access-protected Pages Functions under `/api/admin/*` for listing releases/channels, editing release notes, publishing to `beta`/`stable`, and disabling unpublished releases.

Direct Worker `/api/admin/*` remains disabled. Do not deploy the admin Pages project until a Cloudflare Access application is configured with issuer, audience, and email role variables.

## Required Secrets

Set real values with `wrangler secret put` per environment before any remote deployment:

- `DEPLOY_TOKEN_SHA256`
- `DOWNLOAD_HMAC_KEY_CURRENT`
- `DOWNLOAD_HMAC_KEY_PREVIOUS` during rotation only

The committed Wrangler config intentionally contains only non-secret settings and placeholder binding IDs.

## Phase 3 Boundary

The current admin UI is a lightweight static operator surface. The fuller React console, R2 retention cleanup UI, backup controls, manifest preview polish, and lightweight statistics remain Phase 3+ work.
