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

Source implementation: IN_PROGRESS; repaired batch awaiting changed-input CI.
Debug APK, standard APK, Windows EXE, Android platform tests, devices and
independent acceptance: NOT_RUN. Root owns the bounded native CI step and
standard build entry described above. This log declares no formal PASS.
