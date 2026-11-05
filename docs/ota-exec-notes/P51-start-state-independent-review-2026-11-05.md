# P51-START-STATE-01 Independent Review

Root independent review of the local implementation, not physical P5 acceptance.
Active worktree: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Entry HEAD: `bea55d43bc255415945961ea1ab90c26e7b355b0`.
The original implementation handoff and its dirty-entry/final identities remain
unchanged. Published project-root collaboration and acceptance contracts were
read before this continuation. No `.trellis` exists in this worktree; no new
Trellis task or competing specification was created.

## Reconciled Work

The earlier relay reached a separate session, not this root chat. Sanitized
daemon records show partial-return timeout at 06:03:11 and background-session
closure at 06:13:11 on 2026-11-05 (+08:00). It left
`.cache/p51-start-state-root-review-20261105-01/`, including two executed
context probes and an incomplete evaluator. Neither a final audit nor a PASS
existed when root resumed. Its successful supplement-context test and failed
new-source-context test are retained and reused, not rerun with unchanged input.

Root executed:

    python -I -S -B -X utf8 .cache\p51-start-state-root-review-20261105-02\review.py

Exit 0. This independently evaluates original evidence; it does not rerun the
317 host tests, rebuild native decoders, regenerate packages or operate a device.
`audit.json` SHA-256:
`05e263d6b6399866aca5d9490c49c51e86531d7378da411b762aefe8ca068866`.
Evaluator SHA-256:
`4fe99085800604c1afd6988f46c8df98cfd5ba6fb238752c05aa1d47349539a1`.

Verified: 1,841 retained original files, 54 unrelated dirty files, 2,129
implementation outputs and 67 closed process receipts. The two shared-file
deltas reproduce their actual dirty-entry identities when reversed in memory.
317 distinct original passing host tests and 8 original native checks were
checked against raw logs/exit codes; historical failures remain in the audit.
The original native compilations and successful checks have zero warnings/errors.
No new ARM/native compilation or corresponding warning count is claimed.

Both public-fixture FULL payloads were decrypted and independently decoded with
properties parsed from their actual headers, bounded length, EOS, no unused
bytes and byte-for-byte comparison against the pinned original archive. They
reconstruct the exact 615132-byte 30317/30318 images. These public-key fixtures
remain non-installable and do not prove the protected key/CI route.

Static review traced protected mode admission, exact checkout and version scope,
original archive/source/build/key lineage, actual workflow owner, private-key
binding/cleanup, explicit upload inventory and unchanged legacy/native defaults.
The App-only version gate executes before inspect/bind/execute; the retained
tests prove zero device calls for cross-version pairs and preserve the four
same-version paths. Actual device BCB/App agreement still requires fresh checking.

## Findings

| ID | Disposition | Evidence And Required Action |
| --- | --- | --- |
| P51-START-REVIEW-02 | Required test-isolation fix; HARNESS_FAIL until fixed | `test_p51_package.py` adapter test leaves the two base-version environment fields inherited. The real workflow exports them during regression. The retained new-source probe fails with runner drift before its intended key-mismatch oracle. Explicitly own empty supplement base/full-base fields; cover absent, empty, base-only and base-plus-full ambient contexts without weakening production admission. |
| P51-START-REVIEW-01 | Non-blocking evidence correction | The old handoff says wrong-expected-image exit 2; the original process receipt and results say exit 1. The byte-oracle rejection is valid. Add a new correction, preserving the old record. |

No additional product defect was found in this bounded review. This is not
permission to skip the required real protected supplemental CI or the fresh
device/start-state observations. The actual source/key/workflow identities and
both downloaded initialization packages must be independently checked after CI.

## Evaluator Failures Preserved

The prior evaluator's first failure concerned Node spec-reporter parsing, already
preserved in root-review-01/entry-failure.json. Root's next execution exited 1 at
known-size FORMAT_ALONE decoding. Both actual payloads pass RAW decoding and an
unknown-size ALONE diagnostic with exact original bytes/EOS/no trailing data;
known-size ALONE is rejected by this host. No original package was changed.
root-review-02/entry-failure.json preserves this second failure. The new thin
evaluator explicitly binds the unchanged old script and changes only its output
directory, the independent decoder selection and the recorded findings. Exact
size, EOS, full consumption, source hashes and native oracles remain mandatory.

## Remediation And Boundaries

Root sent one bounded task to the existing `codex-rawchat` relay target. The call
failed with model rate limiting. A subsequent status-only request explicitly
confirmed the task had been read but no work/process remained active. Only then
did root request execution of the pending task, without repeating any completed
work. The task file is root-review-02/remediation.txt; its scope is the affected
test, a new correction handoff and contained fresh evidence, not production code.
The root review files and old handoff are excluded from implementation edits.

Current disposition: independent offline evidence evaluation complete;
P51-START-REVIEW-02 remediation/verification pending. No full task/P5 PASS claimed.
Protected supplemental CI, real-key packaging, installation, J-Link/ADB, service
mutation, P5 execution and production action are NOT_RUN in this continuation.
No commit/push or new sub-agent was performed. All chosen outputs are checked
under the active worktree; original evidence and unrelated changes are preserved.

## Closeout

The execution request after reconciliation also returned the same upstream model
token-rate-limit error (exit 1). The status-only reply was explicit: task read,
implementation pending, no work/process in progress. At final inspection all ten
implementation files still matched the original handoff; no follow-up handoff or
follow-up evidence directory existed. The three ordered call results are saved
in root-review-02/relay-result.json. No agent model, binding or service setting
was changed. Do not infer task completion from transport receipt or repeat an
in-progress task without reconciling its actual state.

Final local-review disposition: HARNESS_FAIL, P51-START-REVIEW-02 still OPEN.
The independent evidence evaluation is complete, but the changed tooling is not
accepted for integration while its new-source regression is broken. No further
ordinary product defect was found. Protected supplemental CI remains NOT_RUN,
not waived; P5 physical acceptance remains NOT_RUN. The next owner is the bound
implementation agent once its execution service is available. Root then reviews
only the test-only delta and its four context results, preserving/reusing this
completed package/native/source audit. No new reference search, firmware build
or replay of the 317 tests is justified by these two corrections alone.

Root's final scoped diff check exited 0 with nine Git LF/CRLF advisories (not
compiler warnings). The two root evaluator failures and all earlier failed
probes/logs remain preserved. Root edited no product or implementation-test code.

## Follow-Up Review: Local PASS

The user supplied `P51_START_REVIEW_FIX_20261105_02` and the separate follow-up
handoff. Root did not contact an implementation agent. This append supersedes
the pending local disposition, not the historical failure or protected/physical
NOT_RUN boundaries above.

Root executed the independent original-evidence evaluator:

    python -I -S -B -X utf8 .cache\p51-start-state-followup-review-20261105-01\review.py

Exit 0, `LOCAL_INDEPENDENT_REVIEW_PASS`. Audit SHA-256:
`adbc87c5cf4bbce8b1598270cf7c5fb6a2ddafe5edd7fcf2ba84234f1a208a71`.
The actual test SHA-256 is
`9a9b8ea23c7f8ed1ec5e53de771102fd2ad36052b994d692daaa86528cf7e121`;
the additive handoff SHA-256 is
`e3f348a52371a3a48ca5d9e3508429ffb9dfe55343576bda4adbceb93b925541`.

P51-START-REVIEW-02 RESOLVED: the fixture explicitly owns both empty version
fields, retains output controls and restores the ambient environment. The four
original contexts (absent, empty, base-only, base-plus-full) each show 2/2 tests,
exit 0, no timeout/interruption/cleanup error and closed WindowsJob trees.
Exact key-mismatch and zero-package-call assertions remain; actual nonempty
supplement overrides still fail the unmodified production admission gate.
These are two distinct affected tests executed in four processes, including one
new regression, not eight distinct new tests. Root evaluated their actual raw
logs and command/environment records rather than executing them again.

P51-START-REVIEW-01 RESOLVED: the new handoff corrects exit 2 to actual exit 1.
The referenced original process receipt hash and exit code match. The old
handoff, results and failure originals are unchanged.

Root reversed only this test-only delta in memory and recovered the exact prior
dirty-file hash. Thirty preserved inputs and all nine other originally reviewed
code/config/test files are unchanged. The follow-up runner and 138 inventoried
output paths were checked; no ETU/EXE/bytecode or active native marker appears in
that evidence area. The prior 317-test/eight-native-check package audit is reused
unchanged; no reference search, firmware build or full-suite rerun was performed.
No remaining finding was identified within this bounded local change set.

Local implementation review is now complete and permits moving to the existing
root-owned integration/protected supplemental packaging stage. Actual protected
CI/key matching, downloaded-asset binding and live start-state establishment are
still required. This is not a formal candidate, whole-task or P5 hardware PASS.
This continuation performed no commit/push, CI, packaging, device operation,
relay contact or new sub-agent action. Root wrote only its project-local evaluator,
audit and appended review/task records; implementation code was not edited.
