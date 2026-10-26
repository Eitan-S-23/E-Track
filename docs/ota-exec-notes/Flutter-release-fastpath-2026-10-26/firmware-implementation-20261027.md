# P35-PREP-FW-01 Protected Candidate Build Wiring

## Scope And Status

Implementation owner, 2026-10-27. Local implementation and host self-tests are
complete. Independent review and real GCC/CI candidate builds remain NOT_RUN.
This is a same-task handoff, not a new Spec, frozen bundle or P3-5 PASS.
Related owner decisions remain P35-PREP-KEY-01 and P35-PREP-CI-01.

Exclusive worktree: `D:/github/my/E-Track/.cache/p35-firmware-20261027`.
Branch: `dev/firmware/p35-candidate-20261027`. Base/HEAD remains
`6dbd18694b0cce1ed35e8bb07a1bdcfa14a24c89`; changes are unstaged/uncommitted.
No new implementation commit exists. Read-only receipt `remote-01` confirms
remote main `91fed6bc` and Flutter delivery `6dbd1869` unchanged.

The two reviewer notes were consumed read-only from the other worktree:
`D:/github/my/E-Track/.cache/flutter-fastpath-20261026/docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/`.
Those notes and its dirty task note were not copied, edited or committed. No
Trellis tree is present; existing P3-5/OTA contracts remain the normative inputs.

## Bounded Delta

Six product/build files, four tests and two task documents:

| Path | Change |
| --- | --- |
| `.github/workflows/firmware-build.yml` | Baseline-default profile choice; identical protected compiler/release mapping; existing development-only keyed recipe accepts the selector for later CI. |
| `.github/scripts/firmware-gcc-keyed-build.mjs` | `--profile`, real CMake argv, generated recipe validation/archive, configuration drift rejection. |
| `.github/scripts/firmware-release.mjs` | Reject incompatible/unbound protected build before base retrieval; retain reference equality and supply current build to promotion. |
| `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-build-profile.mjs` | Shared allowlist/options and actual cache/all-App recipe capture/validation. |
| `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/prepare-firmware-release.mjs` | Existing build-provenance extension, original compile-input rereads and preparation/reference equality. |
| `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/firmware-release-pipeline.mjs` | Request/preparation binding before effects; approved/current build equality in promotion. |
| `tests/ota/firmware-pipeline.host.test.ts` | Actual helpers/CLI with compiler doubles; drift, cleanup, old build and promotion negatives. |
| `tests/ota/test_firmware_build_profile.mjs` | Profile/options/recipe and reference negatives, including existing CMake-owned tuning definitions. |
| `tests/ota/test_firmware_release.mjs` | Real synthetic full/patch/recovery preparation with configuration evidence and replay negatives. |
| `tests/ota/test_firmware_workflow.mjs` | Actual YAML mappings/default/allowlist; existing executable shell gates retained. |
| `docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26.md` | Link to this same-task follow-up. |
| This record | Concentrated facts, originals and remaining authority. |

## Executable Contract And Invariants

`firmwareBuildProfile(value)` admits only `baseline` and `p34-v2-candidate`.
An absent optional helper input defaults to baseline; explicit empty, unknown,
injected or contradictory inputs reject. Candidate real CMake argv selects
`P34_OTA_CANDIDATE:BOOL=ON`, `P34_EARLY_FAULT_VECTORS:BOOL=ON`,
`P3_4_LINK_PROFILE:BOOL=OFF`, `P34_OTA_UART_BAUD:STRING=921600`.
Existing evidence/handoff test options are OFF. Baseline keeps candidate,
early-vector and experiment options OFF and the existing 921600 fallback default.
That value is a compile input, not a measured module baud; valid retained settings
still follow unchanged MCU behavior.

`captureBuildConfiguration({ profile, cache, commands })` verifies generated
Release/cache-OFF options, exact selector options and every App compile recipe.
It requires existing candidate/vectors/WAIT_RX invariants and forbids experiment,
harness and explicit key override defines. Missing/duplicate cache evidence,
unparsed/conflicting `-D` flags or per-source App disagreement fail closed.
After compilation, changed cache/command bytes also fail, with strict cleanup.
This validator does not define another set of MCU tuning macros.

The existing `gcc-build-inputs.json` and `keyed-build-evidence.json` contain
`buildConfiguration`: schemaVersion 1, requestedProfile, actualProfile,
cmakeOptions and sorted appCompileDefinitions. Complete CMake cache and compile
commands are archived with SHA bindings; actual configure argv/diagnostics and
App/Boot artifact identities remain. Canonical configuration has no absolute
build paths, so legitimate cross-run reproduction remains possible.

Preparation independently rereads the originals before/after generation.
Protected execute/publication reject legacy build records without configuration.
Low-level development byte/capture consumers still accept historic unkeyed
baseline inputs; they cannot qualify those inputs for protected publication.
Historical bootstrap originals remain readable and unchanged. Reference and
promotion compare complete build provenance, including key, App/Boot identities,
source/version/timestamp and configuration, plus the existing canonical run and
approval checks. Same source with another profile/definition set cannot reuse an
old result even when synthetic input bytes are deliberately identical.

`CMakeLists.txt`, all MCU/Flutter/Boot sources, key registry, package format,
version encoding, ACK/credit/durable, UART flow control and performance gates
are unchanged. No business key was created, rotated, retrieved or exported.
Original protected secrets, private forced include, key binding, cache isolation,
redaction, owner-specific cleanup and known-development/example-key rejection
remain. `bootKeyConsumer=false` is unchanged; do not replace group16 Boot merely
to change the receiver key.

Registration metadata has no new field. Both protected environments still use
the same canonical workflow and release implementation; required reviewers,
branch rules and production/rehearsal gates were not changed. No legacy release
workflow, public Release, cloud mutation or device operation was used. The
standard APK/EXE build at `2febc00b`, run 40309860485, was not repeated.

## Executed Self-Tests

Commands ran from this root through `.cache/run.py` and the existing
`host_io.checked_output` guard. Node 24.13.0, installed PyYAML 6.0.3 and
PyCryptodome 3.23.0. No local Flutter/Gradle or native MCU compile occurred.
Compiler doubles and existing isolated keys/packages are noninstallable fixtures,
not business artifacts or receiver-key/device evidence.

| Receipt in `.cache/records/` | Actual command after adapter | Result |
| --- | --- | --- |
| `workflow-tests-02.*` | `node --test tests/ota/test_firmware_workflow.mjs tests/ota/test_firmware_s3.mjs tests/ota/test_firmware_build_profile.mjs` | 140 passed, 0 failed/skipped; includes 27 profile checks and old executable shell gates. |
| `pipeline-tests-02.*` | `node app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/vitest/vitest.mjs run --config .github/scripts/p41-host.config.mjs` | 156 passed, 0 failed/skipped; real helpers/CLI with compiler/HTTP doubles and SQLite host ports. |
| `byte-tests-01.*` | `node --test tests/ota/test_firmware_release.mjs` | 25 passed, 0 failed/skipped; real synthetic finalize/full/patch/recovery, replay and failure checks. |
| `pack-tests-01.*` | `python -B tests/ota/test_firmware_pack.py` | 8 passed; key/header/plaintext/reference/stdout negative checks. |
| `worker-host-tests-01.*` | `npm --prefix app/bluetooth_flutter_Trace/cloudflare/update-service/worker test -- --config test/vitest.host.config.ts test/firmware-scripts.host.test.ts test/firmware-migration.host.test.ts` | 41 passed, 0 failed/skipped; fixed metadata/script/migration regressions. |
| `types-01.*` | `node app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/typescript/bin/tsc --noEmit --project app/bluetooth_flutter_Trace/cloudflare/update-service/worker/tsconfig.json` | Exit 0, no diagnostics; configured Worker/shared declaration scope, not excluded host-test static typechecking. |

Before edits, workflow/S3 112 and pipeline 147 tests passed. Originals and
intermediate successful checks remain; only affected later tests were rerun.
Final source bytes and receipt sizes/SHA values are indexed by
`implementation-inputs.json` and `receipt-inventory.json`. These are local
development bindings, not a replacement for committed Git/frozen v3 identity.

No test failed or assertion was removed. Preliminary command-escaping and patch-
context failures were non-writing and corrected; their tool results remain in
the session. Negative injections remain explicit, including cleanup refusal;
only that test's own fixture was recovered using existing owner cleanup. No
private-key header remains in its test directories.

Pinned `npm ci --ignore-scripts` reported 13 vulnerabilities (3 moderate, 10 high).
They were not hidden or auto-fixed; the lockfile did not change. SQLite/runtime
notices remain in logs. No native build warning count is asserted for NOT_RUN.
CR-at-EOL-aware Git whitespace validation passes.

## P35-PREP-CI-01: Exact Request

No current authority permits this pure-firmware branch's staging/commit/push or
dispatch. Request only the twelve paths above on
`Eitan-S-23/E-Track`, `dev/firmware/p35-candidate-20261027`, and one development
dispatch of `.github/workflows/firmware-build.yml` after binding the new commit:
`version_name=3.2.90`, `firmware_build_profile=p34-v2-candidate`,
`publish=false`, `rehearsal=false`, `check_bindings=false`, empty
`approved_rehearsal_run_id` and `release_notes`. No main/tag/force push, merge,
protection or credential edits. The development-only keyed candidate recipe
uses its existing fixture key and must never supply installation artifacts.

Real protected-key candidate build remains NOT_RUN. After independent review,
root/configuration owners must separately resolve these exact approval inputs:

| Input | Next owner action |
| --- | --- |
| Stable source/branch | Bind the newly reviewed commit and this exact branch; do not borrow an old P4 branch to bypass admission. |
| `firmware-rehearsal` admission | Obtain actual authority for the exact branch, keeping required reviewers/protections. Nothing changed here. |
| Protected inputs | `firmware_build_profile=p34-v2-candidate`, rehearsal=true, publish=false, check_bindings=false, OTA_BOOT_CHAIN_READY=false. |
| Forward versions | Proposed receiver 3.2.90 / target 3.2.91, subject to current monotonicity/availability. Neither reserved, built, registered nor installed. |
| `OTA_PREVIOUS_RELEASE_JSON` | Evaluate existing inaugural base originals, bind targetCommitSha to the new reviewed source and targetVersionName to the exact target. A rehearsal receiver is not automatically a formal patch base. |
| `OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256` | Approval owner binds the updated descriptor digest; old 2756ca95 / 3.2.9 target approval cannot be reused. Retain source/archive/run/blob evidence. |
| Existing key and isolated resources | Reuse FIRMWARE_REHEARSAL_OTA_AES_KEY, Worker e-track-firmware-p41-test, D1 2617e1e1-956f-42ce-a465-da56d84abf06, R2 e-track-firmware-p41-test-releases; no new key/hash approval variable. |
| P35-PREP-KEY-01 | Reviewer/device owner reviews protected-key receiver transition and Boot compatibility. Later J-Link installation needs a separate admitted state/device plan. |

These are remaining decisions, not new authority, platform changes or cloud
readiness claims. Production/P5 and approved run/attempt/metadata/evidence hashes
cannot be borrowed from old successes. Access login, endpoint-bound APK and real
phone observation route remain preparation/review-owner work outside this batch.

## Write Audit And Next Owner

Selected writes: the ten source/test files, two task documents, this worktree's
`.cache/` home/cache/temp/receipts/fixtures and Worker `node_modules`. All stay
inside the explicit guarded root. Worktree creation additionally used prechecked
common project `.git` worktree/index and this branch's ref/reflog; no Git staging,
commit or push followed. No PowerShell, external output/move/cleanup, cloud
mutation or device action was selected. Package tests cleaned only their own
project-local temporary allocations; other originals remain. Final path,
receipt and private-header checks are recorded in `audit-final-01.*`.

Next: independent reviewer checks this uncommitted delta/originals; user/root
decides the exact commit/push/development-CI request. Configuration owner handles
protected admission/descriptors without weakening gates. Stop here pending that
decision, not another local build, unchanged APK/EXE run or device action.

## Authorized Development Delivery, 2026-10-27

The user approved the preceding exact twelve-file commit/push and one
nonpublishing development dispatch. The earlier authorization-pending statement
is historical for this scope only; protected rehearsal admission, descriptor
updates, main/production delivery and device work remain excluded.

Before staging, all ten implementation/test files still match the recorded
development byte bindings. Only this task record gains this authorization note.
Git/GitHub commands use the existing Eitan-S-23 identity; global hooks are
read-only, their controllable home/cache/temp outputs are project-contained,
and the optional duplicate chat notification is disabled. Preserve pre-commit
checks, explicit message input, no new key or global configuration writes.
The single dispatch will use the exact newly committed source and the parameters
in P35-PREP-CI-01 above. Results remain NOT_RUN until the run and actual jobs
are observed; no dispatch or final build success is claimed by this note.

## Development CI Outcome And Stable Source

The authorized twelve-file implementation was committed/pushed as
`7a2aea1a81f0d702b804e2935785381611d579c9`. Exactly one dispatch produced
[40374040338/1](https://github.com/Eitan-S-23/E-Track/actions/runs/40374040338)
at that source/branch, with the precise nonpublishing parameters above. It
completed successfully at 2026-10-26T18:03:28Z (2026-10-27 local date).
This supersedes earlier local-only/NOT_RUN statements for development CI, not
for the protected-key receiver or formal acceptance.

| Job / observed gate | Result |
| --- | --- |
| GCC build, 121752112904 | PASS: baseline App/Boot, existing layout/tests, development byte preparation, explicit keyed candidate build/preparation, private-header cleanup and strict uploads. |
| Release tooling development checks, 121752113537 | PASS: script/migration host 41; pipeline host 156; native workerd tests 283; workflow/S3/profile 140; byte preparation 25; package replay tests 8; vectors/typecheck and credential-free Worker bundle steps passed. Native workerd tests are not live staging qualification. |
| Binding qualification, 121752827558 | SKIPPED, no executed steps. |
| Protected rehearsal, 121753128724 | SKIPPED, no executed steps. |
| Production, 121753128526 | SKIPPED, no executed steps. |

Only this existing run's logs and artifact metadata were retrieved. To verify
actual compiled inputs, one keyed-development artifact ZIP was downloaded:
ID `12672334944`, 3266327 bytes, SHA-256
`7e5237014100e6c38187db8a16cbbd885cf0da88a28aff07d33b8f91cc8aa035`,
expiry 2026-11-09T18:03:18Z. ZIP digest/source/run, eight build-artifact hashes,
final/asset bytes and all build/preparation step-output hashes were checked.
Only 31 original text/JSON/ninja files were extracted; no firmware binary was
extracted or installed. The ZIP has no private-key header. Originals and the
extraction inventory are in `.cache/ci-40374040338/`.

The actual product configuration parser reevaluated those originals and checked
all 387 App compile recipes. Actual CMake argv and cache select candidate ON,
early vectors ON, experiment OFF and fallback UART 921600. The resulting
configuration exactly matches both keyed build and preparation provenance.
The compiled key-source SHA also matches its exact Git blob at `7a2aea1a`.
Compiler cache is DISABLED, Boot is not an AES consumer and all development-only
markers remain noninstallable/nonpublishable. SourceDateEpoch is 1786320000;
finalization's source-bound build timestamp is 1793037463. These are build facts,
not an observed module baud or device performance result.

| Candidate artifact, development fixture key only | Bytes / SHA-256 |
| --- | --- |
| GCC App placeholder | 614076 / `903e1d960dcd56466c3a395cf7269ac1eb3a33bc994228a522346563c838fab2` |
| Matching Boot | 14724 / `3554e193f498d23210f5ef32e09de64575b7cd39104fafcc950740e5e8a7ec34` |
| Finalized App image, version 3.2.90 / 30290 | 614076 / `fba3a9f2f0422321ce4cbf9176f8925116ba463023b99749807050d90eec7764` |

The real candidate development preparation passed full-byte equality and recovery
verification, with no patch/base and `r2Verified=false`. Its 3.2.90 version label
does not reserve or register a business release. Do not install these fixture-key
images or present them as the admitted protected-key receiver.

Warning accounting is explicit: candidate build step records **641 compiler
warning lines / 0 error lines**; configure/size record zero. Baseline GCC console
has 640 compiler warning lines. Runtime/action deprecations and dependency audit
notices remain separately visible in the raw console; this is not a warning-free
build. Berkeley size originals report App text/data/bss 611704/940/558632 and
Boot 14720/4/9780, without treating aggregate BSS as a single-bank runtime proof.

The complete raw console is `.cache/records/delivery-logs-01.log`, 2726967 bytes,
SHA-256 `6ee8143e538b861864a46bb87bc374cc97fa39eadbe1dc4658ef3f93b1064276`.
Run/dispatch/artifact originals are `delivery-run-final-01.*`,
`delivery-dispatch-01.*`, `delivery-artifacts-01.*` and `delivery-keyed-zip-01.*`.
Independent implementation-side original checks are
`delivery-extract-originals-01.*`, `delivery-verify-originals-01.*` and
`delivery-diagnostics-01.*`; these are self-checks, not independent acceptance.

Commit-process audit found that the contained HOME hid the global hooks setting
for the initial commit. No commit was amended or rewritten. The unchanged global
pre-commit hook was replayed against that exact immutable delta and passed in
`delivery-hook-03.*`. Two prior replay-adapter failures (hook-relative library
lookup, then unset optional variables) remain in `delivery-hook-01/02.*`.
Subsequent Git commands explicitly bind the read-only global hook path, preserve
checks and disable only optional duplicate chat notification.

This outcome adds only task records under the same authorization. Any later
record-only delivery commit is not the source of the already-built artifacts:
CI and ZIP remain bound to `7a2aea1a`, with no second dispatch or product change.
Main, old Flutter artifact inputs, reviewer notes, protected branch/descriptor
rules, cloud resources and devices remain unchanged. The scoped local outputs
are the existing worktree/cache and authorized common Git metadata; no external
output or cleanup was selected.

Implementation/build wiring is ready for the existing independent reviewer to
consume. P35-PREP-KEY-01 and protected P35-PREP-CI-01 remain open for root and
configuration owners; they must bind the actual selected ref/profile/forward
version and descriptor before a protected-key build. No new business key or
device operation is needed to review this delivery. P3-5/P5/release remain unrun.
