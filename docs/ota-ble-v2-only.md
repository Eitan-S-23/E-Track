# BLE V2-Only Implementation

Effective decision: 2026-11-09. The user confirmed that no deployed device needs
BLE V1 and explicitly requested removal, not another opt-in fast profile.

## Current Behavior

- Both the Flutter sender and MCU receiver support V2 transfers only. The MCU
  rejects retired request opcodes `0x01..0x04`; the sender has no V1 transfer,
  prefix-probe or timeout-fallback path.
- `GET_INFO` still uses its original 50-byte identity layout and format version
  `1`. This is not selection of BLE V1. A successful, nonce-bound `CAPS2` exchange
  is required before `BEGIN2`. Timeout returns `V2_REQUIRED`, without BEGIN.
- Normal App builds select `adaptive-v2-candidate`: at most 24 outstanding
  segments and up to 12 DATA frames per batch, subject to actual receiver credit
  and GATT properties. With-response writes may reduce batching, never protocol.
  The old INFO window field does not cap the V2 sender.
- Normal GCC builds require the V2/WAIT_RX receiver. Disabling
  `P34_OTA_CANDIDATE` fails configuration rather than producing a V1 receiver.
- Epoch/session/sequence checks, durable-only progress, package SHA/CRC,
  activation gates, cancellation ownership and fresh post-reboot identity
  verification remain required. A failed END2 settles ownership once and retains
  the original MCU rejection, not a false success or a replayed END2.

The V2 wire fields and credit rules remain those in
[the two-block contract](ota-ble-v2-contract.md). This decision supersedes only
its prospective old-peer compatibility and bounded V1-fallback provisions.
HTTP schema, ETU/crypto versions, INFO layout, SD OTA and Boot recovery are not
the retired BLE transfer protocol and are not removed.

## Verification And Installation

Current frame/session/synchronous-port tests use V2. Their shared NOR/identity
fixture is `tests/ota/ota_ble_session_fixture.h`, with no old transfer runner.
Historical V1 wire bytes remain only as rejection inputs or in historical
oracles, not as a selectable device implementation. The frozen V1 oracle and
accepted evidence are not edited to claim they passed on this changed source.

Development checks and firmware builds precede any device installation. Bind
the APK and receiver to the actual checked source, retain the existing App
identity/configuration, and reconcile the device's current image and BCB before
changing it. Do not restore an old-protocol baseline for the next measurement.

This note is not a throughput result, independent acceptance, release approval
or completion of P5-1. Existing failed attempts and unfinished formal criteria
remain intact; no four-hour campaign is started by this implementation change.
