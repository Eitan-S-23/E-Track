# Mobile Reconnect Repair

P3-4 development only. Base fixed-signer commit:
`0dd20fe72940ca26101c5d41f1b26cd039189a8a`.

## RECONNECT-02

Original run `20261001T191549-84800/s04` transferred293079 bytes with END OK
in51.714236 seconds,5.534452 KiB/s, zero DATA retransmissions. Its original
App snapshot reports `not-completed`:203 reconnect attempts over180.004637
seconds, none entering bind or GET_INFO. Native trace observed target30243
and the ordinary30-second healthy-App confirmation. Preserve both facts;
this was not an end-to-end successful upgrade or a speed improvement.

The original complete Android log ring contains203 identical errors:
`PlatformException(requestMtu, device is disconnected, null, null)`.
The truncated16000-line tail started after the failure; the full remaining
ring was retrieved without replaying any device action.

The lockfile's flutter_blue_plus1.35.5 `connect` defaults to MTU512.
flutter_blue_plus_android4.0.5 uses exact native string keys for GATT maps;
callbacks use Android `BluetoothDevice.getAddress()`. Passing the lowercased
internal identity to a cold-cache native object is unsafe. Both upstream
archive hashes were checked against the installed-source pubspec.lock.

Repair: canonicalize only MAC-shaped mobile IDs, use the same spelling for
connect/disconnect, replace differently cased cached objects after success,
and request no automatic MTU in connect. Existing requestOtaMtu after exact
discovery remains the sole negotiation. Reject a connect return without a
live connection. UUID spelling, Windows adapter calls, generation ownership,
FFF0/FFF2/FFF1 binding, deadlines, cancellation and full identity checks remain.

Eight mobile boundary tests exercise the real service methods through a
fake BluetoothDevice factory. Both-host development CI must pass before
claiming repair; hardware validation is still pending. Keep the same package
ID and dedicated fixed development signer. No repeat of completed30243 OTA
is allowed just to recreate logs, and no main merge or release is authorized.
