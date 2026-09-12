# P3-3 / P3-5 Acceptance Scope Ruling

## Decision And Authority

Date: 2026-09-10. Decision: **Option A**, recorded as `OTA-DEC-013`.
The user explicitly delegated the decision and its implementation to this
session. Codex selected A under that delegation; the user did not literally
choose the letter A. The original authorization is preserved as record 10 in
`docs/ota-spec-decisions.md`.

Retain the existing P3-3 hardware completion gate and remove the conflicting
deferral from its implementation Spec. This preserves early verification of
real client/platform/BLE/MCU behavior. P3-5 remains a distinct real-backend
integration and disconnect-recovery campaign, not the only stage allowed to
produce hardware evidence.

The normative task requirements are in the two existing task Specs and mirrored
on their board cards. This note records the decision and audit, not a replacement
binary contract or a versioned acceptance bundle. Readiness finding R2 is
resolved as a scope decision; no RC3 finding or unobserved criterion becomes PASS.

## Scope And Completion Matrix

| Evidence | Required Before | Observation |
|---|---|---|
| Actual APK installation | P3-3 completion | Install and launch the frozen Actions acceptance APK on an actual Android phone; bind its identity and digest to the APK used for transfer. |
| Controlled toy package | P3-3 completion | At least one real phone/App/BLE/MCU upgrade with a safe bootable test package, ending at the target identity after reboot and reconnect. |
| Real firmware package | P3-3 completion | A separate real firmware OTA asset completes the same path; toy success cannot substitute. |
| Real backend candidate integration | P3-5 completion | The actual P4-2 register/latest/download, R2 readback and D1 ready release, with the production parameters established by P3-4. |
| Ten disconnect recoveries | P3-5 completion | Ten actual independent recovery events, covering the required durable stages and final identity; ordinary P3-3 transfers do not count. |

Both P3-3 transfer categories must exercise the real OtaService path through
INFO, latest/download, length/package digest verification, BEGIN/DATA/END,
MCU durable completion and a valid ACK_END, followed by the real upgrade,
reboot, a new connection and GET_INFO matching the frozen target version and
complete raw image SHA-256. GATT completion, a progress bar, ACK_END alone or
the old running identity is insufficient. A PC sender or fake MCU cannot
replace the phone path.

Toy/real describe asset purpose; full/patch describe container type. This ruling
does not require a new two-by-two hardware matrix. Both assets must be separately
identified and compatible with the actual device. A toy success asset must be
bootable through the real firmware-header, Boot, BCB and OTA path. It need not
be 4 KB. Golden vectors are not presumed bootable and must not be flashed or
used to bypass validation merely because their parsing tests pass.

## Dependencies And Existing Interfaces

P3-3 hardware acceptance can precede P3-5; it does not wait for P3-5 to start or
finish. The P3-1/P3-2 implementation prerequisites remain unchanged. An approved,
versioned, contract-conforming HTTP test service may be an explicit P3-3
external input when P4-2 is not ready. It must still exercise real HTTP and the
App's complete validation path, without injecting a verified file or bypassing
latest, compatibility, token or digest checks. Its use is not evidence that the
real P4-2 register/R2/D1 chain passed, and creating/deploying it needs the
applicable operation authorization.

The exact baud/timeout/retry settings are acceptance inputs; P3-3 functional
success does not establish P3-4 production performance or relax its contracts.
P3-5 retains all existing prerequisites. Neither card uses task completion as
a substitute for evidence about a different layer.

No API, wire format, retry limit, safety threshold or profile definition changes.
The existing `validate_bundle.py` interface and v3 fields remain authoritative:
`freeze_commit`, `freeze_tree`, `profile_config_blob`, input groups, external
inputs, command/runner dependencies and artifacts. The implementation and any
actual acceptance runner must be committed before freezing. The new governance
bytes must be included in the approved input tree; do not freeze the old Spec
and apply this note informally afterward.

This changes Governance inputs (Specs/decision registry/development guide) and
Validation/Evidence inputs (the policy test), not production inputs. Future
acceptance must use the actual approved profile dependencies; this note does
not declare earlier evidence universally valid or invalid. No existing frozen
profile blob is edited and no historical acceptance is rerun.

Actual asset locators, sizes, package digests, target raw image digests, hardware,
layout, Boot, full/patch and base-version conditions must be frozen before
hardware execution. This ruling does not choose a currently unverified binary
or create a contract/NOT_RUN matrix on behalf of the independent reviewer.

P3-3 evidence may inform P3-5 admission. It cannot simply be relabeled as a
P3-5 EXECUTED/REUSED PASS across task IDs. Relevant external artifacts and any
permitted reuse must be explicitly bound and checked under the execution
contract. No historical bundle is rewritten and no full campaign is rerun here.

## Validation Cases

| Case | Required Treatment |
|---|---|
| CI checks and a debug APK exist, no device observations | Development feedback only; P3-3 cannot be completed. |
| APK signature verification succeeds, installation never occurs | Not installation evidence. |
| A 4 KB golden vector parses but bootability is unproven | Not a valid successful device-upgrade asset. |
| MCU ACK_END succeeds but post-reboot GET_INFO is old or missing | Upgrade completion is not established. |
| Separate safe toy/real assets complete the frozen phone path | Supplies those P3-3 observations; other required gates still apply. |
| P3-3 passes while P3-5 has no real backend/ten-event evidence | P3-5 remains incomplete. |

Wrong: defer every device check to P3-5 but require P3-3 to finish first.
Correct: collect P3-3's own device evidence before its completion, then perform
P3-5's separately scoped real-backend and recovery acceptance.

## Governance Regression

The existing `tests/ota/test_acceptance_bundle.py` entry gains five policy tests
for evidence ownership, missing/duplicate/deferred evidence rejection, bootable
assets/final identity, retained P3-5 requirements and delegated authority.
They test governance text, not the Flutter product or hardware. Existing
Acceptance Governance CI already watches and executes this test file and the
changed governed Specs/decision registry; no workflow change is needed.

The focused ownership test was first run against the old Specs. It exited 1,
rejecting the missing evidence rows and both old blanket-deferral promises.
The original output is retained in
`.cache/p3-3-scope-ruling-20260910-01/before.log`.

Post-change command:

    python -X utf8 -B tests/ota/test_acceptance_bundle.py AcceptanceExecutionPolicyTests PostP26SpecGovernanceTests -v

Result: exit 0, **27 tests passed in 0.818 s**, no skips (nine execution-policy
tests including the five additions, plus eighteen existing Spec governance
tests). Output: `.cache/p3-3-scope-ruling-20260910-01/after.log`.

| Log | SHA-256 |
|---|---|
| before.log, intentional rejection of old policy | c67da803d7ee0ff1cdb5201c2ed97913f2b6b4642109d80e10a399c7593abf33 |
| after.log, 27 passing governance tests | cd8a3328941f7cad73e4dbcf5204fbff0492be6e5ce0978901532f46156fef07 |

Python 3.9 grammar parsing passed. Repository-wide `git diff --check` passed
after normalizing only newly changed/added board lines to LF: its first run
had flagged the CRLF on the edited acceptance row. Unchanged historical rows
were not reformatted; Git's four existing autocrlf advisory messages remain.

No Flutter, firmware, remote Actions, installation, deployment, flashing or
hardware test has been run by this governance task. The reported batch-six CI
results remain the implementation agent's existing report, not new observations
or an independent PASS produced by this session.

## Preservation And Output Boundary

Active root: `D:\github\my\E-Track`.
Initial HEAD: `7e3ab72e928606fe771a6d40e914952164df179b`.
Initial branch: `dev/flutter/apk/p3-3-batch6`.

All selected output paths and their full existing parent chains passed
normalization and reparse-point checks before writing. Generated baseline,
test logs and temporary output stay in
`.cache/p3-3-scope-ruling-20260910-01/`. The baseline protects 417 existing
product/test/runner/workflow/profile/frozen-contract inputs; it is only a local
write-safety snapshot, not an acceptance manifest or evidence-reuse mechanism.

Manual edits use apply_patch. A formatting-only pass preserves existing line
endings on unchanged content, including the board's mixed format. Only the
original P3-3 acceptance row (baseline line 625) changed; four records were
added. Its edited line now uses LF, while all other 727 original CRLF lines
remain byte-for-byte intact and in order. Historical readiness/research text
is retained and superseded by appended follow-ups, not edited into a false
history. The P3-3 implementation owner, current development CI report and RC3
remaining issues are unchanged. P3-5 dependency/readiness state is unchanged.

All 417 protected inputs matched their baseline SHA-256, both historical note
prefixes remained exact, and the selected output paths/parent chains passed
the closing audit. The local audit record is
`.cache/p3-3-scope-ruling-20260910-01/audit.json`. Active outputs are the eight
tracked governance/document/test files, this new note, and the project-local
baseline/log/audit files. No legacy script, PowerShell process or project-external
output was created; inherited untracked files and cache directories were left
alone. HEAD remains the initial commit above.

This scope decision does not grant operation authority or additional retries.
Existing development self-test authorization continues, but actual installation,
device data changes, deployment or flashing require their own approved plan.
This session does not commit, push, dispatch CI, create a frozen bundle or fill
an independent PASS matrix. The current sandbox still treats .git as read-only;
the governance changes must be committed by an authorized write-capable session
before the independent acceptance freeze.
