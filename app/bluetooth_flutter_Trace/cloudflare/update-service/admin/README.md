# Trace Update Admin

Phase 1 provides an Access-protected Pages Functions admin facade with a lightweight static operator UI. The full React console remains deferred until the Worker+D1 control plane is verified end-to-end.

No direct admin mutation route is exposed on the standalone Worker. During the no-custom-domain phase, mutations go through this Pages Functions same-origin facade.

## Current API

The root page loads the current Access session, Android channels, and Android releases. It supports release note edits, beta/stable publish actions, disabling unpublished releases, and viewing R2-ready versus fallback-only asset counts through the API below.

- `GET /api/admin/session`
- `GET /api/admin/channels?appId=trace&platform=android`
- `GET /api/admin/releases?appId=trace&platform=android`
- `POST /api/admin/channels/:channel/publish`
- `POST /api/admin/releases/:releaseId/notes`
- `POST /api/admin/releases/:releaseId/disable`

For the Android API above, `stable` publish and disable require `owner`.
`beta` publish and release note edits require `publisher` or `owner`.
Read-only endpoints allow `viewer`.

## Firmware Controls

The firmware tab consumes the multi-asset DTOs defined by
`OTA-XC-HTTP-ADMIN` in `docs/ota-cross-system-contracts.md`. Its fixed routes are:

- `GET /api/admin/firmware/releases?appId=trace&deviceModel=e-track-at32f435`
- `GET /api/admin/firmware/channels?appId=trace&deviceModel=e-track-at32f435`
- `POST /api/admin/firmware/channels/{stable|beta}/{publish|retract|stop-latest|resume-latest|stop-downloads|resume-downloads}`
- `POST /api/admin/firmware/releases/{releaseId}/{disable|recovery-download}`

All channel mutations require a nonblank `reason` and an `expectedRevision`.
Stable requires owner; beta requires publisher or owner. Publish advances the
version. Retract selects a ready release without changing its identity, state,
hashes or assets. It only affects devices that have not upgraded: upgraded
devices do not downgrade and need a fix with a higher `versionCode`.

Latest and download switches are independent. Download stop blocks subsequent
uses of previously signed public URLs, not just new issuance. Token v2 does not
carry channel identity, so a stopped channel also blocks public downloads of
the same release referenced by another channel. Resume cannot bypass ready/R2
checks or clear the other stop flag. An unchanged switch/message with a current
revision is a no-op, with no new revision or audit.

Release disable is owner-only and rejects any channel reference. Recovery is
owner-only, never an automatic OTA path. Both actions use the existing canonical
UUIDv4 `Idempotency-Key`, actor scope, RFC 8785 fingerprint and permanent
tombstones. No URL, signature or raw key is copied into ordinary audit/logs.

The UI reads state again after success, CAS conflict or an unknown network
outcome. It never automatically repeats a channel write. A failed read locks
further writes until reconciliation succeeds. An unknown release result retains
its exact key/body in page memory; the operator must re-read and explicitly
confirm replay as the same actor. An expired result requires a newly confirmed
action, not an automatic new key. A page reload loses that in-memory request;
read state and reconcile the original operation before starting another action.

The migration and security prerequisites from P4-2 still apply. Local tests or
mock screenshots do not establish a real Access owner session, deployment, or
the P42-EXT-03B Admin exercise. Those require separately authorized real evidence.

Every mutation requires:

- A valid Cloudflare Access JWT in `CF-Access-Jwt-Assertion`.
- The Access JWT issuer, audience, expiry, signature, and email allowlist to verify.
- Same-origin `Origin`.
- `X-CSRF-Token` matching the `trace_admin_csrf` cookie from `GET /api/admin/session`.

## Required Configuration

Configure these Pages secrets before deployment. Prefer the staging deployment script below, which writes them as Pages secrets so account-specific Access values are not committed. Do not also define these names in `wrangler.jsonc` `vars`; Pages rejects duplicate binding names.

```text
ACCESS_JWT_ISSUER=https://<team-name>.cloudflareaccess.com
ACCESS_JWT_AUD=<Access application AUD tag>
ADMIN_VIEWER_EMAILS=<comma-separated emails>
ADMIN_PUBLISHER_EMAILS=<comma-separated emails>
ADMIN_OWNER_EMAILS=<comma-separated emails>
ADMIN_ALLOWED_ORIGINS=<optional comma-separated extra origins>
```

The committed `wrangler.jsonc` intentionally does not define these Access values. The facade fails closed until the matching Pages secrets are configured.

## Staging Deploy

Set the Access values in the current PowerShell session, then run the script from the repository root:

```powershell
$env:ACCESS_JWT_ISSUER = "https://<team-name>.cloudflareaccess.com"
$env:ACCESS_JWT_AUD = "<Access application AUD tag>"
$env:ADMIN_OWNER_EMAILS = "you@example.com"
$env:ADMIN_PUBLISHER_EMAILS = "you@example.com"
$env:ADMIN_VIEWER_EMAILS = "you@example.com"
.\cloudflare\update-service\scripts\deploy-admin-staging.ps1 -Yes
```

The script creates `trace-update-admin-staging` if it does not exist, writes the Access values as Pages secrets, runs the admin typecheck, and deploys `admin/public` with the Pages Functions bundle.

If `pages project list` fails while `CLOUDFLARE_API_TOKEN` is set, Wrangler is using that token instead of the browser login. Either give that token Cloudflare Pages permissions or unset it for this PowerShell session:

```powershell
Remove-Item Env:CLOUDFLARE_API_TOKEN -ErrorAction SilentlyContinue
```

## Local Checks

Run from this admin directory with caches and temporary directories contained
in the active worktree (Windows: use `cmd.exe`, not uncontained PowerShell):

```text
npm ci
npm run check
npm exec -- playwright install chromium --only-shell
npm run test:ui
```

Set `PLAYWRIGHT_BROWSERS_PATH` to a worktree-local browser directory, `PW_OUTPUT_DIR`
to a fresh worktree-local evidence directory, and npm/TEMP/TMP/TMPDIR/home/cache
overrides before running locally. Windows dependency installation must use
`npm ci --ignore-scripts` on hosts where workerd is unavailable. Do not retry
native Windows workerd there: run the worker host suite and the existing Linux
`cloudflare-update-service.yml` workflow instead.

The browser suite serves the real HTML behind intercepted synthetic API routes.
Every screenshot says `MOCK UI / NO REAL ACCESS OR D1`; external requests are
blocked. It covers bilingual confirmation/cancel/conflict, role controls,
independent switches, unknown results, same-key recovery replay, actor changes,
failed reads and mobile layout. CI preserves screenshots, raw UI output and the
checkout SHA for 14 days. These are development checks, not independent acceptance.
