# Companion Sleep And Process-Independent Recovery

Task: APP-COMPANION-01 / COMPANION_SLEEP_WAKE. Owner: Codex root.
Initial checkpoint: IN_PROGRESS; implementation and development checks only.
The later owner request authorizes the combined App fix, a new version and main
delivery through the existing automatic candidate workflow. Current delivery
receipts belong in the primary OTA-COMPANION note and main progress board;
neither this design record nor a development push establishes candidate delivery.
Base: `1faf82911a241e9dc8280c78855ab9148134de1e`.
Branch: `dev/flutter/companion-sleep-20261125`.
Worktree: `.worktrees/companion-sleep-20261125` (sparse App checkout).

## Idle Control Recovery Follow-Up

The owner also reports an established BLE connection that stops serving MCU
CHECK requests after prolonged idle, until the App firmware page is opened.
Source review confirms that link-generation/identity reuse did not establish
live control notifications, notification errors only marked the reader dirty,
and reader completion had no recovery path. The firmware page happens to run
GET_INFO and renew notifications. The existing export ends at 19:13:38 and does
not establish which radio/OS event initially invalidated this later connection.
MCU PHONE_REQUIRED after a ten-second CHECK timeout is not a physical BLE
disconnect observation. The separate automatic HTTP cooldown is not its remedy.

The App now uses the existing native heartbeat to request a coalesced, rate-limited
control health check without delaying the native liveness reply. Foreground and
explicit manual wake also reconfirm control. Notification error/completion
requests repair immediately. A new notification owner is acquired before the
old reader is retired, so old cancellation cannot disable the replacement CCCD.

Repair first leases the existing physical GATT and uses same-session HELLO/CAPS,
preserving offers, request numbering and explicit consent. A pending device
CHECK/CHOICE drains after repair; no HTTP query, download, offer replay or upgrade
is part of a health check. Known control failure retires the captured GATT and
hands retries to the existing native four-attempt/60-minute policy, with bounded
cleanup and old-generation fences. Older firmware without control capability
retains its explicit App fallback rather than entering a reconnect loop.
Diagnostic health completion does not increment cloud-check/OTA-success totals
or discard the current user-facing update notification.

Regression coverage includes silent notification loss, error/completion,
foreground-only recovery, long idle heartbeat/coalescing, checks arriving
during repair, retained Later consent, existing OTA ownership, failed handshakes
and old-firmware fallback. Native tests cover the actual Android alarm/service
boundary. The first native run 45626776225 compiled and ran 189 tests, with eight
failures caused by fixed-duration assertions ignoring 1-5 ms spent in the real
test callbacks. The second native run 45632329953 passed 188 of 190 cases,
exposing the same one-millisecond assumption in two SDK variants of the stale
alarm test. That last positive-duration equality is also replaced with exact
persisted-deadline and bracketed elapsed-clock checks. Original XML/logs are
retained; no arbitrary tolerance, retry budget or test scope is relaxed.

Evidence and operation receipts: `.cache/companion-control-20261125/`.
No local Flutter/Gradle build, phone/MCU operation or manual Cloudflare action.
Real long-idle recovery remains a phone observation, not a claim made by these
host tests. Verification needs no repeated firmware OTA.

## Original Observation

Owner export `.cc-connect/attachments/om_x100b7f58616800a0de1413efa656c4c/companion-diagnostics.zip`,
SHA-256 `708a90558ae2888cfc45ced87d619bad3d0261e740b23da8217d7c443fd128d7`,
contains 3535 contiguous records. Export truncation, pruning, drops and I/O
errors are zero; buffered process-death loss remains possible. All times below
are 2026-11-25 Asia/Shanghai.

- 05:35:26.507: four-attempt window ends and retry is due at 06:35:26.507.
- No recorded recovery until a new background process at 19:10:56.951.
- OS exit history reports low-memory termination at 14:33:06.615, AFTER the
  missed deadline. That kill does not explain the earlier missed execution.
- Recovery, actual CONTROL_READY and MCU notification precede UI creation.
- The export does not identify the installed App build or contain OS Doze/job
  state. The initial cause is not conclusively attributed to an OEM or Doze.

## Research And Design

Read online on 2026-11-25:

- https://developer.android.com/reference/android/os/Handler
  documents the additional deep-sleep delay of uptime-based callbacks.
- https://developer.android.com/training/monitoring-device-state/doze-standby
  documents deferred jobs/WorkManager and idle-allowed alarm rate limits.
- https://developer.android.com/develop/connectivity/bluetooth/ble/background
  recommends companion presence or filtered PendingIntent scans for a dead
  process, not endless periodic scans. Existing companion integration is reused.
- https://developer.android.com/develop/background-work/services/alarms
  documents process-independent alarms, inexact delivery and reboot rearming.
- https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start
  separates alarm delivery from permission to start a connectedDevice service.
- https://stackoverflow.com/questions/67166985/android-ble-automatic-reconnections-after-pairing
  is related experience, not proof of this phone's cause or a modern guarantee
  that a foreground service/autoConnect survives process death.

Preserve four connection attempts per window, capped 60-minute exponential
backoff, existing explicit foreground/manual/presence wake semantics, association
and permission guards, single OTA ownership and update cache/quota policies.
Add one idle-allowed elapsed-realtime WAKEUP alarm per cooldown. No exact-alarm
permission, permanent wake lock, automatic UI opening or new periodic scan.
Persist and fence the deadline by boot, configuration revision, device and
generation. Reconcile after boot/package/radio restoration, reject stale and
duplicate deliveries, and cancel on success/disable/association loss.
Normal process teardown must not cancel an otherwise valid cooldown alarm.

Record requested/actual wake times and lateness, presence registration and
callbacks, and sanitized scheduling/start failures. Never log a Bluetooth
address, token or exception message. A requested wake is not an actual link.

## Verification Plan

Existing native Service/integration suites will cover elapsed-time cooldown,
process recreation, stale generations, duplicate wake sources, cancellation,
boot reconciliation, permission failures and unchanged retry/wake-lock limits.
Use the existing development-only Actions workflow, full dual-host checks and
its explicit native-test/debug-APK inputs. No local Flutter/Gradle builds.
Real screen-off/Doze and OS-reclamation verification remains separate and is not
established by Robolectric, a successful alarm API call or a debug APK. No OTA
is required for that later recovery observation; do not replay an old upgrade.

## Work Boundaries

All selected outputs stay under the project. The seven pre-existing modified
documents and unrelated MCU work are preserved. Only scoped progress additions
are made to the primary board; development source is isolated in the worktree.
The initially empty no-checkout index was populated using the configured sparse
rules before editing; it is not a source deletion or a cleanup of old evidence.
No new agent, device operation, release, deployment or main merge is authorized
by this development self-test route.
