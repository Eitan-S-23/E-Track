# Group16 Development Checkpoint

Status: saved work in progress, not production integration or final acceptance.
This checkpoint preserves the installed group16 Boot experiment and the first
completed 30277 -> 30278 OTA comparison. It does not save every unrelated or
earlier P3-4 working-tree change, and does not enable group16 in production.

## Observed Result

| Metric | Group1 | Group16 |
| --- | ---: | ---: |
| BLE transfer | 17.898428 s | 17.483523 s |
| END ACK to reboot identity | 20.494210 s | 17.029138 s |
| Combined measured intervals | 38.392638 s | 34.512661 s |
| Decimal throughput | 16.428929 kB/s | 16.819722 kB/s |

Post-END saving: 3.465072 s. Combined saving: 3.879977 s (10.1%).
Both runs sent 2298 DATA frames without retransmission. Each run also had one
failed reboot discovery; do not describe the entire session as error-free.
The comparison uses the same executable with version-header changes only.
Post-END includes installation, reboot, readiness polling and reconnection; it
is not a measurement of EEPROM or Flash alone. The earlier approximately 5 s
estimate used the EEPROM's maximum 5 ms write-cycle time as if it were actual
per-page duration, which was not measured here.

The 50 kB/s and 20 s objectives remain unmet. Repeated-run stability, arbitrary
executable-changing upgrade coverage, production integration and independent
acceptance remain outstanding. No new OTA, flashing or hardware test was run
to create this checkpoint. The last verified retained state is group16 Boot
with R2-C 30278, matching full readback and a paired 30 s runtime check.

## Saved Contents

- `sources.patch` is the readable experimental Boot source/configuration delta
  against `manifest.json`'s base commit. It includes required prior Boot changes,
  not just the grouping predicate. It is not applied to production sources.
- `manifest.json` binds every archived member and the actual Boot source/header
  dependencies. Unchanged inputs refer to base Git blobs; exact changed bytes
  are in `evidence.zip` under `source-overrides/`. Toolchain headers remain
  external inputs with hashes. This is not a fresh clean-checkout rebuild claim.
- `evidence.zip` preserves raw group1/group16 snapshots, original comparison and
  postcheck results, standard SEGGER programming logs, original build logs,
  group16 BIN/ELF/map, the installed App readback, original Boot backup and exact
  16 KiB prefixes. Original project-relative paths are under `original/`.
  Derived dependency listings and Boot-only compile commands are under `derived/`.

ZIP packaging preserves exact original bytes without Git line-ending conversion.
Archive integrity and source/artifact bindings were checked at save time; this
does not rerun or upgrade the historical tests into independent acceptance.
Original `.cache` evidence remains untouched. Existing detailed operational
history remains in the adjacent recovery-provisioning note and the P3-4 board.

## Restore Boundaries

Use the base commit plus `sources.patch` in a separate, authorized project-local
work area to recover the experimental source delta, or use exact source override
bytes and the manifest's base blobs. Keep the current dirty worktree intact.
Recovery of the source delta is separate from rebuilding or operating hardware.

The full 64 KiB Boot readbacks are verification/backups, not programming inputs.
Only the specifically recorded first 16 KiB prefixes were used for the approved
Boot replacement/restoration route. Bytes above that range must be preserved.
Do not replay consumed flash scripts or the completed 30277 -> 30278 OTA.
No signing secrets or new authorization are provided by this checkpoint.
