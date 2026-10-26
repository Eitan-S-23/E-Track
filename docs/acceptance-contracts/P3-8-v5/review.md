# P3-8 v5 Independent Review

Independent reviewer/acceptor: `/root/fastpath_review`. Product implementation,
Git writes, CI and original physical sessions remain owned by `/root` or the
historical independent operator. This reviewer changed only offline acceptance
tools/tests and this bundle; no product source, OTA, device state, release,
network service or external-project filesystem was changed.

## Scope And Provenance

The seven criterion IDs are unchanged. This is the formal successor to v4,
not a reset of the failed/missing observations. V1 host-entry failure, v2
runtime-disabled APK readiness, v3 denied D2, v4 recovery/final-identity gaps,
and the later root recovery query-timeout result remain preserved. Original
observation dates are 2026-10-24 through 2026-10-26. Staging provenance in
`inputs/origins-final.json` binds exact source path, SHA and byte count;
selected power/failed-signing lines also retain full source hashes and original
line numbers. No altered historical matrix is presented as green.

The final source is frozen at `2be0540feda1aec0ca001afb8456bb7bd82183ce`.
Product lib/android/pubspec is unchanged from baseline
`410b7d57c7ed918103986f42a30af80960506826` and signing source
`aa760c533853938dacf120dcddff5b1a4f56f05f`. Every physical snapshot is strictly
parsed and externally bound to capture/PID/sentinel/target/APK identity, not
trusted solely because its own header is internally consistent.

## Observations Reviewed Before Freeze

- Standard nonpublishing run 40242995708: Android 772 passed/16 skipped;
  Windows 753 passed/35 skipped; both analyzer steps report no issues and
  both standard builds succeed. Native 18-case JUnit has no failure/error/skip,
  with unchanged applicable Android source. Actual setup selects Flutter 3.47.8,
  framework 737ba8f885dc774b53b442759999a312c9461e4e. No absent Dart/engine
  version is invented. Build warning lines: Android 10, Windows 0. Android
  warnings concern upcoming Gradle/AGP/Kotlin support and plugin SDK 36 needs;
  build success is not represented as warning-free.
- APK and EXE standard ZIPs pass CRC/member checks, distribution EXE equals
  standalone EXE, and official local apksigner/aapt outputs bind exact APK
  bytes, standard package and 1.0.61+87. Historical temporary certificates
  differ legitimately; they are not fixed-key evidence.
- Fixed-key nonpublishing run 40249303504 succeeds on both hosts. Android job
  121337548043 verifies certificate
  9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579,
  APK SHA 66a5ef87fffe171f947c69bdbc67dd60d6498310c5a8d2a3bbac474e7d5b37a1,
  47397132 bytes. No extra APK is downloaded or installed. Earlier runs
  40246822370/40248070782 failed signer-text parsing; the latter actually
  verified the correct certificate under Build Tools 37's `V2 Signer:` label.
  Reviewed aa760c53's exact-one signer count and all-scheme certificate match;
  signature-verification failure still stops execution through pipefail.
- D1 retains one completion after the first pause and all subsequent quiet
  intervals; it does not prove zero GATT starts at the first lifecycle instant.
  D2 native percentages, current task Intent, same PID and returned screenshot
  are independently adjudicated in `notification-adjudication.md`. The screenshot
  is not evidence of numeric transfer progress or the fast-run visual UI.
- Recovery from historical disconnect resumes the exact same package at MCU
  durable 401408, first send 401408, through 1048576. This is explicit recovery;
  automatic reconnect is not inferred. It closes the old durable-resume gap.
- Existing fast full-transfer data establishes v2/window24/batch12 at runtime
  schema 10, 63071407 us and no retransmits/missing/early ACKs. Locked native
  samples share PID 6468 and immutable snapshot prefixes, with durable
  565248/724992/872448/1028096/1048576, actual foreground ownership and an active
  partial lock. This does not establish production fast-path release settings.
- Final full passive App image is 30289, SHA
  245189f7b2f02d968068b3ade77000a0b82a8de20b140bd41e2530675713bad0.
  Header CRC and double-zero embedded hash verify, exact target bytes agree
  with fresh GET_INFO, and Boot SHA remains
  01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527.
  Raw confirmation/SD/idle/fault registers and advancing same-boot health pass.
  Completed/cancelled/failed/disconnected native resources and host closures
  are checked from their actual terminal originals.

## Execution And Portability

The approved formal command has now run once: 11.9190755 seconds, exit 0,
seven criterion PASS results, empty stderr, completed job/handle cleanup.
`execution/offline.closed.json` and `execution/result.json` are its originals.
The prior NOT_RUN precheck passed and the generated plan requires only
`CMD-P38-OFFLINE` (seven rerun criteria, zero reusable criteria). Final bundle
validation remains a separate check; its receipt must be inspected rather
than treating this command-level result as a substituted final validation.

Preparation self-tests (14 unittest cases) and cached seven-criterion smoke
results are not formal execution or approval. Formal execution uses a frozen
NOT_RUN matrix, real previous-v4/minimal-rerun precheck, then exactly one shared
offline evaluation under a 180-second host ceiling, followed by final physical
file verification. No hardware/build/download is repeated. EXECUTED refers to
this independent evaluation; no criterion is fabricated as REUSED.

`inputs/history/v3` and `inputs/history/v4` retain the complete minimum byte
sets required by their matrices/external bindings. The v4 REUSED origin is v3;
v3 itself has no REUSED records. The previous/reuse-source arguments are
mandatory even though v5 uses no REUSED criterion. Their historical absolute
paths are inert original text, not new read/write targets.

Old freeze 60cb25c4 is not an ancestor of the product branch. Root retained its
exact history tip 3f3c32efa7bd9fb9f2c068dedab0517b99f74360 as
`origin/acceptance/p3-8-device-20261024`, without merging old product code.
A new clone must fetch this history branch and full current branch ancestry
before rerun-plan/final validation. The independent offline evaluator itself
uses a hash-bound original v4 transport copy, not that unreachable commit.
Other source applicability anchors 27048aa1, 3daf949f and 410b7d57 are current
freeze ancestors. Check out the eventual bundle commit, not just freeze_commit,
to find the evidence. Contract/matrix bytes and historical bundles are immutable
after formal execution; this report grants no merge or release authority.

All reviewer-chosen generated outputs and temporary/test paths remain under
the approved active worktree scopes. PowerShell, external temporary directories,
new downloads and private vendor-wide device dumps were not used. No
unauthorized external filesystem cleanup is performed.
