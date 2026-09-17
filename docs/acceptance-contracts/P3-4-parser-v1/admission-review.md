# P3-4 PR3 Remediation Review (2026-09-17)

Result: bounded implementation-remediation review PASS. No new blocking
findings were found in the two fixes and their affected paths. P34-PR3-01
and P34-PR3-02 can be closed on the exact delivered bytes recorded below.

Formal acceptance remains NOT_RUN. This is not a frozen-contract execution,
not approval to commit/push, and not a P3-4 completion or performance claim.
It establishes that the known parser blockers have been repaired and the
batch may proceed to authorized submission and contract-approval preparation.

## Finding Closure

| Finding | Independent Observation | Disposition |
|---|---|---|
| P34-PR3-01 | Replayed all six original malformed numeric inputs from the unchanged previous review directory. Each now exits 1, emits exactly its expected fatal code, produces runs=0/ACK=0 and eligibleForThreshold=false. The base and legal retransmission controls still exit 0 and retain one run/eight ACK samples and qualification. | CLOSED for this delivered parser. |
| P34-PR3-02 | The original 65-character SHA ending in LF now exits 1 with GROUP_IDENTITY_INVALID and no threshold qualification. Legal uppercase SHA and maxRetries=0 remain accepted; nonhex and CRLF suffix controls remain rejected. | CLOSED for this delivered parser. |

PR3-01 code review confirms durable samples are validated individually in
link_stats.py:754, both first-send and retransmission require length at
link_stats.py:985, and both write paths use the negative-byte guard at
link_stats.py:726. Invalid durable data suppresses only the misleading
derived final-offset comparison; actual missing observations still have
their counter/final-offset checks. Invalid blocks remain excluded.

PR3-02 now uses full-string anchors for the hex domain at link_stats.py:440
and checks that domain at link_stats.py:602. It does not trim or relabel the
invalid package identity to obtain a passing result.

The new combined numeric CLI input emits exactly eight fatal findings at
lines 181/185/218/234/265/266/267/268. Their code set is exactly
SEGMENT_OFFSET_INVALID, SEGMENT_OFFSET_MISSING, SEGMENT_LENGTH_INVALID and
BYTE_COUNT_INVALID. The platform and GATT callers are both exercised. The
new bad-SHA CLI reports exactly one fatal finding, names packageSha256 and
its 65-character length, and leaves identity.declared=null. The new legal
SHA CLI retains the uppercase 64-character declaration and maxRetries=0,
has two runs, no fatal findings and threshold qualification.

These results remove the remaining PR3-related reservations on PR2-02 and
PR2-04. The previously verified PR2-01/03/05 repairs remain intact. The
known early-ACK and mutation-discrimination behavior also remains intact.

## Verified Evidence

Active root: D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats

Branch: dev/flutter/p3-4-link-stats. HEAD:
0441f7862eaa65d201b49814dbd556ec98e8515a. Tree:
ea6bd78250c17a0311b992f1527b192bc29af65f. These Git IDs identify the old
committed baseline, not the uncommitted delivered implementation.

| Delivered Input | Bytes | SHA-256 |
|---|---:|---|
| link_stats.py | 84728 | 0cf95913612c688c6414b2becddcacffebc5b5aa92641eb989a299737b6b82c7 |
| selftest.py | 164081 | fb1ec6f23644189a1ce17a512d47cd5d70bdbd20c261b767be7075637832b3dc |
| Remediation report | 79632 | 17bee23fc828aef7e91bf683eeb5a05e154da3c551eb4c50c606df92af889986 |
| SHA256SUMS-parser-remediation.txt | 4043 | 530267db86518f7362c8b6ea851df3f8d237d38aae838ba4f96694e3ffc156e5 |

- All 34 manifest entries and the manifest itself are present and match:
  35 delivery files. The two source hashes match the handoff.
- On Windows/Python 3.13.12, the delivered selftest command ran once and
  returned 0: PASS 124, FAIL 0, SKIP 0, stderr empty.
- All 18 archived CLI commands ran once, with exit sequence
  0/0/1/1/1/2/0/0/1/0/1/1/1/0/1/1/1/0 and exact archived output bytes.
  The original 15 command lines and output bytes also match the previous
  independent review's records. No golden output was regenerated.
- All 15 targeted inputs from the previous review now meet their original
  expectations, including all seven previously wrongly accepted cases.
  Old inputs were read directly; old runners were not executed or modified.
- All 64 mutation slots across 23 entries/22 distinct targets were separately
  instrumented. Every slot fails at a relevant AssertionError, with zero
  other exceptions. Ten distinct positive controls and restoration pass.
  The 61 expected-test entries and the new 11 failure sites were checked.
- The developer's individual counterexample probe was independently run once.
  Its output and the selftest output match their archive bodies exactly;
  each archive additionally contains the seven-byte EXIT=0 plus LF wrapper.
  Those wrappers are not output discrepancies or hidden test reruns.
- Actual Git clean/index/checkout filters were tested with a worktree-local
  index and object directory. All 39 delivery targets have text unset and
  exact worktree/blob/fresh-checkout bytes. An unpinned LF control becomes
  CRLF under the same filters, demonstrating a discriminating byte check.
- git diff --check passes. The claimed 3749 insertions/395 deletions match
  tracked implementation and attribute changes; the four pre-existing board
  lines are separate and were not edited by this review.

The four original captures were reinterpreted in the selftest run, not
recollected. Their clean pools remain:

| Capture | Runs | ACK Samples | Unique DATA Segments | P99 Us |
|---|---:|---:|---:|---:|
| ci-35034258547/ubuntu | 6 | 48 | 48 | 900 |
| ci-35034258547/windows | 6 | 48 | 48 | 1328 |
| ci-35094204310/ubuntu | 6 | 48 | 48 | 1184 |
| ci-35094204310/windows | 5 | 40 | 40 | 1020 |

All four have zero fatal findings in the documented default mode. The
Windows mixed block at lines 307-976 stays excluded with source, line and
reason records. Missing sidecar identity makes all four threshold-ineligible;
this does not establish a performance-gate failure.

## Limits And Formal Entry

The disclosed lack of a TOKEN_RE trailing-newline mutation is not a new
blocker: parse_log splits lines and parse_sample splits tokens before that
regex is used. Directly passing newline-containing strings to its permissive
value class would not establish an externally reachable lexical defect.
The HEX64_RE path is externally reachable and has both an original-input
reproduction and runtime mutation proof.

The lack of a dedicated loader mutation or new missing/noninteger-byte
mutation does not invalidate the executed CLI/negative checks. No new
per-function mutation quota is imposed. The review checks the bounded fixes
and known related failures, not every possible parser input or full protocol
semantics. Source-semantic fixtures and numeric-domain controls are not proof
that every constructed sequence was emitted by Dart or a physical device.

This host review does not establish Linux execution, device throughput,
30-run reliability, soak, AT behavior, J-Link operation or deployment safety.
No such action was authorized or performed. P3-4 remains in progress.

Before formal acceptance, the implementation and every participating runner
must be submitted under explicit authorization; dependencies, original
captures and fixtures must be declared in the approved versioned contract;
the contract must be frozen and its NOT_RUN-matrix worktree preflight must
pass. No P3-4 versioned contract file was found in this worktree's acceptance
contract directory. The old HEAD cannot certify the current dirty code.

The delivery now contains four ignored .log files, including the new
pr3-numeric-tamper.log. Authorized inclusion must preserve all four byte-bound
inputs. This review did not stage or commit them, remove ignore rules, modify
profiles, freeze a contract, or rewrite a board.

## Write Audit

Only this new review directory holds retained outputs. No implementation,
delivery file, prior review evidence, source fixture, emitter, provenance
document, real Git index, or board was modified. The final audit rechecks 389
protected files by bytes/SHA and both worktree status snapshots. The previous
review's 132 indexed files, evidence index and final audit were verified
unchanged before execution.

All controlled output paths and parent chains were checked before writes.
Commands used cmd.exe, Python -S -B, explicit project-root cwd and project-local
child TEMP/TMP/TMPDIR. Selftest's ten named temporary paths and the two nested
test-log paths were preflighted and leave no residue. No PowerShell, external
output directory, CI, build, device, AT, J-Link, flashing, install, OTA,
deployment, commit, push, merge or remote deletion was used.

Only this review's isolated Git objects, index and fresh-checkout copies are
removed after their hashes are captured in byte-audit.json. Original inputs,
raw command outputs and diagnostic records remain intact. Final audit and
evidence index record the retained files and precise scratch cleanup paths.

Evidence entry points: baseline.json, checks.json, previous-probes.json,
mutation-audit.json, byte-audit.json, interpretation.json, evidence-files.json
and final-audit.json. This directory is a review record, not a frozen formal
acceptance bundle.
