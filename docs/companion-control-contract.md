# E-Track Companion Control Revision 1

## Scope And Authority

APP-COMPANION-01 adds an idle-text control plane and a separate acknowledged
Android companion entry. It does not change frozen BLE binary opcodes, frames,
durable accounting, package validation, boot safety or historical acceptance.
This is a product implementation contract, not a claim of hardware acceptance.
The existing foreground-only `acquire(taskKey)` contract remains unchanged.

## Runtime And Scheduling

- One associated E-Track main controller, one cached Flutter engine and one
  OtaService own the gateway. Pages attach to them rather than creating senders.
- Android API 26+ uses an explicit foreground CompanionDeviceManager chooser.
  Normalize the selected MAC to uppercase at ScanFilter's OS boundary; persisted
  address keys remain lowercase. Request construction and association submission
  share the same failure cleanup so a rejected request cannot occupy the slot.
  API 31+ presence observation and persisted JobScheduler jobs can request a
  connectedDevice foreground service. Neither association nor start-service
  return is execution ownership: a live Dart handshake and heartbeat are required.
- The default metadata interval is 12 hours, configurable to 6/12/24 hours.
  A 15-minute recovery job considers persisted failures/checkPending. Connection
  recovery first attempts the saved address immediately. Transient offline or
  missing-identity results keep the acknowledged service/engine and retry after
  2, 4 and 8 seconds, within one 60-second monotonic scheduling window. Duplicate
  failures do not stack timers; success resets the budget, and a fresh wake
  replaces a pending timer without extending it. An in-flight bounded connection
  or INFO operation may settle after the scheduling window, not be interrupted
  by a second owner. Only after exhaustion do failures back off from 2 minutes to
  at most 60 minutes. Later disconnections reacquire a bounded CPU wake lock;
  success/stop releases it. Authority/revision/runtime loss stops recovery, and
  an active OTA task is never interrupted by a connection retry.
  Boot/package replacement and Bluetooth STATE_ON request immediate recovery of
  an existing enabled association, including after a previous offline backoff.
  They do not create installation consent or clear persisted failures/pending work. Boot radio initialization
  retains its separate two-minute bounded startup job. No exact alarm or Activity
  launch is used, and off/turning/unrelated broadcasts do not start a runtime.
- Metadata can use any network. Default automatic package download requires an
  unmetered network; a user setting can relax that policy. A valid immutable
  cached package may be reused only after current device/metadata checks.
  A persisted ready-package marker causes a recheck/renotification on a new
  connection even inside the long interval; SHOWN suppresses repeat popups.
  Legacy endpoints without CAPS stop retrying a successfully prepared package
  every recovery tick and keep their explicit App route.
- `acquireCompanion(taskKey, runtimeId)` is an additive entry, not a weakened
  `acquire`. It requires live companion ownership, matching runtime/device token,
  current GATT connection, confirmed association, visible notification capability
  and Bluetooth permissions. Missing admission refuses background work; foreground
  admission and the existing safe pause/recovery path are retained.
- Native `state` rejection invalidates the Dart owner. Lost/revoked owners stop
  background scans, discard consent and stop cancellable owned work. Applying is
  not falsely advertised as cancellable. A service does not guarantee survival
  of force-stop, revoked permissions, Bluetooth-off or OEM process restrictions.
  Each query/control/download/transfer records its companion runtime on the
  existing exclusive owner. `releaseCompanionTask(runtimeId)` cancels that
  runtime's INFO/latest work even though the UI cancel button is unavailable for
  queries; it never cancels another runtime or a foreground task. END/apply waits
  for the existing owner to finish before connection cleanup. Cleanup has a
  five-minute observation deadline and reports unconfirmed state on timeout,
  rather than disconnecting during apply. A new wake cannot replace an owner
  while its stop is settling. Temporary adapter initialization failure does not
  permanently block native readiness or a later retry.
  A failed foreground INFO that clears the shared device identity triggers
  connection/control re-establishment after that owner settles, without waiting
  for the long HTTP interval. It cannot reuse the old session/consent.
- On Android 12+, saved monitored sensor advertisements may be collected for
  8 seconds per minute while a live companion owner is confirmed. The existing
  parser/database are reused; headless startup loads at most 300 recent records
  per device, not the full history. Old UI scan timers cannot start background
  scans outside this lease. Stale advertisements are not new samples. Database
  failures retain the bounded pending buffer and expose failure rather than
  silently discarding it. These are sampled observations, not lossless continuous
  recording. Existing alert dialogs/audio remain foreground UI capabilities.
- Android 8-11 companion connection/checking is separate from sensor background
  scanning: sensor scans fall back to foreground use without mandatory background
  location. iOS/Windows retain the existing foreground OTA path; no Android
  reliability result is extrapolated to those platforms or untested vendors.

## Wire Encoding

`!ETC1|KIND|SESSION|REQUEST[|FIELD...]*hhhh\n`

ASCII only, at most 320 bytes including LF; no spaces, CR, escaping or embedded
separators. `hhhh` is four lowercase hex digits of CRC-16/CCITT-FALSE over all
bytes before `*`, including `!ETC1`. Polynomial 0x1021, init 0xffff, no reflection,
no final xor; `123456789` gives 0x29b1. This is corruption detection, not a new
authentication scheme. Existing trusted device association and signed/validated
firmware checks remain necessary. No secret or signed URL appears on this plane.

SESSION and OFFER_ID are independent 16-byte random App nonces encoded as 32
lowercase hex digits. REQUEST is canonical decimal uint32 without leading zeros;
zero is reserved for App-initiated operations. MCU requests increment from 1
within each negotiated session. Full package/target hashes are 64 lowercase hex
digits, never truncated. Version codes are decimal 1..2100000000.

| Kind | Direction | Fields And Meaning |
| --- | --- | --- |
| HELLO | App -> MCU | No fields, request=0; establishes a new connection session. |
| CAPS | MCU -> App | `1`, request=0; supports revision 1. |
| CHECK | MCU -> App | No fields, nonzero request; check now, not next periodic interval. |
| STATE | App -> MCU | One code from the state table below, with the relevant request. |
| OFFER | App -> MCU | OFFER_ID, versionCode, packageSHA256, targetRawSHA256, prompt `0`/`1`. Sent only for a verified package. |
| SEEN | MCU -> App | OFFER_ID, packageSHA256; storage receipt, not proof the user saw it. |
| SHOWN | MCU -> App | OFFER_ID, packageSHA256; emitted only when actually presented. |
| CHOICE | MCU -> App | OFFER_ID, versionCode, packageSHA256, `NOW` or `LATER`; no automatic consent. |

States: CHECKING, NO_UPDATE, DOWNLOADING, VERIFYING, DEFERRED, BUSY, NO_NETWORK,
PHONE_REQUIRED, INCOMPATIBLE, FAILED, STARTING, COMPLETE, WAIT_WIFI.
Missing/error latest responses are never NO_UPDATE. COMPLETE, when used, requires
new-connection target version AND full raw SHA verification, not END ACK.

## Correlation And Safety

1. App connects and verifies real GET_INFO before HELLO. No CAPS within 3 seconds
   means control unsupported: keep the explicit foreground App route, do not
   assume a legacy MCU supports the button/prompt protocol.
2. MCU CHECK gets a 10-second initial response window. CHECKING acknowledgement
   permits 120 seconds; DOWNLOADING/VERIFYING permits 600 seconds. Modular uint32
   elapsed time handles tick wrap. Unreachable phone or timeout says open/connect
   the phone, not that firmware is current.
   STARTING also has a 120-second deadline, so refused background admission cannot
   strand the MCU menu. Leaving a binary session restores a retryable phone-needed
   state, never an invented upgrade-success result.
3. A device request remains distinct from request=0. An App periodic operation
   cannot overwrite an in-flight MCU request; a later idle periodic operation
   correctly resets request correlation to zero. Overlapping App work coalesces
   through the sole owner; at most one pending device check is retained.
4. App sends OFFER at most three times, waiting at most 2 seconds per storage
   receipt. Exact retransmission re-acknowledges without extending the MCU's
   5-minute offer validity or rearming consumed consent. Unknown schemas, fields,
   CRC failures, nonce/hash/version/request mismatches fail closed.
5. The MCU captures the visible offer at PRESSED and checks that immutable
   snapshot again at CLICKED, including a local offer revision. Any intervening
   replacement (including A-B-A), checking state, expiry or lost interaction
   cancels the press; a replacement requires a new press after display. Exact
   retransmission does not advance the revision. Per the owner's 2026-11-19
   decision, GPS motion does not gate installation, including simulated motion.
   Battery below 30% without charging disallows installation. An open GPX
   recording, including pause with the file still open,
   also blocks the modal's install action and automatic prompt until closed.
   The same recording/power policy gates real BEGIN/BEGIN2 overlay
   acquisition. Successful NOW reserves installation for at most 120 seconds;
   later STATE messages cannot extend that reservation. New recording/resume is
   refused during this pending interval and during binary ownership, with failure
   propagated through the recorder model so the dialplate cannot display REC.
   Timeout, failure, a new offer/session or binary takeover retires the reservation.
   Automatic prompts are limited to stable Dialplate, MainMenu
   and SystemInfos, not navigation or SD-import screens. Later never starts OTA.
6. App consumes CHOICE before awaits, then rechecks address, connection generation,
   full base identity, refreshed metadata, target/package hashes and expiry.
   The same consent is checked again after asynchronous setup and under the
   transport writer lock, after capability negotiation, queueing and MTU waits,
   immediately before its first BEGIN/BEGIN2 platform write. The gate travels
   through the channel and BluetoothService, including baseline mobile service
   discovery; entering `writeChunk` is not dispatch. An initial BEGIN
   paused during setup yields the writer so the existing INFO recovery can run;
   admission is checked only after resume, not while holding a paused writer.
   Reconnect, changed asset, stale callback or consumed offer
   cannot authorize another upgrade. Final success still belongs to existing
   reboot/reconnect GET_INFO verification.
7. Text and binary queries/transfers share the OtaService exclusive owner and
   device-scoped serial writer/late-write quarantine. Control writes do not create
   a second GATT sender or replace the idle notification receiver. Incoming text
   is discarded during binary ownership. MCU uses the existing idle text sink;
   active/ISR binary sessions suppress control RX/TX. Baud-console experiments
   explicitly disable companion control rather than mixing console bytes.
8. Short-click/click event pairs act once. The modal opens/closes asynchronously,
   saves each encoder/keypad's actual group and focus, excludes disabled buttons
   and restores ownership on close. The online entry is separate from filesystem
   paths and remains available without an SD directory.

## Compatibility Inventory

At MCU startup, the production and fixed candidate profiles query the real
module name using `AT+NAME?`. If it is not `E-Track` (or the query times out),
one `AT+NAME=E-Track` request follows. Only an exact OK acknowledges the write;
silence, malformed replies, rejected or partial writes remain reported failures.
Each transmit wait is at most 50 ms and each reply window at most 300 ms; stale
input draining is also bounded. A matching name skips the persistent write.
`Doc/ble.pdf` specifies that the name takes effect after reboot, so naming runs
before the existing one-shot `AT+REBOOT=1`, not after it. This does not add another
reset or change MAC, UUIDs, baud, binding, binary protocol or the legacy text
marker. Baud experiments still suppress automatic naming/reset. Module failures
do not strand boot; RTT reports the outcome. Live advertisement/platform names
supersede stored legacy names in the App without changing device identity.

Development tests cover these policies; real radio timing and wireless upgrade
behavior still require owner testing, not a phone USB prerequisite.

| Device | Current Implementation |
| --- | --- |
| E-Track AT32F435 main controller | Existing GET_INFO/full/delta OTA plus this additive control protocol. |
| Stored electrical sensor advertisements | Existing manufacturer-data parser and local data persistence; no firmware identity/upgrade protocol defined. |
| Other generic discovered BLE peripherals | Discovery/category display is not OTA capability. Unsupported for automatic firmware updates until a real model/identity/transport contract is supplied. |

No generic peripheral is reported as upgradable merely because it has Bluetooth.
The onboarding page explicitly identifies the associated target as the E-Track
main controller; missing peripheral protocols remain a recorded capability gap.

## Verification Oracles

- `tests/ota/test_companion_control.py` compiles the production header, testing
  CRC, rejection, timeouts/wrap, offer expiry/replay, displayed consent and binary
  exclusion. The Dart protocol suite checks the same encoding and field bounds.
- App integration tests must prove no BEGIN on stale/expired consent, including
  expiration during GET_INFO, and no replacement CCCD during an idle control write.
- `test/companion/companion_runtime_test.dart` drives native channel events into
  the actual coordinator with injected BLE/OTA dependencies: interval bypass,
  pending-manual coalescing, failure versus no-update, verified offers, reconnect
  suppression, one-shot consent and scoped stop. The real OtaService integration
  suite separately proves own-query cancellation, foreign-query preservation,
  late HTTP rejection and uninterrupted END/target verification on retirement.
- CompanionServiceTest exercises real Android Service/PowerManager lifecycle at
  an injected execution boundary. Native admission, platform chooser/permissions,
  real GATT, boot/lock/process recreation and firmware installation still need
  original device observations. Robolectric is not hardware acceptance.
- The canonical A1-A6 criteria and remaining observations stay in the single
  APP-COMPANION-01 Spec/card. P3/P4 originals are preserved, not rewritten.

## Delayed-Event Admission Contracts

### Scope And Signatures

AC01-R01..R05 repair delayed UI/connection/transport admission and Darwin
notification compatibility. The binary wire contract and Android foreground-only
legacy entry are unchanged; this section is not independent acceptance.

- `HAL::CompanionSameOffer(first, second) -> bool`: both snapshots must have an
  offer, neither may be checking; compare session, request, offer nonce, version,
  full package/target hashes and local `offerRevision`. The revision is not sent
  over BLE. `Control::Matches` and the modal use this single comparison.
- `HAL::BT_CompanionInstallPending() -> bool`: includes the bounded pending NOW
  reservation and actual binary ownership. It gates recorder START/CONTINUE,
  not STOP; `RecorderCommand` returns refusal to its UI caller.
- `ble_env_overlay_acquire() -> 0/1`: before acquiring the shared overlay, re-read
  open GPX, valid GPS motion and current power. Unsafe state returns existing
  acquisition failure without changing opcodes or aborting an active apply.
- `OtaBleTransport(beforeInitialBegin: void Function()?)`: immutable synchronous
  guard checked at the first BEGIN/BEGIN2 platform write. The service supplies
  its original consent/owner check; subsequent DATA, recovery and END/apply do
  not re-expire that consent.
- `OtaBleChannel.writeChunk(chunk, admission: OtaWriteAdmission?)` and
  `BluetoothService.writeOtaCharacteristicByAddress(..., admission: ...)` forward
  the same one-chunk gate through asynchronous preparation. `dispatch()` executes
  it synchronously after the last project-owned wait and before `ch.write()` or
  the Windows adapter call, with no intervening await. Consumption is recorded
  only there. A rejected/retired gate cannot be reused, and timeout retires a
  still-pending discovery before releasing its writer. Pre-dispatch rejection
  preserves the original exception and GATT binding; it is not a partial write,
  so it neither poisons the channel nor sends cleanup ABORT/resync for an
  unstarted guarded transfer. Actual dispatched-write failures retain quarantine.
- `_ControlBinding = (address, session, generation, epoch)`: attachment flights
  are keyed by the captured binding, not just a runtime epoch. All asynchronous
  publication points and control-operation continuations recheck it. Stale
  listener errors/bytes cannot reset the current decoder or clear dirty state.
- `requestNotificationPermission() -> Future<bool?>`: iOS calls the Darwin
  implementation and returns its actual grant/denial/unknown result. Darwin
  initialization retains the prior alert/badge/sound request; Android
  initialization still does not request permission automatically.

### Validation And Error Matrix

| Case | Required Result |
| --- | --- |
| Unchanged displayed offer, fresh press | One CHOICE; SHORT_CLICKED/CLICKED duplicates do not repeat it. |
| Offer replacement, checking, expiry or lost focus during press | Zero NOW for the replacement; explicit new press required. |
| Exact OFFER retransmission during press | Same binding and original expiry; one valid choice remains possible. |
| Recording active or paused-open, new motion or insufficient power at BEGIN | No overlay acquisition; pending reservation is released on rejection. |
| Recorder start/resume during NOW reservation or binary ownership | Existing unsupported-request result, no GPX/TrackFilter start and no false REC UI. |
| Reservation timeout, failed send, failure/new session/new offer | No leaked recording lock; remote STARTING does not renew the original lease. |
| Consent expires during CAPS, fallback, pause/queue/MTU or baseline writer discovery | STALE_DEVICE_CONSENT before any initial BEGIN chunk; zero new platform writes, including cleanup. |
| Owner retires during first-BEGIN writer discovery | No platform write/BEGIN; existing cancellation owns the terminal result. |
| Initial preparation times out, then discovery completes late | The retired gate refuses dispatch; no late BEGIN or false partial-frame quarantine. |
| Consent valid at initial dispatch, expires afterward | Existing transfer/apply safety and final identity verification continue unchanged. |
| Old attachment discovery/subscription completes after S2 | Only S2 owns its listener; CHECK succeeds without another disconnect. |
| Old metadata operation completes after invalidation | No old offer/state is published into the new control session. |
| iOS first authorization or explicit retry | Preserve request entry and return the actual native result, never unconditional true. |

### Tests And Correct Pattern

`test_companion_control.py` covers all snapshot fields/revision, retransmission
and reservation cleanup/wrap. `test_companion_safety.py` extracts real modal,
HAL admission, recorder and dialplate methods; the two original unsafe boundaries
must fail their corresponding oracles, while the candidate passes. The LVGL,
GPS, power and storage edges are host stubs, not physical-device observations.

The Dart service regressions delay CAPS and v1 fallback across consent expiry;
transport tests delay MTU and queued INFO writes, and prove that a paused initial
BEGIN releases the writer for INFO recovery before its final admission check.
They require zero dispatched BEGIN bytes or a single successful admission.
The service suite also runs the actual BluetoothService writer, discovery and
subscription code with fake device/characteristic boundaries. It delays the
last uncached discovery for v1 and v2, covers expiry/owner retirement and valid
consent, and delays an admitted write's completion across expiry without aborting
the transfer or final identity verification. Cache tests cover guard-error
propagation with/without statistics and preserve a valid reused GATT binding.
Runtime tests cross reconnect during discovery/subscription
in baseline/reuse dependency modes and preserve partial new-session input.
Notification tests assert Darwin grant/deny/retry and no implicit Android request.

Wrong: compare the newly refreshed display with itself, or check a mutable
current link after awaiting old work. Correct: capture the binding at interaction
or operation start, recheck it at the side-effect boundary and discard old work
without touching its successor. Baseline foreground OTA remains supported;
these guards do not grant background ownership or change frozen wire semantics.

## Permission And Headless Coverage Boundaries

T01/T02 use the existing runtime and storage paths, not parallel implementations.
Optional dependencies preserve their production defaults:

- `CompanionSetupPage(requiredBluetoothPermissions: Future<List<Permission>> Function()?)`
  injects only OS permission-list discovery. Status reads, user requests, settings
  return, refresh epochs and navigation remain the real page implementation.
- `CompanionRuntime(checkBluetoothPermissions: Future<bool> Function()?)` injects
  the OS permission query, not telemetry admission or native-owner correlation.
- `BluetoothService(adapter: BluetoothAdapter?, companionClockMs: int Function()?)`
  provides the radio edge and monotonic clock. Initialization, scan leases,
  listeners, reconnect, identity and writes still execute production methods.
  `usesAndroidLifecycle` is a test-visible platform discriminator; lifecycle
  state itself is read from the real WidgetsBinding.
- `MonitorController(database: DatabaseService?, loadHistory: false)` uses a real
  DatabaseService whose test-only `forDatabase(Database)` constructor substitutes
  the SQLite driver. Parser, history limit, pending queue, deduplication, batch
  transaction and failure retention are not overridden. Its test-visible
  `usesAndroidLifecycle` discriminator also retains the OS default in production.

| Case | Required Oracle |
| --- | --- |
| Setup entry, skip, denied or permanent permission | No unsolicited request or enable; unrelated navigation remains usable. |
| Settings open/return, revocation or disabled notification channel | Re-read actual status; no fabricated grant or live owner; stale refresh cannot overwrite the successor. |
| CDM chooser cancellation/timeout/late callback | No new persisted target or background opt-in; modern result requires matching system association. |
| Boot/package replacement, pending check and retry backoff | Restore persisted jobs only; no Activity launch or claim of completed check/engine ownership. |
| Headless service start, UI return and engine loss/recovery | Ready/wake/heartbeat and real GATT admission remain necessary; reuse one engine, reject old state. |
| No page, wrong owner/revision, revoked permission or unsupported sensor background API | Collect only through the acknowledged bounded lease; no foreground timer bypass. |
| SQLite batch failure or partial device success | Keep uncommitted samples, report failure, serialize retries, and do not replay already committed device batches. |

`companion_setup_page_test.dart` drives the page using method-channel permission
and native-boundary responses. `companion_telemetry_test.dart` drives actual
Runtime/BluetoothService/BleController/MonitorController/DatabaseService through
fake device/characteristic, adapter, permission and SQLite-driver edges without
mounting a page. The mobile-adapter scenarios execute on Linux and explicitly
skip Windows, rather than pretending a Windows adapter validates Android scans.
`CompanionIntegrationTest` runs the actual Android Bridge/Service/boot/job paths
on API 26/31/34, with OS and Flutter VM/embedding shadows only. The native runner
selects it explicitly alongside both existing service suites. None of these
host tests proves physical permission dialogs, actual Dart VM survival, radio
reliability, process recovery on an OEM phone, or whole-card acceptance.

The telemetry widget harness advances project timers in FakeAsync and separately
yields the root microtask queue with an empty `tester.runAsync` callback. Dart's
already-completed stream-cancellation future belongs to the root zone; repeatedly
pumping only fake time can starve real stream disposal and falsely leave the OTA
owner busy after a successful HELLO. Do not solve that fixture boundary by
extending deadlines, overriding runtime/stream disposal or running project work
outside the controlled clock. Preserve the first scenario error even when cleanup
also fails, and always retire controllers/registrations so one failure cannot
contaminate the next scenario.

Native host shadows disable call-through only for FlutterEngine, FlutterLoader
and DartExecutor. An outer Context constructor hook alone does not stop the
delegated FlutterEngine constructor from trying to load JNI. The explicit
embedding shadow methods still model engine count/liveness, method messages and
destruction callbacks; assert the cached engine exists immediately after the real
service starts. Project Bridge, Service, receiver, jobs and permission/GATT
admission must never be shadowed to avoid a missing native library in this test.
The Android 8-11 BluetoothManager shadow also routes its legacy direct-Binder
`getConnectedDevices` call through Robolectric's existing GATT-state store;
Android 12+ retains its framework delegation. This fills a stock OS-shadow gap,
not a replacement for CompanionBridge.gattConnected or its permission policy.
Native task fixtures include the real notification snapshot's required `label`;
a missing field must continue to fail service admission rather than be defaulted
by production code to satisfy the test.
