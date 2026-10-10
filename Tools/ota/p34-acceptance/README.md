# P3-4 Admission Observations

These tools prepare/interpret evidence. They do not approve a frozen contract,
operate a device, or turn a self-test into independent acceptance. Trial5 remains
unexplained; none of these observation changes claims to fix its cause.

## Production MCU Metrics (PRE-01)

`P34_OTA_CANDIDATE` enables `CONFIG_OTA_LINK_METRICS=1`. The experimental BLE/install
profiles, baud console and RTT down commands remain OFF. `ota_link_metrics.h`
defines a **420-byte, little-endian u32 ABI**, magic `0x50334d31`, schema 1. It is
not the old 336-byte/schema-2 experimental probe.

The only writable owner is firmware itself. A successful BLE overlay acquisition
resets counters and the staging first-error record. Idempotent BEGIN retries do
not reset them. The first successful BEGIN ACK binds protocol, session, epoch and
initial durable offset. Overlay release drains ACKs, freezes all counters with
IRQs masked and emits one `P34_METRICS <840 hex digits>` line using nonblocking RTT.
The snapshot has a CRC32 over its first 416 bytes. It also remains at
`g_ota_link_metrics` until the next session/reset. `g_ota_metrics_publish_bytes`
must be 853 for a complete RTT write; missing/torn/duplicate records are not zero
cost. RAM-only snapshots do not survive reboot. Collect before the run, not after
discovering that a successful OTA already erased its volatile evidence.

The standard route is the existing SEGGER `JLinkRTTLogger.exe`, device `CORTEX-M4`,
SWD 1000, channel 0, with a finite owned timeout and a fresh project-local output.
Resolve `_SEGGER_RTT` from this exact candidate's map and verify `SEGGER RTT` at
that address with standard J-Link before starting the sole reader. The App base
and target differ only in `fw_header`, so their executable/RAM layout is identical.
No new flashing tool, AT command or installation-only OTA is needed. The decoder
also accepts an exact 420-byte standard J-Link `savebin` read with `--binary`;
read only a quiescent `ready=1,active=0` snapshot and require identical repeated
readbacks/CRC if using that fallback. The formal operator freezes actual command
files, ownership, deadlines and source hashes before the first live qualification.

Decoder entry (replace the input paths/hash/epoch with the bound originals):

    python -I -S -B -X utf8 Tools/ota/p34-acceptance/metrics.py --input RTT_LOG --elf MATCHING_ELF --map MATCHING_MAP --expect-elf-sha256 ELF_SHA --expect-map-sha256 MAP_SHA --package REFERENCE_ETU --expect-epoch APP_BEGIN_EPOCH --expect-baud 921600

Fields and limits:

- `clock_hz=288000000`, `clock_ok`, `overflow`: DWT clock and validity. Per-operation
  intervals may cross one counter wrap, not span a full wrap. Long ambiguous
  intervals and saturated counters invalidate timing instead of wrapping small.
- Each of the ten phases has calls, errors, logical requested bytes, 64-bit
  cumulative cycles (low/high u32) and maximum cycles. No calls means unavailable
  timing (`null`), not a measured zero. The decoder rejects missing required
  stages on a complete zero-start transfer.
- Phases are payload/journal read, program, erase and verify, UART RX IRQ body,
  and ACK TX including its existing drain/gap. UART measures `HardwareSerial`
  flag check, byte capture, ring insertion and callback, excluding exception
  entry/exit and the final counter update. UART error/drop and overlay occupancy
  counters use the same acquisition/release window.
- Staging intervals include XIP restore, higher-priority IRQs and nested WAIT_RX
  processing/ACK TX. They are inclusive wall-cycle costs, **not disjoint costs or
  automatically removable time**. Erase byte counts describe logical 4 KiB IO
  requests; erase-ahead may do 64 KiB physical work or reuse an earlier erase.
- `terminal=0` means END reached successful staging finalization before activation;
  it does not prove installation/reboot success. `terminal=1` retains failed or
  incomplete sessions. Full package SHA, CRC, length and final durable offset are
  copied from the session; only the successful END path makes the full digest
  claim. A pre-BEGIN failure keeps `initial_durable=UINT32_MAX`, never guessed zero.
- `first_error` retains operation/phase/address/length/result/mismatch address and
  expected/observed bytes. Later faults cannot overwrite it. No new recovery or
  storage behavior is introduced. Hardware clock/field advancement, logger health,
  stack high-water/guard and initial-state equivalence still require the first
  independent live qualification.

## App Statistics (PRE-06)

Use `Tools/ota/p3-4-link-stats/acceptance_stats.py`, which consumes the existing
strict `observation_capture.py`, not the older `p34_observation.py`. The simpler
`batch_timing.py --protocol 1|2` remains a clean-batch diagnostic, not the formal
group gate. V1/V2 DATA overhead is 14/18 bytes, BEGIN 111/115, END 42/46; queries,
capability negotiation and ABORTs remain separate control records.

GET_INFO is command `0x00` (10 bytes), not the undefined `0x05`. Complete formal
captures require its actual write, plus CAPS2 for V2 and BEGIN/END; a handwritten
identity line does not replace missing control/GATT evidence.

    python -I -S -B -X utf8 Tools/ota/p3-4-link-stats/acceptance_stats.py --input SNAPSHOT --expect-sentinel APK_SENTINEL --expect-target DEVICE
    python -I -S -B -X utf8 Tools/ota/p3-4-link-stats/acceptance_stats.py --plan RUN_PLAN_JSON

A plan has exactly `schema:1`, `expectedCount` and `runs`. Each entry names `id`,
`input` (path relative to the plan or an absolute original path), `sha256`,
`sentinel`, `target` and `role` (`clean`, `soak`, `disconnect`, `resume`, `injected`).
Clean means no deliberate fault injection, not absence of error ACKs. Keep the predeclared IDs and every attempted run; a
missing original uses `input:null,sha256:null`. Missing/corrupt inputs remain
`evidenceGaps`, never a zero-valued sample. Duplicate IDs/capture identities or
bytes are rejected. The independent contract binds the planned IDs/count and
runner; this JSON is not a substitute source/freeze manifest.

The producer records the actual accepted BEGIN and effective window/timeout/retry
parameters, complete DATA sends, control starts/completions and durable events.
V2 latency is the first complete segment send to its first valid durable ACK,
checked against those original events. Early and missing samples remain separate
and disqualify P99 tuning. Consistent repeated runtime stamps are merged;
conflicting stamps, wire bytes, summaries and clock domains are rejected.

Grouping includes the effective protocol/window/batch/timeout/retries, requested
baud and runtime options, negotiated MTU/write mode, package/base/target, APK
sentinel, foreground/background state and platform. The frozen contract and
original device prechecks additionally bind the exact APK/source, since a
sentinel alone is not a cryptographic APK identity. The MCU's actual baud is an additional required matching
MCU observation, not inferred from the requested rate. Groups never share a P99
pool. Nearest-rank P99 uses all valid segment samples within a group; failed or
partial attempts remain in the denominator and prevent a tuning recommendation.
The timeout is `clamp(ceil(3*P99_us/1000),500,2000)` ms only when eligible.

The 30-run boolean additionally requires 30/30 complete zero-start 1 MiB runs,
>=9 KiB/s, P95<=120 s, every run<=150 s and DATA retransmission<=1%, with maxRetries=5.
The retransmission denominator is unique DATA segments, not total send attempts.
Normal retries remain in the same run and latency pool. Recovery entries
use `recoveryCase` and `role:disconnect|resume`; an actual disconnect failure and
matching durable resume are required, not ABORT or an ordinary success. Ten-case
qualification also checks two each at 8/64/256/512/768 KiB on the 1 MiB reference.
Disconnect classification requires the real service's `failure.stage=transfer`
and exact `transport:DISCONNECTED` or `transport:DEVICE_LINK_CHANGED` reason.
The original reason is retained; bare, substring-matched, cancelled or reboot
failures cannot qualify. All ten pairs must share one parameter/asset group;
`recoveryParameters` exposes that group for comparison with the frozen production
selection, and is null when recovered pairs span multiple groups.
The physical intervention evidence remains the independent controller's input.
Four-hour soak duration requires its single-host monotonic schedule/idle/failure
log, **not** summed App durations or cross-process timestamps; the App-only tool
deliberately returns `soakDurationSeconds:null`.

`--historical` permits explicit diagnostic reinterpretation of older snapshots
without new BEGIN/control metadata. It never enters a formal plan or qualifies
P99/full-reference thresholds. In particular, trial6 remains a resumed small run.

## Filtered Errors (PRE-07)

`OTA_LINK_ACK_ERROR` preserves the first matching error. A separate
`OTA_LINK_ACK_IGNORED` stream preserves the first raw error for each of six bounded
categories: session, epoch, sequence, inactive, retired and unmatched. It includes
cmd/session/seq/epoch/status, available credit fields, expected owner and the
binding-local arrival time. No diagnostic record supplies credit or durable state.
Counts saturate at UINT32_MAX with a flag. There are at most six first records plus
one sealed count record, emitted only after notification subscription closure.
The active summary contains counts as of that summary; later records retain their
own original owner and do not rewrite the summary or active first error. A stream
without sealed counts still proves its retained first records, not a final count.

Flutter tests inject all requested error classes through the real transport,
`OtaDiagnostics`/`OtaObservationLog` export and strict Python reader. They also run
a full V2/schema-10 synthetic transfer through the formal statistics entry. These
are bounded host oracles, not a replacement for the independent hardware matrix.
