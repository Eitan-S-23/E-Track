# P3-8 implementation work log

## Role And Entry

- Implementation owner: Codex, 2026-10-21. Not the independent reviewer.
- Sole Spec: `docs/ota-prompts/prompt-P3-8-implementation.md`.
- Worktree: `D:/github/my/E-Track/.cache/p3-8-implementation-20261021`.
- Branch: `dev/flutter/p3-8-background-ota-20261021`.
- Entry HEAD: `2f4946a15e2ef4ad6c4857b69e3abcba5b864fd1`; initially clean.
- GitHub: active `Eitan-S-23`; repository `Eitan-S-23/E-Track`; development
  workflow API reports `active`. No credentials changed or exported.
- No `.trellis/` exists in this worktree; the assigned OTA card/Spec govern.
- All controlled outputs stay in this worktree, chiefly `.cache/p38/`.
  Root/parent chains and planned output paths checked for reparse points.
  Shared `.git` is used only for this branch's normal Git operations.

## Research And Change Boundary

The existing permanent OtaService owns the exclusive operation/cancellation
locks, durable progress, package verification and reboot GET_INFO identity check.
The page currently owns background pause/resume. Android only has the separate
App-updater dataSync service, which is not a device-OTA execution guarantee.
BackgroundTaskService can restart scans on lifecycle changes.

Planned product files (all under `app/bluetooth_flutter_Trace/`):

- `lib/ota/ota_background.dart`: immutable task key/snapshot and acknowledged
  Android bridge with bounded acquisition, lease checks and stale-event fencing.
- `lib/services/ota_service.dart`: lifecycle-independent task/snapshot ownership,
  foreground fallback, cancellation and cleanup using the existing transport.
- `lib/services/background_task_service.dart`: skip background scan recovery
  while the OTA owner holds the radio.
- `lib/pages/ota_upgrade_page.dart`, `lib/main.dart`: snapshot projection and
  notification routing without recreating the sender.
- `android/app/src/main/kotlin/com/wen/gaia/gaia/MainActivity.kt`, new
  `DeviceOtaBridge.kt`/`DeviceOtaService.kt`, and `AndroidManifest.xml`: retained
  same Flutter engine, separate connectedDevice service, actual owner handshake,
  bounded wake lock and task-bound notification actions.
- `test/ota/ota_background_test.dart`, existing OTA service/page tests and new
  corresponding Android tests; `android/app/build.gradle.kts` only if necessary
  for the native test dependency.

Shared dependencies remain the current BLE transport, connection generations,
scan-pause lease, HTTP downloader, package identity and cancellation write lock.
No MCU/cloud/protocol/performance/App-self-update business changes.

## Validation Route And Gaps

- Local Flutter/Gradle/APK/EXE builds are prohibited and will not run.
- Reviewed WIP commits/pushes use only this exclusive dev/flutter branch and
  Eitan-S-23 under execution contract 7.3.2; no empty permission-probe commit.
- `flutter-dev-checks.yml`: full analyze/test on Ubuntu and Windows. Request
  debug APK explicitly with `test_scope=all,build_apk=true` once appropriate.
- Preserve initial failures, command exits, actual SDK identities and original
  artifacts under `.cache/p38/`; development results are not formal acceptance.
- P38-NATIVE-CI: current workflow runs pure-Java PHY tests and Flutter tests,
  but has no Android app service test step. Prepare bounded app-native tests;
  root must arrange/authorize the minimal Android unit-test invocation using the
  already bootstrapped CI Android SDK. Do not quietly repurpose PHY tests or
  expand a general runner. Native runtime coverage remains NOT_RUN until executed.
- P38-STANDARD-BUILD: standard release-mode APK/Windows EXE use `build.yml`,
  not the development workflow. Root must arrange its exact-candidate check-only
  run with `publish_release=false,replace_existing_release=false`; this agent
  does not dispatch it, open a PR to trigger it, merge, release or deploy.
- Device operations/real background-lockscreen evidence: NOT_RUN, no new device
  authority. Root/independent reviewer owns bounded authorization and remaining
  formal observations. No P4-4 replay, P3-5/P1-7/P5 start, or frozen-bundle edits.

## Execution Ledger

- 2026-10-22: first implementation batch adds a retained same Flutter engine,
  separate connectedDevice foreground service, asynchronous owner probe and
  bounded lease/heartbeat, task-bound notifications, lifecycle-owned fallback,
  durable-only transfer snapshot and END cancellation boundary. Existing package,
  transport and final version/raw-SHA checks retained. Added Dart bridge tests
  and Robolectric Service/PowerManager/notification tests (native NOT_RUN).
- Native test dependency: JUnit 4.13.2 and Robolectric 4.14.1 are test-only;
  no runtime Flutter dependency/platform expansion. Minimal missing CI command
  is `:app:testDebugUnitTest --tests com.wen.gaia.gaia.DeviceOtaServiceTest`, using
  the debug helper's contained SDK/Gradle environment. Root owns authorizing or
  wiring that bounded step; service framework testing is not real BLE/lockscreen
  proof. Standard `build.yml` remains root-owned and NOT_RUN.
- Necessary `git add` of the card/log succeeded (exit 0): this worktree's actual
  index is writable. Global hooks were read: commit uses an explicit message and
  unsets the optional WeChat webhook, so it neither calls a commit-message API
  nor sends unrelated external notifications. No global hook/config edits.
- `git diff --check` exit 0 before the first WIP batch. Full runtime verification
  follows the reviewed branch commit; it is not claimed green in advance.

- Entry read-only checks: worktree/branch/HEAD/status, active account and workflow
  verified. Initial Git write permission will be checked by necessary staging.
- A cmd.exe inline JavaScript arrow was parsed as redirection during path
  preflight; it created only the worktree-local zero-byte `{t`. Detected by
  immediate status, preflighted and removed with apply_patch. The explicitly
  protected old root-level `{a` was not touched. Complex read-only preflight now
  uses noninteractive Git Bash, not PowerShell. No project-external write found.

## Current Results

### First WIP Feedback (2026-10-22)

- Commit `38045e0482c607d9a6f8ec8b976918404e7ad5be` pushed on the assigned branch.
- Checks-only run: https://github.com/Eitan-S-23/E-Track/actions/runs/39637361738
  (attempt 1). Both hosts finished FAILURE; no APK requested.
- Both hosts: Flutter 3.47.7 stable, framework
  `abaf9c523780a608bd46686fd5e53740a07077f8`, Dart 3.13.5, engine
  `deb287481e3ce9468f3434937ced4240a70539ca`. `flutter pub get
  --enforce-lockfile` exit 0; `flutter analyze --no-pub` exit 0.
- Full `flutter test --no-pub --reporter expanded --timeout 2m test`: exit 1.
  Ubuntu: 731 passed, 16 skipped, 2 failed. Windows: 714 passed, 33 skipped,
  2 failed. Both failures are existing in-flight cancellation tests expecting one
  MCU ABORT but observing zero. No assertions weakened or failing logs removed.
- Diagnosis: newly added owner-finally disposal invalidated the transport while
  cancellation's serialized ABORT was queued. Batch repair retains it through
  the per-transport ABORT future, including fail-closed cleanup; starts ABORT
  before awaiting native PHY cancellation. Owner completion is now in a nested
  finally so runtime-release exceptions cannot strand the exclusive owner.
- Added service integration checks for acquired background/hidden/resume with
  one BEGIN, durable-only snapshots, rejected/lost ownership safe pause and
  strict foreground recheck, cancelled delayed acquisition, and END ACK waiting
  for final identity while rejecting a stale cancel action. These Dart tests
  explicitly do not substitute for Android platform execution.
- First artifact retrieval failed with a TLS handshake timeout (exit 1).
  The bounded retrieval retry succeeded (exit 0); no CI rerun was requested.
  Original result JSON and combined logs for both hosts are archived under
  `.cache/p38/run-39637361738/` (14-day remote expiry no longer sole copy).

### Second WIP Feedback And Repair

- Commit `bcf4b2b09b457732af19fc17ef83700b0bbeb8e5`, checks-only run
  https://github.com/Eitan-S-23/E-Track/actions/runs/39647015309 (attempt 1).
  Both analyze exit 0; full tests exit 1. Ubuntu: 737 passed, 16 skipped,
  1 failed; Windows: 720 passed, 33 skipped, 1 failed. The two first-run
  regressions and the new background integration cases now passed.
- The remaining historical cancellation/cleanup atomicity test timed out:
  owner-finally awaited ABORT, but the established concurrency oracle requires
  the retired owner to exit while ABORT is in flight. Repair moves disposal
  ownership to cancelUpgrade after its ABORT future; the old owner can exit,
  and old cleanup retains its transport/key rather than touching a later owner.
  Historical test assertions and their timing bound are unchanged.
- Feedback originals archived under `.cache/p38/run-39647015309/`.
- Additional bounded repairs: one published immutable Rx snapshot for both
  consumers; gate reconnect probes on background ownership and abandon an
  in-flight probe after ownership loss; test loss during reboot verification.
  Native engine callbacks ignore retired engines, and initial notification
  revision fences delayed snapshots. Native changes/tests still NOT_RUN.
- Requested root's bounded native-test and standard-build route while continuing
  authorized development checks. No workflow/build scope changed by this agent.

### Candidate Development Checks

- Product candidate: `0d08d020156e6443530ef84ebae39d76d7379129`.
  App subtree: `1b802bec704e6f71374e27e2dca4aa9bdd59b79c`.
  Branch: `dev/flutter/p3-8-background-ota-20261021`.
- Checks-only run https://github.com/Eitan-S-23/E-Track/actions/runs/39656339389
  succeeded on both Ubuntu and Windows. Both full-package analyze commands exit
  0 with no issues. Full tests exit 0: Ubuntu 739 passed/16 skipped/0 failed;
  Windows 722 passed/33 skipped/0 failed. SDK identity is the same Flutter
  3.47.7 / Dart 3.13.5 / framework and engine revisions recorded above.
- Original results/logs are in `.cache/p38/run-39656339389/`. SHA-256 of the
  development result JSON: Ubuntu
  `f4b73d658d53b4b9089d46363a9131353be38cb2123f11c6b4c9b5ba72643f42`;
  Windows `6237f27f9ede1a129a5e9eb0b909ec17c8675e18d45d0beaf9a8db52e64bfdb9`.
- Explicit development APK request (not a blind rerun): `gh workflow run
  flutter-dev-checks.yml --repo Eitan-S-23/E-Track --ref
  dev/flutter/p3-8-background-ota-20261021 -f test_scope=all -f build_apk=true`
  exited 0. Run https://github.com/Eitan-S-23/E-Track/actions/runs/39657800806
  succeeded on both hosts at the same candidate. Linux `flutter build apk
  --debug --no-pub --target-platform=android-arm,android-arm64` and `apksigner
  verify --verbose` both exited 0. This compiles the Android runtime but does
  not execute the prepared Robolectric tests.
- The existing pure-Java PHY/write-trace lifecycle regression also passed on
  both hosts; its report explicitly says `android_plugin_compiled=false` and
  `hardware=false`. It is not P3-8 Service/engine platform behavior evidence.
- Cross-layer self-check (not independent review): page/notification use the
  same owner-published immutable snapshot; task key is preserved through the
  bridge and every action; native ownership requires service/lock/engine/Dart
  probe; old engines/tasks/revisions are fenced. Existing sender, package
  validation, connection generation and final raw-image identity checks remain
  shared. App updater retains its own channels, ID 2401 and install business.

### Archived Debug Candidate

- Run `39657800806`, attempt 1, full scope, source `0d08d020`: Ubuntu analyze
  exit 0, tests exit 0 (739 passed/16 skipped/0 failed), Windows analyze exit 0,
  tests exit 0 (722 passed/33 skipped/0 failed). Both hosts use the same recorded
  Flutter/Dart revisions as the successful checks-only candidate run.
- SDK build host: Temurin OpenJDK 17.0.20.1+1; Android Build Tools 35.0.0.
  Exact commands, generated-toolchain deltas and all original output are in
  `.cache/p38/run-39657800806/`. No local SDK/build/test substitute was used.
- APK: 131747598 bytes, application ID `com.wen.gaia.gaia`, development debug
  signing (`release_signing=false`). No install or device action authorized or
  performed. It is not a standard release-mode APK or a shipping release.
- APK SHA-256:
  `4a4fd6a87cd01e1c2cb43c9192db0f3d8ef67e9039a3178b0c59230d23405464`.
  Local file, relative to the worktree:
  `.cache/p38/run-39657800806/flutter-dev-debug-apk-0d08d020156e6443530ef84ebae39d76d7379129-39657800806-1/run-0c61af611cfc41aca00fc44e93e43bea/artifacts/trace-dev-debug.apk`.
- Adjacent `trace-dev-debug.json` SHA-256:
  `53537ae9795110130804962b3d453f3f9a11809a8d2f5f01e744d5b0e90ee2d4`.
  APK size/hash/commit were independently recomputed locally and match this CI
  metadata. Remote 3-day APK expiry is not the sole retained copy.
- Development result JSON SHA-256: Ubuntu
  `2a686c0d9d8dd291fe12bca64f9b108b0ccac6add3027b1b84061b4cde625b1f`;
  Windows `8e3d24a3f3940967b7e96589986bbef0a47deb3c43e165396eaeb46260eb92af`.
- The first download failed with a TLS handshake timeout, exit 1; one bounded
  read-only retry completed with exit 0. No build/test rerun followed the download
  failure. The download's temporary zip was automatically removed on completion.

### Handoff And Remaining Owners

- Code candidate implemented; full development analyze/test and debug Android
  compilation/signature verification passed. Subsequent handoff-only commits
  change this record and P3-8's card/log, not the app subtree above.
- Native platform tests: 13 prepared Robolectric Service/notification/wake-lock
  cases, NOT_RUN. They cover delayed/rejected/late probes, stale actions and
  snapshots, indeterminate apply, lost permissions/engine, cleanup and process
  recreation. They do not by themselves prove a real retained Flutter engine or
  background BLE reliability. Root owns authorizing/arranging the narrow native
  CI invocation under the contained development SDK; no workflow was expanded.
- Standard release-mode APK: NOT_RUN. Windows EXE: NOT_RUN. Root owns arranging
  exact-candidate `build.yml` check-only execution with `publish_release=false`
  and `replace_existing_release=false`. No production workflow was dispatched,
  PR opened, release/version bump performed, or shipping artifact claimed.
- Real background/lockscreen/notification interaction/durable advancement,
  disconnect recovery and final new-link GET_INFO version/full raw SHA evidence:
  NOT_RUN. No applicable new P3-8 physical originals exist from this session.
  Root and the non-implementation reviewer reconcile any applicable existing
  observations first and obtain only the missing bounded device authorization.
- Formal contract freeze/approval, independent PASS, whole-card completion and
  main closeout remain exclusively with root/non-implementation reviewer.
  P3-8 remains IN_PROGRESS; required delivery gates are not all satisfied.

### Closing Write-Boundary Audit

- Active root and existing parents of every controlled output were checked;
  product/manual records stay in this worktree. Normal branch Git operations
  use its assigned shared `.git/worktrees/p3-8-implementation-20261021` index
  and the authorized shared object/ref metadata, not other worktree indexes.
- Archive reconciliation: 75 files, 149533496 bytes under `.cache/p38/`, no
  symbolic/reparse redirections observed and every resolved location inside the
  worktree. `.cache/p38/tmp/` contains only the preexisting `.keep` after CLI
  completion. Logs/APK are ignored archives, not staged source or credentials.
- No local Flutter/Gradle build, PowerShell process, device/phone/OTA/firmware
  operation, cloud business mutation, global config/ACL change, main merge,
  release or deployment. The main worktree's historical changes and protected
  root `{a` were not modified. No known project-external active output remains.

## Authorized Validation Continuation (2026-10-22)

- User explicitly confirmed authorization to continue P3-8, add the dedicated
  Android native-test CI route and run standard APK/EXE builds. This supersedes
  the earlier missing-CI-authority entries only in that exact scope; no device,
  installation, cloud business write, publish/deploy or main-merge authority.
- Re-entry: same clean worktree/branch, HEAD `9cba05e2aca0ab83825e633c9f63e84a9593af47`;
  existing GitHub actor `Eitan-S-23`. No new worktree or repository created.
- Bounded change list: `.github/workflows/flutter-dev-checks.yml`, existing
  `Tools/flutter/dev_apk.py` and `dev_checks.py`, their two existing host
  regressions, development guide and this record. Add a default-off
  `device_ota_native_tests` dispatch input, require explicit Linux debug mode,
  run the one P3-8 Service class using the existing contained SDK and archive
  native JUnit/HTML. No new generic runner, acceptance contract or task Spec.
- Validation order: offline non-build helper regressions (project-local
  fixtures), reviewed WIP commit/push, full app checks plus native tests/debug
  build, then exact-candidate `build.yml` with both publish/replace inputs false.
  First failures remain preserved and are repaired from actual diagnostics.
- Local non-build feedback: `python -B tests/ota/test_flutter_dev_apk.py`
  passed 40 tests (exit 0). First `test_flutter_dev_checks.py` ran 64 tests,
  exit 1, with one ERROR in
  `test_bind_toolchain_regen_fails_closed_on_collection_failure` before its
  injected failure: `checkout_identity` -> `worktree_fingerprints` ->
  `git hash-object --no-filters --stdin-paths` exited 128 in the deep
  worktree-local `gitfixture`. This is the local Windows path-length case,
  not an Android or CI result. Retry uses process-scoped
  `GIT_CONFIG_COUNT=1,GIT_CONFIG_KEY_0=core.longpaths,GIT_CONFIG_VALUE_0=true`;
  no global config or outside short directory. Added a strict native-phase
  failure propagation oracle before rerunning the host suite.
- Diagnosed-path retry passed all 65 development-runner host tests (exit 0),
  raw console archived as `.cache/p38/host-checks-longpaths.log`. This is only
  Python/fixture validation and did not start Flutter/Gradle or build an App.
- Helper isolation check with `FLUTTER_DEV_DEVICE_OTA_NATIVE_TESTS=true` passed
  40 tests (exit 0), console `.cache/p38/host-apk-native-option.log`. Local host:
  Python 3.13.12, Git 2.53.0.windows.1. The offline suites used contained fixture
  outputs only; existing symlink/junction negative fixtures were removed by the
  suite and the subsequent audit found no remaining links.

### Executed Native Service Development Tests

- CI/input commit: `5d2a0fa6fee9d58a608a068a7bff9f3d8e31f3a9`; app subtree
  remains `1b802bec704e6f71374e27e2dca4aa9bdd59b79c`. No product source changed
  in this continuation; the extension reuses existing development helpers.
- Dispatch: `flutter-dev-checks.yml`, `test_scope=all`, `build_apk=true`,
  `device_ota_native_tests=true`, same exclusive branch; command exit 0.
  Run https://github.com/Eitan-S-23/E-Track/actions/runs/39697643246 (attempt 1)
  completed SUCCESS on Ubuntu and Windows.
- Both `flutter analyze --no-pub` and full `flutter test --no-pub --reporter
  expanded --timeout 2m test` exited 0 on both hosts. Actual counts: Ubuntu
  739 passed/16 skipped/0 failed; Windows 722 passed/33 skipped/0 failed.
  Actual SDK: Flutter 3.47.7, Dart 3.13.5, framework
  `abaf9c523780a608bd46686fd5e53740a07077f8`, engine
  `deb287481e3ce9468f3434937ced4240a70539ca`.
- Actual `apk_device_ota_native` Gradle command exited 0. Archived JUnit XML
  confirms `tests=13, skipped=0, failures=0, errors=0`, 13 named testcases,
  Robolectric SDK 34. This changes the earlier native Service test NOT_RUN
  state to executed development success, not formal acceptance or a real
  retained-engine/BLE/lockscreen observation.
- Native XML original:
  `.cache/p38/run-39697643246/ubuntu/app/bluetooth_flutter_Trace/build/app/test-results/testDebugUnitTest/TEST-com.wen.gaia.gaia.DeviceOtaServiceTest.xml`;
  SHA-256 `9694a0791ba15c2535a1356306a72fb3dcb6a3d7cd206adab1b8877f5d42d50c`.
  HTML report is archived alongside the original App build report hierarchy.
- Result JSON SHA-256: Ubuntu
  `8e9304638b6e0de17207e70d2aca846825b6dfcb8f016662cd03c5ae392e5de7`;
  Windows `53607ca7e1767c1f320b32efc0c584c12e7ee8a5004b5c9bfab2c122c7c77b67`.
  Originals and raw command logs are under `.cache/p38/run-39697643246/`.
- Debug APK built and signature-verified (both exit 0), archived as
  `.cache/p38/run-39697643246/apk/run-ded6080d2822445cb9d65d80d398b086/artifacts/trace-dev-debug.apk`.
  131748470 bytes; locally recomputed SHA-256
  `aec3a68e86ebbb7573697a504861b410a4210b89cb9a70c6c8e6c5606e3bf7cd`
  matches adjacent CI metadata. Debug-signed production application ID,
  not installed or published; prior debug APK remains preserved separately.
- Existing profile inspection confirms helpers/workflow are in Validation,
  and the native test class is included by current Production/Flutter roots.
  No canonical or frozen profile, contract or previous acceptance bundle changed.

### Authorized Standard Build

- Command: `gh workflow run build.yml --repo Eitan-S-23/E-Track --ref
  dev/flutter/p3-8-background-ota-20261021 -f publish_release=false
  -f replace_existing_release=false`, exit 0.
- Run https://github.com/Eitan-S-23/E-Track/actions/runs/39700401326 targets the
  same `5d2a0fa6` candidate. Android release-mode APK and Windows EXE are in
  progress; no result is inferred yet. The Pages job is skipped; the release
  condition is false. No version bump, release/CF publication or device action.
- Completed result: SUCCESS, exact head
  `5d2a0fa6fee9d58a608a068a7bff9f3d8e31f3a9`, actor `Eitan-S-23`,
  workflow_dispatch attempt 1. Android job `119568062672` and Windows job
  `119568062707` both SUCCESS. Pages and Create GitHub Release both SKIPPED.
- Standard job commands: both `flutter analyze` and `flutter test` exited 0;
  actual summaries are Ubuntu 739 passed/16 skipped and Windows 722 passed/
  33 skipped. `flutter build apk --release
  --target-platform=android-arm,android-arm64` and `flutter build windows
  --release` both exited 0. Setup logs bind Flutter 3.47.7 and framework
  `abaf9c523780a608bd46686fd5e53740a07077f8` on both hosts.
- Android release build retains 10 warning lines: three upcoming Gradle/AGP/
  Kotlin support deprecations and seven plugins requesting Android SDK 36+.
  No compile error; Windows release build has no warning line. Toolchain
  maintenance is not expanded into this P3-8 change.
- Read-only status polling encountered TLS handshake timeout/EOF. A
  process-local `GODEBUG=http2client=0` query succeeded and confirmed both jobs;
  no CI rerun, proxy/global configuration change or TLS validation bypass.
- Original full Actions console archive downloaded by the logs API (exit 0)
  to `.cache/p38/run-39700401326/logs.zip`, SHA-256
  `33f338f5ea0800d585f077bd637da211021b468ac258647aa69eddfa7b544201`.
  Listed/checked all archive paths and regular-file types before extracting
  into its worktree-local `logs/`; SDK/test/build-step originals are preserved.
- Standard APK already archived at
  `.cache/p38/run-39700401326/android-apk/ble-monitor-android.apk`,
  47272692 bytes, SHA-256
  `626ca75be7ea481e8cc2249f7a5811132e95490b456bec1106b5f5b6c6e7abcd`.
  Windows EXE/full ZIP download also completed (CLI exit 0); no artifact has
  been installed or executed.
- Standard Windows EXE:
  `.cache/p38/run-39700401326/windows-exe/ble-monitor-windows.exe`,
  93184 bytes, SHA-256
  `6f65b13859b3846801c64543f8363c7d82aa92742987d56571fcf35e28f17cdb`.
  The executable requires its packaged runtime/DLL/data files; the complete
  distribution is the adjacent `ble-monitor-windows.zip`, 20482542 bytes,
  SHA-256 `5ad8cac64d7baf55b7dbd3bbe09bdafb89ef9cc5f8581cb66d6711000247ed51`.
  Both hashes were computed from the downloaded original bytes, not guessed
  from an Actions artifact-container digest.

### Software Candidate Handoff

The original native CI and standard-build gaps are now closed for the software
candidate `5d2a0fa6fee9d58a608a068a7bff9f3d8e31f3a9`. Full App development
checks, 13 Android Service tests, debug APK, standard release-mode APK and
Windows release EXE/ZIP all actually succeeded and have retained originals.
Later record-only commits do not change App, native-test, helper or workflow
inputs. Historical failures and prior NOT_RUN entries above describe their
original checkpoints and are not rewritten as success.

This is ready for a non-implementation review of source/artifacts and preparation
of the missing bounded physical observations. It is not formal independent PASS:
actual retained-engine handoff, background/lockscreen durable advancement,
notification/page interaction, physical disconnect recovery, final new-link
GET_INFO target version/full raw SHA and real resource release remain NOT_RUN.
Root/non-implementation reviewer owns the remaining contract and observation
work, with separate device/installation/OTA authority. This agent does not
freeze/approve the contract, mark the card complete, install/run artifacts,
merge main, publish or deploy.

### Continuation Write Audit

- Final controlled-output inspection covered `.cache/p38/` and both local
  offline helper-fixture roots: 2019 files, 368300490 bytes. All resolved paths
  are within the assigned worktree; no links remain. Download temp contains
  only `.keep`, not a partial archive. Original ZIPs, extracted logs, JUnit and
  product binaries remain in ignored task-local archives.
- Manual source/guide/card/record edits and generated host logs stay inside the
  worktree. Git writes are only normal operations for this branch/index and
  inner test-fixture repositories under its `.cache/`; no alternate repository
  was created to bypass host restrictions. Long-path/HTTP transport changes were
  process-scoped, not global config or ACL edits.
- Local commands used cmd/Git Bash and Python non-build fixtures; no local
  Flutter/Gradle/EXE/APK build, PowerShell startup or device action. The authorized
  standard remote workflow used its existing hosted build/packaging steps.
  No main ref/index, historical task evidence, root `{a`, cloud business state,
  release or deployment was modified.

## Concentrated Preacceptance Remediation (2026-10-22)

- Input: independent report at the authorized read-only root path
  `D:/github/my/E-Track/docs/ota-exec-notes/P3-8-preacceptance-2026-10-22.md`.
  Original candidate `5d2a0fa6`, delivery HEAD `2a46ecdf`, same clean exclusive
  worktree and branch verified. No main/root edits or review-draft mutation.
- `.trellis/` is absent in this worktree; task Spec, root/App AGENTS and project
  collaboration/validation contracts remain the applicable development rules.
- Scope: OTA service, page, Android Activity/bridge, their three existing tests,
  this record and P3-8 board/log only. No runner, protocol, cloud/MCU, App updater,
  acceptance criteria or permission changes. Existing full dual-host/native/debug
  workflow is runnable; actor Eitan-S-23 and workflow identity were checked.
- P38-R01: recovery epoch invalidated by background transitions and newer
  recoveries; check eligibility after asynchronous identity work and immediately
  before releasing the sender. Foreground gates loop/recheck after awakening.
  Added held-discovery and held-INFO second-pause cases; no extra DATA/END, one
  BEGIN, and a later genuine foreground recovery must succeed.
- P38-R02: sanitize private OTA URI before initial/new Intent reaches Flutter's
  embedding; preserve external links and plugin delivery. Only task-key-validated
  open goes through the dedicated bridge. Added five Robolectric Activity-entry
  cases with an embedding shadow (no native Flutter engine), real key/service
  checks and a recording MethodChannel. This tests the actual MainActivity
  superclass boundary, not real Dart navigation or a running retained engine.
- P38-R03: foreground waiting uses the existing absolute reboot deadline, as
  does disconnect. Expiry reports REBOOT_RECONNECT_FAILED, clears paused projection
  at cleanup, and releases the owner/scan lease without background probes. Added
  a 400 ms unresolved-expiry case and a resumed-then-paused gate case; existing
  return-before-deadline positive remains unchanged in intent.
- P38-R04: page attaches the exact current task address without BLE work; after
  owner exit it reconciles that address before enabling actions. Subscription is
  disposed with the page. Added completed/cancelled/failed no-argument page cases
  and an unrelated explicit-device case, with a held identity read gating actions.
- First implementation WIP: source and new regressions prepared; `git diff
  --check` exit 0. App analyze/tests, native cases and new builds NOT_RUN pending
  the development CI below. Prior successful builds do not verify these changed
  inputs. Device observations and formal independent acceptance remain NOT_RUN.
- Boundary preflight used the existing host_io guard for every manual target and
  task-local archive/temp root. A first cmd inline-Python quotation failed with
  SyntaxError before executing code (exit 1); Git Bash invocation succeeded
  (exit 0). No external output or cleanup followed that read-only failure.

### Native Regression Harness Repair (2026-10-22)

- Successor implementation owner takes over the same clean worktree at
  `be0b64f8fdc397520300e4305603c5ac7c878315`. No review/acceptance role is
  assumed; P38-R01 through P38-R04 remain subject to independent re-review.
- `e1865479` contains the four source repairs and their regressions. Its
  checks-only run `39748109544` passed; native/debug run `39748115816` failed
  because the new tests directly called protected `MainActivity.onNewIntent`.
  `be0b64f8` changed only that test invocation to reflection, preserving the
  product visibility. Its checks-only run `39772250776` passed.
- Native/debug run `39774162835` at `be0b64f8` failed: Ubuntu analyze and all
  Dart tests passed (746 passed, 16 skipped, 0 failed), APK compilation passed,
  but native tests had 18 cases / 5 failures. Windows completed successfully.
  APK verification/collection were NOT_RUN; no successful artifact is inferred.
- Retrieved the original Ubuntu artifact into the write-guarded
  `.cache/p38/takeover-20261022/failed-native/`. The retained JUnit XML shows
  every failure is `OtaEmbeddingBoundary cannot be cast to ShadowActivity` in
  `ActivityController.attach`, before any notification assertion runs. This is
  a test-fixture defect, not evidence of a product routing failure.
- Repair: the Flutter embedding shadow now extends Robolectric `ShadowActivity`
  so its real Activity controller can attach it. Its `onCreate` records the
  sanitized URI then calls the Android `Activity.onCreate` directly, preserving
  framework initialization without starting libflutter. Real MainActivity,
  service/key validation and all five positive/negative routing oracles remain
  unchanged. No production source, dependency, runner or workflow is changed.
- Robolectric 4.14.1 upstream `ActivityController.attach` and `ShadowActivity`
  were checked against the declared dependency. Validation uses the existing
  full dual-host development workflow with `build_apk=true` and
  `device_ota_native_tests=true`, not a local Flutter/Gradle build. The repaired
  native cases and final-candidate builds remain pending until actual results.

### Executed Remediation Validation

- Final code/test candidate: `27048aa10079d8dd01d608967e7b5d1b473861ba`.
  App subtree: `492fb8e35f33012127aa8adf61a22e3d592f483d`. The successor changed
  only the Android test shadow and this record; the four production repairs
  remain those in `e1865479`. No regression assertion was removed or weakened.
- Development run https://github.com/Eitan-S-23/E-Track/actions/runs/39789686610,
  attempt 1, explicit `test_scope=all`, `build_apk=true`,
  `device_ota_native_tests=true`: both hosts SUCCESS. Ubuntu analyze exits 0,
  tests 746 passed / 16 skipped / 0 failed; Windows analyze exits 0, tests
  729 passed / 33 skipped / 0 failed. Both original result files bind a clean
  checkout of `27048aa1`, full scope and successful command exits.
- Actual SDK on both hosts: Flutter 3.47.7, Dart 3.13.5, framework
  `abaf9c523780a608bd46686fd5e53740a07077f8`, engine
  `deb287481e3ce9468f3434937ced4240a70539ca`.
- Original Android JUnit: **18 tests, 0 skipped, 0 failures, 0 errors**. All five
  previously failing Activity-entry tests now execute and pass, alongside the
  existing 13 Service tests. The Gradle command, debug APK build, apksigner
  verification and collection each exit 0. No real Flutter engine/device was
  started by these Robolectric tests; platform/hardware claims remain bounded.
- Originals: `.cache/p38/takeover-20261022/run-39789686610/ubuntu/` and
  `windows/`. Ubuntu result JSON SHA-256:
  `3d222ab7ba7cdba55a62661a808b56bfdeac164d41a1ceecb7a41faa6c064121`;
  Windows result JSON:
  `ba860212b38d748d1b8d0ad05df4da64f173cd3efed2097690f08b1ba93211c4`;
  native `TEST-com.wen.gaia.gaia.DeviceOtaServiceTest.xml`:
  `b6880580cb2aa95b53d3a5d167ce52fe6af018b6b21fb06d46394fba77e3ae2e`.

| Finding | Changed path / exercised regression | Development result |
| --- | --- | --- |
| P38-R01 | Service recovery epoch and rechecking foreground gate; held INFO and held discovery after a second pause, then genuine recovery | Both full Dart suites PASS |
| P38-R02 | Initial/new Intent sanitization in MainActivity and task-bound bridge; active, stale/malformed, recreated-process and ordinary external-link cases | All 5 Activity-entry cases PASS |
| P38-R03 | Original absolute reboot deadline bounds the foreground gate; ownership loss past 400 ms, no new probe, honest failure and resource release; return-before-deadline coverage retained | Both full Dart suites PASS |
| P38-R04 | Exact task-target attachment and terminal reconciliation; completed/cancelled/failed pages and an unrelated explicit device | Both full Dart suites PASS |

These are implementation self-test dispositions, not independent acceptance
closure. Return this bounded batch and its originals to the independent reviewer;
the preacceptance report and its draft/frozen obligations were not rewritten.

### Final-Candidate Standard Builds

- The original user's explicit confirmation of standard APK/EXE development
  verification was rechecked in the handed-over session. Dispatched existing
  `build.yml` with `publish_release=false`, `replace_existing_release=false`,
  no endpoint or application-ID override, on the same development branch.
- Run https://github.com/Eitan-S-23/E-Track/actions/runs/39791568439, attempt 1,
  candidate `27048aa1`: Android job `119868855099` SUCCESS and Windows job
  `119868855022` SUCCESS. Pages and Create GitHub Release both SKIPPED. No
  release/tag, cloud publication/deployment, main merge or device operation.
- Both standard analyze/test steps succeeded. Raw terminal summaries again
  report Ubuntu 746 passed / 16 skipped and Windows 729 passed / 33 skipped.
  Android release APK and Windows release build commands succeeded.
- Android build retains 10 warning lines: 3 Gradle/AGP/Kotlin future-support
  warnings and 7 plugins requiring SDK 36+. It also logs one non-fatal
  `Caught exception: Already watching path` before the successful build.
  Windows build has 0 warning lines. Do not hide these diagnostics or widen
  this repair into unrelated dependency upgrades. Development Actions also
  reports the existing Node 20 action deprecation/forced Node 24 annotation.
- Full standard console ZIP is `.cache/p38/takeover-20261022/standard-logs.zip`,
  SHA-256 `01832f796fd52deafbad5c734a0eaa0a9153c6fe3c5a00eef6d8698b91bccd1c`.
  Its CRC and every extraction path were checked; step logs are preserved under
  `standard-build/logs/` in the same archive root.
- Standard artifact ZIPs match the digests returned by the GitHub artifact API.
  Extracted product files under `standard-build/` were hashed locally:

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `android/ble-monitor-android.apk` | 47272692 | `366a1e1c898b8729392ce86b159501592f66ee33ac19a243ca92b7117f31a026` |
| `windows/ble-monitor-windows.exe` | 93184 | `30ee419ccc6bd3fb12c5aa3fcb9e9d3b89537ab1dc62467c7460ba5a677c0046` |
| `windows/ble-monitor-windows.zip` | 20485199 | `286526d10b7feba76cbeaeccb13c6e30247d98f70fd6920f81c6bffbf30499c0` |

The full Windows ZIP passes CRC checks and its embedded `ble_monitor.exe`
exactly matches the separately downloaded EXE. No artifact was installed/run.

### Retrieval Failures And Scope

- No successful CI job was replayed to recover a download. Initial `gh run
  download` exceeded the host's 240 s bound, retaining an incomplete ZIP;
  subsequent small-artifact requests encountered EOF. Log/JUnit and standard
  console retrieval succeeded through a task-local thin adapter to installed
  curl and the existing `Tools/flutter/dev_apk.py` download/extraction functions.
- curl downloads also recorded TLS failure (35), timeout (28), and two owned
  zero-progress transfers were stopped by their exact PIDs. A failed Python
  attempt targeted an existing zero-byte output; later attempts used fresh
  destinations and preserved that failed output. One Python handshake failed
  with SSL unexpected EOF.
  Subsequent bytes were not treated as complete before digest verification.
- All wrappers, temporary files, archives and extraction targets are under
  `.cache/p38/` in this worktree, guarded before writing. Proxy bypass tests
  affect only these child processes and Azure Blob hosts; TLS verification
  remains enabled. No global network/configuration or credential changes.
- Prevention: a custom shadow replacing a Flutter Activity must retain the
  `ShadowActivity` controller contract and Android base initialization. Plain
  Dart green results cannot qualify an unexecuted Android fixture. Preserve
  the five real Activity-entry cases and the explicit native CI dispatch input.

### Retained Debug APK And Handoff

- The initial partial ZIP's member name identifies this run's
  `run-079972b527294600b78a85f9779a1c74/artifacts/trace-dev-debug.apk`. Its
  original 57458688 bytes were preserved, copied to a task-local successor,
  and completed with one HTTP Range request. The adapter requires HTTP 206 and
  the exact Content-Range before append; the entire 75477882-byte ZIP matches
  GitHub's digest
  `b31bf8e4616d7640d5dd6b822377848c984f6bdbe96f3fc90bcf5f9559a522d5`.
  This is retrieval of the original artifact, not a rebuild or trust in a prefix.
- Checked/extracted debug APK:
  `.cache/p38/takeover-20261022/run-39789686610/apk/run-079972b527294600b78a85f9779a1c74/artifacts/trace-dev-debug.apk`.
  Size 131748394 bytes; locally computed SHA-256
  `0e89bd52a1b9a4c6bb073c692e7af6c94cdc12b10053aaade4381b44f163f97c`
  agrees with the adjacent original CI metadata, which binds `27048aa1`,
  application ID `com.wen.gaia.gaia`, and `release_signing=false`.
- The implementation batch is ready for the original independent reviewer to
  recheck P38-R01..R04 against `27048aa1` and these originals. A later handoff-only
  commit does not change App/runner/workflow inputs. No independent closure,
  formal freeze/PASS, whole-card completion or main integration is claimed.
- Still missing: actual retained-engine/BLE background and lockscreen durable
  progress, notification interaction and permission fallback, disconnect
  recovery, final new-link target version/full raw SHA, and physical resource
  cleanup. The existing preacceptance D0..D3 draft is not operating authority;
  the independent owner must bind devices/assets and the missing bounded
  authority before execution. No successful upgrade is replayed for collection.
- Final local boundary audit covers the takeover archive, temp and CLI-cache
  trees using the existing host_io guard; all resolved outputs stay inside the
  assigned worktree, with no reparse escape. Incomplete/zero-byte download
  attempts remain clearly separate from verified products, not silently erased.
  WMI confirms no remaining curl/Python download worker. No local App build,
  PowerShell startup, device action or known project-external output occurred.
- Bare `git diff --check` reports this board's stored CRLF line endings;
  process-local `core.whitespace=cr-at-eol` passes. The existing LF-to-CRLF
  conversion notice is retained; no global Git setting was changed.

## P38-R04 Real-Owner Follow-up (2026-10-23)

- Independent review closes R01/R02/R03 for `27048aa1` but keeps R04 required:
  synchronous GetX busy delivery occurs before owner-epoch registration, so a
  plain identity query exposes the completed OTA task and rearms the page's
  reconciliation flag. The prior page fake did not execute this owner behavior.
- Same exclusive worktree/branch, clean handoff HEAD `6b7601e7`. Root review and
  frozen/draft evidence stay read-only. Existing scoped development and standard
  build authorizations apply; no device, main, release or deployment action.
- Regression-first batch changes only this record and the existing upgrade
  integration test. It reuses real OtaService, real OtaUpgradePage, synchronous
  GetX delivery and the existing fake BLE/HTTP/file fixture. It covers successful,
  cancelled and failed OTA owners, unrelated-page-device priority, failed INFO,
  one exact-target query, held verification, no extra BEGIN or query loop, and
  a direct service oracle for the task key exposed by the busy callback.
- Production code is intentionally unchanged for this first development push.
  Preserve the actual red result before the minimal owner/page repair; do not
  replace an executed regression with another static review. Local Flutter/
  Gradle builds remain prohibited. The existing dual-host full-check workflow
  is the runnable regression route; artifacts/logs stay in `.cache/p38/`.
