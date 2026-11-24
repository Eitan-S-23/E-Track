# Researched Speed Plan

Current result: the unchanged original-flow OTA retest (`measure/trial6`)
completed and full C30286 App/unchanged Boot/confirmation/SD/running-health
readback passes. Transfer 11.392060 seconds; reconnect 17.772017 seconds.
BEGIN resumed from 45056 bytes, so this is functional retest evidence, not a
zero-start full-package speed improvement. No DATA retransmissions or error
ACKs occurred. The earlier normal C30285 J-Link check also passed; neither
success proves absence of intermittent faults or establishes the trial5 cause.
Both the clock-change and QSPI self-test detours remain cancelled and uninstalled.
See the current decision in [transfer continuation](P3-4-transfer-next-2026-10-07.md).

Previous failure: the restored original full lifecycle (`measure/trial5`) performed
one real C30285->C30286 transfer and failed with `ACK_STATUS` after45056 durable
bytes. The original App snapshot and a receiver-bound frozen MCU profile are
preserved. The twelfth 4 KiB payload verification recorded an error; this does not
yet distinguish restore/read IO failure from byte mismatch. UART/drop counters
are clean. Full C30285 App and group16 Boot remained unchanged. SD readiness was
subsequently restored and verified; the earlier failure is not attributed to SD.
No new speed gain was established by that failure. C30286 was subsequently
installed by the resumed trial6 described above.
See the latest section of [transfer continuation](P3-4-transfer-next-2026-10-07.md)
before using the older preparation checkpoints below.

Current continuation checkpoint: native timing observer commit `ef47dabd51f129c64a0be0945265192d17f70c17`
on `dev/flutter/p34-native-timing-20261008` passed both-host checks and explicit
debug APK run 37745196875 (Linux 700 / Windows 683 passed). APK SHA-256
`c9809a339d19d60f6e686ed99dd9329263c21ed2f66679cff76dd2e6417ea25a` is now
installed and readback-verified. The install command timed out, but read-only
reconciliation proved success and preserved data; no second install was used.
The subsequent INFO query produced a complete native timing row, with zero
errors/overflow. This proves the diagnostic route, not DATA throughput. One new
forward full C30285->C30286 native DATA screen was prepared with unchanged
transport/receiver code and Boot. Two host-adapter failures were fixed; the ready
window then expired with zero upgrade starts. A cheaper read-only attachment to
the existing App/cached package is prepared and host-checked, but its first USB
attempt found the named phone unavailable. Phone USB reconnection is now required;
do not reuse the expired Start instruction or reinstall. See the task note for
the preserved failures, exact current state and non-replaying attachment entry.
No new OTA or measured acceleration has occurred at this checkpoint;
13.343180s remains the last public transfer result. See the latest outcome in
[transfer continuation](P3-4-transfer-next-2026-10-07.md). This is diagnostic
preparation, not a completed transport optimization or independent acceptance.

Newest status: no further speed gain is measured after the WAIT_RX screen.
The installed plain-tag APK (`01e424fd`, Actions APK run 37729963790) passed both
host checks but did not solve native callback observation. Legal per-tag DEBUG
was tested/restored; global logging stayed unchanged. Read-only shell/App-UID/PID
comparison confirmed that standard logcat can return system records, not the
missing native timing for the original queries. A bounded diagnostic recorder
using the existing plugin channel and App snapshot is now selected, not a native
sender rewrite. Its design, evidence gap, tests and finite query-only installation
plan are in the newest section of
[transfer continuation](P3-4-transfer-next-2026-10-07.md). No new OTA, MCU reset,
Boot/EEPROM write or guaranteed speed estimate follows from this preparation.

Current execution update: the WAIT_RX single screen completed after standard
J-Link installation, without an installation OTA. Transfer13.337202s versus the
prior14.757523s,0 DATA retransmissions, complete ACK samples and clean native
counters; full C30285/unchanged group16 Boot/health verification passes. The1.420321s
observed difference is modest, not a large or proven stable causal gain. Compared
with the earlier best13.814972s, it is only0.477770s. All owners closed normally.
The subsequent GATT investigation correlates the entire original v2 transfer,
confirming10.841126s DATA GATT time and actual2M/15ms/251-octet link parameters.
Native callback versus Flutter delivery time is still unobserved; no native
rewrite or fixed saving is justified. See the newest GATT/WAIT_RX sections in
[transfer continuation](P3-4-transfer-next-2026-10-07.md) for exact artifacts,
the bounded read-only query observation and retained verified C30285 state.
This does not reactivate the deferred patch-distribution proposal below.

Status: patch proposal DEFERRED OUTSIDE current P3-4 execution. Owner: Codex root.
User requested an evidenced plan before more speed work. No device operation,
firmware edit, installation, CI dispatch or OTA was performed for this research.
Retained device at the original research checkpoint: C30284 with unchanged
group16 Boot. The later current state is C30285 as stated above.

## Scope Correction

The user questioned the task boundary after conditionally authorizing execution.
The [P3-4 task](../ota-prompts/prompt-P3-4-experiment.md) owns measured transport
throughput, supported baud/timeout/retry selection and reliability. Replacing a
roughly296 KiB full package with a6-12 KiB patch does not meet that objective.
Root's recommendation made a practical product-latency option the main P3-4
plan; that was scope drift. The earlier authorization is not used to expand scope.

Do not execute the patch recommendation below as the next P3-4 action. Preserve
its offline results as a separately scoped option, not a throughput result or
permission to publish assets. No implementation or new OTA followed the latest
authorization. The original diagnosis and proposal remain below for traceability.

Existing patch-format packages may still be legitimate P3-4 test inputs, including
an admitted reference-size fixture. The exclusion concerns shrinking the workload
or changing distribution as a substitute for link improvement, not a blanket ban
on the patch format. Resume only evidence-based transport work under the unchanged
input, statistics, integrity and reliability rules; do not invent another large
speed forecast merely to replace the withdrawn proposal.

## Corrections To The Previous Proposal

The prior recommendation to defer App peripheral initialization, and its claimed
5-10 second opportunity, were not supported by phase evidence. Withdraw that
forecast and do not implement startup reordering on that basis.

Original standard-Commander samples now separate old App activation from Boot.
`.cache/p34-plan-research1/timeline.json` binds SDK logs and prior readbacks.
All brackets use only SDK monotonic timestamps; they are sampled bounds, not
exact transitions or subtraction of phone and MCU clocks.

| Original run | Old App still observed after first terminal END sample | Boot residency bracket | Changed 4 KiB copy blocks |
| --- | ---: | ---: | ---: |
| 30282 -> 30283, real ACK code change | at least 11.706s | 18.317-21.289s | 149/153 |
| 30283 -> 30284, header-only successor | at least 13.082s | 1.225-4.331s | 1/153 |

The installed Boot's source is `.cache/p34-bc-target/f/boot/src/boot_state_machine.c`;
its b16 Ninja configuration enables `P34_BOOT_SKIP_IDENTICAL_BLOCKS=1` and
`P34_BOOT_APPLY_CHECKPOINT_BLOCKS=16`. `compare_existing_block()` and
`copy_source()` skip programming identical blocks. The full Boot hashes in both
postchecks match. These runs are not equivalent installation workloads: the
34.41s versus 20.29s reconnect/identity observations must not be interpreted as
pure Android reconnect timing or an ACK-induced startup change.

The actual App source in `.cache/p34-overlap1/f` shows END2 delegating to
`session_handle_end()`, which sends END ACK, releases BLE ownership, calls the
synchronous activation hook and only then resets. `ble_env_activate_staged()`
runs full/patch apply followed by `OTA_BackupStage()`. This explains why repeated
INFO failures can occur before a new App has even started. It does not identify
the split of the current activation cost into decode, candidate write and backup.

## Verified Large Reduction: Existing Patch Format

Use the existing bsdiff executable, packer and unpacker; no replacement algorithm.
Two historical REAL CODE changes were selected, not header-only speed fixtures.
Original base/target bytes and hashes were verified before packaging.

| Change | Full ETU bytes | Patch ETU bytes | Reduction |
| --- | ---: | ---: | ---: |
| ACK header binding, 30282 -> 30283 | 296444 | 6666 | 97.7513% |
| Cross-block pipeline, 30278 -> 30281 | 296354 | 12403 | 95.8148% |

Evidence: `.cache/p34-plan-research1/result.json`, `native-result.json`, and
`pipeline-change/result.json`. Python roundtrip and the hash-verified existing
C `reference-1.exe` decoder both reconstruct the complete target byte-for-byte.
Both C checks pass image-header validation, buffer guards and workspace lifecycle;
workspace peak is 21856 bytes. The C oracle is a preserved host decoder, not a
new build of the currently installed firmware, and these are not device timings.
The generated historical packages MUST NOT be installed on current C30284.

The large proven result is fewer transferred bytes, not a faster physical link.
Patch reconstruction still writes about 623 KiB of candidate image and Boot
still copies changed internal blocks. Do not claim a 24x/44x whole-upgrade speedup
from package ratios, promise a seconds saving, or relabel this as the same-package
P3-4 throughput/reference/soak acceptance.

## Deferred Product-Latency Proposal

1. Keep the existing BLE baud, MTU, window, retry and integrity rules fixed.
   For the next genuine forward code change from the verified current image,
   generate both full and patch assets with the existing tools. Do not create a
   header-only target solely to manufacture an exceptionally small patch.
2. Bind patch selection to the full raw base-image SHA-256 and target identity.
   Reuse `OTA-XC-ASSET-SELECTION`: exact eligible patch match first, existing
   full fallback when no valid matching patch is available. Do not replace this
   with a version-only match, a new selector or an undocumented fallback on a
   corrupted running transfer. Production publication remains separately scoped.
3. Reuse the existing App/MCU patch transport and decoder. Before the first
   device screen, verify the current compiled decoder configuration and run
   host cases for wrong base, truncated/corrupted input, final target mismatch,
   cancellation and resume. Retain marker-last, backup, STAGED and Boot checks.
4. If new receiver code is actually needed, install through standard J-Link
   after the current App/BCB/staging compatibility checks, then verify full image,
   unchanged Boot and health. No extra OTA solely to provision that receiver,
   no arbitrary BCB edits, and no replay of a historical forward package.
5. Run one legal forward patch screening transfer with original App/native
   recording. Report transfer, activation, Boot and target identity separately.
   Do not call unlike historical installation workloads a controlled A/B test.
   Additional comparisons need a declared equivalent-state design, not blind
   repeats. Stop on integrity/recovery failure or absent useful total-time gain.

## Alternatives Not Selected

- App initialization reordering: current evidence does not support it as the
  dominant delay; most waiting precedes new-App startup.
- More ACK-only tuning: local ACK cost fell but transfer became slower in the
  completed screen. No new round is justified just to seek a favorable sample.
- Immediate simultaneous receive/decode rewrite: BLE and PACKAGE currently own
  the same 40 KiB overlay exclusively. Removing that ownership boundary without
  a memory/lifecycle design is not a proven shortcut.
- WAIT_RX alone: the measured payload erase/program total is about 3.236s and
  overlaps other phases; this does not justify the previous 5-10s promise.
- Native sender rewrite or larger MTU: no demonstrated native-queue bottleneck;
  preserved module negotiation caps MTU at247. Do not build another APK by guess.
- Boot group tuning: keep group16 and the identical-block optimization; many
  changed blocks still incur real Flash work. Header-only results cannot predict
  general code-change installation time.

If the user's requirement is specifically a large throughput increase for the
SAME roughly296 KiB full package, the patch proposal does not satisfy it. There
is currently no verified plan guaranteeing that increase; keep that objective
open instead of silently substituting the reduced-byte result. For practical
version-to-version upgrade latency, the patch route has the strongest evidence
and the smallest new implementation scope among the reviewed alternatives.
