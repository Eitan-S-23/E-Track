# Original Admin Candidate Delivery

## Developer Workflow

### One-Command Version-Only Candidates

From the primary checkout on Windows, with the existing Git, Python and
GitHub CLI installed:

```bat
release_candidate.bat mcu
release_candidate.bat app
```

Each command increments only the selected component, commits only its version
file and pushes main, then waits for the exact formal CI and unpublished-candidate
receipt. MCU updates versionName and release notes; App updates the name and code
in the same pubspec version line. It never builds locally, installs an SDK,
publishes Stable/Beta, generates/enables a delta, touches a device or clears data.
It is a candidate preparation command, not an automated physical OTA test.

Use `release_candidate.bat mcu --dry-run` (or `app --dry-run`) to check the next
version and push access without changing either version file or updating remote
refs. Main must be clean and match fresh remote main; unrelated/untracked files
are never staged.
Occupied Release drafts/tags, divergence and unresolved prior deliveries stop
the command rather than overwriting assets or silently trying another version.
An original main-push failure is closed without a rebuild only when GitHub
confirms failed checks and that both the firmware and App jobs were skipped
without any steps. The original failed receipt remains unchanged.
The firmware registration job retains its existing backend immutability checks.

Receipts and sanitized logs are under `.cache/candidate-release/`. If observation
or the network is interrupted after a commit/push, use the printed receipt:

```bat
release_candidate.bat --resume .cache\candidate-release\RUN\result.json
```

Resume only observes the existing source and never bumps, commits, pushes,
dispatches or reruns a build. A failed/absent push requires explicit Git-state
reconciliation; do not invoke a new release to repair it. A failed formal build
or partial upload requires inspecting that original run and retained assets.
The default finite wait is 120 minutes, adjustable with `--timeout-minutes`.
An existing `active.lock` is not removed automatically: reconcile its owner first.
On the recorded Windows host, Git prefers the existing `Eitan-S-23` RSA SSH
route via `ssh.github.com:443` with strict host verification. The entry verifies
the account and tries an exact `main` dry-run before editing. It does not change
the remote, keys or Git/SSH configuration. On hosts without that local setup,
the existing authenticated HTTPS push remains available. A failed SSH check or
an uncertain push is not retried on another transport.

GitHub API reads of drafts and CI receipts use `GH_TOKEN`/`GITHUB_TOKEN`, the
owner's `gh auth token`, or the same existing owner CLI credential stored by
Windows in the active local console session. It is reused in memory, not
printed, copied to disk, or replaced. SSH does not replace these API checks.
All controllable child caches/temp/logs and Git outputs stay in the project.
Existing proxy environment variables take precedence; when absent, the entry
also passes the already-configured Windows system proxy to gh in memory. It
does not edit system proxy settings or retry an ambiguous push automatically.

For a full OTA test, the owner publishes the new candidate with no enabled delta
matching the device's actual current version, and checks that the App selects
the full package before starting. The script does not assume the currently
installed version or turn a delivered candidate into an OTA PASS.

### Existing Source And CI Route

`main` in `Eitan-S-23/E-Track` is the authoritative App/MCU source and automatic
candidate branch. Develop there, or in a task branch based on current
main and integrate the bounded changes back before delivery. Do not move MCU
or App changes to E-Track's historical `release/candidates` branch to trigger a build.

App delivery retains original Trace signing. Trace's `release/candidates` branch
hosts only the signing executor; it is not where current App source is developed.
It accepts an exact E-Track main SHA descending from integrated source
`a377846c1dbf966ca3f03a46872f905eb28b87a4` and the matching main push run.
App and firmware versions independently select their jobs on the same main push.

This main anchor's complete App tree is byte-identical to the original-signed
1.0.82 candidate `a977c848e03a2798a7b5c46319cd126a292395b4` (tree
`b8be80cfd70dc9d05e4905821b4aae81dd8a1fa8`). Main integrated that source without
the old candidate branch's commit ancestry. The migration therefore pins the
verified main baseline instead of removing the ancestry check or requiring an
unrelated history merge. The former `34495140` anchor remains historical.

1. For MCU delivery, update the code and increment `firmware.versionName` in
   `Tools/ota/original-admin-release.json`, including the release notes. Version
   codes use the existing `major * 10000 + minor * 100 + patch` encoding.
2. Validate and integrate the bounded changes to main. Commit and push `main` under
   the owner's authorization. No candidate-branch copy or manual dispatch is
   needed. If the owner wants the final push, leave the prepared main commit
   locally and provide `git push origin main`; do not push on their behalf.
3. For App delivery, increment both the name and code in
   `app/bluetooth_flutter_Trace/pubspec.yaml` and deliver the exact integrated App
   source through `main`. App code edits without a version change remain normal
   verification commits, not candidate builds.
4. `Original Admin Candidates` runs host regressions and independently plans the
   versioned components. Changed MCU inputs without a new version still fail
   before packaging. A versioned App push is built through the original signer
   only; the ordinary `build.yml` skips its duplicate APK/EXE verification build.
5. Inspect that run. The App job waits for the corresponding Trace workflow;
   a dispatch being accepted is not reported as a completed candidate delivery.
   Firmware uses the dedicated `firmware-candidates` environment without a
   manual reviewer step. Existing `firmware-rehearsal` and production approvals
   remain unchanged; candidate automation does not unlock production.
6. Open `https://trace-update-admin-staging.pages.dev`. The new full package is
   an unpublished candidate. Generate selected deltas there if desired, then
   choose Beta or Stable and publish. Automatic ingestion never chooses a channel.

App version identity changes must increase both the name and code. An unchanged
App version does not create a new candidate; a backward or partially reused
identity fails instead of overwriting installed bytes. MCU inputs retain their
existing explicit-version requirement. Documentation, workflow and backend-only
changes do not create packages. `MCU Firmware Build` does not duplicate main builds;
its pull-request, master build-only and protected manual routes remain available.

The earlier MCU main migration preserved the already delivered `3.3.30 / 30330` and
App `1.0.82+108`. Its source/baseline integration is explicitly CI-skipped, followed
by a documentation-only main push that exercises checks and skips both builds.
This one-time baseline establishment is not a version-check bypass in the planner.
The owner-approved App main migration on 2026-11-19 supersedes the former separate
App source-branch rule. It prepares `1.0.83+109` with the validated boot, icon and
reconnected-device display fixes, without changing MCU `3.3.34`. Only the trusted
source admission changes in Trace; no signing key, backend secret, channel or
existing package is moved. Main integration and candidate delivery do not complete
P5 or outstanding hardware/formal acceptance.

## Candidate Environment

The owner requested unattended firmware candidate delivery on 2026-11-18.
`firmware-candidates` has no required reviewers or wait timer and allows only
the exact `main` branch. Its `OTA_BOOT_CHAIN_READY` variable stays
`false`. Version checks, native package verification and explicit channel
publication remain mandatory; removing the manual wait removes none of them.

The environment reuses the existing firmware AES key as
`FIRMWARE_CANDIDATE_OTA_AES_KEY` and the existing
`ORIGINAL_ADMIN_FIRMWARE_DEPLOY_TOKEN`. The uploader consumes the repository's
unchanged `CLOUDFLARE_ACCOUNT_ID` and `E_TRACK_CI` Secrets. No key or token is
generated or rotated, and the shared rehearsal environment is not modified.
Configuration-only pushes still run checks without rebuilding an existing App
or firmware version. Manual workflow dispatch remains checks-only.

## Original App Boundary

E-Track holds the current App source. Trace holds the original Android signing
key, original payload key and original-backend deployment secrets. The source
workflow uses the owner's existing GitHub credential through
`ORIGINAL_ADMIN_ACTIONS_TOKEN` only to dispatch and observe the Trace workflow.
It does not copy signing keys or use E-Track's isolated historical App secrets.

The checked-in `original-app-candidate.template.yml` under the update-service
scripts directory is deployed as `.github/workflows/build.yml` on the Trace
repository's `release/candidates` branch. The old one-off upload-only branch
and all earlier release assets are left intact. Trace's normal `main` build is
not replaced by this branch's workflow.

Before executing source or accessing signing secrets, the Trace workflow checks
the exact E-Track SHA against the integrated ancestor and current main history, and
checks the originating push run. It pins Flutter 3.47.9 and Node 24. Both host
platforms run strict analysis/tests and APK/EXE builds for a new App version.

Android admission verifies the original package `com.wen.gaia.gaia`, exact source
version, original signer, both ARM libraries, original App/firmware endpoints,
original public payload key, V2 profile and inventory route. The existing profile
selector supplies `OTA_LINK_PROFILE`; a differently named Dart define is not an
equivalent configuration. Missing credentials fail; there is no development-key
or test-endpoint fallback.

Build assets are retained in an immutable GitHub draft before upload, avoiding
the historical Actions-artifact quota dependency. R2 uploads use the existing
full-byte readback implementation. Successful downloads become a prerelease with
`latest=false`, and CI registers the candidate without channel publication.

## Firmware Boundary

Each new firmware candidate compiles the exact main-push GCC App and matching Boot
through the existing key-bound builder with `p34-v2-candidate`, then runs the
existing full/recovery packaging and native byte verification. It does not reuse
the old pinned executable for new firmware source. The compiler and uploader
never receive each other's credentials; the private key header is removed before
registration. Neither an AC5 image nor a benchmark fixture can be substituted.

The original service and bucket remain fixed. `OTA_BOOT_CHAIN_READY` remains
false and production approval remains separate. Full and recovery assets are
uploaded; no arbitrary old versions are silently included as delta bases.

## Failure And Verification

Any analysis, test, native verification, upload or registration failure keeps the
workflow unsuccessful. Do not rerun a successful package to obtain cleaner logs.
Do not replace a GitHub draft/prerelease with the same version or regenerate its
APK. Reconcile retained assets and continue only the missing delivery stage.

Firmware artifact retention runs even after upload/registration fails, provided
packaging succeeded and private-key cleanup succeeded. The 14-day source-bound
artifact includes the exact finalized image, full/recovery envelopes, original
metadata and verification, and any partial upload/preflight receipts. No private
build directory or key header is retained. Missing upload success is still a
failure; retaining bytes only makes a later bounded recovery possible.

Automatic firmware candidate admission is first-attempt-only. GitHub's generic
rerun-failed-jobs action cannot resume that entry, even if only firmware failed.
Do not relax the guard or rebuild an immutable package blindly. Reconcile retained
packages, candidate rows and stored objects first. If an old run retained no
recoverable package and the candidate/objects are conclusively absent, use a fresh
unoccupied version through the existing main-push entry, keeping the failed
version's evidence. A new MCU-only version does not rebuild a successful App.

The source workflow's manual dispatch is checks-only. The Trace workflow also
has a `check_only=true` dispatch that validates source and guards without an APK
build, R2 upload, registration or channel change. These checks qualify the new
wiring, not an unexecuted new-version build or device update. The previous
1.0.76+102 native build, signature and R2 delivery evidence remains the original
package evidence.

## Android-Only Recovery

The Trace workflow accepts optional `resume_android_run` for an original failed
run whose Windows job succeeded but whose APK build did not succeed. Keep the
same `source_sha` and originating E-Track `source_run`; the continuation is a new
explicit dispatch, not a replay of the source push or the successful Windows job.
Both Android analysis and tests still run, and original signing, native APK
inspection, R2 readback and candidate registration remain mandatory.

Admission checks the failed run's source, branch, workflow, first attempt and job
outcomes, then requires exactly one unpublished source-bound draft containing
only the two completed Windows assets. Asset IDs, lengths and SHA-256 digests
are retained as job outputs, rechecked before Android work, and verified against
the downloaded Windows bytes. A successful APK build, retained APK, published or
changed draft, missing digest or failed Windows job rejects continuation. No
existing asset can be overwritten. The draft keeps its original workflow target.

Draft reservations must be checked through `listReleases`, including unpublished
drafts: `getReleaseByTag` may return 404 for a real draft. Treating that 404 as a
free version slot can accidentally request a duplicate build.

Android checkout reuses the development workflow's sparse App/test dependency
set and its 12 GiB pre-SDK disk check. It does not retrieve firmware archives,
restore two overlapping Gradle caches, delete hosted-machine system directories,
change dependencies, or purchase a larger runner. Original runner disk failures
and partial logs remain failures, even when the bounded continuation succeeds.
Executable admission regressions are in `tests/ota/test_original_admin_candidate.mjs`.
