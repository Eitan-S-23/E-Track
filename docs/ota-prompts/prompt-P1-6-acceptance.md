# P1-6 Group16 Boot Fault Acceptance

task_id: P1-6

## Authority And Scope

OTA-DEC-019 / user record 19 selects the retained accelerated group16 Boot.
This is the sole current P1-6 Spec. It supersedes per-block APPLY assumptions
in the July implementation matrix for future tests of this candidate, not the
immutable historical observations. Other completed P1 cards are not reopened.
Task state remains in PLAN-OTA-EXEC.md. No whole-card PASS is implied.

The retained 14800-byte executable SHA256 is
2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80.
Its original source/build records live in the hash-bound p34-bc-target originals.
Reproduce the uninstrumented binary before admitting a same-source instrumented
Boot. Current-tree ordinary Boot is not this candidate. Keep compiled identity,
source applicability and physical observations separate.

## Invariants

G=16 for APPLY and G=1 for ROLLBACK. Units remain 4096-byte blocks. Only a valid
atomic BCB record makes progress durable. APPLY commits at complete G boundaries
or the final partial group. The uncommitted suffix cannot advance resume after
reset. Validate source identity and the persisted prefix before resuming.

An internal block may skip erase/program only after comparison confirms every
byte matches the selected source, including padded tail bytes. Read failure is
an error, never a match. Otherwise the whole erase/program/readback path remains.
State transitions, source fallback, three-try accounting, full-image validation,
header/BCB integrity, partition/write bounds and backup locking remain required.
No BLE/staging window or wire-format change is authorized by this Spec.

## Fixture And Entry

Use finalized V0 and forward V1 of equal length with an identical linked App
body outside the normal firmware header. A declared appended, non-executed data
suffix supplies differing complete blocks. Bind its start K to a 16-block
boundary above the linked binary end, A=K+16, R=K+1 and total block count N>A.
Include a partial final block and final partial group. V0/V1 must actually differ
at K, A and R, without changing arbitrary instructions or executable sections.
Record ELF/map/header/raw identities and reject insufficient or mismatched assets.

Before mutation: exclusive probe ownership, exact live Boot/App, inactive update
state, known recoverable backups, exact persistent-data write bounds, a tested
restoration plan, committed runner inputs, frozen contract and NOT_RUN precheck.
Use existing SEGGER and P1-6 control helpers, not another Flash/SWD driver.
Retarget body/readback/verification and the requested reset/continue stay in one
native session, after the existing invalidate-first gate. No unowned process kill.

## Successor Matrix

The existing July row IDs and fault classes are retained as lineage. K/A/R/N
are bound before dispatch, not selected after looking at successful traces.

| Row | Class | Injection And Required Observation |
| --- | --- | --- |
| 01 | AUTO | Corrupt candidate payload after installation; reject it and restore validated V0 without applying untrusted bytes |
| 02 | AUTO | Reset after full candidate validation, before APPLYING commit; original STAGED BCB remains and validation repeats |
| 03 | PHYSICAL | Actual power loss during first APPLYING record write; only old or complete new record may arbitrate |
| 04 | AUTO | Reset at durable APPLYING/resume=0 before first changed block erase; resume from 0 |
| 05 | PHYSICAL | Actual power loss during erase of a changed APPLY block; resume from the last committed group, never a torn block |
| 06 | AUTO | Reset after complete erase of changed block K, before programming; resume=K and erase/program/readback resumes safely |
| 07 | PHYSICAL | Actual power loss during APPLY programming; do not accept a partly programmed block |
| 08 | AUTO | Reset after block K readback but before group commit; durable resume stays K; a complete equal block may be revalidated/skipped |
| 09 | AUTO | Reset after APPLY resume=A commits; the committed prefix remains and next changed block is A, not the obsolete value 65 |
| 10 | AUTO | Reset after final resume=N, before final image validation; full-image validation leads to TEST_BOOT without restarting completed copy |
| 11 | AUTO | Reset after TEST_BOOT/try=3 commit; next boot durably decrements to 2 before handoff |
| 12 | AUTO | Reset after try=2 commit, before handoff; next boot decrements to 1 |
| 13 | AUTO | Reset after App CONFIRMED commit; directly boot and verify V1 |
| 14 | AUTO | Three pre-confirmation failures; fourth boot rolls back and confirms V0 |
| 15 | PHYSICAL | Actual power loss during first ROLLBACK record write; only old or complete new record may arbitrate |
| 16 | PHYSICAL | Actual power loss during changed rollback-block erase; no progress beyond the last complete per-block commit |
| 17 | PHYSICAL | Actual power loss during rollback programming; safe continuation from the persisted point |
| 18 | AUTO | Reset after rollback resume=R commits; retain prefix and continue at R |
| 19 | AUTO | Reset after rollback CONFIRMED, before handoff; boot validated V0 |
| 20 | AUTO | Corrupt both backup and recovery after try exhaustion; enter recovery without erasing the still-valid internal V1 |

Independently reuse applicable group16 host originals for skip-identical,
comparison-read failure, grouped-tail, persisted-prefix and commit-failure paths.
Missing applicability or originals requires targeted validation, not invented PASS.
For row 08, the successor observation must distinguish retained durable K from
the next actual changed erase (normally K+1 after skipping equal K); do not wait
for an erase of K that the approved optimization intentionally avoids.

## Evidence And Restoration

Each row needs original command streams, actual checkpoint/control bytes, raw
BCB A/B, arbitration, source slots, final full image/header identity and one
terminal classification: BOOTABLE or PHYSICAL_RECOVERY. Host summaries alone
are insufficient. Keep all failed/unknown attempts and restore known preconditions
before the next row. Never resume an uncertain operation blindly after interruption.

Restore retained group16 Boot and production 30313 App with full readback,
confirmed bootability/health, no fault or leftover hardware comparator, no test
instrumentation and safe upgrade/persistent state. Restoration must not overwrite
unrelated user data. A lost collection stream does not authorize repeating a
successful physical test before attempting original-evidence recovery.

## Completion Boundaries

The 14 AUTO rows can close independently only with applicable original evidence.
The six PHYSICAL rows remain ENV_BLOCKED without a qualified electrical fixture;
USB re-enumeration, J-Link lamp darkness and MCU reset never substitute for them.
Under OTA-DEC-018, closed AUTO plus other prerequisites can admit P5-1 and later
ready P5-2 non-power cases. Neither this decision nor AUTO completion closes
whole P1-6, whole P5-2/P5 or production-release gates. P5 statistics remain intact.
