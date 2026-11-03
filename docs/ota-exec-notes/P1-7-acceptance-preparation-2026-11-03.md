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
