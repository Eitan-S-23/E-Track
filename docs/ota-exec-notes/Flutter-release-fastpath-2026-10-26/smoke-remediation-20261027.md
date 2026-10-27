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
Only the specific missing-descendant-Scaffold FlutterError is handled; unrelated
FlutterError is rethrown. No new blanket exception handler was introduced.
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
