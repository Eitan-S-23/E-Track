# Project Workflow Decisions

Owner: root session. User decisions: 2026-09-22. Scope: entire E-Track project.
Normative sources: [collaboration contract](../agent-collaboration-contract.md)
and [device experiment policy](../device-experiment-policy.md).

## PROJECT-01: Shared Rules Are Project-Wide

DECIDED. The first skill/feedback delivery was commit
`73a3563af99ac5a9e0931126be1bc508490cb049` on
`docs/flutter-debug-skill-feedback-20260922`, with working files only in a P3-4
worktree. Although its wording was generic, that was not project-wide integration.

Direction: publish root AGENTS routing, the generic contract, this shared index
and the [Flutter debugging skill](../../.agents/skills/e-track-flutter-debug/SKILL.md)
on main. Root and app CLAUDE files already import AGENTS; do not fork duplicate rules.
Existing agents/worktrees must receive the published revision before new work.
Keep task state/evidence outside normative acceptance profiles and preserve dirty
product changes when integrating only governance files.

Verification: resolve root/app entry points and shared links, validate the skill,
and run profile-ownership plus governance CI regressions. Root owns integration;
every recipient owns loading that revision, not rediscovering prior rejected routes.

## PROJECT-02: Task-Bounded OTA Work, Not Tiny Quotas

DECIDED. Replace agent-created per-OTA/per-reset caps with the finite task matrix
and risk-based stopping conditions in the device policy. The user explicitly
requested less restrictive execution and continuation until real intervention.
This is not a GitHub storage/billing change or an unlimited hardware allowance.

Direction: plan candidate preparation and screening together, act serially on the
one device, and automatically perform justified in-scope recovery/verification.
Preserve actual attempts and resolve uncertain outcomes before repeating them.
Do not modify historical ledgers or treat collector repair as a reason to redo OTA.

## PROJECT-03: Equivalent P3-4 Comparison State

DECIDED, conditional execution. Returning to 3.2.6 is unnecessary for coding,
host tests or all possible link diagnostics. It is necessary for a controlled
repeat of the existing admitted 30206-to-30207 FULL package: current 30207 is not
an equivalent initial version/BCB/staging state. The user authorizes that return
if needed. Root must first establish a supported complete-state restoration,
not just overwrite App or invent BCB bytes. Restore only when the next prepared
experiment needs it, and retain a verified target at the end.

Known evidence: the 284643-byte baseline completed at 115200 with approximately
1.038 KiB/s; discovery and platform-write timing dominate the observed App path.
That package is not the 1 MiB reference and MCU UART/staging timing is not yet
isolated. 115200 is a control, not a selected ceiling or proof higher baud cannot help.

Prepared sender candidates are in commit
`fbc3b5aae468e9ab382ac018c1247de43d890491` on
`dev/flutter/p3-4-batched-link-candidates`, documented at
`docs/ota-exec-notes/P3-4-batch-optimization-2026-09-22.md` in that commit.
Both-host development tests passed; candidate APKs and optimized physical
throughput were not produced by that checks-only run. These source-pinned task
facts are a handoff, not independent acceptance or a mainline product merge.

## PROJECT-04: Reuse Tools Before Replacing Them

DECIDED. User request, 2026-10-07: retain the unnecessary group16 flash-tool
detour as a project-wide lesson. Root owns this record. Normative prevention is
[Reuse Before Custom Tooling](../agent-collaboration-contract.md#reuse-before-custom-tooling);
this case record does not grant hardware operations or alter acceptance gates.

### Root Cause

An implicit assumption became a prerequisite: root treated no-reset/same-CPU-context
resume and exhaustive low-level write auditing as necessary for replacing Boot.
There were genuine risks, including interrupting SD activity, erasing outside the
approved Boot prefix and changing persistent state. Those justified bounded
operations, backup and verification, but did not by themselves require a custom
Flash controller. Installed SEGGER Commander support had not first been ruled out.

### Why The Detour Grew

Root implemented J-Link SDK/AP/DP-based control, Flash sequencing, admission,
settlement and recovery helpers. This was not a new USB/SWD implementation from
scratch, but it still replaced work the vendor tool could perform. Each helper
introduced further test/review dependencies. Local correctness work did not answer
the prior question of whether this route was necessary. Group16 remained uninstalled
while support infrastructure expanded; those tests were not speed measurements.
The error was route selection and late reassessment, not missing user permission.

### Evidence And Corrected Route

The original [recovery note, section 65](../ota-exec-notes/P3-4-recovery-provisioning-design-2026-10-05.md)
records same-context preparation and the custom programming design; section 66
records the user-directed switch to installed SEGGER V8.18 Commander, device
`AT32F435RGT7`, SWD 1000 kHz. Root retained fresh backups, a storage-idle halt,
watchdog handling and exact write bounds, then used standard `loadbin`/`verifybin`,
complete readbacks and deliberate post-verification reset/start. The load command's
`noreset` option did not preserve CPU context or prohibit that later deliberate reset.

The original SDK log confirms that only `0x08000000..0x08003FFF` was programmed;
the remaining Boot bytes and App were verified unchanged. This proves a standard
route sufficed for this operation, not that every target or recovery task is covered.
Full 64 KiB Boot readbacks remain verification assets, never blanket flash inputs.
Do not disconnect J-Link power, use mass erase or replay consumed scripts.

Group16 then completed its first real OTA comparison: post-END to identity fell
from 20.494210 s to 17.029138 s; combined transfer/post-END time fell from
38.392638 s to 34.512661 s. These are single-run header-only observations, not
stability acceptance or pure Flash/EEPROM timings. Debugger download duration is
not OTA performance. The 50 kB/s and 20 s objectives remain unmet.

Original source/evidence checkpoint: local `main` commit
`88549cde315fdc99ccf84985854b235ac2fde3ab`,
[checkpoint contents](../ota-exec-notes/P3-4-group16-checkpoint-2026-10-07/README.md).
That commit is local, not a remote delivery claim. It predates this lesson/rule
update and must not be cited as containing the new governance text.

### Prevention And Verification

Wrong: require original-context resume without establishing its necessity, build
a Flash-control stack to meet it, then treat its growing test count as progress
toward faster OTA. Correct: establish the real safety boundary, validate the
vendor route, add only the missing orchestration, verify exact effects and measure
the candidate. When a genuine capability gap exists, document it and bound the
replacement instead of applying a blanket ban on custom tooling.

The same decision applies to build wrappers, collectors and archive tools: a small
adapter is not the mistake; replacing supported functionality without evidence is.
Preparation has value only through its necessary contribution to the next result.
Do not keep an unnecessary route because implementation/review already cost time.

Owner/next: each implementing agent checks tool necessity before expanding scope;
reviewers challenge unsupported constraints and propose a narrower viable route.
For this documentation change, verify AGENTS routing, shared links and governance
profile ownership with host checks only. No new firmware build, OTA or flash test
is required; preserve historical failures and frozen evidence. Rules must be
explicitly committed/delivered under Git authority before claiming other worktrees
or already-running agents have received them.

## PROJECT-05: J-Link Installation Before OTA Measurement

DECIDED. User request, 2026-10-08: avoid unnecessary OTA provisioning when
standard J-Link can install the candidate. Normative prevention is
[Candidate Installation: J-Link Before Extra OTA](../device-experiment-policy.md#candidate-installation-j-link-before-extra-ota).
Root owns this record; every device agent owns applying the route decision.

### Incident And Cause

The ACK-binding screen used 30282 -> 30283 to install the changed receiver, then
30283 -> 30284 to measure it. The first transfer was received by the old code;
only the second exercised the correction. Root reused the prepared two-OTA
workflow without first establishing a concrete reason that standard J-Link
could not perform the installation. That imposed another phone interaction and
upgrade cycle on the user. A valid distinction between installation and testing
did not justify choosing OTA for both. This was route selection, not missing
permission or a demonstrated J-Link capability gap.

The [screening note](../ota-exec-notes/P3-4-transfer-next-2026-10-07.md) records
both successful images and original observations: transmission14.024562s before
versus14.757523s with the correction. The local ACK cost fell but transmission
did not improve in that screen. Neither this result nor the prior two-OTA plan
proves that an OTA installation was necessary. No retrospective J-Link trial is
required, and this record does not claim direct programming was tested for every
BCB/staging state.

### Prevention And Verification

Wrong: assume every receiver change requires the user to perform two upgrades,
or cite generic persistent-state risks without checking the actual state.
Correct: check current state and exact GCC candidate, install through standard
J-Link when compatible, verify the retained image/Boot/health, then perform the
planned OTA observation. Keep an OTA installation only when its behavior or
initial-state transition is actually under test, or a specific evidenced
constraint rules out safe direct programming. Do not weaken recovery checks or
replace the vendor flasher to avoid the extra OTA.

Verification for this lesson: root AGENTS and the shared index must route to
this record and the normative device policy; host governance routing/link tests
must pass. No hardware rerun, firmware rebuild or historical evidence rewrite.
This update is local until explicitly committed and delivered; do not claim
other worktrees or running agents have received it merely because it exists here.

## PROJECT-06: Only Manual Mentions For Mid-Task Blockers

DECIDED. User clarification, 2026-10-09: normal completion already produces a
bridge @mention. A manual real @mention is needed only when the agent keeps the
current execution open and cannot continue without the user's intervention,
such as reinserting an SD card. Root owns this record; the normative rule is
[User Intervention Notifications](../agent-collaboration-contract.md#user-intervention-notifications).

The earlier rule treated every necessary user response as a manual-notification
trigger. Sending separate reminders alongside the completed P3-4 pre-review
handoff and final v2 scope-approval question therefore duplicated the bridge's
completion notification. Successful send receipts prove delivery, not necessity.
Preserve those historical receipts unchanged; do not replay them.

Further user clarification, 2026-10-10: root incorrectly sent a manual @mention
for PR/CI authorization while other preparation remained active. A chat reply
was required, so keeping the execution open did not justify that reminder.
The earlier "mid-task blocking approval" exception is withdrawn. Preserve its
send receipt as historical evidence of the mistake, not permission to repeat it.

Direction: a manual reminder requires an already-authorized action outside chat,
an execution that remains open, and no required chat reply. Observe the device
or external state after actions such as card reinsertion or a phone dialog;
do not require a chat acknowledgement. Requests requiring a chat reply never
use manual @mentions. Authorization, choices, confirmation and missing
information belong in a normal final reply followed by waiting for the answer,
even if another task or worker could keep running. Final reports and handoffs
also use automatic completion only. Check the receipt for an eligible manual
reminder; ordinary progress and unchanged pending requests need no reminder.

Verification: host governance tests cover both final-reply exclusions, positive
mid-task cases and the shared entry/skill links. No bridge test message, device
operation, firmware rebuild or historical acceptance rerun is needed. This is a
notification-policy clarification, not approval of the v2 protocol or its formal
acceptance scope. The update remains local until explicitly committed/delivered;
do not claim other worktrees or running agents have received it.

## PROJECT-07: Evaluate Existing Evidence Before Repeating Work

DECIDED. User request, 2026-10-13: audit acceptance for every unfinished task,
seek agreement from the already-bound codex-rawchat reviewer, implement the agreed
changes, then have that reviewer assess the actual delta. Root owns implementation.
This requested review is not a new permanent approval layer. Normative routing is
[execution contract section 0](../acceptance-execution-contract.md) and
[OTA-DEC-016](../ota-spec-decisions.md).

### Findings And Direction

- Freezing identifies the admitted inputs and criteria; it does not require a
  third agent. Default to the implementer and one independent reviewer, who may
  prepare/check/freeze/execute/adjudicate. Existing authorization remains bounded.
- The board and templates asked for a second role-specific prompt while readiness
  requires one canonical task Spec. Both roles now share that Spec and hand off
  facts in the existing task note, not another normative instruction set.
- An empty current matrix is not zero project progress. Evaluate earlier developer
  and user observations against actual versions, parameters and original records.
  Formal REUSED retains same-task original anchors. Hash-bound external originals
  can support an independently executed offline evaluation, never a fictional new
  device action, fabricated formal origin or unobserved field.
- P5 instructions still required obsolete worktree manifests; P3-5 excluded failed
  attempts and P5-1 automatically replayed anomalies. Use v3 Git identities and
  real dependencies, retain failures and explain the smallest justified new
  observation. Parser or packaging repair alone is not a reason to replay OTA.
- P3/P5 reliability campaigns overlapped. One stable-candidate final campaign is
  assigned below. Local functional and safety checks still occur before relying
  on a change; actual battery, power-cut and background conditions are not replaced
  by debugger power/reset or foreground success.
- P4 completion required production release while P5 depended on P4 and barred
  that release. Shared staging rehearsal now qualifies the P4 stage. Configuration
  preparation uses implemented wiring, not completed upstream acceptance.
  Production still requires P5, owner/environment approval and the existing
  rebuild/hash-equivalence check. P5 does not depend on its own deferred tests.
- P5-3 pure documentation review needs real link/command/risk checks and independent
  judgement, not another hardware-style JSON bundle. Lightweight packaging never
  waives required tests, CI or an existing frozen obligation.

### Remaining-Task Disposition

These are fourteen board entries, not fourteen findings of absent implementation
or missing historical observations. Unknown coverage remains unreconciled, not
automatically NOT_DONE. This change does not alter task status or dispatch eligibility.

| Entries | Acceptance treatment |
| --- | --- |
| P1-6 | Reconcile fourteen recorded AUTO results by current dependencies; do not restart twenty cases. Preserve real power-cut gaps and share applicable originals with P5-2. |
| P1-7 | Reconcile existing startup/power-hold records; measure only genuinely missing candidate timing, key-hold or battery conditions. |
| P3-4 | Candidate implementation, parameter basis and necessary local checks. Reuse valid baud measurements; no default four-by-three or collector-only qualification OTA. v11 remains HARNESS_FAIL; missing pre-reboot RAM is not repaired by RTT reinterpretation or this policy. |
| P3-5 | One real-backend ten-disconnect group on applicable candidate inputs, retaining all attempts. A controlled local service or ordinary success does not cover it. |
| P3-8 | Real background/lock-screen ownership, durable progress, notification, final identity and teardown. No generic thirty-run campaign per UI scene. |
| P4-1, P4-4 | One shared authorized staging rehearsal, separate pipeline/configuration judgements and unchanged production promotion barriers. |
| P4-2 | Independently evaluate SQL uniqueness/atomicity and selection/API originals; no phone OTA solely to validate SQL. Real integration requirements remain in P3-5. |
| P4-3 | Admin/transaction/retract/stop tests and necessary UI observations, not firmware replay. Share applicable integration originals for actual effects. |
| P5-1 | Four SD/BLE x full/patch combinations plus one same-configuration 30/30 reference-1-MiB series and one real four-hour soak; eligible predeclared observations may serve multiple criteria. All numerical, retry, integrity and safety gates remain. |
| P5-2 | Evaluate applicable P1-6/P3-5 originals, then inject only uncovered or invalidated conditions. No reset-as-power-cut, failed-run replacement or cross-configuration pooling. |
| P5-3 | Independent document/link/command/risk review using existing product conclusions. No new OTA or mandatory separate formal contract for pure docs. |
| CI-ARTIFACT-01, CI-ARTIFACT-02 | Source/host checks plus applicable real CI receipts. Missing remote evidence stays unknown; do not delete artifacts or dispatch only to prove reviewer tooling. |

### Preserved Material And Review

The pre-existing untracked historical host-remediation instruction was reclassified
without content changes, not deleted or exempted from the uniqueness guard:

- Old path: `docs/ota-prompts/prompt-P3-4-implementation.md`.
- New path: [dated host-remediation supplement](../ota-prompts/supplement-P3-4-host-remediation-2026-09-20.md).
- Original, pre-move snapshot and destination: 13533 bytes, SHA-256
  `fc119919f0efef2be5c9295574a763982ab8027cc2bd1515cce04c0111c79158`.

codex-rawchat explicitly agreed to `FLOW20261013-FULL-R1`, proposal SHA-256
`b33e7769850431ab567fa016f5fd0a64983acae89e2b818ab140b1a2c3b36bac`, and
`FLOW20261013-ROUTING`, addendum SHA-256
`88e524b29c68100d96542f3a89e3d543f25ceade7b83b93248495d4b7de6d2ec`.
The peer reviewed supplied material, not an independently accessed filesystem;
plan agreement is not implementation approval or product acceptance.
Original replies, pre-edit snapshots and test receipts are retained under
`.cache/acceptance-flow-review-20261013/`. The baseline of 31 targeted tests had
30 passes and one existing duplicate-prompt failure; that failed receipt remains
unchanged. Post-edit verification and implementation review are recorded separately.

Implementation review covered four actual-diff packets, not just the proposal.
The peer identified three boundary issues: valid originals versus invalidated
same-condition evidence; post-P5 published-asset verification; and single-sample
retry limits versus justified later verification. Root accepted and corrected
all three, including the corresponding positive/negative governance tests.
The first post-edit run had 102/103 passes and one preserved wording-guard failure;
after correction and added boundary tests, the affected suite passed 41/41.
The other 64 checks, including 35 efficiency checks, passed in the first run and
were not needlessly repeated. This is 105 checks covered across scoped runs, not
a claim of one 105-test run, remote CI or product acceptance. Final peer verdicts
and their exact reviewed material hashes are retained with the original receipts.

Delivery is local and uncommitted until explicitly authorized. No device action,
CI dispatch, remote configuration or publication is granted by this change.
The p34-final worktree, its frozen bundles/tools/lock, original product work and
Git index remain outside the edit scope. Do not claim another worktree or running
agent has received these rules until an authorized delivery actually occurs.
