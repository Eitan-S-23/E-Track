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

## Candidate Installation: J-Link Before Extra OTA

User decision, 2026-10-08: distinguish installing the firmware under test from
measuring OTA. When the only prerequisite is putting a candidate receiver on
the authorized board, prefer the installed standard SEGGER Commander route,
then run the required OTA measurement. Do not default to an OTA installation
followed by another OTA merely because a two-cell runner already exists.
See [PROJECT-05](agent-collaboration/project-workflow.md#project-05-j-link-installation-before-ota-measurement).

Before direct programming, check the exact current App/Boot identity, BCB and
pending apply/rollback state, staging state, candidate compatibility and the
supported backup/recovery route. Use the production GCC candidate and exact
App write bounds; coordinate storage-idle halt, watchdog and deliberate restart
through the existing supported route. Preserve uninterrupted J-Link supply.
After programming, verify full App bytes, unchanged Boot, confirmation and
running health before measuring. A download command returning success is not
enough. This policy does not authorize mass erase, Boot replacement, arbitrary
EEPROM/BCB edits or an App-only downgrade across incompatible persistent state.

| Situation | Required route |
| --- | --- |
| Candidate installation only; direct-programming state checks pass | Standard J-Link installation, readback/health verification, then the planned OTA measurement |
| The observation itself tests OTA installation, apply, rollback, recovery or a required OTA-origin initial state | Use the necessary OTA path and explain the specific observation it supplies |
| J-Link is unavailable or a concrete current-state constraint prevents safe direct installation | Record the observed constraint and use the narrowest supported alternative; unresolved device state must be reconciled first |
| Only an old two-OTA runner, a generic BCB concern or missing host logs motivates another OTA | Reassess the route; none establishes that an additional upgrade is necessary |

Record this choice briefly in the existing task note before asking for phone
actions. Do not invent no-reset requirements from uninterrupted power, create
another flasher, or replay a successful OTA to document this lesson. Debugger
installation time is not OTA throughput and direct programming is not evidence
that the OTA apply/rollback path works. Keep installation, measurement and
post-reboot identity verification distinct in reports.

This is not a one-OTA quota: equivalent comparisons, justified repetitions and
reliability campaigns still follow the finite experiment matrix. Existing
permissions and safety boundaries remain unchanged; this documentation update
requires host checks only, not a new flash or OTA experiment.

## Plan Once, Execute The Batch

### SEGGER Native History Exception

User decision, 2026-10-07: "允许，以后同类授权都允许" answers the explicit
request for J-Link automatic native history/config updates inside
`C:/Users/SU/AppData/Roaming/SEGGER/`, principally `JLinkDLL.ini`. This is standing
authorization for those same automatic updates in the authorized P3-4 device
work, not a grant for cleanup, adjacent directories or expanded hardware actions.
Keep controllable settings, logs, firmware, readbacks and temporary/cache outputs
under the active project root. Check resolved paths before invocation and include
the permitted native updates in the final write audit. Do not ask again for the
same history/config side effect.

### Matrix

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
