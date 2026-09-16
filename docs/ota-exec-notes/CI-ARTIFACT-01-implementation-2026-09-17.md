# CI-ARTIFACT-01: Implementation And Validation

Date: 2026-09-17. Implementer for this batch: Codex.
Task status remains owned by the CI-ARTIFACT-01 card in PLAN-OTA-EXEC.md.

## Latest Authorization

After the documentation-only commit 0aa4d9a, the user explicitly requested the
four changes themselves and their commit/push. This supersedes the earlier
pending agent-launch decision for this bounded governance batch: the current
session implements it directly. It does not sign independent acceptance,
implement P3-4 product changes, run device operations or manually delete more
real GitHub artifacts. Authorized mainline integration will install the daily
bounded maintenance workflow; a future schedule execution is a separate result.

## Research And Design

- flutter-dev-checks.yml previously converted every dev/flutter/apk/** push into
  an APK request. The replacement requires workflow_dispatch and build_apk=true;
  both hosts retain full-test requirements for APK requests.
- Debug APK/log retention was uniformly 14 days. New APK retention becomes 3
  days, logs stay 14 days, and build.yml APK/EXE verification copies explicitly
  retain for 14 days. Release assets and historical expirations are unchanged.
- A standalone daily job owns actions:write. It checks exact repository/workflow
  identity, full pagination and source metadata before planning. It excludes
  pinned and active runs, keeps at most 50 planned deletions per invocation, and
  reconciles uncertain results rather than blindly retrying. Budget warnings
  use a configured repository budget, not a guessed account allowance.
- Development diagnostics copy useful sanitized output to ordinary job logs
  before artifact upload. Real counts and SDK identity are extracted when
  recognizable; missing counts stay unknown. Existing process ownership,
  timeout cleanup, failure propagation and strict upload behavior remain intact.

## Validation Scope

Use affected Python host fixtures and governance checks, not a Flutter SDK,
packaging or historical hardware campaigns. Mutation fixtures inject a fake API;
they must not contact or delete production artifacts. All outputs stay below
D:\github\my\E-Track, primarily .cache/ci-artifact-01-20260917/ and the existing
checked runner-test directories. Commands use cmd.exe and isolated Python;
Git/GH temporary state and cache locations stay project-local.

## Executed Development Checks

The following commands ran serially with isolated Python, explicit project CWD
and project-local HOME/AppData/TEMP/cache locations. They are development checks,
not independent acceptance or actual APK/EXE builds.

| Command | Observed result | Raw local output |
| --- | --- | --- |
| python -I -B -X utf8 tests/ota/test_flutter_dev_checks.py | 62 tests PASS, exit 0 | .cache/ci-artifact-01-20260917/runner-4.log |
| python -I -B -X utf8 tests/ota/test_flutter_dev_apk.py | 26 tests PASS, exit 0 | .cache/ci-artifact-01-20260917/apk-1.log |
| python -I -B -X utf8 tests/ota/test_artifact_maintenance.py | 21 tests PASS, exit 0 | .cache/ci-artifact-01-20260917/maintenance-2.log |

Total: 109 tests passed. Python AST parsing, YAML parsing for the four affected
workflows, JSON parsing and staged whitespace checks also passed. Existing real
Windows timeout/child-process cleanup, failed job assignment, batch quoting,
Git identity and sparse-checkout fixtures remain enabled.

Read-only live preflight reused the production maintenance planner with an API
adapter that rejects every method except GET. The completed plan observed 305
artifacts / 1,538,665,642 bytes, including 12 debug APKs / 902,646,481 bytes. All
12 are pinned: selected 0, kept 305, result DRY_RUN. No real DELETE was sent.
The full result is .cache/ci-artifact-01-20260917/live-dry-run.json. The configured
budget and account allowance remain unknown; this is not proof of upload recovery.

## Failures And Consolidated Fixes

- The first full local runner invocation had 10 Git-fixture initialization
  errors. After improving the fixture's CWD/error reporting, the next invocation
  exposed the exact error: missing config value GIT_CONFIG_VALUE_3. Windows
  environment restoration by mock.patch.dict dropped empty process environment
  values while retaining GIT_CONFIG_COUNT. A single-test run did not reproduce
  the earlier environment mutation, so it was not treated as a full-suite PASS.
  The contained test driver now supplies only nonempty Git configuration values
  and a project-local fixture-global configuration path. No product check was
  weakened. Both failures remain in runner-0.log and runner-2.log; the final full
  runner result is the 62-test PASS above.
- The first live read-only inventory stopped on an EOF at page 4. A targeted
  page-4 recovery probe returned total_count 305 and 5 rows; only after that
  observable recovery was the complete read-only plan repeated. No partial
  inventory was applied, no DELETE occurred and the upload-failure history was
  not rewritten. The recovery observation is page-4-recovery.json in the same
  operation directory.
- Precommit code self-review found that redacting serialized JSON could damage
  quoting, and tail clipping could remove a private-key block's opening marker.
  Machine diagnostics now sanitize structured values before serialization, and
  private-key blocks are removed before tail selection. A discriminating test
  covers JSON parsing, unlabeled credential fields and a key block exceeding the
  console limit. This self-review is not an independent acceptance claim.

Cross-layer checks confirmed the active branch/retention guidance, workflow
conditions, Validation profile coverage and push/PR governance triggers agree.
The release-candidate metadata retention remains 7 days; no publishing, signing,
version, Flutter product/test or frozen acceptance bytes were changed.

## Integration Boundaries

Implementation and normative changes were committed as
2d81a4b88a5a5e2451187c885abbd70a0217185a and pushed to main using Eitan-S-23.
Only the 14 reviewed implementation/rule files were in that commit. The board
and this verification note are a later documentation closeout, not self-references
inside the implementation commit.

Old dev/flutter branches must integrate the new workflow and runner to obtain
new push/build selection, TTL and console behavior. Rerunning e783155 or another
old commit does not upgrade its workflow. The standalone daily maintenance uses
trusted main and can classify old artifacts without changing their branches.

Independent acceptance, device operations, actual APK/EXE builds, manual CI
dispatch and a real scheduled maintenance execution have not been performed by
this session. The task card remains the only source of current task status.

## Mainline CI And Write Audit

All three push-triggered runs below bind to the implementation commit
2d81a4b88a5a5e2451187c885abbd70a0217185a. No workflow was manually dispatched.

| Workflow | Run | Observed conclusion |
| --- | --- | --- |
| Acceptance Governance | 35155229025 | success; Validate acceptance and build governance job success |
| Build APK and EXE Release | 35155229120 | success; path detection success; Android, Windows, Pages and Release jobs all skipped |
| GitHub Push to WeChat Notification | 35155228914 | success |

The Actions API reports maintenance workflow ID 360027653, path
.github/workflows/artifact-maintenance.yml, state active. Its first scheduled
execution is not claimed: active registration is not an execution receipt.
The schedule is daily at 02:17 UTC / 10:17 Asia/Shanghai. CI metadata was saved in
.cache/ci-artifact-01-20260917/implementation-ci-1.json.

The write audit verified pre-existing tracked/untracked file bytes against the
387-file baseline (the board is checked separately by reconstructing only the
coordinator-owned section and appended entries). P3-4 implementation/test files
and other sessions' board evidence remain outside this submission. External Git
and GitHub CLI configuration and configured hooks retain their original hashes.
Controlled outputs are confined to the project: .git, the documented source/note
paths, .cache/ci-artifact-01-20260917, the existing runner/APK fixture directories,
and .cache/artifact-maintenance-tests. Test-created junctions were removed by the
tested cleanup path. No PowerShell, external SDK/cache directory, token file,
force-push, reset, branch switch, release, deployment or device operation was used.
