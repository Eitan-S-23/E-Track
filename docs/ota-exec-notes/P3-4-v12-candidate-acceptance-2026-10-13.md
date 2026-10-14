# P3-4 Candidate Successor Execution Record

Date: 2026-10-13. Owner: the existing independent reviewer, not the implementer.

Latest execution: the approved device plan is finished; target 3.2.87 is fully
verified and retained. The new 1/1 qualification is consumed (historical 2/2,
cumulative 3/3 for this chain). Required old-App runtime originals were obtained.
The original transfer owner disappeared during final readback without an exit
receipt; v12 is recorded as EVIDENCE_GAP, not formal PASS. See Actual Closeout.

The current user approved the proposed minimum successor, release of the device
pause within that scope, and at most one additional qualification OTA. Historical
v10/v11 consumption remains 2/2; the new cumulative ceiling is 3 for this chain
only, not a project-wide cap. No push, CI, release, product or runner edits are
authorized. Shared root remains read-only.

## User Authorization Register

Latest decision: 2026-10-13, recorded at 09:41 UTC. The user explicitly approved
the exact slot-release question and requested that this session's permissions be
recorded in the project so successor agents do not ask again. This register
records user decisions; it neither grants new authority nor changes the Spec.

| ID | Approved scope | Limit and continuation rule |
| --- | --- | --- |
| P34-AUTH-MINIMUM | Release the device pause only for the approved candidate successor: read-only admission, one necessary complete-state preparatory restoration, one runtime-evidence qualification, full target/Boot verification and bounded closeout | At most ONE additional qualification OTA; historical v10/v11 2/2 remains unchanged, cumulative ceiling 3 for this chain only. Do not ask again for its unspent planned steps. |
| P34-AUTH-SLOT-01 | Recheck and remove ONLY the archived old query capture selected by `E/capture-slot-proposal/proposal.json`: its phone `events.jsonl`, `health.json` and one directory | Exactly two files, 5390 bytes, one slot. Preserve local originals, v11 and all other seven phone captures. No other old capture cleanup or collector-limit bypass. |
| P34-AUTH-NEW-CAPTURE | Archive/hash-check and prune only the new completed qualification capture through the existing closeout route | Does not authorize deletion of retained old captures. Failed/unverified originals stay preserved. |
| P34-AUTH-RECORD | Persist these decisions and actual consumption in this worktree's existing task record and successor evidence | No new Spec, generic permission system, source edits, extra Git commit, push, merge, CI or release. Shared root remains read-only. |
| P34-AUTH-HOST-COMMIT | Earlier scoped six-file host-remediation commit | Already consumed by `02013607ca38eaf5cff0d5c4fc3de8259fbff916`; not permission for another commit. |
| P34-AUTH-SEGGER | Existing 2026-10-07 standing allowance for automatic SEGGER native history/config updates | Only `C:/Users/SU/AppData/Roaming/SEGGER/`; not cleanup, adjacent paths or a broader device scope. All controllable outputs remain in R. |

The exact slot proposal SHA-256 is
`3ee1def0eafa658d37aa4876ae74a5218f0de0484231ece7ae68816098dc11df`.
Its private capture identity is kept in the proposal, not repeated in messages.
Machine-readable decision binding: `E/authorization.json`. Actual operations and
remaining quota are recorded in `round12/action-accounting.json` and original
receipts, not inferred from this authorization. The approval itself consumes no OTA.

At this decision, additional OTA consumption is 0/1 and preparatory restoration
is 0/1. Successor agents must check actual receipts and remaining quota, then
continue the same approved scope without repeated permission requests. A new
deletion target, exhausted explicit quota, integrity/recovery uncertainty or a
different risk/scope still requires escalation. Do not repeat completed actions.

The same independent reviewer prepares, checks freezing, executes and judges.
No third freezing agent is required. Necessary already-authorized phone UI
actions use one current-session real mention with receipt and actual observation;
ordinary progress and final reports do not receive duplicate manual reminders.

Delivery status: this existing project task record is updated locally on
`acceptance/p3-4-v2-20261009`, based on `02013607`. It is not committed or delivered
to `main`; no such publication is claimed. Cross-worktree handoffs must point to
this exact record and current receipts until an authorized integration occurs.

## Inputs And Scope

- Active root: `D:/github/my/E-Track/.cache/p34-final`.
- Reviewed host commit: `02013607ca38eaf5cff0d5c4fc3de8259fbff916`.
- Governance: `cb317affcd291695f42271084b4b305b0d7e6f8b`, consumed from Git.
- Unique Spec: `docs/ota-prompts/prompt-P3-4-experiment.md` at that governance
  revision. This file is an execution record, not another Spec.
- Asset source: `1c3f7f49baa27c42452f7796839cea57ddd734b7`; Production,
  Firmware and Flutter profile inputs are unchanged at the reviewed host commit.
- Base/target: the existing 613952-byte 3.2.86 -> 3.2.87 pair and original
  group16 Boot in `round11/inputs/live-inputs.json`; no substitute build.
- Reference: 1048576-byte ETU, SHA-256
  `8373305b6817081106ad35c840ef87bf2d4210ffa2e8b9e881e0799ad1ff9e47`.
- Parameters: v2, 921600, timeout 2000 ms, retries 5, window 24, batch 12,
  negotiated write payload 244 bytes. Existing UI and foreground route only.

## Minimum Operations

1. Verify inputs and original records, then read-only phone/owner and MCU
   admission. Preserve the old lock until its owner and device outcome are
   reconciled. No deletion based only on an old PID.
2. Freeze a direct P3-4-v12 successor with the actual v11 parent and standard
   rerun plan/preflight. Independently evaluate the existing v10/v11 originals
   for candidate evidence, not another physical OTA or retroactive formal PASS.
3. If current target and backup/config/Boot admission pass, perform at most one
   necessary preparatory complete-state restoration through the already-tested
   restore helper and ordinary Boot. No direct App-only downgrade or Boot write.
4. Execute at most one new reference transfer to obtain the necessary old-App
   stack/guard, SysTick/tick and WDT originals before reboot. Single sample,
   original absolute deadlines, save before decode, no automatic retry.
5. Verify full target/unchanged Boot/confirmation/health, archive only this new
   capture using the existing byte/hash-checked closeout, and close owned services.
   Retain target 3.2.87; no restoration solely to prepare a nonexistent next cell.

v11 phone originals and every historical result remain preserved. Do not repeat
the completed v10 cleanup. Admission must establish a free capture slot before
any preparatory MCU mutation; a full store is not permission to delete an old
capture or weaken the collector limit.

## Criteria And Boundaries

The runtime evidence requirement comes from `ota-ble-v2-contract.md`, Ownership
And Boundedness, and the original Q-TRANSFER criterion. Empty/short-prefix or
post-reboot RAM cannot cover END/finalization and the missing transfer context.
The v11 RTT is valid and decodable but contains no stack/guard/SysTick/WDT dump.

Prospective scope is candidate evidence and necessary local safety only. Do not
run the old four-rate/twelve-cell matrix. Old Q-RESTORE stays NOT_OBSERVED; the
new plan does not claim that its preparatory restoration satisfies that old
chronological obligation. v11 Q-TRANSFER remains FAIL / harness / HARNESS_FAIL.
Qualification observations are not added to old calibration or final campaigns.

Final 30/30 and real four-hour validation belong to P5-1; real-backend 10/10
recovery belongs to P3-5, with P5-2 assessing applicability. Trial5 remains the
previously deferred unresolved historical risk. No automatic project release.

Retain the existing finite phase budgets, including the 120-second start window,
300-second transfer observation and bounded salvage/closure. Physical identity,
ownership, integrity or recovery uncertainty stops affected mutations. A new
failure is retained and is not permission for another OTA.

## Output Boundary

Only new outputs in `.cache/p34-v12-candidate-20261013/`,
`.acceptance-p3-4/round12/`, the new v12 contract, and this task record.
All tool home/AppData/temp/cache/log/readback paths use the existing contained
helpers. SEGGER automatic history/config updates remain covered only inside
`C:/Users/SU/AppData/Roaming/SEGGER/`; no cleanup there. No shared Git writes.

Admission, freeze, execution and final disposition are recorded as they actually
occur. This initial record makes no device or formal PASS claim.

## Actual Admission And Resource Blocker

The first private-ADB admission found the authorized phone absent. Its original
failure is preserved in `E/phone-admission/`, where E denotes
`.cache/p34-v12-candidate-20261013/`. The owned ADB server closed normally and
its private port was verified closed. A real current-session Feishu reminder
requested only phone USB reconnection/unlock, not a chat response or OTA.
The receipt is `E/notices/usb-connect.receipt.json`; it is not resent.

The phone was then actually observed connected. `E/phone-admission2/result.json`
verifies the installed APK, all eight capture health records, no active transfer,
and byte-identical retained v11 snapshot. The store has 8/8 captures, so the
unchanged `Phone.provision()` cannot create another one. This is a real admission
resource blocker, not a product failure or a reason to change the collector.

Independent standard-Commander readback in `E/mcu-admission/` verifies the full
613952-byte target 3.2.87, unchanged group16 Boot, CONFIRMED=4, healthy/idle state,
and the existing storage observations. This was read-only preparation, not a
reset, installation, rollback, fresh transfer, or formal Q-TRANSFER PASS.

One older non-v11 query-only capture was copied, without any phone writes, into
`E/capture-slot-proposal/originals/`. Both files match their on-phone SHA-256:
2 files, 5390 bytes total; events contain 16 records / 5153 bytes, with zero OTA
starts and zero ends. The immutable exact deletion proposal is
`E/capture-slot-proposal/proposal.json`. No file was unlinked, no App was stopped,
and v11 and the other phone captures remain unchanged. Deleting this one archived
phone copy needs separate explicit authorization; old v10 cleanup is not repeated.

`E/draft-contract.json` is DRAFT only. `E/draft-review.json` and
`E/draft-objects-review.json` check its three criteria/five commands, actual
Git source objects, current worktree profiles and external inputs. Only Validation
changed from v11. These are draft checks, not a formal NOT_RUN preflight or a
new frozen contract. The authoritative v12 contract and matrix do not yet exist.

`round12/action-accounting.json` records prior consumption 2, newly authorized 1,
new consumption 0, no preparatory rollback, and no calibration/final campaign.
The original lock remains byte-identical and has not been removed merely because
its old PID is absent. All owned phone/MCU reader processes were closed.

Next owner remains this independent session. After exact slot-release approval,
recheck and remove only the two already-archived files and their single old-query
directory, verify the other seven captures including v11, reconcile/archive the
old lock, freeze/check the successor and continue the approved finite plan.
Do not request another OTA quota, rebuild unchanged assets, re-review A/B or
delegate to a separate freezing agent for that continuation.

## Authorized Slot Release Continuation

The user has now explicitly granted P34-AUTH-SLOT-01. The preceding resource
blocker is historical, not a request to seek that permission again.

Before unlinking anything, the first cleanup preparation stopped because v11's
live `health.json` time changed from 09:02:54 UTC to 09:47:18 UTC. All its other
health fields, event hash and immutable snapshot hash were identical, as were
the exact approved deletion bytes. No unlink intent or phone deletion occurred.
The App's periodic checkpoint updates health time even without new records
(`ota_observation_log.dart`, periodic checkpoint). This is not a new OTA or the
already-fixed atomic-replacement race.

Preserve `E/capture-slot-release/failed.json` and its first `before.json`. The
continuation compares every protected file hash except live health JSON, whose
full fields must still match after removing only `time`; that time must parse
and move forward. The selected old query's two files still require exact hashes.
No event/snapshot/counter/error/domain check is relaxed. This is a correction to
the reviewer's unfrozen one-off cleanup glue, not a product/acceptance runner edit.

The v11 lock was archived byte-for-byte and reconciled using actual target
readback plus closed command/readers and current process checks, before removal.
The stopped cleanup owner left a new lock; it is reconciled from its failed
pre-delete check, zero unlink intents and normal private-ADB closure before
continuing the same still-unperformed authorized unlink. No PID-age-only deletion.

## Actual Closeout

The exact approved query cleanup finished in
`E/capture-slot-release/heartbeat-resume/`: two files and their one phone
directory, 5390 archived bytes, seven retained captures. All non-health bytes
were unchanged; only the independently explained live health time refresh was
allowed. The v11 immutable snapshot remained byte-identical. The original v11
lock is preserved in `E/lock-reconciliation/original.lock`; it was not discarded
on PID age alone. Both failed pre-delete preparation and successful unlink are
retained. P34-AUTH-SLOT-01 is consumed and must not be executed again.

The real v12 contract and standard same-lineage plan/preflight were created at
`docs/acceptance-contracts/P3-4-v12.contract.json` and `round12/`. Only Validation
changed from the previous frozen input groups. All three frozen original-evidence
commands exited 0. Existing v10/v11 records remain 71.582792/71.316310 seconds,
14.305114/14.358567 KiB/s, zero DATA retransmissions and 8192 ACK samples each.
Their same-group nearest-rank ACK P99 is 827159 us and supports the unchanged
2000 ms candidate timeout. They do not establish 30/30 stability or a soak.

The one necessary preparatory restore exited 0. Independent re-reading of its
saved bytes verified full 3.2.86, unchanged Boot, CONFIRMED=4, four READY and two
committed mailbox samples, preserved configuration and an erased 4096-byte
staging journal. This was one restoration, not an extra OTA.

The user observed the new upgrade complete. Original v12 App and MCU records
independently establish one zero-origin complete 1 MiB transfer with unchanged
candidate parameters: v2, 921600, timeout 2000 ms, retries 5, window 24, batch 12
and write payload 244. Transfer time is 63.708034 seconds, 16.073326 KiB/s,
zero DATA retransmissions and 8192 valid ACK samples. Do not attribute its
timing difference to the host-only A/B repair or pool it into an old campaign.

The actual start was observed within the original window. Exactly one old-App
terminal RAM sample completed inside its original absolute deadline, before
semantic decode. Its 420 bytes equal the CRC-valid RTT record; terminal=0,
clean=true, initial/final durable=0/1048576. Payload read is unused and verify
has 256 calls. Both header reads and VTOR bind the old App, not the new target.
The 32-byte guard is intact; 5092 of 8192 stack bytes remain painted (observed
high-water 3100 bytes, not a whole-program worst-case proof). Clock is 288 MHz,
SysTick is valid, tick advances by 103, and WDT registers 5/3124 match the
existing nominal 10000 ms configuration. A/B remain CLOSED; this is the missing
specific runtime observation, not an unrelated new implementation change.

### Interrupted Original Command

`CMD-Q-TRANSFER` reached ordinary target confirmation and final full readback.
The original host owner then disappeared: its final Boot copy was complete but
its App file was zero bytes, with no commander closure, command closure or action
`result.json`. Current process/port checks found no surviving owner or readers.
The underlying cause is not established and is not attributed to a late click,
the product, A/B, or a specific user message. No exit code is invented.

The original phase deadline was not extended. A separate diagnostic closeout in
`round12/diagnostics/post-interruption/` used the existing read-only MCU and Phone
primitives, after reconciling ownership. It verified full target 3.2.87, original
group16 Boot, CONFIRMED=4, advancing health and idle storage. It then archived and
hash-checked only the new completed capture using the approved closeout route,
pruned that capture, rechecked retained v11, and closed private ADB. No reset,
installation, rollback or additional OTA occurred. Seven phone captures remain.

| Decision | Result and original location |
| --- | --- |
| P34-CANDIDATE-REFERENCE | EXECUTED PASS; `round12/commands/CMD-REFERENCE-*.{stdout,closed.json}` and `round12/adjudications/candidate-reference.json` |
| Q-PREP-RESTORE | EXECUTED PASS; `round12/ops/cmd-q-prep-restore/` and `round12/adjudications/preparation.json` |
| Requested local runtime/product observations | Independently verified; `round12/ops/cmd-q-transfer/mcu/0003-terminal-before-reboot/`, the original App snapshot and `round12/adjudications/runtime-observations.json` |
| Original Q-TRANSFER formal completion | NOT_OBSERVED, not PASS; the physical OTA did execute, but its required original close/action receipts do not exist. `round12/adjudications/interrupted-command.json` preserves this distinction. |
| v12 overall | EVIDENCE_GAP. A successful final bundle validator validates the honest record, not missing original execution or product release. |

This is not a reason to repeat the successful OTA. The decisive runtime and
final identity originals now exist; any future formal successor should evaluate
their applicability offline under execution-contract section 0, retaining this
interruption and the v11 failure. Do not silently waive the old frozen closeout
obligation, create an old PASS, substitute a synthetic exit, or recreate lost
receipts under their original names. The missing item is original host-command
completion evidence, not an uncollected old-App stack/clock/WDT observation.

### Remaining Authority And Responsibility

- Additional qualification: consumed 1/1. Historical v10/v11 remains 2/2 and this
  chain totals 3/3. These are not permanent project-wide device limits.
- Preparatory complete-state restoration: completed 1/1. No post-transfer restore
  was needed or performed; retain the verified target.
- Exact old query cleanup: completed once. New completed-capture cleanup: also
  completed once. Neither authorizes another old-capture deletion.
- The current independent reviewer owns this conclusion and the frozen-record
  gap. No new implementer batch or third freezing agent is needed for A/B.
- Before another long device campaign, the host-execution owner should resolve
  the interrupted owner/receipt path using host-only lifecycle checks, not OTA.
  A host harness test cannot manufacture this already-missing exit receipt.
- P5-1 still owns final same-group 30/30 and real four-hour validation; P3-5 owns
  real-backend 10/10 recovery; P5-2 assesses applicability. Trial5 remains the
  explicitly deferred historical risk. No P3-4 task closure or production release
  is inferred from governance, these local observations, or bundle validation.
- Authorization is recorded in this existing project note and linked from the
  worktree collaboration index. The shared root, Git indexes, source files and
  old frozen records are not modified; no commit, push, merge or CI is performed.

### Validation And Write Audit

The full standard lineage final validator exited 0 and reports
`VALIDATION=PASS ... overall=EVIDENCE_GAP`. Its originals are
`E/host-run/final-validation.{stdout,closed.json}`; `E/sealed.json` binds the
immutable final matrix and contract. This validates the truthful evidence-gap
record, not a formal Q-TRANSFER PASS.

`E/phase2-after.json` preserves the actual write audit. Of the 2016 original
protected paths, 2015 are unchanged. The sole change is the retired active
`.cache/p34-live-device.lock`; all 157 original bytes are preserved with their
original hash in `E/lock-reconciliation/original.lock`. Its removal followed the
approved owner/outcome reconciliation, not PID age. The initial audit's strict
zero-change assertion reported that expected retirement; it is not erased.
`E/audit-disposition.json` independently binds and resolves this one expected
control-file lifecycle difference. All seven reviewed source files and both
Git indexes are unchanged. No old contract, matrix or original is rewritten.

The first diff check flagged mixed CRLF/LF in the modified collaboration index.
Only that operational index was normalized to LF; the final diff check exited
0. No acceptance profile changed, so no hardware or full regression was repeated.
Both initial audit outputs are retained rather than overwritten.

All selected outputs are under R: this task note, the local collaboration index,
the new v12 contract, E and round12. All owned readers and private ports are
closed, and no active device lock remains. No native SEGGER history file changed
against the phase-two baseline. External-default monitoring observed 18 metadata
differences; attribution is UNESTABLISHED, exact paths/metadata are in the audit,
and no external cleanup was performed. This monitoring is not a machine-wide
write trace and does not prove who changed those files. No external default path
was selected as an output by this session.
