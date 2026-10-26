# Release-Mode Fast-Path Candidate Integration

## Scope And Ownership

Implementation follow-up A/B/C, assigned by the user on 2026-10-26. Base main:
`91fed6bc863d07edc7173c8e3c08b14c159f7863`, verified with ls-remote. Exclusive
branch: `dev/flutter/fastpath-backend-20261026`; worktree:
`D:/github/my/E-Track/.cache/flutter-fastpath-20261026`. Shared Git metadata is
inside the authorized project. The dirty root archive and other worktrees are
not implementation targets. No Trellis spec/task tree is tracked on this base;
use the existing OTA contracts and this assigned follow-up, not another Spec.

This is implementation and development validation, not independent acceptance,
P3-5 recovery execution, P5 long testing or production qualification. P3-4 and
P3-8 accepted cards/bundles remain unchanged. Standard APK/EXE build, main merge,
release and cloud/device mutations need their actual root authority.

## FAST-RELEASE-01: Minimal Selection Policy

Build -> `OTA_LINK_PROFILE` -> `OtaLinkProfile.build` -> BluetoothService binding
policy and OtaService transport -> exact INFO/CAPS2/BEGIN ACK -> actual selection.
`adaptive-v2-candidate` is an explicit standard release-mode build option;
shipping defaults remain baseline pending independent review and P3-5/P5 gates.
This same entry is tested in development CI and can build a debug development
APK without a runtime file, device address, experiment run ID or test identity.

The request is v2, window 24, batch 12, connection-bound GATT reuse and preference
for without-response. Existing receiver capabilities are unchanged: exact
P2BL/2/2/128/24 and fresh nonce, with INFO limiting the configured sender window.
With-response-only GATT uses single-frame writes, not unsupported writes.
Only the already-admitted same-valid-unpoisoned-connection CAPS2 timeout permits
v1 compatibility (window <=4, batch 1). Invalid capabilities/INFO/identity/ACKs
and negotiated-v2 failures remain fail closed. No baud, AT, Boot, BCB, staging,
credit, retry, cancellation or background-owner semantics are changed.

`OTA_LINK_SELECTION` is emitted after a valid BEGIN ACK. It separates request
source/profile/window/batch from actual protocol/window/batch/write mode and
bounded downgrade reasons. GATT reuse is labelled enabled, not claimed as a
cache hit; the existing actual discovery/write statistics remain authoritative.
The durable progress UI uses the same selection and labels compatibility or
capability limits instead of silently calling them fast. Build intent is not
speed evidence. Success still requires the existing post-reboot full raw image
identity checks and owner/foreground-service cleanup.

## Validation Route

No local Flutter/Gradle build or SDK download. Existing contained host helper
regressions first; WIP commit/push uses Eitan-S-23 and only the assigned branch.
`flutter-dev-checks.yml` runs full analyze/test on Ubuntu/Windows, plus a small
second test command compiled with the candidate define to exercise the actual
build entry. Candidate checks use the same bounded SDK/process/log route and
must pass before a requested debug APK can be collected. All failures remain.

Planned regressions: build selector without runtime; real service legacy fallback
through read/latest/download/transfer/reboot; v2 actual window/batch; malformed
capability refusal; existing cache generation, ACK/credit/retry/timeout/cancel,
background denial/owner-loss/page-reattachment and final identity tests. Self-tests
do not relabel old acceptance or require a new physical campaign.

## BACKEND-READY-01: Evidence First

P4-2 accepted source `fc4fbbb8193fcc536ef408b7b662d44b30f869dc` and its original
native CI 38591559979/156 tests are delivered. Its historical activation gates
are not the final environment state. P4-4 subsequently delivered C4/3.2.9 and
new S3/Worker-preflight A/B evidence; v8 source/bundle/index are
`640cb359db7672cdab1e40bc5853a9ab311e35fa`,
`e93ea8e9966b2b0e37921ae1dd2384cb5438e35e`,
`fdd998d71a065b748146afaed710b252ac6fe3f8`.
Main delivery is documented in `P4-4-main-closeout-2026-10-21.md`, including the
separate test-driver fix and passing main CI 39602375609. Consume these original
register/ready/readback/binding observations before any remediation.

Current applicability, candidate/device version pairing, endpoint visibility,
expiry/no-update semantics and current read-only environment state are still to
be reconciled. No actual backend defect is asserted. No upload, register,
database edit, Access mutation, provisioning or deployment is authorized here.

### Current Reconciliation, 2026-10-26

Bounded five control-plane reads and two public latest GETs are archived beside
this note. No successful register/upload/rehearsal/readback was repeated.

| Item | Existing evidence and current applicability | Gap / owner / minimum next action |
| --- | --- | --- |
| Real v2 register/schema | P4-2 `fc4fbbb` native entry tests; P4-4 C4 run 39351100037, schema 2 three-asset registration and exact replay | Implemented; no code repair or repeat registration. Root/OTA reviewer retains independent reconciliation. |
| Deployed Worker and target | Current settings GET 200: exact test D1 2617e1e1-956f-42ce-a465-da56d84abf06 and bucket e-track-firmware-p41-test-releases. Current deployment 88983ae0-75b1-487b-af0d-788b6cf976ec/version bb3d44fd-4a84-489e-9e04-6adfc54a458e matches P4-4-v8 configuration original | No redeploy. Published module SHA 1ad919d795a2354cd4c7d9617f3e3c9805f831967d1a2cdd5930ba61e4c3303f remains bound to that version. Original fixed cutover 1792039926 and token TTL 300s are reused, not requalified by a new transfer. |
| Assets and D1 identity | Current SELECT returns 30209 ready/unarchived at C4, the same raw target SHA eecb806e3b11565f5f7c9ad3a28e6dd20cbca27ad245650dd3de70f3973f0eb1 and three available asset rows. Each original full/patch/recovery R2 body was independently rehashed locally and matches current D1 length/digest | Current remote object bytes were not re-downloaded. Immutable original proof is available; if a fresh presence check is required, root must bind an authorized read-only bucket route. Do not replay expired S3 credentials or uploads. |
| Visibility/download state | Both channels still point to 30208; stable revision 13 and beta revision 11; both disable_latest=1 and disable_downloads=1. Ready 30209 is not the pointed-to release | A real P3-5 combination is not currently exposed. Configuration owner/root must authorize and prepare one dedicated staging test channel, not hand-edit ready/hash or unlock production. No stop flag was changed here. |
| Public path | Both host latest probes returned edge 403/error 1010 browser-signature denial | Host-route observation, not a proved Flutter or Worker defect. Root/network-policy owner supplies a permitted route or policy decision; retain failures, do not disguise the host or bypass WAF/Access. Current latest/download/no-update remain unobserved. |
| Stable device/asset pairing | P3-8 retains MCU 30289 with raw SHA 245189f7b2f02d968068b3ade77000a0b82a8de20b140bd41e2530675713bad0; highest test ready release is 30209, below it | Root/firmware asset owner selects a reviewed bootable forward candidate >30289, compatible hardware/key/Boot and actual P3-4 receiver source, then uses the real pipeline under actual authority. No downgrade or invented version/hash. |
| Fixture selection/error behavior | Delivered versioned fixture and P4-2 native tests cover patch/full/no-update/errors; current deployed version/bindings match historical originals | No backend product change or new backend test campaign justified. Actual P3-5 query/download and final no-update need the chosen real pair and permitted route, not a static JSON substitute. |

Backend disposition: implementation exists; configuration/forward-asset/route
readiness is incomplete, with owners above. No backend source defect was found
and no backend code/configuration was changed. This does not reopen P4-2/P4-4
or replace independent acceptance of the eventual real test combination.

## Results

First WIP `4c16fe69b4c818fc3f12d385aad99998c7fe6b14`, development CI
40283979509: analyze PASS on both hosts, tests FAIL (12 on each). Exact logs
retained in the task cache. The new selection prefix was not yet in the existing
strict App/host snapshot allowlists, so diagnostic snapshots failed closed.
Repair adds only the exact `OTA_LINK_SELECTION ` prefix and a distinguishing
snapshot roundtrip; unknown lines, privacy checks, loss/footer/hash and terminal
requirements remain unchanged. No repeat of a successful physical upgrade.

Host helper 46/46 PASS; runner first failed six old command-order/index assertions
after adding the candidate test command, then 65/65 PASS after updating those
exact expectations. Original first failure is preserved, not hidden as green.

Second source `f5cf470e2406be05887238d31bc08c8dbd9af823`, run 40285858937:
full analyze/test and candidate-build-entry tests PASS on both hosts. The next
test-only batch `4f0adc949bffede49a48219642ceb933e328faae`, run 40287042349,
passed tests on both hosts but strict analyze rejected one `use_super_parameters`
lint in the new synthetic peer. Corrected with a super parameter, not suppression.
The new real-service tests exercise v2 batch12, INFO window 8 downgrade,
with-response batch1 and malformed CAPS2 failure, including final full raw
identity. The candidate-defined CI command now exercises these real services
with the compiled default as well as the ordinary baseline full suite.

Proposed final App version: 1.0.62+88 (previous 1.0.61+87); the queried v1.0.62
GitHub Release does not exist. This reserves a candidate input, not publication.
Root build-only request: exact final branch/ref, build.yml, publish_release=false,
replace_existing_release=false, release_ota_link_profile=adaptive-v2-candidate,
no private runtime/device/run/package identity defines. Retain existing fixed
signing selection and both standard Android release APK/Windows EXE gates.

### Stable Development Batch

Source `57e6f064cec0c819aef8e348cd7690ca868c6a7e`, full checks run
`https://github.com/Eitan-S-23/E-Track/actions/runs/40290802257`: both jobs PASS.
Ubuntu: 783 passed, 16 skipped, 0 failed; Windows: 764 passed, 35 skipped,
0 failed. Both candidate-defined real-entry commands: 8 passed, no skipped or
failed tests. Both analyze commands PASS with no reported issues. Actual SDK:
Flutter 3.47.8/revision 737ba8f885dc774b53b442759999a312c9461e4e,
Dart 3.13.7, engine cf636b1dfb818dd6a3ff16e390e93b1a036969c8.
These are development results with declared skips, not hardware proof.

Host regressions: APK helper 46/46, runner 65/65, snapshot 32/32 and fixed-signing
selection/verification shell 17/17 PASS. The signing entry initially could not
import its supported p34-acceptance/live_host helper in the narrow worktree;
materializing that tracked dependency resolved the host prerequisite, not a
product repair. That original failure remains archived. Git whitespace checks
use CR-at-EOL recognition; raw evidence is separately byte/SHA checked and not
edited to satisfy source whitespace rules. Actions' Node-20 deprecation warning
is retained; passing analysis does not claim all CI output is warning-free.

One explicit debug APK request is run 40291265828 on the same source, using
adaptive-v2-candidate, no runtime/observation identity, application suffix
.p35candidate, and the existing fixed signing key. Both complete jobs PASS,
including full tests and strict upload. APK metadata and verified signer are:

- Application ID: com.wen.gaia.gaia.p35candidate.
- Bytes: 131815790; APK SHA-256:
  d1190ceef54acf3196e4f642caf7f78640c71fed033272c2fc5529ff57756a6f.
- Existing fixed certificate SHA-256:
  9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579;
  exactly one signer, v2 scheme verifies.
- Artifact ID: 12636498748; ZIP digest:
  01b643da52d2ff34a50f541b6693b83d3c51bc272da76183720bc316c922e819;
  expires 2026-10-29T08:25:43Z. No APK bytes were downloaded or installed here.
- requested_ota_link_candidate: adaptive-v2-candidate, runtime_config=false,
  build_profile=adaptive-v2-candidate. This is build intent, not a new device
  negotiation or speed/stability observation. Proposed version remains the
  source pubspec 1.0.62+88; no independent APK version readback is claimed.

The adjacent debug summary contains exact selected original signature,
collection and terminal result lines. No local Flutter/Gradle build or SDK
acquisition was performed.
Standard release APK/EXE remain NOT_RUN pending root's actual build-only
authorization; this note and self-tests do not satisfy that gate.

### Root Handoff And Remaining Gates

Stable product source is 57e6f064cec0c819aef8e348cd7690ca868c6a7e. The subsequent
record-only handoff commit does not change App/CI/Worker inputs and must be named
by exact ref at handoff, without pretending the older APK was rebuilt there.

Root may execute or explicitly delegate `build.yml` on that final development
ref, version 1.0.62+88, publish_release=false, replace_existing_release=false,
release_ota_link_profile=adaptive-v2-candidate, release_application_id_suffix=''.
Select the intended permanent firmware endpoint under root's actual authority;
empty firmware_latest_url retains existing configured behavior and is sufficient
for the build-only release-mode software gate, not P3-5 backend admission. No
temporary URL, device address/run ID/package identity or runtime config is a
build input. Both Android release APK and Windows EXE must pass. Preserve fixed
signing, no existing Release replacement or publishing/deployment.

The separate readiness packet above needs configuration/firmware/network-policy
owners: one compatible forward test candidate >30289, a deliberately selected
staging channel with its stop flags handled through the authorized entry, and
a permitted public query/download route. Retain current 30289; do not downgrade,
hand-edit ready/hash/MCU state or use a fake backend. Independent acceptance and
P3-5/P5 physical campaigns are not performed by this implementation owner.

### Output Audit

Owned outputs are confined to this exclusive worktree (source/docs, contained
host fixtures/receipts, downloaded CI logs and selected exact archives) and the
authorized common Git metadata D:/github/my/E-Track/.git. No PowerShell startup,
local SDK/Gradle build, device operation, cloud mutation, credential/configuration
export or other-worktree source write was performed. No frozen evidence was
edited. The dirty root archive remains untouched. Records and reusable handoff
are pending root main integration, not delivered governance on main.

Development and standard artifact results will be recorded with their exact
source/run identities after inspection. Independent acceptance remains NOT_RUN.

## Root Takeover Reconciliation, 2026-10-26

The user assigned this root session to take over the implementation owner's
remaining work. Reuse the existing exclusive worktree, branch and originals;
this assignment does not grant new build/release, cloud or device operations.
The successor owns implementation follow-up, not independent acceptance of it.

Read-only reconciliation receipts are `.cache/records/takeover-remote-01.*`
and `.cache/records/takeover-runs-01.*`, collected through the existing contained
command wrapper. No existing command receipt or evidence archive was overwritten.

- Remote main remains `91fed6bc863d07edc7173c8e3c08b14c159f7863`.
- Remote development head remains `2febc00b15658bde055d2f1e05095809c1444f76`.
- Development checks on that head, run `40295320180`, are completed/success.
  The preceding record-only head `3d069270` also passed run `40294141775`.
- There are no differences from `57e6f064` to `2febc00b` under the App,
  `Tools/flutter` or `.github/workflows`. Existing source-bound full test
  counts and debug APK `40291265828` are retained; neither was rerun or rebuilt.
- The branch run inventory contains no standard APK/EXE build. Those jobs and
  independent acceptance remain NOT_RUN, not satisfied by development checks.

### FAST-RELEASE-BUILD-01: Authorization Required

The original assignment and execution contract section 7.3.2 authorize scoped
development validation, not the standard `build.yml` workflow. Root takeover
does not silently enlarge that scope. Request one nonpublishing standard build:

- Repository: `Eitan-S-23/E-Track`; workflow: `.github/workflows/build.yml`.
- Ref: `dev/flutter/fastpath-backend-20261026`, bound before dispatch to
  `2febc00b15658bde055d2f1e05095809c1444f76`; version: `1.0.62+88`.
- `publish_release=false`, `replace_existing_release=false`.
- `release_ota_link_profile=adaptive-v2-candidate`.
- Empty `release_tag`, `release_application_id_suffix` and
  `firmware_latest_url`; retain existing configured endpoint behavior.
- Inspect Android and Windows results, fixed signing and artifact metadata;
  preserve necessary logs inside this worktree. No new signing key, APK install,
  main merge/push, Release, Cloudflare registration or deployment.

The workflow's release/Cloudflare job is gated on a version tag or an explicitly
publishing dispatch. A dispatch on this development branch with publishing false
must leave that job skipped. Both standard build jobs must actually succeed;
build intent is still not a device speed or backend-readiness observation.

### BACKEND-READY-01: Preserve The Remaining Owner Decisions

Reuse the original 2026-10-26 reconciliation above, without presenting it as a
new current-environment probe. It identifies a forward firmware candidate
greater than 30289, an intentionally exposed staging channel and a permitted
public query/download route as prerequisites. No fresh register/upload, stop-flag
change, database write, network-policy change or device operation was performed.
Select and authorize that exact staging combination separately; do not request
blanket production access or reinterpret a host 403 as a product defect.

Takeover changes only this task note and adds contained read-only command
receipts. No product/build input changed, no Git commit/push or CI dispatch was
performed, and no frozen originals or dirty root-worktree files were touched.
This successor note is uncommitted and pending integration, not delivered on main.

## Authorized Standard Build, 2026-10-26

The user explicitly authorized FAST-RELEASE-BUILD-01 in the successor root
conversation after its exact nonpublishing APK/EXE scope was presented. This
supersedes the earlier authorization-pending state for this one build only;
it does not grant main integration, publishing, backend mutation or device work.

Remote preflight confirms `2febc00b15658bde055d2f1e05095809c1444f76` on the
exclusive development branch. The scoped standard-workflow inventory is empty,
so no prior standard result can be reused. Original receipts are
`.cache/records/standard-preflight-01.*` and `standard-existing-runs-01.*`.
Issue one dispatch with the parameters above; reconcile an uncertain receipt
read-only rather than issuing another dispatch. Standard results remain NOT_RUN
until the actual run and both platform jobs are observed.

### FAST-RELEASE-BUILD-01: Build-Only PASS

The interrupted execution issued exactly one dispatch, recorded by
`standard-dispatch-01.*`. Continuation only retrieved that run's terminal
status, artifact metadata and original console output; no second dispatch,
rerun or local build was performed.

Run [40309860485/1](https://github.com/Eitan-S-23/E-Track/actions/runs/40309860485)
completed/success at 2026-10-26T10:54:07Z. Exact head:
`2febc00b15658bde055d2f1e05095809c1444f76`, branch
`dev/flutter/fastpath-backend-20261026`, workflow `.github/workflows/build.yml`,
event `workflow_dispatch`. The original nonpublishing parameters are unchanged.
Both build logs explicitly report `adaptive-v2-candidate`. Version `1.0.62+88`
is source-bound; no independent binary version/application-ID readback is claimed.

| Gate | Observed result |
| --- | --- |
| Android job 121528195439 | All steps success, including analyze, full Flutter tests, release build, fixed signature verification and strict artifact upload. Tests: 783 passed, 16 skipped, 0 failed. Signing-selection regressions: 17/17 PASS. |
| Windows job 121528195349 | All steps success, including analyze, full Flutter tests, release build, packaging and strict artifact upload. Tests: 764 passed, 35 skipped, 0 failed. |
| Analysis | Both originals report `No issues found!`. |
| Pages job 121528197425 | Skipped, no executed steps. |
| Release/Cloudflare job 121531798205 | Skipped, no executed steps; no Release, R2 registration or deployment through this run. |

Original APK verification reports one signer and verified v2 scheme, using the
existing E-Track Development certificate SHA-256
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
This is fixed candidate signing, not a production-signing qualification.
APK bytes: 47429900; CI-reported APK SHA-256:
`4d6b4d8a4359c48b30a4eb6abcf1adbe192851827899421714c5074ae1a27536`.

Artifacts are bound by the API to this exact run/head. Their ZIP digests are
archive metadata, not interchangeable with the APK or EXE content hashes:

| Artifact | ID | ZIP bytes | ZIP SHA-256 | Expires (UTC) |
| --- | --- | --- | --- | --- |
| android-apk | 12643724663 | 25864416 | `1b019f1339cd637ccdd8f260a03945f4d0982ad3ab94f6f4c3f0702cf3bd8873` | 2026-11-09T10:53:57Z |
| windows-exe | 12644008839 | 20546309 | `d1d4471dd1b91d98d3ba14370f99b83f3a4fbc24989656b95f83d3ac818cf054` | 2026-11-09T10:53:13Z |

No APK/EXE bytes were downloaded, installed or launched on the local host.
Windows raw EXE SHA-256 and runtime verification remain unobserved; its actual
release build and upload are proved by this run, not by the older debug APK.

Warning accounting in the original console: 7 explicit diagnostic lines,
Windows 3 and Android 4. These comprise one Kotlin `jvmTarget` deprecation and,
on each host, `punycode`, `url.parse()` and Node-20 action deprecations.
There are 0 executed GitHub error annotations and 0 failed build steps. This
count excludes echoed shell branches and intentional negative-test diagnostics;
passing analysis is not a claim that all console output is warning-free.

All 18 standard-build command logs/receipts are preserved byte-for-byte under
[standard-40309860485](Flutter-release-fastpath-2026-10-26/standard-40309860485/).
The complete original console file `standard-download-logs.log` has 7246366
bytes and SHA-256
`06911550e9fca64a6d4759ade671b302a17d17e06b074fe238146cbd3d54ed7a`.
Terminal run, jobs and artifact originals are `standard-final-run.log`,
`standard-status-02.log` and `standard-final-artifacts.log` respectively;
adjacent `.json` files record the retrieval command and its exit code.

This closes only the authorized standard build/software artifact gate and
supersedes the earlier standard-build NOT_RUN statements. Independent review,
main integration, production qualification and real backend/device P3-5/P5
remain outstanding. BACKEND-READY-01 still needs the owner's selected compatible
forward firmware >30289, staging-channel authorization and permitted public
query/download route. Stop here pending those decisions, not another build.

Continuation output audit: only this task note, project-local command receipts,
the original-log archive and the existing wrapper's contained home/config/cache/
temp paths were selected for writes. No external filesystem output, move,
delete, Git commit/push, backend mutation or device action was selected.
The note/archive are uncommitted and pending integration, not delivered on main.

## Implementation Delivery Reconciliation, 2026-10-26

The user supplied the A/B/C assignment in this successor thread. Progress was
recovered from its exclusive branch, source diff and original receipts, not
assumed from an unavailable prior conversation. Current ls-remote again reports
main `91fed6bc` and development head `2febc00b`. The unchanged App/CI input set
still traces to stable product commit `57e6f064`.

Fresh read-only GitHub observations confirm development run 40295320180 is
success on both hosts, standard run 40309860485 is success with Android/Windows
builds passed and Pages/Release skipped, and both standard artifacts are still
unexpired with the recorded IDs, sizes and ZIP digests. The three new command
pairs are archived as `resume-*-current-01.*` beside the standard originals.
No dispatch, rerun, APK/EXE download or hardware observation was needed.

The prior successor's task note and 18 raw standard files were left uncommitted.
This owner preserves those bytes, adds only folder-local raw-byte/log inclusion
rules and a size/SHA inventory, then submits this task-scoped record on the
existing development branch under execution contract section 7.3.2. This is
not main integration or new production-build authority. The subsequent record
commit must not be described as the source of an APK built at `2febc00b`.

A and C's implementation/software-build deliverables are ready for independent
review. B's existing implementation and original backend probes were reconciled;
no backend product defect warrants a repair. The backend readings above remain
dated observations, not a new environment probe in this successor. Real P3-5
admission still requires root/configuration, firmware and network-policy owners
to bind the permitted staging channel, forward candidate >30289 and accessible
latest/download route. No previous activation or device authority was inferred
from a task note. Existing P3-4/P3-8 and P4-2/P4-4 completion stays unchanged.

This successor writes only this task's note, evidence-folder metadata/inventory,
copied exact receipts and contained wrapper outputs; branch commit/push uses
the authorized shared project `.git`. Global hooks are read-only inputs, with
their temporary/cache paths contained and optional chat notification disabled
for this command. No external writes, frozen-evidence edits, backend mutation,
device operation, local Flutter/Gradle build or main/tag push is selected.
