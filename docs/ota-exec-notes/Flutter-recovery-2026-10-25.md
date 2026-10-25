# Flutter Recovery Implementation, 2026-10-25

## Scope And Role

The user requested fixes after the P3-8 device observations, including completed
firmware reuse after leaving the upgrade page. This session is now the
implementation owner, not the independent acceptor of its own changes.
The prior `.acceptance-p3-8/v3` and `v4` evidence remains immutable in the
`acceptance/p3-8-device-20261024` worktree. Neither bundle proves full P3-8 PASS.

Implementation branch: `dev/flutter/ota-recovery-20261025`, based on the tested
APK source `6ec6c5ce3189de79794fc0cc437e9b024767ee5d`. Unrelated dirty root
sources were not copied. Local bandwidth policy: no SDK/Gradle downloads or
local builds; checks first in Actions, one final required device APK thereafter.

## Findings And Contracts

| Finding | Repair contract | Regression oracle |
| --- | --- | --- |
| Final firmware file ignored | `findVerifiedFile(asset, cancelToken:)` uses the existing path gate and full length/SHA validation; URLs are not cache identity | Second instance/renewed URL makes zero additional HTTP requests; corrupt/missing/cancelled lookup never publishes ready |
| Page loses recovery entry | Reconcile the exact retained target; serialize reads and coalesce connection events arriving during a read | Same-target reconnect enables actions only after fresh successful identity; another address cannot replace the task target |
| No automatic BLE reconnect | `BluetoothReconnect` retries remembered devices at 1/2/4/8/16 seconds, with native 10-second connect timeout | Adapter off suppresses attempts; duplicate events cannot reset budget; manual disconnect/disposal prevents resurrection |
| Competing link owners | OTA synchronously calls `holdAutomaticReconnect()`, then awaits `automaticReconnectSettled` before IO | Existing attempt settles before OTA, no new automatic attempt during ownership; release is idempotent |
| Concurrent notification permission requests | `initialize()` and `requestNotificationPermission()` share in-flight native operations | Concurrent callers produce one permission prompt; failure and denial remain explicitly retryable |
| Missing startup Overlay | Bluetooth/OTA notification callers use root ScaffoldMessenger only after a frame | No root is safe; a ready root displays the notification without Get snackbar Overlay lookup |
| DATA sent after paused MCU abort | Check latched ACK errors at send/retry boundaries before writing again | MCU abort during pause produces no later DATA or END |
| Adapter-off exception classified unknown | Failed channel writes invalidate the channel and surface `DISCONNECTED` | Identity is invalidated and no stale channel is reused |

## Validation Matrix

- Good: verified final package plus fresh matching metadata restores
  `readyToInstall` without a payload request, including after service recreation.
- Base: a missing completed file follows the existing guarded HTTP/partial path.
- Bad: same-length corruption or changed asset bytes never bypass SHA validation.
- Good: unexpected Bluetooth loss reconnects only the previously selected target.
- Bad: intentional disconnect, disposal, stale completion, or an active OTA owner
  never starts a competing reconnect or a second OTA invocation.
- Recovery starts a new explicit transfer using the receiver's authoritative
  BEGIN/durable state, not cached UI percentage, sequence or session IDs.
- END ACK alone remains insufficient; reboot identity verification is unchanged.

Wrong: infer readiness from a filename or retained percentage; start OTA from a
connection callback. Correct: validate completed bytes and fresh target identity,
show a usable explicit transfer action, and leave OTA start with the user.

## Results

First development batch: `e932d600ab6560cf2f874b3fae1908edf85d6a51`,
Actions run `40145530987`: failed. The second batch
`751f2ca04c6f7980a63f5f9ab2599c8c51ab4ffc`, run `40146295666`, passed all tests
(Ubuntu 772 passed/16 skipped; Windows 753 passed/35 skipped), but analysis
correctly failed on a relative import of the vendored Android test platform.
The import is being corrected to its already-overridden package name. No lint
suppression, removed assertions or dependency upgrade was used. CI SDK:
Flutter 3.47.8, Dart 3.13.7, framework revision
`737ba8f885dc774b53b442759999a312c9461e4e`.

Final tested source: `b5111325581f4170a70492e6c3e1202f68d5c0c9`.
Checks-only run `40147672398` and APK run `40147778398` both concluded success.
Both hosts passed analysis with no issues and all tests (Ubuntu 772/16 skipped,
Windows 753/35 skipped, zero failures). The vendored Android test platform is
now an explicit development dependency; the lockfile and resolved versions did
not change. Android debug APK build passed. Windows EXE build and independent
acceptance are NOT_RUN; the authorized development workflow has no EXE job.

Only one APK archive was downloaded (75,526,008 bytes). APK bytes: 131,809,306;
SHA-256 `e8a77ce2fbb517146b6e5cae196dba7117fbf2185a9ce731e4b5abbb931f05c1`.
CRC, actual application ID `com.wen.gaia.gaia.p38acceptance`, and fixed debug
signer `9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`
were independently checked locally using existing aapt/apksigner, with no SDK
download or local build. Source/result/archive receipts are in
`.cache/recovery/final-ci`, `apk-001` and `apk-verified`.

## Device Follow-Up

The finite follow-up is: verify phone/current installed test APK and unchanged
cached package; replace only the known test package without clearing data; use
schema-1 baseline BLE settings; test cached-file reuse on reentry; test one
Bluetooth off/on recovery; then explicitly resume the remaining transfer and
verify post-reboot identity. Do not replay prior successful background cells or
downgrade the MCU. The retained reference ETU and target remain the original
30287 -> 30288 fixture, SHA-256
`fe6ebde3a100319d53df3bcb85ea95e6a48a75aba6cda40f1953bdeee528707c`.

USB inventory found no devices, corroborated after allowing discovery time.
No APK was installed, no App data changed, and no OTA/MCU operation was started.
Both private ADB windows closed with verified receipts. Network-001 failed its
cross-worktree HTTPS child-entry guard before serving a phone. Network-002 used
the same existing reader through a contained entry, passed the HTTPS fixture
checks and was explicitly closed because the phone is absent. Do not reuse its
expired URL. When USB returns, renew the network and write a fresh schema-1
runtime configuration before launching this runtime-enabled APK; this does not
require another APK build/download. This is a development/observation APK, not a
published general-release artifact or proof of phone-side usability.

## Regression Lessons

Root causes were cross-layer state assumptions and missing integration tests:
completed bytes outlived page memory, a remembered address was mistaken for a
live verified link, and multiple service owners initialized one permission API.
The repair uses verified disk state, explicit link/identity reconciliation and
single-flight native operations rather than broader retries or extra downloads.

Initial remediation failures were concrete test/setup gaps: the old cleanup
test implicitly forced HTTP despite a valid completed cache; simulated native
events lacked platform registration; a snackbar call had additional style
parameters; a reconnect-test timer needed disposal before widget invariants.
The sender fix was narrowed to terminal errors so existing recoverable sequence
error handling remains unchanged. Tests still assert error-budget recovery,
same-target binding, cancellation ownership and byte identity. Bluetooth
controller startup callers were also migrated to the safe notification entry.
