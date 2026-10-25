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
No new APK downloaded or installed. Windows EXE build and independent acceptance
are NOT_RUN; the authorized development workflow does not package Windows EXE.
