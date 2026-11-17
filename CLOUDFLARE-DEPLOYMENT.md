# Cloudflare Deployment Memory

Read this file before deploying the E-Track backend or asking the owner for
Cloudflare credentials. It lives at the project root deliberately. Read the
primary checkout's copy, not only an old task worktree's copy.

## Current State: Pages Not Yet Deployed

Updated 2026-11-17. APP-ADMIN-UX-01's App packages, migration 0014 and Worker
deployment succeeded. Its new Admin and Public Pages have **not** been deployed.
The procedure below is the supported route, not a claim of a successful new
Pages deployment. Do not mark this incident complete until the readbacks pass.

- E-Track Pages run [43978919787](https://github.com/Eitan-S-23/E-Track/actions/runs/43978919787)
  returned HTTP 403 / code 10000 at the exact Admin project GET.
- Original Trace Pages run [43996459438](https://github.com/Eitan-S-23/Trace/actions/runs/43996459438)
  independently used Trace's existing repository secrets and returned the same
  denial. Dependency installation and both deploy steps were skipped.
- The last successful local Pages deployment used Wrangler OAuth, not either
  repository's CI token. Its named retained configurations now return HTTP 401;
  the latest retained grant expires at `2026-11-14T19:21:28.012Z`. Prior normal
  refresh failures remain preserved. An expired copy is not missing owner consent.
- The owner's task authorization already exists. The remaining prerequisite is
  identifying/restoring an existing Pages-capable protected input, not another
  general authorization, a new APK, or automatically creating a new token.

Full dated observations and original receipts:
[APP-ADMIN-UX-01](docs/ota-exec-notes/APP-ADMIN-UX-01.md#existing-local-and-github-routes-2026-11-17).

## Exact Targets

Service directory, relative to the primary project root:
`app/bluetooth_flutter_Trace/cloudflare/update-service`.

| Component | Existing target |
| --- | --- |
| Cloudflare account | `af6dd848e6a21f1cd26d44b1b656af7b` |
| Worker | `trace-update-service-staging` |
| D1 | `trace-update-staging`, ID `0133ad9e-d4a2-4fef-a659-4f2bf3d3a645` |
| Admin Pages | `trace-update-admin-staging`, production branch `main` |
| Public Pages | `trace-update-public-staging`, production branch `main` |
| Admin URL | `https://trace-update-admin-staging.pages.dev` |
| Public URL | `https://trace-update-public-staging.pages.dev` |
| Worker URL | `https://trace-update-service-staging.tangjichentudou.workers.dev` |

The `staging` names are the existing App's configured targets. Do not create
replacement projects, change URLs or substitute production firmware resources.
App package delivery, Worker deployment, Pages deployment, channel publication
and device installation are separate operations.

## Existing Credentials First

The owner has already authorized any E-Track agent to reuse `e-track-ci`
(historical alias `e-track-p41-ci`) for authorized project work. Changing agents
does not require another token-use approval. Existence, operation-specific
capability and task authorization are separate facts.

| Protected input | Locator and use |
| --- | --- |
| E-Track CI token | `.cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt`; working Worker/D1 route, not currently a verified Pages route |
| Project management input | `app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json`, field `secrets.CLOUDFLARE_API_TOKEN` |
| Original standalone Trace input | `D:/github/my/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json`; read-only, not `D:/github/my/Trace` |
| GitHub repository secrets | `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN` in `Eitan-S-23/E-Track` and `Eitan-S-23/Trace`; use inside the owning repository's Actions runner, never extract their values |
| Existing Wrangler user input | `C:/Users/SU/AppData/Roaming/xdg.config/.wrangler/config/default.toml`; read-only source, normal refresh only in a checked project-private copy |
| Last successful local Pages input | `.cache/p35-integration-20261028/source/.cache/admin-copy-version-20261115-01/ui-rollout/private/xdg-config/.wrangler/config/default.toml`; historical input, currently expired |

The provisioning `token.txt` beside `p41-ci-token.txt` is **not** the CI token.
Never export it to GitHub or use it as an interchangeable CI fallback. Do not
print keys, protected JSON/TOML, cookies or credential-bearing request bodies.
Do not scan arbitrary private caches, create empty replacement credential files,
or modify original credentials/ACLs to work around a different Windows identity.
On this host a SYSTEM process is not SU; use the existing exact-slot owner-read
route instead of treating SYSTEM's empty keyring/environment as user logout.

Wrangler prefers its legacy `~/.wrangler` directory when present, otherwise its
XDG configuration. Supported API-token/global-key environment inputs can override
OAuth. Inspect named source metadata and actual configuration resolution before
concluding that the user must log in again. Keep controllable config, logs,
caches and temporary files inside the active project; never refresh the original
user-profile file or a frozen task's file in place.

See [credential registry](docs/agent-collaboration/credential-registry.md) and
[credential rules](docs/agent-collaboration-contract.md#reuse-before-requesting-credentials)
for dated capability evidence and confidentiality/authorization boundaries.

## Normal Deployment

1. Run `python -B Tools/workflow/main_board.py --repo-root .` from the primary
   checkout. Pin the reviewed source commit and affected components. Reuse
   matching successful checks/packages; a Pages-only change needs no APK/EXE
   rebuild, new version, re-signing, candidate registration or delta generation.
2. Check the exact existing account and Pages projects with the selected
   credential. Preserve production/preview configuration privately before any
   deploy. Verify original D1/R2 bindings, variables, Access settings/roles and
   delta workflow references. A nonempty secret slot or `whoami` is insufficient.
3. Prefer the tracked manual workflow
   [.github/workflows/deploy-cloudflare-admin.yml](.github/workflows/deploy-cloudflare-admin.yml).
   It pins `source_sha`, checks existing targets, preserves Access secrets and
   optionally deploys Public Pages with `include_public=true`.
4. If using a verified local Pages credential instead, run the tracked Node
   helper from the service directory with `--yes --skip-secrets --commit-hash`.
   Do not use the PowerShell wrapper on this host while its startup-cache writes
   are uncontained. Preflight all output/cache/temp paths before invoking tools.
5. Deploy Worker code or apply pending D1 migrations only when those inputs
   changed and the operation remains needed. An already-applied migration or
   source-matched successful Worker deployment must not be replayed for Pages.
6. Read back the deployed source and live behavior using the checks below.
   Update this file's dated result, the main board and shared index on `main`.
   Do not leave the only working procedure in a task cache or chat.

These command templates require a reviewed full SHA in `VERIFIED_SHA`, verified
credentials and contained output paths. **Do not rerun the currently denied
credential unchanged.** A dispatch acknowledgement is not deployment success.

From the project root, with the existing `Eitan-S-23` GitHub identity:

```bat
gh workflow run deploy-cloudflare-admin.yml --repo Eitan-S-23/E-Track --ref main -f project_name=trace-update-admin-staging -f branch=main -f source_sha=%VERIFIED_SHA% -F include_public=true
```

From the service directory, for an already verified local route:

```bat
node scripts/deploy-admin-staging.mjs --yes --skip-secrets --commit-hash %VERIFIED_SHA%
```

From the service's `public/` directory, when Public Functions changed:

```bat
node node_modules/wrangler/bin/wrangler.js pages deploy ./site --project-name trace-update-public-staging --branch main --commit-dirty=false --commit-hash %VERIFIED_SHA%
```

The Admin helper can create a missing project. The exact-project existence check
is therefore required before using it for a normal redeploy. Do not omit
`--skip-secrets`, recreate Access configuration, change billing or publish a
release channel as a deployment workaround.

## Success And Failure Checks

| Observation | Required action / conclusion |
| --- | --- |
| New canonical deployment ID, expected full source SHA and successful stage | Deployment identity verified; continue with live checks |
| Production/preview configuration unchanged | Existing bindings, roles, secrets and execution references preserved |
| Real Admin Access session succeeds and served HTML/JS match the intended bytes | New Admin page actually served; a generic HTTP 200 is not enough |
| Affected Public APIs pass, including iOS announcements for this batch | Public Functions update verified; a Worker-only HTTP 200 is not enough |
| Token-management GET returns 403/9109 | That management read is denied; do not infer that publishing credentials are absent |
| Exact Pages GET returns 401/403 | Stop that route; retain the result and reconcile the existing input/account/scope, without automatic login, token creation or permission expansion |
| OAuth copy expired or refresh fails | Check its provenance and other named existing routes; not proof of missing task authorization |
| Timeout, TLS failure or interrupted CLI after upload | Inspect actual remote deployment first; do not blindly redeploy or call it a credential failure |
| All checked routes rejected | State that deployment is incomplete and ask once for the existing Pages-capable input's name/location or restoration of its protected route; never request plaintext keys |

Wrong: "One 403 means the user must log in; rebuild the App and retry everything."
Correct: identify the exact operation and credential, preserve its denial, reuse
other named authorized inputs, and deploy only the component still missing.

The completed `1.0.79+105` package source is
`59131a3ef0712d46e7b17694d585371b751ab7ba`. Its original candidate/R2 artifacts,
migration `0014_admin_ux.sql`, Worker version
`54ad084f-1bc3-41a8-bcad-cdc28ff536d4`, and successful historical delta
`43932189981/1` must not be rebuilt, reapplied or replayed to unblock Pages.
Device/formal acceptance and Beta/Stable publication remain separate obligations.
