# P4-1 Unattended Development

Status: IN_PROGRESS (whole card and current readiness follow-up). The earlier
bounded development checkpoint on `ae6cd49c2f756dd9094ee390121fc0825dbbceac`
passed its actual PR checks and three independent repair reviews; that history
is retained below, not a claim that all later readiness gaps are closed.
The latest 2026-10-16 runtime/key follow-up is at the end of this note. Main
integration, canonical rehearsal and whole-card independent acceptance remain
unperformed; the new acceptance agent must not be handed an incomplete setup.
Sole Spec: `docs/ota-prompts/prompt-P4-1-implementation.md` and its frozen references.

## Entry And Authority

- Baseline: local and remote main `b42d3e25db85d6aba397cb4d0fb34bb5b653904f`.
- P4-2 accepted product: `fc4fbbb8193fcc536ef408b7b662d44b30f869dc`; consume its
  actual v2 schema, scripts, versioned fixture, business handlers and tests.
- Exclusive branch: `dev/p4-1/unattended-20261015`; worktree:
  `D:/github/my/E-Track/.cache/p41-dev-20261015`.
- At initial entry, the user authorizes scoped implementation/WIP commits, pushes as `Eitan-S-23`,
  existing checks/build-only Actions and project-contained evidence retrieval.
  No main merge, tag, Release, deployment, cloud resource/configuration write,
  device operation, external filesystem write or other-task work is authorized.
  The later bounded setup authorization is recorded under
  [Authorized Protected Setup And Account Blocker](#authorized-protected-setup-and-account-blocker);
  it does not expand main, production, device or other-task authority.
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

### 2026-10-15 Qualification Setup After D1 Edit Correction

This checkpoint follows the user's correction of D1 Edit, under the already
recorded authorization for a separate firmware test environment. The previous
statement that D1 Read was sufficient applied to SELECT-only inspection, not to
creating a database or initializing its schema. D1 Edit is required for those
provisioning writes. The corrected token created the database successfully;
P41-CF-SETUP-01's earlier 401 remains historical evidence, not a current blocker.
The Cloudflare account and the GitHub push identity need not share a login name.
No additional permission or token-value request is justified by the host failure
described below.

The tested product code remains `cd4f2e4d651fb7eafe8253ce854b90242cede4d9` and the
CI run remains `38677391835`, with the exact checkout/tree and separate test
counts recorded above. No product source, accepted migration, package version or
workflow changed in this checkpoint. The newly archived originals are in
`P4-1-cloud-qualification-2026-10-15/`: 55 files, including its inventory,
operational scripts, failed/successful command receipts and original CI ZIPs.
The inventory SHA-256 is
`5346fa790bd4edda81588d9cab35eb4dcdb65440114d5d462004225e1354f463`.
Archived operational scripts are evidence copies, not portable entry points;
their original invocation locations and working directories are in the receipts.

#### Created And Verified Test Bindings

| Binding | Isolated qualification value |
| --- | --- |
| Worker/origin | `e-track-firmware-p41-test`, `https://e-track-firmware-p41-test.tangjichentudou.workers.dev` |
| D1 | `e-track-firmware-p41-test`, UUID `2617e1e1-956f-42ce-a465-da56d84abf06` |
| R2 | `e-track-firmware-p41-test-releases` |
| KV manifest cache | `e-track-firmware-p41-test-manifest-cache`, ID `9581ef5b95154abaa7d441fd07c2f220` |
| Repository/environment | `Eitan-S-23/E-Track`, `ENVIRONMENT=staging`, direct Admin API disabled |
| Download configuration | `DOWNLOAD_TOKEN_KEY_VERSION=p41-test-1`, `FIRMWARE_V2_CUTOVER_EPOCH=1792039926` (`2026-10-15T04:52:06Z`) |
| Worker secret names only | `DEPLOY_TOKEN_SHA256`, `DOWNLOAD_HMAC_KEY_CURRENT`; independent new test values, no old secret replacement |

`operations/remote-preflight.json` contains successful HTTP 200 readback of the
actual Worker bindings and `/healthz`, before the separate local proxy startup
failure. Deployment used the already checked CI bundle with `deploy --no-bundle`;
no local Worker build was substituted. The deploy receipt reports version
`26389b5f-123f-402c-847d-d62d1f8c7b2c`; subsequent secret installation is recorded
separately. Both commands exited 0. The bundle's length/hash remain 144770 bytes /
`9ff814b0fd1731418a2250a3ae941ff1f6ce0db99233f6f1db42a1ba2c161082`.

These are **qualification**, not canonical rehearsal, bindings. No GitHub
environment/secret was populated with the account-wide provisioning token.
The frozen rehearsal bucket name still belongs to the protected old Trace App
service in this account; this work neither changes that contract nor repoints
the old resources.

#### Migration Invocation Failure And Recovery

The initial official `d1 migrations apply --remote` failed with exit 1, HTTP 400,
`incomplete input: SQLITE_ERROR [code: 7500]`. This was not an authorization error.
Inspection found only D1's internal/tracking tables and no applied migrations.
One inspection initially suppressed its JSON through `WRANGLER_LOG=info`; its
empty-output receipt is preserved. Setting the logger to `log` restored the
actual query output, without changing the query or claiming the empty output
proved a schema result.

Wrangler 4.105.0 sends migration SQL through `/query`; its documented `d1 execute
--file` route uses transactional `/import`. The latter successfully executed
the five unchanged accepted migration files, with the same migration-tracking
inserts used by Wrangler, in one import. No trigger was removed and no business
release/ready row was handwritten. The supported-route distinction is proven;
the exact internal reason for the `/query` parser failure is not established.

`import-accepted.json` records 105 executed queries and exit 0. Readback confirms
migrations 0001 through 0005, zero foreign-key violations, and 19 tables, 55
indexes and 45 triggers excluding `_cf_KV`. `verify-schema.cjs` independently
compared all returned `sqlite_master` entries with the accepted migrations
executed in in-memory SQLite, normalizing CRLF only; it exited 0. That local
schema comparison is not another native workerd suite or independent acceptance.
The import file is 40786 bytes, SHA-256
`c0ccf1c47f6bcedb96d6a1ea804787945cf1f896855ed89623eaf61079aba497`.

#### Actual API Feedback And Remaining Uploader Block

The operational commands run from the exclusive worktree were:

    node .cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler-operation.cjs import-accepted
    node .cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler-operation.cjs inspect-after
    node .cache/cf-firmware-setup-20261015/d1-edit-r2/verify-schema.cjs
    node .cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler-operation.cjs deploy
    node .cache/cf-firmware-setup-20261015/d1-edit-r2/wrangler-operation.cjs secrets
    node .cache/run.cjs p41-cf-qualification-preflight . node --use-env-proxy .cache/cf-firmware-setup-20261015/d1-edit-r2/qualify-remote.mjs preflight
    node .cache/run.cjs p41-cf-qualification-api-negative . node --use-env-proxy .cache/cf-firmware-setup-20261015/d1-edit-r2/qualify-remote.mjs api-negative
    node .cache/run.cjs p41-cf-protected-after . node --use-env-proxy .cache/cf-firmware-setup-20261015/d1-edit-r2/qualify-remote.mjs protected-after

The storage probe called the real production `withFirmwareBucket` module with
only the new D1/R2 bindings. Its Windows workerd proxy crashed at startup with
`0xc0000005`, consistent with the previously documented native Windows failure.
The failed attempt exited 1 after the owned Node/child processes were closed.
No R2 upload was reached. Do not repeat this input unchanged, install system
runtimes outside the authorized boundary, replace the uploader with a success
stub, or export the provisioning token into a checks-only CI job.

The independent executable API portion used the actual metadata builder and
register client against the deployed new Worker. Its four negative cases passed
with overall exit 0; each produced exactly one HTTP response, not a retry loop:

| Negative input | Actual result |
| --- | --- |
| Claimed readback but R2 assets absent | 503 `BACKEND_UNAVAILABLE`; actual register client rejects with exit-code property 1 |
| Invalid Bearer credential | 401 `TOKEN_INVALID`; actual register client rejects with exit-code property 1 |
| Unknown schema field, sent to the real API | 400 `INVALID_PARAMETER` |
| `isFormalRelease=false`, sent to the real API | 403 `FORMAL_RELEASE_REQUIRED` |

The deliberately false readback claims exist only as negative request inputs;
saved qualification metadata retains `r2Verified=false` for every asset. D1
SELECTs before and after confirm zero releases, assets, channels, registration
audits and ready rows. The shared-client exit-code properties above are not
misreported as separately executed CLI-process exit codes.

The fixture is the byte-tested CI case `firmware-release-tests/case-R5kVz9`, not
an authoritative formal base or installable firmware. Its synthetic provenance
(`commitSha` of repeated `1`, `runId=9001`) is explicitly retained and labelled;
the metadata builder changes only the qualification repository/notes as recorded.

| Qualification input | Bytes | SHA-256 |
| --- | ---: | --- |
| Final App fixture | 8192 | `d8b49b46428a5c0873d6c783daf4f3789d4678117e68ec73ead77f300c4b5cb5` |
| Full fixture | 202 | `cb3471b7790c9628bb183da07c3fc5d866135537b9412cbbe33843f50bf47799` |
| Patch fixture | 208 | `8a825bb74ec5fdccba743d3153db97c747e188ca592355400088af24a6273c67` |
| Recovery fixture | 8200 | `0171c47db39f84b0e9af139f3265847e403f7597cc3df5fa430ef6ac0525964c` |
| Qualification metadata, unverified | 2029 | `fbbd9b4756e8858e45a3ea5bf8c93d7c26b23a50740035a4f18ff5d0c5427ed7` |

The protected-state readback exited 0: the old Trace Worker's previously
observable bindings and compatibility settings are unchanged; its four applied
migrations, 53 App releases, 100 App assets and two populated App channels match
the earlier snapshot. Those counts/bindings are not a complete production R2,
channel-identity or GitHub Release zero-side-effect acceptance claim.

#### Follow-Up Ownership And Audit

- P41-CF-RUNTIME-01: implementation/configuration owner must qualify the existing
  production storage module in a functioning, isolated Linux execution context,
  with a credential boundary reviewed before any credential is supplied there.
  Existing Linux CI proves native runtime support, not real remote access.
  The user's D1 permission is no longer the blocker. No broad token-management
  permission, account login or repeated token paste is requested.
- Formal rehearsal still needs the authoritative previous finalized App,
  canonical isolated staging bindings/credentials, the protected workflow
  environment and before/after production observations. Root/configuration owner
  must resolve the already-used frozen bucket name without touching the old
  service or silently amending the contract; the OTA reviewer owns independent
  rehearsal adjudication. This does not start P4-4, P3-5 or P4-3.
- Real successful three-asset upload/full readback, D1 ready/idempotency,
  canonical rehearsal and whole-card independent acceptance remain NOT_RUN.
  The failed remote-proxy attempt remains FAILED, not relabelled NOT_RUN or PASS.
  Production, tags/Releases, main merge and `OTA_BOOT_CHAIN_READY` remain untouched.
- `operations/wrapup-audit.json` records project-contained outputs, 150 scanned
  setup files without supplied/generated credential values outside the private
  input, closed owned PIDs, and the unchanged shared-root index hash. The five
  disposable `.wrangler` files created in the worktree by the failed proxy were
  hash-inventoried and removed after process closure. An accidental zero-byte
  `[k` file from cmd quoting was also removed with `apply_patch`; no external
  path was involved. No new Windows crash dump was found and no PowerShell or
  system installation was invoked. Historical P41-AUDIT-01 remains disclosed.
- The corrected provisioning token and generated test credentials remain only
  in the ignored, current-user-only input directory while the authorized
  qualification is open. They were not printed, archived, committed or copied
  into CI. Retaining this input prevents another unnecessary user copy/paste;
  remove it when its remaining bounded use is actually complete.

No new shared product consumer changed in this checkpoint. The existing affected
caller list and out-of-scope legacy workflow handoff above remain authoritative.
This cloud setup and its self-tests do not upgrade the earlier independent
bundle-code review into whole-card acceptance.

Record validation re-read all 54 inventory entries by exact length and SHA-256.
The affected readiness test
`PostP26SpecGovernanceTests.test_readiness_matrix_mirrors_board_order_and_derives_dispatch`
ran through `.cache/run.cjs p41-cf-board-readiness`, 1/1 passed, exit 0. Node syntax
checks passed for both operational entry points. Plain staged `git diff --check`
returns 2 because the byte-preserved SQL original contains CRLF; its original
diagnostic is `.cache/logs/p41-cf-raw-whitespace.stdout.txt`. The same check with
`core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol` returns 0.
This recognizes the preserved line ending while retaining the actual whitespace
checks; neither the SQL evidence nor Git's persistent configuration was changed.

### Qualification Record Delivery And Independent Review

The cloud record/evidence commit is
`f1154ead58892a94e361edd99da63eb4706549f1`, pushed as `Eitan-S-23` to the same
exclusive branch. Remote main still equals `b42d3e25`; the shared-root index and
all 54 committed original blobs were rechecked unchanged/by exact hash.

Its automatic PR runs completed successfully: firmware `38687352718`, governance
`38687352778`, backend `38687352737`, and App path detection `38687352802`.
Original command output confirms host scripts/migrations 34, pipeline host 33,
native workerd 156, workflow 41, byte preparation 19, package 8 and vectors 9.
GCC warnings/errors remain 640/0; vendor bsdiff has six warnings. Rehearsal,
production, APK, EXE, GitHub Release and Pages deployment jobs were skipped.
No credentials were supplied to these checks and no manual CI rerun was needed.

Non-implementing agent `/root/p41_cloud_record_review` returned **NO FINDINGS**
for `001c7cfe -> f1154ead`, independently checking the 55-file archive, migration
inputs/readback, deployed bindings/health, four API rejections, preserved host
failure and limited protected-state comparison. It performed no cloud/device
operations, credential access or product-test reruns. This is bounded record
review, not formal rehearsal or whole-card acceptance.

Verbatim review, delivery receipts, new CI originals and local record-check logs
are in `P4-1-cloud-qualification-delivery-2026-10-15/`, separately inventoried
without changing the reviewed 55-file archive. The product code is still the
previously tested `cd4f2e4`; this final record append does not repair or waive
P41-CF-RUNTIME-01 or any NOT_RUN requirement above.

### 2026-10-15 Scoped S3 Upload And Ready Qualification

The user's authorized isolated qualification continued from branch HEAD
`75eea2c7380cfe3dadf147af4514a1e443d6e5d8`. Product code remains
`cd4f2e4d651fb7eafe8253ce854b90242cede4d9`: no workflow, production script,
Worker, migration, package or device code changed. The existing affected-caller
list remains applicable; this continuation adds no shared consumer.

The real Windows `withFirmwareBucket` startup failure is not retried or erased.
Instead, a bounded test-side adapter uses installed curl's S3 SigV4 transport and
calls the **unchanged** `uploadFirmwareAsset` and `registerFirmware` functions.
The former still owns immutable-object handling and full-stream length/SHA-256
verification; the deployed existing Worker independently reads R2 before its
atomic D1 registration. This qualifies those business paths against real R2/D1,
not the Wrangler initializer, an actual release workflow or canonical rehearsal.

#### First Feedback And Credential Boundary

- Cloudflare temporary-credential creation returned HTTP 200. A read-only,
  900-second credential was restricted to the three exact qualification keys;
  HEAD of an allowed missing key returned 404, while another key in the same
  test bucket returned 403. No account/token-management permission was added.
- The first full upload attempt exited 1: HEAD returned 404, then curl's PUT
  connection failed during TLS handshake, curl exit 35, with no R2 HTTP response.
  No verified result or register call followed. Its original receipt and raw
  headers remain in `operations/first-upload*`; the absent PUT body file is not
  fabricated as a successful or empty object.
- A separate bounded retry rechecked HEAD, received PUT 200, HEAD 200 and GET
  200, and the production uploader verified all 202 bytes. It exited 0; D1 was
  empty both before and after this first upload. Only then was the matrix widened.
- The read/write credentials were likewise restricted to those exact three keys
  in `e-track-firmware-p41-test-releases`, with a 900-second TTL. They existed
  only in process memory and were supplied to curl through stdin, never command
  arguments, GitHub secrets, CI, tracked files or console output. The broad
  provisioning input was used only for credential issuance and SELECT/readback.

The executed commands, all from the exclusive worktree, were:

    node --use-env-proxy .cache/cf-r2-qualification-20261015/probe-temporary-access.mjs
    node .cache/run.cjs p41-s3-first-upload . node --use-env-proxy .cache/cf-r2-qualification-20261015/qualify-s3.mjs first-upload
    node .cache/run.cjs p41-s3-first-upload-r2 . node --use-env-proxy .cache/cf-r2-qualification-20261015/qualify-s3.mjs first-upload-r2
    node .cache/run.cjs p41-s3-assets-register . node --use-env-proxy .cache/cf-r2-qualification-20261015/qualify-s3.mjs assets-register

Their exit codes are respectively 0, 1, 0 and 0. The matrix completed at
`2026-10-15T06:32:29.489Z`, with **9 named cases passed**:

| Case | Actual observation |
| --- | --- |
| Partial R2 assets | Real register returned 503 `BACKEND_UNAVAILABLE`; exact release/asset/channel/audit snapshots remained empty. |
| Bad local digest | Shared uploader rejected with `INVALID_PARAMETER` before any remote call. |
| Three-asset upload/readback | Full returned `ALREADY_PRESENT`; patch/recovery returned `UPLOADED`; every successful GET matched the complete local file. |
| Identical upload replay | All three returned `ALREADY_PRESENT`, with no PUT requests. |
| Different bytes, same key | Shared uploader rejected with `R2_OBJECT_CONFLICT`; no PUT or GET followed its HEAD check. |
| Real S3 conditional rejection | Existing-key conditional PUT and stale-ETag GET both returned 412 `PreconditionFailed`; this is a transport-only negative. |
| First real register | HTTP 201, `state=ready`, three registered assets. |
| Identical register replay | HTTP 200, same release ID, `idempotent=true`, identical full D1 rows. |
| Conflicting register | HTTP 409 `RELEASE_CONFLICT`, one request, identical full D1 rows. |

The negative imported-function tests assert the shared client's `exitCode=1`
property; they are **not** separately executed production CLI process exits.
The qualification runner exits 0 after verifying these expected failures.
Existing CI separately covers actual CLI process exits. No negative result is
hidden or relabelled as a successful upload/register.

#### Bytes And Database Outcome

The inputs remain the previously byte-tested synthetic case
`firmware-release-tests/case-R5kVz9` from CI `38677391835`, with synthetic
`commitSha`/`runId=9001` and explicit non-installable notes. They are not a formal
base, production firmware or firmware-scale performance test.

| Verified file | Bytes | SHA-256 |
| --- | ---: | --- |
| Full | 202 | `cb3471b7790c9628bb183da07c3fc5d866135537b9412cbbe33843f50bf47799` |
| Patch | 208 | `8a825bb74ec5fdccba743d3153db97c747e188ca592355400088af24a6273c67` |
| Recovery | 8200 | `0171c47db39f84b0e9af139f3265847e403f7597cc3df5fa430ef6ac0525964c` |
| Verified metadata file, including LF | 2026 | `c963239dadf175bc097bc2d1329f9dba41d95c2380dc3ce276b81411de53efd6` |
| Canonical HTTP/D1 metadata, without LF | 2025 | `2fbc0a4c167c310fc0a58f2e8b6eda1dfe6238d5d6ee9b94155b70b9b5020c62` |

The original 2029-byte unverified metadata is unchanged. `r2Verified=true` was
saved to a separate file only after all three real readbacks succeeded. R2
length, custom SHA/kind/content-digest, content type/disposition and cache policy
were checked; ETags and Last-Modified values remained unchanged after replay and
collision/conditional negatives. There were 25 real S3 requests in the matrix,
all curl exits 0; HTTP 404/412 are the explicitly expected storage observations.

The real release ID is
`fw_e1abd9e066161562fb72322b81ee7c06bf4719df7d6f89e769811a7460373648`.
Exact SELECT snapshots show one ready release, three available assets, one
registration audit and two automatically initialized **empty** channels.
Both channels have null release pointers, revision 0 and `last_action=init`.
No publish endpoint was called. IDs, timestamps, canonical registration JSON,
asset ETags and all other returned fields are identical after HTTP 201, the 200
replay and the 409 conflict. No D1 business row was manually inserted or edited.

#### CI Originals And Audit

The previously uninspected record HEAD `75eea2c` has actual successful firmware
CI `38689324267`. Its raw ZIP and selected step originals confirm separate
script/migration host 34, pipeline host 33, native workerd 156, workflow 41,
byte-preparation 19, package 8 and vector 9 tests, all passed. GCC reports 640
warnings and zero errors; the vendor build reports six warnings. Worker/shared
types and the build-only Worker bundle step passed. Rehearsal and production
jobs were skipped. Product-path diff from `cd4f2e4` to that head is empty.
The CI fixtures generated in this later run are not substituted for the earlier
qualification input or its random package nonces.

Two local CI-log-reader attempts exited 1 because the first parser expected TAP
and Python summaries for steps actually using Vitest and Node's spec reporter.
Both failures are preserved. The corrected reader checks the real reporter's
passed/total and zero failure/skip/cancel counts and exited 0. No CI test was
changed, rerun merely for parsing, or counted from workflow colour alone.

The new original archive is
`P4-1-r2-registration-qualification-2026-10-15/`: 132 files, including its
131-entry length/SHA inventory. Inventory SHA-256:
`37a1335c3cd928d66d45d27e35d000b9db74af84588167a2f66d3011f2603e99`.
It preserves failure/success receipts, raw S3 responses and downloaded bytes,
SELECT/register responses, fixtures, source snapshots and actual CI logs.
Operational scripts are evidence snapshots at their original worktree locations,
not portable commands to run from the archive. Earlier reviewed archives remain
byte-unchanged.

The protected old Trace database's observed migrations/counts and the old
Worker's observable bindings are unchanged. GitHub still reports zero Releases,
zero environments and main `b42d3e25`. These limited observations are not a
complete production R2/channel-identity/Release zero-side-effect proof.
`operations/closeout-audit.json` confirms closed owned upload/runner processes,
no workerd process, project-contained selected outputs and no supplied-token,
test-secret or expired-readonly-secret matches in the scanned qualification files.
The expired read-only credential file was removed from the private input.
Still-needed provisioning/test credentials remain in their ignored user-only
directory to avoid another token paste; no credential was exported to CI.
The shared-root index still hashes to
`2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd`.
No PowerShell, local build, deployment, device action or system installation was
used in this continuation. Historical P41-AUDIT-01 remains disclosed and unchanged.

#### Remaining Inputs And Next Owners

The configuration-name/scope table above remains the workflow handoff. This
test-only S3 adapter introduces **no new production or rehearsal configuration**.
The Cloudflare D1 permission issue is resolved; no extra token permission or
account login is requested for this result.

- Implementation/configuration owner: P41-CF-RUNTIME-01 remains open for real
  `withFirmwareBucket` startup in a functioning isolated execution context.
  Successful S3 qualification does not prove that initializer or its permissions.
- Root/release owner: provide authoritative preceding finalized App provenance.
  This repository still has no formal Release; the fixture is not a substitute.
- Root/configuration owner: resolve the frozen rehearsal bucket name already
  owned by the protected old Trace service, then supply the protected
  `firmware-rehearsal` environment and approved bindings/package key/base inputs.
  Keep the old service untouched; any contract change needs its proper decision
  and review, not a silent bucket rename or a second rehearsal specification.
- Independent OTA reviewer/observer: adjudicate one actual canonical workflow
  rehearsal, including complete before/after production-zero-effect evidence.
  That rehearsal, firmware-scale formal assets and whole-card acceptance remain
  NOT_RUN. This qualification is not their replacement.

The autonomous development candidate and the additionally authorized isolated
R2/register qualification now have actual feedback. P4-1 remains IN_PROGRESS;
no main integration, production unlock/promotion or P3-5/P4-3/P4-4 task starts
follow from this checkpoint.

#### Record Validation And Independent Review

Non-implementing agent `/root/p41_r2_qualification_review` returned **NO FINDINGS**
for both the bounded technical qualification and the final record/archive.
The original verdicts are preserved separately in
`P4-1-r2-registration-review-2026-10-15.json`, without modifying the 132-file
archive. The reviewer checked all 131 staged Git blobs against the inventory,
all 13 extracted CI steps against the original ZIP, the actual byte/metadata and
D1 snapshots, and the stated limitations. It performed no cloud request, private
credential read, build, device action or file write. This is independent bounded
review, not canonical rehearsal or whole-card acceptance.

The readiness regression ran via `.cache/run.cjs p41-s3-board-readiness`, 1/1
passed, exit 0. Full staged `git diff --check` with CRLF recognition returned 2
because untouched CI originals have trailing spaces and HTTP responses have
required final blank lines; its full diagnostic remains in
`.cache/logs/p41-s3-staged-whitespace.*`. It is not reported as green. The separate
authored-record/script/JSON whitespace check, `p41-s3-authored-whitespace`,
returned 0. Original bytes, historical failures and Git's persistent whitespace
configuration were not changed to suppress those diagnostics.

## Interrupted-Session Follow-Up: Inaugural Source And Bucket Candidate

The identified implementation session's last completed delivery was `a29d0ef`.
Its later user instruction delegated the absent predecessor and bucket decisions
to the agent. The subsequent continuation ended with provider errors rather than
a completed implementation. This follow-up resumes that bounded P4-1 work; it
does not ask the user to locate a nonexistent formal predecessor or repeat the
already resolved Cloudflare permission work.

Authenticated read-only GitHub observations in `.cache/github/p41-resume-main.json`
and `p41-resume-releases.json` confirm main remains `b42d3e25` and E-Track has zero
Releases. No main merge, tag, Release, deployment, D1/R2/channel operation, secret
configuration or device action was performed in this follow-up. P3-5, P4-3 and
P4-4 implementation/configuration tasks were not started.

### Candidate Changes And Decisions

| ID | Disposition and implemented direction | Verification boundary |
| --- | --- | --- |
| P41-BOOTSTRAP-01 | Explicit `inaugural-bootstrap-v1` descriptor, independently qualified raw GCC App archive, protected canonical descriptor hash, complete Release inventory and unchanged ordinary formal lookup. No automatic fallback or fictional Release. | Header/raw/placeholder originals independently checked; local source/pipeline and actual patch tests executed. Candidate contract is not yet effective. |
| P41-BUCKET-01 | Rehearsal admits only `e-track-firmware-p41-test-releases`; production rejects that bucket and protected old `trace-update-staging-releases`. Old Trace setup/publish/backfill consumers stay unchanged. | Six role combinations discriminate the old behavior; full pipeline regression passes. No bucket mutation or new cloud observation. |
| P41-BOOTSTRAP-02 | Reviewer found that missing execution-target commit could pass the helper. The bootstrap descriptor now requires exact target-commit equality, including rejecting omission before any fetch. | New missing-target negative plus full source/pipeline suite passes; actual CLI always supplies its selected commit. |
| P41-BOOTSTRAP-RETRY | Existing matching MCU target is forbidden in rehearsal. Only production replay can reach the existing-target exception, retaining the original reference and later full promotion/asset/notes verification before cloud writes. | Exact published/draft retries and conflicts are host transport tests, not production execution. |

The single candidate governance amendment is `OTA-DEC-017`; its canonical fields
are in `OTA-XC-BOOTSTRAP-BASE`, not a new task Spec or registration schema. The
current decision stays `PROPOSED`. Only the source-admission and environment
interfaces, and their P4-1/P4-4 readiness consumers, lose frozen execution
admission while the candidate is reviewed and awaits authorized integration.
Previously frozen metadata/Worker/protocol behavior and historical bundles remain
unchanged. Explicitly authorized development continues under execution contract
section 7.3.1; candidate review is not formal rehearsal or whole-card acceptance.

The new baseline archive is `P4-1-bootstrap-baseline-2026-10-15/`. Its nine-entry
inventory SHA-256 is
`e105229cdd6372998d026187b9b58757719c0ab89a4b1ca086ea9977b4812cab`;
`provenance.json` SHA-256 is
`0071e0ba5e287a18ea5d1bfa7a62a33ed819c397171f69b641b8b2ca45406e28`.
It preserves the six selected original files and development label. Complete ZIPs,
API listings and CI step originals are already retained at `a29d0ef` under
`P4-1-ci-2026-10-15/github/`, so they are referenced without duplication. Source
run `38642386248`, attempt 1, commit `fa74905e` produced the 605072-byte 3.2.7 raw
App `aaf5ccdb047ef8b3ff4ae0837f9593ceca857d90c98ea0bc09360e411bf4196f`.
This is not permission to use its development-key packages as release assets.

### Actual Development Feedback

All commands used the existing `.cache/run.cjs`, explicit worktree-relative cwd,
contained runtime/home/temp/cache paths and uniquely named closed receipts under
`.cache/logs/`. The representative command suffixes are:

    node node_modules/vitest/vitest.mjs run --config ../../../../../.github/scripts/p41-host.config.mjs
    node --test tests/ota/test_firmware_release.mjs
    node --test tests/ota/test_firmware_workflow.mjs
    python -B -X utf8 tests/ota/test_acceptance_bundle.py PostP26SpecGovernanceTests

| Receipt label | Actual result |
| --- | --- |
| `p41-resume-bucket-red` | exit 1; 3 failed, 3 passed, 33 intentionally filtered tests. Preserved evidence of wrong bucket roles. |
| `p41-resume-bucket-green` | exit 0; 39/39 full host pipeline tests passed. |
| `p41-resume-bootstrap-red` | exit 1; three positive source tests failed because the new entry did not yet exist; 70 filtered tests. |
| `p41-resume-bootstrap-green` | exit 0; 73/73 passed before the final mode/tree/omitted-target tightening. |
| `p41-resume-bootstrap-r2` | exit 0; 90/90 full host pipeline/source tests passed, including later-page conflict, incomplete inventory, raw/Git hashes, links/submodules, bounds, encoding and redirect policy. |
| `p41-resume-byte-green` | exit 0; 22/22 actual finalize/full/patch/recovery and failure tests passed. Fixtures remain synthetic; not a firmware-scale rehearsal. |
| `p41-resume-workflow` | exit 0; 42/42 static, actual Bash and CLI tests passed. Checks/nightly still receive no release credentials. |
| `p41-resume-governance` | exit 1; 23 tests, two failures exposed remaining all-decisions-frozen assumptions and missing interface-state propagation. |
| `p41-resume-governance-r2` | exit 0; 23/23 passed with exact one-decision/two-consumer candidate expectations, not arbitrary status relaxation. |

Node reports its SQLite experimental warning; it is not hidden. No local compiler
or Flutter/Gradle build was run. Native workerd, full CI typechecks and GCC remain
the separate branch-CI gate; their new-commit results are recorded below only
after the actual runs. Earlier Windows remote-proxy and audit failures remain
historical open facts, not waived by these local results.

### Next Admitted Work

Commit/push only the independently reviewed exclusive-branch delta using
`Eitan-S-23`, inspect its actual build/check logs, and preserve the
new evidence. Form any real bootstrap descriptor only after its archive and
target commits exist; do not invent commit self-references or silently configure
an approval variable. Main integration, candidate contract activation, protected
environment setup and canonical rehearsal remain distinct gates. No user token
paste or technical bucket choice is required for this development batch.

The independent `/root/p41_bootstrap_review` consolidated review found no
remaining blocking defect and closed P41-BOOTSTRAP-02. It checked all six selected
files against committed ZIP members, all nine baseline inventory entries, all
29 follow-up inventory entries against original cache files, composed-provenance
semantic identity and actual host/byte/workflow/governance outputs. Only candidate
maturity is now `REVIEWED`; the decision remains `PROPOSED`, formal dispatch is
still unadmitted, and P4-1/P4-4 are not completed. The source/byte self-tests are
not mislabelled as independently executed cloud observations.

The verbatim final review and its snapshot hashes are retained in
`P4-1-bootstrap-followup-2026-10-15/independent-final-review.json`. The subsequent
archive-schema check passed on the actual selected raw App and provenance;
`remoteDownload` remains `NOT_RUN`. After the permitted maturity-only annotation,
`p41-resume-governance-reviewed` passed 23/23. Both complete receipt/log triplets,
the final review and the byte-preservation attributes have a separate
`post-review-inventory.json`; the original baseline and 29-entry follow-up
inventories are unchanged. Later closeout annotations are explicitly outside
the reviewer's 16-file diff snapshot, not retroactively claimed as reviewed.

### Candidate Delivery And Actual PR CI

The implementation and reviewed baseline archive were committed and pushed as
`c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124` by `Eitan-S-23`. PR #27 remains
DRAFT and unmerged. Its actual temporary merge checkout is
`76e8c8a924fe4dba642c9972fa6f9d698ff00436`; authenticated Git commit responses
prove both use tree `e823a55cfb45549dc355e58e56ed0e2aceabc769`, with main
`b42d3e25` and the candidate as the merge parents. This does not mean main was
updated. The exact staged 65-file binary diff SHA-256 was
`9ea95c490ce7a7f66f9380a8a1e69ca97fca6f5c95bde56b7415d58ede30713b`.
Authored-source whitespace, staged scope/credential-pattern checks, all original
9/29/8 inventory entries, and evidence Git blob bytes/mode `100644` passed.

| Workflow | Actual attempt-1 result and scope |
| --- | --- |
| MCU Firmware Build, `38759988453` | SUCCESS. Host scripts/migration 34/34, pipeline/source 90/90, native workerd 156/156, workflow 42/42, real byte preparation 22/22, pack 8/8 and golden vectors 9/9. Worker types and build-only bundle pass. GCC App/Boot configure/build, host/layout checks and development-key full/recovery preparation pass. Rehearsal and production jobs are SKIPPED. |
| Cloudflare Update Service Checks, `38759987935` | SUCCESS. Public Pages, Admin Facade and Worker typechecks pass; native invariants 156/156. This repeated native suite is not added to the firmware run's count. No deployment. |
| Acceptance Governance, `38759987663` | SUCCESS. Ordered regression suite counts are 127, 36, 3, 14, 11, 62, 39 and 29. Existing Linux/Windows host-helper jobs and P2-6 probes also pass; no physical acceptance campaign ran. |
| Build APK and EXE Release, `38759988139` | SUCCESS for path detection only. APK, EXE, GitHub Pages and GitHub Release jobs are SKIPPED. |

The actual GCC build contains **640 compiler/linker warning lines and zero error
lines**; the vendor bsdiff build contains six warning lines. No warning suppression
or out-of-scope firmware repair was used. App size is text 603632, data 940,
bss 561992; the raw App is 605072 bytes and Boot is 14724 bytes. Original timestamps,
ELF/map/bin member hashes and all seven artifact ZIP/API digests are retained.
The five firmware artifacts include the Worker build-only bundle; the other two
are governance host-test originals, not hardware observations.

This PR's normal development version is `2.7.0`, with artifact suffix
`2.7.0-nightly.317`. Its finalized raw App SHA-256 is
`982cc4d3e05ee24dbb5e607a21aa5aa33b6bbc4224bd0d19a02bde4488d54278`.
Its GCC placeholder and Boot match the previously recorded raw source digests.
It is not relabelled as a built `3.2.8` target. The synthetic three-asset fixture
has actual full/patch/recovery byte equality; the real GCC development package
has no base and therefore no patch. Neither is a canonical inaugural rehearsal.

### Actual Read-Only Bootstrap Retrieval

After the archive commit existed remotely, a bounded probe invoked the unchanged
`firmwareGitHub.releaseBase` on that exact archive. It admitted seven exact
authenticated GET endpoints only: sanitized user identity, complete one-page
Release inventory, target-tag absence, archive commit/tree and both Contents
responses. Redirects, repeated requests and all mutation methods were forbidden.
The original repository inventory remains empty; the probe target tag is absent.
The complete immutable tree, regular-file modes, Git blob hashes, provenance and
raw App SHA/length all passed through the real client, not a transport double.

The 605072-byte downloaded App is byte-for-byte equal to the independently
qualified `3.2.7` source. The existing `firmware-byte-check.py` then passed its
actual header/CRC/SHA/version and GCC-placeholder comparison, exit 0. Its receipt
is `p41-resume-remote-header`. A missing approval digest was also rejected before
any source request.

The positive probe supplied a **LOCAL_TEST_EXPECTATION_NOT_PROTECTED_APPROVAL**
digest and a probe-only target `3.2.8`/`c860b3b`. Its descriptor digest is
`dc73db65c5475f7949cb2571bd63ef66a335513fc2f9ab62aa960124c3488f7a`.
This is test input, not an approved formal target, environment variable,
production configuration or permission receipt. No protected approval was read
or configured, no target firmware was built by this probe, and no R2/D1/Worker,
tag, Release or device operation was performed. `remoteDownload=PASS` refers
only to this source-reader development check; canonical `rehearsal` and
`production` remain `NOT_RUN`.

### Retained Originals And Remaining Gates

`P4-1-bootstrap-ci-2026-10-15/` retains 53 files, 9922663 bytes. Its inventory
SHA-256 is `9d39bafeeb848d69b9ecdf44b30590103cc10c4b57d2fd123880f9ca08be5270`.
It includes original run/job/log responses, all seven artifact ZIPs, member
digests, selected verification metadata, original source-read responses and the
exact probe/inspection helpers. The earlier baseline and follow-up inventories
remain unchanged. The archive reuses existing stdlib ZIP operations and packaging
summary checks; it does not execute another build or replace any product tool.

One artifact-list retrieval returned `fetch failed` before creating an output.
A single bounded GET retry succeeded; no workflow, build or successful remote
operation was rerun. Both the event and recovery are explicit in the inspection.

This resolves the implementation-side nonexistent-predecessor/bucket choices and
qualifies the real archived-source retrieval route. Those technical choices are
not returned to the user. P41-CF-RUNTIME-01's stock uploader initialization remains
separate from the earlier S3 adapter qualification. The next integration owner
must obtain the still-excluded main-merge authorization, integrate/activate the
reviewed candidate under the shared governance rules, and separately admit the
protected configuration and one canonical staging rehearsal. A finalized target,
approved descriptor, actual uploader/three-asset/readback/registration and full
independent production-zero-effect evidence remain required. This does not start
P3-5, P4-3 or P4-4, unlock `OTA_BOOT_CHAIN_READY`, or complete P4-1.

### Record Check And Boundary Audit

After these annotations, `p41-resume-record-governance` passed 23/23, exit 0.
The archive dry-run and exclusive-create apply passed with the same output plan
SHA-256 `60bf49076ec2dddc5465c6c5b9d76f13965d91728c089daa639660b799979cfe`.
Their complete receipts/logs and the final independent closeout verdict are
retained separately under `closeout-inventory.json`, without changing the
53-file original CI/source archive inventory.

The pre-delivery audit resolved the selected paths and inspected 5387 existing
output entries within the exclusive worktree, finding no links or escaped
outputs. All 18 then-recorded owned command/probe process IDs were absent from
the process list. The shared-root index remains SHA-256
`2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd`.
Only the already-authorized exclusive-branch Git metadata uses the common `.git`.
No PowerShell, local native/Flutter build, new Cloudflare mutation or device
operation was invoked. Historical P41-AUDIT-01 remains disclosed; this scoped
audit does not claim to resolve its earlier external-cache attribution.

The independent closeout reviewer returned **NO FINDINGS**, confirming the
original CI scope/counts, all seven artifact ZIP digests, all 52 indexed archive
entries, the real read-only source/header identities and the appended scope
annotations. Its verbatim verdict is `independent-closeout-review.json` in the
new CI archive. This approves the bounded documentation-only delivery, not main
integration, environment activation, canonical rehearsal or whole-card acceptance.

## 2026-10-16 Runtime And Key Readiness Follow-Up

The user requires finishing P4-1 implementation/readiness before a new independent
acceptance agent starts. The current batch starts at `eec231646c0a1ad4af98ac889d7491db6c39ae4d`,
on the same exclusive worktree and branch. No main merge, tag/Release, production
write, gate unlock, device operation or other task start is admitted by this work.
The prior isolated firmware setup authorization is retained; it does not authorize
exporting its provisioning credential to CI or inventing an independent approval.

### P41-GOV-ENTRY-01: Branch Freeze, Not Main Before Acceptance

Disposition: DECIDED by the delegated root technical owner, independently reviewed
by `/root/p41_bootstrap_review` on 2026-10-16. The acceptance execution contract,
section 1 item 3, expressly permits a pending committed branch. The preceding
main-before-acceptance requirement was an agent-added restriction and is superseded.
The reviewed source/bucket candidate is `c860b3be7a0b1a3ca1b3a53cf79cc9ef21cc9124`;
its latest reviewed delivery record is `eec231646c0a1ad4af98ac889d7491db6c39ae4d`.

OTA-DEC-017 and its two consumer interfaces are frozen on this pending branch.
Actual formal execution still requires authorized approval, independent review
and a v3 freeze against an exact committed revision, plus real protected
configuration and inputs. Main delivery is separate authorized closeout after
independent acceptance. The board restores only P4-1 implementation admission;
P4-1 stays incomplete and P4-4 stays unstarted. Historical PROPOSED/REVIEWED records
and frozen bundles are not modified.

### P41-CF-RUNTIME-01: Supported Native Runtime Entry

The observed Windows host is 10.0.19045.6456. Installed Wrangler 4.105.0 documents
Windows 11, macOS 13.5+ or Linux glibc 2.35 as its supported hosts; installed workerd
is 1.20260625.1. The existing Windows 0xc0000005 failure is preserved, not blindly
retried. No WSL/system runtime installation or local native build was attempted.

The uploader now rejects a known unsupported Windows host before creating runtime
directories. Windows 11 is checked by build 22000, not kernel major 11. Ordinary
Windows script/SQLite tests remain enabled. `verifyStoredFirmwareAsset` reuses the
uploader's existing full streamed hash/length and conditional ETag readback; it has
no upload fallback.

The existing firmware workflow has a default-off `check_bindings` dispatch input
and a protected, commit-bound Linux job. It reads only the three existing synthetic
qualification objects, exact Worker settings and fixed D1 SELECTs, comparing the
bounded before/after D1 observations. It neither creates a package nor registers,
publishes, promotes or performs canonical rehearsal. Build/checks and dependency
installation do not acquire cloud credentials; mixed release/check modes fail.
The canonical Spec records exact inputs, error cases, evidence and deadlines.

### P41-CF-CREDENTIAL-02: A Real Isolation Boundary, Not An Invalid Token

The bounded GET-only inspection found no GitHub environments, no variables and
only `ETRACK_DEV_SIGNING_KEYSTORE` among repository secrets. A missing gate is not
an explicitly configured `false`. The current local Cloudflare provisioning token
verified active; its token-policy GET returned 403. That does not invalidate the
token or authorize requesting token-management permissions. Worker settings still
match the separate existing firmware test R2/D1 resources. The private generated
credential file contains deploy/download credentials, not an OTA AES key. No value
was printed or transferred to CI, and no protected environment was auto-created.

Independent consultation checked the installed Wrangler implementation and the
current official Workers authorization documentation:
https://developers.cloudflare.com/workers/authorization/workers/

Per-Worker Editor permissions now exist, but editing a Worker's R2/D1 bindings
does not require corresponding resource permissions. Thus a token restricted to
editing one Worker is not proof that it cannot bind production data in the same
account. Wrangler's native adapter uses `trace-firmware-uploader` and creates a
temporary edge-preview session; `minimal` is not read-only authorization. Exact
minimum permissions for that private preview endpoint were not independently
probed. The job's fixed business reads are not a claim of zero control-plane writes.

The strict existing isolation rule therefore cannot be satisfied merely by
putting the account's provisioning token into a protected job. A test-only account
with no production resources is the supported strict-isolation route without
rewriting the adapter, and requires an owner-authorized account boundary and
resource/configuration preparation. A same-account exception would require an
explicit accepted risk and governance decision; it is not silently adopted here.
Changing accounts also requires reviewing/rebinding the pinned qualification
targets and moving or requalifying its fixture inputs. No new transport, proxy or
temporary public service is being invented to avoid this boundary.

The native cloud qualification remains NOT_RUN. Existing real S3-side qualification
is retained, but is not relabelled as evidence for native Wrangler initialization.

### P41-AES-01: Bind Compilation And Packaging To One Key Source

The source `Libraries/OTA/ota_keys.c` defaults to a development key; only all four
`OTA_AES_KEY_1_WORDx` definitions select an injected key. The previous GCC workflow
did not provide those definitions. Setting only the packaging secret would not
change the compiled receiver key. This is a P4-1 wiring gap as well as an owner
configuration prerequisite, not a reason to call the old build release-ready.

The two protected jobs now use the same GCC/CMake recipe with their existing
environment's OTA secret. A private, project-contained header supplies all four
words to the App key compilation; compile-command and header checks bind the
result to the key fingerprint and source digest. The matching Boot is built in the
same invocation. Current Boot sources do not consume AES, so the evidence does not
claim a nonexistent Boot key. Raw App/Boot artifacts, compiler diagnostics and
input identities are retained; the private header is excluded from the evidence
directory and removed on normal completion and handled failures.

The independent development review identified P41-KEY-CACHE-01 and
P41-KEY-CLEANUP-01 before any real keyed build. The shared recipe now explicitly
disables `KEIL_GCC_COMPILER_CACHE`, strips cache service variables and checks the
actual CMake cache/launcher rules before compilation. Ordinary builds keep their
existing cache policy. Exclusive-open ownership is recorded before writing key
bytes; partial-write failures clean the owned file. The workflow has EXIT/INT/TERM
traps and a separate always-run cleanup using exact commit/run/attempt ownership;
artifact upload requires successful absence verification. Hard termination is
handled by that separate cleanup route, not falsely attributed to JS `finally`.
The 134/134 host pass includes a deliberately terminated owned Node fixture,
wrong-owner refusal, actual cleanup CLI and a cache-launcher rejection; it did not
run a native compiler. Originals: `.cache/logs/p41-ready-lifecycle-host.*`.

The execute CLI rejects missing, development or mismatched key provenance before
source retrieval or cloud operations. The source-defined default key, public
packaging fixture and zero key are not admissible in rehearsal/production. The
key's existing protected secret/environment approval is the authority; per
P41-KEY-APPROVAL-01, no second key-hash approval variable is introduced. Hashes are
automatically derived for build/packer/reference consistency, not self-approval.

Ordinary GCC outputs remain unchanged by this route. A separate development-only
CI build exercises the same key-injection recipe and packaging with the public
fixture key, explicitly non-installable/non-publishable. Host compiler doubles
test failure/cleanup and byte identities, not successful native compilation.
Actual GitHub Actions compilation of the new recipe is still required before this
batch's implementation result can be reported.

### P41-BOOTSTRAP-KEY-01: Offline Base Is Not Device Key Compatibility

Independent scope decision: keep the existing 3.2.7 archive byte-identical and do
not add a second bootstrap-source campaign. Its old App was compiled with the
development key and cannot decrypt a package encrypted with a new real key. P4-1
staging patch-byte equality does not prove that device transition. First real key
provisioning/receiver compatibility belongs to the authorized P3-5/P5 device owner.
Recompiling a real-key base changes its raw SHA; the owner must use actual INFO/hash
and select full or an independently approved exact new base, not claim it is the
old archived patch base. This batch neither starts those cards nor operates a device.

### Development Evidence And Remaining Owner Inputs

The first local pass recorded host pipeline 123/123, workflow/Bash 56/56, existing
script/migration 34/34, governance 23/23 and Worker types, all exit 0. The subsequent
key-wiring compiler-double/source pass recorded 131/131 before the removal of the
unnecessary second key approval variable. Those are staged development observations;
the final reviewed batch and native CI results will be recorded separately.

The only selected outputs so far are this worktree's source/doc edits, contained
test fixtures, runtime directories and uniquely named closed command receipts.
No PowerShell, real native local compile, Cloudflare mutation, GitHub environment
mutation or production credential export occurred. P41-AUDIT-01 remains historically
ATTRIBUTION_UNRESOLVED; this continuation does not clean or relabel its old caches.

After local/code/CI completion, real readiness still needs the owner-authorized
isolated runtime/configuration path and a non-development OTA secret. Exact target
and descriptor approval must refer to the final real keyed build, not the earlier
3.2.8 probe. Do not start the new whole-card acceptance agent or call P4-1 complete
while those real prerequisites remain missing.

The final pre-CI local batch passes host pipeline/key lifecycle 134/134, actual
workflow/Bash gates 57/57, real fixture byte preparation 22/22, governance 23/23
and Worker types, all exit 0. Source key values are not logged; the deliberate
compiler-error test preserves its redacted error rather than suppressing it.
All test subprocess receipts are closed and no `private-key.h` remains under this
batch's key-build fixture root. The independent reviewer closed both key lifecycle
findings against the actual 134-test original and reported no further blocker in
that bounded development review. Native compilation and real CI are still the
next validation step, not an already-passed result.

### Actual Native CI And Readiness Archive

The preceding pre-CI checkpoint is now followed by actual successful PR checks
on `18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e`. The runner checked out temporary merge
`5b1c50f526f0edf90884b58c1c321593b7db0d1f`; source and checkout have the exact same
tree `5a6977eeace9ea96668f800b50e02b259bfcfe45`. Main is still the original
`b42d3e25db85d6aba397cb4d0fb34bb5b653904f`, and PR 27 stays draft/open/unmerged.

| Actual PR workflow | Run ID | Observation |
| --- | --- | --- |
| MCU Firmware Build | 38788072495 | SUCCESS; ordinary and shared key-bound GCC App/Boot builds and tooling checks pass |
| Cloudflare Update Service Checks | 38788072597 | SUCCESS; Worker native invariants and all three typechecks pass |
| Acceptance Governance | 38788072424 | SUCCESS; main governance suites and both host-helper jobs pass |
| Build APK and EXE Release | 38788072457 | SUCCESS; path detection only, build/deploy/release jobs skipped |

The original tooling logs report separate suites of 34 script/migration, 134
pipeline host, 156 native workerd, 57 workflow/Bash, 22 byte, 8 package and 9 golden
tests. Governance counts are 127/36/3/14/11/62/39/29. The backend repeats the 156
native suite; aggregate and step log copies are not additional cases. Local
134/57/22/23 and typecheck receipts are all closed with exit 0.

Ordinary GCC and keyed GCC each retain **640 compiler/linker warnings and zero
errors**. Vendor tooling has six warnings. The keyed App raw input is 605056 bytes,
SHA-256 `6757d819d080671a68de8d3db51140464cf184e8f9349f911dc58d59b76ff296`;
its finalized App is `44a5e24b09118fe3eb3a5aff0cef9c9f55ef2b00cc8760f8e6773edb66d09797`.
The matching 14724-byte Boot is
`3554e193f498d23210f5ef32e09de64575b7cd39104fafcc950740e5e8a7ec34`, identical
to the ordinary build. This is a real public-fixture-key build, not a protected
real-key candidate and not an assertion that Boot consumes AES.

The actual keyed CMake cache is OFF, its Ninja launcher rules are cache-free,
and compile-input/source/header fingerprints match build and packaging records.
Both actual GCC paths preserve full/recovery byte equality; the separate synthetic
fixture preserves full/patch/recovery equality. Cleanup succeeds and no
`private-key.h` occurs in any uploaded artifact. Isolated binding qualification,
rehearsal and production all remain skipped, not passed.

New immutable originals:
`docs/ota-exec-notes/P4-1-readiness-2026-10-16/`. The 98-file archive contains
eight digest-verified artifact ZIPs, four raw CI log ZIPs, exact API identities,
selected metadata and 15 closed local command receipts with their streams.
Inventory SHA-256:
`61c2710ad57e32bce8445de6bccbf36113f32e61616a6245c55dae176e2a7068`.
Both archive dry-run and exclusive-create apply passed the same output plan
`274dac582cf2563af71f80d00e2cb55eccaf8ee5b789f284879d3f013a1753e1`.
No older inventory, bootstrap bytes or frozen acceptance bundle was modified.

The archive also retains the reviewer's original key-lifecycle closure and its
new preservation message for the four scope decisions. That message labels the
old GOV-ENTRY decision as a summary because its verbatim message is unavailable;
the key-approval/bootstrap excerpts and cloud-scope excerpt are identified as
such. It does not backdate this new CI into earlier review evidence.

Artifact retrieval had real transport failures: Node connection/overall timeouts,
GitHub CLI EOF and a proxied curl timeout after 2292671/3160895 bytes. Partial
responses were not saved as ZIPs. The existing Node API identity/redirect route
plus installed curl direct HTTPS completed the same fixed downloads with TLS
verification intact; all eight exact GitHub ZIP digests then passed. No CI rerun,
new cloud mutation, proxy service or system setting change was used. One CLI error
included a short-lived signed download URL in tool output, not a repository file;
the adapter now redacts those URLs before reporting errors.

### Remaining Real Owner Boundary

The useful autonomous implementation/self-test/native-CI work for this follow-up
is complete; **P4-1 as a whole is not complete or ready for the new acceptance
agent**. P41-CF-CREDENTIAL-02 and real protected key/configuration remain genuine
owner boundaries, not reasons to invent a main-first merge, token-management
permission, another key-hash approval variable or a new bootstrap campaign.

The owner must name/authorize a production-free Cloudflare test account and its
test-only resource boundary, provide the corresponding constrained credential
through a private local input or protected Secret, and authorize preparation of
the existing `firmware-rehearsal` environment and non-development OTA key. Account
changes require reviewed rebinding/migration of the pinned qualification fixtures.
Do not copy the current account's provisioning token into CI or dispatch a job
that would auto-create an unprotected environment. After configuration, qualify
the existing native binding route and actual keyed candidate before handoff;
exact target/descriptor approval and the single canonical rehearsal remain under
their declared independent authority. No production gate unlock, main merge,
Release/tag, device operation or P3-5/P4-3/P4-4 start is authorized by this record.

### Record Regression And Boundary Audit

The documentation delta passes `PostP26SpecGovernanceTests` 23/23, exit 0, under
the contained runner (`p41-ready-record-governance`). The tracked operational-note
`git diff --check` passes. The later full staged check exits 2 on original CRLF
and trailing blank lines in byte-preserved logs/CMake outputs; those bytes are
not rewritten. The explicit operational-note/README staged check passes separately.
Git's two ordinary LF-to-CRLF notices for the operational notes are not compiler
diagnostics and do not change the evidence directory's explicit `-text` policy.

The read-only output audit passes with 7349 resolved existing entries, all 97
original inventory bindings intact, 99 archive files and 927 ZIP members scanned.
No private-key header or supplied credential value was found in those evidence
bytes. All 18 earlier recorded commands are closed; their process IDs are absent
from the current process list. The audit's own outer receipt subsequently closed
with exit 0. Preflight-only directories/`p41-ready-gov-r2` and the deleted empty
`20)` file are recorded as absent, not fabricated successful commands.

The `20)` file was an earlier CMD redirection accident from an unquoted Node
comparison: parsing failed before token access; the exact empty owned file was
verified and deleted with apply_patch, never staged or committed. Subsequent
read-only quoting/search errors created no files. These incidents and bounded
download failures are preserved in the selected-output record, not hidden as
successful operations.

Shared-root index SHA-256 remains
`2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd`.
Only the already-authorized exclusive-worktree Git metadata/common objects and
own branch ref are outside the active worktree's selected write paths. No new
PowerShell, local native/Flutter build, Cloudflare configuration mutation, main
merge or device operation occurred. This audit does not settle the earlier
P41-AUDIT-01 external PowerShell-cache attribution or authorize cleanup there.

The independent bounded evidence/record review returns **NO FINDINGS**: all 97
original inventory bindings, eight artifact digests/810 members, 14 selected
originals and four log ZIPs/117 members match. It confirms the actual count,
cache/key/byte/cleanup observations and the IN_PROGRESS/NOT_RUN boundaries.
The verbatim response is preserved as `closeout/independent-readiness-review.json`
in the new archive. Later closeout receipts/annotations are not automatically
included in that review; none of this is a new whole-card acceptance decision.

## Authorized Protected Setup And Account Blocker

### P41-SETUP-AUTH-01: Owner-Delegated Preparation

On 2026-10-16 the user authorized this agent to prepare the production-free
Cloudflare test account/resources, the `firmware-rehearsal` protected environment
and a non-development OTA key, asking to be told what genuinely needs their
action. This supersedes the missing-setup-authorization part of the preceding
checkpoint, not its missing runtime observations. The exclusive worktree and
scoped WIP commit/push authority remain unchanged. No main merge, production gate
unlock, tag/Release, device operation, billing/paid-plan change or start of the
P3-5/P4-3/P4-4 cards is included.

This setup starts from record commit
`fefcb3f2b493527e14affa236207a8d5f4deb682`; implementation source remains
`18c4da4d28c1f2bcf7175f4b461e2a6bf462a23e`. PR 27 remains draft/open/unmerged.
The prior readiness archive is not edited or re-created. New setup observations
are retained in `docs/ota-exec-notes/P4-1-protected-setup-2026-10-16/`.

### P41-CF-CREDENTIAL-02: Account Creation Needs Owner Action

The current token can list one visible existing Cloudflare account. That is only
its visibility, not proof the user owns no others. The fresh official account
setup documentation permits an additional Free standalone account through the
dashboard or a user-owned token with `User Details Read`; an account-owned token
cannot create accounts. The legacy API reference's Global API key example does
not make a Global API key necessary.

The actual prerequisite `GET /user` returned HTTP 403 / Cloudflare code 9109
(`Unauthorized to access requested resource`). The helper stopped there:
**no `POST /accounts` was sent, no account was created and no Cloudflare mutation
occurred in this setup batch**. The stable creation idempotency key in the retained
plan is unused. Do not repeat the same permission failure, broaden the existing
provisioning token or export that token to CI.

The selected production-free account name is
`e-track-firmware-p41-validation`. The owner can create it with their existing
Cloudflare login at Accounts > Create Account; a new login/email is not required.
Eligibility remains subject to Cloudflare's documented user age, role and account
limits. Native preview isolation still requires this separate account, not merely
a Worker-specific edit policy in an account containing production data.

### Protected GitHub Configuration Completed

The actual readback confirms environment `firmware-rehearsal`, ID `24458272742`,
with required human reviewer `Eitan-S-23` (user ID `204050265`) and exactly one
custom branch policy: `dev/p4-1/unattended-20261015`. There is no wait timer.
`prevent_self_review=false` is intentional: the agent's dispatch uses that same
owner identity, so setting it true would prevent the sole human owner approving.
Human approval is still required; the agent performed no approval and this is
not independent production approval.

| Environment-scoped setting | Actual configured value / observation |
| --- | --- |
| `OTA_BOOT_CHAIN_READY` | `false`; no repository or production gate change |
| `FIRMWARE_REHEARSAL_TRACE_R2_BUCKET` | `e-track-firmware-p41-test-releases` |
| `FIRMWARE_REHEARSAL_TRACE_D1_DATABASE_NAME` | `e-track-firmware-p41-test` |
| `FIRMWARE_REHEARSAL_OTA_AES_KEY` | Secret uploaded; metadata readback confirms its name |

The key was generated with `crypto.randomBytes(16)`, checked by the production
`approvedFirmwareKey` validator and encrypted/uploaded by `gh secret set` through
stdin, never argv or console. Its non-secret SHA-256 fingerprint is
`a94ae0f006b3d6be51279b861dc19b8a0892833939d0a4db5a81ee7af511fe9e`.
The ignored owner copy is `.cache/cf-auth-input/p41-rehearsal-ota-key.json` inside
the exclusive worktree. Readback of the file and parent NTFS ACL grants only the
current `SU` account inherited full control. Retain this private copy for later
authorized provisioning/recovery; do not print, commit, archive or rotate it.
Secret metadata is not runtime verification: **no actual protected real-key
compilation has run**, and `runtimeValueVerified=false` remains explicit.

There were six GitHub writes: environment creation, one branch policy, three
variables and one secret upload. No workflow dispatch, approval or Cloudflare
credential export occurred. `firmware-production` was not created or modified.
Account/token, Worker URL/deploy token, D1 ID, bindings-check commit and bootstrap
descriptor approval remain intentionally unconfigured. A partial environment
must not be used to dispatch the qualification job.

### Exact Owner Input And Next Action

The owner's remaining input is bounded to the new account:

1. Create `e-track-firmware-p41-validation` as an additional Free account, using
   the existing login. Do not change the production account or its token.
2. In that account, enable R2 at Storage & databases > R2 > Overview if needed.
   Cloudflare requires its checkout flow; R2 has included free usage but is
   usage-billed. The owner handles any payment confirmation. No Workers paid-plan
   upgrade is requested or authorized.
3. Create a dedicated account-owned token at Manage account > Account API tokens
   > Create Token, restricted to that account: `Workers Scripts Edit`,
   `Workers R2 Storage Edit`, `D1 Edit`, `Workers KV Storage Edit` and
   `Account Settings Read`. Do not grant production-account, DNS/zone, billing,
   user-details or token-management permissions. The official compatibility
   matrix includes Workers, D1, R2 and KV; exact native-preview capability still
   needs the bounded real qualification, not a documentation-based PASS.
4. Fill `account_id` and `api_token` in the already-created private file
   `D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-auth-input/p41-isolated-account-input.json`.
   Keep `account_name` and `token_kind=account-owned`; do not send credentials in
   Feishu. The file is ignored and its NTFS ACL was checked, not added to evidence.

After that input, the implementation owner validates account/token isolation,
prepares the exact test resources and reviewed fixture rebinding, and completes
the remaining protected settings. The bounded native Linux qualification still
requires the exact source binding and later human environment approval. Final
real-key target/descriptor approval and the one canonical rehearsal retain their
declared independent owners; implementation must not duplicate that campaign.
The old 3.2.7 bootstrap archive and its development-key device limitation remain
unchanged under P41-BOOTSTRAP-KEY-01.

P4-1 stays **IN_PROGRESS, not ready for the new whole-card acceptance agent**.
No new permission request is needed for already-authorized preparation; the
blocking item is the owner's unavailable account/token/checkout capability.

The affected documentation regression, `PostP26SpecGovernanceTests`, passes 23/23
with exit 0 (`p41-setup-governance`). Its original closed receipt and streams are
retained with the new setup evidence. This is a lightweight governance self-test,
not a repeated cloud/hardware campaign or an independent acceptance conclusion.

The new archive contains 22 files; its inventory SHA-256 is
`9d605ad6fc325be20a58fa219de55ab818128d1dc15472ac03f55a62807e0948`.
The pre-commit output audit checks all 21 setup inventory entries, the old 97-entry
inventory and 927 ZIP members, including the new real OTA key in the leak scan:
no credential match, private key header or lingering recorded process. A separate
read-only check verifies the old 19-entry closeout inventory unchanged. The shared
root index still hashes to
`2907ee569cb8415877c8c688b3e09b5948a789d6430796eab99ae3ad43f3a3dd`.
All selected setup outputs are worktree-local; only the previously authorized own
Git metadata/object/ref scope is excepted for branch delivery. No PowerShell or
local native build was used. Historical P41-AUDIT-01 remains attribution-unresolved.

## Existing Account Selected By Owner

On 2026-10-16, after the distinction between resource separation and account-level
credential isolation was explained, the user explicitly selected the existing
Cloudflare account. P41-CF-CREDENTIAL-02 now follows this bounded same-account
owner decision. The earlier request to create an additional account and repeat
R2 checkout is superseded, not a remaining user prerequisite. Its original
403/no-create receipt and the protected-setup archive remain unchanged.

Reuse the existing `e-track-firmware-p41-test` Worker and D1, the
`e-track-firmware-p41-test-releases` bucket and their existing qualification
fixtures. The account ID is already known privately. No new account, resource
migration, fixture rebinding or new R2 subscription is needed for this route.
Same-account Workers edit capability can reach other data through bindings; this
accepted limitation must not be relabelled as hard production-permission isolation.
It does not authorize an operation on the old Trace service or production data.

The remaining owner input is a dedicated `e-track-p41-ci` account-owned API token
for the existing account, not reuse/export of the local provisioning credential.
The suggested initial CI permissions are `Account Settings Read`,
`Workers Scripts Edit`, `Workers R2 Storage Edit` and `D1 Read`. The native adapter
binds only R2/D1, D1 snapshots use SELECT, and registration uses the separate
test-Worker deploy token. This CI route does not deploy the service, migrate D1
or provision KV, so `Workers KV Storage Edit` and `D1 Edit` from the local setup
credential are not requested for it. Exact native-preview compatibility is still
unqualified; these permissions are not an experimentally proved minimum or a PASS.

The already-created private input is
`D:/github/my/E-Track/.cache/p41-dev-20261015/.cache/cf-auth-input/p41-ci-token.txt`.
The owner only fills its token value; the earlier blank isolated-account JSON is
not the input for this route. Do not request another account ID, a Global API key,
all-accounts access, DNS/zone, billing or token-management permissions.

Before credential export or protected dispatch, propagate this owner decision to
the applicable current shared contract/Spec and verify the exact configuration.
The existing native Linux qualification, human environment approval, target/base
approval and independent acceptance obligations remain. No actual cloud/GitHub
mutation or dispatch is performed by recording this decision. P4-1 stays in
progress; no main merge, production unlock, release, device action, unrelated
card start or independent-acceptance claim is included.

### Dedicated CI Credential Received And Read-Checked

The user supplied a separate token through `.cache/cf-auth-input/p41-ci-token.txt`.
It differs from the local provisioning token. On 2026-10-16, five actual
Cloudflare GETs succeeded: token verification (`active`), the expected account,
the existing test Worker settings, its exact R2 bucket and its exact D1 database.
The public test Worker health check also succeeded with `environment=staging`.
The token is unprefixed and the standard user-token verification endpoint accepts
it; do not claim account-owned status or invent a prefix requirement. Its full
policy was not inspected, and no minimal-permission or hard-isolation claim is made.

The sanitized closed receipt is `.cache/p41-existing-account-20261016/probe.json`;
the helper records only selected fields and redacts the account ID and credentials.
No resource write, preview session, schema change or fixture upload occurred.
Native Wrangler qualification and actual protected real-key compilation are still
unperformed. The updated current shared contracts and both consumer Specs now
record the actual same-account owner decision, with production/approval limits
unchanged; historical setup/readiness evidence is not rewritten.

The bounded governance regression passes 24/24, exit 0, including the new scope
guard. Original sanitized probe/helper/documentation and closed test streams are
retained in `docs/ota-exec-notes/P4-1-current-account-2026-10-16/`. Product runtime,
workflow, registration schema and fixed qualification targets remain unchanged.
The next action is to bind the protected configuration to the committed revision
and dispatch only `check_bindings=true,publish=false,rehearsal=false`; the human
owner, not the implementation agent, approves the existing environment gate.
