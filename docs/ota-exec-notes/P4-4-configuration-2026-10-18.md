# P4-4 Redacted Configuration Matrix

This is a timestamped implementation inventory, not a new Spec or acceptance
matrix. Evidence E1/E2/E3 refers to the unchanged JSON receipts in the evidence
archive accompanying this note. Secret presence never implies value correctness.

Current interpretation (2026-10-18 correction): CF-CI-01 / `e-track-ci` exists.
`P44-CREDENTIAL-01` is an unresolved production-use/target/configuration decision,
not a missing-token observation or unconditional new-token requirement. See
`docs/agent-collaboration/credential-registry.md` before any credential request.

## Evidence And Owners

| ID | Original / observation | Applicability |
| --- | --- | --- |
| E1 | `.cache/p44/evidence/inventory-01.json`, 2026-10-18 12:31:08..12:31:52 UTC | Nine GitHub GETs and current Cloudflare metadata/health/Access observations; includes actual 403s. Values are projected/redacted, not secret readback. |
| E2 | `.cache/p44/evidence/production-protection-01.json` | Four successful configuration writes plus readback. No job dispatch or approval. Exact timestamps remain in the receipt. |
| E3 | `.cache/p44/evidence/capability-01.json`, 2026-10-18 12:40:25..12:40:33 UTC | Existing CI and local provisioning tokens active, but self-policy/permission-catalog access denied with 403/9109. No token creation, permission expansion or CI export. |
| E4 | P4-1-v4 at `7f136c07505f56582640761944ab5add093252e4` | Direct sources: v2 ORIGINS/ADMISSION/REHEARSAL, v3 BYTES, v4 R2/STATE. Canonical run 38946949709/1 at b9d7d18; not P4-4 formal REUSED/PASS. |
| E5 | P43-DELIVERY-20261018, delivery inventory/archive on main 0779f67 | Exact deployment ed9c6a39, source 0067b6c, public origin/cutover/signing and owner observations. Private originals stay at their published controlled locations. |

O1 = existing repository owner `Eitan-S-23`, configuration/key lifecycle owner.
O2 = user-assigned main agent, independent OTA reviewer, not this implementer.
O3 = Cloudflare/D1 migration owner with OTA reviewer, root-coordinated, retaining
P42-EXT-02. No new human identity has been invented for O3.

## GitHub Secrets

Each rehearsal name below is environment-scoped in `firmware-rehearsal`. Its
unprefixed production counterpart belongs in `firmware-production`, never at
repository scope where rehearsal could inherit it. The repository currently
contains only the unrelated existing development-signing secret.

| Runtime name | Rehearsal secret | Presence / UTC updated_at | Production presence | Binding / evidence | Gap, owner and next step |
| --- | --- | --- | --- | --- | --- |
| CLOUDFLARE_ACCOUNT_ID | FIRMWARE_REHEARSAL_CLOUDFLARE_ACCOUNT_ID | Present, 2026-10-16 06:11:25 | Absent | Same privately identified account; E1/E4 | O1: confirm the approved production target/account before filling the absent setting. |
| CLOUDFLARE_API_TOKEN | FIRMWARE_REHEARSAL_CLOUDFLARE_API_TOKEN | Present, 2026-10-16 06:11:27 | Absent | CF-CI-01 e-track-ci / e-track-p41-ci, P41-CF-CREDENTIAL-02; E1/E3/E4 | P44-CREDENTIAL-01: confirm production-use/isolation scope and protected consumer; do not infer a new-token requirement from management 403. Existing test authority does not permit production reuse; provisioning-token CI export stays prohibited. |
| TRACE_UPDATE_SERVICE_URL | FIRMWARE_REHEARSAL_TRACE_UPDATE_SERVICE_URL | Present, 2026-10-16 06:11:31 | Absent | Test HTTPS origin, health=staging; E1/E4 | O1: bind the actual production HTTPS origin, not the legacy Trace or test endpoint. |
| TRACE_DEPLOY_TOKEN | FIRMWARE_REHEARSAL_TRACE_DEPLOY_TOKEN | Present, 2026-10-16 06:54:34 | Absent | Successful canonical registration, secret metadata unchanged; E1/E4 | O1: separate target deploy credential; Worker stores only its digest. Runtime pairing still needs its own evidence. |
| OTA_AES_KEY | FIRMWARE_REHEARSAL_OTA_AES_KEY | Present, 2026-10-16 04:24:34 | Absent | Protected real-key App/packer binding at b9d7d18; E1/E4 | O1/O2: approved production key must preserve approved package/compiler identity. Device compatibility remains P3-5/P5, not inferred from CI. |

GitHub does not expose stored secret values. Unchanged update timestamps are
metadata evidence only. Worker secret-value rotation is not observable from its
name listing; do not assert value equality from masked settings.

## Variables And Protection

| Configuration | Type / scope | Observed state / update | Evidence / permissions | Gap, owner and next step |
| --- | --- | --- | --- | --- |
| OTA_BOOT_CHAIN_READY | Repository variable | false, newly created by E2 | Explicit global lock, not a release approval | O1 maintains false until P5 plus independent approval. |
| OTA_BOOT_CHAIN_READY | Rehearsal environment variable | false, 2026-10-16 04:24:28 UTC | E1; unchanged | No write needed. |
| OTA_BOOT_CHAIN_READY | Production environment variable | false, newly created by E2 | Defense against inherited defaults | Never temporarily set true for configuration tests. |
| FIRMWARE_REHEARSAL_TRACE_R2_BUCKET | Rehearsal variable | e-track-firmware-p41-test-releases, 2026-10-16 04:24:29 UTC | E1/E4, exact test bucket | No write needed; both this and old Trace test bucket remain rejected for production. |
| FIRMWARE_REHEARSAL_TRACE_D1_DATABASE_NAME | Rehearsal variable | e-track-firmware-p41-test, 2026-10-16 04:24:30 UTC | E1/E4 | No write needed. |
| FIRMWARE_REHEARSAL_TRACE_D1_DATABASE_ID | Rehearsal variable | 2617e1e1-956f-42ce-a465-da56d84abf06, 2026-10-16 06:11:21 UTC | E1 current binding matches E4/E5 | No migration/backfill authorized by merely reading this row. |
| FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT | Rehearsal variable | c715ec6b00f8d9b06a820213da72421694b1e44c, 2026-10-16 06:11:22 UTC | E1; exact old qualified source | Intentionally not rebound to the P4-4 branch. Wrong current source remains rejected. |
| OTA_PREVIOUS_RELEASE_JSON | Rehearsal environment variable | Explicit non-formal descriptor; updated 2026-10-16 17:56:24 UTC | Target b9d7d18 / 3.2.8, immutable archive c860b3b; E1/E4 | Do not substitute current HEAD or relabel as a formal Release. |
| OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256 | Rehearsal environment variable | 184aaee01d10ed482792fee94dd1f57ef6d25d262f7b891f1af11ecbd383c1a5; updated 2026-10-16 17:56:25 UTC | E1, matches canonical descriptor | No new descriptor approval by the implementer. |
| TRACE_FIRMWARE_MIN_APP_VERSION_CODE | Rehearsal variable | 0, 2026-10-16 11:00:49 UTC | E1/E4 | No unsupported client-compatibility assertion. |
| TRACE_FIRMWARE_MIN_PROTOCOL_VERSION | Rehearsal variable | 1, 2026-10-16 11:00:50 UTC | E1/E4 | No protocol change. |
| TRACE_R2_BUCKET | Production variable | Absent | Must name a distinct real production bucket | O1: qualify target before writing, never use a placeholder or renamed test bucket. |
| TRACE_D1_DATABASE_ID / TRACE_D1_DATABASE_NAME | Production variables | Absent | Actual migrated target, not legacy fixture IDs | O1/O3: qualify exact database and activation state. |
| TRACE_FIRMWARE_MIN_APP_VERSION_CODE / TRACE_FIRMWARE_MIN_PROTOCOL_VERSION | Production variables | Absent | Must match approved canonical metadata | O1/O2: configure with the selected production candidate, not guessed defaults. |
| OTA_PREVIOUS_RELEASE_JSON / OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256 | Production environment variables | Absent | Exact reviewed target/descriptor required | O2/O1: do not transfer b9d7d18 approval to current main. |
| OTA_APPROVED_REHEARSAL_RUN_ID / OTA_APPROVED_REHEARSAL_ATTEMPT | Production approval variables | Absent | E4 proves only run 38946949709/1 at b9d7d18 | O2/O1 bind a still-applicable exact candidate. No production approval is implied by E4. |
| OTA_APPROVED_REHEARSAL_METADATA_SHA256 / OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256 | Production approval variables | Absent | Required by actual workflow and verifyPromotion | O2/O1 bind the original canonical bytes; never use a summary/report hash. |
| firmware-rehearsal | Protected environment | Existing reviewer Eitan-S-23, prevent_self_review=false; exact dev/p4-1/unattended-20261015 branch | E1, unchanged original delegated/human route | P41 delegation is not permission to approve a P4-4 run. |
| firmware-production | Protected environment | Created; required reviewer Eitan-S-23, prevent_self_review=true; only main branch | E2, explicit owner-delegated setup using the sole existing owner | Future dispatcher must not be its approver. Real approval/execution stays after P5; no automatic approval. Platform admin-bypass capability is not an exercised bypass or an independent review. |

Production scope is not silently equated with an existing Trace `prod` example.
No production Worker/D1/R2 has been created or claimed ready. A safe proposed
dedicated namespace is `e-track-firmware-production` and
`e-track-firmware-production-releases`, subject to actual configuration ownership
and existing-resource checks under confirmed target/credential-use authority.
This is not a request for a new token. Do not claim nonexistence of hidden
resources from a token's visibility.

## Worker And Access

| Configuration | Type / target | Presence / observation | Evidence / applicability | Gap, owner and next step |
| --- | --- | --- | --- | --- |
| DB / RELEASES_BUCKET | Worker D1/R2 bindings | Exact test D1/bucket above | E1 live; unchanged from E4/E5 | Production bindings not configured. |
| DEPLOY_TOKEN_SHA256 | Test Worker secret_text | Present; value hidden | E1, E4 registration succeeded under original values | O1 owns rotation; no new value-correctness claim. |
| DOWNLOAD_HMAC_KEY_CURRENT | Test Worker and isolated Admin secret_text | Present | E1/E5; actual matching signed downloads in P4-3 originals | No key was copied or rotated in P4-4. |
| DOWNLOAD_TOKEN_KEY_VERSION | Worker/Admin plain_text | p41-test-1 | E1/E5 | Separate production signing configuration remains to be qualified. |
| DOWNLOAD_HMAC_KEY_PREVIOUS / DOWNLOAD_TOKEN_PREVIOUS_KEY_VERSION | Optional rollover pair | Absent in initial test setup | No incomplete half-pair observed | Do not invent a previous key when no rotation is active. |
| DOWNLOAD_TOKEN_TTL_SECONDS | Test Worker plain_text | 300 | E1 | Retain expiry boundary. |
| FIRMWARE_V2_CUTOVER_EPOCH | Worker/Admin plain_text | Fixed 1792039926 | E1/E5 | Never replace with current time during redeployment. |
| FIRMWARE_DOWNLOAD_ORIGIN | Isolated Admin plain_text | Test Worker HTTPS origin | E5 private project original verified against inventory | Fresh Pages GET using CI token denied; not falsely recorded as current Pages readback. |
| ACCESS_JWT_ISSUER / ACCESS_JWT_AUD | Isolated Admin secret_text | Names configured; current Access app/audience digest matches original | E1/E5; actual protected origin 302 | Value equality is not inferred from empty/masked secret fields. |
| ADMIN_OWNER_EMAILS / ADMIN_ALLOWED_ORIGINS | Isolated Admin secret_text | Names configured | E5 original established owner session and same-origin checks | No owner identity guessed from GitHub login. |
| Publisher/viewer role mappings and sessions | Access/Admin roles | Real session coverage absent | Explicit P4-3 retained limit | O1 supplies actual role identities/session route when required; mock roles are not live evidence. |
| observability.redact_query_string | Test Worker setting | true | E1; only settings delta since E4, authorized P43-OBS-01 | Keep query redaction; no repeated signed-download/log campaign. |

## Rotation And Emergency Revocation

O1 owns secret values and platform changes; O2 reviews the affected candidate and
evidence, and O3 owns actual migration/backfill identity. These responsibilities
do not authorize this implementer to impersonate a reviewer or edit old evidence.

1. Keep the global and environment boot-chain locks false during a planned
   sensitive change. Record the exact target, current metadata, affected callers,
   validity window and rollback/revocation plan before modifying anything.
2. Use protected platform inputs or the guarded private input directory. Never
   put actual values into chat, argv, source, screenshots, artifacts or public
   logs. Do not export the local provisioning credential to any CI environment.
3. Deploy credentials require coordinated target digest and environment-secret
   replacement. Revoke the old dedicated token through its owner-controlled
    platform entry. Do not copy the rehearsal token under test-only authority to
    solve production absence; credential-use changes remain owner decisions.
4. Signing rotation uses a complete current/previous version-key pair on both
   signer and verifier. Retain the previous pair for the actual maximum issued
   capability lifetime, then remove it only under the scoped rotation authority.
   Do not reset cutover or reuse an old version label for new key material.
5. A key/token/binding change invalidates the relevant old runtime evidence.
   Compute the smallest new host/runtime verification and obtain actual approval;
   old run success or configuration HTTP 2xx does not prove the new values work.
6. Emergency action is fail-closed: lock publication, revoke the compromised
   target token/key via O1, retain logs and coordinate the authorized service
   response. Do not delete firmware assets, rewrite audits, re-enable channels,
   issue recovery capabilities or perform device operations as a cleanup shortcut.

## Remaining Owner Configuration

`P44-CREDENTIAL-01` previously requested a separate production token because
self-policy/catalog reads failed. That inference is SUPERSEDED: those 403s only
establish management-read denial. Existing `e-track-ci` is already an observed,
active dedicated input, not a credential the user must create again. No management
permission has been added, no token created/rotated and no secret uploaded here.

Historical proposed owner entry (empty, ignored, no longer the default request):
`D:/github/my/E-Track/.cache/p4-4-integration-20261018/.cache/p44/private/production-ci-token.txt`.
Its emptiness is not evidence that CF-CI-01 or a platform secret is missing.
O1 must confirm the actual production target and credential-use/isolation boundary
before absent production rows are populated. Prefer existing protected inputs and
redacted owner scope receipts; create a new token only for an evidenced need and
an explicit owner decision. Do not put credentials into chat or reinterpret the
frozen test exception as production authority. Then verify only the changed
configuration and affected evidence, without repeating successful staging work.

This matrix is not acceptance-ready while these required production rows remain
absent. Real environment rejection and the stated role/runtime gaps must be
honestly adjudicated by O2; production job execution remains after P5.
