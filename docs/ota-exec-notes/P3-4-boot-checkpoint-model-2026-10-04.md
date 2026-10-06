# BOOT-CP-01: Host Recovery Model

## Disposition

Implemented and self-tested an isolated APPLY checkpoint grouping prototype.
No production source, device Boot, App, BCB or contract was modified. No firmware
target was built, no CI/deployment/OTA was run, and no hardware permission is
implied. Device remains the previously verified30275.

Owner: Codex root, writable root D:/github/my/E-Track. This implements the
host-model step in P3-4-speed-feasibility-2026-10-04.md, not hardware acceptance.

## Implementation

- Policy: Tools/ota/p34_boot_checkpoint.h. Default group1; explicit supported
  experimental groups4 and16. ROLLBACK always commits every block.
- Real code under test: an isolated copy of boot/src/boot_state_machine.c,
  verified against the recorded installed Boot source digest. Only the
  copy-progress commit block is guarded by the policy predicate. Local loop
  variable `block` advances through verified blocks; `current.resume_block`
  remains the persisted frontier until commit_record successfully re-arbitrates.
- Final partial group always flushes before full-image validation/TEST_BOOT.
  STAGED->APPLYING, rollback entry, boot-try consumption and confirmation are
  untouched. No BCB transaction is mocked as successful without a real write.
- The original eeprom_bcb.c serialization, CRC, inactive-slot selection, seq
  increment, readback and arbitration run unchanged against simulated storage.
- tests/boot/p34_checkpoint_hook.h exposes original checkpoint boundaries to a
  setjmp/longjmp power-cut harness. Test-only storage hooks add partial EEPROM
  page, partial Flash erase and partial programming boundaries.
- tests/boot/test_p34_boot_checkpoint.c reuses the existing fixture helpers.
  The copied fixture changes only image length to617588B, block count to151,
  and history capacity. Its original tests are not rewritten to accept grouping.
- Runner: Tools/ota/p34_boot_checkpoint_model.py. It verifies source deltas,
  hashes inputs before/after, uses contained compiler/temp/home outputs, and
  executes native C99 tests with -O2 -Wall -Wextra -Werror and finite timeouts.

Production boot/src/boot_state_machine.c and the original
tests/boot/test_boot_state_machine.c already had unrelated changes at entry;
their bytes were preserved. The experimental integration exists only at
.cache/p34-boot-checkpoint/boot_state_machine.c and is checked against the
runner's exact expected delta. Nothing enables grouping in the production build.

## Executed Results

Canonical result: .cache/p34-boot-checkpoint/r3/result.json.

| Variant | Copy commits for151 blocks | Successful model scenarios | Exhaustive injected cuts | Maximum observed verified-but-uncheckpointed blocks |
| --- | ---: | ---: | ---: | ---: |
| group1 |151|36|0|1|
| group4 |38|3361|3091|4|
| group16 |10|1793|1691|16|

The0 in group1 means no repeated full151-block exhaustive sweep in that variant,
not an absence of default-path validation. The unchanged original regression
suite passed103 checks, and the default-off isolated implementation passed the
same103 checks. Their native executables are byte-identical. Additional group1
large-image, transaction-error, recovery and sequence tests are included above.
Do not describe native executable equality as ARM artifact equality.

Total model scenarios5190; exhaustive APPLY cuts4782 across the changed group4
and group16 policies. Every positive compile completed without warnings/errors.
The `page_events` / `flash_events` fields count all observed events including
successful recovery runs; they are NOT counts of distinct injected faults.

Normal151-block workloads change1,73 or146 blocks. Exhaustive cut sweeps use
the1-block and146-block workloads; mixed73 has normal and transaction-failure
coverage, not a separate exhaustive sweep.

For every swept event, restore initial persistent storage, run to exactly that
event, abandon volatile execution, then re-enter the real state machine from
the surviving Flash/EEPROM contents. The test asserts the cut actually fired.
Oracles include:

- Persisted APPLY frontier never exceeds the verified frontier; its full known
  prefix matches the target image, independently of the commit policy.
- Verified progress lost at a cut is bounded by group size (4/16 blocks).
- Recovery jumps only to the full expected image; final TEST_BOOT status/try
  bounds and unchanged backup payload are checked.
- ROLLBACK remains per-block:151 copy-progress commits in the full rollback
  test, then CONFIRMED backup identity. Boot-try exhaustion still triggers rollback.
- Source corruption and valid-but-differently-bound candidate replacement
  cannot produce a mixed target; they restore the validated backup.
- Seq wrap from65534 and an off-grid persisted resume=3 complete correctly.

Faults covered:

| Fault class | Coverage |
| --- | --- |
| Boot checkpoint interruption | Original checkpoint events throughout normal APPLY paths, including final group and state/try transitions |
| EEPROM write interruption | Before each8B page, after first4 bytes, after all8 bytes of each transaction on swept paths |
| EEPROM returned failure | Before a transaction and after all bytes have been physically written; subsequent arbitration/recovery uses actual surviving bytes |
| Flash interruption | Before erase, half erased, erased, half programmed, programmed, readback complete |
| Flash returned error | Erase/program/readback failures at blocks0,15,16,145,150 on a151-changed-block fixture |
| Internal read error | Failure cannot erase or advance progress; retry after clearing fault completes |
| Candidate invalidation | Corrupt source and valid replacement after interrupted APPLY lead to validated rollback |
| Recovery behavior | Boot-try exhaustion, rollback transaction count and non-group-aligned resume |

## Preserved Host Failures

r1: baseline passed; running `default.exe` exited4294967295 with no stdout,
including one bounded same-file recheck. Its SHA equals baseline.exe exactly.
Copying those same bytes to checkpoint-default-control.exe passed103 checks.
The underlying host filename-specific startup behavior remains unexplained;
it is not evidence of a Boot logic failure. The runner uses default_control.exe.
All original startup receipts and logs remain under r1.

r2: baseline/default control passed; the overly broad full event sweep on the
byte-identical group1 path was deliberately stopped. Before terminating its PID,
the resolved process image was verified as this project's r2/g1.exe. The failed
receipt remains and is NOT a passed campaign. r3 retained default regressions
and large-image checks while concentrating exhaustive cuts on changed policies.
It also added half-erased Flash coverage before running the final matrix.

## Reproduction

Prepared source and results are preserved; do not rerun prepare into an existing
directory. To rerun tests from the project root, choose a fresh contained output:

    python -I -S -B -X utf8 Tools/ota/p34_boot_checkpoint_model.py test --out .cache/p34-boot-checkpoint/r4

The runner has no firmware build, packaging, J-Link, ADB, OTA or deployment mode.
Source mutation makes its validation fail rather than silently changing inputs.

## Limits And Next Gate

This proves the stated finite host model, not universal crash safety, electrical
behavior, target ABI/stack usage or actual seconds saved. EEPROM torn-page
coverage uses the0/4/8-byte cases, not every arbitrary bit-corruption pattern.
Full151-block ROLLBACK power-cut enumeration and source replacement after each
possible persisted frontier are not claimed; original default rollback failure
regressions remain intact, and the new rollback policy is unchanged.

The modeled reduction151->10 is real transaction-count evidence. The earlier
~5.64s estimate still uses nominal EEPROM page cycle time and is NOT a measured
speedup or proof of the20s target. This change does not address BLE throughput.

Before production integration:

1. Review the proposed persisted-frontier semantics against the frozen contract
   and existing acceptance assertions that require per-block commits. Any change
   is prospective; do not weaken historical tests/evidence or update the contract
   merely to make this experiment pass.
2. Independently review state transitions, uncertain-write arbitration and the
   recovery work bound. Add targeted source-switch/persisted-prefix and arbitrary
   torn-page cases as warranted by that review. Self-tests are not independent
   acceptance.
3. Only then consider an opt-in target build, target stack/size verification and
   a specifically authorized Boot replacement/recovery plan. Preserve the exact
   known-good whole Boot image and measure EEPROM transactions separately from
   Flash and reconnect. No hardware test is requested by this result alone.

All selected output paths in this session are inside the project. Test workers
are closed; no device action or project-external write was required.

## Compatibility Review And Targeted Extension

2026-10-04 follow-up, Codex implementation self-review, NOT independent acceptance.
The original r3 inputs/results remain unchanged. No production, frozen contract,
phone, device or Git publication action was taken.

| ID | Disposition and basis | Direction, invariant, oracle and owner |
| --- | --- | --- |
| BOOT-CP-02 | DECIDED: prospective contract decision required before integration. PLAN-OTA.md:147 and PLAN-OTA-EXEC.md:415 explicitly require persistence after every verified block. tests/boot/test_boot_state_machine.c:484 and :1120 enforce this even for identical blocks. The unchanged binary layout in ota-binary-contracts.md section3 does not waive that behavior. | Root requests approval of a prospective APPLY-only grouped persisted frontier and its recovery cost; do not edit frozen rules or remove original assertions. Preserve default group1 and per-block ROLLBACK, atomic transitions, source binding and final verification. New criteria must be reviewed through PLAN-OTA-EXEC.md section9 before production integration. |
| BOOT-CP-03 | DECIDED: harness coverage gap confirmed and targeted self-test passed. The old source-switch test's event40 has APPLY frontier0 and verified2 for both group4 and group16; it never demonstrated a nonzero persisted prefix. | Added a separate extension consuming the r3-bound harness without editing it. Seed every aligned frontier plus off-grid3,150 and final151; test corrupt source, valid different-version replacement, and valid SAME-version/different-content replacement. Oracle: full validated backup restored, CONFIRMED20700, backup unchanged,151 rollback progress commits. Implementation owns this repair; independent reviewer must assess constructed-state coverage versus actual interruption coverage. |
| BOOT-CP-04 | NEED_EVIDENCE: the observed rework bound is per interruption, not a global bound across arbitrarily repeated power losses. The r3 oracle counts verified-but-uncheckpointed blocks, not all block operations or elapsed recovery time. | For group16, describe at most16 verified blocks (64KiB) whose checkpoint can be lost per modeled interruption, not total recovery limited to64KiB or a guaranteed duration. A repeated-cut experiment and1..7-byte torn-page tests remain unexecuted; no universal/electrical safety claim is allowed. Reviewer to assess the smallest additional model matrix before target work. |

Extension source: `tests/boot/p34_checkpoint_extension.c`.
Reusable runner: `Tools/ota/p34_boot_checkpoint_extension.py`.
Original execution: `.cache/p34-boot-checkpoint/extension1/result.json`.
The runner checks every r3 source digest, generates a test translation unit by
renaming only the old main entry and appending the extension, and binds its own
inputs/generated unit before reporting success. It uses the existing contained
host command/environment helpers, finite compile/run timeouts and write-once
receipts. It does not mutate the old campaign to make its result appear broader.

| Policy | Constructed persisted frontiers | Source invalidation/replacement scenarios | Result |
| --- | ---: | ---: | --- |
| group4 |41|123|PASS|
| group16 |13|39|PASS|

Both native C99 builds use `-O2 -Wall -Wextra -Werror`; compiler logs contain
no warnings/errors. These162 scenarios are additional host self-tests, not new
OTA observations or additional exhaustive power-cut events. They establish
source-binding recovery at the stated constructed prefixes, not the reachability
of every prefix under arbitrary storage corruption.

Independent review has NOT been performed. CLI/source discovery located the
relay, but no reviewer request was sent. In particular, CLI startup includes
update-check/logging paths; finding an executable alone is not a contained or
available independent review route. No daemon configuration was changed.

Next gate: obtain the BOOT-CP-02 behavioral-scope decision, then submit this one
consolidated record and source-bound r3/extension1 evidence for read-only recovery
review. Approval of a contract proposal is not approval to flash Boot. The device
remains30275; neither50KB/s transfer nor20s installation/reconnect is established.

## BOOT-CP-02 User Decision: Proposal Authorized

2026-10-04, user explicitly approved changing APPLY progress persistence from
every4KiB to every64KiB AS A PROPOSAL FOR INDEPENDENT REVIEW. This supersedes
the pending user-scope decision above, not the frozen per-block production rule.
The proposed group is exactly16 blocks (65536 bytes), not64000 bytes.

Approved review scope: APPLY copy-progress commits only. Final partial group
must commit; ROLLBACK stays per4KiB; BCB layout, atomic state transitions,
uncertain-write arbitration, candidate binding, backup lock, TEST_BOOT try
consumption and full image verification stay unchanged. Default production
behavior remains group1 until prospective contract review/integration is complete.
No new flash/OTA, Boot replacement, APK installation, release, commit/push or
project-external filesystem write is authorized by this decision.

Independent reviewer packet (read-only, no implementation or test execution):

- Read this record, docs/agent-collaboration-contract.md and
  docs/acceptance-execution-contract.md section7.3. Compare PLAN-OTA.md:147,
  PLAN-OTA-EXEC.md:415/section9 and ota-binary-contracts.md section3 with the
  proposed semantics; do not amend any frozen input.
- Inspect Tools/ota/p34_boot_checkpoint.h, the exact OLD/NEW transformation in
  Tools/ota/p34_boot_checkpoint_model.py, boot/src/boot_state_machine.c,
  Libraries/EEPROM/eeprom_bcb.c, tests/boot/test_p34_boot_checkpoint.c,
  tests/boot/p34_checkpoint_extension.c and its extension runner. Source digests
  are bound by .cache/p34-boot-checkpoint/r3/result.json and
  .cache/p34-boot-checkpoint/extension1/result.json. These are local uncommitted
  experimental artifacts, not a published revision or independent PASS.
- Decide whether the proposal preserves safety invariants and what minimal
  extra recovery evidence is required before opt-in target integration. Review
  BOOT-CP-03 constructed source-switch states and BOOT-CP-04 repeated-cut and
  torn-page gaps explicitly. Check the difference between verified progress
  lost and actual recovery operations; do not promise a global64KiB/time bound.
- Return consolidated finding IDs, disposition, source anchors, recommended
  minimal remedy, invariant, verification oracle and next owner. Do not run
  device/CI/Git writes, rerun the old campaigns, edit files or claim acceptance.
  Use only read-only cmd.exe/isolated Python, never PowerShell startup. If local
  source-bound evidence is inaccessible, report the missing input, not PASS.

### Independent Route Check

The bounded route check is now executed, superseding the earlier untested-route
status. CLI v1.5.1-beta.1+guo-fix (reported commit d8647490+dirty) returned exit0
for version and exit1 for exact-target discovery:
`relay: no binding for this chat. Use /bind <project> first`.
Receipt: `.cache/p34-boot-checkpoint/review-route1/result.json`; sanitized raw
outputs are alongside it. No review request reached another agent, no target was
guessed, and no daemon restart/reconfiguration was attempted.

CLI startup source was inspected: asynchronous update checking caches in memory;
the inherited CC_LOG_FILE was removed from the child environment, and all
controllable home/cache/temp paths were redirected under review-route1/host.
The existing daemon data path was used only to locate its socket. No external
file output was selected. No source-bound model inputs or old evidence changed.

Next owner: user binds an independent review project to this chat using
`/bind <project>` (the actual configured project name, not a guessed target).
Root then repeats only target discovery and sends the read-only packet above.
BOOT-CP-02 proposal authority is already granted and must not be requested again.
Until reviewer availability is resolved, review remains NOT_RUN; no production
integration or device action is implied by the successful authorization record.

## User-Relayed Independent Review And Remediation

The user subsequently supplied an independent agent's read-only review. This
supersedes the earlier "review NOT_RUN" route status: review text was delivered
manually, not through relay. The reviewer reported no deterministic safety defect
introduced by grouping, verified the r3/extension1 bindings and receipts, and
explicitly withheld target-build/Boot-replacement readiness. Root did not repeat
or impersonate that independent review. Reviewer identity/session metadata were
not supplied; provenance is the user-relayed report in this thread.

The following batch implements its bounded host-test requests, without changing
production, old harnesses, frozen evidence or the approved recovery semantics.
Source: `tests/boot/p34_checkpoint_review.c` and
`Tools/ota/p34_boot_checkpoint_review.py`. Result:
`.cache/p34-boot-checkpoint/review-tests1/result.json`.

| Finding | Implementation response | Executed self-test and remaining gate |
| --- | --- | --- |
| BOOT-CP-05 | Added byte-prefix EEPROM tears at6 representative real transactions: STAGED->APPLYING, first16-block checkpoint, opposite-slot32 checkpoint, final151 checkpoint, TEST_BOOT entry and first try decrement. Starting sequence65534 exercises wrap. Added failures at each transaction's pre-arbitration A/B, independent readback, post-arbitration A/B and one readback mismatch. Readback targets include both slots. |336 tears (6x8 pages x7 byte positions),36 read/mismatch faults PASS. Old active-slot bytes remain unchanged during writes. Errors stop the invocation without further EEPROM reads/writes or Flash erases; surviving physical storage arbitrates on recovery. Not arbitrary bit corruption or electrical testing. |
| BOOT-CP-04 | Added persistent-storage-preserving sequences: first checkpoint tear then replay-block interruption; physically successful/error-return commit then next transaction tear; final flush followed by TEST_BOOT or try-transaction tear. Also3 consecutive persisted try-decrement interruptions before jumps, correctly exhausting tries and restoring backup. |5 bounded sequences PASS; no restore/reset fixture between interruptions. Exact candidate-jump try value is derived from the entry state and must match the last actual transaction and active stored record. No cumulative recovery-time/work bound is claimed. |
| BOOT-CP-03 | Real execution now stops after APPLY block20 with durable frontier16 and both BCB slots valid. Corrupt source / different-version replacement / same-version different-content replacement each run with a second tear in rollback entry or first rollback-block commit. No BCB reconstruction or other-slot clearing between those interruptions. |6 combinations PASS. Every rollback write checks atomic entry phase2/resume0, then successive resume increments of1 against the previous physical active record; final backup bytes, padding, CONFIRMED and backup preservation checked. These are selected combinations, not exhaustive ROLLBACK cuts. |
| BOOT-CP-06 | New storage oracle checks legal arbitration, state/phase pairing, persisted-prefix bytes and tail0xFF; at interruption it also checks frontier<=verified. At reentry, persisted bytes are independently checked before initializing volatile progress. Final candidate/backup bytes and padding are checked; candidate jumps require exact persisted try consumption. |3 intentional oracle negatives PASS (ahead of independently supplied verified limit, wrong byte inside persisted prefix, bad tail padding), with correct positive controls. The three malformed states are oracle tests, not claims of reachable product faults. Original per-block assertions untouched. |
| BOOT-CP-02 | Added a prospective proposal registration to PLAN-OTA-EXEC.md section9, naming the exact16x4096B scope, absolute boundaries, forced final flush, per-interruption limitation and unchanged defaults/rollback/atomic behavior. |Registration only; no successor normative contract approved, production integration, target-build authorization or Boot-replacement permission inferred. Follow-up independent review and scope approval still required. |

Total targeted result:336 tears,36 I/O faults,11 multi-interruption sequences,
3 oracle negatives. Native C99 -O2 -Wall -Wextra -Werror compilation and execution
returned0; compile diagnostics empty. The runner's exact count gate passed and
all source bindings remained unchanged. These are implementation self-tests,
not independent acceptance, ARM builds, actual power loss or measured speed.
The generated translation unit renames only the original harness main and
checkpoint callback, then appends the new test fragment. Production state-machine
and BCB code are unchanged; the existing isolated grouping delta is reused.

The old0/4/8-page campaign was not repeated. The new matrix includes4-byte tears
within the uniform1..7-byte set; no earlier case is silently relabeled as newly
executed. Existing5190+162 results remain source-valid and frozen in place.

Follow-up review packet: independently inspect this response table, the two new
files, the source-bound generated unit and compile/run receipts under
review-tests1. Recheck BOOT-CP-03/04/05/06 against the requested oracles and the
section9 registration boundary. Return consolidated findings/readiness; do not
rerun old campaigns, edit files, build ARM targets or operate devices. No new
relay binding is assumed. Any reviewer must have access to these local artifacts.

Scope self-check: the7 existing PlannedExecutionTests from
tests/ota/test_acceptance_efficiency.py passed (scope-tests.log/json in
review-tests1); this is a narrow in-memory regression, not the full acceptance
efficiency suite or independent acceptance. Final write audit covered only the
two new source files, this note, the single new section9 registration row and
review-tests1 outputs. All selected outputs are project-contained; prior model
source digests remain valid. No device process, firmware build or Git write ran.

## Follow-Up Review Closure And Proposed Target Scope

The user delivered the original reviewer's follow-up report. It closes
BOOT-CP-03/04/05/06: the requested targeted host evidence is sufficient, no new
blocking defect was identified, and no further host campaign rerun is requested.
The reviewer verified53 inputs plus the generated source and executable
(55 digests), command receipts and unchanged r3/extension1 bindings. This is
read-only review of self-test evidence, NOT formal independent acceptance.
Root rechecked existing input bindings on receipt without rerunning tests.

BOOT-CP-07 is a non-blocking limitation: scope-tests.json/log lack command,
input-hash and log-hash provenance. Their7 passes remain auxiliary records,
not a formal gate or evidence for the grouping algorithm. Do not rewrite these
receipts or rerun Boot tests to strengthen an unrelated auxiliary claim.

BOOT-CP-02 remains open for successor applicability and implementation scope.
The section9 registration is complete; production per-block requirements remain
effective. User approval so far covers the proposal/review, not target execution.

Proposed next authorization, one contained Boot-only development batch:

1. Prepare a source-bound isolated snapshot under
   D:/github/my/E-Track/.cache/p34-bc-target. Preserve all prior source/evidence
   paths and the production boot/src/boot_state_machine.c bytes. Apply only the
   reviewed grouping delta plus target-local configuration in this new snapshot.
2. Use the repository GCC/CMake X_Track_Boot entry, Release/Ninja and project
   reproducibility settings. Build baseline group1 and experimental group16 with
   the installed identical-block-skip behavior preserved in both. Do not build
   App/simulator/AC5 or enable host fault hooks in ARM binaries.
3. Record exact source/configuration/toolchain/commands and ELF/BIN/HEX/MAP
   hashes, warning/error counts, flash/RAM layout, ABI attributes, disassembly
   differences and Boot stack-usage evidence. A .su file alone is not full
   call-chain/interrupt stack closure; unresolved bounds remain explicit gaps.
4. All controllable output/temp/cache paths must be preflighted under that new
   project-local directory before execution. Do not reuse an existing output
   directory or create external short-path build directories. Restrict any
   necessary build adapter and experimental scope record to this project.
5. Submit target integration/size/ABI/stack findings for independent review.
   No device operations, Boot replacement, OTA, APK install, production-default
   change, CI, commit/push/merge/release or frozen-contract rewrite are included.

This is a scope proposal, not an executed build or an approved normative
successor. Target snapshot/outputs have not been created. The current whole Boot
must remain untouched; any later flash needs a separately scoped recovery plan
and approval. The older preparation/original-whole-boot.bin predates the current
installed skip-identical Boot and must NOT be mislabeled as the current backup;
the recorded current full Boot is .cache/p34-boot/activation/after/boot.bin,
65536B, SHA256 a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.

## Authorized Isolated GCC Target Build

The user explicitly authorized the proposed isolated implementation/build batch.
This grants only the development scope above, not production integration,
normative contract replacement, device operations or publication. No repeat
authorization is needed for this same bounded build scope.

Executed runner: `Tools/ota/p34_boot_target.py`. Comparison runner:
`Tools/ota/p34_boot_target_analysis.py`. Evidence root:
`.cache/p34-bc-target/`; build result `result.json`, comparison `analysis.json`,
original source binding `inputs.json`, generated snapshot `snapshot.json`.

The2381-file source snapshot is under `f/`. Only three snapshot files differ
from their original inputs: the exact reviewed state-machine transformation,
the copied checkpoint policy header under boot/include, and appended target-only
CMake group/stack options. Production sources, old generated models and prior
evidence remain unchanged. Both builds use the same patched snapshot; group1
constant-folds the grouping guard away. Host fault-injection hooks are absent.

Both configurations use repository X_Track_Boot, GCC13.3.1, Release/Ninja,
SOURCE_DATE_EPOCH1786320000, CMAKE_OBJECT_PATH_MAX1024, no compiler cache, and
P34_BOOT_SKIP_IDENTICAL_BLOCKS=ON. No App, simulator, AC5, CI or hardware ran.
Original and snapshot file hashes were verified unchanged after compilation.

| Observation | group1 | group16 |
| --- | ---: | ---: |
| BIN bytes |14780|14800|
| GNU size text |14776|14796|
| Initialized data |4|4|
| GNU size bss including reserved heap/stack |9780|9780|
| Actual .bss section |5172|5172|
| Reserved heap+stack section |4608|4608|
| copy_source symbol bytes |308|328|
| copy_source static stack frame |304|312|
| main static frame |224|224|
| boot_state_machine_run static frame |488|488|
| Native ARM compile/link warnings/errors |0/0|0/0|
| CMake configuration warning blocks |1|1|

The one warning in each configuration lists unused defensive registry options
CMAKE_EXPORT_NO_PACKAGE_REGISTRY and CMAKE_FIND_USE_PACKAGE_REGISTRY. It is not
a compiler warning and was not hidden or treated as zero. No rebuild was run
solely to remove this harmless configuration warning.

BIN SHA256:
- group1: f0ed3994f7f7a7d39dac92a09b0fedf2f2b7b05ee038ac400eba2c569c586954
- group16: 2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80

group1 BIN equals the saved installed skip-identical candidate BIN byte-for-byte.
It also equals the first14780 bytes of the recorded current65536B whole Boot.
The remainder of that whole Boot is NOT all0xFF; do not replace the preserved
whole backup with a padded compact BIN or claim full-region equality.

Both existing validate_boot_artifact.py runs passed:64KiB Flash/vector/layout,
MSP/reset range, required symbols and forbidden-dependency checks. ELF ABI
attributes are equal: ARM ELF32 little-endian, EABI5 hard-float, v7E-M/Thumb2,
VFPv4-D16, wchar4, small enums,8-byte alignment. Generated linker scripts retain
the same RAM/Flash geometry. ELF/HEX/MAP/configuration/log hashes are in receipts.

Only copy_source changes symbol size (+20B). Its disassembly keeps the phase
test and final-block exception; the16-block test is emitted as a low-four-bit
test (shift28), not a division library call. Among261 compiler stack records,
all are static and only copy_source differs (+8B). This set includes emitted
translation-unit functions and must not be summed as a runtime call chain.

### Remaining Target Stack Gate

Full stack bound is explicitly UNKNOWN / NEED_REVIEW in analysis.json. There
are31 register-BLX callsites in each disassembly (including unchanged physical
recovery paths). This inventory does not resolve their target sets or cover all
tail jumps. Complete closure still requires source-bound callback resolution,
library/assembly frame accounting and exception-frame/nesting analysis. The
linker's4096B minimum stack reservation and individual .su frames alone do not
prove complete stack safety. Neither runtime stack high-water nor electrical
fault behavior has been measured. No ready-to-flash conclusion is made.

### Preserved Analyzer Failures

Two host-only analysis attempts failed before creating analysis.json: first an
IndexError from expecting `File Attributes:` followed by newline, then explicit
`missing ARM attribute section`. Raw readelf output actually prints
`File Attributes` without a colon. The second attempt adjusted whitespace but
had not removed that colon assumption. Final parser accepts an optional colon,
requires the section, and completed against the unchanged original logs.
These are parser failures, not GCC/Boot failures; no build or device operation
was repeated. Original command receipts/logs remain untouched.

Next independent review scope: verify authorization/snapshot deltas, baseline
binary reproduction, actual Boot compile commands and artifact validators,
ABI/layout/symbol/frame comparisons, and the explicit remaining stack gate.
Use result.json plus analysis.json and their source-bound inputs. Do not reopen
the closed host fault campaign or infer flash permission. A targeted callback/
stack closure can consume these exact binaries without rebuilding firmware.

## BOOT-CP-08: Existing-Artifact Stack Analysis

The user delivered the original reviewer's isolated-build review. It confirms
the artifact/baseline/ABI/layout/frame observations, retains BOOT-CP-08 as a
pre-flash gap, confirms BOOT-CP-09's whole-backup distinction, and requests no
new build or old fault-campaign run. This follow-up performs offline analysis
only. Production, snapshots, binaries and previous receipts remain unchanged.

New reusable analyzer: `Tools/ota/p34_boot_stack.py`.
New source-bound result: `.cache/p34-bc-target/stack-analysis.json`.
This is implementation analysis awaiting independent verification, not a formal
acceptance or an unconditional system stack bound.

### Call Graph And Frames

Each variant has153 parsed function nodes and253 conservative edges. Direct
calls and cross-function conditional/unconditional branches are included;
tail edges conservatively retain the caller's entire maximum frame, rather
than subtracting a guessed epilogue. Register-call and tail targets are resolved
to source-bound supersets from boot_main's BCB HAL/state_io, boot_recovery's
reader/UART/sink objects, and boot_handoff's reader. All possible members of
each declared union are retained; no target is selected just to reduce the bound.
The result records37 indirect/boundary control sites, including31 BLX sites,
indirect tails, local switch dispatch and the explicit App handoff boundary.

Reachable compiler records must be static. Unknown frame/target and recursive
edges fail graph traversal; none occurs in the reported Boot entry traversals.
Four graph self-checks passed: positive conservative caller+callee accumulation,
recursive edge rejection, missing target rejection and missing frame rejection.
These checks are not a general-purpose disassembler certification; the analyzer
and its source-binding unions must be independently reviewed with the binaries.

Linked assembly/library frames are taken from the actual disassembly, not host
library estimates: Reset_Handler0, default handler alias ACC_IRQHandler0,
__aeabi_uldivmod16, __udivmoddi4 32, __aeabi_idiv0 0, memcmp8, memset0, memcpy8.
The divider wrapper's pre-decrement16B and helper's eight-register32B save are
counted separately. memset is a leaf; memcpy/compare have8B pushes. The result
embeds those instructions for review. One initial analyzer attempt stopped at
the size-less __aeabi_uldivmod alias, which nm --size-sort omits. Parsing was
corrected to consume that explicitly reviewed disassembly label; no build ran.

| Entry (includes its own frame, excludes callers) | group1 | group16 |
| --- | ---: | ---: |
| Reset_Handler / main, all Boot branches conservatively included |2136|2136|
| boot_state_machine_run, covering normal/APPLY/ROLLBACK/TEST_BOOT dispatch |1912|1912|
| copy_source |972|980|
| boot_recovery_receive |1696|1696|
| boot_handoff_to_app, Boot instructions only |1136|1136|
| SysTick software frame / default-handler software frame |0/0|0/0|

The2136B path is main -> boot_state_machine_run -> validate_external_source ->
boot_fw_header_validate -> boot_fw_header_validate_ex -> boot_sha256_update ->
sha256_transform. Physical recovery including its224B main caller is1920B.
The grouping delta adds8B to copy_source's branch, not the global deepest path.
These are conservative static graph results, not measured runtime high-water.

### Boot-Vector Exception Budget And MSP

Both actual131-word vector tables were checked: all nonzero exception/IRQ
entries other than Reset target either SysTick_Handler or the infinite-loop
default-handler address. SysTick only increments a global and returns, with no
software stack allocation. Reset_Handler sets MSP=0x20058000; SystemInit writes
the Boot VTOR. boot_platform_init configures SysTick priority0xF0; external IRQ
enable paths are absent from the Boot initialization. Analysis assumes normal
reset entry with reset NVIC priorities and no debugger/foreign state mutation,
not an arbitrary branch into Boot with inherited application interrupt state.

For the interval with Boot vectors active, a deliberately conservative allowance
is4 nested hardware frames: SysTick, one reset-priority configurable exception,
HardFault and NMI. Disabled external IRQs are not needed for the normal path;
the extra configurable level is retained as a margin. Equal-priority handlers
do not preempt each other and active exceptions do not recursively self-enter.
Per frame reserve32B basic core state +72B optional floating context +4B alignment
=108B, even though these Boot handlers execute no floating instructions. This
covers the extended/lazy frame allocation without assuming FP context is absent.
All observed handler software frames are0. Conditional Boot-vector bound:
2136+4x108=2568B, leaving1528B against the4096B minimum stack reservation.
This exception calculation and reset-state assumptions are review inputs, not
a claim that asynchronous electrical faults have been simulated.

The actual image has data4B, .bss5172B, then4608B heap/stack reservation ending
at0x20002638. MSP starts at0x20058000:350664B separates it from that reserved
region's end. The4096B reservation is not a hardware guard or the entire physical
gap; it is used above as a conservative comparison budget. No allocation or
external writer may be assumed to consume this gap silently. App stack layout
after handoff is a different ownership domain.

### Precise Unclosed Boundary

BOOT-CP-08 is PARTIALLY CLOSED, not fully closed. The graph records the
boot_branch_to_app MSP replacement and BX r1 as an explicit outgoing boundary,
not an unresolved Boot callback that can be ignored. Before reaching it,
boot_handoff_to_app writes SCB->VTOR=OTA_APP_ORIGIN, then reads/checks vectors,
records globals and may log/hold on mismatch while still using the Boot MSP.
An NMI or HardFault in that interval dispatches through APP vectors. Boot ELF,
Boot .su and Boot vector-table checks cannot bound those App handler call chains.
This window already exists in the byte-identical baseline; it is not a newly
proved grouping defect. Simply claiming interrupts are disabled is insufficient
for NMI, and no handoff repair was silently added to this scope.

Preferred next direction: in the prospective Boot-replacement plan, bind the
exact App artifact(s) to be handed to, resolve their NMI/HardFault/default handler
paths and budget their execution on the pre-switch Boot MSP and post-switch App
MSP. For a generic all-future-App guarantee, a successor App/Boot handoff contract
must supply a defensible handler-stack bound, or a separately reviewed handoff
design must address the transition. Root must not borrow an unrelated App
high-water measurement or invent a zero-cost handler. Until that evidence/scope
is selected, full_system_bound remains null with status
UNKNOWN_APP_VECTOR_HANDOFF_WINDOW in stack-analysis.json.

Next owner: original independent reviewer checks this graph, target unions,
library frames and conditional exception calculation, then decides the minimal
App-pairing/successor-scope evidence for the remaining window. No repeated build,
host fault matrix, Boot flash, device readback or production edit is requested
by these findings. BOOT-CP-09 full65536B backup remains protected and unchanged.

## Finite App Pairing: Initialization Dependency Found

The user supplied the original reviewer's stack follow-up: Boot-only graph and
conditional2568B budget accepted as partial closure; App-vector window remains
open. This investigation reuses existing artifacts only. No build, device
access, fault injection or old test campaign was performed.

Reusable binder: `Tools/ota/p34_app_handoff.py`. Outputs:
`.cache/p34-app-handoff/result.json`, `preinit-analysis.json` and original
objcopy/nm/objdump/readelf logs with bounded command receipts. The source manifest
and artifact hashes from p34-sha-candidate were checked before extraction.
ELF load bytes reproduce the raw617588B build BIN exactly; each finalized image
differs only within the96B fw_header at0x400. Neither "same version" nor a file
name was used as evidence of executable identity.

| Role | Evidence and limit |
| --- | --- |
| Retained current App30275 | SHA4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6; matches the prior verified observation and measure.bin |
| Predecessor30274 | SHA22a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002; bootstrap.bin, same executable outside header. This is NOT proof of current physical backup-slot payload |
| Matching ELF | .cache/p34-sha-candidate/b/app-gcc/X-Track-App-GCC.elf; SHAd1b619be49801178d7e0161fda11b23212a43d3f9d86289e0c2660bf825d4c0f |
| Matching MAP | same directory X-Track-App-GCC.map; SHAb1fdcc3e79de7a80c9e4ad3ac6601be72322efa7f49dd89f808b03f42cdc466f |
| Future candidate | Not selected or built. Do not invent a successor identity |
| Physical backup/recovery | Exact present payload set not established by the consumed closing record, which reports BCB state4 but not full external slot identities. No device read was issued to fill this gap |

Both images' vector MSP is0x20058000. NMI vector0x0801b835 points to the
two-byte default-handler self-loop (symbol alias ACC_IRQHandler); it has zero
software frame but still incurs architectural exception stacking. HardFault
vector0x08043b59 points to the real HardFault_Handler at0x08043b58.

### BOOT-CP-10: Pre-Initialization Handler Prerequisites

NEED_EVIDENCE / scope decision for the handoff boundary, not a demonstrated new
grouping defect and not a reported device crash. It applies to BOTH group1 and
group16 and BOTH matched App images.

Actual linked path:
HardFault_Handler -> vApplicationHardFaultDump -> cmb_printf (merged with the
FaultPrintf implementation) -> vsniprintf (vsnprintf alias) -> _vsniprintf_r.
The handler first calls SEGGER_RTT_Init and sets nonblocking mode; this initializes
RTT, not all App globals or the C library state.

At0x08056516/0x08056518, vsniprintf loads `_impure_ptr` from0x20000304 and passes
it into the reentrant formatter. The matching App data initializer would set
that pointer to0x20000308, but App Reset_Handler has not copied .data yet during
the handoff window. Boot's actual g_copy_block occupies0x20000004..0x20001004,
overlapping that pointer. In a completed copy of either bound617588B image, the
last block supplies word0x7ff9cf28 at image offset0x96300 to that location, not
the App-initialized pointer. This is a source/artifact-derived overlap example,
not a fresh RAM measurement or proof that every formatter call dereferences
that value. Even ordinary confirmed-start Boot BSS initialization does not
establish the App .data initializer. The normal-runtime libc precondition cannot
be assumed valid; error/alternate formatter paths cannot be waived silently.

At0x08043af6/0x08043af8, vApplicationHardFaultTrace reads the one-byte
s_faultHandleReady at0x20052d48. Its zero initializer belongs to App BSS, not
Boot BSS. Before App startup it may contain retained/uninitialized RAM; it is
not a trustworthy early-boot readiness gate. A nonzero value enters
cm_backtrace_fault. The same flag in cmb_printf gates Print::print using the
serial object at0x20003adc, whose App C++/RTOS/runtime setup is likewise not
established. Arbitrary pre-init object state cannot be treated as a known virtual
callback target. The matching generated HAL_FaultHandle source and disassembly
are bound in the new evidence; no assumption is made from the unrelated live
source alone.

These prerequisites are missing both after VTOR changes while the old Boot MSP
is active (including vector-mismatch log/hold) and after MSP changes before
App data/BSS initialization completes. More stack-size arithmetic alone does
not establish initialization-safe handlers, so no finite whole-window upper
bound or ready-to-flash result is emitted. The App runtime guard/linker budget
must not be used as proof that this earlier initialization window is safe.

Preferred next action for independent reviewer/root: confirm whether a narrowly
scoped early-exception-path remedy is required, with no dependency on uninitialized
App globals, libc/heap, virtual serial objects, RTOS or backtrace state. If a
safe bounded path can instead be proved for these exact existing bytes, supply
the path-sensitive proof and both-MSP budget. A proposed remedy must separately
define startup/handoff ownership and preserve normal runtime diagnostics; do
not silently change handoff ordering or assume PRIMASK masks NMI. Current
authorization is analysis/isolated Boot development only, not an App fault-path
change or production handoff redesign. Freeze the finite candidate/backup/recovery
set before any eventual hardware plan. Until that decision, BOOT-CP-08 remains
partially closed and BOOT-CP-10 records the specific initialization obstacle.

All new outputs are under .cache/p34-app-handoff; the only other writes are the
new binder and this existing note. Existing binaries, full Boot backup and source
bindings are preserved. No device speed or electrical-safety result is claimed.

## BOOT-CP-10 Direction Confirmed; Proposed Remediation Scope

The user relayed the original reviewer's independent decision: initialization
prerequisites are genuinely unestablished in the two matched Apps; pursue a
bounded early-exception-path prerequisite repair rather than more generic stack
arithmetic. This confirms a pre-existing static gap, not an observed crash or a
grouping regression. The technical decision grants no App implementation or
device permission. BOOT-CP-08 remains partially closed; old grouping tests stay
closed and existing evidence remains immutable.

Preferred design candidate for separate review, NOT an approved implementation:

- Keep the App's fixed-address primary vector table safe before any App RAM
  initialization. Its relevant exception entries route to an assembly-only early
  path whose selection depends on Flash vector contents, not stale RAM flags.
- Evaluate a separate runtime vector table. Switch VTOR to it only after the
  exact dependencies of the existing diagnostic path have been initialized.
  Determine the real initialization ordering and all interrupt users first;
  do not assume FaultHandle_Init alone establishes every dependency.
- Early handler behavior is deterministic bounded halt (or a separately reviewed
  bounded reset policy), without globals, libc, heap, RTT, serial objects, RTOS
  or backtrace. Existing runtime diagnostics must remain available after the
  explicit transition. Do not silently trade away normal fault reporting.
- Review table alignment/placement, the fixed fw_header offset, App vector
  validation, SystemInit VTOR writes and interrupt enable ordering. A second
  table must not enlarge the primary vector prefix across fw_header. The
  Flash-vs-RAM runtime-table choice and exact exception coverage remain design
  decisions until the linker and startup sources are inspected.
- Cover Boot-MSP/App-VTOR, App-MSP/pre-init, and fully initialized phases, plus
  mismatch log/hold and applicable NMI/fault nesting. Boot handoff ordering and
  BCB/grouping semantics remain unchanged. If those invariants cannot be met,
  stop that design branch and seek a specific scope decision, not a workaround.

Requested next bounded authorization: prepare the detailed App startup/exception
design; obtain independent design review; then implement and host-test it in an
isolated project-local development snapshot and build GCC App artifacts with
fresh source/ELF/vector/disassembly bindings. Planned output root:
D:/github/my/E-Track/.cache/p34-early-fault. Any adapter/test files remain inside
this project. Reuse existing Boot artifacts; do not rebuild Boot or rerun its
closed fault matrix merely because App code changes. Full source/output preflight
still precedes each actual write/build.

Excluded: production-default changes, frozen-contract rewrite, release, Git
commit/push/merge, APK installation, device reads/writes, Boot replacement or OTA.
No remediation source or target snapshot has been created under this proposal.
Finite future App/backup/recovery identities remain a later hardware-plan gate.

The user subsequently authorized that bounded design/review/isolated App
implementation/build scope. The detailed design is now prepared at
docs/ota-exec-notes/P3-4-early-exception-design-2026-10-04.md. It proposes two
immutable Flash vector tables and end-of-HAL_Init runtime promotion, with an
explicit initialization-period halt tradeoff and strict live-VTOR compatibility
boundary. Independent DESIGN review is still required before implementation;
no App source or new build snapshot has been changed yet. Do not request the
same implementation/build authorization again after an in-scope design approval.
