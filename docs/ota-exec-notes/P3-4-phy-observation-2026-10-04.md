# P3-4 PHY Observation Development

Owner: Codex implementation/root. Development branch:
`dev/flutter/p3-4-phy-observation-20261004`.
Base/installed App source: `c5a8c53195bcda43e3ae060f7ce5e8007a4cf6ae`.
Project root governance applies; this is not a mainline delivery or acceptance.

## Basis

HALF-ERASE-01 retained firmware 30266. Its measured transfer was 18.095728 s
(16.216424 decimal KB/s), END-to-target 20.363205 s, combined 38.458933 s.
The existing capture showed a 15 ms DATA connection interval, DLE 251 in each
direction and remote support for LE2M. Actual PHY was unknown. Neither support,
`setPreferredPhy` return nor DLE implies negotiated PHY or a throughput gain.

## Contract

Schema 8 adds mandatory `androidPhyPolicy=off|observe|prefer2m`; schemas 1..7
retain off. Only the immutable development runtime config selects it.
After exact characteristic binding and before GET_INFO recheck/BEGIN, the service
awaits one native probe and rechecks its cancellation generation. Identity,
durability, sender window, batch size, backpressure and reboot verification stay
unchanged. Probe time is outside BEGIN-to-END transfer timing and must be reported
separately when evaluating end-to-end latency.

The debug-only `etrack/ota_phy` bridge shares the upstream BluetoothGatt owner
and method/callback mutex. `observe` reads actual TX/RX; `prefer2m` reads before,
requests 2M, awaits update and reads again. A successful preference invocation is
never returned as observed PHY. Unsupported, missing, failed, stale, invalid or
timed-out evidence blocks this experiment before BEGIN. Preference only admits
transfer when final actual TX and RX both equal 2. Control admits any valid PHY.

One native operation per BluetoothGatt object is deliberate. Android carries no
request token in callbacks. Failure/completion spends that GATT, disconnect clears
pending work, and auto-connect reuse cannot consume a late callback as fresh
evidence. No automated reconnect or retry is added. A four-second native deadline
and five-second Dart bound clean up/report failure. Results bind request ID,
address, native connection generation and the App config hash in `OTA_PHY`.

## Verification

Pure Java host regression initially passed 173 assertions with `--release 8 -Xlint:all
-Werror`, zero warnings/errors. It covers actual readback, callback ordering,
status failures, malformed PHY, all timeout/disconnect/clear stages, GATT reuse,
stale callbacks, synchronous native exceptions and generation invalidation.
App tests cover schema compatibility, channel identity/shape validation,
unsupported platforms, late completion and pre-BEGIN cancellation/failure guards.
App analyze/tests on both CI hosts and explicit APK compilation are still required.

First CI: `57a06316a7fc560d9f0c60dcc2e5be568e6ae21f`, run 37137053728 failed
on both hosts. Six upstream vendored Dart lints and five new fixture failures
were consolidated. All five fixtures used the default with-response fake while
explicitly selecting batch12; the existing fail-closed transport correctly rejected
them before PHY. Fixtures now explicitly use without-response, not weakened guards.
Original result: Linux 651 pass/16 skipped/5 fail, Windows 634 pass/33 skipped/5 fail.

The same remediation batch adds request-bound native cancellation. Without it,
discarding the Dart result alone could still permit a pending read to trigger a
later PHY preference. The updated pure Java regression passed 215 assertions,
zero warnings/errors, including cancellation in all three native stages.
Legacy profiles add no new await in the cancellation path. The PHY observations
are pre-BEGIN samples, not a continuous guarantee of unchanged PHY during DATA.

## Next Hardware Matrix

No device operation occurred in this implementation batch. Prepare one same-package,
same-certificate debug APK after CI stabilization. Keep installed firmware 30266
and original Boot. First obtain source-bound query readiness; then prepare matched
header-only full packages for observe versus prefer2m with unchanged radio, baud,
batch, erase and reconnect settings. A fresh GATT is an explicit setup requirement,
not an automatic successful-OTA replay. Unknown/unsupported/not-2M stops the 2M
candidate without firmware transfer. Preserve all original results, including
non-improvements; no new system report permission is assumed.
