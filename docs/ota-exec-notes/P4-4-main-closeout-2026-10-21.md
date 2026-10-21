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

## Final Main Delivery Result

P44-DELIVERY-CI-01 is closed by the test-only commit
`3ecc6722b9eb847f6b6aae196aad6aa6a23a232e`. PR #31 passed Cloudflare checks
39601550033 and App path detection 39601550273, then merged at
`2026-10-21T12:46:59Z` as `75d3ad24424989f5a5f38fe237d24deef9decd4f`.
Main Cloudflare checks 39602375609 passed all three jobs, including 36/36
Admin mock UI cases with zero configured retries. Main App path detection
39602375723 also passed; APK/EXE, deployment and release jobs were skipped.
The original main failure is retained and is not relabelled as a successful run.

The earlier main Governance and GCC results remain applicable: the follow-up
changes only the Admin test driver and this note, not their implementation,
workflow or frozen evidence inputs. The GCC log retains 640 warning diagnostics
in each of the ordinary and development-key builds, zero compiler errors, and
six vendor bsdiff warnings. These development-key artifacts are not a device or
production candidate authorization. Dependency/action deprecation warnings are
not erased or represented as a warning-free build.

`main-delivery-audit01` independently rechecks the actual Git objects and main
CI receipt: all eight historical contract blobs and eight bundle trees are
unchanged; C8/B8/I8 are ancestors of main; no product or P4-4 tool changed during
closeout. The shared original worktree's HEAD, index, tracked diff and status
remain byte/identity equivalent to the pre-operation baseline.

Formal P4-4 stage acceptance, main integration and required delivery CI are now
complete. The following documentation commit records this result; its own SHA
is deliberately not self-recorded. Its ordinary triggered checks must still be
observed before the root session reports final delivery.

## Evidence And Output Audit

The adjacent `P4-4-main-closeout-2026-10-21/` directory contains a SHA-256
inventory of the PR/merge/main-CI receipts, delivery audits, original failing
UI output and screenshots, successful UI output, and compiler-step excerpts.
Compiler excerpts are explicitly selected job/step originals, not a substitute
for an unexecuted build. The full fetched compiler log and the downloaded
failure artifact also remain under the task worktree's ignored cache.

Archived CI output retains its original trailing whitespace and blank lines.
The initial whole-staging whitespace check rejected those originals; that
diagnostic is preserved in the task cache. Do not trim original logs to satisfy
a source-style check. Manual documents use the scoped Git whitespace check
with Windows CR-at-EOL recognition; archive files use exact staged-byte/SHA-256
verification instead.

All active filesystem outputs are contained in
`D:/github/my/E-Track/.cache/p4-4-integration-20261018` or the authorized shared
Git metadata `D:/github/my/E-Track/.git`. No other worktree, external temporary
directory, credential configuration or original main-worktree file was changed.
The main project directory remains on its pre-existing archive branch with its
unrelated dirty files preserved; a clean new task must consume `origin/main`,
not assume that directory was reset to main.

No P4-4 formal command, successful business observation, platform configuration,
device experiment, deployment or production publication was repeated. Product
remains C4/3.2.9 and gate=false. The two extra CI rounds validate an actual
test-driver correction, not unchanged-input retries until green.

## Next Owner: P3-5 Integration

Use the existing `docs/ota-prompts/prompt-P3-5-integration.md`, not another
P4-4 remediation task. Reconcile the P3-1/P3-2/P3-3/P3-4 candidate evidence and
P4-2 real register/latest/download, ready release, R2 readback and versioned
fixture with the already accepted P4-1/P4-4 originals. The old readiness row's
P4-2 dependency wording is not automatically proof of either a current gap or
admission: update only from the actual evidence and preserve real prerequisites.

P3-5 owns the phone-App real-backend upgrade path and ten independent durable
disconnect/recovery events. It does not repeat successful P4-4 A/B, upload,
registration or readback merely because the agent or worktree changed. Hardware,
candidate-key identity and any genuinely missing backend setup remain subject
to that task's actual admission and authority; P5 and production do not start.
