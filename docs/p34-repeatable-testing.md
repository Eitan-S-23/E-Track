# Repeatable P3-4 Screening

## IRQ Bootstrap Verified; Fixed-Receiver Screen

The 2026-09-23 `irq-bootstrap-115200` completed. Its original App snapshot,
full 30210 App readback, unchanged 64 KiB Boot and fresh confirmation agree;
SD is ready and both observer owners exited normally. Retain 3.2.10-p34i.
Do not repeat this upgrade or either bootstrap setup entry.

BEGIN-to-END ACK was 81.123085 seconds for 290855 package bytes and 2273 DATA
segments, with no retransmissions/error ACKs and no UART/ring/parser/Flash
errors. All 2273 latency samples were valid. This transfer was received by
30208, so it installs but does not test the repaired receiver. It is not a
QSPI speedup result. Original evidence: `.cache/p34q/irq/runs/irq-bootstrap-115200/`.

`Tools/ota/irq_screen.py` prepares the next fixed-input group under
`.cache/p34q/irqscreen/`. 30210 and 30211 have identical executable bodies and
the same original IRQ-only map; only the finalized image header differs.
All three cells use the same 290911-byte `irq-fixed-full.etu`, SHA-256
`326d30cca183833e0da34dcfcb52659a0d2af4062d36a71fb36f2c5d231a97f8`.
The installed p34retry APK, original staging, 128-byte DATA, CRC, credit and
retry behavior remain unchanged. No APK reinstall or QSPI candidate is mixed in.

The finite order is 460800 first to discriminate the former CRC fault, then
115200 and 921600 with the same input and supported complete 30211 -> 30210
restoration. A single completed cell is screening, not reliability acceptance.
An unknown outcome or integrity/recovery failure blocks dependent mutations;
another unchanged retry is not an experiment. Each cell has its own immutable
launch/config/result; a running worker is polled, never replayed.

Host package decode and all four negative packages passed. The new input,
routing, source-transform, baud and inactive-BCB guards pass 16 offline tests.
Recovery helper preparation passed 18 real BCB tests and the GCC build with
640 warnings / zero errors; the helper has not been flashed. Five real loopback
HTTP checks pass, including exact download/range and no update at 30211.
The runner renews only acknowledged-closed services, stops only the exact
completed debug App, preserves its data, verifies actual baud and cold start,
then prepares the original MCU collector and strict App extraction route.
Only connection/download/start UI remains user-owned.

At 09:13:37 UTC the first setup owner exited normally. The module returned
index 7 at 460800 before and after the matched restart; retained baud is 460800,
register-derived actual baud is 460063 and retention error is zero. The full
30210 App and unchanged Boot were verified again before collector readiness.
The same installed APK is now PID 8129. The actual new package and App query
were verified at 09:15:54 UTC; MCU reservation was acknowledged at 09:15:55.
Capture/coordinator now await the user's upgrade-start control. At 09:17 UTC
the healthy App still had zero starts/ends; no new OTA had started.
Do not replay `launch --run irq-460800` or edit its source-pinned workers.

Runtime: `.cache/p34q/irqscreen/runtime/`. Private USB port 5062 has a new
deadline of 10:41:50 UTC. The previous bootstrap phone/network owners are
normally closed. The new HTTPS package was verified with certificate validation
intact before device mutation. Use `irq_screen.py status --run irq-460800` for
current receipts, not a historical bootstrap command or old endpoint.

Output audits `irqscreen/continuation-audit.json` and
`.cache/p34q/session-audit-002.json` cover the selected new outputs and 11020
regular files. Original Flutter files, Git index, ADB key and native J-Link
history are unchanged. The pre-existing external PowerShell startup cache
changed again; its writer remains unknown and it was not cleaned. The user was
informed. All explicitly selected output paths remain inside the project root.

## Retrieved CRC Evidence And UART Repair

Update 2026-09-23: the fixed App's original failed snapshot has been retrieved
over the renewed private USB route, without launching/installing the App,
replaying OTA or changing baud. The installed APK still matches
`37cdfcb0863546013de84ed5ec26acbbf44af6f50e4a82699669bc73ebca719a`.
Capture `1790111283453873-0ea0151f5ee2c762df276d3e`, PID 27721, contains 1435
records / 1432 producer lines, a healthy zero-loss footer and one failed
invocation. Raw snapshot SHA-256 is
`ae91953a5cb2ac11f65456e42808ff7a0d4bb2062faf5cf926828972ac51ae7f`.

The initial retrieval adapter rejected only the uppercase/lowercase MAC
comparison after preserving all original bytes. Offline reconciliation compares
the validated six address octets, retains that original host failure and never
reopens USB. See `.cache/p34q/usb-retrieval-001/offline-analysis.json`.
The private server closed normally; its owner exited 1 for the host comparison,
not for a device operation or forced shutdown. Do not replay `baud_retrieve.py`.

The actual transfer has four ERR_CRC and 31 ERR_SEQ NAKs across six internal
sessions, 352 DATA sends / 160 repeated-offset sends, and final durable 24576.
The starting prefix was 4096, so new durable data is 20480 bytes. There is no
in-transfer background pause, ignored-ACK event or timeout DATA-retry event.
This is not the earlier durable watchdog failure and not a speed result.
The preserved last MCU profile alone has one bad frame and zero UART/ring/Flash
errors; missing earlier per-session profiles remain an evidence gap.

### P34-UART-01

`HardwareSerial::IRQHandler` read DT, invoked its callback, then cleared RDBF
again. The AT32 vendor contract (`at32f435_437_usart.c`, `usart_flag_clear`
notes) explicitly says reading DT already clears RDBF. A byte arriving after
that read can have its new pending flag cleared by the trailing write, silently
losing the byte without setting overrun. The repair removes only that trailing
clear; FIFO behavior, callback ownership, baud, CRC and protocol guards stay intact.

`tests/ota/test_hardware_serial.py --out FRESH_PROJECT_LOCAL_DIR` compiles the
real HardwareSerial implementation/header and real OTA parser with a bounded
AT32 register model. It covers idle/single-byte IRQs, arrival immediately after
DT or during the callback, a pending final byte, overflow/FIFO/wrap/flush and
32 complete wire frames. Before repair, both root and immutable experimental
sources fail 10 of 198 checks: an injected overlap yields 4543/4544 bytes,
one parser error, 30/32 valid frames and zero UART overruns. After repair all
198 checks pass, including 4544 bytes and 32 valid frames. These are modeled
interleavings, not proof of the timing of the earlier physical fault.

Root GCC App/Boot build passes with 392 warnings and zero errors. Related
staging 112, HAL 128, frame/ring 39 and BLE session 114 checks pass. The new
serial test is included in the firmware CI definition, but no new CI run,
mainline commit, release or independent acceptance has occurred.

The next bootstrap is prepared separately under `.cache/p34q/irq/`: retain the
original 30208 baseline, install an IRQ-only 30210 through a legal FULL OTA at
verified 115200, then test that repaired receiver before measuring QSPI speed.
Use `Tools/ota/irq_bootstrap.py` only with its new source-bound plan. The existing
fixed APK is reused; the unique `irq-bootstrap-full.etu` name preserves older
downloads. No App-only downgrade or Boot replacement is part of this cell.
The QSPI candidate is separately built under `.cache/p34q/`; its schema-2
336-byte profile includes distinct payload/journal verification timings.
Old 288-byte profile/map bindings must not be used for that candidate.

Current runtime: `irq-bootstrap-115200` is already armed, using the existing
p34retry App, PID 3842. User has downloaded the verified 290855-byte package
and has been instructed to start while foreground. Do not call `launch` again.
`irq/resume_setup.py` handled the original pre-USB proxy TLS failure without
recreating the service or any device action; the user later saw a transient 530
that recovered when the same tunnel reconnected. New admission tests 8/8,
HTTP checks 5/5 and QSPI profile checks 120/120 pass. QSPI App/Boot build has
638 warnings / zero errors and remains uninstalled. See the screening note's
"Bootstrap Ready At The User Start Boundary" for the exact runtime/deadlines.

## Current 460800 Failure And Retry Fix

Latest state: the fixed APK was installed and `retry-460800-fix` was attempted.
The user reports recoverable-error exhaustion `0x02` (`ERR_CRC`). Fresh passive
readback verifies the original full 30208/Boot and 24576 correct durable bytes,
not a completed upgrade. See `runs/retry-460800-fix/crc-readback/result.json`.
The original MCU reader and this passive reader have closed normally.
USB device `10ADA4197U001CK` is currently absent and no readable JSONL attachment
was available in the thread. Retrieve the immutable App snapshot after USB
reconnection; do not repeat installation, reset, OTA, `freeze`, `launch` or
`advance`. The pending phone route is `runtime/phone-r4`, deadline
2026-09-22 22:35:49 UTC; the unchanged network-r2 expires at 22:39:48 UTC.

Read-only follow-up at 21:32:16 UTC still returned device not found. No readable
attachment was recovered from the bridge's exposed resources or bounded local
filename search. The next input is the original JSONL (resend or absolute path),
or USB reconnection for retrieval; no additional OTA is needed. The external
startup-cache discrepancy from audit 001 has been disclosed and remains open;
see the screening note and `.cache/p34d/output-audit-002.json`.

`baud-460800` failed with `transport:NO_DURABLE_PROGRESS`, not a background
pause. Its original finished snapshot is complete and preserved. A bounded
passive readback verified full 30208/Boot, the correct 4096-byte durable prefix
and an idle MCU session whose final bitmap was `0x7fffffff`. The second block's
last 128-byte segment was missing. No UART overflow/error or Flash I/O error was
recorded; first and last internal profiles each contain one bad frame. The
origin of that bad frame remains unproved.

`Tools/ota/baud_durable_failure.py` owns the completed, write-once analysis,
offline ABI probe and passive readback under
`.cache/p34m/runs/baud-460800/failure/`. Do not replay those operations. Its
15 host tests passed. The original first-session profile is not the last
internal recovery session: original RTT has runs 1 through 4, while the App has
one upgrade invocation. Both original observers and the passive reader closed
normally. Never call `baud_advance.py` with this failed predecessor.

The reproduced sender bug is in `_TransferAckView.onAck`: an ignored, non-inflight
ACK used to call `_signal()`, restarting `waitForChange(ackTimeout)`. MCU liveness
every 500 ms could therefore suppress a missing segment's retransmission until
the unchanged 30-second durable deadline. Ignored ACKs must not signal a state
change. They still cannot alter durable/bitmap/credit or become ACK samples.

The isolated development branch is `dev/flutter/p3-4-durable-retry`, fix commit
`f30d71f3bd29238b01eb0c599e7b58e0d31e14b0`. Baseline commit `d43da13` with only
new tests reproduced three failures on both hosts in run `35781644426`.
Fixed checks `35782221936` and APK run `35782373638` passed: Windows 441 passed /
21 skipped, Linux 446 passed / 16 skipped. Flutter 3.47.5 / Dart 3.13.4 was used.
The debug APK is `com.wen.gaia.gaia.p34retry`, SHA-256
`37cdfcb0863546013de84ed5ec26acbbf44af6f50e4a82699669bc73ebca719a`.
This is pending mainline integration, not independent acceptance or a release.

`Tools/ota/baud_retry.py` prepares only `retry-460800-fix`, using the same FULL
package and retained durable prefix. Its eight offline route/admission tests
passed. It renews owned USB, preserves the original APK/data, installs the
side-by-side fixed APK, checks the live endpoint, and reuses the original
image-bound cold-start/capture/coordinator. No flash, AT command, manual staging
erase or downgrade is needed. The user still owns Bluetooth dialogs, connection
and the actual foreground start. The plan is `.cache/p34d/retry/plan.json`.

    python -I -S -B -X utf8 Tools/ota/baud_retry.py freeze
    python -I -S -B -X utf8 Tools/ota/baud_retry.py launch

These are fresh preparation entries, not replay commands. Inspect their immutable
receipts before acting. A resumed transfer is recovery, never a full-package
throughput result. After reconciliation, the remaining equal-input clean matrix
still includes 115200, 460800 and 921600 with the same fixed APK.

Required regression oracles: a lost block tail plus duplicate or unknown-seq
liveness ACKs is retransmitted with identical seq/payload and succeeds; persistent
loss retries but still ends at the durable deadline without END. A notification
is not necessarily a state change. Increasing the deadline or trusting unknown
ACK progress is not a fix. The fixed diagnostic path logs `MONO_ACK_IGNORED`,
`MONO_DATA_NAK` and `MONO_DATA_RETRY` with status/session/seq/bitmap or offset.

## Whole-Region Staging Verification

### Scope And Signature

P34-QSPI-01 is a source-only optimization in the root worktree, not yet installed
on the device. The internal `ota_staging_io_t` now ends with this optional field:

    ota_staging_result_t (*verify)(void *ctx, uint32_t address,
                                   const uint8_t *expected, uint32_t len);

Zero-initialize the I/O structure or populate every field through
`HAL::OTA_StagingGetIo`. NULL retains the original 128-byte read/compare fallback.
The callback borrows `expected` only for its synchronous invocation and must
read back and compare every requested byte, without publishing any progress.
The binary protocol, persistent metadata and 4 KiB/128-byte boundaries do not
change. The added function pointer changes in-memory sizes, so a newly linked
image still needs its own exact ELF/map/layout bindings.

### Validation And Error Contract

| Callback or port condition | Result |
| --- | --- |
| Full readback matches | `OTA_STAGING_OK`; caller continues the original checkpoint/bitmap sequence |
| Any byte differs | `OTA_STAGING_ERR_VERIFY`; no successful block/finalize result |
| Read/XIP restoration fails | `OTA_STAGING_ERR_IO`; do not access mapped bytes after a failed restore |
| Any other callback return, including positive progress values | Normalize to `OTA_STAGING_ERR_IO`, never treat it as block completion |
| QSPI port receives NULL, zero/over-block length, invalid range or disabled OTA | Reject before XIP restoration/mapped access |

The HAL restores XIP once per complete comparison, then compares directly with
the already-owned RAM block. It caches no mode assumption between calls and
allocates no second block. Ordinary reads and post-erase/program restoration
remain unchanged. Correct: amortize setup while checking all bytes. Wrong:
remove readback, trust a stale cross-client XIP flag, or enlarge the send window
without updating the frozen flow-control contract.

### Cases And Verification

`tests/ota/test_ota_staging.py` now also compiles the real
`USER/HAL/HAL_OTA_Staging.cpp` with the narrowly scoped NOR/XIP model under
`tests/ota/staging_hal_stubs`. It covers full/1/129/4095-byte blocks, corruption
across the block including its last byte, ETRJ/bitmap/ETSL/marker corruption,
every block-commit restoration failure, write failures, reset before bitmap
commit, loss of mapped mode, and the portable fallback. These are host tests,
not physical Flash timing evidence.

The pre-fix run preserved 37 XIP restores for one full block and failed the two
new performance assertions. The changed HAL uses 6 restores, with all 128 final
HAL checks passing. Both portable verification paths and invalid callback
returns pass 112 checks; unchanged dependent BLE/SD tests pass 114/29 checks
plus 7 actual OtaUpdate scenarios. The SD runner's old aggregate text still
says 5 scenarios; use its actual seven scenario results instead.

Evidence: `.cache/p34q/baseline/`, `fixed-tests-001/`, `final-hal-001/`,
`dependent-tests-001/`, `build-001/` and `stack-001/`. GCC App/Boot build passed
with 397 warnings and zero errors; Boot was already up to date. The new HAL
verification function has a 16-byte compiler-reported local stack frame; the
portable verifier has 160 bytes including its existing fallback buffer. These
are individual function bounds, not a new complete call-stack proof.

The final current-wrapper run is `final-tests-001/` (112 staging plus 128 HAL
checks); `.cache/p34q/summary.json` binds the results. The output audit observed
a further unexplained change to the external PowerShell startup cache and the
user was informed; no external cleanup was performed. See the screening note
for its exact path and digest. This remains an open host-audit discrepancy.

### Hardware Gate

No new package, flash, reset, AT command, App installation or OTA was performed.
The latest passive device state and missing CRC snapshot remain as documented
above. The root build artifacts are build-validation outputs, not a newly
admitted/finalized OTA package. The old instrumented firmware and its evidence
remain unchanged. A future instrumented build must time the new `verify`
callback too: a wrapper that measures only `read` would otherwise lose the
optimized readback time and falsely suggest that it became zero. Prepare
matching new image/map/collector inputs and retrieve the original App failure
before running the same-input physical comparison. No speedup is yet claimed.

## Current Fixed-Firmware Entry

The active continuation is `.cache/p34m/`, not the failed `.cache/p34b/`
bootstrap described in the historical sections below. Fixed 30208 has passed
one actual OTA, full target/whole-Boot readback and startup memory qualification.
The installed single APK is unchanged. `baud-115200-r6` failed before END after
a 105.284339-second background pause exceeded the MCU's 30-second inactivity
timeout. The original snapshot, abort profile and failure receipts are preserved.
`baud_interruption.py` verified the full retained 30208 App/Boot and all 45056
durable bytes without a reset or target write. Do not call `advance` for r6 or
rerun the successful bootstrap.

Current coordinator/capture entry: `Tools/ota/baud_foreground.py`. A new nonce
envelope of the identical 30209 image lets the existing BEGIN logic rebuild the
unmatched journal without manual erasure or a separate recovery OTA. The shared
three-rate package remains 290810 bytes, SHA-256
`35d15c8c3ed87c070e068e61af3943ab58c67cf79b24478bd1c8ffc979d4043b`.
The finite cells are `baud-115200-f1`, `baud-460800`, `baud-921600`. Only after the
named previous cell has a valid original `completed.json` and clean MCU profile:

    python -I -S -B -X utf8 Tools/ota/baud_advance.py advance --run baud-115200-f1
    python -I -S -B -X utf8 Tools/ota/baud_advance.py advance --run baud-460800

The first command prepares 460800; the second prepares 921600. They do not skip
the original target/Boot/confirmation/memory guards or the complete-state
restoration route. Actual foreground OTA starts remain phone UI actions. Do not
use a stale `status.json` to override a completed/failed result receipt.

The 115200 foreground cell has now completed: 80.895157 seconds, 3.510645 KiB/s,
zero retransmissions, 2272 valid ACK samples, P99=927033 us, no background pause,
and full retained 30209/Boot confirmation. This small-package development result
is not the 1 MiB or reliability acceptance. Its App/MCU observers closed normally.

The original foreground `advance` command was blocked before any device command
because its reused recovery runtime still selected the closed phone-r2 route.
Do not replay that entry. `baud_advance.py` binds recovery to current phone-r3,
preserves the original raw-image helper expectation and foreground successor
package, and reuses the tested native process/cache reader for recovery links.
Six host regression cases cover routing, real completed admission, excluded
predecessors and unchanged write/rollback guards. Its first advance has already
launched under `runtime/advance-rebound-baud-115200-f1`; inspect its receipts rather
than launching the same transition twice.

That transition completed normally at 20:08:57 UTC. Complete-state rollback
verified the original 30208, unchanged Boot, erased staging journal, unchanged
settings and SD readiness. Actual 460800 communication (module index 7) and
post-reset retention passed. `baud-460800` launched App PID 10152; the same
package/query were verified and the MCU reserved the cell at 20:09:23 UTC.
It subsequently failed before END; see the current failure section above.
921600 remains unmeasured. The failed `baud-460800` capture/coordinator, f1 and
its advance owners have all closed normally.

`baud_uncached.py` supplies native process inventory and the physically verified
aligned eight-byte DWT CTRL+CYCCNT reader. Scalar `ReadMemEx` and `ReadMemHW`
reads can return the J-Link V8.18 debug-register shadow even when the ordinary
memory cache is disabled; neither a larger timeout nor removing the clock guard
is a fix. `baud_resume_clock.py` also binds the tuning link to the same reset
exception class as the reader. The original host failures and all source
generations remain preserved. Current host regressions: 13 cache/presence cases
and three reset-type cases, plus the original MCU/runtime tests.

The current private USB route is `runtime/phone-r3` with owner `phone-worker-r3`;
the network is `runtime/network-r2` with owner `network-worker-r2`. The previous
phone-r2 and network-r1 owners closed normally after failure reconciliation. An
old `close` command targeting `phone-r1` does not close the current server. Reconcile
the actual current owners and their deadlines/closure before renewing them;
never restart a worker into its existing evidence directory. Keep the live
parent and continuation sources immutable. See the screening task note for
original hashes, failure receipts and the exact remaining experiment scope.

The initial foreground setup stopped before opening the new App/MCU cell because
the host's configured proxy returned TLS EOF for the new tunnel. The same origin
worked with direct HTTPS and normal certificate verification. The bounded
`foreground/resume_setup.py` completed only the remaining setup, not the old
release/closure. Preserve both owner receipts; do not rerun `launch`, `prepare`,
or that one-shot helper. Direct HTTPS verification is process-local and does not
change the system proxy. No APK/firmware rebuild or TLS bypass was involved.

### Interruption Contract

`baud_interruption.py analyze --run RUN` validates the original App-generated
snapshot, exact input identity and frozen abort profile. `launch-readback` then
requires acknowledged observer closure and uses one bounded read-only worker.
Its write-once results are under `runs/RUN/failure/`; an existing partial or
successful extraction must never be overwritten. The helper is not a retry
command and grants no device mutation.

| Observation | Required handling |
| --- | --- |
| Background pause, MCU abort, no END | Failed invocation; preserve it and reconcile current firmware/staging |
| Journal CRC/package/bitmap or raw prefix mismatch | Stop dependent writes; never assume the logged offset is safe |
| Committed staging or target activity | Not this pre-END path; reconcile apply/target state instead |
| Verified nonzero durable prefix | A resumed transfer is recovery, not full-package screening |
| Known previous download during replacement | Wait for the normal App download; unknown bytes still fail closed |
| New shared package, actual query and reservation | One user foreground start; no chat acknowledgment during OTA |

The regression suite includes the real failed snapshot and negative cases for
success reinterpretation, duplicate starts, backward clocks, wrong identity/CRC,
bitmap holes/out-of-range blocks and already-complete/committed staging. The new
input-group tests reject changed raw firmware, changed size, unchanged package
SHA or missing decoder checks, and verify all three configurations and the
original recovery helper share the same raw identities. The real HTTP suite also
checks full download, range requests and no update after the target is installed.

Wrong: replay a successful bootstrap, count the remaining 245754 bytes as a full
290810-byte measurement, or delete the background pause guard. Correct: preserve
the failed invocation, verify retained state, and declare a new equal-input group
for all rates. Android background execution remains the separate P3-8 work item.

## Single-App Three-Rate Successor

The 115200/460800/921600 successor uses `Tools/ota/baud_runtime.py` and
`.cache/p34b/plan.json`; the commands below this section still describe the
completed older 30206/30207 four-App campaign and must not be used unchanged
for the new diagnostic group. See the exact artifacts, permissions, tests and
state gates in `docs/ota-exec-notes/P3-4-screening-2026-09-22.md`.

Run from the explicit project root with isolated Python, no PowerShell:

    python -I -S -B -X utf8 Tools/ota/baud_runtime.py open
    python -I -S -B -X utf8 Tools/ota/baud_runtime.py start --run bootstrap
    python -I -S -B -X utf8 Tools/ota/baud_runtime.py status --run bootstrap
    python -I -S -B -X utf8 Tools/ota/baud_runtime.py advance --run bootstrap

`open` verifies the new temporary service, starts the isolated owned USB server
and installs only the exact single debug APK when absent. `start` provisions an
immutable per-process experiment file, admits the image-bound MCU observer, then
launches the App. The coordinator waits for original queries and exact download
bytes before arming; only the user starts the actual foreground OTA. `advance`
requires the previous completed App snapshot and full target readback, releases
that exact debug App, performs the admitted baud/restoration route and prepares
the next fixed cell. It runs under a detached bounded supervisor, not a terminal
that must remain open. It does not replay a prior operation with an uncertain
result. A later `advance` names `baud-115200` or `baud-460800`; after 921600 there
is no automatic extra experiment.

The 30207 -> 30208 diagnostic bootstrap is separate from the three 30208 -> 30209
measurements. Never flash the raw unfinalized build BIN or use the old 326 recovery
helper for these identities. Service closure requires a fresh bound endpoint,
not a new APK. Source-pinned workers remain immutable until acknowledged closed.

### Current Bootstrap Failure

The first `bootstrap` returned to 30207 after three diagnostic startup attempts
and watchdog resets. Its transmission completed, but its immutable App snapshot
is `not-completed`. Do not call `advance --run bootstrap`, rewrite its finished
directory, or fabricate a completed binding. `baud_failure.py analyze` preserves
this distinction; its already-executed bounded readback verified the whole
returned App, Boot, candidate and backup without MCU writes.

`baud_startup_trace.py` provides the narrowly scoped startup probe. Its
`launch-probe` mode was validated on the normal baseline with non-halting PCSR,
exception and health reads. Its `prepare-run` mode has already prepared
`bootstrap-trace`, using the same installed APK/package at 115200, a renewed
private ADB window, and one MCU reader. Do not repeat those preparation commands
or edit their live sources. Actual start is a user UI action after the current
run's query/package and MCU reservation receipts exist.

New evidence is `.cache/p34b/runs/bootstrap-trace/mcu/startup-probe.jsonl` plus
the normal raw epochs and App snapshot. Startup snapshots are not performance
data. A stopped health counter alone does not prove a specific cause; resolve
the matching sampled PC/stack with the exact diagnostic ELF. Unknown images,
changed prefixes and sampling limits reject/stop diagnostic reads, never bypass
OTA success gates. `test_baud_failure.py` and `test_baud_startup_trace.py` cover
these behaviors with 12 offline tests. Full findings and current worker receipts
are in the screening task note linked above.

`Tools/ota/repeat_cycle.py` is the single entry for the admitted 2026-09-22
experiment. It reuses the source-bound matrix, complete restoration helper and
installed generation-3 APKs. It is not a generic flasher and does not rebuild
firmware, create APKs, replace Boot, clear App data or tap phone controls.

## Commands

Use cmd.exe, explicit cwd `D:\github\my\E-Track`, and the installed Python 3.13.
The abbreviated `python` below must resolve to that interpreter. No PowerShell
startup, local Flutter/Gradle build or external temporary directory is needed.

```bat
python -I -S -B -X utf8 Tools\ota\test_repeat_cycle.py --out .cache\p34-cycle-tests-r4
python -I -S -B -X utf8 Tools\ota\repeat_cycle.py start --run c2-001 --candidate discover-without --previous reuse-with
python -I -S -B -X utf8 Tools\ota\repeat_cycle.py status --run c2-001
```

After a completed run, select its actual predecessor explicitly:

```bat
python -I -S -B -X utf8 Tools\ota\repeat_cycle.py start --run c3-001 --candidate reuse-without --previous discover-without --previous-run c2-001
```

Use `--tests PATH` for a later source-bound passing test receipt. Every test
invocation needs a fresh output directory. Every actual comparison needs a fresh
run name. Existing successful C0 and C1 transfers must not be repeated to repair
host evidence.

## Automatic Steps

The detached, finite coordinator checks the previous private ADB closure and
renews only its private port. It releases the exact completed debug App, admits
the full on-device backup and whole Boot, executes the supported complete 3.2.6
rollback, verifies baseline/Boot/clean staging/confirmation/SD, starts the MCU
reader and launches the exact installed candidate.

`NEEDS_USER` means connect BLE, handle actual permission dialogs, query firmware
and download in the selected App. Do not start yet. The coordinator verifies real
App queries and downloaded bytes, then arms the reader. `READY_TO_START` means
tap upgrade once and keep the App foreground; no chat acknowledgment is needed.
It then retrieves the immutable finished snapshot, waits for full target/Boot
verification and writes `cells/<candidate>/measurement.json`. `COMPLETED` means
both sources passed, not independent performance/reliability acceptance.

The capture budget separately includes 1800 seconds of phone preparation,
900 seconds of start waiting, the unchanged 1280-second transfer/apply/readback
reserve and 120 seconds of margin. Ordinary apply still gets 300 seconds. A
suggested start deadline never terminates an observer of a possibly active OTA.
Workers remain finite; expired or uncertain operations are reconciled, not replayed.

## Recovery And Evidence

Run state is under `.cache/p34-cycles/<run>/`: immutable config/source bindings,
`actions/*.intent.json`, `actions/*.done.json`, `status.json`, worker logs and
original per-cell results. Complete restoration still writes fresh
`cycle-<run>` namespaces under `.cache/p34-restore-20260922/`; it references the
unchanged finalized helper instead of rebuilding it. Legacy backend host caches
and command journal remain in the admitted screening registry inside the root.
The exact already-authorized native J-Link history exception is unchanged.

```bat
python -I -S -B -X utf8 Tools\ota\repeat_cycle.py resume --run c2-001
```

Resume requires the previous coordinator's closed receipt. Completed phases are
adopted only with unchanged original evidence; a started phase without a verified
result becomes `RECONCILE_REQUIRED`. Never delete an intent to force a retry.
An expired ADB route requires host-only renewal/reconciliation, not another
upgrade. Do not edit source-pinned scripts while any worker is running.

The runner intentionally depends on the preserved, tested local backend
and current finite experiment authorization. An expired embedded HTTPS endpoint,
changed backend/assets, unknown device state or changed permission scope fails
closed before dependent mutations. Host tests are not hardware acceptance.

## Runtime Contract

The commands above are the public signatures. `start` requires a fresh run,
the selected candidate, a verified completed predecessor and current source-bound
host tests. `status` is read-only. `resume` creates only a new coordinator after
the old coordinator is demonstrably closed; it is not a new device trial.
Internal `work`, `phone-worker` and `capture-worker` modes consume that exact
immutable `config.json`; do not invoke them to bypass `start`.

`config.json` binds `root`, `out`, `run`, `candidate`, `previous`, original
predecessor evidence, private ADB predecessor and hashes of driver/backend/test
sources. Phase receipts bind the config hash and exact original result hash.
`status.json` is the owned mutable projection with `time` and `state`; the
original results and phase receipts, not a stale status projection, decide resume.
Children use project-local HOME/USERPROFILE, APPDATA/LOCALAPPDATA, TEMP/TMP/TMPDIR
and Android homes. Existing ADB keys are read-only inputs.

| Condition | Result |
| --- | --- |
| Completed phase with unchanged evidence | Reuse, zero repeated device commands |
| Intent exists, original completed result appeared after interruption | Validate and adopt that exact result |
| Intent exists without a valid result | `RECONCILE_REQUIRED`; no replay |
| Wrong phone/APK/package/target/Boot or dirty baseline staging | Reject before dependent operation |
| Package is still downloading or observation has not initialized | Wait within the preparation bound |
| Collector closed before App launch | Reject launch; no false ready indication |
| Phone download and real queries verified; MCU reservation acknowledged | `READY_TO_START` |
| Original App snapshot and full MCU/Boot verification complete | Write measurement, retain target, `COMPLETED` |

Base case: C1's original snapshot yields 247.039059 seconds and one discovery,
but incomplete ACK samples remain threshold-ineligible. Good recovery: resume
adopts a completed restore result without reflashing. Bad recovery: deleting its
intent or starting a new run to hide an uncertain restore is prohibited.

`test_repeat_cycle.py` checks replay/adoption, source and evidence drift, missing
results, sibling/relative path escapes, invalid labels, independent time budgets,
dirty health/staging, wrong device/package/Boot, delayed download/initialization,
closed collector rejection, actual backend output binding and the unchanged
300-second apply gate. The original host-only receipt was
`.cache/p34-cycle-tests-r2/result.json`: 21 tests, zero failures/errors. These
include read-only regression against original C1 evidence, not new device work.

## Prelaunch Host Recovery

C3 exposed a publication race: `preflight.json` can exist before the next
two-second `state.json` update reflects readiness. The original immediate
`fresh_baseline()` check failed safely before any App launch, but unnecessarily
closed its USB server. A completed preflight and a status projection are not an
atomic pair. The MCU reader remained healthy, unarmed and on the same baseline.

Keep live source-pinned scripts unchanged. `resume_cycle.py` is the bounded
recovery entry for this exact failure, not an alternative flasher:

```bat
python -I -S -B -X utf8 Tools\ota\resume_cycle.py selftest --out .cache\p34-cycle-recovery-tests-r1
python -I -S -B -X utf8 Tools\ota\resume_cycle.py start --run c3-001 --out .cache\p34-cycle-recovery-tests-r1
```

It requires the original coordinator's actual closed receipt, normal old ADB
closure and a closed port, unchanged verified restoration/preflight, a live
baseline MCU observer, and no launch/arm/stop intent. Its ten-second readiness
wait tolerates publication delay but rejects any reserved/changed epoch, error,
closed reader, stale/future timestamp or deadline expiry. The eight new host
tests explicitly reproduce the false-negative projection window and its repair.

Recovery records its plan and original failure under `host-recovery-r1/`, starts
only `phone-recovery-r1`/`adb-recovery-r1`, and continues the original cell's
launch/arm/finished/measurement journal. It never calls restore, reset, install,
release or capture. Preparation may use the remaining original setup allowance;
the independent 900-second start and 1280-second transfer/verification reserves
are not reduced, and the original MCU deadline is not extended.

Wrong: rerun `start`/delete an intent/reflash because a status projection lagged.
Correct: preserve the failed coordinator, wait for the live state predicate and
renew only the demonstrably closed host route. After C3 and its workers close,
the next runner revision should use this readiness wait in the ordinary start
path as well, with explicit preservation/migration of the v1 source bindings.

## Revised Normal Entry

After all C3 workers closed, the bounded readiness predicate was moved into
`repeat_cycle.py` and shared by normal start and host recovery. The current
normal-entry receipt is `.cache/p34-cycle-tests-r4/result.json`: 36 tests passed,
including all eight recovery tests and a normal-entry delayed-publication case.
The standalone recovery suite also passed in `p34-cycle-recovery-tests-r2`.
The r3 test run preserves a misplaced test-assertion NameError; it was corrected
without any device operation or change to the original evidence.

Actual v1 scripts were copied byte-for-byte before modification into
`.cache/p34-cycle-source-archive/`, with SHA-256 filenames and
`manifest-v1.json`. Only a verified completed predecessor can use that exact
original-path/hash/length archive binding. Live runs still require current
source equality, with no archive fallback. `resume` of a completed run validates
its original results and returns `COMPLETED` with zero device commands.

A new cycle enumerates the completed predecessor's original and recovered
private ADB routes, requires all to be closed, and selects the latest route.
It never treats an older closed server as evidence that a later server closed.
The current C3 confirmation entry, not a replay of its completed invocation, is:

```bat
python -I -S -B -X utf8 Tools\ota\repeat_cycle.py start --run c3-002 --candidate reuse-without --previous reuse-without --previous-run c3-001
```

The confirmation round exposed a second pending-state case: the real
`CaptureState` starts with `epoch=None`, not the epoch-0 fixture used in the
first repair. Its live scripts remain unchanged. The current recovery entry is:

```bat
python -I -S -B -X utf8 Tools\ota\resume_cycle_v2.py selftest --out .cache\p34-cycle-recovery-v2-tests-r2
python -I -S -B -X utf8 Tools\ota\resume_cycle_v2.py start --run c3-002 --out .cache\p34-cycle-recovery-v2-tests-r2
```

Its 12 passing tests exercise the actual collector constructor and confirmation
transition. None is pending only before readiness with no activity; it cannot
hide a reservation, error or post-readiness loss. This adapter retains the old
MCU reader and renews only the closed private ADB route. Normal-entry integration
is deferred until this reader closes so its source bindings remain immutable.
No further physical run is needed just to validate that host-only integration.

## Initial-Epoch Fix Completed

C3 confirmation `c3-002` completed with 80.309317 seconds / 3.461263152 KiB/s,
zero retransmissions and full target/Boot verification. Its original failed
prelaunch coordinator is preserved. All its workers closed before source edits.
`manifest-v2.json` in the source archive preserves the exact four current source
files, including the original v2 recovery adapter, before normal-entry integration.

The normal entry and both recovery routes now share `ready_state` / `wait_ready`.
The actual constructor's `epoch=None` is pending only before readiness and with
no activity/error/begin epoch. Closed, reserved, changed, erroneous and timed-out
observations remain rejected. Both explicit source-archive manifests are usable
only for verified completed predecessors, never to excuse live source drift.

Normal-entry host tests: `.cache/p34-cycle-tests-r5/result.json`, 48 passed.
The compatibility adapter's standalone tests:
`.cache/p34-cycle-recovery-v2-tests-r3/result.json`, 12 passed. These include real
collector constructor/confirmation transitions and a zero-device-command resume
of the original completed confirmation. No new OTA was used for verification.

The completed five-transfer screening successor is
`.cache/p34-cycle-checkpoints/screening-summary-v2.json`; the first summary stays
unchanged. The next 115200/460800/921600 asset group is described in the existing
screening task note. The old runner's pinned APK/endpoint/package are historical
inputs, not a ready entry for that new firmware group.
