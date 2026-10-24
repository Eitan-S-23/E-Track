# P3-8 Recovery Observations

Product input remains 8ede0920 / 6ec6c5ce. No product fix or new APK is represented
by this record. D3A has one actual pre-END Bluetooth-off interruption, not a
successful OTA. Original sealed snapshot SHA-256:
606751ab1706a5a3e558ea461385f2b9f507c93812b654014fca657b1e200571.

## P38-RECOVERY-01: No General Adapter-On Reconnect

DECIDED, current capability gap; not yet attributed as a new P3-8 regression.
User observed no automatic connection after re-enabling Bluetooth. Native log
records adapterTurnOff/disconnected at 1792875350.145, followed by repeated
ota-chars-missing queries. The first later connect is at 1792875470.240, with
auto:false; connected follows at 1792875471.520. The user reports initiating that
connection manually. GET_INFO then succeeds at 1792875473.144.

bluetooth_service.dart:861 only updates adapter state and clears scan results
when off. Its mobile connectDevice at line 1321 makes one explicit connection;
the disconnected callback at line 1335 removes the device and invalidates the
link generation, with no reconnect scheduling. No autoConnect/general automatic
reconnect implementation was found in lib. The separate post-END reboot probe
is not a general adapter-on recovery facility.

Direction: if general reconnection is required, the Bluetooth connection owner
should implement bounded, exact-target reconnect after adapter-on. Never resume
old DATA from cached seq/session; reconnect and fresh identity/BEGIN durable
remain mandatory. Never automatically issue a new OTA after user cancellation
or an ambiguous outcome. Ownership/scope belongs to the implementation owner;
this independent acceptance session does not edit product code.

## P38-RECOVERY-02: Failed-State Recovery Entry

NEED_EVIDENCE for the complete user-visible path; concrete source gaps identified.
User reports that the upgrade UI disappeared after leaving and reconnecting.
The recorded earlier page shows an explicit device address but identity pending.
D3A terminal reason is FlutterBluePlusException/writeCharacteristic/adapter off;
ota_service.dart:1594 assigns phase=failed. ota_upgrade_page.dart:969 exposes
the direct transfer button only for readyToInstall or cancelled, not failed,
even if the verified firmware file remains available.

Additionally, the connection callback at ota_upgrade_page.dart:150 only starts a
read when currentAddress is null. A retained _attachedTaskAddress or explicit
connectedDevice keeps it non-null, while a failed terminal read has already
cleared _needsTaskReconcile before awaiting GET_INFO. The same target reconnect
can therefore be ignored until another page/lifecycle action initiates a read.
This is a code-path diagnosis, not a claim that every observed missing card had
that exact cause.

Smallest discriminating check: preserve the same PID and cached ETU, reopen the
existing firmware page without a new transfer, capture identity/readiness, and
check latest once if enabled. _checkLatestLocked restores readyToInstall for an
already verified matching asset (ota_service.dart:772). Success proves an
explicit manual recovery route, not automatic reconnection or transparent UI
recovery. Failure leaves the remaining D3B observation blocked by the page state.

Recommended implementation direction: react to reconnection of the retained exact
target, serialize fresh identity reconciliation, and expose an explicit retry
entry only for a compatible, verified retained package after a retryable terminal
failure. Preserve different-device rejection, cancellation/END guards, single
owner, fresh BEGIN/durable authority and no automatic transfer. Verify both
same-target reconnect and wrong-target/late-event negatives with real host tests
before requesting any new APK. Do not repeat D1/D2 to test a page-only fix.

No full P3-8 PASS or automatic-reconnect PASS is claimed. D2 acquired background,
33.830-second sleep, current notification return and cancellation have separate
originals; these observations are not erased by the recovery findings.
