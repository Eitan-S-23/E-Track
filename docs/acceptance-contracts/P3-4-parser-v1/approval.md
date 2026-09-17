# P3-4 Parser Acceptance Scope And Approval

This is the first formal parser-subdelivery contract, not a replacement for
the P3-4 AT/performance task. Earlier parser reviews were admission reviews,
not formal acceptance rounds; no failed formal round is being skipped.

The user delegated permissions needed for project-compliant P3-4 acceptance
in this thread on 2026-09-17, after local submission, contract freezing and
host execution were explicitly discussed. Codex is the non-implementation
reviewer and delegated approver of this bounded host-only scope. The parser
implementation owner remains Claude. User delegation is not reported as a
user review of an unseen performance gate.

## Scope

The deliverable is Tools/ota/p3-4-link-stats/link_stats.py, its supplied
selftests and fixtures, and the newly committed acceptance entry point.
The parser remediation bytes passed admission review before submission.

The four required criteria are supplied host-regression correctness,
mutation discrimination, independently specified parser controls and
reinterpretation of complete CI captures. The latter are immutable parser
fixtures. Their expected counts and percentiles are exact regression values,
not product-performance thresholds or proof of physical throughput.

All commands run on this Windows/Python host with no network requirement.
Each of the three phase commands may execute once in the first formal round.
Each child process has a 120-second timeout; a phase has a 300-second outer
deadline. No blind retries are allowed. Failures retain raw stdout/stderr;
changes after freezing require a new approved contract version and computed
rerun scope. Preparation and evidence-only validation do not consume or
invent product-observation quota.

## Dependencies

Use the three mandatory base input groups. The current approved Evidence
profile does not cover Tools/ota/, while Validation covers the parser,
selftest, fixture and acceptance entry point. Therefore these process/tool
criteria depend on Validation, not a fabricated narrow profile. Production
and Governance remain declared base groups but are not falsely presented as
measured product inputs. No profile, validator, schema or SLA is changed.

The fixture plan binds every copied input by SHA-256 and length. Original
sidecars are copied byte-for-byte; their informational input names/paths are
retained, and actual raw-log content SHA bindings remain unchanged. Actual
command arguments and source IDs are captured in the phase results. The
native selftest's four external capture locations are declared and checked
before/after execution; exact raw copies are included in this bundle.

The acceptance entry point's comparison/path checks have one positive and
seven negative self-checks. It does not edit the parser or its selftest and
does not substitute constant PASS values for observations. The executed
frozen matrix, not this approval note or the development report, determines
the parser-subdelivery verdict.

## Boundaries

Write scope is the active p3-4-link-stats worktree, plus the repository Git
metadata necessary for the explicitly authorized local submissions under
D:\github\my\E-Track\.git. The main worktree's source and board remain read-only.
TEMP/TMP/TMPDIR and generated evidence stay in the active worktree. Existing
global pre-commit quality checks are retained; explicit commit messages skip
AI message generation, and notification credentials are removed from the
commit environment. No push or remote operation is required for this scope.

Raw copied input whitespace is data: it must not be normalized to satisfy
source formatting checks. Authored source/JSON/Markdown is checked separately;
staged blob bytes must exactly match every retained source/evidence file.

## Parent Task Still Open

P3-4 still requires physical timing decomposition, optimization comparisons,
115200 baseline and supported AT candidates up to 921600, the unchanged
throughput/duration/retransmission gates, 30/30 success, four-hour soak,
10/10 reconnection recovery and independent confirmation of one production
parameter combination. No such requirement is removed or marked optional.

The existing research record reports no qualified 1,048,576-byte reference
ETU and no final device/asset/AT recovery/quota execution sheet. Those are
input/plan gaps, not a renewed request for general permission. This contract
does not authorize inventing a padded package, inheriting P3-3 hardware
quotas, starting an unbounded device campaign or publishing a production
configuration. Parent-task formal product acceptance remains NOT_RUN.

This approval permits proceeding with local input submission, Git-object
freezing, NOT_RUN-matrix preflight and the three bounded host commands.
It does not imply a parser PASS in advance or close the parent P3-4 card.
