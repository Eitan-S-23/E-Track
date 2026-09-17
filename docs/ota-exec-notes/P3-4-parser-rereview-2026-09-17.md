# P3-4 Parser Remediation Rereview (2026-09-17)

Status: admission review NOT READY; five blocking findings below. Formal
acceptance remains NOT_RUN. Keep P3-4 in progress and preserve the existing
implementation owner. This is not a new formal acceptance round.

## Scope

This independent review examines the uncommitted P34-P01 through P34-P07
remediation in `dev/flutter/p3-4-link-stats`, based on commit
`0441f7862eaa65d201b49814dbd556ec98e8515a`. The commit identifies the old tree,
not the delivered modified Python files. No contract freeze or formal PASS is
claimed. Product code, prior captures, the delivery bundle, and the previous
review evidence remain read-only.

The only active write root is
`D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats`.
New diagnostic files and outputs are under
`.cache/p3-4-parser-rereview-20260917/`. No CI, hardware, commit, push, merge,
deployment, or external-directory writes are authorized by this review.

## Findings

Code locations below refer to the delivered worktree bytes, not the old HEAD.
They are follow-up observations in the same bounded parser scope. They do not
invalidate successful unrelated repairs or authorize new hardware/CI work.

| ID | Priority / Basis | Location / Impact | Required Disposition | Independent Evidence |
|---|---|---|---|---|
| P34-PR2-01 | P1; P01/P02/P04 qualification must preserve invalid/missing observations; execution contract section 7 | `link_stats.py:1411` through the assignment at `:1423`: qualification checks identity reasons only. It does not require an eligible sample population and does not consume capture-level fatal errors. | Make threshold eligibility depend on usable, attributable observations and the relevant complete validation result, not merely a supplied identity. Preserve exclusion and error records. Do not change the already-correct empty/null parsing errors to conceal the inconsistent flag. | A correctly hash-bound sidecar makes empty capture, null summary, and an UNKNOWN_KIND-fatal capture return `eligibleForThreshold=true` with runs=0/ACK=0, despite exit=1. An honestly declared `partial:missing=1` capture returns exit=0, runs=0, ACK=0, and eligibility=true. See four `qualified-*` cases in `probe-results.json`. |
| P34-PR2-02 | P1; P01 requires actual identity, not field-name presence | `link_stats.py:497`, `:338`, `:1208`: `str` accepts empty strings and `int0` accepts zero for identity parameters. Required package/commit/method/state declarations can all be empty while the identity is considered complete. | Validate meaningful identity values and distinguish unknown/empty identity from a declared usable group. Apply the documented identity domains without inventing new performance thresholds or claiming physical verification from synthetic metadata. | `empty-metadata-is-not-identity`: empty packageSha256/senderCommit/firmwareCommit/captureMethod/appState and zero baud/timeoutMs/maxRetries/packageBytes give exit=0, zero findings, runs=1/ACK=8 and eligibility=true. |
| P34-PR2-03 | P1; P01 input binding and independent-run accounting | `link_stats.py:1228`, `:1463`, `:1471`: sidecar entries are collapsed by digest, but repeated CLI inputs are parsed and counted repeatedly. Input sources are reduced to basename, losing multi-file attribution. | Reject or deduplicate repeat references to the same capture; additional copies are not evidence of independent runs. Preserve a unique input identifier tied to the source hash/path in group findings and exclusions. Do not rely only on a list-length check. | `repeated-input-is-not-two-runs`: the same path supplied twice with one bound input changes runs 1->2 and ACK 8->16, exit=0/eligibility=true. `edge-results.json` also shows distinct `a/tests.log` and `b/tests.log` producing indistinguishable excluded source=`tests.log`, firstLine=1, summaryLine=31 records. |
| P34-PR2-04 | P2; P03/P05 field completeness and valid clock/segment domains; OTA-XC-BLE-TUNING | `link_stats.py:247`, `:815`, `:1006`, `:1063`: elapsedUs is not required, its absence skips the positive-duration check; segment offsets/lengths and phase timestamps are checked only partially. | Make required-field completeness reflect the actual measurement contract. Validate successful timing independently of optional presentation fields, and validate per-kind numeric domains while preserving legal zero-duration operations, retransmission and resume shapes. | Removing elapsedUs while setting startUs=endAckUs and matching zero-length transfer phase returns exit=0, no findings, strictFieldsComplete=true and eligibility=true. Separate negative DATA offset, zero DATA length and negative bind-phase timestamps also return exit=0, no findings, and eligibility=true. See `probe-results.json` and `edge-results.json`. |
| P34-PR2-05 | P2; byte-bound evidence must survive checkout; evidence integrity gap | New bundle paths have unspecified text/eol attributes under core.autocrlf=true. The report's section 1.2/5 assumption that no new byte-identity asset was introduced does not cover the newly SHA-bound evidence. | Protect the new byte-bound assets before their authorized inclusion in Git, then verify their fresh-checkout bytes against the recorded hashes. `git add -f` addresses ignore rules only. Do not normalize or rewrite the original logs to conceal the mismatch. | Actual Git clean/smudge filters, with an isolated worktree-local object directory, change sidecar-ok.json 719->743 B, SHA256SUMS 2019->2041 B and the self-test archive 21317->21318 B. The existing -text fixture remains 41982 B with identical SHA. See `byte-audit.json`. |

The qualification flag is not a full performance PASS, but it still cannot
truthfully mean "usable for threshold comparison" for an empty or invalid
population. These findings do not demand device throughput measurements in this
Python batch.

## Verified Repairs

| Original Finding | Current Bounded Disposition |
|---|---|
| P34-P01 | Observable device/MTU/write-mode conflicts are separated, absent sidecar and wrong SHA are detected. Identity content, duplicate input, and qualification composition remain open under PR2-01/02/03. |
| P34-P02 | The original mixed Windows block no longer enters the clean pool. Partial, straggler and block-local fatal exclusions work. The new final eligibility flag still bypasses this result (PR2-01). |
| P34-P03 | Missing first-send off, duplicate ACK off, orphan retransmission and ACK-without-send cases now reach their intended checks. Numeric range/completeness holes remain under PR2-04. |
| P34-P04 | Empty/noise capture and null/non-object summary now return explicit fatal errors. The parser-layer repair is verified; sidecar qualification must not override those errors (PR2-01). |
| P34-P05 | Existing zero elapsedUs, wrong summary types, phase quantiles and GET_INFO totals are now checked. Omitted timing fields and unchecked numeric domains remain under PR2-04. |
| P34-P06 | The linked early-ACK replay shape is accepted without a false clock rollback; unrelated replay and actual rollback checks remain. This is source-semantic synthetic evidence, not Dart/device execution. |
| P34-P07 | All 38 current type-preserving mutation pairs fail at their relevant test assertions, with zero TypeError/IndexError or other runtime failures. Positive controls and restoration pass. The old three false proofs are resolved for this baseline. |

The static search for expected code text in the next 2000 source characters is
not itself runtime proof. This review independently recorded the actual failure
locations in `mutation-audit.json`; the current 38 pairs hit the intended checks.
The disclosed lack of dedicated P01/P04 mutation pairs is not, by itself, an
additional blocking finding. The newly reproduced qualification faults now
need targeted coverage.

## Verification

- Source hashes match the handoff exactly: parser
  `460bf54882806ae1f9d1700e82f98e95e7994e8b06351bf7e74076e5b7c43935`;
  selftest `e375dd9188dadcd3d224c952ed16beb82401d1d9eaf38621eacba8258569717d`.
- The remediation report hash is
  `f77f84c14584d3777008606191e0ed5a1ab7aae154a82656a5db099620c231c6`.
  All 17 manifest entries and the manifest itself (18 files) match their supplied
  sizes and SHA-256 values. None was modified by this review.
- The preceding review's 75 indexed files plus its index and final audit (77
  files) were verified by hashes, not timestamps, and remain unchanged.
- Windows/Python 3.13.12: the delivered command
  `python -X utf8 -S -B Tools/ota/p3-4-link-stats/selftest.py` ran once:
  exit=0, PASS=92, SKIP=0, FAIL=0, stderr empty.
- Raw self-test stdout is 21310 B, SHA-256
  `d128029b6e05cdacd94c28c594352e837877f22f390c9af6c86bfe536bf9c9a1`.
  The archived 21317-byte file equals these exact stdout bytes followed by
  `EXIT=0\n`. This explains the seven-byte difference; it is not a test-output
  discrepancy or a determinism failure.
- All 10 commands in cli-index.txt were independently executed once. Exit codes
  are 0/0/1/1/1/2/0/0/1/0, and all archived .out bytes match.
- The real Windows fifth-run clean pool is now 6 runs / 48 ACK samples / 48 unique
  segments; the original 9-instance mixed block is excluded. The other real-log
  replay results match the handoff. No new capture was performed.
- `probes.py` ran 16 new/control inputs: 6 controls behaved as expected; 10 cases
  exposed the listed gaps, runner exit=1. `edge_probes.py` added two focused
  reproductions (timing bypass/source ambiguity), runner exit=1. These are
  synthetic admission-review inputs, not additional formal rounds or devices.
- `mutation_audit.py` recorded 38/38 AssertionError results at relevant assertion
  sites, zero other exceptions, positive controls and restoration successful.
- `byte_audit.py` used actual Git clean/smudge filters, with GIT_OBJECT_DIRECTORY
  under this review's .cache directory. It did not edit the real index, object
  store, attributes, delivery files or HEAD.

One review-only setup correction is recorded in `preflight-note.txt`: the initial
manifest reader stopped on comment headers before any selftest/CLI execution.
It was corrected to skip comments while verifying every file entry. This is not
a product failure or an extra execution of the delivered tests.

## Byte Evidence

| File | Current SHA-256 | Checkout-Equivalent SHA-256 |
|---|---|---|
| sidecar-ok.json | `9a38bc5dd278f5467641155b767cf018908d3c2a73f49c3c336b48d94aa43c32` | `1b3e1f97443dfddbd90d477215ef5def231bb0df50ff961268aa0851298c921c` |
| SHA256SUMS-parser-remediation.txt | `610c7a07f14230e8d8154862960dc1b260eed97d70f16eb56359b25a02f7d5e4` | `542f64f8d5ee901d13d456de36d2b8fa3889fe17a7f79d5b364e9ba4623dfc29` |
| selftest-full-2026-09-17.log | `509001ae5c693d1f52bece98ee4ff91b3f80724557f1ffc9cc806ee1383d100d` | `29c1c45b43bd3826a924fa1b80aa35ec217326cb4138e448f2e9e7fc968ade91` |
| Existing -text fixture control | `d482f9ed386a064146992585fdf93ab2738f1b785c2bdc2e910e0d81c37bf645` | Identical |

## Next Batch

1. Fix PR2-01 through PR2-05 as one bounded batch, including callers and tests
   affected by the same causes. Keep verified P06/P07 behavior and raw evidence.
2. Extend the existing tests for qualification composition, semantic identity,
   duplicate/source input identity, missing timing fields and numeric domains.
   Do not encode the current wrong outputs as new golden expectations.
3. Preserve ignored .log assets when authorized to include the stable batch;
   review all byte-bound new files rather than only the three ignored logs.
4. No firmware/App build, CI rerun, device experiment, AT or new capture is
   needed to correct these Python/evidence issues. Do not restart historical
   campaigns or claim that the old seven findings all remain unfixed.
5. Formal acceptance still needs submitted implementation/runner inputs, an
   approved versioned contract and a NOT_RUN-matrix preflight. The current dirty
   tree cannot be frozen under the unchanged old HEAD. This does not prevent
   ordinary contained development tests or authorized implementation WIP work.

## Audit And Handoff

New outputs are this report, two append-only notes in this worktree's board,
and `.cache/p3-4-parser-rereview-20260917/`. The main worktree's board and
implementation report remain read-only; do not overwrite them with this
branch's older board snapshot. The main board currently has P3-4 in progress
and Claude as implementation owner; that remains the authoritative task state.

The worktree-local notes can be carried into the main board/report by an
authorized, serialized follow-up. Suggested handoff: parser remediation
rereview is not ready; PR2-01 through PR2-05 remain; 92 tests, 10 CLI outputs,
38 mutation pairs and all supplied hashes were verified; formal acceptance is
NOT_RUN and the implementation owner is unchanged.

Before test or Git-filter writes, controlled outputs and parent chains were
checked for worktree containment and reparse points. TEMP/TMP/TMPDIR were
redirected inside the new review directory. Selftest's seven known _tmp_ paths
were absent before execution and are absent afterward. No PowerShell, remote
operation, commit, push, merge, device access or outside-worktree write was used.

`baseline.json`, `probe-results.json`, `edge-results.json`, `mutation-audit.json`
and `byte-audit.json` bind commands, raw outputs and hashes. The final
`evidence-files.json`/`final-audit.json` record all local evidence, unchanged
reviewed inputs, unchanged delivery/prior evidence, and preserved pre-existing
board text/line endings. They are review records, not a frozen acceptance bundle.
