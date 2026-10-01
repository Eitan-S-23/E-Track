# Bounded Reboot Discovery

## Evidence

The fixed-signer APK e29c139 completed the30243-to30244 screen. Original
snapshot SHA-256:3bfa383e85bf6f810ddbe056ee8d266de1bbe8334e5fb40718a8b408cb6876e8.
Transfer37.784388s,7.571874KiB/s, no retransmissions/errors. END-to-target
identity22.394300s. The second of four probe attempts spent15.011773s in
discovery. Later original logcat explicitly reports
`FlutterBluePlusException | discoverServices | fbp-code: 1 | Timed out after 15s`.
Full target/Boot readback and ordinary confirmation passed; all owners closed.
This is a complete development successor screen, not formal1MiB acceptance.

## Repair

Pass a native3-second discovery-response timeout only from the reboot identity probe.
Ordinary queries/discovery retain their existing plugin default. Observation
labels never select behavior. The complete180-second window and per-attempt
cap remain unchanged. UUID/service/write-mode checks, MTU negotiation and full
target raw SHA checks remain mandatory.

After an unresolved mobile probe, disconnect only if its captured connection
generation is still current and the probe is neither cancelled nor abandoned.
Cleanup waits at most5seconds, within the outer attempt/window bounds. Do not
let a late discovery or old cleanup disconnect a new owner. A completed identity
keeps the existing success behavior; Windows discovery and cleanup stay unchanged.
The native timeout is not claimed to cancel Android GATT by itself; owned-link
retirement handles its pending operation.
The SDK's queued disconnect and Android race-workaround delay are retained;
neither is bypassed for speed. Lockfile-verified flutter_blue_plus1.35.5 source
confirms discovery defaults to15seconds and releases its global mutex on timeout.
Its archive SHA is bfae0d24619940516261045d8b3c74b4c80ca82222426e05ffbf7f3ea9dbfb1a.

Regression scope: native timeout/default forwarding with and without stats,
invalid timeout rejection, failed-binding invalidation, late binding isolation,
failed-probe cleanup, newer-generation protection and abandoned-probe protection.
Development CI on both hosts is required before another same-certificate APK.
No new hardware result,20-second success,50KB/s, release or merge is claimed.
