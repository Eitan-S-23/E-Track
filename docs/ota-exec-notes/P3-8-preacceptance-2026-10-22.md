# P3-8 Independent Preacceptance Review

Latest follow-up: [2026-10-24 phone admission](#phone-admission-2026-10-24).
The [2026-10-23 R04 re-review](#r04-re-review-2026-10-23) checks
`8ede0920` / `6ec6c5ce`. R01/R02/R03/R04 are closed in software pre-review.
The user has now authorized taking over real-device acceptance. Phone identity
has been observed; formal execution remains NOT_RUN pending the admitted
worktree, runner, installed-candidate and firmware/fixture bindings below.
The original reviews, failed attempts and non-executable drafts below are retained.

## Status And Identity

- Reviewer: Codex root, independent of the implementation author, 2026-10-22.
- Handoff: session `01a161cc-1ecc-7f00-886a-aec0d53b8b6c`; the user asked this
  session to take over its unfinished review and acceptance preparation.
- Sole Spec: `docs/ota-prompts/prompt-P3-8-implementation.md`.
- Base: `2f4946a15e2ef4ad6c4857b69e3abcba5b864fd1`.
- Reviewed candidate: `5d2a0fa6fee9d58a608a068a7bff9f3d8e31f3a9`.
- Candidate tree: `40f881552e9222769c90c76267f5957e39cfd100`.
- Profile configuration blob: `5ef97ae98674373c3cf641676c16ff7baf1b617f`.
- App subtree: `1b802bec704e6f71374e27e2dca4aa9bdd59b79c`.
- Delivery record: `2a46ecdf50512bdfd8c8540f0f295ca208932a41`, on
  `dev/flutter/p3-8-background-ota-20261021`; this changes the board and work log,
  not the implementation inputs. Read its
  `docs/ota-exec-notes/P3-8-implementation-2026-10-21.md` with `git show`.
- Source references below are line numbers in the reviewed candidate, not the
  dirty root checkout. The implementation worktree remains read-only here.
- Disposition: **four required source fixes before formal execution admission**.
  This is a concentrated pre-review under execution contract section 7.3, not a
  formally executed PRODUCT_FAIL round. New regression cases and hardware checks
  have not been executed. No independent PASS or completed card is claimed.

## Existing Evidence Reconciliation

Existing originals are under the implementation worktree's `.cache/p38/`, i.e.
`.cache/p3-8-implementation-20261021/.cache/p38/` relative to the active root.
They were read, not replaced. The machine-readable audit and command record are
in [the review directory](P3-8-preacceptance-2026-10-22/).

| Observation | Independently checked result | Limit |
| --- | --- | --- |
| Development run `39697643246`, candidate `5d2a0fa6` | Both hosted jobs successful; full analyze exit 0; Ubuntu 739 passed / 16 skipped / 0 failed, Windows 722 / 33 / 0 | Original result JSON, raw log endings and GitHub job identity checked; not a new test execution |
| Native Service tests from that run | JUnit has 13 named cases, 0 skipped, 0 failures, 0 errors; Gradle exit 0 | Robolectric SDK 34; FakeRuntime substitutes for the real Flutter engine/BLE owner |
| Debug APK | 131748470 bytes; original apksigner verification exit 0; metadata and file hash agree | Production application ID, development signing; not installed |
| Standard build `39700401326` | Android job `119568062672` and Windows job `119568062707` successful at the same candidate; original test and build logs retained | Pages and Create GitHub Release both skipped; no publishing/deployment |
| Windows distribution | ZIP contains `ble_monitor.exe`, `flutter_windows.dll`, data and supporting binaries; embedded main EXE hash matches the separate EXE | No EXE executed |
| Record-only run `39707198784` | GitHub reports success at `2a46ecdf`, attempt 1 | Does not change App inputs or add hardware evidence |

Actual SDK: Flutter 3.47.7, Dart 3.13.5, framework
`abaf9c523780a608bd46686fd5e53740a07077f8`, engine
`deb287481e3ce9468f3434937ced4240a70539ca` on both development hosts.
The result JSON also records effective Flutter-generated toolchain deltas and
the restored source state; do not describe the build as using unmodified Git
bytes for those generated files.

| Artifact | SHA-256 |
| --- | --- |
| Debug APK | `aec3a68e86ebbb7573697a504861b410a4210b89cb9a70c6c8e6c5606e3bf7cd` |
| Standard APK | `626ca75be7ea481e8cc2249f7a5811132e95490b456bec1106b5f5b6c6e7abcd` |
| Windows EXE | `6f65b13859b3846801c64543f8363c7d82aa92742987d56571fcf35e28f17cdb` |
| Windows ZIP | `5ad8cac64d7baf55b7dbd3bbe09bdafb89ef9cc5f8581cb66d6711000247ed51` |
| Standard Actions logs ZIP | `33f338f5ea0800d585f077bd637da211021b468ac258647aa69eddfa7b544201` |

The Android release build has **10 warning lines**: three toolchain support
deprecations and seven plugins requesting Android SDK 36 or newer. The Windows
release build has no warning line. Both builds succeeded with no compile error;
this review does not silently turn the warnings into a separate toolchain task.
Earlier failed development runs remain historical failures, not overwritten PASS.

These development originals can support a later, explicitly frozen independent
offline evaluation under section 0.1. They are not an existing P3-8 formal
EXECUTED PASS bundle and must not be entered as REUSED.

## Consolidated Findings

All four findings are static control-flow findings on the same fixed candidate.
Their proposed new runtime regression oracles remain NOT_RUN. The existing
passing tests do not exercise the distinguishing sequences below. Fix them as
one implementation batch; do not start four formal acceptance rounds.

### P38-R01: Late Resume Can Unpause An Unowned Background Transfer

- Priority/disposition: P1, required fix; `OTA-XC-ANDROID-OTA-BACKGROUND` safe
  fallback and same-owner requirements.
- Evidence: `lib/services/ota_service.dart` lines 294-319 start an unawaited
  `resumeFromBackground()` after returning to the foreground. Its checks at
  lines 1820-1821 and 1879-1889 fence cancellation, transport replacement and
  link identity, but not a later lifecycle transition. Line 1948 resumes the
  transport after asynchronous rediscovery and GET_INFO without checking that
  the App is still foreground or currently has acknowledged background ownership.
- Sequence: no acquired background owner; pause; resume and hold rediscovery or
  GET_INFO; pause again; complete the old recheck. The second pause is undone by
  the late first resume, allowing DATA/END without background ownership while
  the published task still reports safe pause.
- Preferred repair: bind foreground recovery to a lifecycle/recovery epoch and
  recheck it after every await and immediately before unpausing. Re-entering the
  background without acquisition must invalidate the old recovery. Also make
  foreground wait gates recheck eligibility after awakening instead of treating
  an earlier resumed event as permanent authorization.
- Invariants: retain link/characteristic/full identity checks, MCU durable truth,
  cancellation locks and acquired-background uninterrupted operation. This
  inherited recovery gap is not a reopening of the accepted P3-3-v9 bundle.
- Oracle: gate recheck completion, drive resumed -> paused -> late completion;
  assert no extra DATA/END, paused snapshot and no duplicate BEGIN. A subsequent
  genuine foreground recovery must pass identity checks and resume once.
- Next owner: original implementation owner; add service-level lifecycle race
  coverage, then return the changed commit and original targeted/full CI results.

### P38-R02: Internal Notification URI Reaches Flutter Before Key Validation

- Priority/disposition: P2, required fix; stale-event isolation and notification
  navigation in `OTA-XC-OTA-PROGRESS`.
- Evidence: `DeviceOtaService.kt` lines 154-164 put a
  `trace-device-ota://task/<task>/<generation>/open` URI on the Intent.
  `MainActivity.kt` lines 92-95 call `super.onNewIntent(intent)` before
  `DeviceOtaBridge.consumeOpen(intent)`. The Manifest does not disable Flutter's
  default deep-link handling. Thus even a rejected stale task can already push
  an internal URI into Flutter navigation before the task-bound handler returns.
- SDK cross-check: at the recorded Flutter framework revision,
  `FlutterActivityAndFragmentDelegate.java` lines 970-980 forward any nonempty
  Intent data through `navigationChannel.pushRouteInformation`; lines 551-558
  do not restrict its action/scheme. `FlutterActivityLaunchConfigs.deepLinkEnabled`
  defaults to true. These sources were fetched read-only from the matching
  `flutter/flutter` revision, not inferred from an unrelated SDK version.
- Preferred repair: consume/sanitize the internal device-OTA action before the
  superclass can interpret its URI, or suppress only its automatic routing.
  Keep existing external `trace://` links and plugin Intent delivery working.
  Check the recreated-Activity initial-Intent path as well as onNewIntent.
- Oracle: active internal Intent produces exactly one `/device-ota` navigation;
  stale task/generation produces none and does not change the current route;
  ordinary external deep links retain their previous behavior. Cover the actual
  Activity/embedding boundary, not just a FakeRuntime service event.
- Next owner: original implementation owner; Android routing plus regression.

### P38-R03: Foreground Gate Can Outlive The Reboot Verification Deadline

- Priority/disposition: P2, required fix; bounded recovery and terminal cleanup.
- Evidence: `_waitForForeground()` at `ota_service.dart` lines 281-284 waits on
  an unbounded Completer. `_waitForTargetIdentity()` creates the absolute reboot
  deadline at line 2120 but awaits that gate at lines 2127 and 2139 outside any
  remaining-budget timeout. After END, `canCancelTask` is false.
- Sequence: END accepted; background owner is lost while App remains background;
  foreground gate is reached and the user does not return. The existing 180 s
  deadline cannot be checked, the OTA owner/scan lease cannot reach finalization,
  and the UI cancellation route cannot release this verification wait.
- Preferred repair: bound foreground waiting by the existing absolute reboot
  deadline and settle the unresolved result/cleanup at expiry, without sending
  new background probes. Do not restart the timer on each lifecycle event.
- Invariants: no invented completed status, no ABORT promise after application,
  no repeated successful OTA to recover missing verification. Later foreground
  recovery must reconcile the actual version/full raw SHA through read-only
  identity observation first.
- Oracle: use a short injected reboot window; lose acquisition after END and
  stay background beyond the window. The owner must finish with an honest
  unresolved/timeout state and release resources without new probes or user
  input. Also cover returning before the deadline.
- Next owner: original implementation owner; extend the existing ownership-loss
  test, which currently returns to foreground after only 50 ms.

### P38-R04: Notification-Created Page Does Not Bind The Active Target

- Priority/disposition: P2, required fix; task reattachment and usable recovery UI.
- Evidence: `lib/main.dart` opens `/device-ota` with `const OtaUpgradePage()` and
  no device parameter. In `ota_upgrade_page.dart`, `_deviceAddress` depends only
  on widget/resolved device (lines 59-64), but `_resolveDeviceAndRead()` returns
  before even resolving it while an owner is active (lines 142-146). No owner
  completion observer fills it later. `_deviceReady` gates subsequent actions
  at lines 409-413.
- Sequence: open a fresh page from the active notification; let that task cancel
  or end without another lifecycle/connection event. Its progress can be shown,
  but the page retains a null address, leaving subsequent check/transfer actions
  unavailable despite the service's known target and an existing connection.
- Preferred repair: attach display/target identity from the current owner without
  issuing GATT work while busy; on terminal transition, reconcile that exact
  target before enabling a new operation. Do not choose an arbitrary first
  connected device or restore cached progress as transport truth.
- Oracle: open the notification page during an active task without a device
  argument; assert one owner/no extra GET_INFO/BEGIN while busy; complete or
  cancel, then assert correct target attachment and usable identity-gated actions
  without closing/reopening the page. Include an unrelated connected device.
- Next owner: original implementation owner; task/page attachment and widget test.

## Acceptance Draft And Remaining Bindings

The [v1 draft](../acceptance-contracts/P3-8-v1.draft.contract.json) and
[NOT_RUN matrix](P3-8-preacceptance-2026-10-22/evidence-matrix.draft.json) express
the remaining criteria. They are **not executable or freeze-ready**. Command
placeholders are deliberately non-executable; no collector is claimed to exist.
The pending device JSON is an explicit list of unknowns, not a hardware receipt.
A successful `--allow-draft` check means structure only, not frozen admission.

Before FROZEN, replace the candidate with the repaired committed batch, bind
the final runner paths and actual immutable originals, fill all device/fixture
identities, obtain missing operating authority and pass the normal NOT_RUN
preflight in a clean admitted worktree. Do not invent a new component profile
to make the dirty root checkout admissible. The root is on an archive branch;
its unrelated dirty changes remain untouched. No worktree/Git metadata writes
or main synchronization were attempted under this read-only Git sandbox.

Missing bindings: selected phone/Android build and USB identity; actual installed
APK hash, application ID, signer and update compatibility; board App/Boot/BCB/
staging state; immutable ETU length/hash, source/target versions and complete raw
image hashes; observer configuration and retrieval route; safe recovery assets;
sole device operator and current user-approved scope. Neither this task request
nor the CI authorization supplies those physical bindings/permissions.

## Finite Device Operation Draft

This is a proposed coverage matrix, not a new authorization or a permanent OTA
quota. Freeze exact commands, identities and bounds only after remediation.
Prefer the existing contained USB/App observation and SEGGER routes; do not
build a new flasher or repeat a successful upgrade because retrieval failed.

| Cell | Proposed bounded work | Decisive observation |
| --- | --- | --- |
| D0 | One read-only phone/board/asset preflight; APK install only if necessary and separately covered | Correct signer/update route, complete firmware and persistent-state compatibility, collector readiness; no uninstall/clear-data workaround |
| D1 | One notification-permission/channel denial-and-restoration case; bounded foreground/hidden/resumed transitions; no END | Explicit unacquired reason, no background sends, strict foreground recovery, no late resume after a second pause; restore the prior notification setting |
| D2 | One acquired partial transfer with normal app switch, lockscreen and notification-return windows, then cancel before END | Each background/lock window has timestamped increasing MCU durable samples; one task/sender; UI/notification agree; task-bound cancellation and released resources |
| D3 | Resume the verified same package with one planned pre-END disconnect/reconnect, then complete and verify once | Fresh device/package checks and BEGIN durable recovery; no cached-progress trust; new-link target version/full raw SHA match; terminal service/lock/subscription release |

Each D1/D2 lifecycle window is at most 30 s and requires decisive observations,
not a manufactured speed threshold. Preserve the existing no-durable-progress
limit. If the immutable package cannot accommodate a required window before END,
record that coverage gap and revise the planned fixture before execution; do not
quietly replay completed transfers. Proposed per-transfer host deadline: 15 min,
with the implementation's separate 180 s reboot verification window and explicit
cleanup allowance. These host bounds are not product performance acceptance gates.

Only D3 is intended to finish firmware application. Plan up to two partial
attempts and the final resume/disconnect continuation, not a P3-5 ten-disconnect
campaign or P5-1 thirty-run stability campaign. Reconcile the actual device state
after any uncertain outcome; preserve failures and stop unchanged blind retries.
The final retained state is the verified target, not an automatic downgrade.
Boot replacement, mass erase, arbitrary BCB/EEPROM writes, App-data clearing,
cloud publishing and unrelated device operations remain excluded.

## Handoff And Write Audit

- Draft verification: the existing candidate validator with `--allow-draft`
  exits 0, reporting overall NOT_RUN. The same command without that flag exits 1
  with `contract must be FROZEN`, as required. This is not the frozen execution
  preflight. `git diff --check` for the changed board/index exits 0; Git still
  emits its LF-to-CRLF conversion notice for the index. All checks and the initial
  record-format failures are retained in
  [draft-validation.json](P3-8-preacceptance-2026-10-22/draft-validation.json).

- Next implementation owner: `Codex(P3-8 implementation) / 2026-10-21` on the
  existing development branch. Address P38-R01 through P38-R04 in one batch and
  return targeted regressions, full dual-host feedback and builds applicable to
  the changed App inputs. No old assertions weakened; preserve failed runs.
- Reviewer then checks that bounded remediation and binds the stable acceptance
  inputs. It does not ask the user to operate the phone before the software and
  observation routes are ready. Formal device execution still needs its missing
  bounded authority; no repeated per-cell requests within an approved matrix.
- This handoff has not been sent to or acknowledged by another live agent.
  Root-local notes/index/board changes remain uncommitted and pending authorized
  integration; no claim of delivery to main or refresh of another session.
- This session changes only review records, DRAFT preparation and the P3-8 board/
  index entry under `D:/github/my/E-Track`. Outputs were preflighted with the
  existing host_io guard. Original evidence and implementation files are read-only.
  No local Flutter/Gradle build, device operation, commit, push, merge, release,
  deployment, cleanup or known project-external output was performed.

## Remediation Review 2026-10-23

The user asked Codex root to take over session
`01a161fa-1c90-7753-8f25-b31e9a06a5d7` after it received the repaired handoff but
failed before performing the new review. This reviewer did not author the product
repairs. This is the bounded remediation check under execution contract sections
0 and 7.3, not a new formal execution round or a whole-card PASS.

### Inputs And Scope

- Candidate: `27048aa10079d8dd01d608967e7b5d1b473861ba`, tree
  `5b004d20c083abffefa364f62ce6f3f00d79400e`.
- Handoff: `6b7601e79a422fbfb905a5c94241a2bdc5466bf5`, the implementation
  worktree's clean HEAD. It changes only the board and implementation record.
  Both commits have App subtree `492fb8e35f33012127aa8adf61a22e3d592f483d`.
- Profile configuration remains `5ef97ae98674373c3cf641676c16ff7baf1b617f`.
  The product delta from `5d2a0fa6` is limited to `ota_service.dart`,
  `ota_upgrade_page.dart`, `MainActivity.kt`, and `DeviceOtaBridge.kt`, plus
  three test files. No MCU, BLE wire format, firmware package, or cloud change.
- Source line references in this follow-up are in `27048aa1`, not the unrelated
  dirty root checkout. The implementation worktree and originals were read-only.
- Machine-readable source excerpts, dependency provenance, CI/job identities,
  original hashes and archive-member checks are in
  [remediation-review-2026-10-23.json](P3-8-preacceptance-2026-10-22/remediation-review-2026-10-23.json).
  Exact commands, the one-off reader source and preparation failures are in the
  [command record](P3-8-preacceptance-2026-10-22/remediation-review-2026-10-23.commands.json).

### Current Disposition

| ID | Disposition | Basis and limit |
| --- | --- | --- |
| P38-R01 | DECIDED: closed in remediation pre-review | `ota_service.dart` 289-309 and 1829-1984 recheck lifecycle/recovery epoch after waits and before unpausing. Original full CI includes the held-discovery and held-INFO second-pause regressions. No new device result is implied. |
| P38-R02 | DECIDED: closed in remediation pre-review | `MainActivity.kt` 26-32 and 103-115 remove the internal URI before initial/new embedding entry; `DeviceOtaBridge.kt` 222-229 retains task-key validation. The five added Activity-entry cases execute in the 18-case original JUnit. The embedding is shadowed, so this is not real-engine/phone evidence. |
| P38-R03 | DECIDED: closed in remediation pre-review | The foreground wait uses the original absolute reboot deadline at `ota_service.dart` 2156-2181. The injected 400 ms ownership-loss case checks honest timeout, no further probes and cleanup; the before-deadline recovery case remains. |
| P38-R04 | DECIDED: P2 required fix remains | The target is now attached, but a real identity read rearms the completed task's pending-reconciliation flag through synchronous busy notification. Existing page tests replace the real busy/epoch behavior and do not close this oracle. |

### P38-R04 Follow-up: Reconciliation Rearms Itself

This is a newly identified control-flow defect in the first R04 remediation,
not a claim that its original fake-based tests failed. The distinguishing
real-service/widget regression has **NOT_RUN** in this reviewer session.

Evidence:

- `ota_service.dart` 180-183 exposes the global `_isUpgrading` stream as
  `taskActivity`; `taskDeviceAddress` checks the task key against `_ownerEpoch`.
- A real `readDeviceInfo` takes `_runExclusive` at lines 554-560. That function
  publishes `_isUpgrading.value = true` at line 2067, before advancing
  `_ownerEpoch` at line 2071. The old completed task key is still visible to a
  synchronous listener at the moment the busy event is delivered.
- `ota_upgrade_page.dart` 77-83 treats every busy event as task attachment.
  `_attachCurrentTask` at 183-190 sets `_needsTaskReconcile = true`, including
  while `_reconcilingTask` is already true. The guard at line 167 then ignores
  the corresponding idle-triggered reconciliation; the outer finally at
  174-175 clears only `_reconcilingTask`.
- `_deviceReady` at 68-70 requires both flags to be false, and the check button
  consumes it at 454-458. The page can therefore finish a successful GET_INFO
  and still leave its action disabled until an extra refresh/reopen event.
- The pinned GetX 4.7.2 archive was read in memory and its SHA-256 matched
  `pubspec.lock`: `c79eeb4339f1f3deffd9ec912f8a923834bec55f7b49c9e882b8fef2c139d425`.
  `rx_impl.dart` 98-105 calls `subject.add` synchronously; `get_stream.dart`
  43-50/94-98 invokes the subscribed callback inline. The archive/member hashes
  and exact excerpts are retained in the machine-readable review, not inferred
  from a different GetX version.
- The page fixture at `ota_upgrade_page_test.dart` 730-741 only waits on
  `readGate` and publishes identity. It never performs the real read's
  busy/owner-epoch transitions, so the new tests at 588-627 miss this sequence.

Decisive sequence: active task ends -> page marks reconciliation in flight ->
real identity read emits busy with the old epoch -> page rearms the old pending
flag -> identity read emits idle while reconciliation is still in flight ->
guard drops that attempt -> outer finally leaves the pending flag set.

Preferred minimal repair: complete owner/generation registration before publishing
observable busy state in `_runExclusive`, so a new plain identity query cannot
expose the completed OTA key. Also keep the page's own reconciliation from
reattaching/rearming that completed task. Do not treat all generic busy changes
as a new OTA task identity. Preserve synchronous exclusive ownership before the
first await, cancellation-generation barriers, exact target binding and the rule
that successful identity verification precedes enabling actions.

Verification oracle: exercise the notification page with real `OtaService` and
the existing fake BLE, or a fixture that preserves its actual synchronous
busy/epoch transitions. For completed/cancelled/failed tasks, require one
identity read for the task's exact target, no extra BEGIN, no stuck flag or
reconciliation loop, and usable controls after the successful read without
another lifecycle event or reopening the page. Keep the unrelated-device case;
a failed identity read must still leave controls disabled. The current candidate
must fail the distinguishing case before the repair, then pass it after repair.

### Verified Existing Originals

| Original | Independent check |
| --- | --- |
| Development run [39789686610](https://github.com/Eitan-S-23/E-Track/actions/runs/39789686610), attempt 1 | Both exact GitHub jobs SUCCESS at `27048aa1`; full analyze exits 0; terminal raw summaries are Ubuntu 746 passed / 16 skipped / 0 failed and Windows 729 / 33 / 0. |
| Android JUnit | 18 distinct cases, 0 skipped/failures/errors; includes the five real MainActivity-entry cases and the original 13 Service cases. Not a real Flutter engine or phone run. |
| Standard run [39791568439](https://github.com/Eitan-S-23/E-Track/actions/runs/39791568439), attempt 1 | Android job `119868855099` and Windows job `119868855022` SUCCESS at `27048aa1`; raw tests/build outputs retained. Pages and Release jobs SKIPPED. |
| Retained artifacts | Debug APK, standard APK, standalone EXE and full Windows ZIP hashes match the handoff. Five original artifact ZIPs match GitHub-published digests; CRC and every consumed extracted member were checked against its original ZIP. The Windows ZIP's embedded EXE matches the standalone EXE. |

Both development hosts used Flutter 3.47.7 / Dart 3.13.5, framework
`abaf9c523780a608bd46686fd5e53740a07077f8` and engine
`deb287481e3ce9468f3434937ced4240a70539ca`. Effective Flutter-generated configuration
changes are retained, not described as unmodified committed build bytes. Windows
post-restoration `clean` is actually false solely for the recorded generated
header EOL difference; semantic and untracked differences are empty. The first
reader's over-strict clean-flag assertion was corrected against the existing
runner's semantic-state policy; its failed check is preserved in the command record.

The standard Android build retains **10 warning lines** and one non-fatal
`Caught exception: Already watching path`; Windows has 0 warning lines. These
remain visible diagnostics, not a new dependency-upgrade task. Partial download
attempts were neither trusted nor deleted. No successful CI/build was replayed.

### Next Owner And Execution Boundary

- Original implementation owner: repair the remaining P38-R04 batch on
  `dev/flutter/p3-8-background-ota-20261021`, add the distinguishing integration
  regression and return original development checks/builds for changed App inputs
  through the existing authorized route. Do not weaken the passing assertions.
- Independent reviewer: recheck R04 and affected shared ownership/page paths after
  that batch. R01/R02/R03 are not reopened merely because the reviewer changed.
  A source fix or successful offline audit is not formal acceptance.
- Formal preparation remains gated by R04. The unchanged seven-criterion draft
  still names `5d2a0fa6`, is DRAFT/NOT_RUN and must not be executed or treated as
  the repaired candidate's freeze. The existing device-binding and D0..D3 gaps
  remain; do not request a phone window before the software and collectors are ready.
- This session changed only the root review/index/board and its compact evidence,
  plus a project-local one-off read-only evaluator. The evaluator source is also
  retained in the command record; it is not an admitted formal runner. All paths
  were checked with the existing output guard. No PowerShell startup, local App
  build, CI dispatch, device operation, product edit, commit/push, main integration,
  publishing, external-project output or cleanup was performed.
- Records are uncommitted and pending authorized integration. No live
  implementation-agent receipt or delivery to main is claimed.

## R04 Re-review 2026-10-23

The user asked this independent Codex root session to take over
`01a16451-4704-7b10-933e-6d9dd05a0362` after its R04 handoff request failed
before review. This session did not author the product changes. The sole Spec,
review scope and formal-acceptance boundary above remain unchanged.

### Decision And Inputs

**P38-R04: DECIDED, closed in software remediation review.** No additional
required source defect was found in this bounded delta. R01/R02/R03 retain
their preceding software pre-review closure. This is not a whole-card PASS,
new formal execution round, or proof of real Android background operation.

- Candidate: `8ede09208a0857b716ee9614c09cb83247c2bc39`; tree
  `de43d94830549b4c917ef0155c175baa1f92d336`.
- Handoff: `6ec6c5ce3189de79794fc0cc437e9b024767ee5d` on
  `dev/flutter/p3-8-background-ota-20261021`.
- Both have App tree `e22fb7a6db1c47304354c7652c0ddf9693d4818b` and profile
  blob `5ef97ae98674373c3cf641676c16ff7baf1b617f`.
- Relative to `27048aa1`, product changes are only `ota_service.dart` and
  `ota_upgrade_page.dart`; new regressions are in
  `test/ota/ota_service_upgrade_test.dart`. Android, dependencies, runners,
  workflows, BLE wire semantics and MCU inputs are unchanged.
- References below use candidate line numbers, not the dirty root checkout.
  The root's published governance was checked against local `main`
  `b42d3e25`; no branch switch or Git metadata write was needed.

The repair addresses both observed synchronous boundaries:

1. `ota_service.dart` 2067-2075 registers the owner future, epoch and cancellation
   generation before publishing busy. A plain query cannot expose the completed
   OTA key, and cancellation from an inline busy listener sees the registered
   query and fences its body. Exclusive ownership still precedes the first await.
2. `ota_upgrade_page.dart` 164-215 prevents self-reattachment while reconciling
   and waits for both owner exit and a settled terminal/ready phase. Its phase
   listener covers cancellation publishing its result after busy becomes false;
   the page query no longer advances the epoch in that gap. Both subscriptions
   are cancelled at disposal (122-125). Exact-target and successful-identity
   gates remain in place.

The seven new cases at `ota_service_upgrade_test.dart` 326-459 use real
`OtaService`, real `OtaUpgradePage` and synchronous GetX delivery, with the
existing fake BLE/HTTP/background-service boundary. They cover completed-key
visibility, inline-busy cancellation, completed/cancelled/failed page recovery,
an unrelated explicit page device and rejected identity. They assert no extra
BEGIN/query while active, one exact-target identity reconciliation, disabled
controls while verification is held, no query loop, preserved terminal phase,
and enabled controls only after successful identity verification. They do not
replace real-engine, native-service or phone observations.

### Original Results And Provenance

All counts below were read from full raw logs and bound to their original
result JSON and immutable GitHub artifact ZIP members. Skips are 16 on Ubuntu
and 33 on Windows throughout; they are not counted as passes.

| Input / original run | Independently verified result and interpretation |
| --- | --- |
| Tests-only `14e5d157`, run `39823659366` | Ubuntu 635 / Windows 618 passed, 1 failure each: an ambiguous BluetoothService import prevents this test file loading. Not the behavioral red oracle. |
| Tests-only `1ecabeca`, run `39824670865` | 746 / 729 passed, 6 failed on each host. Product `lib/` and `android/` are identical to `27048aa1`. The busy callback exposes `aa:bb` rather than null; four positive real-page cases leave controls disabled. The sixth failure is a malformed-INFO fixture's incorrect one-query assumption, not another product defect. |
| First repair `596cc08b`, run `39826146792` | 748 / 731 passed, 5 failures each, with actual pending-animation-timer assertions; analysis also flags missing braces. These failures remain failures. |
| Candidate `8ede0920`, [development run 39827513211](https://github.com/Eitan-S-23/E-Track/actions/runs/39827513211) | Both jobs SUCCESS; full analyze exits 0; Ubuntu 753 / Windows 736 passed, 0 failed. All seven exact new case names execute on both hosts. |
| Same candidate, [standard run 39829695971](https://github.com/Eitan-S-23/E-Track/actions/runs/39829695971) | Android job `120002449663` and Windows job `120002449651` SUCCESS, including full 753/736 tests and APK/EXE builds. Pages and Release jobs SKIPPED. |
| Documentation handoff `6ec6c5ce`, [run 39845776205](https://github.com/Eitan-S-23/E-Track/actions/runs/39845776205) | Both development jobs SUCCESS. Same App tree; supplementary delivery feedback, not another product or hardware observation. |

The final `596cc08b..8ede0920` App diff only adds braces and drains the disposed
fixture's delayed animation callbacks with a one-second pump. It does not disable
timer invariants or weaken behavioral assertions. The negative INFO fixture was
changed to a structurally valid unknown model, retaining failed-identity gating
without mistaking legitimate transport retries for a reconciliation loop.

The checked SDK remains Flutter 3.47.7 / Dart 3.13.5, framework
`abaf9c523780a608bd46686fd5e53740a07077f8`, engine
`deb287481e3ce9468f3434937ced4240a70539ca`. Actual generated-toolchain deltas
and Windows' restored generated-header EOL-only state are retained. A truncated
console-diagnostic excerpt does not truncate the separately archived full log;
its actual byte count and ZIP member hash were checked.

Eight small development ZIPs were retrieved once into the reviewer's own
project-local cache. Their published SHA-256 values and all 48 consumed result/
log members match. Both existing standard artifact ZIPs match GitHub digests;
their three extracted products match, APK/Windows ZIP CRC checks pass, and the
Windows ZIP's embedded EXE equals the standalone EXE byte-for-byte.

| Candidate product | Bytes | SHA-256 |
| --- | --- | --- |
| Standard APK | 47272692 | `1ef9cd86b35bd175b238a9c6ce542ce5fb991543fd0470684e82836e025b0f8d` |
| Standalone EXE | 93184 | `bb111ec40f24d74e971e6291d27e99d54f003993ad00c1cd2b1ad347a9b07be7` |
| Full Windows ZIP | 20485471 | `cda4b776e33927fcddf9cb6c2d75c7ce654d3c0eed8366719eb6c06793f2b6ca` |

Android retains **10 warning lines** and the non-fatal `Already watching path`
exception; Windows has 0 build warning lines. The unchanged Android scope keeps
the prior 18/18 native JUnit original; its bytes and zero-failure XML were
rechecked, not newly executed. No new debug APK or new native Service test run
is claimed.

The compact [R04 review record](P3-8-preacceptance-2026-10-22/r04-review-2026-10-23.json)
contains exact Git/source excerpts, public run/job identities, raw failure
observations, SDK/input deltas, archive/member hashes and the executed reader.
The [command record](P3-8-preacceptance-2026-10-22/r04-review-2026-10-23.commands.json)
preserves the first reader failure: it counted a legacy page test sharing the
R04 label. Restricting the check to the seven full names in the actual changed
test file fixes only the reader. The next offline audit passed 344 integrity
checks; these are not 344 new product tests or formal acceptance criteria.

### Remaining Acceptance Admission

The known software remediation gate is now closed, but formal acceptance is
still **NOT_RUN**. The original seven-criterion draft, NOT_RUN matrix and
pending-device record remain unchanged at their historical `5d2a0fa6` input;
they must not be executed as a freeze of `8ede0920`.

Next owner is the independent root/acceptance operator, not another product
remediation round. Prepare the stable candidate's real runner/input bindings
under the same Spec, then obtain the still-missing bounded device authority:

- Bind the selected phone/Android/USB identity, installed APK/application ID,
  signer and update compatibility against the exact new standard APK above.
  No APK has been installed or executed by this review.
- Bind actual App/Boot/BCB/staging state, immutable ETU length/hash and complete
  source/target image identities, safe recovery assets and the sole operator.
- Finish and verify the observation/retrieval route before opening a phone
  window; do not treat the draft's placeholders as an implemented collector.
- Approve/freeze the existing D0..D3 coverage with those bindings and admitted
  runner paths, then perform the normal clean-worktree NOT_RUN preflight.
  Only missing real observations are new work; no successful OTA is replayed
  merely to change reviewer or repair retrieval.

Actual background/lockscreen durable advancement, notification interaction,
permission fallback, disconnect recovery, new-link target version/full raw SHA
and physical service/lock/subscription cleanup remain unobserved here. Existing
P3-3/P3-4 results and unchanged native tests cannot fill those P3-8 gaps.

This review edits only its own root-local records/index/board and owned cache.
No product edit, local App build, CI rerun, device operation, commit/push,
main integration, publishing, cleanup or known project-external write occurred.
The records remain uncommitted and pending authorized integration.

## Phone Admission 2026-10-24

The current user requested real-device acceptance and continued autonomous work
until actual intervention is necessary. This covers preparing the bounded
P3-8 D0..D3 route, not Git commit/push/merge, data clearing, Boot replacement or
unrelated hardware. Codex root is the current independent acceptance operator;
the original implementation owner and software review dispositions are unchanged.

### Executed Read-Only Observation

- At 04:17:32..04:17:41 UTC (12:17 Beijing), 18 read-only ADB commands inspected
  the phone through a fresh private server on localhost port 5078. Phone:
  `10ADA4197U001CK`, vivo `V2312A`, Android 13 / SDK 33, current user 0.
  Fingerprint: `vivo/PD2312/PD2312:13/TP1A.220624.014/compiler06251531:user/release-keys`.
- Installed normal package `com.wen.gaia.gaia`: SHA-256
  `428a5d3a3f5c829df19e523800124712ffa30eb620ce0af277fe38352f90e382`.
  Diagnostic package `com.wen.gaia.gaia.p34probe`: SHA-256
  `858b6bd8811d3c2baaf758d0f99bb7e472192e693650018d00fd3cd3273ef68f`.
  Both report versionCode 86 / versionName 1.0.60, stopped=true and no PID.
  User 0 has Bluetooth scan/connect and notification permissions granted;
  the separate uninstalled user 999 section must not be mixed into that result.
- The candidate standard APK was rehashed in place: 47272692 bytes, SHA-256
  `1ef9cd86b35bd175b238a9c6ce542ce5fb991543fd0470684e82836e025b0f8d`,
  matching the reviewed `8ede0920` original. It is **not** the installed APK.
  Signer/update compatibility is still unverified; no install was attempted.
- Original commands/stdout/stderr/server log and result are retained under
  `.cache/p38-device-20261024/inventory-001/`. Result SHA-256:
  `d48a21d987b47038b3d646bcea53b9edb9160dbe0e9c3388e4c502c87f03993b`.
  The one-off preparation adapter is `.cache/p38-device-20261024/probe.py`,
  SHA-256 `76cb7b7eeb6839e6c8ba32963a2619638f3e9680c9c7661fe6d23f5b12a42bda`.
  It wraps standard ADB and the existing host_io guard. The old P3-4 controller
  binds historical APK/firmware/cell identities and was not replayed. This
  adapter is not a committed/admitted formal acceptance runner.
- Server stop and server exit both returned 0; the private port is closed and
  the existing read-only ADB key is unchanged. No App launch, installation,
  settings change, UI input, BLE operation, MCU access or OTA took place.

### Remaining Admission And Next Owner

Phone connectivity is no longer the blocker. Do not ask the user to reconnect
it based on the old session's unexecuted preparations. Do not use this inventory
as whole-D0 success, a source/signer match, or a P3-8 product PASS.

The root remains on the dirty archive branch. The implementation worktree at
`6ec6c5ce` has no tracked changes, but belongs to the implementation owner and
was only inspected. The historical v1 draft remains untouched with non-executable
command placeholders and its old `5d2a0fa6` identity. Execution contract section
1 requires committed runner inputs and a clean admitted worktree before formal
commands; the current user request did not authorize creating another writable
worktree or local acceptance commits. No new profile or relabeled lightweight
test is used to bypass these requirements.

Next approval requested: create only the independent acceptance worktree
`D:/github/my/E-Track/.cache/p38-acceptance-20261024`, on a new local branch
`acceptance/p3-8-device-20261024` based on `6ec6c5ce`, with its normal Git
metadata under the existing project `.git/`. Permit scoped local commits of
necessary P3-8 collector/tests and acceptance bindings/records. This request
excludes push, merge, release, deployment, changing other worktrees or committing
the root's unrelated dirty files. Keep the product candidate unchanged; any
necessary product remediation remains a separate implementation/review boundary.

After approval, the acceptance operator should finish signer-safe candidate
installation preparation, verify the observation/retrieval route and current
App/Boot/BCB/staging/recovery identities, bind a legal immutable ETU and the
finite D1..D3 matrix, then freeze/preflight and execute. Actual user-only phone
dialogs/connection/start actions are requested only when that route is ready.
No completed OTA is repeated to recover evidence.

### Output Audit

Active writable root: `D:/github/my/E-Track`. Before invocation the adapter,
inventory directory, all controlled home/AppData/temp/Android paths and shared
project-local device lock were checked with host_io; each result path was checked
again before writing. The own output tree contains 47 entries / 40 files /
69226 bytes, all within the root, with no reparse ancestry or generated host-home
files. Existing key bytes were unchanged and no PowerShell, Java, J-Link, local
App build, CI dispatch or Git write ran. No known project-external output was
created. Root note/board edits remain uncommitted; formal acceptance is NOT_RUN.
