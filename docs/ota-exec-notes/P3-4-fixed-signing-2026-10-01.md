# Persistent Diagnostic Signing

Owner: Codex root. User requested stable signing rather than a new application
for every diagnostic build. This does not authorize uninstalling the current
App, clearing its data, changing release signing or merging main.

## SIGN-01: Diagnosis

The installed diagnostic APK (`aea62c6`, application ID
`com.wen.gaia.gaia.p34probe`) has certificate SHA-256
`60fa63aa01a8edfbb8d138b2e43e65d14dd0108cc26f9c57781f27ec5a1be85e`.
The uninstalled reconnect candidate (`64a53a7`) has certificate
`d97a4bc7a8d9e8c66abd0172c4385af001985a877c3d6ca7f7d7b8933c136af9`.
Both were decoded directly from their APK v2 signing blocks. The prior workflow
used ephemeral debug keys; it uploaded only reports/logs/APK/metadata, not the
key. No matching project keystore was found. A certificate alone cannot recover
the private key or authorize a signing-key rotation.

Do not install that transient reconnect APK over the existing diagnostic App.
Its raw APK and original successful CI reports remain preserved under
`.cache/p34-reconnect/`; they are not evidence of an installed upgrade.

## SIGN-02: Persistent Key

Dedicated development certificate SHA-256:
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.

Repository secret: `ETRACK_DEV_SIGNING_KEYSTORE` in `Eitan-S-23/E-Track`.
Persistent local backup: `.local-archive/development-signing/development.jks`.
Initial protected copy: `.cache/p34-signing/private/development.jks`.
Both local locations are Git-ignored and have current-user/SYSTEM-only ACLs.
Provisioning and equal-backup receipts are under `.cache/p34-signing/`.
Never print, commit, upload as an artifact or rotate this key to fix a build.
Do not use the release private key for diagnostic builds.

## SIGN-03: Implementation And Verification

Pending mainline integration: branch
`dev/flutter/fixed-development-signing-20261001`, commit
`0dd20fe72940ca26101c5d41f1b26cd039189a8a`.
Read the branch's `Tools/flutter/dev_apk.py`, development workflow, Gradle debug
signing configuration and `docs/flutter-development-validation.md` together.

Only explicitly requested suffix-bearing development APKs receive the secret.
The helper verifies the keystore certificate before building; Gradle refuses a
missing fixed keystore; final APK collection independently verifies exactly one
pinned signer with apksigner and records the certificate in metadata. Ordinary
release signing remains unchanged. No private keystore is in upload paths.

Host regressions: 62 runner + 38 APK helper + 26 observation tests passed in
`.cache/p34-signing/host-tests-002/`. The failed earlier blanket-secret test is
preserved in `host-tests-001`; its replacement allows only the guarded named
development secret, retaining the prohibition on release secrets/permissions.
Push CI run `36870533170` passed on Ubuntu and Windows. Generation 1, run
`36871478030`, also passed both hosts. Its downloaded APK SHA-256 is
`adaabe6061f055245eba76cb2ffd1521f57794ed109f78b0898a0a5e23e127e3`;
direct local APK v2 certificate parsing matches the pinned development signer.
Original reports and archive digests passed; 18 original logs contain no exact
private-keystore secret. Evidence: `.cache/p34-signing/apk-g1/apk.json`.
Generation 2, run `36874130469`, passed both hosts. Its APK SHA-256 is
`1ec71e54f738abacbf5f4360ba421076061e2026a666ef484c8e3a17759884da`.
Both actual APK v2 certificates match the fixed fingerprint. The result is
`TWO_BUILDS_SAME_CERTIFICATE` in `.cache/p34-signing/signer-comparison.json`.
Generation 2 retained a failed redirect attempt and 287 verified chunks after a
single chunk failed; only the missing chunk was retrieved in the final attempt.
No CI or signing operation was repeated for a download failure. Both generations'
18-log sets were checked for the exact private-keystore secret with no matches.
The final local write/root-preservation audit is `.cache/p34-signing/final-audit.json`.
No fixed-signature installation or measured OTA gain is claimed.

## Next Action

Both APK checks using `Tools/ota/p34_signing_artifacts.py` are complete. Keep original
artifacts and signer-comparison receipt. The user subsequently explicitly approved
the one-time same-package backup/uninstall/install migration. It completed via
`Tools/ota/p34_signing_migration.py`: verified old APK, completed30242 capture,
98 persistent files, 118799360-byte original tar, matching second device read,
and protected duplicate under `.local-archive/p34-signing-migration/`.
The completed30242 snapshot digest matched its original analysis input exactly.

The fixed generation-2 APK was installed under the same `.p34probe` ID and its
installed SHA-256 was verified. All 98 files were restored with identical content.
Only two path mappings were applied in a separate restoration tar: old runtime
config became `files/p34-migration-original-config.json`; old active captures
became `files/p34-migration-observations/`. Original tar bytes were not modified.
This preserves evidence without reusing an expired endpoint or filling the new
capture store. No App launch, MCU command or OTA occurred during migration.

Original user-0 BLUETOOTH_SCAN/BLUETOOTH_CONNECT grants were recovered from the
pre-uninstall package record. Both grants were restored via USB and verified;
no additional permissions were granted. Each private USB session closed normally
with the original ADB key unchanged. Receipts are in
`.cache/p34-signing/migration/{inspect,backup,replace,restore,permission}-001/`.
Five offline migration tests passed before the destructive step.

Continue host validation and prepare the legal30242-to30243 reconnect screen,
now binding `.cache/p34-signing/apk-g2/apk.json`. Keep the same ID and private key;
ordinary in-place updates preserve app data. Runtime reconnect cadence changes
need no new APK. Retained MCU remains confirmed30242 and Boot is unchanged.

## RECONNECT-HOST-01: Interrupted Observation Window

The signed reconnect host route passed 375 source-bound host checks: 354 original
passes plus 21 residual checks after a host-test timeout. The original timeout
remains preserved. Coverage is under `.cache/p34-reconnect/session-tests-r2/`.

Run `20261001T155444-25400` ended normally before any MCU cell because all seven
DNS readiness attempts failed. The exact no-cell recovery is preserved under
`.cache/p34-reconnect/dns-recovery/`; do not replay that spent helper.

Run `20261001T161736-81500` subsequently resolved and verified HTTPS/package bytes,
then launched the fixed APK. After a gap in host observation, its supervisors,
workers, USB launcher and listening ports were absent without final closure
receipts. Do not relabel this as graceful closure or assume no OTA from stale
host health alone.

Fresh USB inspection at `2026-10-01T19:09Z` retrieved both active capture
directories. The same installed APK, PID23723, runtime config and capture
`1790873190640854-e74f259a6cf81bd47609ba5e` remain. The capture contains two
successful queries, zero upgrade starts/ends, no snapshot and no loss/error.
Evidence: `.cache/p34-reconnect/orphan/inspect-20261001T190946/`.
The first inspection falsely rejected space-separated `adb devices -l` output;
its original receipt is preserved, parser corrected and space/tab/offline/
unauthorized/duplicate cases tested. No reinstall or user cable action was needed.

Next finite host recovery uses `Tools/ota/p34_reconnect_orphan.py recover` once:
verify absent old owners, unchanged original checkpoint, fresh full App/Boot
readbacks and unchanged native session generation; recheck the exact unused
phone capture; archive only its expired runtime config through the existing
retirement primitive; restore the host pointer to completed30242. All original
missing-closure evidence stays untouched. No MCU reset/flash/OTA or capture
deletion. Host outputs stay under `.cache/p34-reconnect/orphan/`; the only
external write remains the authorized SEGGER connection-history file.
Then create a fresh bounded service/observer for the same30242-to30243 cell.
The user still owns connect/download/Start, only after readiness is verified.

Recovery completed at `2026-10-01T19:14Z` with
`ORPHAN_NO_TRANSFER_RECONCILED`; nine targeted host tests passed. Fresh full
readbacks, unchanged native generation, exact unused App binding, configuration
archival and normal new-USB closure all passed. Receipt:
`.cache/p34-reconnect/orphan/recover-001/result.json`. This does not repair or
rewrite the missing closures of the interrupted original run. The same tested
reconnect profile can now start a fresh observation window; no OTA was replayed.

Fresh run `20261001T191549-84800/s04` reached
`READY_FOR_FULL_INSTALL_START` at `2026-10-01T19:30:12Z`. Its three successful
App queries, exact downloaded293079-byte30243 package, schema3 cadence2000/500,
fixed APK PID17127 and current30242 raw identity were verified. Service and
both observers are live. Await one user Start in the foreground; no new OTA
has started at this checkpoint. Preserve the ordinary30-second healthy-App
confirmation and collect the original finished snapshot, never repeat the OTA
for host evidence. Network expires `2026-10-01T20:49:16Z`; App Start has its own
shorter deadline shown by `p34.bat --run 20261001T191549-84800 --cell s04 status`.

## RECONNECT-02: Target Installed, App Verification Failed

The user started that admitted run. Its original immutable snapshot reports
`not-completed`; do not rewrite it as success. Transfer completed with END OK,
293079 durable bytes,51.714236 seconds,5.534452 KiB/s and zero DATA retransmits.
All203 reconnect attempts failed before bind/GET_INFO over180.004637 seconds.
Full Android ring retrieval found203 identical
`PlatformException(requestMtu, device is disconnected, null, null)` errors.
Evidence: `.cache/p34-reconnect/timeout-30243/analysis.json` and
`logcat-full-001/logcat.log`; the original short tail was insufficient and is
preserved separately. No OTA was repeated for these logs.

The original MCU trace observed target30243 and its ordinary30-second health
confirmation. Fresh full App/Boot readbacks then passed at19:57Z: App SHA-256
`fef244ea0eb85a85b89c6bbcdc8955673c2cf26ad2dc979deec63a4a11bc45ed`,
Boot SHA-256 `a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`,
BCB4, confirmed1, state-snapped1, SD-ready1. Receipt:
`.cache/p34-reconnect/timeout-30243/readback-recovery/readback-001/result.json`.
Its detached900-second supervisor exited normally. The earlier terminal-host
readback ended with intent only, before MCU outputs; that receipt remains.
All original service/USB/native owners are closed. Retain30243, not30242.

Repair pending CI/hardware verification: exclusive branch
`dev/flutter/p3-4-mobile-reconnect-20261002`, commit
`e29c1392db7a1e0570b588f4d2f2c8d0d9c9c3ad`, CI36918287393.
The service canonicalizes mobile MAC identifiers, preserves UUID/cache spelling,
uses connect(mtu:null), keeps explicit post-discovery MTU negotiation and rejects
a connection return without a live link. Eight new mobile boundary tests drive
the real service methods with a fake device factory. Windows paths stay unchanged.
The same fixed signing implementation is inherited. No main merge/release and
no speedup are claimed. Detailed branch note:
`docs/ota-exec-notes/P3-4-mobile-reconnect-2026-10-02.md`.

CI36918287393 passed both hosts. Requested APK run36918990724 also passed both
hosts and produced a verified APK with SHA-256
`5fd96270b90f64c706ce8eaeba4b88a3c3df1b1ea90763369e118adb9f23a366`.
Actual APK v2 certificate matches the fixed development certificate. Evidence:
`.cache/p34-connect-fix/apk-g1/apk.json`; all288 APK download chunks passed
without retry. The collection owner closed normally. No Windows EXE was built
by this development-only workflow.

The same-package `adb install -r --no-streaming` attempt was rejected by the
phone system: `INSTALL_FAILED_ABORTED: User rejected permissions`. Preserve
`.cache/p34-connect-fix/install-001/` and its normal owner/USB closure. A fresh
read-only reconciliation confirmed the old fixed-signer APK is still installed,
the original snapshot and runtime config are unchanged, and the App is stopped.
Receipt: `.cache/p34-connect-fix/install-reconcile-001/result.json`.
This is not a signing mismatch and no uninstall/data clear occurred. Await the
user unlocking/keeping the phone awake, then one newly owned install attempt
with user confirmation of the actual system prompt. Do not rerun the spent
install-001 entry. New firmware remains raw-confirmed30243; no OTA replay.

Additional offline diagnosis: GATT time16.785s versus previous15.817s, while
last-send-to-durable intervals total32.145s versus15.365s. Native erase/program
costs remain about3.346s/0.479s, close to the prior run. This does not prove a
root cause, but the slowdown is not explained by increased Flash erase time.
Original transfer partition and native profile are preserved under
`.cache/p34-reconnect/timeout-30243/`. Keep clocks and overlapping phases separate.

## RECONNECT-02: Installed Repair And Successor Screen

After the user confirmed readiness, `install-002` succeeded at
2026-10-01T20:25:45Z. Same package, same fixed certificate, no uninstall or data
clear; original failed OTA snapshot, configuration and Bluetooth grants survived.
Both the installation owner and private USB closed normally. The earlier system
rejection remains preserved and is not a certificate mismatch.

`query-001` passed at 20:28:14Z with the repaired APK, PID17018. Original App
GET_INFO reported30243 and the full raw SHA
`fef244ea0eb85a85b89c6bbcdc8955673c2cf26ad2dc979deec63a4a11bc45ed`.
MTU247/payload244/without-response; zero upgrade starts or ends. Query worker
and USB closed normally. This is normal-query evidence, NOT post-END reconnect
acceptance and NOT a20-second result.

Next finite screen: one legal30243-to30244 header-only FULL successor with the
installed repaired APK. Retain the current Boot, executable, rollback and normal
30-second confirmation. Hold921600/window28, schema3, INFO2000ms and interval500ms
fixed. Root is sole operator; all controllable outputs stay below
`D:\github\my\E-Track\.cache\p34-connect-fix\followup`. The standing device policy
applies; the only external host write is the already authorized SEGGER connection
history at `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`.

The new standalone `Tools/ota/p34_reconnect_followup.py` consumes the original
App timeout, durable END, confirmed complete raw target readback and subsequent
genuine GET_INFO. It does not alter the failed predecessor verdict or replay it.
Before the device window: native package positive/four negative decodes, adapter
self-tests, bound APK/CI checks, service verification and complete retrieval route.
User controls required in-App navigation/download/Start; no automatic UI taps.
The network and cell use separate finite owned workers, with the existing25-minute
start window,15-minute active bound and retained cleanup/readback reserve. Retrieve
the full original Android ring even if final snapshot validation fails. Unknown
device state stops dependent mutations; never reflash/reset to fix a host collector.

Only this screening cell is planned. A completed transfer is not repeated merely
to recover logs. Retain a fully verified30244 on success; no downgrade or Boot
replacement. Original Boot backup stays at
`.cache/p34-boot/preparation/original-whole-boot.bin`. Formal acceptance and further
transfer optimization remain separate; no throughput improvement is claimed here.

The successor is now prepared:292965 bytes, package SHA-256
`3c81d75f9fc886ee30b3dc22f1ea89e8b69410dba9a19fcdf982235967976234`, target raw SHA
`175ed1a4494f1945d781321979d207898031854b48aaeccc9f2f40c98e191eee`.
Native positive and four negative decodes passed;14 adapter guard tests and the
real offline context/configuration check passed. Originals are in
`.cache/p34-connect-fix/followup/assets`, `tests` and `runtime/check`.

Active screen: `.cache/p34-connect-fix/followup/trial-001`, not the old generic
`p34-session/current.json` pointer. The system resolver initially returned11001;
the same hostname resolved at the seventh scheduled check and HTTPS/package
verification passed. No retry trial or system DNS change was made. Separate
`p34_scoped_dns.py` fallback preparation passed9 tests and an exact TLS/package
GET, but it is NOT used by the active trial. Its original Python3.13 constructor
failure, archived source and corrected test/probe remain under `scoped-dns`.

At2026-10-01T21:45:06Z the cell reached `READY_FOR_FULL_INSTALL_START`. Fresh
complete raw30243 App/Boot checks passed without reset/halt/flash. App PID1998,
capture `1790891079051299-33907bf1f4188996f192722e`, two successful original
queries and the exact downloaded292965-byte package were admitted before BEGIN.
Runtime config SHA `fd5e383cd46dd47b420da1b031c1c6cefb2fca57ce752942dc19fbc5922a6bc1`.
USB, native trace, network and coordinator remain live with finite deadlines;
the user was asked only to tap Start and keep the App foreground/USB connected.
Poll this trial's `cells/s04/health-live.json`, `status.json`, `result.json` and
owned closure receipts. Do not relaunch a spent entry or infer transfer success
from readiness. Full post-OTA reconnect/performance results are still pending.

The user then completed the upgrade. Original analysis now reports
`FULL_INSTALL_VERIFIED` at
`followup/trial-001/analysis/1790891623124538900/result.json` (relative to
`.cache/p34-connect-fix/`), SHA
`07a9d0c05132d0bde90f85c61baeacb62c5863b09e2c4ca9f39a1192bf5f4382`.
The new immutable App snapshot SHA is
`3bfa383e85bf6f810ddbe056ee8d266de1bbe8334e5fb40718a8b408cb6876e8`.
Transfer37.784388s /7.571874KiB/s; END-to-target-identity22.394300s, four probes,
zero DATA retransmissions or ACK errors. Raw30244 App SHA matches the prepared
target and the full65536-byte Boot is unchanged. Normal BCB/confirmation passed.
All trial coordinator/network/cell/USB/native owners closed normally. Retain30244.
This fixes the prior180-second reconnect failure in a real successor test, but
does not establish stability acceptance or the20-second/50KB/s targets. Transfer
is faster than the failed30243 run but still slower than the32.643871s30242 run.

One probe spent15.011773s in discovery. A read-only late console retrieval
(`followup/late-logcat-002`) confirmed the explicit plugin timeout after15seconds;
its original snapshot remained identical and the new USB owner closed normally.
The first attempted live-USB borrow stopped at preflight because the successful
trial had already closed USB; it sent no device command. Do not replay the OTA.
Console lines lag the App's monotonic markers substantially; measure from the
original monotonic fields, not printed logcat timestamp differences.

Next bounded remediation: exclusive development branch
`dev/flutter/p3-4-reboot-discovery-20261002`, WIP commit
`89fee42f548e99eb5bc437aa736d2e9cc8ddf5de`, checks-only CI36934785450.
The patch gives only reboot discovery a3-second plugin response timeout and
retires an unresolved mobile link only while its generation still belongs to
that non-abandoned probe. It preserves global/native serialization, Android
disconnect delay, full identity guards, ordinary confirmation and Windows behavior.
Seven new boundary/lifecycle tests plus existing suites await the real CI result.
Detailed branch note: `docs/ota-exec-notes/P3-4-reboot-discovery-2026-10-02.md`.
No new APK, post-change hardware result,20-second result or throughput gain is
claimed for that WIP patch yet. The fixed development signer remains unchanged.

## RECONNECT-03: Discovery Deadline Successor

Checks-only CI36934785450 and APK CI36935410469 passed on both Ubuntu and
Windows for89fee42f548e99eb5bc437aa736d2e9cc8ddf5de. The collected APK SHA is
`5d7b11ca58927a0ad6441c578a52ae3294e3a08d23980e1ee32561a326d4fc05`;
its actual v2 certificate matches the fixed signer and its application ID remains
`com.wen.gaia.gaia.p34probe`. Collection completed normally with all288 APK
chunks verified; no dispatch or download retry was needed.

Current bounded matrix: install this exact APK in place with data/configuration/
original30244 snapshot/grants preserved; perform a query-only smoke check; then
one legal30244-to30245 FULL successor screen. Root is sole device operator and
the user still owns required system confirmations and in-App Start. No automatic
UI taps, uninstall, data clear, Boot replacement, reset or downgrade. Keep all
existing recovery/rollback and normal30-second healthy-App confirmation paths.
All controllable new outputs stay under `.cache/p34-discovery-fix`; the sole
external host-write exception remains the already-authorized SEGGER connection
history file named above. No production release or mainline integration.

The successor changes only the version header, not executable bytes. Native
positive/four negative package checks and three parent-admission negative checks
passed. Package292945 bytes, SHA
`6dcfba87d2752e2b80bb9847e498ffaa7018bd2b6c9d42293f029c6413bb7170`;
target raw616540-byte SHA
`35270c33dd3e825f42102227e478fbec6e4ba0e444598db2011e80ac6e0ea107`.
Boot stays65536 bytes with the prior confirmed SHA. Retain30245 only after full
raw readback and confirmation pass; unknown state stops dependent mutations.

`p34_discovery_install.py` has a900-second finite owner and a180-second actual
installation bound. Query-only smoke has a600-second owner. The new trial entry
retains the tested finite network/cell bounds,25-minute user Start window,
15-minute active bound and readback/cleanup reserve. Hold921600/window28,
schema3, INFO2000ms/interval500ms and full/prefix0 fixed. Verify the entire
retrieval route before inviting Start; do not repeat a successful OTA to repair
a collector. This remains a development successor screen, not1MiB/stability
acceptance and not evidence yet of meeting20seconds or50KB/s.

The in-place discovery update succeeded at2026-10-01T22:49:56Z. Actual installed
APK hash matches the artifact; original snapshot/configuration/Bluetooth grants
are unchanged. No human installation confirmation was required this time.
Installation worker and private USB closed normally. The new query-only smoke
then succeeded with PID16153, capture
`1790895078341757-825e5ceec9021c26eb02cf1e`, full30244 identity, one successful
GET_INFO, zero upgrade starts/ends and no recorder loss/error. Its USB and worker
closed normally; see `query-001/result.json` under the discovery area.

Eleven new adapter host checks passed, including real immutable predecessor,
package/APK proofs, stale-version rejection, all fixed axes and failed-snapshot
console retrieval. The full offline configuration/source check also passed with
163 pinned sources. Receipts: `tests/result.json` and `runtime/check/worker.log`.
The next trial's launcher is owned and finite under `runtime/launch`; its output
is `trial-001`, not the stale generic session pointer. No new OTA has started at
this checkpoint.

Transfer follow-up remains separate: original30244 stats contain2292 GATT and
platform writes for325174 physical bytes, with GATT median5074us and P9517093us.
Each142-byte DATA frame still occupies a separate write despite payload244.
This is measurable host/platform overhead, not proof that larger windows or
UART speed solve it. Original console confirms continued scan callbacks and
monitor-processing logs during the logical transfer markers. The observer stops
scanning at initial bind, but monitoring has scan-restart paths; a future
owner-scoped scan pause must cover those entry points and restore prior demand.
No pause/priority/batching change is mixed into this discovery comparison.
Current Android connection interval remains unknown: no connection-update or
interval record was found in the preserved full console. Old browser HCI values
are not evidence for this phone run.

Trial `trial-001` reached `APP_LAUNCHED_CONNECT_AND_DOWNLOAD` at
2026-10-01T23:14:46Z. The new endpoint completed real HTTPS/package verification.
Fresh pre-transfer initial/final full App and Boot readbacks both match the
retained30244/unchanged Boot hashes; BCB4, confirm1, snapped1 and SD-ready1.
No reset/halt/flash was used. The new capture is
`1790896481244860-1d625871c806583d059b8535`; original producer lines are advancing,
upgrade starts/ends remain zero and no loss/error is reported.

Coordinator/network/cell/native/USB owners remain live and finite. Network
expiry is2026-10-02T00:31:26Z, and the shorter App-start allowance is25minutes
from actual launch. The user has been asked to navigate to OTA and download
3.2.45-p34r, but NOT Start yet. Package admission must be written before BEGIN;
notify Start only after `cells/s04/status.json` says
`READY_FOR_FULL_INSTALL_START`. The generic session pointer still refers to
the old failed trial and must not be used or rewritten to fake device identity.
After the user's download, continue this live trial, not another launcher.

Package admission is now verified: `READY_FOR_FULL_INSTALL_START` was recorded
at2026-10-01T23:16:16Z for PID10524 with the exact292945-byte30245 package. The
latest health still has zero upgrade starts/ends and no loss/error. The next
required user action is only Start, keeping the App foreground and USB attached.
The output/key/owner audit is `turn-audit-001.json`; its stale download-wait label
is explicitly superseded by `turn-audit-002.json` with the actual admission
evidence. No original audit or OTA result was rewritten. New performance results
remain pending the user's transfer and full post-OTA verification.

## RECONNECT-03 Result And RADIO-01

The user completed30245. Full original verification passed in
`.cache/p34-discovery-fix/trial-001/analysis/1790897278436463300/result.json`,
SHA `167c35d0c893d4df1f403307ae86f806b40885c8eb6b06dfeddfa2c8ca81a59c`.
Snapshot SHA `991a7ac61ba5939ae267f7d60b5b35e421e430031c89376b8907fafa3a5b5eb9`.
Package292945 bytes transferred in44.885462s; END-to-target-identity26.478168s.
Six probes, zero DATA retransmissions/ACK errors. Three-second discovery timeouts
were observed, but neither end-to-end measurement improved over30244. Both
20-second and50KB/s goals remain unmet. This is not a stability/reference-package
acceptance result. The immediate complete Android ring already contains the
discovery failures; no extra OTA or late-log retrieval was needed this time.

Initial/final raw post-upgrade App hashes match target30245, Boot is unchanged,
BCB4/confirm1/snapped1/SD-ready1. All coordinator/network/cell/native/USB owners
closed normally. Retain30245. New native full-apply cost is6286ms (valid millis
measurement), including2916ms erase and939ms program; host/phone/native clocks
must not be subtracted from one another. No claim of a cause from one slow run.

Next candidate: exclusively owned `dev/flutter/p3-4-radio-policy-20261002`,
checkout `.cache/p34-radio-fix/src`. Initial WIP53022b1 adds strict schema4's
independent `pauseScanDuringOta`/`androidHighPriority` flags, serialized owned scan
pause/restoration and per-device generation-bound priority requests. Old schemas
and production defaults are unchanged. Detailed contracts and the finite four-arm
screen plan are in that branch's `docs/ota-exec-notes/P3-4-radio-policy-2026-10-02.md`.
No radio-policy APK or device result exists yet. The next artifacts must retain
the same application ID and persistent development certificate.

Initial CI36945142728 failed on both hosts due to an ambiguous BluetoothService
import in the new API-forwarding test. Linux additionally reported a test compiler
exit during that failed compilation. Exact job logs and original host artifacts
are preserved under `.cache/p34-radio-fix/ci-53022b1` and `ci-job-*.log`; do not
erase or relabel them. Revision254e78507d27aedc636cca3614272003e67bd369 restricts
the plugin import to BluetoothDevice/ConnectionPriority. Its changed-input CI
push is underway via the finite `runtime/push-r2` owner. No unchanged-run retry,
local Flutter build, mainline merge, release or installation was performed.

Revision254e785 passed checks-only CI36947970924 on both hosts. Explicit debug
APK dispatch36948347840 also passed both hosts. The fixed-signer collection is
running under `.cache/p34-radio-fix/runtime/apk-collect`; do not dispatch again.
The complete original failed53022b1 CI artifacts were retrieved and verified,
confirming the ambiguous import and compiler-exit observations before correction.

All four host-only successor packages passed native positive/four-negative
decodes per arm. Order: baseline30246 (292928 bytes), scan30247 (292920 bytes),
priority30248 (293081 bytes), combined30249 (293036 bytes). They differ only in
version headers; prepared lineage is explicitly NOT current installed identity.
Exact hashes and bindings are in `.cache/p34-radio-fix/assets/result.json`.

New source-bound entry `Tools/ota/p34_radio_trial.py` loads a private backend
module, adds strict schema4 cadence/boolean/unknown-field validation, and keeps
all original backend/old snapshot bytes unchanged. It requires real previous
FULL success and complete raw confirmation before each next arm. Eleven host
tests passed in `.cache/p34-radio-fix/host-tests`; radio acknowledgements and
cleanup uncertainty are checked separately from firmware success.

`Tools/ota/p34_radio_install.py` is prepared but not yet run. It updates the exact
completed30245 App in place, retaining snapshot/config/grants, with a900-second
owner and180-second install bound. No uninstall, data clear, launch or OTA.
Do not consume another capture slot with a separate query launch: seven capture
directories existed at the last trial. The first baseline trial incorporates the
new APK's genuine query/package checks before user Start. Later arms may require
separately verified archival of preserved inactive captures before another launch;
do not delete arbitrary data or silently bypass the eight-capture store guard.

The radio APK was collected and verified: SHA
`20ae2d51c9623c8abfc264afadf5ad397edea46c1fa15c3199475b06c5f7f80e`,
131641762 bytes, unchanged fixed certificate/application ID, both original host
PASS reports. All288 APK chunks verified and the collection owner closed normally.

Radio `install-001` was attempted once at2026-10-02T01:14Z. The phone returned
`INSTALL_FAILED_ABORTED: User rejected permissions` after its actual install
command. Preserve the failed receipt; no automatic repeat, uninstall or data
clear. Original completed30245 snapshot/config/grants were checked and backed up
before stopping the App. USB closed normally and its existing key was unchanged.
The owned worker correctly exited1 for this rejected operation. This is a system
confirmation barrier, not a signing mismatch or another OTA failure.

A new read-only reconciliation is running under
`.cache/p34-radio-fix/runtime/install-reconcile`, output `install-reconcile-001`.
It checks the old installed APK, preserved snapshot/config, grants and screen
power state, without reinstalling or launching the App. The user has been asked
only to unlock/keep the phone awake and handle the real system installation
confirmation. Do not replay the spent `install-001` entry. After actual readiness,
use a fresh owned attempt tied to the original rejection and read-only result;
then bind the trial entry's installation receipt to that successful attempt.
No radio trial or offline full-context check has run yet because installation is
not verified. Retained firmware remains fully confirmed30245.

Read-only reconciliation completed normally at2026-10-02T01:17:06Z:
`OLD_APK_DATA_PRESERVED_AFTER_SYSTEM_REJECTION`. Old APK5d7b11ca remains installed,
the App is stopped, original snapshot/configuration/grants are intact, and the
phone reports `mWakefulness=Asleep` while USB powered. No install or OTA was
repeated. The actual remaining intervention is to wake/unlock the phone and
confirm the system dialog on a freshly scheduled installation. Generic permission
messages do not change the phone's sleep state or satisfy that system UI step.

## RADIO-02: Same-Signer Update Completed

After explicit phone readiness, the fresh `install-002` attempt completed at
2026-10-02T05:06:41Z with `FIXED_SIGNER_RADIO_UPDATE_VERIFIED`. Installed APK
SHA-256 is `20ae2d51c9623c8abfc264afadf5ad397edea46c1fa15c3199475b06c5f7f80e`.
Original snapshot, runtime configuration and Bluetooth grants were preserved.
No uninstall, data clear, App launch or OTA occurred. Installation owner exited
zero without forced termination; private USB closed normally and the existing
read-only ADB key hash was unchanged. Original rejection/reconciliation remain
untouched under `install-001` and `install-reconcile-001`.

The radio trial now explicitly binds `install-002`, not the rejected attempt.
Fresh source-bound tests at `host-tests-002/result.json` passed all12 checks,
including the successful-install anchor and preservation of the failed receipt.
The terminal-owned full offline context check lost its tool session without a
retrievable result; no success is claimed. A fresh finite detached check is
running under `runtime/check-001`, with no device operations.

Use this installed APK for all four configured radio arms. Switching baseline,
scan pause, high priority and combined policy does not require another APK.
Firmware remains last verified30245; no new throughput improvement is claimed.

The detached full offline context check completed successfully at06:07:36Z.
The initial baseline attempt then stopped before cell launch: served filenames
omitted the App-required `-full.etu` suffix. Preserve `trials/baseline` as failed;
its network and coordinator exited1 without forced termination, service listener
and worker closed, and preflight USB closed normally. No cell, App launch,
configuration retirement or OTA occurred. The phone still had7 capture directories
and its completed30245 snapshot was unchanged.

The adapter now derives only corrected served metadata from the immutable asset
manifest; package/target bytes and hashes remain unchanged. All14 source-bound
checks passed under `host-tests-003`, including all four names against the actual
`Backend.validate_served` contract, rejection of original malformed names and
the exact pre-cell recovery gate. Do not weaken the download contract or rewrite
the manifest/failure. New trial namespace is `trials-v2`; baseline launch owner
is `runtime/launch-baseline-002`. No new APK is required for this host-only fix.

## RADIO-03: Confirmed30246 Baseline And Capture Capacity

`trials-v2/baseline` completed with `FULL_INSTALL_VERIFIED`; coordinator, network
and s04 owners exited0 normally by2026-10-02T06:49:48Z. Report:
`analysis/1790923510784013900/result.json`, SHA-256
`62bf2c5aa2ead484dbd4343dcd6ef6a725d5f0202557a6d7ba7274253096ea36`.
Original finished snapshot is1052456 bytes, SHA-256
`b36de84896286524ca671707662676ef46a10aab979228f6746d37234260b5a1`.
Capture `1790922902993068-85c604a42872fe472af630d8`, PID12542.

Measured292928-byte transfer:32.611190s,8.771912KiB/s. END ACK to verified target
identity:23.154605s; six reconnect probes. DATA retransmissions and all ACK error
categories are0, MTU247/payload244/without-response. Both radio options were off.
This is one baseline sample, not proof of stable improvement or either target.
Both initial/final complete App reads match30246 SHA-256
`366ad628f13a4916cdbee141e7d908b3b50c7ef7dd8e9360f32145a2e74312f3`;
Boot remains `a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
BCB4, confirm_done1, state_snapped1 and sd_ready1; no reset/halt/flash was used.

The eight-capture limit is now reached. Before each remaining arm, the bounded
`p34_radio_archive.py` route preserves and moves exactly the immediately previous
inactive, FULL_INSTALL_VERIFIED capture, protecting the newest completed capture.
It checks closed owners, exact installed APK/PID/config, both original snapshots,
strict directory/file inventories, host copies and a second remote byte read.
Only after stopping the verified completed App does it move the selected directory
to `files/p34-archived-observations/<capture>` with no overwrite or deletion.
It checks all moved bytes and protected state afterward. Unknown files, changed
state or uncertain move outcomes stop the route; never repeat a spent attempt.
Host outputs remain in `.cache/p34-radio-fix/archive/<after-arm>` and owned
`runtime/archive-<after-arm>`; six offline guard tests passed in `archive-tests`.
The first archive operation targets30245, not the current30246 capture.

`archive/baseline` completed `INACTIVE_CAPTURE_ARCHIVED_VERIFIED` at06:55:44Z.
The30245 directory remains intact under the App archive path, all three files
have matching host and phone copies, and the protected30246 snapshot/config are
unchanged. Archive worker and USB exited normally; read-only ADB key unchanged.

Next active arm is `trials-v2/scan`, not the completed baseline or stale generic
session pointer. Service HTTPS/package verification passed. App launched at
07:13:16Z with capture `1790925192124168-1a3c191610d5b0cc5010d74d`.
Schema4 requests scan pause=true and high priority=false; all other axes retained.
Target30247 package292920 bytes, SHA-256
`ab16d1eb05e9e4591bf48292688300c69f9efbb82602c7b2a6513fd580a838e6`.
At07:15:59Z the original App health was healthy, lost0, starts0/ends0.
User has been asked to connect/download first, not start before the observer's
`READY_FOR_FULL_INSTALL_START` checkpoint. The network/coordinator/s04 owners
remain intentionally active with finite deadlines; no additional APK installed.

## RADIO-04: Scan Upgrade Succeeded, Recorder Failed

At07:20:09Z the scan arm recorder reported `invalid-record`, lost345, starts1,
ends0; the observer correctly closed as `FULL_INSTALL_INCOMPLETE`. Its later
read-only phone retrieval found lost9344, no snapshot and an empty PID2078 logcat.
Original files remain under `retrieve-scan-001`; do not manufacture a footer or
claim a speed from the incomplete records. The phone still had the same APK,
PID and configuration. No reinstall, App stop, reset or OTA replay was used.

Independent full native readback subsequently passed at07:26:20Z:
`readback-scan-001/result.json` is
`TARGET_30247_RAW_CONFIRMED_CAPTURE_INVALID`. Exact App/Boot bytes and ordinary
confirmation passed; checkpoint SHA-256 is
`fb6f2bbf2a78f97f83b270f196e869a399f8333d7ae9c3351b47c42ed54f4606`.
Retain30247. This is successful firmware installation with unavailable performance
evidence, NOT `FULL_INSTALL_VERIFIED` for the failed recording and not permission
to replay the successful scan transfer. Retrieval/readback owners closed normally.

Root cause: the new service emitted `OTA_RADIO` but the Dart recording prefix
allowlist and Python envelope reader lacked that prefix. Initial radio service
tests disabled diagnostics. Both consumers are fixed in development commit
`24ce23842d80241731eee335e60688447a55380b`, with four real-service/real-recorder
export-to-Python integration cases and cleanup-message/sensitive-line tests.
Existing26 Python parser regressions passed. Both-host full development CI
36978841701 passed. Dedicated APK request36979544261 is in progress under
`recorder-fix/apk-g1`; preserve the original APK receipts and certificate.
No main merge/release or new phone installation has occurred.

## RADIO-05: Recorder Repair Installed And Remaining Arms

Both-host APK run36979544261 passed. All288 chunks and the actual fixed signer
were verified; corrected APK SHA-256 is
`d1bc81c8b8151ef34d095df87bfbe7afcc40444b6f391446a9e0239f592c4991`.
`recorder-fix/install-001` completed `FIXED_SIGNER_RECORDER_UPDATE_VERIFIED`
at07:54:28Z, same package/certificate, no uninstall/data clear/OTA. Original
invalid capture, runtime configuration and Bluetooth grants remained intact;
new App stayed stopped and USB/owner closed normally.

`recorder-fix/recovery-001` subsequently archived the exact invalid scan directory
to `files/p34-archived-observations/1790925192124168-1a3c191610d5b0cc5010d74d`
and its configuration to the existing retired-config directory. All source bytes
were copied/read back on host and phone, not deleted or repaired. Protected30246
snapshot remained unchanged; no new App launch occurred. Final result is
`INVALID_CAPTURE_ARCHIVED_TARGET_RETAINED`, with performance still UNAVAILABLE.

Remaining finite matrix: priority-only30247-to30248, then combined30248-to30249.
Do not replay the successful scan OTA solely for missing measurements. The new
`p34_radio_followup.py` entry uses the repaired APK and its matching Python reader
without changing the original root reader or frozen trials. Its initial predecessor
is explicitly `RAW_CONFIRMED_CAPTURE_INVALID`, not a fabricated full snapshot.
Fresh native admission and final complete raw/Boot verification remain required.
The combined arm requires actual `FULL_INSTALL_VERIFIED` priority evidence.
The new observation wrapper saves the Android ring even when an observation guard
fails, without waiting for a finished snapshot method to be reached.

Seven offline followup tests passed, including wrong-image rejection, no replay,
failure preservation, exact repaired APK, and repaired-reader corruption/secret
rejection. Full binding check is owned by `runtime/followup-check-001`.
New trial namespace is `recorder-fix/trials`; original `trials-v2/scan` remains failed.

## RADIO-06: Host Startup Adapter And HTTP530 Recovery

The first priority attempt, `recorder-fix/trials/priority`, failed before admission
with `AttributeError: module 'recorder_fixed_envelope' has no attribute 'same_device'`.
Its coordinated tunnel then closed, explaining the user's check-update HTTP530.
The source-checkout envelope supports the new prefix but lacks runtime-only query
helpers. The correction loads a private copy of the original runtime reader and
extends only its prefix tuple after requiring exact agreement with the tested
APK reader. Historical readers and failed trial files remain unchanged.

First `startup-recovery-001` stopped without any App mutation because the App PID
changed from6169 to14503. `startup-inspect-001` then preserved current-process
logcat, exact APK/config and latest captures. The old capture had0 starts/0 ends,
healthy=true; current-process GET_INFO still reported30247 with its exact SHA.
`startup-recovery-002` verified the reconciled PID and original query bytes,
stopped the idle App, and archived that query capture/config without deletion.
Result: `PRESTART_QUERY_ARCHIVED_NO_TRANSFER`; USB and recovery owners closed.
No priority OTA was replayed and no new APK was installed for this host repair.

Nine source-bound tests passed under `recorder-fix/host-tests-002`, including the
actual `Backend.launched_capture` path, case-normalized identity checks, corrupted
capture rejection and no-OTA recovery proof. New attempt namespace is
`recorder-fix/trials-v2/priority`; launcher is `runtime/followup-launch-priority-002`.
The old expired URL must not be reused; wait for fresh HTTPS/package and App query
admission before inviting the user's Start action. Current retained firmware30247.

## RADIO-07: Priority-Only Confirmed30248

`recorder-fix/trials-v2/priority` completed `FULL_INSTALL_VERIFIED` at09:25:50Z;
coordinator/network/s04 owners closed normally by09:25:52Z. Analysis report
`analysis/1790932863718168500/result.json` SHA-256:
`8dbe06c45c4891ec2c3468baf66fcbc9d3b7b0aec33c5833d6fe513b6a2bc562`.
Original snapshot1047427 bytes, SHA-256
`1300b23616fd23d9f03d56ca685e28092e0ea8306fceaaa043aa292f4d0d0401`;
capture `1790932265347583-a45ac20990bc8526b1711a8c`, PID31319.

Measured293081-byte transfer27.922012s,10.250404KiB/s; END-to-verified-identity
22.137555s. All2290 DATA segments were unique, with0 retransmissions and0 ACK
error/duplicate/malformed/no-progress/abort counts. Request accepted high priority,
scan pause=false, no unresolved cleanup; actual negotiated interval stays UNKNOWN.
ACK P50/P95/P99 were85.054/154.750/182.266ms. Baseline was8.771912KiB/s and
23.154605s reconnect: this sample is faster, not stable or same-package acceptance.
Both target50KB/s and20s remain unmet.

Initial/final full App hashes match30248:
`2962c8d7dbcfee6c8ec904a7f3ec92a22677f3d96f9c766b6bfcf54ea0e4e47b`.
Boot unchanged; BCB4, confirm_done1, state_snapped1 and sd_ready1.
The corrected writer/runtime reader now produced and validated a real full capture.

For the last combined arm, `p34_radio_combined_archive.py` reused the checked
archive implementation to preserve inactive30246, protecting current30248.
`recorder-fix/combined-archive-001` passed with all bytes preserved on both sides,
no deletion, and the current snapshot/config unchanged. It did not select the
invalid30247 recording. Full combined binding check is owned by
`runtime/followup-check-combined-001`; no new APK required.

## RADIO-08: Reusable Recorder Capacity Diagnosis

The first combined attempt (`recorder-fix/trials-v2/combined`) ended before
an upgrade: `FULL_INSTALL_INCOMPLETE`, App start window expired. Early inspection
found seven recordings, but another query process consumed the eighth slot before
formal launch. PID21189 had no recorder. This is a host admission race, not a
measured combined-arm failure or a reason to reinstall the APK.

`Tools/ota/p34_runtime_doctor.py` is the reusable entry, with explicit absolute
run and fresh project-local output paths:

    python -I -S -B -X utf8 Tools/ota/p34_runtime_doctor.py launch --run ABS_RUN --out ABS_FRESH_OUT
    python -I -S -B -X utf8 Tools/ota/p34_runtime_doctor.py recover --run ABS_RUN --out ABS_FRESH_OUT --diagnosis ABS_RESULT

Diagnosis attaches read-only to the existing private USB owner; it never restarts
that owner. Recovery requires closed prior owners and an exact diagnosed
`NO_CURRENT_CAPTURE_STORE_FULL` state. It preserves bytes on host and phone,
archives only an explicitly owned unused query recording, and retires the expired
configuration. It does not delete recordings, reinstall, or perform OTA.

Original diagnosis: `.cache/p34-runtime-doctor/combined-001/result.json`.
Recovery: `.cache/p34-runtime-doctor/combined-recovery-001/result.json`,
`PRESTART_CAPACITY_RECOVERED`; its runtime exited normally with code0 and no forced
termination. Seven active-store captures remain; completed30248 stays protected.

`p34_capture_capacity.ensure_capacity` now runs inside the formal provision path,
with the App stopped, immediately before writing configuration and launching.
Full capacity without a safely archivable owned query fails closed. Snapshots,
unhealthy/unfinished captures and unknown files are protected. Six doctor/capacity
tests passed; ten followup tests passed in `recorder-fix/host-tests-003`, including
proof that failed capacity admission prevents the underlying provision call.

Recorder readiness alone is not permission to start an upgrade. Require actual
current-PID producer health, matching configuration, package admission and
`READY_FOR_FULL_INSTALL_START`; `APP_LAUNCHED_CONNECT_AND_DOWNLOAD` is only an
intermediate state. Continue the unspent combined30248-to30249 cell in
`recorder-fix/trials-v3/combined`, preserving the failed v2 attempt. Both radio
flags are enabled; the existing APK and prepared package remain unchanged.

## RADIO-09: Combined Confirmed30249 And Bottleneck Decision

`recorder-fix/trials-v3/combined` completed `FULL_INSTALL_VERIFIED`.
Report: `analysis/1790939796737635200/result.json`. Coordinator, network and s04
owners all exited0 without forced termination. Same installed APK; no reinstall.
The just-in-time capacity gate saw seven captures and needed no archival.
Current PID6495 was admitted only after original query and package verification.

The293036-byte transfer took26.006960s:11.003515KiB/s (11267.60B/s).
END ACK to verified identity took22.155833s. Compared with the single baseline,
throughput improved25.44%; compared with priority-only it improved7.35%.
Installation/reconnect is essentially unchanged from22.137555s priority-only.
Neither50KB/s nor20s is achieved; these are sequential screening samples, not
same-package A/B, stability acceptance or the1MiB reference result.

All2290 DATA segments were unique; zero retransmissions and ACK errors. Scan
pause and accepted high priority were recorded; negotiated interval remains
UNKNOWN. Snapshot SHA-256:
`954baab9302929071259fad8e913d9c09c34b8cf942df5b45bc4c39417eab35d`.
Full raw initial/final readback confirms30249 App SHA-256
`9443421b1118eb3b8791be0501e5cc40f37b85c408eed3d33c41307ab9950925`;
Boot remains `a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
BCB4, confirm_done1, state_snapped1, sd_ready1. The transient trace lacks an
initialized/confirmed target sample; final raw confirmation is valid but must
not be used to manufacture internal Boot timing. Observed Boot residency only
is bracketed5.9205174 to8.123661s.

Reused `Tools/ota/p34_wait_analysis.py` on both original reports, without device
operations. Outputs: `recorder-fix/comparison-001/{combined,priority}-waits.json`.
Combined App-clock partition closes exactly at26006960us:

| Component | Combined us | Priority-only us |
| --- | ---: | ---: |
| DATA GATT writes | 15907716 | 17358197 |
| Last send to block durable | 9199132 | 9746700 |
| Inferred full-window credit wait | 0 | 0 |
| After-credit same-block gaps | 596242 | 547957 |
| First-send preparation | 74928 | 71569 |
| BEGIN to zero durable | 159191 | 128829 |
| Final durable to END ACK | 69751 | 68760 |

DECIDED: stop blind baud/window/radio tuning. There were no full-credit gaps;
window expansion has no demonstrated benefit. Next bounded design review should
target fewer platform write round trips and block-boundary durable latency.
Preserve single byte-stream ownership, cancellation/late-write poisoning,
session/sequence/credit semantics and readback-before-durable guarantees. Do not
remove awaits or issue concurrent characteristic writes as a shortcut.

The firmware performs erase, program, readback and journal commit before durable
advances (`commit_current_block`). Native erase/program samples are3.451064s
and0.484631s, respectively, and overlap App-observed waits. They must not be added
to the partition above. Conditional on retaining serial block receive/commit,
DATA UART bytes plus these measured costs imply about39.26KB/s before other
overheads; this is a model, not a measured ceiling. Reaching50KB/s likely needs
more than radio flags: investigate safe batching and receive/commit scheduling
with host regressions before another finite hardware cell. Retain30249; no
automatic repeat, downgrade or extra APK installation is justified by this result.

## RADIO-10: Saved Checkpoint And Batch Geometry Prototype

User requested Git preservation followed by further optimization. Local branch
`checkpoint/p34-radio-20261002`, commit
`d882a8401146f1b034df793d3cfe85e4e8666e5d`, preserves eight scoped host tool/test/note
files using an isolated index. Main HEAD and its index were unchanged; no push,
merge or release. Installed APK source remains commit
`24ce23842d80241731eee335e60688447a55380b`. This is a local checkpoint, not a
standalone distribution of the historical cache-dependent hardware harness.

Added pure offline planner `Tools/ota/p34_batch_plan.py`. It caps each reservation
by actual free credit and a bounded batch size, preserves frame bytes and offset
order, stops at the durable block boundary and maps each frame completion to its
containing GATT chunk. It is not connected to the App sender. Original-report
replay output: `.cache/p34-batch-plan-20261002/combined.json`.

| Frames per batch | DATA calls | Saved calls | Maximum chunks per batch |
| --- | ---: | ---: | ---: |
| 1 | 2290 | 0 | 1 |
| 2 | 2289 | 1 | 2 |
| 3 | 1574 | 716 | 2 |
| 4 | 1717 | 573 | 3 |
| 8 | 1431 | 859 | 5 |

DECIDED: shortlist three frames, not two or four, for the first bounded runtime
prototype. Three minimizes cancellation exposure while eliminating31.27% of DATA
write calls under the geometry model. This assumes enough free credit before
each batch; it predicts neither runtime throughput nor ACK timing.

Eleven pure planner tests passed. Eight native decoder checks passed in
`.cache/p34-batch-plan-20261002/wire-002`: the real `ota_ble_frame.c` accepts the
unchanged stream, while the fixture rejects CRC damage, truncation, missing and
reordered frames. Build uses host GCC with `-Wall -Wextra -Werror`, no compiler
diagnostics. `wire-001` is preserved as a failed fixture run: demux storage was
not zero-initialized before the reset API that preserves bad-frame counters.
The fixture was repaired, not the production parser.

Before App integration, require tests for reserved-but-unsent ACK rejection,
per-frame send timestamps at actual chunk completion, early ACK buffering,
partial-batch timeout/late-write poisoning, frame-boundary cancellation, credit
shrink, bitmap resume gaps, block commit during a write and default-off behavior.
Do not feed batched logs into the current one-GATT-write-per-DATA timing partition;
its pairing assumption must be explicitly versioned before hardware observation.
All work here is host-side; no new APK, OTA or device mutation was performed.

## RADIO-11: Implemented Batch Sender And End-To-End Development Checks

Owner: Codex root, authorized root unchanged. Exclusive checkout
`.cache/p34-batch-fix/src`, branch `dev/flutter/p3-4-three-frame-20261002`.
Latest code commit: `70a41c848099b3051a5244abaae899bd9d6027d5`.
Development CI37018647007 passed on both hosts; no merge/release/deployment.
Use `git show` with this commit and
`docs/ota-exec-notes/P3-4-three-frame-2026-10-02.md` for the branch handoff.
Root helper `Tools/ota/p34_batch_validation.py` preserves the borrowed object
stores and original root index. Do not use bare Git for this checkout.

Transport now supports default-off three-frame batching, bounded by actual free
credit and the current4KiB block. Frames become ACK-eligible only before the
chunk containing their final bytes is dispatched. Completion accounting is per
chunk, not delayed to batch end. Cancellation drains only a partial frame; pause
also releases the write owner at a frame boundary so INFO rechecks cannot
deadlock behind the paused batch. Retransmissions remain single-frame and
timeout/late-write poisoning remains in force.

Schema5 adds `dataBatchFrames` (1 or3). Schemas1-4 remain single-frame. Batch3
requires configured cached GATT/without-response policy and actual
without-response binding. The original recorder accepts the existing
`OTA_LINK_SAMPLE` prefix with `kind=batch_chunk`; the summary's
`transfer.dataBatch` explicitly versions its chunk counts. Six pure Python
checks and actual service/recorder/exported-snapshot/Python-reader tests cover
the new `Tools/ota/p3-4-link-stats/batch_timing.py` analyzer. Its residual time is
not labeled isolated ACK/flash cost; partial ACK sample quality stays explicit.

Failures preserved, not papered over: first new transport test fixture used a
cleanup method defined only on a subclass (37006326859); moving it to the shared
fixture restored execution. The exported-snapshot check caught missing CI sparse
checkout entries (37014590655), then isolated Python sibling import setup
(37015514016). The reader's text-return contract was also normalized with
splitlines. Reusable `p34_batch_ci_logs.py --run ID` retrieves exact-branch
original logs without repeating CI; it strips credentials at signed redirects.

Next finite screening cell:30249-to30250, one legal FULL transfer, batch3 with
both measured radio policies retained, baud921600/window28. Existing measured
combined30249 is the predecessor/control; do not replay its upgrade. Package
preparation is complete at `.cache/p34-batch-fix/assets/result.json`:
292946 bytes, SHA-256
`f32f572c173dd3e3d73a7e835133e73b98d0e77ebb8d830b26632dbf897d719f`;
target raw616540 bytes, SHA-256
`ee109334b6db2171fd402f6074dd4635027f130919c9a8bb57fb620b8622d99c`.
Native decode/readback and negative package checks passed. Executable bytes are
unchanged; only the version header differs. Retain ordinary Boot confirmation,
full App/Boot readback, just-in-time capacity protection and original snapshots.

One explicit same-package/same-development-signer APK dispatch was accepted at
14:29:18Z for the above commit, run37020212404. Receipt:
`.cache/p34-batch-fix/apk-g1/accepted.json`; helper `p34_batch_artifacts.py`.
At this entry it is still building, not collected or installed. Do not request
another APK to compensate for a collection failure. Prepare and self-test the
schema5 hardware controller and preserve/retire the prior recording/config before
opening any user Start window. Actual phone firmware remains verified30249;
no new device operation or measured batch throughput has occurred.

APK collection subsequently completed: run37020212404 passed both hosts, the
288-chunk APK download had zero failed chunks, and `apk-g1/apk.json` verifies
SHA-256 `97cacd39f163357e6844098d1840adefde4c1aee24cf52edd8e6fd003fb8320a`
with the unchanged development certificate and application ID. APK is not yet
installed. `Tools/ota/p34_batch_artifacts.py wait-collect` is the bounded
wait/download entry; preserve its original download and dispatch receipts.

Read-only phone preflight `.cache/p34-batch-fix/preinstall-001/result.json` at
14:46:29Z reports `NEEDS_PHONE_WAKE`: same installed APK, PID6495, original
snapshot/config preserved, USB owner closed normally. No App stop/install/launch
or OTA occurred. `p34_batch_install.py check` verified exact APK/CI/signer and
prior completion inputs. Its `launch` entry is prepared for one same-signer
replacement after the user wakes/unlocks the phone; it preserves capture/config
and permissions, does not launch the App, and refuses changed process identity.
The schema5 hardware trial controller/capacity preparation still follows before
requesting any OTA Start. Do not mistake this wake request for transfer readiness.

## RADIO-12: Batch Observation Route Ready

Same-signer replacement completed at 14:54:19Z with
`FIXED_SIGNER_BATCH_UPDATE_VERIFIED`; installed APK matches the RADIO-11 artifact.
Snapshot, configuration and permissions were preserved, without uninstall/data
clear or App launch. Receipt: `.cache/p34-batch-fix/install-001/result.json`.
The inactive priority capture was archived, not deleted, at 14:55:37Z. The current
30249 capture/config stayed unchanged, seven active capture directories remain,
and both USB owners closed normally. Receipt:
`.cache/p34-batch-fix/archive-001/result.json`.

`Tools/ota/p34_batch_trial.py` reuses the original device/readback controller
through a private schema5 adapter. Ten host-only tests passed in
`.cache/p34-batch-fix/host-tests-001/`: exact config and observation types,
APK/predecessor bytes, capacity-before-provision, actual MTU/durable/device,
unique reboot markers and explicit partial ACK quality. Full offline bindings
passed with 166 sources in `runtime/offline-001/worker.log` under the same area.
No batch speed has been measured yet. The finite RADIO-11 cell remains unspent.

The controller uses the new per-chunk timing reader only for this screening;
the historical full-trace acceptance function remains unchanged on disk.
Partial ACK samples cannot qualify as complete P99 evidence. Final success
still requires original snapshot, full App/Boot bytes and ordinary confirmation.
Next: bounded service/observer launch, then actual query and download admission
before inviting user Start. Do not reinstall the APK or regenerate the package.

## RADIO-13: Batch3 Measured And Retained

Run `.cache/p34-batch-fix/trials/batch` is `FULL_INSTALL_VERIFIED`.
Original report: `analysis/1790955249035971100/result.json`, SHA-256
`8679eb51f949062218d119ed445ba3987abe933516f3e783609f38b26aff7514`.
All three worker owners closed normally. Full initial/final target readbacks
match `ee109334b6db2171fd402f6074dd4635027f130919c9a8bb57fb620b8622d99c`;
Boot is unchanged. Final BCB4, confirm_done1, state_snapped1, sd_ready1.
Retain30250; do not replay this completed transfer.

| Metric | Prior combined | Batch3 |
| --- | ---: | ---: |
| Package bytes | 293036 | 292946 |
| BEGIN to END ACK seconds | 26.006960 | 21.020354 |
| Throughput KiB/s | 11.003515 | 13.609670 |
| Throughput decimal KB/s | 11.267599 | 13.936302 |
| END to verified identity seconds | 22.155833 | 24.423845 |
| DATA GATT calls | 2290 | 1573 |
| DATA GATT seconds | 15.907716 | 10.927220 |

This sequential screen improved transfer throughput23.684751%, saving4.986606s,
but installation/reconnect worsened2.268012s. Neither requested target is met.
It is not identical-package A/B or reference/stability acceptance. All2289 DATA
frames were unique; zero retries, duplicate/error/malformed/no-progress ACKs,
and zero early invalid/unsent ACK samples. Complete latency set: P99=173470us.
Radio policies remained acknowledged; negotiated interval remains unknown.

Reusable `Tools/ota/p34_batch_review.py` verified original reports, snapshot,
readbacks and owner closures and produced `.cache/p34-batch-fix/review-001/`.
Four host regressions passed in `review-tests-001`. Transfer residual10.093134s
is not isolated flash/ACK time. Six reconnect attempts took21.827983s total;
round time24.350327s leaves2.522344s outside attempts (including five500ms waits).
Attempts3/5 spent about3.01s in failed discovery; attempts2/4 reached INFO but
timed out at about2s; attempt6 completed in3.242551s. These failures overlap
ordinary firmware apply/reboot, so their sum is not recoverable time.

Native apply/backup tick counts6357/7005ms are not calibrated wall time. Boot
residency is bracketed6.607289..9.342061s. Transient confirmed-target sampling
is missing; final full readback/ordinary confirmation remains valid separately.
DECIDED: retain batch3. Reducing500ms poll sleeps alone cannot demonstrate the
20s goal; even deleting all measured outside-attempt time leaves over21s.
Next inspect discovery/INFO retry behavior and apply/backup IO, preserving fresh
connection identity and ordinary confirmation. No reason to reinstall this APK.

## CRC-01: Default-Off App Candidate

Batch screening checkpoint is `c6397b2b084658e9f8023b7485bea5680f234619` on
local `checkpoint/p34-batch-20261002`; main/index were preserved, no push.
The App source remains the already-pushed `70a41c84` development revision.

New host candidate: `boot/src/boot_crc32.c` has default-off
`CONFIG_OTA_APP_CRC32_NIBBLE`. Two 4-bit lookups replace eight bit steps with
the same reflected polynomial, initial/final XOR and streaming state. No check
is removed; the installed Boot is not modified. `p34_crc_screen.py` passed9224
equivalence checks (known vector, lengths, arbitrary states, streaming chunks,
null handling) plus original backup tests with the flag both off and on.
Host16MiB timing0.193s bitwise versus0.086s candidate is not an MCU speed result.

The isolated App-only build in `.cache/p34-crc-screen/` starts from the verified
erase source tree, proved executable-equivalent to retained30250 outside its
version header, and overlays only CRC source. Candidate image616620 bytes is80
bytes larger. ARM disassembly shows two table loads in internal Flash. No Boot
target was built. GCC reported638 warnings, all equal to the retained baseline,
zero new warnings and zero errors. Initial comparison failed on CMake's embedded
`D_/.../.cache/...` paths; preserve the original failure. `p34_crc_review.py`
reuses the existing tested warning normalizer, adds eight path/content/count
checks (15 total), and verifies the existing artifacts without another build.

Finite next matrix: FULL30250-to30251 bootstrap, then conditional
FULL30251-to30252 measurement, same batch3 APK/radio/baud/window/cadence. The
bootstrap installs CRC code but its apply/backup is still run by old30250;
only the second cell measures the candidate's installation path. Each requires
actual confirmed predecessor, original snapshot, full App/Boot readback and
normal BCB confirmation. Stop dependent mutations on uncertain state. Preserve
the existing Boot and retain the latest verified target; no automatic downgrade.
User owns necessary connection/download/Start UI actions, not repeat approvals.

`p34_crc_assets.py` produced both legal packages and exact new map/ELF bindings;
native decode/readback and four negative-package cases per group passed.
Bootstrap292986 bytes, measure292982 bytes. Outputs and finite worker receipts
remain under `.cache/p34-crc-screen/`; APK reinstall is not planned. Archive only
the inactive30249 capture to free one slot while preserving the original30250.

CRC bootstrap controller `p34_crc_trial.py` passed seven host gate checks in
`trial-tests-002/` and full offline174-source binding checks in
`runtime/offline-002/`. Preserve failed `offline-001`: a historical decoder test
required the old root CRC bytes. The new controller uses the existing historical
resolver with a single exact path/hash mapping to immutable
`.cache/p34-erase/f/boot/src/boot_crc32.c`, SHA-256
`b7f5c763006fa3bc4b60a861fb82c2a1311373846aca6deb70cc09277287d0c4`.
Wrong hashes still fail; old records and current candidate source are unchanged.
The archived30249 capture is preserved under `archive-bootstrap/`; protected30250
snapshot/config and normal USB closure passed. No CRC OTA has occurred at this
entry. Bounded launch is `runtime/launch-001`, targeting `trials/bootstrap`.

That first host window closed before any cell existed. Its coordinator entered
cleanup at16:36:32Z; network setup completed and closed at16:39:38Z, but the90s
cleanup wait had already thrown and masked the primary exception. The original
trigger is UNKNOWN, not a demonstrated DNS or device fault. All original owners
and listener are now closed; prestart inspection preserved completed30250 and
the unchanged config, with no App launch/OTA/cell directory in that window.

The CRC-only coordinator now polls write-once ready/closed receipts while waiting
for service preparation, records a primary error before cleanup, and preserves
cleanup errors separately under a finite600s cleanup bound. Actual readiness
still uses the original live-owner and remaining-service guards. Ten host tests
passed in `trial-tests-004`, including primary-plus-cleanup failure injection.
The new finite launcher is `runtime/launch-002`, output `trials-v2/bootstrap`;
same tested APK/package/build, no recompile/reinstall or repeated OTA.

`trials-v2/bootstrap` correctly preserved its primary failure: a newly opened
App PID20776 created unused capture `1790959268475229-bc770f2b66f2da82ee932e56`
under the old owned configuration, filling slot8 before preparation. It has
zero starts/ends and no successful queries; no network or device cell started.
The coordinator closed normally with failure evidence, not a cleanup-masked
trace. `Crc.inspect` now runs a pre-prepare capacity check: validate the exact
owned unused capture/config/PID, preserve its original bytes, stop that idle
App, and call existing `ensure_capacity`; then perform the canonical fresh
inspection. The later just-in-time provision gate remains. Twelve tests passed
in `trial-tests-005`; `runtime/launch-003` targets `trials-v3/bootstrap`.
Do not reopen App while host preparation is running; the controller launches
it when the verified service and recording route are ready.

## CRC-02: Candidate Installed, Measurement Prepared

`trials-v3/bootstrap` completed with `FULL_INSTALL_VERIFIED`; report
`analysis/1790964090117998900/result.json`, SHA-256
`2101a30be071caad5ad5c77b208615585a76b2e07ba47d6d51f9d6866ba44c79`.
Full target SHA-256 is
`09a60200a8e88a1b159ba4cfe3726e056e30b63c16134e511c1cbd22fe9a1bad`.
Boot is unchanged; BCB4, confirm_done1, state_snapped1, sd_ready1. All owners
closed normally. Retain30251; do not replay this bootstrap.

Bootstrap transfer21.528448s,13.290282KiB/s, END-to-identity43.943652s. This is
not the CRC implementation's apply/backup measurement: those phases ran in
old30250 (6324/6996 device ticks ms). Boot residency22.195027..24.477243s is
observed separately. Byte comparison under the unchanged4096-byte Boot copy
geometry finds145 different blocks out of151 for this executable change, versus
one different block for the prepared30251-to30252 measurement. Do not equate
bootstrap installation latency with the preceding header-only screening sample.

`p34_crc_measure.py` prepares the measurement with the same APK, batch3 and Boot;
seven host checks passed in `measure-tests-001`. The inactive30250 capture was
archived under `archive-measure/`, preserving current30251 snapshot/config and
normal USB closure. The fresh measurement output is `trials/measure` and its
offline check is `runtime/measure-check-001`. A measured CRC gain is still UNKNOWN.

## CRC-03: Measurement Complete, No End-To-End Gain

`trials/measure` is `FULL_INSTALL_VERIFIED`, original report
`analysis/1790966205697885600/result.json`, SHA-256
`2c97e9787ef8cb65ea949ee47b2447a2d3a02ba767b2758c381fed7612f01c20`.
Original snapshot SHA-256:
`00b1f43e60236fc50bbfbf77946411da9138c29e62ac3c696efc72671dcd0c74`.
Full616620-byte App SHA-256:
`4733c5b3b2bb0da34b509821fa75bd2c642d0b27b641a3f7ee647062d4d800c6`.
Boot unchanged, BCB4, confirm_done1, state_snapped1, sd_ready1. All owners and
USB closed normally. Retain30252; do not repeat its successful upgrade.

Measured transfer21.267146s =13.453391KiB/s =13.776273 decimal KB/s, with2289
unique frames,1574 DATA GATT chunks, zero retries/ACK errors, complete ACK set
and P99=174485us. DATA GATT11.135639s; remaining10.131507s is not isolated
ACK/flash time. END-to-identity30.166151s is worse than batch-only24.423845s;
neither50KB/s nor20s is met. No end-to-end CRC speedup is claimed.

Original P34COST full/backup totals6261/6254ms and residuals2158/1904ms are
MCU ticks, not calibrated wall time. The earlier batch-only values6356/7005ms
and2238/2683ms show a small full-phase reduction and751ms lower backup ticks,
but do not justify calling overall OTA faster. Boot residency is bracketed
6.248692..9.448894s; transient confirmed-target timing remains missing separately
from the valid final full readback and normal confirmation.

The App reconnect round took30.088979s, with six attempt durations
2.011356,9.602378,3.029601,4.470775,3.032110,5.411766s. Outside-attempt time is
2.530993s. Attempt2 includes1.428931s binding and2.008772s INFO wait; the
remaining connect/dispose/disconnect breakdown is UNKNOWN. Attempt6's5.411766s
includes1.394698s binding and0.901254s INFO. Do not label the residual as a
particular Android call without evidence. Original logcat printing was delayed:
its line timestamp cannot replace embedded OTA_MONO times for phase arithmetic.

DECIDED: do not iterate CRC tables or reinstall APKs on the assumption that CPU
is the remaining bottleneck. Inspect actual BLE connection/PHY parameters and
probe lifecycle first. `Tools/ota/p34_hci_status.py` performed one bounded
read-only USB check after all measurement owners closed. Receipt:
`.cache/p34-hci/status-001/result.json`; Android API33, standard btsnoop
properties empty and settings null. This is UNKNOWN configuration/readability,
not proof that logging is enabled or disabled. No setting changed, no App
restart and no OTA. A user confirmation of the Developer Options HCI setting
is the next observation input; future link negotiation can be captured without
replaying this completed OTA.

## HCI-01: Full Logging Confirmed, Current Export Needs Scope

After the user's enabled confirmation, `p34_hci_status.py --attempt 002`
checked the vendor/system property already used by the existing exporter:
`persist.sys.bluetooth.btsnooplogmode=full`. The first checker had omitted this
property; its empty standard fields did not establish that logging was off.
Keep status-001 as the original incomplete configuration probe, not a false
disabled-state baseline. Both status-002 and status-003 closed USB normally.

Direct shell reads of `/data/misc/bluetooth/logs`, its standard snoop file and
`/sdcard/btsnoop_hci.log` are unavailable. The report directory
`/data/user_de/0/com.android.shell/files/bugreports` is readable. Read-only
inventory in `.cache/p34-hci/status-003/result.json` shows only the two existing
September30 ZIP reports and their system sidecars; none covers current30252.
No new report, setting change, APK operation or OTA was performed.

Reuse `p34_hci_export.py`, `p34_hci_att.py` and `p34_hci_compare.py`, not a new
parser. The old September30 HCI evidence under
`.cache/p34-target50/hci-export/ack-boundary.json` recorded45ms ->7.5ms ->45ms
connection intervals, DLE251 octets, and no observed PHY update. This historical
connection is not evidence of the current App's high-priority outcome. Its
old corruption finding also must not be relabeled as a current CRC/OTA failure.

Next export route requires a separately scoped new system report in the above
phone directory (and its system-managed log/stats sidecars). The previous
two-report operation is closed, not reused as authorization for a third report.
Request one new report, retain prior ZIPs, never upload/save the whole report
on the host, and extract bounded Bluetooth members only into project-local
`.cache/p34-hci/`. Report generation may temporarily re-enumerate USB; reconcile
the generated report rather than issuing another generation if collection fails.

## HCI-02: Single Current Report Export

The user explicitly approved one new report in the HCI-01 phone directory,
including system-managed log/statistics sidecars. Existing reports remain intact;
no full report is retained on the host or uploaded. This is a new single-report
scope, not a replay of the closed September30 two-report scope.

`Tools/ota/p34_hci_current.py` reuses the original exporter parsers and USB
ownership/closure implementation. A scoped initial-receipt adapter supplies a
1500-second USB deadline inside an 1800-second owned worker. The historical
600-second USB default cannot admit a 900-second report command. Neither the
historical helper nor any running source is modified. Generation has a durable
write-once intent; an existing intent prohibits generation replay. Retrieval
verifies size and two phone SHA-256 observations, reads the ZIP in memory, and
writes only bounded HCI members plus metadata. Missing/lossy captures remain
explicit and are not current-OTA evidence merely because they were exported now.

Host self-tests: `.cache/p34-hci/current-tests-001/result.json`, 24 passed,
zero device operations. Includes deadline, scope, uncertain-command/no-retry,
path traversal, extraction bounds and truncated packet regressions. Current
operation: `.cache/p34-hci/export-current-001`, owned runtime
`.cache/p34-hci/runtime/export-current-001`. Bound input remains the verified
30252 measurement and unchanged installed APK. No OTA, reset, App launch,
installation, rollback or Boot operation is part of this diagnostic cell.

HCI-02 completed: owned worker exited0 without forced termination; USB server,
launcher and stop returned0, port5062 closed, read-only ADB key unchanged. The
single report completed in the approved phone directory. Host retained only
two HCI files (416839 and3168479 bytes) plus metadata, not the report ZIP.
Both files have zero truncated records and zero reported drops. HCI-01 export
file has no new target connection event; HCI-02 file contains the30251-to30252
measurement. Those are file numbers, not a second report generation.

## HCI-03: Exact OTA Correlation And Durable-Block Tail

`Tools/ota/p34_hci_ota.py` reuses the strict HCI/ATT decoder and protocol CRC
validator. It reassembles characteristic streams across split/batched GATT
values, binds FFF1/FFF2 from original declarations, verifies every DATA byte
against the original292982-byte package and requires the complete ACK set,
END package SHA, old30251 image SHA and post-END30252 image SHA. Latest result:
`.cache/p34-hci/ota-analysis-002/result.json`; original HCI SHA
`9054258ab237b9a22832135cba941328c4eef2bb0304096a9ef1fd2063e9014b`.
Host checks:18 existing ATT/correlation tests and6 current OTA stream tests,
including the real original measurement, all passed without device operations.

Observed generation2 contains2289 DATA frames,2289 ACKs,1574 DATA ATT writes.
Connection interval was15ms before DATA and did not change during DATA; final
data-length update before DATA was251 octets in both directions. No observed
PHY update establishes the current PHY. Old45ms/default connections are not the
active DATA-phase interval. HCI BEGIN-to-END-ACK21.257885s and END-ACK-to-target
INFO30.071694s corroborate the original App stopwatch21.267146s/30.166151s;
they are not new performance improvements or a new OTA run.

Absolute snoop timestamps appear to contain vendor local-wall-clock encoding.
The exploratory `current-analysis-001/result.json` fields labeled UTC are not
verified UTC and must not be aligned to host clocks as such. Preserve that
exploration; use only original identities/package bytes and differences within
the same HCI clock in the final correlation. No cross-clock subtraction is used.

For the72 durable blocks, disjoint first-DATA-to-last-DATA intervals sum
11.747984s, last-DATA-to-durable-ACK tails sum8.383299s, and ACK-to-next-DATA
intervals sum0.895409s. Every last-block ACK confirms the actual durable end.
FIFO HCI Number Of Completed Packets reports split the8.383299s tail into
1.268646s before controller completion reporting and7.114653s after reporting.
All samples are nonnegative in this capture. Completion reporting is not an
exact over-air timestamp; the latter span includes module/UART/MCU/return-path
work and must not be called isolated Flash time. Tail and its two subspans
overlap by definition, so never add all of them together.

Existing same-run MCU profile provides independent nested durations:
payload erase3.366866s, payload program0.488614s, payload verify0.039581s,
ACK write calls0.855085s, pump work5.679925s. It records234 pump entries,
RX ring peak3874/4096, no drops/UART/parser errors. These MCU timings cannot
be subtracted from HCI spans as exclusive stages. Configured pump period is
20ms, but observed aggregate pump-start spacing is much larger; next diagnosis
must distinguish cooperative-loop delay from tick drift and synchronous flash
blocking, rather than assuming20ms is the actual service cadence.

Decision: do not rotate/reinstall the APK, replay this completed OTA, or claim
50KB/s from a connection-priority acknowledgment. Preserve30252/Boot/BCB.
Prioritize the receiver scheduling/durable-block tail and separately bound
connect/INFO/disposal timing. No CRC lookup expansion or unmeasured baud increase
is justified by these observations. All new host outputs in this continuation
are under `.cache/p34-hci/`; code/tests and this note remain in the project root.

## UI-01: Receiver Scheduling Candidate

Two finite, read-only native windows used `p34_pump_clock.py` and the exact30252
image/map. Both verified the full616620-byte image, sampled11 times, then closed
normally without reset, Flash/RAM writes, RTT consumption or OTA. Results live
in `.cache/p34-hci/pump-clock-001` and `pump-display-001`. Native-history access
used the existing exact-path authorization; `JLinkDLL.ini` bytes/mtime did not
change in either window. DWT count is frozen in these idle observations and is
not used as a clock oracle. SysTick reload287999/core288MHz and host-vs-millis
advance are consistent with approximately1ms ticks, not a fourfold clock error.

The20ms pump task reports scheduling errors of0..60ms, frequently39..41ms even
without a transfer. In the display window, about5239ms of MCU time contains74
completed refreshes totaling3898ms, approximately52.7ms per refresh and74.4%
occupancy. These are idle observations, not a synchronized OTA causal proof;
they support a small receiver/UI scheduling discriminator before more baud work.

Candidate `CONFIG_OTA_UI_CADENCE` defaults0. When explicitly enabled for an
App-only development build, `OtaUiCadence` calls the LVGL handler at most every
200ms while `OTA_OverlayIsOtaOwned()` is true, restoring normal cadence on the
first unowned loop. HAL task scheduling, health confirmation, watchdog feeding
and WFI remain outside the UI gate. No progress value, wire/CRC/seq/durable
contract, phone APK, Boot or normal idle UI layout changes. Whole-handler
throttling also bounds input/timer responsiveness during the owned OTA period;
hardware screening must verify cancellation/terminal recovery rather than claim
that the host cadence unit test proves runtime safety or speed.

Host result `.cache/p34-ui-cadence/tests/result.json`:34 checks across flag0/1,
plus2 integration checks; strict warning-free native test builds. Tests cover
idle behavior, entry, period boundary, late scheduling without catch-up bursts,
release/reentry and32-bit wrap. Source preparation copies the immutable CRC
baseline and adds only the cadence header/main-loop guard, retaining prior MCU
profiling. Build scope is App-only, not Boot/release/deployment. No new OTA is
yet started and30252 remains installed. Any later matrix needs a bootstrap to
install the receiver change and a header-only successor to measure it; bootstrap
install time must not be compared to the old header-only measurement.

UI-01 pre-deployment review caught an integration defect in the first candidate:
`OTA_OverlayIsOtaOwned()` means PACKAGE ownership only, not BLE ownership. The
first `.cache/p34-ui-cadence/` build and packages are REJECTED_NOT_DEPLOYED;
their successful compilation/decoder results do not make the cadence active.
No device upgrade used them. Preserve these artifacts rather than rewriting the
evidence. The corrected candidate adds a distinct `OTA_OverlayIsBleOwned()`
query without changing the old query's semantics, and wires only that BLE query
to the cadence gate. New root is `.cache/p34-ui-cadence-r2/`;34 native checks
and5 integration checks pass, including rejection of the PACKAGE-owner wiring.

The already completed `.cache/p34-ui-cadence/archive-bootstrap` remains valid
and is reused, not repeated:30251 inactive capture was copied/verified and moved
inside the phone's existing archive,30252 snapshot/configuration preserved,
seven active-store slots remain, App stopped, USB closed. No deletion or APK
change. Source preparation/build for the corrected candidate uses fresh paths;
historical built source trees and receipts stay unchanged.

Corrected App build completed with638 existing warnings, zero new warnings and
zero errors; size616748 bytes (+128 versus CRC). Both legal packages passed
positive native byte/Boot/guard/workspace checks plus4 negative cases each.
No packet has been transferred. `p34_ui_trial.py` prepares the same APK/radio
policy and reuses the original native/USB collectors and600-second coordinator
cleanup allowance.

The first offline context check stopped before device access because the old
erase manifest referenced pre-query `USER/HAL/HAL_OTA_Package.cpp`. Its exact
53143-byte archived CRC-baseline copy has SHA
`c08e0f12b7ce2af62643c4f5008cc68fb49ff0cb48a3e36cec32e2998b05921a`.
Use a process-local exact-hash historical resolver, as for the earlier CRC
transition; do not overwrite old manifests or make the current file impersonate
old bytes. A wrong-hash negative is included in the7 passing UI trial tests at
`.cache/p34-ui-cadence-r2/trial-tests-002`. The replacement offline check is a
finite owned worker under `runtime/offline-002`; a host failure is not an OTA.

Offline-002 passed with179 bound inputs. The corrected bootstrap coordinator
started under `.cache/p34-ui-cadence-r2/trials/bootstrap/runtime/coordinator`;
sources are immutable while its workers run. After the cell closes, reconcile
using the existing `Ui` context and `api.analyze_install(c, out, 's04')` rather
than replaying the upgrade. `Ui.installed_context(out)` was included in the
offline check. If the normal installed readback is missing, the existing
`verify_install_readback` route verifies the retained target without resetting.
Do not change the pinned trial source to add an analysis CLI mode mid-run.

Additional offline reconnect observations from the already retained HCI file,
relative to the matched END ACK: target connections established at8.560244s
and17.081724s, each sent GET_INFO without an INFO reply, and were locally
disconnected at13.788482s and22.293626s. The next successful target connection
established at27.635627s and returned the matched30252 INFO at30.071694s.
This identifies repeated connected-probe teardown/rebind as a follow-up axis,
not a measured new optimization or proof of when the MCU became ready. Preserve
the mandatory fresh post-END connection and exact target identity; evaluate
whether bounded repeated INFO on that same valid connection can avoid teardown
only after the current single-factor MCU/UI trial. No APK change in this matrix.

Bootstrap READY_FOR_FULL_INSTALL_START at2026-10-02T20:21:57Z: installed App
PID3544, current30252, target30253,293150-byte package SHA
`73689da5c95741025f4e87e76796c34f9310e74422b5f379d8eb10b0937f9d0f`,
config SHA `5f929d34de45d82d66062c81c0818f70d916aec72703b83651682677335ab5e1`.
Original queries prove `start_inputs_verified_before=true`; baseline native
closure retains the verified image. User has been asked to press Start Upgrade
once in the existing foreground App. No second download or APK installation is
needed. Coordinator/network/s04 workers remain live with their finite deadlines;
do not relaunch them. This is a readiness checkpoint, not an upgrade verdict.

Bootstrap completed and all three workers closed normally. Original report:
`.cache/p34-ui-cadence-r2/trials/bootstrap/analysis/1790972923961609100/result.json`,
SHA `d2b967607d9c71949df8ff6f7b931a0b81d1395db1fd85f3641cc3abd7bdb1cd`.
Result FULL_INSTALL_VERIFIED; retained30253 raw App SHA
`e761b0981527e1a633d667554d05b1166b24cabcaf5e15cc27fb786584bd3f67`,
616748 bytes; Boot unchanged, BCB4, confirm_done/state_snapped/sd_ready all1.
Transfer22.373877s /13.102334KB/s; END-to-target42.808421s. This run installs
changed executable pages using the old receiver and is NOT a cadence benefit
measurement or a comparable header-only installation timing.

`Tools/ota/p34_ui_result.py` reuses the cell's existing automatic strict report,
checks normal owner closure and distinguishes bootstrap from measurement. It
does not rerun the expensive context/analysis or contact either device. Five
host regressions pass in `result-tests-003` (wrong cell, partial verdict, forced
closure and non-mixed speed/reconnect outcomes included). Bootstrap projection
is saved under `review-bootstrap/result.json`.

`archive-measure` completed with a verified host copy and phone-internal move
of the inactive30252 capture; current30253 snapshot/configuration preserved,
seven active-store entries remain, App stopped and USB closed. No delete or
APK installation. Measurement launch is owned by
`.cache/p34-ui-cadence-r2/runtime/launch-measure-001`; it starts the existing
`p34_ui_trial.py launch --arm measure` route. Do not repeat either launch or
archival. Measurement package is293103 bytes, SHA
`7003e6831729c2281e0c2f7c7b659a736ceac42bcb8540deefd9e740939f8364`,
target30254 raw SHA
`855a42a9c3a6ad1fe7ef832fb0e627508811b095d6c0ba1526fba3c3eb4dba35`.
The receiver and target executable bytes outside the96-byte header are equal.

## UI-02: Measurement DNS Recovery, No OTA Replayed

The original `trials/measure` network exhausted its system-DNS readiness window
(`gaierror`, six attempts). No `cells/` or `runtime/s04` was created and the
network result records zero device operations. Its listener and worker stopped;
network/coordinator owners exited1 without forced termination. Current30253
and the already-completed `archive-measure` remain unchanged. Preserve the
failed origin, actions and receipts rather than treating this as a failed OTA.

A read-only query through the existing `p34_scoped_dns.resolve` returned public
A records for that origin while the system resolver still failed. Recovery
entry `Tools/ota/p34_ui_dns.py` reuses that existing resolver plus hostname/SNI
certificate verification, same-origin redirects, exact metadata and package
byte checks. It does not change system DNS, disable TLS verification, catch an
integrity failure or rotate firmware/APK artifacts. Thirteen boundary/route
tests pass in `dns-tests-002`; failed-owner/no-cell reconciliation is mandatory.

New route: `.cache/p34-ui-cadence-r2/trials-dns/measure`, launched through the
finite `runtime/launch-dns-001` owner. It reuses the existing measurement assets
and archive, but starts a fresh service only after the failed one closed. Sources
remain pinned while running. After success use
`p34_ui_result.py launch --arm measure --route dns` to project the original
automatic report; do not analyze the failed `trials/measure` path as the new
trial. Six result-wrapper regressions pass in `result-tests-004`.

## UI-03: Completed Measurement And Next Sender Candidate

The DNS recovery completed normally, without another APK install or replay.
Original strict FULL_INSTALL_VERIFIED report:
`.cache/p34-ui-cadence-r2/trials-dns/measure/analysis/1790976214280622600/result.json`,
SHA `3765f27be89a02743e8b5887cf8c536acabc46f7e1f7a159712f78d03bc08a32`.
All coordinator/network/s04 owners exited0 without forced termination. The
offline projection `review-measure-dns/result.json` reused that report; its
owner exited0. Retained30254 full App SHA
`855a42a9c3a6ad1fe7ef832fb0e627508811b095d6c0ba1526fba3c3eb4dba35`,
Boot unchanged, BCB4, confirm_done/state_snapped/sd_ready all1.

Transfer293103B took20.528829s (14.277629KB/s), END-to-target21.232236s.
Compared with CRC30252: speed+3.639273%, transfer0.738317s shorter,
installation/reconnect8.933915s shorter. This is a single sequential header-only
successor, not identical-package A/B, repeated stability, or a full executable
replacement installation guarantee. Neither user target is met.
2290 unique DATA and2290 valid ACK samples, zero retries/ACK errors/lost records.

Native pump entries increased234->587; RX ring peak3874->3525, zero UART,
parser or overflow errors. Payload erase3.396236s, program0.492285s,
verify0.039568s; ACK write calls1.023330s, pump work5.878078s. These nested
native durations are not additive with each other or App-clock timings.
Coarse Boot residency6.616632..8.096907s has no target-confirmed trace sample;
the later separate full-image/BCB readback supplies final confirmation. Preserve
that trace gap; no reset or replay is justified.

App-clock DATA GATT calls total10.686188s across1574 chunks, with9.842641s
remaining inside measured transfer. The remainder is not isolated ACK/Flash
cost. A50KB/s transfer of this package permits only5.86206s overall, so keeping
the measured serialized GATT cost unchanged cannot meet that target even if
other waits vanished. Further transfer work must address sender write overhead
as well as receiver staging; neither a new baud nor UI throttling alone proves it.

Next bounded development batch: default-off schema6 `reuseRebootInfoLink`,
up to three settled INFO timeout retries on one valid fresh post-END binding.
Preserve initial disconnect, exact discovery, seq/poison guards, outer budgets,
cancellation, link generation/GATT token and target identity. Valid old identity
still retires the probe. No hardware use until exact CI and host admission are
ready. Exclusive source `.cache/p34-probe-fix/src`, branch
`dev/flutter/p3-4-probe-reuse-20261003`, WIP commit
`fedb3fd748e005cd3d1160d44d679eb7e63971e5`; full Linux/Windows self-tests run
`37078259647`. This is not a speed checkpoint, APK build, release or mainline
integration. No new App installation or device transfer has been performed.

### Probe Candidate Validation And Installation Blocker

Commit `fedb3fd748e005cd3d1160d44d679eb7e63971e5` passed the checks-only run
`37078259647` and explicit debug-APK run `37078753249` on both hosts.
Original APK-run reports: Windows585 passed/33 skipped/0 failed;
Linux602 passed/16 skipped/0 failed. Both analyze steps passed. Actual SDK:
Flutter3.47.6, Dart3.13.5, framework
`5fc346839b5d0eef006ed8404392afb4dfae428d`. No Windows EXE build, mainline
integration, production release or independent acceptance was performed.

Collected APK SHA
`2b501a94bdf83d3c9568cb5e2cc2e61d83d71ba9db138e13e638589be228a099`,
131649642 bytes; exact package `com.wen.gaia.gaia.p34probe`, fixed certificate
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
Receipt `.cache/p34-probe-fix/apk-g1/apk.json`; owned collection exited0.
The preparation receipt's initial source scope preceded adding the schema6
config and its tests; the actual stage/commit explicitly includes those two
files. Preserve the original preparation receipt, not retroactive edits.

`p34_probe_assets.py` prepared control30255 and reuse30256, each293188-byte
FULL packages with unchanged executable bytes. Both pass original native
positive decoding and four negative rejection checks. Host profile tests6/6,
trial wiring tests5/5. Offline control context check verifies188 source/input
bindings, exits0 and explicitly does NOT attest installation. No trial,
archive-control or new OTA has been launched.

Installation attempt `install-001` preserved the original30254 capture and
configuration, force-stopped its completed App, then invoked one in-place
`adb install -r --no-streaming`. Android returned:
`INSTALL_FAILED_ABORTED: User rejected permissions`.
This is not a certificate mismatch. Keep original `install-intent.json`,
`usb/commands.jsonl`, `result.json` and owner receipt; do not relaunch it.
The worker exited0 because the reused installer records failures in JSON;
that exit is NOT installation success. USB stop/server/launcher all exited0,
port5062 closed and ADB key unchanged. No MCU command or firmware mutation.

User intervention needed: allow USB App installation in the phone's system
prompt/settings, keep it unlocked, then notify the session. Do not treat a
generic request to continue as proof the phone setting changed. Before a new
attempt, read the installed package hash and reconcile old versus new APK;
never blindly repeat the install. The new candidate has NO measured speed
result yet; current retained MCU and last measured figures remain30254,
14.277629KB/s and21.232236s.

After verified same-signer update, resume the prepared control/reuse matrix
through `p34_probe_trial.py`, preserving source pins. Archive only the named
inactive verified capture with the existing no-delete helper, then perform
the offline binding gate and source-bound host tests before a live window.
Wait for READY_FOR_FULL_INSTALL_START before asking for Start Upgrade.

### Probe Installation Resumed After Phone Readiness

User confirmed readiness after the system install rejection. The new
`p34_probe_install_resume.py` entry requires the exact one rejected install,
closed original resources and unchanged APK. It reuses the installer that
verifies the old installed APK before any mutation; an already-new or unknown
APK cannot be blindly replaced. Original `install-001` remains preserved.

`install-002` completed at2026-10-03T02:52:19Z with
FIXED_SIGNER_BATCH_UPDATE_VERIFIED (the reused installer's unchanged result tag).
Actual installed APK SHA is
`2b501a94bdf83d3c9568cb5e2cc2e61d83d71ba9db138e13e638589be228a099`.
Snapshot, configuration and permissions preserved; App not launched. USB and
owner exited normally. This removes the prior phone-install blocker, not a new
OTA result or measured speed improvement.

Trial entry now references this resumed-install receipt; five host wiring tests
pass in `trial-tests-002`. Offline check `runtime/check-control-002` exits0,
verifying191 inputs without device operations. `archive-control` then provides
a verified no-delete archive of inactive30253, preserving current30254 snapshot
and configuration; seven active-store entries remain. Its owner/USB closed.

`runtime/launch-control-001` exited0 after starting the existing control
coordinator at2026-10-03T03:01:22Z, under `trials/control/runtime/coordinator`.
Do not repeat this launch, installation or archival. Control prestart phone
inspection is APP_INSPECTED/stable_completed with the exact prior config and
snapshot; USB closed normally. The network worker started03:04:52Z. Running
sources are pinned. Next wait for live service, cell and original
READY_FOR_FULL_INSTALL_START. No new firmware transfer has yet been requested.

Control service became verified at03:08:30Z; cell/s04 started03:08:32Z.
Fresh native readback retains30254 App SHA
`855a42a9c3a6ad1fe7ef832fb0e627508811b095d6c0ba1526fba3c3eb4dba35`,
BCB4 and confirm_done/state_snapped/sd_ready all1, no reset or Flash writes.
New App PID6132 launched03:15:22Z. Capture
`1790997323855212-13e5053292f43aa65ee07907` has real producer records, healthy,
lost0/error null and upgradeStarts/Ends0 at03:20:19Z. State is
APP_LAUNCHED_CONNECT_AND_DOWNLOAD, not yet start-admitted. User was asked to
download3.2.55-p34p only, not start. Expected package293188B SHA
`fba5f85fb5563dc3368a856776d4d9c9c4ca1e246f7abbbe36ac5d77049ef8b6`.
Coordinator/network/s04 remain owned and live; do not relaunch or edit pinned
helpers. After download verify original queries and READY_FOR_FULL_INSTALL_START
before requesting the single Start action.

### Probe Control Complete, Reuse Arm Started

Control download admission was recorded03:20:36Z, before the user's upgrade.
The original finished capture has one start/end, outcome completed, lost0 and
no error. Final strict report is FULL_INSTALL_VERIFIED:
`.cache/p34-probe-fix/trials/control/analysis/1790998161500856300/result.json`,
SHA `db99fe4bfe722ad3d34554381b40485aa7ce5d09df24afb2e33c7bae68d3fd55`.
All control coordinator/network/s04 workers exited0 without forced termination.
Retained30255 full App SHA
`0a9c3680c408c256483067a716950d4a21b6e5fab99d37e6d5d0f87d7ecdc47f`;
Boot unchanged, BCB4 and confirm_done/state_snapped/sd_ready all1.

Control schema6 explicitly records `reuseRebootInfoLink=false`, config SHA
`7062c27fc58af391d6df82ea97f7527a0e2ced6d383237aedc3df73821fc28eb`.
293188B transfer21.817592s,13.438147KB/s; END-to-identity23.030221s.
2291 DATA/valid ACK latency samples, zero retransmits/ACK errors/capture losses.
This is the new APK's off-arm baseline, not an enabled-candidate speed result.
Six reconnect probes: two valid bindings had INFO timeouts before local teardown;
the sixth verified target. Reuse remains an unmeasured hypothesis at this point.

`archive-reuse` safely archived inactive30254 while preserving current30255,
configuration and seven active-store records; owner/USB closed normally.
Offline `check-reuse-001` exited0 with191 input bindings. No code/test change
or App installation was required between arms.

`launch-reuse-001` exited0 after starting the reuse coordinator03:54:07Z.
`trials/reuse/prestart-phone/result.json` is APP_INSPECTED/stable_completed,
binding the original30255 snapshot. Verified service became ready04:01:20Z;
cell/s04 started04:01:22Z. Do not relaunch any existing owner.
Expected30256 raw SHA
`6e518dcd2b0729504d4c28a1681225931db9821fa328fd5ea412cb9da11f61da`;
293188B package SHA
`90d92987ec2a9cfc8cc0a7df4d41bbca638bcbfee11a142dc2addba969ff04e6`.
Same APK, radio/baud/window/batch/INFO timeout/interval and executable bytes;
only the declared reuse flag plus legal successor version/package identities
differ. Wait for App capture/download admission before asking Start.

Reuse reached READY_FOR_FULL_INSTALL_START at2026-10-03T04:09:33Z, PID27881,
target30256 and exact293188-byte package verified from the phone. Capture
`1791000477648854-9513b3395ceed022b66cce7f` is healthy with zero lost/error and
zero upgrade starts/ends at04:10:21Z. The original query receipt confirms
start_inputs_verified_before; runtime schema6 explicitly enables the reuse
flag. User was asked to press Start once and stay foreground. No further
download or App install is required. Keep the existing three owned workers;
retrieve their automatic report after actual completion, never replay.

### Probe Reuse Verified And Bounded Interval Follow-Up

Original reuse FULL_INSTALL_VERIFIED report:
`.cache/p34-probe-fix/trials/reuse/analysis/1791001002324789600/result.json`,
SHA `e930c6e6adfc05813bc4734203049b416cb02a9e1a541b16e610aca910105cad`.
All three owners exited0 normally. Retained30256 App SHA
`6e518dcd2b0729504d4c28a1681225931db9821fa328fd5ea412cb9da11f61da`,
unchanged Boot, ordinary BCB4/health confirmation. No OTA replay or new APK.

Reuse transfer21.208131s,13.824320KB/s; END-to-target21.235894s.
2291 DATA and valid ACK samples, zero retransmits/ACK errors/capture losses.
Reconnection uses four probes rather than control's six. Probe2 retains its
binding through three2-second INFO timeouts, then retires; probe4 verifies
target. The observed END-to-target saving is1.794327s (about7.79%), still above
20 seconds and not repeated stability evidence. The transfer difference is NOT
attributed to the post-END reuse switch. Neither50KB/s nor20s is achieved.

Within the existing task/device scope, one additional targeted cell is planned:
retain30256 as receiver, legal header-only30257 successor, same installed APK,
Boot, baud921600, window28, batch3, scan pause/high priority and reuse enabled.
Only rebootProbeIntervalMs changes500->100; INFO timeout remains2000ms.
Do not shorten INFO timeout below measured successful first-identity latency.
This tests scheduled waiting without changing safety checks or parser budgets;
it does not promise that five shorter waits translate directly into2s gain.
Use fresh `.cache/p34-probe-cadence` outputs, normal original collectors,
full final readback and orderly closure. Stop this path on unreliable state,
integrity errors or missing ownership; no blind repeated OTA or extra APK.

### Interval Assets And DNS-Only Setup Recovery

`p34_probe_cadence.py` prepared the30257 FULL successor,293194B SHA
`37ac2384d668550b7225c0ad7b6fafa8176c3c71d55b1cd002e0450dcf58203c`.
Original native decoder positive and four negatives pass; five host tests pass
in `.cache/p34-probe-cadence/tests-001`. Offline check verifies195 bindings.
The unchanged2s INFO timeout avoids cutting below observed first-identity
latencies. The earlier RADIO-11 conclusion about insufficient500ms sleep savings
used a different24.42s baseline; it is not silently reclassified. The current
21.24s reuse baseline and its intra-binding intervals motivate this one new
discriminator, not a promised2s improvement.

Archive safely moved inactive30255, protecting30256 and leaving seven entries;
owner/USB closed normally. The initial `.cache/p34-probe-cadence/trial` attempt
failed in network setup with `DNS ID/status/count mismatch`. No `cells/` or
`runtime/s04` exists. Network/coordinator exited1 without forced termination,
and the inner listener/worker closed. Original DNS raw header was not recorded,
so its exact negative/status cause remains UNKNOWN. A later read-only lookup
of the same original hostname returned matching ID, flags0x8180 and two public
A records under the original strict parser. Do not label this a failed OTA.

New reusable `p34_dns_readiness.py` permits at most six DNS attempts, with2s
between well-formed correlated zero-answer NOERROR/SERVFAIL/NXDOMAIN replies.
Wrong ID/question, truncation, malformed records, private addresses and other
failures are not retried. Original hostname/SNI TLS verification, same-origin
redirect and exact metadata/package byte gates remain unchanged. Eighteen
DNS/TLS/redirect/strict-recovery tests pass in `dns-tests-002`; the earlier
9-test output remains preserved. No system DNS modification.

Recovery entry `p34_probe_cadence_dns.py` requires the exact original failed,
closed, no-cell receipts before using fresh `.cache/p34-probe-cadence/trial-dns`.
`runtime/launch-dns-001` started05:24:48Z and must not be relaunched. This reuses
the same APK, assets and completed archive; no new device transfer is consumed.
After completion read the original automatic report from `trial-dns`, not the
failed `trial` path. Preserve all running source pins and wait for actual
download admission before requesting Start.

The recovery launcher exited0; coordinator started05:26:33Z. Verified service
became ready before cell/s04 started05:33:41Z. No repeated DNS failure was
observed. Current receiver readback remains30256 raw SHA
`6e518dcd2b0729504d4c28a1681225931db9821fa328fd5ea412cb9da11f61da`;
reader closed normally before the continuous observer. App PID25095 launched
05:40:35Z with runtime schema6, target30257, INFO timeout2000ms, interval100ms,
reuse enabled. The current capture is
`1791006035732113-0f54983c13e8c1cdd8d7a7bc`.

At05:44:31Z the original App events file contains only its open header; the
observer correctly has not accepted it as a working producer/query snapshot.
Status is APP_LAUNCHED_CONNECT_AND_DOWNLOAD, not READY_FOR_FULL_INSTALL_START.
User was asked to enter OTA, connect and download3.2.57-p34p only. Do not start
until original query/package admission appears. Existing coordinator/network/s04
remain live and source-pinned; do not recreate them or repeat an installation.

### Interval Result And Sender Timing Follow-Up

The original trial-dns download admission completed05:45:51Z, before the single
user Start. Target30257 is now FULL_INSTALL_VERIFIED; original report:
`.cache/p34-probe-cadence/trial-dns/analysis/1791006777304686400/result.json`,
SHA `711d5092c071d25ce6bb533b78ed208016c02b111182a90c23a3b22d167947c8`.
Coordinator/network/s04 exited0 normally by05:58:06Z. Retained616748-byte App
SHA `26e738fb9559d0d80e8c1bfa35a93590beb9e7938741074e981e24feacca63ef`;
Boot unchanged, BCB4 and ordinary health confirmation verified by full readback.
The transient trace still lacks a target-confirmed sample; no reset/replay was
used to fill that gap. No APK installation was performed in this interval cell.

293194B transfer21.179229s (13.843469KB/s), END-to-target22.267714s.
2291 DATA/valid ACK samples, zero retries/ACK errors/lost records. Four probes;
probe2 exhausts three2s INFO requests, probe4 succeeds on its third request.
Compared with the500ms reuse baseline21.235894s, reconnect is1.031820s slower,
not a speed improvement. Stop the100ms cadence candidate; do not run further
blind interval/timeout reductions or call this a speed checkpoint. Both user
targets remain unmet; this is still a header-only successor, not full executable
replacement timing acceptance. Retain30257 rather than downgrading for a label.

`Tools/ota/p34_batch_timing.py` adds batch-aware accounting without changing
the old one-frame/write parser or running device helpers. Thirteen regressions
pass in `.cache/p34-batch-timing/tests-001/result.json`. It reuses strict original
report/input/readback/closure verification and rejects missing/duplicate samples,
wrong chunk/frame geometry, retransmissions, invalid ACK sets and negative spans.
Original30256 and30257 projections are `reuse.json` and `cadence.json` there.

30257 App-clock DATA GATT11.372907s contains platform11.097507s and service
wrapper0.275400s. Block last-chunk-to-durable tails sum8.940238s; within-block
nonwrite remainder0.669809s; BEGIN and END remainders0.196275s. These disjoint
accounting buckets sum21.179229s. Platform/wrapper are nested, not extra buckets;
durable tails include multiple components and are not isolated Flash timings.
The50KB/s budget is5.863880s, already below platform-call time alone. Optimizing
only service lookup/allocation or only receiver waits cannot meet the target.

Next bounded diagnosis reads only the existing exact-PID25095 native Android
main ring through `p34_native_ring.py`, after the prior owners closed. Same APK,
config and report are verified before reading; no App launch, log clear, system
report, J-Link operation or OTA. Output `.cache/p34-native-ring/30257-001` uses
the existing private USB/key/closure route. An incomplete ring remains a gap,
not permission to replay this successful upgrade. Inspect the already available
exact FBP1.35.5 / Android4.0.5 source before selecting a sender candidate;
without-response callback pacing/global serialization must not be bypassed.

The native-ring read completed with0 bytes, normal USB/server/launcher closure
and unchanged ADB key. Five collector guard tests pass under
`.cache/p34-native-ring/tests-001`. The empty output is not a native latency
measurement; no system report, App restart or OTA was performed to fill it.
Historical exact HCI generation2 was decoded again offline: phone MTU512 request
record480 (`020002`) receives module MTU247 response record483 (`03f700`). The
same connection later requests247 and receives247 before DATA. This rules out
blindly increasing the phone request as a useful next change on this observed
module configuration. Receipt: `.cache/p34-batch12/mtu-evidence.json`.

### Batch12 Development Validation

The next bounded sender candidate is schema7 batch12, not a native callback or
global serialization bypass. An explicit isolated checkout contains the scoped
change, leaving the root index/unrelated changes and prior source checkouts
unchanged: `.cache/p34-batch12/src`, branch
`dev/flutter/p3-4-batch12-20261003`, WIP commit
`c5a8c53195bcda43e3ae060f7ce5e8007a4cf6ae`.
Checks-only run `37102894423` passed both hosts. Explicit fixed-signer APK run
`37103202227` is in progress; no new APK is installed yet. A transient read-only
GitHub status TLS EOF did not trigger a CI rerun or a second APK request.

The service's actual-write-mode guard is also in the final10-file staged scope;
the preparation receipt preceded adding that path. Preserve the preparation
receipt, not a retroactive scope edit. Schemas1..6/default behavior remain;
schema7 alone admits12 while matching all identity/radio/credit/timeout checks.
Transport tests run the batch3 and12 cancellation, pause, late-write poison,
reserved-frame ACK, short-tail/MTU and small-window cases. Source-side Python
reader tests8/8 pass in `host-tests-001.json`. No release/EXE/mainline integration.

`p34_batch12_assets.py` generated control30258 and candidate30259, with unchanged
executable bytes and Boot. Two native positives and eight negative package checks
pass; the asset owner closed normally. Packages are293107B and293036B, respectively.
These are sequential legal packages, not identical-package A/B. Geometry under
constant free credit28 predicts22 versus19 GATT calls per full4KB block, not an
observed speedup or a route to50KB/s by itself. `geometry.json` preserves the
offline alternatives; batch4 is worse, batch8 needs20 calls per full block.

`p34_batch12_trial.py` reuses the verified same-signer installer, no-delete
archival, strict DNS/TLS readiness, original collectors and final full readback.
Eight host admission tests pass in `trial-tests-001`. The finite plan is one
same-signer APK update followed by control batch3 and candidate batch12 with
500ms/INFO2000ms/reuse enabled, baud921600/window28 and identical radio policy.
No collectors, installation or new OTA have started. Finish APK provenance and
offline context validation first; only ask for real phone actions when ready.

APK run37103202227 completed successfully. Original reports: Linux633 passed,
16 skipped,0 failed; Windows616 passed,33 skipped,0 failed. Both analyze steps
passed. Actual SDK Flutter3.47.6 / Dart3.13.5, framework
`5fc346839b5d0eef006ed8404392afb4dfae428d`. No Windows EXE/release build.
The fixed-certificate APK is131652082B, SHA
`a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387`;
`.cache/p34-batch12/apk-g1/apk.json` binds its original artifacts and two reports.
All288 APK ranges downloaded without failed ranges; collection owner exited0.
Eighteen original logs contain no exact encoded private-keystore secret.
Control offline check `runtime/check-control-001` exited0 with204 input bindings.

The installer preparation `install-001` exited before any install attempt:
`NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED`. The exact current old APK was verified,
but Android power state was not Awake. No install-intent, force-stop, App launch,
uninstall, data clear, archive or MCU command occurred. USB stop/server/launcher
exited0, port5062 closed, ADB key unchanged; installer owner closed normally.
Current installed APK therefore remains
`2b501a94bdf83d3c9568cb5e2cc2e61d83d71ba9db138e13e638589be228a099`.

User intervention: wake/unlock the phone and keep USB connected. Do not relaunch
the spent `install-001` entry. On readiness, preserve its no-attempt receipt and
use a fresh bounded resumed-install output, rechecking actual old/new package
and awake state before any in-place install. The present `apk(s)` admission still
names `install-001`, so its verified-success reference must be updated through a
tested no-attempt resume adapter before launching a trial. Do not mark it installed
from the supervisor's exit0 or edit the old receipt. All other setup, APK, assets,
host tests and source remain reusable; no new CI/APK generation is necessary.

### Batch12 Installation Reconciled

`install-002` also ended before installation because the phone had slept during
host preparation. Both001/002 retain their original no-attempt receipts: no
install-intent or stop-intent, normal owner/USB closure and unchanged ADB key.
This was a host readiness-timing problem, not an APK or firmware failure.

The tested resume adapter pre-arms a read-only180-second Awake gate before the
same-signer installer. It does not wake the phone, tap UI or change settings.
Source-bound resume tests10/10 and trial tests8/8 pass in `resume-tests-002` and
`trial-tests-003`. The trial admission now uses `install-003`.

`install-003` started2026-10-03T07:05:22Z, observed Awake and completed at07:07:17Z
with `FIXED_SIGNER_BATCH_UPDATE_VERIFIED`. The installed APK SHA is
`a48549082f74a234d5acf0affdfa0d4120f2099fffefa8a40dc0302cac444387`.
Snapshot, configuration and permissions were preserved; no uninstall, data clear,
App launch or OTA occurred. USB stop/server/launcher and installer owner exited0
normally, port5062 closed and the existing ADB key was unchanged. Do not install
again for either comparison cell.

Continue the prepared control30257-to30258 batch3, then30258-to30259 batch12
matrix under this same APK. A fresh offline binding check uses
`runtime/check-control-002`; archive only the verified inactive30256 capture,
preserving30257 and the configuration, before opening the control observation.
The wake recovery and installation are not measured OTA speed improvements.

Control offline check002 completed07:13:01Z with215 bindings and normal exit0.
`archive-control` completed07:11:58Z: inactive30256 capture
`1791000477648854-9513b3395ceed022b66cce7f` was copied and verified on the host,
then moved within the App to `files/p34-archived-observations/`. No deletion;
seven active entries remain. Protected30257 snapshot/configuration are unchanged.
Archive owner and USB closed normally. Do not archive this record again.

Control launcher001 exited0 after starting coordinator at07:15:22Z. The
coordinator failed at07:17:18Z during `capacity-preflight`, before network,
prestart capture, MCU access, configuration provisioning, App launch or OTA.
All nine original USB `get-state` calls returned exact phone not found. The
private ADB server itself started, then closed normally (all three exits0,
port5062 closed, ADB key unchanged); coordinator exited1 without forced shutdown.
Windows connected-device enumeration also found no phone/Android/ADB match.
This is a missing USB device, not a failed APK install or OTA attempt.

Original receipts remain in `.cache/p34-batch12/trials/control/`; do not replay
its fixed-path launch or overwrite the failed intent/result. User was asked to
reconnect/unlock the phone and leave USB attached. On return, reconcile this
no-device-mutation outcome and use a fresh bounded control attempt while reusing
the installed APK, validated packages and successful archive. Candidate routing
must depend on that fresh control's actual verified result, not the failed path.
No new speed measurement, OTA, reset, J-Link command or installation occurred
after install003. Current retained MCU identity remains the last raw-confirmed30257.

### Batch12 USB Recovery Entry

User reported ready again; Windows connected-device enumeration now shows the
exact serial10ADA4197U001CK and its ADB interface. The new entry
`Tools/ota/p34_batch12_recovery.py` preserves the original control directory and
uses `.cache/p34-batch12/resumed-trials/{control,batch12}`. Nine source-bound
host regressions pass in `recovery-tests-001`; no device operations in those tests.

Recovery admits only the exact missing-phone failure, failed get-state commands,
normal prior owner/USB closure and no network/cell/provisioning/MCU operation.
It also checks original source bindings and successful control archival. Original
installer, trial, archive and observer sources are unchanged. No APK reinstall,
archive repeat, download generation, MCU reset or Boot replacement is planned.

The finite matrix remains30257-to30258 batch3, then30258-to30259 batch12 under
the same APK and prior radio/timing policy. Candidate predecessor and archive
routing use the fresh control's actual verified report, never the failed control
or prepared assets. Launch/control uses a600-second launcher and6000-second
coordinator; original bounded network/cell/USB observers retain their deadlines.
Keep these sources immutable while active, and request connect/download/Start
only after the corresponding original readiness gates are observed.

Recovery launcher started07:26:25Z and exited0 after coordinator startup07:28:08Z.
Capacity preflight verified the exact phone/APK and a free observation slot;
prestart inspection completed07:30:09Z with the unchanged stable completed capture.
Network started07:31:43Z. One transient negative DNS response resolved on the next
bounded check; verified HTTPS/package service became ready07:35:21Z without any
system DNS change or replacement tunnel. Cell/s04 started07:35:23Z.

The current receiver was passively verified as30257 with unchanged Boot, BCB4,
confirm_done/state_snapped/sd_ready all1. Its ordinary existing configuration was
archived before provisioning, without reinstall/data clear/reset. App PID14581
launched07:42:33Z under schema7 batch3, INFO2000ms/interval500ms/reuse enabled,
baud921600/window28. Capture: `1791013351651993-3b1f1e336028d2c6ada0f541`.

At07:43:56Z the original status reached `READY_FOR_FULL_INSTALL_START`: two
successful App queries, negotiated MTU247,20 producer lines, zero lost/error,
upgradeStarts/upgradeEnds both0. The phone-downloaded control package is293107B,
SHA `a890157a36665b388a2e95fec0e7c4ff234c5b416dd8167ec9ca3e01e263f4cc`.
User was asked to press Start once for3.2.58, keep OTA foreground and USB attached,
and not switch back to chat during the transfer. All three owners remain live;
do not relaunch, reinstall, change pinned helpers or repeat this admitted cell.
Next: retrieve automatic finished originals and fresh raw target confirmation;
then archive/start the candidate through `p34_batch12_recovery.py --arm batch12`
only after the resumed control's actual verified outcome and normal closure.

### Batch12 Same-APK Control Result

User reported upgrade complete. Resumed control30257-to30258 is now
`FULL_INSTALL_VERIFIED`; report
`.cache/p34-batch12/resumed-trials/control/analysis/1791013890016506000/result.json`,
SHA `624e32161019f945068cba75f533a59692c6d68e31459179e5b7343cb61d2273`.
Original App snapshot contains9528 records and its genuine completed footer,
with one start/end, no loss or capture error. Exact target616748-byte raw SHA
`bf3417acd3a028550447d250865e5ca0295b490dd87f320a5fe2d53fdc1df72c` was independently
read back; unchanged Boot, BCB4, confirm_done/state_snapped/sd_ready all1.
USB and all coordinator/network/s04 owners closed normally with exit0.

Control batch3:293107B transfer21.580741s,13.581878KB/s (13.263553KiB/s),
END-to-target21.305316s. All2290 DATA ACK samples valid; zero retransmissions,
ACK errors or lost records.1574 DATA GATT chunks; same schema7 APK and planned
500ms/2000ms/reuse settings. This is the comparison control, not an improvement
checkpoint; neither50KB/s nor20s is met. Sequential header-only FULL successors
remain distinct packages and are not full executable-replacement acceptance.

Offline disjoint timing in `.cache/p34-batch12/timing-control.json`: DATA GATT
11.690324s (nested platform11.397875s plus wrapper0.292449s), within-block
nonwrite0.764609s, last-chunk-to-durable tails8.927165s, BEGIN/END remainder0.198643s.
These sum21.580741s; tails are not isolated Flash. No new device operation was
used to compute these figures. Archive-batch12 started07:57:22Z, preserving the
completed30258 capture and moving only the already-verified inactive30257 capture.
After its verified closure, launch the existing candidate30258-to30259 batch12
through the recovery entry. No APK reinstall, MCU reset, Boot change or replay.

The transient trace again lacks an initialized/CONFIRMED target sample; final
independent raw readback above supplies ordinary confirmation, not a fabricated
trace sample. No reset was used to fill the gap. Archive-batch12 exited0 normally
at07:57:51Z with seven active captures and unchanged30258 snapshot/configuration.
Candidate launcher started07:58:11Z in `runtime/launch-batch12-001`; its runtime
target is `resumed-trials/batch12`. Keep the current sources pinned and poll this
launch/owner rather than creating another candidate invocation.

### Batch12 Candidate Awaiting Phone Download

Candidate launcher exited0 after coordinator startup; prestart phone inspection
completed08:01:52Z with the exact completed30258 capture preserved. Network started
08:03:26Z. The first DNS/HTTPS readiness attempt timed out; the existing bounded
retry succeeded08:07:15Z under verified TLS, without a replacement tunnel or
system DNS change. The service serves293036B SHA
`fc164ec111ee3adb9dd4d357ac4c29accac415314a61b61d93fb34455f11cde4`.
Cell/s04 uses the existing finite3900-second owner and started after service
readiness. Fresh passive MCU readback confirms30258 raw SHA
`bf3417acd3a028550447d250865e5ca0295b490dd87f320a5fe2d53fdc1df72c` and unchanged Boot.

App PID31615 launched08:14:09Z with the same verified APK, runtime schema7,
batch12/window28/baud921600, INFO2000ms/interval500ms/reuse enabled. Target30259
raw SHA is `e09411c2b71807b9b121b230f6882542976c65e5345e8db69f51d31c7ccb7b01`.
Status is `APP_LAUNCHED_CONNECT_AND_DOWNLOAD`, not transfer admission. User was
asked to connect in OTA and download3.2.59 only, not Start. All three candidate
owners remain active. Verify original queries, downloaded package and
`READY_FOR_FULL_INSTALL_START` before inviting one Start; do not re-provision,
reinstall, restart or edit source-pinned helpers while this session is live.

Candidate reached `READY_FOR_FULL_INSTALL_START` at08:16:56Z. Original download
is293036B and matches the expected SHA above; query checkpoint has two successful
queries and13 producer lines under PID31615/schema7/batch12. Capture is
`1791015248853947-a862d34f1048c60892f40136`; live health subsequently has16 records,
15 producer lines, no loss/error and zero upgrade starts/ends. At08:18Z all three
owners remain live. User was asked to Start3.2.59 once and keep OTA foreground
with USB attached. Continuation audit005 checks499 project-local entries,
225 unchanged bound inputs, unchanged root index and the authorized native-history
path. It records a live candidate, not a completed trial or measured improvement.
Next action is observation/original retrieval and final raw target verification,
not another launch, download, APK install or successful-transfer replay.

### Batch12 Result And Staging Follow-Up

Candidate30259 completed `FULL_INSTALL_VERIFIED`; original report
`.cache/p34-batch12/resumed-trials/batch12/analysis/1791015862788452400/result.json`,
SHA `c89dc46e606a7c51a1aac76bd392694c07f5dde90c92fcc7ce8b11d13e87742d`.
Full raw App SHA matches `e09411c2b71807b9b121b230f6882542976c65e5345e8db69f51d31c7ccb7b01`;
Boot unchanged, normal BCB/health confirmation. All owners exited0 normally.
Retain30259. Do not replay or downgrade this completed candidate.

293036B transfer21.670283s,13.522481KB/s; END-to-target21.879886s.2290 valid ACK
samples with no retransmission/ACK/capture errors. GATT chunks fell1574-to1378,
but0.969510s less DATA GATT time was offset by1.059052s more nonwrite/tail time.
Transfer is0.089542s longer and normalized throughput about0.44% lower; install
reconnect is0.574570s longer. Stop larger-batch screening and return to batch3
for subsequent experiments. No speed checkpoint is justified. Original comparison
and disjoint timings: `.cache/p34-batch12/comparison.json`, `timing-control.json`,
`timing-batch12.json`. Neither user goal is met; these are screening packages,
not reference-size reliability acceptance.

Next bounded development candidate addresses measured staging payload erase:
72 callbacks account for3.409340s on the candidate MCU clock. This does not
explain all waiting or promise50KB/s; platform writes alone still exceed its
5.860720s transfer budget. Use optional64KB erase-ahead only in the exclusive
staging payload, preserving4KB program/readback/bitmap/durable semantics and
all existing packet checks. Select only the observed W25Q128, default off;
invalid input, errors, retried sectors and rebinding must lose eligibility.
Never erase earlier durable bytes, the staging journal, other slots or Boot.

Implementation is isolated at `.cache/p34-staging-erase/f`, copied from the
verified3272-file UI-cadence source manifest; root product changes are untouched.
Header/runner/tests are `Tools/ota/p34_staging_erase.h`,
`Tools/ota/p34_staging_erase_candidate.py`, `tests/ota/test_p34_staging_erase.cpp`.
Only the isolated staging HAL and copied helper differ from that source base.
Host r1 compile failure was a redundant force-include of the existing unguarded
driver enum; preserve its log. Removed that unnecessary test shim, not a firmware
guard. Host r2 passed1468 assertions per variant. Expanded r3 passes1510 per
variant for bulk0/1 x QE0/1, warnings0/errors0: ordinary HAL regressions,
full/short/1MiB streams, each resume offset, partial erase failure, all six restore
failure points, bitmap/readback interruptions, retry, future-write invalidation,
non-selected chip and partition boundary behavior. These are host models only.

Finite next matrix: host validation and isolated App-only build, then a legal
30259-to30260 bootstrap installing the receiver change, followed by a30260-to30261
measurement successor using the same APK, batch3 and existing radio/reconnect
settings. Prepare native positive/negative package checks and source-bound
observers before either OTA. No new Boot, APK, release or flash recovery is planned.
Stop this candidate on integrity/resource failure or no useful measured gain;
do not silently multiply repetitions. Build uses the existing CMake/GCC arguments
plus the single experimental macro; all outputs/temp/cache remain under the
project-local candidate area. `runtime/build-001` is the finite active build;
poll it rather than relaunching or editing its inputs.

Staging erase build completed08:49:06Z, owner exit0. GCC App616932B raw build SHA
`7214fd6ed5c066f4eb5978014a9044816c4a08f1eaae2a4f4047991a98fc172d`;
warnings638, new warnings0, errors0, Boot not built. Assets owner completed
08:58:24Z normally: bootstrap293196B and measurement293164B, both native positive
decodes and all eight negative checks passed. Seven source-bound trial tests
pass in `trial-tests-001`. Complete offline bootstrap check exited0 at09:07:35Z,
211 input bindings. Source header and actual HAL are exercised in all four host
variants, not only an independent planner model.

`Tools/ota/p34_staging_erase_hal.patch` preserves the exact reviewed HAL overlay;
both `git apply --check` against the copied base and reverse-check against the
candidate succeed without applying either operation. The patch is a reusable
source artifact, not a change to the retained firmware or an acceptance result.
Archive-bootstrap completed normally with current30259 snapshot/config unchanged
and seven active entries. The verified older30258 record was copied/moved, never
deleted. Launcher started09:08:43Z at `runtime/launch-bootstrap-001`; no additional
APK build/install. Wait for its real service/App/query/download gates before
requesting a user Start. No stage-erase performance result exists yet.

Bootstrap service verified09:17:32Z with293196B package SHA
`22d5c8632c054fbd4db6a7f29a3c23be778a464cbd9842a7430645af4d2558db`.
All coordinator/network/s04 owners remain live. Fresh MCU readback confirms
the retained30259 raw SHA and unchanged Boot, BCB4 and all ordinary health flags.
App PID18931 launched09:24:28Z using the unchanged fixed-signer APK. Current
capture is `1791019466441785-1b4475aefb992bf7e66036df`.

User was asked to connect and download3.2.60 only. At09:26:13Z status remains
`APP_LAUNCHED_CONNECT_AND_DOWNLOAD`, live health30 records/29 producer lines,
zero starts/ends/loss/errors. Do not ask for Start until original download/query
admission becomes `READY_FOR_FULL_INSTALL_START`. No new firmware transfer has
started. Bootstrap target616932B raw SHA is
`9006050c2d0530a2180e53ebbda219165accda47860cd2086286a0e0813b5b3e`;
the prepared measurement target is30261, raw SHA
`bec377e3480a5260a580c7a6091cc713bb8466e5eeb604aa881227cf3683a5fb`.
Use the existing live bootstrap, not another launcher or APK installation.

`.cache/p34-staging-erase/continuation-audit-001.json` checks5318 contained entries,
source/compiled manifest bindings, the unchanged root Git index, preparation
closures and live trial ownership. Controlled build/test/cache/log output stays
in the project; only the existing exact SEGGER history exception applies.
The sole deleted source was this turn's redundant new test include shim; failed
r1 compile receipts remain. Root product files and frozen prior evidence were
not rewritten. Further work is bootstrap verification, then the prepared
measurement arm, not a claim that either speed target has been achieved.

Bootstrap download admission reached `READY_FOR_FULL_INSTALL_START`09:30:04Z.
User reported download complete. Exact293196-byte phone package matches the
expected SHA above; original checkpoint has four successful queries and45
producer lines, PID18931 and the expected runtime-config SHA
`97566636f556aad39534c3b26fa17bb89688869584abb196ad67af75f51331cb`.
At09:30:42Z live health is healthy with61 records/60 producer lines, zero
starts/ends/loss/errors. All three owners are live with sufficient remaining
time. User was asked to Start3.2.60 once, keep OTA foreground and USB attached,
and not switch to chat mid-transfer. Continue original collection/readback;
do not restart the admitted bootstrap, reinstall the APK or replay a success.

Bootstrap completed and original automatic analysis is `FULL_INSTALL_VERIFIED`:
`trials/bootstrap/analysis/1791020246114145400/result.json`, SHA
`5dc350d49fb388d9a9563626f4c9e83c166c0b6a4354e87bdc59737127236c47`.
The unchanged APK produced one start/end,9591 records/9588 producer lines,
lost0/error null. Full initial/final target readbacks match30260 raw SHA above;
Boot is unchanged, BCB4 and confirm_done/state_snapped/sd_ready are all1.
USB closed09:37:25Z; s04/network/coordinator exited0 normally by09:43:00Z.
No reset, halt, flash recovery, APK installation or OTA replay was used.

Bootstrap293196B transferred in21.778287s (13.462767KB/s decimal), with2291
complete valid ACK samples, zero retransmissions and zero ACK errors. DATA GATT
is10.966126s; END-to-target identity is38.103912s. This cell installs changed
executable code and was received by30259: it is not the staging-erase speed
measurement and its installation workload is not the prior header-only control.
Neither user speed target is met, and no performance checkpoint is justified.

Continuation checked3492 input records including the isolated build manifest,
unchanged root index and native history. JLink_x64.dll is an external read-only
input, not an output; the initial generic output guard correctly rejected that
input classification before any write. All next controlled outputs were checked
under `.cache/p34-staging-erase`; no external output authorization was expanded.
The prepared measurement remains30260-to30261 with the same APK/batch3/radio
policy. `runtime/archive-measure` started09:44:49Z with a600s finite owner;
protect30260 and archive only the older verified30259 capture, without deletion.
Wait for its original result/normal closure before the fresh measurement launch.

Archive-measure completed normally: moved only30259 capture
`1791015248853947-a862d34f1048c60892f40136` to the App-internal archive after
verified host preservation;30260 snapshot/config unchanged, seven active entries.
Fresh `runtime/launch-measure-001` started09:46:32Z and exited0 at09:48:09Z.
Measurement coordinator started09:48:08Z, session
`01ccda1457d54fac8b35f837ec596d19`, supervisor11556/worker10996,6000s bound;
network owner started09:51:44Z. The current operation is `trials/measure` and
must not be relaunched. No new OTA has been requested yet.

Existing `p34_batch_timing.py` produced `timing-bootstrap.json` without hardware
operations:21.778287s partitions into DATA GATT10.966126s, pre-last-chunk
nonwrite0.892521s, last-chunk-to-durable9.617043s, BEGIN-to-zero0.184960s and
final-durable-to-END0.117637s. Nested platform writes10.682495s already exceed
the5.863920s budget for50KB/s; do not add nested costs or label the durable tail
as isolated Flash. MCU payload erase separately measured72 callbacks/3.369394s.

`continuation-audit-002.json` checked5603 contained entries and72 redirected
environment paths, unchanged root index and authorized native-history bytes.
It includes original bootstrap closure and archive evidence. Its first read-only
attempt rejected a UTF-16 environment dump before writing; BOM-aware decoding
resolved that host audit issue without another device command. New outputs are
the measurement/archive/launcher trees, timing report, audit and this note, all
project-local; no new deleted path or project-external controllable output.

Measurement service verified09:55:39Z, expires11:21:44Z, package293164B SHA
`9c8c4b905d1d2a07de2a364c0fdc8efbfd5543ee8f28e3a88c5188d9e749961b`.
s04 started09:55:40Z, worker3032,3900s bound. Fresh passive MCU readbacks confirm
30260 raw image, unchanged Boot and ordinary confirmation/SD health. USB ready
10:00:48Z. Same APK PID10895 launched10:02:25Z; status is
`APP_LAUNCHED_CONNECT_AND_DOWNLOAD`, not transfer admission.

Capture `1791021745274654-89fa972ab02eab6998617420` is current and PID-bound, but
at10:03:57Z its original events file still contains only the open header, no
experiment/producer line. Existing launch screenshot is black. Do not declare
capture readiness or ask for Start from that header alone. Next necessary user
action: unlock/bring the existing OTA App foreground, connect and download3.2.61,
but do not press Start until original query/package/health admission passes.
Keep USB attached. Do not relaunch/reinstall or reuse bootstrap's admission.
Coordinator/network/s04 remain live; final incremental audit checked179 current
trial entries, unchanged index/native history and current target readback hashes.
Poll these existing owners and original capture first on continuation.

User reported measurement download complete. Original admission became
`READY_FOR_FULL_INSTALL_START`10:09:04Z. Recheck10:12:22Z verifies the exact
293164-byte phone package SHA above, two successful original App queries,
PID10895/current capture, and runtime-config SHA
`903792e5bca6e47ec8a736f22ec75fa57175a30dff87250fcd8f979b9084c9e4`.
Live health has16 records/15 producer lines, starts0/ends0/lost0/error null,
healthy true. Query bytes match the original recorded digest; all three owners
are fresh/live with sufficient reserve. No new device command or APK operation
was needed for this check; root index remains unchanged.

User is now asked to press Start3.2.61 once and keep the OTA page foreground
and USB attached throughout transfer/reboot verification. Poll this existing
measurement first; do not relaunch it, repeat the Start instruction blindly,
or replay a success to recover evidence. Automatic snapshot, target/Boot raw
readback, analysis and normal owner closure remain required before claiming
the candidate result or a speed improvement. This continuation's only manual
write is this project-local note; the existing finite owned collectors continue
writing under the previously checked measurement tree.

## STAGING-02: Verified Erase-Ahead Screening Gain

Measurement30260-to30261 is `FULL_INSTALL_VERIFIED`, original report
`trials/measure/analysis/1791022694105723500/result.json`, SHA
`a716a68ca994b79e7bd37c855d1f6a99a3fef236d56b1bab10ebb3f3eb0ae091`.
Original App snapshot has9528 records/9525 producer lines, one start/end,
lost0/error null and complete2291 ACK samples; zero retransmissions/ACK errors.
Raw target readbacks match30261 SHA above; Boot remains unchanged, BCB4 and
confirm_done/state_snapped/sd_ready all1. All three owners exited0 normally
by10:23:06Z. Retain30261; no OTA replay, reset or APK installation occurred.

Reusable read-only `Tools/ota/p34_staging_erase_review.py` validates original
closed reports, identical APK/Boot/device/link policy and actual raw-image
header-only workload classification. It uses the existing strict disjoint
timing analyzer. Ten new comparison regressions and thirteen existing timing
regressions pass. Output: `.cache/p34-staging-erase/review-001/result.json`.

| Metric | Same-APK batch3 control30257-to30258 | Optimized receiver30260-to30261 |
| --- | --- | --- |
| Complete legal package bytes | 293107 | 293164 |
| BEGIN-to-END ACK seconds | 21.580741 | 20.104213 |
| Decimal KB/s | 13.581878 | 14.582217 |
| END-to-target identity seconds | 21.305316 | 22.111564 |
| MCU payload erase seconds | 3.388285 | 1.621099 |
| DATA GATT seconds | 11.690324 | 11.217055 |
| Last DATA chunk to durable sum seconds | 8.927165 | 7.913809 |

Transfer saves1.476528s, size-normalized rate improves7.365246%; native erase
saves1.767186s on its separate clock, not an additive App-time component.
Installation/reconnect worsens0.806248s. Neither50KB/s nor20s is met. This is a
useful one-sample-per-role development screening gain, not repeatability,
strict same-package A/B, reference-size reliability or independent acceptance.
Bootstrap30259-to30260 must not replace the control: its executable-change
installation workload is different, and its receiving code predates the change.

The measured receiver still spends10.940400s in nested Android platform writes,
already above the5.863280s budget for50KB/s. Its full App-clock partition is
11.217055s DATA GATT,0.775090s nonwrite before last chunk,7.913809s last-chunk
to durable,0.135274s BEGIN-to-zero and0.062985s final-durable-to-END.
Reconnect has four attempts, including a three-timeout second binding and one
timeout before successful final INFO; do not treat failed attempts overlapping
apply/Boot as wholly recoverable delay. Final raw confirmation supplies the
confirmation absent from the coarse transient trace; do not reset to fill it.

Under the user's checkpoint-and-continue direction, preserve the bounded
staging source overlay, its tests/runner, reusable timing review and this note
on local `checkpoint/p34-staging-erase-20261003` using an isolated Git index.
Parent is the prior batch checkpoint, not a rewrite of main. No push, merge,
release, hidden unrelated product changes or standalone cache-free harness claim.

Saved checkpoint `a17cbfb71fa2cc608fa448ed59bdf1007bd86670`,12 scoped files,
branch `checkpoint/p34-staging-erase-20261003`. Receipt is
`.cache/p34-staging-erase/checkpoint-001/result.json`; main HEAD/index unchanged,
no push. Unified patch syntax passed forward/reverse apply checks; whitespace
checks cover all scoped code/tests/note, excluding the patch's required context
line spaces. This is a local development checkpoint, not a production merge.

## PUMP-01: Active-Only Scheduling Candidate

Next bounded development matrix retains30261 and all staging/GUI/radio policies.
The current641 pump entries span about20.07s (mean31.3ms), while nested pump work
is4.106319s. Configured20ms cadence is not the observed interval; synchronous
Flash/UI work and scheduler stalls remain included. Test whether a shorter
active-only eligibility interval reduces the avoidable portion, without claiming
all non-pump time is recoverable or that this alone can reach50KB/s.

Default-off `CONFIG_OTA_ACTIVE_PUMP` selects2ms only while the existing BLE overlay
owner is active; idle keeps the configured20ms. Reuse the existing cooperative
task manager and unchanged pump, ACK batching, byte order, protocol, watchdog,
4KB durability and200ms active UI cadence. No concurrent pump/ISR processing,
catch-up loop, IRQ/NVIC change, Boot change or APK installation is planned.
Source is isolated under `.cache/p34-pump-cadence/f`, copied from the exact
staging build manifest. Only its HAL scheduler wiring and new helper differ.
Host tests exercise the real task manager with flag0/1, ownership transitions,
rollover, disabled tasks, long stalls, duplicate ticks and independent tasks.

After host checks and GCC App-only build, prepare two legal FULL cells:
30261-to30262 installs the new receiver; only30262-to30263 measures its receive
path. Keep batch3/baud921600/window28 and existing INFO/reconnect policy, same APK
and observations. Build/test/package/observer preparation precedes user action.
Stop on integrity/resource failure or no useful measured gain; no blind repeats.
All controllable outputs remain under the authorized project root; the existing
exact native-history exception is unchanged. No additional device action has run.

Pump candidate host flag0/1 each passed375 real scheduler checks (750 total),
zero warnings/errors. Exact HAL overlay is `Tools/ota/p34_pump_hal.patch`;
forward check against the retained staging source and reverse check against
the candidate both pass without applying either operation. Source copy has3273
base files plus the new helper; root product files and old sources are unchanged.

GCC App-only build exited0 at11:07:44Z:616980B, raw build SHA
`b9ed337d648d266932060322c55dcb8083c25aa636326b2c08aee940f039946e`;
638 existing warnings, zero new warnings/errors, Boot not built. Asset worker
completed normally; both native positive decodes and eight negative package
checks pass. Prepared bootstrap293304B SHA
`ca804d017ef4dce0063311151a5e7019a114440d85b4c9b0e969d8f8bd101007`, target30262
raw SHA `392820031fb2b59e37bf6b14dab59cdb76e81c8c5e68cba3afb4da1782c3ee13`.
Measurement293292B SHA
`7aaaf6d515bca7efd4d54115c3526f0825a34b04473bc00cd2c3d976e4bac956`, target30263
raw SHA `c42d58d83efea96e62dc7a73444cb68c7b9101a762768db2ff686379b0031a68`.
Both target images are616980B and executable-identical outside the header.

`p34_pump_trial.py` reuses the original same-APK observers and binds both completed
staging arms as predecessors. Seven current controller tests pass. Finite
`runtime/check-bootstrap-001` completed `PUMP_OFFLINE_VERIFIED bootstrap 220`,
exit0. Archive-bootstrap also closed normally, protecting current30261 capture
`1791021745274654-89fa972ab02eab6998617420` and its config; only older30260 capture
was host-preserved and moved into the App's archive, no deletion or OTA replay.

Pump bootstrap launcher `runtime/launch-bootstrap-001` started11:18:27Z,
supervisor16288/worker15972,600s bound. Its coordinator will own
`.cache/p34-pump-cadence/trials/bootstrap`; do not start a second launcher or
modify pinned helpers. Wait for actual service/App/query/download gates before
inviting user Start. This candidate has no measured gain yet; saved staging
screening remains14.582217KB/s and22.111564s installation/reconnect.

Pump preparation audit `continuation-audit-001.json` checked5220 entries and36
redirected environment paths, source/build bindings, normal preparation-owner
closure, unchanged root index/native history and the saved local checkpoint.
Final incremental check covered188 live trial entries. No new project-external
controllable output or manual deletion; Git objects/ref/reflog and the isolated
index were explicitly checked inside the project before the checkpoint write.

Current pump bootstrap coordinator started11:20:03Z, supervisor2668/worker1456;
network started11:23:48Z, supervisor16128/worker14408, expires12:53:48Z; s04 started
11:27:32Z, supervisor7424/worker3704,3900s bound. All remain live. Service verified
11:27:31Z; fresh initial/final MCU raw readbacks match retained30261 and unchanged
Boot, BCB4 and all ordinary confirmation/SD health flags. USB ready11:32:39Z.

Same APK PID22042 launched11:34:16Z, capture
`1791027254979129-03e84a968d48b6137a2e3a51`, runtime-config SHA
`8204b63c7e4d829cbc02aa2f98e9a1891458089399153ae14b97cf5df381f48b`.
Download admission became `READY_FOR_FULL_INSTALL_START`11:35:48Z while host
checks were finishing. Do not ask the user to download again. Exact293304-byte
phone package matches the bootstrap SHA above; original checkpoint contains
three successful queries/20 producer lines, expected PID/config and verified
pre-start inputs. At11:36:50Z health has22 records/21 producer lines, starts0,
ends0,lost0,error null,healthy true. Existing owners have sufficient reserve.

User is now asked to Start3.2.62 once, keep OTA foreground and USB connected
through completion/reconnect, without switching to chat during the transfer.
Poll this original bootstrap first on continuation; do not relaunch/reinstall
or repeat the instruction blindly. Retrieve original snapshot and full target/
Boot readbacks and require normal owner closure before advancing to30263.
Bootstrap reception still runs on30261; it is not the active-pump speed result.

Pump bootstrap is now `FULL_INSTALL_VERIFIED`, original report
`trials/bootstrap/analysis/1791027809411548800/result.json`, SHA
`6e7ce23f0fd04d432b41464d24ed4073b148044deb4ce514956a3f52fe1b852e`.
The original snapshot has9554 records/9551 producer lines, one start/end,
lost0/error null,2292 complete valid ACK samples and no retransmissions/errors.
Fresh full target readbacks match30262 raw SHA above; Boot is unchanged, BCB4
and confirm_done/state_snapped/sd_ready all1. All owners closed normally before
the11:50:10Z check. No replay, reset or additional APK operation was used.

Bootstrap293304B transfer is19.802015s, DATA GATT11.231176s, END-to-target
identity38.455167s. It installs changed executable code and is received by30261;
do not use either timing as the new active-pump receiver benefit or replace
the header-only control with this different installation workload.
The prepared30262-to30263 measurement remains the next declared cell, with the
same APK/batch3/baud921600/window28/radio/reconnect policy and existing assets.

Measurement output/host/USB/runtime paths were preflighted under the pump area;
source bindings and root index remained unchanged. `runtime/archive-measure`
started11:50:49Z (supervisor14536/worker9568,600s), preserving current30262 and
archiving only the older verified30261 capture without deletion. Await normal
archive closure before the fresh `runtime/launch-measure-001` launcher; never
repeat the completed bootstrap or alter its pinned sources to advance.

Archive-measure exited0 normally at11:51:18Z, protecting30262 capture/config and
leaving seven active entries. Fresh `runtime/launch-measure-001` started11:53:09Z
and exited0; measurement coordinator started11:54:45Z (worker16072,6000s).
The current trial is `.cache/p34-pump-cadence/trials/measure`, not bootstrap.
Network owner started11:58:31Z (worker10756); verified service became ready
12:02:26Z and expires13:28:31Z. s04 started12:02:28Z (worker5872,3900s).
No App install, new build or repeated transfer was needed to prepare this arm.

Served measurement package is exactly293292B with the prepared SHA
`7aaaf6d515bca7efd4d54115c3526f0825a34b04473bc00cd2c3d976e4bac956`.
Wait for fresh receiver/phone checks and original App/download/query admission
before inviting Start. Do not shrink apply/reboot/collection allowances because
host preparation takes minutes; that overhead is not OTA performance time.

`continuation-audit-002.json` checked5520 contained entries and66 redirected
environment paths, preserved source identities, unchanged root index/native
history, original bootstrap closure and the completed archive. Current manual
edits are confined to this note; new host/runtime/archive outputs are in the
preflighted pump area. There are no new project-external controllable outputs
or manual deletions. Continue the existing finite measurement owners.

Measurement receiver admission now confirms30262 full raw SHA, unchanged Boot,
BCB4 and confirm_done/state_snapped/sd_ready all1. USB ready12:07:33Z.
Unchanged APK PID10775 launched12:09:13Z; capture
`1791029350907817-de830aa115e2ef193b8abdf8`, runtime-config SHA
`b7d16cad249a535710b4bf8274c62fb5dd32d70c5d5573183e04563a2ccf9314`.
At12:10:59Z status remains `APP_LAUNCHED_CONNECT_AND_DOWNLOAD`, healthy with
8 records/7 producer lines, starts0/ends0/lost0/error null. The downloaded-package
and original query admission are not yet complete; do not invite Start yet.

User is asked to download3.2.63 in the current OTA page, keep USB connected and
not press Start until package/query admission passes. Existing coordinator is
supervisor12504/worker16072, network2384/10756 and s04 16132/5872; all live.
Final incremental audit checked180 current trial entries and unchanged root
index/native history. No additional build, APK installation, reset, reflash or
OTA replay was used. Poll this existing measure trial first on continuation;
never use bootstrap's completed status or prior admission for the new transfer.

User reported3.2.63 download complete. Original measurement admission reached
`READY_FOR_FULL_INSTALL_START`12:13:01Z. Recheck12:16:47Z verifies the exact
293292-byte phone package SHA above, three successful original queries,
PID10775/current capture and the expected runtime-config SHA. Preserved query
bytes match their recorded length/hash. Health has30 records/29 producer lines,
starts0/ends0/lost0/error null,healthy true; all three owners are fresh/live with
sufficient reserve. Root index is unchanged. No new device command, launch,
installation or generated host artifact was needed for this download check.

User is now asked to Start3.2.63 once, retaining the OTA page foreground and USB
through transfer, reboot and identity verification, without switching to chat
during transfer. Poll this existing measurement first on continuation. Require
its original completed snapshot, exact target/Boot readbacks, normal health and
normal owner closure before judging active-pump speed. Do not replay a success,
relaunch the trial or repeat the Start instruction blindly. This turn's only
manual write is this project-local note; existing owned output paths stay as
audited in the measurement tree.

### PUMP-01 Result And Checkpoint

Measurement30262-to30263 is `FULL_INSTALL_VERIFIED`; original report
`trials/measure/analysis/1791030295726633100/result.json`, SHA
`86a9017a28e050ebb6e00e39e5cdfcdc54c8dae0938e5262c5e8057468a03899`.
Fresh initial/final target bytes match `c42d58d83efea96e62dc7a73444cb68c7b9101a762768db2ff686379b0031a68`;
Boot remains `a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
BCB4, confirm_done/state_snapped/sd_ready all1, no reset/halt/flash. USB closed
normally12:24:55Z; s04/network/coordinator closed normally by12:30:08Z. Original
snapshot has9544 records/9541 producer lines, one start/end, no loss/error,
2292 complete valid ACK samples and zero DATA retransmissions/ACK errors.

Reusable `Tools/ota/p34_receiver_review.py` verified the exact closed control,
bootstrap and measurement originals, both predecessor raw-identity edges, same
APK/Boot/device/link policy and actual header-only versus executable workloads.
Result: `.cache/p34-pump-cadence/review-001/result.json`; eleven host tests PASS
in `review-tests-002`. Initial review rejected an incorrect equal-count assumption:
BEGIN can activate profiling inside BT_OtaPump, adding one work sample without
an active entry. The initial gap starts at profile activation, so gap count is
pump_entries, not entries-1. Exact source: isolated HAL_Bluetooth.cpp132-168 and
940-978. New regression covers both legal counts and rejects a two-call gap.
Original trial data and source-pinned helpers were not changed or replayed.

| Metric | Staging control30260-to30261 | Active pump30262-to30263 |
| --- | --- | --- |
| Complete package bytes |293164|293292|
| BEGIN-to-END ACK seconds |20.104213|17.642275|
| Decimal KB/s |14.582217|16.624387|
| END-to-target identity seconds |22.111564|21.266501|
| DATA GATT seconds |11.217055|11.080134|
| Last DATA chunk-to-durable, disjoint App total seconds |7.913809|5.785919|
| Native active entries |641|4692|
| Native mean gap milliseconds |31.320073|3.751974|
| Native pump work seconds |4.106319|4.974716|

Useful screening gain: throughput+14.004519%, transfer2.461938s shorter. The
installation/reconnect observation is0.845063s shorter, but remains above20s;
neither user target is met. The reconnect-round stopwatch21.218853s is nested
and is not a replacement for END-to-target21.266501s. Native work increased and
native maximum gap remains about312ms; do not add native and App savings or
claim all scheduler stalls were eliminated. Boot transition sampling lacks an
initialized-target marker, so internal Boot timing remains an evidence gap;
separate full readback/ordinary confirmation and final App identity succeeded.
One sequential package per role is not strict same-package A/B, repeatability,
reference-size reliability or independent acceptance.

Preserve the bounded pump implementation, HAL overlay, build/assets/controller,
comparison/tests and this note as a local checkpoint based on
`a17cbfb71fa2cc608fa448ed59bdf1007bd86670`. Use an isolated Git index, retain
main HEAD/index and unrelated changes; no push/merge/release or APK installation.

### PUMP-BATCH-01: One Interaction Screening Cell

The active receiver reduced the disjoint last-chunk-to-durable total by2.127890s,
while DATA GATT remains11.080134s. Earlier batch12 on the old receiver saved
about0.97s GATT but lost that benefit elsewhere; that rejection still stands.
Changed receiver scheduling justifies one new interaction screening cell, not
blind batch growth or a repeated old transfer. Keep current30263 receiver and
use one legal header-only30264 FULL successor with dataBatchFrames12 on the
already installed schema7 APK. Compare with the current batch3 original; no
new MCU executable, Boot, UART, window, MTU, radio, INFO timeout or probe policy.

Prepare native positive/negative package checks, tested same-APK controller,
archive/protected capture, network and original snapshot/full readback closure
before user UI. One new transfer, no automatic repeats; reject on integrity,
loss/clock failure or no normalized throughput gain. Keep the verified target
and return sender config to batch3 for later work if batch12 loses; no firmware
downgrade or replay. This is a sequential-package interaction screen only.
Owned service deadlines retain6000s coordinator/3900s cell and normal apply/
verify reserve. All controllable files live under `.cache/p34-pump-batch12`
inside the authorized project, with the existing exact native-history exception.

Pump checkpoint saved: `de94bda22edfda959edc8ba51f77a37291d3858c` on local
`checkpoint/p34-pump-cadence-20261003`, ten scoped files, parent staging checkpoint.
Receipt: `.cache/p34-pump-cadence/checkpoint-001/result.json`. Root HEAD/index
unchanged, no push/merge. This checkpoint is pending integration, not mainline
delivery. The long inline checkpoint command was rejected by cmd's length limit
before execution; the contained source-pinned checkpoint script then completed
normally. No native device action was repeated for this host issue.

PUMP-BATCH-01 assets completed normally12:41:52Z:293304B, package SHA
`3c884d05d6538ed758ac82a31c3b19b56fb1471323f4ad23abe2b70a04c5da24`,
target30264/616980B raw SHA
`b3e7d35a492a0d51b9a4f3c1aa5ce7ccb4f2cf55f42839f758044f3dbb399f23`.
One native positive and four negative decodes pass, seven controller tests pass.
Offline check closed normally12:47:45Z with226 exact input bindings. The original
30263 measurement is the batch3 control; no new control transfer is planned.

Archive completed12:44:36Z: protected30263 capture/config unchanged, only older
30262 capture host-preserved and moved to the App archive, no deletion/replay.
Audit `.cache/p34-pump-batch12/continuation-audit-001.json` checked5849 contained
entries and144 redirected environment paths; root index/native-history bytes
unchanged. Preparation launcher started12:48:55Z and exited0 at12:50:33Z;
new coordinator owns `.cache/p34-pump-batch12/trials/measure` (worker7868).
Wait for live service, MCU identity and original phone-query/download admission.
Do not replay the launcher or modify any source-pinned helper while it is live.

Additional pump diagnosis from the same originals: ACK UART calls rose550-to1309
while bytes stayed43568-to43587; nested ACK write time1.024437-to1.786452s.
Faster eligibility improved total transfer but reduced ACK coalescing efficiency.
Do not blindly shorten2ms further or add this nested cost to App durations.
The pending sender batch12 interaction can reveal whether wire packing reduces
the dominant11.08s GATT path without losing the receiver-side gain.

Interaction service verified12:58:06Z, expires14:24:10Z. Coordinator7868,
network12556 and s04 worker6552 own the new trial; s04 started12:58:08Z with3900s
bound. Fresh full30263 App/Boot readbacks match the retained hashes, BCB4 and
confirm_done/state_snapped/sd_ready all1, reader closed normally. No reset,
Boot change, APK install or firmware executable build was needed.

Same APK PID16713 launched13:05:00Z; capture
`1791032697982510-6d9693f0b012a2579baa34b5`, runtime-config SHA
`4aaa0f138e610afbac4f80e9199d52eba4ab4493576860e262e77c07c7bfdf89`.
Original query/download admission reached `READY_FOR_FULL_INSTALL_START`
13:05:25Z. The exact293304B next package is already downloaded; do not ask for
another download. At13:05:49Z health has16 records/15 producer lines, healthy,
starts0/ends0/lost0/error null. The user now only needs to Start3.2.64 once and
keep OTA foreground/USB connected until ordinary completion/reconnect.
Poll the current trial first on continuation; do not replay launch/archive/OTA.

Next comparison entry is `Tools/ota/p34_sender_review.py`, seven current-source
tests PASS in `.cache/p34-pump-batch12/review-tests-002`. Its control is
`.cache/p34-pump-cadence/trials/measure`, measure is
`.cache/p34-pump-batch12/trials/measure`; use a fresh `--out` under the latter
experiment area only after original final reports and all normal owner closures.
It requires batch3/12 as the only sender-policy delta, actual raw predecessor
continuity, header-only workloads, same APK/Boot/device and complete-package
rate normalization. No synthetic missing result or new speed claim is allowed.
Final source self-check covers25 tests (receiver11/controller7/sender7); seven
new/modified Python files pass syntax/ASCII/whitespace checks. Root diff check
has no whitespace failures; pre-existing tracked files emit CRLF conversion notices.

### PUMP-BATCH-01 Result

30263-to30264 completed `FULL_INSTALL_VERIFIED`, report
`trials/measure/analysis/1791033134172828100/result.json`, SHA
`239b9a1b47110e10073187354e1eae0ff31ad7b706292494a18a7a7ee485c7f4`.
Original snapshot8918 records/8915 producer lines, one start/end, no loss/error;
2292 valid complete ACK samples, zero retransmissions/errors. Both target raw
readbacks match30264, unchanged Boot, BCB4 and ordinary confirmation/SD health.
All owners closed normally by13:17:33Z; no successful OTA was repeated.

`Tools/ota/p34_sender_review.py` produced
`.cache/p34-pump-batch12/review-001/result.json`: complete293304B transfer
16.953554s,17.300443KB/s, versus16.624387KB/s batch3 (+4.066657%). DATA GATT
fell11.080134-to9.720879s (1575-to1371 DATA chunks); other transfer time rose
6.562141-to7.232675s. Net transfer reduction0.688721s. END-to-target increased
21.266501-to22.004656s, so transfer+install changed38.908776-to38.958210s:
no whole-upgrade gain. Preserve the sender screening as a partial throughput
result, not stable repeatability or achievement of50KB/s/20s. Batch12 is the
current measured sender for the next independent installation candidate.

Native ACK time stayed1.790407s/1313 calls; payload erase1.641421s/72 calls.
Original FULL and descriptor-bound retained backup cost records are complete:
FULL6292 ticks = erase2988 + program974 + other2330;
backup6223 ticks = erase2958 + program969 + other2296. These are MCU millis
ticks, not calibrated wall seconds and not additive to the App interval.

### HALF-ERASE-01: Payload Boundary Erase Candidate

Prepare one default-off App-only32KiB erase extension after the verified30264
receiver. The current install planner uses64KiB for aligned interior payload
and4KiB for prefix/tail. For this622592-byte candidate extent it needs32
commands; adding32KiB at complete aligned payload spans reduces this to18,
without widening the extent or including the separately erased4KiB slot header.
Backup adds its unchanged mandatory candidate-header re-erase. Do not combine
the slot header with a block operation or reuse old markers.

The existing read-only W25Q128BV Rev E manual copy and text under
`.cache/p34-erase/references` document opcode52h/24-bit address in7.2.24 and
120ms typical/800ms maximum in8.7. This is capability evidence, not actual board
timing or proof of the exact silicon revision. Gate by the same cached W25Q128
JEDEC and enabled Flash gate as64KiB; other chips and flag-off retain old calls.
Keep the raw range/self-test reservation guards, WREN/RDSR, bounded polling,
watchdog servicing, XIP restore-on-error, no hidden retry, marker-last, immediate
backup readback, CRC/SHA, BCB ambiguity handling and unchanged Boot.

Isolate source/build/tests under `.cache/p34-half-erase`, copying the exact
retained pump build manifest. Use an additive planner/API, preserve old wrappers
and I/O structure. Host matrix: all4/32/64 capabilities and aligned spans,
overflow/partial bounds, actual raw-driver failures, HAL feature/chip/restore
guards, real backup success/failure/marker/BCB regressions. Only after these and
GCC App-only build/package checks pass, prepare30264-to30265 bootstrap and
30265-to30266 header-only measurement on the same APK/batch12/link policy.
No extra repeats; stop on integrity/clock/resource failure or no installation
benefit. Ordinary worker/apply/verification bounds and exact native-history
exception remain unchanged. No new hardware mutation has run for this candidate.

Partial sender screening saved as local checkpoint
`10fa716fffc80bfef690769c1712c9cd2861e2c3`, branch
`checkpoint/p34-pump-batch12-20261003`, parent
`de94bda22edfda959edc8ba51f77a37291d3858c`. Six scoped files, isolated index,
main HEAD/index unchanged, no push/merge. Receipt is
`.cache/p34-pump-batch12/checkpoint-001/result.json`.

HALF-ERASE-01 host r4 passed: planner6666758 assertions, backup799643 total
assertions (including original155967), driver32/64 checks101/82, and five HAL
variants12706/12706/12711/887/456 checks. No warnings/errors. Exact copied source
includes3274 base files plus the helper. Only the five existing overlay files
and new planner header differ. `Tools/ota/p34_half_erase.patch` preserves the
overlay; forward/reverse checks pass with `--ignore-space-change` for existing
mixed CRLF/LF context, without applying either operation.

GCC App-only build completed13:49:47Z:617324B, raw build SHA
`3aa22ae98fc7361b9308cf9488ffbbc193fcad521b63aca5d5656f419f75e58b`,
638 existing warnings, zero new warnings/errors, Boot not built. Build owner
closed normally. Both packages completed native positive/four-negative checks
at13:51:37Z and preserve the same Boot. Bootstrap30265 package293421B SHA
`05b7d9e64a4a6e3cbcaa37f36683aeb38a3aaab241e902d983af0b21283dd9a6`,
target SHA `dc25f08fec894a4d0a7a5f468cb4d9a522607821c788178bc404956878df2970`.
Measurement30266 package293448B SHA
`f8289d8c9eafda047dda9465f287e8c58a2d1bf79e8cf0b0a2515fee026155ea`,
target SHA `ddc9c8b60a04ce36134e8418c927532a5f680b735056752f338a6dbc6d58893b`.
The two targets are executable-identical outside the96-byte firmware header.
Six same-APK controller tests passed. Offline bootstrap and bounded archive
preparation now run under the half-erase runtime; wait for normal closure before
launching the new coordinator. Bootstrap reception still uses30264 old erases.

### HALF-HOST-01: Test Harness Lessons

1. Category E (assumptions): the firmware snapshot carries older tests than the
   already-verified64KiB extension. Initial preflight stopped before test outputs;
   bind the live baseline test to its original `p34-erase/tests/r2` SHA instead
   of assuming every copied test is newest. No prior file was rewritten.
2. Category B (interface): r2 HAL stubs used host `size_t` for32-bit I/O lengths.
   Strict C++ compilation rejected all three callbacks. Use the actual uint32_t
   contract; never cast the mismatch away or enable permissive compilation.
3. Host launch discriminator: r3 `default.exe` exited4294967295 with empty output
   before main, including under the debugger. The byte-identical copy named
   `hal.exe` passed12706 checks. The OS mechanism is unknown; this proves a
   filename-dependent host issue, not a firmware failure. Preserve
   `diagnose-hal-001..003`, and use `hal-<variant>.exe` for every HAL fixture.
4. Prevention is executable: current r4 reruns the default, all flag combinations,
   chip fallback, every erase-failure position and restore failure with strict
   warnings. Old helper/source bytes, device state and successful OTA evidence
   remain untouched; no device replay was used to repair these host issues.
5. Knowledge capture stays in this existing task record because `.trellis` and
   its template tree are absent. Do not fabricate a general OS root cause or
   rewrite project governance from this single host observation.

### HALF-ERASE-01 Executable Contract

Scope/trigger: opt-in32KiB payload erases in the App installation path only;
the64KiB/4KiB baseline, unchanged Boot and the wire/staging protocol remain the
control. This extends the experiment, not any frozen acceptance contract.

Signatures:

- `ota_erase_next_size_mixed(uint32_t address, uint32_t remaining, int allow_block, int allow_half_block)`
  returns0/4096/32768/65536, reusing the existing planner's invalid-span rejection.
- `qspi_status_t qspi_erase_32k(uint32_t block_addr)` uses52h and the existing
  bounded4000ms block wait; it never grants capability or expands the window.
- `ota_backup_stage_with_mixed_erase(io, bcb_hal, out, erase_64k, erase_32k)`
  adds optional typed ports without changing `ota_backup_io_t`. Old wrappers
  pass null for32KiB; `erase_count` still counts successful4KiB coverage units.

Contracts: prefer a fitting64KiB block, then32KiB, otherwise4KiB. All blocks
are aligned and fully inside the requested payload span. HAL32KiB requires
`CONFIG_OTA_INSTALL_HALF_ERASE=1`, the existing block opt-in and cached W25Q128
with an enabled Flash gate. Headers stay separate4KiB operations. The first
failed/uncertain command stops the phase; no fallback erase, program or commit.
XIP restoration is still attempted after raw-operation failure. No structure,
BCB/marker format, byte order, durability or confirmation changes are included.

| Validation or error | Oracle |
| --- | --- |
| Null32KiB port / flag off | Same old planner sequence and old backup wrappers |
| Other chip / disabled gate | No32KiB call; disabled installation fails closed |
| Misalignment, overflow, incomplete tail | Reject or use4KiB, never round outward |
| Header failure | No bulk erase or subsequent programming |
| WREN / command / busy failure | First failure returned, no retry |
| Partial failed32KiB command | No success count for that block, no STAGED |
| Bad erased bits / program readback | Reject before markers/BCB commit |
| Restore failure after erase | HAL returns failure even if erase succeeded |
| Normal622592B extent | Candidate18 commands; backup19 including its mandatory header re-erase |

Good/base/bad: at aligned0x8000 with32768B remaining the half-enabled planner
selects32768; half-disabled selects4096. At0x8000 with28672B remaining it must
select4096. Wrong: merge slot metadata into a32KiB command or report one erased
sector for a block. Correct: invalidate the4KiB header first, use payload-only
aligned blocks and count eight successful sector units per32KiB operation.

Required tests are the executed r4 planner/real-backup/driver/HAL suites above.
Cross-layer review checked both new HAL call sites, driver declaration/body,
additive C wrapper, all flag combinations and source/map/package provenance.
No import cycle or new mutable wire/runtime field was introduced. Tests and
build establish development readiness, not measured speed or independent acceptance.

Offline bootstrap check closed normally13:58:18Z (`HALF_ERASE_OFFLINE_VERIFIED`
236 bindings). Archive closed normally13:55:15Z, preserving current30264 capture
and config while moving only the host-preserved30263 capture, no deletion.
Audit `continuation-audit-001.json` checked5728 contained entries/99 environment
paths, exact unchanged root index/native history, and byte-identical renamed
host diagnostic. Bootstrap launcher started14:01:47Z, exited0 normally;
coordinator started14:03:25Z, worker15352,6000s. Poll this existing bootstrap
before any new launch. Await actual service/MCU/App gates before user UI.

Bootstrap service verified14:10:53Z, expires15:37:04Z. Network worker12636 and
s04 worker7948 are live; s04 started14:10:55Z with3900s bound. Fresh initial/
final App readbacks still match30264 raw
`b3e7d35a492a0d51b9a4f3c1aa5ce7ccb4f2cf55f42839f758044f3dbb399f23`;
Boot unchanged, BCB4 and confirm_done/state_snapped/sd_ready all1. MCU reader
closed normally; no reset, halt, flash or Boot operation was needed.

Same APK PID12221 launched14:17:50Z; current capture
`1791037068044724-99d047d290f1dd231d0e979a`. Original package/query admission
reached `READY_FOR_FULL_INSTALL_START`14:19:12Z. The293421-byte bootstrap is
already downloaded and matches its prepared SHA, so do not request another
download. At14:19:26Z health is16 records/15 producer lines, starts0/ends0,
lost0/error null, healthy. The only next human action is Start3.2.65 once,
keeping the OTA page foreground and USB attached through ordinary completion.
Do not repeat launch/archive/OTA on continuation; poll this existing bootstrap.
It installs the new implementation but does not measure its receiving/install
benefit. The unchanged-code30266 successor remains the subsequent declared cell.

HALF-ERASE-01 implementation is still an uncommitted development candidate;
do not label its host build/tests as measured speed. The latest actual sender
screen remains17.300443KB/s and22.004656s installation/reconnect, with no total
upgrade improvement or50KB/s/20s achievement. The current scripts, matrices,
native failure receipts and original successful trials remain preserved.

### HALF-ERASE-01 Bootstrap Closure

User reported the admitted3.2.65 upgrade complete. Original automatic analysis
finished14:33:03Z with `FULL_INSTALL_VERIFIED`, report
`.cache/p34-half-erase/trials/bootstrap/analysis/1791037684240728600/result.json`,
SHA `930f7d49dfaba66bd117be9763494696f8bbe1ecd7ca9217619ce56412b0cf35`.
The8953-record/8950-producer-line snapshot has one start/end, no loss/error,
2293 complete valid ACK samples and zero DATA retransmissions. Both installed
App readbacks match30265 raw SHA above, whole Boot is unchanged, BCB4 and
confirm_done/state_snapped/sd_ready all1. All three owners exited0 normally
by14:33:05Z; no reset, replay or extra collector was needed.

Bootstrap transfer293421B took16.367937s (17.926572KB/s); END-to-target took
38.420578s. This is the changed-executable bootstrap received/applied by30264,
not the32KiB candidate measurement or a header-only comparison. Its original
FULL erase record still has32 calls. VTOR-observed Boot residency is bracketed
22.2170224..25.1960993 host seconds; this is not isolated flash-copy time and
does not by itself establish the cause of the longer total. Keep this result,
including the slowdown, separate from the retained header-only control. Neither
50KB/s nor20s has been achieved. Host post-processing is outside OTA timing.

The already-declared30265-to30266 measurement is next, with unchanged executable
outside its96-byte header, the same APK/batch12/link policy and unchanged Boot.
Finite offline owner `runtime/check-measure-001` started14:33:45Z; bounded
archive launcher `runtime/prepare-archive-measure-001` started14:34:05Z. Both
live under `.cache/p34-half-erase`. Archive protects30265 and only host-preserves
and moves the verified older30264 capture. Wait for normal closures and offline
PASS before starting the measurement coordinator. Never replay the bootstrap.

Offline measure check passed236 bindings and closed normally14:37:33Z. The
archive worker closed normally14:34:53Z, with the protected30265 snapshot and
configuration unchanged, seven active capture directories and private USB
closed. Measurement launcher `runtime/launch-measure-001` started14:38:25Z
and exited0 normally after handing off to the6000-second coordinator. Its
worker4568 started14:40:04Z; network worker15844 started14:43:47Z. Poll the
existing `trials/measure`, not another launch. There is no new APK/build/OTA.

### HALF-REVIEW-01: Repeatable Screening Comparison

Scope: new `Tools/ota/p34_half_erase_review.py` is an offline reader for the
three declared batch12 roles, not a firmware change or independent acceptance.
It reuses original report/closure validation, actual raw header classification,
App timing partition, pump statistics, RTT descriptor validation and the strict
cost parser. Existing source-pinned trial helpers were not modified.

Entry after all measurement owners close normally:

    python -I -S -B -X utf8 Tools/ota/p34_half_erase_review.py --out .cache/p34-half-erase/review-001/result.json

Signatures: `compare(rows)` computes control-to-measure App timing/rate changes;
`parse_costs(texts)` requires one complete successful FULL and backup block;
`installation_costs(store, row)` verifies original report/native/RTT hashes and
returns phase records plus `erase_command_plan_observed`. Output is write-once
under the checked project root. No device, network, reset or OTA operation exists
in this entry. A missing measure report/closure is a prerequisite failure, not
permission to synthesize an observation or replay OTA.

Contracts: roles are30263-to30264,30264-to30265,30265-to30266; batch12 and the
remaining link policy must match exactly. Actual raw SHA continuity, same
APK/Boot/device, foreground, legal complete-package lengths and finite positive
App durations are mandatory. Only control/measure are header-only. Transfer and
END-to-target are disjoint App intervals; native phase ticks and nested
GATT/ACK/pump times are not added as wall savings. The bootstrap is preserved
but never used to calculate the candidate gain.

Bad/missing/truncated/orphan/duplicate/failed cost phases fail closed. Retained
bytes are reconstructed only with `p34_full_trace.ring_tail` and matching
original partial/pending records; `p34_native_ring.py` is an Android log helper,
not the MCU RTT decoder. Planned full/backup commands are32/33 for control and
bootstrap,18/19 for measure, covering622592/626688 bytes respectively. A different
observed count is reported false, never relabeled as the expected count.

Ten tests passed in `.cache/p34-half-erase/review-tests-002/result.json` (the
earlier eight-test result remains in `review-tests-001`). Assertions include
role/policy/identity rejection, smaller-package normalization, invalid clocks,
separate50KB/s/20s boundaries, partial-vs-total gain, excluded bootstrap/native
times and malformed cost records. Current-source ASCII/syntax/whitespace checks
pass. Real read-only control/bootstrap samples and their32/33 cost counts pass;
the complete three-role comparison is NOT_RUN until measurement exists.

Review dimensions: reused existing decoders instead of redefining their units,
kept experiment-specific policy outside old batch3 comparisons, no import cycle,
no mutable protocol/API field and no change to running sources. No `.trellis`
tree exists, so this executable contract stays in the existing task note.

### HALF-ERASE-01 Measurement Ready

User reported download complete. Service verified14:47:53Z, expires16:13:47Z;
s04 worker2488 started14:47:55Z with3900s bound. Fresh initial/final30265 App
and whole Boot readbacks match the prepared receiver/unchanged Boot; BCB4 and
confirm_done/state_snapped/sd_ready are1. Native reader closed normally without
reset/halt/flash. Same installed APK launched14:54:47Z, PID459, capture
`1791039287079074-d6f8dfe1a81f0a829517d60e`.

Original successful App query and exact293448-byte measurement download passed
admission14:56:40Z (`READY_FOR_FULL_INSTALL_START`). Package SHA remains
`f8289d8c9eafda047dda9465f287e8c58a2d1bf79e8cf0b0a2515fee026155ea`;
runtime config SHA is
`ccd3ffd2a3b541a0447a9daee87c011b6acb439340167313c2fd0e8062e9e86b`.
At14:59:22Z health is10 records/nine producer lines, zero starts/ends/lost,
error null, healthy; all three owners have fresh live unforced heartbeats.
Only user Start3.2.66 once is needed, with OTA foreground and USB retained.
Do not request another download or rebuild/reinstall the APK. Poll this existing
measurement on continuation, and never replay launch/archive/bootstrap.

Audit `continuation-audit-003.json` covered545 contained entries,135 environment
paths and240 unchanged live-source bindings. Root index and the exact authorized
native-history file remain unchanged. New review helpers are uncommitted host
preparation, not a measured candidate improvement; retain the prior checkpoints.

### HALF-ERASE-01 Measured Result

30265-to30266 completed `FULL_INSTALL_VERIFIED`; original report
`.cache/p34-half-erase/trials/measure/analysis/1791040252023917200/result.json`,
SHA `80c21636ad19c2abf4641c54e970c152729300292d5e6a3a5a65fa0d4c43b943`.
Original snapshot8935 records/8932 producer lines, one start/end, no loss/error,
2293 complete valid ACK samples and zero DATA retries/errors. Both full target
readbacks match30266 raw SHA above, Boot unchanged, BCB4 and ordinary
confirm_done/state_snapped/sd_ready all1. All three owners exited0 normally by
15:15:59Z; no successful OTA was repeated for evidence.

Automated comparison `.cache/p34-half-erase/review-001/result.json` verifies
the actual predecessor chain, header-only control/measure, same APK/batch12,
all original inputs/closures and both complete native cost phases:

| Metric | Control30263-to30264 | Measure30265-to30266 |
| --- | --- | --- |
| Complete package bytes |293304|293448|
| Transfer seconds |16.953554|18.095728|
| Decimal KB/s |17.300443|16.216424|
| END-to-target seconds |22.004656|20.363205|
| Transfer plus installation seconds |38.958210|38.458933|
| Full/backup erase commands |32/33|18/19|
| Full/backup erase ticks |2988/2958|2465/2514|
| Full/backup total ticks |6292/6223|5752/5764|

Useful installation screening gain1.641451s; throughput fell6.265846%, so the
disjoint App total improves only0.499277s. Neither50KB/s nor20s is met. Preserve
both the gain and regression; do not compare against the changed-executable
bootstrap's38.420578s to magnify savings. These are single sequential legal
packages, not repeated reliability or full executable replacement acceptance.
MCU ticks are not calibrated wall seconds and are not added to the App savings.

Save the bounded mixed-erase implementation/overlay/tests, measured comparison,
and task note as a local checkpoint based on `10fa716fffc80bfef690769c1712c9cd2861e2c3`.
Use a private Git index; preserve main HEAD/root index and unrelated changes,
with no push/merge/release. The actual verified30266 target remains installed.

Next discriminating observation: DATA platform writes alone took9.877679s,
above the5.868960s whole-transfer budget for50KB/s. DATA GATT10.113985s and
last-chunk-to-durable7.122125s remain separate App partitions, not additive
native costs. The current pump mean gap3.678977ms and clean MCU counters do
not identify the radio/platform delay cause. Do not blindly expand CRC tables,
remove UART ACK settling, or repeat the rejected100ms reconnect setting.
`runtime/native-ring-001` started15:21:58Z for one bounded read of existing
PID459 Android Bluetooth log records, output `native-ring-001`. No App restart,
system report, APK installation, setting change or OTA replay is included.

Half-erase checkpoint saved locally as
`389b03fca7bd824d324e97e75187b0731c7a9cb4`, branch
`checkpoint/p34-half-erase-20261003`, parent `10fa716fffc80bfef690769c1712c9cd2861e2c3`.
Fourteen scoped files, private index, unchanged main HEAD/root index, no push,
merge or release. Receipt: `.cache/p34-half-erase/checkpoint-001/result.json`.
The reproducible checkpoint entry is `Tools/ota/p34_half_erase_checkpoint.py`;
its read-only `check` passed before `save`. Do not replay the spent save entry.

### LINK-NEXT-01: Current HCI Retrieval Boundary

`native-ring-001` read the exact still-installed APK/current PID459 without
restart or setting change. It closed normally15:22:09Z with an empty native
log. This is an evidence gap, not proof of zero Android overhead, and it is not
permission to rerun the successful OTA. No system report was requested.

`Tools/ota/p34_link_status.py` reuses the original read-only status worker via
function-local global bindings instead of editing the old source or pretending
30252 is current. Inputs require an original `FULL_INSTALL_VERIFIED` report,
normal trial closures and the exact original installed APK. Its three tests
pass in `link-status-tests-001`; actual `link-status/status-003` and private USB
closed normally15:32:50Z. Full HCI property remains `full`; protected/public
snoop paths are unreadable. Existing report inventory contains only the prior
September30 reports and the earlier October3 03:05 report, not this measurement.
No Bluetooth toggle, report generation, APK operation or OTA was issued.

The already-tested direct AdapterService/manager routes have no packet block
under full logging (HCI01 history); do not repeat those unpromising probes.
Next bounded route is one new system report in
`/data/user_de/0/com.android.shell/files/bugreports`, including its ordinary
system-managed log/stats sidecars, then local extraction of Bluetooth members
to `.cache/p34-half-erase/hci-export-001`. Reuse `p34_hci_current` deadline/
retrieval primitives and the existing strict HCI/ATT parsers. Protect all prior
phone reports, never retain/upload the whole report on the host, and never
regenerate to repair a failed retrieval. Generation can temporarily re-enumerate
USB and reports can contain unrelated application/device diagnostics.

This exact new report/privacy scope still needs user confirmation. The previous
explicit two-report and subsequent one-report authorizations are completed
operations, not an unused reporting allowance. All safe current-trial analysis,
speed checkpoint and read-only route checks are complete; retain30266 and await
only this scope decision. Do not ask for another firmware/App upgrade.

LINK-NEXT-01 authorization: user replied "do it" to the exact new-report request
in this thread. This permits one new system report and ordinary sidecars in
`/data/user_de/0/com.android.shell/files/bugreports`, preserving existing reports.
Local Bluetooth-only extraction goes to `.cache/p34-half-erase/hci-export-001`;
do not save/upload the full report on the host. Recheck actual phone output
ancestry and full-logging/service state immediately before generation. No OTA,
APK installation, setting toggle, existing-file deletion or second generation.

`Tools/ota/p34_link_hci.py` binds the current30266 completed trial and its closed
status check to the existing `p34_hci_current` generator/retriever and1500s USB
adapter. One1800s owned worker covers generation<=900s, retrieval<=180s and
closure. Host tests include prior export/uncertain-generation guards and the new
current-input/immutable-adapter checks. A failure is reconciled from the saved
intent/output; never reissue the generation to repair missing host evidence.

### LINK-NEXT-01 Export And Correlation Complete

Exporter30 tests passed in `hci-export-tests-001`; original parser24 regressions
passed in `hci-analysis-tests-001` (no skips). Owned exporter started15:41:33Z,
completed and exited0 normally15:45:21Z. Exactly one real `bugreportz -p` ran.
Generated phone report:
`/data/user_de/0/com.android.shell/files/bugreports/bugreport-PD2312-TP1A.220624.014-2026-10-03-23-41-48.zip`,
20573703B, SHA `6c619e811c56ef11d64ee72b0c7bba96b56bbfbf1750e76c0fd31550028bf787`.
Only Bluetooth members were retained locally: `hci-export-001/hci-01.btsnoop`
2993807B SHA `e57352f156ebfb8f452dda166aa18c07563c6d95362f631d7746864ffd2e9d34`,
and `hci-02.btsnoop`3414652B SHA
`4e7040756e032c0700a296dfb4a45bd06ec164406bba7c47260161e2c3632dbf`.
Both have zero truncated packets/reported drops; packet counts13434/16384.
Full ZIP was processed in memory, not saved on host or uploaded.

Read-only `post-hci/status-003` also closed normally. Report inventory gained
exactly the generated ZIP; all three old ZIP names/sizes remain unchanged.
This is an inventory/size check, not a new full-hash check of the old reports.
The new report and its system sidecars remain on the phone as authorized;
no cleanup/deletion was requested or performed. No APK/MCU operation or OTA.

`hci-correlation-002/result.json` binds original generation2 to the complete
293448-byte30265-to30266 package and both raw identity hashes:2293 DATA,
2293 valid ACKs,1378 DATA ATT writes. Same-HCI-clock BEGIN-to-END ACK is
18.079495s (16.230984KB/s); END-to-target is20.276939s. These corroborate,
but do not replace, App18.095728s/20.363205s. Absolute vendor wall-clock mapping
is unverified; HCI is host/controller capture, not an over-air measurement.

Current link sequence before DATA:45ms,7.5ms,45ms,15ms. DLE settled at251
octets each direction; no parameter update occurred during DATA. HCI last-chunk
tails total6916.163ms =2768.522ms through the controller completion report plus
4147.641ms after that report. All72 block subspans are nonnegative. Completion
events include reporting latency; the latter span is not isolated MCU Flash cost.

`hci-link-001/result.json` preserves original controller request/feature records.
Before BEGIN, record4515 is host LE Connection Update opcode0x2013 requesting
11.25..15ms (`0113200e0e0009000c000000f40100000000`); observed final interval15ms.
Record2523 is successful remote LE features for the same handle14:
`043e0c04000e00eff1010000000000`. Feature bit8 is set (LE2M capability).
No LE Set PHY command or successful PHY read/update appears on this connection.
Actual negotiated PHY remains UNKNOWN; DLE2120us allowance is not a PHY verdict.
Do not infer that50KB/s is attainable merely from capability or halve observed
time by assuming2M air time dominates.

Read-only dependency inspection fetched `flutter_blue_plus-1.35.5` in memory
and verified the exact lock SHA
`bfae0d24619940516261045d8b3c74b4c80ca82222426e05ffbf7f3ea9dbfb1a`.
It exposes `getPhySupport()` and `setPreferredPhy(txPhy, rxPhy, option)` but no
public actual-PHY read/update stream in the inspected device/adapter APIs.
The setter is explicitly a preference and its Future only confirms method
invocation. Existing App source does not call it. No dependency, APK or PHY
configuration was changed by this inspection, and no package archive was saved.

Next direction: a default-off Android PHY-preference experiment with actual
negotiation observation, not another blind cadence/CRC/baud change. Preserve
exclusive GATT ownership, timeout/fallback, connection-generation checks and
all durable/identity gates. Any App change must use the standing development
CI route and fixed signer; a successful preference call alone is not evidence
of2M or a reason to declare performance success. No new APK build/install,
new firmware package or additional report generation has been started.

### HCI-HOST-01: Empty Connection Metadata

1. Category E/D: the original correlator required FFF1/FFF2 declarations even
   for a connection with zero ATT rows. New capture generation1 connected and
   disconnected without ATT; generations2-4 contain valid declarations. This
   was a host-analysis assumption, not lost DATA or a failed upgrade.
2. The unmodified CLI rejection remains in `hci-correlation-001/failure.json`.
   No parser result was overwritten and no report/OTA was repeated. The first
   wrapper edit's clone lookup was corrected before test execution to the real
   `p34_batch_trial.clone` entry, rather than guessing a nested module attribute.
3. `p34_hci_trial.analyze(data, package, expected)` preserves the entire raw
   capture, timestamps, all ATT rows and generation IDs. It retains empty
   connection metadata separately and only omits it from characteristic decoding.
   Every nonempty connection still passes the original strict analyzer.
4. Three regressions passed in `hci-correlation-tests-001`: empty metadata is
   retained, nonempty bad declarations cannot be filtered away, and this actual
   complete2293-frame capture correlates. Do not generalize to suppressing a
   partial/malformed ATT stream or a different package's BEGIN.
5. `.trellis`/template trees are absent, so this contract and prevention record
   remain in the canonical task note. Existing source-pinned analyzers stay
   immutable; the additive adapter and tests are uncommitted diagnostic work,
   not a new speed checkpoint or mainline delivery.

## PHY-01: Explicit Preference With Actual Readback

Continuation on2026-10-04 created `.cache/p34-phy/src` from installed App
source c5a8c53195bcda43e3ae060f7ce5e8007a4cf6ae. Root HEAD/index and unrelated
tracked changes remain untouched. `Tools/ota/p34_phy_validation.py` owns the
exclusive branch `dev/flutter/p3-4-phy-observation-20261004`; host outputs are
project-contained. No local Flutter/Gradle build, phone command or firmware
change occurred. Upstream Android plugin4.0.5 was hash-verified before safe
extraction; its license and exact original archive are retained.

First WIP57a06316a7fc560d9f0c60dcc2e5be568e6ae21f ran development CI37137053728.
Both hosts failed with six pre-existing vendored Dart lints and five new
test-fixture write-mode mismatches, not a device failure. Original artifacts
are preserved under `.cache/p34-phy/ci/37137053728/`. The updated fixtures use
the explicit without-response mode required by batch12; no guard was relaxed.
The additional cancellation repair ensures a pending native PHY read cannot
issue a new preference after acknowledged cancellation. Native host tests
passed173 assertions initially and215 after this change, zero warnings/errors.

Schema8 adds default-off `androidPhyPolicy=off|observe|prefer2m`. Probe sequence
is read-before, optional preference/update, read-after, then ordinary identity
recheck and BEGIN. Only actual2M in both directions admits the2M candidate.
Timeout/missing/unsupported/stale evidence blocks the experiment before transfer.
Each GATT object is single-use for this probe because Android callbacks lack a
request token; no automatic reconnect/retry or completed-OTA replay is added.
Observations are pre-BEGIN samples, not a continuous DATA PHY trace.

Reusable `p34_phy_artifacts.py` separates Flutter and native reports, preserves
failed CI inputs, and supports one explicitly dispatched same-package/fixed-signer
APK after both-host green checks. No APK has been requested or installed yet.
Measured performance remains16.216424KB/s and20.363205s from HALF-ERASE-01;
neither50KB/s nor20s is achieved by this source work.

### PHY-01 Development And Device Entry

Stable development commit41d147a94294911929fba08478ab0b5337ed1107 passed
checks-only run37137779427 on both hosts: Linux659 passed/16 skipped,
Windows642 passed/33 skipped. Both native runs passed215 assertions. Original
artifacts and native input bindings are retained under
`.cache/p34-phy/ci/37137779427/`; Windows native source hashes correspond to the
exact CRLF checkout of the pinned LF Git blobs, recorded separately from raw
blob identity. The initial host collector rejected Windows path separators and
then CRLF hashes. Those failures/duplicate original downloads remain; the fixed,
tested adapter reuses existing verified receipts instead of redownloading.

One explicit same-signer APK request, run37138093799, passed both hosts and
Android compilation. APK SHA256:
`7cafe0c20956cd6791f9c9a495feeac19843cd390d09b0fdcdee4ecb4edc748a`.
Package `com.wen.gaia.gaia.p34probe`; fixed certificate remains
`9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
Receipt `.cache/p34-phy/apk-g1/apk.json` binds actual APK, original both-host
Flutter/native reports and exact commit. This is a development APK, not release,
Windows EXE verification or independent acceptance.

Finite hardware plan under the existing P3-4 task authorization:

- Sole owner Codex; phone10ADA4197U001CK/V2312A, private ADB5062,
  BLE 02:00:00:00:00:01; host outputs remain under `.cache/p34-phy`.
- Necessary same-package replacement only: old APK a4854908...44387 to the
  above verified APK. Preserve settings, permissions, runtime config and the
  original completed30266 snapshot byte-for-byte. No uninstall/data clear,
  automatic phone taps, new system report or Boot replacement.
- Start from confirmed30266, App rawSHA ddc9c8b6...893b, BCB4,
  confirm_done/state_snapped/sd_ready all1; original whole BootSHA
  a63346db...df4 remains. Recheck actual state before subsequent device work.
- Two full header-only cells:30266->30267 observe; only after confirmed success,
  30267->30268 prefer2m. Same executable, baud921600/window28/batch12,
  payload244/without-response, high priority/scan paused and INFO2000/probe500.
  These are sequential screening packages, not identical-package A/B or1MiB
  reliability acceptance. Unsupported/unknown/not2M stops the candidate before
  BEGIN; no assumed success or automatic same-GATT probe retry.
- Assets `.cache/p34-phy/assets/result.json`: observe293487B,
  SHA0e491732c3d292ca7e95aaf424d20a6ad3397b2437864b75e4610970d74a5cca;
  prefer2m293495B,
  SHA1a5c0a5f2e4f733f68768e166cc4423d22ed79dbe9ebdb83fa558e9e5d1e5564.
  Each passed actual native positive decode and all four negative guards;
  asset worker closed normally in6.33s, no build or device operation.
- Use existing600s installation owner and bounded OTA/network/MCU collectors;
  do not shrink transfer/apply/reconnect allowances. Preserve uncertain outcomes
  and reuse the original snapshot instead of repeating an upgrade. Retain the
  last fully verified target, never App-only downgrade across BCB changes.
- Installer adapter4 tests, trial policy3 tests and artifact adapter2 tests
  passed locally. After APK identity/offline preparation, only real unlock,
  vendor installer dialog or in-App start/navigation is assigned to the user.

At17:13Z the first install owner completed read-only checks and returned
`NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED`: exact old APK matched, phone powered
overUSB but `mWakefulness=Asleep`. No stop/install intent exists; no App stop,
replacement, config write, firmware transfer or system report was performed.
`.cache/p34-phy/runtime/install-001/closed.json` confirms normal worker exit0;
USB stop/server/launcher all0, port5062 closed, adbkey unchanged. This is an
unspent installation requiring a fresh source-bound resume after actual unlock,
not permission to replay the existing launch path or overwrite its result.

The complete `p34_phy_trial.py check --arm observe` also passed offline,
binding243 original source/evidence records and the correct target context.
Its history-chain hash checks took several minutes; they are host preparation,
not measured OTA time. Future startup performance work should measure/reuse
unchanged immutable inputs without weakening hashes or editing frozen helpers.
No PHY request or new full OTA has occurred. The next human action is to unlock
the phone and keepUSB connected. All local download/asset/check/install workers
are closed; no short device window is left running while waiting for the user.

### PHY-02: Resume After User Readiness

After the user confirmed ready, `p34_phy_install_resume.py` verified the original
install-001 no-attempt/closed receipts and used a fresh install-002 directory.
Three host regressions passed. The bounded wake gate observed Awake at17:20:49Z;
one same-signer replacement completed at17:21:22Z. Installed SHA is exactly
7cafe0c20956cd6791f9c9a495feeac19843cd390d09b0fdcdee4ecb4edc748a.
Original snapshot/config/permissions were preserved; no uninstall/data clear,
App launch or OTA was performed by the installer. Owner/USB closed normally,
port5062 closed and the read-only adbkey hash was unchanged.

`p34_phy_trial_resume.py` binds the successful install-002 result and its exact
closure instead of relabeling the old install-001 no-attempt receipt. Two host
regressions passed, including rejection of lost permissions. Original pinned
installation/trial helpers and old test receipts are unchanged.

Before the observe cell, archive-observe moved only inactive capture
1791037068044724-99d047d290f1dd231d0e979a to the App's existing
files/p34-archived-observations directory after host backup and byte verification.
Protected completed30266 capture1791039287079074-d6f8dfe1a81f0a829517d60e and
configuration were unchanged; seven active capture directories remain. No
deletion/OTA occurred; the archive owner closed normally at17:24:43Z.

The observe coordinator was launched at17:29:07Z under its existing6000s bound.
Inputs are the prepared30266->30267 package and schema8 observe policy. Actual
new PHY/OTA results are not yet known; never treat process launch as readiness.

Host setup profiling was captured during the required launch, without an extra
device run: `.cache/p34-phy/launch-profile-001.pstats`. Main226.106s,
context214.540s;284602 stat calls took79.063s,20023 buffered reads69.468s,
20343 opens19.984s,19275 SHA256 calls11.488s. These are host preparation costs,
not BLE or installation time. Future optimization must preserve fresh output
preflight and immutable input/hash validation; do not patch the running source-
pinned coordinator or remove checks merely to accelerate startup.

The observe service became ready at17:38:29Z and the s04 device worker started
at17:38:31Z under its3900s bound. New APK process25415 launched at17:45:42Z,
capture1791049540786102-976637933aaa484110151ba7, sentinel
OTAOBS96bb2c74d5ad6ccecaf30e40. Runtime schema8 observe config SHA:
10f8dc68dc1bef99ebfe4b3adea8cdb07a9c35d76104609e66c7e1eefdbce59a.

At17:47:39Z `READY_FOR_FULL_INSTALL_START` was recorded. The original App
checkpoint contains two successful GET_INFO queries, negotiated payload244,
without-response writes and batch12; its loss/error counters are clear and
upgradeStarts/upgradeEnds were0. The phone-downloaded293487B package was
retrieved and bound before admission in `cells/s04/queries/result.json`.
The user was invited to click Start for3.2.67-p34p, keeping the App foreground
without switching to chat during transfer. This is readiness, not a PHY verdict
or completed upgrade. The finite coordinator/network/s04 collectors intentionally
remain active for that action; do not launch a second owner or repeat installation.

### PHY-LOG-01: Capture Failure And Retained Target Reconciliation

The admitted observe invocation began, but at17:50:03Z its recorder reported
35 records,33 producer lines,one start,no end,lost784 and `invalid-record`.
`cells/s04/result.json` remains `FULL_INSTALL_INCOMPLETE`: the host capture
failed, not an established firmware failure. The s04 worker exited1 normally;
network/coordinator exited0 without forced termination. No OTA was repeated.

Read-only `p34_phy_failure.py` retrieved the original App bytes under
`.cache/p34-phy/reconcile-001`. The same PID25415 remained live. Recovery health
had lost8907 and no snapshot; Android ring retrieval returned zero bytes.
The USB owner closed normally at17:53:08Z. Unhealthy originals remain ineligible
for speed or PHY conclusions; no footer or healthy result was manufactured.

Bounded `p34_phy_readback.py` then used the prepared30267 target bindings and
the existing native-history exception. It performed no OTA/reset/halt/flash,
retained921600 and verified full raw App/Boot twice. Result at18:00:56Z:
`PHY_TARGET_30267_RAW_AND_BOOT_CONFIRMED`; App617324B,
SHA b6452ac18c37dd7ce5cc8c27cfeab336583ed8446847a4379f7d83d11ae55e66;
whole Boot65536B, SHA a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
Final session is idle, BCB4,confirm_done/state_snapped/sd_ready all1.
Closure `.cache/p34-phy/readback-001/installed-mcu/closure.json` SHA
f639147e97e108f1a7e2b5d7717093b9862f54b9681ba0a8ffd7d5338b30f025;
worker closed normally at18:00:57Z. Native-history hash stayed7e0d3213...95f90.
Therefore the target installation succeeded and30267 is retained, while
App reconnect timing, DATA speed and actual PHY remain unmeasured this trial.

Root cause categories C/D: PHY producers were added without propagating the
exact `OTA_PHY ` / `OTA_PHY_CANCEL ` prefixes to the Dart recorder and Python
envelope reader. Previous service tests enabled experiment config but not the
real diagnostic sink. The repair is isolated from the installed source in
`.cache/p34-phy-logfix/src`, based on41d147a94294911929fba08478ab0b5337ed1107,
exclusive branch `dev/flutter/p3-4-phy-logfix-20261004`.

Repair invariants: add only the two exact prefixes; preserve loss/credential/
multiline/capacity/hash/identity guards and all transport behavior. Eight service
scenarios now exercise enabled diagnostics and automatic snapshot import through
the real Python reader, including cancellation NACK and close NACK. Host parser
tests also enforce Dart/Python prefix parity and reject lookalikes/sensitive data.
Local29 host regressions passed; Flutter/Android CI remains pending. No local
Flutter build, new installation, new OTA or threshold improvement is claimed.
Historical source/evidence remains unchanged. `.trellis`/template trees are absent;
this note and the development-branch repair note retain the prevention contract.

### PHY-LOG-02: Development Validation And Remaining Cell

Repair commit b85f50aae66f51895aa4f9bbb9a82732138bae3b passed checks-only
run37142839035 on both hosts. Flutter3.47.6/framework5fc346839b5d0eef006ed8404392afb4dfae428d,
Dart3.13.5; Linux662 passed/16 skipped, Windows645 passed/33 skipped,
no test failures and strict analysis passed. Original host/native reports are in
`.cache/p34-phy-logfix/ci/37142839035`. The explicit same-package/fixed-signer
APK dispatch37143201736 is pending; no Windows EXE/release or independent
acceptance was requested. Root HEAD/index and tracked unrelated changes remain.

`p34_phy_logfix_install.py` reuses the private USB route, verifies the exact
old APK and raw-confirmed30267, preserves unhealthy event bytes and configuration,
then admits one required same-signer replacement. Five simulated guard tests
passed, including asleep/wrong APK no-op, uncertain installation and changed
evidence rejection. No real installation has yet occurred for this repair.

`p34_phy_logfix_trial.py` is the tested successor entry for the original matrix's
remaining30267->30268 prefer2m cell. No observe replay or additional candidate is
admitted. Before its device window: verify repaired APK, back up and move only
the stopped invalid capture and its exact config to existing App archive/retired
directories without deletion; keep the protected30266 snapshot unchanged.
Then perform offline context/config checks and prepare collectors before inviting
user navigation/download/Start. Trial retains the exact prepared293495B package,
unchanged Boot and firmware executable,921600/window28/batch12 and prior policies.
The raw-confirmed30267 predecessor is explicitly `RAW_CONFIRMED_CAPTURE_INVALID`,
not a fabricated successful observation. Source-bound host envelope integration
adds only the exact new prefixes, retaining the runtime query/identity helpers.

Six current successor tests passed, covering strict reader behavior, source/target
and actual2M gates, no observe replay, prestart guards, exact no-delete archival,
redirected paths and uncertain moves. The first four-test fixture referred to a
nonexistent helper name; failed trial-tests-001 is preserved. It was corrected to
the real `experiment_record`, four tests passed in002; expanded six-test batch003
passed. These are host fixtures, not physical archive/install/OTA outcomes.
Only after repaired installation/archive and actual readiness may the remaining
cell run. Report pre-request/post-request actual PHY; even a valid snapshot does
not establish continuous DATA PHY or identical-package A/B acceptance.

APK run37143201736 subsequently passed both hosts and Android compilation.
Verified download at18:22:29Z:131658682B,
SHA aef3d433a54da801b594f5ddce64b5bdf80f0c0f1c2016a42f1188e04ae96934;
package/signing certificate and observation sentinel remain unchanged.
Receipt `.cache/p34-phy-logfix/apk-g1/apk.json` binds original host/native reports,
APK bytes and repair commit. No Windows EXE/release/independent acceptance.
The successor's full offline check is running before the installation window;
the APK receipt's `installed=false` is build provenance, not a mutable device verdict.

Full offline check passed with235 bindings before opening USB. At18:26:20Z,
the600s install-001 owner started; the exact installed old APK still matched
7cafe0c2...c748a. Actual power state was `mWakefulness=Asleep`, so the helper
returned `NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED` at18:26:32Z. Neither stop-intent
nor install-intent exists. No App stop, replacement, config change, archive move,
new firmware transfer or system report occurred. Worker exited0 normally;
USB stop/server/launcher all0,port5062 closed,adbkey unchanged.

The only current human requirement is unlock/wake while keepingUSB connected.
Preserve this no-attempt result. Resume with a fresh source-bound install-002
entry after checking the closed/no-mutation receipts; do not reuse install-001.
The prepared trial's installation binding must consume that new success receipt,
not relabel this no-op as a successful installation. No short OTA/network window
has been opened while awaiting the user. Current retained firmware30267 and the
original failed observation remain unchanged; measured throughput/install-reconnect
remain16.216424KB/s and20.363205s from the earlier half-erase checkpoint.

### PHY-LOG-03: Resumed Installation After Readiness

After the user's ready message, `p34_phy_logfix_install_resume.py` validated the
closed install-001 no-attempt and original USB command receipts. Eight host tests
passed, reusing the original installer boundary fixtures against a fresh output.
The new install-002 worker observed Awake at18:35:28Z and completed one same-signer
replacement at18:35:58Z. Installed APK SHA is
aef3d433a54da801b594f5ddce64b5bdf80f0c0f1c2016a42f1188e04ae96934;
original invalid capture/config/permissions were byte-preserved, App remains
stopped and no firmware OTA occurred. USB and supervisor closed normally.

`p34_phy_logfix_trial_resume.py` binds the actual install-002 success/closure,
not the old no-attempt result. Two binding regressions passed. It reuses the
unchanged prepared archive/remaining prefer2m machinery and source-pins both
the old helpers and the new resume adapter. The invalid capture/config archive
is now launched under its600s owner; all original failures remain preserved.

Archive recovery-001 stopped before mutation with `App must remain stopped`.
Its owner exited1 normally and USB closed; no move-intent exists. Read-only
startup-inspect-001 then found repaired APK process20656, started around the
installation's completion, and the same eight old capture directories/config.
No new capture belongs to this process. The install receipt's `app_launched=false`
means only that the agent did not launch it; the earlier statement that the App
remained stopped is superseded by this actual PID observation. Do not blame this
on a user action or infer an extra OTA. Future install handoffs must check actual
post-install process state, not treat absence of an agent launch as proof.

A bounded, getters-only Dart VM query through privateUSB/forward6129 timed out;
runtime-state-001 remains `RUNTIME_STATE_INCOMPLETE`, not a proved idle state.
It performed no restart/install/OTA and closed its forward/USB owner. Do not
repeat the identical collector or interpret the timeout as device failure.

`p34_phy_logfix_continue.py` owns recovery-002 under900s: fresh passive complete
App/Boot/idle readback first, then recheck exact PID/config and all eight capture
headers before stopping the recorder-blocked process. The installed enabled
recorder cannot initialize at eight directories and cannot admit BEGIN without
its log; this software invariant supplements, not replaces, the fresh MCU state.
Only then reuse the tested no-delete invalid-capture/config archival in a fresh
output. Two continuation guards passed. No new APK or firmware mutation is
authorized by this host repair; the only remaining physical cell is prefer2m.

Recovery-002 completed at18:49:19Z. Fresh passive readback again matched30267
App/full Boot and confirmed idle BCB4; checkpoint SHA
a44b08318f669155fa4d62b5f40c1fc6fd3725a1d52ee70276d39dddee362f0d.
After verifying all eight original headers and unchanged config, the blocked
process20656 was stopped. Only invalid capture1791049540786102-976637933aaa484110151ba7
and config10f8dc68...ce59a were moved to existing App archive/retired directories.
Their raw bytes and the protected30266 snapshot were verified unchanged; seven
active captures remain. Both private USB windows and the recovery owner closed.
No reinstall/reset/flash/OTA occurred. Launch preparation for the remaining
prefer2m cell now uses `p34_phy_logfix_continue.py`, binding this recovery and
actual install-002 success while preserving recovery-001's failure.

The remaining cell coordinator launched at18:53:38Z, network at18:57:37Z,
and s04 at19:01:34Z under the existing finite bounds. The verified service is
https://heaven-exempt-adapters-aerospace.trycloudflare.com and expires20:27:37Z.
New App process17433 launched at19:08:19Z with capture
1791054496947888-3a837d37e40cd24a8410dddc and unchanged observation sentinel.
Runtime schema8 prefer2m config SHA:
228b05a9947ff0b429b59bd858f91d2c0b416002e3bf598fac5a151c9222548c.

At19:08:56Z s04 recorded `READY_FOR_FULL_INSTALL_START`. Two successful original
App GET_INFO queries, payload244/without-response, batch12 and the downloaded
293495B package were verified in `cells/s04/queries/result.json`. Recorder health
was clear with zero starts/ends and zero lost records. This is readiness, not
a measured PHY or successful upgrade result. The next required user action is
Start for3.2.68-p34p and keeping the App foreground without switching to chat.
Coordinator/network/s04 deliberately remain owned and active for that action.

### PHY-LOG-04: Completed 2M Screen And Offline Reconciliation

After the user's completion message, the existing owners finished without a new
OTA, APK installation, reset or parallel reader. Final report at19:25:53Z:
`.cache/p34-phy-logfix/trials/prefer2m/analysis/1791055240036225300/result.json`,
SHA7491896ab53d42e029cd14f457a5b9ae8a77b39166c59f0e710d5621f3126f5d,
`FULL_INSTALL_VERIFIED`. s04/network/coordinator exited0 normally by19:25:56Z.
USB closed normally; the temporary network is closed, not a usable download URL.

The original App snapshot is1018331B,
SHA5499e1c968503bca0d5dc48114a8a879635d80aa4cbf46a3148fe078e63597bc:
8973 records,8970 producer lines,one start/end,completed,healthy,lost0,error null.
Before BEGIN, the bound PHY observation records actual Tx/Rx1M-to-2M, successful
read/update statuses and connection generation2. This is not continuous DATA PHY
observation. Final complete617324B App readback matches target30268 raw SHA
737e22d8fcdc5afa58ebf1c983bfd2eb8b32e7fd3e456951e450ce2b06c718d2.
Whole Boot65536B remains a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4;
BCB4,confirm_done/state_snapped/sd_ready all1 and idle session were verified.

Reusable `Tools/ota/p34_phy_review.py` consumes only original closed reports,
strict snapshots, actual PHY/config bindings, full raw readbacks and native
installation phases. `review-tests-002` passed8 tests, including all three real
closed inputs, malformed/duplicate/incomplete timing markers, exact50KB/s and20s
boundaries, shifted clock origins and faster-transfer/slower-total comparisons.
Initial7 pure checks passed; the first integration invocation rejected the
lowercase semantic device address when the original envelope required its exact
uppercase target. The adapter now uses the original report's sentinel/target and
separately checks semantic address equality; no original evidence/guard changed.

Review `.cache/p34-phy-logfix/review-001/result.json` SHA
aa42da0e47c8d2da99969d5429e022a9dc6c031024c69ea3b623887f259e800b.
Uniform public OTA_MONO boundaries give:

| Sample | Complete package B | BEGIN-to-END s | Decimal KB/s | END-to-target s | Total s |
| --- | --- | --- | --- | --- | --- |
| Historical batch12 |293304|16.958695|17.295199|22.004656|38.963351|
| Historical half-erase |293448|18.099745|16.212825|20.363205|38.462950|
| Current prefer2m |293495|17.015007|17.249185|21.959865|38.974872|

Earlier entries'16.953554/18.095728 transfer values use the internal link-stats
stopwatch. They are not identical to public OTA_MONO boundaries. This review
recomputes all three from originals rather than mixing those durations; current
internal transfer17.012066s differs from public by2941us. Relative to half-erase,
transfer saves1.084738s but END-to-target adds1.596660s, total adds0.511922s.
Neither target is met; no causal PHY gain, matched-package A/B, repeatability or
independent acceptance is established. No new measured-speed checkpoint is made;
checkpoint389b03fca7bd824d324e97e75187b0731c7a9cb4 remains the saved milestone.

The strict internal App partition closes to17012066us: DATA GATT10125201,
pre-last-chunk nonwrite635598,last-chunk-to-durable5994134,BEGIN-to-zero136125,
final-durable-to-END121008. Platform9882938 and service-wrapper242263 are nested
inside DATA GATT. Platform duration alone exceeds the entire5869900us budget
for this package at50KB/s; durable tails are not isolated Flash costs.
All2293 DATA/ACK samples are complete, no retransmits/early-invalid/error ACKs;
1383 DATA chunks,one discovery and zero GATT errors. Native counters are clean:
staging I/O2.227550s,ACK UART calls1.938289s,pump work5.079729s and mean pump
gap3.710986ms. These native durations overlap App spans and are not extra costs.

Original installation profiles: full5777 ticks (erase2487,program961,residual2145),
backup5730 ticks (erase2473,program958,residual1884);32/64KiB mixed planning
observed18/19 erase calls over the unchanged622592/626688B extents. Native millis
is not calibrated App wall time. Boot residency is bracketed6.157803..8.781380s;
the transient trace still lacks initialized/CONFIRMED target, while the later
separate complete readback supplies confirmation. No reset fills this trace gap.
App reconnect round21.883401s has four attempts2.012746/10.012961/3.033546/5.296438s,
the first three no_verdict and last completed;1.527710s is outside attempts.
The second attempt has three2s INFO failures, last succeeds on its second INFO.
Do not sum nested discovery/INFO/attempt/native durations or retry100ms blindly.

### LINK-NEXT-02: Reuse Existing Evidence Before Another APK

Offline review of the locked FBP1.35.5/Android4.0.5 source confirms each
without-response write still waits for the native callback under global BLE
serialization. The callback means local buffer availability, not durable MCU
ACK. Removing that callback/serialization is not an admissible speed fix.
The current original logcat contains discovery/MTU lines but no native DATA
write/callback records, so it cannot split9.882938s into Android queue versus
Flutter callback delivery. No unchanged failed native-ring collector was rerun.

Historical raw HCI e57352f156ebfb8f452dda166aa18c07563c6d95362f631d7746864ffd2e9d34
was parsed with the existing `p34_hci_att.analyze`: generation2/handle14,
record2582 sends MTU512 (`020002`),2586 receives MTU247 (`03f700`). The earlier
remote request2526 is also247. This is historical capability evidence, not a
current2M connection measurement; it rejects a blind larger-MTU APK experiment.
The preserved module manual documents AT+AINTVL as advertising interval, not
connection interval; no undocumented AT connection command was sent.

Existing generic `p34_link_status.py` was reused with this trial and fresh
`.cache/p34-phy-logfix/link-status/status-003`, without another bespoke collector.
At19:35:25Z exact installed APK still matched; full HCI logging is enabled but
protected/public snoop paths are unreadable. The four existing ZIP reports all
predate this OTA, newest2026-10-03-23-41-48 local time. Read-only status/USB owners
closed normally, no setting toggle/report generation/restart/install/OTA.

Preferred discriminating next step: one new system report plus ordinary sidecars
under `/data/user_de/0/com.android.shell/files/bugreports`, then Bluetooth-only
extraction under `.cache/p34-phy-logfix/hci-export-001`, using the existing
bounded generator/retriever and strict correlation against this exact package.
Preserve existing reports. Process the ZIP in memory, do not save/upload its
unrelated contents on the host. Generation can temporarily re-enumerate USB and
creates device/application diagnostics beyond Bluetooth. Previous explicitly
limited report authorizations are consumed; this new report scope is not yet
authorized. No generation has been started and no short device window remains.
After that scope decision, first bind the generic route to30268/current APK and
current original snapshot; never replay30266's fixed exporter or this OTA.
The observation should distinguish changed connection/DLE/PHY and controller
backpressure from callback scheduling before committing to another APK change.

LINK-NEXT-02 standing authorization,2026-10-04: the user explicitly approved
this and future equivalent diagnostic-report requests without repeated approval.
This supersedes the preceding pending-scope condition for the same phone/task,
report directory and ordinary sidecars, project-contained Bluetooth-only
retention, no upload/full-report host retention and no deletion of old reports.
Use evidence-driven finite operations; uncertain generation must be reconciled,
not blindly repeated. Broader data access, deletion or unrelated devices are not
included. Routine host/window renewal and equivalent report collection need no
new question; ask only for actual human-only actions or a real scope change.

`Tools/ota/p34_current_hci_export.py` parameterizes the verified trial, status,
fresh output and source-bound tests while reusing the existing1800s supervisor,
1500s USB session,900s generation and180s retrieval primitives. Its per-operation
one-report bound is duplicate prevention, not a per-task authorization quota.
This operation binds current30268, repaired APK and the successful prefer2m
snapshot; output `.cache/p34-phy-logfix/hci-export-001`. No new OTA/APK/reset.

### INFO-TIMEOUT-01: Same-APK Reconnect Screen

Current HCI confirms actual bidirectional2M,15ms interval,251-octet DLE and no
parameter updates during DATA. All2293 DATA/ACKs and1383 chunks match the original
package. HCI BEGIN-to-END17.004864s and END-to-first-target21.873535s corroborate
but do not replace public App17.015007/21.959865s. The joined original contains
20752 records; the exact analysis prefix ends at16889, while later target query
16988 remains in the full joined file and original rotations. Zero drops/truncation.
Derived files and provenance are in `hci-correlation-001`;34 exporter,3 rotation
and6 queue tests passed. No successful upgrade or report was repeated.

DATA-feeding spans total10.065214s: tracked DATA has outstanding controller
completion reports during9.087835s and none during0.977379s, peak12 packets.
Completion reporting is delayed, so this is not proof of physical buffer fullness
or a pure Flutter stall. Durable tails5.806478s split at completion reports into
1.680474s before and4.126004s after; neither part is isolated Flash cost.
No speculative native queue rewrite/new APK is justified by this alone.

Execute one bounded reconnect screen to target the independent20s objective:
30268->30269 header-only FULL, same installed repaired APK, executable, Boot,
921600/window28/batch12/payload244/without-response/prefer2m/high-priority/paused
scan and500ms probe cadence. Change only `rebootInfoTimeoutMs`2000->1000, already
supported by installed schema8 (allowed500..10000). This does not shorten the
overall reconnect window, relax identity, overlap requests or repeat the rejected
100ms cadence. Motivation: three2s failures in attempt2 and one in the successful
attempt4; whether1s improves alignment is unknown until measured, not a forecast.

Owner Codex, existing phone/BLE and project root. Prepare a legal successor with
native positive/four-negative decode, test the inherited config/envelope guards,
verify current completion and same APK, then archive only the inactive30266
capture by host backup plus no-delete phone move, protecting current30268.
The original finite archive/USB/network/cell/readback machinery is reused through
`Tools/ota/p34_info_timeout.py`. Retain latest fully verified target; no downgrade,
Boot replacement, automatic UI taps, data clear or APK installation. Stop this
screen on unresolved integrity/clock/device state; no blind additional cells.
Host outputs under `.cache/p34-info-timeout`; user acts only for actual in-App
download/Start once the complete observation route is ready.

LINK-NEXT-02 export closed normally at19:46:05Z after220.63s. Exactly one
`bugreportz -p` generated phone ZIP2026-10-04-03-42-39,19666544B,
SHA78770669541c8b392ebaa219621b3ce79221c21cb179933ffc1229972004c8dd.
Only the two Bluetooth members were retained on the host:1152699B,
SHA1a2e8e3f24f919391f5c37189463c0dbabff6ab7faba1de8daec2736303e44d5,
and3321455B,SHA722f5834f2326c7e5c5aabe0bf678445c8115abde427313886805b7a6823959d.
No whole report was saved/uploaded, no report was deleted. Post-HCI read-only
status completed20:03:28Z: all four prior ZIP names/sizes remain and exactly the
new ZIP appears, with its ordinary dumpstate log/stats sidecars. This inventory
does not claim a fresh hash of all old phone reports. All report/status USB and
supervisor owners closed without forced termination; ADB key unchanged.

Two offline assumptions were corrected without another report/OTA: the vendor
rotated mid-DATA, and the old correlator allowed only one target INFO in the
entire capture. `p34_hci_rotated.py` validates each original's drop/truncation
counters, header and monotonic record order, rejects duplicate/overlapping parts,
then concatenates packets without editing them. The full joined4474138B file
SHAbae3881af56837a1dd0135db6918229818574a3f56e98a54de6c02cb49c104b6
is retained. The exact3393249B prefix through first target INFO is a labeled
derived input, SHA76ba9af16b62e77b732b6e979577cbd481bca1ac8ebaa2e786da4f4a36f39344.
The unchanged strict verifier still checks the full package, all DATA/ACKs,
CRC/sequence/durable and old/new identities. Later query metadata and all original
bytes remain available, rather than fabricating a single-query original log.

Correlation SHA c70d65e969aa2b90811cb2703e3f690df6d44dd892ee8ee6faf32ab5e97a9cdc
records generation3/handle9, actual PHY update2/2 at13772 and15ms interval at13760;
no DATA-phase parameter change. Its inherited generic PHY warning does not
override the explicit raw update event. Completion reports acknowledge groups
of1/2/3/4 DATA packets261/158/154/86 times respectively, median inter-report gap
15.922ms; these reporting groups are not over-air connection-event packet counts.
`p34_hci_queue.py` separately preserves queue accounting. Relative provenance
paths are canonicalized before comparing all path/size/hash fields; no hash
guard was removed. Negative tests reject changed sizes/digests and bad clocks.

INFO-TIMEOUT-01 preparation:293472B legal package,
SHA346c26f41ec697ec3bd99dc1ee6d3a88e9a28ca9de826f3f5e4d479a63d2ae7e;
target617324B raw SHA7dc6f8b5d506e8a4a9b57eb28d9acfde7377d23be9a340bb6f9b88473736943f.
Asset owner exited0 at19:57:09Z; native positive and four negative cases passed.
Five adapter tests and full252-binding offline check passed, without new CI/APK.
At20:05:42Z the verified inactive30266 capture was backed up and moved, not
deleted; current30268 snapshot/config were unchanged and seven active captures
remain. Archive owner/USB closed normally. Prestart again observed that exact
snapshot/config with no live App PID. The coordinator began20:10:14Z, network
20:14:02Z and cell20:17:45Z, with existing6000/finite-network/3900s bounds.
Verified origin https://generate-sorted-pork-cartridges.trycloudflare.com expires
21:44:02Z. At this entry no new transfer has started; poll existing owners instead
of launching another collector or retrying the upgrade.

INFO-TIMEOUT-01 reached `APP_LAUNCHED_CONNECT_AND_DOWNLOAD` at20:24:34Z,
using the unchanged APK and new process11955. The current native reader is ready
and the before-OTA checkpoint retained confirmed30268/unchanged Boot. Its startup
screenshot is black; no new capture-health receipt or downloaded-input admission
exists yet, so this is not `READY_FOR_FULL_INSTALL_START`. The user was asked to
unlock/open the original App, connect E-Track and download3.2.69-p34p, without
pressing Start until the real query/package/recorder checks pass. This is an
actual UI action, not another authorization or APK-installation request.
Coordinator/network/s04 remain owned and bounded while awaiting that action;
do not create a competing USB/RTT owner. Runtime config keeps INFO1000ms,
probe500ms and all remaining link settings unchanged. No new OTA was observed.

INFO-TIMEOUT-01 observation update,2026-10-04: the existing worker admitted the
download at20:36:13Z after two original successful queries and exact293472B
package readback. The user reported download, was invited to Start only after
that admission, then reported completion. Capture1791059072852634-5cabcb857c855624bf58ab99
from unchanged APK/process11955 has8936 records/8933 producer lines, starts=ends1,
outcome completed,lost0,error null,healthy true. Original snapshot SHA
8cd40f29fae85185bd0a08ffb40e0775ac395af877b673bfd75fd02ff7f6460e.
Its public OTA_MONO durations are17.744681s transfer,20.649056s END-to-identity,
38.393737s total,16.538590 decimal KB/s. These remain a sequential screening
sample, not matched-package A/B or repeatability acceptance. Compared with the
prior2s timeout: transfer adds0.729674s, installation/reconnect saves1.310809s,
total saves0.581135s. Neither50KB/s nor20s is met. Compared with the half-erase
checkpoint total38.462950s, the difference is only0.069213s; do not promote that
single-sample difference as a proved new speed milestone.

The same owned post-upgrade reader completed full App/Boot readback and recorded
final state at20:42:22Z: target raw7dc6f8b5d506e8a4a9b57eb28d9acfde7377d23be9a340bb6f9b88473736943f,
Boot a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4,
BCB4,confirm_done/state_snapped/sd_ready all1,idle session. Native trace is closed;
coordinator/cell/network closure and final strict analysis are still pending at
this entry. No competing MCU or USB collector was started.

The1s INFO screen has four reconnect attempts, with three failures in attempt2
and two failures before the successful INFO in attempt4. That successful call
took836765us, not zero. Reduced timeout is not automatically saved wall time;
blindly selecting500ms could expire a call that succeeded here. The reusable
`Tools/ota/p34_reconnect_review.py` accepts control/current trial paths, requires
closed verified original reports and a single INFO-timeout configuration axis,
and keeps public/internal/native timing separate. Eight host tests passed under
`.cache/p34-info-timeout/review-tests-001`, including actual snapshot and negative
cases for changed inputs, late/missing/duplicate samples and unsupported timeout.

LINK-NEXT-03 finite observation plan: after all INFO-TIMEOUT-01 owners close
normally, use the existing `p34_link_status.py` read-only inventory, followed by
one `p34_current_hci_export.py` report under standing LINK-NEXT-02 authorization.
Sole operator remains Codex root; same phone10ADA4197U001CK,private ADB5062,
same APK and retained confirmed30269/Boot. Host outputs stay below
`.cache/p34-info-timeout/{link-status,hci-export-001,hci-correlation-001,hci-queue-001,post-hci}`.
Phone output remains `/data/user_de/0/com.android.shell/files/bugreports` with
ordinary report sidecars; preserve every prior report and retain only Bluetooth
members on host. Status bounds600s,export supervisor1800s,report command900s,
USB1500s; existing source-bound34-test exporter receipt is reused only if its
full source list still matches. Do not generate again on an uncertain outcome.
Correlate exact current package and first target INFO using the tested rotation
reader, then verify the post-report inventory. This performs no OTA,reset,flash,
APK install,data clear,automatic UI tap or report deletion. Diagnose remaining
INFO/connection scheduling and DATA pacing before choosing another hardware cell.

INFO-TIMEOUT-01 final closure: all three owners exited0 normally by20:47:32Z.
Strict report `.cache/p34-info-timeout/trial/analysis/1791060142941266400/result.json`
is FULL_INSTALL_VERIFIED,SHAcb3f6e9bc6c9f429fc872d58ca68346d1d8485296b2993d283211df35ac00678.
The reusable review's first invocation rejected the legal repeated startup/BEGIN
configuration records; no review output or device operation occurred. It now
reuses the existing experiment_record consistency parser, which rejects
conflicting repetitions. The next negative test initially expected the wrong
exception type; corrected to the shared CaptureError. Preserve attempt001 and
test001/002; ten tests including both closed trials passed in review-tests-003.
Final review SHA b1e6f80700ee664c57210ccd092dafca305a2271f6fb026aad69b59f8f2ae3cb.
Native full/backup costs5847/5786 MCU ticks; Boot-residency bracket6.143050..9.383935s.
Transient native confirmation sample is absent; separate complete raw readback
above supplies actual final confirmation, not a fabricated transient sample.

LINK-NEXT-03 completed: status/export/post-inventory owners all closed normally.
One report04-49-19,20447141B,SHA1caef2aa27bf88772d76dd06ffcb730bc4ed9ea59b46816f855045032da3335d,
was created in the authorized phone report directory; only Bluetooth originals
are on host. All five previous ZIP names/sizes remain; no deletion,whole-host
report,upload,APK install or additional OTA. The exporter took228.558s.

Current rotations also contain the previous OTA. The original correlator
correctly refused the foreign BEGIN rather than silently assigning it to this
package. Its reusable range selector now starts at the exact-package connection
event when earlier upgrades exist, retains unchanged packet bytes through first
target INFO, and reruns the original strict DATA/ACK/CRC/old+new identity checks.
Earlier/later records stay in full originals and the joined file. Four tests
include the previous single-upgrade capture, current two-upgrade capture,
invalid rotations and package corruption; the unbounded mixed range still fails.
Failure receipt is hci-correlation-attempt-001.json; no report was regenerated.

Joined6704873B SHA41395ee185160ef371657d53b8b2244006dde37d9d3ea885f9773ce2139f4ffb;
range614405B SHAc2874efeb67db7d3164822d5e67743de30193a670364c4b3c8b49e4c2dd532bc
maps original records22703..26468 with derived-record offset22702. Correlation
SHAc6970e68a4493c844bb4cc3e6aa6511999f5e1acd6edf99438cb8b945a373c6a
verifies2293 DATA/ACK frames,1375 chunks,15ms connection interval,251-octet DLE,
explicit Tx/Rx2M and no DATA-phase parameter change. HCI transfer17.734877s,
END-to-target20.560650s; vendor wall encoding is not synchronized with App/host.
Feeding10.439409s,durable tails6.155049s,including4.669075s after controller
completion reports. Outstanding-report feeding time9.199857s,empty1.239552s,
peak13. These report intervals still do not establish exact air events or a full
Android buffer, and they do not predict50KB/s from a baud or batch change.

In that HCI range, the next valid connection begins at END+3.575041s. INFO seq4/5/6
are sent at5.091247/6.603743/8.118375s without replies. Android issues a local
disconnect at10.813881s (completion10.832309s); next connection starts15.187679s.
Its INFO seq7/8/9 start16.700114/18.216265/19.731907s; seq9 returns target identity
at20.560650s. Source retryInfoOnCurrentLink currently permits only3 attempts.
Preserving a still-current binding longer is therefore a bounded candidate,
not proof that all4.37s of reconnection overlaps can be removed from total time.

INFO-RETRY-01 development started, no new device mutation: exclusive project-local
source `.cache/p34-info-retry/src`,branch `dev/flutter/p3-4-info-retry-20261004`,
based on installed APK commitb85f50aae66f51895aa4f9bbb9a82732138bae3b. Canonical
root governance1e1f92f2254bf826b44d9807c5522051991906e8 was consumed. Seven scoped
files add schema9 `rebootInfoMaxAttempts`1..12 with explicit link reuse, preserving
schemas1..8/default3, all deadlines,cancellation,link-generation and identity guards.
Tests cover bounded attempts, late responses, configuration rejection and full
service fifth-query behavior on one versus two bindings. No sender/Boot/firmware
change is included. WIP b6e6e32df1fdf5418aa94ba6ac858256e8ef9066 was committed/pushed
under standing development-only authority; root index and unrelated files were
preserved. Checks-only run37154109221 is active on Ubuntu and Windows:
https://github.com/Eitan-S-23/E-Track/actions/runs/37154109221 .
APK/EXE builds,installation and measured retry comparison are NOT_RUN. No new
speed milestone was committed; checkpoint389b03f remains the last measured one.

INFO-RETRY-01 development verification update: push run37154109221 completed
successfully on both hosts. Original logs are archived under
`.cache/p34-info-retry/ci/37154109221`: Linux terminal668 passed/16 skipped,
Windows651 passed/33 skipped; both analyze/test commands returned0. These counts
come from each original tests.log terminal, not the absent console_summary key.
The sole explicit APK dispatch37154382710 also completed successfully on both
hosts by21:23:59Z; collection/actual signer verification is pending at this entry.
https://github.com/Eitan-S-23/E-Track/actions/runs/37154382710 .
No local Flutter/Gradle build,EXE build,release,merge or main push was performed.

Finite upcoming device matrix: install the one verified same-package/fixed-signer
APK from b6e6e32, retaining the original completed30269 capture/config/permissions;
then screen exactly two sequential legal header successors with the same APK:
control30269->30270,INFO1s,cadence500ms,maxAttempts3; extended30270->30271,
identical settings except maxAttempts12. Each target must be fully read back and
confirmed before the following cell. Same Boot,executable,baud921600,window28,
batch12,negotiated244-byte payload,without-response,GATT reuse,prefer2m,high
priority and paused scanning. These different legal headers/packages are not
matched-package A/B. No downgrade,Boot replacement,BCB edit,automatic UI tap,
data clear,uninstall or blind failed/successful replay is permitted.

Both immutable packages are already prepared in `.cache/p34-info-retry/assets`:
control293394B SHA8bbe67b5042fad8807e0f0d3bf936b8fd3a03d29f0c36059ee88aca598e4926a,
target617324B SHA99dadf089ba23008421e4ef0ff56b44d7fc37da0466b67b58a2943c4dd09d763;
extended293472B SHAab823e7b8eff746aaf437d202a7c65fbbe42cdd2ca5985b8553a9d8f6e16503b,
target617324B SHAc67966a1fde307bdd35687eb4ab89bd9d9ea0692a541526219ac86aaec6536a3.
Each native decode is byte-identical and four CRC/truncation/same-version/flags
negative packages are rejected before preparation. No compiler or device ran.

The reusable `p34_verified_install.py` takes explicit closed trial/APK/commit/out
bindings and reuses the established same-signer installer. Four guard tests pass
under install-tests-002; earlier self-tests remain preserved. It verifies exact
source/CI/native regression reports and actual APK signer, prior App hash and
current completed snapshot before any stop/install. Sleep or missing identity
cannot trigger installation. One600s owned window includes a180s install bound,
original-byte/config/permission readback and graceful USB closure. If the phone
is asleep, request only actual wake/unlock after the APK is ready; do not reinstall
or rerun an uncertain attempt. Installation output and all controlled host paths
stay under `.cache/p34-info-retry/install-001`; no MCU reset/flash is part of it.
Archive only a verified inactive completed capture when needed for the next
recording slot, preserving its original bytes; prepare query/package/native/App
collectors before inviting a new download/Start. No new OTA has yet been run.

INFO-RETRY-01 APK ready: run37154382710 both hosts PASS; Linux debug APK PASS,
Windows EXE NOT_REQUESTED. Original APK-run test logs show Linux668 passed/16
skipped and Windows651 passed/33 skipped. Collected131659530B APK SHA
53434b036d5879166ccd1c9e28bc919a0d61c74784230fd8591756cd089c0f3c,
actual fixed signer9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579,
application IDcom.wen.gaia.gaia.p34probe,commitb6e6e32df1fdf5418aa94ba6ac858256e8ef9066.
Both host reports and native lifecycle evidence were hash-bound during collection.

Installation precheck ran once at21:28:35Z under supervisor1860/worker2924,
out `.cache/p34-info-retry/install-001`. It verified the existing old APK, then
observed the phone asleep. At21:28:48Z it returned
`NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED`; USB closed gracefully and no App stop,
install,uninstall,data clear or firmware operation was attempted. The phone
still has original APK aef3d433a54da801b594f5ddce64b5bdf80f0c0f1c2016a42f1188e04ae96934
and confirmed30269. User must now wake/unlock the phone and keep USB connected;
do not ask for the already-granted authorization or ask them to download/install
the APK manually. Do not use the closed old firmware tunnel or invite OTA Start.
After a readiness reply, first verify this precheck's final owner/USB closures
and absence of install-intent/stop-intent, then use a fresh scoped installer out
with the same exact APK/trial/commit/tests bindings. This is resuming an unspent
installation after an observed sleep prerequisite, not retrying an uncertain
installation. Preserve install-001. A new live OTA controller and its recorder
capacity/admission are still required before either prepared matrix cell starts.

INFO-RETRY-01 installation continuation, 2026-10-04: install-002 stopped at
get-serialno because the phone was absent; install-003 verified the old APK but
found the phone asleep. Neither performed an install. Their receipts and normal
USB closures remain preserved. After actual readiness, install-004 completed at
06:17:23Z with FIXED_SIGNER_BATCH_UPDATE_VERIFIED. The installed APK SHA is
53434b036d5879166ccd1c9e28bc919a0d61c74784230fd8591756cd089c0f3c;
snapshot/config/permissions were byte/state verified unchanged. No uninstall,
data clear, App launch or OTA occurred. Its owner and private USB closed normally,
with the existing ADB key unchanged.

The new Tools/ota/p34_info_retry_trial.py reuses the existing bounded collectors,
adds exact schema9/attempt observation checks and admits extended only after a
real FULL_INSTALL_VERIFIED control predecessor. Five host tests passed in
.cache/p34-info-retry/trial-tests-002; initial test output is also preserved.
Only served metadata uses the required -full.etu suffix; immutable package bytes
and target identity are unchanged. Full offline context verification is pending.

archive-control completed at06:24:41Z: inactive completed capture
1791054496947888-3a837d37e40cd24a8410dddc was backed up byte-for-byte under the
project and moved to the App's existing archived-observations directory. No
deletion; current30269 capture1791059072852634-5cabcb857c855624bf58ab99 and its
runtime configuration were verified unchanged. Seven active captures remain;
App stopped and private USB closed. No new throughput result or milestone is
claimed. Next: finish offline binding check, then source-pin one control cell
and its live network/App/native collectors before asking for download/Start.

Control offline check completed: INFO_RETRY_OFFLINE_VERIFIED,262 source bindings.
Coordinator started06:27:50Z (supervisor8660/worker10784,6000s); network ready and
s04 owner started06:35:38Z (supervisor6504/worker7336,3900s). Source-pinned live
helpers must remain unchanged. At06:44:18Z cells/s04/status.json reported
READY_FOR_FULL_INSTALL_START: target30270,293394B,baud921600/window28,PID10697.
The original query and exact downloaded package were admitted before Start.
Capture1791096163996788-2af8c4882a547a1b851771ed was healthy/lost0/error null,
starts0/ends0 at06:44:34Z. User was asked only to click Start and keep foreground;
do not launch a second cell, reinstall, reset or expire/recreate the live endpoint.
Current owner outputs: .cache/p34-info-retry/trials/control; collect original
finished snapshot and raw App/Boot confirmation, then close/analyze the same cell.

INFO-RETRY-01 control completed, 2026-10-04: original automatic analysis is
FULL_INSTALL_VERIFIED at .cache/p34-info-retry/trials/control/analysis/
1791096622313902400/result.json, SHA256
43e2fef40c2f39c8b883ec8a14a8f433138bf0caa7bad48af4192e1d4de0f741.
All three owners exited0 without forced termination by06:55:29Z. Full raw App
617324B matches99dadf089ba23008421e4ef0ff56b44d7fc37da0466b67b58a2943c4dd09d763;
whole Boot65536B remainsa63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
BCB4,confirm_done/state_snapped/sd_ready1; no reset/halt/flash in readback.
Original capture completed once,8960 records/8957 producer lines,lost0,error null.

Public OTA_MONO timing: transfer17.036323s,17.221673949 decimal KB/s;
END-to-identity27.840474s,total44.876797s. Neither user target met. Six reconnect
attempts: attempts2 and4 had valid bindings but exhausted three INFO calls each;
attempt6 succeeded with857445us INFO. This is the default3 control, not evidence
that extended12 improves speed. No new measured milestone commit is warranted.

Tools/ota/p34_info_retry_results.py summarizes either closed arm and reuses an
existing strict report instead of regenerating it. Four tests passed in
tests/ota/test_p34_info_retry_results.py. Control summary is
.cache/p34-info-retry/results/control.json. An initial read-only quick metric
call to the historical batch3 helper rejected this batch12 snapshot; original
bytes were preserved and public metrics use p34_phy_review.public_metrics.
The live collector already performs strict analyze_install automatically.

Extended preparation: archive-extended completed normally06:58:39Z, preserving
and moving only inactive30269 capture1791059072852634-5cabcb857c855624bf58ab99;
current30270 capture1791096163996788-2af8c4882a547a1b851771ed and config unchanged.
Seven active recordings remain. App stopped, USB closed, no OTA/reinstall/delete.
Extended offline check is in progress. Next is the already-planned30270->30271
header-only cell with maxAttempts12 using the SAME installed APK and Boot.

Control internal-timing qualification: native_trace/result.json is TRACE_INCOMPLETE,
reader_closed=true, with "unknown App executable/header; refuse stale addresses".
Its frozen END profile and receiver RTT are retained, but native phase analysis
correctly reports EVIDENCE_GAP_NO_REPLAY. Do not convert partial trace into a
complete phase profile. Separate final whole-App/Boot readback and App identity
prove successful installation; public OTA_MONO timing remains available. No
repeat of the successful control is authorized merely to recover native timing.

Extended offline bindings passed (262 sources). Coordinator launched07:03:13Z,
supervisor1860/worker13376,6000s, under trials/extended. Same source-pinned adapter
and APK; do not edit active helpers or start another competing device operation.

Extended network ready; s04 owner started07:11:06Z (supervisor13516/worker2784,
3900s). At07:18:07Z status APP_LAUNCHED_CONNECT_AND_DOWNLOAD; original recorder
1791098282927293-17cf3a77b37d5a9c55be5a35 is healthy/lost0/error null,starts0/ends0.
User asked to connect and download30271/3.2.71-p34p, NOT Start until exact package
and original query admission become READY_FOR_FULL_INSTALL_START. Keep this
existing owned cell; do not reinstall or launch a duplicate. Live outputs remain
under .cache/p34-info-retry/trials/extended. Control summary remains17.221674KB/s,
27.840474s installation/reconnect,44.876797s total, not a speed milestone.

INFO-RETRY-01 matrix complete, 2026-10-04: extended report
trials/extended/analysis/1791098839297706400/result.json is FULL_INSTALL_VERIFIED,
SHA256 b2e409734831701717bf33cf9f4ea45096bfc14d47d841172079e304e77cae91.
All three owners exited0 without forced termination by07:32:26Z. Retained30271
whole App617324B matchesc67966a1fde307bdd35687eb4ab89bd9d9ea0692a541526219ac86aaec6536a3;
whole Boot65536B unchanged, BCB4 and confirm_done/state_snapped/sd_ready1.
Original capture completed once,8957 records/8954 producer lines,lost0,error null.
Unlike control, the extended native reader returned TRACE_CLOSED without error.

Public OTA_MONO extended: transfer17.566441s,16.706400574 decimal KB/s;
END-to-identity20.995065s,total38.561506s. Relative to same-APK control:
installation/reconnect saved6.845409s, transfer added0.530118s, total saved6.315291s.
Two reconnect attempts rather than six; second valid binding succeeded at its
11th INFO call after10 timeouts. This supports retaining the bounded same-link
retry candidate, but both user targets remain unmet. The sequential packages
differ in legal headers/lengths; no matched-package A/B, repeatability, formal
acceptance or new historical speed best is claimed. No new milestone commit.

Machine summaries/comparison are .cache/p34-info-retry/results/{control,extended,
comparison}.json, preserving exact report inputs, same APK/Boot and sole retry
axis (apart from declared package/version/endpoint identities). Both planned
cells are complete; no third OTA is pending. Preserve current30271 and installed
APK53434b03. Do not reuse either closed endpoint, reinstall, or repeat a completed
upgrade to fill the control native-timing gap. Further transfer work must address
measured GATT feeding/durable waiting, not re-enable already-observed2M PHY or
claim that bridge batching alone removes Android backpressure.

## ACK-HOLD-01: Bounded Cross-Pump ACK Aggregation

User resumed optimization without unnecessary stops on2026-10-04. Root remains
sole device operator; writable root D:\github\my\E-Track. Same phone/target and
existing native-history exception apply; no new external host write scope.
Original control/extended accounting now lives in p34-info-retry/results/
{control,extended}-timing.json. Extended DATA GATT9.746290s (nested platform
9.493064s), last-chunk-to-durable6.728966s, other pre-last nonwrite0.805219s.
Native ACK write calls1324 cost1.800894s, including the retained1ms post-UART gap;
these overlap App timing and are not additive isolated physical costs.

Candidate Tools/ota/p34_timed_ack_batch.h preserves every ACK byte/FIFO order and
the existing12-frame/228-byte capacity. Ordinary successful nondurable-advancing
ACKs may persist across pump invocations. The oldest-byte2ms threshold is checked
at pump end; this is not a hard wall-time guarantee through scheduler stalls.
Durable advancement, control/error responses, capacity and inactive-session end
flush immediately. Overlay release drains first. Unexpected queued epoch changes
and uncertain UART writes latch failure without replay. BEGIN can acquire the
overlay inside a pump, so empty-queue epoch rebinding is explicit and tested.
UART stop-bit drain and1ms gap, protocol/CRC/seq/credit/durable semantics stay.

Isolated source .cache/p34-timed-ack/f was cloned from the exact built half-erase
manifest, not the unrelated dirty root sources. Product delta is HAL_Bluetooth.cpp
and new p34_timed_ack_batch.h only. Native test r1 passed, integration review then
found the intra-pump epoch issue; r2 adds that positive/negative boundary and
passes with0 warnings/errors. The GCC App-only build completed07:56:34Z with
0 errors,638 existing warnings,no new warnings, Boot not built. Raw candidate
617492B (+168B),SHA66f9cc4c7852b058b24f1b4fb39dbeb90e4cda21927dfd04e34427fdfb0c3692.
Build/source/test/artifact receipts are retained under .cache/p34-timed-ack.

Finite screen after offline admission, same installed APK53434b03/schema9:
bootstrap30271->30272 installs the new receiver; measure30272->30273 measures it.
Keep baud921600/window28,batch12,payload244,prefer2m,high priority,paused scan,
INFO1s/cadence500ms/maxAttempts12 and foreground unchanged. No APK installation,
Boot replacement, BCB edit, downgrade or automatic UI taps. Ordinary Boot
rollback/confirmation remains intact; retain the verified target on success.
On uncertain integrity/session state, stop dependent mutation and reconcile
original snapshots plus full readback before selecting any recovery. Current
known-good30271 App and unchanged whole Boot remain preserved in prior assets.
Bootstrap is not receiver-throughput evidence; do not skip it or claim speedup
from its receive path. Measurement has different legal package/header, not strict
matched-package A/B. Original frozen evidence is never rewritten.

Both packages decoded byte-identically and passed four negative guards by
07:58:41Z; native asset worker closed0. Bootstrap293553B SHA
b6b884fa13fcd37b4f5961c811e36455f20499266c79687924a04ac15142857e,
target190c81ed673b51594c6b3d81c17981a8fa6e32dfa8fd97104dd6f55e0c0b57d5.
Measure293632B SHAcd37f0c88459f77a709bb3539b51febe7a265bac50d1d9797489284b62d279a3,
target236b98b44d6ed642fd75ab1d9661b3e02e405e0a4f21269fbc24c0167fee3d02.
Tools/ota/p34_timed_ack_trial.py reuses the bounded existing native/App/network
route;4 host tests passed. Complete original snapshot/full App+Boot/confirmation
and normal owner closures remain mandatory. Archive only verified inactive
captures with byte backups. Runtime bounds remain6000s coordinator/3900s cell,
with ordinary apply/readback/cleanup allowance and no blind replay. Full offline
binding check is in progress; no new device operation has occurred at this entry.

ACK-HOLD-01 admission update: complete bootstrap offline binding check passed
with275 source inputs. archive-bootstrap completed08:03:37Z, backing up and
moving only inactive control30270 capture1791096163996788-2af8c4882a547a1b851771ed.
Current30271 capture1791098282927293-17cf3a77b37d5a9c55be5a35 and runtime config
unchanged; seven active captures remain; App stopped; archive and USB closed0.
Bootstrap coordinator launched08:07:07Z,supervisor7300/worker15364,6000s,
out .cache/p34-timed-ack/trials/bootstrap. No new firmware transfer yet. Keep
these source-pinned helpers unchanged and use this owned operation, not a replay.

ACK-HOLD-01 bootstrap ready: network ready and s04 launched08:14:40Z,
supervisor2816/worker7980,3900s. At08:23:07Z status is
READY_FOR_FULL_INSTALL_START,target30272,293553B,PID28992. Exact downloaded
package and original query were admitted before Start. Recorder
1791102097485354-1f9c47beb3559192a25c7974 is healthy/lost0/error null,starts0/ends0.
User was asked to click Start and keep foreground/USB. The live owner remains
.cache/p34-timed-ack/trials/bootstrap; do not start a duplicate, reinstall APK,
edit pinned helpers, or reuse a closed prior endpoint. After this install,
verify whole App/Boot/confirmation and original snapshot before the30273 measure.

ACK-HOLD-01 bootstrap completed: automatic report
trials/bootstrap/analysis/1791102836905429400/result.json is FULL_INSTALL_VERIFIED,
SHA09ce03cf8a5a04575cfa46a92eab023911a147f4a7ebc96bc9726eea20d0f88b.
All three owners exited0 without forced termination by08:39:08Z. Full App617492B
matches190c81ed673b51594c6b3d81c17981a8fa6e32dfa8fd97104dd6f55e0c0b57d5;
whole Boot unchanged, BCB4,confirm_done/state_snapped/sd_ready1. Original capture
completed once,9037 records/9034 producer lines,lost0,error null. No replay/reset.

Bootstrap public timing (old receiver, NOT timed-ACK benefit): transfer16.811246s,
17.461703909KB/s, installation/reconnect36.860075s,total53.671321s. Public and
batch accounting are saved in results/bootstrap-public.json and
results/bootstrap-timing.json. Probe round36.782761s: first no-binding2.011503s,
second abandoned at20.001830s with11 failed INFO calls, third completed13.740903s
with9 calls/8 failures. This is additional evidence against treating extended
INFO retry as a stable speed guarantee. Preserve it; do not hide it behind the
earlier21s sample. Native apply/backup5942/5965 ticks are not wall durations.

Measure offline bindings passed275 inputs. archive-measure completed08:41:28Z,
moving only inactive30271 capture1791098282927293-17cf3a77b37d5a9c55be5a35 after
verified byte backup. Current30272 capture/config unchanged,7 active recordings,
App stopped, USB/owner closed normally. The existing declared30272->30273
measurement launch is in preparation; keep same APK/Boot/radio/INFO settings to
avoid mixing the new receiver axis with reconnect-policy changes.

ACK-HOLD-01 measure owner started08:46:48Z,supervisor9932/worker9744,6000s;
network ready and s04 started08:54:17Z under the same source-pinned adapter.
At09:03:23Z status READY_FOR_FULL_INSTALL_START,target30273,293632B,PID31616.
Original query and exact package admission completed before Start. Recorder
1791104477362678-2d2a92e072f730b9699a8237 was healthy/lost0/error null,starts0/ends0
at09:04:50Z. User asked to click Start and remain foreground/USB. Live output is
.cache/p34-timed-ack/trials/measure. Do not duplicate, reinstall, reset, or edit
running inputs. After completion collect original snapshot and full target/Boot
readback, compare transfer and actual ACK UART calls with the old-receiver
bootstrap and prior30271. Pending measure is the second/final declared cell.

### ACK-HOLD-01 Closed Result And HCI Recovery (2026-10-04)

Both declared cells completed. Retained target30273, raw App617492B SHA256
236b98b44d6ed642fd75ab1d9661b3e02e405e0a4f21269fbc24c0167fee3d02;
whole Boot65536B unchanged SHA256
a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
Full readback, BCB4, confirm_done/state_snapped/sd_ready=1 verified.
Measure report: .cache/p34-timed-ack/trials/measure/analysis/1791105012204966300/result.json,
SHA256413a999388d221351667266122f1b3bd50b96c8576b1ae4e2efd3364d50ccc5a.
Original recorder8960 records/8957 producer lines, lost0/error null.
Trial owners closed normally09:15:17Z. No next OTA is pending.

Public App-clock comparison (decimal KB/s):

| Receiver | Transfer seconds | KB/s | END to identity seconds | Total seconds |
| --- | ---: | ---: | ---: | ---: |
| Old/bootstrap30272 | 16.811246 | 17.461704 | 36.860075 | 53.671321 |
| Timed ACK/measure30273 | 17.487465 | 16.790999 | 20.438290 | 37.925755 |

ACK UART calls1438->1030, unchanged43625 bytes, measured UART time
1.915343972->1.506126990s. This saved408 calls/0.409217s but transfer worsened
0.676219s. No effective transfer improvement, repeatability claim or milestone
commit. Reconnect variation dominates total-time differences; neither target met.
Measure GATT10.074859s (platform9.828983s nested), before-last nonwrite0.665194s,
last-chunk-to-durable6.507385s. Native staging program0.487973s/erase1.604549s
overlap App timing and must not be added. Native RX/UART/parser clean.

HCI export001 generated one report successfully but the host parser rejected
valid trailing PROGRESS after OK. Preserve that original failure. Export parser
now accepts one safe OK followed only by valid PROGRESS; duplicate OK, FAIL,
BEGIN or junk remain rejected. Retrieval-only helper reuses the same report,
never generates another. Source/test originals preserved in hci-fix/source-before;
38 tests passed in .cache/p34-timed-ack/hci-fix/tests-001/result.json.
Prior source-pinned exporter test proof is stale and must not admit new generation.

.cache/p34-timed-ack/hci-retrieve-001 extracted two untruncated original snoops;
six older report names/sizes unchanged, no phone deletion or whole-report host
copy/upload. Retrieval closed normally09:32:44Z; all device workers closed.
.cache/p34-timed-ack/hci-measure-001/result.json correlates2294 DATA/ACK and
1371 ATT chunks. Actual bidirectional2M/DLE251 and15ms interval during DATA;
no connection-parameter changes during DATA. HCI END->identity20.342773s uses
its own clock, not interchangeable with App timing.

Offline queue.json under the same correlation directory revalidated original
bindings: feeding9.985125s, reported-outstanding9.039436s, empty0.945689s,
peak11 packets. Completion-report occupancy is neither airtime nor proof of
controller fullness; empty time alone does not establish Flutter overhead.
This offline analysis performed zero device operations.

Next owner remains Codex root. Do not repeat ACK-hold tuning or blindly batch
Android writes. Investigate durable-tail/link scheduling and cold identity cost.
Source inspection confirms cold identity validates normalized image SHA then
computes raw SHA; these are distinct domains, not removable duplicate checks.
Any proposed hash acceleration must preserve both full validations, failure
behavior and identity binding, and first demonstrate measurable target cost.
No APK reinstall, Boot replacement or new device experiment was made by this
offline continuation. Its outputs are project-local queue.json and this note;
prior recovered outputs remain under .cache/p34-timed-ack. No known unauthorized
external writes; unrelated dirty root files remain untouched.

### SHA-O2-01 And Durable-Tail Screening (2026-10-04)

Offline tail classifier Tools/ota/p34_hci_tail.py revalidates original HCI,
package, report and archive before grouping payload boundaries. Five pure tests
passed in .cache/p34-timed-ack/tail-tests-001. Current HCI tail.json reports
four64KiB boundaries1.139760s,67 ordinary full blocks5.055024s, one partial
block0.069273s. Median boundary/ordinary tails286.813/77.728ms. All tails total
6.264057s: controller completion reports split1.570982s before/4.693075s after.
These are not isolated Flash measurements; grouping denotes payload offsets,
not observed erase commands. Ordinary blocks dominate, so another large-erase
change alone cannot plausibly close the50KB/s gap.

Code inspection found App SHA compiled with-Oz. A bounded independent local
screen compares unchanged source with-O2, not another digest or skipped checks.
Tools/ota/p34_sha_screen.py reuses exact ARM App flags from the measured Ninja
entry. Each native optimization passed208 hashlib-oracle vectors including
empty/padding/block boundaries,617492B, unaligned input and8 streaming sizes;
final context zeroing checked. Four oracle rejection tests passed. Results:
.cache/p34-sha-screen/r1/result.json and parser-tests-001/result.json.
ARM text904->968B, transform stack328->344B; no MCU speed has been measured.

Prepare an isolated App candidate in .cache/p34-sha-candidate, copied from the
verified timed-ACK source manifest. The only source delta is an App-target-only
SHA-O2 CMake property; keep Boot and all other compilation unchanged. Full App
build and generated App/Boot SHA command checks precede package preparation.
This is an installation/identity-latency screening hypothesis, not a50KB/s fix.

Finite next matrix: bootstrap30273->30274, then measurement30274->30275 using
the same executable with successor header. Same installed schema9 APK/signer,
Boot,921600baud,window28,batch12,244B writes,2M preference, high priority,
scan pause,INFO1000ms/retry12/cadence500ms. Codex root is sole device owner,
under standing P3-4 authority and D:/github/my/E-Track write boundary.
Build/package/native positive+four-negative guards and full collector preflight
must pass before device mutation. Preserve30273 as current until actual OTA.
No APK reinstall, Boot replacement, auto UI taps, data clear or blind replay.
Archive only an inactive verified recording with host backup/no-delete move,
protecting the current capture. Inherited6000s coordinator and bounded network,
USB/native collectors retain ordinary apply/readback/closure allowances.
On integrity/identity/clock uncertainty stop dependent mutations and reconcile
original evidence. Retain the latest fully verified target, never App-only
downgrade across BCB changes. Compare App END-to-identity and native apply costs,
not mixed clocks; no gain claim from host tests or object size. User action is
needed only for the actual in-App download/Start after observation is ready.

SHA-O2-01 preparation completed: App617588B (+96B), raw build SHA256
65cec892c2e93db3aa5d9d7288cb9bc834cdee648c824e6cd96b788ba091ce2e.
Build0 errors/638 existing warnings/no new warnings; generated Boot SHA flags
remain-Oz, App SHA alone adds-O2. No Boot artifact built. Both legal package
native decode positives and4 negatives each passed;4 trial adapter tests passed.
Bootstrap30274:293642B package SHA256
10530a4a029fc80a0f842de0f8f986df581716797cae6edf3f59e59b3a624969,
target raw SHA25622a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002.
Measure30275:293666B package SHA256
657b5c843e377e97d0886b5fe99909eb654ad4385eb27645bca3a2c2bb192976,
target raw SHA2564d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6.
Host inputs/results are in .cache/p34-sha-screen and .cache/p34-sha-candidate;
canonical reusable entries Tools/ota/p34_sha_{screen,candidate,assets,trial}.py.
Installed APK remains b6e6e32df1fdf5418aa94ba6ac858256e8ef9066,
SHA53434b036d5879166ccd1c9e28bc919a0d61c74784230fd8591756cd089c0f3c;
fixed signer9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579.
Phone10ADA4197U001CK/BLEE3:49:E1:14:D6:CB; initial30273/Boot digest as above.
Before bootstrap, archive only the inactive30272 recording with the existing
verified no-delete route; current30273 recording and settings stay protected.

SHA-O2-01 bootstrap execution:288-binding offline check passed. Archive-bootstrap
closed normally10:08:16Z, moving only inactive30272 capture
1791102097485354-1f9c47beb3559192a25c7974 after byte-verified host backup;
current30273 capture/config unchanged,7 active recordings, no deletion/OTA.
Coordinator launched10:10:39Z (supervisor6140/worker5384,6000s); network ready
10:18:29Z and s04 launched10:18:31Z. At10:25:44Z status is
APP_LAUNCHED_CONNECT_AND_DOWNLOAD,existing APK process26883. Native trace route
is active under cells/s04/native-trace. User asked to connect/download30274,
not Start yet. No OTA has been requested in this cell. Wait for original query,
download and healthy producer admission before inviting Start. Preserve this
source-pinned runtime; no duplicate launch, reset, replay or APK installation.
Runtime/evidence root:.cache/p34-sha-candidate/trials/bootstrap.

Continuation audit: manual code/tests and this note are project-local; copied
candidate, compiler/stack/temp/cache products, assets and capture outputs remain
under .cache/p34-sha-{screen,candidate}; tail evidence under p34-timed-ack.
Pre-device audit found no reparse points in these new output trees; adbkey and
authorized JLinkDLL.ini hashes matched their prior anchors. No known unauthorized
external writes. Active finite device workers intentionally remain open for the
required user connect/download action, not claimed closed or complete.

SHA-O2-01 bootstrap admitted10:28:54Z: READY_FOR_FULL_INSTALL_START,
PID26883,target30274,293642B downloaded package matches
10530a4a029fc80a0f842de0f8f986df581716797cae6edf3f59e59b3a624969.
Original query checkpoint contains2 successful queries and verified start inputs.
At10:31:02Z recorder1791109543492381-a4d3bfe9d005aecc87088458 remains
healthy,16 records/15 producer lines,lost0/error null,starts0/ends0. Existing
s04 owner live with ample remaining deadline. User now asked to tap Start once,
remain foreground/USB and allow ordinary reboot verification. No new worker,
download, APK install or reset was issued by this admission check. Only this
project-local note was edited; existing finite collectors remain active.

SHA-O2-01 bootstrap completed and owners closed normally10:42:39Z. Original
report analysis/1791110235456759200/result.json under trials/bootstrap has
SHA256cbe1150ec0203e8e2130dbc705362b0ff47dfc80b31f9a6d38f316ec1fb649ff.
Retained30274 App617588B SHA22a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002;
whole Boot unchanged,BCB4,confirm_done/state_snapped/sd_ready=1. The correct
post-upgrade evidence is installed-mcu/closure.json; mcu/closure.json is the
pre-transfer30273 checkpoint, not the new target. Recorder8967 records/8964
producer lines,starts1/ends1,completed,lost0/error null.

Strict summary in results/bootstrap-public.json: transfer16.821642s,
17.456203KB/s,END->identity36.426757s,total53.248399s; both objectives unmet.
Reconnect4 attempts; second binding12 INFO failures, fourth5 calls/4 failures.
Do not attribute this spread entirely to SHA. Bootstrap is received/applied by
the older program; the declared30274->30275 same-executable cell remains the
candidate installation measurement. No milestone commit or stable speed claim.
App timing in bootstrap-timing.json:GATT10.352266s (platform10.112919s nested),
before-last nonwrite0.557706s,tail5.678069s. Host readback/analysis time is not
added to OTA elapsed time. Reusable result adapter Tools/ota/p34_sha_results.py
uses the existing strict analyzers; report and original evidence are unchanged.
Next: offline measure admission, archive inactive30273 only while protecting
30274, then launch the already-declared second/final cell. No new APK or Boot.

SHA-O2-01 measure offline check passed288 bindings. Archive-measure completed
with current30274 snapshot/config unchanged,old30273 moved only after verified
host backup,no deletion,USB/owner closed normally. Coordinator started10:53:52Z,
supervisor3920/worker8368,6000s. Network ready11:02:50Z,s04 started11:02:52Z.
At11:10:06Z status APP_LAUNCHED_CONNECT_AND_DOWNLOAD,target30275. User asked
to connect/download3.2.75-p34p,not Start yet. Await original query/download/healthy
producer admission before inviting Start. This is the second/final declared
SHA-O2-01 cell; do not duplicate, reinstall, reset or edit pinned inputs.
Active evidence root:.cache/p34-sha-candidate/trials/measure. Host outputs of
this continuation are the project-local SHA result adapter, bootstrap summaries,
archive-measure and measure runtime plus this note. Original bootstrap report
was reused unchanged. Finite measure collectors intentionally remain active for
the user download action; no new speed claim and no commit.

SHA-O2-01 measure admitted11:11:37Z:READY_FOR_FULL_INSTALL_START,target30275,
PID6001,293666B package SHA657b5c843e377e97d0886b5fe99909eb654ad4385eb27645bca3a2c2bb192976.
Original query/start-input admission passed. At11:12:40Z recorder
1791112203004255-d72cb83d6d8ace1100542bab is healthy,30 records/29 producer
lines,lost0/error null,starts0/ends0. Existing s04 owner live with ample deadline.
User asked to tap Start once and remain foreground/USB through ordinary reboot
verification. No repeated download/install/reset or new collector was issued.
Only this project-local note was edited during admission; finite owners remain
active for the declared measurement cell.

SHA-O2-01 completed: measure report
trials/measure/analysis/1791112692393641600/result.json under the candidate root,
SHA256ddfe75d5b7602d2b4e6884f3bb968690b349ed70b88551aa58b3afe0f5a0d567.
All coordinator/network/s04 owners closed normally by11:23:15Z. Retained30275
App617588B SHA4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6;
whole Boot unchanged,BCB4,confirm_done/state_snapped/sd_ready=1. Original recorder
8982 records/8979 producer lines,starts1/ends1,completed,lost0/error null.
No pending OTA or live owned device worker remains in this matrix.

Final public timing:16.740038s transfer,17.542732 decimal KB/s,
20.361587s END-to-identity,37.101625s total. Both goals remain unmet.
Reconnect required2 attempts,successful second binding11 INFO calls/10 failures.
App GATT10.203518s(platform9.944115s nested),nonwrite0.629368s,
last-chunk-to-durable5.753145s;50KB/s budget5.873320s. These spans do not identify
an isolated radio/MCU cost and must not be added to native timing.

Comparison output results/comparison.json uses header-only30272->30273 as
control,not the changed-executable30273->30274 bootstrap. Numerical savings are
transfer0.747427s and installation/reconnect0.076703s. Sequential legal packages
are not identical-package A/B or repeatability evidence. Native activation
apply/backup ticks control5749/5752,bootstrap5800/5753,measure5755/5777 do not
show useful SHA-driven improvement; these are not calibrated wall milliseconds.
Do not call the36.43->20.36s bootstrap/measure difference an optimization gain.
SHA-O2-01 is closed with no proven causal/stable speedup. Do not add blind O2
repeats or a speed-milestone commit. Retain30275; no downgrade or Boot change.

The reusable result adapter now compares closed, version-bound, policy-bound,
same-Boot evidence and excludes bootstrap from gain calculation. Four comparison
tests passed in comparison-tests-001 (live owner, wrong version, changed Boot
rejected). Results remain in results/{measure-public,measure-timing,comparison}.json.
Next diagnostic focus is supported link scheduling and durable-tail attribution,
not further SHA/ACK micro-tuning. Any new hardware/API/protocol hypothesis needs
specific supporting evidence and a bounded plan before another OTA.
This closeout changed only project-local result tooling/tests, generated reports
and this note. Original trial evidence remains unchanged; all device workers
are closed and no installation/reset/replay was added to recover evidence.

OFFLINE-PLAN-01: user requested evidence-based feasibility instead of more OTA
trials. Completed analysis is P3-4-speed-feasibility-2026-10-04.md; reproducible
report .cache/p34-feasibility/analysis.json, six host analysis tests passed.
No device/CI/network actions or product changes in this investigation.
Important correction to the earlier variability discussion: installed Boot
skips identical blocks; exact known-byte comparison gives146 changed blocks in
the bootstrap versus1 changed/149 known-identical/1 unknown-padding block in
each header-only control/measure. Bootstrap Boot residence alone22.465650..
24.787154s differs materially from header-only6.719949..8.836719s. Never explain
the entire36s versus20s difference as retry policy or SHA behavior.

Next preferred installation candidate is host-only grouped Boot progress
checkpoints:151 copy-path EEPROM commits->10 with group16,nominal avoided page
write cycle time~5.64s (not measured savings). Requires recovery model and
contract review; no new Boot replacement authorized or performed here.
Transport math: removing all latest durable tail with other costs fixed gives
26.74KB/s; halving GATT alone25.24KB/s; both idealized changes49.93KB/s. These are
counterfactuals,not predictions or hardware limits. v1 forbids cross-block
prefetch; true two-block pipeline needs negotiated credit/lifecycle changes.
Within-block early erase/page programming is a smaller compatible hypothesis,
also unimplemented. First establish sustained link service and validate Boot
checkpoint crash recovery,not more SHA/ACK tweaks or generic full-upgrade trials.
All newly selected outputs remain project-local; original captures/report
bundles and device30275 state are untouched. No commit or performance claim.

BOOT-CP-01 host model completed; see P3-4-boot-checkpoint-model-2026-10-04.md.
Real Boot state machine/BCB code exercised with isolated checkpoint predicate;
production source/defaults and device Boot unchanged. r3 result at
.cache/p34-boot-checkpoint/r3/result.json: original/default-off103 checks each,
byte-identical native executables;151-block group1/4/16 copy commits151/38/10.
Group4:3361 scenarios,3091 exhaustive cuts,max rework4 blocks. Group16:1793
scenarios,1691 cuts,max rework16 blocks. Group1 large-image/control36 scenarios;
do not claim its deliberately omitted exhaustive151-block sweep was executed.
Combined4782 cuts cover changed group policies, EEPROM before/half/after page,
partial Flash erase/program and original Boot boundaries. Uncertain successful
EEPROM writes, source invalidation, seq wrap, rollback and off-grid resume tested.
No warnings/errors in positive builds. No target firmware build or hardware.

r1 default.exe filename-specific no-output startup failures preserved; identical
bytes under an explicit test filename passed. r2 redundant default full sweep
was deliberately terminated after exact process-path verification; not PASS.
r3 is the completed source-bound result. Limits include simulated0/4/8-byte
EEPROM tears, no full151-block rollback fault sweep or target electrical/ABI
proof. Transaction reduction is validated in the model, not seconds saved.
Next gate is prospective contract/recovery review, not an automatic Boot flash.
All model outputs/compiler temp/cache/logs remain under the project, test workers
closed, no new APK/OTA/reset/Boot write, no unrelated dirty changes reverted.
