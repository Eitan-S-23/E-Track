# P4-1 Unattended Development

Status: IN_PROGRESS (whole card). Unattended development implementation and
validation are complete on `fa74905e84c489cccc248617d37ab9f56c8f961c`.
Implementation self-tests are not independent acceptance. Main integration,
real rehearsal and the retained external audit question are not declared complete.
Sole Spec: `docs/ota-prompts/prompt-P4-1-implementation.md` and its frozen references.

## Entry And Authority

- Baseline: local and remote main `b42d3e25db85d6aba397cb4d0fb34bb5b653904f`.
- P4-2 accepted product: `fc4fbbb8193fcc536ef408b7b662d44b30f869dc`; consume its
  actual v2 schema, scripts, versioned fixture, business handlers and tests.
- Exclusive branch: `dev/p4-1/unattended-20261015`; worktree:
  `D:/github/my/E-Track/.cache/p41-dev-20261015`.
- User authorizes scoped implementation/WIP commits, pushes as `Eitan-S-23`,
  existing checks/build-only Actions and project-contained evidence retrieval.
  No main merge, tag, Release, deployment, cloud resource/configuration write,
  device operation, external filesystem write or other-task work is authorized.
- Shared archive worktree, main's historical evidence, and the pre-existing
  initializing P4-1 worktree remain untouched. No reset/clean/stash is used.
- P3-5 is paused by this dispatch, not by a new dependency. P4-3/P4-4 are not
  started. The eventual configuration checklist is an interface handoff only.
- `.trellis` is absent. Do not create a competing task or Spec.

## Gap Register

| ID | Observed gap and invariant | Bounded action / owner | Feedback |
| --- | --- | --- | --- |
| P41-01 | `publish=false` skips release tooling; native Worker tests exclude `*.host.test.ts`. | P4-1 adds credential-free development execution in the existing firmware workflow; explicitly separate host script/migration and native workerd runs. | Final CI: host 34/34, pipeline host 20/20, native 156/156; separate commands and raw counts verified. |
| P41-02 | Workflow still supplies removed single-bin metadata flags and omits uploader asset/remote selectors. P4-2 scripts already enforce v2. | Replace only P4-1's consumers; retain one schema/backend. Enumerate other consumers without modifying their workflows. | In-scope consumer uses v2. Legacy workflow remains an explicitly recorded out-of-scope unsafe consumer. |
| P41-03 | No formal base provenance/patch byte validation/recovery packaging in the workflow. | Thin orchestration of existing finalize/pack/unpack/recovery owners; actual byte and negative tests before widening. | Byte 19/19, pack 8/8, golden 9/9 and actual GCC full/recovery preparation pass. Authoritative real base remains NOT_RUN. |
| P41-04 | Existing release step edits tags and clobbers assets, defaults to staging bucket, and has no production environment declaration. | Immutable publish/readback, explicit environment configuration, first-step gate and shared rehearsal path; no real publish execution this batch. | Pipeline host 20/20 and workflow 15/15 pass. External GitHub/R2 surfaces in those tests are doubles, not a real release/rehearsal. |
| P41-05 | Canonical rehearsal provenance/rebuild comparison and version monotonicity are not wired. | Preserve frozen canonical `runId`; audit-only execution id; fail before remote writes on inconsistent inputs. | Approved-envelope byte replay and changed provenance/hash/version negatives pass. Actual approval and cloud binding observations remain NOT_RUN. |
| P41-EXT | Actual isolated bindings/uploader credentials, approved formal base, rehearsal and independent approval unavailable. | P4-4/root configuration owner plus independent reviewer; keep real observations NOT_RUN. Do not retry expired login or D1 401. | NOT_RUN. |

## Batch Plan

1. Establish actual host/script/migration and native workerd feedback, including
   expected failures and no downstream effects. Commit a bounded WIP and inspect
   raw Actions steps, not just the run conclusion.
2. Add byte preparation and provenance validation through existing tools, then
   execute positive/negative byte and CLI tests.
3. Wire the same preparation/upload/register implementation into isolated
   rehearsal and gated production, verify ordering/failure/gates and all callers.
4. Run affected CI on the candidate commit, preserve originals and byte hashes,
   deliver configuration/real-rehearsal checklist, then request independent review.

Every meaningful batch obtains runtime feedback before further product changes.
Real R2/D1/Access, production-zero-side-effect snapshots and independent acceptance
are never inferred from fixtures or local doubles. P4-1 remains in progress.

## Initial Feedback

- npm mirror download failed with ECONNRESET; original `batch1-npm-ci` output is
  preserved. The pinned install succeeded (87 packages, exit 0) after explicitly
  switching the registry host to npmjs with integrity still enforced. No lockfile
  or tool version changed.
- Initial host run: migration 17/17 PASS, script suite failed to import (exit 1).
  Vite's `hashbangRE = /^#!.*\n/` does not strip CRLF shebangs, while direct Node
  imports succeed. These mode-100644 files are always invoked with Node. Removing
  only their unused shebangs fixes the cross-platform test entry without changing
  schema or business behavior; all three firmware CLI consumers are covered.
- Windows native run: zero tests, three workerd startup access violations (exit 1),
  consistent with the accepted P4-2 host limitation. No system runtime installation
  is authorized or attempted. Native evidence must come from Linux Actions.
- Build outputs move from `/tmp/etfw` to the Actions workspace `.cache/etfw`;
  the build inputs, targets and path-length setting are unchanged.

## Milestone 1: Runnable Feedback

- WIP `1735f9d4da8fc423f4fe8364cd1cdd2f333941d7`, run `38630966396`:
  explicit host script/migration tests 34/34, native workerd 156/156, Worker
  typecheck and GCC App/Boot build passed. Release job skipped under
  `publish=false`; no cloud credentials in the development job.
- Raw ZIP is `.cache/github/batch1-logs.zip` (234558 bytes). Its actual command
  lines, CLI output, `SQL_REJECT` constraints and separate 34/156 count lines were
  inspected. Duplicate job/step log copies in the ZIP are not additional tests.
- Negative originals include bad raw digest/missing artifact migration rejection
  before SQL writes, R2 collision rejection without overwrite, missing readback,
  skip-readback CLI exit 2 and actual native D1 ready/uniqueness constraints.
- Local repaired host run is also 34/34 (exit 0); local typecheck exit 0.

## Batch 2: Byte Preparation

The production preparation script calls the existing finalize, full/patch pack,
unpack and recovery helper. It checks subprocess exit/stdout, actual candidate
bytes, raw/base identities, recovery tail/header and same-run GCC App/Boot inputs.
The P4-2 builder remains the sole registration schema and naming implementation.

`--reproduce-from` reuses an approved envelope only after recomputed header plus
ciphertext equals every reference byte under the configured key. It is not a
nonce override; changed plaintext, key, header or corrupt reference fails before
output. Normal packaging keeps its random nonce. The vendor algorithm is not
changed. Its scratch cwd is contained and its success stdout is checked.

Local self-tests: production preparation 14/14 (actual Python/vendor processes),
package/replay 8/8, exits 0. The first Python run had 7 passing cases and one
harness error caused by `tempfile` caching a deleted test directory; the scoped
test override restores that cache per case. Original failure is preserved as
`batch2-pack`, corrected run as `batch2-pack-fixed`; no assertion was weakened.
Linux byte-generation CI is required before treating the host adapter as tested.

The Windows test artifacts are deliberately synthetic, not an approved formal
base or a rehearsal. The production transport must obtain and verify actual
source provenance before calling this offline preparation entry.

Linux byte feedback: commit `84aa6a7ef72955b3248d07fad7de548eb6868798`, run
`38632973096`, passed the existing vendor CMake adapter build, 8 package tests,
14 byte-preparation tests, 34 host tests, 156 native tests and GCC App/Boot build.
Original ZIP `.cache/github/batch2-logs.zip` is 252337 bytes. This run still has
no real R2 upload, D1 registration or rehearsal.

## Batch 3: Publication Wiring

- `firmware-release.mjs` captures same-run GCC App/Boot identities and is the
  common rehearsal/production entry. Checks additionally run its development
  path on the actual GCC build without cloud credentials or an invented base.
- Formal base retrieval enumerates real formal GitHub releases, resolves the
  tag's commit, selects the preceding version and downloads the whole pinned
  App/recovery source. The normal byte verifier then validates the final image.
- Production independently binds the approved rehearsal run/attempt, metadata,
  evidence and preparation hashes; its current execution id is audit-only.
  App/Boot inputs and the original envelope must reproduce exactly before any
  cloud write. Rehearsal retries require their prior attempt's original artifact.
- The GitHub client never replaces an asset or retargets a tag. A new Release is
  populated as a draft, each asset is read back, then the published inventory and
  every published byte are rechecked. Rehearsal has no GitHub write path and uses
  a read-only token. Staging-only secret names avoid repository production-secret
  fallback; both environments map to the same runtime configuration interface.
- D1 monotonicity/unresolved-legacy and Worker environment checks precede writes.
  The shared uploader verifies every byte before setting any local ready flags;
  the actual P4-2 register client is last, followed by an idempotency replay.
  Abort/failure prevents later steps. Shared remote binding startup remains NOT_RUN.

Local pipeline tests are 19/19, using the actual P4-2 handler and SQLite host
adapter. GitHub/R2 external surfaces are doubles, not remote observations. The
first 13-case run had one oracle failure: an empty database legitimately gains
two unpointed revision-zero channels on first registration. The corrected oracle
checks those exact defaults and byte-identical channel state on replay, rather
than treating initialization as a promotion. The original failure is preserved.
Shared script regression is 17/17 and Worker typecheck exits 0.

Workflow tests are 15/15, including nine actual Bash gate executions with expected
0/1/2 exits and an actual execute-CLI rejection of a checks context before cloud
entry. An initial harness dependency error (`yaml` is bundled, not an installed
Worker module) was preserved and fixed using explicitly pinned PyYAML 6.0.3.
No cloud gate was opened to test its failure. This batch's CI result is recorded
in Final Hardening Feedback below.

## Shared Consumers

| Consumer | Impact / disposition | Next owner |
| --- | --- | --- |
| `.github/workflows/firmware-build.yml` | In scope; replaces removed single-bin flags with the shared v2 array pipeline, explicit bindings and immutable publication. | P4-1 |
| `.github/workflows/mcu-firmware-release.yml` | Out of scope; still creates/edits/clobbers a Release BEFORE passing removed `--firmware-file`/`--device-model`/`--version-code` flags to the v2 builder, and its uploader omits `--asset`/`--remote`. It also has an optional real deploy path. Do not dispatch it as a fallback; retire/disable or separately migrate it before production use. No schema downgrade or incidental workflow edit was made here. | Root / legacy workflow owner |
| `worker/test/firmware-scripts.host.test.ts` | Existing builder/uploader/register module and CLI consumer; explicitly executed separately from native tests. | P4-1 regression; P4-2 source ownership preserved |
| `update-service/docs/README.md` | Already documents v2 explicit assets and readback; no compatibility fallback added. | Root / backend documentation owner |
| Existing pack callers and golden vectors | Default random packaging remains unchanged; optional replay is fail-closed. Vendor scratch cwd and success checking now apply to all callers. | P4-1 tests; other task owners retain their frozen artifacts |

The current checked-in Worker environments use `GITHUB_REPO=Trace`, whereas this
firmware workflow publishes from `Eitan-S-23/E-Track`. A separately isolated
firmware environment must configure the matching repository without breaking the
Trace App updater's bindings. Existing staging D1 is not assumed disposable or
independent. P4-4/root must verify actual Worker/D1/R2 identity and permissions;
this implementation neither changes nor claims those deployed settings.

## Final Hardening Feedback

Batch 3 CI `38639059128` on `81b42bd5d9b61b36145f2cf2fe01ac63b67e4453`
passed: host 34, pipeline host 19, native 156, workflow 15, package 8 and byte 14.
It additionally prepared full/recovery from the actual 605072-byte GCC App and
14724-byte Boot input; no formal base was invented. Both cloud jobs were skipped.
Compiler warnings remain in the originals; zero-warning success is not claimed.

The cross-layer check then added explicit ETU outer target/base/hardware/length
checks through the existing parser, identity snapshots against late asset swaps,
error-over-success stdout rejection and register request-id binding. The local
byte suite now passes 19/19, pipeline host 20/20, shared script host 17/17 and
golden-vector compatibility 9/9; Worker typecheck exits 0. The legacy golden
fixture's development-key warning is expected and retained. Production preparation
still requires its explicit key and never uses that fallback. Final CI and its
preserved failed predecessor are recorded below.

## Configuration Consumption Handoff

This is an inventory of the implemented interfaces, not a new Spec, a P4-4 task
start or permission to configure/deploy anything. No values below were set or
retrieved from Cloudflare in this session. The shared entry is
`node .github/scripts/firmware-release.mjs execute`; `capture` binds build inputs,
and `development` uses a non-installable test-key path with cloud entry absent.

| Runtime name | GitHub source / scope | Required verification by configuration owner |
| --- | --- | --- |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | In `firmware-rehearsal`, secrets `FIRMWARE_REHEARSAL_CLOUDFLARE_ACCOUNT_ID` / `FIRMWARE_REHEARSAL_CLOUDFLARE_API_TOKEN`; production uses the unprefixed secrets in `firmware-production`. | Exact account and least-privilege target R2 read/write plus D1 read. Qualify any additional Wrangler remote-binding preview requirement rather than guessing or broadening permissions. Actual remote proxy startup is NOT_RUN. |
| `TRACE_UPDATE_SERVICE_URL`, `TRACE_DEPLOY_TOKEN` | Rehearsal secrets `FIRMWARE_REHEARSAL_TRACE_UPDATE_SERVICE_URL` / `FIRMWARE_REHEARSAL_TRACE_DEPLOY_TOKEN`; production uses unprefixed names. | Credential-free HTTPS origin; `/healthz` must report `staging` / `prod`; real Worker `DEPLOY_TOKEN_SHA256` must match. Verify actual Worker bindings, not only its environment label. |
| `OTA_AES_KEY` | Rehearsal secret `FIRMWARE_REHEARSAL_OTA_AES_KEY`; production secret `OTA_AES_KEY`. | Explicit 32-hex approved device/package key for key slot 1. The approved envelope must reproduce under the configured key. Separate secret storage does not permit different package bytes; never copy a test key or expose values. |
| `TRACE_R2_BUCKET` | Rehearsal variable `FIRMWARE_REHEARSAL_TRACE_R2_BUCKET`; production variable `TRACE_R2_BUCKET`. | Rehearsal must be exactly `trace-update-staging-releases`; production must use its explicitly approved other bucket. Inventory actual bindings and zero production effects independently. |
| `TRACE_D1_DATABASE_ID`, `TRACE_D1_DATABASE_NAME` | Rehearsal variables prefixed `FIRMWARE_REHEARSAL_`; production unprefixed variables. | Exact independently scoped migrated v2 database. Preserve P42-EXT-02 legacy/backfill authority; unresolved pointers or unknown inventory are not an empty database. No D1 migration/write is done by P4-1 except the real register API. |
| `OTA_PREVIOUS_RELEASE_JSON` | Environment variable in each release environment. | Approved descriptor fields: `isFormalRelease`, `kind` (`app` or `recovery`), canonical `versionName`/`versionCode`, `releaseTag`, `commitSha`, raw `imageSha256`, exact `sourceSha256`/`sourceSizeBytes`, immutable `sourceUrl`. An App source is `X-Track-App-GCC.bin`; recovery uses `recovery-vVERSION.bin` with separate file and stripped-image hashes. Populate from real authoritative provenance, not these tests. The client independently enumerates releases, resolves the tag and reads all source bytes. |
| `TRACE_FIRMWARE_MIN_APP_VERSION_CODE`, `TRACE_FIRMWARE_MIN_PROTOCOL_VERSION` | Explicit environment variables, no guessed defaults in release execution. | Canonical integers in 0..2100000000 and 0..255; choose values compatible with the approved clients and device. Hardware/layout/min-Boot remain the current compiled 1/1/1 target, not arbitrary metadata claims. |
| `OTA_BOOT_CHAIN_READY` | Repository/environment variable. | Exactly `false` for rehearsal. Only the repository owner may later set `true` after independent approval AND P5; this session never changes it. |
| `OTA_APPROVED_REHEARSAL_RUN_ID`, `OTA_APPROVED_REHEARSAL_ATTEMPT`, `OTA_APPROVED_REHEARSAL_METADATA_SHA256`, `OTA_APPROVED_REHEARSAL_EVIDENCE_SHA256` | Production approval variables. | Independent reviewer/owner binds the successful original run/attempt and exact metadata/evidence bytes. Dispatch `approved_rehearsal_run_id` must match; current production execution id never enters canonical metadata. |
| `firmware-rehearsal`, `firmware-production` | Protected GitHub environments. | Rehearsal receives no production cloud/publish credential. Production retains independent environment approval. Secret prefixes deliberately prevent fallback to repository production secrets. No environment/policy/secrets were configured here. |
| Worker `GITHUB_OWNER` / `GITHUB_REPO`, cutover and signing bindings | Existing P4-2 deployment configuration, not new P4-1 output fields. | Dedicated firmware origin must accept `Eitan-S-23/E-Track`; retain the actual P42-EXT-03 cutover/HMAC/legacy gates and protect the Trace App update environment. |

Rehearsal produces `p41-rehearsal-RUN_ID-ATTEMPT` Actions artifacts; later production
downloads that exact artifact and verifies its successful run/attempt and approved
hashes. A retry without the original artifact stops, rather than generating new
nonces over partially uploaded keys. Archive originals before their 14-day expiry.

## Remaining Real Observations And Owners

1. Root assigns a non-implementer to review this bounded branch, original tests
   and the sole P4-1 Spec. Self-tests do not count as that review or acceptance.
2. P4-4/root prepares and independently inventories actual isolated Worker/D1/R2,
   credentials, environment approval and the official finalized base. The prior
   D1 401/code 10000 and expired login were not retried. P42-EXT-02 stays with the
   migration owner plus OTA reviewer; P4-1 does not hand-write or activate D1 rows.
3. Under separate real-operation authority, P4-1/P4-4 share ONE staging rehearsal:
   actual three assets, complete R2 readback, real ready and idempotency responses,
   and external before/after production D1/R2/channel/GitHub Release snapshots.
   The rehearsal job itself cannot collect production snapshots using production
   credentials; an independently authorized observer supplies those originals.
4. Independent acceptance adjudicates that evidence under the existing execution
   contract. All these real observations remain NOT_RUN, so P4-1 stays in progress.
   Production promotion remains after P5/owner/environment approval. Do not start
   P3-5 or P4-3 as a continuation of this development batch.

For formal component-profile admission, do not use `Firmware` alone: it omits the
new `.github/scripts/` entry and backend script consumers. Existing base groups
`Production` + `Validation` cover them and the real runners; a narrower profile
change belongs to the governance owner with its own checks, not an incidental
edit here. No profile, frozen Spec or historical bundle was changed.

## Preserved Final-CI Harness Failure

Run `38641534498` on `1eed86222e1ac3ef14281fc1b1b4a26a94b73375` is FAILED,
not a delivery PASS. GCC build and real-GCC packaging, host 34, pipeline host 20,
native 156 and package 8 completed successfully. The newly wired legacy golden
suite then failed to import `etu_pack`: its existing `tools` path is lowercase,
whereas the tracked directory is `Tools`. Windows' case-insensitive filesystem
had concealed this. Workflow/19-byte tests were skipped after that failure.

The remediation is confined to the P4-1 workflow invocation:
`PYTHONPATH="$GITHUB_WORKSPACE/Tools" python3 -B tests/ota-vectors/test_vectors.py`.
Historical vector source/bytes and assertions are unchanged. The original failed
ZIP is `.cache/github/batch4-logs.zip` (262496 bytes), with the failure at the
package/golden step. This is a test-entry portability repair, not a firmware or
cloud product failure; the changed invocation receives a new CI run.

## Final Development Verification

Tested product commit: `fa74905e84c489cccc248617d37ab9f56c8f961c` on
`dev/p4-1/unattended-20261015`. Firmware run
<https://github.com/Eitan-S-23/E-Track/actions/runs/38642386248> is SUCCESS.
Both release jobs are SKIPPED under the explicitly dispatched `publish=false`,
`rehearsal=false`; the P3-4 candidate-only steps are also skipped. Actual job/step
metadata and console commands, rather than only the workflow conclusion, were
inspected. No real `publish=true` dispatch was used as a negative test.

The final Ubuntu runners report 24.04.5, Node 24.21.0 and npm 11.19.0. The GCC
action consumes Arm GNU 13.3.Rel1. Let `W` mean
`app/bluetooth_flutter_Trace/cloudflare/update-service/worker`; other commands
below run at the repository root. Counts are separate suites, not an aggregate
claim that repeats across runs or duplicate ZIP members are new tests.

| Scope / cwd | Actual command | Final result |
| --- | --- | --- |
| Script and migration host / W | `npm test -- --config test/vitest.host.config.ts test/firmware-scripts.host.test.ts test/firmware-migration.host.test.ts` | 34/34, exit 0; 17 script plus 17 migration tests |
| Pipeline host / W | `npm test -- --config ../../../../../.github/scripts/p41-host.config.mjs` | 20/20, exit 0; actual P4-2 handler with SQLite host ports |
| Native Worker / W | `npm test -- --reporter=verbose` | 156/156, exit 0; native workerd D1/R2/register/Admin tests, not host doubles |
| Worker types / W | `npm run check` | exit 0 |
| Package replay | `python3 -B tests/ota/test_firmware_pack.py` | 8/8, exit 0 |
| Existing golden vectors | `PYTHONPATH="$GITHUB_WORKSPACE/Tools" python3 -B tests/ota-vectors/test_vectors.py` | 9/9, exit 0; historical test bytes unchanged |
| Workflow and gates | `node --test tests/ota/test_firmware_workflow.mjs` | 15/15, exit 0; actual Bash gates and execute-CLI rejection included |
| Production preparation | `node --test tests/ota/test_firmware_release.mjs` | 19/19, exit 0; actual finalize/pack/unpack/recovery processes |
| GCC App and Boot | `cmake -S MDK-ARM_F435/cmake-generated -B "$BUILD_DIR" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024`, then `cmake --build "$BUILD_DIR" --target X_Track_App_GCC X_Track_Boot --parallel` | configure/build exit 0, `SOURCE_DATE_EPOCH=1786320000` |
| Actual GCC packaging | `node .github/scripts/firmware-release.mjs capture ...`, then `node .github/scripts/firmware-release.mjs development ...` | exit 0; seven real tool steps, complete argv/stdout/stderr identities in the original verification JSON |

The existing build job also ran its Boot/OTA/P3 host regressions and layout/handoff
assertions. These are existing CI host checks, not reopening old cards or new
device observations. No local Flutter/Gradle/APK build or simulator build was
performed for this task.

Backend run <https://github.com/Eitan-S-23/E-Track/actions/runs/38641540543>
passed Worker, Public Pages and Admin facade checks, including 156 native tests,
on `1eed86222e1ac3ef14281fc1b1b4a26a94b73375`. Its backend/workflow inputs are
byte-unchanged in `fa74905` (`git diff --exit-code` over those paths returned 0).
This is identified separately, not relabeled as a run on a different SHA or
counted as another 156 unique tests.

Compiler/linker diagnostics in the final build step: **640 warnings, 0 errors**.
The same 640 warning lines occur in each of the four preceding firmware runs;
firmware sources were not modified here. Vendor bsdiff adds **6 format warnings**.
The native log also retains 21 error-like constraint/rollback diagnostic lines
inside passing negative tests, including 17 explicit `SQL_REJECT` anchors.
These are not compiler failures and were not suppressed or removed. Counts use
one original step/aggregate representation, never both duplicate ZIP copies.

GCC size output: App `text=603632 data=940 bss=561992 dec=1166564`; Boot
`text=14720 data=4 bss=9780 dec=24504`. App FLASH is 605072/983040 bytes. The
linker reports RAM/overlay reservations at 100%; this is not a new runtime RAM
measurement. All warnings remain visible to the independent reviewer.

## Original Evidence And Artifact Identity

The tracked directory `docs/ota-exec-notes/P4-1-ci-2026-10-15/` contains all five
firmware ZIPs, including failed run `38641534498`, the final backend ZIP, actual
job/run API responses, four final artifact ZIPs and local failure/success outputs
with closed process receipts. `inventory.json` binds 153 files, excluding itself;
the directory contains 154 files and 5481822 bytes. Its own SHA-256 is
`b2987506a1ac1dcf620f6c47d5a984240210c9dede0c838b796f776531565293`.

`artifact-members.json` records length, SHA-256 and original ZIP timestamp for all
591 members in the four artifact ZIPs. Every downloaded ZIP exactly matched the
GitHub API digest, size, run ID and source commit. `ci-inspection.json` binds the
actual counts and selected byte observations to these originals. Selected metadata
and verification files are exact extracted bytes, not rewritten summaries.
`.gitattributes` preserves raw bytes; raw console whitespace must not be normalized
to make `diff --check` quiet. Source/prose checks exclude those original streams.

The actual GCC development artifact is intentionally not installable or a formal
release. It has no invented previous formal base, so its patch result is null;
all `r2Verified` flags remain false. Its retained `DEVELOPMENT-ONLY.json` explicitly
marks this boundary. The following are hashes of downloaded original bytes:

| Actual GCC item | Bytes | SHA-256 |
| --- | --- | --- |
| Placeholder App `X-Track-App-GCC.bin` | 605072 | `5f7c42bd43acef12a262e53c378fa1fee3f44a6571c081a373d60b494d23fe8e` |
| Boot `X-Track-Boot.bin` | 14724 | `3554e193f498d23210f5ef32e09de64575b7cd39104fafcc950740e5e8a7ec34` |
| Finalized `app-final.bin` | 605072 | `aaf5ccdb047ef8b3ff4ae0837f9593ceca857d90c98ea0bc09360e411bf4196f` |
| `e-track-at32f435-v3.2.7-full.etu` | 285764 | `f81c9dce2655a64031fab02b44ac1ba5a68ef96abf214133f3b8096643e2958d` |
| `recovery-v3.2.7.bin` | 605080 | `81f40793e84be3fc90313e8425e0269180bfbcb690c2819f4c82c65ab8ec0c05` |
| Unverified v2 metadata | 1441 | `0850c7b9fa35e8fd4ace12f69ddf4eaaa17b58614e318a0030d6beef75284bb8` |
| Preparation verification JSON | 7034 | `6c85dfeddc3ee5b9e7098b31042c19b29b79e374db3ed0e3a96c81c0f5fb3bce` |

Original App/Boot ZIP timestamps are `2026-10-14 21:43:54`; finalized App/metadata
are `2026-10-14 21:44:04` (ZIP fields have no timezone field). GitHub artifact
creation timestamps are separately retained in the API response. These are not
the local download times. Raw App/Boot input manifests and all eight GCC output
files remain in their original ZIPs.

The three-asset positive test is separately identified as synthetic: original
`BYTE_FIXTURE` path `firmware-release-tests/case-aTieJp/prepared/` in artifact
`11930178698`, using the P4-2 fixture's `Trace` identity. No such source is approved
as the production base. Its full/patch applied outputs both equal the exact
8192-byte finalized target, raw SHA
`d8b49b46428a5c0873d6c783daf4f3789d4678117e68ec73ead77f300c4b5cb5`.

| Synthetic item | Bytes | SHA-256 |
| --- | --- | --- |
| `e-track-at32f435-v2.8.1-full.etu` | 202 | `946a097406b3cd467783df0594e4241396b38ce36465dc73497b5a43d0cbedf6` |
| `e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu` | 208 | `06775c91a8d118394bccdeafb0ad15eb3feece1239a2c1b146a348a7a7bee191` |
| `recovery-v2.8.1.bin` | 8200 | `0171c47db39f84b0e9af139f3265847e403f7597cc3df5fa430ef6ac0525964c` |
| Unverified v2 metadata | 1989 | `476920e84f39d7b83dd2941bfb6d0eddf7857a9fd8617070bb03365df741b800` |

Archival verification additionally rechecked every successful tool step's exit
code and stdout/stderr digest, all asset sizes/digests and full/patch/recovery App
byte equality. It did not rerun generation, cloud operations or a successful CI.
One App artifact download terminated before producing a file; the exact artifact
ID was retrieved once more after other downloads succeeded and its digest was
verified. That collection failure is not a failed firmware observation.

## Discriminating Negative Evidence

Final `batch5-logs.zip`, the test artifact's step originals and the tested source
assertions jointly demonstrate the following, rather than only a green summary:

| Negative | Observed oracle and downstream boundary |
| --- | --- |
| Wrong GCC/base digest, invalid/nonformal/ETU base | Real validation rejects; no finalized target or registration metadata is produced. |
| Patch subprocess exit 0 with failure stdout | `patch-apply failed exit/stdout` is rejected; recovery does not start. |
| Patch reports success but candidate bytes differ | Byte comparison rejects; no metadata is emitted. |
| Corrupt recovery tail or ETU outer identity/length | Existing parser/helper verification rejects before metadata. |
| Missing assets or late asset replacement | Builder/snapshot checks reject rather than recording new unchecked digests. |
| Missing key through actual CLI | Original `PREPARATION_CLI` records positive exit 0 and missing-key exit 2 with `INVALID_PARAMETER`. |
| R2 put appears successful but readback is missing | Actual shared uploader rejects; no persisted verified metadata or D1 registration. |
| Cancellation after first upload | Later uploads and registration never run. |
| Conflicting register metadata and duplicate/missing-ready assets | Real handler/SQLite host tests and separate native D1 constraint tests reject; no partial ready/channel promotion is claimed. |
| Wrong approved run/hash/commit, wrong version or release gate | Shared pipeline and actual local Bash/CLI tests fail before publishing; no real production dispatch is used. |

## Write, Process And Handoff Audit

- Final read-only remote/local main is still
  `b42d3e25db85d6aba397cb4d0fb34bb5b653904f`. The shared root remains on
  `archive/p34-root-before-delivery-20261014` at `cb317affcd291695f42271084b4b305b0d7e6f8b`.
  Its index SHA-256 remains
  `2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd`, with the
  original `2026-10-12T19:53:21.544Z` mtime. Other worktrees were not changed.
- All selected implementation/cache/test/download/archive outputs are in this
  exclusive worktree. Normalized paths and reparse parents were checked before
  writing, including the archive's exact 153-target plan. The only parent-root
  writes permitted are this branch/worktree's own Git metadata, not another index.
- `local/handoff-write-audit.json` records 34 closed local child receipts, no
  receipt PID still present and no workerd/bsdiff/bspatch helper left running.
  Evidence processing is foreground and bounded. No device collector was started.
- No temporary credential file was created; the selected GitHub identity was
  verified as `Eitan-S-23` and its token lived only in process memory. No Cloudflare
  credential refresh/login was attempted. No credential/configuration cache was
  copied into the evidence, and the archive credential-pattern check passed.
- **P41-AUDIT-01, ATTRIBUTION_UNRESOLVED:** the metadata-only external cache audit
  found `C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
  modified at `2026-10-14T21:55:19.828153Z`. It is a Windows PowerShell startup
  cache. All task-selected shells use `cmd.exe`, `login:false`; the bounded
  read-only Windows event query confirms an engine start/stop then, but contains
  no current-worktree/helper reference. The writer is not established. No cleanup,
  move or overwrite was attempted, and an unqualified machine-wide "no external
  writes" claim is not made. Root owns cross-session/host attribution; any cleanup
  still needs path-specific user authorization. Other inspected npm/Wrangler/GitHub
  CLI/crash cache files had no mtime updates since this worktree's creation.

The final delivery is record/evidence-only after the tested product SHA; no
rebuild or repeated product tests are justified by those records. The branch is
pending main integration, which is not authorized in this session. Root should
hand this stable batch and its original evidence to a non-implementer for bounded
review, without an extra mandatory freezing agent. The configuration handoff and
real-observation owner list above remain the next steps. P4-1 stays IN_PROGRESS;
P3-5, P4-3 and P4-4 were not started as tasks.
