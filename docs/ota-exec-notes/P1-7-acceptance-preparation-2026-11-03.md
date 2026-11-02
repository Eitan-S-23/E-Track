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
