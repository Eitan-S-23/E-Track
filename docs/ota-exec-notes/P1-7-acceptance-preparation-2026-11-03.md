# P1-7 Acceptance Preparation

Status: PREPARATION ONLY, NOT_ADJUDICATED. The user requested P1-7 execution and
pre-authorized necessary task operations. This turn did not reset, halt, flash,
run OTA, write device persistence, or make Git metadata changes.

## Current Identity And Reuse

The preceding passive readiness observation is
`.cache/p17-readiness-20261103-01/inspect-01/result.json`. It confirmed the complete
30313 App, the retained physical Boot, advancing confirmed App health and idle
storage/OTA. It is not a P1-7 timing, recovery-key or battery observation.

Physical Boot64 SHA256:
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.

The 30313 CI package's default 14724-byte Boot is NOT this physical Boot. It must
not be used for address resolution or silently installed to simplify acceptance.
The actual first 14800 executable bytes exactly match the historical group16
Boot at `D:/github/my/E-Track/.cache/p34-bc-target/b16/boot/`; the remaining bytes
through 16KiB are erased. The preserved 16..64KiB suffix is not a programming
target. This original directory was read only, never modified.

Copied Boot BIN/ELF/map and original objcopy/nm/objdump command receipts are in
`.cache/p17-acceptance-20261103-01/prepare-01/`. ELF conversion equals the BIN;
BIN equals the physical executable prefix. The executable size is 14800 bytes,
below 65536; actual clock behavior still requires Boot-phase observation.

## Prepared Observation

`Tools/acceptance/p17_observe.py` reuses `live_host` and `live_mcu`, including the
standard SEGGER Commander, output guards, Windows Job ownership and device lock.
There is no new Flash driver, firmware modification or transport controller.

The proposed startup cell checks complete current images and health, stops at
the existing storage-idle App boundary, and performs one reset/start. It samples
RTT signature, PD2, VTOR, CRM registers and exact Boot clock/tick symbols. SDK
entry/return timestamps provide observation bounds rather than nominal sleep
durations. PLL multiplier and dividers are decoded against the original 8MHz
reference. Post-start PD2 sampling continues at least 3 seconds past the first
RTT signature. Normal confirmation and complete retained-image checks follow.

This cell can supply startup, sampled power-hold continuity, clock and tick-rate
observations. It does not test the physical recovery key or battery-only startup.
Clock register decoding is not oscillator metrology; sampled PD2 continuity is
not a scope-level exclusion of arbitrarily short glitches.

The production recovery-key function only executes in the fault-recovery path.
Do not corrupt App/backup/recovery or rewrite BCB merely to reach it. The safe
isolated key observation method still needs to be selected and bound before its
execution. Battery-only startup still requires the user's cable/power action.

## Host Checks And Admission

Fourteen offline tests pass. Exact stdout/stderr, closed command receipt and
source hashes are in `.cache/p17-acceptance-20261103-01/host-tests-01/`.
They cover raw native bytes, incomplete/short reads, nonmonotonic clocks, normal
timing, delayed startup, PD2 drops, stale RTT, missing samples, repeated resets,
accelerated Boot ticks, bad PLL multiplier/divider and bounded sampling.
These are harness checks, not device criteria or overall P1-7 acceptance.

The early `prepare-01/plan.json` predates the final parser/admission edits. Keep
it as preparation history and create a new bound plan after source review and
commit; do not bypass its stale source pin or overwrite it.
The runner requires a FROZEN P1-7 contract and NOT_RUN matrix, then invokes the
canonical validator before device ownership. No contract was frozen this turn.

## Remaining Authority Boundary

The active writable root remains
`D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Git resolves shared metadata to `D:/github/my/E-Track/.git` and this worktree's
metadata to its `worktrees/source1/` child. The earlier P3-5-specific commit
allowance is not silently extended to P1-7. Under the user's explicit filesystem
rule, the specific shared-directory write scope needs confirmation once.

Requested scope is P1-7 local source/evidence/closeout commits: objects, the P1-7
task ref/reflog, and this worktree's metadata. Exclude the main ref/index/worktree,
unrelated files, push, merge, release, global configuration and hook edits.
Existing hooks and all unrelated dirty/untracked contents must be preserved.

All agent-chosen writes this turn are the two new source/test files, this note,
and the new project-local preparation tree. A global `git diff --check` found
pre-existing whitespace in PLAN-OTA-EXEC.md; it was not changed or cleaned.
No project-external write, device operation or task completion is claimed.

## Subsequent Explicit Git Authorization

The user subsequently answered "allowed" to the exact shared Git directory and
P1-7 local-commit scope above. That boundary is now authorized for this task.
Proceed on a separate local P1-7 task branch, preserving main and unrelated work.
No additional approval is needed for each same-scope local commit. This update
does not turn preparation tests into device acceptance or authorize remote writes.

## First Physical Observation And Offline Parser Repair

The admitted first cell executed once after FROZEN/NOT_RUN precheck passed.
Source commit: `ad85298dde3efa08a5ff13935b208edfb64b1fc2`.
Original bundle: `6fc4687018942bcffd7201a0ac732fd2d302294d`.
Parser repair: `95ced4719becde765655fa9eaae3a426cf26f769`.
Branch: `acceptance/p1-7-20261103`, local only. No main change or push.

Complete image/health checks, storage-idle breakpoint, one reset/start, 200
six-field sample sets, normal settling, and complete post-image/health checks
executed. The runner then failed in offline interpretation: native Commander
uses GoEx and ReadMemU32_64, whereas the first parser covered Go and ReadMemEx.
The original exit 1 and HARNESS_FAIL matrix remain unchanged and were validated
before changing the parser. No physical measurement was repeated to fix parsing.

The amended parser normalizes only API naming and item-versus-byte counts.
Seventeen host tests pass, including the actual native original and rejection
controls. Offline review rehashed all declared originals and verified that all
159 Git blobs inside the first evidence package equal their original file bytes.
Native CRLF and trailing spaces were preserved using package-local attributes;
the earlier whitespace-check failure was not repaired by altering raw evidence.

Results from those same original samples:

- CPU release (GoEx) to fresh RTT signature: 1446.335..1478.732 ms. The committed
  pre-observation oracle uses this running interval, not a post-hoc timing change.
- Including the debugger reset API invocation overhead, the upper bound is
  1564.947 ms. Keep this different host timing scope explicit; do not present it
  as <=1500 ms or silently conflate it with reset release.
- PD2 first high is bounded by 984.409..1015.716 ms after GoEx. No later sampled
  low among 200 sets; samples extend 3975.944 ms past the first signature. The
  largest inter-read gap is 28.711 ms, not continuous oscilloscope coverage.
- Fifty-one Boot-phase clock samples decode PLL source/multiplier/dividers to
  nominal 288000000 Hz; the exact executable is 14800 bytes.
- Boot ticks advance 1371 over a 1364.4875 ms native-clock interval, ratio
  1.004772854. This is clock/tick calibration, not a measured recovery-key hold.
- Post-reset App/Boot match the full originals, BCB snapshot is CONFIRMED,
  main-loop/watchdog health advances, SD is ready, and CFSR/HFSR are zero.

Machine-readable review: `P1-7-startup-observation-2026-11-03.json` alongside this
note. This is a verified original-observation report, not overall P1-7 PASS and
not a retroactive change to the first contract's HARNESS_FAIL verdict.

The failed runner retained its device lock after the parser exception. The
reviewer verified the original successful postcheck, all closed receipts and
absence of the owner/debugger processes, archived the lock, then released only
that owned lock. This reconciliation added zero device operations.

## Next User Observation

Remaining actual conditions are recovery-key short/long behavior and battery-only
power-button startup. Do not emulate the first by holding the key during an
ordinary valid-App boot; that path correctly never invokes the recovery predicate.
Do not damage images or BCB just to reach it. Its isolated method remains pending.

For the battery observation, the board is verified and all owned tools are closed.
Ask the user to shut down normally, disconnect both USB and J-Link from the device,
start on battery using the normal power button, release it, and observe normal
operation for 30 seconds. Preserve the user's exact report/video as a user-owned
observation and bind it to the pre/post identity; do not claim the agent directly
observed an unplugged device. No user battery result has been received yet.

Keep P1-7 in progress. A final same-task supplemental evaluation must include the
missing observations, preserve the first failure and exact timing scopes, and
complete admission/validation without repeating the successful startup capture.

## Autonomous Follow-Through And Explicit Formal Blocker

2026-11-03: the user requested the remaining work that does not need physical
intervention. Existing observation evaluation and host preparation proceeded,
without another reset, flash, OTA or debugger session.

The new offline entry `Tools/acceptance/p17_review.py` verifies the exact first
contract/matrix, all declared originals, native timestamped samples, full before
and after images, original health buffers and 17 original command closures.
It calls the existing pure parser/health checks, never a device entry.

P17-ENTRY-01 is CLOSED. Its first committed entry (`e1898b05a30ceacf5fd9b35b41ed46c73356a05c`)
passed import-based tests but failed the real isolated CLI: Python -I excludes
the script directory, so the sibling parser could not be imported. This was a
reviewer-written harness mistake, not firmware regression or network trouble.
The original command actually exited 1 before evaluating any original. The
failure and unchanged copied originals were committed as
`138303c3d4cd83ea4da524d0d4183ca31bba678c`, P1-7-v2. They must not be relabeled
as successful execution or as an unexecuted NOT_RUN predecessor.

Repair `d665f92a45889b95bd433c80194297a3789bda70` explicitly adds the local module
directory and adds a real isolated CLI test. All 22 Python tests pass (17 existing
parser tests and 5 evaluator tests, including seven tampering subcases). The
corrected CLI was also actually executed on the same original bytes. Results:
three scoped startup criteria PASS, recovery-key and battery NOT_OBSERVED.
Machine-readable result: `P1-7-offline-followthrough-2026-11-03.json`.
Exact logs/source pins: `.cache/p1-offline-20261103-01/host-02/` and
`offline-corrected-01/`. This standalone review is not formal successor admission.

P17-RECORD-01 remains NEED_DECISION, a formal recording limitation exposed by
the reviewer's failure. The new frozen v2 command declares expected_exit_codes
[0], but its actual failed invocation is 1. The canonical validator rejects even
a HARNESS_FAIL matrix with that unexpected exit code. Its exact rejection is
preserved in `.cache/p1-offline-20261103-01/record-import-failure-01/`.
v2 precheck/rerun-plan generation passed; final validation did NOT pass. No
FREEZE-INDEX row or whole-card acceptance is claimed for v2. The failed native
stderr also triggered whitespace checking; its exact staged bytes were verified
and excluded only from whitespace checking, not from any evidence verification.

Do not edit frozen v2 to add exit 1, replace the actual exit with 0, substitute
the old NOT_RUN matrix as predecessor, or skip v2 by reusing v1 as the immediate
parent. These would conceal the real execution history. Fixing the import does
not by itself resolve this formal-history issue.

Recommended next decision is a narrowly approved correction to failure-record
handling in the shared execution contract/validator: an unexpected actual exit
may be recorded as failure with original output and a failed criterion, never
as PASS or a reusable PASS anchor. Keep strict exit-code admission for PASS,
strict command text, original history, artifact hashes and all product gates.
Tests must cover unexpected exit with failure, rejection with PASS, missing
output, and actual predecessor lineage. A new P1-7 successor then binds the
corrected evaluator and the actual v2 HARNESS_FAIL predecessor. Because this
changes common acceptance governance beyond the local P1-7 source/evidence
scope, this session did not silently implement it or rewrite any frozen file.

Six additional host cases compiled the unchanged production recovery predicate
with stubbed GPIO/time and passed with zero compiler warnings/errors. They prove
logic only, not a physical recovery-key hold. The power-cut feasibility review
also found no qualified autonomous rail-cut/restore fixture. Details and P1-6
original-location findings are in `P1-autonomous-review-2026-11-03.md`.

P1 remains 5/7. Physical key and pure-battery startup are still unobserved. All
local P1-7 commits stayed on acceptance/p1-7-20261103; main and its index were
preserved. No push/merge, device operation, product edit or external cleanup.

## Authorized Failure-Record Correction And v3 Closure

2026-11-03: the user explicitly approved the proposed limited common-validator
failure-record correction. P17-RECORD-01 is now CLOSED; this supersedes the
NEED_DECISION/formal-blocker status above without changing its historical facts.

Source: `7146a0060230cb99b818f6a1c1b669379b5e03e9`, branch
`acceptance/p1-7-20261103`. Execution contract section 4.1 and validate_matrix now
allow an unexpected integer exit only in a non-PASS final record with a directly
consuming EXECUTED FAIL criterion, no consuming PASS criterion, and hashed actual
command output even if output was originally optional. Command identity,
provenance, artifact checks, failure ownership and all product gates are unchanged.
An unrelated failure, NOT_OBSERVED or REUSED record cannot authorize this exception.
Explicitly approved nonzero negative-test success codes retain their old meaning.

The new 8-test group first reproduced the failure, then passed with the fix.
Its first green attempt exposed an error in the new test fixture's use of a
canonical JSON hash instead of the actual predecessor file hash; the fixture
call was corrected, with the failed run preserved. The full acceptance bundle,
acceptance efficiency, P1-7 parser and P1-7 evaluator suites then passed all 203
tests with no skips. This is local host regression, not a CI or hardware campaign.
Exact red/green/full logs and old validator bytes are included in the v3 bundle's
`policy-correction/` directory. Working receipts are under
`.cache/p17-record-20261103-01/`.

P1-7-v3 freezes the corrected source and uses the actual v2 HARNESS_FAIL matrix
as its immediate predecessor. The original v1 observation remains a distinct
hash-bound raw input. Both old bundles, actual exit codes, and the old validator
rejection remain byte-identical. The new rule makes that failed record
representable; it does not claim the old invocation or old validation succeeded.

FROZEN/NOT_RUN precheck and the computed rerun plan passed. One admitted offline
original-evaluation command executed, followed by successful final validation.
Result: C-STARTUP, C-POWER-HOLD and C-CLOCK-SIZE are EXECUTED PASS for this offline
evaluation; C-RECOVERY-KEY and C-BATTERY are NOT_OBSERVED. Overall EVIDENCE_GAP.
The CPU-release 1478.732 ms upper bound and reset-API-inclusive 1564.947 ms upper
bound remain separate, and sampled PD2/nominal PLL limitations remain explicit.
The standalone prior review has not been retroactively declared an admitted run.

Bundle: `28e1a9e0542ae6b274ba7961b6eb919e6c6bacf4`.
Contract: `docs/acceptance-contracts/P1-7-v3.contract.json`.
Matrix: `docs/acceptance-contracts/P1-7-v3/final-matrix.json`.
This is the local evidence closeout, not whole P1-7 completion or main delivery.
The freeze index is appended only after the bundle commit. To reproduce final
validation at the bundle commit, use the same existing validator with:

    python -I -S -B -X utf8 Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P1-7-v3.contract.json --matrix docs/acceptance-contracts/P1-7-v3/final-matrix.json --repo-root . --previous-contract docs/acceptance-contracts/P1-7-v3/predecessor/contract.json --previous-matrix docs/acceptance-contracts/P1-7-v3/predecessor/final-matrix.json

Remaining product work is unchanged: actual recovery-key short/long behavior,
pure-battery startup, and P1-6 original retrieval/physical power-cut obligations.
No reset, flash, OTA, device collection, remote CI, push or merge was performed.
Common rules and this handoff remain pending authorized main integration; other
worktrees must not be described as already updated by this local commit.

## P17-BATTERY-01: User Reports Normal Battery-Only Startup

2026-11-03: the user reported that the requested battery-only startup check was
performed and everything was normal. The exact Chinese response is preserved in
the P1-7 card in PLAN-OTA-EXEC.md. This is a user-owned firsthand observation,
not an agent-collected video, debugger measurement or new firmware readback.

The immediately preceding instruction was to disconnect board USB and all J-Link
connections, power on with the battery, release the power button after about two
seconds and observe for one minute. The user was asked to report normal entry,
continued operation after release, and any unexpected shutdown/restart. Their
response reports success for that check; the durations are requested procedure,
not independently measured timestamps. No battery voltage, current or endurance
measurement is inferred. The user declined video, and no video or repeat startup
is requested as a condition of recording this observation.

The last agent-verified binary identity before this user action was the retained
30313 App and group16 Boot in
`.cache/p16-usb-cycle-20261103-01/run-01/result.json`. It is contextual identity,
not a fresh post-battery readback. No debugger was reattached for this update;
any later attachment must account for the newly connected battery and avoid
parallel probe-power injection.

Disposition: battery-only startup is now USER_REPORTED_NORMAL rather than having
no user observation. This operational annotation is not a new formal matrix
result taxonomy. Preserve the actual report and prior identity for supplemental
review; do not manufacture instantaneous logs or change the frozen v3 matrix.
Physical short/long recovery-key behavior remains outstanding, and P1-7 is not
closed. A normal valid-App startup does not test the recovery predicate.
P1-6 power-cut gaps and the current formal P5 entry requirements are unchanged.

Only this existing note and the local task-board annotation were edited. No
device operation, repeated startup, build, Git write, network operation or
project-external output was performed in recording this user result.

## P17-KEY-01: Battery-Powered Debug Connection Preparation

2026-11-04: the user asked whether J-Link must stay disconnected and requested
notification when physical intervention is needed. J-Link debugging is needed;
the old probe power-output feed must not be paralleled with the new battery
supply. Battery-only startup has already been reported normal and is not repeated.

The exact retained Boot BIN/ELF/map hashes were checked again offline. Existing
native disassembly identifies boot_platform_recovery_key_held at 0x08001E6C,
g_boot_millis at 0x20001030, and the instruction immediately after platform init
at 0x080019AA. The key function reads PA15, returns false when released before
3000 ticks, and returns true only while held at that threshold. It has no direct
storage-writing path. These are offline method inputs, not live-state evidence
or authorization to jump the PC without a validated bounded caller/restoration.

Battery supply adds a prerequisite absent during probe-powered observations:
reset/platform initialization withdraws PD2 power hold for the initial one-second
interval. A reset therefore needs coordinated physical key holding to sustain
battery supply. Do not issue an unattended reset on the assumption that removing
the probe's supply has no effect on the old startup procedure.

Next action is only a passive connection/identity check using the existing
Commander adapter after the user connects debug signals. Board header H2 pins
3/4/5 are SWCLK/SWDIO/GND. Leave the former power feed at H2-6 disconnected;
UART pins 1/2 are unnecessary. The board must already run on battery. A separate
probe VTref input is not a power output; do not guess or bridge it to the old
feed. If voltage reference is required and the probe refuses to connect, stop
and identify that probe-side connection rather than reintroducing dual supply.
An inseparable cable needs clarification before being plugged back as a whole.

Do not request short/long key presses until the bounded predicate-call and safe
exit method is qualified. No App/backup/recovery corruption or BCB modification
is permitted to force the real recovery branch. Host predicate checks and the
new user battery report remain separate from the missing physical key result.

This preparation only read existing sources/artifacts and edited this note.
No debugger attachment, reset, key call, build, network operation, Git write,
notification API call or project-external output occurred. The current reply
requests wiring confirmation, so it uses the bridge's normal completion notice,
not a duplicate manual mention or a claim of future unattended monitoring.

### P17-KEY-01 Passive Attachment After User Wiring

2026-11-04: the user confirmed the requested wiring was completed: battery-powered
normal operation, J-Link USB to host, H2 SWCLK/SWDIO/GND only and the old H2-6
power feed disconnected. Perform a fresh passive inspection, not a key test.
The thin caller in `.cache/p17-battery-debug-20261104-01/inspect.py` reuses the
previous verified readiness function with only its new output AREA redirected;
it does not run any spent device mutation or overwrite old results.

The existing adapter checks exclusive device ownership, pinned tools/images,
complete App/Boot bytes and initialized health/storage state. One native read
session is bounded at 300 seconds. Its command files, native logs, readbacks,
home/AppData/temp/cache and receipts stay inside that new worktree-local tree;
the scoped native SEGGER history exception remains unchanged. No reset, halt,
Flash/EEPROM write, OTA, USB cycle, GPIO override or recovery-key call is allowed
in this attachment check. A connection/reference failure stops this route without
reconnecting the probe's power output. Actual result is recorded separately.

### P17-KEY-01 Attachment Result: Target SWD Not Connected

2026-11-04: host USB successfully opened the same ARM-OB STM32 J-Link, but the
1000 kHz standard AT32F435RGT7 connection failed at InitTarget with
"Failed to initialized DAP". No target memory readback was created. A single
changed-speed discriminator at 100 kHz attempted only a four-byte CPUID read;
it failed at the same DAP step and produced no CPUID bytes. The two actual
failures are preserved, not repeated as an unchanged retry or hidden as PASS.

Originals: `.cache/p17-battery-debug-20261104-01/inspect-01/` and
`probe100-01/`, including scripts, native SDK logs, stdout/stderr and results.
Both print VTref=3.300V, but that alone cannot establish this probe's actual
target-supply wiring, a distinct voltage-sense input or a live MCU rail.
Do not reconnect H2-6 or infer that a reference-voltage wire is certainly missing.

Eight owned host command receipts are closed, including the two failed Commander
commands. No reset/halt/write native APIs were found, no target bytes were read,
and the device-owner lock was released. No key observation was attempted, no
firmware was changed and the earlier user-reported battery test is not invalidated
by this separate debug-connection failure.

Next required user observation: is the board still visibly running its normal
screen with the three debug lines connected? If not, resolve battery/run-state
before attempting SWD again. If yes, inspect signal/ground contacts and the exact
probe-side pin labels/reference arrangement; do not guess the power connection.
No further reset, reconnection of a power output or automatic retry is scheduled.
Chosen outputs stayed in the new local directory and this note; only the existing
native SEGGER history exception was available outside the active worktree.

### P17-KEY-01 User Clarification: Board Was Off

2026-11-04: the user clarified that the board had not been switched on during
the two failed connections above. The agent had failed to confirm this physical
precondition. Those failures therefore do not establish bad wiring, missing
voltage reference or broken debug capability. The user subsequently confirmed
normal battery power-on while retaining the three debug wires and no H2-6 feed.

Run the same passive 1000 kHz inspection once under this changed power state,
using `.cache/p17-battery-debug-on-20261104-01/`. Preserve the previous failures;
do not change speed, reset, flash, reconnect power or invoke the recovery key.
The previous tool/output guards, 300-second native read bound, exclusive owner
and native SEGGER-history exception remain applicable. Record the actual result
before proceeding to any device mutation or user key request.

### P17-KEY-01 Powered Attachment Still Fails At DAP

With user-confirmed battery power-on, the new 1000 kHz passive inspection still
failed at DAP initialization before any target readback. A single powered-state
100 kHz CPUID-only discriminator failed identically. These are saved under
`.cache/p17-battery-debug-on-20261104-01/inspect-01/` and `probe100-01/`.
The earlier 100 kHz attempt was made while the board was off and therefore could
not distinguish powered link behavior. No further unchanged retry is planned.

Both powered attempts opened the J-Link over USB successfully, so host USB
enumeration is not the failed stage. The actual cause of SWD failure is still
unknown: signal/ground contact, probe-side pin mapping and voltage reference must
be checked, not inferred from the printed VTref=3.300V. The proposed three-wire
connection has not been demonstrated to work on this actual probe/board setup.

Next required input is the J-Link-side connector labels and actual wire mapping,
especially which labeled pin carried the former H2-6 feed. A text description
or one still photo is sufficient; do not request video, plug the power feed back
without identifying it, or modify the board/firmware to mask a connection fault.

Eight owned command receipts closed (two connection commands exited nonzero).
No MCU readbacks, reset/halt/write native APIs, key call, flash, power cycling or
firmware change occurred. The owner lock is released. All controlled outputs are
under the new active-worktree directory plus this note; the native SEGGER-history
exception is unchanged. The prior user battery observation remains preserved.

### P17-KEY-01 User Reports Shutdown When Keil Queries J-Link

2026-11-04: the user reports normal battery operation without a debugger query,
but the board shuts off when viewing J-Link information in Keil and needs the
power key to start again. This is the user's separate Keil observation, not a
measured timestamp correlated with our earlier Commander log. The user declines
further photo requests; do not request a picture/video or repeat the same Keil
action simply to reproduce this report.

The earlier description of H2-6 as a proved probe power OUTPUT was too definite.
The board-side net is 3V3_MCU; the probe-side electrical role is still unknown.
Do not infer that disconnecting it is certainly the cause, or reconnect it as
an assumed VTref input. Printed VTref=3.300V is not a measured rail observation.

Offline review confirms that the saved Commander commands contain no explicit
reset/halt/programming command, and fail inside AT32 InitTarget before savebin.
This does NOT prove that opening/initializing the probe has no electrical or
implicit reset side effect. The retained Boot disassembly explicitly resets PD2,
waits 1000 ms and sets PD2 again; reset-induced loss of battery power hold is a
plausible mechanism, not a proved cause of the reported Keil shutdown. No rail
measurement or reset-cause readback exists for the event.

Read-only Windows file-version inspection found Keil's installed JLinkARM.dll
at D:/install/keil5 mdk/ARM/Segger/ is 7.90.0.0, while the bounded Commander route
uses 8.18.0.0. The exact modules loaded by the user's running Keil were not
enumerated, and a version mismatch is not a diagnosis. Do not update/replace
either driver or probe firmware speculatively. Saved project options also do
not prove the exact live settings/dialog action. Online manual lookup reached
the Keil index but not usable debug-page text; no undocumented reset behavior
is claimed on that basis.

Next discriminator is PREPARED_NOT_RUN: open the USB probe and quit without
issuing MCU connect, memory access, reset, halt or Flash commands. The three-line
script is .cache/p17-probe-open-20261104-01/commands.jlink. Existing saved logs
show that SetRestartOnClose opens the USB probe before the separate connect
command; reuse that prefix with DisableAutoUpdateFW, AutoConnect=0 and qc.
This isolates the probe-open phase; it is not guaranteed electrically inert.

Use the pinned Commander/serial from the last passive plan, existing live_host
environment/process/lock primitives and a fresh run-01 subdirectory with native
settings, SDK log and command receipts. Bound the Commander at 15 seconds with
no automatic retry. Before running, preflight every output, check both roots'
device-owner locks, confirm no other debugger owns the probe (including Keil),
and obtain the user's readiness with normal battery operation and unchanged
three-wire connection. No held-button timing is requested for this cell.

The immediate user action is to close Keil completely, leave wiring unchanged,
and start the board normally only if it is off. After one probe-open command,
obtain a simple stayed-on/shut-off observation. If it shuts off, stop target
connection experiments and investigate probe/interface electrical initialization.
If it stays on, the next candidate is a separately prepared minimal target-connect
discriminator, not proof that the full old attachment route is now safe. Absence
of a user observation or an unexpected native target-connect call stays unknown.

This update performs no probe access, hardware experiment, driver installation,
firmware edit, Git write or old-evidence edit. Chosen writes are only this note
and the new three-line script in the verified active worktree. The manual fetch
used memory/stdout only. User readiness is requested in the final reply; there
is no background device worker or duplicate manual completion mention.

### P17-KEY-01 Probe Open Completes; User Reports Board Stayed Lit

2026-11-04: after the user's readiness confirmation, the planned single
probe-open-only command completed with exit code zero. Originals are under
.cache/p17-probe-open-20261104-01/run-01/. The native SDK log records one USB
probe open and no JLINK_Connect or InitTarget, and no target read/reset/halt/write
API was observed. Three owned command receipts are closed, no competing debugger
remains in the final process list and the worktree device lock is released.

The user subsequently confirms that the board stayed lit throughout. This is
retained separately in user-observation.json; the original result.json's pending
observation is not overwritten. The visible observation is user-reported, not
a rail-voltage measurement or an agent-verified no-reset uptime trace.

Decision: host-to-probe USB opening and metadata retrieval work in this tested
Commander route without a reported shutdown. Target SWD communication is NOT
yet demonstrated after the battery rewiring; the earlier DAP failures remain
unresolved. Keil's exact dialog sequence and reset as the shutdown mechanism
are still unverified. Do not describe J-Link debugging/programming as repaired,
nor conclude that every probe-open path or Keil version is now qualified.

The next useful device check would isolate minimal target attachment from this
successful USB-open phase, without replaying full image reads or changing the
power wire. It still requires a prepared bounded route and board-state recovery;
the present user question is not treated as an instruction to start that check.
No additional device command was issued while recording this observation.
This update writes only this note and the separate user observation inside the
verified active worktree. No product edit, driver replacement or Git write.

### P17-KEY-01 Generic Target Attachment Discriminator

2026-11-04: the user authorizes proceeding after the successful probe-only
opening and user-reported continuously lit screen. One new connection attempt
uses the installed Commander's standard CORTEX-M4 profile instead of the earlier
AT32F435RGT7 device-specific InitTarget route. SWD, 1000 kHz, probe 123456 and
the exact pinned V8.18 executable remain unchanged. No new driver, custom SWD
implementation or probe firmware is installed. This is a changed-profile
discriminator, not a repeat of either failed full-image read.

New scope is only connect then quit: no explicit memory-dump, reset, halt,
register-write, Flash/EEPROM, recovery-key or power-cycle command. Native target
attachment can itself access debug registers and need not be electrically inert;
do not represent this as zero MCU interaction or guaranteed no implicit reset.
DisableAutoUpdateFW, SetRestartOnClose=0, InhibitConnectRetries=1, AutoConnect=0
and a 15-second command deadline are retained. No fallback retry is scheduled.
The user was asked to observe whether the screen goes off during this attempt.

Use the existing live_host contained environment, Windows Job and exclusive
device-owner lock. Original script and fresh native receipts/settings/logs stay
under .cache/p17-generic-connect-20261104-01/. Every controllable output and the
existing local lock is preflighted; the standing native SEGGER history exception
is unchanged. Check both roots' locks and exclude Keil/other debugger owners.
If attachment fails, preserve the failure and stop. If it succeeds, report that
connectivity only; do not proceed to image reads or the physical key test before
reconciling the user's visible board state. An unknown outcome stays unknown.

Result: the single generic-core connection completed successfully (exit 0).
It found SW-DP 0x2BA01477, AHB-AP 0x24770011, CPUID 0x410FC241 and identified
Cortex-M4 r0p1. Originals are in run-01/result.json, commander.stdout and sdk.log
under the new directory. The native log contains one JLINK_Connect call, and
reports the old probe firmware lacks DPIDR reading via DAP jobs before proceeding
successfully through the generic route. This is not proof of the exact cause of
the earlier AT32 InitTarget failure or the user's Keil shutdown.

The statement that this check would not read memory meant no explicit memory
dump; standard native attachment did read identification/debug registers. The
SDK also records automatic CPU_WriteMem at DHCSR (0xE000EDF0), DWT_CTRL
(0xE0001000) and CPACR (0xE000ED88). These must not be misreported as zero target
writes. No explicit reset/halt/programming command was sent, and no reset/halt
API marker was observed; no absence-of-electrical-side-effects claim follows.

All three owned command receipts closed, the final debugger process list was
empty and the owner lock was released. Controlled outputs were audited inside
the new worktree directory; the permitted native SEGGER history exception was
unchanged. Generic three-wire target communication is now demonstrated in this
one connection. Firmware identity/integrity, Keil compatibility and full debug/
Flash operation have not been newly verified. User observation of the screen
is still PENDING; no further device operation is started pending that report.

The user then reports that the board remained lit throughout and requests
continuation until real physical intervention is required. That report is stored
separately in the generic connection's user-observation.json; no old result is
rewritten. Proceed with passive current-image/readiness verification through
the same generic profile, not the failed AT32-specific initializer.

The new .cache/p17-generic-readiness-20261104-01/inspect.py is a thin adapter
around the unchanged previous preflight/MCU checks. Only the Commander's device
argument changes to CORTEX-M4; the existing full App/Boot, health, confirmation,
storage and stack gates remain. Explicit commands are allowlisted to existing
read-only startup settings, connect, savebin, sleep and quit. Native attachment's
debug-register writes remain disclosed. No reset/halt/Flash/EEPROM/key call or
firmware change is scheduled. Preserve all failed and successful old originals.

The adapter uses a fresh inspect-01 tree; preflight maps the previously verified
readiness outputs into this new root, plus the adapter/binding, this note and
the separate user observation. Existing contained process/environment/lock
primitives and the native SEGGER history exception remain unchanged. A successful
read may unblock offline preparation of the physical predicate call; it does
not grant P1-7 PASS or authorize forcing recovery by corrupting persistent state.

### P17-KEY-01 Readiness Restored; Prepared Physical Key Window

2026-11-04: generic-profile full readiness succeeded in
.cache/p17-generic-readiness-20261104-01/inspect-01/. Complete App 30313 and
Boot64 hashes still match the retained originals; confirmation, advancing main
loop/watchdog health, SD, idle OTA/storage, fault registers and stack guard pass.
The adapter's offline checks covered profile substitution, unchanged input argv,
reset rejection, non-Commander command preservation and Keil exclusion. This is
not a new P1-7 startup/reset campaign or a firmware repair.

The existing one-shot Commander wrapper cannot promptly react to a short human
press when every poll opens a new process. A small interactive Commander adapter
was therefore checked in .cache/p17-key-method-20261104-01/native.py; it reused
the installed CLI, existing contained environment, Windows Job and device lock,
not an SWD protocol/Flash implementation. Its memory decoder/prompt tests passed,
but the real redirected-pipe attempt buffered the initial prompt until exit.
qualify-01 preserves this host failure and the native originals. It opened the
probe but never issued JLINK_Connect or touched MCU memory. Native close exited
zero. After confirming the Python owner was gone and no debugger remained, only
that dead owned lock was archived/released in lock-reconciliation.json. This
interactive-pipe route is abandoned; do not rerun or grow it into a PTY framework.

The supported GDB route already used by tests/ota/p2_6_rtt_ota_driver.py provides
hardware breakpoints, synchronous inferior calls and built-in condition loops.
Installed GDB 14.2.90 lacks embedded Python and the proposed direct-call timeout
features; exact host output is retained in host-tools-01. No replacement GDB,
driver or probe firmware was installed. The prepared method uses ordinary GDB
commands and the existing live_host bounded processes instead of those features.

gdb-qualify-01 actually connected the generic CORTEX-M4 GDB server to this MCU,
read CPUID 410fc241, disabled Flash breakpoints and detached normally. SDK output
shows that GDB reading common registers briefly HALTS the MCU despite -nohalt
at server startup; this is not a halt-free route. It resumed through GoEx on
detach. There was no reset, Flash programming or key call; probe firmware stayed
the same ARM-OB STM32 2012 image. Every GDB/server receipt closed and all four
private ports closed. Do not infer that disconnect on an error necessarily leaves
the core halted just because SetRestartOnClose=0 was sent.

Because that attachment halted the MCU, a fresh post-check was completed under
.cache/p17-gdb-post-20261104-01/inspect-01/. Full retained App/Boot and the original
health/storage/stack gates again pass, with debug freeze restored to zero. This
is the final observed board state for the current continuation, not an assumed
safe detach. No automatic further hardware operation remains running.

Prepared physical-method entry (NOT_RUN):
.cache/p17-key-method-20261104-01/key-plan-final.json, gdb-definitions-03.gdb and
gdb-key-03.gdb. Definitions 01/02, their generators and original hashes remain
unchanged. gdb-check-02 caught literal quotes in GDB's set-logging filename
argument, before any physical key work; its stderr/absence of a stage file are
preserved. gdb-check-03 actually loads the corrected definitions, creates/closes
a synthetic stage file, and checks guard/order/restore structure against the
original Boot and actual GDB register names. No key predicate was executed by
these host checks, and host preparation is not a physical PASS.

The bounded planned window is one reset and two isolated calls to unchanged
Boot predicate 0x08001E6D in initialized Boot context, with a 240-second GDB
window and at most 60 seconds for each requested human transition. Subsequent
normal Boot settling and generic full verification have their own existing
bounded allowance (up to 300 seconds), not a shortened remainder of that window.
First stop at the known storage-idle HAL boundary, confirm current state/header,
and ONLY THEN prompt the user to hold the physical power key. The held key keeps
battery power through reset and Boot's initial PD2-low second. Stop at 0x080019AA
after platform init, before QSPI/state-machine/recovery execution.

Verify Boot vectors, 288MHz/tick configuration, physical PA15 input/pull-up,
PD2 high, aligned MSP, thread/Thumb state and enabled interrupts. Save normal
and special CPU registers plus 512 bytes of scratch below SP. With the first
hold maintained, call the predicate and require true with >=3000 Boot ticks;
then prompt release, wait for actual PA15 release, prompt an approximately
one-second press/release, and require false with a positive <3000-tick interval.
GDB's normal inferior-call mechanism and hardware return breakpoint must return
to the exact original PC/context after each call. No GPIO spoof, timer write,
image corruption, BCB edit or recovery receiver invocation is part of this method.
Restore scratch and the original watchdog debug-freeze value, detach into normal
Boot, and verify full retained images/health before reporting a successful cell.

The first actual call remains to be qualified in this physical window. On an
unexpected stop, timeout or bad context, stop the batch, preserve native logs,
close owned processes, retain the device lock and reconcile actual PC/state
before any continuation. Do not blindly resume/reset, bypass a failed context
check, repeat a completed hold to repair logs, or relabel the old frozen bundle.
The original three accepted startup criteria and the user-reported battery-only
startup are not re-executed. Overall P1-7 is still not closed.

Current stop is for actual user participation, not more project/driver authority:
the user needs to be ready beside the board for the hold/release/short-press
prompts. Do not ask them to press now while the App is still running. No task
worker is left waiting in the background; start the bounded window only when
the user is available. Use the existing current-session notification policy for
in-window physical prompts, without duplicate completion mentions or photo/video.

Chosen writes in this continuation are this note, the generic connection's new
user observation, and the new generic-readiness/key-method/GDB-post directories
under the verified active worktree. Controlled cache/home/temp/settings/log paths
were contained. Only the standing native SEGGER-history exception was available
outside it. No product edits, commit/push/merge, OTA, firmware build/installation,
USB power cycle, explicit target reset, key call or old-evidence rewrite occurred.

### P17-KEY-01: Physical Predicate Observations And Retained-State Closure

2026-11-04 Asia/Shanghai: the user was ready beside the board and authorized the
prepared window. The physical observation and final device restoration are now
complete. Entry: `.cache/p17-key-method-20261104-01/closeout-01/result.json` and
`files.json`; successful native originals are in `gdb-key-03/`. This supersedes
the preceding NOT_RUN state for this observation only, not the frozen v3 matrix.

The same-session Feishu requester was resolved from the current runtime session
key, not a historical chat. Actual hold/release/short reminders used cc-connect
send and real mentions; each received a successful send receipt. GPIO observations,
not a chat acknowledgment, advanced the test. IDs and session keys were not
printed or written into command receipts. No duplicate final notification was sent.

Two preparation failures are retained. `gdb-key-01` opened the generic server but
GDB failed to source a quoted filename before attaching, resetting or calling
anything. Unquoted source syntax was checked offline; a host check initially
misclassified GDB's valid `User-defined.` help text, then accepted the unchanged
original without rerunning it. `reconcile-01` verified complete images and health
before releasing that dead owned lock.

`gdb-key-02` reached the idle App checkpoint, observed the real held key, reset
once and reached initialized Boot at 0x080019AA. Before either predicate call,
GDB rejected `$sp & 7` because its SP register is pointer-typed. The stop/move-on
failure and abort-release notification are retained. A bounded read-only
`reconcile-02` found PC 0x080019AA, DHCSR 0x00030003, VTOR 0x08000000, PD2=4,
freeze=4096, zero fault registers and Boot tick 1003. The board was still halted
at the known checkpoint; no unknown return context or predicate call was resumed.

The corrected expression was exercised offline with a typed pointer, then
`gdb-key-03` continued the two still-unexecuted calls from that same initialized
Boot checkpoint. No second reset or repeated successful key call was performed.
All earlier definitions, plans, wrappers and failed outputs remain unchanged.

Observed unchanged physical predicate at Thumb address 0x08001E6D:

- Long hold: return true, Boot ticks 1003 -> 4003 (3000 ticks). Native host time
  from function-PC assignment to restored caller-PC assignment is 3024 ms; this
  includes debugger overhead and is not an exact pin-waveform measurement.
- Short sample: return false, ticks 4003 -> 4013 (10 ticks). The requested action
  was approximately one second, but the measured predicate interval was 10 ms.
  Preserve that distinction: this proves rejection of the observed brief sample,
  not a measured one-second stable press or a debounce-waveform characterization.
- Both calls returned through standard GDB inferior-call handling to 0x080019AA;
  the saved normal and special register checks passed. Saved 512-byte scratch
  stack was restored and debug freeze returned to its original zero value.

This is isolated execution of the exact retained Boot predicate with real PA15
input. It does not force invalid images/BCB or enter the recovery receiver, and
does not claim end-to-end recovery installation. The valid-App ordinary startup
path remains unchanged. No GPIO spoof, timer write or Flash programming occurred.

Final passive verification completed in
`.cache/p17-key-post-20261104-01/inspect-01/`. Full App 30313 remains SHA256
4126d801e6bd6efd57a9f20d5a128a50cfb5a46580dc10d9a2227702247d5805 and the physical
Boot64 remains 01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527.
Main-loop/watchdog counters advanced 16374 -> 16640; App confirmation, SD,
storage-idle, fault registers and stack guard passed. Candidate/backup/recovery
slot headers and staging journal match the pre-window read byte for byte.

The final offline cross-check independently reparsed native tick/PC originals,
rechecked full image bytes with existing health/storage/stack oracles, rejected
four invalid result/timing controls and rehashed the 188 prior preparation inputs.
Its first inventory attempt assumed all historical custom receipts shared the
standard cleanup field; `closeout.py` retains that failed assumption. The corrected
`closeout-02.py` checks new standard receipts and reuses hash-bound prior closure
for the older custom route. No physical test was repeated to repair an auditor.

All new owned process receipts are closed; debugger ports and device locks are
released. The board is running normally and the requested physical participation
is finished. Actual task-window totals: one reset, two predicate calls, no flash,
OTA, USB power switching, product edits, build or Git write. Controlled writes
are confined to new files beneath the key-method directory, the new key-post
directory, this appended note and the task-board annotation in the active
worktree. Native SEGGER history remains within its existing authorized exception.

Formal boundary: P1-7-v3 and its EVIDENCE_GAP matrix are unchanged. The new raw
key observation and earlier USER_REPORTED_NORMAL battery-only observation are
inputs for supplemental formal evaluation, not retroactively admitted v3 commands.
The remaining administrative work is a successor original-evaluation/freeze/final
bundle under the existing scoped local Git authority. No additional device test
is justified merely to package these originals. P1-6 physical power-cut obligations
remain separate; this note does not mark whole P1 or P1-7 formally complete.

### P1-7-v4: Formal Supplemental Acceptance Complete

2026-11-04: the original independent acceptance owner completed the remaining
offline closeout under the existing P1-7 local Git authority. No further human
action, device sample, reset, key call or firmware change was required. The
previous stop before packaging was unnecessary and is not an authority blocker.

Source commit: `7b067c01f4fc03c526573a2d6f7f9e01cdf8bb47`.
Freeze tree: `f9e4222daa75beb2634ab4442dac75577583e1fe`.
Bundle commit: `f3af9ee656593e7f5581835c596bc6df53b4b54f`.
Branch: `acceptance/p1-7-20261103`, local only; no push, merge or main update.
Contract: `docs/acceptance-contracts/P1-7-v4.contract.json`.
Accepted final matrix: `docs/acceptance-contracts/P1-7-v4/final-matrix-02.json`.

The existing p17_review startup evaluator and live_mcu health/storage primitives
are reused. The new p17_supplement evaluator verifies hashed raw originals,
native function/caller PC transitions, native return registers, MCU ticks and
host interval, exact collector bytes, complete retained App/Boot and post-state.
It also evaluates the user's actual battery-only startup report as firsthand
human evidence, not manufactured instrumentation. All 214 host regression tests
passed; full originals are included under the bundle's `host-regression/`.

FROZEN/NOT_RUN precheck passed. The actual v3 EVIDENCE_GAP matrix is the immediate
predecessor, and the computed plan requires only CMD-REVIEW. All five criteria
are EXECUTED PASS for that single offline evaluation, not new physical trials.
The initial assembly wrongly populated REUSED-only matrix linkage fields even
though every criterion is EXECUTED. Its rejected `final-matrix.json` and exact
validator failure remain in the bundle. `final-matrix-02.json` clears only those
inapplicable fields and binds the unchanged originals plus packaging history.
Final validation then passed without repeating the evaluator or any device action.

Accepted scopes and retained limits:

- C-STARTUP: original CPU release to RTT upper bound 1478.732 ms, below 1500 ms.
  The different reset-API-inclusive bound remains 1564.947 ms, not relabeled.
- C-POWER-HOLD: no observed PD2-low sample after latch; original sample resolution
  remains explicit, not an oscilloscope claim.
- C-RECOVERY-KEY: unchanged physical predicate accepts 3000 ticks/real >3 seconds,
  rejects the observed 10-tick short sample, and original calibrated Boot timing
  brackets the one-second latch delay. No one-second stable short-press or forced
  end-to-end recovery receiver entry is claimed.
- C-CLOCK-SIZE: original Boot-phase register decoding supports 288 MHz and the
  bound executable is 14800 bytes, within 64 KiB.
- C-BATTERY: the user's battery-only power-button startup report is accepted with
  its actual human origin. No video, rail/current, duration or endurance claim.

P1-7 is now locally accepted and complete; P1 progresses from 5/7 to 6/7. Its
implementation owner is unchanged. Earlier source/failure/missing-observation
history and P1-7-v1/v2/v3 remain immutable. P1-6 precise physical power-cut and
original-evidence obligations remain open; P5's existing dependency gate is not
waived by this local P1-7 result. No duplicate USB cycling or hardware campaign
was used as a packaging prerequisite.

Reproduce final validation on the bundle commit with:

    python -I -S -B -X utf8 Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P1-7-v4.contract.json --matrix docs/acceptance-contracts/P1-7-v4/final-matrix-02.json --repo-root . --previous-contract docs/acceptance-contracts/P1-7-v4/predecessor/contract.json --previous-matrix docs/acceptance-contracts/P1-7-v4/predecessor/final-matrix.json

Work receipts: `.cache/p17-closeout-20261104-01/`. The later index/task commit
registers the immutable bundle commit rather than guessing a self-reference.
Writes stay within this active worktree and the explicitly authorized shared
task Git objects/ref/reflog/worktrees-source1 metadata. Shared main/ref/index,
unrelated dirty files, old evidence and device state are preserved. Only the
P1 summary row and P1-7 card are staged from the already-dirty task board.
