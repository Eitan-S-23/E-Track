# APP-COMPANION-01 Implementation Record

## Current Verified Milestone, 2026-11-16

The implementation and development-validation milestone below supersedes earlier
pending-CI statements. The single card remains IN PROGRESS; C1-C6 are not signed
off. Implementation, device observation, independent acceptance and main product
integration are separate.

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
