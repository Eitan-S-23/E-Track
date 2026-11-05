# P51-START-STATE-01 Local Implementation Handoff

Local uncommitted implementation/self-tests, pending root independent review.
No commit, push, protected CI, protected-key access, service change, ARM build,
device/phone/SD operation or physical acceptance. No sub-agent was started.

Active worktree: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Entry/final HEAD: `bea55d43bc255415945961ea1ab90c26e7b355b0`.
Branch remains `dev/flutter/p51-timing-20261104`.
Evidence E: `.cache/p51-start-state-impl-20261105-01/`.

## Cause And Bounded Repair

Root's actual archived group16/native backup probe is reused, not physically
re-executed: CONFIRMED Boot validates/jumps without synchronizing cur_vcode after
App-only programming; backup admission requires BCB/App version agreement.
App-only 30313 -> 30317/30318 therefore cannot establish the required start.
Ordinary health/CONFIRMED bytes do not establish that agreement. The last retained
App/BCB is 30313; this batch did not observe the current board state.

The existing candidate route lacked FULL envelopes for the two finalized starts.
An explicit `start-state-supplement` mode now consumes the pinned original archive
and emits only `initialize-30317-full.etu`, `initialize-30318-full.etu` and its
separate `supplement-metadata.json`. It does not compile, refinalize an image,
change the timestamp, search a reference, regenerate 30319 packages or register
anything. Archived-original and new-source remain explicit, unchanged modes.

Reused mechanisms: `envelope`, `lzma_alone_encode`, strict LZMA/full consumption,
FULL limits/header parsing, the existing real FULL/native decoder, key binding,
build-profile verification, WindowsJob/POSIX ownership, 90-second native commands,
660-second adapter deadline, 30-minute package step, 40-minute job, output guards,
redaction and owner-bound private cleanup. None of those limits was increased.
`native_verify` adds an optional FULL-only selector/prefix; its default legacy
and new-source cases retain their old behavior. The archived resolver is used
read-only to supply the native host's older 30313 base, never to infer live state.

`MCU.install` now compares the pinned current/destination App header versions
before `inspect`, `bind`, debugger freeze, breakpoints, writes or flash. Any
cross-version pair fails closed. INSTALL_PAIRS, same-version receiver/maintenance,
bound same-version restore, staging admission, safe halt, readback and ordinary
Boot rollback remain. It does not repair an already mismatched BCB, bypass
backup checks, edit EEPROM, force recovery/PC or replace Boot.

## Input And Source Identity

Original source `1430c8ff7f3bcd9a35bfe158ba697b99021f75f2`, CI 41900439548/1,
artifact 13359301400; finalized timestamp 1793820855. Original archive is
`docs/ota-exec-notes/P5-1-new-source-candidate-2026-11-05/artifact.zip`, 6586031 bytes,
SHA-256 `a906221d772a0df5b6b069a250a5b8f951b97371bacd1a8be4b0d77c51988e0b`.
The independent artifact receipt and archived metadata/build/keyed evidence are
also byte-pinned. Both 615132-byte starting images remain unchanged:

- 30317: `0fc735659ad2febf7eed7bd2576bfc2a0605f706b3924bffd7ea0b24099a82b9`.
- 30318: `74c20ab69baa85e73cd6273d84dea95e53428fd81620d184d25c859d150407a1`.
- Preserved 30319: `fdd065a8871bcffcc8e262fa4a43a71cbf20752adab9904a27c0eb59d8f7b89d`.

New metadata records original compilation source/run/attempt/artifact, archive,
ELF/MAP/header relationship and external group16 Boot separately from actual
supplement workflow commit/ref/run/attempt. It states zero new source compilations,
no Boot included/rebuilt, preparation-only purpose and exclusion from P5 statistics.
It never rewrites GITHUB_SHA to the original compilation SHA.

Modified files:

- `.github/scripts/firmware-candidate-context.mjs`: explicit protected supplement admission.
- `.github/scripts/firmware-candidate.mjs`: supplemental routing and source/asset/native metadata binding.
- `.github/workflows/firmware-build.yml`: explicit mode and separate exact supplemental upload allowlist.
- `Tools/ota/p51-package.py`: immutable supplement resolver, FULL packaging and optional existing native verifier branch.
- `Tools/ota/p51-start-state-inputs.json`: new, separate pinned contract; old input files untouched.
- `Tools/ota/p34-acceptance/live_mcu.py`: pre-device version gate, retaining root's dirty changes.
- `tests/ota/test_p51_package.py`, `tests/ota/test_firmware_candidate.mjs`, `tests/ota/test_p34_live_route.py`: executed bounded regressions.
- `tests/ota/test_firmware_workflow.mjs`: honor existing P51_TEST_AREA for contained test outputs; old default retained.
- This independent handoff; root's main records were not edited.

E/audit-01.json and closing audit record every final SHA-256, HEAD-blob identity
and the two actual entry dirty-file hashes. For example, p51-package.py HEAD blob
`f509cedc937b032179c0a810856c01d24fe7fa93d39d47d0b2b284edb0a9d62e` becomes
`7741971a0ac5964fa25e3949ae7020a073baa621803c45b7b8a6610b95863cc5`;
new config SHA-256 is `855b4dd5384de5a359a2fc58abaf4738f1297ad92c7efafbfffff4e7cb0f7ccd`.
HEAD blobs are explicitly distinguished from actual dirty-entry bytes.

## Executed Self-Tests And Failures

All commands use cmd.exe, explicit active-worktree cwd and project-local
TEMP/TMP/TMPDIR/HOME/USERPROFILE/APPDATA/LOCALAPPDATA/cache paths. E/run.py uses
the existing owned launcher, strips cloud/publishing credentials and invokes:
`python -I -S -B -X utf8 E/run.py RUN`. Each RUN/command.json retains exact argv,
cwd/output environment; RUN/evidence/native/host-suite.{stdout.txt,stderr.txt,
process.json} retains raw output, exit code and tree closure. UTF-8 is explicitly
enabled for inherited Python children, not achieved by filtering diagnostics.

| Final run | Actual argv after Python/runtime prefix | Result |
| --- | --- | --- |
| python-01 | tests/ota/test_p51_package.py -v | exit 0, 24/24, 143.633 test seconds |
| live-01 | tests/ota/test_p34_live_route.py | exit 0, 137/137, 250.748 test seconds |
| node-03 | node --test tests/ota/test_firmware_candidate.mjs tests/ota/test_firmware_workflow.mjs | exit 0, 156/156, 37.773 seconds |
| diff-02 | scoped git --no-optional-locks diff --check | exit 0; Git line-ending advisories only |

317 distinct top-level host tests; earlier supplement-01 4/4 and install-01 4/4
are subsets, not extra tests. node-02 also passed 156 but is not double-counted.
New-source's synthetic reference test replays retained, strictly identity-checked
original measurements; it is not a cold search or re-search of this candidate.
The integration test uses an explicitly labelled selection/build-proof double
with actual encoding/native execution. Actual protected candidate key admission
rejects the public fixture key before any prepared package/output is created.

Two actual public-01-key FULL packages strictly reconstruct the exact archived
30317/30318 bytes and pass eight fresh real native FULL/CRC/truncation/wrong-target
version checks. A wrong expected 30318 image for the 30317 package separately
causes actual native exit 2 / byte oracle failure. Initialization decoder builds
use -Wall/-Wextra/-Werror: zero compilation warnings/errors. Successful runtime
checks have zero warnings/errors; expected malformed-input rejections are not
suppressed errors. Metadata drift and idle decoder/private cleanup are exercised.
The existing failed-compiler redaction and one-second descendant timeout tests
also run unchanged; tree closure and private-active absence are checked.

The positive supplement test changes only its in-memory key-binding proof to the
existing public 01 key. It does not claim original compiled-key or CI admission.
All original images, codecs and decoder execution are real. Fixtures are labelled
SELFTEST-ONLY, not installable/protected candidates. E/results.json gives exact
paths, hashes and raw-log hashes. Final fixture package identities are:

- 30317 FULL: 291656 bytes, SHA-256 `2105883c4a5b6b286f86a9e20804445f572ac7f55050a941049d01d0bdcebcf4`.
- 30318 FULL: 291652 bytes, SHA-256 `0870d3848529a8c8e2cc852772f7776536841420313133a504560299dfe3d897`.

They live under E/python-01/fixtures/supplement-fixture-07v_kq1c/.cache/p51-candidate/prepared/.
Nonce-dependent fixture hashes are not production package bindings.

Wrong archive/image/version/source/run/attempt/artifact/key, mixed modes,
workflow/owner drift and changed metadata are rejected. Cross-version tests
cover all four INSTALL_PAIRS and three version pairs with zero inspect/bind/
execute/wait calls; all four same-version routes remain executable using device
doubles, including restore readback/state. The original archived/new-source
native package regressions and existing production/rehearsal/bindings shell
gates run without cloud operations. No constant native PASS substitutes an oracle.

Preserved actual failures:

- node-01: exit 1, 67 reported tests including one module-level YAML failure.
  Raw ReaderError U+DCB6 is in host-suite.stdout.txt; Windows default stdin
  decoding was incompatible with the UTF-8 workflow. PYTHONUTF8=1 fixed the
  host environment; node-02/node-03 passed. No production logic was weakened.
- Two early shell-wrapper syntax failures are retained in entry-failures.json.
  An unanticipated cmd arrow redirection created an empty worktree-root file.
  It was disclosed and safely moved, byte-preserved, to
  E/entry-failures/redirected-empty-original after full source/target preflight.
  No outside-project write occurred. This was a preflight lapse, not a product
  or protected packaging failure; it is not represented as a successful precheck.

## Boundary Audit And Next Owner

Audit verifies 1841 original candidate/execution/restore files and 54 unrelated
dirty files byte-identical. Reversing only this task's exact two shared-file
hunks **in memory** reproduces the actual entry hashes of live_mcu.py and
test_p34_live_route.py; no filesystem restoration occurred. Old manifests,
keyed-build helper, encoding/search, Boot, restore bindings and original assets
remain unchanged. All old p51-package functions except main/native_verify are
AST-identical to HEAD. No UI/product/state-machine source was changed.

Controlled outputs are E, the ten listed code/config/test files and this handoff.
Before workflow-test output override, node-01/node-02 created fresh uniquely named
fixtures under project-local `.cache/firmware-workflow-tests/`; those remain,
were guarded by existing outputPath/writeOutput and are included in the audit.
Later outputs are fully under E. The empty root artifact is archived as above.
No old output was cleaned/replaced. Reparse parents/normalized paths are checked;
closing audit inventories ignored outputs, not only Git status. Private CI
headers/decoder outputs remain excluded from upload; local retained headers are
public test fixtures only. Every retained owned-process receipt confirms tree
closure; no active native marker remains. Staged diff is empty and HEAD unchanged.

Root's precise next dispatch inputs after independent review/integration:

- firmware-build.yml at the actual newly reviewed tooling commit/ref; candidate_reviewed_commit equals that actual checkout SHA.
- package_candidate=true, candidate_mode=start-state-supplement, version_name=3.3.19 (original candidate identifier, not a target override).
- candidate_base_version and candidate_full_base_version empty; firmware_build_profile=p34-v2-candidate.
- publish=false, rehearsal=false, check_bindings=false; OTA_BOOT_CHAIN_READY remains false.
- Existing firmware-rehearsal environment/secret only; no key export or fake original GITHUB_SHA.

The job admits source/inputs without the secret, skips the new-source toolchain,
checks the existing original compiled-key/profile proof against the protected key,
packages/native-verifies the two starts, checks cleanup, then uploads only the
two explicit initialization ETUs, supplement metadata, evidence and the three
safe admitted JSON proofs. No target30319/Boot/private/decoder assets enter its
separate upload list. Root should independently bind downloaded packages and
both source identities, reconcile actual board state and establish aligned starts
through normal product OTA/Boot/confirmation. Such initialization is outside P5
four-combination, 30/30 and four-hour statistics; restore fixtures require their
matching preceding OTA backups and are not initial-state substitutes.

NOT_RUN: protected supplemental CI/key match, ARM build, live BCB/App observation,
initialization/installation, recovery fixture execution, device/phone/SD/OTA work,
P5, physical or independent acceptance. No task or historical acceptance is closed.
