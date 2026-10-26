# Release-Mode Fast-Path Candidate Integration

## Scope And Ownership

Implementation follow-up A/B/C, assigned by the user on 2026-10-26. Base main:
`91fed6bc863d07edc7173c8e3c08b14c159f7863`, verified with ls-remote. Exclusive
branch: `dev/flutter/fastpath-backend-20261026`; worktree:
`D:/github/my/E-Track/.cache/flutter-fastpath-20261026`. Shared Git metadata is
inside the authorized project. The dirty root archive and other worktrees are
not implementation targets. No Trellis spec/task tree is tracked on this base;
use the existing OTA contracts and this assigned follow-up, not another Spec.

This is implementation and development validation, not independent acceptance,
P3-5 recovery execution, P5 long testing or production qualification. P3-4 and
P3-8 accepted cards/bundles remain unchanged. Standard APK/EXE build, main merge,
release and cloud/device mutations need their actual root authority.

## FAST-RELEASE-01: Minimal Selection Policy

Build -> `OTA_LINK_PROFILE` -> `OtaLinkProfile.build` -> BluetoothService binding
policy and OtaService transport -> exact INFO/CAPS2/BEGIN ACK -> actual selection.
`adaptive-v2-candidate` is an explicit standard release-mode build option;
shipping defaults remain baseline pending independent review and P3-5/P5 gates.
This same entry is tested in development CI and can build a debug development
APK without a runtime file, device address, experiment run ID or test identity.

The request is v2, window 24, batch 12, connection-bound GATT reuse and preference
for without-response. Existing receiver capabilities are unchanged: exact
P2BL/2/2/128/24 and fresh nonce, with INFO limiting the configured sender window.
With-response-only GATT uses single-frame writes, not unsupported writes.
Only the already-admitted same-valid-unpoisoned-connection CAPS2 timeout permits
v1 compatibility (window <=4, batch 1). Invalid capabilities/INFO/identity/ACKs
and negotiated-v2 failures remain fail closed. No baud, AT, Boot, BCB, staging,
credit, retry, cancellation or background-owner semantics are changed.

`OTA_LINK_SELECTION` is emitted after a valid BEGIN ACK. It separates request
source/profile/window/batch from actual protocol/window/batch/write mode and
bounded downgrade reasons. GATT reuse is labelled enabled, not claimed as a
cache hit; the existing actual discovery/write statistics remain authoritative.
The durable progress UI uses the same selection and labels compatibility or
capability limits instead of silently calling them fast. Build intent is not
speed evidence. Success still requires the existing post-reboot full raw image
identity checks and owner/foreground-service cleanup.

## Validation Route

No local Flutter/Gradle build or SDK download. Existing contained host helper
regressions first; WIP commit/push uses Eitan-S-23 and only the assigned branch.
`flutter-dev-checks.yml` runs full analyze/test on Ubuntu/Windows, plus a small
second test command compiled with the candidate define to exercise the actual
build entry. Candidate checks use the same bounded SDK/process/log route and
must pass before a requested debug APK can be collected. All failures remain.

Planned regressions: build selector without runtime; real service legacy fallback
through read/latest/download/transfer/reboot; v2 actual window/batch; malformed
capability refusal; existing cache generation, ACK/credit/retry/timeout/cancel,
background denial/owner-loss/page-reattachment and final identity tests. Self-tests
do not relabel old acceptance or require a new physical campaign.

## BACKEND-READY-01: Evidence First

P4-2 accepted source `fc4fbbb8193fcc536ef408b7b662d44b30f869dc` and its original
native CI 38591559979/156 tests are delivered. Its historical activation gates
are not the final environment state. P4-4 subsequently delivered C4/3.2.9 and
new S3/Worker-preflight A/B evidence; v8 source/bundle/index are
`640cb359db7672cdab1e40bc5853a9ab311e35fa`,
`e93ea8e9966b2b0e37921ae1dd2384cb5438e35e`,
`fdd998d71a065b748146afaed710b252ac6fe3f8`.
Main delivery is documented in `P4-4-main-closeout-2026-10-21.md`, including the
separate test-driver fix and passing main CI 39602375609. Consume these original
register/ready/readback/binding observations before any remediation.

Current applicability, candidate/device version pairing, endpoint visibility,
expiry/no-update semantics and current read-only environment state are still to
be reconciled. No actual backend defect is asserted. No upload, register,
database edit, Access mutation, provisioning or deployment is authorized here.

## Results

Development and standard artifact results will be recorded with their exact
source/run identities after inspection. Independent acceptance remains NOT_RUN.
