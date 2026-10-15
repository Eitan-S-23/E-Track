# P4-1 Unattended Development

Status: IN_PROGRESS (whole card). Unattended development is COMPLETE on product
`ae6cd49c2f756dd9094ee390121fc0825dbbceac`: actual PR checks passed and the
non-implementing reviewer closed all three required repairs. See PR Remediation
Closure below. Earlier dispatch successes and PR/red-test failures remain intact.
This bounded development review is not whole-card acceptance. Main integration,
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

## PR And Independent Review Repair Batch

Draft PR: <https://github.com/Eitan-S-23/E-Track/pull/27>, head
`55eac1d49851b9024d6b7fcfb078e5fbae8fc5a9`, base
`b42d3e25db85d6aba397cb4d0fb34bb5b653904f`, synthetic merge
`bcaaeb6106b915d06a7281c2625eebaf35f8a56c`.
Firmware PR run `38650328601` failed at version extraction; release-development
checks passed and both cloud jobs were skipped. Governance PR run `38650328602`
failed one of 126 governance regressions; both host-helper jobs passed. These
failures do not overwrite the earlier successful dispatch observations.

| ID | Required repair and invariant | Current feedback / owner |
| --- | --- | --- |
| P41-REVIEW-01 | Actual PR source `v2.7` fails strict three-part parsing. Normalize that legacy source only for non-release checks without an explicit input; never infer a formal/rehearsal version, accept suffixes or let huge integers wrap. | CLOSED by independent delta review: real Bash 39/39 locally and in PR CI; actual PR version is `2.7.0-nightly.310`. |
| P41-REVIEW-02 | GitHub's by-tag lookup finds published releases, so an interrupted untagged draft cannot resume. Enumerate bounded drafts, require a unique exact full-commit identity, validate existing bytes, never retarget a tag. | CLOSED by independent delta review: actual production client 33/33 locally and in PR CI, including 0/1/3-asset recovery and no-mutation rejection cases. |
| P41-REVIEW-03 | Readiness row already admits P4-1, but the exact governance expected set and section 9 dispatch registration were not updated together. | CLOSED: only P4-1 and its explicit dispatch record were added; equality and other task states unchanged. Local 22/22, main CI governance suite 126/126, independently checked. |

The non-implementing reviewer independently checked all 154 original archive
files, the 153 inventory bindings, four ZIP identities and all 591 members, tool
stream hashes, actual byte identities, counts and warnings. This is evaluation
of existing originals, not a new build, real rehearsal or whole-card PASS. The
same reviewer subsequently adjudicated the repaired delta after local and PR
feedback; its final message is preserved in the new archive below.

The local red/green batch used the actual YAML Bash version step and production
GitHub client, not a separate release implementation. Logs and closed receipts
are under `.cache/logs/` pending archival with the new CI originals:

| Command (root unless noted) | Before repair | After repair |
| --- | --- | --- |
| `node --test tests/ota/test_firmware_workflow.mjs` | `p41-version-red`: 31 pass, 8 fail, 39 total; exit 1 | `p41-version-fixed`: 39/39; exit 0 |
| Worker cwd: `node node_modules/vitest/vitest.mjs run --config ../../../../../.github/scripts/p41-host.config.mjs` | `p41-draft-red`: 22 pass, 11 fail, 33 total; exit 1 | `p41-draft-fixed`: 33/33; exit 0 |
| `python -X utf8 -B tests/ota/test_acceptance_bundle.py PostP26SpecGovernanceTests` | `p41-gov-red`: 21 pass, 1 fail, 22 total; exit 1 | `p41-gov-fixed`: 22/22; exit 0 |
| Worker cwd: `node node_modules/typescript/bin/tsc --noEmit` | Not repeated before repair | `p41-types-fixed`: exit 0 |

Draft interruption cases retain 0, 1 or 3 uploaded assets, resume release ID 7
and upload only the remaining 3, 2 or 0 assets. Existing bytes are unchanged and
the actual client completes its published-inventory/full-byte checks. Wrong
draft target, mutable branch target, notes, prerelease, duplicate draft or tag
conflict fail before any mutation. A tag changed during upload fails before the
publish PATCH. A published release still requires its tag. These GitHub surfaces
are explicit HTTP doubles, not actual Release operations or rehearsal evidence.

The pre-repair version log also proves the old code accepted `2.7.0-rc.1` and
wrapped `18446744073709551616.0.0` to code 0. Both now exit 1 without writing any
step outputs; the maximum `429496.72.95` still yields 4294967295. Only implicit,
non-release legacy source `v2.7` becomes `2.7.0`; MCU source is unchanged.

The caller rescan found no new consumers: the changed GitHub client is imported
only by `.github/scripts/firmware-release.mjs` and this host suite. Both release
environments continue to use that same entry. The legacy workflow and other
P4-2 script consumers retain the dispositions in the consumer table below.
The next PR synchronization is checks/build-only: both cloud jobs require a
dispatch event; backend/governance have no deployment; App path detection excludes
these non-App files and its Release/Pages paths exclude PR events. No separate
`publish=true` validation or redundant dispatch is planned.

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
| `.github/scripts/firmware-release.mjs`, `tests/ota/firmware-pipeline.host.test.ts` | Sole callers of the new GitHub client; formal-base lookup remains strict, both formal execution modes retain the shared entry, and the host suite exercises real client draft recovery. | P4-1 |
| `.github/workflows/mcu-firmware-release.yml` | Out of scope; still creates/edits/clobbers a Release BEFORE passing removed `--firmware-file`/`--device-model`/`--version-code` flags to the v2 builder, and its uploader omits `--asset`/`--remote`. It also has an optional real deploy path. Do not dispatch it as a fallback; retire/disable or separately migrate it before production use. No schema downgrade or incidental workflow edit was made here. | Root / legacy workflow owner |
| `worker/test/firmware-scripts.host.test.ts` | Existing builder/uploader/register module and CLI consumer; explicitly executed separately from native tests. | P4-1 regression; P4-2 source ownership preserved |
| `update-service/docs/README.md` | Already documents v2 explicit assets and readback; no compatibility fallback added. | Root / backend documentation owner |
| Existing pack callers and golden vectors | Default random packaging remains unchanged; optional replay is fail-closed. Vendor scratch cwd and success checking now apply to all callers. | P4-1 tests; other task owners retain their frozen artifacts |

The final executable-caller rescan also identified these exact shared-tool sites:
`Tools/ota/p34-acceptance/reference.py`, `tests/ota/test_ota_update.py`,
`tests/ota/p3_2_verify_build.py`, `tests/ota-vectors/gen_vectors.py`,
`tests/ota-vectors/test_vectors.py`, `tests/ota/test_firmware_pack.py`,
`tests/ota/test_firmware_release.mjs`, `tests/boot/test_prepare_bootstrap_app.py`,
`Tools/jlink/deploy-ota-bootstrap.ps1`, `Tools/jlink/flash-recovery-container.ps1`,
`.github/scripts/firmware-byte-check.py` and `scripts/prepare-firmware-release.mjs`
under the update service. Finalize/recovery interfaces and default pack behavior
are retained; the changed optional replay/vendor-check paths have actual package
and byte tests. Existing golden tests ran 9/9 via the scoped `PYTHONPATH` repair.
The historical vector generator also uses the lowercase `tools` path; its owner
should correct that invocation if Linux regeneration is separately needed. It
was not run and no historical vectors, accepted P3-4 campaign or device consumer
were regenerated/reopened to exercise unchanged APIs.

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

1. The bounded non-implementer candidate review is COMPLETE on `ae6cd49`; its
   original verdict is below. This does not supply the still-missing independent
   adjudication of a real rehearsal or count self-tests as independent execution.
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

### Delivery And Audit Follow-Up

Evidence/record commit `4c149e7810f816316dc038398f70642565a9391e` was pushed as
`Eitan-S-23` and its exact remote branch SHA was read back. All 154 evidence files
also match their staged Git blob bytes; product-input diff from `fa74905` is empty.
The two subsequent task-record changes do not alter this immutable archive or
the tested source. Final source/prose `diff --check` exits 0; Git's two ordinary
LF/CRLF notices do not apply to the byte-preserved evidence.

P41-AUDIT-01's last cache timestamp is `2026-10-14T22:10:18.610491Z`, not unchanged
since the first audit. A bounded metadata-only event inspection found Engine 400
starts at `21:55:19.4687459Z` and `22:10:18.1941546Z`; both HostApplication values
have SHA-256 `f93c863cedace81dae5c45c428f5b556d8d5c3564cbd12c9a69dceb747696302`
and include the `Export-StartLayout` cmdlet. Neither references this worktree or
its helpers. This narrows the observed command but does not establish its invoking
process or grant cleanup authority. The original audit is retained unchanged.
Root can reconcile that exact command/two event times rather than repeat product
tests or scan unrelated credentials. At the post-push check, all 36 then-existing
local child receipts were closed, none of their PIDs remained and the shared root
index still matched its entry SHA.

## PR Remediation Closure

Current tested product: `ae6cd49c2f756dd9094ee390121fc0825dbbceac`, pushed as
`Eitan-S-23` to `dev/p4-1/unattended-20261015`. PR #27 remains DRAFT and unmerged.
Its actual CI checkout is merge `46934e6567616786e4b4e104d9ec6f7396feb2f3`, with
parents `b42d3e25db85d6aba397cb4d0fb34bb5b653904f` and `ae6cd49`. The original GitHub
commit API responses show both head and merge have tree
`1df05946b03a53a81d425d1d46ea870e9369abe6`. Build manifests correctly identify the
actual merge SHA, not a relabeled head run. Main has not advanced or been merged.

| Actual PR workflow | Run / outcome | Original execution |
| --- | --- | --- |
| MCU Firmware Build | `38655458519`, SUCCESS | Same commands listed in the earlier dispatch table: host script/migration 34/34, pipeline host 33/33, native workerd 156/156, package 8/8, golden 9/9, workflow 39/39, production byte preparation 19/19, types and GCC App/Boot exit 0. |
| Acceptance Governance | `38655458363`, SUCCESS | `test_acceptance_bundle.py` 126, `test_acceptance_efficiency.py` 36, `test_ac5_ram_budget.py` 3, `test_f435_build_bootstrap.py` 14, `test_p2_5_build_provenance.py` 11, `test_flutter_dev_checks.py` 62, `test_flutter_dev_apk.py` 39, `test_artifact_maintenance.py` 29; all pass. Existing Linux/Windows host-helper jobs and P2-6 spec probes also pass; no old physical campaign ran. |
| Cloudflare Update Service Checks | `38655458606`, SUCCESS | Worker/native 156/156, Worker/Public/Admin type checks exit 0. These 156 repeat the same native suite and are not added to the firmware count. |
| App path detection | `38655458526`, SUCCESS | Only changed-path detection runs; Android, Windows, Release and Pages are SKIPPED. No APK/EXE build or deployment. |

URLs use `https://github.com/Eitan-S-23/E-Track/actions/runs/RUN_ID`. Both firmware
cloud jobs and the P3-4 candidate-only build/upload are SKIPPED in the job API.
The raw version step produces `2.7.0-nightly.310` and code 20700. GCC remains
640 compiler/linker warnings and 0 errors, with 6 vendor bsdiff warnings.
The 17 native `SQL_REJECT` lines and other expected rollback diagnostics are
retained; none was hidden to obtain a passing result.

The independent reviewer `/root/p41_independent_review` accepted this bounded
development candidate and closed P41-REVIEW-01/02/03 after reading the new source,
local red/green originals, actual CI command/step results and all four artifact
identities. The exact final message and transport provenance are in
`P4-1-pr-review-2026-10-15/independent-final-verdict.json`. The unavailable cc-connect
route returned "no binding for this chat"; it was not guessed or reconfigured.
The native non-implementer fallback performed no file writes, test reruns, cloud
or device operations. This is not independent whole-card rehearsal acceptance.

New archive: `docs/ota-exec-notes/P4-1-pr-review-2026-10-15/`, 102 files,
4722809 bytes. Its inventory binds 101 files excluding itself; inventory SHA-256
is `25b3c0d4812c0195b3ba327c31184913a9be175db0629ecb2b91477efc3a5d1a`.
All 659 members of the four artifact ZIPs have recorded lengths, digests and ZIP
timestamps. ZIP/API lengths and hashes, complete candidate byte equality and
tool stdout/stderr hashes were rechecked before copying; no product rerun was
used for this archival check. The earlier 154-file archive and every historical
failure remain byte-unchanged. The new archive preserves the first PR failures
and all three local red/green pairs, not just the final green logs.

The current real-GCC development artifacts are not installable, a formal base or
a rehearsal. `DEVELOPMENT-ONLY.json` retains that boundary, and every generated
asset's metadata still has `r2Verified=false`. The unchanged placeholder App and
Boot retain the lengths/digests in the earlier table. New finalized bytes bind
this PR merge's version and timestamp, so they are not substituted for the older
dispatch's distinct finalized image.

| Current PR artifact | Bytes | SHA-256 |
| --- | --- | --- |
| GCC finalized App | 605072 | `cc751921c9df49408aa0206e50e54077333f4e10b5148c296f40bff0796805f1` |
| GCC `e-track-at32f435-v2.7.0-full.etu` | 285674 | `e09a0a3f10efb94c3ac5eeb526423eae31e50493fa718e69b230d615a0bdf541` |
| GCC `recovery-v2.7.0.bin` | 605080 | `f2b777c00fc7f5c6ecf0944578d76ba1bd5cc88161d522c7d79d2b855e1a8ac5` |
| GCC unverified metadata | 1441 | `0453194e9c24400bff82557b922a86db4e02d7562465bab91ec4a9afcae6b394` |
| GCC verification JSON | 7034 | `2ffcfcff38e587cccc7654fc2c726bf7cb72d70915a4f9523cfa5c4658b5a279` |
| Synthetic full `v2.8.1` | 202 | `f22d87969b9a5ef787a905b987e1b93f9cebc598e307540c1c63d969f6e9d67d` |
| Synthetic patch `v2.8.0-to-v2.8.1` | 208 | `7c05c3f84d6944a44f71e31a55e1b1a61acb07757528ff50147d8e401bb66130` |
| Synthetic recovery `v2.8.1` | 8200 | `0171c47db39f84b0e9af139f3265847e403f7597cc3df5fa430ef6ac0525964c` |
| Synthetic unverified metadata | 1989 | `35f9b189b7a7fe152ed3a607452452f7f4460b6ff8eb161c60db8133c4cbc218` |

The synthetic three-asset prefix is `firmware-release-tests/case-fwMuyr/prepared/`
in artifact `11937130275`. Both actual full/patch applied outputs equal the exact
8192-byte target with raw SHA
`d8b49b46428a5c0873d6c783daf4f3789d4678117e68ec73ead77f300c4b5cb5`.
This fixture is explicitly not an authoritative previous formal release.

### Actual Remaining Inputs

Read-only GitHub inventory returned no releases (`autonomous-releases.json`) and
no environments (`autonomous-environments.json`, total_count 0) in Eitan-S-23/E-Track.
There is therefore no verified preceding formal finalized App or configured
release environment to consume. The original D1 HTTP 401/code 10000 and expired,
non-refreshable Wrangler login remain the credential observations; no repeated
login, refresh or cloud mutation was attempted. These facts cannot be repaired
by substituting a fixture, guessing a repository/base or relaxing the frozen Spec.

The next minimum owner work is authoritative formal-base provenance plus approved
isolated Worker/D1/R2 bindings, a usable scoped uploader/register credential and
the protected release-environment configuration listed above. Root/configuration
owners must resolve those inputs; this is a P4-4 interface handoff, not starting
P4-4. Then a separately authorized real rehearsal and independent production-zero-
effect observer can supply the actual full R2 byte readback, D1 ready/idempotency
and before/after snapshots. Those observations and whole-card acceptance remain
NOT_RUN. No additional P4-1 product changes are justified merely to stay busy while
those authoritative inputs are absent. P3-5, P4-3 and production remain outside
this batch, and no main merge, tag, Release or deployment was performed.

### Closing Audit And Lesson

The pre-archive audit at `2026-10-15T00:00:39.155Z` found 50 completed child
receipts, no workerd/bsdiff/bspatch helper, no project-local credential-file
candidate, and the original shared-root index hash and timestamp. PID 18500 now
belongs to `taskhostw.exe`; the earlier GitHub help receipt records a closed
`gh.exe` at `2026-10-14T22:48:54.794Z`. This is PID reuse, not a surviving owned
helper, and that unrelated process was not terminated.

All selected source, fixture/cache, log, download and archival outputs stay under
the exclusive worktree; only its authorized Git metadata uses the shared `.git`.
The archival plan checked every normalized target and Windows reparse attribute
before any copying, refused overwrites and matched plan SHA
`d88b0b2bf12c439f8f9cf1607622fad0918f9696bf34d866af80b107e8b05575`.
No credential value was written to a file; the Eitan-S-23 token existed only in
process memory. No cleanup of old evidence or external paths was attempted.

P41-AUDIT-01 remains ATTRIBUTION_UNRESOLVED. The same external startup cache was
most recently observed at `2026-10-14T23:55:18.821Z`, size 1004 bytes. The earlier
Export-StartLayout observations do not establish this later writer. No further
unbounded task/event scan or external cleanup was undertaken. The other inspected
PowerShell, npm, Wrangler, GitHub CLI and crash-cache files showed no modification
since worktree creation. This is a bounded metadata audit, not a machine-wide
zero-write claim. Root/host ownership is still needed only for that attribution.

The failure mechanism was a test coverage/implicit-state gap (a checks dispatch
with explicit version cannot cover default PR versions; an always-tagged GitHub
double cannot cover interrupted drafts), plus missed governance propagation.
The repair adds actual event/state regressions and exact registration rather than
another Spec, relaxed assertions or a replacement pipeline. Future P4-1 changes
must retain these now-executed cases and distinguish raw observations from green
workflow labels. The remaining delivery change is records/evidence only; automatic
PR synchronization is not another formal acceptance campaign.

### 2026-10-15 Follow-Up: User-Provided Read-Only Cloudflare Access

This is a new observation using a user-provided token, not a rewrite of the
earlier HTTP 401/code 10000 or expired Wrangler evidence. Token verification
returned `active`. Ten Cloudflare control-plane requests returned HTTP 200:
eight GETs and two SELECT-only D1 query requests containing six statements.
Every SQL result reported `rows_written=0` and `changed_db=false`. No deployment,
remote preview, upload, migration, registration, secret/configuration mutation,
CI dispatch or device operation was performed.

Sanitized request/response observations, exact SELECT text, timestamps and
Cloudflare request identifiers are in the exclusive worktree's ignored
`.cache/cf-readonly-20261015-r1/`. `summary.json` binds the lengths and SHA-256 of
six observation files; `audit.json` records the final local write/cleanup audit.
This local diagnostic archive is not a frozen rehearsal/acceptance bundle and
does not modify either previously committed evidence archive.

Observed existing resources:

| Resource | Actual observation | P4-1 consequence |
| --- | --- | --- |
| Worker `trace-update-service-staging` | Last modified `2026-07-07T13:37:56.578162Z`; `ENVIRONMENT=staging`; GitHub origin is `Eitan-S-23/Trace`, not `Eitan-S-23/E-Track`. | Existing Trace App bindings must not be repointed as a firmware setup shortcut. |
| R2 `trace-update-staging-releases` | Bucket exists and is bound to that Worker. | Existence is not uploader permission, object byte readback or rehearsal evidence. |
| D1 `trace-update-staging` | UUID `0133ad9e-d4a2-4fef-a659-4f2bf3d3a645`; migrations 0001 through 0004 applied; `0005_firmware_multi_asset.sql` absent. | The deployed schema is still the legacy single-asset firmware schema; the repository's accepted P4-2 v2 implementation is not thereby deployed. |
| Existing D1 data | 53 App releases, 100 App asset rows, two App channels with non-null release pointers; zero firmware releases/channels. | This is not an empty disposable database. Zero firmware rows is a dated read-only observation, not migration/cutover authority. |
| Public Worker health | One credential-free `/healthz` request failed with `fetch failed`; no HTTP response and no repeated probe. | Transport observation failed; runtime health remains unverified despite successful control-plane access. |

The new token resolves the ability to inspect the account and D1 with this
credential only. It does not establish write/uploader/remote-preview capability,
an isolated firmware deployment, a formal base, R2 byte verification or ready/
idempotency. Those real rehearsal requirements and whole-card acceptance remain
NOT_RUN. No product change or product-test rerun was needed for this inspection.

Next owner remains the root/configuration owner: approve a bounded firmware-only
test-environment setup that preserves the existing Trace App service and data,
qualify resource/credential isolation, and supply the formal-base and protected
environment inputs already listed above. The original prohibition on remote
mutations was not lifted by supplying a token for read-only inspection. This
handoff does not start P4-4, P3-5, P4-3 or a production path.

The user entered the token into an ignored, current-Windows-user-only file under
`.cache/cf-auth-input/`; it was used only in process-memory Authorization headers.
No token value was printed, committed or copied into observation files. After
the inspection, the exact temporary token file and its empty private directory
were deleted and absence was verified. No Cloudflare token was revoked or
otherwise changed remotely. All selected outputs and cleanup targets are inside
the exclusive worktree; no external path or shared-root index was modified.

### 2026-10-15 Follow-Up: Firmware Test-Environment Setup Authorized

The user subsequently authorized the explicitly proposed firmware-only test
service/database/environment setup and instructed the agent not to request the
same authorization again. That bounded setup may now proceed autonomously once
its technical prerequisites exist. Existing Trace App Worker/database/channel
state and production remain protected. Main merge, tags/Releases, device work,
production gate activation and starting unrelated task cards remain excluded.

The preceding read-only token's local copy was already deleted as promised; it
cannot be recovered from its verification response or GitHub. No replacement
Cloudflare deployment credential is currently available in the designated input.
This is a missing credential, not a request to reauthorize the operation. No
expired credential was retried and no login was initiated.

The private, ignored `.cache/cf-auth-input/token.txt` entry was recreated empty.
The deployment-setup credential requirements are Account Settings Read, Workers
Scripts Edit, D1 Edit, Workers KV Storage Edit and Workers R2 Storage Edit, limited
to the approved project account. KV is required by the existing manifest-cache
binding; no new cache implementation is proposed. These exact permission names
were checked against the current Cloudflare permission reference. No Global API
Key, all-accounts grant, DNS, Pages or user/token-management permission is needed
for the planned worker/storage setup.

This is a local provisioning credential, not automatically a rehearsal runtime
credential. The fixed rehearsal bucket already exists in the active Trace App
bindings. Qualify resource and credential isolation before binding or uploading;
different Worker/database names alone do not prove isolation. Do not put an
account-wide production-capable credential into the rehearsal environment or
change the frozen bucket contract to bypass this check. Formal-base provenance,
remote uploader/readback, ready/idempotency and independent rehearsal evidence
remain required and NOT_RUN.

Only the empty credential entry and this task record changed for this setup
checkpoint. No product code, cloud resource, GitHub environment or remote secret
was changed, and no product test or CI rerun was claimed. Input-path containment,
Windows ACL and final local audit are recorded in the ignored
`.cache/cf-setup-credential-input-audit.json`. The credential file will be removed
after its bounded use; it currently contains no credential.

### 2026-10-15 Firmware Environment Qualification: First Feedback

A replacement credential was supplied after its permissions were updated. Its
verification status is `active` and the approved account remains unchanged.
Request originals are under `.cache/cf-firmware-setup-20261015/`; the credential
itself remains only in the private input and process memory, not those records.
The earlier deleted input and failed probes are not rewritten as successful.

The previously inconclusive public-health request was a local transport problem:
curl returned HTTP 200, and the actual Node fetch returned HTTP 200 after enabling
the existing proxy with `NODE_USE_ENV_PROXY=1`. Both responses identify the old
service as `staging`. No login or old-Worker modification was needed.

The existing `bootstrap-staging.mjs` was inspected but is not safe to run for
this target: it rewrites the tracked staging bindings, deploys the old Worker
name, and prints the generated deploy token. Its documented alternate resource
names do not fix the Worker-name/configuration/logging risks. Reuse the existing
Worker, migrations and official deployment tooling with explicit new targets,
not a new backend, crypto implementation or generalized provisioning framework.

The first code increment only adds a credential-free Worker bundle artifact to
the existing `firmware-build.yml` development-checks job. The pinned Wrangler
CLI runs `deploy --dry-run`; its home/config/cache and output are contained in
the CI workspace, account/token inputs are empty, and publication keeps the
existing gates. The bundle carries its exact source commit and an explicit
build-only label. Artifact upload requires the job's checks to succeed.

Local command `node .cache/run.cjs p41-worker-bundle-wiring . node --test
tests/ota/test_firmware_workflow.mjs` executed 41 tests, 41 passed, exit 0. The
added negative checks reject removing `--dry-run`, injecting an extra command or
supplying a credential to that build step. Existing shell version/gate rejection
cases still executed. Originals are `.cache/logs/p41-worker-bundle-wiring.*`.
This is wiring feedback, not proof of deployment or cloud-side asset behavior;
the exact CI command/output and later remote results remain to be collected.

The authorized next target is a separately named firmware qualification Worker,
D1, KV and bucket, with no old Trace bindings or data changed. The fixed formal
rehearsal bucket is already in the active Trace App bindings; do not silently
reuse it, rename the frozen contract or give CI a production-capable account
credential. This qualification environment is explicitly not a formal rehearsal.
Real fixture-based API/uploader observations may qualify the shared production
tools, but cannot substitute for a formal base, canonical rehearsal bindings or
whole-card acceptance. Those requirements remain NOT_RUN.

### Qualification Checkpoint: CI Passed, D1 Provisioning Rejected

The tested code increment is `cd4f2e4d651fb7eafe8253ce854b90242cede4d9`, pushed
using `Eitan-S-23` on `dev/p4-1/unattended-20261015`. Primary run
`https://github.com/Eitan-S-23/E-Track/actions/runs/38677391835` is an actual
successful pull-request run. Its checkout is
`45da975bcecd97f0248fbf1d86bdf802763405ef`; GitHub and local Git confirm that its
tree equals the feature commit's tree
`0a2eeb3771468dcf866a2d114861765268517277`.

The original run/jobs/artifact JSON, complete log ZIP, selected exact step logs,
bundle and fixture ZIPs are retained under
`.cache/cf-firmware-setup-20261015/ci/`. Actual executed counts were host scripts/
migrations 34, host pipeline 33, native workerd 156, workflow/Bash 41, byte
preparation 19, package 8 and golden vectors 9, all passed with exit 0. The native
suite is not combined with duplicate backend-CI executions. GCC emitted 640
compiler warnings and zero errors; vendor bsdiff emitted six warnings. The Worker
bundle emitted one non-blocking default-environment-selection warning. Both
formal rehearsal and production jobs were skipped.

The raw bundle step invokes the pinned Wrangler JS entry with `deploy --dry-run`
and ends with `--dry-run: exiting now.` This is actual bundling, not a YAML-only
check and not a deployment. Artifact `11946284512` contains the five expected
regular files and the exact checkout marker; its executable `index.js` is
144770 bytes, SHA-256
`9ff814b0fd1731418a2250a3ae941ff1f6ce0db99233f6f1db42a1ba2c161082`.
No local Worker/Flutter/Gradle/APK build was substituted for this CI result.

Non-implementing agent `/root/p41_worker_bundle_review` independently reviewed
the two changed code files and supplied CI originals: NO FINDINGS. Its verdict
is recorded in `ci/independent-review.json`. It performed no writes, test reruns,
credential access, cloud or device operations. This bounded review does not
approve cloud rehearsal or whole-card acceptance.

`P41-CF-SETUP-01` is a real provisioning failure, not a code-test failure:

- The supplied token verifies as active and GET D1 inventory returns HTTP 200.
- One POST to create the new `e-track-firmware-p41-test` database returned HTTP
  401, code 10000, `Authentication error`; request identifier is
  `a4abde947bcd138a-SJC` at `2026-10-15T03:52:09.498Z`.
- The exact request (name only, no credential), failure response and their prior
  inventory are preserved as `resource-d1-request.json`,
  `resource-d1-created.json` and `resource-d1-precheck.json`. The response file's
  SHA-256 is `1dea9c407c1e020770c14ce8ffb263fdd7c62568bea6131c79a770886c659cf0`.
- A read-only reconciliation still finds three databases and no new target. The
  existing Trace database retains its prior UUID and reported size. No KV, R2,
  Worker, migration, registration or GitHub environment/secret mutation followed.
- Reading this token's own permission metadata returned 403/code 9109. Do not
  add token-management permissions merely to inspect it. Effective D1 creation
  access is not established; the error does not prove which dashboard policy or
  account-role condition is responsible.

Do not retry creation without a credential-policy change or a diagnosed fix.
The next necessary user input is the permission-summary screenshot for the
actually supplied token, with the token value excluded, or confirmation that its
Account / D1 / Edit policy for the approved account was corrected and saved.
Operational authorization is already sufficient and must not be requested again.
The current credential input remains in the ignored, current-user-only file for
that in-place correction; no new copy/paste is needed. It is not stored in CI or
observation files and will be removed when its bounded setup use is complete.

The new environment is not created. Real upload/readback, D1 ready/idempotency,
canonical rehearsal bindings, formal-base provenance, zero-production-effect
acceptance and the whole card remain NOT_RUN/in progress as applicable. No
historical failure, frozen evidence or completed P3/P4 card was rewritten.
