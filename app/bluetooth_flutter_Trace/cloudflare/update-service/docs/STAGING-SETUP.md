# Cloudflare Staging Setup

This guide turns the Phase 1 Cloudflare update-service scaffold into a real staging deployment. It intentionally does not create or deploy production resources.

## What The Script Does

`scripts/bootstrap-staging.mjs` automates the safe staging-only steps:

- Creates or reuses the D1 database `trace-update-staging`.
- Creates or reuses the KV namespace `trace-update-staging-manifest-cache`.
- Creates or reuses the R2 bucket `trace-update-staging-releases`.
- Writes the real staging D1/KV/R2 resource IDs into `worker/wrangler.jsonc`.
- Applies D1 migrations to staging.
- Deploys the staging Worker.
- Writes Worker secrets:
  - `DEPLOY_TOKEN_SHA256`
  - `DOWNLOAD_HMAC_KEY_CURRENT`
- Calls `/healthz` and `/api/public/latest` as smoke tests.
- Prints the GitHub Secrets needed later for CI candidate registration.

The script refuses `prod`. Production must be a separate, explicit step after staging is verified.

## What Still Needs Human Confirmation

These cannot be safely automated without account-specific decisions:

- Creating the Cloudflare API token in your account.
- Deciding who can access the future Pages admin console.
- Creating the Cloudflare Access application for the future admin UI.
- Enabling the client app to use the staging Worker URL in a GitHub Actions build.
- Promoting any release to stable or production.

Direct Worker admin mutations remain disabled by design. `/api/admin/*` should return 503 until the Access-protected Pages Functions facade is implemented.

## Prerequisites

- Node.js 24 or compatible modern Node.js with built-in `fetch`.
- Cloudflare account access.
- A Cloudflare API token with account-level permissions for:
  - Workers Scripts: Edit
  - D1: Edit
  - Workers KV Storage: Edit
  - R2: Edit
- The repo checked out locally.
- No local Flutter, Gradle, Xcode, Dart compile, or package build commands are needed.

Install Worker dependencies first:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npm ci
npm run check
Set-Location D:\github\my\bluetooth_flutter_Trace
```

`npm test` is expected to fail on this Windows host if local workerd still crashes with `0xc0000005`. The Linux GitHub Actions invariant test is the authoritative runtime check for now.

## Step 1: Create The Cloudflare API Token

In Cloudflare Dashboard:

1. Open `My Profile` -> `API Tokens`.
2. Create a custom token.
3. Add the account permissions listed in prerequisites.
4. Scope it to your account.
5. Copy the token once.

Do not commit the token. Set it only in your shell:

```powershell
$env:CLOUDFLARE_ACCOUNT_ID = "your-account-id"
$env:CLOUDFLARE_API_TOKEN = "your-api-token"
```

## Step 2: Preview The Bootstrap Plan

Run without `-Yes` first. It prints the plan and does nothing remotely:

```powershell
.\cloudflare\update-service\scripts\bootstrap-staging.ps1
```

Optional dry-run form:

```powershell
.\cloudflare\update-service\scripts\bootstrap-staging.ps1 -DryRun
```

Expected plan:

- Environment is `staging`.
- D1 database is `trace-update-staging`.
- KV namespace is `trace-update-staging-manifest-cache`.
- R2 bucket is `trace-update-staging-releases`.
- Deploy target is `trace-update-service-staging`.

## Step 3: Run The Staging Bootstrap

Run:

```powershell
.\cloudflare\update-service\scripts\bootstrap-staging.ps1 -Yes
```

Optional: write a local JSON summary to an ignored path:

```powershell
.\cloudflare\update-service\scripts\bootstrap-staging.ps1 -Yes -Output cloudflare/update-service/.bootstrap/staging-summary.json
```

The output includes:

- Worker URL.
- D1 database ID.
- KV namespace ID.
- R2 bucket name.
- `TRACE_UPDATE_SERVICE_URL` for future GitHub Secrets.
- `TRACE_DEPLOY_TOKEN` for future GitHub Secrets.

Do not commit `TRACE_DEPLOY_TOKEN`. The Worker stores only `DEPLOY_TOKEN_SHA256`.

## Step 4: Confirm The Local Config Diff

The script updates only non-secret resource IDs in:

```text
cloudflare/update-service/worker/wrangler.jsonc
```

Check:

```powershell
git diff -- cloudflare/update-service/worker/wrangler.jsonc
```

Expected staging changes:

- `env.staging.d1_databases[0].database_id` is no longer the placeholder UUID.
- `env.staging.kv_namespaces[0].id` is no longer the placeholder ID.
- `env.staging.r2_buckets[0].bucket_name` is `trace-update-staging-releases` or your override.

Do not copy staging IDs into `prod`.

## Step 5: Manual Smoke Checks

If the script prints a Worker URL, test it:

```powershell
$worker = "https://your-staging-worker.workers.dev"
Invoke-RestMethod "$worker/healthz"
Invoke-RestMethod "$worker/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature"
```

Expected:

- `/healthz` returns `ok: true`, service name, and `environment: staging`.
- `/api/public/latest` returns `errorCode: NO_UPDATE` until a candidate is registered and manually published.
- If the bootstrap script warns that Node smoke checks were inconclusive, but these PowerShell checks succeed, the staging deployment itself is healthy. This can happen when local Node `fetch` is affected by proxy or network settings.

Confirm migrations:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npx wrangler d1 migrations list trace-update-staging --env staging --remote
Set-Location D:\github\my\bluetooth_flutter_Trace
```

Confirm secrets exist without revealing values:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npx wrangler secret list --env staging
Set-Location D:\github\my\bluetooth_flutter_Trace
```

Expected secret names:

- `DEPLOY_TOKEN_SHA256`
- `DOWNLOAD_HMAC_KEY_CURRENT`

## Step 5b: Deploy Public Pages Endpoint

Use this only when client devices can reach `pages.dev` more reliably than `workers.dev`. The public Pages project exposes only:

```text
/healthz
/api/public/latest
/api/public/download
/api/public/github-fallback
```

It does not expose `/api/admin/*` or `/api/ci/*`; CI registration must continue using the Worker URL.

Set a download HMAC key for the Pages project. It may be independent from the Worker key because Pages signs and verifies its own public download URLs:

```powershell
$bytes = [byte[]]::new(48)
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$env:TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_CURRENT = [Convert]::ToBase64String($bytes)
.\cloudflare\update-service\scripts\deploy-public-staging.ps1 -Yes
Remove-Item Env:TRACE_PUBLIC_DOWNLOAD_HMAC_KEY_CURRENT
```

If the Pages secret already exists and you do not want to rotate it, run with `-SkipSecrets`.

Smoke check:

```powershell
$public = "https://trace-update-public-staging.pages.dev"
Invoke-RestMethod "$public/healthz"
Invoke-RestMethod "$public/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature"
```

Set this GitHub Actions variable for future APK builds:

```powershell
gh variable set TRACE_PUBLIC_UPDATE_SERVICE_URL --repo Eitan-S-23/Trace --body https://trace-update-public-staging.pages.dev
```

## Step 6: GitHub Secrets For CI Registration

After bootstrap, configure GitHub Actions secrets and variables with the local config script. First copy the example config:

```powershell
Copy-Item `
  .\cloudflare\update-service\github-actions-secrets.staging.example.json `
  .\cloudflare\update-service\.github-actions-secrets.staging.local.json
```

Edit `.github-actions-secrets.staging.local.json` and fill the blank values. The local file is ignored by git. Blank values mean "keep the value already configured in GitHub"; if GitHub does not already have that name, the script fails before writing.

The script can read these values from `.bootstrap/staging-summary.json` when `useBootstrapSummary` is `true`, so they normally do not need to be pasted manually:

```text
TRACE_UPDATE_SERVICE_URL=<printed staging Worker URL>
TRACE_DEPLOY_TOKEN=<printed raw deploy token>
```

`TRACE_UPDATE_SERVICE_URL` must remain the Worker base URL because `register-release.mjs` posts to `/api/ci/releases`. The non-secret `TRACE_PUBLIC_UPDATE_SERVICE_URL` variable is the Pages base URL compiled into APKs for `/api/public/latest`.

The values that usually must be filled manually are:

```text
CLOUDFLARE_ACCOUNT_ID=<Cloudflare account id>
CLOUDFLARE_API_TOKEN=<token with R2 object write/read permission for the staging bucket>
TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64=<from Step 7>
TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64=<from Step 7>
```

Run a no-write plan:

```powershell
.\cloudflare\update-service\scripts\configure-github-actions-secrets.ps1 -DryRun
```

Write the configured values to GitHub:

```powershell
.\cloudflare\update-service\scripts\configure-github-actions-secrets.ps1 -Yes
```

The script uses `gh secret set` and `gh variable set` for repository `Eitan-S-23/Trace`. Secret values are passed through stdin and are not printed. The script verifies required names exist afterward, but GitHub does not allow reading secret values back.

Required repository variable:

```text
TRACE_R2_BUCKET=trace-update-staging-releases
```

These settings are not enough to publish production updates. They allow the formal GitHub Release job to upload staging R2 assets, call staging `/api/ci/releases`, and create a D1 `candidate`.

## Step 7: Configure Payload Signing For Client-Visible Updates

Generate an Ed25519 signing key pair:

```powershell
node .\cloudflare\update-service\scripts\generate-payload-signing-key.mjs
```

The script prints:

```text
TRACE_UPDATE_PAYLOAD_KEY_VERSION=<key-version>
TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64=<pkcs8-der-private-key>
TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64=<raw-32-byte-public-key>
```

Add the private key and public key as GitHub repository secrets:

```text
TRACE_UPDATE_PAYLOAD_ED25519_PRIVATE_KEY_BASE64
TRACE_UPDATE_PAYLOAD_ED25519_PUBLIC_KEY_BASE64
```

Add the key version as a GitHub repository variable:

```text
TRACE_UPDATE_PAYLOAD_KEY_VERSION
```

Do not publish Cloudflare candidates to phones until these are configured. Without the signing secrets, CI uses a staging-only placeholder `payloadSignature` that is intended to fail closed in clients.

## Step 8: Client Activation Boundary

The Android client only uses Cloudflare primary when the app build includes:

```text
TRACE_CLOUDFLARE_UPDATE_MANIFEST_URL=https://trace-update-public-staging.pages.dev/api/public/latest
```

Do not run local Flutter builds. Wire this into GitHub Actions through `TRACE_PUBLIC_UPDATE_SERVICE_URL` only after staging Worker/Pages checks pass and you intentionally want a Cloudflare-capable artifact.

Before enabling this for normal users:

- Keep GitHub latest pointing only to a manually approved stable release.
- Verify old clients are still safe.
- Verify the Cloudflare manifest returns v1-compatible output for clients without `schemaVersion` and `capabilities`.

## Step 9: Verify Candidate Registration

After the GitHub Secrets are configured and the CI workflow changes are pushed, trigger a formal test release from GitHub Actions:

```text
workflow_dispatch:
  publish_release: true
  release_tag: v<next-version>
```

Expected result:

- GitHub Actions creates the tag-specific GitHub Release. If the release already exists, the job fails by default; only use `replace_existing_release=true` for an intentional staging-only replacement.
- The release job uploads `ble-monitor-android.apk`, `ble-monitor-update.json`, and any `.tpatch` files.
- `build-github-release-metadata.mjs` creates local CI metadata from those assets.
- `upload-r2-assets.mjs` uploads those assets to R2, downloads them back, verifies SHA-256, and writes `r2Key` plus `r2Verified: true` into the metadata.
- `register-release.mjs` calls staging `/api/ci/releases`.
- D1 stores the release as `candidate` and stores each asset with `r2_state = 'available'`.

The public latest endpoint should still return `NO_UPDATE` until an Access-protected admin facade publishes that candidate to `stable` or `beta`:

```powershell
$worker = "https://your-staging-worker.workers.dev"
Invoke-RestMethod "$worker/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature"
```

Staging registration allows a placeholder `payloadSignature` when no real payload signing key is configured. Do not publish those candidates to clients. Configure real Ed25519 payload signing before using Cloudflare latest for production updates.

## Step 10: Configure Access-Protected Admin Facade

The Phase 1 admin facade lives in:

```text
cloudflare/update-service/admin
```

Before deploying it, create a Cloudflare Access application for the Pages project URL and collect:

```text
ACCESS_JWT_ISSUER=https://<team-name>.cloudflareaccess.com
ACCESS_JWT_AUD=<Access application AUD tag>
```

Configure Pages secrets for the admin project. Do not also define these names in `admin/wrangler.jsonc` `vars`; Pages rejects duplicate binding names.

```text
ACCESS_JWT_ISSUER
ACCESS_JWT_AUD
ADMIN_VIEWER_EMAILS
ADMIN_PUBLISHER_EMAILS
ADMIN_OWNER_EMAILS
ADMIN_ALLOWED_ORIGINS
```

At least your email must be in `ADMIN_OWNER_EMAILS` for stable publish, rollback, and disable operations. The facade fails closed while `ACCESS_JWT_ISSUER` or `ACCESS_JWT_AUD` is empty.

Set the values in the current PowerShell session. Use the email address that Cloudflare Access will place in the `email` claim after login:

```powershell
$env:ACCESS_JWT_ISSUER = "https://<team-name>.cloudflareaccess.com"
$env:ACCESS_JWT_AUD = "<Access application AUD tag>"
$env:ADMIN_OWNER_EMAILS = "you@example.com"
$env:ADMIN_PUBLISHER_EMAILS = "you@example.com"
$env:ADMIN_VIEWER_EMAILS = "you@example.com"
```

Run local non-build checks:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\admin
npm ci
npm run check
Set-Location D:\github\my\bluetooth_flutter_Trace
```

Deploy the staging Pages project only after Access is configured. The script creates `trace-update-admin-staging` if it does not exist, writes the Access values as Pages secrets, and deploys the current admin facade:

```powershell
.\cloudflare\update-service\scripts\deploy-admin-staging.ps1 -Yes
```

If `pages project list` fails while `CLOUDFLARE_API_TOKEN` is set, Wrangler is using that token instead of the browser login. Either give that token Cloudflare Pages permissions or unset it for this PowerShell session:

```powershell
Remove-Item Env:CLOUDFLARE_API_TOKEN -ErrorAction SilentlyContinue
```

If you want to run the Wrangler commands manually instead, create the project before deploying:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\admin
npx wrangler pages project create trace-update-admin-staging --production-branch main --compatibility-date 2026-06-28 --compatibility-flag nodejs_compat
npx wrangler pages deploy .\public --project-name trace-update-admin-staging --branch main --commit-dirty=true
Set-Location D:\github\my\bluetooth_flutter_Trace
```

If `pages project create` says the project already exists, skip that command and run only `pages deploy`.

Then protect the resulting Pages URL with the Access application before using mutation endpoints.

## Step 11: Publish A Candidate To Beta

Open the protected Pages URL in a browser first so Cloudflare Access sets the session. Call:

```text
GET /api/admin/session
GET /api/admin/channels?appId=trace&platform=android
GET /api/admin/releases?appId=trace&platform=android
```

Use the `csrfToken` from `/api/admin/session`, the current `beta` channel `revision`, and the target `releaseId`:

```text
POST /api/admin/channels/beta/publish
{
  "appId": "trace",
  "platform": "android",
  "releaseId": "<candidate release id>",
  "expectedRevision": <current beta revision>,
  "rollback": false
}
```

Expected result:

- The API returns `{ "ok": true, "revision": <new revision> }`.
- D1 `channels.beta.current_release_id` points to the candidate.
- `/api/public/latest?...channel=beta...` returns an update manifest for clients below the target `versionCode`.

Verified staging result on 2026-06-29:

- The Pages admin UI published `rel_trace_android_v1_0_4` / `v1.0.4` to Android `beta`.
- D1 `beta` revision became `1` and points to `rel_trace_android_v1_0_4`; `stable` revision stayed `0` with no release.
- D1 recorded the publish operation in `channel_history` and `audit_logs`.
- The `beta` latest endpoint returned `updateAvailable: true`, versionCode `30`, and three patch entries.
- The `stable` latest endpoint returned `NO_UPDATE`.
- Non-following GET checks against fallback URLs returned `302` redirects to tag-specific GitHub Release URLs under `/releases/download/v1.0.4/...`. HEAD checks return `401` because signed download tokens are GET-scoped.

Useful verification commands:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npx wrangler d1 execute trace-update-staging --env staging --remote --command "SELECT c.name, c.platform, c.revision, c.current_release_id, r.release_tag, r.version_code, r.state FROM channels c LEFT JOIN releases r ON r.id = c.current_release_id ORDER BY c.platform, c.name;"
npx wrangler d1 execute trace-update-staging --env staging --remote --command "SELECT channel_id, release_id, revision, action, actor_type, created_at FROM channel_history ORDER BY created_at DESC LIMIT 5;"
npx wrangler d1 execute trace-update-staging --env staging --remote --command "SELECT app_id, actor_type, action, target_type, target_id, created_at FROM audit_logs ORDER BY created_at DESC LIMIT 5;"

$worker = "https://trace-update-service-staging.tangjichentudou.workers.dev"
curl.exe -sS --max-time 30 "$worker/api/public/latest?appId=trace&platform=android&channel=beta&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature"
curl.exe -sS --max-time 30 "$worker/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature"
```

To validate fallback redirects without downloading the APK or patch body:

```powershell
$manifest = (curl.exe -sS --max-time 30 "$worker/api/public/latest?appId=trace&platform=android&channel=beta&versionCode=1&schemaVersion=2&capabilities=patch,full,payloadSignature") | ConvertFrom-Json
$firstPatch = $manifest.patches | Select-Object -First 1
curl.exe -sS -o NUL -w "status=%{http_code} redirect=%{redirect_url}`n" --max-time 30 $firstPatch.fallbackUrl
curl.exe -sS -o NUL -w "status=%{http_code} redirect=%{redirect_url}`n" --max-time 30 $manifest.fullFallbackUrl
```

Do not publish to `stable` until beta verification succeeds on a real phone.

## Step 12: Verify R2 Primary Distribution

Deploy the updated staging Worker before validating R2 streaming:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npm run check
npx wrangler deploy --env staging
Set-Location D:\github\my\bluetooth_flutter_Trace
```

For new formal releases, GitHub Actions uploads R2 assets before candidate registration. Existing Phase 1 candidates can be backfilled without rebuilding locally:

```powershell
$env:TRACE_UPDATE_SERVICE_URL = "https://trace-update-service-staging.tangjichentudou.workers.dev"
$env:TRACE_DEPLOY_TOKEN = "<raw staging deploy token>"
$env:CLOUDFLARE_ACCOUNT_ID = "<account id>"
$env:CLOUDFLARE_API_TOKEN = "<token with R2 object write/read permission>"
$env:TRACE_R2_UPLOAD_RETRIES = "3"
$env:TRACE_R2_OPERATION_TIMEOUT_MS = "600000"

.\cloudflare\update-service\scripts\backfill-r2-release.ps1 -ReleaseTag v1.0.5 -Yes
```

The backfill script downloads immutable GitHub Release assets with `gh release download`, validates the manifest/APK/patch SHA-256 values, uploads to R2, reads the objects back, and calls `/api/ci/releases` with `r2Backfill: true`. The Worker only updates D1 when the existing release tag, commit SHA, asset ID, size, and SHA-256 match.

For a full staging test release, use the one-command publish wrapper instead of manually chaining backfill, D1 publish, and verification:

```powershell
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.6 -Channels stable,beta -Yes
```

The wrapper is staging-only. It downloads and validates GitHub Release Android assets, uploads them to R2, read-back verifies them, registers the R2 backfill, publishes the selected D1 channels with CAS revision checks, and verifies the public latest endpoint plus a signed patch download. It does not run local Flutter, Gradle, Dart, Windows, or packaging builds.

Useful options:

```powershell
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.6 -Channels stable,beta -DryRun
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.6 -Channels stable -Yes -KeepAssets
.\cloudflare\update-service\scripts\publish-staging-release.ps1 -ReleaseTag v1.0.6 -Channels stable -Yes -SkipBackfill
```

By default the wrapper refuses to publish unless every active Android asset for the release has `r2_state = available`. `-AllowPartialR2` exists only for temporary staging diagnostics, for example when validating a single small patch while full APK upload is still being recovered. Do not use `-AllowPartialR2` for normal releases.

If the GitHub assets are already downloaded and verified, avoid re-downloading them:

```powershell
$dir = Join-Path $env:TEMP "trace-r2-backfill-debug"
.\cloudflare\update-service\scripts\backfill-r2-release.ps1 -ReleaseTag v1.0.5 -Yes -SkipDownload -KeepAssets -AssetsDir $dir
```

`TRACE_R2_OPERATION_TIMEOUT_MS` is intentionally high in the example because 40-60 MB patch uploads can be slow through some Windows proxy setups. The script still fails into bounded retries instead of hanging forever.

Confirm D1 asset state:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npx wrangler d1 execute trace-update-staging --env staging --remote --command "SELECT release_id, asset_type, file_name, r2_state, r2_key FROM release_assets WHERE release_id='rel_trace_android_v1_0_5' ORDER BY asset_type, file_name;"
Set-Location D:\github\my\bluetooth_flutter_Trace
```

Expected result:

- All active assets for the release have `r2_state = available`.
- `r2_key` follows `trace/releases/{versionCode}-{releaseTag}/...`.

Confirm primary patch download is served by R2:

```powershell
$worker = "https://trace-update-service-staging.tangjichentudou.workers.dev"
$manifest = (curl.exe -sS --max-time 30 "$worker/api/public/latest?appId=trace&platform=android&channel=stable&versionCode=30&schemaVersion=2&capabilities=patch,full,payloadSignature") | ConvertFrom-Json
$firstPatch = $manifest.patches | Select-Object -First 1
curl.exe -sS -D - -o NUL --max-time 60 $firstPatch.downloadUrl
```

Expected response headers include:

```text
HTTP/1.1 200
X-Trace-Asset-Source: r2
Cache-Control: public, max-age=31536000, immutable
Content-Disposition: attachment; filename="..."
```

Confirm gated GitHub fallback still works and still does not use `/latest/download`:

```powershell
curl.exe -sS -o NUL -w "status=%{http_code} redirect=%{redirect_url}`n" --max-time 30 $firstPatch.fallbackUrl
```

Expected result:

- `status=302`
- `redirect` contains `/releases/download/v1.0.5/`
- `redirect` does not contain `/latest/download/`

Verified staging result on 2026-06-29:

- `v1.0.5` was backfilled from existing GitHub Release assets with no local app build.
- R2 read-back SHA-256 verification completed for the APK, manifest, and five patch files.
- D1 shows seven `rel_trace_android_v1_0_5` assets with `r2_state = available` and versioned keys under `trace/releases/31-v1.0.5/...`.
- `npx wrangler deploy --env staging` deployed the updated Worker.
- `deploy-admin-staging.ps1 -Yes -SkipSecrets` deployed the updated Pages admin facade.
- A signed primary patch download returned HTTP `200`, `X-Trace-Asset-Source: r2`, `Content-Length: 513666`, and immutable cache headers.
- The matching fallback URL returned HTTP `302` to `/releases/download/v1.0.5/...` and did not use `/latest/download`.

## Failure Handling

If resource creation fails:

- Verify `CLOUDFLARE_ACCOUNT_ID`.
- Verify token permissions.
- Re-run the script. It is idempotent and reuses resources with the same names.

If `wrangler deploy --env staging` fails:

- Run `npm ci` in `cloudflare/update-service/worker`.
- Run `npm run check`.
- Re-run bootstrap with `-SkipMigrations` if migrations already applied.

If smoke tests cannot infer the Worker URL:

```powershell
$env:TRACE_CF_STAGING_WORKER_URL = "https://your-staging-worker.workers.dev"
.\cloudflare\update-service\scripts\bootstrap-staging.ps1 -Yes -SkipDeploy -SkipMigrations -SkipSecrets
```

If the deploy token was lost:

```powershell
$env:TRACE_DEPLOY_TOKEN = "new-random-token"
.\cloudflare\update-service\scripts\bootstrap-staging.ps1 -Yes -SkipDeploy -SkipMigrations -SkipSmoke
```

Then update GitHub secret `TRACE_DEPLOY_TOKEN`.

If Node `fetch` in `register-release.mjs` cannot reach `workers.dev` through the local Windows/proxy stack, first verify that PowerShell or curl can reach the same Worker:

```powershell
curl.exe -sS --connect-timeout 30 --max-time 60 -D - -o NUL https://trace-update-service-staging.tangjichentudou.workers.dev/healthz
Invoke-WebRequest -Uri "https://trace-update-service-staging.tangjichentudou.workers.dev/healthz" -TimeoutSec 60
```

If those succeed and the R2 metadata file already contains verified `r2Key` values, retry only the registration with PowerShell. This reads the local ignored bootstrap summary but does not print the deploy token:

```powershell
$metadata = Join-Path $env:TEMP "trace-r2-backfill-debug\cloudflare-r2-backfill-metadata.json"
$summary = Get-Content -LiteralPath "cloudflare/update-service/.bootstrap/staging-summary.json" -Raw | ConvertFrom-Json
$serviceUrl = if ($summary.githubSecrets.TRACE_UPDATE_SERVICE_URL) { $summary.githubSecrets.TRACE_UPDATE_SERVICE_URL } else { $summary.workerUrl }
$headers = @{
  Authorization = "Bearer $($summary.githubSecrets.TRACE_DEPLOY_TOKEN)"
  "Content-Type" = "application/json"
}
Invoke-RestMethod -Uri "$serviceUrl/api/ci/releases" -Method Post -Headers $headers -Body (Get-Content -LiteralPath $metadata -Raw) -TimeoutSec 90
```

## Cleanup

Only clean up staging if you no longer need it. Use Cloudflare Dashboard, or run Wrangler/API commands manually after confirming names:

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\worker
npx wrangler delete --env staging
npx wrangler d1 delete trace-update-staging
npx wrangler kv namespace delete --namespace-id <staging-kv-id>
npx wrangler r2 bucket delete trace-update-staging-releases
Set-Location D:\github\my\bluetooth_flutter_Trace
```

Do not run cleanup commands against `prod`.

## Script Reference

PowerShell wrapper:

```powershell
.\cloudflare\update-service\scripts\bootstrap-staging.ps1 -Yes
```

Node script:

```powershell
node .\cloudflare\update-service\scripts\bootstrap-staging.mjs --yes
```

Useful options:

```text
--dry-run
--skip-deploy
--skip-secrets
--skip-migrations
--skip-smoke
--output <path>
```

Useful environment overrides:

```text
TRACE_DEPLOY_TOKEN
TRACE_DOWNLOAD_HMAC_KEY_CURRENT
TRACE_CF_STAGING_WORKER_URL
TRACE_CF_STAGING_D1_NAME
TRACE_CF_STAGING_KV_TITLE
TRACE_CF_STAGING_R2_BUCKET
```
