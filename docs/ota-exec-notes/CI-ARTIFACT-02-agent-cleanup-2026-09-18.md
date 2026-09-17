# CI-ARTIFACT-02: Bounded Agent Cleanup Authorization

Date: 2026-09-18 (Asia/Shanghai)
Owner: Codex, root coordination/governance session
Active project: `D:/github/my/E-Track`

## Authorization And Scope

The user explicitly approved implementing the proposed revocable, bounded
cleanup allowance for implementation and acceptance agents, cleaning currently
unneeded repository artifacts under that scope, and committing/pushing these
changes. This does not authorize deleting other artifact classes, changing
billing/visibility/credentials, building or operating devices, or including
unrelated product changes in the commit.

This is a CI governance change, not P3-4 product implementation or acceptance.
CI-ARTIFACT-01's prior self-tests/CI and pending independent acceptance remain
historical facts. No historical frozen contract or evidence bundle is modified.

## Pre-Implementation Review

- The existing trusted-main maintenance workflow already selects only verified
  `flutter-dev-debug-apk-*` artifacts from this repository's development workflow.
  Its 72-hour/rolling-count rules, 12 pinned IDs and 50-ID cap remain unchanged.
- The existing manual entry requires case-by-case authorization. Replace this
  with the user's narrowly scoped allowance, not general DELETE permission.
- Manual apply currently recomputes candidates without binding the reviewed
  dry-run list. Add exact approved-ID matching before any deletion; inventory
  changes must reject the batch rather than silently adding new candidates.
- The helper cannot discover all active tasks' evidence dependencies. Agents
  must coordinate their review of candidate use and existing pins before apply;
  an ambiguous or unpinned required candidate blocks dispatch, not protection.
- Artifact storage, accumulated storage usage, runner usage and payment/budget
  restrictions are separate. No cleanup result promises upload/job recovery.

## Execution And Evidence

Session evidence is under `.cache/artifact-agent-20260918/`. A baseline records
387 existing dirty/untracked files and the original edited files. GitHub CLI
cache/config output, temporary files, helper logs and tests stay in this project.
Existing credentials are read without printing or changing them.

The initial GET `/user` failed with a transport EOF before repository discovery;
no DELETE occurred. The failure is retained under `inspection/api/0001.json`.
A bounded GET-only retry uses HTTP/1.1. Inventory, candidate review, actual
deletion receipts (if any), tests and Git closeout will be recorded below.

## Inventory Result: No Eligible Deletions

Authenticated actor: `Eitan-S-23`. Repository identity: `1310649784`;
development workflow ID: `353793017`. The successful inspection used 19 GET
requests and no DELETE, at `2026-09-17T20:40:56.812494Z` (2026-09-18 local).

| Scope | Count | Bytes | Disposition |
| --- | ---: | ---: | --- |
| All repository artifacts | 305 | 1538665642 | Preserved |
| Development debug APKs | 12 | 902646481 | All 12 are pinned |
| Other artifact classes | 293 | 636019161 | Outside the approved deletion scope |
| Eligible candidates / backlog | 0 / 0 | 0 | No apply, no DELETE, 0 bytes freed |

The authenticated full inventory and source-run checks found no unpinned
development APK. The user-approved scope therefore permits no current deletion.
Do not unpin evidence or delete a different class merely to produce a nonzero
cleanup result. Account quota and upload/job recovery remain unknown/unverified.

- Policy SHA-256 (unchanged):
  `c2fe4e7ca445adfb6d3fcbb8becc38070d44d99b4e74fce6012ffa284349d7b3`.
- Plan: `.cache/artifact-agent-20260918/inspection-02/plan.json`, SHA-256
  `bf33f6f27a809d5ca0844aaa675696b7cf3a0cf4aab3faa51ada9d44324b4c00`.
- Raw GET records: `.cache/artifact-agent-20260918/inspection-02/api/`.

## Implementation And Local Validation

The helper and workflow now require a reviewed, exact artifact-ID set for manual
apply. IDs cannot select a subset, override pins or add newly eligible candidates.
Scheduled policy selection and the trusted-main context checks are unchanged.
Authorization is recorded in the execution contract section 7.3.3, both AGENTS
files, the development guide and the board; API cleanup is not product acceptance.

Executed with Python 3.13 using `-X utf8 -S -B`, repository cwd and contained
home/cache/temp directories. The fixtures use injected APIs; no test sends a
real GitHub deletion or builds Flutter/firmware.

| Command | Result | Raw stderr SHA-256 |
| --- | --- | --- |
| `python -X utf8 -S -B tests/ota/test_artifact_maintenance.py` | 29 tests, exit 0 | `58170ab061a70d54976c0c7ae6d4057dc2d3331e77183b84b25d821b4fcbaa5f` |
| `python -X utf8 -S -B tests/ota/test_flutter_dev_checks.py` | 62 tests, exit 0 | `4a7f575b52b809f84802bbb15f8a88b309205500fbd1f0a20945d78628972d97` |
| `python -X utf8 -S -B tests/ota/test_flutter_dev_apk.py` | 26 tests, exit 0 | `b23a566f9d2da9b6df3550abc5f4fc7c0c84c01168467765b53eef8344c2e723` |

All 117 host tests passed. Eight new maintenance tests cover invalid/duplicate/
over-cap IDs, exact-set matching, newly protected/active candidates, dry-run
non-mutation and CLI/scheduled behavior. Python 3.9 syntax compatibility,
workflow YAML parsing and input-to-environment wiring also passed. Raw logs and
hashes are in `tests/` and `evidence/summary.json` under the session directory.

## Status

Implementation and local validation are complete; cleanup assessment completed
with zero eligible artifacts and zero deletions. Implementation commit
`7664b082dfd86f3b114d823688833f912fb00302` was pushed to `main`; a subsequent
fetch confirmed local HEAD equals `origin/main`. This follow-up records the
observed CI/closeout facts in a separate documentation commit.

### CI Environment Block

All observations below came from authenticated GET requests after the push;
no workflow dispatch or rerun was requested.

| Workflow | Run | Observed result |
| --- | --- | --- |
| Acceptance Governance | `35275572903` | failure; governance job `105385262609` has 0 steps |
| Build APK and EXE Release | `35275572927` | path-detection job has 0 steps; APK/EXE/Pages/Release skipped |
| GitHub Push to WeChat Notification | `35275572962` | notification job has 0 steps |

All three stopped jobs have the same GitHub annotation:

> The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings

Therefore governance CI is **ENV_BLOCKED / NOT_RUN**, not a test failure and not
PASS. The generic annotation does not identify the precise account quota or
prove a specific unpaid bill. It does prove that deleting unrelated artifacts
or repeatedly rerunning this commit is not a justified recovery action.
Raw metadata/annotations are under `primary-ci/api/`; the compact result is
`primary-ci/ci.json` in the session directory. Independent review/acceptance
remains NOT_RUN; CI-ARTIFACT-02 stays in progress, separate from P3-4.

### Preservation And Write Audit

Only the nine scoped governance/tool/test/record paths were committed. The
shared board was staged from its original HEAD plus this session's rule, card
and journal only; other sessions' board entries remain uncommitted. The byte
audit confirms the original board after removing these owned additions and
all other 386 pre-existing dirty/untracked files are unchanged.

All actively selected output locations are inside the active project: session
evidence/runtime under `.cache/artifact-agent-20260918/`, fixture outputs under
the existing `.cache/artifact-maintenance-tests/`, `.cache/flutter-dev-checks-tests/`
and `.cache/flutter-dev-apk-tests/`, and Git objects/index/refs under `.git/`.
No PowerShell, device tools, build/package/install commands or release/deploy
operations were run. Existing user Git and GitHub CLI configuration bytes remain
unchanged. Credentials were used only in process memory, never committed or
written into the evidence. Existing untracked assets and worktrees were retained.
