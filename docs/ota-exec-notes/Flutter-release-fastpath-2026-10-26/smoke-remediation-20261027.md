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
