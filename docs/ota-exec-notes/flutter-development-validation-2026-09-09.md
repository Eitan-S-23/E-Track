# Flutter Development Validation Entry

## Scope And Rationale

The user authorized adding a development-validation entry and updating project
rules on 2026-09-09. This is a CI/governance change, not implementation of the
remaining P3-3 findings. P3-3 product code, app tests, ownership, hardware criteria,
historical evidence and frozen acceptance bundles remain outside this change.

At entry, HEAD is `0ef3cc14f6fdbece4f15b45864b94cb1007af735`. The existing
`build.yml` already has uncommitted Flutter test/path changes; preserve them.
Its two analyze steps use `continue-on-error: true`, while the workflow also
contains packaging, signing and publishing operations. It is not an appropriate
sole development feedback loop.

## Implemented Change

- Added a read-only-token development workflow on `dev/flutter/**` pushes and
  explicit manual dispatch, with Linux and Windows hosts and no packaging,
  signing, deployment or release steps.
- Added a bounded Python runner for SDK setup, locked dependency resolution,
  strict analysis and tests. Keep configurable outputs inside the checkout;
  collect test results even when analysis fails, without masking either result.
- Exercised the runner's success, failure, timeout and boundary behavior with
  host tests. These are runner self-tests, not Flutter or independent acceptance.
- Clarified that explicitly authorized WIP commits may be used to obtain CI
  feedback before formal acceptance admission. Lack of an SDK or authorization
  means NOT_RUN, not completed remediation or a formal failed acceptance round.

The new runner is configured to clone the public Flutter stable branch into a unique
workspace-local run directory and record the actual SDK identity. Direct
retrieval of third-party Action metadata was unavailable in this session; the
entry therefore does not depend on unverified Action cache-path inputs.

The two existing `build.yml` analyze steps no longer use `continue-on-error`.
Existing implementation-owned test steps and path detection were preserved.
The new host regression is wired into Acceptance Governance and the new
development workflow. The workflow is covered by Validation and the new guide
by Governance; no historical profile blob or acceptance bundle was changed.

## Executed Verification

Commands ran from `D:\github\my\E-Track` using `cmd.exe`, with Python bytecode
writes disabled. The test executable was the installed Python 3.13 interpreter;
neither a Flutter SDK nor the real app tests were invoked.

| Command | Result | Raw log under `.cache/flutter-dev-checks-tests/` |
|---|---|---|
| `python -B tests/ota/test_flutter_dev_checks.py` (initial) | exit 1; 27 tests, one error | `host-20260909-01.log` |
| Same command after raw-byte PID parsing correction | exit 1; 27 tests, one error | `host-20260909-02.log` |
| Same script selecting the four process/Windows cases below | exit 0; 4 tests passed | `host-20260909-03-targeted.log` |
| `python -B tests/ota/test_flutter_dev_checks.py` (final code) | exit 0; 28 tests passed in 13.810 s | `host-20260909-04.log` |
| `python -B tests/ota/test_acceptance_bundle.py AcceptanceExecutionPolicyTests` | exit 0; 4 policy tests passed in 0.014 s | `policy-20260909-01.log` |

The four targeted cases were
`FlutterDevelopmentChecksTests.test_real_timeout_terminates_parent_and_child_without_hanging`,
`FlutterDevelopmentChecksTests.test_windows_batch_quoting_and_exit_propagation`,
`FlutterDevelopmentChecksTests.test_windows_job_assignment_failure_never_starts_the_command`,
and `FlutterDevelopmentChecksTests.test_real_process_preserves_stdout_stderr_and_exit_code`.
These are developer self-tests of this new entry, not acceptance rounds.

The first failure was in this session's test: native-codepage `taskkill` output
was read as UTF-8. The raw file was retained, and PID extraction now uses bytes.
The second run exposed a real runner weakness: this restricted host denies
`taskkill`, so timeout cleanup could not establish that descendants had exited.
The implementation now assigns a stdin-gated launcher to a kill-on-close Windows
Job Object before allowing it to spawn the command. Timeouts terminate that job
and verify its active process count reaches zero. Job-assignment failure never
starts the command. The real subprocess/child and batch exit-code tests passed;
no skip or weakened assertion was used to conceal either failure.

The old failing fixture children (PIDs 14392 and 3924) had bounded 60-second
lifetimes and were independently checked through native process handles as no
longer running. No process-name-wide termination was used. All original failure
logs and fixture outputs remain in the project cache.

Additional static checks passed: Python 3.9 grammar parsing of both new Python
files; PyYAML parsing of the new workflow, build workflow and governance workflow;
parsed assertions for branch scope, read-only token, both hosts, explicit shells
and working directories; and profile JSON parsing. This does not establish a
Python 3.9 runtime result or a GitHub Actions execution result.

## Deferred Verification

Actual SDK checkout/bootstrap, Flutter analyze/test, both remote development
jobs, APK/EXE builds, full governance CI and hardware remain NOT_RUN. The local
host tests exercised Windows; the POSIX subprocess branch awaits the Linux CI
host. No deployment, release, commit, push or workflow dispatch was performed.
Remote execution requires separately authorized validation-branch commit/push
or dispatch. P3-3 stays in progress; formal acceptance is NOT_RUN.

The user-authorized change is the development entry and rules, not closure of
RC3-01 through RC3-12 or resolution of the P3-3/P3-5 hardware-criteria difference.
Once authorized, obtain CI feedback on the actual committed remediation batch,
fix failures in the implementation session, then proceed through the unchanged
build and independent-acceptance gates. Do not call another static-only batch
complete or invent a formal failed acceptance round.

## Output Boundary

Before the first edit, all target paths were normalized beneath
`D:\github\my\E-Track`. All 22 existing target/ancestor nodes passed direct
`fsutil reparsepoint query` checks as non-reparse points. New files use their
checked nearest existing parents. Host fixture outputs were confined to
`.cache/flutter-dev-checks-tests/`; no legacy temporary scripts were run.

Only the new CI/runner/host-test files, the new guide/this note, the two AGENTS
files, execution-governance text, profile ownership and board records were
edited. The four previously pure-CRLF files edited in this task were normalized
back to CRLF after patching. Root AGENTS and the board retain their pre-existing
mixed line endings.

## Final Audit

- All 68 protected files (app source/tests and the existing P3-3 research record)
  match their pre-edit byte hashes. No P3-3 product/test remediation was performed.
- Compared with the pre-edit dirty workflow, `build.yml` differs only by removal
  of its two analyze `continue-on-error` lines. Every other line, including the
  implementation-owned edits, is preserved.
- Every pre-existing board line is preserved byte-for-byte and in order. Exactly
  three records were added: the P3-3 governance note, section 9 registration and
  section 10 journal. The board retains 728 CRLF lines, and root AGENTS retains
  its original 703 CRLF lines. The card owner, state and hardware criteria did
  not change.
- The self-test cache contains 354 files / 160394 bytes, all under the new
  `.cache/flutter-dev-checks-tests/` directory. No link/junction remains in that
  cache. Only test-owned fixture lockfiles and test-created links were removed;
  no historical files were deleted, moved, rewritten or executed.
- The non-board tracked files changed for this task pass scoped `git diff --check`.
  Repository-wide `git diff --check` still reports the pre-existing board line
  626 only; it was intentionally not rewritten. Existing access diagnostics for
  `.manifest-test-mzl4deqo/` and `.pytest_cache/` remain untouched.
- All agent-selected writes were inside `D:\github\my\E-Track`. No local Flutter
  SDK installation, PowerShell startup, project-external output, commit, push,
  dispatch, build, deployment or hardware operation was performed.

Raw-log SHA-256 checksums (development logs, not acceptance freeze anchors):

| Log | SHA-256 |
|---|---|
| `host-20260909-01.log` | `9b3f6affea4fa6ffd2f2386350fbfca7f6987443be3345c7c9c279f1231d951e` |
| `host-20260909-02.log` | `810f79206f83536475395c96cd85c7ad68c28ee3f8f8b23d53b7d07b91f0b311` |
| `host-20260909-03-targeted.log` | `d40960dd9d9b3d3fcb8058ea326fba0a2ee9514c3bba7acf1e36567db9da2101` |
| `host-20260909-04.log` | `355c737dc17c12daabaf268754a7a4c6ac52d6df2a7fbdaf363e7af004194890` |
| `policy-20260909-01.log` | `5f1137cfb5f69a32f626dae0b03fa7a60bbe9fde8f7c13c4a9581df6c8ce6154` |
