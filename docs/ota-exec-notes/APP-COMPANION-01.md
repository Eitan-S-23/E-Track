# APP-COMPANION-01 Implementation Record

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
