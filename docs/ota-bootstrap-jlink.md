# P1-5 J-Link Bootstrap

This document describes the one-time migration from the legacy AC5 layout to
the OTA Boot plus relocated GCC App layout. It is an implementation procedure,
not a change to the frozen binary contracts.

## Prerequisites

- A clean hardware connection using the onboard J-Link.
- SEGGER J-Link V8.18 with device AT32F435RGT7.
- SWD speed exactly 1000 kHz.
- Power and the board's SD card in a stable state. A J-Link halt can interrupt
  SDIO; if the card becomes unavailable, power-cycle or reinsert the card
  before continuing.
- No JLinkRTTViewer window and no stale JLinkRTTLogger process.
- A legacy MDK-ARM_F435\Objects\X-Track.hex artifact. The deployment script
  copies the legacy hex, axf, hex, and bin into its run directory before any
  flash operation.

## One-time migration

Run from the repository root:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\jlink\deploy-ota-bootstrap.ps1 -Version 2.8.0 -InstallRecovery

The script creates a unique .cache\p1-5-bootstrap-* directory and performs
these steps:

1. Preserve the legacy artifacts and their SHA-256 manifest.
2. Configure and build a fresh GCC Release X_Track_App_GCC and X_Track_Boot
   pair.
3. Finalize a copy of the App with Tools\etu_pack.py; the raw build output is
   never mutated.
4. Run prepare-bootstrap-app.py, which validates every fw_header field, the
   double-zero SHA, header CRC, vector MSP/Reset_Handler range, and generates a
   recovery container when requested.
5. Program and verifybin Boot at 0x08000000 and the finalized App at
   0x08010000.
6. Clear both BCB records through the authenticated 128-byte NOLOAD bootstrap
   command. On the next ordinary reset Boot validates the App and creates a
   CONFIRMED BCB with cur_vcode read from the validated header.
7. With -InstallRecovery, ask Boot to copy the validated internal App into the
   recovery slot. Boot erases and verifies each 4 KiB block and writes the ETSL
   commit marker last; the host does not construct or bypass that header.
8. Perform an ordinary MCU reset, re-resolve _SEGGER_RTT from the current App
   map, verify the SEGGER RTT signature by mem8, and collect one bounded RTT
   log. The script requires a VTOR=0x08010000 handoff line and a BCB line.

P1_5_DEPLOYMENT=PASS is emitted only after the ordinary reset evidence is
present. A restricted debugger start is not accepted as this evidence.

## Bootstrap command utility

The command protocol is generated and checked by the Python tool:

    python .\Tools\jlink\prepare-bootstrap-app.py command --operation snapshot-bcb --output .cache\snapshot-command.bin

Supported operations are clear-bcb, install-candidate, install-backup,
install-recovery, stage-slots, and snapshot-bcb. The common PowerShell layer
writes the command to 0x20058000, resets and runs Boot, waits with a bounded
timeout, saves exactly 128 bytes, and rejects a missing result magic or CRC.
The Boot result is never accepted based on a textual J-Link message alone.

## Direct recovery-container flash

For a physical recovery asset produced by CI:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Tools\jlink\flash-recovery-container.ps1 -RecoveryContainer .\recovery-v2.8.0.bin

The tool requires a valid final 8-byte image_len + crc32 trailer, verifies the
complete App, writes a separate recovery-stripped-app.bin, and flashes only
that file at 0x08010000. The trailer is therefore never written into the App
partition. It emits P1_5_RECOVERY_TRAILER_STRIPPED=PASS only after confirming
the prepared image is exactly 8 bytes shorter, then requires an ordinary reset
to leave VTOR at 0x08010000. The original container is not changed. On failure
the preserved legacy hex is used as the automatic recovery flash.

This direct path assumes the P1-5 Boot is already installed. The normal
deployment path's -InstallRecovery option is preferred for populating the
external recovery slot.

## Failure handling and evidence

Every run directory retains:

- the preserved legacy artifacts and SHA-256 manifest;
- fresh CMake configure/build logs;
- raw, finalized, deployed, and recovery asset hashes;
- J-Link command files and logs;
- bootstrap command/result binaries and parsed CRC/status output;
- RTT signature, ordinary-reset, and bounded logger output.

If any build, validation, VerifyBin, bootstrap, or ordinary-reset assertion
fails, the deployment script does not delete OTA artifacts. It attempts to
reflash the preserved legacy hex and then rethrows the original failure.
Investigate the run directory before retrying.

The procedure does not perform the P1-6 physical power-loss matrix. It also
does not add OTA receive, decryption, decompression, or patching behavior.
