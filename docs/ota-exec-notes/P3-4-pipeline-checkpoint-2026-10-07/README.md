# Measured Pipeline Checkpoint

Local archival checkpoint, pending source integration. Not a release or independent acceptance.

Measured transfer: 17.480900 -> 13.814972 s; normalized throughput +27.5209%; one sample.
Current retained App: C30282, 622884 bytes, SHA-256 d973f6d517ca6cc28e0434ac870da4b4bd04778c4ce56dbbcb08edaa2c0100f3.
Full unchanged group16 Boot/App readback and health passed. No new hardware operation.

sources.zip contains all 3284 exact firmware build inputs, four pipeline tests and sender.tar,
the full tested sender Git tree at db4f007bf63b43b7c89e2798b88af41fd1a903bd. No APK credential or private key is included.
Build with the saved configure command after relocating source/build/install/prefix-map paths
inside an authorized project. Keep all definitions; App-only, GCC; Boot was not rebuilt.

evidence.zip preserves the original App snapshot, failed old validator/native collector receipts,
the finalized target, matching ELF/map and host checks. MCU runtime drop profile and collector
closure are missing. The 30% screening target was not met. No identical-package A/B or soak claim.
Never replace failed receipts or replay a successful upgrade merely to improve collection.

Existing HCI original hash was reverified: phone MTU512 request, module MTU247 response.
No larger-MTU trial is justified without a changed module configuration.
