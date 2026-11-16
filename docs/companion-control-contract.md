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
  API 31+ presence observation and persisted JobScheduler jobs can request a
  connectedDevice foreground service. Neither association nor start-service
  return is execution ownership: a live Dart handshake and heartbeat are required.
- The default metadata interval is 12 hours, configurable to 6/12/24 hours.
  A 15-minute recovery job considers persisted failures/checkPending. Connection
  failures back off from 2 minutes to at most 60 minutes. No exact alarm or boot
  Activity launch is used. Boot/package-replaced receivers restore scheduling.
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
5. The MCU checks the displayed offer snapshot again at activation. Motion
   (valid GPS speed >=3 km/h) and battery below 30% without charging disallow
   installation. An open GPX recording, including pause with the file still open,
   also blocks the modal's install action and automatic prompt until closed.
   Automatic prompts are limited to stable Dialplate, MainMenu
   and SystemInfos, not navigation or SD-import screens. Later never starts OTA.
6. App consumes CHOICE before awaits, then rechecks address, connection generation,
   full base identity, refreshed metadata, target/package hashes and expiry.
   The same consent is checked again after asynchronous setup immediately before
   transport begins. Reconnect, changed asset, stale callback or consumed offer
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
