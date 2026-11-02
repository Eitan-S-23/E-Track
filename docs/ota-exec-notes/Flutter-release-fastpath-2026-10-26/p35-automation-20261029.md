# P35-AUTO-01: Release Automation Script

User request: implement P3-5 automatic testing without screenshot/model-driven
control. Current restriction: phone unavailable, no human intervention. This
entry implements and self-tests host scripts only; it does not execute a campaign.

## Reuse Decision

The existing `Tools/ota/p34-acceptance/live_host.py` supplies process ownership,
bounded commands, input pins, local output guards and device locking. The standard
Android uiautomator/adb tools supply UI and radio actions. No custom BLE sender,
ADB implementation, Flash driver, fixture backend or generic replacement framework
is introduced. Appium was not found in PATH; no global installation was attempted.

Concrete gaps: existing `OtaExperimentRuntime` is guarded by kDebugMode;
`live_phone.py` diagnostic retrieval uses run-as; neither is a qualified Release
automation entry. Existing Release92 does not emit a complete loss-accounted
state stream binding UI phases, package/target identity and MCU resume state.
Those facts prevent claiming current-APK unattended readiness.

## Delivery

New files: `Tools/ota/p35-automation/runner.py`, `test_runner.py`,
`plan.example.json`, and `README.md`. The runner has offline check, no-tap probe,
and explicit execute modes; native accessibility selectors, continuous raw
logcat, bounded ten-window event control and no-replay accounting are implemented.
The missing Release producer is specified precisely in README, but NOT added to
product code in this script-only change. A synthetic unit-test producer cannot
qualify a live APK. Probe/run report CAPABILITY_MISSING rather than inventing data.

The default example keeps missing immutable inputs and Bluetooth-toggle permission
unset. It cannot start operations by accident. Its future target/windows are
examples, not a newly built/registered firmware. Retained30293 and the successful
user observations remain unchanged. No successful upgrade is repeated for logs.

The runner's packet group shares one final identity across ten independent
disconnect/resume events. The independent P3-5 owner must evaluate that grouping,
the adapter-wide Bluetooth impact, actual injection latency and component inputs
before formal use. The script is not a frozen contract or an independent PASS.

## Verification And Remaining Work

Original local self-test receipts are under `.cache/p35-automation-tests-20261029/`
in the active candidate worktree. Tests exercise the entire synthetic ten-event
path and negative cases: wrong input/identity/package, stale idle, missing/lost
records, missed actual cut, wrong MCU resume offset/session, collector failure,
radio restoration, misleading UI completion and no-durable-progress timeout.
No synthetic test counts as a phone recovery. The README documents invocation,
all source-data semantics, readiness gaps and failure/cleanup behavior.

Executed local Windows results: run-01 passed26 tests; run-02 passed30; final
run-03 passed34 with zero failures. These are successive development checks, not
independent acceptance rounds. cli-01 ran four real Python entry checks: help and
valid offline plan exited0; incomplete template and missing --execute exited2 as
expected. Neither rejected command created its requested live output directory,
and no adb/phone adapter was launched. Existing dirty files were not staged or
reverted. No .trellis exists in this worktree; no Trellis task was invented.

Remaining: Release-side producer/persistence integration, actual native UI and
radio capability qualification, exact real-backend/asset/source/profile binding,
independent review/freeze, and the live campaign. Product code was not changed;
no APP rebuild is triggered by these host-only files. Existing Release92 remains
installed; its NO_UPDATE fix and user-confirmed background upgrade stay valid.

All controlled outputs are project/worktree-local; no phone, network, build,
commit, push, merge, cloud write or external install is performed by this delivery.
The branch remains `candidate/p35-app-batch-20261029`; this change is uncommitted
and has not been delivered to main or another worktree.

## Continuation: Release Integration (Supersedes Host-Only Limitation)

The user requested completion rather than another host-only report. Added a
Release-capable, explicitly started OtaP35Recorder with no Debug VM, runtime
configuration injection or exported control provider. The normal OtaService
supplies phase/asset/identity snapshots, and existing transport/statistics hooks
supply accepted ACK state and actual completed DATA offsets. v1 uses the actual
bitmap; v2 uses null and resumes the durable offset. No firmware policy changes.

App-owned external JSONL files are flushed before logcat publication; bounded
queue/storage failures latch, and a footer binds the exact state bytes/count.
The host can retrieve unchanged originals after USB recovery without run-as,
running PID, reinstallation or repeating the upgrade. Missing footers remain
partial evidence. Old OtaObservationLog capture constraints remain unchanged.

Native semantic identifiers cover record/stop/reconnect/check/download/start.
Reconnect uses the normal connector and GET_INFO; it never starts transfer.
Host swipes are bounded to the native scroll viewport; no screenshots are used.
Both this UI mapping and Android Bluetooth/shell file access are still NOT_RUN
on the phone. Existing Release92 cannot gain these capabilities without a rebuild.

Local host regressions: 39 methods passed after protocol/archive integration.
Added Dart writer-failure, flush-order, bounded-loss, multi-resume and real Python
archive-consumer checks, actual v1/v2 transport observation tests, and native
semantic-action tests. They are development simulations, never physical recovery.
The exclusive dev/flutter/p35-automation-20261029 branch is for standing-authorized
checks-only CI. No Debug APK, production workflow, main merge, cloud or device
operation is part of this continuation. CI results will be appended when known.
