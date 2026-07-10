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

`stable` publish/rollback and disable require `owner`. `beta` publish/rollback and release note edits require `publisher` or `owner`. Read-only endpoints allow `viewer`.

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

```powershell
Set-Location D:\github\my\bluetooth_flutter_Trace\cloudflare\update-service\admin
npm ci
npm run check
```

These are non-build checks.
