# P3-4 Radio Policy Screening

Development only; no production selection or hardware speedup claim. The real
30244-to30245 predecessor succeeded with44.885462s transfer and26.478168s
END-to-identity. Three-second discovery deadlines worked but did not improve
overall reconnect time. Preserve the complete original result, including the
slower transfer. Retain confirmed30245 and the unchanged Boot.

## Requested Axes

Strict runtime schema4 adds two required booleans: `pauseScanDuringOta` and
`androidHighPriority`. Schemas1-3 retain their exact field sets and behavior.
Both new axes default off for old schemas and production. Schema4 stays FULL
only, with the existing reboot cadence, image, package and protocol gates.
One fixed-signer APK can therefore screen the four declared combinations by
changing an archived, pre-launch runtime configuration, not rebuilding per cell.

The finite development matrix is off/off, on/off, off/on and on/on, with legal
header-only successors and otherwise fixed921600/window28, MTU247 request,
without-response and2000/500ms reboot cadence. Prepare/admit each legal successor
from the actual confirmed preceding state. No automatic UI Start, no repeat for
lost host evidence, no reset/downgrade or Boot replacement. Screen before deciding
whether any repeat or reliability campaign is justified.

## Ownership Contracts

The optional scan gate serializes native start/stop work, separately retains
requested scanning, and suppresses watchdog restarts while any OTA lease exists.
An explicit stop, an expired original scan timeout or controller disposal prevents
restoration. Closing an older lease does not release a later lease. Acquisition
does not claim ready until an in-flight native start has settled and stop succeeds.

Android priority uses the lockfile-verified FlutterBluePlus1.35.5 API. Requests
are serialized per device and bound to both logical owner and connection
generation. Balance restoration skips a newer owner or disconnected/changed
generation. A successful request is not evidence of the negotiated connection
interval. Unsupported platforms fail that opted-in candidate before BEGIN.

OtaService obtains leases only after exact package/identity validation, checks
cancellation after readiness, and releases them on success, failure and cancel,
including runs without diagnostics. Readiness/cleanup waits are bounded to5s;
timeouts do not cancel or overlap the underlying serialized native operation.
Late operations remain owned by the queue and cannot release newer work. Cleanup
uncertainty is recorded explicitly, not treated as a passing radio-policy test.

CRC, sequence, durable credit, framing, no-progress budget, transfer cancellation,
full post-reboot identity, ordinary health confirmation and fixed signing remain
unchanged. No UART, PHY, data batching or background OTA ownership is added here.

## Verification

New tests exercise scan demand, in-flight startup, nested owners, stop, timeout,
native failure, disposal, priority generations/late requests, real service API
forwarding, strict schema matrix and actual startOtaUpgrade cancellation/cleanup.
Run the full development CI on both hosts. Runtime schema4 also needs a new
source-bound host observation adapter before device use; do not weaken or rewrite
the old schema3 parser or frozen trial evidence. This revision is WIP until CI
and the declared hardware screen have actual results.
