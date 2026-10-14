# P3-4 Offline Original-Evidence Closeout

Date: 2026-10-13. Same independent reviewer; no implementer role change.

Latest continuation (2026-10-14): candidate-stage independent acceptance is PASS
under `P3-4-v15`. The verified local evidence commit is
`15a025b9c2690e864456a32fb2820422846fb85b`, with 8838 raw Git blob checks and a
successful standard validation at that commit. See Candidate Stage Closure below.
The host repairs remain CLOSED; v11/v12/v13, the new v14 partial failure and 3/3
are preserved. Local closeout and necessary same-scope continuation permissions
are recorded and must not be requested again. Main integration, push/CI, device
actions and P3-5/P5 final validation are not granted or claimed by this result.

Git delivery continuation (2026-10-14): the user has now explicitly authorized
the proposed PR/CI/main integration and safe task-record closeout. See Git
Integration And Delivery below. This supersedes the earlier Git-only authority
exclusions for this delivery, not the device pause or production-release barrier.

## Why Work Continues

The previous reply stopped too early: completion of the bounded device plan did
not finish independent acceptance. Existing user authorization and execution
contract section 0.1 already permit the remaining offline original-evidence
evaluation. No renewed device permission or another physical OTA is needed.

Use the single Spec at governance commit
`cb317affcd291695f42271084b4b305b0d7e6f8b`. This note is not another Spec.
Authority and consumed actions remain recorded in
[the v12 authorization register](P3-4-v12-candidate-acceptance-2026-10-13.md#user-authorization-register).
The v12 note, contract, matrix and originals remain unchanged.

## Scope

The direct parent is v12, source
`02013607ca38eaf5cff0d5c4fc3de8259fbff916`. Its P34-CANDIDATE-REFERENCE and
Q-PREP-RESTORE criteria are direct EXECUTED PASS anchors and must be REUSED,
not executed again. The interrupted Q-TRANSFER is not a reuse PASS anchor.

The successor evaluates its captured product observations through the existing
committed App/MCU readers, the installed standard binary comparator, and the
independent reviewer's raw register/guard/health checks using unchanged pure
gates. No new acceptance runner implementation, inline frozen interpreter,
device reader, product code or competing approval system is introduced.

Product conditions are retained: exact legal package, source/ELF/map/parameter
binding, zero-origin complete transfer, CRC/clean terminal, timely original
pre-reboot RAM and old-App context, stack/guard, clock/SysTick/tick/WDT, full
target/Boot identity, confirmation and actual final reader/archive closure.

Any resulting Q-TRANSFER PASS means this NEW offline original-evidence
evaluation passed. It does not claim v12's host command completed within its
deadline, invent its exit/closed/action receipt, or erase its EVIDENCE_GAP.
The later diagnostic readback remains explicitly later. v11 HARNESS_FAIL and
the cumulative three physical qualification transfers remain preserved.

This continuation has zero device actions and zero extra OTA allowance. It
does not commit, push, merge, trigger CI, release, alter the shared root, or
change final performance/reliability gates. P5-1 owns final 30/30 and four hours;
P3-5 owns real-backend 10/10 recovery; P5-2 assesses applicability. The deferred
trial5 risk and host-owner interruption remain separate, visible limitations.

## Completed Offline Scope

R is the worktree above; S is the read-only shared project root. E is
`R/.cache/p34-v13-offline-20261013`; B is `R/.acceptance-p3-4/round13`.
Actual HEAD was rechecked as `02013607ca38eaf5cff0d5c4fc3de8259fbff916`.

The frozen v13 candidate-original-evidence evaluation is PASS. All eight required
offline commands exited 0; the full standard lineage final validator exited 0.
This is not merely a passing validator for a failed matrix: the new offline
Q-TRANSFER criterion itself was executed and independently judged PASS.

| Criterion | v13 disposition | Direct evidence |
| --- | --- | --- |
| P34-CANDIDATE-REFERENCE | REUSED from the original v12 EXECUTED PASS | v12 contract/matrix and `B/adjudications/candidate-reference.json` |
| Q-PREP-RESTORE | REUSED from the original v12 EXECUTED PASS | v12 contract/matrix and the copied complete restoration originals |
| Q-TRANSFER | New EXECUTED offline-evaluation PASS, not a new physical execution | Eight `B/commands/CMD-Q-TRANSFER*` receipts and `B/adjudications/offline-transfer.json` |

`E/sealed.json` binds the completed contract, matrix and final-validation receipt.
The contract SHA-256 is
`747cff42a2cdd74c286e2e361e8658f3766617eb3b20bcc3269fa3f3f6bd5b32`;
the matrix SHA-256 is
`a106cdea4fdce187db9d7352b6717f8c01a307dddc40a47d0757378012940d4e`.
`task_completion_allowed=false` and `production_release_allowed=false` remain
unchanged. This three-criterion stage does not close the entire P3-4 Spec.

The initial lineage-preflight binding error, its corrected preflight, and the
v12-origin namespace correction remain preserved in E. None changed the frozen
v13 contract or any original v12 file. No completed command was replayed to
obtain a more favorable result.

## Reconciliation By Applicability

| Observation | Disposition | Identity, original location and limit |
| --- | --- | --- |
| Historical 115200 comparison and repeat | Usable historical product observations | Five 30206 -> 30207, 284643-byte transfers; S `.cache/p34-cycle-checkpoints/screening-summary.json` binds C0-C3 originals, and S `.cache/p34-cycles/c3-002/cells/reuse-without/` holds the repeat. The baseline records source `fbc3b5aae468e9ab382ac018c1247de43d890491`. Four candidate APK hashes differ; C3 and its repeat match. Do not infer a common current-v2 sender or combine these with the 1 MiB group. |
| Historical 460800 failure versus later resume | Retain distinct historical outcomes; current applicability not established | S `docs/ota-exec-notes/P3-4-screening-2026-09-22.md` traces the failed DATA transfer and later recovery. A zero-DATA resumed success cannot supply a fresh full-transfer success. Neither proves the current v2 candidate would fail at 460800. |
| Current-candidate 230400 | Not reconciled, not "unsupported" or "never completed" | No applicable original was established through this bounded entry-point review. The earlier selected screening plan explicitly omitted mandatory 230400; this is not grounds for an automatic four-rate rerun. |
| v10/v11 reference transfers | Usable original performance/product facts; old formal gaps remain | 3.2.86 -> 3.2.87, exact 1048576-byte ETU, protocol 2, 921600/2000 ms/5, window 24, batch 12, write payload 244. `B/inputs/reference-v10.jsonl`, `reference-v11.jsonl`, `reference-v11-mcu.rtt` and their reference-command receipts. v10 remains EVIDENCE_GAP; v11 remains HARNESS_FAIL. |
| v11 missing old-App RAM | Genuinely absent from v11 | Re-decoding RTT never supplies that run's stack/guard/SysTick/WDT reads. No old record was filled with later RAM. |
| v12 local runtime and final product identity | Covered by new originals, accepted offline in v13 | `B/ops/cmd-q-transfer/mcu/0003-terminal-before-reboot/`, original phone snapshot, and explicitly later `B/diagnostics/post-interruption/` full target/Boot readback. Old-App context and the original terminal deadline were verified. |
| Original v12 command completion | Genuinely missing, not retroactively repairable | Original final App readback is empty and the original close/action receipts are absent. v12 remains EVIDENCE_GAP even though the product observations can now be evaluated independently. |
| Trial5 | Deferred, not repaired or exonerated | Its missing-page failure and unknown root cause remain recorded in the shared P3-4 continuation note. The user's deferral is not a pass. |

The four historical comparison snapshots, binding/measurement records and full
App/Boot readbacks were checked against their recorded hashes. The fifth original
snapshot was also verified. Initial ad-hoc reads incorrectly assumed uniform
legacy relative-path/key spellings; they stopped read-only, not because the
originals were absent. Existing per-record bindings were then used, without
editing evidence or relaxing the snapshot validator.

Historical C0/C1/C2/C3 transfer times are 244.870742 / 247.039059 / 79.003209 /
74.326403 seconds; C3 repeat is 80.309317 seconds. These preserve the original
write-mode/discovery observations, including the lack of a clear reuse-only gain.
The old WAIT_RX comparison used 296376 versus 296551-byte packages, as explicitly
recorded in S `docs/ota-exec-notes/P3-4-transfer-next-2026-10-07.md`, WAIT_RX Screen
Complete. It is not an identical-package causal comparison of the current v2
candidate. Do not silently promote either historical series to that stronger claim.

## Candidate And Timing

The evidence-supported candidate remains protocol 2, 921600 baud, timeout 2000 ms,
maxRetries 5, window 24, DATA batch 12 and negotiated write payload 244. The legal
1 MiB ETU SHA-256 is
`8373305b6817081106ad35c840ef87bf2d4210ffa2e8b9e881e0799ad1ff9e47`.
Both finalized App images are 613952 bytes; asset source is
`1c3f7f49baa27c42452f7796839cea57ddd734b7`.

| Original | BEGIN-to-END seconds | KiB/s | DATA retransmissions | Valid ACK samples |
| --- | ---: | ---: | ---: | ---: |
| v10 | 71.582792 | 14.305114 | 0 | 8192 |
| v11 | 71.316310 | 14.358567 | 0 | 8192 |
| v12 | 63.708034 | 16.073326 | 0 | 8192 |

The original v10/v11 reference criterion retains its P99 of 827159 us and 2000 ms
clamp. A supplemental distribution of all 24576 same-candidate original ACK
samples yields nearest-rank P99 761183 us and the same 2000 ms clamp. This does
not add qualification runs to an old calibration or final 30-run campaign.
The faster v12 time is not attributed to the host-only A/B fix.

The unchanged committed `batch_timing.analyze(..., protocol=2)` applied to v12
gives DATA GATT calls 38.039566 seconds and other transfer spans 25.668468 seconds,
total 63.708034 seconds. The remainder is not isolated ACK or Flash time. Original
upgrade summary: one discovery, 17.867 ms; 5603 total GATT/platform writes,
zero errors; MTU 247, payload 244, without-response mode. GATT p50/p95/max are
5.514/15.286/44.984 ms. Binding is a separate 629.133 ms phase.

The MCU's independently measured wrappers report payload erase/program/verify
4.634648/2.286065/0.146102 seconds, UART IRQ 1.846741 seconds and ACK submission
6.182312 seconds. Each payload write/erase/verify has 256 calls; unused read timing
is null, not a measured zero. These wrappers may nest/overlap and use the MCU
clock; do not add them to App times or label their subtraction as a speedup.
No complete installation-only duration or original host-command completion time
is inferred from the interrupted final readback. Later identity verification is
kept separate.

## Source And Local Safety Coverage

`E/spec-review/completed.json` records the supplemental applicability checks.
Production/Firmware/Flutter source diffs are empty under BOTH old and current
profile definitions. Production and Flutter definitions expanded to explicitly
include three Gradle files; those files themselves are unchanged. The standard
definition-change invalidation rule remains intact. Its initial failure is not
evidence of changed runtime code and was not bypassed for formal PASS reuse.

Four original CI archives and metadata were rehashed and ZIP CRC checked:
38047823595 (governance), 38047823559 (MCU), 38047820907 (Flutter development),
38047823551 (APK/EXE), all at `6942ae068f6c57b1b42c679a2ebe039d5b9b0fef`.
Both original full Flutter logs and reports match: Linux 722 passed/16 skipped;
Windows 705 passed/33 skipped; zero failures. Flutter tests and runtime/build
inputs have no intervening changes. This is applicability of existing Actions,
not a claim that a new CI run tested `02013607`.

Seven existing firmware host suites were hash-checked against the source register
and their original successful receipts. The independently executed receiver
containment model in `R/.cache/p34-independent-review-20261010/receiver1/` retains
327 checks across 10 cases, with the source-mutating negative exiting 1. All ten
bound sources and four logs still match. These cover modeled failures, not the
physical cause of trial5. No successful suite was rerun for this review.

The actual existing candidate `build.ninja` has 387 relevant definition rows:
AT experiment, BLE profile, RTT down-command and install profile/cost are OFF;
production-format link metrics are intentionally ON. The bound base image lacks
the disabled `BXST:` and `RTTCMD:` markers. No firmware rebuild was needed.

A/B are CLOSED by the prior independent host review and the committed source
identity. v12 additionally supplies the necessary single timely old-App sample:
420-byte RAM/RTT equality and CRC, intact guard, 5092/8192 stack bytes still
painted, 288 MHz clock, valid SysTick, tick delta 103, WDT registers 5/3124 and
nominal 10000 ms watchdog. These are observed local bounds, not a whole-program
worst-case stack proof, forced-watchdog-recovery experiment or physical cold
power-cycle test. Ordinary Boot and full confirmation are established separately.

## Open Boundaries And Next Owners

| Item | Owner and minimum next action | Verification boundary |
| --- | --- | --- |
| Entire P3-4 Spec closure | P3-4 root/Spec owner consumes this candidate-stage result and the historical comparison ledger. Do not mark the whole card complete from three criteria. Exact current-v2 causal gain is not established by the old different-package/variant observations; keep a bounded/no-causal-gain conclusion unless matching originals close that stronger claim. | No default rate sweep or extra OTA. A new physical comparison requires an actual unmet required claim, matched inputs and a minimal plan, not a parser or agent change. |
| Interrupted host owner | Host-execution owner, before a future device campaign: diagnose caller/owner/Windows Job cancellation and receipt finalization using host-only lifecycle evidence. Repair only a demonstrated defect. | Normal exit, cancellation and timeout must retain originals and honest exit/uncertain outcomes, finite deadlines and reader ownership. No fabricated old exit, automatic OTA retry or deadline extension. Cause currently UNESTABLISHED. |
| Trial5 | Existing root owner; preserve the user's deferred investigation and original failure. | Do not claim its physical root cause fixed by the model or by later successes. |
| Final reliability/performance campaign | P5-1: one final same-group 30/30 and real four-hour soak. | Retain all numerical/statistical gates and failures; no duplicate P3-4 campaign. |
| Real-backend recovery and remaining physical faults | P3-5: one 10/10 real-backend recovery group; P5-2 assesses applicability and genuinely uncovered conditions. | Ordinary success is not disconnect recovery; ordinary reset is not physical power loss. |
| Project delivery | Authorized root integration, not this read-only shared-root session. | Local note/index and authority register are not yet committed or delivered to main. No commit/push/CI/release authority is inferred. |

No additional device observation is proposed by this closeout. All missing
specific old-App runtime observations in the approved minimum plan now have
original evidence. Unknown comparison/fault applicability must first be resolved
from source/metadata/originals; it is not a preapproved new device action. The
current chain's cumulative qualification consumption remains 3/3, with v10/v11
2/2 unchanged. Previously completed cleanup and restoration are not repeated.

## Write Audit And Handoff

The closing audit is `E/write-audit.json`. It checks the 2016 original protected
paths, the authorized retirement/archive of the old lock, all v12 matrix-bound
originals, both Git indexes, reviewed sources, the sealed v13 evidence and the
unchanged v12 authorization note. It inventories new outputs inside R, including
the local collaboration index. No product/runner source or shared-root file is
a selected write target.

The old external-default-directory metadata differences remain unattributed in
the v12 audit. This review neither cleans those paths nor claims a machine-wide
write trace. Controllable new outputs are confined to E, B, the v13 contract and
this operational note/index. The saved device closeout is the latest observation,
not a new live device query in this offline continuation.

## Followup: P34-HOST-CLOSE-01

Disposition: DECIDED, required harness repair before another device campaign.
Owner: the original host implementation owner; this session remains the
independent reviewer. No third freezing agent and no additional OTA are needed.
F denotes `R/.cache/p34-v13-followup-20261013`.

The previous reply again ended while safe host-side work remained. That was an
execution-scheduling mistake, not missing user authorization. This continuation
completed a bounded source review, one normal control, two cleanup-error cases,
a primary-error discriminator and a narrow read-only Windows event query.

### Evidence And Scope

Actual source remains `02013607ca38eaf5cff0d5c4fc3de8259fbff916`.
`Tools/ota/p34-acceptance/live_host.py:153` sets `self.closed=True` in a finally
block, but writes the close receipt only after that block. If either
`WindowsJob.terminate()` or `WindowsJob.close()` raises, the receipt write is
skipped. Termination failure also skips handle close. A subsequent `close()`
returns immediately because `self.closed` is already true.

`F/close-probe.json` records execution of the actual unchanged Process.close
method with writable real fixture streams and mocked process/job APIs:

| Case | Observation |
| --- | --- |
| Normal control | Receipt exists; ordinary owner/stream closure completes. |
| Job termination error | OSError propagates, receipt absent, handle close not attempted, owner marked closed; the model can still report an alive child. |
| Job handle-close error | OSError propagates, receipt absent, owner marked closed. |
| Second close after either error | No additional cleanup or receipt attempt. |

No OS child or native Windows Job operation was started by these fixtures; the
alive-child observation is a model result, not a claimed surviving real device
reader. `F/primary-probe.json` additionally exercises actual `h.command()`:
a primary ValueError from the operation is replaced as the surfaced exception by
cleanup OSError in its finally block. Python exception context retains ValueError,
but consumers which record `str(error)` receive the cleanup failure instead.
The close receipt is again absent despite writable evidence paths.

This failure path was not covered by the prior normal-exit/timeout/readiness
tests. Those existing successful tests are not rerun or represented as failures.
The four bound host/test source files remain unchanged in `F/before.json`.

The old v12 partial App file's last-write timestamp is 10:21:39 UTC; that is NOT
a process-exit timestamp. The original readback had its own 345-second phase
budget, and absence was reconciled later. The narrow Application-log query for
10:16:30..10:37:00 UTC, crash/hang event IDs 1000/1001/1002, exited 0 and returned
no related Python/J-Link event. `F/eventlog.json` binds the query and output hash.
This does not distinguish forced termination, an unlogged crash, cleanup failure
or another cause. The v12 cause remains UNESTABLISHED. Do not claim this probe
reproduced the historical interruption or blame the user.

### Consolidated Repair Packet

Preferred scope: `Tools/ota/p34-acceptance/live_host.py::Process.close/command`
and focused regressions in `tests/ota/test_p34_live_route.py`; update only the
existing task handoff plus fresh implementation logs. Do not replace WindowsJob,
create another controller or touch product/metrics/phone/MCU implementations.

Attempt the remaining owned cleanup in bounded finally paths even when an earlier
step raises. Record truthful exit-or-unknown and cleanup errors while evidence IO
is still available; do not mark physical closure verified merely because close
was attempted. Preserve the primary operation failure, associating cleanup
errors without substituting a success or masking that first failure. Repeated
close must be safe without a new command, silent retry, overwritten receipt or
unbounded cleanup loop. Failure to persist a receipt must itself remain explicit;
do not pretend persistence can be guaranteed after abrupt process death or disk
failure.

Required positive/negative oracle:

- Normal and nonzero exits, timeout, readiness yield and duplicate close preserve
  existing output/exit/deadline behavior.
- Terminate error and handle-close error retain the original streams and a
  truthful failure/uncertain close record when the output path is writable.
- An operation error plus cleanup error preserves the primary error and records
  the secondary cleanup problem. Neither becomes PASS.
- The bounded owned-job cleanup is still attempted appropriately; no foreign
  process kill, automatic device retry, new reservation or extended deadline.
- Actual process destruction is not modeled as a catchable Python exception;
  preserve the distinction between a modeled cleanup failure and unknown v12
  historical cause.

The existing contained regression entry is:

    python -I -S -B -X utf8 Tools/ota/p34-acceptance/selftest.py live --out ABSOLUTE_FRESH_R_LOCAL_OUTPUT

The implementer must preflight the output and set `P34_HOST_TEST_OUT` to a fresh
contained subdirectory, retain commands/full logs/counts and source hashes, and
return the bounded diff for this reviewer's independent checks. No commit, push,
merge, CI or new formal round is implied by this repair packet. Do not edit or
replay this already-executed diagnostic script as the new regression suite.

The defect concerns host cleanup/error accounting, not firmware bytes, ETU,
App throughput or the completed normal offline commands. A/B remain CLOSED;
the v11 failure, v12 gap, v13 scoped PASS and cumulative 3/3 stay unchanged.
Do not append a physical qualification to validate this host repair.

## Followup: Comparison Applicability

`F/comparison-applicability.json` now binds all four actual historical APK hashes
and their adjacent original `trace-dev-debug.json` metadata. All declare source
`fbc3b5aae468e9ab382ac018c1247de43d890491`. The three non-baseline metadata entries
explicitly select the GATT-reuse/no-response factor combinations; their requested
choices match the recorded write modes/discovery observations. The baseline
metadata omits the later request field; its actual with-response/discovery result
remains the authority. C3 and its repeat share the same APK.

The old commit object is not available in this local Git object database, so no
new source-tree diff at that commit is claimed. This is a bound historical
source/parameter declaration and verified product observations, not invented
source inspection or a current-v2 gain result.

Correction to the earlier remaining-work wording: different APK hashes alone do
not invalidate a declared same-source factorial comparison. The canonical Spec
permits a negative/limited hotspot conclusion and existing-observation adoption;
it does not mandate another exact current-v2 comparison solely because acceptance
has reached this candidate stage. Do not convert the absence of a stronger causal
claim into an automatic new device observation. Numerical/final reliability gates
and all old frozen obligations remain unchanged.

The actionable next implementation work is the single consolidated host-close
repair above. This reviewer can then independently check its affected host paths,
using the saved originals rather than another OTA. Trial5 remains explicitly
deferred and P3-5/P5 final campaigns retain their own scope.

## Followup Audit

`F/audit.json` checks the previous v13 audit inventory, all unchanged bound
sources/Git indexes and the new output inventory. Only this operational note
and its local collaboration-index link are updated outside F; their exact
pre-continuation bytes are preserved in F. No frozen contract, evidence matrix,
device original, previous audit or authorization note is modified.

## Independent Review: P34-HOST-CLOSE-01

Disposition: DECIDED, primitive repair verified; required caller integration
remains open. Owner: original host implementer, then this independent reviewer.
No new permission request or device action is required for that host-only work.
I is `R/.cache/p34-host-close-01-20261013`; E is
`R/.cache/p34-host-close-01-review-20261013`.

The actual HEAD remains `02013607ca38eaf5cff0d5c4fc3de8259fbff916`, branch
`acceptance/p3-4-v2-20261009`. The reviewed implementation is uncommitted, so
HEAD alone does not identify it. Final SHA-256 values are:

- `live_host.py`: `a0d98161aadccee0346b8f7438cf65566ae6e72d7cf8cc576641e833d7cc6431`.
- `test_p34_live_route.py`: `751ef1833852ab39ee113a6fa9ae7f67f24bd60062f790b8aa452febf3ad336d`.

`I/handoff.md`, `I/changes.patch`, final test logs/receipts and source identities
were checked. The implementation's final targeted 18/18 and full live 117/117
results match their actual logs and final sources; no full-suite replay was
needed. The independent affected-path run in `E/focused/` passed 23/23 with
exit 0 and no timeout: the 18 primitive lifecycle tests plus five existing
process/deadline/readiness checks. This accepts the bounded primitive change,
not the compatibility of every real caller or the whole P3-4 card.

### Confirmed Caller Findings

All three findings are subitems of the same P34-HOST-CLOSE-01 batch, not a new
Spec or acceptance round. They exercise actual caller and Process methods with
modeled process/Job APIs. The Network.start check additionally uses a contained
loopback HTTP server; no external tunnel, ADB, J-Link or device reader is run.

| Subitem | Actual entry and failure | Independent original |
| --- | --- | --- |
| C1 | `live_phone.py:186`, Network.close: tunnel handle-close failure prevents HTTP shutdown, server_close, thread join and log-handler close. All four call counts stay zero even after a duplicate close; the Process cleanup itself is attempted only once. | `E/callers/observations/network-drain.json` |
| C2 | `live_phone.py:145`, Network._start/read: reader exit 7 first raises RuntimeError, but the finally close rethrows its cached cleanup OSError. Both the surfaced exception and startup-failed.json report the cleanup error instead of the primary. Normal-cleanup control preserves RuntimeError. | `E/callers-complete/observations/network-primary.json` |
| C3 | `live_phone.py:514`, Phone.close: a modeled private-server stop ValueError is replaced by server cleanup OSError in finally. Normal-cleanup control preserves the primary object; each control invokes stop once. | `E/callers-complete/observations/phone-primary.json` |

No surviving real device reader or server is inferred from the modeled C1
counts. Python exception context still retains the primary in C2/C3, but the
actual caller's surfaced type/message is wrong. This matters because failure
receipts consume those fields. None establishes the cause of the old v12 owner
interruption, which remains UNESTABLISHED.

The initial caller group had one C1 assertion failure and one reviewer fixture
error: the primitive fixture mocked `h.os` with only `name`, while caller setup
needed `fsync`. That AttributeError is not an implementation defect. Its original
log remains in `E/callers/tests.log`. `E/reviewer-fixture-correction.json` records
the correction, and the fresh `callers-complete` group then ran only the pending
Network/Phone primary-error checks: two actual assertion failures, no setup
errors or timeout. The completed 23 checks and C1 probe were not replayed.

### Minimum Integration Packet

The earlier two-file/no-live_phone scope isolated the primitive defect but is
insufficient for these demonstrated caller dependencies. Supersede that limit
only for `live_phone.py` lifecycle blocks: Network.start/read/close and
Phone.close, with focused tests in the existing `test_p34_live_route.py`.
This does not authorize changes to provisioning, phone/device logic, metrics,
A/B, firmware, App, contracts, deadlines or the accepted primitive behavior.

Reuse the existing primary-preserving Process helper and bounded cleanup
pattern, not a replacement controller. Network.close must attempt all remaining
owned cleanup despite an earlier error, retain honest failure/unknown state and
record diagnostics when possible. Repeated close must not retry the failed
cleanup, repeat a stop command or overwrite its original receipt. A failed
receipt write remains explicit; persistence after process death is not promised.

Network.read and Phone.close must preserve the original operation exception and
associate secondary cleanup errors. Review Network.start's outer error/save/
finally-close block at lines 86-95 in this same batch: it has the same structural
masking risk, established by source review, not a separate executed probe.
Successful operation followed by failed cleanup must still fail, never pass.

Positive/negative verification uses existing host tests and fresh contained
outputs, not another device experiment:

- C1: terminate/handle-close failure still attempts HTTP shutdown, server close,
  bounded thread join and handler close; failure remains visible. A second close
  adds no cleanup/stop attempt or receipt overwrite.
- C2/C3: normal controls and primary-plus-cleanup failures preserve the expected
  primary object/type/message and secondary diagnostics; no-primary cleanup
  failure still propagates. Include the outer startup error/receipt/close path.
- Existing success, nonzero exit, timeout, DNS retry, readiness, partial startup,
  single-reader ownership and absolute-deadline behavior remain unchanged.
- Preserve all failed test logs. Add the caller oracles to the existing suite,
  self-test the completed batch, and return one bounded diff with actual counts,
  source/log hashes and a write audit. Do not replay E's write-once review scripts
  or create a new formal bundle to make this review green.

`E/final-review.json` is the independent NOT_CLOSED conclusion. `E/audit.json`
is its write-audit authority; exact pre-review operational note/index bytes are
saved as `E/note.original.md` and `E/index.original.md`. The implementation and
historical evidence remain immutable review inputs. Only E and this operational
note/index are selected outputs, all inside R; the shared root stays read-only.

The next dependency is implementation integration, not user device action or
renewed authorization. No new device observation is proposed. A/B CLOSED,
v11 HARNESS_FAIL, v12 EVIDENCE_GAP, v13 candidate-original-evidence PASS and
cumulative physical qualification 3/3 remain unchanged. Entire-task completion,
production release, deferred trial5 and P3-5/P5 responsibilities remain exactly
as recorded above; the local update is not delivery to main.

## Caller Integration Review: P34-HOST-CLOSE-01

Date: 2026-10-14. Disposition: DECIDED, CLOSED within the host lifecycle scope.
The same independent reviewer checked the returned caller batch; no role change,
new freezing agent, new formal round or device operation occurred. The preceding
NOT_CLOSED review and its failed originals remain preserved, not reclassified.

C is `R/.cache/p34-host-close-01-callers-20261013`; E is
`R/.cache/p34-host-close-01-callers-review-20261014`.
Actual HEAD is still `02013607ca38eaf5cff0d5c4fc3de8259fbff916` on
`acceptance/p3-4-v2-20261009`. The accepted working-source hashes are:

- `live_host.py`: `a0d98161aadccee0346b8f7438cf65566ae6e72d7cf8cc576641e833d7cc6431`, unchanged primitive.
- `live_phone.py`: `3c524300133818dfed7d056a525ffe044082d0dc5c185aea8a16b98532b89723`.
- `test_p34_live_route.py`: `848e5e1902982052da0d8be0d5fd6a82c8992e77e0564165f6a673e7191c5cb5`.

The incremental diff was independently reconstructed from C's saved entry bytes
and matched `C/changes.patch`. The original ProcessCloseTests body and unrelated
Phone/config definitions are unchanged. C's final 17/17 and full live 134/134
counts, exit/timeout receipts, complete logs and source bindings were verified;
neither the full 134 nor the unchanged primitive 18 was replayed.

The independent run is `E/suite/tests.log` with its actual command receipt and
source-bound intent. It passed 20/20, exit 0, no timeout, skip or warning: the 17
affected caller tests plus three independently specified original failure
discriminators. These counts are not added to the implementation's 134 as unique
product checks. `E/result.json` binds the complete independent result.

| Closed subitem | Independently observed result | Original |
| --- | --- | --- |
| C1 | Tunnel cleanup failure still attempts shutdown, server close, thread join, log close, Job termination and handle close exactly once. Second close returns the same failure without repeating work or altering the receipt; confirmed closure stays false. | `E/observations/c1.json` |
| C2 | Both normal-cleanup and failed-cleanup reader controls retain the original RuntimeError and exit 7. startup-failed.json records the primary; secondary cleanup identity and diagnostics survive. | `E/observations/c2.json` |
| C3 | A stop-command ValueError remains primary with its cleanup OSError attached. Stop executes once with the original ten-second bound; duplicate close preserves the original receipt and failure. | `E/observations/c3.json` |

The same affected suite covers nested reader/tunnel failures, startup receipt
failure, cleanup failure without an operation failure, live/unknown observations,
unstarted HTTP thread cleanup and duplicate-close protection. Existing DNS,
readiness, ownership and deadline tests in the bound complete live log remain
applicable. No new blocking finding was identified in this bounded change set.

The actual caller and Process methods ran with modeled device/process/Job APIs;
the network checks use contained loopback HTTP fixtures. They do not prove an
actual device-reader leak, catch forced process destruction, guarantee receipt
persistence during disk failure or establish the v12 historical cause. The
known old failure remains distinct from this now-closed demonstrated defect.

### Task-Level Handoff After Host Closure

The candidate parameters, timing/comparison ledger, v12 local observations and
their v13 independent original-evidence result above remain usable within their
recorded limits. This caller-only change does not invalidate those product
observations. No extra OTA, four-rate sweep, new causal-speedup comparison or
repeat of completed restoration/cleanup is proposed. There is no remaining
P34-HOST-CLOSE-01 implementation action; do not send the same fix back again.

The project-level closing work is source/record integration and explicit
whole-card candidate-scope adjudication against the single Spec. The reviewed
host changes and operational records are still uncommitted; shared root is
read-only and commit/push/merge/CI authority has not been added. These are real
delivery boundaries, not reasons to replay product tests or another implicit
permission request for completed device work. Any future formal execution must
use properly committed/frozen applicable inputs, not these hashes as a fake Git
revision. The existing task board/readiness rows were not changed by this review.

v13's `task_completion_allowed=false` and `production_release_allowed=false`
remain intact. Trial5 retains the user's explicit deferral and unresolved failure;
it is neither repaired nor silently waived by host closure. P3-5 retains the
real-backend 10/10 group, P5-1 the final same-group 30/30 and actual four-hour
soak, and P5-2 the applicability review. Their final campaigns must not become a
circular requirement to redo them inside P3-4 before candidate-stage handoff.

`E/adjudication.json` is the independent CLOSED decision. `E/audit.json` checks
C's 25,496 protected inputs, implementation inventory, reviewed sources, both
Git indexes and the new output inventory. Only this operational note/index are
updated outside E; their exact prior bytes are saved in E. No old audit, original,
contract, matrix, authority register or accounting file is rewritten. A/B CLOSED,
v11 HARNESS_FAIL, v12 EVIDENCE_GAP, v13 scoped PASS and cumulative 3/3 all remain.

## Local Closeout Preparation

Date: 2026-10-14. This continuation finishes the safe preparation rather than
stopping at host-fix closure. L is
`R/.cache/p34-local-closeout-prep-20261014`; `L/prepared.json` records actual
inputs and the proposed local sequence. Status is PREPARED, NOT AUTHORIZED OR
EXECUTED. It is neither a second Spec nor another acceptance control system.

### Single-Spec Checklist

The governing Spec is still
`cb317affcd291695f42271084b4b305b0d7e6f8b:docs/ota-prompts/prompt-P3-4-experiment.md`.
This table is an applicability/closeout checklist, not a replacement frozen
matrix or a declaration of new EXECUTED PASS criteria.

| Spec deliverable | Existing evidence and independent disposition | Limit retained |
| --- | --- | --- |
| Baseline and candidate screening | Historical C0-C3 plus repeat and the current v10/v11/v12 group are reconciled in the comparison and candidate sections above. `F/comparison-applicability.json` binds the four APKs and original factor metadata. | 230400 is unreconciled, not unsupported; old 460800 failure/resume is not a clean current-v2 comparison. No automatic four-rate campaign. |
| Per-observation identity | The current group uses the exact 1 MiB ETU, 613952-byte 3.2.86/3.2.87 pair, original group16 Boot and registered firmware/App source `1c3f7f49baa27c42452f7796839cea57ddd734b7`. v13 originals and the source-lock review bind versions, parameters and hashes. | The old historical factorial source is declared by original metadata; its unavailable Git object is not presented as a newly inspected tree. Groups stay separate. |
| One supported candidate and retry basis | v2, 921600, 2000 ms, retries 5, window 24, batch 12 and payload 244. Three real reference observations are 14.305114/14.358567/16.073326 KiB/s with zero DATA retransmissions. The recorded same-group ACK distributions support the 2000 ms clamp. | Qualification observations do not fill old calibration or final 30-run accounts. This is not the final highest stable production setting. |
| Necessary local functionality and safety | Seven source-bound firmware host suites, the independent 327-check/10-case receiver containment model and its failing source mutant, plus the timely v12 old-App metrics/guard/stack/clock/tick/WDT originals and complete target/Boot confirmation. | Observed bounds are not whole-program stack worst-case, physical power-loss or electrical-fault coverage. Trial5 is still unresolved and deferred. |
| Independent original-evidence evaluation | v13 preserves two direct original v12 EXECUTED PASS anchors and newly evaluates Q-TRANSFER originals offline. A/B and P34-HOST-CLOSE-01 are independently closed. | v11 HARNESS_FAIL and v12 EVIDENCE_GAP remain; no old command receipt, successful physical invocation or PASS is invented. |
| Timing, hotspot and comparison report | The timing section separates BLE, discovery/GATT, MCU wrappers and later identity verification; existing historical factorial observations and limited/negative hotspot conclusions remain usable. | No current-v2 causal gain or isolated MCU installation duration is claimed. Different/overlapping clocks are not subtracted or summed. The defined BLE throughput boundary is not total end-to-end installation time. |
| Actual build/CI and source provenance | Four original CI archives at `6942ae068f6c57b1b42c679a2ebe039d5b9b0fef`, complete dual-host Flutter logs, the unchanged runtime profile trees, candidate build definitions and the recent source-bound host reviews are available. | Those Actions tested their actual commit, not the dirty current worktree. The three accepted host files still need a real committed source identity before a new formal execution. |

The completed supplemental provenance review is
`R/.cache/p34-v13-offline-20261013/spec-review/completed.json`; it is adopted,
not replayed. The canonical BLE performance/tuning clauses require separate
timing boundaries and reserve final statistical/stability claims to P3-5/P5;
they do not justify a new installation-speed or four-rate campaign merely to
rename this candidate stage. Any future request for a stronger claim must first
identify its actual unmet criterion and insufficient original.

Trial5's original user disposition was rechecked in shared-root
`docs/ota-exec-notes/P3-4-transfer-next-2026-10-07.md`, Acceptance-Only Direction:
the user stopped further root-cause work and did not require that separate
investigation before candidate preparation/submission. This does not repair or
waive the original failed observation. Keep that risk visible at task adjudication
and in downstream applicability checks; do not restart it without a new basis.

### Bounded Local Commit Sequence

The next necessary scope is local to the existing R branch, not a request for
device intervention or another implementation agent:

1. Commit only the three accepted host source/test paths: `live_host.py`,
   `live_phone.py` under `Tools/ota/p34-acceptance/`, and
   `tests/ota/test_p34_live_route.py`. Their full paths/hashes are in
   `L/prepared.json`. Do not stage unrelated dirty records or all untracked files.
2. Using that actual source identity, prepare/check the candidate-stage closeout
   against the existing Spec and standard profile/lineage rules. Use the saved
   trustworthy observations for only the required offline evaluation. A changed
   Validation group is not permission to repeat restoration or OTA. Keep old
   contracts/matrices and their explicit scope flags unchanged.
3. Commit the necessary verified evidence and existing P3-4 task records, then
   append the real bundle/freeze references to the local FREEZE-INDEX in a later
   commit. Do not manufacture commit IDs, make an index reference itself, stage
   credentials, alter old evidence or declare release eligibility.

This is one proposed bounded local closeout permission, not a request to approve
each command or commit again. New original-evidence checks still fail honestly;
the preparation does not preassign their outcomes or waive unresolved criteria.
P3-5/P5 final campaigns remain outside it.

Actual Git common directory:
`D:/github/my/E-Track/.git`; the R index is under its
`worktrees/p34-final/` directory. Even a commit issued from R writes shared Git
metadata outside R. The prior P34-AUTH-HOST-COMMIT was consumed by `02013607`;
the existing authority register explicitly does not authorize another commit.
The user's instruction to continue autonomously does not erase that boundary.

Local main is still `cb317aff`; the branches have 1 main-only and 15 R-only
commits. A read-only shared-worktree check also found 54 tracked modifications
and 711 untracked status entries. Do not merge, reset, stash, clean or copy back
over that work. The proposed exception is for local Git metadata writes only;
the shared main worktree, main ref, push, CI and release stay outside this plan.

Global hooks were inspected read-only before proposing commit execution.
`prepare-commit-msg` can call an external AI API, and the commit hooks can send
an external notification. Use an explicit commit message and remove only the
child-process AI/notification variables to avoid those unapproved effects;
preserve pre-commit checks, contain temporary outputs, and do not edit global
hooks/configuration or run their external paths as a test.

The v13 matrix currently names 704 original files totaling 36203199 bytes, with
none missing. A bounded read-only heuristic screen of its 528 text files found
no private-key/credential/signed-URL pattern hits. This is only preliminary
screening, not export approval or justification for bulk staging the historical
trees. Reconcile the exact necessary commit contents before any future staging.

`L/audit.json` is the write-audit authority. Only L and this operational
note/index are updated; their previous bytes are retained in L. No test, build,
device operation, staging, commit, Git-ref mutation, notification or CI was run.
The same independent reviewer can execute the local sequence once its actual
Git-write scope is explicitly approved; no new freezing agent is required.

## Local Closeout Authorization

Recorded 2026-10-14 after the explicit local-closeout approval question. The user
approved and instructed that the same authorization must not be requested again.
The original decision is recorded in
`R/.cache/p34-local-closeout-20261014/authorization.json`, binding the prior
prepared plan. This resolves the preparation-time authorization gap above;
the old proposal and audit remain unchanged historical records.

Authorized scope is the bounded local P3-4 closeout chain on
`acceptance/p3-4-v2-20261009`: the three independently accepted host source/test
files, necessary verified P3-4 evidence and existing task records, followed by
the real bundle/freeze index entry. The writable worktree remains R. The explicit
additional write boundary is `D:/github/my/E-Track/.git`, for the shared objects
and this worktree/branch's local commit metadata. The shared main worktree,
main ref and its index remain protected.

Continue required local commits and offline preparation/checking within this
scope without per-command, per-commit, per-agent or per-continuation approval.
Record actual execution and stop only the affected action for an actual integrity
problem, changed scope/risk or user revocation. This is not general authority to
commit unrelated work or to rewrite historical records.

No push, merge, CI, publication, release, device operation, additional OTA,
reset, installation, old-original cleanup, global configuration change or
hook-triggered external API/notification is authorized. Preserve normal
pre-commit checks while containing its environment and disabling only the
unapproved external paths. The previous device authorization register and all
v11/v12/v13 outcomes and cumulative 3/3 remain unchanged.

## Local Source Commit And V14 Admission

Date: 2026-10-14. E is `R/.cache/p34-local-closeout-20261014`.
The authorized source commit actually completed:
`fcbace8b3f782714a139a77a12cb9305dbaef7cc`, parent
`02013607ca38eaf5cff0d5c4fc3de8259fbff916`. It contains only
`Tools/ota/p34-acceptance/live_host.py`,
`Tools/ota/p34-acceptance/live_phone.py`, and
`tests/ota/test_p34_live_route.py`. Their bytes equal the independently reviewed
inputs. `E/source-commit.json` and `E/source-commands/` contain the actual commit,
staged-byte checks and command receipts. No host suite, device action or OTA was
repeated merely to commit these files. A/B and P34-HOST-CLOSE-01 remain CLOSED.

The new candidate closeout has NOT been admitted. The authoritative v14 contract
was written as FROZEN and its matrix is NOT_RUN. Its standard lineage preflight
exited 1 with exactly four errors: `CMD-CANDIDATE-ARCHIVE-04`, `-07`, `-10` and
`-13` omitted `runner_paths` for their Python standard-library ZIP checks.
This is the independent reviewer's premature-freeze preparation error, not a
product failure or a regression in the accepted host repair. The validator
correctly rejected the incomplete dependencies. There are no v14 formal command
receipts, no `candidate-prepared.json`, and no new candidate or whole-task PASS.

### P34-V14-PREFLIGHT-01

The failed original is retained in
`E/candidate-host/lineage-preflight.{started.json,stdout,stderr,closed.json}`.
Byte-exact pre-correction copies are
`E/v14-preflight-original.{contract,matrix,plan}.json`; the authoritative contract,
bundle copy, matrix and plan still match them. The contract's original SHA-256 is
`f760ee663f786f474b8bde0297a8b076c98b86c7d4fc21a8b572b3d6bcb0eb74`.

`E/metadata-correction-proposal.json` binds an unapplied correction, and
`E/metadata-admission-review.json` records the independent delta review.
Only the four commands' `runner_paths` would be populated with their actual
owned-launcher dependencies: `live_host.py`, `build.py`, `Tools/flutter/dev_checks.py`
and the project skill's `host_io.py`. The prepared contract/matrix/plan source,
dependency and external-input checks pass. This is proposal validation only,
not a successful authoritative preflight. The proposed contract SHA-256 is
`7aa4ed3bb760ce0cc0a5acdaaa9e15a85bad30785f73cd0644da29ddbb76cad4`.

The existing local commit authority remains valid and must not be requested
again. The only additional decision is whether this unadmitted v14 may receive
that narrow frozen-metadata correction, with all pre-correction originals and
the failed preflight retained. Execution-contract sections 1 and 3 protect
frozen identity and lineage; this record does not silently relabel FROZEN as
DRAFT, overwrite it, change the validator, or skip the actual parent.

No command argv, criterion, threshold, timeout, source, old v11/v12/v13 record,
or physical allowance is part of the proposed correction. The only associated
changes are the same authoritative contract's bundle copy and derived
contract/matrix/plan hash bindings. New explicit authority is required for that
exception, not for ordinary local commits, a new agent, or device work.

After the metadata decision, the same independent reviewer can perform a fresh
standard preflight under a new output label. Only a real preflight PASS permits
the 19 already-planned offline commands, original-data adjudication, final
validation, a real bundle commit and a later FREEZE-INDEX commit. There is no
physical replay or automatic retry. The candidate-only stage still cannot
grant P3-5/P5 campaign or production-release eligibility, resolve trial5, or
manufacture the missing v12 original close receipt.

The authorization and host-review task records can be committed independently
of this blocked admission. Such a records-only commit is not `bundle_commit`
and receives no FREEZE-INDEX entry. Actual receipts and final write-audit results
are recorded in `E/records-commit.json` and `E/write-audit.json`, respectively;
neither is inferred from this plan. Shared main worktree/ref/index, devices,
historical evidence and the cumulative 3/3 remain protected. Main integration,
push, merge, CI and release are outside the current authority.

## Candidate Stage Closure

Date: 2026-10-14. This is the completed candidate-stage independent decision,
not another Spec or a new physical campaign. The governing Spec is still
`cb317aff:docs/ota-prompts/prompt-P3-4-experiment.md` and OTA-DEC-016.

The current user explicitly approved P34-V14-PREFLIGHT-01 and subsequent
necessary authorizations in this same local closeout. The original response is
retained in `E/metadata-correction-authorization.json` and in the committed
round15 inputs. Continue this bounded R/shared-Git-metadata chain without
repeated per-command, per-commit or per-agent permission questions. This does
not expand it to devices, additional OTA, shared main writes, publication,
product/gate changes or unrelated work.

The four v14 runner declarations were corrected under that authority; all
pre-correction bytes and the rejected preflight remain preserved. The admitted
v14 then completed its three reference commands and three transfer readers,
but native `fc.exe` rejected a POSIX-spelled input filename with exit 2.
Both actual inputs existed and were byte-identical. This reviewer preparation
error is not a failure of the accepted host code or firmware. v14 was sealed as
EVIDENCE_GAP with its complete reference EXECUTED PASS and its partial-command
failure intact. Missing downstream command receipts were not fabricated.

The direct v15 successor changes only the seven FC filename spellings to native
absolute paths. It keeps the same source, criteria, thresholds and originals.
The standard plan reuses the actual v14 reference PASS and requires 16 remaining
offline commands. All 16 and the final standard lineage validation passed.

| Criterion | Current execution | Decision and limit |
| --- | --- | --- |
| P34-CANDIDATE-REFERENCE | REUSED from v14 EXECUTED PASS | Same-group v10/v11 originals and valid MCU evidence; not an old v11 formal PASS or a new physical transfer. |
| Q-PREP-RESTORE | EXECUTED, offline | Original v12 full base/Boot bytes, six mailbox samples, preserved configuration, confirmation/health and erased journal verified; no new restoration. |
| Q-TRANSFER | EXECUTED, offline | Original zero-start 1 MiB App/MCU/RAM, one timely old-App sample, guard/clock/tick/WDT, later full target/Boot and actual archive/reader closure verified. Original v12 command exit remains missing. |
| P34-CANDIDATE-CLOSEOUT | EXECUTED, offline | Actual source/CI applicability, four original archives, dual-host Flutter logs, seven firmware suites, receiver containment/mutant and the closed caller repair verified; no build, CI or product-test replay. |

The adjudication is
`.acceptance-p3-4/round15/adjudications/candidate-original-review.json`.
The real contract/matrix are `docs/acceptance-contracts/P3-4-v15.contract.json`
and `.acceptance-p3-4/round15/evidence-matrix.json`. The matrix contains one
directly anchored REUSED criterion and three newly EXECUTED offline criteria.
The contract is bound to source `fcbace8b3f782714a139a77a12cb9305dbaef7cc` and
tree `7038ea9de58dba625d487caee57c6dfb130d04b6`.

The historical baseline lacks the modern runtime stamp. Its rejected modern
reader attempt and the two legacy record-shape mismatches are retained under
round15 `host/`. The final evaluation uses the existing strict envelope/sample
readers, recomputes the original timing/frame/discovery counts and verifies the
hash-bound historical parser reports. It synthesizes no runtime fields and
preserves missing/early ACK samples and parser exclusions. Original APK hashes,
declared factors and full image/Boot readbacks were checked; the missing old
source Git object is still not claimed to have been inspected.

### Applicability And Remaining Work

The supported candidate remains v2, 921600 baud, 2000 ms, retries 5, window 24,
batch 12 and write payload 244. The three 1 MiB observations remain
71.582792 / 71.316310 / 63.708034 seconds, each with 8192 usable ACK samples and
zero DATA retries. Reference P99 is 827159 us; the supplemental three-observation
P99 is 761183 us. Both support the unchanged 2000 ms clamp. These observations
do not populate an old calibration ledger or a final 30-run campaign.

115200 historical C0-C3 timing/factors are reconciled, including the absence of
a clear reuse-only gain and the incomplete old ACK samples. 230400 remains
unreconciled, not unsupported; the old 460800 failure/resume series is not an
equivalent current-v2 comparison. No current-v2 causal speedup is claimed.
BLE timing is not installation time; nested discovery and overlapping ACK work
are not added as exclusive phases. These limits do not justify an automatic
four-rate rerun or another OTA for this accepted candidate scope.

No additional device observation is required to close this candidate decision.
Final selected-group 30/30 and a genuine four-hour wall-clock campaign remain
with P5-1; real-backend 10/10 recovery remains with P3-5; P5-2 owns the applicable
physical-fault gaps. Their requirements come from the existing Spec and
OTA-DEC-016, not this report. Three ordinary transfers and host models cannot
prove those larger sample counts, continuous duration or real backend/physical
fault behavior offline. Trial5 remains explicitly deferred, unresolved and not
waived. Production release is still prohibited by the candidate contract.

### Local Delivery

The authorized evidence commit is
`15a025b9c2690e864456a32fb2820422846fb85b`. It contains the required v1-v15
history and original inputs without rewriting old results. 8838 exact selected
paths were checked against staged raw blobs and the committed tree; targeted
attributes preserve original P3-4 contract/evidence bytes across checkout.
Normal hooks passed. `E/bundle/verified.json` records standard self-validation
at the actual bundle commit. A later records-only commit registers the real
v14/v15 freeze-index rows; it does not change the accepted bundle.

The P3-4 candidate acceptance and local evidence delivery are complete. Main/PR
integration remains a separate, unperformed delivery action, so the project card
is not silently declared fully delivered. Shared main worktree/ref/index stay
untouched; no push, merge, CI, release, device action or new OTA occurred. Current
3.2.87/group16/CONFIRMED=4 remains a historical observation, not a fresh query.
The cumulative physical chain stays 3/3, not a permanent whole-project limit.

## Git Integration And Delivery

### Authorization And Scope

Date: 2026-10-14. The user answered the concrete Git-delivery plan:

> 那就做吧，全权授权给你

That plan comprises checking and updating existing PR #26, integrating the
approved governance and accepted commit history, necessary non-release CI,
merge-commit delivery to main, safe main synchronization and task/index records.
The same reviewer/root continues; routine steps within this scope need no new
per-command, per-commit or per-agent approval. This is the user's authority,
not permission created by this record or by candidate acceptance.

The active worktree is `D:/github/my/E-Track/.cache/p34-final` (R). Its project-local
delivery output is `.cache/p34-git-delivery-20261014`. The shared Git directory
`D:/github/my/E-Track/.git` is writable for the named branch/PR/main delivery.
The shared project `D:/github/my/E-Track` may be synchronized only without losing
or publishing unrelated existing work. No reset, stash, cleanup, squash, rebase,
force-push, global configuration change, device operation, extra OTA, release or
deployment is part of this plan. Old failures, contracts and action accounts stay
immutable; P3-5/P5 final campaigns are not executed by this Git closeout.

### Verified Starting State And Plan

- Local accepted branch: `acceptance/p3-4-v2-20261009`,
  `e63ea9e41bfce2a3cb8a0dfc74ff68130ff613f0`; tracked source was clean.
- Local main: `cb317affcd291695f42271084b4b305b0d7e6f8b`.
- The actual remote PR #26 was OPEN/DRAFT, head
  `352ad286a26fc49255a132e00b93090527253747`, base main
  `4e5ae68ccbaff9134a268e8aa3d284450ead5a84`. Its earlier green checks do not
  attest the new integration. The authenticated account has repository delivery
  rights; authentication values were not logged or copied into the repository.
- The initial protection inventory covers 31955 R files. The shared root has
  54 tracked modifications and 1166 untracked files, including about 1.58 GB of
  original content. Counts are this run's actual snapshot, not older handoff counts.
- Merge governance `cb317aff` into the accepted branch preserving both parents.
  Resolve document-only overlap by retaining v2 admission, the newer allocation
  of final campaigns, historical records and the actual v15 candidate decision.
  No firmware/App/host implementation or frozen bundle is changed by this merge.
- Check required integration CI and the source -> bundle -> integration ancestry.
  Historical bundles remain validated at their actual bundle commits, not rewritten
  to make the new top-level governance tree match an old freeze.
- After verified CI, deliver by merge commit, record real remote/main identities
  and update candidate-stage completion and downstream ownership. Preserve shared
  work in place if safe synchronization cannot retain its exact content.

Raw Git/GitHub command receipts, the write inventory and pre/post hashes remain
under the delivery output above. Publication preflight found no oversized Git
blob. Its bounded secret-pattern scan found two historical controlled-service
download signatures, both expired on 2026-10-11 under the existing 300-second
exclusive-expiry gate. Neither is an account credential; values/URLs were not
printed and original evidence was not altered. This scan is not a claim of a
universal secret detector. Ordinary push/PR workflow gates exclude Release and
Cloudflare registration; unchanged web-doc/backend paths do not request deployment.

At this entry, integration is in progress. No remote update, successful new CI,
PR merge or synchronized main is claimed before its actual receipt exists.
