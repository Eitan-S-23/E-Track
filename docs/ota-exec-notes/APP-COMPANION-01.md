# APP-COMPANION-01 Implementation Record

## Complete Public APK Readback 2026-11-19

The owner's next autonomous-completion follow-up closes the remaining remote
whole-file check without another build, deployment, channel change or device
operation. A fresh Stable manifest selects the original signed `1.0.84+110` APK.
The actual signed `/api/public/download` response was streamed completely to a
project-private file, then that closed file was independently hashed:

- Bytes: 48,718,441; HTTP 200; original R2-backed Public download route.
- SHA-256: `de4ce7c0c3f1d9dc4a753ddd7d397e1192fea25d13a057a97fd4374fadfadf6a`,
  matching the exact original signing CI and registered candidate.
- Direct-route download/hash time: 194.350 seconds, within the new bounded
  900-second verification window. No system proxy setting was changed.

The previous 180-second timeout and bounded probe remain historical evidence,
not retroactively marked complete. A further proxy-route transfer was stopped
while comparing routes; its 15,480,320-byte partial file is retained and is not
an APK verification pass. The succeeding direct-route whole-file result now
supersedes the earlier Public-body coverage limitation below.

Originals: `.cache/companion-fast-20261119/public-apk-complete-01/interrupted.json`
and `public-apk-complete-02/result.json`; the latter directory retains the full
APK in `private/` and the final write audit. No new update is needed for this
verification. Actual phone/MCU installation and radio/UI observations remain
outside this remote check; this does not close whole-card physical acceptance.

## Stable Rollout Completed 2026-11-19

The owner's follow-up requests autonomous completion and grants the needed
authorization. This supersedes the preceding handoff's reservation of this
batch's delta generation and channel publication. The bounded continuation uses
only the existing original staging Stable channels: Android 109 to 110 and MCU
3.3.34 to 3.3.35. Beta, configuration, credentials, signing infrastructure and
devices remain untouched; protected production gates are not bypassed.

Fresh owner/D1 inspection found App Stable 1.0.83 at revision 59, MCU Stable
3.3.34 at revision 8 and 42 existing delta jobs. Both new full candidates were
already available from exact main product source `48ad9f03`; neither was rebuilt.
The existing selected-base workflows generated exactly two new jobs, both on
attempt 1 with successful source-bound reconstruction and R2 readback:

| Update | Actions | Patch Bytes | Reduction From Full | SHA-256 |
| --- | --- | --- | --- | --- |
| Android 109 to 110 | [44450526439](https://github.com/Eitan-S-23/Trace/actions/runs/44450526439) | 778654 | 98.40% | `70a4ed92a16dc4d1902cae64518c4f07e5422b6f76e24fd3aeccf43df16a28fb` |
| MCU 3.3.34 to 3.3.35 | [44450532113](https://github.com/Eitan-S-23/E-Track/actions/runs/44450532113) | 8236 | 97.27% | `233cb19d66d2f04a194768314b2c0f7b9ac5042d1695dc7bd0554f13515ab73a` |

Android uses the unchanged original Trace generator `4745aead`, bsdiff/LZMA and
the original Ed25519 key. Its exact base APK SHA is
`b5e28b14de5bd6b956ac54a9c27053a4c1873077bec6513487b764d6668ce47d`.
MCU uses the unchanged E-Track generator `3135a06e` and exact 3.3.34 raw-image
SHA `06554819f0b140a3aeb64ec7fe253df697659dd6fcaa72d3c22f0d76fb6330b9`.
Both result/input hashes and target hashes match their selected pairs. The App
signature was independently checked locally; both actual stored patch objects
were completely read and hash-matched before enabling them. Original Actions
logs are retained without redispatching either successful job.

Both patches are enabled, revision 4. App Stable now points to
`rel_trace_android_v1_0_84` at revision 60; MCU Stable points to
`fw_64679463f44154bc305a755a32492463dc6937338d7633614b787dccd9af52f4`
at revision 9. The original revision checks guarded both publications. Both Beta
rows, channel stop/download flags and all 42 prior delta identities are unchanged;
there are 44 jobs in total. Windows assets retain the preceding successful build
and original prerelease; no nonexistent Windows update channel was created.

Real Public checks confirm that the current base selects its new patch, an
unmatched base selects the full fallback, and the new version returns NO_UPDATE.
Both signed patch downloads and the MCU full download complete with exact byte
counts and hashes. App full fallback returns HTTP 200, the expected 48,718,441-byte
length, R2 source and valid APK prefix. A whole-file public APK download exceeded
the host's 180-second bound; that failure is retained. The follow-up reads 4,623
bytes and reuses the original signing CI's full upload/readback and exact GitHub/
R2 hash evidence. It is explicitly not a new whole-file Public hash check.

Two earlier read-only transport failures did not dispatch or enable anything.
The first publication successfully advanced Android, then the strict firmware
route rejected a missing `Accept: application/json` header. Repairing the host
caller preserved that validation; the follow-up read back Android's completed
publication and performed only the pending MCU publication. An prematurely
invoked Public probe lacked the final publication receipt and made no mutation.
All failed receipts are retained, not rewritten as success.

Evidence is under `.cache/companion-fast-20261119/rollout/`: the immutable plan,
`keyring-rollout-inspect-01`, `create-01`, `status-01/02`, `verify-01`,
`enable-01/02`, `publish-01/02` and `public-01/02/03` (each with the full
`keyring-rollout-` prefix). The decisive final Public result is
`keyring-rollout-public-03/result.json`. Original job logs are in sibling
`keyring-logs-09/10`; initial live discovery reused the established reader and
saved a new `keyring-inspect-03` under
`.cache/firmware-check-update-release-20261119/`, without altering older receipts.
The host adapter's eight mutation-boundary cases pass. All controlled writes are
project-local, and the final write audit is retained beside the rollout records.

No phone/MCU installation, reset, flash, OTA execution or measured radio timing
was performed. Users can now request the new update over the existing wireless
route without USB. D0-D5, C1-C6 and whole-card independent acceptance retain their
existing scope; deployment and host checks do not close those physical obligations.

## Fast Reconnect And Candidate Delivery 2026-11-19

The owner authorized this bounded implementation, main integration/push, new
versioned candidates and the separate Admin hotfix. Phone USB is unavailable and
is not a delivery prerequisite. No phone installation, MCU flash/reset/OTA,
Stable/Beta promotion, delta generation or Trace signing-infrastructure migration
is included. The icon-regression hypothesis was explicitly dropped by the owner.

Product source `48ad9f03beccf74feffacdaed303919146fda35f` is now on local and
remote main, following Admin hotfix `9e19f9d1`. The owned implementation worktree
is `.worktrees/companion-fast-20261119`, branch
`dev/flutter/companion-fast-20261119`; exactly 15 App/MCU/test/contract files were
fast-forward integrated. App `1.0.84+110` and MCU `3.3.35` are new candidate
versions, not replacements for the successful 109/3.3.34 artifacts.

### Implemented Behavior

- The existing native companion service keeps its acknowledged runtime after
  transient offline/identity failures and retries at 2/4/8 seconds within one
  monotonic 60-second window. The original saved-address attempt is immediate;
  only exhaustion enters long offline backoff. Success cancels/reset retries,
  duplicate failures do not stack timers, later disconnections reacquire a
  bounded wake lock, and disable/revision/permission/runtime loss stops recovery.
  Active OTA ownership is never replaced by a retry or a second BLE loop.
- Bluetooth STATE_ON restores an existing enabled association without waiting
  for the periodic job or a previous offline backoff. Off/turning/unrelated
  broadcasts do nothing; the receiver never opens an Activity or grants consent.
- GPS motion no longer prevents an explicitly confirmed install, at both the
  modal and actual BEGIN/BEGIN2 overlay boundary. Open/paused GPX files and low
  battery without charging still refuse admission. Consent, reservation, overlay
  ownership, firmware integrity and final target verification are unchanged.
- The actual module receives bounded `AT+NAME?` / `AT+NAME=E-Track` commands
  before the existing single startup reboot. A matching name avoids a persistent
  rewrite. `Doc/ble.pdf` specifies that naming takes effect after reboot. The
  fixed production candidate profile participates; baud experiments remain
  isolated. No MAC, UUID, baud, binding or protocol-marker change is included.
  App metadata regressions retain the same address while a fresh E-Track
  advertisement supersedes a stored X-Trace name.

### Executed Development Checks

Ordinary dual-host run `44438101219` and full native/debug run `44438330161`
attempt 2 pass on exact source `48ad9f03`. Flutter is 3.47.9,
`c197ca5199e9ee5661e865596c9c07294dfab51c`, Dart 3.13.7. Full Linux tests report
942 passed / 16 skipped; Windows reports 893 / 65. Both strict analysis and
eight per-host candidate tests pass. The supported native entry requires
`build_apk=true`; its development APK was built/verified, not installed or used
as a substitute for the original-signed release build.

Original JUnit reports contain 107 executed native tests, zero failures/errors/
skips: CompanionIntegration 69, CompanionService 20, DeviceOtaService 18. The
new retry and Bluetooth-on cases are present on the applicable SDK variants.
They exercise real Bridge/Service/receiver orchestration at OS/embedding test
boundaries, not real radio timing. The first native run failed before tests on
a Maven dependency HTTP 404. An exact-URL read returned 200 with the pinned
SHA-256; only the failed Linux job was rerun. Original Windows success and the
failure log remain retained, without a dependency change or test relaxation.

Host checks pass 86 Python cases (33 startup/name, 19 safety, 24 control,
9 real-LVGL modal, one menu harness) plus 65 candidate/planner cases. The old
unsafe receiver/UI boundaries still fail their original regression oracles.
The first new motion fixture incorrectly expected consumed consent to re-enable
the button; it was corrected to assert one choice and successful receiver
admission while keeping duplicate consent disabled. An obsolete GPS stub caused
an earlier harness-only unused-function error. Both generated fixtures remain.

GCC App/Boot and MSBuild simulator builds pass. The standard batch first hit
Windows dependency-path length errors in unchanged LVGL assets. Reconfiguring
the same project-local build with `CMAKE_OBJECT_PATH_MAX=200` fixed the host
path issue; no external short directory or source workaround was used. Successful
GCC emits 641 warning lines and simulator 102, all with zero errors. Exact
artifacts, timestamps, sizes and SHA-256 values are in `build-02/result.json`.
These local binaries are not the keyed production CI candidate artifacts.

All originals are under `.cache/companion-fast-20261119/`: `host-01`,
`build-01/02`, `keyring-logs-02/04`, `keyring-artifacts-01`,
`native-verification.json`, and Git integration/push receipts. The XML reader's
initial classname/filename filtering mistakes are recorded separately; original
reports were not edited and no CI run was repeated for that offline reader.

### Automatic Candidates Delivered

Main push `48ad9f03` completed original-candidate run
[44441921617](https://github.com/Eitan-S-23/E-Track/actions/runs/44441921617),
including checks, firmware and App delivery. The original Trace signing child
[44442089690](https://github.com/Eitan-S-23/Trace/actions/runs/44442089690) succeeds
for Android APK and Windows EXE/ZIP. APK verification confirms the original
`com.wen.gaia.gaia` package, signer
`3cecee6330a930e020b454b6d4a79568f4494ca324ae7bcf2c1914e51b04ab47`, both supported
ARM ABIs, original backend, BLE V2 and signed bsdiff/LZMA capability. The original
workflow fully uploads/readbacks APK and manifest, then registers
`rel_trace_android_v1_0_84` at 02:32:59 UTC. Its assets remain in the original
[v1.0.84 prerelease](https://github.com/Eitan-S-23/Trace/releases/tag/v1.0.84),
not GitHub latest or an Admin Stable/Beta promotion.

The actual keyed GCC profile is `p34-v2-candidate`, including
`P34_OTA_FIXED_CONFIG=1` and `CONFIG_BT_BAUD_EXPERIMENT=0`. Its archived compiler
binary contains the real E-Track query/set commands and no legacy XTrace set.
CI source proof, compiler binary hash and upload receipts agree. MCU registration
is `fw_64679463f44154bc305a755a32492463dc6937338d7633614b787dccd9af52f4`, ready with
two assets and no published channel. Target raw image SHA-256 is
`05d0b280cf2b0df09cff1b4f1bda15a7924d6b1cf44789997a9ac12eba43a55a`.
Native candidate GCC reports 641 warning lines and zero errors.

| Delivered Asset | Bytes | SHA-256 |
| --- | --- | --- |
| Android APK | 48718441 | `de4ce7c0c3f1d9dc4a753ddd7d397e1192fea25d13a057a97fd4374fadfadf6a` |
| Windows EXE | 161792 | `115f9c9faaa61e5ea9175918f25a07bb4c437be93308a351fa256a6d399a99ec` |
| Windows ZIP | 20679260 | `e7f2d377d6e81f89ce3a857b3a9b218e0014b3c344836d03575f1ca180eeacc2` |
| MCU full ETU | 301429 | `0a46e6d97e3c806b5c137d9d9beef250a23a626bccfd47f4deca6b30f9a80288` |
| MCU recovery BIN | 630768 | `0aeeaf00697e982fb5522c44c55c14e9295203fcf6fdd57966fd3981bad9bcb1` |

Final real-owner/Admin and D1 readbacks confirm both exact source/run/version
identities, available assets and candidate visibility. Both MCU objects were
independently read completely from R2 and match the table; App R2 identity
matches the original signing workflow's full readback and GitHub asset digest.
Neither new candidate is referenced by a release channel. Channel pointers and
all existing delta identities are unchanged during verification. No delta was
generated, no device operated and no successful older candidate rebuilt.

Additional originals: `keyring-logs-05/06/07`, `keyring-artifacts-02`,
`firmware-verification.json`, `app-ci-evidence.json`, and
`keyring-cloud-live-03/result.json` in the same task cache. The result reader
distinguishes actual timestamped receipt JSON from the shell's echoed source.
All selected output paths remain within the project; existing unrelated files
and failed receipts are retained. The final filesystem audit is recorded there
separately, not inferred only from Git status.

R01-R05/T01/T02 historical review, D0-D5, C1-C6 and formal whole-card acceptance
retain their existing boundaries. Actual wireless recovery time, the displayed
device name and motion-time upgrade must be tested after the owner installs
the new candidates; no measured speedup or new physical observation is claimed.

## App Main Candidate Migration And 1.0.83, 2026-11-19

The owner authorized migration of the App candidate entry to main, integration
of the validated repairs and the final main push. They explicitly retain the
subsequent backend publication/delta and phone operations. No manual package
dispatch, channel change or device action is part of this delivery.

This integration preserves the commits of validated App source
`ab0ef2c589a07b04776e3483c7bf9b7af9407efd`, including immediate guarded boot
recovery, independent branded launcher resources and reconnected-device name/
capability restoration. Its development evidence remains run `44406058730`:
Linux 941/16 and Windows 892/65 passed/skipped, both analysis/candidate checks,
84/84 native checks and the verified debug APK. Only the shipping version changes
to `1.0.83+109`; a fresh original-signed APK/EXE build remains the automatic
pipeline's responsibility, not an inferred result from the debug package.

The main push now independently selects an App candidate when both App version
name and code increase. Ordinary App edits with unchanged version remain normal
verification commits. Invalid/backward/partially reused versions fail. The same
version predicate lets the ordinary build workflow skip a duplicate APK/EXE
build only for versioned E-Track main pushes. MCU `3.3.34`, its explicit version
rule, protected environments, keys and publication gates are unchanged.

Trace's signing executor stays on its existing `release/candidates` workflow;
current App source is no longer delivered through E-Track's branch of that name.
Only the source description, trusted baseline, main-history membership and
originating source-run branch checks changed. The remote workflow update is
`12ff41fc11eb4920ab32d69ae0f7e1cc095f996e`, replacing `8797520045ddedbdcff9c7fe66a83c7a36882256`.
The API readback and commit comparison confirm that only `.github/workflows/build.yml`
changed. No signing/backend Secret or existing draft/release was changed.

The old App delivery ancestor `34495140` is not an ancestor of current main.
Instead of deleting the history check or merging unrelated history, the new
guard pins the freshly verified pre-migration main
`a377846c1dbf966ca3f03a46872f905eb28b87a4`. Its entire App tree equals original-signed
1.0.82 source `a977c848e03a2798a7b5c46319cd126a292395b4`, tree
`b8be80cfd70dc9d05e4905821b4aae81dd8a1fa8`. The obsolete synthetic firmware
baseline fallback was removed; the planner reads the actual before-commit's
firmware version and must not rebuild already delivered MCU 3.3.34.

Evidence is under `.cache/app-main-20261119/`: `source-baseline.json`,
`keyring-inspect-01`, `keyring-integrate-01`, `keyring-trace-01` and
`host-tests-02`. Final host regression passes 65 workflow/planner/admission cases
and eight original-App identity cases. Tests include real temporary Git checkouts,
the actual read-only build selector, both-component selection, ordinary App
commits, rejected legacy branches, wrong history and retained immutable-draft
continuation. All three affected workflow YAML files parse successfully.

The shared workflow guide, agent entries and board are delivered with this
integration; older LOCAL_PENDING checkpoints below are superseded only for main
source delivery. Original-signed build completion, candidate ingestion, channel
publication and actual phone startup/icon/display validation remain separate.
At this integration checkpoint the automatic build/ingestion result is not yet
confirmed. Follow the push's `Original Admin Candidates` run; the owner requested
handoff after the push rather than an agent-driven publication or installation.

## Android Boot And Desktop Icon Repair, 2026-11-19

The owner reported no prompt recovery after a phone reboot and the Flutter
template icon on the home-screen launcher. They subsequently clarified that
the recent-tasks icon is normal; no screenshot is required to restate that
observation. This is separate from the completed MCU 3.3.34 publication below.

The first observation is read-only, without starting an Activity/service,
sending a boot broadcast, reinstalling an APK, resetting the phone or operating
the MCU. Original evidence is `.cache/app-boot-icon-20261119/inspect-01/`.
It binds Vivo V2312A, Android API 33, original App 1.0.82/108 and the installed
48684713-byte APK SHA-256
`8567bf5b93294b7df46247ba7bf23a8eb8b1d64128731ae6ae017b1acc441a65`.
Bluetooth/notification/boot permissions and the battery exemption are present.
The phone had been up about 759 seconds. JobScheduler records job 2412 running
at 03:40:57 local time; the companion foreground service was created then,
during collection, not by an agent launch command. Earlier boot-delivery detail
was not present in the retained bounded log and is not fabricated.

BOOT-01: the existing receiver calls `restore`, which recreates the persisted
15-minute recovery and periodic-check jobs but never immediately requests the
background runtime. The repair adds immediate guarded startup after boot or
package replacement. Transient Bluetooth initialization gets a non-persisted
five-second-minimum retry job with a fixed two-minute elapsed-time deadline;
system scheduling is not a real-time guarantee. Disabled/missing association,
denied permissions and a healthy existing runtime do not create duplicate
owners. Periodic fallback, pending checks and actual runtime acknowledgment
remain intact. Native logs name the system event/result, not device addresses.

ICON-01: the exact installed APK was read back, then parsed with Google's aapt2
without building or repacking it. Its legacy PNG, adaptive foreground and
Android 13 monochrome binding all contain/reference E-Track artwork. The home
screen's Flutter icon is therefore inconsistent with those installed resources;
the precise OEM cache/theme writer is not proved. The repair declares an explicit
branded launcher resource for Application, MainActivity and roundIcon while
preserving the package/component names, artwork and user data. Physical launcher
refresh and reboot persistence still need the updated installed package; this
entry does not claim that changing XML alone repaired the phone.

Implementation is on owned sparse worktree `.worktrees/app-boot-icon-20261119`,
branch `dev/flutter/app-boot-icon-20261119`, source
`0efd19aa2cd17c241e94c8a4056e3fb335e47119`. Five scoped Android files are pushed.
The push skips duplicate checks in favor of one explicit full/native dispatch:
[44387264148](https://github.com/Eitan-S-23/E-Track/actions/runs/44387264148),
both hosts, `build_apk=true`, `device_ota_native_tests=true`, debug-only suffix
`.bootcheck`. The new tests exercise actual receiver/job/service orchestration,
cold headless startup, radio delay/deadline/disable, permission denial, duplicate
ownership and manifest icon resolution. At this checkpoint CI is RUNNING;
release APK/EXE verification, main integration and installation are NOT_RUN.

The owner has been asked for bounded original-signed App build/install authority,
preserving data and permissions, and whether they will perform the final phone
reboot. No new original-signed release or device mutation precedes that answer.
The proposed physical check is one installed candidate, then one reboot after
baseline collection, followed by startup/service/BLE and home-screen icon checks.
Do not clear launcher/App data, replace the launcher component, uninstall the
normal App, retest the completed MCU OTA or infer whole-card D0-D5/C1-C6 acceptance.

### Native Validation And Icon Resource Correction

The first run `44387264148` completed with Windows success and Linux failure.
Both hosts passed analysis and their full Dart tests: Linux 927 passed/16 skipped,
Windows 880 passed/63 skipped; each also passed eight candidate tests. Flutter
was 3.47.9 (`c197ca5199e9ee5661e865596c9c07294dfab51c`), Dart 3.13.7. Debug APK
compilation passed, but native failure correctly blocked verification/collection.

The original JUnit reports in `keyring-artifacts-01/extracted/` show 83 native
tests, 80 passing and three icon assertion failures. All new boot/radio/deadline/
permission cases passed. `CompanionServiceTest` is 9/9 and `DeviceOtaServiceTest`
18/18. On API 26/31/34, Android resolved the new icon alias to the underlying
resource ID rather than the independently expected launcher ID. This is a real
limitation of the initial icon approach, not evidence that the phone's OEM cache
has been inspected. The assertions are retained rather than changed to accept
the alias collapse.

Source `82c56986ad71a7dabdd14693baccfdd676f99b31` replaces that approach with
independent `launcher_e_track` adaptive XML resources for Android 8+ and 13+,
retaining the original artwork and a legacy fallback. Application, roundIcon
and MainActivity reference the same distinct resource. The icon test now also
executes on the actual phone's API 33. Startup implementation is unchanged.
The changed-input full/native validation is
[44390811240](https://github.com/Eitan-S-23/E-Track/actions/runs/44390811240),
RUNNING at this checkpoint. This remains development-only; no App installation,
phone reboot or release APK/EXE invocation has occurred.

Retained first-run Linux log artifact `14466744168` is 342194 bytes with ZIP
SHA-256 `4c5859b22d9147a463fa6c382a75abeb46c8c914224da3b1fd1e2e00639d38b1`,
matching GitHub metadata. Original console logs are in `keyring-logs-01`.

### Compiled Drawable Validation

The second run `44390811240` completed with Windows success and Linux failure.
Analysis and full Dart tests still pass; debug compilation passes. The original
native reports contain 84 tests, 80 passing and four failures at the subsequent
`getApplicationIcon` non-null assertion, not at the manifest/resource-ID checks.
All four API 26/31/33/34 bindings now resolve the distinct branded resource.
The startup tests remain passing. APK verification/collection is correctly
NOT_RUN after the native failure.

This failure is a test-boundary defect: the pinned Robolectric 4.14.1
[`ShadowApplicationPackageManager`](https://github.com/robolectric/robolectric/blob/robolectric-4.14.1/shadows/framework/src/main/java/org/robolectric/shadows/ShadowApplicationPackageManager.java#L1286)
implements `getApplicationIcon(String)` as `applicationIcons.get(packageName)`.
That is an uninjected stub map, not the installed/compiled resource loader.
Do not fill the map with a fabricated passing icon or reinterpret this failure
as an observed OEM launcher defect.

Source `4d82427ccce91662642f5b8c0894588b3fe74cf3` keeps every resource-ID and
old-ID rejection assertion. It loads the actual compiled resource through
`Resources.getDrawable`, requiring an adaptive icon, foreground/background and
the API 33+ monochrome layer. Production inputs are unchanged from `82c56986`.
The full two-host/native debug run is
[44393287786](https://github.com/Eitan-S-23/E-Track/actions/runs/44393287786),
RUNNING at this checkpoint. This is a changed-test-input validation, not a blind
retry or an installation/release claim.

Second-run originals are in `keyring-logs-02` and `keyring-artifacts-02/extracted`
under `.cache/app-boot-icon-20261119/`. The Linux archive is artifact
`14468947052`, 319197 bytes, ZIP SHA-256
`b9bc59e79fe02f863845b33506459592b1e9fd91fb675dc50deba7b04d95fcb7`, verified
against GitHub metadata. The existing bounded collector is extended only to
retain the exact successful run's debug APK and validate its source, suffix,
development-only classification, length and both archive/APK digests before
offline resource inspection. It performs no device operation or local build.

### Development Validation Passed

Run `44393287786/1` on `4d82427ccce91662642f5b8c0894588b3fe74cf3` completed
successfully on both hosts. Original console logs are `keyring-logs-03`; original
Linux logs and JUnit reports are `keyring-artifacts-03/extracted` under the same
task evidence root. Flutter/Dart revisions match those recorded above.

| Executed Check | Result |
| --- | --- |
| Linux analysis/full Dart tests/candidate tests | PASS; 927 passed, 16 skipped; 8 candidate tests passed |
| Windows analysis/full Dart tests/candidate tests | PASS; 880 passed, 63 skipped; 8 candidate tests passed |
| CompanionIntegrationTest | 57/57, including actual receiver/job/service paths and all four icon API variants |
| CompanionServiceTest / DeviceOtaServiceTest | 9/9 and 18/18; total native 84/84, zero skips/errors/failures |
| Linux debug APK build/verification/collection/upload | PASS; not an original-signed release or EXE build |

The retained Linux archive is artifact `14470105335`, 346537 bytes, SHA-256
`a7fabaf51ddcfaf673536ff9e466b8d9c39b9cf58160f55b5716f1377cce4aee`.
Debug archive `14470425126` is 76244553 bytes, SHA-256
`db64939efe264aab7c50e817891c3437483be07765fc1be7ce6a051486c1d8a4`.
Both match GitHub's archive digests. Its actual APK is 132538720 bytes, SHA-256
`e6c8d31a1ac549515d6c06832823a17a14cce1d6b233e7f22af9720d230cbf1a`, package
`com.wen.gaia.gaia.bootcheck`. The fixed development signer is not the installed
original App signer; this APK is retained for inspection, not installed.

`compiled-icon-01/result.json` records read-only aapt2 inspection of that actual
APK. Application, MainActivity and roundIcon reference new resource
`0x7f0c0002`, distinct from legacy `0x7f0c0000`. Both Android 8+ and Android 13+
adaptive XMLs resolve the original foreground/background, with the 13+ monochrome
layer intact. Raw PNG file bytes differ between release/debug packaging; the
initial byte-comparison failure is retained, not hidden. The existing Playwright
PNG decoder then confirms identical dimensions and RGBA pixels for all ten
legacy/foreground density images in `compiled-icon-01/artwork-pixels.json`.
No new image dependency, local build or old APK rebuild was needed.

Product source remains on the clean development branch, pending main integration.
The board and this note remain local uncommitted main edits. Original-signed
APK/EXE delivery, installation, real post-reboot startup time and desktop-icon
persistence remain NOT_RUN, pending the owner's build/install/reboot decision.
No Activity/service start, boot broadcast, installation, phone reboot, App/launcher
data clearing, MCU operation or channel publication occurred in this repair.
The selected-output inventory/closure audit is `write-audit-01.json` in the task
evidence root. The inherited PowerShell-cache timestamp observation remains
attribution-unresolved; no cleanup or whole-OS zero-write claim is made.

### Reconnected Device Metadata Follow-Up

The owner additionally reported that automatic reconnection after an MCU/phone
restart works, including updates, while the device name becomes unknown and
details incorrectly claim that the device only broadcasts. No new physical
experiment is needed to reproduce the source-level display contradiction.

METADATA-01: `BleController.isConnectable` treated a missing scan result as
`false`. Direct address-based reconnection does not require a scan, so this is
not evidence of an unsupported device. Name lookup also depended exclusively on
this process's advertisement/platform-name caches. Both detail pages captured
some display values outside reactive observers.

The repair on `dev/flutter/app-boot-icon-20261119` adds bounded, local-only
connected-device name history. It retains at most 64 previously connected
identities, normalizes address lookup and merges delayed restoration without
overwriting a newer name or erasing an older name on a nameless reconnect.
Android's existing `FlutterBluePlus.systemDevices([])` query hydrates names only
for this App's already-connected addresses. It does not scan, connect, discover
services or adopt another App's connections. The locked 1.35.5 API was checked
against the official package archive and lockfile SHA-256 in `metadata-api-01`.
Storage/native waits are bounded; metadata is never live GATT/OTA authority.

Display connectability now prefers the current App connection, then an explicit
advertisement flag, then a prior successful connection; otherwise it is unknown.
Unknown is not described as broadcast-only. Both real detail pages and the two
device-card widgets observe metadata changes without replacing the device handle.

First metadata source `c66fb9ff64ef7e0a53be9783ca38fdaaa943b381` failed run
`44402690231/1`: Windows 880 passed/63 skipped/1 failed; Linux 923 passed/16
skipped/5 failed. The new test file could not load because `Get.reset()` returns
void. Analyzer also found a protected `RxMap.value` access and a super-parameter
lint. The Linux originals additionally exposed four existing OTA-test timeouts:
an unavailable native `platformName` read escaped the new metadata refresh and
made a successful reconnect return false. These are retained failures, not PASS
or an unexplained flaky run. Original consoles are `keyring-logs-06`; the Linux
archive `keyring-artifacts-04` has artifact ID `14472688593`, 304270 bytes and
verified SHA-256 `da674fe659b918391c997ecd0fa00c1228f24c20d497605b2c854821792e429c`.

Source `53213d5ba2f8945667023fe09da28eea0669f850` fixes those three static issues
and isolates optional platform-name lookup failure from connection results. A
new regression drives the real companion connection while native metadata fails;
the existing OTA tests are unchanged. Fourteen new unit/widget scenarios cover
persistence, races, capacity/corruption, storage/native failure, truthful
connectability, address matching, foreign-connection exclusion, late completion,
real companion connection and reactive real UI paths.

Run `44404940589/1` passed analysis and the prior OTA regressions on both hosts.
Linux recorded 940 passed/16 skipped/1 failed and Windows 891 passed/65 skipped/
1 failed. The only remaining failure was widget-test teardown: the real detail
page's existing `flutter_animate` delayed entry timers had not fired yet.
All name/capability assertions executed; `pumpAndSettle` alone can stop while a
future animation delay has no scheduled frame. `keyring-logs-09` and
`keyring-artifacts-05` preserve the originals. No production animation or assertion
was removed. Source `ab0ef2c589a07b04776e3483c7bf9b7af9407efd` changes only the
test wait: first build the changed tree, advance beyond the existing entry delay,
then settle its actual frames. Full/native debug run
[44406058730](https://github.com/Eitan-S-23/E-Track/actions/runs/44406058730)
completed successfully on both hosts. Linux passed 941 tests with 16 platform
skips; Windows passed 892 with 65 skips. Both passed analysis and eight candidate
tests. The two new mobile-only connection cases are skipped only on Windows.
The compiled native JUnit reports pass 57 CompanionIntegration, 9 CompanionService
and 18 DeviceOtaService tests: 84/84, zero skips/errors/failures. SDK identity is
unchanged from the earlier successful boot/icon run (Flutter 3.47.9, Dart 3.13.7).

Final original consoles are `keyring-logs-12`. Linux archive
`keyring-artifacts-06`, artifact `14476106317`, is 343922 bytes with verified
SHA-256 `4345bd4f1d82ace507743a283626bd1226cfa1e5b4619c7c88242c4bcee6b203`.
The debug archive `keyring-apk-02`, artifact `14476491083`, is 76248267 bytes,
SHA-256 `8640c35cae0f7db9e1640b47b871eb157d2e6e641fb949ad5240b903a7759e11`.
Its extracted APK is 132544296 bytes, SHA-256
`74bd8b90071b054dc4cf0517d2e78799ffe4d1c6b7d105d5de12c1aeb5b1460a`, package
`com.wen.gaia.gaia.bootcheck`, fixed development signing, not original release
signing. Archive digests match GitHub, and the extracted APK matches its CI
metadata. The actual extraction path is retained in `keyring-apk-02/apk-paths.json`.
No local Flutter/Gradle build, installation or replacement of the normal App ran.
Android inputs are byte-unchanged from `4d82427c`; earlier compiled-icon/artwork
checks are reused alongside this run's actual compiled-resource native tests.

Cross-layer lesson: absent discovery metadata is not negative capability, and
display-history retrieval must not be on the transport success/failure path.
Regression coverage exercises the real connection plus both real detail pages,
not only a standalone formatter. The earlier boot/icon source and green evidence
remain intact. Main integration, original-signed APK/EXE, installation and real
post-restart display verification remain pending. This follow-up performs no
phone launch, installation, reboot, boot broadcast, MCU operation or publication.
The selected-output/source/CI/APK audit is `write-audit-02.json` under the same
evidence root. Main board and this note remain local pending records, not a
mainline commit or a whole-card independent acceptance claim.

## Check Update Release 3.3.34, 2026-11-19

The owner explicitly requested a new MCU firmware version, delta-compatible
with the currently installed image, to test the MCU Check Update function.
This authorizes bounded source commits/push, original-Admin candidate/delta
delivery and publication on the current App's MCU Stable channel. It does not
authorize a phone update, Boot programming, OTA installation on the device,
unrelated channel/configuration changes or bypassing protected production gates.

Entry inspection confirms original MCU Stable 3.3.30 (revision 7), Beta 3.3.26
(revision 10), no registered 3.3.33 and 40 retained delta jobs. The current App
uses Stable. Retain App channels, Beta and every earlier artifact/job. Source
anchor `53ebe07e78430d541a24f87c40e84adbbd33b126` contains the bounded 20-file
repair/test/record change already installed locally; it is not a new CI build.

The base is the exact installed 630100-byte 3.3.33 image, SHA-256
`19ba4b030c567cee6e1a2b1dc7b24ba216049ed6d6b843adc3bdceb5205ff3fd`.
Recompiling the same version would not establish matching bytes. The high-level
CI preparer requires a numeric Actions run, while this image has an existing
local GCC build and complete device readback. The smallest adapter therefore
reuses `etu_pack.py`, `etu_unpack.py`, the native byte/recovery verifiers and
`buildFirmwareMetadata` without recompiling or re-finalizing the base. Its
registration run ID is explicitly `local-gcc-companion-reconnect-20261119-build-02`,
not an invented GitHub run. The ordinary schema, immutable S3 uploader,
preflight, verified R2 readback and registration module remain unchanged.

Base packaging and byte-equal reconstruction pass. Register it without channel
publication before creating the higher target, preserving the monotonic catalog.
Then push target version 3.3.34 through the normal main Actions entry, use the
existing operator-selected MCU delta workflow for this exact base, verify exact
reconstruction/R2 bytes, enable that patch and publish only MCU Stable. Stop
before claiming success if the actual Public latest query does not select the
30333/base-SHA patch. No device installation is part of this delivery.

Evidence root: `.cache/firmware-check-update-release-20261119/`. Publication was
pending at this checkpoint. The source-matched release checks comprise 138
passing cases: 136 original passes in `keyring-check-02` and the two actual
original-Admin packaging cases in `keyring-check-03`. Earlier failed host
receipts are retained: the first wrapper omitted process-local Git ownership
configuration, and the remaining two native entries found the WindowsApps
`python3` alias. Selecting installed `python` repairs the host invocation,
without changing product tests, relaxing assertions or modifying global Git.
The first read adapter's HEAD/null-body failure is likewise retained separately.

### Published And Byte-Verified

MCU **3.3.34 is published on the original Stable channel**, revision 8.
Source `c85b39c65594c6683b163454f071f805273a65c5` is delivered on main, together
with the preceding repair-source anchor `53ebe07e`. Candidate Actions
[44369848861](https://github.com/Eitan-S-23/E-Track/actions/runs/44369848861)
passes checks, fresh keyed GCC App/Boot compilation, native package verification,
private-header cleanup, R2 readback and registration. App packaging is skipped.
Governance run `44369848829` also passes. The GCC evidence reports **641 warning
lines, zero error lines**; configure and size have zero warnings/errors.

| Delivered Item | Exact Identity |
| --- | --- |
| Target release | `fw_c2f51d02fa5398f4f432607a6fefc2f401a9e9e50c53ea842dcbe9083b7d06f0`, 3.3.34 / 30334 |
| Target raw App | 630176 bytes, SHA-256 `06554819f0b140a3aeb64ec7fe253df697659dd6fcaa72d3c22f0d76fb6330b9` |
| Full ETU | 301051 bytes, SHA-256 `271ef96a93fe04ebd3212f9ce01dfe0f93183155737e5e7b86122c3ae11c078b` |
| 3.3.33-to-3.3.34 patch | 8066 bytes, SHA-256 `c6b42b8ec64b3391ba3f65d0de467abdaad5bebe78bc3ba943a14339fa4bec3e`; 97.32% smaller than full |
| Original installed base registration | `fw_b5be874cc7279e41cbfd18ecbdd799a239318ae7884005a0383788ab1bacb6ad`; exact installed raw SHA remains unchanged; unpublished |
| New delta job | `delta_d34dd9d1b9e6b5af2446808328b549854a0f8504ce23175b96202f4d9b32388d`, attempt 1, ready/enabled, revision 4 |
| Delta Actions | [44372037247](https://github.com/Eitan-S-23/E-Track/actions/runs/44372037247), exact existing generator `3135a06e92a9165158cac49abdb789732fcd6842` |

`keyring-verify-01/result.json` verifies the actual R2 full and patch bytes,
decrypts/applies them with the original key and installed base, and requires
byte-equal target reconstruction. Both native outer/inner checks pass. The
finalized target also matches the exact archived CI GCC placeholder outside its
finalized firmware header; a tag/version string alone is not the source oracle.
Artifact `14458613310` is retained in `keyring-artifacts-01`: the 982676-byte
ZIP matches GitHub digest
`e6aee7e98ae1ef08e503022059363a54c5a976061a29a593d2e1aa7e1abc8a31`.
Its nine originals include the matching ELF/map and source/key/registration
proofs. Complete candidate job logs are in `keyring-logs-01`.

`keyring-enable-02` enables only this verified patch. `keyring-publish-02`
advances only MCU Stable, using its original revision 7 as the CAS precondition.
`keyring-public-02/result.json` then executes the real Public Pages route:

- Current 30333 and the installed raw SHA select the new 30334 **patch**. Its
  signed download returns HTTP 200, correct ETU content type and exact bytes/hash.
- A nonmatching base SHA selects the full package; that signed download also
  returns HTTP 200 with the exact verified bytes/hash.
- Current 30334 and its actual target SHA return NO_UPDATE.
- Both App channel rows and MCU Beta remain unchanged. All 40 previous delta
  rows are identical; only the new job is added, 41 total.

No phone install, MCU reset/flash, OTA transfer, Boot programming, backend
redeployment or credential/configuration change was performed for this release.
The last device-verified input remains 3.3.33; publication is not an assertion
that the device has installed 3.3.34. The owner can now keep the original App
connected in the background and select MCU Check Update. Actual positive device
interaction/installation and independent D0-D5/C1-C6 adjudication remain separate.

The first S3 adapter's Fetch/proxy request failed. A read-only native-SDK HEAD
confirmed the object was absent, then the same credential and immutable files
uploaded/read back successfully through the standard SDK transport. The exact
earlier transport cause was not established. An enable read failed before any
mutation; its successor enabled the same job once. The first publication POST
returned 400 because the adapter omitted `Accept: application/json`; the server
rejected it before business mutation. The corrected request preserved all other
headers, CSRF/role checks and the original CAS revision. `keyring-public-01`
stopped locally for lack of a successful publication receipt, with no HTTP call.
All failures are retained; no successful build or delta was regenerated.

The final local audit is `final-write-audit.json` in this release evidence root.
Selected source/Git/cache/test/archive/log outputs remain project-contained.
Compared with the preceding repair audit, the existing 1004-byte file
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
has mtimeNs `1795027991791634000`, previously `1795023492761699400`.
Local selected commands did not invoke PowerShell; attribution/content changes
remain unconfirmed. No external cleanup/restoration was attempted. ADB key,
SEGGER history and the other monitored PowerShell-cache metadata are unchanged.
This is a scoped comparison, not a whole-operating-system no-write claim.

## Coupled Bluetooth Startup Repair, 2026-11-19

The owner selected MCU-startup Bluetooth-module reset as the preferred repair,
with App retry changes only where the actual restart observation requires them.
`Doc/ble.pdf` identifies XY-MBO35A and documents `AT+UART?` and `AT+REBOOT=1`
with `OK` / `+READY` responses (PDF pages 11 and 13). `AT+RESET=1` is factory
reset and is explicitly excluded. The PCB netlist connects U13 pin 4 / RST to
3V3_MCU, not a controllable MCU reset output; the old commented PA15 enable
definition must not be enabled. No UART rate, advertising or persistent module
setting will be changed to make this test work.

Root is the sole operator in `D:/github/my/E-Track`. The finite repair matrix is:
one connected-state UART query; one module-only software reset if that query
establishes the live control route; source/host regression and GCC verification
of a bounded startup reset if the probe succeeds; then the minimum paired
background reconnection observations on the repaired firmware. Additional App
changes use the existing development CI route, not local Flutter/Gradle builds.
No protocol extension is the default while the simpler module route is viable.

At entry, the installed input was the fully verified 3.3.31 App and original Boot.
Before debugger calls, recheck image, running health, confirmed state and idle
BLE/storage ownership. Reuse the proven standard SEGGER/GDB method at HAL_Update,
temporarily pause the watchdog only while halted, call the existing serial writer
with a small LVGL allocation, retain original replies and release the allocation,
debugger and watchdog setting. Never reset the MCU merely to recover a failed
collector. J-Link programming, if needed for the repair, remains App-only with
full readback/Boot checks and a new firmware version, not overwritten 3.3.31 bytes.
ADB observes the original App without installation, launch, UI taps or settings
changes. Evidence is `.cache/companion-reconnect-20261119/`; all controllable
outputs stay inside the project. The standing SEGGER native-history exception
is unchanged. No commit/push, candidate publication or independent PASS is implied.

The first connected-state UART query completed its exact ten-byte write, but
GDB halted between the serial write and the separate wait call. Its retained
ring contains only `+`, with one new hardware overrun event (flag 8), so this is
an invalid response capture, not evidence that online AT is unsupported. The
MCU resumed fault-free, UART divisor 156 unchanged, phone still backgrounded and
connected; no module/MCU reset or Flash write occurred. Preserve `probe-query-01`.
The bounded follow-up `probe-query-02` uses a 32-byte-or-smaller RAM call adapter
around the same installed serial writer and one-second wait, with no intervening
debugger halt. This is not a new UART driver or production AT console. The
allocation is freed, register/fault/receive-error checks and debugger cleanup
remain required. A successful module reset is followed by a separate UART query
to establish retained baud before firmware implementation.

Online results are now retained: `probe-query-02` received `+UART:8`,
`probe-reboot-01` received the complete `OK` / `+READY`, and
`probe-after-query-01` confirmed the same 921600 module rate and MCU divisor 156.
No rate/factory/configuration command was issued. Android observed a real
disconnect/reconnect while the original App remained backgrounded. However,
the subsequent MCU counters restarted; `observe-reset-01` retains `Reset: NRST
WDT`. Thus this cell proves module control, not successful end-to-end companion
recovery, and does not establish an App-only defect. No MCU reset command was
requested in that cell. Further observations must keep uninterrupted MCU uptime
and the actual companion session, not just OS connection, as the success oracle.

The first firmware candidate 3.3.32 adds a single startup reset with a finite
response wait and retains RX bytes after READY. Fifteen policy tests pass; the
standard GCC App/Boot/simulator build passes with 447 historical warnings and
zero errors (`build-01/artifacts`). Full App/Boot readbacks and health/storage
admission pass for App-only `install-01`. The initial validator lacked an
explicit installed Python dependency path; its failure is preserved and the
same original readback was validated offline, not recaptured to hide the error.
`observe-01` shows stable health but `BTSTART: reset=2 elapsed=1000`, no UART RX
bytes and no companion session. This is an unsuccessful startup repair, not a
completed fix. `probe-late-init-01` diagnostically admits one repeat of the same
initializer after startup and also times out; `probe-query-03` still receives a
valid UART query through the previously qualified contiguous Print writer.
Do not attribute the difference solely to early startup or extend delays blindly.
The next version, 3.3.33, sends the command through that same complete-buffer
writer instead of interleaving per-byte clock/ready checks. The same fifteen host
cases pass. The subsequent successful device observations are recorded below.

Additional host regressions in `regression-01`: control 24, safety 18, BLE
contract 9 and candidate workflow 56 PASS. Node 24 emitted its human-readable
`tests 56` summary; the wrapper's zero count is an unrecognized-format metadata
field, not zero executed tests. Original stdout is retained. The install
adapter's old `ClrBP 0` did not match the returned native breakpoint handle 1;
the subsequent reset/readback has all FPB comparator registers clear, and the
adapter now clears the actual first handle. No foreign debugger was stopped.

### Verified Startup And Background Recovery

RECONNECT-01's MCU-startup repair is implemented and installed as 3.3.33.
`build-02/artifacts/result.json` records the standard GCC App/Boot/simulator
build, original-key verification and private-header removal. It has 447 warning
lines and zero errors; normalized comparison with the preceding UI-repair build
found no new distinct warning messages. The installed `app-final.bin` is 630100
bytes, SHA-256 `19ba4b030c567cee6e1a2b1dc7b24ba216049ed6d6b843adc3bdceb5205ff3fd`.
The matching ELF/map are retained under `build-02/artifacts/app-gcc/`.
`install-02/native/result.json` verifies every App byte and the unchanged physical
65536-byte Boot, SHA-256
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
Building a matching Boot did not program it.

| Original Device Observation | Executed Result |
| --- | --- |
| `observe-02/native/result.json` | Initial startup reset Ready in 129 ms; actual companion session established, CONNECTED, advancing tick/main-loop/watchdog counters and clear fault registers. |
| `restart-01/native/result.json` | Ordinary MCU software reset; module Ready in 128 ms, initially PHONE_REQUIRED with no session, then CONNECTED with a session. Nine samples over approximately 40 seconds remain healthy with no additional restart. |
| `restart-02/native/result.json` | Second ordinary MCU reset; Ready in 129 ms, the same empty-to-established session transition and approximately 40-second healthy observation. |
| `check-01/native/result.json` | Existing MCU Check Update function queued onto the normal LVGL loop; actual phone reply NO_UPDATE, request 0 -> 1, checking=false, session retained, sameBoot=true, unchanged UART and clear faults. |

The original phone App 1.0.82/108 remained in the background with its real
CompanionService; retained Android observations show disconnect/reconnect and
the actual GET_INFO/HELLO exchange. No App launch, UI tap, installation, setting
change or synthetic protocol reply was used. The final two reset cells do not
reproduce the preliminary `probe-reboot-01` watchdog restart; that earlier
restart's cause remains unconfirmed rather than being erased by the final PASS.
Likewise, no logic-analyzer trace establishes the precise electrical/inter-byte
cause of the rejected 3.3.32 writer. Its timeout and the failed collectors remain
original evidence, not successful runs.

The product resets XY-MBO35A only once per MCU startup, with the existing
complete-buffer writer and exact `AT+REBOOT=1\r\n`, a bounded TX-ready wait and
at most 1000 ms response wait. It requires complete OK/+READY lines, discards
stale pre-command RX and stops reading at READY so new-link bytes reach the
normal demultiplexer. It never calls the RX-clearing `HardwareSerial::flush`,
changes persistent module settings or schedules periodic resets. Experimental
baud builds retain their existing AT gate. No App-side repair was necessary for
this observed restart failure; broader process-death/radio coverage is not
claimed by these two tests.

Relevant development checks total 122: startup policy/wiring 15, companion
control 24, safety 18, BLE contract 9 and candidate workflow 56. The final
test-only wiring assertion requires the qualified complete-buffer HAL writer;
`closeout-checks-01/startup.log` retains its 15-test rerun, with no product change
or repeat build/flash. Other originals remain in `regression-01`, including the
Node summary/count discrepancy described above.

### Repair Closeout And Write Audit

Source and records remain LOCAL_PENDING on primary main `74fa4bcb`; no commit,
push, Actions dispatch, Cloudflare candidate registration, channel publication
or OTA transfer occurred. Earlier UI/menu/font repairs remain intact. This is
the bounded repair's implementation/device result, not D0-D5, C1-C6 or whole-card
independent acceptance. No further physical replay is needed merely to document
these results. Remote delivery is a separate owner-authorized step.

`closeout-01.json` records actual source/evidence hashes, selected output paths,
final main freshness and process/port/lock checks. All agent-selected build,
test, log, temporary, helper and documentation outputs are project-local.
J-Link/ADB/GDB processes and ports 5048/23485/23486/23487 are closed; the device
lock and both temporary private-key headers are absent. No external cleanup,
overwrite or restoration was performed.

The separately monitored existing file
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
remained 1004 bytes, but its mtimeNs changed from `1795018093789849500` to
`1795022591045326600` during the repair. The selected commands did not invoke
PowerShell; limited checks of the relevant build entries found no such call.
Writer/content attribution remains UNCONFIRMED and was disclosed to the owner.
The original ADB key, SEGGER JLinkDLL.ini and the other monitored PowerShell
cache retained their recorded metadata. These scoped checks do not establish
that the whole operating system was unchanged; no cleanup is authorized.

## Background Reconnection Diagnosis, 2026-11-18

RECONNECT-01: required session-recovery fix, not a new permission request.
The user connected the phone by USB to diagnose the missing background recovery.
This round made read-only phone queries and a non-halting J-Link observation of
the already-authorized board. No App launch, UI tap, setting change, install,
explicit halt/reset, Flash write, OTA, CI or release was performed.

- Phone snapshots at 23:20 and 23:31 Asia/Shanghai: V2312A / Android 13,
  original signed App 1.0.82 / 108, PID 5121 unchanged. Installed APK SHA-256 is
  `8567bf5b93294b7df46247ba7bf23a8eb8b1d64128731ae6ae017b1acc441a65`, matching
  the existing release receipt. Bluetooth scan/connect and notification grants
  are present. `CompanionService` is a foreground service, the system association
  has presence observation enabled, and Android lists that associated MCU among
  connected Bluetooth devices. This is not merely an App in the recent-task list.
- Between those phone reads, J-Link verifies the entire installed 629,732-byte
  App against the retained 3.3.31 image and matching ELF layout. MCU main-loop
  counters advance, the core is running and fault registers are clear. The actual
  companion control has `status=PHONE_REQUIRED`, an empty session, no offer and
  no pending check. `lastRxTick` is zero; this is an idle UART receive marker,
  not proof about every ISR-handled binary packet. No debugger reset fallback
  occurred. The OS-level connection and MCU-level session are demonstrably not
  equivalent in this observation.
- `CompanionRuntime._wake` sends `HELLO` only inside its new-link branch.
  `_sameLink` uses the phone's link generation and cached identity; the native
  heartbeat probes the Dart runtime, not MCU session liveness. MCU `Control`
  starts with an empty session, accepts it through `HELLO`, and cannot send
  `CHECK` until that happens. There is no independent idle session-recovery
  mechanism for a restarted MCU behind a surviving BLE module connection.
- Android also records an App process reclamation at 23:13:18, reason
  `LOW_MEMORY`, description `single-cleaner`. The current process/service has
  already recovered. Do not attribute the original report solely to this event:
  the original MCU reboot/connection timeline was not captured. Production
  `run-as` correctly denies private preferences, the filtered App log is empty,
  and the vendor Bluetooth-manager dump is empty; none is a successful protocol
  trace or proof of a specific lost callback.

Root should next repair bounded peer/session liveness and fresh identity/session
establishment independently of GATT disconnect, including the initial handshake
timeout case. Preserve OTA exclusivity, fresh-session/replay protection, offer
identity and explicit user installation consent. The minimum regression cases
are MCU-only restart with retained GATT, real radio disconnect/reappearance, and
background service/process recovery; do not replace the release App or replay
an OTA merely to collect missing historical logs. This is a diagnosis, not a
completed repair or D0-D5/whole-card acceptance.

Originals and adapters are under `.cache/companion-reconnect-20261118/`:
`phone-01`, `mcu-01`, `phone-02`, and `closeout.json`. The standard ADB/J-Link
tools, existing owned-process helper and contained WMI launcher were reused.
Private ADB port and all owned native processes closed; the original ADB key
is unchanged. Controllable outputs remain under the project; automatic
`C:/Users/SU/AppData/Roaming/SEGGER/JLinkDLL.ini` updates use the standing exception.
The separately watched file
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
remains 1,004 bytes but its mtime changed from `2026-11-18T15:08:10.940Z` to
`2026-11-18T15:23:10.662Z`. No selected command invoked PowerShell, its writer
and content changes remain unconfirmed, and no cleanup/restoration was attempted.
Preserve it unless a separately scoped attribution/cleanup is requested.
The existing MCU repair and these additional records remain LOCAL_PENDING on
primary main `74fa4bcb`; no product source was changed by this diagnosis.

## Check Update UI And Frozen Device, 2026-11-18

Owner request: use the four-character Chinese Check Update label as a separate
MCU menu action, replace the rudimentary companion modal with the existing MCU
visual language, and fix the observed freeze after leaving it. The user reports
the board is currently frozen and explicitly supplies the connected J-Link.
Active write root is primary `D:/github/my/E-Track`, starting at `74fa4bcb`.
This is local development/device debugging, not a new GitHub push, channel
publication or independent whole-card acceptance authorization.

Finite development matrix:

- Preserve the current fault first with one standard J-Link halt/register/RAM/
  internal-Flash capture, then resume without reset. Root is the sole operator;
  no competing debugger/RTT process was present at entry. Decode only against
  the matching original ELF after checking the running App header and bytes.
- Diagnose the modal/input-group/page lifecycle and reproduce its failure with
  actual LVGL host code. Cover touch and encoder exit, repeated open/close,
  navigation after close, unavailable phone and ready/deferred update states.
- Use the existing dark/cyan surfaces, Chinese/number fonts, separators and
  focused controls. One clear title, a short status body and clear actions;
  restrained focus/entrance transitions only, no separate UI theme.
- Validate code/font coverage and build the production GCC App plus matching
  Boot and simulator through the supported contained build route. Keep the
  historical 3.3.30 package and original evidence unchanged.
- Before any candidate programming, verify App/Boot identity, BCB/pending
  transition/staging state and complete recovery inputs. Program only admitted
  App bounds with standard J-Link, preserve Boot and persistent records, and
  verify readback and running health. No mass erase or arbitrary BCB edits.
- On the repaired target, check the independent menu entry, readable Chinese
  status/actions, repeated exit/re-entry and continued navigation/heartbeat.
  Stop dependent mutations if identity, persistent state or recovery is unclear.

Each native helper has a finite deadline and original receipts under
`.cache/mcu-check-update-20261118/`; initial capture is bounded to 120 seconds.
Only the standing SEGGER native-history exception applies outside the project:
`C:/Users/SU/AppData/Roaming/SEGGER/`. Run native J-Link as the existing SU owner,
contain command/log/temp/readback paths, and audit that exception without cleanup.
Initial register capture establishes a 3.3.30 HardFault (CFSR 0x8200,
BFAR 0x19191935); originals are `capture-03/`. The generic CORTEX-M4 route works
after the device-specific connect failed and the vendor tried its reset fallback.
The slow halted RAM read did not preserve a stable original stack: later RAM and
`backup-01` registers show normal execution, consistent with watchdog recovery.
Do not attribute a precise faulting instruction from that mixed-time RAM image.
`backup-01` contains a complete 1 MiB Flash read, but eight zero bytes in the
libc code differ from original 3.3.30; a fresh non-halting inspection must reconcile
that read before it can be used as a recovery image. No firmware has been written.

The source defect is independently reproducible with the bundled LVGL: button
creation joins the default group, and this version's `lv_group_add_obj` does not
unlink the old group. Closing the companion modal leaves stale page-list entries.
The repaired controls explicitly leave the default group, and close resets the
input transaction while restoring each input's focus/editing state. The main-menu
entry is separate and visible in the first six rows; the file-browser shortcut is
removed. Existing Chinese subset generation supplies all new labels.

Development results: real LVGL nine tests PASS, including the original red oracle,
100 open/close/navigation cycles, two distinct input groups plus an ungrouped input,
expired/replaced press protection, deleted focus, Escape, async duplicates and
five rendered states. Original control 24 and safety 18 tests PASS. Evidence is
under `.cache/companion-modal-tests/run-23rs_r6u`, `.cache/companion-control-tests/run-2ifinz_n`
and `.cache/companion-safety-tests/run-i1f2g4_e`; the first harness's temporary
input-driver lifetime error and missing-glyph failures are retained separately.
No native crash dumps were created by that failed harness. The composite preview
is `.cache/mcu-check-update-20261118/ui-preview.png`.

The local version is now 3.3.31, not an overwrite of 3.3.30. The supported default
App/Boot/simulator batch is being run with the existing original firmware key;
this local wrapper reuses the official key-header primitive without pretending to
be a GitHub release run. It removes its private header and restores the local
compiler flags after preserving artifacts. All build/test outputs remain inside
the primary root, including the existing `.cache/companion-*-tests`, production
CMake output and `Simulator/Output`. Build, native installation and live UI checks
remain pending; no push, backend registration or channel publication is implied.

The supported batch now passes (GCC 641 warning lines, MSBuild 102 warning lines,
zero errors; no diagnostics in the changed UI/font files). App size is 629,732
bytes. `inspect-02` independently verifies the original App header/image SHA and
exact original executable, resolving the earlier eight-zero-byte read error;
its Boot backup matches the first Flash capture. Current BCB snapshot is confirmed
state 4, staging is the already-consumed 30330, and storage/BLE owners are idle.
The standard AT32F435RGT7/1000 kHz route succeeds from this running state.
`prepare-01` halts at HAL_Update with idle SDIO and watchdog debug pause; `install-01`
programs only App, deliberately restarts, and verifies every candidate App byte,
unchanged Boot and clear fault registers. `health-01` observes live confirmed
30331, healthy SD and advancing main-loop/watchdog counters after restart.

Remaining native UI matrix: use the installed SEGGER GDB Server and exact ELF to
call existing menu/event methods only at the HAL main-loop boundary; no debug
firmware, Flash download, phone check or install choice is required. Run ten
main-menu and ten original file-page modal close/navigation cycles, then return
to the menu, close owned debugger processes, restore the watchdog debug register
and read back final image/health. This supplements, not replaces, the actual-LVGL
host regressions and is not a claim of physical touch/rotary or D0-D5 acceptance.

### Local Repair Complete

The local repair and authorized installation are complete. Final checks in
`.cache/mcu-check-update-20261118/checks-01/` pass all 52 control/safety/menu/real-LVGL
tests, 81 automatic-candidate tests and actionlint. The real-LVGL suite retains the
original failing ownership oracle and 100 repaired close/navigation cycles; five
Chinese rendered states were inspected. The main-menu item retains action-keyed
button storage, so inserting it on the first screen does not renumber existing
actions. The menu and dialog both use the requested four-character label.

Native `gdb-ui-01` executes ten main-menu and ten file-page modal cycles on the
installed production-configuration image. Each closes through the real button
event and asynchronous cleanup, restores the original group count/focus and
traverses that group without HardFault. This uses debugger-driven native UI, not
a claim of 20 physical taps. The GDB attach emitted one initial MSP-alias warning;
native calls were admitted only after the exact HAL_Update breakpoint and register
refresh. The final readback independently checks the resulting device state.

`final-01` and `final-verification.json` confirm every App byte is still the
3.3.31 candidate after debugging, Boot remains identical, confirmed state is 4,
the modal is closed, SD is healthy, owners are idle, fault registers are clear,
watchdog/main-loop counters advance and the debugger pause register is restored.
No J-Link/GDB processes remain. The App is 629,732 bytes; GCC App/Boot and simulator
builds passed with 641 GCC plus 102 MSBuild warning lines and zero errors. Changed
UI/font files emitted no diagnostics; the broader existing warnings are not waived.

Source, version metadata, CI regression entry and these records remain uncommitted
on primary main, based on `74fa4bcb`. No remote push, new Actions run, Cloudflare
registration, channel publication, App package or OTA transfer was performed.
The earlier candidate/main migration and D0-D5/whole-card obligations are unchanged.

### Bug Analysis: Modal Focus Ownership

1. Root cause: an implicit ownership assumption plus a coverage gap. This bundled
   LVGL auto-adds buttons to its default group but does not unlink that group when
   adding them elsewhere. The old modal freed controls still referenced by the page.
2. Validation correction: simplified safety stubs never modeled default-group
   insertion. The first new host harness also used a temporary input-driver object;
   LVGL retains that pointer. Static driver storage fixes the harness without
   changing product behavior, and its failed originals are retained.
3. Prevention: explicitly detach modal controls, restore each real input transaction,
   retain a genuine old-code failure and run the real-LVGL regression in candidate CI.
4. Expansion: inspected the other page group users. They reuse the default group;
   the companion modal is the separate transient group. Do not replace the vendor
   library globally or confuse this local repair with an independent OTA campaign.
5. Knowledge capture: this existing component record, adjacent ownership comment
   and executable test are the project-local references. Trellis is absent; no
   parallel task/spec hierarchy or unauthorized documentation commit was created.

### Write Audit

Controllable tools, fonts, sources, tests, images, logs and temporary/build outputs
were preflighted inside `D:/github/my/E-Track`. The generated private key header
was removed after the build; registered key inputs were not changed. Only owned
test temporary directories and that generated header were deleted. Existing
untracked work, failed captures and prior worktrees were preserved.

The authorized native history update remains under
`C:/Users/SU/AppData/Roaming/SEGGER/`. SU CrashDumps metadata is unchanged from
2026-11-17 and the SYSTEM CrashDumps directory remains absent. However the final
audit observes a changed modification time, `2026-11-18T14:23:26.443Z`, on
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
(1004 bytes). Its writer is unconfirmed: selected commands used cmd/Python/Node
and native tools, and the reused WMI launch function contains no PowerShell call.
This is not claimed as a zero-external-write session. The user was informed; no
cleanup, overwrite or restoration of that cache was performed or authorized.
The separate Microsoft/PowerShell cache remains at its previous 2026-11-11 mtime.
Detailed output inventory and final references are in
`.cache/mcu-check-update-20261118/write-audit.json`.

## MCU Main Migration, 2026-11-18

The owner requested main-based MCU development and automatic candidate delivery.
Source/workflow integration `0b7e1275f91f0c6c0a2f89e19f664d60d5ffee9e` is now on
local and remote main. This bounded 67-file change imports the already delivered
3.3.30 MCU/paired-simulator source and necessary tooling/tests, not the candidate
branch's unrelated experiment history or old deployment/governance workflows.
All ten MCU/simulator input directory trees match `cb360b76`; the App tree remains
`b8be80cfd70dc9d05e4905821b4aae81dd8a1fa8` (`1.0.82+108`). The existing
3.3.30 native build/registration remains Actions `44276457821`, not a new build.

`Original Admin Candidates` now routes main pushes to firmware only and
`release/candidates` pushes to App only. Exact source, first-attempt admission,
mandatory version increments, V2 profile, private-key cleanup and unpublished
full/recovery registration remain enforced. Main no longer starts the duplicate
build-only firmware push workflow; pull-request/master and protected manual
routes retain their gates. Future MCU work starts from current main, updates
`Tools/ota/original-admin-release.json`, and is integrated to main before the
final push. The original Trace signing route is unchanged.

The six-file App routing update is
`1564d5886bf248c83b87afa9c991ab5404a6f73b`, with no product/version changes.
Actual push run [44295658568](https://github.com/Eitan-S-23/E-Track/actions/runs/44295658568)
passes checks and skips both builds. Existing environment `firmware-candidates`
now permits only main, with no required reviewer/wait timer. Readbacks confirm
unchanged Secrets, `OTA_BOOT_CHAIN_READY=false`, repository Secret metadata and
both protected rehearsal/production environments. No Cloudflare credential was
read/exported, no key rotated, and no channel or device operation was performed.

Local checks pass: 229 Node tests, eight original-App boundary tests, 43 MCU
control/safety/encoder tests, nine BLE contracts, 11 link-metrics tests, real
host frame/session/staging/package/patch suites, and actionlint for both workflows.
The planner regressions execute actual temporary Git checkouts: main requires
no historical App-branch ancestry, versioned firmware schedules only firmware,
source edits without a new version fail, and documentation never rebuilds 3.3.30.
Packaging tests use synthetic non-installable inputs, not a native firmware build.

The source/baseline commit deliberately uses `[skip ci]` because the old main
did not contain the versioned release configuration. This recording-only follow-up
does not skip CI: its actual before-SHA now has 3.3.30 and must select no package.
The follow-up is `84a41a613e5a2ef314fa3c90f44e96a33efe79ac`. Actual main push
[44299234275](https://github.com/Eitan-S-23/E-Track/actions/runs/44299234275)
passes checks and skips both build jobs; its original log confirms `branch=main`,
`firmware.required=false`, `app.required=false` and no channel publication.
Governance run [44299234383](https://github.com/Eitan-S-23/E-Track/actions/runs/44299234383)
also passes on that exact source. The source/baseline commit has no Actions runs,
and the old duplicate firmware workflow did not start on the follow-up.
No permanent bootstrap exception was added to the planner. The next real firmware
version must be greater than 3.3.30; this migration does not replay that release.

Original receipts are under `.cache/firmware-main-migration-20261118/`:
`import-before.json`, `import-after.json`, `check-03/`, `keyring-app-01/`,
`keyring-policy-02/`, `keyring-main-02/`, `keyring-followup-02/`,
`keyring-verify-04/` and `keyring-logs-01/02/`.
The initial local test, unsupported policy-update field (HTTP 422) and imported
fixture-whitespace check failures are retained, not relabeled as successes.
The corrected policy update changed only its name, not its type or Secrets.
The main board's mixed line endings were preserved; only the edited lines were
returned to their original LF convention. Final verification records are a
documentation-only `[skip ci]` commit, not another build or workflow replay.

Firmware product main integration is no longer outstanding. D0-D5 and formal
whole-card acceptance remain outstanding; C1-C6 remain unchecked. This delivery
does not extend the independent R01-R05/T01/T02 source-review conclusions or
replace their original evidence. Earlier dated pending-main statements below
retain their point-in-time meaning and are superseded only for this integration.

## MCU Delivered And Candidate Approval Removed, 2026-11-18

The owner performed the final push of `816b1888be2dfaa632e4e802e6b680ec85ed5aec`
to `release/candidates`. Original Actions run
[44276457821](https://github.com/Eitan-S-23/E-Track/actions/runs/44276457821)
completed successfully: checks and firmware passed; App was skipped. The native
registration receipt confirms two assets and ready firmware `3.3.30 / 30330`,
release `fw_6149475085189032dd38065a5e12d50697d51b564b9533a6ca87e5b939466ceb`.
This reuses the successful original run and its six source/package/registration
receipts; no package was rebuilt to obtain this observation. Registration is not
channel publication, a device installation, or whole-card acceptance.

The owner then requested removing the manual approval from automatic candidate
delivery. Configuration commit `cb360b762cdd571ceef0d1de881a0de313b95f3c` is now
on `release/candidates`. Its three-file delta changes only the candidate workflow,
its regression test and `docs/original-admin-candidates.md`. Firmware/App versions,
product trees and `.github/workflows/firmware-build.yml` are unchanged.

The dedicated GitHub environment `firmware-candidates` has no required reviewers
or wait timer and exactly one branch policy, `release/candidates`. Its production
gate remains `OTA_BOOT_CHAIN_READY=false`. The existing AES key is reused as
`FIRMWARE_CANDIDATE_OTA_AES_KEY`, with its identity matched to the successful
3.3.30 build. The existing `ORIGINAL_ADMIN_FIRMWARE_DEPLOY_TOKEN` is reused;
the uploader inherits repository Secrets `CLOUDFLARE_ACCOUNT_ID` and `E_TRACK_CI`.
No key or token was generated, rotated or printed. Readbacks verify unchanged
rehearsal/production approvals, rehearsal Secrets and repository Secret metadata.

Local validation passes 100 Node checks, eight Python checks and actionlint.
The actual candidate planner selects neither App nor firmware for this
configuration-only change. Actions
[44283291086](https://github.com/Eitan-S-23/E-Track/actions/runs/44283291086)
passes its checks; both build jobs are skipped. No existing package, original
successful run, channel or device operation was replayed. The new environment's
next real versioned build has not been executed just to test the configuration.

Receipts are under `.cache/firmware-candidate-automation-20261118/`, principally
`keyring-inputs-03/`, `keyring-configure-01/`, `check-01/`, `keyring-deliver-02/`
and `keyring-verify-02/`. Earlier diagnostic failures are preserved separately.
This milestone supersedes the pending-push/build statements in the historical
preparation below. D0-D5, formal whole-card acceptance and firmware product
integration into main remain outstanding; these are documentation-only main
records, not a merge of the candidate product tree.

## MCU Candidate Locally Prepared, 2026-11-18

The owner requested local preparation and will perform the final push. Candidate
`816b1888be2dfaa632e4e802e6b680ec85ed5aec`, branch
`prep/firmware-companion-3.3.30`, is clean in
`.worktrees/firmware-companion-candidate-20261118`, based on fresh remote
`release/candidates` source `a977c848e03a2798a7b5c46319cd126a292395b4`.
Only the reviewed `3028a057` MCU/paired-simulator delta, six host test files,
the `3.3.30 / 30330` release request and a bounded candidate note are committed.
Existing candidate filename/scrolling fixes and V2-only ACK handling are retained.
App 108, publishing workflow, Boot, OTA implementation and control contract
have identical Git objects to the candidate base.

Local development results: control 24, production-method safety 18 and encoder
1 pass; all 74 candidate/profile checks pass. Windows template CRLF initially
caused two extraction failures; formatting to its existing Git LF bytes restores
the checks without changing content or assertions. The initial commit closeout
only found stale index stat for that identical template blob; a scoped stat refresh
leaves the candidate clean without another commit or any App tree change.

The actual candidate planner, simulated locally for a first push, reports
`firmware.required=true`, version `3.3.30 / 30330`, `app.required=false`,
`channelPublished=false` and `automaticDeltas=false`. No push, Actions dispatch,
native firmware build, Cloudflare mutation or device operation was performed.
Those delivery results remain for the owner's final push and its resulting run.
D0-D5, whole-card acceptance and product main integration remain outstanding.

Candidate record: `docs/ota-exec-notes/APP-COMPANION-01-firmware-candidate-20261118.md`
in the named commit. Original preparation receipts are under primary-root
`.cache/firmware-companion-prep-20261118/`. This primary board/note/index update
is LOCAL_PENDING, uncommitted and unpushed; it does not claim backend delivery.

## Current Independent Review, 2026-11-17

The original non-implementation review resumes on `3028a057`. The 15-file
T01/T02 delta and 116 original source/log/artifact files have been independently
checked: the identified host-coverage gaps and AC01-T02-NATIVE-01 source defect
are CLOSED, with no new blocking finding in this bounded review. See
[the independent result and exact limits](#independent-t01t02-review-3028a057).
R01-R05 remain source-closed. D0-D5, formal whole-card acceptance and firmware/
whole-card integration remain outstanding; C1-C6 are not signed off. The review
was originally LOCAL_PENDING on main `990d8b4d`. Its unchanged findings are now
delivered with APP-ADMIN-UX-01's root records. That task delivered the existing
1.0.78 App baseline plus its UX changes to main `304d01f5` and built the original
signed 1.0.79 candidate, without importing the unrelated firmware history.
This App-only source delivery is not whole-card integration or independent
acceptance of the later version. The dated milestones below retain their
original point-in-time meaning, including their then-pending delivery statements.

## Current Verified Milestone, 2026-11-16

The implementation and development-validation milestone below supersedes earlier
pending-CI statements. The single card remains IN PROGRESS; C1-C6 are not signed
off. Implementation, device observation, independent acceptance and main product
integration are separate.

Latest independent remediation review on `f463649f`, 2026-11-16: R03 is CLOSED
for the identified source defect, so R01-R05 are now CLOSED at source-review
scope. No new blocking defect was found in the bounded 11-file delta. See
[Independent R03 Closure](#independent-r03-closure-f463649f).
T01/T02 and D0-D5 remain open/NOT_RUN. Root owns the authorized documentation
delivery below; its submission receipt and fresh main-board check establish
publication. Historical LOCAL_PENDING entries retain their point-in-time meaning.
This is not whole-card acceptance or product integration.

Independent offline review, 2026-11-16: AC01-R01 through AC01-R05 below are open
on `7fa86c2c`. Two production-method host probes reproduce product failures;
three further findings are source traces, not claimed device observations.
See [Independent Offline Review](#independent-offline-review-2026-11-16).
This reviewer update is local and pending delivery; the original development
results below remain valid as development results, not whole-card acceptance.

- The authoritative board is `D:/github/my/E-Track/PLAN-OTA-EXEC.md`, not a cache
  or task-worktree copy. The published main before this note delivery is
  `5b8724eee59677af5f1f03ecbdf4f32635bdfa14`; the fresh entry query verified that
  remote with MAIN_MATCHED before these new note edits.
  Governance CI `43784070134` passed on that main. Entry delivery `27804263` and
  preserved history are intact.
- Current product source is `7fa86c2cffc3fc7bd611887c0a7c399830445c28` on
  `dev/flutter/app-companion-01-20261116` in `.worktrees/app-companion-01`.
  The branch is pushed; its product changes are not merged to main or installed.
  Earlier source batches, including `bedfa12f` and `d402571a`, remain in history.
- Permissions, explicit Android CDM association, 6/12/24-hour scheduling (12-hour
  default), bounded recovery/scans, retained-engine ownership, headless sensor
  persistence, MCU check/offer/consent, menu Back and selected icon are implemented.
  The product-branch contract `docs/companion-control-contract.md` documents the
  additive text protocol and runtime rules without altering frozen binary OTA.
- The companion implementation also fixes pending-offer renotification inside
  the long check interval, retryable MCU STARTING/binary-exit states, ownership-safe query
  cancellation, late callback fencing and manual-check coalescing. An open GPX
  recording (including paused) blocks install. Scoped stop cancels only its own
  query and waits for non-cancellable END/apply rather than disconnecting it.
  `bedfa12f` adds bounded control-session recovery after a failed foreground INFO
  invalidates shared identity, without triggering another long-interval HTTP
  check. Its regression passes on both hosts. Native/MCU inputs are unchanged
  from the preceding validated batch.
- The follow-up closes a development-collection gap: the old debug endpoint
  option also started an automatic BLE probe, while standard release-mode private
  files cannot be assumed readable with `run-as`. The existing observation entry
  now accepts `observation_mode=passive`: it records the real runtime's producer
  events without scanning, connecting, reading INFO or disconnecting on its own.
  Mode/target/endpoint are bound to a verified compiled token and the unchanged
  log format. No new OTA sender or collector protocol was created. The executable
  contract is in the product branch's `docs/flutter-development-validation.md`,
  section Passive Companion Diagnostics.
- Android/native APK and nonpublishing standard APK/EXE verification use the
  existing Actions entries, not local Flutter/Gradle packaging. The side-by-side
  suffix is `.companion`; shipping package identity, signing configuration and
  version have not been changed. No release/channel update or deployment is
  requested by the current standard-build dispatch.

### Latest Validation Originals

Paths beginning `.cache/companion-` below are relative to the product worktree;
development adapter receipts are below root `.cache/app-companion-01-20261116/`.
Every listed check is implementation self-validation, not independent acceptance.

| Source / Original | Result And Boundary |
| --- | --- |
| `f735993e`, checks `43777114133` | PASS, Linux 941 passed / 16 skipped, Windows 921 passed / 36 skipped; 11 candidate-profile tests also pass on each host. |
| `f735993e`, debug/native request `43777179312` | PASS. Original CompanionServiceTest XML: 9 tests, zero failures/errors/skips. Linux logs/JUnit preserved in `development/keyring-artifacts-43777179312/logs/`. This earlier APK is not the final candidate. |
| `a25a746b`, checks `43778687616` | Whole run FAIL on one new-test brace-style diagnostic; both full test suites pass, including 13 new coordinator and four real OtaService retirement tests. Failed console and complete Linux logs are preserved in the matching `keyring-log-` and `keyring-artifacts-` directories. |
| `9ccea658`, checks `43779357804` | PASS: Linux 958 passed / 16 skipped, Windows 938 passed / 36 skipped; each also passes 11 candidate-profile cases, analysis clean. Full console is `development/keyring-log-43779357804/console.log`. |
| `9ccea658`, debug/native request `43779455252` | PASS on both hosts, debug APK verified. Native XML: CompanionServiceTest 9/9 and DeviceOtaServiceTest 18/18, no failures/errors/skips. Full Linux logs/JUnit are in `development/keyring-artifacts-43779455252/logs/`; downloaded APK/metadata and local hashes are in `development/keyring-package-43779455252/`. |
| `9ccea658`, standard build `43779471610` | Attempt 1: Windows EXE PASS; Android wrapper initialization fails on Maven Central HTTP 429 before App compilation/signing. Original job log is `development/keyring-job-43779471610-133013271843-02/console.log`. Only Android job was retried once after the separate hosted debug/native build resolved those dependencies; Windows retains its original 00:17:45..00:26:40 UTC execution. Attempt 2 PASS, full console in `development/keyring-log-43779471610-03/console.log`. No release/deployment. This is an earlier source, not the current artifact. |
| `bedfa12f`, checks `43782315932` | PASS: Linux 959 passed / 16 skipped, Windows 939 passed / 36 skipped, zero failures; each also passes 11 candidate-profile cases and strict analysis. Both SDK identities are Flutter 3.47.8 / Dart 3.13.7. Console is `development/keyring-log-43782315932/console.log`; full Linux development logs are in `development/keyring-artifacts-43782315932/logs/`. |
| `bedfa12f`, standard build `43782557046` | PASS on first attempt: Android release-mode APK and Windows release-mode EXE. `publish_release=false`, `replace_existing_release=false`, `.companion`, baseline link profile; Pages and Create GitHub Release are SKIPPED, with no Cloudflare deployment. Console is `development/keyring-log-43782557046/console.log`. Both named artifacts and local hashes are retained in `development/keyring-standard-artifacts-43782557046/`; run/source and build-only jobs are checked before download. |
| `d402571a`, checks `43786280669`, debug request `43786444133`, standard build `43786357506` | FAIL on the new passive diagnostic test on both hosts; analysis passed. The fixture sent an `OTA_OBS` status line through the strict OTA producer-record API, causing `observation capture incomplete`. Build gates correctly prevented APK/EXE production. Original failed test log is in `development/keyring-artifacts-43786280669-02/logs/`; debug/standard consoles are in their `keyring-log-` directories. `7fa86c2c` changes only this fixture: status reporting is separate from accepted producer records. No production logger guard was weakened. |
| `7fa86c2c`, checks `43787172124` | PASS: Linux 962 passed / 16 skipped, Windows 942 passed / 36 skipped, zero failures; strict analysis and 11 additional candidate-profile tests pass on both hosts. Console and full Linux logs are in `development/keyring-log-43787172124/` and `development/keyring-artifacts-43787172124/logs/`. |
| `7fa86c2c`, passive debug request `43787308531` | PASS on both hosts; debug APK produced with the actual public firmware endpoint and `device_observation.mode=passive`. Manifest application ID, fixed signer and compiled target/endpoint/mode token are verified. APK/metadata are in `development/keyring-package-43787308531/`; console and Linux build logs are in the matching `keyring-log-` and `keyring-artifacts-` directories. Native sources were not changed or retested in this request. |
| `7fa86c2c`, standard build `43787389782` | PASS: Android release-mode APK and Windows EXE, first attempt. Publishing, replacement, Pages and Cloudflare deployment remain disabled/skipped. Both named artifacts and source/hash checks are in `development/keyring-standard-artifacts-43787389782/`; original console is in `development/keyring-log-43787389782/`. |
| Root `checks-passive-01/` | PASS: 51 APK-helper tests, 66 development-runner tests and whitespace. Tests cover the new workflow input, default compatibility, malformed modes, missing compiled tokens and rejection of an automatic APK as passive. |
| `.cache/companion-tests-06.log` | 18/18 PASS, including STARTING timeout and binary-exit menu recovery. The retained compiled fixture and source SHA are recorded in the log. |
| `.cache/companion-build-07/result.json` and `build.log` | GCC App/Boot and simulator PASS, source unchanged, 394 warning-containing lines and zero errors. Boot and simulator are unchanged incremental outputs, not newly linked artifacts. |
| Root `checks-02/` | 40 entry/governance/icon/menu cases PASS; original menu fails the same oracle that the candidate passes. Source-bound originals are retained; no claim of physical rotary testing. |
| Root `checks-03/04` | Final 40 entry/governance/icon/menu plus 18 MCU cases PASS. The separate rendered-icon check initially fails because contained HOME/AppData hides the user's installed Pillow; only that check is rerun in checks-04 with its existing library as read-only PYTHONPATH input and passes. No global package installation or source/image regeneration. |

### Current Build Artifacts And Collection Boundary

Current-source passive debug APK: 132382559 bytes, SHA-256
`90c0910c73f313c54996bb584e2c4a94d91c394b5b765e7b3d81283ea794db80`.
Its local bytes match the CI metadata. Manifest application ID is
`com.wen.gaia.gaia.companion`, fixed certificate SHA-256 is
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
Verified sentinel is `OTAOBS6ba2efba386aa57b6c13996c`, with compiled passive token
`passive:OTAOBS6ba2efba386aa57b6c13996c`. The injected URL is
`https://e-track-firmware-p41-public.pages.dev/api/public/firmware/latest`, read
from the existing repository public-service variable, not a placeholder.
Expected target `E3:49:E1:14:D6:CB` is taken from the hash-verified P3-8-v5 original
capture bindings; it is a historical expectation, not a current live observation.
Actual phone/MCU identity, endpoint response and collection readiness remain D0
checks before installation/OTA. Source version remains `1.0.71+97`; nothing is
installed yet. This debug package is the prepared private-file retrieval route.

Current-source standard APK: 48318616 bytes, SHA-256
`1cb4da4b7be0da51dd68363f2bdc4465595d035acfb27b73f1586eeffecc324c`.
The downloaded file exactly matches the build's SHA-256 and length output.
CI verifies one fixed signer with certificate SHA-256
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
The actual build log confirms the `.companion` suffix and configured public
update service/public key; the reviewed workflow injects its separate
`/api/public/firmware/latest` endpoint. Intended package ID remains
`com.wen.gaia.gaia.companion`, version `1.0.71+97`. Final manifest and installed
package identity still require D0 verification; build configuration alone is not
an observation of the phone. No live endpoint/device compatibility is claimed.

The Windows EXE is 161792 bytes, SHA-256
`df9c142eeee7055c8e6145b5898f927f3ed3de1119216d09a812df425ac3b6d7`.
Its accompanying runtime ZIP is 20628483 bytes, SHA-256
`0621108739c9ae80c8a560a20d7f295fd643788ccb79224b6bca3a7030f2fbf2`.
The EXE alone is not the complete Windows installation. Artifact IDs are
`14191720158` (Android) and `14191520950` (Windows), both expiring on 2026-11-30;
the local copies preserve the exact current build independently of that expiry.

The earlier-source downloaded debug APK is 132379951 bytes, SHA-256
`3a1e17b7112c67b48ec838b926b6e4c6a406f903abfb6e30bfe7700f5588e085`,
application ID `com.wen.gaia.gaia.companion`, fixed development certificate
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
It uses the unchanged App version `1.0.71+97`. This debug request did not inject
a firmware-latest URL or an automatic device-observation profile: it is suitable
for onboarding/runtime observation, not proof of a configured live OTA gateway.
Before D3/D4 use the current passive debug package and prove the existing Phone
helper's `run-as` private-file/snapshot route on the actual phone. Do not substitute
the standard release-mode APK for that route or enable the legacy automatic
observer while evaluating companion ownership. Do not install the earlier
unconfigured debug APK and misdiagnose an absent endpoint as an OTA defect.
Earlier `bedfa12f` standard hashes and artifacts remain in their original
download receipts; they are not overwritten or relabeled as the current build.

The `keyring-build-02` metadata GET and `keyring-ci-24` follow-up checks GET each
encountered a transport EOF. The former failed before dispatch; the latter had
already saved the successful standard-build result. Original receipts remain;
neither means the build failed or authorizes replaying a completed build.
Later `keyring-ci-30` failed on a `/user` GET EOF; `keyring-ci-31` had already
saved the current-source results before a historical-main query hit EOF.
`keyring-ci-32` completed successfully. These were status reads, not repeated
builds. The bounded adapter now preserves sanitized command-failure diagnostics
even before its identity receipt and removes credential-bearing URL queries.

Build 07 App BIN is 611564 bytes, SHA-256
`8a6ff0630ed5dd4d929ab5423961f9f1756a27cd8b01bb7af11687840dbc9c9a`;
ELF `6956b11834cac98e684cda1a3b20b0f4ea9dc6d2cec157269316aa32ca9b5070`;
simulator EXE `cee8d35a6a882efeb102988610febf634ff4f38473382a255ed2801d327c6056`.
These are build products, not a finalized/installed candidate. Version/header,
current App/Boot/BCB/staging and recovery compatibility still need live preflight
before programming. No App-only downgrade or Boot replacement is implied.

The shared SDK is Flutter 3.47.8, framework
`737ba8f885dc774b53b442759999a312c9461e4e`, Dart 3.13.7. Strict analysis and the
development lockfile gate stay enabled. Existing failed runs are not rewritten.

### Menu Inventory And Remaining Observation

| Reachable Page / Mode | Implementation Inspection And Required Observation |
| --- | --- |
| MainMenu main list | Back now joins the focus group independently of item capacity; focused/visible state, empty-list fallback and one activation are in the original-red/candidate-green host test. Physical rotation/press remains NOT_RUN. |
| MainMenu navigation, records, display, sensor, system subpages | All use CreateBase/CreateFooter and RefreshEncoderGroup. Back returns a subpage to the main list, then the main list pops one page. Test long/dynamic lists and re-entry on the device; existing placeholder setting/record data is not upgraded by this task. |
| RouteSelect | RefreshGroup already includes Back; SHORT_CLICKED is the sole activation event. Empty/long lists and return to navigation require device observation; no unnecessary rewrite. |
| FirmwareUpdate browser | Back is grouped after file rows; online `@companion` works with no SD. Capacity increased to preserve the 24 existing file slots. Real empty/long/no-SD navigation remains to observe. |
| FirmwareUpdate SD confirm/result/apply | Cancel/start and result controls have mode-specific groups; working/apply does not expose an unsafe exit. Existing SHORT_CLICKED behavior retained. |
| New companion modal | Async open/close saves actual input groups/focus, excludes disabled controls and rechecks displayed consent. Verify actual wheel focus/restore, Later and safety-disabled Install on the device. |
| SystemInfos | Focused icons use the existing single PRESSED exit action, not an explicit Back button. Retained as the original interaction; physical observation remains. |
| RouteImport | Progress page uses LEAVE/GESTURE cancellation and has no visible Back button to register. Do not invent an ordinary menu Back during critical operations. |
| Dialplate / LiveMap / Startup / StatusBar | Existing page entry/gesture/zoom or noninteractive behavior, not affected multi-level Back controls; automatic update prompts are limited to safe stable pages. |
| Legacy FileBrowser helper | Not an AppFactory page, no caller of file_browser_create, and not in the GCC/simulator target. Do not re-enable its legacy .bin updater or count it as a tested production menu. |

### Finite Device Plan

The follow-up authorization covers this task's necessary verification, but not
production publishing, unrelated devices, data clearing or project-external
writes. The current session is the sole implementation operator. This is a
development plan, not an independent frozen acceptance matrix or reused quota.

| Cell | Bounded Work And Oracle |
| --- | --- |
| D0 Identity and readiness | Connect/unlock the known test phone; use the existing private-port Phone helper for serial/model/SDK/current package. Verify exact successful-CI APK metadata/hash and existing installation before any install. Read current MCU App/Boot/BCB/staging before choosing finalized receiver/target assets. |
| D1 Permission and association | On the isolated App, user handles real system dialogs. Observe skip, denial, settings return, association and explicit enable; unknown OEM switches remain unknown. Agent does not automate taps or clear data. |
| D2 Background ownership | One pass each: foreground to background, lock/unlock, recent-task removal, process recovery and phone restart, only under declared API/OEM conditions. Confirm live owner, actual BLE/data and bounded offline recovery, then disable and confirm resource release. Force-stop is a negative boundary, not a promise of survival. |
| D3 MCU check and preparation | Trigger the MCU check independently of the long interval, confirm in-flight coalescing and network/metered failures, then verified-package readiness. Later and a stale choice must produce no BEGIN. Reconnect must revalidate before renotification. |
| D4 Consented update | After exact forward-compatible assets and recovery are ready, one legitimate consent starts the existing sender. Preserve original App/MCU observations and ordinary apply/reboot, then fresh target version/full raw SHA and Boot state. A successful OTA is not replayed just to repair collection. |
| D5 Navigation and icon | Exercise the menu inventory with actual wheel rotation/press, single-level Back and focus restoration; inspect installed launcher/notification icons and package identity. Simulator/host checks are supporting evidence only. |

Each cell gets a finite device window and original action/result record. Any
diagnosed fix needs only its affected regression; no full endurance/P5 campaign
is added here. For receiver installation prefer existing standard J-Link after
D0 safety checks; no extra provisioning OTA merely to install receiver code.
Production GCC output must be finalized/verified for the actual retained state,
not blindly loaded as the raw build HEX. Prepare collectors, package bytes,
post-reboot retrieval and cleanup before asking for an OTA-start action.

Existing USB preflight is UNAVAILABLE: the expected test phone was not found.
Original command/error and closed-port/process receipts are under root
`.cache/app-companion-01-20261116/device-preflight-01/`; no new install, App launch,
tap, MCU flash or OTA has occurred. Do not repeat this absent-device probe without
a connection/state change. The next necessary human action is connecting and
unlocking that phone, followed by its actual system dialogs when prompted.
After preparing the current artifacts, the 2026-11-16 01:51 UTC Windows PnP
connected-device query still did not identify the expected phone serial.
`host-usb-presence-02.json` records that result without starting ADB or mutating
a device. No blind repetition of the failed ADB preflight was made. Authorization
is not the missing input: the next physical action is connecting/unlocking the
known test phone and accepting its USB-debugging dialog if shown.

### Acceptance And Main Integration

The implementation session will not sign its own independent acceptance. A
non-implementation session must review the stable bounded source, reuse applicable
P3/P4 originals and execute only genuinely missing A1-A6 observations under the
existing execution contract. There is no additional task card or invented third
freezing role. Product main integration follows that independent result; the
root board/note delivery is not a product merge. P3 8/8, P4 4/4, P1/P5 gaps and
production gates remain unchanged.

### Host Write Audit

Root `.cache/app-companion-01-20261116/final-write-audit-03.json` retains the
earlier source/Git/build/test/download/temp inventory, not just Git status.
`final-write-audit-04.json` binds the earlier delivered main `5b8724ee` and product
`bedfa12f`. The continuation inventory is written as `final-write-audit-05.json`
after this main-note delivery to bind the new main and product `7fa86c2c`.
They resolve within the approved project. The generated Windows compatibility
junction at product `.cache/build-home/AppData/Local/Microsoft/Windows/INetCache/Content.IE5`
resolves to sibling `IE` in the same project; it was inspected, not removed.
Git configuration/hooks and ADB key metadata are unchanged, and no local
PowerShell was invoked. Archived evidence and the preservation stash remain.

Native-side-effect attribution remains UNRESOLVED: the read-only audit found
certificate/CRL cache timestamps changing during the task under
`C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache/`
and `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/`. Exact file paths,
sizes and timestamps are in the audit receipt. The two inspected SYSTEM content
entries are public Google PKI CRLs. Earlier Git post-commit notifications invoked
native curl and are a possible source, but there is no before-image/process trace
to attribute all changes. Do not claim zero native external writes on this basis.
The optional notification is now disabled only in bounded Git subprocesses;
pre-commit quality checks still run. No external cache was cleaned, moved or
overwritten. Retain it; any future cleanup needs path-specific user authorization.

## Earlier Milestone, c822765a

The following observations are retained as history, not current completion claims.

- Root-main entry/governance/card delivery: `278042636699067dd95c61160d2e1900d9dcbe33`,
  remote checked with MAIN_MATCHED. Governance run
  `https://github.com/Eitan-S-23/E-Track/actions/runs/43768837547` passed.
- Product branch `dev/flutter/app-companion-01-20261116`, worktree
  `.worktrees/app-companion-01`, submitted current batch
  `c822765a99b83735685e251d9a289f97e6d291e4`. Earlier menu/icon batch
  `8e2804e59d4402267bd8e5718f61c8bf439e05bf`, lock reconciliation
  `1701bc48a5ee11d99260e8c7f124fe03479d0eb3`, first App implementation
  `eaa27847f3873083e5b7e8bff68cafa05800ef52` remain in history.
- Implemented scope now includes SDK-specific onboarding, CDM association,
  persisted 6/12/24-hour checks (default 12), bounded connection recovery,
  acknowledged connectedDevice/retained-engine execution, one shared OTA sender,
  headless saved-sensor collection (8 seconds/minute on Android 12+), real
  GET_INFO/latest/cache checks, MCU control/confirmation, encoder modal focus
  restoration and the selected icon. These are implemented, not accepted.
- Additive protocol/runtime contract is at product commit above,
  `docs/companion-control-contract.md`. It preserves foreground-only legacy
  admission and frozen binary OTA/Boot semantics; background admission separately
  requires actual runtime/GATT/permission ownership. MCU receives storage and
  actual-display receipts separately; stale/expired device consent is rechecked
  after asynchronous pre-BEGIN work. Control writes no longer replace the idle
  CCCD receiver. Unknown peripherals remain explicitly unsupported for OTA.
- Native service tests were added to the existing opt-in CI native-test step.
  No local Flutter/Gradle compile/package command was run. The debug request
  explicitly uses isolated application suffix `.companion`; dispatch receipt:
  `.cache/app-companion-01-20261116/development/keyring-apk-01/dispatch.json`.

### Original Validation Results

| Original | Result And Boundary |
| --- | --- |
| Earlier `checks-01/02` | 40 entry/governance/icon/menu unittest cases PASS, selected source unchanged. |
| Product `.cache/flutter-dev-checks-tests/run-ba674512be7a4481b3398c5b55bf7258` | Development runner 66/66 PASS. |
| Product `.cache/native-runner-tests-01.log` | APK helper 46/46 PASS, includes companion native-test selection. |
| CI 43769801181, 1701bc48 | Locked dependencies and App tests passed (Windows 898/35 skipped; Linux 917/16 skipped), but strict analysis failed on 46 new Flutter 3.50 Material migration diagnostics. Whole run FAIL. |
| CI 43773033275, eaa27847 | Flutter 3.47.8/framework 737ba8f885dc774b53b442759999a312c9461e4e, Dart 3.13.7, dependencies PASS. Analysis had 29 new-code diagnostics; App tests failed to compile two entry files. Whole run FAIL, not a successful first App batch. |
| Product `.cache/companion-tests-03.log` | 16 MCU protocol cases PASS on original header include layout. |
| Product `.cache/companion-tests-04.log` | Same 16 behavior cases PASS after include correction; process exit 1 due WinError 5 removing the completed test EXE. HARNESS cleanup failure retained for scoped repair, not a product failure or whole-run PASS. |
| Product `.cache/companion-build-03/04` | Preserved compiler failures (header include resolution, missing direct UI header and unavailable LVGL getter). No firmware installed. |
| Product `.cache/companion-build-05/result.json` and `build.log` | GCC App/Boot and simulator PASS, all modified source hashes stable, 468 warning-containing lines, zero errors. Unchanged Boot outputs are incremental, not newly linked. |

The Flutter SDK pin is shared by development and standard APK/EXE entries;
strict analysis and `--enforce-lockfile` remain enabled. This deliberately avoids
an unrelated UI-library migration or diagnostic suppression. Latest App CI and
debug/native-build outcomes must still be read before claiming they passed.

Current GCC App: text 609968, data 940, bss 563096 (size-tool section totals,
not physical SRAM usage). App BIN 611408 bytes,
SHA-256 `f30424d7f6f7ee72a99426bc337a58c59efc4decce9e499e2320062da2d7df63`.
Simulator EXE SHA-256 `678644dc75b615e11893583391fe951a6912c9b29a1488cb57a2db705e58f712`.
Full ELF/HEX/MAP/Boot sizes, times and hashes are in the build receipt.

### Remaining Work And Next Owner

Current root/implementation session continues CI/native remediation, remaining
cross-layer tests and finite device preparation. Real permission/association,
background/lock/restart, actual rotary operation and MCU-confirmed OTA remain
NOT_RUN for this implementation. Standard Android APK/Flutter Windows EXE,
independent acceptance and product main integration are also unfinished.
P3/P4 remain complete; P1/P5 and production gates are not reopened or bypassed.
No production publishing/deployment, new firmware install, phone data clearing
or historical evidence rewrite has occurred in this batch.

## Ownership And Scope

The user approved the six-step plan on 2026-11-16 and assigned implementation
to this Codex session. There is one card and one Spec. This record is an evidence
and design index, not another status board or an independent acceptance result.
No other agent is using the current directory according to the user.

## Main Entry Preservation

The public GitHub main ref was checked on 2026-11-15 at 21:27 UTC (2026-11-16
local): `bd146e6b7dc6d1c2616c823f1e3668b671c8076d`. The root is now on this
`main`; `.cache/p34-final` is detached at the same commit and retained in place.
No reset, forced checkout, branch rewrite, push or merge was used.

- Original archive HEAD: `cb317affcd291695f42271084b4b305b0d7e6f8b`.
- Tracked-only preservation stash: `1fb0e5662fa2d42658d0c57e527d31f4266ff14e`.
- Raw preservation root: `.cache/app-companion-01-20261116/preserved/`.
- Original inventory: `.cache/app-companion-01-20261116/preservation.json`.
- Migration intent/result and separate Git command logs are in the same directory.
- 57 tracked changes and 1,238 root changed paths were accounted for; raw copies
  total 1,587,405,622 bytes including existing artifacts, not newly built products.
- 34 untracked/ignored files conflicting with the main checkout were moved to
  `.cache/app-companion-01-20261116/relocated/` after verified preservation.
  Other untracked files remain in place. Do not apply the archive stash to main.
- All 18,426 old-main untracked evidence files retained their size, mtime and
  SHA-256. The selected `generated-images/29.png` remains unchanged with SHA-256
  `fa849d68e0d718a08d8461f2e04caecb6807d1396090ad64201f2a88b0d4cf85`.

The bounded Node adapter only orchestrated native Git and preservation hashes.
The existing filesystem guard is PowerShell-based; uncontained PowerShell is
not allowed here. The first read-only scan repeated parent checks excessively;
its exact owned process was stopped, then the scan was completed with cached
read-only ancestry checks. Writes still check their full destination chains.

These entry/card/rule changes are local pending main delivery. The authenticated
GitHub CLI route reports no readable OAuth token in this process, even though
the configured user is Eitan-S-23. Public ref access works. No credential was
exported, reset or replaced. Development CI is not yet available from this session.

## Implementation Baseline

Use `.worktrees/app-companion-01`, branch
`dev/flutter/app-companion-01-20261116`, based on the exact main revision above.
The primary root remains the sole board entry; do not treat a task checkout's
historical board as current. This worktree has been created and is the current
product implementation location; the root remains on main.

Reuse completed P3-8-v5, P3-5-v5 and P4. P1 physical evidence and P5/final
production obligations remain outstanding and unchanged. Other task branches
are inputs to inspect, not trees to copy into this implementation.

## Current Code Findings

- MainMenu on current main still creates a footer outside its encoder group.
  Its encoder event branch returns before the footer's touch-oriented handler.
  Fix group registration, focus visuals, duplicate-click handling and cleanup,
  not just the one missing `lv_group_add_obj` call.
- BackgroundTaskService uses an in-process 30-second scan timer; it does not
  establish restart, boot or retained execution ownership. P3-8 already provides
  real task-scoped OTA ownership and must not be replaced by a second sender.
- DeviceOtaBridge currently admits acquisition from a resumed Activity. A new
  background companion entry cannot silently remove that established safeguard.
- The App already has GET_INFO, identity-bound latest/download/cache and final
  reboot/raw-SHA verification. Device-requested checks must reuse those paths.

## Validation And Next Work

Entry/rule regression, product self-tests, CI builds, device observations and
independent acceptance are separate. No product tests, new build, device OTA,
publication or independent acceptance are claimed by the migration receipts.
The entry guard has nine passing host tests and its actual remote read returns
the primary board with `LOCAL_PENDING`, not a false published-state claim.
Its Linux/Windows unit checks are wired into Acceptance Governance but that
workflow has not been run for these uncommitted changes.

## First Product Batch

Menu source changes and tests are in the implementation worktree. The real
`IsFocusItem`, `RefreshEncoderGroup`, `ClearEncoderGroup` and `onEvent` bodies
are compiled against a small LVGL unit boundary. The original main bodies fail
the missing-footer oracle; the candidate passes group/focus/cleanup, empty list,
hidden/disabled controls, single rotary/pointer activation and unchanged row
routing. This is a host behavioral self-test, not a physical encoder observation.
The footer remains outside the fixed setting-row array and its CLICKED handling
precedes encoder-row dispatch, suppressing the paired SHORT_CLICKED event.

The selected image is preserved as the App's `branding/e_track_source.png`.
`Tools/assets/app_icons.py` generated 27 canonical source/launcher assets and a
local visual preview, with deterministic byte verification and an input-pinned
manifest. Android uses adaptive density layers and a separate white notification
vector; iOS retains its existing AppIcon filenames, Windows retains its ICO path.
Package IDs, labels, signing, versions and update channels are unchanged.

The prescribed default firmware/simulator build encountered the existing Windows
dependency-path-length limit while compiling LVGL benchmark asset sources.
Original attempt: `.cache/companion-build-01/` in the implementation worktree,
58 warning-containing lines, six error-containing lines, no final artifacts.
The narrow native recovery route uses project-local `.cache/b` and
`CMAKE_OBJECT_PATH_MAX=180`, retaining the same GCC production App/Boot targets,
Release configuration and SOURCE_DATE_EPOCH. No external short directory,
source relocation, toolchain replacement or local Flutter build is used.

Permission onboarding and companion/control-plane work remain to implement.
Do not mark C1-C6 complete from this first batch. Flutter Actions/APK/EXE and
actual device checks remain NOT_RUN; authenticated development CI must be
available before iterative App remediation and final verification.

## Verified Results And Remaining Input

- `checks-01/` under the root preservation directory contains original logs:
  entry tests 9/9, existing PostP26SpecGovernanceTests 27/27, icon tests 3/3 and
  an actual entry check from the new task worktree, all successful.
- `python -B tests/ota/test_main_menu_encoder.py` in the implementation worktree
  passes its source-bound original-red/candidate-green behavioral case. Candidate
  MainMenu SHA-256: `dbb5d62701ad977ec72c126bc9ab9765a7120298162d5df616dfa0e91684ba8c`.
- The original root whitespace check caught CR on newly added lines of the
  mixed-EOL board. Only changed lines were normalized; historical lines were
  preserved. The follow-up `git diff --check` passed. The original failure log
  remains in `checks-01/root-whitespace.log`.
- `.cache/companion-build-02/result.json` in the implementation worktree records
  successful GCC App, Boot and LVGL Simulator builds, unchanged menu source,
  742 warning-containing lines, zero error-containing lines, and timestamps,
  sizes and SHA-256 for all nine final artifacts. There was no timeout.
- GCC size output: App text=603812, data=940, bss=561992; Boot text=14720,
  data=4, bss=9780. These are size-tool section totals, not invented physical
  SRAM-usage claims. The original linker diagnostics remain in the build log.
- Local self-tests total 40 unittest cases across the four suites above.
  They do not replace UI rendering, physical rotary, Android lifecycle or OTA
  observations, independent acceptance, or the separate Flutter build gate.

No new delivery commit or CI run exists for this batch. The implementation
worktree remains based on `bd146e6b7dc6d1c2616c823f1e3668b671c8076d` with local
changes. Flutter development tests and Android APK / Windows App EXE builds
are NOT_RUN; there is no current run URL. The successfully built LVGL simulator
is not the Flutter Windows App. No firmware/device install, channel publication,
release or cloud deployment was performed.

Next required input is restoration of this process's access to the existing
Eitan-S-23 GitHub login (or use of an already-authenticated execution context),
not a new token sent in chat. The current configured login exists but both named
and default `gh auth token` reads fail. Public main verification remains usable.
Keep the first batch intact while this validation route is restored; permission
onboarding, the companion runtime, and device-requested check/confirmation are
still outstanding, not silently represented by the existing P3-8 service.

## Final Local Verification And Write Audit

The final `checks-02/` run in the root evidence directory passes all four suites
(40 unittest cases), approved-source icon rendering, root/task whitespace checks,
and a fresh main-entry query issued for the task worktree. The first failed
whitespace result and the first failed default build remain available; neither
was relabeled as a successful run. No firmware build was repeated after the
successful short-path build because its actual menu input remained unchanged.

The write audit records the primary root on main, the implementation branch,
the preserved stash and original evidence, unchanged existing phase totals,
one APP-COMPANION-01 card, and the original selected image. All selected output,
backup, relocation and build paths are inside `D:/github/my/E-Track`; controllable
build HOME/AppData/temp outputs were redirected into the task worktree. The
known external Git/GitHub configuration and PowerShell cache metadata show no
modification since this work started. This is an audit of this session's chosen
operations and known tool outputs, not a claim to have scanned every system file.
Audit receipts are `final-write-audit.json` and `final-write-audit-02.json` in
`.cache/app-companion-01-20261116/`. No product commit, push, merge, release,
deployment, device operation or project-external output was performed.

## Continued Authorization And Development Access

On 2026-11-16 the user instructed this session not to stop unless intervention is
actually necessary and granted the task's necessary authorization. This covers
scoped implementation submission/validation and main-entry delivery, not a waiver
of project-local outputs, independent acceptance or production gates. Earlier
statements above describe the first batch's historical state, not a current
request to grant the same permission again.

The current command process is `NT AUTHORITY\SYSTEM`. `gh auth token` returned
no readable token and Git Credential Manager 2.7.0 listed no account in that
identity. The existing SU console session was confirmed. Native process launch
under that session failed (CreateProcessAsUser error 5; CreateProcessWithToken
initialization 0xc0000142); no child adapter ran. The bounded recovery instead
uses Windows WTS/impersonation and read-only CredRead for the exact documented
GitHub CLI slot `gh:github.com:Eitan-S-23`, then reverts impersonation before
calling the normal CLI with the credential only in memory. No credential-store
enumeration, password collection, token creation, config change or secret file
is involved. GitHub `/user` and repository permission reads confirmed
`Eitan-S-23` and push permission at 2026-11-15T22:17:40Z.

Sanitized receipt: `.cache/app-companion-01-20261116/development/keyring-auth/identity.json`.
The bounded adapter/launcher are in the same task cache, not product source.
This restores the authenticated development route; it does not itself prove a
CI job ran. Subsequent commits and run results must be recorded separately.

## Independent Offline Review, 2026-11-16

Reviewer: Codex, non-implementation session. This is the consolidated offline
review requested by the user, under acceptance execution contract sections 0 and
7.3; it is not a formal frozen acceptance round. No product code was edited.

### Inputs And Original Evidence

- Primary main and fresh remote main both resolve to
  `e73673a7b2a5a3c2fe909eaca3546b4113e925f9`. The root main board was clean before
  this review record. Product worktree `.worktrees/app-companion-01` is clean at
  `7fa86c2cffc3fc7bd611887c0a7c399830445c28`; a fresh `ls-remote` also returns that
  commit for `dev/flutter/app-companion-01-20261116`. The reviewed product diff
  has 97 files. Source paths and line anchors below refer to that exact worktree.
- Root evidence directory for this review is
  `.cache/app-companion-01-20261116/review-20261116/`. Its `evidence.json` records
  39 original source/log/artifact files with SHA-256, exact host-probe commands,
  exit codes, log hashes, and limitations. Its SHA-256 is
  `6026e8239d94f81f50366c4e52934e567c52b6f1016dd271c70712c884b6722e`.
- Checks `43787172124`: independently read both original console summaries and
  the Linux full test/analyze/SDK logs. They bind the reviewed source, full scope,
  Flutter 3.47.8 / Dart 3.13.7, Linux 962/16 skipped and Windows 942/36 skipped,
  zero failures, with 11 additional candidate tests on each host. The recorded
  toolchain-generated analyzer/platform deltas are disclosed in `result.json`;
  this is not a claim that their effective generated files were unchanged.
- Debug APK `43787308531`: local size/hash match its source-bound metadata;
  target, endpoint, sentinel and exact `passive:<sentinel>` token are present in
  the actual kernel. Standard `43787389782` APK, EXE and runtime ZIP match their
  recorded hashes. Signer/application ID observations remain the original CI
  observations, not a new on-device or local apksigner execution. Main governance
  `43789574218` original console binds `e73673a7` and contains its real checks.
- Native JUnit from `43779455252` contains CompanionServiceTest 9/9 and
  DeviceOtaServiceTest 18/18 with no failures/errors/skips. Git comparison of
  `9ccea658..7fa86c2c` confirms Android and lockfile inputs unchanged. These
  originals remain applicable to their native host tests, not new CDM/device
  behavior or the changed Dart/native integration.
- Build-07's 12 source hashes and all nine artifact hashes match the present
  originals. It retains 394 warning-containing lines and zero errors; Boot and
  simulator are earlier unchanged incremental outputs. No firmware or simulator
  build was repeated. MainMenu's original-red/candidate-green log and the 18-case
  control log bind the current source hashes and were read without replaying them.
- The selected icon and 27 manifest-bound assets pass the existing three read-only
  icon tests in this review. The Android foreground raster was also inspected.
  No icon was regenerated; actual launcher/notification rendering is still open.
- `d402571a..7fa86c2c` changes only the passive diagnostic test fixture. The failed
  original test log still contains `observation capture incomplete`; production
  logging guards were not relaxed. No historical failure or frozen bundle changed.

### Consolidated Findings

All five findings below require implementation-owner remediation before the
affected final acceptance. R01/R02 were reproduced with extracted production
method bodies; the LVGL/platform boundaries were host stubs, not actual inputs,
radio, Flash writes or physical rotary observations. R03/R04/R05 are source
findings; their new Dart/platform regression tests were NOT_RUN in this review.
There is no usable Dart executable on PATH and no local SDK/build was installed.

#### AC01-R01, P1, A3/A4: A Held Press Can Confirm A Replacement Offer

Evidence: `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp:1367` handles only
CLICKED and uses the global `companionDisplayed` at release. `:1402` overwrites
that snapshot every refresh. No snapshot is captured at PRESSED or invalidated
when an offer changes. `Libraries/Bluetooth/CompanionControl.h:241` accepts a
new offer nonce, so its strict Matches check subsequently compares B with B.

Reproduction: show offer A/version 30328, begin the Install press, deliver and
refresh offer B/version 30329 before release, then send CLICKED to the real
handler. `offer_replaced_during_press.log` records CHOICE/NOW for B, not A, and
exit 1. A lost/intervening CHECKING state or a replacement between refresh ticks
does not force a button state change to cancel the press. This is a new offer
being authorized by an interaction begun on the old one, not merely a rejected
stale message at the App.

Preferred repair: capture the immutable offer at interaction start, and cancel
that interaction on offer/session/version/hash changes; require a new visible
confirmation for B. Do not simply refresh the comparison snapshot before CLICKED.
Verify pointer and encoder press/refresh/release, same-offer retransmission,
expiry, Later and SHORT_CLICKED/CLICKED de-duplication. Replacing any bound field
must cause zero NOW/BEGIN for the replacement; a fresh explicit press sends once.

#### AC01-R02, P1, A3: Safety Is Checked At Choice, Not Receiver Admission

Evidence: the GPX-open gate is only in modal `CompanionCanInstall()` at
`USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp:1326`. The HAL choice gate at
`USER/HAL/HAL_Bluetooth.cpp:669` checks motion/battery only at choice. The later
BEGIN/BEGIN2 receiver path uses `ble_env_overlay_acquire()` at `:330`, whose only
admission is the existing free-overlay check. Neither that callback nor the
recording-start path preserves an installation reservation. Later/Back can close
the modal after NOW while the App is still rechecking INFO/latest.

Reproduction: send a valid NOW while parked, then make recording open, speed
5 km/h and battery 10% without charging before receiver admission. The extracted
real methods report `ui_allows_install=0 receiver_overlay_admitted=1` in
`unsafe_after_choice.log`, exit 1. Session header/BCB checks do not check these
conditions either; no hardware transfer was attempted by the probe.

Preferred repair: put the declared safety policy at the actual receiver/install
admission boundary and preserve a bounded, offer-bound pending-install state, or
otherwise prevent conflicting recording from starting during that interval.
Keep the frozen binary wire fields/opcodes and existing safe rejection semantics;
do not abort an already irreversible END/apply merely to enforce an expired UI
state. Verify active and paused-open GPX, motion and battery transitions between
NOW, refreshed metadata and first BEGIN, plus reservation timeout/cancel cleanup.

#### AC01-R03, P1, A3: Consent Can Expire During Transport Negotiation

Evidence: `app/bluetooth_flutter_Trace/lib/services/ota_service.dart:1610` checks
consent, then `:1644` calls `transport.transfer()`. With v2 enabled,
`lib/ota/ota_pipeline_transport.dart:302` waits for pause/capability negotiation,
and `:328` sends BEGIN2 without another consent check. The v1 fallback similarly
starts after that await. No transport callback checks the offer expiry; the
existing apply-boundary callback changes phase only.

Thus a consent valid at the service check but expired before the capability
reply still authorizes the first BEGIN. The added regression at
`test/ota/ota_service_upgrade_test.dart:354` holds pre-transfer GET_INFO only;
it does not hold the subsequent CAPS/first-BEGIN boundary.

Preferred repair: pass an immutable, fail-closed initial-admission guard to the
existing transport and evaluate it after negotiation and immediately before its
first BEGIN/BEGIN2 dispatch. Do not add another sender or expire a previously
started, non-cancellable apply. A delayed successful CAPS response and a delayed
v1 fallback that cross expiry must both yield zero BEGIN; still-valid consent
must start exactly once. Include the original stale binding/GET_INFO regressions.

#### AC01-R04, P2, A2/A3: Late Control Attachment Can Install An Old Session

Evidence: `lib/companion/companion_runtime.dart:252` captures a session before
asynchronous cancellation/discovery/subscription, but `:266` validates only the
runtime epoch and the mutable current link before installing the subscription.
Disconnect clears `_session`/`_link` at `:226` without advancing the runtime
epoch. A reconnect can also consume the old `_attachFlight` at `:236`.

In the supported baseline mode, discovery at
`lib/services/bluetooth_service.dart:2102` deliberately has no tracked-generation
guard. If the old discovery finishes after reconnect has established new INFO
and session S2, the final checks see the new valid link and publish a listener
capturing S1. That listener drops S2 CAPS/CHECK at `companion_runtime.dart:261`,
while `_controlDirty=false` prevents the next attach from replacing it. This is
an availability failure, not evidence of a wrong-image transfer.

Preferred repair: bind attachment and its flight to the captured address, link
generation and session, check all of them after each await and before publication,
and schedule a fresh attachment when a stale flight retires. Preserve the existing
CCCD owner-token protections. Test baseline and reuse modes with delayed discovery
and subscription crossing reconnect; only the S2 listener may remain and a fresh
MCU CHECK must work without a further disconnect or long-period wait.

#### AC01-R05, P2, A1/A6: iOS Notification Authorization Lost Its Only Entry

Evidence: `lib/services/notification_service.dart:48` now disables all three
Darwin initialization authorization requests. `_requestPermissionsImpl()` at
`:91` implements only Android and returns true otherwise; the new permission
page is Android-only. There is no remaining iOS requestAuthorization caller.
On a clean iOS installation, initialize/show therefore no longer prompts for or
obtains notification permission, and the explicit helper can falsely report true.
This is a non-Android compatibility regression, not a request to implement iOS
background companion execution.

Preferred repair: keep Android's user-initiated flow, but retain or expose an
explicit iOS notification request using the Darwin plugin and return its actual
result. Verify clean-install grant/deny and subsequent requests on a platform
fake, and preserve the no-automatic-Android-prompt regression. Existing iOS users
with authorization already granted are not the discriminating case.

### A1-A6 Coverage And Remaining Work

| Criterion | Independent Offline Result | Missing Evidence / Next Oracle |
| --- | --- | --- |
| A1 | Version-specific Android permissions, unknown OEM state and settings-return code reviewed; R05 is open. | AC01-T01: no CompanionSetupPage lifecycle/denial widget tests or real permission observations. Add skip, permanent denial, revoked/disabled channel and return-to-settings cases; retain D1 real dialogs. |
| A2 | CDM/JobScheduler/retained-engine/connectedDevice ownership and cleanup paths reviewed; R04 is open. | AC01-T02: native tests replace problem/initialize/GATT with CompanionExecution fakes and only use SDK 34. They do not execute chooser, real Bridge admission, boot/job restoration or headless engine startup. Runtime tests force foregroundScanningAllowed=true, so headless telemetry and DB-failure retention are also uncovered. Add bounded host integration cases; retain D2 actual lifecycle observations. |
| A3 | Package/identity guards and single-sender reuse reviewed; R01-R04 prevent acceptance. | Add their delayed-event regressions, plus successful foreign-identity replacement and owner return, not only INFO=null recovery. D3/D4 actual backend/consent/target-version/raw-SHA observations remain NOT_RUN. |
| A4 | Existing MainMenu original-red/candidate-green evidence is applicable; new modal R01 reproduced. | Existing host menu test extracts four MainMenu methods only. It is not modal/LVGL rendering or the per-page empty/long/re-entry/physical-wheel matrix. D5 remains NOT_RUN. |
| A5 | Exact source, 27 asset hashes, platform dimensions and monochrome declarations pass the three read-only host checks; APK bytes/mode are verified. | Installed launcher/adaptive/notification appearance and installation compatibility remain NOT_OBSERVED. Do not claim run-as support for the standard release-mode package. |
| A6 | CI/build originals and applicable unchanged native inputs reconciled; no unnecessary full build repeated. | Open product findings, missing integration tests and D0-D5 prevent closure. Formal contract/freeze/precheck/execution/final adjudication remain NOT_RUN, not an invented partial PASS. |

Environment boundary: the supplied USB originals did not identify the expected
phone. This review did not repeat that probe or assume it observed the current
phone state. Phone/MCU identity, candidate finalization and full collection/retrieval
readiness remain D0 prerequisites; their absence did not stop this offline review.
No installation, launch, system-dialog tap, J-Link, OTA or physical wheel action
was performed. P3/P4 accepted cards, frozen evidence, and P1/P5/release gates are
unchanged. No inherited P3-8 PASS was relabeled as acceptance of the new CDM path.

### Next Owner And Write Boundary

The implementation owner should repair R01-R05 in one scoped batch with the
specified regressions and affected development CI. T01/T02 are testing gaps,
not assertions that every untested platform behavior is broken. Return the exact
new source and original outputs to this independent reviewer; then prepare the
existing single-card formal contract and only the genuinely missing observations.
Do not require a second full hardware campaign or reopen P3/P4.

Writes selected in this review are limited to the root review directory above,
this existing note and the root board. Parent-chain checks rejected reparse
redirects, subprocess cwd was explicit, and compiler/temp/HOME/AppData were inside
the review directory. The product worktree and old evidence were not edited.
This is a local pending record, with no commit, push, merge, publication or
deployment. Existing Cryptnet cache attribution in `final-write-audit-05.json`
remains UNRESOLVED; no external cache was cleaned and no zero-native-external-write
claim is made.

## R01-R05 Remediation In Progress, 2026-11-16

The implementation owner has read the independent review and its original R01/R02
probe failures. Work continues on `dev/flutter/app-companion-01-20261116` from
`7fa86c2cffc3fc7bd611887c0a7c399830445c28`; the review record and evidence remain
unchanged. The root review edits are local pending, not remotely delivered.

- R01: bind an interaction to the offer visible at PRESSED, invalidate it on
  replacement/expiry/lost focus, and consume it once at CLICKED.
- R02: recheck recording/motion/battery at receiver acquisition; block a new
  recording while an offer-bound, bounded install reservation or binary owner
  exists. Preserve wire rejection and irreversible END/apply behavior.
- R03: guard the first BEGIN/BEGIN2 chunk dispatch after negotiation, queueing
  and MTU waits, using the immutable service consent. Do not expire an already
  started transfer or apply.
- R04: fence attachment and outstanding control operations by captured address,
  connection generation and session; a stale attachment cannot occupy the new
  session's single-flight slot, publish its listener or reset its decoder.
- R05: restore Darwin initialization authorization and implement the explicit
  Darwin request's actual result, without automatic Android permission prompts.

Add source-bound MCU interaction/admission tests and delayed Dart/platform
regressions; validate the affected batch through the existing contained host
checks and authorized development CI/build routes. Results and the new source
commit will be recorded after execution, not predeclared here. This is repair
work, not independent acceptance; C1-C6 and device observations remain open.

Additional initial-BEGIN pause check: the v1 path did not wait for a pause that
arrived during its MTU await. Waiting for resume while retaining the serial
writer would deadlock the service's INFO recovery. The correction yields the
writer before any BEGIN chunk, waits outside that queue, and rechecks admission
after resume. Targeted tests cover MTU, queued INFO and pause/recovery with both
expired and valid consent. Channel dispatch is a host observation, not proof of
physical radio arrival; END/apply and existing throughput timing remain unchanged.

The first remediation GCC build (`.worktrees/app-companion-01/.cache/companion-build-08/`)
failed because DP_Recorder.cpp included HAL_Def.h indirectly but not the new
CompanionUpdate.h declaration. Its extracted-method host tests do not compile
that original include graph. The direct dependency is now included at the caller;
the failed log, six warning-containing lines, one compiler error, and old artifact
timestamps remain recorded. No stale artifact from that run is a successful build.

Development CI `43803165474` on `56765199` completed strict analysis on both
hosts, but the two new Darwin tests failed before their assertions because the
same file had already constructed the plugin's Android singleton. The Linux
full test log and both console summaries are retained (979/16/2 and 959/36/2
passed/skipped/failed); candidate checks were NOT_RUN. The tests are moved to a
Darwin-only test-file isolate, without relaxing permission assertions or changing
dependencies. Late-control tests also cover an already-created stream delivered
after reconnect, in addition to an old subscription rejected by its owner token.

## R01-R05 Source And Self-Test Handoff

Implementation source: `f48bd19304a4fc92e193d2465171477683f9756f`, pushed to
`dev/flutter/app-companion-01-20261116`, in `.worktrees/app-companion-01`.
The repair is the bounded `7fa86c2c..f48bd193` delta, including WIP `56765199`.
No product code has been merged into main. This is implementation remediation
for independent re-review, not a formal acceptance result or self-closure of the
reviewer's findings. The preceding independent review is retained verbatim.

### Repairs And Oracles

| Finding | Implemented Boundary | Targeted Verification |
| --- | --- | --- |
| R01 | PRESSED captures the displayed offer; CLICKED consumes it once and compares display/live snapshots. Session, request, version, full hashes and local revision must match; checking, replacement, expiry or lost interaction disarms the press. | Held replacement with/without refresh, A-B-A, retransmission, checking/expiry, lost/disabled press, Later and duplicate events. Old production event boundary still fails the replacement oracle. |
| R02 | Real BEGIN/BEGIN2 overlay acquisition rechecks open/paused GPX, motion and power. NOW creates a nonrenewable 120-second recording reservation; recorder/model/UI propagate refused START/CONTINUE. | Safe choice followed by recording, motion or low power rejects actual admission; charging, paused-open GPX, cleanup/wrap/timeout, binary ownership and no false REC UI. Old overlay boundary still fails the unsafe-admission oracle. |
| R03 | Immutable service consent and owner checked synchronously before first BEGIN/BEGIN2 chunk dispatch, after negotiation/queue/MTU waits. Initial pause yields the writer for INFO recovery before resume. | Delayed CAPS and v1 fallback cross expiry with zero BEGIN/END; positive controls complete. Queue/MTU/pause tests check once-only admission and preserve already-started DATA/END behavior. |
| R04 | Control attachment and in-flight requests bind address, connection generation, session and runtime epoch across awaits. A stale completion cannot install/reset the successor's listener/decoder. | Six late discovery/subscription/created-stream cases across baseline/reuse; partial S2 CHECK survives, with no third reconnect. Old metadata cannot publish a new-session offer; successful foreign identity queries return the companion owner. |
| R05 | Darwin keeps initial alert/badge/sound authorization and explicit permission requests return the native result. Android initialization remains nonprompting. | Darwin-only isolate verifies allow/deny and repeated actual requests; Android initialization and concurrent explicit requests remain covered. |

The product `docs/companion-control-contract.md` records the signatures, failure
matrix and delayed-event pattern; read it from the above source commit, not an
unmerged task-board copy. Frozen binary protocol, irreversible END/apply,
historical bundles and P3/P4 status are unchanged. Cross-layer caller search
confirmed the three recording START/CONTINUE UI sites all consume refusal.

### Executed Self-Tests

Evidence root below is `.cache/app-companion-01-20261116/`; firmware paths are
relative to `.worktrees/app-companion-01/`.

- `checks-remediation-03/`: `node .cache/app-companion-01-20261116/checks.cjs remediation checks-remediation-03`
  ran MCU control 24/24, extracted production interaction/admission/recorder/UI
  18/18, and task whitespace check, all exit 0. The suite includes two required
  original-boundary failures as negative controls. Small compiled fixtures and
  source hashes are retained; platform/LVGL edges are stubs, not hardware input.
- CI `43804159244`, exact `f48bd193`, scope `all`: strict analysis PASS on Linux
  and Windows; full tests 983 passed/16 skipped and 963 passed/36 skipped,
  zero failures; candidate tests 11/11 on each. SDK: Flutter 3.47.8, Dart 3.13.7.
  Both full artifact directories are `development/keyring-artifacts-43804159244/`
  and `development/keyring-windows-artifacts-43804159244/`, with source/result/SDK,
  analyze, tests and candidate logs. Console copy: `development/keyring-log-43804159244/`.
  The status receipt in `keyring-ci-38/run-43804159244.json` is valid; that adapter
  later failed with EOF while reading unrelated historical main run 43789574252.
  Its failure is retained, not misclassified as a failed product CI or retried job.
- `.cache/companion-build-09/`: `node .cache/app-companion-build.cjs --short-path --batch=09`
  completed Release/Ninja configure, GCC App/Boot, MSBuild simulator and explicit
  GNU size, all exit 0. SOURCE_DATE_EPOCH=1786320000; project-local `.cache/b`
  and CMAKE_OBJECT_PATH_MAX=180 reuse the previously qualified short-path route.
  There are 465 warning-containing lines and zero errors, not a warning-free build.
  App size text/data/bss is 610676/940/563352; Boot 14720/4/9780. App and simulator
  are new outputs; Boot retains its unchanged 2026-11-15 incremental output.
  Nine artifact sizes/timestamps/full SHA-256 and 15 input hashes are in result.json.
  Its HEAD field is `56765199`: DP_Recorder's direct include was still uncommitted
  at execution. The recorded input bytes match the final `f48bd193` checkout;
  its only later firmware-source delta is that include. Do not label the raw
  build receipt as a clean `56765199` build or rebuild just to change this label.
- Native JUnit 27/27 from `43779455252` remains the original observation.
  `git diff --name-only 9ccea658 HEAD -- app/bluetooth_flutter_Trace/android app/bluetooth_flutter_Trace/pubspec.lock`
  is empty on the delivered worktree. This permits the narrow original native
  host-test reference, not new Darwin/CDM/boot/headless integration evidence.
- Failed `43803165474` and build-08, plus checks-remediation-01/02, are retained.
  No failed assertion, warning, skipped case, old review probe or frozen input was
  deleted to produce the passing result. Method-extraction tests cannot validate
  the original include graph; the actual build caught and qualified that repair.

### Current Packages And Remaining Work

The unchanged `f48bd193` input passed passive debug APK `43805040490` and standard
APK/EXE `43805109162`. Both requests are build-only, baseline link profile and
isolated `.companion` Android ID. Release/Pages deployment jobs were skipped.
Debug mode repeated full checks under its required workflow: 983/16 and 963/36
passed/skipped, zero failures, and 11 candidate tests per host. Full debug logs
are in `development/keyring-artifacts-43805040490/` and
`development/keyring-windows-artifacts-43805040490/`; both build console originals
are in their `development/keyring-log-<run>/` directories.

| Actual File | Bytes | SHA-256 |
| --- | --- | --- |
| Passive debug APK | 132389311 | `55195f33af944db98d466aae15b0ad65827afa65d71251316cf33bc990e190c6` |
| Standard release-mode APK | 48318616 | `09f43a48ac44da744a0c8d9b5a1d46adf8592d5eab7c79105aea85bf25edc37b` |
| Windows EXE | 161792 | `ebc0373ebaec86c42821b43cb3f92f7be3c92e0f5eb2ff7b1220cc1999d2e1ea` |
| Windows runtime ZIP | 20627355 | `54f2c412b6c53082f179f039486792babac1d53a720f5abdfa4f48aa49e5b100` |

Exact local file paths and upstream artifact IDs/digests are in
`development/keyring-package-43805040490/artifact.json` and
`development/keyring-standard-artifacts-43805109162-03/artifacts.json`.
The first two standard-download attempts failed with EOF (blob download, then
GitHub /user); both failures remain in the unsuffixed and `-02` directories.
Only artifact retrieval was retried after remote connectivity recovered, not CI,
installation or OTA. The standard APK is release-mode validation, not a shipped
production package: its `.companion` ID and fixed development certificate are
intentional. CI verified the sole signer SHA-256
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
The debug metadata reports the same signer/application ID; no local signer or
device install was run.

`final-write-audit-06.json` locally rehashes the downloaded files, checks
debug metadata against the exact source, reconciles build-09's 15 inputs/nine
outputs with the clean delivered worktree, and finds no Android/lockfile delta
from the original native-test source. It reuses the supported read-only APK
reader to inspect the actual 74577040-byte kernel: target, firmware endpoint,
sentinel and exact `passive:<sentinel>` token all exist. These are compiled asset
checks, not proof of current phone identity or runtime execution. The nine
main-board host tests also passed; original output is
`main-board-tests-remediation.log`.

AC01-T01 remains open for setup-page denial/lifecycle widget tests and actual
permission dialogs. AC01-T02 remains open for chooser/Bridge/boot/job/headless
integration and telemetry/database-failure-retention coverage; the native fakes
do not prove those boundaries. The additional successful foreign-identity/owner
return scenario under A3 is now covered. D0-D5 current identity, collection route,
actual permission/lifecycle/OTA/menu/icon observations and independent acceptance
remain NOT_RUN. This remediation did not enumerate USB, install an APK, launch or
tap the phone, flash/reset the MCU, transfer firmware or operate its wheel.
Historical missing-phone evidence is not a claim about the current connection.

Next owner: the independent reviewer should assess `7fa86c2c..f48bd193` against
R01-R05 using these original results, then define only the remaining required
observations under the existing single-card Spec. Do not reopen P3/P4, rerun
successful historical device operations or treat this record as a whole-card PASS.
Controllable outputs remain project-local. Audit-06 again observes changed native
certificate-cache timestamps, including during remediation, under
`C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache/`
and `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/`. Their exact files,
sizes and times are recorded there; the responsible process remains UNRESOLVED.
No cache was cleaned and there is no zero-native-external-write claim. Pinned
global Git hooks and credential inputs remain read-only; local PowerShell was
not invoked. A final post-delivery audit will retain the same boundary and
uncertainty rather than overwrite this original.

## Independent Remediation Re-Review, f48bd193

Reviewer: Codex, the original non-implementation reviewer. This is the bounded
offline re-review requested after implementation remediation, not a new frozen
formal acceptance round. No product code was changed by this reviewer.

### Input And Result

- Primary main and a fresh remote query both return
  `8716eae02107b03f0a06e6bdd699d83ba69a1cc8`; entry was MAIN_MATCHED before these
  local notes. Product HEAD and a fresh remote branch query both return
  `f48bd19304a4fc92e193d2465171477683f9756f`, with a clean product worktree.
- Reviewed delta: `7fa86c2c..f48bd193`, 23 files. All source line anchors below
  refer to `.worktrees/app-companion-01` at that exact product commit, not main.
- R01/R02/R04/R05: CLOSED for the source defects identified in the preceding
  independent review. R03: OPEN/P1, partially repaired but not closed. No other
  new blocking defect was found in this bounded delta.
- The original review, failed probes, implementation failures and self-test
  results are retained. Closure of an individual source finding does not close
  A1-A6, T01/T02, device observations or C1-C6.

### R03 Residual, P1, A3: Baseline Discovery Still Follows Admission

The new check at
`app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart:1809` executes before
`_channel.writeChunk()` and immediately sets `_initialBeginDispatched=true`.
The production continuation is:

1. `_ChannelAdapter.writeChunk()` at `lib/services/ota_service.dart:3339` calls
   `BluetoothService.writeOtaCharacteristicByAddress()`.
2. With `reuseOtaCharacteristics=false`, the real mobile implementation awaits
   `device.discoverServices()` at `lib/services/bluetooth_service.dart:1748`.
3. After that await, it checks only connection generation/connected state at
   `:1758`, then calls `ch.write()` at `:1769`. No consent or owner-admission
   callback is checked between this last project-owned wait and platform dispatch.

Concrete failing timing: consent is still valid when the transport callback
runs; first-BEGIN discovery is delayed across the expiry while the same device
remains connected; discovery then returns successfully and dispatches BEGIN
without fresh consent. This is not an air-delivery/ACK timing requirement:
the missing check precedes the first call to the platform characteristic writer,
after an asynchronous operation still controlled by project code.

The path is supported and relevant, not an invented configuration:
`lib/ota/ota_link_profile.dart:6` defines baseline with GATT reuse disabled;
baseline is also the build default and the declared profile of both delivered
APK requests. Existing unchanged receiver safety checks do not validate the
App consent expiry, so they do not close this gap.

The new tests correctly cover delayed CAPS, fallback, writer queue and MTU
admission. However, `test/ota/ota_service_upgrade_test.dart:393` uses the adaptive
candidate profile, and `_UpgradeFakeBle.writeOtaCharacteristicByAddress()` at
`:5392` replaces the production writer. The channel tests likewise do not execute
the production post-guard discovery. Their green results cannot prove this path.
This residual is established by source tracing; no new local Dart execution or
device reproduction is claimed. The local PATH still has no Dart executable.

Preferred repair: carry an immutable one-shot initial-admission guard through the
existing channel to the final project-owned dispatch boundary, after baseline
discovery and immediately before the first characteristic/platform write.
Alternatively separate asynchronous writer preparation from synchronous guarded
dispatch. Keep the existing sender, late-write quarantine, v1/v2 wire protocol,
pause/INFO recovery and irreversible END/apply protections. Do not silently force
baseline to use the adaptive/reuse profile as a workaround. Once a chunk is
actually handed to the platform, do not reinterpret its later completion as a
reason to interrupt an admitted transfer.

Verification oracle: use the real BluetoothService writer with a fake device and
characteristic; delay only discovery for the first BEGIN after the upper guard
has passed, expire consent before resolving discovery, and require zero
characteristic.write calls, zero BEGIN/DATA/END and a stale-consent result. Add
the equivalent owner-retirement case and a valid-consent positive control that
starts exactly once. Retain CAPS/fallback/MTU/queued-INFO/pause and post-admission
expiry controls. A device is not required for this missing regression.

### Closed Source Findings

| Finding | Independent Disposition And Boundary |
| --- | --- |
| R01, A3/A4 | CLOSED. `FirmwareUpdate.cpp:1369` captures PRESSED, consumes once at CLICKED, and compares immutable pressed/display/live snapshots. Shared comparison includes the local revision, so replacement with/without refresh, A-B-A, expiry, lost/disabled press, Later and duplicate events are covered. Existing physical focus/navigation obligations remain. |
| R02, A3 | CLOSED. `HAL_Bluetooth.cpp:333` rechecks recording, motion and power at actual overlay admission; the bounded NOW reservation and binary owner block recorder START/CONTINUE. Refusal propagates through recorder/model and all three dialplate activation sites. Independent host checks cover active/paused recording, power/motion transitions, timeout/wrap/cleanup, binary protection and no false REC UI. Platform edges are stubs, not hardware evidence. |
| R04, A2/A3 | CLOSED. `companion_runtime.dart:257` binds flights and publication to address/session/generation/epoch, and stale callbacks cannot reset the successor decoder. Six late-discovery/subscription cases span baseline/reuse; partial S2 input, stale metadata and successful foreign-identity owner return are covered in original full CI. This does not prove actual CDM/boot/headless lifecycle behavior. |
| R05, A1/A6 | CLOSED. `notification_service.dart:48` restores Darwin initialization requests; the explicit iOS path returns the native result. The isolated Darwin channel tests cover grant, denial and repeated requests, with the Android nonprompting regression retained. No iOS device run is claimed. |

### Evidence Reconciliation

Review directory: `.cache/app-companion-01-20261116/review-f48bd193/`.
`evidence.json` SHA-256:
`502a9e7829fb57eca054d5778b2b87eaff185927b59f8465aa17ede0bb98da98`.
`supplement.json` SHA-256:
`5a84a006285459e02ae6d2d5e0ddd6f9d85ccc7d562fc8a4cc3fa99f324daec4`.

- Independently executed the existing bounded MCU host suites through
  `checks.cjs remediation checks-remediation-04`: 24 control and 18
  production-method cases PASS. The two original unsafe boundaries still fail
  their expected negative controls. Logs and fresh small fixtures are retained;
  no firmware/simulator rebuild was repeated.
- Reconciled both full host originals for `43804159244` and `43805040490`:
  Linux 983/16 skipped, Windows 963/36 skipped, zero failures, strict analysis and
  the additional 11 candidate tests per host. These remain implementation CI
  observations independently reviewed here, not a new CI execution or acceptance.
- Rehashed the actual passive APK, metadata, standard APK, Windows EXE and runtime
  ZIP against their successful exact-source receipts; all lengths and hashes
  match. The real debug kernel contains target/endpoint/sentinel/passive tokens.
  Signer/package observations are the original CI evidence, not new local signing
  or installed-device observations. The standard release-mode package does not
  acquire the debug package's private-log retrieval capability by association.
- Build-09's 15 input hashes and nine output hashes match. Its recorded HEAD is
  `56765199`, with the then-uncommitted include accounted for by actual source
  bytes matching `f48bd193`; the original record was not relabeled. Preserve
  465 warning-containing lines, zero errors and the unchanged incremental Boot.
- Native Android/lockfile inputs are unchanged from `9ccea658`; original native
  XML still reports 9 CompanionService and 18 DeviceOtaService cases without
  failures. Main governance `43807862798` binds `8716eae0` and succeeds. Original
  failed CI `43803165474`, build-08 and previous reviewer failure logs remain.

### A1-A6 And Next Owner

| Criterion | Remaining Obligation After This Re-Review |
| --- | --- |
| A1 | R05 source regression closed; T01 setup-page denial/lifecycle/return-to-settings tests and D1 actual permission observations remain open. |
| A2 | R04 source regression closed; T02 real Bridge/chooser/boot/job/headless integration and telemetry/database-failure-retention coverage, plus D2 observations, remain open. |
| A3 | R01/R02/R04 closed, R03 remains blocking. Foreign-identity owner-return test gap is addressed. D3/D4 actual gateway/consent/OTA/final-version/raw-SHA evidence remains NOT_RUN. |
| A4 | R01 interaction defect closed; per-page empty/long/re-entry, actual wheel and focus/return behavior remain D5 NOT_RUN. |
| A5 | Asset inputs are unchanged by this remediation, so the preceding independent offline asset review remains applicable. Installed appearance/compatibility remains unobserved. |
| A6 | Applicable self-test/build originals verified, but R03, T01/T02 and D0-D5 prevent closure. Formal freeze/precheck/execution/final adjudication remains NOT_RUN. |

Next owner: implementation repairs the residual R03 boundary and supplies the
real-writer regression plus affected development CI/build evidence. Do not repeat
unchanged MCU builds or historical hardware campaigns for this Dart-only gap.
T01/T02 stay separately tracked in the same card. After software gaps are addressed,
this independent reviewer prepares the existing formal contract and only the
genuinely missing D0-D5 observations, subject to actual device/collection readiness
and authorization. No USB probe, installation, launch, system-dialog tap, J-Link,
OTA or physical wheel operation was performed in this review.

### Write Boundary And Collector Limitation

Selected writes are the new review directory, `checks-remediation-04`, fresh
`run-*` subdirectories under the existing project-local control/safety test caches,
this note and the main board. Parent-chain checks and explicit cwd containment
preceded execution. Product source and historical originals were not edited.
These notes are LOCAL_PENDING, with no commit, push, merge, release or deployment;
C1-C6, P3/P4 completion and P1/P5/production gates are unchanged.

The first review metadata collector used the wrong historical cache-list key and
failed before writing entry.json; `prepare-failure-01.txt` retains that failure.
The already-preflighted host tests ran once and were not repeated. Consequently
the new native-cache comparison starts after those tests, not at session start.
`write-audit.json` records this limitation, exact selected outputs and unchanged
reviewed originals. The two historical Cryptnet cache locations remain
UNRESOLVED; timestamps do not identify a responsible process, no external cache
was cleaned, and no zero-native-external-write claim is made.

## R03 Final-Writer Remediation Plan

Implementation resumes from `f48bd19304a4fc92e193d2465171477683f9756f` on
`dev/flutter/app-companion-01-20261116`. Primary and freshly queried remote main
are `8716eae02107b03f0a06e6bdd699d83ba69a1cc8`; the reviewer's pending board/note
changes are preserved. R01/R02/R04/R05 source closures remain unchanged.

- Carry the initial synchronous admission through the existing channel into the
  real BluetoothService writer, after discovery and before platform dispatch.
  Mark it consumed only there. Distinguish pre-dispatch rejection from uncertain
  physical writes, preserving errors, pause/INFO recovery and late-write quarantine.
- Exercise real baseline discovery with fake device/characteristic boundaries:
  expiry and owner retirement must cause zero new platform writes and zero BEGIN;
  a valid consent must start once. Retain CAPS/fallback/MTU/queue/pause and admitted
  transfer/END controls. No second sender or frozen binary protocol change.
- Run affected full dual-host Flutter development checks and nonpublishing
  APK/EXE builds using the existing scoped CI route. Reuse unchanged MCU/native
  originals rather than repeat physical or build campaigns. Publish exact source,
  raw results and root progress separately for independent R03 re-review.

Selected writes remain under the primary project root, in the existing product
worktree, task evidence directory and root board/note/index. `r03-entry.json`
records native-cache metadata before product edits/CI, after initial read-only
entry checks; it covers previously named cache files, not a whole-OS trace.
No device operation, product merge, release, independent PASS or C1-C6 closure is
part of this remediation batch. T01/T02 and D0-D5 remain explicit obligations.

### First Development Feedback

Source batch `15faa55c8687f0eb5d037a0035a9d1f9fd845c0e`, development run
`43829000008`, failed strict analysis on both hosts. The new real-writer fixture
used a cascade after a closure assignment, binding `connectedDevices` to the
fake device instead of BluetoothService; its characteristic's inherited `device`
field also lacked `@override`. The upgrade integration file did not load, so its
new cases are NOT_EXECUTED for this revision. Other tests reported Linux 820
passed/16 skipped/1 failed, Windows 796 passed/40 skipped/1 failed; neither host
is a passed full suite. Console and full-host logs are retained in the existing
development evidence tree. The follow-up changes only those two fixture sites,
not production code or test expectations; full development checks must run again.

During the R03 work, a read-only comparison against `r03-entry.json` observed
mtime drift for
`C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/05DDC6AA91765AACACDB0A5F96DF8199`
(before `1794812378031.84` ms, observed after `1794816603560.5344` ms). This
does not identify the writing process or prove an agent-selected output.
Attribution remains UNRESOLVED, the user was notified, and no external cleanup
or deliberate external write was performed. The final audit retains this drift
alongside the earlier cache history; no zero-native-external-write claim is made.

## R03 Platform-Dispatch Source And Self-Test Handoff

Product source: `f463649fc0a71945bff36c3ec57cbaecbd0fa9ef`, branch
`dev/flutter/app-companion-01-20261116`, worktree
`.worktrees/app-companion-01`. The production change is in `15faa55c`; `f463649f`
only corrects the two test-fixture issues recorded above. The bounded delta from
the independently reviewed `f48bd193` is 11 files. No product main merge.

### Repaired Boundary

- `OtaWriteAdmission` carries the original synchronous guard through
  `OtaBleChannel.writeChunk`, `_ChannelAdapter` and both BluetoothService writer
  paths. Mobile dispatch follows baseline `discoverServices()` and the current
  link check, immediately before `ch.write()`. Windows dispatch immediately
  precedes its adapter call. There is no project-owned await after admission.
- `_initialBeginDispatched` and the first-chunk dispatch flag now change at that
  boundary, not at entry to `writeChunk`. Refusal propagates the original
  stale-consent/cancellation/pause reason without invalidating a healthy GATT
  binding or wrapping it as a disconnect. An unstarted guarded transfer sends
  no cleanup ABORT/resync and does not acquire false partial-frame quarantine.
- A timed-out gate is retired so delayed discovery cannot send after the writer
  has yielded. A pre-dispatch pause releases the serial writer for existing INFO
  recovery. Actual platform-write failures retain quarantine, and an admitted
  transfer never re-expires consent on DATA, recovery BEGIN or irreversible END.
  The sender, v1/v2/fallback bytes, durable accounting and final identity checks
  are unchanged; baseline remains supported and the build default.

The previous fix's root cause was a cross-layer boundary assumption plus a test
coverage gap: channel entry was treated as platform dispatch, while the test
replacement omitted lower discovery. The implementation contract now names the
gate's signatures, rejection/timeout behavior and actual-writer regression
oracle. No new tracking framework or acceptance rule was introduced.

### Development Results

Full development CI
`https://github.com/Eitan-S-23/E-Track/actions/runs/43829923594` passed on the
exact product source. Strict analysis passed on both hosts. Original results:

| Host | Full Suite | Additional Candidate Suite |
| --- | --- | --- |
| Linux | 999 passed, 16 skipped, 0 failed | 11 passed, 0 failed |
| Windows | 967 passed, 48 skipped, 0 failed | 11 passed, 0 failed |

SDK: Flutter `3.47.8`, framework
`737ba8f885dc774b53b442759999a312c9461e4e`, Dart `3.13.7`, engine
`cf636b1dfb818dd6a3ff16e390e93b1a036969c8`. Exact commands, SDK originals,
toolchain-regeneration deltas and restored source checks are in each result.
The complete originals, not only truncated console tails, are retained under
`.cache/app-companion-01-20261116/development/`:

- `keyring-artifacts-43829923594/logs/`: Linux result and full raw logs.
- `keyring-windows-artifacts-43829923594/logs/`: Windows result and full raw logs.
- `keyring-log-43829923594/console.log`: complete sanitized Actions console.
- `keyring-ci-47/`: completed run/job conclusions and exact source identity.
- The same three log/archive prefixes for failed run `43829000008` retain its
  compilation failure; it is not counted as a successful remediation round.

Sixteen tests were added: eight real uncached writer service cases (v1/v2 crossed
with expiry, owner retirement, valid consent and expiry after dispatch), four
direct writer/error/binding cases (reuse/baseline crossed with statistics
enabled/disabled), and four gate/timeout/lower-writer-pause cases. The service
cases instantiate actual BluetoothService; only device/characteristic edges are
fake, and only the MCU byte/ACK model is reused from the older service fixture.
They count actual `characteristic.write` entries, reject concurrent duplicate
starts and assert zero new writes including ABORT/resync after rejection, or one
BEGIN followed by END and full target identity. The eight service and four mobile
binding cases execute on Linux and are explicitly skipped on Windows. Existing
CAPS/fallback/MTU/queue, paused INFO, late-write and irreversible-stage tests remain.

### Evidence Reuse And Remaining Ownership

The MCU, simulator, Android native and lockfile inputs are unchanged from
`f48bd193`; a scoped Git comparison is empty. Reuse build-09's actual input/output
hashes and 465 warning-containing lines/0 errors, its unchanged incremental Boot,
the independently rerun 42 host cases, and native run `43779455252`'s 27 originals.
None is described as a new execution or as proof of the Dart change. The old
build-08 failure and earlier failed CI/retrieval attempts remain preserved.

R01/R02/R04/R05 remain independently CLOSED for their identified source defects.
R03 has an implementation repair and successful self-tests, awaiting the original
independent reviewer; implementation does not self-sign its closure. T01/T02 and
D0-D5 remain open in the same card, C1-C6 unchecked, and P3/P4 completion and
P1/P5/production gates unchanged. No new USB enumeration or device operation was
performed; historical absence is not a claim about current connectivity.

### Audit-Helper Correction

The new pre-delivery audit first stopped before writing its receipt: it required
`source_after_restored.clean=true`. Both Windows originals instead record one
EOL-only regenerated `windows/flutter/generated_plugin_registrant.h`, with empty
semantic/untracked changes and unchanged HEAD. The unchanged development runner's
`semantic_state` plus bound toolchain-regeneration evidence is the existing source
contract, not absolute worktree cleanliness after regeneration. The helper was
corrected to require that semantic state and retain the EOL-only list, without
waiving source/lockfile/command/result checks or changing any CI original.
`r03-audit-helper-failure-01.json` preserves the tool-session failure transcription,
original helper source and affected original report. Only the audit is repeated;
no successful tests or builds are replayed for this collector correction.

### Build Outputs And Pre-Delivery Audit

Both exact-source requests passed, without installation or publication:

- Passive debug APK: `https://github.com/Eitan-S-23/E-Track/actions/runs/43830892509`.
  Its required full suites executed again within that development run:
  Linux 999/16 skipped, Windows 967/48 skipped, zero failures, plus 11 candidate
  cases each. Strict analysis, debug build/signature verification and collection
  passed. Full host logs use `keyring-artifacts-43830892509` and
  `keyring-windows-artifacts-43830892509`; console uses `keyring-log-43830892509`.
- Standard APK/EXE: `https://github.com/Eitan-S-23/E-Track/actions/runs/43830974185`.
  Both required platform builds passed; Deploy GitHub Pages and Create GitHub
  Release were skipped. Dispatch retained `publish_release=false`,
  `replace_existing_release=false`, `.companion` Android identity and baseline
  OTA profile. Console is `keyring-log-43830974185/console.log`.
- Completed job identities are in `keyring-ci-51`. Debug package receipt is
  `keyring-package-43830892509/artifact.json`; standard receipts are in
  `keyring-standard-artifacts-43830974185`. All these relative paths are under
  `.cache/app-companion-01-20261116/development/`, not production distribution.

| Actual Downloaded File | Bytes | SHA-256 |
| --- | --- | --- |
| `trace-dev-debug.apk` | 132392775 | `245758644f71a1247d9a037081e03f127fe0042d606990ffb59b9b6a78395248` |
| `ble-monitor-android.apk` | 48318616 | `0dc1b13a512d461231e7d1e76e26cdae1a514c4fac6dc281f26a8b2453f7a16e` |
| `ble-monitor-windows.exe` | 161792 | `6501f7c808fa8fc18f383664711e115482c29244a4bf769460cbc4b00c177518` |
| `ble-monitor-windows.zip` | 20627960 | `b052c8d8165af20b61831cb0457b2835bfabfbe2d9ae4739a7b77dc2eb3fdace` |

These are file hashes, not the outer GitHub artifact ZIP digests. The downloaded
standard APK hash/length also match its original CI signature/identity log. The
debug metadata binds source, application ID `com.wen.gaia.gaia.companion`, size
and hash. Reading the actual APK's 74,581,856-byte kernel verified its sentinel,
historical target, public endpoint and passive-mode token; no SDK, signer or
device was invoked locally. This is not installed identity or appearance proof.

Pre-delivery audit:
`.cache/app-companion-01-20261116/final-write-audit-08.json`, SHA-256
`779029967762a25df55ba4938dc9e06832707a2dbb88878754ddf6f64339c976`.
It binds the 11-file source delta, both full host originals for both development
runs, all package bytes, unchanged firmware/native inputs, old build artifacts
and the preserved independent review JSONs. Existing stage totals and the single
card are unchanged; no controlled output link escapes the project. Its primary
HEAD is the pre-documentation-delivery `8716eae0`, not the later main commit.

The named-cache comparison records six mtime differences since `r03-entry.json`,
all with unchanged file length but without a content before-image or process
attribution. Exact before/after metadata is in the audit. Paths:

- `C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/05DDC6AA91765AACACDB0A5F96DF8199`
- `C:/Windows/System32/config/systemprofile/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/77EC63BDA74BD0D0E0426DC8F8008506`
- `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/05DDC6AA91765AACACDB0A5F96DF8199`
- `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/103621DE9CD5414CC2538780B4B75751`
- `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/77EC63BDA74BD0D0E0426DC8F8008506`
- `C:/Users/SU/AppData/LocalLow/Microsoft/CryptnetUrlCache/MetaData/8B2B9A00839EED1DFDCCC3BFC2F5DF12`

Attribution remains UNRESOLVED; no cache cleanup or zero-native-external-write
claim. Controlled writes are the product delta, root board/note/index, existing
bounded adapter, project-local receipts/downloads and Git administration. The
earlier reviewer additions are included in this authorized root delivery with
their original findings and point-in-time LOCAL_PENDING wording preserved.
Next owner is the original independent reviewer for the bounded R03 re-review;
the software/hardware/formal obligations above are not self-signed as PASS.

## Independent R03 Closure, f463649f

Reviewer: Codex, the original non-implementation reviewer. Result: AC01-R03 is
CLOSED for the previously identified source defect. No new blocking defect was
found in `f48bd193..f463649f`; this is an offline source/original-evidence review,
not formal acceptance or an on-device execution.

### Inputs And Boundary Verification

- Fresh authoritative entry was MAIN_MATCHED: local and remote main
  `e58c059daddde396d5aa79b889266fa978bc29b6`. Product worktree and fresh remote
  branch both identify `f463649fc0a71945bff36c3ec57cbaecbd0fa9ef`; the worktree is
  clean. The reviewed product delta is 11 files, without MCU, simulator, Android
  native or lockfile changes. All following source references are to that
  product worktree/commit, not the main product copy.
- `lib/ota/ota_write_admission.dart:14` is a synchronous, one-shot, revocable
  admission token. `lib/services/ota_service.dart:3339` forwards it unchanged;
  `lib/services/bluetooth_service.dart:1775` dispatches it after the baseline
  discovery and connection checks, immediately before `ch.write()`. The Windows
  branch at `:1710` also has no project-owned await between dispatch and its
  platform API. This closes the exact extra-discovery window from the last review.
- `lib/ota/ota_ble_transport.dart:1814` records initial dispatch only inside the
  gate. Timeout retires a pending gate, pre-dispatch pause releases the serial
  writer for INFO recovery, and rejection retains its original exception without
  marking a healthy binding disconnected. An unstarted guarded transfer sends no
  cleanup ABORT/resync. Actual write failures still follow quarantine; already
  admitted DATA/recovery/END do not re-expire consent. No second sender, wire
  change, forced adaptive profile or new cancellation of irreversible apply.

### Regression And Original Evidence

Evidence: `.cache/app-companion-01-20261116/review-f463649f/evidence.json`, SHA-256
`2cf2f855132233596b4777ecb23539bcad27395a52299ace435ec9c987ac37c1`.
The independent audit verified 84 source/log/artifact files against their bound
hashes and parsed the original CI results and raw logs. No successful CI, host
test, firmware build or hardware operation was rerun in this review.

- The eight new service scenarios at
  `test/ota/ota_service_upgrade_test.dart:434` instantiate actual BluetoothService
  in uncached mode. Only the device/characteristic edges and existing MCU model
  are fake. v1/v2 each cover expiry during discovery, owner retirement, valid
  consent and expiry after platform dispatch. They assert zero characteristic
  writes/BEGIN/DATA/END/ABORT on rejection, reject duplicate starts, and verify
  final target version/raw SHA in admitted positive controls. All eight names
  are individually present in both original Linux execution logs.
- Four direct writer variants cover baseline/reuse and statistics on/off,
  exception identity and healthy binding preservation. Four further cases cover
  one-shot/retired gates, timeout with late completion, and lower-writer pause
  with allowed/refused resume. Source inspection and the unfiltered full-suite
  commands/counts account for all 16 additions. Both expanded concurrent logs
  show 13 of these names literally; the synchronous gate test and two stats=false
  names are not individually printed. Do not claim per-case raw lines for those
  three. The first review parser incorrectly required all 16 literal names;
  `audit-failure-01.txt` preserves that collector failure. Only the reader was
  corrected, retaining exact source/full-command/count and eight-critical-case
  checks; no original or product test was altered and no CI was replayed.
- Exact-source development `43829923594` and debug `43830892509` each have Linux
  999 passed/16 skipped and Windows 967 passed/48 skipped, zero failures, strict
  analysis and 11 additional candidate tests per host. Twelve new mobile-path
  cases run on Linux and are explicitly skipped on Windows, not Windows PASS.
  SDK originals bind Flutter 3.47.8/Dart 3.13.7. Windows' one regenerated
  registrar-header EOL-only delta satisfies the existing semantic-state contract;
  it is not described as a literally clean restored worktree.
- Actual passive debug APK, metadata, standard APK, Windows EXE and runtime ZIP
  hashes/lengths match their successful source-bound receipts. The debug APK's
  74,581,856-byte kernel contains the target, endpoint, sentinel and passive token.
  Standard `43830974185` and main governance `43835079308` originals pass on their
  respective product/main sources. Signer/package observations remain original
  CI evidence, not new local signing or installed-device proof.
- The `15faa55c..f463649f` delta changes only the two test-fixture issues; the
  original failed `43829000008` is retained. Unchanged build-09's 15 inputs and
  nine outputs still match, including 465 warning-containing lines, zero errors
  and incremental Boot. The prior independent 42 host cases and original native
  27 cases remain applicable to their unchanged inputs, not new executions or
  evidence of Android lifecycle reliability. Earlier reviewer evidence is intact.

### Remaining Acceptance And Ownership

| Criterion | Status After This Source Review |
| --- | --- |
| A1 | R05 remains source-closed. T01 permission-page denial/lifecycle/settings-return coverage and real permission observations remain open. |
| A2 | R04 remains source-closed. T02 chooser/Bridge/boot/job/headless and telemetry/database-failure coverage, plus real background lifecycle observations, remain open. |
| A3 | R01/R02/R03/R04 source findings closed. Actual gateway/consent/OTA/final identity observations remain D3/D4 NOT_RUN. |
| A4 | R01 remains source-closed. Per-page real wheel/navigation/focus observation remains D5 NOT_RUN. |
| A5 | Unchanged offline icon evidence remains applicable; installed appearance and compatibility remain unobserved. |
| A6 | R01-R05 source closure is not whole-card PASS. T01/T02, D0-D5 and formal freeze/execution/final adjudication remain outstanding. |

Next owner: implementation supplies the remaining T01/T02 coverage; the
independent acceptance owner prepares only the missing D0-D5 observations and
existing formal contract when the actual collection/device/authorization
prerequisites are satisfied. This review did not enumerate or operate devices,
and does not assert the current phone connection state. C1-C6 stay unchecked;
P3/P4 completion, P1/P5 and production gates are unchanged.

This reviewer changed only the root note/board and the new project-local review
directory. The product worktree is untouched; no commit, push, merge, install,
release, deployment or external cleanup occurred. This update is LOCAL_PENDING.
`write-audit.json` binds selected outputs and verifies reviewed originals remain
unchanged. Handoff audit-09's 13 Cryptnet metadata differences are preserved;
this review's named-file comparison is separate, not process attribution or a
whole-OS audit. Attribution remains UNRESOLVED and no zero-native-external-write
claim is made.

## Root-Owned Review Delivery, 2026-11-16

The user assigned submission of the review record to the primary agent. This
documentation-only delivery carries the independent R03 closure and current
board status to main. Its tracked scope is exactly `PLAN-OTA-EXEC.md` and this
note; product source remains `f463649fc0a71945bff36c3ec57cbaecbd0fa9ef` on the
unmerged development branch. The original non-implementation review above is
not rewritten as an implementation self-test or whole-card PASS.

The next implementation batch is the outstanding coverage, not another repair
of closed R01-R05: T01 needs setup-page skip, permanent denial, revocation,
disabled notification channel and return-from-settings cases. T02 needs real
Bridge/chooser/boot/job/headless integration paths and headless telemetry with
database-failure retention; keep fakes at external boundaries rather than
replacing the behavior being tested. Preserve the existing task, criteria and
development-validation route. Return the source changes and original regression
results for independent review. D0-D5 and final independent acceptance remain
separate, unexecuted obligations; no device action or product merge is granted.

Submission and CI receipts are in the project-local `development/` directories
named `keyring-submit-notes-review-01` and `keyring-ci-review-*`, under
`.cache/app-companion-01-20261116/`. The separate submission write audit is
`review-submission-01/write-audit.json` under that same base. These delivery
receipts do not overwrite the preceding review evidence, failed originals or
write audits. No external cleanup or zero-native-external-write claim is made.

## T01/T02 Coverage Batch, 2026-11-16

Implementation resumes from `f463649fc0a71945bff36c3ec57cbaecbd0fa9ef` in the
existing `.worktrees/app-companion-01` worktree. The primary entry and fresh
remote main both identify `5f1a0731fa157cfc64fc39570d0e16455ecd208c`.
The published independent R03 closure supersedes the older shared-index wording:
R01-R05 remain source-closed and are not a new remediation batch.

- T01: drive the real setup page through denial/permanent denial, defer/return,
  revocation, disabled notification channels and resumed/settings-return events.
  Fake only platform permission/settings responses; opening settings is not a
  grant. Keep Android requests user-initiated and existing Darwin cases isolated.
- T02 native: execute real CompanionBridge admission, chooser completion,
  boot/job restoration and CompanionService headless-engine orchestration with
  Android/Flutter-embedding boundaries under Robolectric. Do not replace the
  production CompanionExecution or claim that a service-start request is ownership.
- T02 Dart: exercise page-independent collection through the real runtime,
  scan lease, monitor parser and persistence queue, including owner loss,
  stale advertisements, save failure/retention and retry. Add only narrow external
  dependency seams if the current constructors cannot express those inputs.
- Run full Linux/Windows development checks and the affected Android native
  suite via the existing Actions route. Changed App build inputs also require
  source-matched nonpublishing APK/EXE verification. Reuse unchanged MCU evidence;
  neither historical native results nor fixture-only checks qualify new inputs.

This is implementation self-validation, not independent acceptance. No USB
enumeration, installation, device operation, product main merge, release or
deployment is included. D0-D5, formal acceptance and C1-C6 remain outstanding.
The entry metadata will be recorded in
`.cache/app-companion-01-20261116/t01-t02-entry.json` before product edits/CI.
It is a named-cache metadata measurement after read-only context checks, not
process attribution or a whole-OS write audit. Preserve all earlier originals
and unresolved Cryptnet observations; no external cache cleanup is authorized.

### Development Feedback And New Association Edge

The first coverage source `1830c94c` fails strict analysis in checks
`43849493314` and the debug/native request `43849849630`. The package declares
Dart language 3.0: it cannot promote nullable instance fields or use repeated
wildcard parameters merely because the installed SDK is newer. The new fixture
also awaited Get.reset (void) and used a nonconforming doc-comment style.
`f25daecb` corrects those new sites without changing the dependency/SDK baseline.
Both complete host originals and console logs are preserved under the matching
`development/keyring-*` directories. Native execution did not occur in the
analysis-blocked debug request.

`b920f45d` replaces the setup fixture's pumpAndSettle with bounded frame advances:
the real page has an intentionally repeating atmosphere animation. Its checks
`43851810123` pass the 11 T01 cases and strict analysis; Linux still fails all
15 new telemetry cases because guarded expect calls inside external driver
callbacks conflict with an in-progress WidgetTester.pump. The follow-up uses
Flutter's synchronous callback assertion API, preserving every assertion, and
keeps the fake service-reset stream live until teardown. These are fixture
repairs, not new changes to closed R01-R05.

AC01-T02-NATIVE-01 is a new source finding while inspecting the actual chooser
path. The page supplies lowercase MAC keys but Android ScanFilter.Builder uses
BluetoothAdapter.checkBluetoothAddress, which accepts uppercase hex only.
Previously the builder also ran outside the association cleanup try block.
The bounded repair uppercases only the OS filter address and moves request
construction inside that try; stored/correlated addresses retain existing
semantics. The native integration oracle checks the actual Android validator,
the normalized filter, the user/system result and absence of automatic enable.
The source diagnosis was checked against Android 8's ScanFilter/BluetoothAdapter
implementation; runtime proof remains pending the new native CI, not a claimed
hardware reproduction or an R01-R05 reopening.

### Real-Path Dart Coverage And Scheduler Diagnosis

The first full green coverage source is
`8e7907f5d6cd7460534c5e637b5328ec6c52d554`, checks `43862023870`:
Linux 1025 passed/16 skipped and Windows 978 passed/63 skipped, zero failures,
strict analysis and 11 additional candidate cases per host. The additions are
11 real setup-page cases and 15 real headless telemetry/persistence cases.
The latter execute only on the mobile-adapter Linux host and are explicitly
skipped on Windows. Both hosts use Flutter 3.47.8/Dart 3.13.7; full original
reports/logs, not only console excerpts, are retained in the corresponding
`development/keyring-artifacts-*`, `keyring-windows-artifacts-*` and
`keyring-log-*` directories under the existing evidence root.

The intervening failures are preserved, not relabeled as product successes:
`43853759666` has no terminal Linux summary after the earlier fixture hang;
`43857075064`, `43859544296` and diagnostic `43861138521` expose the subsequent
bounded failure. On `553d81d2`, the original telemetry log reaches HELLO, the
fake characteristic returns and the real sender reports write-done, then stops
at transport dispose-start. The ordinary non-widget control regression in the
same raw log completes disposal. Only after widget teardown can the delayed
disposal finish. The SDK's completed stream-cancellation future is rooted in
the real microtask zone; pumping FakeAsync repeatedly cannot advance that queue.

The repaired fixture yields the root microtask queue with an empty
`tester.runAsync` callback between controlled pumps. All project operations,
permission/owner checks and timer advancement stay in the original fake zone;
the 2000-step bound and every business assertion remain. No deadline extension,
mocked runtime/scan/save implementation or second sender is used. The fixture
logs its first error before cleanup and unconditionally retires registrations
to prevent cascading failures. The temporary production diagnostics are removed;
`ota_service.dart` has no net difference from the independently reviewed
`f463649f` baseline. This is a test-scheduling repair, not a change to R01-R05.

Native request `keyring-passive-apk-native-01` binds that first green source.
The subsequent cross-layer check also found that the new suite was selected by
the native command but missing from the explicit XML upload list. The bounded
workflow repair adds its XML and asserts that every selected native suite has an
upload path. The existing HTML-report upload remains. Native execution/results
and final source-matched packages are recorded separately below when available;
this Dart milestone alone does not close T02, D0-D5 or formal acceptance.

### Native Compilation Feedback

The first native request is run `43863022720` on `8e7907f5`. Full Dart checks
pass on both hosts and the Android `apk_build` command succeeds, but
`apk_device_ota_native` fails at `compileDebugUnitTestKotlin`. No native test was
executed, and APK verification/collection were NOT_RUN. Six compiler diagnostics
identify two hidden SDK inspection getters (`deviceFilters`, `scanFilter`) and
four accesses through nullable JobInfo results. Both host originals and the full
console are retained in the corresponding `development/keyring-*43863022720`
directories, including the original 29168-byte native command log.

`0b2809e764da56eeeb678a2f4cbf6c96edd3704c` fixes only these fixture/collection
sites: reflection reads the actual constructed Android request/filter, scheduled
jobs are explicitly required to exist before assertions, and all three selected
native suites have explicit XML upload paths. The local existing helper tests
pass, 51 APK-helper and 66 development-runner cases; their raw results are in
`checks-coverage-02/`, not native execution evidence. The follow-up request is
`keyring-passive-apk-native-02`; no permissions, admission, runtime ownership or
test oracle was relaxed to address the compiler failures.

Run `43865948374` compiles the native suite and executes 70 cases: existing
DeviceOtaServiceTest 18/18, CompanionServiceTest 9/9, and integration 13/43, with
30 integration failures and no skips. All three original XML files and complete
host/native logs are archived. The engine-dependent failures share one fixture
boundary: FlutterEngine's delegated constructor executes before the outer
Context-only shadow hook and attempts to load unavailable host JNI; service
startup then has no cached engine. Non-engine Bridge/boot/job/admission paths do
run, but these results are not a green T02 suite. The follow-up disables real
call-through only for the three external Flutter embedding shadow classes and
adds an immediate cached-engine assertion after real service startup. It does
not substitute CompanionExecution, shadow project behavior, add native libraries
or relax any permission/ownership test. The new request is
`keyring-passive-apk-native-03` after its exact source is submitted.

The shadow source is `2496e6649417ad228b86ea9c55a9679398d9cd92`. Its checks-only
`43868429845` passes both hosts. Debug request `43868695116` instead stops before
APK/native work: Linux has 1024 passed/16 skipped/1 failed, Windows passes. The
one failure is the existing P35 test `disconnect during async recorder open
cannot publish a stale connected flag`, at `ota_service_p35_test.dart:268`:
after a fixed 20 ms delay the asynchronously flushed observation list is still
empty. This file runs in a different Flutter-test isolate from the new T02 suite.
The bounded fixture repair reuses that file's existing five-second `waitFor`
completion helper and then stops/drains the real recorder before asserting every
published connected/fresh flag is false. It does not extend that deadline, alter
recording production code, weaken the assertion or reopen an accepted OTA card.
All six source-matched checks/debug host originals and console directories are
preserved; native shadow correctness is still unproved by this prerequisite
failure. `keyring-passive-apk-native-04` is the next source-bound request.

`a41a9ca8d597f0b019a8a5a712c6bea29d38aaad` passes full checks `43870409744`.
Debug/native `43870546871` passes Dart and executes all 70 native cases, 63 passed
and seven failed (integration 36/43; both old suites 27/27). The delegated-engine
boundary now runs, including all three real chooser/normalized-filter cases.
Five remaining API-26 failures are at real GATT-state admission: Android 8's
framework method calls Binder directly while Robolectric 4.14.1 only implements
`getDevicesMatchingConnectionStates`. A test-only BluetoothManager shadow reuses
that same external state store for the legacy `getConnectedDevices` entry; the
production GATT predicate is unchanged. The two API-31/34 OTA-service failures
use a fixture snapshot missing the required notification `label`; supply that
input, retaining production rejection of malformed snapshots and every ownership
assertion. Follow-up request: `keyring-passive-apk-native-05` after submission.
The first console download for `43870546871` failed with a GitHub GET EOF; it is
preserved alongside the second retrieval, without replaying CI. Full XML, raw
host/native artifacts and successful checks originals are retained separately.

### Final Coverage Validation In Progress

The submitted follow-up is `3028a0570bdbc1ed115b8de92bfde47933d1dd4c` on
`dev/flutter/app-companion-01-20261116`. Checks `43873348049` pass with Linux
1025 passed/16 skipped and Windows 978 passed/63 skipped, zero failures, strict
analysis and 11 candidate cases per host. The full downloaded originals contain
all 11 named T01 setup cases and all 15 named T02 telemetry cases on Linux;
the mobile-adapter T02 cases are explicitly skipped on Windows. This does not
establish physical Android permissions, radio behavior or VM/process survival.
Native/debug request `43873444657` binds this same commit; its result and final
nonpublishing APK/EXE verification are still pending at this checkpoint.

The coverage delta from independently reviewed `f463649f` is 15 files. Production
defaults remain unchanged by the narrow permission, radio, monotonic-clock and
SQLite-driver injection seams. The only new operational repair is the named
AC01-T02-NATIVE-01 ScanFilter address/cleanup edge. No OTA sender, consent gate,
wire format, firmware, simulator or dependency-lockfile change is in this batch.
The old P35 test now waits for its actual recorder publication instead of a fixed
20 ms delay; its original false-connected/fresh assertions and five-second
completion bound remain. Failed compilation, scheduler, native-embedding and
fixture runs above retain their original logs and classifications.

This checkpoint also corrects the shared index's stale R03 review status without
rewriting any historical reviewer text. T01/T02 remain implementation self-tests
pending the original independent reviewer's evaluation. D0-D5, final formal
acceptance and product main integration are not performed, and C1-C6 stay open.

### Native Coverage Passed On The Final Source

Run `43873444657` completes successfully on `3028a057`: both Dart hosts pass with
the same full-suite counts as checks `43873348049`, and native compilation,
execution, APK signature verification and collection all return zero. The three
downloaded original XML files report 70 executed, 70 passed, zero failures,
errors or skips: DeviceOtaServiceTest 18, CompanionServiceTest 9 and the new
CompanionIntegrationTest 43. Its 14 cross-SDK methods run on API 26/31/34 plus
one API-34 notification-revocation method. The final SDK variant has no suffix
in Robolectric's XML; that is not a missing API-34 execution.

The previously failing API-26 GATT and malformed-notification fixtures now pass
through actual Bridge/Service admission. The real chooser's filter and matching
system-association cases also pass on every declared SDK, covering the new
AC01-T02-NATIVE-01 repair. This is host execution with external OS/embedding
shadows, not a connected phone, actual Flutter VM recovery or independent source
closure. The reviewer should evaluate this new edge with the bounded coverage
delta; R01-R05 remain closed and are not reopened.

Original native XML paths are under
`development/keyring-artifacts-43873444657/logs/app/bluetooth_flutter_Trace/build/app/test-results/testDebugUnitTest/`
in the existing evidence root. Complete per-host result/command logs are under
the matching `keyring-artifacts-43873444657` and
`keyring-windows-artifacts-43873444657` directories; the full Actions console is
`development/keyring-log-43873444657/console.log`. These are new executions of
changed native inputs, not a reuse claim for the old 27 native cases.

`development/keyring-build-08/dispatch.json` requests standard APK/EXE build-only
verification on the same commit, with `publish_release=false`,
`replace_existing_release=false`, application suffix `.companion` and the
baseline OTA link profile. Its final result and actual packages are recorded
below after retrieval; this dispatch alone is not a successful build or release.

The first final debug-package download hit the adapter's existing 180-second
deadline, with no collected APK and a nonzero adapter result. Its immutable
`development/keyring-package-43873444657/{failure.json,download.log}` remains;
`development/keyring-ci-86/run-list.log` separately records a GitHub API TLS
handshake timeout. These are local retrieval failures, not failing CI, missing
credentials or a reason to replay tests. The existing thin download adapter now
accepts a numbered receipt-directory suffix, as its log/artifact routes already
do, and the audit can bind that explicit successful receipt. One subsequent
download uses `keyring-package-43873444657-02`, retaining the same command,
180-second deadline, source check and artifact-byte hashing. The first directory
is not moved, overwritten or cleaned.

That second debug retrieval also reaches the unchanged 180-second child limit;
the first standard-package retrieval reaches its 240-second limit before Android
collection. Both retain a null child exit and empty download log, not an actual
server error or a proved throughput diagnosis. The standard failure is under
`development/keyring-standard-artifacts-43875796816/`. Meanwhile source-matched
standard build `43875796816` passes Android and Windows; its Pages and Release
jobs are skipped, and its complete console is archived. Checks/log downloads and
the subsequent CI query succeed. CI's original debug collector binds a
132392283-byte APK; no local copy is inferred from that remote result.

The next bounded retrieval-only attempt uses the same gh command with a
600-second per-archive limit and records artifact ID/digest/size/start time before
download. The standard action's outer bound is 1500 seconds for its two archives;
all other outer bounds are unchanged. This is a host collection-budget change,
not a product/test deadline relaxation or proof that time alone fixes the network.
Receipts use `keyring-package-43873444657-03` and
`keyring-standard-artifacts-43875796816-02`; older directories remain immutable.
No CI, build or device observation is replayed for these retrieval failures.

The 600-second debug attempt also returns `ETIMEDOUT` without collected bytes;
its pinned intent identifies artifact `14230505837`, a 76099816-byte archive
with GitHub digest `e036b34af5b86f7ae6ab8c6520ada0f442137c1e25b0a8cb8024ed0bb96d124d`.
Increasing the wrapper deadline is therefore not a qualified repair. The next
readback reuses `Tools/flutter/dev_apk.py`'s download/size bound, SHA-256 and
checked extraction functions through a small project-local API-redirect adapter.
It sends the existing credential only to the fixed GitHub API origin, retains
the signed storage URL only in memory, rejects additional/unsafe redirects, and
requires archive size plus GitHub digest agreement before extraction. Python's
OpenSSL route avoids deliberately choosing the inspected Git curl's Schannel
HTTPS path; no TLS validation is disabled and native-cache attribution remains
unresolved. This is a bounded replacement for the failed host retrieval step,
not a new artifact producer, ZIP implementation, OTA sender or acceptance suite.
New debug receipts use `keyring-package-43873444657-04`; the not-yet-run standard
`keyring-standard-artifacts-43875796816-02` uses the same readback. Original gh
timeouts remain unchanged. Final package-byte checks are still required.

Readback `-04` receives 30408704 bytes before its actual 650-second process
deadline; its intent still contains the older 600000-ms field. This collector
metadata discrepancy is preserved, not silently corrected. The observed bytes
show the longer transfer is not merely waiting on an unavailable API, but do not
attribute the earlier gh stalls. The retained prefix and its digest are inputs
to `keyring-package-43873444657-05`, never an already valid ZIP or APK. A fresh
request must return HTTP 206 with the exact remaining Content-Range; its tail is
stored separately and joined into a new archive only after the prefix is checked
again. Complete size and GitHub SHA-256 still gate extraction. No existing prefix
or failed directory is modified. Missing/mismatched range support fails closed.
The observed low transfer rate justifies a 30-minute readback process budget for
these exact final artifacts, not a changed test or product deadline; intents now
record the actual process bound. The debug outer bound is 35 minutes, and the
two-archive standard action is 65 minutes. Unrelated commands retain their bounds.

The range guard's five offline checks pass, covering an exact positive response,
ordinary non-range download, ignored Range, wrong offset/end/total or missing
Content-Range, and the HTTPS handler. Original output is
`artifact-range-selftest-01.log` in the existing evidence root. These are collector
checks, not additional T01/T02 product or independent acceptance executions.
The final audit additionally re-hashes all three downloaded archives against
their source-matched GitHub digests, checks the readback logs, and confirms the
retained prefix did not change. Package metadata alone does not satisfy it.

## T01/T02 Source And Self-Test Handoff

Product source: `3028a0570bdbc1ed115b8de92bfde47933d1dd4c`, branch
`dev/flutter/app-companion-01-20261116`, clean worktree
`D:/github/my/E-Track/.worktrees/app-companion-01`. Review the bounded 15-file
delta from `f463649fc0a71945bff36c3ec57cbaecbd0fa9ef`. The root delivery contains
only this note, `PLAN-OTA-EXEC.md` and `docs/agent-collaboration/index.md`.
It does not merge product source or self-sign independent acceptance.

### Observed Results

| Source-Matched Run | Actual Result |
| --- | --- |
| [Full development checks 43873348049](https://github.com/Eitan-S-23/E-Track/actions/runs/43873348049) | Strict analysis passes; Linux 1025 passed/16 skipped, Windows 978 passed/63 skipped, zero failures; 11 additional candidate cases per host. |
| [Passive debug/native 43873444657](https://github.com/Eitan-S-23/E-Track/actions/runs/43873444657) | Both full Dart hosts pass with the same counts. Native 70/70: new integration 43, existing DeviceOtaService 18 and CompanionService 9. Debug build, signature verification and collection pass. |
| [Standard build-only 43875796816](https://github.com/Eitan-S-23/E-Track/actions/runs/43875796816) | Android APK and Windows EXE pass. Pages and GitHub Release jobs are skipped; baseline profile and `.companion` suffix, no release/deployment. |

Original SDK identity is Flutter 3.47.8, framework
`737ba8f885dc774b53b442759999a312c9461e4e`, Dart 3.13.7. The full raw logs of
both development requests each contain all 11 T01 case names on both hosts and
all 15 T02 telemetry case names on Linux. The 15 mobile-adapter cases are
explicit Windows skips, not Windows execution. Its regenerated registrar header
has the previously allowed EOL-only restored-state difference; semantic and
untracked source deltas are empty, not a claim of literally clean CI files.

T01 covers no automatic prompts/enable, skip/re-entry, API-specific Bluetooth
permissions, denial/permanent denial, setting-return revocation, notification
denial/channel disablement, unknown OEM settings and stale/disposed refreshes.
T02 exercises actual Runtime/BluetoothService/BleController/MonitorController/
DatabaseService without a page: real INFO/control setup, bounded scan leases,
owner/revision/permission/API rejection and recovery, late callbacks, stale and
duplicate advertisements, exact failed-save retention, partial success and
single-flight retries. Native tests exercise real Bridge/chooser/Service/boot/job
paths with only OS and Flutter embedding/VM edges shadowed. No native
CompanionExecution substitute is used in the new integration suite.

The only new operational repair is AC01-T02-NATIVE-01, the CDM ScanFilter
uppercase-address and shared failure-cleanup boundary. Narrow dependency seams
keep production defaults; the old P35 fixture waits for real recorder publication
without weakening its false-connected/fresh assertions. R01-R05, the OTA sender,
wire/consent contracts, firmware, simulator and dependency lock remain unchanged
in this coverage delta. The earlier failure chronology above stays intact.

### Original Evidence

All paths below are relative to
`D:/github/my/E-Track/.cache/app-companion-01-20261116/`:

- Full host originals: `development/keyring-artifacts-43873348049/`,
  `development/keyring-windows-artifacts-43873348049/`,
  `development/keyring-artifacts-43873444657/` and
  `development/keyring-windows-artifacts-43873444657/`. Each contains its real
  `result.json` and complete command logs. The native directory also contains all
  three JUnit XML files under the exact test-results path recorded above.
- Full Actions consoles: `development/keyring-log-43873348049/console.log`,
  `development/keyring-log-43873444657/console.log` and
  `development/keyring-log-43875796816/console.log`.
- Debug package and metadata: `development/keyring-package-43873444657-05/`.
  Its 76099816-byte archive matches GitHub's digest after validated range
  recovery; the earlier 30408704-byte prefix remains unchanged in `-04`.
- Standard APK/EXE/runtime ZIP:
  `development/keyring-standard-artifacts-43875796816-02/`. Both original
  archives match their GitHub digests before checked extraction. The reader
  reports actual durations of 1263.793 s for debug remainder/readback,
  686.104 s for Android and 349.071 s for Windows. These are retrieval durations,
  not build or OTA timings; they do not prove the cause of earlier gh stalls.
- Earlier failed CI and retrieval directories, the first empty download logs,
  TLS query failure, `-03` timeout and `-04` partial file are retained. No CI,
  build or device operation was replayed solely to repair collection.

| Actual Collected File | Bytes | SHA-256 |
| --- | --- | --- |
| Passive `trace-dev-debug.apk` | 132392283 | `abd8c6136144f382d9d2b721b34c24288b0184562c94a4425b39f19bba49b26f` |
| Standard `ble-monitor-android.apk` | 48318616 | `1d4873e47e4bde4d8165036713cbd3cdc342bb4cce1f2c04bdc809d788d09a0a` |
| `ble-monitor-windows.exe` | 161792 | `e56757c6fbf4953ff7f45df5458ab8f89c3ec8c1f0563b6dbd28cfcd4df1b31a` |
| `ble-monitor-windows.zip` | 20627891 | `ceb95312bf0b10af5f38b38a9857036e01c0f63ab05d8b45feac174b07b0c987` |

The post-delivery readback/write audit is `final-write-audit-10.json`, with its
exact source/run/path inputs in `t01-t02-audit-inputs.json`. It must check the
actual APK kernel constants, package/ZIP hashes, all four full host originals,
fresh native XML, stage preservation and the final current main/CI receipts.
Its presence or a path in this note alone is not PASS; read its actual result.
Main submission/CI originals are separate under `development/`, beginning with
`keyring-submit-notes-07`; no product-main integration is implied.

### Boundaries And Next Owner

Reuse unchanged build-09 inputs/outputs and the previous independent 42 MCU
host results; do not repeat firmware or simulator builds. Build-09 retains
465 warning-containing lines, zero errors and incremental Boot output. The
new 70 native executions, not the old 27-case run, qualify this changed native
test/source batch for implementation feedback.

`t01-t02-native-02.json` records 30 named certificate-cache metadata differences
against this batch's `t01-t02-entry.json`; the earlier `-01` checkpoint had 24
against that same entry. Do not add these counts to one another or to the
reviewer's separate historical observations. Exact paths are in the snapshots;
the final audit takes a fresh comparison. Attribution remains UNRESOLVED, with
no external cleanup, whole-OS claim or zero-native-external-write assertion.
Controllable source, Git, cache, archive, test and evidence outputs remain inside
the authorized project. No PowerShell, local Flutter/Gradle build, USB enumeration,
installation, data clearing, flash, OTA, production release or deployment occurred.

Next owner: the original independent reviewer evaluates this coverage delta,
the new CDM repair and these original results. This is not another R01-R05
remediation request and not self-signed T01/T02 acceptance. D0-D5, real permission
dialogs/background recovery/radio observations, real wheel navigation, formal
whole-card adjudication and product main integration remain outstanding.
C1-C6 stay unchecked; P3/P4 completion, P1/P5 and production gates are unchanged.

## Independent T01/T02 Review, 3028a057

2026-11-17, Codex, resumed original non-implementation review. This is the
bounded source/original-evidence evaluation allowed by execution-contract
section 0, not a new formal device campaign or an implementation self-signoff.
No production source, old reader, prior result or frozen bundle was changed.

### Inputs And Disposition

- Primary root: `D:/github/my/E-Track`, branch `main`, local and freshly queried
  remote revision `990d8b4d73bde3cdd37316c66800a98481bed38b` at entry.
- Product: `.worktrees/app-companion-01`, branch
  `dev/flutter/app-companion-01-20261116`, clean source
  `3028a0570bdbc1ed115b8de92bfde47933d1dd4c`; remote branch matches. The review
  delta starts at independently source-reviewed
  `f463649fc0a71945bff36c3ec57cbaecbd0fa9ef` and contains exactly 15 files.
- No new blocking source finding was identified. Existing R01-R05 closure is
  retained, not reissued as whole-card acceptance. Firmware, simulator, OTA
  sender/consent inputs and the dependency lock are unchanged in this delta.

| ID | Independent Disposition | Evidence And Remaining Boundary |
| --- | --- | --- |
| AC01-T01 | Host-coverage gap CLOSED | Eleven real CompanionSetupPage cases cover defer/re-entry, API-specific denial, permanent denial, revoked permissions, notification denial/channel disablement, OEM uncertainty and stale/disposed refreshes. Both host originals contain these cases. Only OS permission/settings responses are substituted. D1 physical dialogs remain required. |
| AC01-T02 | Host-integration/telemetry coverage gap CLOSED | Fifteen Linux mobile-adapter cases execute Runtime, BluetoothService, BleController, MonitorController and DatabaseService without a page. They cover acknowledged scan leases, owner/revision/permission rejection, late scan completion, stale/duplicate samples, failed-save retention, partial success and single-flight retries. Windows explicitly skips those 15 cases. Forty-three native integration executions cover the real Bridge, chooser, Service, boot/job and engine wiring across API 26/31/34. D2 real lifecycle/radio observations remain required. |
| AC01-T02-NATIVE-01 | Identified source defect CLOSED | `CompanionBridge.associate` uppercases the MAC only at ScanFilter's OS boundary and places request construction inside the same failure-cleanup try/catch as submission. Persisted keys stay lowercase. Real-Bridge tests verify the filter address, foreground admission, system association matching, cancellation, timeout and stale callbacks. This is not a physical CDM result. |

The optional constructor seams retain production defaults. The telemetry tests
override the platform discriminator, not the runtime's ownership checks or the
monitor's save algorithm. The injected Database is the SQLite-driver edge;
`appendDeviceDataBatch` still executes the production transaction and batch path.
Native shadows replace OS/Flutter embedding boundaries, not CompanionExecution
or the project's admission methods. They cannot prove real Dart VM survival or
database durability across physical process death.

The P35 fixture now waits for actual recorder publication and then closes its
recording. Its original disconnected/fresh-connection assertions and bounded
wait remain. Native workflow selection and XML upload include all three suites;
the added integration suite is not merely an unexecuted source file.

### Independently Checked Originals

The reader and its results are in root
`.cache/app-companion-01-20261116/review-3028a057/`. It reuses the earlier review's
path/hash helpers and adds only original JSON/log/XML/ZIP interpretation. It does
not launch Flutter, Gradle, a compiler, ADB, J-Link, an installer or an OTA sender.
`review.py run` completed successfully and `review.log` records the result.
`evidence.json` binds 116 files and the actual read-only commands; its SHA-256 is
`bedd8f02f1c4742126d24e4bc49bcee3bc10863f6ecbda494fa738b6d0c43bcc`.

| Original | Independently Verified Result |
| --- | --- |
| Checks `43873348049` and native/debug `43873444657` | Four complete host result/command-log sets bind source `3028a057`, strict analysis and unfiltered `test` scope. Each Linux run reports 1025 passed / 16 skipped; each Windows run reports 978 passed / 63 skipped; each host also passes 11 candidate cases. Terminal counts and source-derived case names were read from original logs, not only the implementation inventory. |
| Native XML from `43873444657` | 70 executed / 70 passed, no failure/error/skip: DeviceOtaServiceTest 18, CompanionServiceTest 9, CompanionIntegrationTest 43. The latter matches 14 source methods on API 26/31/34 plus one API-34 notification case. Robolectric names the final SDK variant without a suffix; it is not an omitted execution. |
| SDK and regenerated files | Flutter 3.47.8, framework `737ba8f885dc774b53b442759999a312c9461e4e`, Dart 3.13.7. Restored semantic/untracked deltas are empty, lock unchanged. Windows retains the previously disclosed registrar-header EOL-only difference. |
| Standard build `43875796816` | Android APK and Windows EXE jobs succeed; Pages and GitHub Release are skipped. Actual downloaded files and archived run/console evidence are source-matched, not a claim of installation or release. |
| Debug/standard archives and packages | All three ZIP digests agree with their original GitHub artifact receipts; each selected member hashes to the actual collected package. Five files are checked: debug APK/JSON, standard APK, EXE and runtime ZIP. The retained partial debug prefix is unchanged. Actual debug kernel bytes contain the declared target, endpoint, sentinel and passive-mode token. |
| Unchanged MCU/simulator evidence | Build-09 input/output hashes and prior independent review anchors remain valid for this delta. Its 465 warning-containing lines, zero errors and incremental Boot output stay explicit. The earlier 42 independent MCU host cases are not relabeled as newly executed. |

The original package hashes and failed-retrieval chronology remain in the
[implementation handoff](#t01t02-source-and-self-test-handoff). This review does
not erase failed runs, re-download successful archives, repeat CI or infer a
transfer root cause. CI signer/application-ID checks qualify the collected
packages, not an installed phone. No new product test/build/device run occurred.

### Remaining Acceptance And Next Owner

| Scope | Remaining Work |
| --- | --- |
| A1 / D1 | Actual permission dialogs, association, settings return and revocation on the declared phone/API/OEM; a settings launch is not a grant. |
| A2 / D2 | Real ordinary background, lock, recent-task removal, process recovery/restart, offline backoff and resource release. OS/VM shadows do not close these observations. |
| A3 / D3-D4 | Actual MCU check/readiness/decline/stale-choice behavior and a legitimate consented update with fresh post-reboot identity, full raw SHA and applicable Boot evidence. |
| A4-A5 / D5 | Actual wheel rotation/press, one-level Back/focus restoration and installed launcher/notification/icon/package checks. |
| A6 / D0 | Current device identity/readiness and collection route, formal frozen inputs/precheck, missing observations and final adjudication. C1-C6 and product main integration remain open. |

Next owner: root/independent acceptance prepares the existing D0-D5 plan on this
stable candidate; do not request another unchanged T01/T02 implementation batch.
The recorded device-preflight failure has no newly confirmed connection-state
change in this thread. The next human action is connecting/unlocking the known
test phone and accepting its USB-debugging dialog if shown, before a new bounded
D0 identity check. No blind repeat of the absent-device probe was performed.
The same independent owner may prepare/freeze and execute the formal acceptance;
no additional freezing role or duplicate full campaign is required.

These board/note/index edits are LOCAL_PENDING on primary main, without staging,
commit, push or product merge. Entry metadata is in `entry.json`; the post-note
preservation/output audit is separately recorded in `write-audit.json`. All
selected outputs remain under the project root. Named Cryptnet metadata is only
a before/after observation, not writer attribution or a whole-OS zero-write
claim. Historical attribution remains UNRESOLVED and no external cleanup occurs.

The first post-note audit stopped at whitespace checking: its isolated Git
environment disabled the installed system `core.autocrlf=true` setting and
reported the shared index's historical CRLF lines as new trailing whitespace.
`failure-01.txt` and `finish-diagnosis.json` retain that failure and its command
output. `finish-with-eol.py` reuses the unchanged successful reader, supplying
the observed EOL setting only to primary-checkout Git commands. It does not
modify Git configuration, rewrite historical index lines or repeat the product
review. The separately preserved `whitespace-before.log` precedes normalization
of only this review's six added/changed board lines.
