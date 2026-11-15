# P51 Current App And Backend Follow-up

## Current Status

P5-1 remains in progress. The latest original App, its safe restart/reconnection
and recording lifecycle have actual device observations. The complete firmware
upgrade/verify/restore short cycle and four-hour campaign are NOT_RUN.
`canStartFourHour=false`. Do not reuse the old benchmark inputs as if they match
the currently installed App and MCU.

Working root: `D:/github/my/E-Track/.cache/p35-integration-20261028/source`.
Evidence prefix: `.cache/project-closeout-20261115-01/` in that worktree.
The script changes described here are local, not represented as product code
already integrated on main. Main receives this status/issue record only.

## Observed App And Recorder

The installed original package is `com.wen.gaia.gaia`, version 1.0.77 / 103,
APK SHA-256 `bff1dce207c438194b8d2a524e294729893b88569606d31fc1bda080642747a8`.
It matches the original signed release from source
`9623cc43d6cb48a922caedbe08b82b5492afd7be`. It was not replaced or downgraded.
The earlier extra legacy benchmark installation is preserved in `p51-install-01`;
that App is not used, relaunched or uninstalled in this adaptation.

Fresh INFO reports MCU **3.3.27 / 30327** and raw-image SHA-256
`c04ddccdb73b096517baed57911b33f9f8d93508f85ad1808319873989ba9d14`.
This is a live App-origin identity, not a new full native readback/Boot/BCB proof.
No firmware was installed by this follow-up and no native J-Link operation ran.

`current-recording-07` obtained identity, then its wrapper failed before STOP
because it did not acknowledge the completed reconnect state. The original
record was safely stopped and retrieved in `current-recording-recovery-05`:
118718 bytes, SHA-256
`ba1f07f8600dd27f9fba7f9241649c58a5cdf657516c90b7bf625a98c5b8c7aa`.
Its unhealthy footer and interrupted live stream remain a failure. Retrieval
does not turn it into a successful real-time recording.

After the fix, `current-recording-09` automatically restarted the existing App
once after checking idle state and archiving its old record, reconnected the
device, recorded fresh identity, stopped, and retrieved the new original.
The file is 13894 bytes / 19 records, SHA-256
`f4137b28ec1550d5187c519e9978762d3283cb7e33bc7eae3ef008f18531c7af`.
Its healthy footer/count/hash, byte equality with the acknowledged stream,
native mirror and unchanged old on-phone archive are verified by
`current-lifecycle-verification-01/result.json`.

The original command exited on an inappropriate final check: it required link
timing diagnostic samples although no transfer occurred. That failed receipt
is retained. The query-only entry now uses the existing ordinary capture audit;
the same already-collected bytes were evaluated without another recording.
Real upgrade paths still require the existing V2 timing diagnostics. No link
throughput, P99 latency, OTA success or independent acceptance is claimed here.

USB absence and a vivo sidebar overlay were observed separately. Their notices
were acknowledged and their actual clearance was checked before continuing.
No coordinates were clicked through a foreign overlay. Both private ports and
the recorder owner are closed/released after the verification.

## Script And Backend Adaptation

The current-App adapter preserves exact APK/source/signer and endpoint checks.
It reuses the existing launch, semantic controls, closed-recorder restart and
original-file verification. A requested navigation restart is permitted only
before recording/OTA, after verifying idle state and all earlier sealed files;
one failed recovery does not become an unbounded restart loop.

The explicit development entry is, from the working root:

    Tools\ota\p51-acceptance\short_test.bat --inputs PREPARED_INPUTS.json --out FRESH_PROJECT_LOCAL_DIRECTORY

This is not a ready command until compatible inputs exist. It checks the actual
backend/package before acquiring the device, then reuses exactly one existing
V2 upgrade/readback/restore cell. It cannot start the long campaign. Receiver,
Boot, 1-MiB package, source and complete-state restoration checks remain intact.

The installed App uses
`https://trace-update-public-staging.pages.dev/api/public/firmware/latest`,
not the old isolated benchmark endpoint. Live requests with the current MCU
hash and App 103 returned schema 2 / NO_UPDATE on both Stable and Beta; originals
are in `current-backend-contract-01`. No regular channel was changed.

The adapter validates current query names, base/target/package identity,
`-patch.etu` filename, same-origin V2 public-download fields and expiry, then
requires full byte equality. NO_UPDATE, CHANNEL_STOPPED, wrong/older base,
full/smaller assets, stale signatures or another endpoint cannot count as a
successful P51 reference transfer. It does not use Admin cookies/CSRF or change
GitHub approval rules. Positive response/token checks have host regressions;
an actual matching current-backend download is still pending, not claimed by
the live NO_UPDATE observations.

All four affected host suites passed: 89 benchmark, 46 execution, 4 clock and
27 current-App tests (`short-entry-regressions-01`). After the query-only oracle
correction, the 27 current-App tests passed again (`current-app-final-tests-01`).
These are self-tests, not independent P5 acceptance. No new Flutter build,
firmware build, backend deployment or paid service was introduced.

## Deferred Issue And Remaining Work

`APP-BLE-NAV-20261115`, user-reported, NOT_FIXED at the user's request:
connect a device, enter its firmware page, leave without disconnecting, then
return to scanning. The already-connected device is absent and the firmware
page cannot be reopened until the App is restarted. Expected: the connected
device remains accessible without restart. Do not treat the user's earlier
manual restart as proof of an App crash or claim this UI bug is fixed by the
test script's restart handling.

The old 30321/30322 fixed-load package, isolated endpoint and restore executable
do not match the installed original App/current 30327 state. Preparation still
needs a compatible current-source reference package, a test-only delivery route
reachable by the installed App, and exact native/recovery bindings. Do not
publish the isolated benchmark to ordinary users, redirect the App silently,
install the rejected old test App, or downgrade by App-only flashing.

After those inputs are ready, inspect actual App/Boot/BCB/staging state and run
the one complete upgrade/verify/restore short cycle. Only then can the separate
four-hour invocation be prepared under its unchanged acceptance obligations.
The known UI bug stays deferred; the already completed MCU build/main-rule work
is not repeated to fill these missing test prerequisites.
