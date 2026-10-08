# P3-4 Development PHY Fork

Upstream: flutter_blue_plus_android 4.0.5, unchanged package version and license.
Archive: https://pub.dev/api/archives/flutter_blue_plus_android-4.0.5.tar.gz
SHA-256: 9723dd4ba7dcc3f27f8202e1159a302eb4cdb88ae482bb8e0dd733b82230a258

Eight upstream trailing-whitespace lines in AndroidManifest.xml and the plugin
Java file are normalized for the repository whitespace gate; no license edits.
Six upstream Dart lints are repaired without suppression: three immutable
constructors are const and verbose prints use unthrottled debugPrintSynchronously.

The narrowly scoped fork adds a debug-only `etrack/ota_phy` method channel to the
existing plugin/GATT owner. No reflection, second connection, changed GATT write
mode, frame concurrency, production timing or OTA wire command is introduced.
`p34ObservePhy` permits `observe` or `prefer2m` before BEGIN. Preference is not
negotiation evidence: record read-before, update and read-after independently.

`PhyProbe` owns a four-second deadline and one observation per GATT object.
Android callbacks carry no request ID; after completion/failure/timeout the same
GATT cannot start another probe. Disconnect/restart/detach invalidate pending
results and cancel timers. Reusing an auto-connect GATT object does not erase its
spent marker. A new native GATT is necessary, not an automatic retry or OTA replay.
Successful delivery rechecks the exact GATT and connection generation.
`p34CancelPhy` matches the active request on the exact current GATT, stops pending
read/preference transitions and preserves the spent marker. Cancellation does not
claim to undo a preference already handed to Android.

The pure Java coordinator tests run on both development CI hosts. Android plugin
compilation still requires the explicit CI debug APK build. Neither proves 2M
negotiation or throughput on hardware. No firmware or Boot changes belong here.

The native Android log tag is `FBP-Android` without square brackets. Android
property names reject brackets, so the upstream tag cannot use a per-tag
`log.tag.<tag>` override when the phone's global logging threshold is INFO.
This name-only change permits a temporary, independently restored debug override
without enabling debug logging for other apps. Log levels, write serialization,
callbacks, payloads and PHY behavior are unchanged. The existing native CI entry
checks the tag's property-name compatibility; live timing still requires actual
device observations and must not be inferred from a successful APK build.

## Native Write Timing

The scoped tag override did not produce usable markers on the authorized phone
during successful App queries. The existing HCI trace cannot split native callback
latency from main-thread delivery. Rather than widen global phone logging or
rewrite the sender speculatively, this fork adds a bounded in-memory observer.

The same `etrack/ota_phy` channel exposes `p34TraceStart`, `p34TraceSnapshot` and
`p34TraceStop` only to the debuggable `com.wen.gaia.gaia.p34probe` application.
The existing development diagnostic capture explicitly starts it with an exact
capture ID and target. It observes only FFF0/FFF2 writes to that target. Production
and non-Android paths do not start it. It performs no Bluetooth operations.

Each sample contains its sequence, native GATT object generation, length, CRC32,
method-entry/submission/return/callback/main-thread-dispatch timestamps, native
API result and GATT status. Timestamps are relative `System.nanoTime` nanoseconds,
not the App, HCI or radio clock. Early callbacks are retained, not clamped. Missing
events, ambiguous/late callbacks, write errors and the 8192-sample bound are explicit.
The recorder never changes the write result, retries, backpressure or delivery order.

Snapshot export runs after identity queries and at the existing diagnostic export,
not in the DATA loop. It uses the existing App writer in bounded flush batches;
there is no per-write disk I/O or extra MethodChannel round trip. No payload bytes
are retained. Pure Java and Dart tests cover binding, lifecycle, failure, clocks,
capacity and export. Actual query records are still required to validate native
hooks, and short INFO queries cannot establish saturated DATA throughput.

## Main-Looper Callback Scheduling Candidate

The 2026-10-09 trial6 offline analysis matched all 1322 native writes, including
two retired-instance ABORT observations. Its 1303 DATA fragments spent 2.009790
seconds between native callback entry and main-looper dispatch. API-return
overlap reduces the entire interval's optimistic removable upper bound to
1.997279 seconds; callback body work and main-thread execution remain necessary.
No measured speed gain or synchronization-barrier duration is established yet.

This candidate changes only the callback scheduler: one shared main-looper
Handler dispatches all plugin events, asynchronous on Android API 28+ and ordinary
on older versions. Android's async Handler API bypasses synchronization barriers
and retains FIFO among its own messages. It does not create a worker thread,
prioritize selected write events over peer BLE events, skip write callbacks,
return success early, batch writes, change MTU/credit, or modify the Flutter UI.
Existing main-channel availability checks, API results and backpressure remain.

The native CI runner tests the actual factory with SDK/Looper/Handler doubles
and checks its single-handler/dispatch-guard wiring. Those host models do not
measure Android scheduling or prove performance; a real APK build and a bounded
equivalent-state device screen are separate requirements. This development fork
is pending integration, not a production or independent acceptance result.
