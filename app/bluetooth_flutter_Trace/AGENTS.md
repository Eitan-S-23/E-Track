# Agent Instructions

## Build Policy

This project must not be built locally.

- Do not run local build or packaging commands such as `flutter build`, `gradle build`, `./gradlew assemble*`, `xcodebuild`, `dart compile`, or platform package/signing commands.
- Use GitHub Actions for all compile/build verification and release artifacts.
- After changing Flutter app code, GitHub Actions verification is required. The user-approved standing self-test authorization below permits implementation agents to commit/push only their scoped WIP validation branches. Mainline commits, merges, releases and deployment remain root-session operations requiring separate explicit authorization; the build gate alone grants none of them.
- Local non-build checks are allowed when useful, such as formatting, static analysis, tests that do not invoke a build, and file/content inspection.
- If a task requires a real build result, trigger or inspect the relevant GitHub Actions workflow instead of attempting a local build.

### Development Validation Before Acceptance

- Before debugging, installing an approved APK or collecting OTA observations,
  read `../../.agents/skills/e-track-flutter-debug/SKILL.md`. It covers contained
  host tooling, real APK/device identity, finished logs and batch experiments.
- Use `../../docs/agent-collaboration-contract.md` for implementation questions
  and review feedback: evidence, preferred repair route, invariants, a bounded
  verification oracle and next owner. A bare rejection or spec link is not enough.
- Read `../../docs/flutter-development-validation.md` before implementing or reviewing Flutter changes. Establish the SDK/host, commands, output boundary and authorization route early, not after repeated source-only remediation batches.
- Standing authorization (user decision, 2026-09-09): implementation agents may stage/commit their assigned changes on an exclusively owned `dev/flutter/**` branch, push that branch using `Eitan-S-23`, and dispatch or rerun `.github/workflows/flutter-dev-checks.yml` on it without asking again for each self-test batch. Reruns need changed inputs, a new validation request or a diagnosed environment recovery, not blind repetition. Read the exact boundaries in `../../docs/flutter-development-validation.md` and execution contract section 7.3.2 before acting.
- The workflow runs strict analyze and tests on Ubuntu/Windows. All `dev/flutter/**` pushes, including `dev/flutter/apk/**`, are checks-only. Request an Android debug APK only by explicit `workflow_dispatch` with `build_apk=true`; APK requests use full tests, and the Linux build requires its checks to pass. The workflow has no release signing secrets, publishing, deployment or Windows packaging. Any Windows failure keeps the overall run red even if a Linux debug APK exists.
- New debug APK artifacts retain for 3 days; development logs retain for 14 days. Before upload, the runner publishes sanitized diagnostics and actual parseable counts in ordinary job logs, without weakening upload errors. The separate trusted-main artifact maintenance job never deletes release assets or APK/EXE verification copies. See `../../docs/flutter-development-validation.md`; pinned development artifacts still expire under GitHub's native retention.
- Bounded cleanup authorization (2026-09-18): implementation and acceptance agents may use the trusted-main maintenance workflow for confirmed-unused development APKs under execution contract section 7.3.3. Review a dry-run and active/evidence dependencies, coordinate serially, and supply the exact approved artifact IDs for manual apply. The whole incident is capped at 50 IDs; do not remove pins, delete ambiguous assets, widen classes, loop to meet a quota or use direct DELETE scripts. If CI cannot start, escalate to the root session; cleanup does not prove upload recovery or acceptance.
- Never change branches, stage or commit concurrently in a shared worktree/index. Use an exclusively owned validation worktree inside the approved project boundary, or ask the root session to serialize the already-authorized operations. Do not include unrelated dirty files, other agents' work, secrets or cache artifacts; bootstrap may include the reviewed development-entry files delivered with this policy. Never force-push, push main/master/tags, merge, invoke the production build/release workflow or change credentials under this allowance.
- The allowance does not grant missing GitHub credentials, workflow-token scopes or sandbox write access. Report those as technical prerequisites without bypassing them or reverting to repeated source-only completion claims. An explicit later user prohibition or narrower task authorization overrides this standing allowance.
- A reviewed WIP validation commit is allowed before tests are green and before a formal contract is frozen. Do not require formal acceptance admission to obtain the development feedback needed for that admission. Preserve unrelated work; do not merge or release a red validation commit.
- The default `all` scope runs package analysis and all app unit/widget tests; manual `ota` scope narrows tests to `test/ota`, not analysis. Windows-only tests require the Windows job; a Linux skip is not Windows evidence. Targeted checks do not replace the app-wide checks required for a stable batch.
- Analysis and test errors/timeouts must fail the development job. Do not use `continue-on-error`, suppress diagnostics or weaken tests to make it green. The runner collects tests after an analyze failure so one batch can address both sets of findings.
- Report source edits, development self-tests, APK/EXE builds and independent acceptance separately. Include the tested commit, workflow run URL, SDK identity, actual scope and raw logs for CI results. No SDK or no authorization means NOT_RUN: state the missing input and request a bounded validation route, rather than repeatedly reporting remediation as complete.
- A checks-only green run is not an APK build; a debug APK is not release-mode APK/EXE verification and is not independent acceptance. The build gate below and the unchanged frozen-contract/NOT_RUN precheck rules still apply. Development-only validation does not require a shipping version bump. Installing an APK on a real device, uninstalling existing apps or clearing data requires separate authorization.

### GitHub Actions Verification Gate

- Do not report Flutter app code changes as complete until the required development checks and GitHub Actions APK/EXE builds have actually passed and their run conclusions have been inspected. This completion gate does not prohibit explicitly authorized WIP validation commits.
- If the worktree is unsafe to push, preserve existing changes and report the blocker. After authorization, use a reviewed clean worktree within the approved filesystem boundary; never silently relocate, commit or push unrelated work.
- A final response for Flutter app code changes must include the commit SHA, workflow run URL, and whether Android APK and Windows EXE jobs succeeded. Local `git diff --check`, formatting, or analysis results are not enough by themselves.
- Android APK and Windows EXE build verification is required only when Flutter app build inputs or `pubspec.yaml` / `pubspec.lock` version/dependency inputs change. Cloudflare admin Pages UI, docs, AGENTS.md, and other non-app changes must use their own checks/deploys and should not trigger APK/EXE rebuilds.
- If the user explicitly says not to push, do not push; state that GitHub Actions verification was intentionally not performed and provide the exact git commands the user can run.

## Device OTA Performance And Background Execution

- Read `../../docs/ota-cross-system-contracts.md` clauses
  `OTA-XC-BLE-PERFORMANCE`, `OTA-XC-ANDROID-OTA-BACKGROUND` and
  `OTA-XC-OTA-PROGRESS` before changing device OTA writes, lifecycle or notifications.
  Task boundaries are P3-4 and P3-8 in `../../PLAN-OTA-EXEC.md`; P3-3-v9 remains
  historical accepted evidence, not proof that these new capabilities exist.
- Do not assume UART baud is the bottleneck. Measure service discovery, negotiated
  MTU, GATT writes, ACK waits and durable advancement; compare identical assets
  and parameter groups. Reuse strictly discovered characteristics only within the
  valid connection generation, invalidating them on disconnect or service change.
- Android background OTA must have one task owner independent of the page, with
  an acknowledged connected-device foreground service and a live execution/BLE
  runtime. The existing App self-update dataSync service is not that guarantee.
  Do not just delete `pauseForBackground()` or add a notification and claim support.
- Entering background or locking the screen may continue only after successful
  handoff. Missing notification/Bluetooth permission, service-start failure or
  loss of execution ownership requires a visible safe fallback. Force-stop is not
  promised to keep running; recovery must revalidate package/device identity and
  use MCU durable state, never cached UI progress as transport truth.
- Use a separate device-OTA notification identity. Show download/transfer/apply/
  reconnect/verification phases, with transfer progress based on confirmed durable
  bytes. END ACK is not upgrade success; require the target version and full raw
  SHA-256 after reboot/reconnect. Do not invent apply percentages or assume every
  Android status bar can render a persistent numeric percentage.
- Notification actions and late callbacks must be bound to the current task and
  generation. Cancellation is only available in cancellable phases. Release
  service, wake lock and listeners on terminal paths without affecting App updates.
- Real background, screen-lock, return-to-page and disconnect/recovery evidence
  is required alongside Actions checks/builds. Unit tests or APK creation alone
  do not establish Android background reliability. Hardware actions remain subject
  to separate authorization; this section does not expand standing CI permissions.

## GitHub Credentials

- This Windows machine may have multiple GitHub credentials configured.
- When pushing to the remote repository, explicitly use the `Eitan-S-23` GitHub identity/credential. Do not assume the default cached credential is correct.

## Cloudflare Update Release Automation

The update pipeline prepares Cloudflare release candidates automatically, but it must not auto-publish them to users.

- A normal `git push` to `main` can prepare a new Cloudflare candidate only when `pubspec.yaml` has a new version/build number, for example `1.0.13+39`.
- Before pushing app-facing Flutter code that is intended to ship in a rebuilt APK, bump both the version name and build number in `pubspec.yaml`, for example from `1.0.17+43` to `1.0.18+44`.
- When the user asks to rebuild or release app code, check `pubspec.yaml` first and include the version bump in the same change. Do not rely on rebuilding the same version; an existing tag skips Cloudflare candidate preparation, and same-tag APK hash drift can break incremental updates for installed clients.
- The workflow derives the GitHub release tag from `pubspec.yaml`, such as `v1.0.13`, builds artifacts in GitHub Actions, creates the GitHub Release, uploads APK/manifest/patch assets to Cloudflare R2, and registers a D1 release in `candidate` state.
- If the derived tag already exists, automatic candidate preparation is skipped. Do not force-replace or re-upload the same tag unless the user explicitly asks for a staging-only replacement; same-tag APK hash drift breaks incremental updates for installed clients.
- A registered candidate is not visible to clients until an operator publishes it to `stable` or `beta` through the Access-protected admin UI or the staging publish wrapper.
- Keep `TRACE_UPDATE_SERVICE_URL` as the Worker URL for CI `/api/ci/releases`; keep `TRACE_PUBLIC_UPDATE_SERVICE_URL` as the Pages URL compiled into APKs for public update checks.
- VCDIFF patches must only be generated for source clients with versionCode `41` or newer. Earlier clients contain the upstream `vcdiff_decoder` address-cache bug and must use one full APK transition before receiving VCDIFF again. Read `cloudflare/update-service/docs/VCDIFF-COMPATIBILITY.md` before changing patch generation, decoder dependencies, or update publishing thresholds.
- Do not use local Flutter/Gradle builds to verify release artifacts. Inspect or trigger GitHub Actions instead.

## Cloudflare Admin Pages Deployment

- Before deploying or troubleshooting the update admin UI, read `cloudflare/update-service/admin/README.md` and `cloudflare/update-service/docs/STAGING-SETUP.md`. The former `.codex/skills/deploy-update-admin-pages/SKILL.md` reference is not tracked and is not a prerequisite.
- Normal admin UI/code redeploys must use `.\cloudflare\update-service\scripts\deploy-admin-staging.ps1 -Yes -SkipSecrets` unless the user explicitly asks to update Access secrets and provides current values.
- Keep the admin Pages `wrangler.jsonc` bindings synchronized with `AdminEnv` in `functions/api/admin/[[path]].ts`; notably, `/api/admin/storage` requires the `RELEASES_BUCKET` R2 binding.
- Do not treat GitHub Actions deployment attempts as proof that the Admin Pages fix is live. The repository `CLOUDFLARE_API_TOKEN` may lack Pages or D1 permissions; an Actions failure with Cloudflare `Authentication error [code: 10000]` means the token is insufficient, not that the UI code is invalid.
- If the repository Cloudflare token lacks Pages/D1 permissions, switch to local Wrangler browser authorization instead of repeatedly retrying the Actions deploy. Run `node node_modules/wrangler/bin/wrangler.js login --browser=true` from `cloudflare/update-service/admin`, let the browser open, and ask the user to approve the Cloudflare authorization page.
- After local browser authorization succeeds, deploy with `.\cloudflare\update-service\scripts\deploy-admin-staging.ps1 -Yes -SkipSecrets`; do not omit `-SkipSecrets` unless intentionally updating Access secrets.
- After deploying, verify the latest Pages deployment with `wrangler pages deployment list --project-name trace-update-admin-staging` and confirm the `Source` commit is the intended commit.
- If local Wrangler cannot run because the Windows host blocks Node child processes with `spawn EPERM`, state that deployment is blocked by the local runtime and provide the exact browser-login and deploy commands for the user to run; do not claim the Pages fix is live.
- If the admin UI reports `BACKEND_UNAVAILABLE: Admin backend unavailable`, first inspect the response `detail` and `requestId`, then verify the production Pages deployment, Access secrets, D1 binding, and R2 binding. A missing binding in an auxiliary endpoint such as `/api/admin/storage` can break the UI even when the release candidate itself is valid.
- Do not claim the Access-protected admin publish button was verified unless it was tested with a real Cloudflare Access session. Without that session, verify release state through D1 plus the public latest/download path, or use the staging publish wrapper and state clearly that it validates the release pipeline rather than the UI button.
- After publishing, verify `channels.current_release_id` and `revision` in D1, confirm `/api/public/latest` returns the intended release/versionCode, and confirm at least one patch or full download is served from R2 via `X-Trace-Asset-Source: r2`.
## Android Self-Update Installer

- Android 10+ restricts background activity launches. Do not treat a foreground service, `PendingIntent.send()`, or a full-screen notification as proof that the package installer appeared while Trace is backgrounded.
- Android 14+ requires explicit background-activity-launch opt-in for PendingIntent senders, and Android 15+ also requires creator-side opt-in. Even with opt-ins, system policy can block or downgrade the launch, so background update completion must not depend on it.
- Full-screen notifications are not guaranteed to open a full-screen UI while the user is using the device; the system can show a heads-up notification instead. Use the notification as a user-tapped install entry, not as an automatic installer launch guarantee.
- Native `installApk` must fail closed with `APP_NOT_FOREGROUND` unless `MainActivity` is at least `Lifecycle.State.RESUMED`. Dart must keep `app_update_pending_install_apk_path` and retry only after Trace returns to foreground and settles.
- After download or synthesis finishes in background, close the progress dialog, show an install-ready notification, and leave status at ready-to-install. Avoid leaving the UI stuck on `打开系统安装器` / `正在调用系统安装器` when Android refused a background installer launch.
- Do not preflight package installer availability with `resolveActivity` on Android 11+ unless package visibility is configured; it can return false negatives. Prefer `startActivity` with `ActivityNotFoundException` and `SecurityException` handling from a resumed Activity.
- Self-update installer fixes only affect update attempts started by an already-installed source version that contains the fix. If the fix first ships in `1.0.46`, then `1.0.45 -> 1.0.46` still runs the old `1.0.45` updater code and cannot validate the fix. Validate with `1.0.46 -> 1.0.47` or later, or require one foreground/manual bootstrap install for older clients.
