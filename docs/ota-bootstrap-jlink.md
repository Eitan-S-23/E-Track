# P1-5 J-Link Bootstrap

This procedure performs the one-time migration from the legacy AC5 layout to
the OTA Boot plus relocated GCC App layout. P1-5 runtime and deployment
functionality is tool and documentation work only. The separately registered
legacy AC5 project/scatter prerequisite only makes the pre-migration image
reproducible; it adds no production Boot feature or binary contract. P1-5 does
not add a production Boot command channel, QSPI write API, OTA receive path,
decryption, decompression, or patching.

## Prerequisites

- Use SEGGER J-Link V8.18 with device `AT32F435RGT7`.
- Use SWD at exactly `1000 kHz`.
- Close JLinkRTTViewer. The scripts terminate stale JLinkRTTLogger processes
  before and after every bounded capture.
- Supply the explicitly selected legacy HEX. The default is
  `MDK-ARM_F435\Objects\X-Track.hex`.
- Start from a pure legacy device whose two BCB records are blank or invalid.
  The production Boot already handles that condition by validating the App and
  atomically creating `CONFIRMED` with `cur_vcode` from its verified
  `fw_header`. The deployment tool does not clear or rewrite EEPROM.
- Keep power and the SD card stable. A J-Link halt can interrupt SDIO; recover
  the card by power cycling or reinserting it before retrying.

## One-Time Migration

Run from the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\jlink\deploy-ota-bootstrap.ps1 -Version 2.8.0 -LegacyHex .\MDK-ARM_F435\Objects\X-Track.hex
```

The script creates a unique `.cache\p1-5-bootstrap-*` run directory and:

1. Copies the selected legacy HEX to a
   `selected-legacy-<sha256>-<basename>` file before any device write.
2. Copies repository-default legacy artifacts under separate
   `repo-default-*` names. They are audit assets and are never selected for
   rollback.
3. Builds fresh GCC Release `X_Track_App_GCC` and `X_Track_Boot` targets.
4. Finalizes a copy of the App and validates the complete frozen `fw_header`,
   double-zero SHA-256, header CRC32, MSP, and Reset_Handler contracts.
5. Generates a recovery container as a retained host artifact only. The script
   does not install or modify an external recovery slot.
6. Programs Boot at `0x08000000` and finalized App at `0x08010000`, then
   requires two distinct `VerifyBin` success results.
7. Performs two ordinary MCU resets with a 90-second stabilization window and
   a bounded 30-second RTT capture. Each reset must report a PC inside the App
   partition, `VTOR=0x08010000`, and exact `CFSR=0x00000000`.
8. Re-resolves `_SEGGER_RTT` from the fresh App map, verifies the
   `SEGGER RTT` RAM signature, and requires a current
   `OTA: HANDOFF vtor=0x08010000` line.
9. Requires `OTA: BCB already CONFIRMED vcode=<fw_header version_code>`.
   Together with the separately recorded blank/double-bad BCB starting-state
   precondition, this proves that Boot established the record from the
   validated App rather than from host-supplied metadata. The script itself
   never clears or synthesizes BCB data.

`P1_5_DEPLOYMENT=PASS` is emitted only after every gate above passes. A
debugger-forced MSP/PC start is not accepted.

## Asset Preparation

`prepare-bootstrap-app.py` intentionally exposes only `prepare` and
`verify`:

```powershell
python .\Tools\jlink\prepare-bootstrap-app.py prepare --input .\app.finalized.bin --input-kind app --output .\app.deploy.bin --recovery-output .\recovery-v2.8.0.bin
python .\Tools\jlink\prepare-bootstrap-app.py verify --input .\recovery-v2.8.0.bin --input-kind recovery
```

The tool rejects all input/output and App/recovery output path collisions
before writing. It reads back every generated file and verifies that the
source asset remains byte-identical.

## Direct Recovery-Container Flash

Direct J-Link flashing of a CI recovery container requires the matching App
map so the RTT address is not guessed:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\jlink\flash-recovery-container.ps1 -RecoveryContainer .\recovery-v2.8.0.bin -AppMap .\X-Track-App-GCC.map -LegacyHex .\MDK-ARM_F435\Objects\X-Track.hex
```

The script validates the recovery trailer, writes a separate
`recovery-stripped-app.bin`, and confirms that the source length and
SHA-256 are unchanged. The stripped file must be exactly eight bytes shorter,
so the recovery container trailer is never written into the App partition.

This path assumes the production Boot is already installed. It does not clear
BCB and does not install an external recovery slot. PASS requires App-range
PC, the expected VTOR, exact zero CFSR, the map-derived RTT signature, and a
current Boot-to-App handoff line.

## Failure Handling

No script deletes legacy or generated artifacts. If a failure occurs before
the first device write, the MCU is left untouched. If a failure occurs after a
device write begins, rollback uses only the hash-named copy of the explicitly
selected legacy HEX. A basename-colliding repository default can therefore
never replace the rollback source.

Every run directory retains manifests, build logs, raw/finalized/deployed
assets, J-Link command logs, reset register evidence, RTT signature checks,
and bounded RTT captures. Investigate those files before retrying.

The external recovery-slot installer and the P1-6 physical power-loss matrix
are outside this procedure.
