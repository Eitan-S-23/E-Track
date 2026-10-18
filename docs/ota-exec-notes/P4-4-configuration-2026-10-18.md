# P4-4 Redacted Configuration Matrix

This is a timestamped implementation inventory, not a new Spec or acceptance
matrix. Evidence E1/E2/E3 refers to the unchanged JSON receipts in the evidence
archive accompanying this note. Secret presence never implies value correctness.

## Current Production Matrix

Updated after the owner's explicit target/key authorization, with final readback
at 2026-10-18 16:09:03 UTC (2026-10-19 local). E8 below is the current production
state. Earlier E1/E6 tables are retained as historical inventories, not assertions
that production is still empty. P44-TARGET-01 is implemented; P44-CREDENTIAL-01
now concerns the production CI protected source/scope. Existing e-track-ci remains
available and is not requested again. The owner's 2026-10-19 dedicated-token
choice supersedes the earlier existing-source-first condition. The current
blocker is the native-proxy/resource-scope gap under `Dedicated Production CI
Decision`, not another request to choose a token.

| Configuration | Platform / scope / type | Presence / latest relevant UTC observation | Binding and evidence | Owner / remaining action |
| --- | --- | --- | --- | --- |
| e-track-firmware-production | Cloudflare / owner-confirmed account / Worker | Deployed, final code upload 2026-10-18 16:07 | Version d4ecbdc7-f097-4ced-b55c-b2f6dfe4c451; E8 | O1 lifecycle; firmware-only DB/R2 service, not legacy Trace App or production Admin qualification. |
| DB | Worker binding / D1 | Present; UUID 1cd5db26-6bbd-4595-abef-72ff51ecdaf3 | New e-track-firmware-production DB, accepted five migrations; E8 schema/SELECT originals | O1; no legacy/backfill. O3 ownership is unchanged for any future legacy work. |
| RELEASES_BUCKET | Worker binding / R2 | Present; created 2026-10-18 15:26:13 | e-track-firmware-production-releases, distinct from both test buckets; E8 | O1; no firmware object was uploaded. |
| Production public origin | Worker / HTTPS origin | 200/prod final health at 16:10 | https://e-track-firmware-production.tangjichentudou.workers.dev; E8 | O1; health is not upload/register qualification. |
| CLOUDFLARE_ACCOUNT_ID | GitHub / firmware-production / secret | Present; updated 15:50:24 | Confirmed existing account; E8 metadata/secure input receipt | Configured; no account value in evidence. |
| CLOUDFLARE_API_TOKEN | GitHub / firmware-production / secret | Absent at E8; no later write attempted | Dedicated-token choice authorized; required cold-session Scripts permission is account-scoped; E9 | P44-CREDENTIAL-01: owner decides the scope/interface gap below. No test/setup-token reuse, broad-policy creation or claimed creation failure. |
| TRACE_UPDATE_SERVICE_URL | GitHub / firmware-production / secret | Present; updated 15:50:29 | Exact new HTTPS origin; E8 | Configured; downstream candidate/runtime checks remain. |
| TRACE_DEPLOY_TOKEN | GitHub / firmware-production / secret | Present; updated 15:50:32 | Newly generated independent value, paired locally with Worker digest; E8 | O1 rotation/revocation; actual valid-token registration NOT_RUN. |
| OTA_AES_KEY | GitHub / firmware-production / secret | Present; updated 15:50:34 | Existing approved p41-rehearsal-ota-key.json source, original key identity/integrity verified; E8 | Not generated/rotated. O2 evaluates candidate App/packer applicability. |
| TRACE_R2_BUCKET | GitHub / firmware-production / variable | Present; updated 15:50:38 | e-track-firmware-production-releases; E8 | Configured. |
| TRACE_D1_DATABASE_NAME | GitHub / firmware-production / variable | Present; updated 15:50:39 | e-track-firmware-production; E8 | Configured. |
| TRACE_D1_DATABASE_ID | GitHub / firmware-production / variable | Present; updated 15:50:42 | 1cd5db26-6bbd-4595-abef-72ff51ecdaf3; E8 | Configured. |
| TRACE_FIRMWARE_MIN_APP_VERSION_CODE | GitHub / firmware-production / variable | Present, 0; updated 15:50:45 | Existing approved metadata value, not a new compatibility claim; E8 | O2 verifies the selected candidate. |
| TRACE_FIRMWARE_MIN_PROTOCOL_VERSION | GitHub / firmware-production / variable | Present, 1; updated 15:50:47 | Existing protocol value; E8 | O2 verifies the selected candidate. |
| DEPLOY_TOKEN_SHA256 | Cloudflare / new Worker / secret_text | Present; written 15:47:36 | Digest of the new production deploy token; local pair check, names-only platform readback; E8 | O1; no secret readback or valid production registration claimed. |
| DOWNLOAD_HMAC_KEY_CURRENT | Cloudflare / new Worker / secret_text | Present; written 15:47:40 | New independent production HMAC, not copied from testing; E8 | O1; production Admin signer pairing is not configured in this Worker-only scope. |
| DOWNLOAD_TOKEN_KEY_VERSION | Cloudflare / new Worker / plain_text | p44-prod-1 | Initial current pair; no previous pair required; E8 | O1 preserves unique version on rotation. |
| DOWNLOAD_TOKEN_TTL_SECONDS | Cloudflare / new Worker / plain_text | 300 | E8 | Preserve bounded lifetime. |
| FIRMWARE_V2_CUTOVER_EPOCH | Cloudflare / new Worker / plain_text | 1792039926 | Existing fixed parameter, not rewritten to deployment time; fresh empty DB; E8 | O1/O3 retain fixed/auditable semantics. |
| observability.redact_query_string | Cloudflare / new Worker / setting | true, reverified after final upload | E8 scoped PATCH/readback; no signed capability was issued | No assumption that a later deployment preserves it. |
| OTA_BOOT_CHAIN_READY | GitHub / repository, rehearsal, production / variables | false at all three scopes | E8; no unlock or setting rewrite | O1; P5 and existing approvals remain mandatory. |
| firmware-production protection | GitHub / environment / rules | Reviewer Eitan-S-23, prevent_self_review=true, main branch only | Unchanged E2/E8; can_admins_bypass=true remains disclosed | Real production approval/execution only after P5. |
| OTA_PREVIOUS_RELEASE_JSON / OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256 | GitHub / firmware-production / variables | Absent | Candidate-specific descriptor/digest not guessed or copied as fresh approval | O1/O2 select and independently validate exact applicable original. |
| OTA_APPROVED_REHEARSAL_RUN_ID / OTA_APPROVED_REHEARSAL_ATTEMPT / OTA_APPROVED_REHEARSAL_METADATA_SHA256 / OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256 | GitHub / firmware-production / variables | Absent | No new candidate approval manufactured | O1/O2 own exact binding; old staging success is not a new production approval. |

Runtime key locator, private and excluded from evidence:
`D:/github/my/E-Track/.cache/p4-4-integration-20261018/.cache/p44/private/production-secrets.json`.
It inherits an SU-only ACL. AES continues to use the already registered protected
P4-1 source; no new AES entry or rotation exists. Credential metadata/pairing
checks are not proof of a completed production release.

Historical E8 discovery, superseded as an action request by the dedicated-token
decision below: no qualified production CI source was found in the known registered/local
entries, named process environment or production environment secret list. The
account token catalog is unreadable through the existing setup credential, so
this is not an exhaustive claim that no other token exists. No creation POST or
scope expansion was attempted with an unverified policy. The precise remaining
owner operation is to select/verify an existing source in the Cloudflare owner
interface (or create a qualified scoped one if none exists), provide a redacted
resource/operation policy, and place the value in firmware-production's
CLOUDFLARE_API_TOKEN or a named protected file. Do not send plaintext in chat.
If native preview requires permissions exceeding the allowed production boundary,
stop and return that concrete interface gap to the main/P4-1 owner; do not solve
it by granting account-wide access. Catalog 403 does not prove creation denial.

## Historical Inventory Before Owner Deployment

The following timestamped E1..E7 observations and decision history are preserved.
Their former pending owner decisions and absent production resources are
superseded by the current production matrix above, not rewritten as old successes.

## Evidence And Owners

| ID | Original / observation | Applicability |
| --- | --- | --- |
| E1 | `.cache/p44/evidence/inventory-01.json`, 2026-10-18 12:31:08..12:31:52 UTC | Nine GitHub GETs and current Cloudflare metadata/health/Access observations; includes actual 403s. Values are projected/redacted, not secret readback. |
| E2 | `.cache/p44/evidence/production-protection-01.json` | Four successful configuration writes plus readback. No job dispatch or approval. Exact timestamps remain in the receipt. |
| E3 | `.cache/p44/evidence/capability-01.json`, 2026-10-18 12:40:25..12:40:33 UTC | Existing CI and local provisioning tokens active, but self-policy/permission-catalog access denied with 403/9109. No token creation, permission expansion or CI export. |
| E4 | P4-1-v4 at `7f136c07505f56582640761944ab5add093252e4` | Direct sources: v2 ORIGINS/ADMISSION/REHEARSAL, v3 BYTES, v4 R2/STATE. Canonical run 38946949709/1 at b9d7d18; not P4-4 formal REUSED/PASS. |
| E5 | P43-DELIVERY-20261018, delivery inventory/archive on main 0779f67 | Exact deployment ed9c6a39, source 0067b6c, public origin/cutover/signing and owner observations. Private originals stay at their published controlled locations. |
| E6 | `.cache/p44/evidence/targets-01.json`, 2026-10-18 14:21:51..14:22:54 UTC; `r2-targets-02.json`, 14:24:59..14:25:04 UTC | Existing e-track-ci reads actual Worker/D1/R2 metadata; nine GitHub configuration GETs. Initial R2 ECONNRESET and Pages 403 remain recorded. The R2-only retry succeeded; no token-management probe, provisioning-token use or configuration mutation. |
| E7 | `.cache/p44/evidence/auth-negative-01.json`, 2026-10-18 14:29:47..14:29:53 UTC | Two real test-Worker POST denials, missing/wrong deploy token, empty metadata, both 401/TOKEN_INVALID with exact requestId echoes. Not an upload, successful registration, approval rejection or production test. |
| E8 | `.cache/p44/evidence/production-*.json` and `P4-4-integration-2026-10-18/production.zip` | Owner-authorized create/schema/deploy/key/GitHub results, final current-source readback-02 and smoke-02; includes failed import, superseded deployments, source mismatch, dependency failure and their bounded repairs. Current configuration, not formal acceptance. |
| E9 | `.cache/p44/ci-policy/` and `P4-4-integration-2026-10-18/ci-policy.zip` | Official permission/API docs, tagged SDK source, five unchanged product inputs/eight static checks, account permission-group GET 403/9109. No token creation, secret write or runtime session. |

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

## Pre-Deployment Live Reconciliation

E6 supersedes only the observation time, not old receipts. The protected test
settings are unchanged; no write was needed. Worker settings still bind the
exact E-Track test DB/bucket, ENVIRONMENT=staging, fixed cutover=1792039926,
download key version=p41-test-1, TTL=300 and query redaction=true. Its current
ETag is `e106f789a1385841130cc67dd462b33c1031d0bc89871b1f751b1c0d973f39bc`.

| Surface | Current observation | Meaning and remaining action |
| --- | --- | --- |
| Visible project Workers | e-track-firmware-p41-test and trace-update-service-staging; five scripts returned overall, unrelated names omitted | Neither is an approved production target. Old Trace staging identifies repository Trace, not E-Track, and lacks the E-Track fixed-cutover binding. Do not repurpose it. Visibility is not proof about inaccessible resources. |
| Visible project D1 databases | e-track-firmware-p41-test and trace-update-staging; page 1 returned 4/4 total databases | API field version=production is a D1 service generation, not ENVIRONMENT=prod or an owner-selected OTA production database. No row/schema/backfill was changed. |
| Visible R2 inventory | Only e-track-firmware-p41-test-releases and trace-update-staging-releases; returned 2/2 total | Both are explicitly rejected as production buckets by the actual workflow. R2 read works; the initial transport failure is not a token-permission failure. |
| firmware-production | No secrets; only variable OTA_BOOT_CHAIN_READY=false; reviewer Eitan-S-23, prevent_self_review=true, only main branch | Required production config is genuinely absent. Do not populate placeholder bindings, guess secret values or transfer old candidate approvals. |
| firmware-rehearsal | Same five secrets/nine variables and exact P4-1 branch; gate=false | Existing receipts remain inputs. No new branch, key or secret was installed; successful rehearsal is not repeated. |
| Admin bypass setting | Both environment GETs report can_admins_bypass=true | Configuration capability, not an exercised bypass. Read-only GraphQL UpdateEnvironmentInput introspection exposes no bypass input; no guessed mutation was sent. O1 owns any separate UI hardening. |
| Pages metadata | Existing CI token still receives 403/10000 | Endpoint-specific read limitation, not token absence. P43 deployment originals remain the source; no refresh of a different credential or replay of Admin actions. |
| Deploy authentication | E7: missing and wrong deploy token each rejected with 401/TOKEN_INVALID | Real negative evidence for the current test Worker; neither validates a future production credential nor supplies missing GitHub approval/rejection evidence. |

The production placeholders in tracked `worker/wrangler.jsonc` have zero-like
D1/KV IDs and repository Trace. They are not an approved production handoff.
User-wide CF-CI-01 authority permits this agent to use the existing token for
the current configuration task; it does not silently select a production CI
consumer or amend the frozen staging/production credential boundary.

## Consolidated Owner Decisions

Historical decision packet: the later owner granted the target, provisioning and
key-generation scopes. Their actual implementation is in the current matrix
above. No repeat target/AES authorization is requested; production CI source/scope
and the main reviewer's candidate/evidence work remain explicit.

This is the precise remaining decision packet, not a request for another token
by default. Earlier generic authority and project-wide agent use are already
recognized and will not be requested again.

| ID | Required decision/input | Preferred bounded direction; effects and next owner |
| --- | --- | --- |
| P44-TARGET-01 | O1 confirms the actual production Worker/D1/R2 target and public origin | Prefer a new, empty E-Track namespace: Worker/D1 e-track-firmware-production and R2 e-track-firmware-production-releases, in the existing account; origin based on that confirmed Worker. This would create new resources and deploy the accepted Worker, not publish firmware or touch old Trace. If an existing target is intended, supply its exact identity instead. Empty-database setup is distinct from P42-EXT-02 legacy/backfill, which remains with O3. |
| P44-CREDENTIAL-01 | O1 specifies the protected production workflow credential source/isolation decision, device AES key source and deploy/HMAC provisioning route | Existing e-track-ci remains available for authorized configuration. Do not assume it must be replaced, but do not silently make a test credential a production CI credential. Prefer the already approved device AES key to preserve package identity; new deploy/HMAC values need protected owner provisioning or explicit generation authority. An existing protected file locator or direct platform configuration is enough; no plaintext in chat. |
| P44-EVID-01 | NEED_EVIDENCE: O2 organizes the minimum formal rejection observation on an authorized exact workflow/ref, with the existing reviewer | Preserve waiting state, actual rejection actor/receipt and unexecuted release steps from the same run/attempt. A 401, cancellation or timeout is not reviewer rejection. No P4-1 delegation, branch-rule relaxation or gate bypass. If waiting cannot be reached, retain the gap. This belongs in the formal acceptance plan, not an implementation prerequisite to obtain independent PASS. Production approval/execution remains after P5. |

Once O1 decides P44-TARGET-01 and P44-CREDENTIAL-01, implement only the selected
missing settings, read them back, run affected host checks and assess evidence
invalidation, then deliver a stable batch. O2 may plan P44-EVID-01 as the minimum
formal observation; the implementer need not obtain independent PASS beforehand.
Real publisher/viewer sessions, the
unexercised admin-bypass route and inherited dependency/cache limitations are
still explicit; nothing here reopens P4-1/P4-2/P4-3 acceptance or completes P4-4.

### Main Review Disposition

The user relayed the main reviewer's DECIDED response to progress commit
`9f7acdebcfebe2f3164f08ac0462403d7cef48b9`. It accepts the submission as progress
and a configuration-decision request, not a formal acceptance handoff or P4-4
PASS. The reviewer reports read-only inspection of the 85/26-test originals and
both 401 receipts. They remain implementation self-tests and test-Worker denial
observations, not production qualification or reviewer rejection evidence.

- P44-TARGET-01: OUT_OF_SCOPE means outside the main reviewer's authority to
  authorize on the owner's behalf, not rejection of the technical direction.
  The independent namespace is recommended; O1 must confirm account, resources,
  public origin and create/deploy scope. No legacy/backfill is included.
- P44-CREDENTIAL-01: OUT_OF_SCOPE for the same owner-authority reason. No new
  generic token request or default new-token requirement. O1 decides production
  CI protected source/use boundary and key lifecycle. Prefer the approved
  App/packer-matched AES key; new deploy/HMAC values require secure owner setup
  or explicit generation delegation. No provisioning-token export to CI.
- P44-EVID-01: NEED_EVIDENCE, owned by O2 as set out in the updated row above.
  This corrects any earlier implication that the implementer must first obtain
  formal independent rejection evidence before handing over a stable batch.

This response grants no target, credential, key-generation or platform-operation
authority. The reviewer reported no file/platform changes or formal acceptance
start. These paragraphs are the implementation agent's later record of that
relayed decision, not a new independent verdict. P4-1 originals remain cross-task
inputs for independent evaluation, never a direct P4-4 REUSED entry or a reason
to repeat successful rehearsal. Gate=false and post-P5 production gates remain.

## Dedicated Production CI Decision

On 2026-10-19 the owner explicitly chose a new independent production CI token.
That replaces the condition to prove no qualified existing source first. This
is an isolation/lifecycle decision, not an inference from any 403. Creation and
direct protected installation into firmware-production/CLOUDFLARE_API_TOKEN are
authorized only within the three approved production resources. Scope expansion,
test-token reuse, provisioning-token export, publication and product edits remain
outside this delegation.

`P44-CREDENTIAL-01`: unresolved. The dedicated-token choice is DECIDED. The
documented ordinary-token/native-proxy route needs a broader resource permission,
so no creation POST was sent. Creation was NOT observed to fail. This does not
claim that every possible Cloudflare access mechanism is impossible or that the
complete preview permission set has been established.

### Source And Permission Reconciliation

Five product inputs match main 0779f677507fa2c8a88c1799c8d2909bbae5a0a0 after
CRLF normalization. Locked/installed Wrangler is 4.105.0. E9 source-analysis.json
binds hashes and SDK excerpts; the official matching tagged preview source was
retrieved without credentials.

| Required operation | Target / business capability | Documented scope and disposition |
| --- | --- | --- |
| `getPlatformProxy(remoteBindings=true)` | `withFirmwareBucket` configures `trace-firmware-uploader` plus remote R2/D1 bindings | Not an S3 client or exclusively a call to the production Worker. SDK uploads a temporary proxy, not a permanent application deployment here. |
| Cold-session `GET /accounts/{account}/workers/subdomain` | SDK `createPreviewSession` calls `getWorkersDevSubdomain` | Official API accepts Workers Scripts Read or Write. Ordinary token documentation scopes these groups to the account, not a script name. Even the read grant covers the account's scripts beyond the three targets. This required capability is enough to stop policy creation. |
| `GET /accounts/{account}/workers/subdomain/edge-preview`; `POST /accounts/{account}/workers/scripts/trace-firmware-uploader/edge-preview` | Obtain session and upload temporary R2/D1 proxy with minimal_mode | Methods/paths are source-observed. Full permission minimum is NOT_ESTABLISHED: guessed public edge-preview reference returned 404. The distinct permanent-module PUT API is not proof that Scripts Write is necessary/sufficient for preview. |
| R2 `head`, conditional `put` with `etagDoesNotMatch: "*"`, `get` | Only e-track-firmware-production-releases; no deletion requested | Bucket-scoped Workers R2 Storage Bucket Item Write / Object Read & Write is documented as S3-only, not Cloudflare REST. Current code uses native bindings, not S3 keys. A bucket token alone cannot satisfy account subdomain/preview APIs. No account-wide R2 Write added. |
| Three D1 SELECT preflight queries | Only 1cd5db26-6bbd-4595-abef-72ff51ecdaf3 intended | Current code uses the proxy, not public D1 REST. Public query API documents D1 Read/Write with ordinary account scope; moving to REST alone does not establish database-only isolation. D1 Edit is not a business requirement for SELECTs. |
| `/healthz`, `/api/ci/firmware/releases` | Exact production origin; registration uses existing TRACE_DEPLOY_TOKEN | No CF control-plane token permission needed for these application calls. Neither was replayed here. |

The module-upload API lists `Individual Workers Admin/Editor` as alternatives.
That is not a qualified ordinary-token resource policy or authorization for the
separate account-subdomain/preview APIs. Captured member-role/token documentation
does not establish that route. No new role or guessed resource key was applied.
Any granular mechanism needs its exact supported policy and API qualification.

The new GET `/accounts/{approved-account}/tokens/permission_groups` via the
authorized local setup input returned 403/9109 at 2026-10-18T17:37:27.997Z,
cfRay a4c94fa48ce1a0ee-NRT. This is distinct from the old `/user/tokens` GET and
proves only this catalog read was denied. Creation remains unprobed because no
in-bound policy was available to submit; no existing token was expanded.

### Official Sources

- Policies and provisioning requirements: https://developers.cloudflare.com/fundamentals/api/how-to/create-via-api/
- Permission scopes: https://developers.cloudflare.com/fundamentals/api/reference/permissions/
- Mandatory subdomain API: https://developers.cloudflare.com/api/resources/workers/subresources/subdomains/methods/get/
- Bucket scope/S3-only Object permissions: https://developers.cloudflare.com/r2/api/tokens/
- Account token UI: https://developers.cloudflare.com/fundamentals/api/get-started/account-owned-tokens/
- Pinned preview source: https://raw.githubusercontent.com/cloudflare/workers-sdk/wrangler@4.105.0/packages/wrangler/src/dev/create-worker-preview.ts

E9 preserves response bytes, timestamps/status/hashes, the documentation redirect
and 404. Official documentation's example credentials are vendor examples, not
project secrets; archive scanning also checks actual known project values.

### Owner Console Steps And Next Decision

There is no honest click-through compliant-token recipe for the current route
under the unchanged strict boundary. The precise UI route for owner inspection,
or subsequent use after a compliant policy/explicit scope decision:

1. Cloudflare dashboard: select the existing account, **Manage account > Account
   API tokens > Create Token**. Creator needs Super Administrator or API Token
   Provisioning and can grant only their allowed subset. Suggested separate name:
   `e-track-production-ci`. No new member/account is requested.
2. Inspect permissions/resources. **Workers Scripts Read** is the documented
   lower bound for the subdomain call, NOT the complete release policy. If scope
   is account-wide, stop before creation: the current authorization excludes it.
   Do not choose Workers Platform Admin, token-management permissions, global
   account access or a broad Edit template for this CI token.
3. For a future approved S3 route only: **R2 Object Storage > Overview > Account
   Details > API Tokens > Manage > Create Account API token**; **Object Read &
   Write**, specific bucket `e-track-firmware-production-releases`. This cannot
   replace the current native consumer by itself; do not create it just to fill
   a secret name. No existing credentials or permissions should be changed.
4. After a complete compliant policy is qualified, or its broader scope separately
   approved: **Continue to summary > Create Token**. Keep the one-time value in
   the secure owner flow. GitHub: **Eitan-S-23/E-Track > Settings > Environments >
   firmware-production > Environment secrets > Add environment secret**, name
   `CLOUDFLARE_API_TOKEN`. Return only redacted policy/creation/expiry metadata;
   never place the value in chat, variables, rehearsal settings or evidence.

Preferred direction preserves strict isolation: main coordinates a bounded
P4-1/P4-2 interface decision rather than granting account-wide CI control. Evaluate
bucket-scoped S3 with conditional put/readback and target-authenticated preflight
for the existing three D1 queries. Do not drop monotonic/legacy checks or edit
accepted products here. This is a repair direction, not a new implementation Spec.
The alternative is a separately explicit owner exception for account-read/proxy
scope after the remaining preview permissions are identified, not a default fix.
P41's test-only same-account exception is not extended; no new subscription is
requested.

Oracle for the chosen route: gate=false, exact policy/consumer, real authorized
target readback and outside-target denial; preserve object identity, monotonic/
legacy preflight, value-free logs and environment separation. Coordinate any
negative probe with main before accessing other resources. No full rehearsal or
production publication is required to settle this interface decision.

Executed: eight static source/document assertions. Historical 11/85/26 tests keep
their original attribution, not rerun or relabelled. Token creation, secret write,
new-token runtime validation, CI dispatch and formal acceptance are NOT_RUN.
Existing production resources, AES, deploy/HMAC, old evidence and gate unchanged.
