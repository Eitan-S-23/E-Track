# P3-4 Bounded Pre-Review Remediation Supplement

## Latest User Direction: Acceptance Essentials Only

On 2026-10-09 the user explicitly deferred further trial5 root-cause work and
required only candidate preparation and the necessary independent acceptance.
This supersedes this batch's earlier demand to finish a separate trial5 causal
investigation before submission. Preserve the original failure as an unresolved
historical risk; do not assert operator error, a repair, or PASS. A new failure
in the approved formal matrix still stops its affected path and is recorded
under the unchanged product/integrity rules. Do not add diagnostics or repeat
full OTAs to reproduce trial5. Retain already-completed bounded self-tests.

Task: P3-4. Batch: 2026-10-09. Root decision: `OTA-DEC-015`.
This is a governed batch supplement to the one P3-4 experiment Spec, not a
second task/readiness prompt or a replacement for the original task claim.
Work only under `D:/github/my/E-Track`; preserve the original implementation
claim and all unrelated dirty changes. This succeeds, but does not rewrite,
the consumed 2026-09-20 implementation prompt or prior experimental evidence.
Read root AGENTS, the collaboration/execution contracts and the
[current task note](../ota-exec-notes/P3-4-transfer-next-2026-10-07.md) first.

## Decision And Inputs

The user approved retaining the already-exercised v2 two-block/synchronous
WAIT_RX route for remediation and future acceptance, not production release.
Use [the prospective v2 supplement](../ota-ble-v2-contract.md), not a silent
rewrite of the v1 contract. The root note's PRE-01 switch inventory is the
selected productionization direction, subject to the stated verification.

Read the complete independent pre-review report at
`.cache/P3-4-independent-pre-review-report-2026-10-09.md`
(SHA-256 `3325f74baa203b3c967c8e314158ed17ad42aade7fa5a7592e84232ee576f857`).
Receiver reference: `.cache/p34-overlap1/f/`, original build/config/source
receipts under `.cache/p34-overlap1/fw-wait2/`. App reference: Git revision
`ef47dabd51f129c64a0be0945265192d17f70c17`. Neither equals dirty root by assumption.
Last retained C30286 and group16 Boot bindings remain in the root note; they
are historical observations, not permission to skip a live device check.

## One Remediation Batch

- PRE-01: reconcile the actual source registrations and chosen build definitions.
  Split functional ACK timing/generation, UART initialization and memory budgets
  from experiment loggers and AT/debug entry points. Do not merely turn all
  switches off or import every file from an experimental source copy.
- PRE-03: use the actual trial5 package and the first 13 blocks, not only a 9000 B
  generated fixture. Reuse the existing pipeline/session/HAL tests and IO fakes.
  Exercise the twelfth block and repeated slot rotation, missing 0xB500/0xB700
  pages, restore/read/verify/journal failures, source ownership, reentrant poll,
  ABORT and premature END. Preserve the 45056-byte correct prefix, bad-block
  journal bit, durable boundary and no-activation guarantee; verify exact bytes
  after journal-based resume. Distinguish containment from a reproduced cause.
- PRE-07: preserve the first numeric error and command/session/seq/epoch/credit
  context through the existing App snapshot path. Receiver observations identify
  first failed IO/restore/verify/journal location. No extra success semantics,
  unbounded per-frame logger or private wire status. Known/unknown/malformed and
  stale epoch/seq cases need positive and negative tests.
- PRE-06: the actual Android vendor plugin, native tests, compiled Tools ACK
  headers and source-pinned collectors must belong to their real consumers'
  approved profiles. Add only evidenced dependencies; do not hide them in cache
  or move files solely to shrink invalidation. Final runners must be committed.

Affected product scope is the existing OTA pipeline/session/staging and QSPI
call path, its HAL/serial/clock/config/CMake registration, and the existing
Flutter OTA transport/service/diagnostic path plus corresponding tests. Preserve
all other changes. Any needed new product behavior beyond this batch requires
an evidenced root decision, not blanket import of historical experiments.

## Validation And Stop Rules

Start offline, with contained host outputs and real implementation code. The
saved receiver tree is read-only; a test may bind it explicitly as a development
input, but cannot thereby make it a final Git freeze. Never edit a consumed
helper, source receipt, report, snapshot or failed readback.

If a host test proves a defect, implement the smallest repair and discriminating
regression. If it proves only safe containment, leave PRE-03 NEED_EVIDENCE and
define the smallest missing real-page observation. Do not assume absent FF pages
prove clock, cache, SD, DMA or buffer corruption. Do not perform repeated full
upgrades to hunt an intermittent failure.

Any later hardware probe must have fresh identity/state checks, one physical
owner, exact legal package and bounded capture/cleanup. For candidate installation
use standard J-Link first; do not write a flasher or schedule installation-only
OTA. No END/activation is needed for a prefix diagnostic. The specific device
plan must be recorded before execution under the existing device policy.

No group16 Boot replacement, arbitrary BCB/EEPROM modification, cancelled QSPI
frequency/startup-self-test branch, Handler/native sender, 50 kB/s exploration,
UI redesign or P3-8 background work. No publication or ordinary commit/push is
granted here; Flutter development validation follows its separate standing scope.

Batch targeted host tests and actual affected builds. Do not require the
implementer to duplicate the formal 30/30, 4-hour and 10/10 campaign. Before
that campaign, close known blockers, bind a production candidate and legitimate
1 MiB/equivalent initial state, then obtain the real versioned formal freeze and
NOT_RUN preflight. Never fill missing commit IDs or observations with placeholders.

For safety/scope conflicts, project escapes, unresolved device outcomes or three
consecutive same-item failures, preserve evidence and stop the affected action;
continue independent safe work. Root coordinates resolution. Required mid-task
user intervention follows the current manual-mention rule; normal final handoffs
already receive automatic completion notification.

## Delivery

Update the existing task note's single PRE issue table with actual changes,
source bindings, commands/exits, positive and negative results, retained failures
and remaining gaps. Keep preparation, compilation, installation, measurement and
independent acceptance separate. Anyone writing a product fix is an implementer
for that scope and cannot give its independent acceptance PASS. P3-4 remains in
progress until the formal requirements are actually satisfied.
