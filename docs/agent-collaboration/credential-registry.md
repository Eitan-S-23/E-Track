# Credential Registry

Operational inventory, not a secret store or acceptance input. Rules live in
[Reuse Before Requesting Credentials](../agent-collaboration-contract.md#reuse-before-requesting-credentials).
The root-level operational entry is
[CLOUDFLARE-DEPLOYMENT.md](../../CLOUDFLARE-DEPLOYMENT.md); read it before deployment
or another credential/login request.
Dates and successful observations below are historical, not perpetual validity
claims. This inventory is not exhaustive; an unlisted credential is not proved
absent. Owner-confirmed changes update the same ID with source and date, without
overwriting old failures or widening authority.

## CF-CI-01: Existing E-Track CI Token

| Field | Recorded fact |
| --- | --- |
| Canonical name | `e-track-ci` |
| Historical alias | `e-track-p41-ci`; the user explicitly confirmed these are the same token |
| Authorized users | User standing authorization, 2026-10-18: any E-Track agent may use this existing token for authorized project work, across tasks, roles and worktrees; not exclusive to the original agent or task. Do not request token-use permission again merely because the agent changed. |
| Kind / platform | Dedicated Cloudflare API token; distinct from local provisioning credentials |
| Owner | Existing Cloudflare credential owner / user; repository configuration owner `Eitan-S-23`. The GitHub name is not proof of a Cloudflare identity or Admin role. |
| Protected local input | `D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt` |
| GitHub consumer | Secret `FIRMWARE_REHEARSAL_CLOUDFLARE_API_TOKEN` in `firmware-rehearsal`; workflow maps it to `CLOUDFLARE_API_TOKEN` |
| Named backend consumer, 2026-11-18 | Repository Secret `E_TRACK_CI` in `Eitan-S-23/E-Track` is used by the published Worker/D1/Admin/Public workflow. Actual Actions deployment `44186088340` and live source/configuration readbacks succeeded; no secret replacement was needed during deployment. |
| Other protected input, NOT interchangeable | `D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt` is the local provisioning credential, not the dedicated CI token and not for CI export |
| Known secret metadata | Rehearsal secret `updated_at=2026-10-16T06:11:27Z`, observed 2026-10-18; metadata does not expose or verify stored bytes |
| Historical OTA test scope | `P41-CF-CREDENTIAL-02` permits the existing-account dedicated token for the exact P4-1 test Worker/D1/R2; P4-4 consumes that same test configuration. This test-resource exception is distinct from the project-wide agent-use authorization above. |
| Production boundary | Existing test authority does not authorize production use. Same-account capability is not hard production permission isolation. A production-use/isolation decision is not automatically a requirement for a new token. |
| Rotation / emergency revocation | Credential owner controls Cloudflare rotation/revocation; configuration owner coordinates affected protected consumers, records new metadata and assesses evidence applicability. No automated rotation or deletion is authorized by this record. |

The locator above is a named protected input on the recorded Windows host, not a
portable dependency or permission to write into that completed worktree. If it
is unavailable, first reconcile the existing platform secret/protected route
with its owner. Do not create an empty replacement and then report the original
credential missing. Do not read/display `token.txt` as a fallback CI credential.

The user explicitly confirmed project-wide agent use in the 2026-10-18 follow-up
to this registry. No per-agent token or repeat token-use approval is required.
The recorded authorization is implemented in the collaboration contract linked
above. It does not approve every technically available API operation, inherit a
different task's approvals, authorize permission expansion/rotation, or remove
production gates. Token values stay in protected inputs, never in chat or evidence.

### Provenance And Observed Capabilities

- Actions cutover is now executed, not pending: the owner-authorized
  Actions run `44186088340`, linked in the deployment memory below,
  uses `E_TRACK_CI` for the original Worker, D1 and both Pages targets on source
  `28459a89fcd6792611052cb601b231bb947bcc6d`. Exact deployed sources, original
  runtime configuration and real owner/Public readbacks pass. The prior run
  `44183120496` also applied 0015, but failed a Worker environment-label check;
  the adapter was repaired without reapplying the migration or changing this
  credential. This is scoped operation evidence, not a promise about token
  lifetime, account-wide powers or unrelated production authority. No new login,
  token rotation, legacy R2/Trace/rehearsal Secret change or provisioning-token
  export occurred. See [current deployment memory](../../CLOUDFLARE-DEPLOYMENT.md#current-state-actions-deployment-verified-2026-11-18).

- Owner-confirmed alias and protected locator:
  [P4-3 Updated E-Track-CI Authorization](../ota-exec-notes/P4-3-implementation-2026-10-17.md#updated-e-track-ci-authorization),
  delivered on main `0779f677507fa2c8a88c1799c8d2909bbae5a0a0`. That record explicitly
  corrects the preceding agent's incomplete credential inventory. P4-3's bounded
  Access/telemetry remediation is not a standing grant for future mutations.
- Accepted same-account exception:
  [OTA-XC-SECRETS](../ota-cross-system-contracts.md#ota-xc-secrets),
  `P41-CF-CREDENTIAL-02`, and record 16 in
  [spec decisions](../ota-spec-decisions.md). No new account/subscription,
  provisioning-token export, second token/hash approval variable or claim of
  hard production isolation follows from that exception.
- Historical runtime: [P4-1 v4 record](../ota-exec-notes/P4-1-implementation-2026-10-15.md#p4-1-v4-independent-acceptance-pass),
  evidence commit `7f136c07505f56582640761944ab5add093252e4`, canonical run
  `38946949709/1` at `b9d7d18c76e6495fbebf6758df6e4427e79e97b5`.
  Successful test R2 upload/readback and Worker registration qualify those
  original inputs, not an arbitrary production target or subsequently changed key.
- P4-4 read-only observation, 2026-10-18 12:31..12:40 UTC: token verify active;
  test Worker settings and Access app/policy GETs succeeded. Token self-policy
  and permission-catalog GETs returned `403/9109`; Pages GET returned `403/10000`.
  These are different APIs. Management denial does not prove token absence or
  publication failure; Pages denial is not a successful current Pages readback.
  Source: `1e28caf350de7e02a7961350a10018bb5e566e51`, repository-relative
  `docs/ota-exec-notes/P4-4-configuration-2026-10-18.md`, E1/E3, and the unchanged
  `docs/ota-exec-notes/P4-4-integration-2026-10-18/initial.zip`. Read via
  `git show COMMIT:PATH` if that task record is not yet on main.

### Pages Reads Restored After Owner Permission Update

2026-11-18, LOCAL_PENDING. The owner explicitly confirmed editing `e-track-ci`.
Fresh exact Admin and Public Pages project GETs using the registered
`p41-ci-token.txt` input both pass. No OAuth or repository-source management
token was substituted. Original denials remain historical; reuse the new
receipts under `.cache/app-admin-ux-20261117/cloud/`:
`keyring-cloud-pagesprobe-04/result.json` (Admin) and
`keyring-cloud-pagesprobe-05/result.json` (Public).

This qualifies project-read access, not a deployment or all write permissions.
No Secret replacement, token creation/rotation, workflow dispatch or deployment
was performed. The separate repository `CLOUDFLARE_API_TOKEN` cannot be read
back; its named local source is not `e-track-ci`. Owner-approved binding of this
token to that existing Secret is distinct from its current Pages capability.
See the [updated deployment entry](../../CLOUDFLARE-DEPLOYMENT.md#e-track-ci-pages-reads-restored-2026-11-18).

### Named Pages Secret Migration

Owner-requested migration, 2026-11-18. Cloudflare retains the name `e-track-ci`;
GitHub uses `E_TRACK_CI` because its Secret names exclude hyphens and normalize
case. The existing GitHub CLI set that exact repository Actions Secret using
the protected `p41-ci-token.txt` input through stdin. Metadata readback confirms
creation/update at `2026-11-17T18:01:05Z`; no value was read back or exposed.
Receipt: `.cache/app-admin-ux-20261117/cloud/keyring-cloud-githubsecret-01/result.json`.

Only the existing Admin/Public Pages workflow is being migrated. Its four local
bindings now reference `secrets.E_TRACK_CI`, preserving Wrangler's environment
variable name. The old `CLOUDFLARE_API_TOKEN` remains untouched for App/MCU R2
release consumers. The rehearsal environment, original Trace repository,
provisioning token and Cloudflare token policy were not changed by this action.

GitHub Secret creation is complete; workflow/record commit and push remain
LOCAL_PENDING. No Actions run or deployment occurred. Do not repeat the secret
write just because the workflow has not been published. This supersedes the
earlier undecided Pages binding, not the historical credential-denial receipts
or separate production/firmware permission boundaries.

### Unattended Firmware Candidate Environment

Owner-requested configuration, 2026-11-18: `release/candidates` workflow commit
`cb360b762cdd571ceef0d1de881a0de313b95f3c` uses the dedicated `firmware-candidates`
environment, with no required reviewer or wait timer and only that exact branch
allowed. `OTA_BOOT_CHAIN_READY=false` and manual channel publication remain.
It consumes the unchanged repository `E_TRACK_CI` and `CLOUDFLARE_ACCOUNT_ID`
Secrets. The original `firmware-rehearsal` configuration and all its Secrets
remain unchanged; this is not a removal of other tasks' approval requirements.

Two existing protected values are installed in the new environment, without
generation or rotation: `FIRMWARE_CANDIDATE_OTA_AES_KEY` comes from the named
`p41-rehearsal-ota-key.json` source in
`.cache/p41-dev-20261015/.cache/cf-auth-input/`; its identity matches successful
native build `44276457821`. `ORIGINAL_ADMIN_FIRMWARE_DEPLOY_TOKEN` comes from
`.cache/p35-integration-20261028/source/.cache/mcu-release-flow-20261111-01/private/original-firmware-deploy-token.txt`,
the original setup source for that same rehearsal Secret. Both inputs remain
read-only, owner-protected sources; no plaintext copies or values are published.

Environment and Secret metadata readbacks pass; configuration-only Actions
`44283291086` passes with App/firmware jobs skipped. This does not claim a new
native build through the new environment or a channel release. See
[the bounded delivery record](../ota-exec-notes/APP-COMPANION-01.md#mcu-delivered-and-candidate-approval-removed-2026-11-18).

### Main Firmware Candidate Branch

Owner-approved migration, 2026-11-18: the existing `firmware-candidates`
environment now allows only `main`, superseding the earlier `release/candidates`
policy above. Its ID, branch-policy ID, no-review/no-wait behavior, locked
`OTA_BOOT_CHAIN_READY=false` and both Secret metadata records are unchanged.
Repository Secrets and the full rehearsal/production protection, policy, gate
and Secret metadata also match the pre-migration snapshot. No credential value
was read, copied, regenerated or rotated for this branch change.

Main source/workflow baseline is `0b7e1275f91f0c6c0a2f89e19f664d60d5ffee9e`.
App routing commit `1564d5886bf248c83b87afa9c991ab5404a6f73b` keeps original Trace
signing; actual checks-only push `44295658568` succeeds with both builds skipped.
The documentation-only main push is the remaining routing check at this record.
Native 3.3.30 remains the original successful `44276457821`, not a new build
under the migrated branch. See [the migration record](../ota-exec-notes/APP-COMPANION-01.md#mcu-main-migration-2026-11-18)
and `.cache/firmware-main-migration-20261118/keyring-policy-02/configuration.json`.

### Recurrence And Correction

On 2026-10-18 the user identified a repeat of the P4-3 discovery error: the alias
and locator were buried in a long task note, rather than reachable directly from
agent entry points. P4-4 had already used the existing token, but then overstated
management 403s as requiring a separate new production credential. Both failure
modes need prevention: discover known inputs first, and keep existence,
operation-specific capability and authorized scope separate.

`P44-CREDENTIAL-01`'s unconditional new-token request is superseded, not its
underlying 403 receipts. Production target/settings and credential-use boundaries
remain owner decisions; the registry does not populate absent secrets or qualify
production. The empty later P4-4 input slot is not evidence that CF-CI-01 is absent.

## CF-PAGES-01: Pages Deployment Input Reconciliation

2026-11-17 operational correction for APP-ADMIN-UX-01. The user reaffirmed existing
Cloudflare authority. The prior claim that another browser login was the only
remaining prerequisite is withdrawn. This record adds input locators/observations,
not a new credential, permission grant, token-management requirement or CI export.

| Existing input | Bounded current observation |
| --- | --- |
| `CF-CI-01`, protected `p41-ci-token.txt` above | Working Worker/D1 route; original Admin Pages GET denied with 403/10000. Do not ask again for authority to use this token on authorized project work. |
| `app/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json`, `secrets.CLOUDFLARE_API_TOKEN` | Original P4-4 handoff source, distinct from e-track-ci. Current verify is active; direct and proxied original Admin Pages GETs return 403/10000. Own-policy 403/9109 is a separate management-read result, not proof of account permission absence. |
| `D:/github/my/bluetooth_flutter_Trace/cloudflare/update-service/.github-actions-secrets.staging.local.json` | Correct standalone Trace input; read-only. Same account and duplicates an already tested token, so no duplicate failed operation. A prior guessed `D:/github/my/Trace` location was wrong. |
| `.cache/p41-dev-20261015/.cache/cf-auth-input/token.txt` | Local provisioning credential, never a CI fallback/export. Local-only exact Admin Pages GET also returns 403/10000. No token creation or permission change. |
| Existing task-private Pages OAuth copies named in APP-ADMIN-UX-01 | Normal renewal failed; old interactive links expired. An expired copy is not an exhaustive inventory of available authority. |
| `C:/Users/SU/AppData/Roaming/xdg.config/.wrangler/config/default.toml` | Official existing user-config location; source read only. Normal noninteractive renewal in a new project-private copy failed. No user-profile write or fresh login in the correction turn. |

Origins: [P4-4 original credential handoff](../ota-exec-notes/P4-4-s3-preacceptance-2026-10-19.md#independent-credential-handoff)
and [APP-ADMIN-UX-01 correction](../ota-exec-notes/APP-ADMIN-UX-01.md#owner-correction-and-credential-reconciliation).
New receipts are under `.cache/app-admin-ux-20261117/cloud/keyring-cloud-sourceprobe-01/`,
`keyring-cloud-sourcecheck-01/02/03` and `keyring-cloud-renewglobal-01/`.
No values, token identifiers or credential-bearing hashes belong in this registry.

At that earlier checkpoint Pages delivery was unresolved. The subsequent
owner-approved restoration and completed deployment below supersede that status,
not the original refusals. Do not conflate task authorization, one token's
capability and an OAuth copy's status; new login, credentials or expanded scope
are not the automatic response to a refusal.

### Owning Repository And Standard Input Readbacks

Further 2026-11-17 checks are recorded in
[APP-ADMIN-UX-01](../ota-exec-notes/APP-ADMIN-UX-01.md#existing-local-and-github-routes-2026-11-17).
Both repositories' secret names and environment inventories were checked without
extracting values. Trace's existing slots were last updated on 2026-06-29, versus
E-Track's 2026-11-07; neither metadata date proves equivalent values or capability.
Actual Trace run `43996459438` uses its own protected slots and fails the exact
Admin Pages GET with HTTP 403/code 10000 before installs or deployment. No secret
was exported, replaced or widened. E-Track's prior `43978919787` remains separate.

Named configurations traced from successful local deployment scripts form three
distinct OAuth inputs across five files. Exact current Admin GETs return 401/code
10000; duplicate bytes were compared only in memory and not retried. No source
configuration was changed or new login started. The supported token/global-key
environment names are absent from SU's persistent user environment, the machine
environment and the current process. Legacy `C:/Users/SU/.wrangler/config/default.toml`
is absent; the official XDG file remains the already checked July-expired input.
The primary root/App/service `.env` and `.env.local` paths are absent. These are
bounded named-source checks, not an exhaustive private-file search or proof that
the owner has no other Pages-capable credential.

### Restored OAuth And Completed Pages Deployment

2026-11-17, LOCAL_PENDING operational update. The owner explicitly approved the
earlier browser authorization, then requested deployment and retry. The canonical
protected input is
`.cache/app-admin-ux-20261117/cloud/private/xdg-current/.wrangler/config/default.toml`,
with `account:read`, `user:read`, `pages:write` and `offline_access` for the existing
account. Original global/historical configurations remain read-only.

Normal renewal in that canonical project-private configuration succeeded; the
latest renewal at 15:02 UTC is recorded in `cloud/keyring-cloud-renew-03/` under
`.cache/app-admin-ux-20261117/`. Exact Pages reads then succeeded. Admin deployment
`63cdf429-13dc-41b4-aa93-966755ee9d79` and Public deployment
`3865fc8c-8c36-4247-afbf-408b1a8e35b1` both bind the full source
`59131a3ef0712d46e7b17694d585371b751ab7ba` and successful stage. Real owner/static
source and three-platform Public API checks pass; see the
[deployment closeout](../ota-exec-notes/APP-ADMIN-UX-01.md#pages-deployed-and-verified-2026-11-17).

No new browser login, API token, scope expansion or GitHub secret replacement was
performed during the retry. These observations qualify the local Pages route,
not recovery of either denied CI input, Worker write permission for this OAuth,
or a fixed one-month/permanent grant lifetime. Keep renewal serial, preserve the
latest rotated configuration, and distinguish a hung CLI's raw exit status from
the independently verified authorization/deployment. No renewed value belongs in
this registry or any public log.

### Actions Credential History Check 2026-11-18

Read-only, LOCAL_PENDING. Retained dedicated Pages histories contain six failed
Trace runs and one failed E-Track run, including five Trace failures from July.
The recent successful Trace `43969069993` used its repository
`CLOUDFLARE_API_TOKEN` for R2 upload/readback; registration used the separate
`TRACE_DEPLOY_TOKEN`. Neither establishes successful Pages deployment.

Secret metadata still records token updates at `2026-06-29T13:49:09Z` (Trace) and
`2026-11-07T17:48:02Z` (E-Track). These are not token-policy or expiry readbacks.
The November exact Admin GET denials remain 403/10000; July logs are unavailable
(HTTP 410). A longstanding Pages authorization/account-scope gap is suspected,
not a proven precise permission list or a diagnosed recent expiry/revocation.
The named local token's active result does not verify GitHub's encrypted bytes.

See [original evidence and limits](../ota-exec-notes/APP-ADMIN-UX-01.md#actions-credential-history-check-2026-11-18).
Next confirmation is a redacted view of the existing token's Pages permissions,
account scope and conditions, reconciled to its protected CI input, not an
automatic new token, browser login or unchanged failed deployment retry.

Further history check, 2026-11-18: Trace's older combined checks workflow did
contain a green `Deploy Admin Pages` job, `84609678528` in run `28539578982`.
Its retained `Admin Pages deploy unavailable` annotation proves the command
failed; source `7705b36e` deliberately returned `exit 0` after that warning.
This is not historical Pages capability evidence. The warning's permission
suggestion is not an actual token-policy readback. See the
[historical green-run correction](../ota-exec-notes/APP-ADMIN-UX-01.md#historical-green-pages-run-2026-11-18).
