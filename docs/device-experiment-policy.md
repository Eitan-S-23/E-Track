# Device Experiment Authorization

## Scope And Authority

User decision, 2026-09-22: make OTA experimentation less restrictive and continue
the approved work until actual human intervention is necessary. This project-wide
policy replaces agent-invented per-invocation quotas for future development work.
It applies when the user has authorized the device/task and its operating route;
it does not turn an arbitrary coding request into hardware or deployment permission.

For the current P3-4 continuation, the user has also authorized restoring 3.2.6
if an equivalent comparison genuinely requires it. The root agent determines
necessity and validates the complete recovery route before acting, without asking
for the same permission again. App-only downgrade across changed BCB state is not
an acceptable implementation of that authorization.

This concerns physical OTA experiments, not GitHub billing/storage quotas or the
development-artifact deletion policy. It does not authorize releases, production
deployment, unrelated devices/data, Boot replacement, arbitrary EEPROM/BCB edits,
clearing app data, bypassing security, or new project-external filesystem writes.
Later explicit user restrictions and actual resource limits take precedence.

## Plan Once, Execute The Batch

Record the following in the existing task note before the first device mutation:

| Field | Required content |
| --- | --- |
| Authority and ownership | User decision, task/device IDs, sole operator and writable root |
| Inputs | Tested revision, APK/package hashes, starting App/Boot/BCB/staging identity |
| Experiment matrix | Candidate axes, finite cells/repetitions, screening and stopping rules |
| Operations | Necessary install/launch, transfer, supported AT tuning, reconnect and verified restoration routes within the authorized task |
| Recovery | Exact known-good assets, supported complete-state recovery, final retained state |
| Runtime | Finite per-operation/worker deadlines, progress watchdog, apply/verify/cleanup allowance |
| Evidence | Original results, action journal and failed/uncertain outcomes |

The matrix is an execution plan, not a new approval ceremony. The root agent may
prepare and refine it within the user's task/risk boundary and proceed. Changing
an in-scope candidate or adding evidence-based targeted validation does not require
another user question. Record the reason and the new finite work remaining; do
not extend an experiment indefinitely or silently cross into a different risk class.

No default "one OTA", "one reset", "one installation", three-round ceiling or
30-minute whole-task limit applies. Counts derive from the useful planned tests,
not an arbitrary small quota. Screening repetitions, shortlisted comparisons and
an explicitly requested reliability campaign are different stages; do not run a
full campaign on every candidate. One physical link has one owner and runs serially.
Prepare independent candidates, host tests and CI artifacts in a batch first.

Within the authorized plan, routine reconnects, needed verified debug-APK installs,
safe baseline restorations, supported baud comparisons and targeted reruns after
a diagnosed fix proceed without per-command permission. Do not reinstall, reset
or reflash to compensate for a broken host collector when existing evidence or a
host repair suffices. A planned statistical repetition is not a blind failure retry.

Workers still have finite lifetimes. CI/setup time does not consume an OTA count;
start the device window near actual use. The agent may restart an expired owned
host window after checking closure and live state. It must not shorten transfer,
ordinary Boot apply or final verification to fit a spent setup window.

## Accounting And Failure Decisions

Use one small action journal, not a new ledger/harness per question. Record a
stable action/cell ID and `planned`, `started`, `completed`, `failed` or `unknown`,
with the actual command, input identity, observation and result. A host reservation
is not proof a device operation ran. An uncertain operation is not free to repeat:
reconcile the actual device/CI state first. Host repair never erases prior attempts.

| Observation | Required next action |
| --- | --- |
| In-scope planned cell; prerequisites satisfied | Run it without requesting another quota |
| Host failure before any device command | Repair/self-test the host and resume; no fictional OTA consumed |
| Known failed observation with a diagnosed fix/state change | Preserve the failure; run the smallest relevant test within the plan |
| OTA may have succeeded but collector/receipt failed | Retrieve original App snapshot and inspect device identity; do not repeat OTA |
| Same failure, no changed input or discriminating new evidence | Stop that retry path; investigate or switch to an already-authorized safe route |
| Unknown device outcome, integrity failure or recovery no longer works | Pause dependent mutations; determine state or request the precise missing intervention |
| Planned screening complete | Select evidence-supported finalists; stop unhelpful cells rather than spending a quota |
| New destructive operation, device, side effect or explicit user cap reached | Ask once for the exact additional scope, while independent safe work continues |
| User must unlock/approve a dialog, tap an App control or physically reconnect | Ask for that concrete action only when the prepared route needs it |

"Continue until intervention is needed" means continue executable work, not stop
to report each successful substep. Progress updates are not permission requests.

## Existing Contracts And Helpers

Do not alter closed action journals, failed receipts or frozen acceptance bundles.
Their historical caps remain part of their original execution record. Reference
this later decision in the new task plan rather than pretending old credit remains.
An old source-pinned one-shot controller must not be replayed unchanged or patched
while running. Reuse its safe primitives through a tested new entry when needed.

Formal independent acceptance still follows
[the execution contract](acceptance-execution-contract.md): committed inputs,
approved frozen criteria and machine-computed minimum reruns. This policy changes
operating cadence, not CRC/sequence/credit/durable guarantees, performance gates,
evidence validity or acceptance independence. If a still-active frozen contract
encodes a conflicting execution plan, publish its successor before formal execution;
do not retroactively rewrite it. Development checks are not formal acceptance.

## Example

Good: prepare GATT-reuse and supported write-mode candidates together; screen a
declared matrix with the same legal package and restored initial durable state,
then compare supported baud rates on the shortlisted sender. Count actual results
and preserve failures; retain the verified target at closeout.

Bad: ask the user for one more OTA after every cell, or call an App-only flash a
safe baseline reset. Equally bad: repeat a successful transfer to recreate a lost
host log, weaken a protocol guard for speed, or continue flashing an uncertain board.
