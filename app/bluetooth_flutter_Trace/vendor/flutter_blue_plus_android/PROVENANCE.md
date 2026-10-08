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
