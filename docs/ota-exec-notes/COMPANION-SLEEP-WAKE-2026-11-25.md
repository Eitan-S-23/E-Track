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

## Long-Idle Failure And Deadline Repair (2026-11-26)

Task: COMPANION-IDLE-20261126, IN_PROGRESS, not a phone-verified repair.
Base: `5916e3145b925f8560d4e91ac82a83e3eba1a4bf`; isolated sparse worktree
`.worktrees/companion-idle-20261126`, branch `dev/flutter/companion-idle-20261126`.
In the earlier diagnosis window, the owner authorizes USB diagnosis and explicitly
releases the existing 5037 ADB owner. That exact instance is stopped once; the private 5048 owner is
closed and the existing ADB key remains unchanged. No App launch/check, Bluetooth
toggle, installation, data clearing, OTA, backend mutation or new agent occurs.

Passive capture `phone-02` confirms Android 13/API 33, installed original
1.0.96+122 and APK SHA-256
`20b83967b98cbf44229dfa4926e27217dbd16e2382ee7d8179b2cd86cfb70fa9`.
It retains 4,843 native records and scoped AlarmManager/JobScheduler, service,
process-exit and association observations. The owner had already opened the App
and performed manual checks. Current healthy GATT/control is not proof of the
earlier background interval. OS history confirms low-memory/cleaner exits, but
the 15:08 exit cannot explain missing earlier callbacks. The association and
battery exemption are present; the export/system snapshot does not prove an OEM
denial or identify why the earlier alarm was not delivered.

Confirmed source gaps: connected-owner recovery discards `checkPending`; the
normal twelve-hour check deadline is not a process-independent native wake;
`CHECK_TOO_SOON` loses the returned deadline and is presented as failure.
Repair keeps one persisted, fenced check alarm separate from BLE cooldown, drains
pending checks through the same runtime, and lets the existing heartbeat/job
claim an overdue check if its alarm was missed. Exact idle-allowed alarms are
used only when Android already allows them, otherwise the inexact mode is
reported; no new permission, permanent lock or UI autolaunch is added.
Server/local automatic cooldowns become explicit waiting deadlines, without
advancing successful-check markers. Four BLE attempts, capped one-hour backoff,
independent App/MCU budgets, the deferred 24-hour preparation policy, offer
deduplication, explicit consent and single OTA ownership remain unchanged.

Development validation is required on both hosts, plus native regression tests
and debug APK compilation; no local Flutter/Gradle build. Real acceptance needs
the repaired original-signed App on this phone and a non-charging long-idle
window, including device absence beyond the maximum cooldown, process recovery,
and a connected device's request without opening the firmware page. Observe the
actual due/callback/link/check/offer timeline; no repeated successful OTA is
needed. A green CI result does not close that phone observation.
All selected evidence and adapters are under `.cache/companion-idle-20261126/`.
Primary board delivery and formal version/main integration remain separate;
unrelated pending documents and concurrent MCU work are preserved.

### Development Continuation And Original Failures

Validated development source before the formal delivery below:
`0eba2b992b3792e49de1c3ea5e3d8ca7f9d6ab38` on
`dev/flutter/companion-idle-20261126`. Git receipts
`git-04` and `git-05` verify the exact development pushes, unchanged primary
index/main and clean task worktree. Checks-only run `45849366803` passes both
hosts; full/native/debug-APK run `45849693985` also passes both hosts. It observes
Linux 1084 passed/16 skipped/0 failed, Windows 1032/68/0, eight candidate cases
per host and all 225 native cases (24 OTA Service, 56 Companion Service, 139
integration, six GATT plugin). Actual SDK: Flutter 3.47.9, framework revision
`c197ca5199e9ee5661e865596c9c07294dfab51c`, Dart 3.13.7. No formal original-signed
APK, Windows EXE, candidate or installation is implied by either development run.

Complete original host archives are retained and digest-verified: Linux artifact
15134067539 in `artifact-03`, SHA-256
`42e5cfecf92091134b88eb1e3e90b8cafedd2f2f68bcd10ae9c264196278a1ed`;
Windows artifact 15133716277 in `artifact-04`, SHA-256
`993d17d8e1e5e2f00fc18b49a7cdb14949380bd365e9dcedb62c8c971263be6b`.
Full job logs are in `logs-04`. Raw debug build/native/verifier logs retain
12/35/4 warning-prefixed lines and zero error-prefixed lines, including toolchain,
SDK/plugin and deprecated test API messages. No warning is suppressed or
unrelated toolchain upgrade bundled into this repair.

Collected debug APK metadata: application ID `com.wen.gaia.gaia`, 133669931
bytes, SHA-256 `61982d0d66a4a55ed32f0e158156f44278b4b74bb29d0b41cdc1ff26fa1a15fa`.
Signature verification passes V2 with one development signer. This is not the
original release signer; the large debug APK is not downloaded or installed.
The complete logs and metadata, not an invented local APK path, are the receipts.

The final runtime batch preserves `CHECK_QUOTA_EXCEEDED.resetsAt` as well as
`CHECK_TOO_SOON.nextCheckAt`. A genuine automatic request failure stays failed
and unfinished, but retains a validated server retry deadline or a one-hour
fallback. Earlier recovery wakes cannot repeatedly spend requests; after expiry
the check runs again. Valid prepared-cache reuse clears an obsolete retry marker
without advancing successful-query timestamps or changing the deferred cache
policy. App and manual budgets are not consumed by these local waiting paths.

Run `45839079010`, source `9e5b010d`, compiles the App but cannot compile three
new test calls: Robolectric 4.14.1 exposes `setCanScheduleExactAlarms` as a static
method, not an instance method. Those calls are corrected without changing the
dependency or weakening exact-permission/race/fallback assertions. Full originals
are in `logs-02`.

Run `45845163312`, source `613eb5e3`, passes all Flutter tests: Linux
1084 passed/16 skipped/0 failed, Windows 1032/68/0, plus eight candidate cases
on each host. Native tests execute 225 cases, with 224 passing and one failed
heartbeat-after-sleep fixture. The original XML is retained and SHA-256 verified
in `artifact-02`; full logs are in `logs-03`. In the actual 4.14.1 library,
`ShadowPausedLooper.idleFor` calls `setCurrentTimeMillis`, which sets elapsed time
equal to uptime and discards a preceding `simulateDeepSleep`. The corrected
fixture advances both clocks with shadowed `SystemClock.sleep`, then drains real
due Handler work with `idle`. It retains the original dispatch/pending-work
assertions and adds explicit uptime/elapsed invariants; production is unchanged
from `613eb5e3`. This is not evidence that the phone's missed wake was a fixture
or OEM failure. Library sources: `ShadowPausedSystemClock.java` and
`ShadowPausedLooper.java` under tag `robolectric-4.14.1` in the Robolectric repo.

### Authorized Main And Candidate Delivery (2026-11-27)

MAIN_DELIVERED / CANDIDATE_DELIVERED / PHONE_VERIFICATION_NOT_RUN. The owner's
latest authorization covers the main merge/push, App `1.0.97+123`, formal build
and observation of automatic candidate registration only. Manual Cloudflare
publication/configuration/deployment/deltas, phone update and real device tests
remain owner actions. This delivery performs no phone launch/check/install,
Bluetooth toggle, data clearing, OTA, MCU operation or independent acceptance.

The validated source is fast-forwarded locally from main `5916e314`, then only
the pubspec version is committed. There is one versioned main push, not an
intermediate unversioned push. Exact App source:
`a63c8a5df0154ae17131a76bdc720982b5b3d5fb`. Its App difference from `0eba2b99` is
only `1.0.96+122 -> 1.0.97+123`; no MCU/backend product input or signing policy
changes. Fresh `reservations-02` reads all 135 Trace Releases and 135 tags,
including drafts, before the edit. Existing RSA SSH is verified as `Eitan-S-23`
under SYSTEM with repository dry-run; no user login, key/trust/configuration
change or credential copy occurs. `main-prepare-01`, `main-merge-01` and
`main-publish-01` retain the scope, parent, push and exact document-preservation
receipts. One read-only remote freshness failure is followed by a successful
fresh check, without repeating a push, dispatch or build.

Formal source CI [45859072310](https://github.com/Eitan-S-23/E-Track/actions/runs/45859072310)
and original-signer Trace [45859365606](https://github.com/Eitan-S-23/Trace/actions/runs/45859365606)
both succeed. Source checks/app pass and firmware skips; Trace admission,
Windows and Android pass, with strict analysis/tests and actual APK/EXE builds.
Trace executor `12ff41fc11eb4920ab32d69ae0f7e1cc095f996e` is the workflow source,
not the App source. The request binds the exact App SHA and parent run above.
No successful development run or package is repeated to obtain cleaner logs.

The original-signed APK is `com.wen.gaia.gaia`, `1.0.97+123`, 49669709 bytes,
SHA-256 `72205b6c5a19c100b5e688faa3dbb988f5fe4f735f572c6a4d8895bbb55a31b0`.
Native inspection verifies the unchanged original signer, both ARM libraries,
original backend, BLE V2-only profile and inventory. APK and manifest pass R2
full-byte verification. Manifest SHA-256 is
`324280d7ed6c24849e9c964041be1ecc702e5fcf4b2ce1ae1238f654dff8ebd5`.
Automatic registration returns `ok=true`, `rel_trace_android_v1_0_97`,
`idempotent=false`, with `channelPublished=false` at CI delivery and no patches.
The complete original logs are retained in `logs-05` / `logs-06`, the source-bound
completion receipt in `deliver-01`, and checked metadata/digests in `inspection-01`.
No additional APK download or installation is performed by this delivery.

Raw warning-prefixed counts: Android APK build 10, Windows build zero; zero
error-prefixed build lines. Android wrapper preparation also retains 11 warnings,
and each host's widget tests retain one warning. These are not suppressed or
reported as a clean toolchain. Formal machine test events are retained in full;
the exact separately parsed development counts remain in the earlier section.
Original failures, archives and test assertions stay intact. The actual phone's
missed-wake cause remains unproven; these build results do not establish a
phone-level repair or reopen completed OTA observations.

Only the new task section, current index paragraph and the board's task/session
rows are selected for record delivery. `records-snapshot-01` pins the exact
unrelated bytes, including the original board SHA-256
`b98abd7b4ed83d7cc51cb902bc3fdcb9fd56ea49466715a82b510378b75f0c0b`.
The remaining pending documents and other MCU work are not staged or reverted.

### Prepared Passive Phone Verification Route

1. Main delivery and the original-signed `1.0.97+123` candidate are complete as
   recorded above. The owner publishes the candidate and updates the phone;
   neither is performed automatically by this task. Do not replace it with a
   debug APK or repeat a successful OTA to test background recovery.
2. Before inviting a device window, bind the actual formal source/version/APK
   SHA-256 and recheck USB ownership. The existing passive `phone_probe.py` now
   accepts `--expected-version`, `--expected-code` and `--expected-apk-sha256`,
   rejects a mismatched installed package and retains its private 5048 server,
   read-only command allowlist, bounded lifetime and closure checks. CLI help is
   checked without starting ADB; earlier phone receipts remain unchanged.
3. Capture a baseline of actual check/retry deadlines, check/recovery alarm mode
   and exact capability, association, permission, radio, runtime/GATT/control
   and relevant manual-query/cache markers. Do not clear data, offers or dedup
   to fabricate eligibility. A normal connection is not a new server check.
4. Observe on normal battery/non-charging conditions with Bluetooth on, without
   opening the App, manually checking or toggling Bluetooth. For the absence
   scenario, wait beyond the actual recorded cooldown deadline; do not assume
   any ninety-minute interval has reached the capped one-hour backoff. For a
   scheduled query, use its actual due time and explain cache/local/server waits.
5. Retrieve persistent journal pages and system/exit/alarm/job observations
   passively. USB reconnection can itself wake the phone: only records preceding
   that reconnection establish unattended recovery. Separate requested wake,
   actual callback/process/runtime, link/identity/control, HTTP/cache outcome and
   offer acknowledgement/dedup; missing callbacks or records remain explicit.
6. Separately verify a connected device's CHECK after long idle without opening
   the firmware page. No repeat OTA, forced-stop simulation, induced data loss or
   extra firmware build is required. No physical window has been opened by this
   continuation, and no phone-level PASS is claimed.

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
