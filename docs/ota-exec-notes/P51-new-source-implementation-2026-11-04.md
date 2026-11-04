# P51-NEW-SOURCE-01 Local Implementation Handoff

本地未提交实现；未运行真实受保护 CI；未制成正式候选；未操作设备。

Root owns independent review, integration, protected execution/approval, candidate
binding and P5. No formal acceptance PASS, version reservation or historical
acceptance amendment is claimed.

## Design And Scope

Writable root: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Entry HEAD and current HEAD: `b871d57e66645f43b29a8006a58ca6a3692951f3`;
branch: `dev/flutter/p51-timing-20261104`. Existing unrelated modifications
were retained. Read the requested governance, P5 prompt, latest build/gap note
and UI follow-up handoff. No Trellis directory exists in this worktree.

The evidenced gap was admission/lineage, not a missing compiler or credential:
archived packaging cannot truthfully become a source build through changed
manifest values. The new explicit `new-source` input uses an independent
`p51-new-source-inputs-v2` configuration. Default `archived-original` keeps
the original manifest, 30313/30316 recipe and v1 metadata.

Reuse:

- `buildKeyedFirmware`: canonical GCC/CMake profile, private forced include,
  cache disabling, configuration capture, key binding, sanitized diagnostics,
  build artifact capture and owner-bound private-header cleanup.
- Existing `WindowsJob`/POSIX launcher through `p51-package.py::native_command`:
  bounded compiler trees and closure receipts. A narrow `command` adapter is
  the missing interface; the new mode cannot use the bare spawnSync executor.
- Existing key/profile/schema helpers, `etu_pack.build_fw_header`,
  `normalize_patch_header`, envelope/LZMA codecs, reference
  `encoding.search/encode/strict_lzma/patch_stream`, and recovery owner.
- Existing reference host with a conditional all-assets adapter invokes the
  unchanged native full/patch decoders; recovery uses native CRC/header checking
  and exact image bytes, not UART/real Flash or Boot state-machine execution.

One reviewed executable is compiled once. Start and target are separate
fw_header finalizations with the actual checkout's commit timestamp. An optional
root-selected `candidate_full_base_version` produces a third finalized start
from that executable, at a distinct lower version than the patch base. It is a
real restorable image, not a fabricated GET_INFO/hash/D1 fixture. The metadata
explicitly records two or three header derivations and one source compilation.

External approved group16 Boot retains its original image/build/source archive
proof. Ordinary Boot, built by the existing helper in the same invocation, is
uploaded separately under keyed-build and marked compile-only/not candidate Boot.

Changed files: `.github/scripts/firmware-candidate{,-context}.mjs`,
`.github/scripts/firmware-gcc-keyed-build.mjs`,
`.github/workflows/firmware-build.yml`, `Tools/ota/p51-package.py`,
`Tools/ota/p51-new-source-inputs.json`,
`Tools/ota/p34-acceptance/reference_host.c`,
`tests/ota/test_firmware_candidate.mjs`, `tests/ota/test_p51_package.py`,
`tests/ota/firmware-pipeline.host.test.ts` (contained fixture path override only),
and this new handoff. No UI, firmware algorithm, version gate, FAT/USB/Boot/BCB,
protocol or root task-record edit.

## Contracts And Outputs

Both modes require artifact-only dispatch, exact reviewed checkout, locked
`OTA_BOOT_CHAIN_READY=false`, profile `p34-v2-candidate`, and publish,
rehearsal and check_bindings exactly false. Cloud/publishing credentials are
rejected. Existing production/rehearsal gates are not relaxed.

New mode additionally binds the actual workflow SHA/ref and protected candidate
context, verifies b871d57e ancestry and unchanged product paths, and rejects
tracked dirty checkout/untracked product inputs. Reviewed product baseline,
actual compilation checkout, workflow/runner revision and run/attempt have
separate metadata fields even when checkout and workflow revision are equal.
This implementation deliberately supports same-checkout runner/source, not an
unreviewed second checkout.

Versions must be canonical uint32 names fitting the 16-byte header, strictly
forward and above retained 30316. No concrete version is reserved by this code.
Optional full start must also be below target and differ from patch base.
Root still checks occupation and recovery feasibility before selecting values.

New outputs: app-start.bin, app-final.bin, optional app-start-full.bin, external
X-Track-Boot.bin, full.etu, exact-base patch.etu/reference-1MiB.etu aliases,
recovery.bin, keyed App BIN/ELF/HEX/MAP, separate ordinary Boot artifacts,
configuration/build receipts, reference measurements/selection, native receipts
and v2 candidate metadata. ELF/MAP exactly identify the raw GCC compilation;
metadata gives the 0x400/96-byte finalized-header relationship. They are not
mislabelled as independently compiled or header-updated ELF files.

Reference is a legal deliberately non-minimal progressing delta, not padding.
Exact total size, EOS/full consumption, patch progression and byte identity are
verified before packaging. Failure to find an exact witness within 256 samples
fails closed; no length-forcing fallback. Fresh nonces are generated once, with
reference an exact alias of patch. Upload uses explicit public files/receipts,
not the build tree/private headers/decoder/toolchain. Unconfirmed native or
key-build trees, mismatched owner or failed cleanup block upload.

## Actual Self-Tests

Evidence: `.cache/p51-new-source-impl-20261104-01/`.
All commands use cmd.exe and the explicit writable root. `run.py` contains
TEMP/TMP/TMPDIR, Python encoding/cache and npm outputs; each run retains raw
stdout/stderr, argv, cwd, exit and diagnostic hashes in command.json.

Final commands (prefix each with
`python -B .cache/p51-new-source-impl-20261104-01/run.py RUN`):

| RUN | Remaining argv | Exit | Result |
| --- | --- | ---: | --- |
| node-04 | node --test tests/ota/test_firmware_candidate.mjs tests/ota/test_firmware_workflow.mjs tests/ota/test_firmware_build_profile.mjs | 0 | 167/167 |
| python-04 | python -I -S -B -X utf8 tests/ota/test_p51_package.py | 0 | 13/13, 257.914 s |
| keyed-01 | node app/bluetooth_flutter_Trace/cloudflare/update-service/worker/node_modules/vitest/vitest.mjs run --config .github/scripts/p41-host.config.mjs --testNamePattern=firmware.key.wiring --reporter=verbose | 0 | 17 passed, 139 unrelated tests explicitly skipped |
| reference-01 | python -I -S -B -X utf8 tests/ota/test_p51_reference.py | 0 | 8/8 |
| diff-01 | git diff --check -- [the eight changed tracked script/workflow/test files] | 0 | No scoped whitespace error; 8 Git LF/CRLF advisories |

205 selected host tests, not 205 LVGL assertions or independent acceptance.
Native subcases: legacy patch 5, default new-source 11, optional-full-start
pipeline 12. Actual native builds use -Wall/-Wextra/-Werror, zero compile
warnings/errors. Successful package/decoder runtime diagnostics have zero
warnings/errors. Keyed regression has one Node SQLite ExperimentalWarning and
one intentionally injected, redacted compiler error, both retained. Compiler
doubles do not count as a production build or its warnings.

Coverage includes new/old admission, source/workflow/review/config drift,
canonical forward/full-start pairs, mixed/production gates, actual keyed-helper
invocation, captured private include/profile, wrong key, request owner/run/attempt,
full/patch/recovery byte reconstruction, wrong actual base bytes, CRC/truncation,
exact 1MiB and LZMA-tail rejection, metadata asset drift and cleanup/timeout
descendant closure. Old candidate inputs/header-only result are actually
resolved/packaged/native-tested, not merely checked as source strings.

The reference search really executed. The separate pipeline integration reuses
its exact recipe, re-encodes/strictly decodes it and runs native tests; its search
selector alone is doubled. Keyed compiler tests use compiler doubles and public
synthetic keys/environments. The package images are explicitly synthetic altered
archived bytes, not newly protected-compiled UI or installable assets. Fixture
versions 3.4.0/3.4.1/3.4.2 are not reserved or registered.

Final pipeline originals:
`python-04/fixtures/pipeline-_40luk8_/.cache/p51-candidate/`.
Its patch/reference is 1,048,576 bytes, SHA-256
`afdfb7bf2747ac0d481d9f85ad48f3ec8bb0128ef69e1f9f14311fca04d47441`.
The full is 290,922 bytes, SHA-256
`5ee8207e63b31a824ce1179cfdc05074199e26afee61cb1569ccf9343c9393ed`.
Recovery is 614,100 bytes, SHA-256
`fe4fac6374145a7bd69d3df5c26ed767a476b261babd768b282b3690ee435b84`.
All remain SELFTEST-only; complete identities are in SELFTEST-metadata.json.

Failures retained: node-01 child YAML GBK failure and outer printing failure;
Python-02 metadata check failed after the loaded Python verifier and on-disk
Node checker became different revisions during that run. It is not final
evidence. Stable default rerun python-03 passed 13 tests; optional batch
python-04 also passed 13. node-02/node-03 pass originals remain. Entry filename
enumeration failure and repairs are recorded in entry-failures.txt.
No old failure/warning evidence was edited or removed.

## Identity And Audit

Before/final identities and original-file preservation are recorded in
baseline.json and audit-before-handoff.json under the evidence root. Initial
SHA-256 -> final SHA-256 for the two principal helpers:

- candidate.mjs: `2a35c900dfa2f61712489cb650155916e380d89903f5a46a0c9b2b1ddabfc752`
  -> `f049380c7386221088bba0b46f09919915fdc544b6f957a48e24d14d7676b523`.
- keyed-build.mjs: `78709cd3b57a99c78686192c9c8d55c7b09f647ce0d8594184041d24450ed095`
  -> `db0f89408436354014c53ba3cf0de71cc8159cf26a1e92a50a9f8aa2ebee819d`.
- New context SHA-256:
  `0354ec90f4041bfa04cf958edd52b59f1c32a636db0096355f23c6a99e25d47e`.
- New independent input configuration SHA-256:
  `781d30bf57a77ea893991d72ee70160897772fc1a1ef63289ddf5a50759ec5a5`.
- Unchanged v1 manifest SHA-256:
  `f07b239edcae98736cac220fa111e302560809ebc10ad9db8289bcdc256573c9`.

Closing receipt `final-02.json` adds the handoff identity and exact Git outputs:
11 changed/new source-record identities, 25,356 initial files verified with no
out-of-scope byte changes, 10,029 controlled output files checked and 117 actual
native tree-closure receipts. HEAD/branch remain unchanged and product-path diff
is empty. The intentional negative fixture markers are listed, not mistaken for
unclosed actual processes.

Boundary preflight uses normalized absolute paths and the existing host_io
reparse-parent guard. Outputs are the new evidence directory, contained Worker
node_modules/npm installation, and fresh mkdtemp workflow-test directories under
`.cache/firmware-workflow-tests`. No PowerShell, external temp/cache/download,
J-Link/phone/SD action, commit/index mutation, CI dispatch, upload or deletion
of originals. Npm ci used --ignore-scripts, explicit prefix/cache/userconfig,
no audit/fund, and did not change package-lock. Toolchain checksum was read
from the official endpoint to stdout; the toolchain itself was not installed
or MCU-compiled locally in this task.

Actual native process receipts confirm tree closure, including injected timeout.
Intentional empty active markers/public fixture key headers remain only in
negative test fixtures; they are not live processes or protected key residue
and are not an upload set. Real protected private-header cleanup and ARM CI
execution remain NOT_RUN. The audit does not credential-discover pre-existing
wrangler state; no wrangler command was executed.

NOT_RUN: real protected GCC/new candidate CI, toolchain archive extraction on
Linux, finalized production ELF/BIN identities, environment approval, formal
candidate/service binding, device recovery/GET_INFO/full selection, UI replay,
OTA/four-cell/endurance/production release. Existing UI and P1/P3/P4/P2-5
results are not reclassified or replayed.

## Root Next Steps

1. Concentrated independent review of these files and the final host originals;
   integrate/commit only the reviewed task paths, preserving unrelated changes.
2. Select unoccupied legal base B and target T, with 30316 < B < T. For BLE full,
   optionally select F with 30316 < F < T and F != B. Check actual recovery route.
3. On the exact independently reviewed execution commit C, dispatch the existing
   firmware-build.yml with package_candidate=true, candidate_mode=new-source,
   candidate_reviewed_commit=C, candidate_base_version=B, version_name=T,
   optional candidate_full_base_version=F, firmware_build_profile=p34-v2-candidate,
   and publish/rehearsal/check_bindings=false. Keep OTA_BOOT_CHAIN_READY=false.
   The workflow itself supplies strict candidate context; do not fabricate it
   or reuse rehearsal=true. Approve the existing firmware-rehearsal environment
   only under root's effective authority.
4. Inspect actual run/attempt, checkout/workflow/baseline identities, key/profile,
   external group16 proof, warnings/errors, exact-byte/native/reference receipts
   and successful cleanup before binding any artifact. Confirm raw ELF/MAP and
   finalized header relationships. Do not call fixture outputs real CI evidence.
5. Root binds the actual candidate and recovery fixtures. Optional app-start-full
   has a truthful version distinct from the registered patch base, so a real
   restored/CONFIRMED F can legitimately select full; no GET_INFO/hash/D1 forgery.
   Keep original group16 Boot and old 30313/30316 assets unchanged. Then compute
   the affected minimum P5 scope and resume under valid device authorization.

No third freezing agent, unrelated historical replay or implementation-owned
P5 closure is needed or performed.
