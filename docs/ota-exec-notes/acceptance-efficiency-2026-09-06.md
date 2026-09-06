# Acceptance efficiency governance, 2026-09-06

## Scope and authority

The user requested governance changes that prevent unnecessary P2-5/P2-6-style
reruns without weakening independent acceptance. This is a governance-only task;
no product card is claimed, no firmware is changed, and no historical frozen
bundle is rewritten. Commits, remote CI, deployment and hardware operations are
not authorized by this editing request.

On 2026-09-07 the user explicitly authorized committing and pushing this batch.
The publication branch is codex/acceptance-batch-governance-20260907. This does
not authorize merging main, deploying, or running hardware operations. The
completed local checks below are retained; publication is not formal acceptance.

## Research and implementation contract

- Keep Git-object freezing, execution-worktree cleanliness, physical evidence
  validation, frozen gates, independent review and bounded operation quotas.
- Permit approved component profiles from the frozen profile configuration.
  Unknown or incomplete dependencies must fail closed, never silently narrow.
- Separate collection criteria from offline analysis/packaging criteria. A
  changed collector invalidates its observations; a changed packager must not
  cause unrelated acquisition or firmware builds.
- Multi-round reuse must point directly to a physically validated original
  EXECUTED PASS. Missing originals, changed inputs, later failures, tampering,
  circular references and fabricated command/artifact records must fail closed.
- Update entry-point guidance, templates and governance CI together. Verification
  uses host regression tests only, not a fresh P2-5/P2-6 hardware campaign.

## Verification

Initial checks completed before the batch-review follow-up below (serial
execution, Python bytecode disabled, fixtures and output inside this project):

| Check | Result |
| --- | --- |
| test_acceptance_bundle.py | 94 passed; symlink tests required |
| test_acceptance_efficiency.py | 22 passed |
| test_ac5_ram_budget + test_f435_build_bootstrap | 17 passed; static host checks only |
| test_p2_5_build_provenance, eight Python-only cases | 8 passed |
| Template contract/matrix CLI with --allow-draft | Valid draft; overall=NOT_RUN, not product acceptance |
| cap.ps1 AST, ASCII and CheckOnly | Passed before the startup-cache audit exception was discovered |
| git diff --check | Passed; Git reported seven LF/CRLF conversion warnings, not test failures |

Three worktree-guard tests that spawn PowerShell were deliberately not run after
the cache discovery; they remain in CI, not converted to skips or successful
results. CI wiring includes the new regression suite and affected entry files.
No remote CI was triggered, no commits/pushes were made, and no hardware or
firmware/simulator build was run. A capture preflight is not visual UI acceptance.

A separate read-only reviewer identified intermediate-round failure laundering,
missing module/basename entry detection and attached inline-interpreter bypasses.
These were fixed with adversarial
regressions. Actual product/collector changes still require new observations;
missing/tampered originals, missing history plans, self-reference and later
failures cannot be replaced with an older PASS. Each historical matrix is checked
once per validator invocation, without rebuilding old products or recapturing.

Final wording was aligned with the tested behavior: declared component groups
are allowed, a valid REUSED PASS can retain its original execution anchor, and a
production-bound build entry does not also require Validation solely because it
is a script. Actual acceptance probes and helpers remain declared dependencies.

The first test iterations exposed a set/slice exception, changed error ordering,
and an overly broad app profile intersection. These were corrected without
relaxing the existing isolation, command, hash or negative-test requirements.
Final logs are in .cache/acceptance-efficiency/. Local self-tests and read-only
review are not independent formal acceptance; CI must be inspected after an
authorized commit/push before claiming governance closeout.

## Operational contract

### Follow-up: batch review and execution scope

The user requested a further pass after the remaining risks were identified:
piecemeal reviews, whole-card restart wording, overly broad dependency groups,
and successful re-execution outside a computed plan. This follow-up reuses the
same research note, tests and CI entry, rather than starting another audit kit.

The bounded change is to require a consolidated review/fix batch before costly
formal acceptance, distinguish safe in-scope defects from stop conditions, review
profile consumers before freezing, and reject unplanned EXECUTED PASS commands
when validating a current round against its predecessor. Shared commands already
required by an invalidated criterion need no duplicate execution. New failures
and gaps must still be reported; an old PASS cannot erase them. Planning output
must not be mistaken for final acceptance. No scheduler or automatic hardware
quota counter is introduced, and historical frozen bundles remain unchanged.

Function/CLI contract: validate_planned_execution(matrix, contract, rerun_plan)
returns a list of errors. The CLI invokes it for the current round when a valid
previous pair was supplied and --write-rerun-plan is absent. Existing contract,
matrix, physical-evidence and reuse checks still run; no schema fields or
historical source bundles are rewritten.

| Current-round case | Scope-check behavior |
| --- | --- |
| Reusable EXECUTED PASS adds an unplanned command | Reject with unplanned EXECUTED PASS; final CLI exit 1 |
| Its complete command set is already required by another invalidated criterion | Permit consuming the one scheduled execution; other checks still apply |
| A shared command is used to bring along extra commands | Reject the extra commands |
| New FAIL or NOT_OBSERVED | Preserve the report; do not grant retroactive execution authorization |
| REUSED | Existing physical origin/history validation still required |
| --write-rerun-plan | Plan output plus FINAL_VALIDATION=NOT_RUN, not final VALIDATION=PASS |

Wrong: copy a previous EXECUTED PASS into another round and run all commands
again simply because the validator accepts the evidence. Correct: generate the
plan, use verified REUSED results or the one already-scheduled shared execution,
and obtain approved invalidation/operation scope before extra observations. A
failure is still a failure and is never hidden to meet a round limit. Deliberate
omission of the actual previous round cannot be inferred from an isolated bundle;
the execution rules require it even when all results are EXECUTED.

This stable batch passed both affected suites, once each, in serial:

| Command | Result | Log under .cache/acceptance-efficiency/ |
| --- | --- | --- |
| python -X utf8 -B tests/ota/test_acceptance_efficiency.py | 31 passed, 168.520 s | test_acceptance_efficiency-batch.log |
| python -X utf8 -B tests/ota/test_acceptance_bundle.py | 94 passed, 122.745 s | test_acceptance_bundle-batch.log |

The nine new tests cover the scope cases above, the plan-only CLI boundary, and
recording a new failure followed by a committed fix and valid retest. The 22
earlier efficiency cases and 94 existing acceptance cases remain green. Tests
ran from the project root through cmd.exe with TEMP/TMP/TMPDIR pointing to
.cache/acceptance-efficiency/temp, PYTHONDONTWRITEBYTECODE=1,
GIT_CONFIG_GLOBAL=NUL, GIT_CONFIG_NOSYSTEM=1, GIT_OPTIONAL_LOCKS=0, and
OTA_REQUIRE_SYMLINK_TEST=1. No PowerShell subprocess, firmware/simulator build,
hardware operation, commit, push or remote CI was performed for this follow-up.
The earlier 17 static build checks and eight provenance checks were not rerun
because this batch did not change those inputs. The three PowerShell tests remain
pending; these 125 local passes are not formal independent acceptance or CI.

### Reuse and dependencies

Component groups extend, rather than replace, the three conservative base groups.
Profiles and their required paths are read from each frozen Git tree. Commands
declare input_groups and runner_paths; criterion dependencies must cover command
dependencies. Transitive dependencies, SLA provenance and honest observations
still require non-implementation review, not merely nonempty declarations.

New REUSED records bind origin_contract_sha256 and origin_matrix_sha256. The
actual previous round remains bound, and --reuse-source supplies original and
intermediate bundles for read-only verification. Original evidence is the only
observation anchor; intermediate reuse never becomes a new experiment. Changed
criteria, tools or external inputs invalidate the relevant consumers. Unknown
dependencies require conservative scope or a decision, never silent exclusion.

## PR integration, 2026-09-07

The user subsequently authorized merging this work into main so later
implementation and acceptance sessions use the updated rules. PR #23 targets
main from codex/acceptance-batch-governance-20260907. The implementation commit
is 460bb4262d30c021966601ab1d388640decb07b5; no squash or rebase merge is allowed.

Governance CI for that commit passed:
https://github.com/Eitan-S-23/E-Track/actions/runs/34049428961

- 153 regression tests passed: 94 acceptance, 31 efficiency, 3 AC5 RAM,
  14 build-bootstrap and 11 provenance tests, with no skipped test reported.
- The three PowerShell-dependent provenance checks deferred on Windows ran in
  CI. This resolves their CI verification gap, not the local startup-cache rule.
- All 8 spec probes and 20 classification self-tests passed.
- The APK/EXE workflow ran its path detector only; Android, Windows, Pages and
  release jobs were skipped because their product inputs did not change.
- One existing warning remains: actions/checkout@v4 targets deprecated Node.js
  20 and was run on Node.js 24. No product build or deployment was triggered.

The raw job log is .cache/acceptance-efficiency/governance-pr23-460bb42.log;
SHA-256: 97e0e8325df7529685490c6cd2d1d68b1b653b62188c22765b476ac4ca9f2124.
Independent read-only review found one blocking scope-laundering path: a mixed
REUSED/EXECUTED intermediate round that never passed final validation could
become a later reuse source. A three-round regression reproduced the invalid
success before the fix; historical-round validation now also calls
validate_planned_execution. The capture launcher also uses a visible window for
screen capture instead of depending on a hidden process exposing MainWindowHandle.
No simulator/hardware capture was run for this governance change. A focused
follow-up read-only review checked the fix, the new regression and the remaining
template/document differences, and reported no remaining merge blocker. It did
not claim runtime capture verification or independently hash the CI log.

The targeted three-round regression failed before the fix (invalid success,
exit 0 instead of the required rejection) and passed after it in 16.835 seconds.
Logs are history-scope-red.log and history-scope-green.log in the same local
cache directory. The updated efficiency suite contains 32 tests. The latest
PR-head governance CI must pass before merge; the old 460bb42 run alone is not
approval for the corrected code. Final CI/merge identity is available on PR #23.
Then fetch and fast-forward the main worktree, verify HEAD equals origin/main,
and preserve all eight pre-existing untracked files and the other worktrees.

This record is committed before merging to avoid leaving closure evidence on an
already-merged feature branch. It is governance verification, not a new product
acceptance campaign or permission to rewrite historical frozen bundles.

## Filesystem audit exception

All chosen source edits, logs and test fixture outputs are inside E-Track.
However, the PowerShell startup optimization caches below were observed updated
during this session. No pre-session hash/stat baseline was recorded, so these
updates cannot be exclusively attributed to this session or excluded from it.
TEMP, TMP and TMPDIR do not contain this runtime feature. After discovering the
earlier audit in acceptance-framework-v3.md section 8.3, the agent stopped new
PowerShell launches, switched to cmd.exe, and did not clean or move either file.

- C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive:
  1,004 bytes, observed mtime 2026-09-06 18:57 local time.
- C:/Users/SU/AppData/Local/Microsoft/PowerShell/StartupProfileData-NonInteractive:
  103,432 bytes, observed mtime 2026-09-06 18:59 local time.

The final read-only audit observed further updates: the Windows/PowerShell file
was 1,004 bytes with mtime 2026-09-06 21:12, and the Microsoft/PowerShell file was
79,736 bytes with mtime 2026-09-06 19:32 (both local time). Final resumed checks
launched cmd.exe, not PowerShell; timestamps alone do not identify the writer.
The updated observations were reported, without cleaning either cache.

At the batch-review follow-up audit, the Windows/PowerShell cache was 1,004 bytes
with mtime 2026-09-06 23:42, and the Microsoft/PowerShell cache was 80,900 bytes
with mtime 2026-09-06 22:20 (local time). This batch launched only cmd.exe and
Python/Git tests, not PowerShell. These observations do not establish attribution;
both external files were left untouched and no cleanup authorization was inferred.

These are startup optimization data, not intentional project deliverables. The
user was notified. Keep them unless the user explicitly authorizes cleanup of
these exact paths; no outside-write permission was inferred. PowerShell-dependent
tests must wait for an approved/contained host or CI rather than silently writing
outside the project again.

Final project audit found no remaining fixture directories from the acceptance
or manifest-stability suites, and .cache/acceptance-efficiency/temp was empty.
Logs remain inside .cache/acceptance-efficiency/. The pre-existing
.manifest-test-mzl4deqo directory and the eight unrelated untracked files were
left untouched. No project-external move, cleanup or restoration was performed.
