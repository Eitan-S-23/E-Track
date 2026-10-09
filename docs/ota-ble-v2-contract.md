# BLE V2 Two-Block Supplement

Revision: 1 (2026-10-09). Decision: `OTA-DEC-015`. Task: P3-4.
Status: prospective scope approved; implementation, independent verification,
production freeze and release are NOT approved by this document alone.

## Scope And Precedence

This is the limited successor contract for the already-exercised negotiated
two-block receiver and synchronous WAIT_RX port. It is not a sender rewrite or
an asynchronous Flash-driver project. It changes only the v2 wire/credit rules
listed below. The frozen [v1 binary contract](ota-binary-contracts.md),
`PLAN-OTA.md`, P3-3-v9 and all historical bundles remain unchanged. Old peers
continue to use v1. HTTP schema v2 and the ETU format are separate version domains.

For a successfully negotiated v2 session, this supplement supersedes only the
v1-only command/ACK lengths, single-block credit and bitmap confirmation rules.
Unmodified integrity, version, device identity, lifecycle, retry, foreground and
performance requirements remain in force. In particular, it does not change
group16 Boot, ETU bytes, the upgrade UI flow, hardware pins or QSPI frequency.

The selected source reference is the saved `fw-wait2` receiver and installed
App revision `ef47dabd51f129c64a0be0945265192d17f70c17`, not arbitrary current HEAD.
These are development references, not a production freeze. Candidate disposition
and the unresolved trial5 failure are tracked in the
[current P3-4 note](ota-exec-notes/P3-4-transfer-next-2026-10-07.md).

## Framing And Fields

Retain `A5 5A | cmd:u8 | session:u8 | seq:u16 | len:u16 | payload | crc:u16`.
All multibyte integers are little-endian. `len` counts only payload bytes.
CRC16-CCITT-FALSE covers `cmd` through the last payload byte, excluding sync
and CRC. Verify length, command and CRC before any storage side effect. GATT
fragmentation does not redefine DATA boundaries. V1 INFO remains 50 payload
bytes with `proto_ver=1` and `max_window=32`.

| Message | Command | Payload in order | Payload bytes | Whole-frame bytes |
| --- | --- | --- | --- | --- |
| CAPS2 | 0x10 | nonce:u32 | 4 | 14 |
| CAPS2_REPLY | 0x90 | magic[4]="P2BL", version:u8=2, slots:u8=2, segment:u16=128, nonce:u32, max_in_flight:u32=24 | 16 | 26 |
| BEGIN2 | 0x11 | version:u8=2, total_len:u32, package_sha256[32], etu_header[64], epoch:u32 | 105 | 115 |
| DATA2 | 0x12 | epoch:u32, absolute_offset:u32, data[1..128] | 9..136 | 19..146 |
| END2 | 0x13 | epoch:u32, package_sha256[32] | 36 | 46 |
| ABORT2 | 0x14 | epoch:u32 | 4 | 14 |
| ACK_BEGIN2 | 0x91 | status:u8, assigned_session:u8, epoch:u32, durable_off:u32, accepted_off:u32, credit_end:u32 | 18 | 28 |
| ACK_DATA2 / ACK_END2 / ACK_ABORT2 | 0x92 / 0x93 / 0x94 | status:u8, epoch:u32, durable_off:u32, accepted_off:u32, credit_end:u32 | 17 | 27 |

ACK status values retain v1 section 5.7; there is no private success/error code
extension. Unknown status, invalid length and inconsistent assigned/header
session fail closed. A successful session ID is nonzero. Missing/malformed
epoch information in a frame/CRC error response cannot grant credit.

## Negotiation And Compatibility

1. Discover/subscribe the exact OTA characteristics and validate ordinary INFO
   first. CAPS2 uses session 0, an echoed query sequence and a fresh nonzero
   caller nonce. Its response must match the current connection generation,
   sequence, nonce, exact length, magic, version, slots, segment and cap.
2. CAPS2 neither opens storage nor grants DATA credit. An idle capable receiver
   remembers the nonce only after a successful response submission. BEGIN2 must
   use that nonce as its epoch, session 0 and the validated package identity.
   Missing negotiation, zero/reused epoch, invalid header, version/base or busy
   storage must not admit a new transfer.
3. A repeated matching BEGIN2 with the same epoch, sequence and package identity
   reports the existing session without reinitializing buffers or storage.
   An incompatible BEGIN while storage is owned does not replace that owner.
4. A new sender may select v1 only after a bounded CAPS2 timeout on the same
   still-valid, unpoisoned connection, before successful negotiation or any
   BEGIN2/DATA2 side effect. An old sender continues on unchanged v1. Malformed
   capabilities, unknown versions, a poisoned write, lost connection or a
   negotiated-v2 failure are not grounds for silent v1 fallback.
5. Stale v1 commands must not mutate a live v2 session. Late v2 responses from
   another connection/session/epoch are ignored, never new progress. Teardown
   must settle ownership before a fresh negotiated attempt can begin.

## Credit And Durable Progress

The receiver owns two 4096-byte RAM slots. DATA is still 128 bytes except the
final short segment; offset is aligned to 128 and bounded by the package length.
Success snapshots satisfy `0 <= durable_off <= accepted_off <= credit_end <= total_len`.
`credit_end = min(total_len, durable_off + 8192)`. Durable offsets are aligned to
4096 except final completion; accepted offsets are aligned to 128 except the tail.

The sender has at most 24 submitted, not-yet-accepted DATA segments, additionally
limited by its configured cap and the receiver credit. Reservations and GATT
completion are not receiver acceptance. A response cannot confirm undispatched
DATA. A 24-segment physical cap does not turn the 8192-byte credit into v1's
single 4096-byte window.

New DATA is accepted in order. Retransmission retains the original absolute
offset, bytes and sequence; a conflicting replay of buffered data terminates
the session. For resume offset R and BEGIN sequence B, DATA sequence is
`(B + 1 + (offset - R) / 128) mod 65536`; END uses
`(B + 1 + ceil((total_len - R) / 128)) mod 65536`. ABORT is bound to the session
and epoch and echoes its request sequence; it does not advance DATA sequencing.

`accepted_off` means RAM reception only. Advance `durable_off` only after actual
payload write, successful readback comparison and journal commit. Failure must
not clear the bad block's journal bit, advance durable or produce successful END.
An error snapshot supplies diagnostics only and never grants credit.

On a new connection/epoch, discard volatile acceptance and recover from the
existing matching package journal. BEGIN reports `accepted_off=durable_off`;
the incomplete block is erased and rewritten through the existing staging path.
UI progress remains durable-only. END requires complete durable storage,
quiescent IO, SHA/CRC/finalization and the existing activation checks. Final user
success still requires reboot/reconnect and the expected full raw image identity.

## Ownership And Boundedness

The existing synchronous Flash port remains selected. WAIT_RX may receive into
the other slot during permitted Flash waits; it is not a second Flash writer.
The borrowed program source stays immutable until the call returns. Recursive
poll cannot settle or start IO; ABORT, premature END and conflicting DATA may
stop reception but cannot free/reinitialize the overlay before quiescence.
No indirect-Flash receive callback may read busy memory-mapped external Flash.

The existing 4000 ms pipeline poll constant cannot interrupt a blocked synchronous
driver call and is not a demonstrated driver deadline. Qualify the actual waits,
watchdog/recovery path, nesting and relevant IRQ/stack bounds. Preserve the
measured 40 KiB overlay, 8192-byte OTA stack and 32-byte guard as candidate
constraints pending final map and targeted runtime verification.

First-error observation must retain command/session/sequence/epoch/status and
the last credit snapshot without granting credit or changing failure behavior.
Receiver diagnostics must distinguish program, restore, verify and journal
failures and preserve the first failing location. Missing historic values stay
unknown; new diagnostics cannot reconstruct a numeric status for old trial5.

## Measurement And Acceptance

Retain all [OTA-XC-BLE-TUNING](ota-cross-system-contracts.md#ota-xc-ble-tuning)
gates: a legal complete 1048576-byte ETU, at least 9 KiB/s, P95 at most 120 s,
every run at most 150 s, clean DATA retransmission at most 1%, one combination
with 30/30 consecutive complete successes, a 4-hour soak with no unrecoverable
error, and 10/10 reconnect recovery. Retain maxRetries=5, 30 seconds without
durable progress as an abort condition, and the supported 115200..921600 sweep.
50 kB/s is not a new acceptance gate or an active optimization branch.

For v2 the ACK latency sample ends at the first valid ACK whose durable offset
covers that DATA segment, not its accepted offset. Start at first complete
transmission of the segment; retries do not restart the sample. Preserve early,
missing and invalid samples as explicit limitations, not fabricated zero latency.
Use same-parameter clean runs and nearest-rank P99; final timeout remains
`clamp(3*P99_ACK, 500 ms, 2000 ms)`. Resumed or incomplete runs do not stand in
for complete zero-start reference-package measurements.

One approved finite formal plan supplies shared performance/stability observations.
Implementation first performs affected host tests and bounded discriminating
hardware checks, not a duplicate full campaign. Follow the
[acceptance execution contract](acceptance-execution-contract.md) for real source
and runner dependencies, reachable commits, freeze approval, NOT_RUN preflight,
failure retention and minimum reruns. This supplement is not an acceptance bundle.

## Required Verification Matrix

| Area | Positive case | Negative case / oracle |
| --- | --- | --- |
| Compatibility | Old peer stays v1; new peers negotiate exact capabilities | Bad length/magic/version/nonce/epoch cannot start v2 or trigger silent fallback |
| Credit and replay | Two-slot rotation, ordered delivery, duplicate same DATA | Future credit, wrong seq/session/epoch and changed buffered replay never advance progress |
| Storage | Exact original package bytes survive at least 13 blocks and resume | Trial5-shaped missing pages, restore/read/verify/journal faults preserve the 45056-byte committed prefix |
| WAIT_RX ownership | Receive the next block while borrowing the current source | Reentrant poll, ABORT and early END cannot free or mutate borrowed source |
| Diagnostics | First matching error retains numeric status and location | Unknown codes and stale epoch/seq remain distinguishable; error ACK grants no credit |
| Production | Functional defaults work with experiment entry points disabled | Missing real plugin/ACK/header/runner dependency invalidates its consumer |
| Formal evidence | Final same-input legal reference campaign | Resumed success, old debug builds and absent logs cannot supply formal PASS |
