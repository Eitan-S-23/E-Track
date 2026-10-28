# P35 Candidate Release-Mode Build Verification, 2026-10-28

## Authority And Exact Inputs

The current user explicitly authorized the outstanding APK/EXE build verification
on source `28860cf8ab4edffef7e28005154348ee768df32a`, with artifact archival but
without merge, publication, deployment or device operations. This is a software
build gate, not independent acceptance, production qualification or authority
to repeat P3-5/P5 hardware campaigns.

Exclusive branch: `dev/flutter/p35-smoke-followup-20261027`.
Repository: `Eitan-S-23/E-Track`; workflow: `.github/workflows/build.yml`.
Current remote preflight confirms the exact branch/source above; main remains
`91fed6bc863d07edc7173c8e3c08b14c159f7863`.
Source version: `1.0.62+88`. No version or product input was edited for this
nonshipping exact-source verification.

Dispatch inputs:

- `publish_release=false` and `replace_existing_release=false`.
- `release_ota_link_profile=adaptive-v2-candidate`.
- Empty `release_tag`, `release_application_id_suffix` and `firmware_latest_url`.
- Existing signing selection and configured permanent endpoint behavior retained.
- No device address, temporary URL, runtime config, run ID or package identity
  was supplied as a build define. No new signing key or credential was generated.

The workflow's Release/Cloudflare job cannot run on this branch with publication
false. Pages deployment is independently gated and has already been skipped.
Existing vendor/GitHub hosted build tools and runner caches are reused; no local
Flutter/Gradle build or developer-machine SDK installation is selected.

## Dispatch And Preserved Attempts

One dispatch was issued; no rerun or second dispatch was issued.
Run: https://github.com/Eitan-S-23/E-Track/actions/runs/40583705411
Attempt: 1; event: `workflow_dispatch`; source matches the authorized commit.
Created: `2026-10-27T21:04:58Z`.

The first read-only existing-run lookup failed with a GitHub API EOF. Its failed
`candidate-build-existing-01.*` receipt is preserved. The second read-only lookup
completed and returned an empty exact-source standard-build inventory before
dispatch. No uncertain dispatch was retried. Two quoted content searches failed
argument parsing without writing files; corrected unquoted searches were used.

Original local receipts are `.cache/records/candidate-build-*.{json,log}`;
downloaded artifact ZIPs use the same prefix and `.zip`. They are write-once and
do not replace earlier lifecycle or standard-build evidence.

## Result

PASS for the authorized software build gate. Run 40583705411/1 completed success;
Android job 122469769935 and Windows job 122469769558 passed every recorded step,
including analysis, full tests, release compilation and strict artifact upload.
Android also passed fixed signing selection and actual APK verification. Release
and Pages jobs were skipped with no executed steps. No rerun was needed.

| Host | Actual test result | Raw terminal anchor |
| --- | --- | --- |
| Android/Ubuntu | 813 passed, 16 skipped, 0 failed; analyze no issues | candidate-build-android-console-01.log:24397 |
| Windows | 794 passed, 35 skipped, 0 failed; analyze no issues | candidate-build-windows-console-01.log:24084 |

Both build logs bind Flutter 3.47.8, framework revision
737ba8f885dc774b53b442759999a312c9461e4e through the setup action's actually
restored cache key and active FLUTTER_ROOT. This workflow did not print a separate
machine-version command: independently observed Dart/engine identity stays
NOT_OBSERVED, not copied from the preceding development run. Earlier candidate
tests and full development reports remain their own source-bound observations.

Archival directory: `.cache/apk-exe-28860cf8-20261028/`.
`inventory.json` binds all three extracted assets to original API-bound ZIPs;
`verification.json` records jobs, tests, original log hashes/line anchors,
manifest, signature, verifier identities and unexecuted scopes.

| Asset | Bytes | SHA-256 |
| --- | --- | --- |
| android/ble-monitor-android.apk | 47429900 | eec74359fef22a81f156cf074f5e010f6cd72a10ac88d578622c701e69ee673c |
| windows/ble-monitor-windows.exe | 93184 | 1ff1ade8d917ea6651d7de77ee872ffe2a14a1683600e75d9d3019799cc6c020 |
| windows/ble-monitor-windows.zip | 20518702 | e040b6376e789ac2136992d75aaf78e6d262989274cf3988a57920c4cbd1bb35 |

The actual APK declares com.wen.gaia.gaia, 1.0.62+88, min SDK 24, target SDK 36,
compile SDK 35, ARM64/ARMv7 and no debuggable flag. No debug kernel blob exists.
Existing fixed certificate SHA-256 is
9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579:
one signer, v2 verifies in CI and against the locally preserved APK. This is
fixed candidate/development signing, not production-signing qualification.
Windows is AMD64; its bundle contains the same exact EXE bytes as the standalone
asset. Neither the APK nor EXE was installed or executed.

Android artifact 12770484953: ZIP 25869386 bytes, SHA-256
2c36f622480784c98122392ded57c0f29a308c262336c3c62232c70330d9d9de,
expires 2026-11-10T21:14:02Z. Windows artifact 12771510430: ZIP 20548878 bytes,
SHA-256 6ce343a897373904ac66009a55451d4fd32a1023efbbd826649683a116aa97bf,
expires 2026-11-10T21:12:30Z. Both original download bytes match API digests and
lengths; required originals are already local. Existing safe extraction and
path guards were reused, not replaced by a new archive framework.

### Diagnostics And Limitations

Android has ten explicit build Warning lines: three impending Flutter support
deprecations (Gradle 8.14, AGP 8.11.1, Kotlin 2.2.20) and seven plugin SDK 36
requirements against compile SDK 35. The parser's compiler_warning_lines bucket
contains these Flutter dependency-validator messages, not ten native compiler
warnings. There are zero matching compiler error lines on both hosts.
Android additionally has one SDK mismatch summary, one Gradle deprecation notice,
two nonfatal Already-watching-path exceptions (wrapper/build), two Node runtime
deprecation notices and one Node-20 Actions annotation. Windows has zero matching
build/compiler warning or error lines, two Node runtime deprecation notices and
one Node-20 Actions annotation. All originals and distinct diagnostic anchors
remain in verification.json; neither a green job nor a passed upload erases them.
No dependency validation bypass or assertion/skip relaxation was added.

FAST-RELEASE-APK-ENDPOINT-01: NEED_DECISION, configuration owner/root. Android
build log lines 24503/24504 explicitly report no configured Cloudflare public
update URL and payload public key; this binary has no default firmware latest
endpoint and retains the documented fail-closed/legacy behavior. Empty dispatch
inputs were authorized and sufficient for build-only verification, not P3-5
backend admission. This does not establish a missing backend implementation.
Before a real-backend candidate is called ready, root must choose the existing
permanent firmware endpoint and permitted test channel and reconcile their
existing asset/state evidence. A changed-input build would be separate from this
exact-input result; no repository variable/secret, channel stop flag, backend
state or production gate was changed here. Actual BLE negotiation and speed
remain NOT_RUN for these artifacts.

One inline metadata command exceeded cmd.exe's length limit before execution,
so it created no receipt or result. Its same task-specific checks were moved to
.cache/candidate_build_verify.py using apply_patch; the owned receipt adapter
then completed them once as candidate-build-archive-audit-01. This is a one-shot
original-file evaluation, not a new collector, acceptance harness or CI rerun.

## Remaining Boundaries

Independent review/acceptance, main integration and production release remain
separate. No new backend register/R2/D1 operation, APK installation, MCU reset,
OTA transfer, P3-5 ten-disconnect campaign or P5 long test is performed here.
The completed lifecycle archive audit and its original document hash remain
unchanged; this new build record supersedes only the latest-source APK/EXE
NOT_RUN state after actual results are available.

All selected developer-machine writes are under this exclusive worktree:
this record, contained receipt/HOME/TEMP/cache paths and the build archive.
No common Git metadata write, project-external local output, move or deletion
is selected. This record remains local/uncommitted pending root integration.
