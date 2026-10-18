# P4-3 Formal Acceptance

Result: PASS, round `P43-20261018-01`, seven required criteria.
Independent owner: the user-assigned Codex root acceptance session.
The implementation owner and the sole Spec are unchanged.

- Implementation: `0067b6c3caa9ee263c53ae372fdc63cc7f74250f`.
- Frozen input commit: `1ddd948bbf7d0dc2097c14d87def767314342f8f`.
- Frozen tree: `855c15853c572b83d9684235dbf69a247d4968b2`.
- Contract: `../P4-3-v1.contract.json`; the identical copy is `contract.json`.
- Contract SHA-256: `5517F3D4778C702B251985C38DF81BC904569BE53F8764BC3E7B9ECF65C10858`.
- Matrix: `evidence-matrix.json`.
- Authority and full review: `../../ota-exec-notes/P4-3-acceptance-2026-10-18.md`.

Four frozen offline commands independently evaluated the existing original data
and the current source. They did not redeploy, modify cloud state, issue a new
recovery capability or repeat a successful live exercise. Historical operations
are hash-bound external inputs, not invented formal REUSED origins. This is the
first formal P4-3 round; the earlier failed pre-review and its successful
remediation review remain intact.

| Criterion | Evidence |
| --- | --- |
| P43-API | Source-bound Worker 270/270, compiled routing 3/3 and exact CI/serving identities |
| P43-CHANNEL | Both channel revision/audit chains, real repaired CAS conflicts and cancellation |
| P43-PUBLIC | No downgrade for upgraded clients; independent stop flags and exact original URL/binary checks |
| P43-RELEASE | Disable/reference protection, recovery expiry, replay and one-effect audit with source-bound negative tests |
| P43-UI | Original bilingual screenshots, source-bound browser 36/36 and independent current-source probe 6/6 |
| P43-RETENTION | All six asset rows and release identity preserved, with the original pre-disable dependency check |
| P43-GOVERNANCE | CI 39110429390 at the frozen input commit: three successful jobs, eight governance suites |

The live and remediation archives contain 585 and 158 byte-verified entries.
The live evaluator also read 186 exact private originals, checked 55 D1 responses,
53 projections, 54 HTTP exchanges, 18 public bodies and 21 screenshots, and
reconciled 24 channel changes, three recovery issuances and one disable.
The earliest 933b790 source differs from 972e74c only in the reviewed session-GET
cookie preservation and its tests; 0067b6c changes only the two reviewed UI
functions and their browser tests. The compiled server executable is unchanged.

## Preserved Failures

`preparation/dev-ci-01.*` records the pre-freeze adapter failure: seekless ZIP
stdin lists 569 instead of 585 entries on this Windows tar. Seekable file input
passes; no archive or original cloud observation was replaced.

`evidence/formal-precheck.*` and `preparation/precheck-initial-matrix.json`
preserve the first precheck rejection. The helper emits/expects a lowercase
matrix contract hash, whereas the existing validator requires uppercase for that
field. Only this mutable matrix field is normalized at the packaging boundary:
lowercase for the unchanged finalizer, uppercase for precheck/final validation.
The digest value and frozen contract bytes never change. No frozen runner was
edited, no acceptance gate was weakened and no product observation was repeated.
`formal-precheck-02` passed with overall NOT_RUN before all four executions;
`formal-validate` passed with overall PASS after them.

## Limits

The last real deployment remains 972e74c. The repaired UI is source/CI verified,
not claimed deployed. Real publisher/viewer sessions are still missing; this
does not certify the full deployed role matrix or P4-4/production configuration.
Inherited dependency advisories, original Windows timeout history, native warning
lines and the unresolved external-cache attribution remain disclosed in the
review report. This task result grants no production/P5/device readiness.

`inputs/private-originals.json` is a size/hash retrieval registry, not the private
bytes or credentials. Those originals remain in the authorized task worktree;
re-executing the semantic evaluator on another host requires their controlled
retrieval. A missing or changed original fails closed. The committed package
retains the public projections, raw sanitized archives, original CI logs and
independent verification outputs; it deliberately publishes no session secrets.

For immutable package validation, use the registered bundle commit from
`../FREEZE-INDEX.md`, not a later unrelated source state:

    python -I -S -B -X utf8 Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P4-3-v1.contract.json --matrix docs/acceptance-contracts/P4-3-v1/evidence-matrix.json --repo-root .

Do not run the preparation/freeze/finalize modes against an already-final package
or rerun its product commands to refresh timestamps. The published contract,
matrix and original evidence are immutable; new inputs require the normal
successor-contract and minimum-rerun assessment.
