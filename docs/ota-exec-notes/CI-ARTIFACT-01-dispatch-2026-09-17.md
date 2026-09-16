# CI-ARTIFACT-01: Dispatch Decisions

Date: 2026-09-17. Author: root coordination session, not the implementation agent.
Task state and implementation ownership are maintained only in PLAN-OTA-EXEC.md.

## User Decision And Scope

The user approved the four proposed improvements: explicitly requested debug APKs,
tiered retention, independent bounded maintenance/capacity reporting, and useful
diagnostics even when artifact upload fails. This is a CI governance task, not a
reopening of P3-3 or a new P3-4 hardware acceptance round.

The root session remains a coordinator. Permission to launch an implementation
sub-agent and a separate code-review agent was requested in the current thread.
No agent launch is inferred from unanswered input. The frozen implementation
dispatch is docs/ota-prompts/prompt-CI-ARTIFACT-01-implementation.md.

## Read-Only Findings

- flutter-dev-checks.yml currently turns every push to dev/flutter/apk/** into a
  full-test debug APK build. Ordinary development pushes and requested builds
  share a workflow, but their production intent is not separated sufficiently.
- Both development log artifacts and debug APK artifacts currently retain for
  14 days. Each historical debug APK artifact is approximately 72 MiB.
- build.yml has no explicit retention-days on android-apk/windows-exe uploads;
  those copies inherit repository settings. Its separate candidate metadata
  already retains for 7 days and is outside this retention change.
- dev_checks.py redirects child stdout/stderr to project-local files, then prints
  command status/exit code. The ninth P3-4 run therefore lost detailed results
  when artifact creation failed, although analyze/test steps succeeded.
- The user-authorized cleanup removed 40 old debug APK artifacts. The last
  measured inventory was 305 artifacts / 1,538,665,642 bytes, with 12 explicitly
  retained APKs. This is repository inventory, not an account quota measurement.
  See P3-4-artifact-cleanup-2026-09-17.md for IDs, receipts and limitations.

## Bounded Defaults

1. All development pushes are checks-only, including legacy apk-named branches.
   APK generation requires an explicit workflow_dispatch build_apk=true request;
   APK requests still require full tests and Linux build/signature verification.
2. New debug APK uploads retain for 3 days. Development logs retain for 14 days.
   Newly produced android-apk/windows-exe CI verification copies explicitly retain
   for 14 days; GitHub Release assets, firmware outputs and frozen bundles do not
   acquire an automatic-deletion policy from this task.
3. Maintenance targets only validated flutter-dev-debug-apk artifacts from this
   repository's development workflow and dev/flutter/** branches. Eligible
   artifacts are older than 72 hours or beyond the newest two per source branch,
   excluding pinned IDs and active/incomplete runs. Keep the initially retained
   12 IDs from the cleanup note pinned pending a separate archival decision.
4. A dedicated daily workflow provides maintenance independently of build/upload
   success. It runs trusted default-branch code only, has a dry-run manual default,
   limits deletion to 50 selected IDs per invocation, and never expands scope to
   satisfy a capacity target. New production activation requires authorized Git
   integration; implementation-stage tests must not delete real artifacts.
5. Capacity reporting measures repository artifact bytes and supports an explicit
   configured warning budget. An unset budget is reported as unknown/unconfigured,
   not guessed from upload history or presented as the account allowance. No
   payment settings, account token scopes or repository visibility are changed.
6. Ordinary job stdout must retain sanitized useful diagnostic output and real
   command/result metadata before upload. Counts that cannot be parsed remain
   unknown. Artifact upload remains strict; no continue-on-error workaround.

Pins protect against this maintenance tool only. They do not extend GitHub's
native expiration. Required acceptance/recovery bytes must be archived before
expiration, not merely named in a permanent exception list. TTL changes apply to
new artifacts; existing copies retain their already assigned expiry dates.

## Verification And Authorization Boundaries

Implementer self-tests cover the affected Python runners, classification and
deletion guards, failure/timeout propagation, output redaction and workflow
conditions. Existing real Windows child-process cleanup tests must remain intact.
New tests are wired into Acceptance Governance with complete trigger paths.

Independent review evaluates one complete batch. Formal CI/acceptance is distinct
from local self-tests and cannot be claimed before execution. No historical
firmware/hardware campaign is required for these governance changes.

The approval to improve behavior does not independently grant mainline commits,
push/merge, remote workflow dispatch, additional manual artifact deletion,
deployment, billing changes or device operations. Existing scoped development
self-test authorization remains subject to exclusive worktree/index ownership;
do not manipulate the shared index for this task without root coordination.

## Filesystem And Shared Work

The sole writable project root is D:\github\my\E-Track. All helper output, logs,
fixtures and caches must be preflighted under this root, including child-process
HOME/AppData/TEMP and GitHub CLI state. Use cmd.exe, not uncontained PowerShell.
Do not blindly write GITHUB_STEP_SUMMARY if its actual path is outside the
workspace; ordinary job stdout plus a checked project-local report is sufficient.

Existing P3-4 Dart/test edits, the earlier artifact-cleanup note and board history
must be preserved. The implementation dispatch excludes app product code,
firmware code, frozen contracts/bundles and their historical profile snapshots.

## Documentation Submission Authorization

On 2026-09-17 the user explicitly requested committing and pushing this session's
changes if they had not already been submitted. This authorizes the cleanup note,
this dispatch note, the implementation prompt and only the coordinator-owned
board changes. Existing P3-4 implementation changes and other sessions' board
entries are excluded. This submission does not implement or activate the four
improvements, authorize a manual CI rerun, or answer the pending agent-launch
question. Earlier statements of no Git submission describe their original time.
