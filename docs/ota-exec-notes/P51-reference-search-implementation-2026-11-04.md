# P51-REFERENCE-SEARCH-01 Local Implementation Handoff

Implementation/self-test only, pending root's concentrated independent review.
Started 2026-11-04; closeout 2026-11-05 Asia/Shanghai. Local uncommitted changes;
no protected CI, formal candidate, service mutation or device operation.

## Scope And Design

Worktree: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Entry/final HEAD: `db049b6b2b9e0bc0ff0c534d52b686494b7d704c`.
Branch: `dev/flutter/p51-timing-20261104`, unchanged.
Root's failed run `41849745315/1` remains a reference-synthesis failure, not a
GCC/UI/device failure: 641 compiler/linker warnings, zero compiler errors,
256 completed measurements, package exit 1 without timeout, successful cleanup.
Its original artifact and all observations were not rewritten.

Root cause: salt=0 bisection provides a coarse location, not a monotonic fine
root. In the real measurements, count 210159 -> 210160 decreases total size by
122 bytes. The old scheduler spent its remaining budget on four fixed counts
without re-centering after salt changes. The existing 61-sample fixed-neighborhood
failure also remains; those points were not re-encoded.

New-source alone calls `search_adaptive`, strategy
`adaptive-count-salt-seed-v2`. It reuses the existing progressing `patch_stream`,
LZMA encoder, strict decoder and candidate/native process owners:

- Keep coarse salt=0 localization and its measured slope as a proposal only.
- For each salt, start from the closest observed count, measure, then correct
  count from the new error/slope. Permit proposals outside the original bracket.
  Avoid already visited triplets; an unchanged/repeated proposal uses a bounded
  nearest unvisited count. At most four measurements per salt prevents one noisy
  neighborhood monopolizing the budget.
- Reserve one quarter of the budget for `(initial_seed + 1) & 0xffffffff`.
  This changes the whole legal progressing stream, not just the final eight
  seeks. Re-center using that seed's own measurements. At budget 256, the first
  seed gets at most 192 total measurements and the second gets the remainder.
  This deterministic policy is not a known-image recipe or a lucky seed input.
- All unique `(count, seed, salt)` selections, including cache hits, count toward
  the unchanged 256 limit. Persist ordered samples, outcome and source hashes
  in `search-report.json`; selection records strategy, actual seed and count.
- New-source cache reads additionally check count/seed/salt/groups, decoded size,
  LZMA properties, size arithmetic and hash syntax. Existing base/target digest
  checks remain; selected compressed/raw hashes are re-encoded and verified.
- Typed exhaustion reports `stage=reference-search`,
  `reason=REFERENCE_SEARCH_BUDGET_EXHAUSTED`, measurements and budget. No exception
  value/traceback or protected input is printed. Separate reference-config,
  reference-verify and source-package-roundtrips stages clarify other failures.

Changed tracked files: `Tools/ota/p34-acceptance/encoding.py`,
`Tools/ota/p51-package.py`, `tests/ota/test_p51_package.py`, and this new handoff.
The test entry adds four scheduler/cache/diagnostic tests and an optional
identity-checked `P51_TEST_REFERENCE_CACHE` for reusing original measurements.
No new build system or general test framework.

Archived-original still uses its existing recipe and unchanged `search`.
`measurement` defaults to the old behavior; stricter checking is opt-in only at
the new-source caller. AST comparison confirms `search`, `patch_stream`, `encode`,
`strict_lzma`, `package_bytes` and `witness` are unchanged. Both input manifests,
workflow, admission/keyed helpers, production/rehearsal gates and UI/product
sources are unchanged. Metadata remains old v1 versus new-source v2, not a
reclassification of old images. Actual new recipes remain in uploaded evidence.

## Actual Encoding Results

Evidence root: `.cache/p51-reference-search-impl-20261104-01/` (E below).
All cases use the real encoder, no search/compression-result mock. Values are
self-test/diagnostic inputs, not reserved versions or installable firmware.

| Case | Inputs | Unique samples | Witness count/seed/salt |
| --- | --- | ---: | --- |
| Exact failed CI pair | 615132 bytes, 3.3.18 -> 3.3.19, timestamp 1793802751 | 137 | 210156 / 7 / 30 |
| Header/timestamp variation | Same raw GCC bytes, 3.3.20 -> 3.3.21, timestamp 1793802752 | 177 | 210130 / 7 / 40 |
| Independent synthetic image | 524288 bytes, seeded random/zero halves, 4.0.0 -> 5.99.99, timestamp 0xffffffff | 26 | 242362 / 7 / 2 |
| Existing synthetic source regression | 614100 bytes, modified archived body, 3.4.1 -> 3.4.2, timestamp 1790000000 | 229 | 208314 / 8 / 9 |

The fixed input digests are exactly:

- Base: `0c3362e302504c1890f9e5c4ba1f6d9b00e9396e6250d14507c027c2d50c776c`.
- Target: `46e576cd3b20b65ffafc420c44da3082ab060ecbf937b52fc16d7b74ca0884df`.

Fixed witness: decoded progressing stream 5,658,900 bytes; compressed stream
1,048,472 bytes; total ETU 1,048,576 bytes. Raw SHA-256
`251793868a1efd4abf16e9ec9b65eb65b270233d99f3c7f1d9f597b5f96efe3e`;
compressed SHA-256
`fe75637a23258850117a037e35cb252d4210f7a639ebc68ee5ca7d84e020046c`.
Public-01-test-key ETU SHA-256
`d760f46d45bb6782f6fb75fef358d42ae6cc7362ff34953273c6a2746de51c81`.
Fresh nonce regeneration will change ciphertext hashes, not this recipe's
raw/compressed identity. Native full/patch/recovery reconstruct the exact target;
LZMA EOS, full consumption and progressing patch byte equality are checked.
No padding, trailing junk, truncation or fake lengths.

`fixed-01` created 94 new measurements, reused 43 already observed measurements
and still charged all 137 to the policy. Its search/verification took 359.937 s.
The 317 preloaded originals were not free search budget: unselected cache rows
did not influence scheduling. `fixed-02` replayed those 137 charged selections,
re-encoded/strictly verified the witness and ran 11 actual native cases in
55.766 s (not a cold search benchmark).

Header case: 177 fresh encodings, search/verification 831.936 s, complete native
case 856.862 s. Independent synthetic case: 26 fresh encodings, 146.042 s search/
verification, 169.056 s complete native case. Concurrent Windows measurements
are not Linux CI timings.

The first count/salt-only proposal failed the existing synthetic regression at
256 samples. That is retained in `python-01`, exit 1, 17 tests with one error,
1222.710 s. Do not treat it as the final result. Reserving seed diversity repaired
that input: `python-02` selected 192 original first-seed observations and encoded
37 new second-seed observations, totaling 229, then ran actual native/metadata
checks. All 17 tests passed in 268.153 s. No input/header/version was changed to
obtain success. No recipe was inserted into production search.

`replay-01/fixtures/results.json` actually re-runs the final v2 scheduler for the
first three cases, charging every cached point and re-encoding/strictly verifying
the selected stream. Counts remain 137/177/26 and raw/compressed digests match
the completed native originals. Native checks are explicitly reused, not falsely
reported as executed again. The fourth case's native checks actually ran with v2.

## Commands And Coverage

Each command uses cmd.exe with the explicit worktree cwd. Prefix the table's
remaining argv with `python -B -X utf8 E/run.py RUN`. Each run retains exact argv,
cwd, elapsed time, exit/signal/timeout, process owner and raw stdout/stderr under
`RUN/command.json` and `RUN/evidence/native/`. No real secret in host tests.

| RUN | Remaining argv | Exit | Result |
| --- | --- | ---: | --- |
| node-01 | node --test tests/ota/test_firmware_candidate.mjs tests/ota/test_firmware_workflow.mjs tests/ota/test_firmware_build_profile.mjs | 0 | 167/167 |
| python-02 | --reference-cache E/python-01/fixtures/new-source-zbe3sveb/evidence/reference/logs python -I -S -B -X utf8 tests/ota/test_p51_package.py | 0 | 17/17 |
| reference-01 | python -I -S -B -X utf8 tests/ota/test_p51_reference.py | 0 | 8/8 |
| keyed-01 | node app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/vitest/vitest.mjs run --config .github/scripts/p41-host.config.mjs --testNamePattern=firmware.key.wiring --reporter=verbose | 0 | 17 passed, 139 unrelated skipped |
| unit-05 | python -I -S -B -X utf8 tests/ota/test_p51_package.py AdaptiveReferenceSearch | 0 | 4/4 final targeted rerun, not extra distinct tests |
| fixed-02 / header-01 / synthetic-01 | python -I -S -B -X utf8 E/regression.py fixed / header / synthetic, respectively | 0 | Exact witness and 11 native checks each |
| replay-01 | python -I -S -B -X utf8 E/replay.py | 0 | Final v2 strict encoding replay, native evidence reused |
| exhausted-02 | python -I -S -B -X utf8 E/failure.py | 1 expected | Real fixed-input two-sample budget exhaustion, precise safe diagnostic, no success assets/native invocation |
| audit-01 | python -I -S -B -X utf8 E/audit.py | 0 | Preservation, identity and boundary audit |

209 distinct selected host tests, plus the separately run native probe cases;
not independent acceptance. The successful Python suite includes 5 old patch,
11 new-source and 12 optional-full-start native checks. Additional fixed/header/
synthetic probes include 33 native checks. Existing wrong base, CRC, truncation,
LZMA tails, metadata/key/source drift, mixed/production gates, upload allowlist,
timeout descendant closure and private cleanup regressions remain exercised.
The pipeline-integration selector double remains explicitly labelled; the
fixed/search/generalization tests above do not use that double.

Native compilation uses existing -Wall/-Wextra/-Werror: zero warnings/errors.
Successful package/native runtime diagnostics: zero warnings/errors. Keyed tests
retain one SQLite ExperimentalWarning and one intentionally injected, redacted
compiler diagnostic. These are separate from real CI's 641 warnings. Scoped
`diff-01` passes with three Git LF/CRLF advisories, not compiler warnings.

Other retained failures: `unit-01` and `fixed-01` child operations succeeded but
the initial evidence wrapper failed afterwards on duplicate `argv` dict keys.
Their original child logs/process receipts remain; corrected runs use new
directories. Read-command quoting failures and wrapper diagnostics are recorded
in `entry-failures.json`. The interrupted tool session later lost process IDs;
completed on-disk process receipts, not a guessed status, resolved both runs.

Budget remains 256, including reuse. Existing source-package child timeout
660 seconds, package step 30 minutes and job 40 minutes are unchanged. Original
Linux CI's 256 measurements took 432.2472 s total (max 2.0493 s/sample); extrapolating
that observed maximum yields 524.6208 s, not a worst-case guarantee. Windows cold
cases and sum-of-cached measurements are explicitly not CI timing proof. The
existing deadlines still fail closed; no bound was widened. Final-strategy Linux
performance and the next exact commit/time pair remain NOT_RUN for root to check.
The search makes no universal existence or within-budget success guarantee.

## Identity And Boundary Audit

Initial -> final SHA-256:

- encoding.py: `43711e1e8344dd428d0dd9247f8cc1667c71c3a1893828b6d1b8926604e0ca7e`
  -> `4f25b6a1460aed3da8a70c39e60325c5912f8f5f1bba9662fe08ec9d58fdd9e7`.
- p51-package.py: `9d0115e8f0e17c359d104b5d1a6462a182b12e5f950a847e78b71662cac4db0b`
  -> `f509cedc937b032179c0a810856c01d24fe7fa93d39d47d0b2b284edb0a9d62e`.
- test_p51_package.py: `7b32177f23bcb7a93ad3e7ef963f96789e29c3a944bb4a9a653fe43ba68f05ee`
  -> `71e43f74319086678e7067ff38a9ed456ea852a5253b306200446ac467da27c5`.

Old manifest remains
`f07b239edcae98736cac220fa111e302560809ebc10ad9db8289bcdc256573c9`.
`initial.json`, `preservation.json`, `audit.json` and closing receipt bind remaining
identities, hashes, original evidence and Git state. Audit byte-preserves 55
unrelated work files and all 774 original delivery files, including failed CI,
the 61-point probe, archives and diagnostic binaries. No root task-note edit.

Preflight uses existing `host_io.checked_output`: normalized absolute target,
nearest existing parent and every reparse parent checked; reparse outputs are
rejected. Writes are the fresh E evidence tree, the three named source/test files,
this handoff, fresh existing workflow-test directories under
`.cache/firmware-workflow-tests`, and contained Vitest caches under Worker
`node_modules/.vite`/`.vite-temp`. TEMP/TMP/TMPDIR, npm cache, fixtures, native
outputs and logs are redirected inside the worktree. No installation/download,
PowerShell, external temporary path, credential discovery or protected key read.

The audit checked 360 evidence directories/3148 existing files and 110 completed
process receipts, all with confirmed tree closure. Its own live audit marker was
observed while the audit child ran; the closing receipt checks its subsequent
closure and absence of all actual active markers. Public fixture headers and
test decoders remain only in local fixtures, not an upload whitelist or protected
secret residue. Existing owner-bound private cleanup, native jobs and whitelist
code were not weakened. No original result was deleted or overwritten.

## Root Next Action

Concentrated independent review of the three implementation/test paths, this
handoff and original/replay evidence. Root alone integrates/commits the reviewed
scope, checks exact next execution source and its actual version/timestamp inputs,
then arranges the next protected artifact-only run if justified. Do not hardcode
the diagnostic witness or assume the next commit timestamp produces the same
recipe. Keep seed/budget inputs and source/config/Boot provenance truthful.

Check actual Linux timing, new reference report/selection, strict/native bytes,
metadata and successful cleanup before candidate binding. Preserve archived
30313/30316 assets and group16 Boot. No unrelated UI or historical P1/P3/P4/P2-5
rerun follows from this tooling repair. Root owns candidate/device/P5 decisions.

NOT_RUN: real protected CI with this change, ARM rebuild, exact next-commit
candidate construction/binding, cloud operations, installation, phone/SD work,
OTA, UI/device replay and formal P5/independent acceptance.
