# Agent Instructions

## Build Policy

This project must not be built locally.

- Do not run local build or packaging commands such as `flutter build`, `gradle build`, `./gradlew assemble*`, `xcodebuild`, `dart compile`, or platform package/signing commands.
- Use GitHub Actions for all compile/build verification and release artifacts.
- After changing Flutter app code, if local compile/build verification is unavailable or prohibited, the change must be committed and pushed so GitHub Actions performs the build verification.
- Local non-build checks are allowed when useful, such as formatting, static analysis, tests that do not invoke a build, and file/content inspection.
- If a task requires a real build result, trigger or inspect the relevant GitHub Actions workflow instead of attempting a local build.

### GitHub Actions Verification Gate

- Do not report Flutter app code changes as complete until a GitHub Actions build has been pushed or manually triggered and the run conclusion has been inspected.
- If the current local worktree is dirty, behind `origin/main`, or otherwise unsafe to push, create a clean temporary clone or worktree from the latest `origin/main`, apply only the intended changes, commit, push with the `Eitan-S-23` credential, and trigger or inspect the relevant workflow there.
- A final response for Flutter app code changes must include the commit SHA, workflow run URL, and whether Android APK and Windows EXE jobs succeeded. Local `git diff --check`, formatting, or analysis results are not enough by themselves.
- Android APK and Windows EXE build verification is required only when Flutter app build inputs or `pubspec.yaml` / `pubspec.lock` version/dependency inputs change. Cloudflare admin Pages UI, docs, AGENTS.md, and other non-app changes must use their own checks/deploys and should not trigger APK/EXE rebuilds.
- If the user explicitly says not to push, do not push; state that GitHub Actions verification was intentionally not performed and provide the exact git commands the user can run.

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

- Before deploying or troubleshooting the update admin UI at `cloudflare/update-service/admin`, read `.codex/skills/deploy-update-admin-pages/SKILL.md` and follow it.
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
