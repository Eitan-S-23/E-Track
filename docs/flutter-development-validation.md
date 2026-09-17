# Flutter Development Validation

## Purpose And Authorization

Development feedback must be available before a stable implementation can be
submitted for independent acceptance. Do not make green tests or a frozen
acceptance bundle prerequisites for an explicitly authorized WIP validation
commit. Do not use repeated static reviews as a substitute for missing runtime
feedback.

The user's 2026-09-09 follow-up grants standing authorization for the bounded
implementation-agent self-test operations below. It replaces the earlier
per-batch root-only approval requirement for this development path only.
It does not authorize mainline changes, merge, release, deployment or hardware.

### Standing Authorization

- Implementation agents may stage/commit their assigned changes on an exclusively
  owned `dev/flutter/**` validation branch, push it using the `Eitan-S-23`
  identity, and dispatch or rerun only `flutter-dev-checks.yml` on that branch. No repeated
  user approval is needed for the same bounded self-test loop.
- Verify the repository/remote and account before pushing. Review explicit staged
  paths and hunks; preserve unrelated dirty/untracked files, other agents' changes,
  secrets and caches. Initial bootstrap may include the reviewed development
  workflow/runner/rules delivered with this authorization, not arbitrary old work.
- Never switch branches or mutate a shared Git index while another agent is using
  that worktree. Use an exclusive validation worktree within the approved project
  boundary or have the root session serialize these already-authorized operations.
- No force-push, branch overwrite, main/master/tag push, merge, production workflow,
  release key, publishing, deployment or hardware action is covered. Do not change
  GitHub credentials/remote settings or bypass sandbox restrictions to make it work.
- Agents may inspect this repository's CI results and download artifacts into a
  preflighted project-local directory. Record commit, run URL, both host results,
  exact scope and APK checksum. Explicit later prohibitions or narrower task
  authorizations override this allowance.
- Rerun only for changed inputs, a new validation request or a diagnosed transient
  environment recovery. Inspect the run's workflow/ref first, prefer failed-job
  retries where appropriate, and do not repeatedly restart an unexplained failure.

This is policy authorization, not provision of GitHub credentials, token workflow
scope or filesystem write access. A missing credential or a read-only `.git` is a
technical prerequisite to resolve with the root session, not a reason to keep
claiming source-only remediation is complete or to request redundant policy approval.

Local Flutter builds and packaging remain prohibited. Contained local non-build
analysis/tests remain allowed under the app rules when an SDK is actually
available and its writes and subprocesses have been checked. Installing an SDK
outside the project or starting uncontained PowerShell needs separate approval.
The automated entry below is deliberately CI-only, not a local SDK installer.

## Entry Point

Workflow: `.github/workflows/flutter-dev-checks.yml` (Flutter Development Checks).
Runner: `Tools/flutter/dev_checks.py` (Python 3.9 or newer on the hosted runner).

- Pushes to the explicitly selected `dev/flutter/**` branches run without a path
  filter, so first bootstrap and a new APK request cannot be silently skipped
  just because the latest commit touched documentation. The workflow file must
  be in the pushed commit. No main/master merge is needed; ordinary branches
  and mainline documentation changes do not trigger this workflow. Push to a
  validation branch only for needed feedback, not to repeat unchanged checks.
- Manual dispatch offers `test_scope=all` or `test_scope=ota`, plus `build_apk`.
  Only explicit `workflow_dispatch` with `build_apk=true` requests a debug APK.
  All pushes, including legacy `dev/flutter/apk/**` branches, are checks-only.
  APK requests force `all` tests on both hosts. GitHub must first
  know the workflow on the default branch for manual dispatch to be available;
  use the authorized validation-branch push for initial bootstrap instead of
  merging an unverified batch just to enable the button.
- Both Ubuntu and `windows-2022` run independently (`fail-fast: false`). Windows
  shell steps use `cmd`, not PowerShell. Windows-only BLE discovery tests are
  meaningful only on the Windows host, not when skipped on Linux.
- The token has only `contents: read`; checkout does not persist credentials.
  Only the Linux job can build a debug APK, after its checks pass. There are no
  production signing secrets, EXE builds, publishing or deployment steps. A
  Windows test failure keeps the overall run red even if Linux produced an APK.
- Both CLI entries reject non-`dev/flutter/**` refs. The workflow does not become
  an authorized path to test or package arbitrary mainline/release refs.

Under the standing authorization, an implementation agent in an exclusive
worktree may use a new checks-only branch after reviewing the staged files:

```cmd
git switch -c dev/flutter/p3-3-validation
git diff --cached --name-only
git commit -m "WIP: validate Flutter development batch"
git push -u origin dev/flutter/p3-3-validation
```

The legacy `dev/flutter/apk/` branch prefix no longer requests packaging. The
allowance covers only these bounded development actions, not main/master/tag
pushes, merge or shipping a red validation commit.
Existing validation branches must integrate the new workflow and runner before
they receive this behavior. Actions uses the workflow in the pushed/ref commit;
rerunning an old commit does not retroactively change its APK trigger, retention
or console diagnostics. The daily maintenance job independently uses trusted main
and can classify old development artifacts without rewriting those branches.
Once a dispatchable workflow exists, a targeted checks-only run is:

```cmd
gh workflow run flutter-dev-checks.yml --ref dev/flutter/p3-3-validation -f test_scope=ota
```

A debug APK request on the validation branch is:

```cmd
gh workflow run flutter-dev-checks.yml --ref dev/flutter/p3-3-validation -f test_scope=all -f build_apk=true
```

Read-only result inspection:

```cmd
gh run list --workflow flutter-dev-checks.yml --branch dev/flutter/p3-3-validation
gh run view RUN_ID --json headSha,url,conclusion,jobs
```

## Commands And Results

The development workflow uses a Git sparse checkout for the complete Flutter
package, its host checks, runners, workflow definitions, ignore/attribute rules
and profile/documentation dependencies. Unrelated firmware payloads and historical
acceptance bundles are not materialized in this disposable development checkout;
their Git objects and the archived evidence are not edited or deleted. This is
not the checkout mode for independent acceptance or Acceptance Governance CI.
When a check gains a repository dependency, update the checkout patterns and the
real-Git sparse-checkout regression together.

Before a Linux debug APK run, the workflow logs free/used/total bytes and requires
12 GiB free. This is a cold-run resource budget for SDK/NDK bootstrap, Gradle
dependencies/intermediates and packaging headroom, not an OTA acceptance gate or
a guarantee that future toolchains will fit. Insufficient capacity fails early,
before SDK downloads; final disk usage is logged even after later failures. The
workflow does not delete preinstalled tools, local developer files or frozen
evidence, and does not narrow the Flutter test suite or APK target architectures.

The runner first verifies the explicit checkout root, the selected package/test
directory and the existing lockfile. It then uses a fresh directory under
`.cache/flutter-dev-checks/runs/` for SDK, HOME/USERPROFILE, AppData, pub cache,
XDG cache/config, temporary files and logs. It checks normalized paths and full
existing parent chains, rejects links/reparse points and never reuses an old
run's report. No SDK cache or artifact is downloaded onto the developer machine
by adding this entry.

| Step | Command | Timeout |
|---|---|---|
| SDK checkout | `git clone --config core.longpaths=true --depth 1 --branch stable https://github.com/flutter/flutter.git <run>/sdk` | 180 s |
| SDK identity | `flutter --version --machine` | 300 s |
| Dependencies | `flutter pub get --enforce-lockfile` | 300 s |
| Analysis | `flutter analyze --no-pub` | 300 s |
| Tests | `flutter test --no-pub --reporter expanded --timeout 2m test` | 600 s |

`ota` changes only the final positional test directory to `test/ota`; it does
not narrow analysis. `all` covers the app's unit/widget test directory, not
device integration tests or other repository components. Targeted green tests
do not stand in for app-wide validation of a stable batch. Choose scope according
to affected callers, codecs, tests and dependencies, not just one file's hash.

The SDK follows the same stable channel as `build.yml`; the raw version command
records the resolved Flutter/Dart revisions. This is not a pinned environment
or a formal evidence-reuse decision. A future acceptance profile must bind its
actual SDK/environment inputs separately. Each development run is cold and
workspace-local rather than relying on undocumented third-party cache settings.

Setup/dependency failure leaves downstream steps NOT_RUN. Analysis failure or
timeout still collects tests if process cleanup succeeded, but the overall run
fails. Any test failure, command timeout, launch error or lockfile change fails
the run. Windows uses a kill-on-close Job Object and a stdin-gated launcher so
the command cannot spawn children before job assignment; POSIX uses an isolated
process group. Cleanup targets only that command tree, without `taskkill` or
process-wide name matching. If cleanup is unproven, no later command starts.
There are no automatic retries, diagnostic
suppression or `continue-on-error` overrides.

Each run records exact arguments, working directories, actual exit codes,
timeouts, SDK logs, checkout identity/status, host/Python, run URL/attempt and
lock hashes. `result.json` and raw combined stdout/stderr logs are uploaded with
`always()` even after a failure. Checks upload logs/reports; a successful Linux
APK mode additionally uploads the debug APK and its metadata, never SDK/cache
trees. If setup/job cancellation prevents a complete report, use the failed or
cancelled Actions status and available console logs; never infer PASS from a
missing log. Development log retention is 14 days; preserve needed evidence inside an
approved project evidence directory before expiry. Debug APK retention is the
exception: new debug APK artifacts retain for 3 days. New `android-apk` and
`windows-exe` CI verification copies explicitly retain for 14 days; GitHub Release
assets are not changed. Existing artifacts keep their original expiry dates.

Before each upload, the runner also emits `DEV_COMMAND`, prefixed `DEV_LOG[name]`
lines and a final `DEVELOPMENT_RESULT` JSON summary to ordinary job stdout. The
summary binds the tested commit, host, scope, command status/exit codes, recognized
SDK identity, terminal test counts and `OTA_LINK_` line counts. SDK identities
come from `flutter --version --machine`, not a hard-coded SDK version. Test counts
are parsed only from a recognized terminal expanded-reporter summary; absent or
unrecognized values are `null`, not zero or a guessed PASS.

Console copies redact known credential environment values, credential fields,
authorization headers, private-key blocks and URL query/fragment/userinfo.
Machine summaries sanitize structured values before JSON serialization, so
redaction cannot break JSON quoting. Private-key blocks are suppressed before
tail selection so clipping cannot expose a block whose opening marker was lost.
Child output is prefixed so it cannot inject Actions workflow commands. At most
64 KiB of complete trailing log lines is mirrored per command; the console marks
truncation and counts scan the entire raw log. Oversized individual lines are
omitted from the console, not split into potentially unredactable fragments.
Raw project-local logs are retained unchanged. Missing logs or a failed console
copy fail diagnostics without changing the original command exit code. The
original Job Object/process-group cleanup and strict upload steps still apply.

## Debug APK Mode

`Tools/flutter/dev_apk.py` is a Linux-CI-only helper. It reuses the same Flutter
SDK and locked dependencies that just passed analysis and full tests. A failure
in either check prevents APK setup/build; build or signature verification failure
prevents collection. The source checkout must remain the committed input tested
above. No device is connected or operated by this workflow.

The hosted runner must provide `JAVA_HOME_17_X64` and Android command-line tools.
They are read-only bootstrap inputs. The helper creates its own Android SDK,
Java home/temp preferences, Gradle cache and wrapper-bootstrap project under
the checked run directory. Existing hosted license records are copied; it does
not automatically accept new license terms. Missing prerequisites fail explicitly.

Gradle's version comes from the tracked wrapper properties. The official binary
distribution is SHA-256 checked before path-checked extraction. The bootstrap
uses the app's compileSdk (currently 35) and Build Tools 35.0.0 for AGP 8.9.1;
review this dependency when changing AGP. Required NDK components may be installed
by Gradle in the workspace-local SDK. Tracked Gradle/app configuration is not
rewritten: only Git-ignored generated wrapper files and `local.properties` in
the disposable CI checkout may be refreshed.

The build command is `flutter build apk --debug --no-pub
--target-platform=android-arm,android-arm64`, followed by `apksigner verify`.
The helper collects `trace-dev-debug.apk` and a JSON record with commit, size,
SHA-256 and `development-debug-apk` classification. Their artifact name includes
the commit, run ID and attempt. SDK/cache trees and debug keystores are not uploaded.
The job has a 90-minute outer bound, with individual setup/build command timeouts;
normal checks-only runs do not enter any APK step.

This debug-signed APK is for development, not distribution to users, release
signing verification, Windows EXE verification or independent acceptance. It
does not need a shipping version bump. Its signing identity can differ from an
installed release and from another CI run. Do not install it, uninstall an
existing app or clear device data without separate hardware authorization.

## Completion And Review

Record four distinct outcomes: source edits, development self-tests, APK/EXE
builds, and independent acceptance. Include commit SHA, run URL, actual scope,
SDK identity, both host results and original failures with a remediation report.
No SDK, missing authorization, compilation failure or an unexercised test oracle
must not be relabeled as completed remediation. Request the bounded validation
route early and keep missing checks NOT_RUN.

Passing checks or generating a debug APK does not satisfy the release-mode
APK/EXE build gate. Shipping app
input changes still need authorized `build.yml` runs with both required builds
passed. Development-only checks do not need a shipping version bump. Existing
release/version/signing rules still apply when preparing an APK to ship.

Self-tests are not independent acceptance. The unchanged execution contract
requires committed implementation/runner inputs, approved frozen profiles and
criteria, the execution-worktree gate and NOT_RUN matrix precheck. Formal
reruns still use `validate_bundle.py` and its `required_commands`; these reports
are not replacement manifests or original independent EXECUTED PASS anchors.
This entry does not satisfy or lower P3-3's hardware criteria. OTA-DEC-013
(2026-09-10) assigns actual APK installation and both toy/real-package device
upgrade round trips to P3-3 before completion. P3-5 retains real-backend candidate
integration and ten independent disconnect recoveries. The task Specs define
the required bootable assets and final GET_INFO identity observations; a debug
APK or fake test is not that evidence. No hardware authority follows from this
development entry.

## Runner Regression

From the project root, without a Flutter SDK, network access or PowerShell:

```cmd
python -B tests/ota/test_flutter_dev_checks.py
python -B tests/ota/test_flutter_dev_apk.py
python -B tests/ota/test_artifact_maintenance.py
```

This tests the orchestration and real subprocess failure/timeout handling using
small host fixtures. Fixture output stays under the checked project-local
`.cache/flutter-dev-checks-tests/` and `.cache/flutter-dev-apk-tests/`; it neither changes app tests nor establishes
that they compile or pass. The host regression is also wired into both this
workflow and Acceptance Governance CI. The development workflow belongs to the
Validation profile and this guide to Governance; historical frozen profile
blobs and bundles are not rewritten.

## Artifact Maintenance

### Scope And Trigger

`.github/workflows/artifact-maintenance.yml` runs daily at 02:17 UTC (10:17
Asia/Shanghai), independently of build/upload success. Only the trusted `main`
workflow in `Eitan-S-23/E-Track` may run. The job alone has `actions: write`;
development jobs remain read-only. Concurrency is serialized without cancelling
an in-flight batch. Scheduled runs apply the bounded policy after authorized
mainline integration. Manual runs default to dry-run. The user's 2026-09-18
revocable allowance in execution contract section 7.3.3 permits implementation
and acceptance agents to initiate a bounded manual cleanup without asking again
for each batch. It is not general deletion permission or a local DELETE entry.

Before dispatch, coordinate serially with the root session and review a dry-run
against current task deliveries and evidence dependencies. Pinned, in-use,
pending-review, acceptance-referenced or ambiguous assets are protected. The
helper cannot infer all such dependencies: an unpinned protected candidate blocks
apply until the root session resolves protection through the governance process.
Do not drop its ID and assume the remaining subset is the same reviewed plan.

Record one cleanup incident, actor, dry-run source, selected IDs/reasons and
protected assets in the existing task record. The incident permits at most 50
IDs in total; changing agents/runs or immediately repeating batches cannot reset
that cap. No eligible candidates means stop, not broaden the scope to free space.
If the workflow cannot start because of billing or missing access, report the
blocker to the root session. Do not forge CI variables or substitute direct API
deletions under this standing allowance. A separately authorized root-session
local cleanup is a one-off operation, not a new routine entry.

### Signatures

CI entry: `python3 -B Tools/flutter/artifact_maintenance.py --repo-root .`
Optional mode: `--mode dry-run` or `--mode apply`. The normal workflow supplies
`ARTIFACT_MAINTENANCE_MODE` and the job's `GITHUB_TOKEN`, never a new PAT.
Manual apply additionally requires `approved_artifact_ids`, a nonempty CSV of
1-50 distinct positive decimal artifact IDs from the reviewed dry-run. The
workflow passes it as `ARTIFACT_MAINTENANCE_APPROVED_IDS`; the CLI equivalent is
`--approved-artifact-ids`. It binds a set, not the ordering, and cannot override
selection or pins. Missing/malformed IDs or any difference from the current
candidate set fails before DELETE. Scheduled apply remains policy-driven.

Non-destructive manual plan (still creates a CI run):
`gh workflow run artifact-maintenance.yml --ref main -f mode=dry-run`.
After review, apply only that list:
`gh workflow run artifact-maintenance.yml --ref main -f mode=apply -f approved_artifact_ids=<id1,id2>`.
The entry and guard must already exist on trusted `main`; a feature-branch copy
does not confer production maintenance access. Keep CLI config/cache/temp output
inside the preflighted active project, without changing existing credentials.
Offline regression: `python -B tests/ota/test_artifact_maintenance.py`.

### Contracts

Policy: `Tools/flutter/artifact_maintenance_policy.json`. The repository ID,
workflow path, branch prefix and artifact prefix are fixed authorized scopes.
Only `flutter-dev-debug-apk-<40-hex-commit>-<run-id>-<attempt>` artifacts from
`flutter-dev-checks.yml` and `dev/flutter/**` qualify. Artifact API metadata,
repository/head repository, workflow ID, commit, source branch and the exact
run attempt must agree; the latest run must be completed too.

An unpinned, unexpired artifact from a completed run is eligible at 72 hours old
OR outside the newest two eligible rolling copies of its source branch. Pins
and active runs do not consume these two rolling slots. Ordering uses UTC
creation time then artifact ID, never local time or API page order. The initial
12 evidence/latest IDs retained on 2026-09-17 are pinned with reasons. Pins only
protect against this helper: they cannot stop native GitHub expiry. Archive
required bytes before expiration; TTL configuration does not update old copies.

Each invocation fully enumerates inventory, plans at most 50 IDs, revalidates
each immediately before DELETE and journals intent/results. Excess backlog waits
for a future invocation. It never deletes runs, logs, caches, tags, Release assets,
`android-apk`, `windows-exe`, other prefixes or other repositories.

`CI_ARTIFACT_WARN_BYTES` is an optional positive repository variable in bytes;
the policy's `warning_budget_bytes` is the fallback. Unconfigured budgets and the
actual account quota are reported as unknown. Repository artifact bytes are not
account-wide billed usage. Actions artifacts and GitHub Packages share an
allowance; caches have a separate allowance, and other repositories plus delayed
accounting can affect account limits. Deleting artifacts reduces current storage
and future accrual, not past storage accrual or consumed runner minutes. Payment
or spending-limit blocks are separate. A warning budget never widens deletion
scope or promises immediate recovery. No visibility, billing or token-scope
change is made. See GitHub's [Actions billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

Output is ordinary `ARTIFACT_MAINTENANCE` JSON log lines plus checked workspace
`.cache/artifact-maintenance/runs/<id>/{operations.jsonl,result.json}`. No artifact
upload or external `GITHUB_STEP_SUMMARY` write is required. `confirmed_freed_bytes`
counts only HTTP 204 deletions whose IDs are absent in the final inventory;
unavailable final inventory leaves that value unknown.

### Validation And Error Matrix

| Condition | Behavior |
| --- | --- |
| Dry-run | Complete plan/report; zero DELETE calls |
| Manual apply lacks valid reviewed IDs | Nonzero exit before API client/output creation |
| Candidate ID set changed since review | Nonzero exit before any DELETE; review a new dry-run |
| Required/in-use/ambiguous candidate not pinned | Agent must not dispatch apply; coordinate protection first |
| Wrong repo/ref/event/checkout/policy | Nonzero exit; no deletion |
| Incomplete/changing pagination, duplicate IDs, invalid target metadata | Nonzero exit; no deletion plan applied |
| Pin, active run, expired artifact, other prefix | Preserve; no scope expansion |
| Candidate changes before DELETE | Stop batch; preserve prior receipts |
| DELETE transport/5xx uncertainty | One read-only reconciliation, no automatic retry, no successful-byte credit |
| API rejection or partial failure | Nonzero exit; no later candidate deleted |
| Final inventory cannot be verified | Nonzero exit; confirmed freed bytes unknown |
| Configured budget exceeded | Warning only; protected artifacts remain protected |

### Good, Base And Bad Cases

- Good: four recent, completed, unpinned APKs on one branch produce two oldest
  candidates; a different branch's newest copies are unaffected.
- Base: one fresh APK and only pinned/active/other-class artifacts produce no
  deletions. With no configured budget, usage is reported without quota inference.
- Good manual apply: reviewed IDs `11,12` equal the current selection; the helper
  still revalidates both artifacts and source runs before DELETE.
- Bad manual apply: reviewed ID `11` but a newly eligible `12` appears; neither
  is deleted. An empty candidate list does not justify deleting other classes.
- Bad: a forged artifact name, foreign workflow, missing digest, incomplete page
  or unsupported event fails closed rather than authorizing a best-effort cleanup.

### Required Tests

`test_artifact_maintenance.py` covers exact identity, attempt reconciliation,
age/count boundaries, pins, active runs, branch isolation, pagination, metadata
changes, dry-run, uncertain/partial deletion, caps, capacity and workflow/profile
coverage with an injected API. Runner tests exercise real stdout/stderr, exit
codes, timeouts, redaction, unknown counts and strict diagnostics; APK helper tests
remain in the same governance CI. Local self-tests are not independent acceptance
or proof that a scheduled GitHub invocation has executed.
Manual-apply tests additionally assert CSV/type/duplicate/cap rejection, exact-set
matching, changed pins/active runs, zero mutations on drift, CLI environment
propagation and unchanged scheduled behavior. No fixture deletes real artifacts.

### Wrong Versus Correct

Wrong: retry an uncertain DELETE, infer the account quota from past uploads, or
delete release/log artifacts to reach a target size. Correct: reconcile that ID
read-only, keep byte credit unknown/zero until proven, stop on failure, and retain
the original fixed scope and raw failure record.
Wrong: an implementation/acceptance agent deletes a candidate just because it is
not pinned, or keeps opening batches until billing clears. Correct: establish
that no active delivery/evidence needs it, bind the reviewed IDs, stop at the
incident cap, and report storage/job recovery separately from deletion.
