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
