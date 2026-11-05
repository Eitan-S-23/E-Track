# P51 Start-State Follow-Up Implementation

Reply ID: `P51_START_REVIEW_FIX_20261105_02`.
Local uncommitted test-only correction, pending root's independent scoped review.
Active worktree: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
HEAD remains `bea55d43bc255415945961ea1ab90c26e7b355b0`, branch
`dev/flutter/p51-timing-20261104`; index remains unchanged and empty.
E: `.cache/p51-start-state-followup-impl-20261105-01/`.

## P51-START-REVIEW-02

Implemented root's required isolation repair in `tests/ota/test_p51_package.py`.
The old adapter fixture inherited `INPUT_CANDIDATE_BASE_VERSION` and
`INPUT_CANDIDATE_FULL_BASE_VERSION` from the new-source regression job. Its real
supplement adapter therefore rejected runner drift before the intended key
binding rejection. The retained root-review-01/context-new-source stderr and
exit 1 are reused, not rerun or overwritten.

The fixture now explicitly owns both fields as empty strings. A private helper
reuses the existing real input admission and rejection checks. The added test
calls that helper under absent, empty, base-only 3.3.18, and base-plus-full
3.3.18/3.3.17 ambient fields, asserting environment restoration after every call.
`mock.patch.dict` retains other environment fields, including output controls;
it does not clear the process environment. Each helper reaches the exact
`key binding mismatch` oracle with the public fixture key, leaves
`package_supplement` uncalled and leaves `prepared` absent. Existing owner/flag
drift checks remain, and two added negatives prove actual nonempty supplement
base/full-base overrides still fail at `runner drift` before packaging.
No production guard, packaging function, workflow or installer was edited.

## Executed Verification

All commands use cmd.exe and explicit active-worktree cwd. Thin E/run.py reuses
the existing `host_io` output guard and `p51-package.py` owned native launcher;
it selects only the two affected tests, not the supplement class/full suite.
Each command below exited 0:

    python -I -S -B -X utf8 .cache\p51-start-state-followup-impl-20261105-01\run.py entry
    python -I -S -B -X utf8 .cache\p51-start-state-followup-impl-20261105-01\run.py absent
    python -I -S -B -X utf8 .cache\p51-start-state-followup-impl-20261105-01\run.py empty
    python -I -S -B -X utf8 .cache\p51-start-state-followup-impl-20261105-01\run.py base-only
    python -I -S -B -X utf8 .cache\p51-start-state-followup-impl-20261105-01\run.py base-plus-full
    git --no-optional-locks diff --check -- tests\ota\test_p51_package.py

Each context's command.json records exact Python executable/argv, cwd, ambient
fields, contained environment and 90-second bound. Selected test names:

- `StartStateSupplement.test_real_supplement_adapter_rejects_mixed_owner_and_key_before_packaging`
- `StartStateSupplement.test_real_supplement_adapter_isolated_from_ambient_base_versions`

| External context | Top-level result | Test time |
| --- | --- | --- |
| absent | 2/2, exit 0 | 8.521 s |
| empty | 2/2, exit 0 | 9.663 s |
| base-only | 2/2, exit 0 | 8.891 s |
| base-plus-full | 2/2, exit 0 | 8.652 s |

Two distinct tests executed four times, not eight new distinct tests. The new
regression additionally checks its four ambient subcases in every process.
Original stdout/stderr and WindowsJob receipts live in
E/CONTEXT/evidence/native/adapter-tests.{stdout.txt,stderr.txt,process.json}.
All four receipts report exit 0, no timeout/interruption/cleanup errors and
treeCleanupComplete=true; all active native markers are absent. Test diagnostic
warnings/errors: 0/0. Scoped diff check has one Git LF/CRLF advisory, not a
compiler warning. Entry Git inspection also emits line-ending advisories.
One read-only rg command initially used cmd-incompatible single quoting and
exited 2; the corrected content lookup succeeded. No regression run failed.
No Python bytecode, ETU, EXE or compiler output was generated in E.

## P51-START-REVIEW-01

Correction to the preserved old implementation handoff: the wrong-expected-image
native process exited **1**, not 2. This matches the original process.json and
`wrongExpectedImageNativeExit` in the old results.json. The byte-oracle rejection
remains valid; this batch does not rerun it or rewrite the old handoff/results.
Original receipt:
`.cache/p51-start-state-impl-20261105-01/python-01/fixtures/supplement-fixture-07v_kq1c/.cache/p51-candidate/evidence/native/wrong-expected-image.process.json`.
Receipt SHA-256: `aea6014173e754abea823fcaabf865dc4e93c1d6a1bb69d12af6a6bf30131574`.

## Identity And Boundary

Actual dirty-entry test SHA-256:
`ea9e5351307dc6f4c120335c704c858ff75c22d3375d17e5f98980bb40391c18`.
Final test SHA-256:
`9a9b8ea23c7f8ed1ec5e53de771102fd2ad36052b994d692daaa86528cf7e121`.
Thin runner SHA-256:
`e9f0379cbc9a529b5cbaff7ba76bee19622d508fb6cc77ba970829cbe15898e9`.
E/entry.json binds the actual pre-edit dirty files and retained review/receipt
anchors; E/closeout.json binds final identities, raw logs and process closure.

Only the affected test, this new handoff and E were chosen for writes. All were
normalized and checked against the unique authorized worktree and full parent
reparse chain before writes. Every test's TEMP/TMP/TMPDIR, HOME/USERPROFILE,
APPDATA/LOCALAPPDATA, XDG/npm caches and fixture root are under E. No PowerShell,
package manager, download, firmware/native build, credential use, network/service
mutation, commit/push, CI, device action or sub-agent was used. No output was
selected outside the active worktree, and no previous output was cleaned.
The closeout inventories ignored evidence/fixtures, checks output paths and
unchanged preserved input hashes; it is not just a Git-status audit.

No `.trellis` exists here. Existing task contracts and root's bounded remediation
packet were used rather than creating a new task/spec. Project-root published
contract differences were read only; neither governance copy was edited.
No file identity, package selection, OTA behavior or UI implementation changed.

## Next Owner

Implementation self-test oracles for REVIEW-02 are met; REVIEW-01 is corrected
only in this additive handoff. Root owns the independent review of this test-only
delta and four context results, then integration/candidate binding. The completed
317-test/native/package audit is reused unchanged. Full-suite rerun, ARM/native
build, protected supplemental CI/key packaging, installation and P5 physical
acceptance are NOT_RUN here and are not waived. This is not whole-task/P5 PASS.
