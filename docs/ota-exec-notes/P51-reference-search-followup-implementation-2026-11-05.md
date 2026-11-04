# P51-REFERENCE-SEARCH-02 Local Implementation Handoff

Local uncommitted implementation/self-tests, pending root's independent review.
No protected CI, ARM build, candidate binding, service mutation or device work.
The earlier independent review and 137/177/26/229 results remain valid; neither
they nor the new b1422489-input failure are reclassified.

Worktree: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Entry/final HEAD: `b1422489a3cb5a56428f5e640513d195ca29e46f`.
Branch: `dev/flutter/p51-timing-20261104`, unchanged.
Evidence E: `.cache/p51-reference-search-followup-20261105-01/`.

## Strategy And Scope

The new fixed failure demonstrates that re-centering alone still leaves holes in
the nonmonotonic count neighborhood: salt=0 already has a -2-byte sample, while
the v2 scheduler changes salt instead of systematically exploring its neighbors.
A near miss is not a monotonic root or evidence that an exact stream is absent.

Final strategy: `isolated-frontier-count-salt-seed-v4`, new-source only.

- Preserve v2's main proposals, logical seed quotas and **separate main history**.
  Frontier measurements cannot change main anchors or its visited-point decisions.
- For measured points within eight bytes of the target, expand an error-ranked
  frontier over unvisited count offsets +1/-1/+2/-2 at the same seed/salt. Newly
  close neighbors participate in the next priority choice. This is adaptive
  coverage across multiple measured anchors, not one enlarged fixed neighborhood.
- Frontier capacity is ceil(budget/10), 26 at budget 256. Main/frontier share one
  physical `(count, seed, salt)` cache and budget. Cache selections are charged;
  a frontier point later used by main is not charged twice. Main and frontier
  statistics can overlap and must not be added to infer total unique encodings.
- Persist `mainSamples`, `mainMeasurements`, frontier usage and selected
  `foundBy` alongside the ordered global samples. Diagnostics retain the precise
  reference-search stage and REFERENCE_SEARCH_BUDGET_EXHAUSTED reason.

The four previous cases need at most 229 main measurements. An isolated frontier
adds at most 26 unique measurements, retaining an executable route within 255
for these cases. This is a bounded regression argument, not a guarantee for every
possible image or the next commit timestamp.

Only `Tools/ota/p34-acceptance/encoding.py::search_adaptive`,
`tests/ota/test_p51_package.py` and this new handoff changed. Two new tests cover
frontier coverage and main-history isolation; the existing budget test now checks
the 26-point frontier bound. No encoder, patch stream, protocol, key/profile,
manifest, workflow, production gate, UI, Boot/BCB, filesystem or version change.
`p51-package.py` itself is unchanged. Nine other encoder functions, including
archived `search`, `measurement`, `encode`, `patch_stream` and strict LZMA,
are AST-identical to HEAD.

Rejected proposals are retained, not promoted: eight terminal-seek variations,
eight final diff/extra partitions and seven fresh/one cached count neighbors all
missed an exact result. Their strict byte reconstructions are diagnostic evidence,
not a successful repair. They did not change product encoding functions.

A first frontier proposal (v3, 32-point capacity with shared main history) passed
the new fixed pair and three declared variants, but exhausted 256 on the retained
177-point case. `old-header-01` preserves that failure. `v3-encoding.py` preserves
the exact rejected source. The final v4 isolates the histories and reduces only
internal allocation, without increasing total budget/deadlines.

## Executed Evidence

The fixed b1422489 pair is unchanged, each 615132 bytes, timestamp 1793813128:

- Base 3.3.18: `69f83b830e10b7d4247714183c48747f9599b6b27f6dd08e14482c9b9b66d03c`.
- Target 3.3.19: `83f5cc00ae8f279f18f92a4e298b0f62535fb6c7c3d56ad027857401dbd06c2a`.

Final exact witness: count 210031 / seed 7 / salt 7, **62 unique measurements**,
46 main selections and 17 frontier selections with one overlap; found by frontier.
Decoded bytes 5,655,900; compressed bytes 1,048,472; ETU total **1,048,576**.
Raw SHA-256 `decb2cfddcd853c0f7c3df54b0d24c4cdeba47d1b7104db38bf9d57f78d33a56`;
compressed SHA-256 `e4a181de961ee3e0ac9f8b9b9785aa971beabdb4a64154cdfe6f76eb30bed835`.
Cold public-01-key ETU SHA-256
`1a9a83a5102866d8dff4a96dd8a28f38e9b74f19e52dbea21b129365bf61094f`.
Ciphertext changes with fresh nonces. These are diagnostic/self-test artifacts,
not newly ARM-built or installable/registered candidates.

`plan.json` declared the three additional cases before **any** case execution:
same 3.3.18 -> 3.3.19 at timestamp +1 and +3600; 3.3.20 -> 3.3.21 at the unchanged
b1422489 timestamp. No failed variant was removed or replaced.

| Final run/case | Unique | Reused / fresh | Search + strict verification seconds | New native checks |
| --- | ---: | ---: | ---: | ---: |
| next-fixed-02, fixed pair | 62 | 62 / 0 | 10.248 | 11 |
| next-cold-01, same fixed pair | 62 | 0 / 62 | 313.479 | 11 |
| timestamp-one-02, 1793813129 | 126 | 47 / 79 | 403.521 | 11 |
| timestamp-hour-02, 1793816728 | 69 | 66 / 3 | 27.627 | 11 |
| version-02, 3.3.20 -> 3.3.21 | 159 | 49 / 110 | 518.757 | 11 |
| old-fixed-02, previous 137 case | 157 | 157 / 0 | 12.087 | 11 |
| old-header-02, previous 177 case | 197 | 197 / 0 | 11.201 | 11 |
| old-synthetic-02, previous 26 case | 38 | 38 / 0 | 13.293 | 11 |
| python-02, previous 229 source case | 249 | Cached actual originals and earlier measurements | See command/test logs | 11 in suite |

Every search uses actual cached measurements or the unchanged real encoder,
not a search/compression double. Fixed cold search newly encodes all 62 points;
it is not a replay of the old failed 256-point strategy. Total fixed cold
execution including native checks is 338.129 seconds. `*-02` variants are hybrid
executions, not cold benchmarks. Their initial `*-01` v3 executions were cold:
132/72/51 samples, respectively. All initial and final results remain.
Historical `encodingSeconds` sums in hybrid receipts are not current wall time.

All successful cases check exact size, strict LZMA EOS/full consumption and target
byte identity, without padding, trailing garbage or nonprogressing controls.
Real native full/patch/recovery and CRC/truncation/wrong-base checks use only the
existing public 01 fixture key, unchanged decoder sources and owned launcher.
Native compilation uses -Wall/-Wextra/-Werror: zero warnings/errors. Successful
runtime diagnostics contain zero warnings/errors; negative error codes are
expected rejection observations, not suppressed failures.

`verify-01` compares actual final main traces to the retained v2 originals:
exact prefixes of 46/137/177/25/229 main points for new fixed/old fixed/header/
synthetic/source cases. Every count, seed, salt, total length and raw/compressed
hash agrees. `main-prefixes.json` binds both current and original report hashes.
It does not mock measurements or skip a missing cache entry.

### Commands And Failures

Every run uses cmd.exe and the explicit active worktree cwd. Normal prefix:
`python -B -X utf8 E/run.py RUN`. Audit uses isolated parent Python too.
`RUN/command.json` and `RUN/evidence/native/RUN.{stdout.txt,stderr.txt,process.json}`
retain exact argv, exit, duration and tree closure. Matrix commands are
`python -I -S -B -X utf8 E/matrix.py CASE`, with explicit `--cache PATH` or
`--cold` recorded in argv, not inferred from execution time.

- `python-02`: `--reference-cache E/python-01/fixtures/new-source-8ycx8542/evidence/reference/logs python -I -S -B -X utf8 tests/ota/test_p51_package.py`, exit 0, **19/19**, 113.332 test seconds, 114.232 outer seconds.
- `unit-04`: `python -I -S -B -X utf8 tests/ota/test_p51_package.py AdaptiveReferenceSearch`, exit 0, **6/6**, subset of the 19, not extra distinct tests.
- `verify-01`: `python -I -S -B -X utf8 E/verify.py`, exit 0, five real main-prefix checks.
- `exhausted-02`: `python -I -S -B -X utf8 E/negative.py`, exit **1 expected**. Two original real fixed-input measurements are charged, no selected stream/success assets/native call, precise reference-search/budget diagnostic.
- `diff-02`: scoped `git --no-optional-locks diff --check`, exit 0, two LF/CRLF advisories, not compiler warnings.
- `audit-01`: `python -I -S -B -X utf8 E/audit.py`, exit 0; closing receipt adds the handoff and subsequent absence of its own live marker.

`python-01` remains an 18-test failure with one timeout-fixture error: PID stdout
was empty before the existing one-second timeout. Tree closure was confirmed;
child readiness was not observed. Contention is a hypothesis, not a proved cause.
The same parameters passed alone in `timeout-01` and in the final serialized
19-test suite. No timeout/assertion was enlarged or relaxed. Full raw failure
and v3 search results are retained. A JS duplicate-declaration entry failure
executed no nested tool or filesystem operation. `entry-failures.json` indexes
these observations and the rejected probes.

Previously reviewed Node 167, keyed 17 and reference-input 8 checks are reused,
not freshly rerun or added to this batch's 19-test count. Their source paths and
dependencies are unchanged. Existing metadata drift, wrong key/base/source,
archived-original packaging, optional full start, exact reference, private cleanup
and descendant timeout checks actually run in the Python suite. Compiler doubles
and integration selector doubles remain explicitly labelled, not real CI evidence.

## Identity And Boundary

Initial -> final SHA-256:

- encoding.py: `4f25b6a1460aed3da8a70c39e60325c5912f8f5f1bba9662fe08ec9d58fdd9e7`
  -> `b907500d5b2a6bb35c0f7d7678735ccd41e5742d760944b359e254a37a77063f`.
- test_p51_package.py: `71e43f74319086678e7067ff38a9ed456ea852a5253b306200446ac467da27c5`
  -> `e7949d94aedc8f3de9bf1db5961d406344c473584ca884f15673dfa186df7a9f`.
- p51-package.py unchanged: `f509cedc937b032179c0a810856c01d24fe7fa93d39d47d0b2b284edb0a9d62e`.
- Old manifest unchanged: `f07b239edcae98736cac220fa111e302560809ebc10ad9db8289bcdc256573c9`.

`baseline.json`, `audit.json` and closing receipt bind all other identities and
preservation checks. All **5225 original delivery/implementation/root-review
files** and **55 unrelated work files** remain byte-identical. Nine nonadaptive
encoder functions are unchanged. Root's task records, old 30313/30316 assets,
earlier successes/failures and frozen evidence were not modified.

All controlled writes are E, the two named code/test files and this new handoff.
Existing `host_io.checked_output` preflights normalized absolute paths, nearest
existing parents and every reparse parent; reparse outputs are rejected. TEMP/
TMP/TMPDIR, fixtures, compiler outputs, npm cache and raw logs remain worktree-local.
No PowerShell, installation, download, external temp path, protected-key retrieval
or extraction, cloud mutation or device service. Publishing credential prefixes
are stripped from host children; the only matching inherited name observed was
the noncredential GH_PAGER. NODE_COMPILE_CACHE was unset. Test headers/decoders
remain public-fixture artifacts only, never an upload whitelist.

Audit checked 421 directories, 5168 then-existing files and 268 completed process
receipts, all closed. Its own running marker is explicitly identified, not a
claimed residual process. The final receipt confirms its later closure and no
active markers. No older result was cleaned up, overwritten or deleted.

## Root Handoff

Budget remains 256 unique encodings. Existing source-package timeout 660 seconds,
package step 30 minutes and job 40 minutes are unchanged. Fixed **Windows** cold
cost is observed, not a Linux timing guarantee or permission to widen deadlines.
Generalization hybrids and cached elapsed sums are not cold performance evidence.

Root should independently review these two implementation/test files, the handoff,
the cold witness, all three predeclared variants, v3 failure and v4 main-prefix
proofs. Then integrate only the reviewed scope and separately check the next
execution commit's actual timestamp/input identities before arranging CI. Do not
hardcode this witness or infer that the next commit automatically works. Keep the
existing group16 Boot, protected secret path, artifact-only gates and exact asset
binding checks. No unrelated UI or historical device campaign is reopened.

NOT_RUN: new protected CI/Linux cold benchmark, ARM production build, exact next
commit prediction, candidate/service binding, installation, phone/SD/OTA work,
P5 or independent acceptance. This is only a local uncommitted implementation.
