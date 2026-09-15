# Implementation-Agent Self-Test Authorization And APK Mode

## User Decision

On 2026-09-09, the user asked to give implementation agents a convenient
GitHub Actions self-test path, including APK generation, and to update the
project rules accordingly. The previous entry provided analyze/tests only and
still reserved commit/push/dispatch to a separately authorized root session.
It therefore did not yet grant an implementation agent an autonomous feedback
loop or produce an APK.

This task records a standing, bounded authorization for development validation:
implementation agents may commit only their assigned changes on exclusively
owned `dev/flutter/**` branches, push those branches using Eitan-S-23, and
dispatch the designated development workflow without asking again each batch.
Shared worktrees/indexes still require coordination; main/master, other agents'
changes, force-push, merge, tags, production workflows, release signing,
publishing, deployment and hardware operations remain excluded. Tool sandbox
and GitHub credential limitations are not changed or bypassed by this policy.

## Implemented Scope

- Extended the existing development workflow, not the release workflow. Normal
  validation branches retain checks-only behavior. `dev/flutter/apk/**` pushes
  or explicit `build_apk=true` dispatches request a debug APK.
- APK requests run full analysis/tests on both hosts. Only the Linux job builds
  the APK, after its own checks pass. A failing Windows job keeps the whole run
  red; a Linux APK alone is not proof of both-host validation.
- Keep SDK/Gradle downloads, caches, temporary files and APK outputs in the CI
  checkout. Reuse the hosted JDK 17 and Android command-line tools read-only;
  install Android packages in a workspace-local SDK. Preserve tracked Android
  configuration and use no production signing secrets.
- Preserve existing P3-3 product/test changes, ownership, review findings and
  formal NOT_RUN status. This is CI/governance work, not P3-3 remediation or an
  independent acceptance round.

The dedicated validation branches deliberately have no push path filter. This
prevents first bootstrap or a new APK request from silently doing nothing when
the tip commit is documentation-only. Main/master and ordinary feature branches
are not push triggers. Both CLI entries reject non-development refs. A reviewed
initial validation commit may carry the already-delivered entry/rules alongside
the implementation agent's scoped work; it does not require a mainline merge.

APK setup refreshes only Git-ignored generated Android wrapper files and
`local.properties`, never tracked Gradle configuration. The helper copies
existing hosted license records, verifies the official Gradle distribution
checksum before path-checked extraction, installs SDK packages under the run
directory, builds with `--debug --no-pub`, verifies the APK signature and records
its commit/size/SHA-256. Inherited Java/SDK-manager option overrides and production
signing environment variables are removed from the APK subprocess environment.
No APK is built after failed analysis/tests; failed build/signature verification
prevents collection. Checkout/commit and lockfile drift fail the run.

Authorization, entry usage and exclusions are synchronized in root/app AGENTS,
the development guide, execution contract section 7.3.2 and board rule 8. The
board also records this user decision in the P3-3 card, section 9 and section 10.
Existing reviewed/frozen implementation and acceptance documents are not rewritten.

## Preflight

Active root is `D:\github\my\E-Track`. The 25 existing output/ancestor nodes
passed direct reparse-point checks before writing. A read-only baseline covers
103 existing files, including app source/tests/Android inputs, the release
workflow and historical research. New helper fixtures will use only
`.cache/flutter-dev-apk-tests/` and new logs in
`.cache/flutter-dev-checks-tests/`. No old temporary script will be executed.

## Verification

All commands below ran from the project root via `cmd.exe`, with Python bytecode
writes disabled. Logs are in `.cache/flutter-dev-checks-tests/`.

| Command | Result | Log |
|---|---|---|
| `python -B tests/ota/test_flutter_dev_checks.py` (initial extension) | exit 0; 33 tests | `authorized-runner-20260909-01.log` |
| `python -B tests/ota/test_flutter_dev_apk.py` (initial) | exit 1; 16 tests, one failing subcase | `authorized-apk-20260909-01.log` |
| `python -B tests/ota/test_flutter_dev_checks.py` (policy/trigger guard added) | exit 0; 34 tests | `authorized-runner-20260909-02.log` |
| `python -B tests/ota/test_flutter_dev_apk.py` (ZIP correction) | exit 0; 16 tests | `authorized-apk-20260909-02.log` |
| `python -B tests/ota/test_flutter_dev_checks.py` (final inputs) | exit 0; 34 tests in 19.628 s | `authorized-runner-20260909-03.log` |
| `python -B tests/ota/test_flutter_dev_apk.py` (Java override guard) | exit 0; 16 tests in 9.567 s | `authorized-apk-20260909-03.log` |
| `python -B tests/ota/test_acceptance_bundle.py AcceptanceExecutionPolicyTests` | exit 0; 4 policy tests | `authorized-policy-20260909-01.log` |

The ZIP failure was retained, not hidden or reclassified as a product failure.
On Windows, Python normalizes backslashes in `ZipInfo.filename`; the original
negative fixture did not preserve its intended raw member name. The fixture
now writes and independently asserts the original name, and extraction checks
`orig_filename` as well as normalized path components. The corrected negative
case rejects the archive before extracting even its earlier ordinary member.

Other executed checks cover analysis/test failure propagation, APK admission,
build failure/no collection, branch and host restrictions, inherited environment
overrides, distribution checksums, traversal/symlink rejection, real Git ignore
protection for tracked files, generated-wrapper/local-property preservation,
artifact metadata and local-build refusal. Existing real Windows subprocess
exit-code/timeout/Job Object tests remain green. The small `.apk` ZIPs beneath
the helper-test cache are fixtures, not built or installable app artifacts.

Python 3.9 grammar parsing of the four runner/helper/test files and parsed YAML
checks for branch scope, boolean APK option, host matrix, full-scope selection,
read-only permissions, upload gates and mirrored governance triggers passed.
The helper and its tests are included by the existing Validation `Tools/` and
`tests/` roots; the development workflow/guide retain their existing profile
ownership. No profile schema, frozen profile blob or bundle was modified.

After keeping the Chinese policy marker as an ASCII Unicode escape in the test
source, the focused command
`python -B tests/ota/test_flutter_dev_checks.py FlutterDevelopmentChecksTests.test_standing_authorization_is_not_a_mainline_or_release_grant`
also passed (exit 0, one test; console output). This is the same policy case,
not an additional independent acceptance criterion.

This turn has not committed, pushed, dispatched Actions, installed Flutter,
downloaded a real SDK/Gradle distribution, built an app APK, deployed or operated
hardware. Actual Linux/Windows Flutter checks and APK toolchain/build remain
NOT_RUN. Policy authorization is not a claim that credentials, the current
sandbox or the remote runner have already been verified. The implementation
agent can use the standing authorization for its next scoped validation push;
there is no new per-batch user-approval requirement for that allowed operation.

## Preservation And Output Audit

All 94 protected existing inputs match their pre-edit hashes, including app
source/tests/Android inputs, pubspec files, the production release workflow and
the two historical research records. No P3-3 product or Flutter test was edited.
Except for the intentionally revised governance rule 8, every existing board
line is preserved in order; exactly three new records were appended. The board
retains 728 CRLF lines. App AGENTS and the governance workflow retain CRLF;
root AGENTS keeps its mixed format, with only edited policy paragraphs changing.

All selected outputs are inside `D:\github\my\E-Track`: the named governance/
runner/test files and new logs/fixtures in the two checked cache directories.
No historical script was executed, no unrelated file was removed or reverted,
and no project-external output or PowerShell process was created. Full
`git diff --check` still reports only the pre-existing board line 626; it remains
untouched. HEAD remains `0ef3cc14f6fdbece4f15b45864b94cb1007af735`.

Final log SHA-256 values (host self-test checksums, not formal PASS anchors):

| Log | SHA-256 |
|---|---|
| `authorized-runner-20260909-03.log` | `c12826c58ba687eb50eedb18106cc81c807107c62049c71983f6a10cdaeaa829` |
| `authorized-apk-20260909-03.log` | `3576df040251f8967620516a5eea75399551524d8a8107713b893d93bec7d7b0` |
| `authorized-policy-20260909-01.log` | `5f1137cfb5f69a32f626dae0b03fa7a60bbe9fde8f7c13c4a9581df6c8ce6154` |
