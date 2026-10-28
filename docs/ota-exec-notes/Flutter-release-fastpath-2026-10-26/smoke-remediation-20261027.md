# P35 Smoke Follow-Up: UI And Complete File Route

## Scope And Owner

Same implementation owner and issues P35-SMOKE-UI-01 / P35-SMOKE-LOG-01.
Original root independently reviews; this is development remediation, not a
new task Spec, frozen role, independent acceptance or P3-5/P5 PASS.

Base: 18f6b3d3af0c24b1ce81573700cd61005b7c530e. Exclusive validation branch:
dev/flutter/p35-smoke-followup-20261027. Worktree:
D:/github/my/E-Track/.cache/p35-firmware-20261027/.cache/p35-flutter-followup-20261027.
The firmware worktree and its six untracked root records are read-only inputs.
The device-smoke record's three requested sections and original stack at
observe-002/private/phone-logcat.stdout:1294 were consumed without alteration.
The delivered prompt is the actual handoff; no other agent was spawned or relay
binding changed. No device action, OTA replay, MCU build, APK installation,
business key, production workflow, main push or Release is in this batch.
The board's retained 30292 identity is historical smoke evidence, not a new read.

## P35-SMOKE-UI-01

Confirmed device reproduction: awaited download success at page line 1224,
Get.snackbar -> SnackbarController -> Overlay.of, uncaught null check.
Cleanup/check/export sites are analogous risk checks, not additional claimed
device reproductions. The verified downloaded package survives that exception.

Minimal product delta: the page reuses safeSnackbar for all five affected async
feedback sites, stops page-owned continuations after disposal, and passes its
context. The existing helper rechecks that exact context on its scheduled frame,
rejects covered/transitioning/background page delivery and uses ScaffoldMessenger
instead of a GetX overlay. Missing Navigator/Messenger returns without redirecting
to another page. Service callers retain their existing root-context fallback.
Before display the helper checks for a mounted descendant Scaffold owned by the
same Messenger through the public widget tree. No exception handler is needed;
unrelated errors propagate normally. This avoids relying on debug assertions or
private registration fields. The first candidate's exception-based guard failed
the missing-Scaffold regression and was superseded as recorded below.
Feedback uses the existing helper's Material SnackBar presentation, not GetX's
top overlay/icon. Live foreground success/error feedback remains required.

No service, BLE, task owner/generation, cancellation, identity/package validation,
durable progress, MCU/Boot or build/signing configuration changed.
Deferred service/diagnostics substitutes drive real page buttons. Assertions cover
download after disposal, foreground success/transfer entry, covered navigation,
failed/cancelled download, delayed check/cleanup/export failures, unavailable
sharing, package retention and call counts. Helper regressions include root
service feedback, no GetX Navigator, missing dependencies, post-frame disposal,
navigation animations, background suppression and unrelated-error propagation.

## Original Red Run

Tests-only source ad58a1b963c7943b8711d185320971bd9d51926c retained old product
code. Checks-only push run 40509082166, attempt 1:
https://github.com/Eitan-S-23/E-Track/actions/runs/40509082166.
Both hosts analyzed successfully and executed all tests:

| Host | Original result |
| --- | --- |
| Ubuntu | FAIL, 786 passed / 16 skipped / 8 failed |
| Windows | FAIL, 767 passed / 35 skipped / 8 failed |

The original Ubuntu tests.log:10009 reaches the exact old download call and
SnackbarController/Overlay path. Subsequent cancellation also encounters the
poisoned GetX snackbar controller; retain this as downstream failure, not an
independently reproduced cancellation bug. Some disposed cases were obscured
by that singleton queue failure, not a demonstration that old lifecycle handling
was safe. The download loop now runs the disposal case first without weakening
any assertions; every original failing test remains in the final suite.

SDK on both hosts: Flutter 3.47.8 / Dart 3.13.7, framework
737ba8f885dc774b53b442759999a312c9461e4e, engine
cf636b1dfb818dd6a3ff16e390e93b1a036969c8.
Original full console/metadata/receipts are .cache/records/red-*;
hash-verified, complete raw reports/logs are .cache/ci-40509082166/.
Artifact IDs: Ubuntu 12736910245, Windows 12735784177; both retain 14 days.
A wrong-ID artifact fetch failed and remains red-ubuntu-zip-01.*; the correct
metadata-bound downloads are red-ubuntu-zip-02 and red-windows-zip-01.
One inline extraction command had shell redirection parsing failure before
Python ran; the corrected command preserved existing originals and extracted
12 text/JSON files. No firmware or APK binary was downloaded in this batch.

## P35-SMOKE-LOG-01

Existing route: emitOtaObservation -> OtaDiagnostics.record -> append-only
OtaObservationLog -> finishUpgrade/exportSnapshot -> observation_capture.py.
No logging product/protocol or production default changed. The default standard
APK still does not enable file diagnostics and logcat clipping is not repaired
retroactively. This route's qualification is distinct from measuring an OTA.

Added execution oracle uses the actual OtaLinkStats producer's >1024-byte
aggregate with a UTF-8 reason, real file writer and automatic finish export,
then invokes the existing Python CLI from the same repo. It verifies original
prefix bytes, SHA-256, record/producer counts, exact unwrapped message bytes/hash,
immutable close behavior, and rejects missing/footer/record, clipping, byte
corruption, counter corruption and missing file. A disabled recorder remains
disabled and cannot export. Synthetic invocation outcome is not-completed;
it does not manufacture successful identities, P99 or a device observation.

The existing build opt-in is device_observation=true with explicit target and
credential-free firmware-latest HTTPS endpoint; the development helper binds
the generated sentinel into its metadata/APK. main initializes diagnostics
from that build configuration. A later authorized measurement must bind the
actual APK/source/sentinel/target and retrieve the immutable App file via the
existing export/share route, then run the strict parser with those expected
inputs. Runtime-pipeline experiments additionally need their valid existing
runtime binding; none is added to the standard APK by this remediation.
No new APK/observation request or completed OTA replay is authorized here.

## Validation Pending

Consolidated fixed-code all-scope Ubuntu/Windows checks are NOT_RUN until their
new source/run is observed. Standard APK/EXE verification, debug packaging,
post-fix device UI observation and independent acceptance are NOT_RUN, not
covered by a checks-only push. Shipping build authorization remains a root
decision; do not invoke build.yml or alter versions/signing for this self-test.

Selected outputs are the exclusive worktree's source/tests/task record,
project-local .cache home/temp/GH/receipts/downloads and authorized common Git
objects, owned index/ref/reflogs and branch upstream config. All were preflighted
with the existing host_io guard. No PowerShell or local Flutter/Gradle ran.
The initial worktree checkout failed on long historical evidence paths; Git
removed its own partial checkout, then a scoped core.longpaths=true checkout
reused the retained branch successfully. Both creation receipts stay in the
parent firmware worktree .cache/records/smoke-worktree-01/02.*. No frozen
evidence was edited and no other worktree/index was switched or staged.

## First Fixed Batch And Consolidated Feedback

Source 491de8b3745e6af443674c57240c51beda413940, push run 40510986837/1:
https://github.com/Eitan-S-23/E-Track/actions/runs/40510986837.
Ubuntu 802 passed / 16 skipped / 3 failed; Windows 783 passed / 35 skipped /
3 failed. Analysis on both hosts found one missing-braces lint. Those original
logs, uploads and failed watch receipt remain unchanged under fixed-* and
.cache/ci-40510986837/. This batch is not claimed green.

All original page download/check/cleanup/export failure and cancellation
regressions passed. The three remaining failures are new dependency/share checks:
missing Scaffold produced AssertionError (tests.log:11872 on Ubuntu), not the
FlutterError the old helper anticipated. The final helper therefore checks the
actual Messenger-owned descendant Scaffold before display instead of expanding
catch to arbitrary errors. The unrelated-error test now installs a real
Scaffold before injecting its unrelated failure; its assertion is unchanged.
Missing-braces lint is corrected, not suppressed.

The two unavailable-share cases had zero intercepted calls because the initial
test double used shareFiles. Read-only source archives for share_plus 12.0.2
and share_plus_platform_interface 6.1.0 match the existing lockfile SHA-256s.
The real interface calls method share; the test handler now uses that exact
method, also checks the original file path and retains deferred completion,
foreground feedback, disposal and original-file assertions. No sharing product
logic, dependency or lockfile was changed or installed locally.

P35-SMOKE-LOG-01 passed on both hosts in this otherwise-red batch. Actual summary
is 1200 UTF-8 bytes; prefix has five records/two producer lines. Ubuntu snapshot
2633 bytes / SHA-256 185d564917b1acebeed4bf3c48a5fd3c36bfe569801b9e9d82f8fac7f4ccbb6b;
Windows snapshot 2635 bytes / SHA-256 35612c79ca60c299197afbde5eb35493c8d4d59b9fe98a5b4b0d46abafeec20b.
Exact unwrapped bytes have identical SHA-256 on both hosts:
bb9d11524e9a4e1c258cd5cc26eec1f9b45309b66b8f8eec3706f7b553c79222.
All six damaged variants and missing input were rejected; disabled behavior and
close immutability passed. Original lines are Ubuntu tests.log:11677 and Windows
tests.log:786. The existing host parser regression additionally
executed locally: python -I -S -B -X utf8 tests/ota/test_p3_4_observation_capture.py,
32 passed in parser-tests-01.*. This is file-route self-testing, not formal
acceptance, native Android execution or recovery of the clipped smoke records.

A patch invocation had invalid hunk syntax before editing; the corrected patch
keeps all original assertions. The consolidated changed-input checks are pending
their next exact source/run; unchanged red runs are not rerun or erased.

## Consolidated Development Result And Root Handoff

This section supersedes the development-pending statements above, without
changing the original failed runs. Stable tested/published source:
50130043967456db7dc8f559b97016c52ba69893, same dev/flutter branch/worktree.
Run 40513386721, attempt 1, push event, all scope, completed success:
https://github.com/Eitan-S-23/E-Track/actions/runs/40513386721.

| Host | Executed outcome |
| --- | --- |
| Ubuntu, job 122220711429 | Analyze PASS/no issues; full tests 805 passed, 16 platform skips, 0 failed; candidate tests 8 passed/0 skipped/0 failed. |
| Windows, job 122220711849 | Analyze PASS/no issues; full tests 786 passed, 35 platform skips, 0 failed; candidate tests 8 passed/0 skipped/0 failed. |

Both hosts used the same recorded Flutter/Dart revisions as the preceding runs.
All six runner commands (checkout/version/dependencies/analyze/tests/candidate
tests) exited 0 without timeout/cleanup failure; complete diagnostics and unchanged
lockfile were verified from original reports. Both host jobs also passed existing
runner/APK-helper regressions, PHY host lifecycle checks, strict snapshot parser,
batch accounting and v2 full-run/stability accounting. These are host checks,
not Android background/device outcomes or new performance acceptance.
Actions Node/runner deprecation notices remain in original console logs; no
notice was hidden or treated as a product pass. Platform skips are explicit.

P35-SMOKE-UI-01: implementation/self-tests complete, ready for root review.
All 13 deferred real-button cases and eight helper dependency/lifecycle/error
cases pass, alongside unchanged task ownership, cancellation, download/package,
durable and reboot-identity negatives. Download success preserves the service's
verified package and enables transmission on a live page; disposal/covered
route cannot produce stale feedback or setState. Only the historical download
stack is called a device reproduction. No post-fix phone observation occurred.

P35-SMOKE-LOG-01: existing complete-file route is verified reusable for the
bounded oracle. Final run again passes the actual 1200-byte UTF-8 producer through
record/finish/export/strict CLI/extraction, all six damaged cases and missing
input rejection, disabled mode and close immutability. Exact unwrapped SHA-256
remains bb9d11524e9a4e1c258cd5cc26eec1f9b45309b66b8f8eec3706f7b553c79222
on both hosts; capture sizes differ only with legitimate header/platform identity.
No logging product/default/protocol change was required. The diagnostic capacity,
one-business-invocation limit and four-export limit remain real constraints;
this file test does not qualify throughput/P99 or remove further input admission.

Commands on each hosted runner:
flutter analyze --no-pub;
flutter test --no-pub --reporter expanded --timeout 2m test;
flutter test --no-pub --reporter expanded --timeout 2m
--dart-define=OTA_LINK_PROFILE=adaptive-v2-candidate --plain-name candidate
test/ota/ota_release_link_profile_test.dart test/ota/ota_service_upgrade_test.dart.
Exact argv, cwd, SDK/lock/source identity and cleanup results are retained in
the original result.json files, not reconstructed from a green upload step.

Full run/job console: .cache/records/consolidated-logs-01.log. Complete original
reports/raw logs (22 text/JSON files) and their hash inventory:
.cache/ci-40513386721/. Product-source/run/attempt/host/commands were checked in
its verification.json. Artifact ZIPs are bound to the API digests:
Ubuntu 12737649747, 189275 bytes,
7300b0ff90f2f53515991e2140c3251b8b91342e29075800ce8747bf690b6ac3;
Windows 12737629769, 187340 bytes,
1f2a4e0862c4f1a18a42f9e20c974d6857683c9764a4ab7484a3096978538574.
Both expire 2026-11-10; required records are already downloaded locally.
Red/fixed predecessor raw logs/reports remain intact, including every failed
adapter/checkout/fetch receipt. No assertion, skip or fail gate was removed.

Standard Android APK and Windows EXE: NOT_RUN, no shipping build authorization
or workflow invocation in this batch. Debug APK: NOT_REQUESTED/NOT_RUN. Native
Android Service packaging/Robolectric: NOT_RUN. Post-fix device UI/OTA, protected
MCU builds, independent acceptance and formal P3-5/P5: NOT_RUN.
The task is ready for independent remediation review, not shipping completion.
Root owns that review and any separately authorized build/minimal observation/
forward asset/ten-disconnect plan. Do not replay the retained 30292 smoke.

Code/tests remain exactly the green remote commit. Only this final task-record
addition is deliberately uncommitted/unpushed locally, so a documentation-only
push does not trigger another unnecessary full development run. Root may read
this current worktree record and integrate it under its actual authority; this
is not a claim that an unmerged branch or local note was delivered to main.
Six-file bounded delta from 18f6b3d3: two UI/helper product files, three test files,
this task record; no dependencies, workflow, firmware or other agent files.
Final inventory/write/original-preservation audit is .cache/records/final-audit-01.json.

## Continuation: Query And Download Lifecycle

P35-SMOKE-LIFECYCLE-01 continues the interrupted implementation investigation;
it does not reopen the completed snackbar/file-route work or replay the 30292
device smoke. The preceding no-service-change statements describe the preceding
green batch, not this new delta. Same exclusive branch/worktree and development
self-test authority; no new agent, hardware, backend mutation or shipping build.
Actual remote main was read at continuation entry: 91fed6bc863d07edc7173c8e3c08b14c159f7863.
Remote owned branch was 50130043967456db7dc8f559b97016c52ba69893 before this batch.

The shared busy flag covers INFO/latest queries, file cleanup, downloads and
transfers. It did not identify which operation was safely paused. Consequently,
an INFO/latest operation ending in background left a UI pause that scheduled
BLE rediscovery and GET_INFO after the owner had already finished. Public manual
resume also rechecked an idle retained query transport. A foreground event before
download cancellation settled cleared the flag used to publish its safe-stop
failure, leaving phase downloading after the operation returned false.
These are host reproductions, not new confirmed phone reproductions.

Tests-only source 7c306505328dee8bee5b38dadf7338b4384f1372 retained old service code.
Run 40571458840/1 completed failure on both hosts:
https://github.com/Eitan-S-23/E-Track/actions/runs/40571458840.
Ubuntu: analyze PASS/no issues; 805 passed, 16 skipped, 8 failed.
Windows: analyze PASS/no issues; 786 passed, 35 skipped, 8 failed.
All eight new regressions failed. Original INFO test counts changed from 2/2/2
to 3/3/3 (discovery/INFO/platform write); latest and idle tests changed 1/1/1
to 2/2/2. The early download-return test observed downloading instead of failed.
No test timeout, analyze suppression or failure gate bypass occurred.
Candidate-entry tests and later host checks were NOT_RUN in this red batch.

Complete raw reports/logs are .cache/lifecycle-red/ (12 originals), with archive
digest/size verification and per-file hashes in inventory.json. Original Ubuntu
tests.log:24,35,46,57,68,77,88,99 and Windows tests.log:6565,6577,6589,6601,
6613,6622,6634,6646 contain the eight failures. Artifact IDs are Ubuntu
12765329066 and Windows 12765845051, both expiring 2026-11-10. Original API,
status, ZIP, commit/push and console receipts remain lifecycle-red-*.
The small cache-only extractor reuses host_io, checks all member paths before
writing, verifies API-bound ZIP identity/hashes and preserves only original text
reports. It is not an OTA collector or an acceptance runner.

Minimal repair source: 28860cf8ab4edffef7e28005154348ee768df32a.
Only ota_service.dart changes after the tests-only commit. Registration classifies
query/download/transfer before synchronous busy listeners run, resets the pause
and invalidates older recovery epochs. Query/cleanup do not pause retained BLE
transports. Downloads use their existing cancellation/foreground-retry route;
the safe-stop cause survives a resumed event until cancellation settles. Only
a live paused transfer in transferring phase may run the unchanged three-level
BLE recheck. Every awaited recovery result also checks owner epoch, operation
kind, active lifetime, phase, cancel generation, transport and recovery epoch.
Operation exit retires recovery before awaited native release/cleanup.

No capability, sender window/batch, GATT binding, ACK/credit/durable logic,
deadline, retry, notification identity, runtime debug boundary, HTTP schema,
device/package identity, version, signing or Boot/BCB code changed. Download
success still verifies the original package; stopped downloads require an
explicit retry. Successful transfer still requires fresh reboot version/raw SHA.
All eight red-test assertions remain byte-identical in the fixed batch; the
download cases additionally exercise explicit retry and exact downloaded bytes.

Root-cause analysis: implicit assumption (busy implies live transfer) plus a
coverage gap between otherwise-tested query, download and transfer paths.
The preceding snackbar fix addressed a different proven failure, not this owner
classification gap. Prevention is structural operation tagging plus live-owner
checks, and the eight deterministic service/adapter regressions. Similar cleanup
and completed-owner paths use the same query classification; real transfer
failure/identity/generation/cancel regressions remain in the full suite. No
Trellis tree exists here, so this lesson stays in the existing task handoff,
not in a newly invented spec system or altered frozen governance.

Fixed all-scope run 40572554673/1 is pending observation:
https://github.com/Eitan-S-23/E-Track/actions/runs/40572554673.
This is not yet a green delivery. Standard APK/Windows EXE, debug packaging,
post-fix phone observation and independent P3-5/P5 acceptance remain NOT_RUN.

## Lifecycle Development Closeout, 2026-10-28

This closes the interrupted report/archive work, superseding only the pending
lifecycle result above. No product edit, CI dispatch/rerun, commit/push, backend
mutation, APK build/install or device action was performed in this continuation.
At the preceding continuation entry, read-only remote reconciliation reported main
91fed6bc863d07edc7173c8e3c08b14c159f7863 and the owned development branch
28860cf8ab4edffef7e28005154348ee768df32a.

Run 40572554673/1 completed success at 2026-10-27T19:52:26Z, all-scope,
checks-only push. Original reports establish:

| Host | Executed outcome |
| --- | --- |
| Ubuntu, job 122430321566 | Analyze PASS/no issues; full tests 813 passed, 16 skipped, 0 failed; adaptive candidate tests 8 passed, 0 skipped, 0 failed. |
| Windows, job 122430321202 | Analyze PASS/no issues; full tests 794 passed, 35 skipped, 0 failed; adaptive candidate tests 8 passed, 0 skipped, 0 failed. |

Both reports bind Flutter 3.47.8 / Dart 3.13.7, framework
737ba8f885dc774b53b442759999a312c9461e4e and engine
cf636b1dfb818dd6a3ff16e390e93b1a036969c8. All six recorded runner commands
passed without timeout; diagnostics are complete, per-host lockfile bytes are
unchanged, and recorded semantic generated-toolchain deltas were restored.
Ubuntu's restored checkout is clean. Windows retains only the runner-classified
EOL-only modification to windows/flutter/generated_plugin_registrant.h; its
semantic fingerprints and untracked-file lists are empty. This is not a claim
that both hosted checkouts are byte-clean or that effective build inputs were
unchanged: both reports preserve their bound regeneration deltas. The generated
analyzer/platform-file handling is the existing runner behavior, not a new lint
suppression in this repair. Console tail truncation is explicit; the full raw
test logs are retained. Platform skips and Node/runner notices are not hidden.
Both jobs also passed the existing runner/APK-helper, PHY lifecycle, observation
snapshot, batch timing and v2 full-run/stability host checks.

All eight lifecycle regressions that failed on the tests-only source now pass.
The test file is byte-identical between 7c306505 and 28860cf8; no assertion was
relaxed. Query completion and idle resume issue no extra BLE recovery; both
download cancellation orderings publish a safe-stop failure and allow explicit
verified retry. Existing live-transfer owner/cancellation/durable/reboot identity
regressions remain in the full suite. These are development self-tests, not
post-fix phone observations or independent acceptance.

The existing extractor preserved 22 complete original text/JSON reports under
.cache/lifecycle-fixed/, with per-file size/SHA-256 in inventory.json.
Full-test terminal anchors: Ubuntu tests.log:23210; Windows tests.log:23568.
Archive metadata and ZIP identities:

| Host | Artifact ID | Bytes | SHA-256 |
| --- | --- | --- | --- |
| Ubuntu | 12765915961 | 181736 | b61a9472d39a622e0b12d71326d5f11df9bf576441da2fc1ab6e8c06122b5ab8 |
| Windows | 12766231254 | 187391 | b2cee8e94f5bbecf3d251b5b10353868dd322b0cdb7d9f9add3746e781b6c1e4 |

Both artifacts expire 2026-11-10; local originals are already preserved. Existing
full console/API/status/watch originals remain lifecycle-fixed-*; the new
remote/download/extraction receipts were added without replacing earlier files.
The red lifecycle inventory and preceding UI/file-route originals remain intact.
Two inline read-only preflight commands encountered Windows argument-quoting
SyntaxErrors, and one quoted content search returned no match. Corrected unquoted
arguments completed preflight; these host lookup failures wrote no files and are
not product-test failures or verification successes.

P35-SMOKE-LIFECYCLE-01 implementation/self-tests are complete and ready for the
original root review alongside P35-SMOKE-UI-01 / P35-SMOKE-LOG-01. Root owns
independent review and any separately authorized release-mode APK/EXE build or
minimum device observation. The retained 30292 smoke must not be replayed merely
to replace clipped diagnostics. This batch does not qualify P3-5/P5 or production.
Standard APK/EXE, debug packaging, native Android Service tests and post-fix
device observations remain NOT_RUN for this repair source.

The final audit is .cache/records/lifecycle-fixed-closeout-audit-01.json. Selected
writes are only this existing task record and exclusive-worktree .cache report,
ZIP, receipt and contained HOME/TEMP/GH/cache paths. No new common Git metadata
write, project-external output, move or deletion was selected. Product code stays
at the green remote commit; this closeout record remains deliberately local and
uncommitted/unpushed to avoid an unnecessary documentation-only development run.
Main integration and the overall candidate delivery remain separate root work.

## P35-SMOKE-LIFECYCLE-01 Requirement Coverage Correction

The previous closeout's eight green regressions did not establish every requested
lifecycle timing. Its implementation-complete claim was premature for this issue.
The broader implementation-handoff-20261028.md is not this remediation's oracle;
its A/B/C build/backend material and proposed additional acceptance role do not
replace the original root's independent review. Preserve those historical records,
but use this issue-specific continuation for the scoped handback.

The original root finding and its observation limits were read from the standard
worktree's smoke-ui-observation-20261028.md. No phone root cause is established by
the zero-byte logs or screenshot. The 30292 observation is not replayed.

Same original worktree/branch. Remote reconciliation for this batch observed main
91fed6bc863d07edc7173c8e3c08b14c159f7863 and owned branch
28860cf8ab4edffef7e28005154348ee768df32a. Product source was clean; the existing
three local closeout documents were retained without staging unrelated records.

Fourteen supplemental real-service tests add inactive/paused, repeated resumed,
NO_UPDATE/HTTP error with explicit discovery-null/changed-map sentinels, return
before and after HTTP completion, held/completed successor HTTP owners sharing
the retained subscription/package, and delayed real-transfer discovery/INFO
after cancellation followed by a new query owner. They assert discovery, INFO,
platform writes, ABORT, BEGIN, status/terminal/notification and exact package
bytes, rather than merely no exception. Existing eight tests remain intact.

Development plan: one old-service comparison on the same owned WIP branch,
then restore the exact 28860cf8 service bytes and run all-scope Ubuntu/Windows
checks. No assertion relaxation, new dependency, workflow, native test/build,
device action or cloud mutation. The temporary old-service source is explicitly
not a deliverable; preserve its run and restore before handback. The existing
receipt/extraction adapters are reused with fresh matrix-red/matrix-fixed names
so no original evidence is overwritten. Execution results remain pending.

Closeout-audit attempt 01 stopped before creating its result: an embedded parser
fixture also uses result.json but is not a development runner report. The audit
now selects the existing etrack-flutter-dev-checks-v1 schema and still requires
exactly two source-bound host reports and all original hash/command checks.
Attempt 02 encountered the same Windows inline-argument quoting issue before
evaluation. Both failed host receipts remain lifecycle-fixed-closeout-01/02.*;
neither failure reran CI, changed originals or relaxed product criteria.
Attempt 03 reached report evaluation but rejected the Windows EOL-only residual
because its original assertion required a completely clean checkout. Its failed
receipt also remains unchanged. The closing check requires the same source,
empty semantic/untracked changes, and exactly that Windows generated-header
residual (no residual on Ubuntu); it does not restore files or waive source drift.

The final continuation also encountered one read-only inline Python quoting
SyntaxError and one unmatched quoted heading search; neither wrote files. It
reused the existing receipt adapter and boundary guard with a whitespace-free
encoded argument, not a new harness or collector. Closing receipt:
.cache/records/lifecycle-fixed-closeout-04.json and its original log. The audit
checks both red/fixed inventories, preceding receipt hashes, exactly two runner
reports, command outcomes, source/test identity and output boundaries. Only the
existing task record, audit JSON and closing receipt/log are new selected writes;
all are inside this exclusive worktree. No new build, CI, backend, device, Git
metadata, project-external write, move or deletion was selected.

## P35-SMOKE-LIFECYCLE-01 Complete Matrix Handback, 2026-10-28

This supersedes the premature completion claim and pending supplemental matrix,
not historical failures or root observations. Implementation and the requested
development regressions are now complete for this bounded issue. Return to the
original root for independent review; no new freezing/acceptance role and no
independent acceptance PASS. The broad A/B/C report is not this issue's oracle.

### Source And Minimal Repair

Worktree: D:/github/my/E-Track/.cache/p35-firmware-20261027/.cache/p35-flutter-followup-20261027.
Exclusive branch: dev/flutter/p35-smoke-followup-20261027.
Reviewed UI/log baseline: 50130043967456db7dc8f559b97016c52ba69893.
Prior lifecycle repair: 28860cf8ab4edffef7e28005154348ee768df32a.
Old-service comparison: fec94361704407ebc699a7b4cb53de8bd60575e4.
Final tested/published source: a2e4b1af025594fd239fe42367fd25e7780bf35f.

Final service blob equals 28860cf8; comparison service equals 50130043. The test
blob is identical between comparison and final sources: no assertion relaxation.
Relative to 28860cf8 the final committed delta is tests only; relative to 50130043
only ota_service.dart and ota_service_upgrade_test.dart changed. No root source
copy, version/dependency/workflow/log-default/tuning/firmware changes occurred.

Repair remains operation registration before synchronous busy listeners, query-safe
background handling, download-specific stop/retry, live paused transfer owner and
recovery fencing, and retirement before awaited cleanup. Null discovery, chars
match, link generation, INFO identity, ACK/credit/durable/bitmap, cancel/deadline,
END and post-reboot version/raw-SHA gates remain unchanged.

### Executed Red And Green

Both runs are checks-only push events, attempt 1, all scope, not APK requests.

| Source/run | Ubuntu | Windows |
| --- | --- | --- |
| fec94361 / 40599854488/1 | Analyze PASS; 807 pass / 16 skip / 20 fail | Analyze PASS; 788 pass / 35 skip / 20 fail |
| a2e4b1af / 40600996231/1 | Analyze PASS; 827 pass / 16 skip / 0 fail | Analyze PASS; 808 pass / 35 skip / 0 fail |

https://github.com/Eitan-S-23/E-Track/actions/runs/40599854488
https://github.com/Eitan-S-23/E-Track/actions/runs/40600996231
Green jobs: Ubuntu 122528780655, Windows 122528780779. Both green candidate-entry
commands additionally executed 8 pass / 0 skip / 0 fail. All six green runner
commands exited 0 without timeout; lockfile unchanged, diagnostics complete.
Existing runner/APK-helper, PHY lifecycle, observation integrity, batch and v2
accounting host checks passed on both green hosts. Red candidate/downstream checks
were NOT_RUN due to failed full tests; host checks are not native Android evidence.

All hosts bind Flutter 3.47.8 / Dart 3.13.7, stable framework
737ba8f885dc774b53b442759999a312c9461e4e and engine
cf636b1dfb818dd6a3ff16e390e93b1a036969c8. Toolchain regeneration deltas are recorded.
Restored Ubuntu checkout is clean; Windows has only the classified EOL-only
generated_plugin_registrant.h residual, no semantic/untracked deltas. This is not
a claim of byte-clean Windows or identical effective build inputs. Console
truncation and Node/runner notices remain explicit; complete raw logs are retained.

Red evidence: eight preceding tests fail; eight new HTTP timing/sentinel cases
perform extra discovery/control writes; four retained-transport successor cases
publish OtaTerminalState over the later owner's null terminal. Two new genuine
transfer cancellation late-callback tests already pass on old code and are
preservation regressions, not new defects. Thus 12 of 14 supplemental tests are
red discriminators; all 14 plus the preceding eight pass after repair. This
refines the root's mechanism analysis without inventing more defects.

### Requested Regression Mapping

Line anchors refer to final ota_service_upgrade_test.dart.

| Requirement | Executed coverage and oracle |
| --- | --- |
| 1. INFO, held latest, inactive/paused, background completion, owner exit, resumed; no OTA | Line 468 matrix establishes real INFO, holds HTTP, delivers both background events, finishes HTTP, asserts owner exit and zero BEGIN/END. |
| 2. Legal NO_UPDATE and HTTP error retained | Eight line-468 cases cover NO_UPDATE and HTTP 400 INVALID_PARAMETER; status, terminal, phase and exact notifications survive return. Available/invalid-schema cases at 362 remain green. |
| 3. Null/changed-map sentinels; no discovery/INFO/ABORT | Every line-468 case installs a sentinel after INFO; call tuple unchanged, sentinel unconsumed, ABORT/BEGIN/END zero. Old code consumes it and performs a control write. |
| 4. Query unfinished on return, repeated resumed | Four early cases return twice while HTTP is held, assert busy query and no BLE recovery, then finish HTTP and return again. Late cases return after owner exit. |
| 5. Late recovery/new owner, same retained transport | Four line-536 cases delay old discovery across a held/completed successor HTTP owner. Exactly one subscription, no rebinding/control work; later state/notifications and exact verified file bytes survive. Two line-621 cases additionally exercise genuine transfer recovery discovery/INFO, cancellation and a later query owner. |
| 6. Identity query, download ownership, cleanup | Held INFO at 334 and download stop/early-return/verified retry at 422 pass. Existing real cleanup/attempt ownership/cancel/file-gate regressions execute in full suite; new retained-transport cases retain verified file. No package-clearing workaround. |
| 7. Actual transfer safety and late negatives | Acknowledged owner at 817, denial/loss safe pause at 856, second-pause late callbacks at 891, link negatives at 3822/3914, chars mismatch at 3954, INFO drift at 3987, late cancellation at 4017 and valid resume/final identity at 4063 all execute in green full suite. |

Tests use real service entry points, not private pause/owner state injection. On
fixed code obsolete query recovery exits before discovery. On old code its actual
discovery await survives into the successor owner, and release overwrites the
successor terminal. Genuine transfer recovery is tested separately and is not
substituted for the query-only defect.

### Originals And Final Audit

Complete reports/logs and per-file hashes are .cache/lifecycle-matrix-red/inventory.json
(12 originals) and .cache/lifecycle-matrix-fixed/inventory.json (22 originals).
Full console/API/status/commit/push/download/extraction receipts use fresh
.cache/records/lifecycle-matrix-* names; no historical receipt/archive overwritten.
Red terminal anchors: Ubuntu tests.log:23748, Windows tests.log:24353.
Green terminal anchors: Ubuntu tests.log:23306, Windows tests.log:23900.
Individual red locations: lifecycle-matrix-red-collect-01.log.

| Archive | Artifact ID | Bytes | SHA-256 |
| --- | --- | --- | --- |
| Red Ubuntu | 12778206156 | 194041 | a926623f5e25c445dcd1599534b0a87506fb36845192d7dd8fecf62876892557 |
| Red Windows | 12778111130 | 194180 | 1c814d4967fc92304ba66a9cb63e4ed709c78b17c330c13c170bd2767c166d9e |
| Green Ubuntu | 12778247177 | 192234 | 7b3a10a7f902001e593cc41cd52166ec9b1c6d76fdae5540de1a175b106af412 |
| Green Windows | 12778043148 | 195245 | 0a6923ece3d1de9b181e430cdf819fd63bfbdfc4b19e9f4e6183fa5d1e43abde |

All expire 2026-11-10; required bytes already preserved locally. Preceding lifecycle
and UI/log originals remain intact. The extractor's temporary label allowlist
extension was restored after collection. Existing adapter/helper retained; no
generic tooling introduced. One read-only cmd pattern failed, one guessed helper
filename was absent, and a documentation patch had mismatched context before
editing; corrected operations did not rerun CI or weaken assertions.

Selected local writes: two scoped code/test files, this existing note, fresh
exclusive-worktree .cache receipts/reports/ZIPs/inventories and contained
HOME/TEMP/AppData/GH paths, plus authorized common Git objects and this worktree's
index/HEAD/ref/reflogs and owned remote-tracking ref. Outputs and parent reparse
chains were preflighted using host_io. No PowerShell, local SDK/Flutter/Gradle,
project-external output, device/cloud operation, main/tag push, merge, Release,
move or deletion was selected. Audit: .cache/records/lifecycle-matrix-audit-01.json.

Code/tests are committed/pushed. This note remains local and uncommitted as
requested; the two pre-existing untracked broad closeout documents remain
untouched. Main integration remains pending original root authority.

### Return Boundary

Original root owns independent review of this exact lifecycle delta and originals.
No implementation/testing from the seven requested areas is delegated to root.
Standard/debug APK and EXE were NOT_REQUESTED/NOT_RUN in this supplemental batch;
native Android Service tests, phone observation, flashing/reset/OTA and backend
mutation are NOT_RUN. Prior built/installed APKs are not claimed to bind this new
supplemental source.

Phone original check-click cause remains unproved: screenshot followed Activity
foregrounding and three related logs are empty. Host reproductions prove the
software lifecycle defect, not its exact occurrence on that phone or changed
UUID/device/MCU. P3-5/P5, ten disconnect recoveries, production defaults and release
qualification remain separate obligations. Retained 30292 / 3.2.92 is historical;
it was neither read nor replayed.

Final audit executed PASS: 577 cache entries passed boundary checks; 90 original
files across the four lifecycle archives and prior green UI/log archive match
their retained size/SHA-256 inventories. Four exact-source host reports, real
counts, SDK, unchanged test blob, restored service blob and empty staged index
were verified. Receipt/log: lifecycle-matrix-final-audit-01.json/.log. Final
working-tree status remains only this modified concentrated note and the two
pre-existing untracked broad closeout documents; no uncommitted product/test
changes. A read-only lookup initially used inventory.json instead of the prior
UI archive's extraction.json; the correct original inventory was then verified.

## P35-SMOKE-LIFECYCLE-01-R01: Paused END Retry

Original root's review at smoke-independent-review-20261027.md:226 reports a P1
source-level regression in a2e4b1af, not an executed phone failure. The preceding
green CI and originals remain valid, but the issue is not review-PASS. The newly
introduced transferring-only eligibility rejects applying even though applying
starts before END ACK and the v1 retry can still be blocked at the pause gate.
Entry and stale predicates must describe the same live transport operation.

Same exclusive worktree/branch, same development-only authority. Remote main
91fed6bc and owned branch a2e4b1af were reconciled; root inputs remain read-only.
Eight real-service regressions add baseline and negotiated-v1 fallback END retry
with early/late foreground return, null-discovery/link-change bounded failures,
deferred first END processing/late ACK and closed-owner isolation. The fake can
drop the first END frame or defer its processing; actual validation/apply/identity
logic remains intact. Tests never set service phase/pause fields by hand. Normal
cancelCurrentTask remains a no-op after END; onClose is only bounded fixture
retirement for a failing test. No user cancellation is re-enabled.

First run preserves these tests with unchanged a2e4b1af service; then the minimal
repair will share eligibility across entry/stale checks, including a live
applying owner whose transport has actually started END. Existing owner epoch,
cancel generation, transport/connection identity, strict recheck, END sequence,
durable and target gates remain unchanged. No transport timeout/budget changes,
SDK/build/device/cloud operations or new review role. Results pending.

### R01 Implementation And Development Result

The P1 finding is reproduced by executed development tests and repaired; return
to the original root for independent re-review, not independent PASS. The prior
NOT PASS, successful prior CI and all historical originals remain preserved.

Worktree/branch remain the original exclusive implementation tree above.
Red tests-only source: abce1f536638be1e2d6b83a426fc0faf53022774, whose service
blob equals reviewed a2e4b1af. Repaired source:
392158684d2c2e9492e6140ca41e86bb7f118efc, committed/pushed on
dev/flutter/p35-smoke-followup-20261027. The red/green test blobs are identical.
Relative to a2e4b1af, only the service and its existing test file changed; no
previous query/download assertions, skips, dependencies or protocol were changed.

Minimal product delta is 8 added/4 removed lines in ota_service.dart:
_hasLiveTransferRecoveryOwner at line 1875 requires a busy transfer owner and
transferring, or applying with transport.endStarted=true. Resume entry at 1904
and post-await stale check at 1933 share it. Owner epoch, cancel generation,
transport identity, recovery epoch, foreground/closed checks and all three strict
link/characteristic/INFO rechecks remain. Queries/downloads/retired owners remain
ineligible. No blind unpause, user cancellation after END, budget reset, timeout
change, fake target success or transport/MCU change was introduced.

| Run / source / attempt | Ubuntu pass / skip / fail | Windows pass / skip / fail |
| --- | --- | --- |
| 40640015806 / abce1f53 / 1 | 828 / 16 / 7; analyze PASS | 809 / 35 / 7; analyze PASS |
| 40642081269 / 39215868 / 1 | 835 / 16 / 0; analyze PASS | 816 / 35 / 0; analyze PASS |

https://github.com/Eitan-S-23/E-Track/actions/runs/40640015806
https://github.com/Eitan-S-23/E-Track/actions/runs/40642081269
Green jobs: Ubuntu 122662286557, Windows 122662286268. Both are all-scope,
checks-only pushes; APK and native Android tests were not requested. All six
green runner commands exit 0 without timeout; candidate-entry commands each pass
10/0/0 (the two adaptive-profile END tests now match the existing candidate name
filter, alongside the prior eight). Full original tests are unfiltered.
The runner/APK-helper, PHY lifecycle, observation snapshot, batch and v2 accounting
host checks pass on both green hosts; no native/device claim follows. Red
candidate/downstream checks were NOT_RUN because full tests failed.

Both runs/hosts bind Flutter 3.47.8 / Dart 3.13.7, framework
737ba8f885dc774b53b442759999a312c9461e4e and engine
cf636b1dfb818dd6a3ff16e390e93b1a036969c8. Lockfiles unchanged, diagnostics complete.
Toolchain regeneration deltas remain recorded; restored Ubuntu clean, Windows
only declared generated_plugin_registrant.h EOL drift, no semantic/untracked
delta. Raw logs preserve console truncation and Node/runner notices. No lint,
failure or upload gate was weakened.

Eight new real-entry cases in final ota_service_upgrade_test.dart:

| Cases | Executed oracle and result |
| --- | --- |
| Four at line 683: baseline and negotiated-v1 fallback, foreground before/after first END ACK timeout | DATA reaches actual applying/END; first END frame dropped. inactive/paused, repeated resumed and manual resume retain non-cancellable task UI. A valid retry reuses END seq, no extra BEGIN/ABORT, strict resume INFO plus fresh reboot INFO run; target 20900 and full raw SHA '62'*32 match, owner settles within six-second test bound. All four fail by pending-Future timeout on red, pass on green. |
| Two at line 729: null discovery or changed link after paused END timeout | Strict recheck cancels the owner with DEVICE_LINK_CHANGED and retains package; no INFO after failed link/chars, no retry END and no false success. Original ABORT routing retained (one for null discovery, zero physical ABORT on changed link). Both timeout on red, pass with bounded failure on green. |
| One at line 765: deferred first END processing and late original ACK after timeout | Real fake-peer END validation/apply executes when released. The late ACK does not release the paused retry or fabricate success; foreground recheck sees the changed version/raw identity and strictly fails DEVICE_IDENTITY_CHANGED. Timeout on red, bounded safe failure on green. This is not an ACK-only completion path. |
| One at line 798: closed END owner, late ACK and duplicate resumed | Normal cancelCurrentTask remains disabled after END. onClose retires owner, releases resources and late original ACK/resumed events cause no discovery/INFO/write/status/phase revival or completed phase. This already passes on red and remains green. |

onClose in failing-test finally blocks only releases bounded host fixtures after
the asserted six-second timeout; it does not turn a hanging operation into a
passing test or enable UI cancellation. No service phase/pause fields were set
by hand. The fake _handleEnd keeps the existing content/sequence/durable checks;
loss/defer switches only control when the first received END is processed.
The preceding 22 lifecycle tests plus live-transfer/cancellation/download and
post-reboot identity negatives remain in the unchanged full suite. Aggregate
counts, exact test registration/blob, unfiltered commands and zero failures bind
green execution; no invented per-case concurrent-reporter anchors are claimed.

Original archives: .cache/lifecycle-r01-red/inventory.json (12 text/JSON originals)
and .cache/lifecycle-r01-fixed/inventory.json (22 originals). Full console/API/
status/commit/push/download/extraction receipts use fresh lifecycle-r01-* names.
Red terminal anchors: Ubuntu tests.log:24065, Windows tests.log:23776.
Seven failure anchors: Ubuntu 360/420/737/1701/2428/3853/5427; Windows
8533/9566/11423/12176/12284/12340/12396, all pending-Future timeout failures.
Green terminal anchors: Ubuntu tests.log:23951, Windows tests.log:24058.

| Archive | Artifact ID | Bytes | SHA-256 |
| --- | --- | --- | --- |
| Red Ubuntu | 12795520439 | 198266 | 8d1e97897c37ac00a05435d5ae19802826127483f82427902c81050302c2705a |
| Red Windows | 12795510903 | 183375 | e6264951a1d1cab44fa43445e8904ec8357e7cdaaac28235f90e643c750ffe8b |
| Green Ubuntu | 12795873786 | 207393 | a454939f5ba945ae8e9df9fdd5f3834e5f524d0abd22025c1c9bdf1b2e30f1a5 |
| Green Windows | 12795523255 | 196500 | 4437bfeb380393c1821b65a745451332b718e8d4dccb19d71534937dee644635 |

All expire 2026-11-11; required bytes have been archived and API size/digests
verified. Prior lifecycle/UI/log/standard-build inputs remain intact. Extractor
temporary label expansion was restored; no new general tool. The interrupted
continuation resumed only extraction/verification/reporting, not CI/device work.

Selected writes are source/test, this appended existing note, fresh contained
.cache receipts/ZIPs/reports/inventories/HOME/TEMP/AppData/GH cache, and authorized
common Git objects plus this owned worktree's index/HEAD/branch/ref/reflogs.
Outputs and ancestor reparse chains were preflighted; no project-external output,
PowerShell/local Flutter/Gradle, other worktree writes, main/tag push, merge,
Release, APK/EXE build/install, phone/MCU/cloud operation, move or deletion.
Audit: .cache/records/lifecycle-r01-audit-01.json.

Product/test are committed/pushed; only the concentrated note remains modified
and the two pre-existing broad closeout documents untracked, deliberately not
staged. Original root owns re-review of this exact delta/originals. Phone original
check-click cause remains unproved; no physical repeat of 30289 -> 30292 or new
read of retained 30292. Native Android, formal P3-5/P5, ten disconnect recoveries
and production/release qualification remain outside this development repair.

R01 final audit executed PASS: 124 originals across six lifecycle archives and
the prior green UI/log extraction match their retained size/SHA-256 inventories.
Four exact-source R01 reports and API-bound ZIPs, real counts, SDK, identical red/
green test blob, service-only repair commit and empty staged index verified.
698 cache entries passed boundary/reparse checks. Closing receipt and raw log:
.cache/records/lifecycle-r01-final-audit-01.json/.log. No product/test remains
uncommitted; only this concentrated note and the two pre-existing broad local
closeout documents remain as previously reported. R01 implementation/self-test
handback is complete; independent review decision remains the original root's.
