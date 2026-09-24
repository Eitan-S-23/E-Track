# P3-4 N01: Unified Durable Prefix Probe

## Scope And Inputs

Owner: Codex root. Active writable root: `D:/github/my/E-Track`.
Development branch: `dev/flutter/p3-4-unified-probe-20260924`.
Source baseline: `b657e1c7fea7b25f876bc92af87f822184eff5fd` (the previous
validated window-4 APK). Root product files and old evidence remain unchanged.
Current root governance was read from `main`; the progress table was committed
locally as `785f9a2`, with no main push or release authorization inferred.

This note records research and the selected design before product edits. It is
development work, not an independent acceptance result or a device run.

## Evidence And Decision

- The last complete 921600/window-4 OTA transferred 290865 bytes in
  103.801512 seconds with no retransmissions. It is not faster than the older
  460800 result, whose subsequent Boot apply failed. Inputs differ.
- The latest receiver performed 2273 payload readbacks taking 21.584581 seconds.
  The old <=31-segment probes never commit a 4 KiB block, so cannot measure this
  staging bottleneck. The approved next screen sends 32768 DATA bytes per cell.
- `ota_ble_transport.dart` already owns credit, retries, durable progress,
  sequence validation, cancellation and GATT physical-write settlement. Reuse
  that sender, not a second synthetic transport or a sleep-based throughput test.
- Existing `_abortRoundTrip()` deliberately ignores ACK timeout and does not
  validate the ACK payload. It is recovery machinery, not verified closure.
- MCU `session_handle_abort` rejects a mismatched active session; for an accepted
  ABORT it sends ACK_ABORT/ABORTED with current durable/bitmap before teardown.
  Teardown preserves staging durable bytes. ABORT does NOT restore a zero state.

## Selected Contract

1. Preserve exact schema-1 config behavior. Schema 2 has an exact field set and
   adds `senderWindowSegments` (1..32), `transferMode` (`full` or `prefix`), and
   `prefixBytes`. Full mode requires zero prefix bytes; prefix mode requires a
   positive 4096-byte multiple, at most 32768, strictly smaller than the package.
   Runtime config remains debug-only, immutable after initialization, with the
   same target, endpoint, version and package bindings.
2. Keep the full-transfer public API and its ACK/error semantics. Add a distinct
   typed debug prefix API backed by the same private sender. Require observations;
   reject a nonzero first BEGIN durable or bitmap before DATA, require every
   confirmed prefix segment to have actually been sent by this invocation, and
   never send DATA outside the requested prefix or send END in prefix mode.
3. At exact durable completion, consume any latched error and verify a solicited
   ACK_ABORT with matching sequence/session, ABORTED status, exact prefix durable
   and zero bitmap. Timeout, malformed/error ACK, unsolicited abort, unresolved
   GATT write or cancellation cannot produce a successful prefix result. Existing
   best-effort recovery/failed-transfer cleanup stays unchanged.
4. Report BEGIN-write-to-prefix-durable-ACK and ABORT ACK separately using the
   existing App monotonic clock. Never manufacture an END timestamp or report
   prefix timing as the contract's full-ETU throughput. Record unique DATA bytes,
   total DATA bytes, actual window and verified closure independently.
5. The service verifies that the original firmware identity still responds after
   ABORT. A new probe-completed phase and a distinct producer verdict must not
   report upgrade success, run the reboot/target loop, or advance upgrade history.
   The existing snapshot envelope remains `not-completed` (no full upgrade);
   original integrity/footer/loss checks remain strict. The link summary uses a
   distinct probe label and never marks full-transfer outcome OK.

## Regression Matrix

Run configuration, shared sender, service, UI, observation and host-parser tests.
Include schema compatibility/type/range/mode failures; windows 4/8/16 and MCU
credit caps; exactly 32 KiB unique DATA across eight commits; nonzero initial
durable/bitmap; resume without invented bytes; forged durable/bitmap; malformed,
wrong-session, wrong-sequence, wrong-status or missing ABORT ACK; late errors,
cancelled/failed GATT writes; and no END, install, target verification or successful
upgrade envelope/history on a prefix path. Existing full OTA tests must still pass.
Use the standing development-only CI authorization on both hosts; no local
Flutter/Gradle build, production workflow, main push or release.

## Device Admission And Remaining Work

N02 remains NOT_RUN. Screen 460800/windows 4, 8, 16 and 921600/window 4;
four initial cells, at most two finalists repeated twice each (eight maximum).
Use one legal package and receiver, one APK, equal zero initial durable state,
fixed MTU/write mode/timeouts/retries and verified ABORT/idle closure. Each cell
writes staging Flash. No END means no installation, not no persistent writes.

The last retained receiver is 30214 / 3.2.14-p34w, 613344 bytes, raw SHA-256
`17d52849ec32719c748cb3475fd3d522da2762e29add905e56dc93ac63159242`.
Retain repaired Boot SHA-256
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`
and its target-owned TMR4 priority 2. This is historical identity, not a fresh
device check. The matching package, supported equivalent zero-state restoration,
APK identity, original log retrieval and both finite collectors must be prepared
before any physical cell. Do not replay a successful full upgrade for missing logs.

N03 still needs the whole-region verifier running in the receiving firmware.
N04 installation/candidate/backup/Boot/reconnect timings belong to a planned full
upgrade, not this prefix test. No physical speedup or acceptance is claimed here.
