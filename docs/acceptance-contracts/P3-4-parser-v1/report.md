# P3-4 Parser Independent Acceptance

Date: 2026-09-17. Reviewer: Codex, non-implementation acceptance session.
Round: `20260917-P3-4-parser-r1`. Contract: `P3-4-parser-v1`.

## Verdict And Scope

**PASS for the parser subdelivery.** All four required criteria are fresh
`EXECUTED PASS` observations after contract freezing and NOT_RUN-matrix
preflight. The final project validator exits 0 with `overall=PASS`.
No development or admission-review result is relabeled as formal execution.

Known parser findings P34-P01 through P34-P07, P34-PR2-01 through PR2-05,
and P34-PR3-01/02 are closed for this frozen parser. The previous admission
reviews and their failures are retained; they were not earlier formal rounds.
No new parser blocker was found in the approved bounded checks.

**The parent P3-4 AT/performance task remains in progress, owned by Claude.**
This tool-level PASS does not accept Flutter measurement wiring, establish
physical throughput, select production parameters or close P3-4.

The user explicitly delegated project-compliant P3-4 acceptance permissions.
The non-implementation reviewer approved this bounded host-only contract at
`2026-09-17T13:34:03+00:00`; see `approval.md`. This records delegated approval,
not a claim that the user personally reviewed unseen gates.

## Frozen Identities

- Implementation submission: `b7cab91cc9814a706fc2e3aff7bcffcd35ff0770`.
- Freeze commit: `f90f603d4d8c56be4bae6dc01553610ff7a07712`.
- Freeze tree: `6d5c93361c9c1cbb302759a34b925481211e81b2`.
- Profile config blob: `3769369d053aad028b67d7e2c17b5827b2b96f55`.
- Contract SHA-256: `e4cda8f591c7df15ff0f4996095ba875a41a06713b8e514b5615dc43cd0b9971`.
- Final matrix SHA-256: `12ef4a1d3851b94729f1d0bd2180b243b8e92927bd0ce12da62a91fe9d009bb7`.
- `link_stats.py` SHA-256: `0cf95913612c688c6414b2becddcacffebc5b5aa92641eb989a299737b6b82c7`.
- `selftest.py` SHA-256: `fb1ec6f23644189a1ce17a512d47cd5d70bdbd20c261b767be7075637832b3dc`.

The three mandatory base profiles are retained unchanged. Criteria consume
Validation because the approved Evidence component does not cover Tools/ota.
The contract binds the immutable input plan, Windows/Python host identity and
four entire capture files; the plan additionally binds 68 raw input files.
The evidence bundle commit is registered by a later FREEZE-INDEX commit,
avoiding a self-referential bundle identity.

## Executed Evidence

Host: Windows, Python 3.13.12, Git 2.53.0.windows.1. Commands used
`python -X utf8 -S -B` from the active worktree root, with assertions enabled
and contained temporary directories. Exact commands, timestamps, exit codes,
stdout/stderr hashes and child argv are retained in `commands/` and `results/`.

| Required Criterion | Actual Observation | Result |
|---|---|---|
| PARSER-SELFTEST | 124/124 cases; no FAIL or SKIP; stderr empty; original captures unchanged; no temporary residue | EXECUTED PASS |
| PARSER-DISCRIMINATION | 64 mutation slots; each intended AssertionError detected and restoration passes; no incidental runtime-exception successes | EXECUTED PASS |
| PARSER-CONTROLS | 33 independent controls; exact exits, fatal-code sets, eligibility/counts and applicable source/duplicate bindings | EXECUTED PASS |
| PARSER-CAPTURES | Four complete immutable CI captures reinterpreted with the frozen parser; all expected fields match | EXECUTED PASS |

All three phase commands ran exactly once and exited 0. Selftest and
discrimination share the same execution. Quota used: 1/1 per phase;
remaining: 0 per phase. No blind retry, recovery, previous formal matrix,
REUSED criterion or rerun plan was needed. Each child timeout was 120 seconds;
each phase had a 300-second outer limit. No timeout occurred.

The supplied suite retains 23 discrimination entries, 22 distinct mutation
targets, 61 expected-test entries and 10 positive controls. The frozen
acceptance comparator also passed one positive and seven negative checks
before submission; its raw preparation outputs are retained in `preflight/`.

| Full Capture | Clean Runs | ACK Samples | Unique DATA Segments | P99 Us | Strict Fields Complete | Threshold Eligible |
|---|---:|---:|---:|---:|---|---|
| ci-35034258547/ubuntu | 6 | 48 | 48 | 900 | false | false |
| ci-35034258547/windows | 6 | 48 | 48 | 1328 | false | false |
| ci-35094204310/ubuntu | 6 | 48 | 48 | 1184 | true | false |
| ci-35094204310/windows | 5 | 40 | 40 | 1020 | true | false |

All four captures have zero fatal parser findings. Excluded blocks remain
visible with source, lines and reasons in the raw JSON. In particular, the
polluted ci-35034258547/windows block at lines 307-976 is not admitted into
the clean numeric pool. Missing sidecar identity makes all four captures
ineligible for threshold use; this is not a failed physical-performance test.
These P99 values are exact parser-regression expectations, not product SLAs.

## Residual Scope

The main() input-loading layer has CLI controls rather than mutation pairs.
The emitter-shaped early-ACK cases are synthetic, not Dart device execution.
The token regex newline shape is not an externally reachable line-parsing
case. These declared coverage limits are not silently promoted to hardware
or exhaustive-parser guarantees.

The parent task still requires the following, all NOT_RUN in this acceptance:

| Parent Requirement | Current Gap |
|---|---|
| Physical timing decomposition and same-asset optimization comparisons | No accepted device measurement series in this parser bundle |
| 115200 baseline and supported AT candidates through 921600 | Device/module identity, recovery actions and bounded operation sheet are not finalized |
| Legal complete 1,048,576-byte ETU | Research section 6 reports no qualified reference package; padding a toy is not an acceptable substitute |
| P95 <= 120 s, each run <= 150 s, throughput >= 9 KiB/s, clean DATA retransmissions <= 1% | Unchanged OTA-XC-BLE-TUNING gates; no threshold-qualified physical input here |
| Same-parameter 30/30 success, four-hour soak without unrecoverable errors, 10/10 recovery | No physical campaign executed or quotas inherited from P3-3 |
| Independent production baud/timeout/retry recommendation | Requires the above evidence; no production parameter is selected |
| Flutter wiring CI evidence completion | Latest main-board record still has artifact-upload and test-count evidence gaps; this parser-only round does not resolve them |

These are material, execution-plan and evidence gaps, not a renewed claim
that general acceptance authorization is missing. The historical research
and main-board authorization wording is not rewritten by this local report.
No firmware, Flutter, AT, device, build, CI, installation, OTA, remote deletion,
push, merge, release or deployment command ran during this formal host round.

## Preservation And Recheck

Before closeout, 541 protected files and all four existing review-directory
inventories were verified unchanged. This includes parser/selftest bytes,
development evidence, original captures, the main board and the main Git index.
See `audit/unchanged-inputs.json`; it checks bytes and inventories, not just
git status. Old review runners were not rerun or their evidence overwritten.

Writes are confined to the active worktree plus the explicitly authorized
Git metadata needed for local submissions. No PowerShell host was launched.
The worktree board is an older snapshot: only append acceptance information;
never overwrite the newer main board or its implementation owner.

To recheck the registered bundle, use its bundle_commit checkout and run:

    python -X utf8 -S -B Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-4-parser-v1.contract.json --matrix docs/acceptance-contracts/P3-4-parser-v1/evidence-matrix.json --repo-root .

Expected: `VALIDATION=PASS ... overall=PASS`. This is an evidence-only recheck,
not permission to rerun the three consumed phase commands. The frozen
NOT_RUN matrix and preflight output are retained separately, and
`SHA256SUMS.txt` binds the compact bundle including final validation outputs.
