# P4-4 Main Integration Closeout

## Scope And Authority

On 2026-10-21 the user requested completion of P4-4 closeout before a P3-5
implementation handoff. This covers the main integration and its required CI,
not production publication, gate unlock, deployment, device work or a new P4-4
acceptance campaign. Root performs the closeout without remediation sub-agents.

The preceding formal result remains:
`VALIDATION=PASS contract=P4-4-v8 round=P44-20261021-08 overall=PASS`.
All nine required criteria passed. The source/evidence/index identities are:

- C8: `640cb359db7672cdab1e40bc5853a9ab311e35fa`.
- B8: `e93ea8e9966b2b0e37921ae1dd2384cb5438e35e`.
- I8: `fdd998d71a065b748146afaed710b252ac6fe3f8`.

## Main Integration

PR #30 merged at `2026-10-21T12:25:46Z` as
`6469233b282bdaf188e764d68128133f553f0247`, preserving all original commits.
The merge tree equals I8 exactly. The eight frozen contract blobs and eight
bundle trees are unchanged, and C8 -> B8 -> I8 -> main ancestry passes.
The original shared worktree HEAD, index, tracked diff and status are unchanged.

All four PR workflows passed:

| Workflow | PR run |
| --- | --- |
| Acceptance Governance | 39598924484 |
| MCU Firmware Build | 39598924545 |
| Cloudflare Update Service Checks | 39598924787 |
| Build APK and EXE Release | 39598924489 |

On the same-tree main merge, Governance 39599518438, MCU 39599518509 and
App path detection 39599518588 passed. Cloudflare 39599518618 passed Worker
invariants and Public typecheck but failed two of 36 Admin mock UI cases.
The failed run, screenshot/context artifact 12345182782 and command receipts
remain preserved. No automatic run retry or cloud/device operation followed.

## P44-DELIVERY-CI-01: Mock Dialog Autofocus Race

This is a delivery CI test-driver issue, not a P4-4 product acceptance failure.
The two failures are the English/Chinese cancel-and-fresh-confirmation cases at
`admin/test/firmware-ui.spec.ts:166`. The helper awaited an enabled accept button,
but the failure screenshot shows `stable browser operator reason` in the
confirmation text field and an empty reason field. The product correctly kept
the button disabled and sent no unauthorized mutation.

`admin/public/index.html` schedules the initial focus in `requestAnimationFrame`
after opening the dialog. The old test helper started consecutive fills without
waiting for that initial focus. The delayed callback could move focus back to
the confirmation field while the reason text was being entered.

Root changes only the shared Playwright helper: wait for the visible dialog and
the existing `confirm-open` animation-frame marker, fill the applicable fields, and verify their exact
values before accepting. All 36 cases, cancellation/no-write assertions,
timeouts and zero-retry policy remain. No product/UI/Worker implementation,
P4-4 collector, acceptance criterion or frozen evidence is changed.

The frame marker is preferred to requiring the initial field to remain focused:
some existing callers intentionally fill the maintenance field before invoking
this helper. The readiness wait must not reject that valid focus change.

Validation uses the existing Cloudflare checks workflow on the changed test
input. A local browser dependency is not installed in this worktree; no local
browser build, external cache write or substitute static PASS is claimed.

At this recording point the test-only correction is pending CI and delivery.
P4-4 formal PASS and PR #30 integration are complete, but full main closeout
must not be reported complete until the delivery CI correction is verified.
