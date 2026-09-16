# CI-ARTIFACT-01: Implement Bounded CI Artifact Management

task_id: CI-ARTIFACT-01
Dispatch owner: root coordination session. Date: 2026-09-17.
This is an implementation dispatch, not an independent acceptance contract.

## Role And Entry

You are the implementation agent for this CI governance task. The root session
does not implement or independently accept your work. Read AGENTS.md, the
CI-ARTIFACT-01 card in PLAN-OTA-EXEC.md, docs/acceptance-execution-contract.md,
docs/flutter-development-validation.md and
docs/ota-exec-notes/CI-ARTIFACT-01-dispatch-2026-09-17.md before editing.
Claim only this card with your identity/date. Leave P3-4 ownership and state alone.

Use D:\github\my\E-Track as the sole writable root. Preflight every output path
and child-process cache/temp location; use explicit working directories and
cmd.exe. No PowerShell, local Flutter/Gradle builds or external SDK installation.
Preserve all unrelated dirty/untracked files. Do not stage, switch branches,
commit, push, merge or launch remote workflows in the shared worktree. This
dispatch authorizes implementation and contained host self-tests, not new real
GitHub deletions. Do not spawn further agents.

## Allowed Files

- .github/workflows/flutter-dev-checks.yml
- .github/workflows/build.yml (only explicit APK/EXE artifact retention)
- .github/workflows/artifact-maintenance.yml (new dedicated maintenance workflow)
- .github/workflows/acceptance-governance.yml (new tests and their trigger paths)
- Tools/flutter/dev_checks.py
- Tools/flutter/artifact_maintenance.py (new helper)
- Tools/flutter/artifact_maintenance_policy.json (new scoped policy/pins)
- tests/ota/test_flutter_dev_checks.py
- tests/ota/test_flutter_dev_apk.py (only directly affected assertions)
- tests/ota/test_artifact_maintenance.py (new host tests)
- Tools/provenance/manifest_profiles.json (only necessary new input coverage)
- AGENTS.md and app/bluetooth_flutter_Trace/AGENTS.md (affected development rules)
- docs/flutter-development-validation.md
- docs/acceptance-execution-contract.md (development self-test clause only)
- docs/ota-exec-notes/CI-ARTIFACT-01-implementation-2026-09-17.md
- Your task card and your session-log entry in PLAN-OTA-EXEC.md

Do not change app product/test code outside this list, firmware, cloud deployment,
version numbers, signing, release behavior, historic prompts/evidence, versioned
acceptance contracts or frozen profile snapshots. A new helper dependency or an
additional changed file requires a root scope decision, not silent expansion.

## Required Behavior

### 1. Explicit APK Requests

Every push to dev/flutter/** must be checks-only, even when the branch begins
dev/flutter/apk/. Generate a debug APK only on explicit workflow_dispatch with
build_apk=true. Preserve all/ota test-scope behavior, both Ubuntu/Windows checks,
full tests for APK requests, Linux-only APK packaging and signature verification.
Do not weaken diagnostic failures, timeouts, source identity or lockfile checks.
Existing APK suffix/device-observation opt-ins remain compatible but must not
silently turn a checks-only push into a build.

### 2. Tiered Retention

New development debug APK artifacts: retention-days=3. Development logs: 14.
Set android-apk and windows-exe CI verification artifacts in build.yml to an
explicit 14 days without changing their contents or triggering conditions.
Do not alter Release assets, firmware retention or candidate-metadata retention.
Document that retention changes do not rewrite existing artifacts' expiry dates.

### 3. Independent, Bounded Maintenance

Implement a dedicated daily workflow and manual dry-run/apply entry. Default
manual operation is dry-run. Real scheduled apply is confined to trusted main
of Eitan-S-23/E-Track and becomes active only after authorized integration.
Reject fork repositories, non-default refs and untrusted PR execution. Keep
actions:write only on the maintenance job, not the development/build workflows;
use the job token, do not introduce a PAT or broader account permissions.

Enumerate the complete inventory before deleting anything. Validate repository,
workflow, source branch, artifact name/embedded commit/run/attempt and API metadata;
missing or contradictory target metadata must not authorize deletion. Only this
development workflow's flutter-dev-debug-apk artifacts on dev/flutter/** qualify.
Never delete workflow runs, logs, releases, tags, caches, android-apk/windows-exe,
other repositories or unrelated artifact names. Do not use wildcard shell deletion.

An unpinned, completed-run target qualifies when older than 72 hours OR outside
the newest two APK artifacts for its source branch. Use deterministic UTC ordering
and an ID tie-breaker. Exclude active/incomplete runs. Seed the policy's pin list
with the 12 retained IDs and their reasons from
docs/ota-exec-notes/P3-4-artifact-cleanup-2026-09-17.md. Pins block this helper, not
GitHub expiry; archival must precede expiry for any required evidence/recovery APK.

Dry-run must be entirely read-only remotely. Apply consumes its current bounded
plan, revalidates each ID before DELETE, and records outcome/bytes/remaining scope.
Limit each invocation to 50 planned IDs; report excess backlog rather than widening
scope. Serialize maintenance runs without cancelling an in-flight deletion batch.
On uncertain network results, reconcile that ID read-only before any retry; do not
restart the full batch blindly or count a missing response as a successful DELETE.
Partial failures and pagination/auth/schema errors must remain visible and fail
closed. Keep diagnostic plans/results in ordinary job logs and checked workspace
files; the maintenance job must not depend on a successful artifact upload.

Report total repository bytes, debug APK bytes, selected/kept counts and actual
freed bytes. Support a configured warning budget; if unset, state unknown rather
than inventing the account's allowance. Do not delete protected/other-class assets
to satisfy a target, change billing, or promise immediate quota recovery.

### 4. Diagnostics Independent Of Artifact Upload

Keep useful sanitized command output in ordinary job stdout before the upload
step, including failure/timeout diagnostics. Record tested commit, host, actual
SDK identity, scope, exit codes and counts derived from real test output where
available. Missing/unrecognized counts remain unknown, not zero or guessed.
Retain the project-local raw reports/logs and strict artifact upload step.
Do not use continue-on-error or turn an upload failure into an overall green run.

Reuse the current child-process ownership and timeout cleanup in dev_checks.py;
do not weaken Windows Job Object/stdin-gated startup or POSIX process-group cleanup
to implement output mirroring. Do not let output decoding or a broken sink hide
the original failure. Ensure tokens, credentials and signed URLs are redacted in
public diagnostic output. A command-completion diagnostic copy is acceptable;
there is no requirement to introduce a complex background streaming subsystem.
GITHUB_STEP_SUMMARY may be outside the approved workspace: do not write it blindly.
Ordinary stdout and a checked project-local summary fulfill this requirement.

## Self-Tests And Review Readiness

Add host positive/negative cases for explicit build selection, TTL/count/pin
boundaries, branch isolation, active runs, pagination completeness, forged names,
metadata changes, unauthorized repo/ref, dry-run with zero DELETEs, API failures,
uncertain DELETE reconciliation, caps and capacity reporting without a quota.
Use injected API fixtures, not production GitHub artifacts, for mutation tests.

Exercise real process stdout/stderr and nonzero/timeout propagation, diagnostic
redaction, unknown counts and missing logs. Keep existing process cleanup tests.
Update real workflow assertions rather than deleting them. Ensure maintenance
helper/policy/workflow/test changes trigger the governance job and are included
in relevant input coverage. No historical frozen bundle may be modified to pass.

Run the affected host suites serially after inspecting their output paths:
python -X utf8 -B tests/ota/test_flutter_dev_checks.py
python -X utf8 -B tests/ota/test_flutter_dev_apk.py
python -X utf8 -B tests/ota/test_artifact_maintenance.py
Additional relevant governance checks must be bounded and must not start hardware,
build old firmware, invoke uncontained PowerShell or perform live cloud mutations.
No new Flutter SDK is needed for these runner/helper fixtures. Remote CI results
remain NOT_RUN until an authorized route is actually executed.

## Delivery And Stop Conditions

Deliver one consolidated batch: changed paths, rationale, exact self-test commands
and exit codes, raw output locations, a single findings/coverage list, and explicit
unverified items. Record self-tests, remote CI, independent review and rollout
separately. Update only your card/session entry; do not declare formal acceptance
or production activation. Stop after delivery for independent review.

Stop the affected action for output-boundary failures, missing authorization,
out-of-scope changes, possible deletion of protected assets, credential exposure
or conflicts with frozen contracts. Ordinary in-scope bugs should be fixed in a
batch with targeted self-tests. Do not turn this into a new audit framework or
reopen P3-4 hardware work. User-facing reports should be in Simplified Chinese.
