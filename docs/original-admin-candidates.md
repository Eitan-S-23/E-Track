# Original Admin Candidate Delivery

## Developer Workflow

The delivery branch is `release/candidates` in `Eitan-S-23/E-Track`. It starts
from integrated source `34495140d28ce401616cc19b6b62bb6bba1d764c`, not the older
standalone Trace application. Other branches retain their existing behavior.
This is an operational candidate branch, not a merge into `main` or completion
of P5/hardware acceptance.

1. Make the App and/or firmware changes on this integrated source line.
2. For an App change, increment both the name and code in
   `app/bluetooth_flutter_Trace/pubspec.yaml`.
3. For a firmware change, increment `firmware.versionName` in
   `Tools/ota/original-admin-release.json`. Version codes use the existing
   `major * 10000 + minor * 100 + patch` encoding.
4. Commit and push to `release/candidates`. `Original Admin Candidates` runs
   host regressions and prepares only the changed component's new version.
5. Inspect that run. The App job waits for the corresponding Trace workflow;
   a dispatch being accepted is not reported as a completed candidate delivery.
   Firmware signing keeps the `firmware-rehearsal` environment's existing
   reviewer protection. A waiting approval is not a successful build, and this
   workflow does not approve itself or unlock production.
6. Open `https://trace-update-admin-staging.pages.dev`. The new full package is
   an unpublished candidate. Generate selected deltas there if desired, then
   choose Beta or Stable and publish. Automatic ingestion never chooses a channel.

Changed code without a version increment fails before package creation, rather
than overwriting an installed version. Docs/backend-only changes do not rebuild
the App or firmware. The initial automation delivery changes neither version,
so it does not rebuild or upload the already delivered `1.0.76+102` or `3.3.24`.
Both components may be advanced together in one push.

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
the exact E-Track SHA against the integrated ancestor and candidate branch, and
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

Each new firmware candidate compiles the exact pushed GCC App and matching Boot
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
