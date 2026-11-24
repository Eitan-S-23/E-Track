# P3-4 N04 Offline Install Workload

## 2026-10-01 Measured Install Costs: P34-COST-05

`20260930T175922-37800/s04` is FULL_INSTALL_VERIFIED. Original report
`analysis/1790792784974267300/result.json` has SHA256
`547c0048dac76c0980050e46092b4c5cfbbfc2f503e71d5e025a5a380ff2e47e`.
The616048-byte30240 App reads back as
`04ea0a5bbde84af9d11f7032f0030ee528deae0385a2293602c4f81f8ece26ab`;
the complete optimized Boot remains
`a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
Final idle/SD/BCB4/confirm_done1 checks passed. Device/network owners exited0
normally at18:31:27Z/18:32:09Z. Retain30240, with no replay or downgrade.

The292649-byte FULL took32.016924s,8.9262178672KiB/s; installation/reconnect
was34.557491s. All2287 DATA segments were sent once, with complete ACK samples,
P99=279120us, zero retransmits and clean native counters. Boot residency is
6.2590631..8.1686763s. The trace still lacks a target CONFIRMED timestamp;
separate full final readback proves confirmation without filling that historical
timestamp gap. Neither50KB/s nor20s is achieved; this header-only screen is not
the1MiB reference or a general code-change installation benchmark.

The actual receiver emitted both complete eight-line cost records. FULL comes
from its original RTT channel; backup comes from the verified retained ring tail
during Boot. No lines were fabricated or discarded. The strict parser closes
each port sum plus residual to its phase total and agrees with BLEACT totals.

| MCU millis ticks | FULL | Backup | Combined |
| --- | ---: | ---: | ---: |
| Package reads | 36 | 0 | 36 |
| Internal App reads | 0 | 130 | 130 |
| Candidate reads | 67 | 0 | 67 |
| Slot reads | 0 | 240 | 240 |
| Erase | 7319 | 7194 | 14513 |
| Program | 985 | 962 | 1947 |
| XIP restore | 65 | 44 | 109 |
| Residual software/uninstrumented work | 2222 | 2658 | 4880 |
| Total | 10694 | 11228 | 21922 |

Erase accounts for about66.2% of these ticks, not independently calibrated wall
time. Residual is not pure LZMA decode. The bound result is
`.cache/p34-cost/measurement-30240/result.json`; original logs remain untouched.

## Payload Block Erase Candidate: P34-ERASE-01

### Confirmed Measurement And Next Probe: P34-ERASE-03

`20261001T112936-16300/s04` completed as `FULL_INSTALL_VERIFIED`. Original report
`analysis/1790856005667863200/result.json` SHA256
`e68b4fde5e7d477c1a09097f88836ee0a17a2039d7fe80756fbceb77625c9225`.
Retained30242 App616540 bytes SHA256
`822eb57da1210dacea670ad48d3c7f784e02ffc467b0c74de48525c98974939d`;
the whole Boot remains unchanged. Full raw identity, idle/SD and CONFIRMED passed.
The device/network owners exited0 normally at12:05:57Z/12:09:34Z; no forced stop.

Transfer292978 bytes took32.643871s,8.764626233KiB/s,2289 DATA segments and zero
retransmissions/duplicate ACKs/errors. P99=304671us. Installation/reconnect was
34.914724s; Boot residency6.7260114..8.2328545s. Neither50KB/s nor20s is achieved.
Compared with the old header-only30240 screen (8.926218KiB/s,34.557491s), there
is no demonstrated overall improvement. Do not attribute the difference from
the code-change30241 bootstrap to block erase alone.

The new erase path did execute: FULL32 commands/622592 bytes/2919 ticks, backup
33 commands/626688 bytes/2912 ticks, all failures0. FULL total6297 and backup6956
ticks sum13253, versus21922 old30240 ticks; ticks are not calibrated wall time.
Both original cost records and the verified retained RTT ring were checked.
Bound results: `.cache/p34-erase/measurement-30242/result.json` and `partition.json`.
The clean App transfer partition closes exactly: GATT15.816990s, last-send to
durable15.365397s, credit0.523841s, after-credit0.568430s, preparation0.066551s,
BEGIN0.214584s, END0.088078s. These are App-observable categories, not isolated
hardware costs or cross-clock subtraction.

Both30240 and30242 needed four reconnect rounds. In30242, two failed INFO calls
took10.036514s and10.012001s; successful INFO took0.843295s, and the installed
APK source uses3s between rounds. These waits overlap device work, so their sum
is not freely recoverable time. They support a bounded reconnect-cadence screen,
not a claim that all35s can be removed.

Next finite development work: create an exclusive
`dev/flutter/p3-4-reconnect-20261001` validation checkout under `.cache/p34-reconnect`,
based on the exact installed APK source commit. Add an explicit diagnostic
configuration for2s INFO and0.5s intervals, leaving ordinary settings unchanged.
Keep the180s overall window,20s round cap, poisoned-write recovery, abandoned
probe/notification ownership and final hardware/version/full-hash checks.
Self-test through the standing development workflow before requesting a diagnostic
APK; no local Flutter build, main merge, release or Boot change is authorized by
this plan. After APK verification, plan one legal header-only successor from
retained30242, not a replay. Source changes/testing are not yet completed.

### Confirmed Bootstrap: P34-ERASE-02

`20260930T195151-65600/s04` completed as `FULL_INSTALL_VERIFIED`. Original report:
`analysis/1790799277559745400/result.json`, SHA256
`543e64c7da60580dcc398e61a77fdd35d50bfbe830ff073e6b1cb36e1189cb34`.
Retained App30241 is616540 bytes, SHA256
`591f3ca1f8ae7c58e2fb5de97d766edc6a0dcefc38e29b1384d2bd389ecd5088`;
complete65536-byte Boot remains
`a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
Final idle/SD-ready/BCB4/confirm_done1 and both raw images passed. The device
worker exited0 normally at20:19:40Z; the network exited0 normally at20:20:31Z.
Neither was forcibly terminated and no OTA was replayed.

Transfer292961 bytes took42.181114s (6.782531314KiB/s), with2289 unique DATA
segments, zero retransmissions/errors,13 duplicate ACKs and complete latency
samples (P99=402700us). Installation/reconnect was48.636948s. Boot residency
was22.3150843..24.4766618s, reflecting a code-change update rather than the
previous header-only copy screen. The trace still lacks a target-confirmed
timing bracket; preserve that EVIDENCE_GAP. Separate final native readback and
confirmation establish the retained state, not a fabricated timing sample.

Both complete old30240 cost phases were recovered and strictly parsed from the
original FULL log and the descriptor-verified retained backup pending bytes.
FULL10528 ticks = erase7157 + other3371; backup11245 = erase7219 + other4026.
Their erase counts remain152/153, as expected for the old receiver. These are
MCU millis ticks, not calibrated wall seconds. This bootstrap is not evidence
of new64KiB performance. Bound derived evidence is
`.cache/p34-erase/measurement-30241/result.json`.

The existing30241-to30242 package remains unchanged. Four new fixed archival
mode guards passed, and its operational body is byte-identical to the prior
validated body. `.cache/p34-erase/measure-preparation/tests.json` binds the new
mode: archive completed30240, protect30241 and current configuration, no delete
or transfer. No session-suite rerun is required for unchanged product/runtime
inputs; the existing369-case development coverage is retained.

The30240 archive attempt stopped before phone operations because the exact USB
serial was not found. Preserve `.cache/p34-erase/archive-30240/result.json` and
`phone/usb/commands.jsonl`: bounded get-state calls reported device not found;
no quiesce/backup/move intent was created. USB stop/server/launcher exited0,
port5062 closed and the existing ADB key remained byte-identical. This is a
missing-phone prerequisite, not a failed30241 upgrade. Do not rerun this spent
output path or repeat OTA to recover logs. Once the user reconnects/unlocks the
phone, use a fresh, explicitly tested archive-recovery output after rechecking
this no-mutation failure and exact current30241 capture.

Host-only preparation continued successfully: `profile-erase-measure.json`
SHA256 `eb8de7d2e7d216a7ade33e340ef2bce91fa1c9a383fb3807514e3b9c7f6ea1a9`
binds the original confirmed30241 and unchanged292978-byte30242 package. No new
service, observer or transfer has started. Actual remaining intervention is
reconnecting/unlocking the phone; no routine authorization is requested.

The user subsequently reported the phone reconnected. An explicit
`--erase-measure-resume` archive entry now uses the fresh
`.cache/p34-erase/archive-30240-resume` directory. Before any backend/device
operation it checks the three exact original failure hashes, permits only the
recorded failed get-state queries, rejects any old quiesce/backup/move intent,
verifies normal USB closure/unchanged key and both completed OTA owners. The
actual capture/backup/non-overwriting move body remains byte-identical. Eight
host guard checks passed at `.cache/p34-erase/measure-resume/tests.json`; the
old failure is preserved. The fresh archive attempt is in progress, not a new
OTA. The already-prepared30242 package remains292978 bytes, SHA256
`158933d79d95dfde292a28d08fad0a453e01991aa0d4ce1e8963d1d483d9a1a0`.

The recovery archive completed with all three files byte-identical to host
backups, zero deletion/transfer, preserved30241 capture/configuration and normal
USB closure. The original failed directory is unchanged. New measure run
`20261001T112936-16300/s04` is preparing from the existing tested profile; no
rebuild, repackaging or replay was performed. The earlier30241 transfer has13
duplicate ACKs and is outside the strict zero-duplicate scope of
`p34_wait_analysis.analyze`; do not weaken that parser or claim its finer credit
partition for this run.

The30242 start command returned normally after871.772s. The same run reached
`READY_FOR_FULL_INSTALL_START` at2026-10-01T11:52:59Z, PID11712,292978-byte
package,921600/window28. Fresh capture
`1790855482189170-bfba33ff19dfd706ce2761f9` is healthy with32 producer lines,
zero starts/ends/loss/errors. The original Boot and30241 receiver admission,
native observer and verified service are ready. At invitation there were3353s
left in the cell and4208s in the service, with1396s of App-start allowance.
Invite one foreground Start for3.2.42-p34e; do not redownload, replay30241 or
restart these live owners. No new performance result is claimed before completion.

### Scope And Trigger

The measured erase dominance motivates an opt-in App-side64KiB payload erase
path. No Boot, staging credit/bitmap, wire format, EEPROM layout, header/marker
format, readback, rollback or30-second confirmation change is included.
`CONFIG_OTA_INSTALL_BLOCK_ERASE` defaults0. The HAL enables it only for cached
JEDEC `QSPI_JEDEC_W25Q128` and an enabled OTA Flash gate; other chips retain4KiB.
The raw driver API requires its caller to establish chip capability.

### Signatures

- `ota_erase_next_size(uint32_t address, uint32_t remaining, int allow_block)`
  returns0 for invalid alignment/length/overflow, otherwise4096 or65536.
- `qspi_erase_64k(uint32_t block_addr)` returns `qspi_status_t`; exact64KiB
  alignment and the complete existing production range guard precede WREN.
- `ota_backup_stage_with_block_erase(io, bcb_hal, out, erase_64k)` adds an
  explicit `int (*)(void *ctx, uint32_t address)` callback without extending the
  existing I/O structure. `ota_backup_stage` calls the same engine with null,
  retaining sector-only behavior and avoiding uninitialized new struct fields.

### Contracts

Both candidate and backup headers are erased separately with4KiB first. Only
complete aligned payload blocks inside the already-required extent may use64KiB.
Prefixes/tails remain4KiB; never round the extent outward to a64KiB boundary.
Backup programming remains fixed4KiB chunks with immediate readback; marker-last,
candidate-header re-erase, double-slot validation and BCB commit classification
remain unchanged. `erase_count` keeps successful4KiB coverage units: one
successful64KiB callback adds16, not1. A failed callback may have partially
modified Flash; counters never prove that an attempted failed operation had no
side effects. Cost logs count actual raw commands and requested bytes separately.

Raw block erase reuses the existing command geometry with opcodeD8h, WREN and
RDSR completion polling. Its4000ms bound is separate from the unchanged sector
timeout. Watchdog servicing remains before/after each command, and XIP restore
is attempted on success or failure; failure never falls back to another erase
or advances into programming/commit. The existing self-test reservation and
contracted8MiB window are not widened.

The locally available W25Q128BV Revision E manual documents D8h/24-bit addressing
and64KiB block erase (section7.2.25). Its table lists150ms typical/1000ms maximum;
JEDEC does not identify the board's exact silicon revision, so these are not a
measured board guarantee. Original manual is read-only; its byte-identical copy,
source hash, extracted text and tool receipt are under `.cache/p34-erase/references`.

### Validation And Error Matrix

| Condition | Required result |
| --- | --- |
| Disabled flag / nonselected chip | No64KiB operation; original4KiB coverage |
| Invalid/overflowing planner span | Return0; no inferred enlarged extent |
| Unaligned block / protected or out-of-window range | Reject before WREN |
| WREN, command or busy timeout | Propagate first failure, no hidden retry |
| Header erase failure | No payload bulk operation or programming |
| Failed/partially erased bulk operation | Stop; no STAGED; successful coverage count only |
| Erase reports success but leaves bad bits | Program readback rejects; no marker commit |
| XIP restoration fails after raw erase | Return failure; do not program or claim usable XIP |
| Normal large image | Exact backup and candidate contents, marker-last, verified STAGED |

### Good, Base And Bad Cases

For the616048-byte image, header+payload requires622592 bytes. With a separately
invalidated header, the planner uses32 candidate erase commands instead of152;
backup adds the mandatory candidate-header re-erase. Coverage is unchanged.
Null callback is the base case. Combining the header into a bulk command,
rounding the tail upward or interpreting a bulk callback as one covered sector
are rejected cases, not performance shortcuts.

### Tests And Build

Planner checks cover all sector-aligned starts over two block periods and all
image-sized lengths, including wrap rejection. Real backup tests retain old
cases and add maximum-size images, null fallback, header/payload/marker/commit
failures, partial failed erases, bad erased bytes and canaries beyond the extent.
HAL tests execute extracted real functions and reject mutants that merge either
header. Driver tests check opcode, alignment, range, WREN/command/busy ordering
and timeout propagation. These are host models, not electrical Flash timings.

Initial host run passed4367888 planner assertions,155967 backup checks,82 driver
checks and16 HAL tests. App-only GCC build produced616540 bytes (+492),
text615100/data940/bss560184 (BSS unchanged),0 errors and638 warnings. The first
warning comparator incorrectly retained build-root paths inside wchar_t messages;
its original report is preserved. The corrected review now passes: all638 warning
messages and multiplicities equal baseline after normalizing only the two known
build-root segments,0 new warnings/0 errors, no rebuild. The r2 host run preserves
the same counts and adds XIP-restoration failure coverage and7 normalizer checks.
Evidence: `.cache/p34-erase/build-review/result.json` and `tests/r2/result.json`.

Two immutable FULL packages are prepared in `.cache/p34-erase/assets/result.json`:
30240-to30241 bootstrap292961 bytes, then30241-to30242 measurement292978 bytes.
Each passed the real native decoder and four negative-package checks. The targets
differ only in the legal firmware header; inputs bind original30240 completion,
raw App/Boot, build/review, source copy and host tests. No physical64KiB operation
or new installation has run. Separate `ERASE_GROUPS` retain old cost manifests,
exact predecessor admission and filename validation. Integration checks are running.

The first integration attempt (`.cache/p34-erase/session-tests`) preserves127
executed tests and8 errors, including three class-setup failures. All errors trace
to the old decoder's original `ota_backup.h` record pointing at the now-edited
working tree, not to a device operation. Six selected methods never executed.
`p34_historical_inputs.resolve` now resolves only five explicitly named original
source records to preserved, SHA-pinned byte-identical archives: that header and
the four affected loader sources. Every other input still requires its exact
current bytes; no binary/package/report is exempt. The decoder comparison reads
the resolved original header, preserving the original equivalence result rather
than rewriting it. Runtime source admission separately pins current loader/helper
bytes and all five archives. Seven negative/identity tests cover this distinction.
No old manifest, package nonce, decoder executable or production source was
changed by this host repair. The second integration attempt uses a fresh directory.

The second attempt executed140 tests in764.158s:138 passed, and two recovery
tests encountered the actual `command.lock` held by concurrently preparing the
new profile. The preparation exited normally and removed its own lock. No lock
was forcibly removed and no guard changed. A serial two-test rerun passed in
`.cache/p34-erase/session-tests-r3`; its coverage joins those two PASS anchors to
the138 unchanged current PASS and229 unchanged prior PASS (369 development
coverage, not369 tests re-executed). Both real erase contexts, strict filename/
metadata validation, signed downloads, profile flags, Boot and all seven archive
provenance checks passed. Failed originals remain intact. Do not overlap these
legacy real-store lock tests with a live CLI preparation in later batches.

`profile-erase-bootstrap.json` is prepared against the exact30240 original report
and assets. Completed30239 capture archival is the next phone-only operation;
its fixed `--erase` mode protects30240, checks three files byte-for-byte, and
does not delete records or launch a transfer.

Archival completed: `.cache/p34-erase/archive-30239/result.json` records the
same-basename move of `1790788189634122-086835854f739f7c44a5b922` from observations
to observation-archive. All three files match verified host backups, eight live
directories became seven, and30240 capture/configuration were preserved. USB
closed normally; no transfer or file deletion occurred. The tested30241 start
command is now preparing its own fresh service/observer window.

Fresh run `20260930T195151-65600/s04` is now
`APP_LAUNCHED_CONNECT_AND_DOWNLOAD`. The start command returned normally after
499.6777s; the owned cell subsequently completed receiver checks, started the
native trace and launched the verified diagnostic APK as PID32391. External
service verification binds the292961-byte bootstrap package and strict FULL
filename. At the initial invitation, the network had4678s of verified service
reserve and the cell3452s, including1483s remaining for App start. The user is
asked only to connect/download3.2.41-p34e, not to begin BLE yet. No30241 install or
new performance result is claimed. Keep both live owners and source pins intact;
verify downloaded bytes and zero-start recording before inviting Start.

The same cell subsequently reached `READY_FOR_FULL_INSTALL_START` at20:07:43Z:
292961 bytes, target30241,921600/window28, PID32391. Fresh health has15 producer
lines, zero upgrade starts/ends, zero loss/errors and healthy=true. The network
and native owner remain live. The user may now tap Start once and keep the App
foreground; no further download or chat acknowledgment is required first.

### Wrong Versus Correct

Wrong: silently widen `flash_erase_4k`, erase a header and payload together,
skip verification or retry after an uncertain erase to obtain a faster number.
Correct: explicit optional callback, exact planned coverage, separately invalidated
headers, fail-closed restoration, original commit rules and retained evidence.

The next bounded screening, only after host/build review, will install the
candidate via30240-to30241, then measure it via verified30241-to30242 with the
same executable. Both retain the same Boot/APK and921600/window28. Bootstrap
does not measure its newly installed receiver. No self-test-region writes,
Boot flash, data deletion, release or formal acceptance are part of this plan.

## 2026-10-01 Confirmed Diagnostic Bootstrap: P34-COST-04

`20260930T163130-3100/s04` is FULL_INSTALL_VERIFIED. The original report is
`analysis/1790789202618306000/result.json`, SHA256
`f454d604a4ee9b27ef3365efd2b6ada86cce8f8a0e37d9c3d0a67f3a88414348`.
The616048-byte30239 App reads back as
`abfbaaf85ed317e628af2a228aeac8522db78e0ad8f672119feda46332a85db9`;
the complete65536-byte optimized Boot remains
`a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
Final state is idle, SD ready1, BCB4/CONFIRMED and confirm_done1. Original App
recording has9362 records, one completed upgrade and no loss/errors. Device and
network owners exited0 normally at17:33:00Z/17:33:57Z; no forced termination.

The292557-byte transfer took44.317011s,6.4467388225KiB/s; installation/reconnect
took49.511777s. All2286 DATA segments sent once, complete ACK samples,
P99=478638us, zero retransmits or ACK/UART/parser/drop errors. This is slower
than30238 and is not50KB/s or20s acceptance. Receiver30238 installed new code;
it did not measure the new cost collector. The previous header-only package is
not an equivalent comparison for general code-change installation.

Boot residency22.1103278..24.4543797s contrasts with the previous header-only
6.4127432..8.6487659s. Candidate10576 and backup11204 MCU millis ticks remain
uncalibrated against host wall time. Preserve the native trace's missing target
CONFIRMED timestamp as EVIDENCE_GAP; separate final readback proves actual
confirmation, not a time inside that trace. Compact bound findings are in
`.cache/p34-cost/measurement-30239/result.json`.

Next is the previously planned30239-to30240 same-executable measurement, with
the unchanged292649-byte package. Before opening it, archive only completed
30238 capture `1790777081899036-2e8880b661bed7f37dc19925`, protecting current
30239 capture `1790788189634122-086835854f739f7c44a5b922`. Use the standing
same-basename, verified host-backup, non-overwriting, non-deleting phone archive
authority. The exact completed App may be stopped; preserve its configuration.
No archive or OTA is replayed on uncertainty.

The parent service-readiness wait is being corrected from450 to900 seconds:
source/DNS setup exceeded450 although the owned service subsequently verified.
This changes only parent waiting, not network5400/supervisor5480/cell3900,
active-transfer900, App-start1500 or any remaining-time/source/identity gate.
Regress actual start with ready/timeout/closed-network outcomes before use.
No firmware, APK, Boot, protocol or confirmation change belongs to this repair.

The startup repair passed31 executed regressions plus326 unaffected original
PASS cases (357 development cases, not357 reruns). The archive's data/path/
lifecycle guard body is unchanged apart from bound capture identifiers; two
isolated wrong-current/selected-profile checks performed no archive writes.
Evidence: `.cache/p34-cost/measure-preparation/tests/coverage.json` and scope
proof beside it. The pre-edit files and prior test binding remain archived.

Original App-clock partition: GATT DATA writes22.618764s, last-send-to-durable
19.795086s, credit wait0.631011s, after-credit0.611400s, first-send preparation
0.129646s, BEGIN-to-zero-durable0.251763s and final-durable-to-END0.279341s.
These close to44.317011s;13 of2214 same-block gaps exhaust window28. This is
not an exclusive physical radio/Flash partition. Byte comparison finds144 of
150 shared complete4KiB blocks differ for30238-to30239, versus1 for30239-to30240.
Unrecorded Flash tail remains unknown; image differences alone do not prove
which physical blocks Boot copied or their duration. Original inputs and derived
results are in `measurement-30239/partition.json` and `changed-blocks.json`.

Completed30238 archival succeeded: three files match their host backups and
original completed snapshot,8-to7 recording names, protected30239/configuration
unchanged and normal USB closure. No deletion or replay. Evidence:
`.cache/p34-cost/archive-30238/result.json`. The prepared second-cell profile is
`.cache/p34-session/profile-cost-measure.json`, SHA256
`f0f475a603c2e9e1b20dc6a6121e1553dd32a2a31332ec00429f7aaedc84bffe`.
It binds actual completed30239 and the unchanged292649-byte30240 FULL package;
preparation made no device changes. Fresh service/observation admission is now
starting. Do not call this a completed30240 installation or measured cost result.

Second cell `20260930T175922-37800/s04` started through the normal parent path
without a wait timeout or network-resume invocation. It reached
READY_FOR_FULL_INSTALL_START at2026-09-30T18:18:13Z. PID2369/capture
`1790792260297690-eb603a4cbe55740b41f5caf2` supplies healthy zero-start records;
the phone's292649-byte package matches SHA256
`19902e9cbc271dfeff5211e788e68baf809a81c999cbb5a7f19f198f105c7a49`.
The live native observer confirms initialized30239/CONFIRMED, and receiver
readback closed normally. Since download was already complete, invite one
foreground Start directly, not a redundant download. Both finite owners remain
live for this action. No30240 installation or cost result is claimed yet.

## 2026-10-01 Pre-Cell Service Repair: P34-COST-03

The first diagnostic bootstrap service, `20260930T155736-6400`, failed strict
FULL filename validation before any cell/runtime or App launch. Its original
`NETWORK_INCOMPLETE` result remains preserved. Network worker exited1 normally,
without forced termination; prestart USB closed normally. The stopped App's
completed30238 capture/configuration remained unchanged. No OTA was consumed.

Change only served names to `p34-cost-bootstrap-full.etu` and
`p34-cost-measure-full.etu`. The new `assets/result-v2.json` references the
original manifest and archived generator, preserving package bytes, nonces,
decoder proofs and target/Boot bindings. Do not regenerate these packages or
rewrite the original failure/manifest/profile. The validator is not weakened.

`p34_cost_filename_fix.py` executes the five affected cost tests, including real
V2 metadata, strict App-contract validation, signed package download and a
negative old-filename case. Coverage publication requires actual PASS;351
unaffected tests retain their prior executed anchors. The ten isolated recovery
guard checks passed, with all writes intercepted. These checks are host-only,
not a new installed version or performance result.

`p34_cost_network_recovery.py` admits only the exact closed pre-cell failure,
rechecks the completed30238 lineage and unchanged assets, and records a separate
receipt before restoring the host current pointer. The successor v2 profile
changes only its descriptive name and manifest binding. Fresh normal device
admission remains mandatory. No second archive, reset, Boot flash or automatic
UI tap is part of this repair.

The five service tests passed; development coverage is5 executed/351 reused.
Original output and current source pins are in
`.cache/p34-cost/network-fix/tests/coverage.json`. The real host-only recovery
also completed, preserving the failed run and binding the v2 execution profile
in `.cache/p34-cost/network-fix/recovery.json`. The fresh normal bootstrap
start is now in progress; no diagnostic firmware installation is yet claimed.

## 2026-09-30 Install Port Cost Candidate: P34-COST-01

Following the user's instruction to act on the30238 measurements, the first
bounded implementation adds diagnostics, not speculative erase/write changes.
The old restore-only profile cannot attribute10523/11056 receiver ticks to
candidate/backup internals. Keep the actual30238/new Boot device untouched.

### Scope And Signatures

Default-OFF `CONFIG_OTA_INSTALL_COST` in `USER/HAL/HAL_OTA_Package.cpp` enables
seven non-overlapping port buckets: package read, internal base read, candidate
read, slot read, raw4KiB erase, raw program and complete XIP restore. All three
entry points (FULL/PATCH/backup), including early failure exits, begin/end the
same collector. Counts/bytes describe I/O after port argument validation, not
rejected argument attempts. Original watchdog calls, operation order, errors,
validation, checkpoint/rollback and30-second confirmation remain unchanged.

`ota_cost_begin(stats, now)` resets fixed storage; `ota_cost_add(stats, kind,
start, end, bytes, result)` counts calls/failures and accumulates uint64 byte/tick
totals. `ota_cost_finish(stats, now, residual)` rejects invalid buckets, counter
overflow, sum overflow or a port sum greater than the phase interval. Unsigned
32-bit tick subtraction handles one millis wrap; the bounded OTA lifetime is
far shorter than a49-day wrap period. There is no long-phase DWT subtraction.

`p34_install_cost.parse_one(text)` accepts one `P34COST` phase header plus exactly
seven unique `P34COST_IO` rows. It validates phase/kind, uint32 fields, uint64
high:low encoding, failures<=calls, zero-cost uncalled ports and the exact
port-sum+residual=total identity. A failed phase retains its nonzero result;
successful headers cannot hide failed port operations. Missing, malformed,
duplicated, mixed-phase or invalid-clock records fail closed.

### Measurement Contract

All new durations are MCU `millis()` ticks, not calibrated wall seconds. Small
reads may correctly record zero ticks. Residual includes decode, hashing,
unmeasured BCB work, watchdog/setup and instrumentation overhead; it must NOT be
called pure decode time. Do not mix these totals with host Boot residency or
App stopwatch timings. The existing `P34INSTALL` cycle profile is unchanged
and remains a separate restore-only measurement. New output goes directly to
RTT, with no heap allocation, filesystem output or UI progress changes.

Good: total10 ticks, seven1-tick buckets and residual3 closes exactly. Base:
flag absent removes all new state/timing/logging. Bad: missing one bucket,
sum11 with total10, wrapped call count, valid=0 accepted as a valid sample,
or labelling the residual LZMA-only; reject or preserve as unmeasured.

### Host Results And Build

- `tests/ota/test_ota_install_cost.cpp`:14 native assertions, including normal,
  failed I/O, zero-tick reads, millis wrap, reset, unknown kind, call overflow,
  sum overflow and all seven bucket IDs.
- `Tools/ota/p34_install_cost.py test`:12 parser checks and the original14 native
  assertions; `.cache/p34-cost/tests/result.json` is `COST_HOST_PASS`.
- `tests/ota/test_qspi_install_restore.py`:12 real-source HAL/driver model tests
  PASS, including cost-only and combined restore/cost profiles, default-OFF,
  all status pairs, error propagation and four negative mutations.
  `.cache/p34-cost/hal-tests/result.json`; this is not electrical NOR timing.
- App-only isolated GCC build from the exact immutable ACK-batch source plus
  only the modified package HAL/new header passes. BIN616048 bytes (+952),
  text614608/data940/bss560184: text+952/data unchanged/bss+184 versus its base.
 638 warnings exactly match the normalized baseline multiset;0 new warnings,
 0 errors. `.cache/p34-cost/build/result.json`; Boot was not built.
- Default-OFF ARM HAL object is byte-for-byte identical to the original18136-byte
  object, SHA256 `45ef9abd239c7825f83dd4d9db3a0b4e821c3fd6f261fdcf518f9abe8257932e`.
  Compiler flags came from the generated compile database, with only the new
  flag removed and output redirected. `.cache/p34-cost/build-check/result.json`.

At the host-build checkpoint the candidate was not yet packaged/admitted/installed. It is not a speed
improvement or formal acceptance result. Existing APK, retained30238/new Boot,
original evidence and shared index are preserved; no local Flutter build, CI,
commit/push, flash, reset or new OTA was performed for this host batch.

### Transfer Direction

Actual30238 GATT calls still serialize one142-byte DATA frame per platform
write although negotiated MTU permits244 bytes. This is a candidate overhead,
not proof that packing alone reaches50KB/s; the already-measured rolling browser
244-byte path peaked18.358KiB/s and was not durable OTA. A future Flutter batch
must retain frame completion, ACK sample validity, per-device partial-write
poisoning, cancellation and credit limits. Do not merely concatenate frames
under the existing per-frame completion accounting. Android priority requests
also need a verified development APK and connection-generation ownership; a
successful request does not prove a negotiated interval. No Flutter source was
changed in this diagnostic batch.

### Finite Device Plan: P34-COST-02

The user-approved continuing device work now plans two serial FULL cells:
30238-to30239 installs the cost collector; only a verified completed30239 may
admit30239-to30240, which keeps the executable unchanged and measures its cost
output. Both use921600/window28, the same verified diagnostic APK and current
optimized Boot. Keep30-second healthy confirmation, all durable/readback/rollback
checks and the normal900s active/3900s owner bounds. Root is sole operator;
host outputs remain under `D:/github/my/E-Track`. No Boot reflash, data clearing,
release, commit/push, new APK or automatic UI taps are part of this matrix.

`.cache/p34-cost/assets/result.json` binds292557-byte bootstrap and292649-byte
measurement packages, exact MAP/ELF/raw targets and both positive/four-negative
native decoder checks per package. No regeneration/replay after an uncertain
operation. Failure requires original-snapshot and full raw-state reconciliation;
retain the last verified target. Successful bootstrap is not a measurement of
the new collector; successful measurement is not50KB/s or20s acceptance.

Before starting the bootstrap, use the existing standing non-deleting archive
authority to move only completed30235 capture
`1790762757650934-dd5b864e26ea6ef1d45ad8d0` from `files/p34-observations/` to
`files/p34-observation-archive/` with the same basename. First verify/stop only
the exact completed diagnostic App, preserve its current configuration and
capture30238 `1790777081899036-2e8880b661bed7f37dc19925`, back up every selected
file and compare the finished snapshot against the original successful report.
Reject links, unknown files and existing destinations; verify all moved bytes,
the unchanged remaining names/configuration and normal USB closure. No deletion.

Prepare the full phone/RTT/after-reboot readback route before inviting connection,
download and a single user Start. Existing source-pinned helpers remain unchanged
while active. Cost records require complete per-phase rows and exact sums; a
missing/truncated record remains an evidence gap, never a reason to replay a
successful upgrade. Tick residual is not pure decode or host wall time.

Preparation is now complete: both exact packages passed native positive and
four-negative checks, and `profile-cost-bootstrap.json` SHA256
`0d5bcff827162d8c8aa42994790e958c0d11a085353375ecb818d388f028db75` binds the actual
completed30238 predecessor. Thirteen affected session tests passed in285.802s;
343 unchanged direct originalPASS cases are reused, development coverage356.
Exact pre-edit source snapshots, unchanged AST outside the bounded integration,
old-group axes/dependencies and original PASS anchors are preserved in
`.cache/p34-cost/session-before/` and `session-tests/`. No full356 rerun is claimed.

Completed30235 archival succeeded with three byte-identical backed-up files,
seven remaining capture names, current30238/configuration unchanged and normal
USB closure. `.cache/p34-cost/archive-30235/result.json`; no files deleted.
The bounded unused-network continuation helper now accepts an explicit current
run only in the verified new-Boot lineage. Seven admission checks pass; prior
helper bytes were reconstructed and archived with the original hash. It remains
unspent for this new group and will not restart a service or replay an attempted
cell. All prerequisites are ready for the bootstrap's fresh device admission.

## 2026-09-30 Completed Boot Copy Measurement: P34-BOOT-OTA-01

Run `20260930T133457-87100/s04` is `FULL_INSTALL_VERIFIED`. User reported the
completed upgrade; original App snapshot and independent full native readback
agree on30238. App615096-byte SHA256
`43c3c92fe207b779d7acaa9c05ddfdf6a224b49c3f76ff95bae33145d8c03b07`;
whole65536-byte Boot remains
`a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`.
BCB4/CONFIRMED, confirm_done1, SD ready1 and idle passed. Retain this state;
no replay, downgrade, reset, additional Boot flash or phone-record cleanup.

The original292114-byte FULL took31.608311s from BEGIN to END ACK,
9.0250813504KiB/s. All2283 unique DATA segments sent once, complete ACK samples,
P99=300177us, zero retransmits or ACK/UART/parser/drop errors. Installation to
verified reconnection took34.611291s. Against the preceding30235 upgrade,
throughput is22.4380% higher and installation14.452171s/29.4561% shorter.
Receiver, window32-to28, header and Boot differ: this is a sequential screening
comparison, not isolated same-package A/B. Neither50KB/s nor20s is achieved.
This small header-only best case is not the1MiB reference or general firmware.

Observed Boot residency is6.4127432..8.6487659s versus the preceding
22.8655572..24.8475859s. The trace closed before a targetCONFIRMED sample;
preserve its explicit confirmation EVIDENCE_GAP. The subsequent separate full
readback proves ordinary final confirmation; do not relabel it as a timestamp
inside the earlier trace. App candidate10523ms and backup11056ms are receiver
ticks, not independently calibrated wall durations or additive host phases.

The existing strict App-clock partition closes exactly to31.608311s:
GATT DATA writes16.207882s; last DATA send to durable14.468095s;
credit wait0.019225s; first-send preparation0.078246s; after-credit0.592725s;
BEGIN-to-zero-durable0.159077s; final-durable-to-END0.083061s.
Only3 of2211 same-block gaps exhaust window28. Increasing window is not the
evidence-supported next direction. Native staging erase/program3.351980s/
0.482827s and pump5.847981s overlap other activity and use another clock;
do not subtract them from App gaps to invent an exclusive radio/Flash cost.
ACK batching emitted403 write calls for43416 bytes; prior2285 calls for the
same ACK bytes took2.762264s versus0.876209s now. Calls are batches, not ACKs.

Next discriminators: reduce/measure GATT invocation cost and block-tail wait,
then instrument candidate/backup erase, program, verification and decode
separately before selecting an installation optimization. Preserve durable,
all checkpoint/rollback guards and30-second healthy confirmation. No new device
matrix, APK or successor package is implied by this completed observation.

Original report: `analysis/1790777941954503400/result.json` under the run,
SHA256 `f9237faaa7f435d6965d8b19eae5e8542958a1bb5e3860c1740621e0b2308357`.
Derived comparison/partition: `.cache/p34-boot/measurement-30238/result.json`.
Original snapshot has9344 records/9341 producer lines, one completed upgrade,
zero lost/errors. Device worker exited0 at14:23:59Z; network exited0 at14:30:56Z,
no forced termination. USB launcher/server/shutdown exited0, port closed and
read-only ADB key unchanged. Old service and upgrade invitation are closed.

Host history remains separate: parent start timed out while DNS was pending;
the original network later resolved at attempt7 and passed HTTPS/package checks.
`p34_resume_boot_network.py` resumed only the exact unused cell after full source
and remaining-time checks (one allowed/six rejected guard cases). It did not
restart service, regenerate assets or repeat OTA. Preserve the failed earlier
entry, DNS failures and all test reconciliation receipts.

## 2026-09-29 Capacity And Installation Bounds: P34-TARGET50-01

User requested 50 KB/s transfer and 20-second installation/reconnection, then
approved the proposed discriminating measurements. Codex root remains the sole
operator; all controllable outputs stay under `D:/github/my/E-Track`, with new
evidence in `.cache/p34-target50/`. No Boot replacement, BCB edits, release,
phone-record deletion or replay of a completed OTA is part of this batch.
Retain confirmed30230 and the original Boot. Existing device authorization and
its exact J-Link history exception are unchanged.

Baseline is the original completed pressure run20260929T135725-69500/s04:
1048576-byte legal PATCH,116.718954s transfer,8.7732109KiB/s,63.192273s
installation/reconnection. Its Boot residency is22.4460928..27.1815755s;
internal phase timing is NOT established. Millis ticks, host monotonic time,
App stopwatch and nested DWT durations must not be summed or subtracted across
clock domains. Report both50000B/s and51200B/s budgets; neither becomes a
replacement for the frozen P3-4 acceptance criterion.

Research before implementation:

- `Doc/ble.pdf` is the XY-MBO35A V0.0.5 manual,22 PDF pages. PDF pages5/6
  describe BLE5.3,1M/2M sensitivity and default30ms connection interval;
  pages8/9 enumerate AT commands but do not establish a sustained-throughput
  guarantee or current negotiated PHY/DLE. This document alone does not bind
  the installed module model/firmware. Do not invent a connection-interval AT
  command or treat its default as the current connection measurement.
- Existing `uart_probe.js` permits only31 distinct128-byte segments. This
  sub4KiB burst is not a sustained ceiling measurement. The real receiver's
  `session_handle_data` accepts identical same-offset/new-sequence DATA as
  `OTA_STAGING_DUPLICATE`, returns a frame-bound ACK and does not feed the
  package hash twice. A sustained diagnostic can exercise this path without
  supplying the32nd unique segment or END. It measures repeated-payload link
  capacity including parser/ACK overhead, NOT unique durable OTA throughput.
- The proposed diagnostic must first prove the actual receiver has no NOR
  mutation after BEGIN, including repeated data and ABORT. BEGIN for a new
  legal successor can initialize staging metadata; do not describe the whole
  session as read-only or reuse a rejected old-version package. Live admission
  still needs fresh full identity/CONFIRMED and a legal current-bound package.
- Existing Boot RAM outcome globals are not per-block phase progress. Existing
  coarse trace may miss confirmation because it reads receiver-layout state
  addresses after selecting the target image; compare exact layouts before
  attributing the gap. Precise Boot subphase wall time needs independently
  validated observation, not relabeling VTOR residency or a PC histogram.

Finite preparation/measurement matrix:

1. Validate the sustained diagnostic against real C session/staging and JS
   fault fixtures, with<=31 in-flight frames, unique seq, strict CRC/identity,
   bounded writes, monotonic duration and acknowledged ABORT. Source-bound
   tests precede physical transmission. Old source-pinned helpers stay intact.
2. One bounded private-USB read-only doctor of the retained phone/capture and
   existing owner closure. No App launch/taps, clearing, MCU reset or transfer.
3. Prepare142-byte versus244-byte GATT chunks, at most20 seconds DATA each,
   stopping before the existing30-second no-durable bound. Screen each once;
   repeat only the useful finalist once. Preserve failures. No END encoder,
   retransmission substitution for loss, automatic trial replay or deployment.
   This step remains NOT_RUN until exact sender/device/input and both
   observation/cleanup routes are ready; it is not implied by host-test PASS.
4. Reuse original installation observations and test improved phase-boundary
   analysis offline. Do not repeat an upgrade merely to repair a collector.
   A future necessary successor installation must bind its own tested inputs
   and observation matrix before opening the device window.

Decision oracle: a clean sustained result above the target supports further
sender/staging work, not a promise of durable50KiB/s. A lower result bounds
only that measured sender/configuration; it does not prove an immutable radio
ceiling. Missing live PHY/DLE, exact Boot phases and statistical reliability
remain explicit evidence gaps. Owner/next: Codex root implements the bounded
diagnostics and obtains live observations only after their prerequisites pass.

### Local USB Route Refinement

The user requested continuation after the first host checks. No approval of a
new phone-record deletion is inferred. The separate raw-GATT capacity screen
does not use the Flutter observation store, so all eight records can remain.
This is a different sender from Flutter and cannot be called a Flutter OTA
benchmark. Its localhost USB route replaces the failed historical public
browser endpoint; do not reopen that old endpoint or old worker.

Use `Tools/ota/p34_capacity_session.py` with the existing owned-worker/USB/MCU
primitives. Preparation creates a valid291667-byte FULL for30231 from the exact
30230 executable, native decoder/Boot/guard checks passed. No END is representable
in the sender. The packet is only a legal BEGIN input; it will not be installed.
Current code/image/Boot/BCB remain30230/CONFIRMED and unchanged.

New finite device matrix: quiesce only the verified completed diagnostic App,
preserving its config and all records; open one900-second owned worker, fresh
complete30230/original Boot/idle/CONFIRMED/921600 admission; set only owned ADB
reverse tcp8874 to the localhost HTTP listener; launch installed Chrome, no
automatic UI taps. Require an actual page-origin secure-context/Web-Bluetooth
receipt before inviting the real chooser and Run button. The page sends one
142-byte and one244-byte trial,10-second nominal DATA duration each,20-second
hard DATA bound and at most16000 frames. No automatic finalist repeat in this
entry. Each trial must have exact INFO, all ACKs, ABORT, native byte/error counts,
zero payload erase/program and unchanged first payload block. A new BEGIN may
initialize the staging journal; final staging is this legal package at zero
durable, not a claim that the old journal was restored.

The host snapshots the served JS/HTML, accepts only the local origin and a
session token, archives original browser result bytes and binds native terminal
ABORT=1 (wire ACK status is255, a different field). Failed/uncertain writes stop
the screen; permit only the ordinary session timeout, never a reset. Finish
with full retained App/Boot/state verification, remove only this reverse route,
close the HTTP listener/native reader/private USB, and preserve all failures.
The600-second interaction window reserves separate cleanup time. No Flutter
capture-cap change, deletion, new APK, Boot replacement or frozen-rule change.

Host results so far:17 sender tests,7 offline-analysis tests and8 real C fixture
checks passed; the C receiver processed16000 identical/new-sequence DATA frames
without any NOR mutation after BEGIN or double-feeding SHA. Two additional
identity-refresh sender tests and the local-route contract tests are being
validated before opening the live worker. These are not physical speed results.

Offline bound analysis: `.cache/p34-target50/bounds-r1.json` retains the measured
8.7732109KiB/s and conditional serial ceiling40139.2B/s, not an immutable link
ceiling. The actual compiled source manifest binds the30000ms health gate;
`PLAN-OTA.md` also explicitly requires the30s healthy main loop. The old trace
ended with target tick18064 and identical receiver/target state addresses,
before that gate could complete. It is not an address-drift defect or a failed
upgrade. Keep20-second usability/reconnection distinct from final CONFIRMED;
do not shorten the health contract.

Phone inspection/archival: doctor1790693252535281700 was stable completed with
8/8 directories and the exact current snapshot hash. The first generic cleanup
preview was mistakenly given the current run and rejected before USB/device
operations; its group whitelist also lacks receive-pressure, so it is not a
ready cleanup entry for this state. No guard was weakened. A separate read-only
preview at `.cache/p34-target50/capture-preview/result.json` resolved and archived
the old30229 directory
`/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790689316781787-c27d732d2b0839d86b5c5b5f`;
1042115-byte snapshot matched the original byte-for-byte. Both USB windows
closed normally; nothing was deleted. Do not act on the earlier deletion
question while this independent no-deletion diagnostic route is in use.

Final preparation:19 sender and4 route tests plus inline-page syntax passed in
`tests-r3/result.json`; unchanged7 analysis tests/8 native checks reuse their
direct original `tests-r1/result.json`. `quiesce/1790696327920238000/result.json`
closed exact completedPID21364 without clearing config or records. The new
capacity worker started at15:40:59 UTC with900-second lifetime; status is
`.cache/p34-target50/session/status.json`. No chooser invitation until actual
browser capability receipt. This is a new link-only diagnostic, not replaying
the completed pressure OTA or claiming any new throughput yet.

### P34-TARGET50-ACK01: First Physical Probe And Bounded Discriminator

The actual localhost browser capability and exact30230 INFO passed. The user
operated the page and the142-byte/window31 trial began. It stopped in the first
31-frame batch with `non-frame notification bytes`;244-byte trial NOT_RUN.
Original `session/trial-142.json` contains missing ACK prefix bytes, not merely
a split notification. Preserve it as a failed observation, no speed PASS.

Native closure proves all31 DATA plus ABORT received:4412=31*142+10 bytes,
expected_seq33, last ACK_ABORT seq33, terminalABORT=1, no RX/drop/UART/parser
errors. Firmware30230, original full Boot, BCB4/confirm_done1, SD ready1 and idle
remain verified. USB shutdown exits0, reverse8874 removed, native reader closed;
owned worker exited1 normally (measurement failure, not forced termination).
Original `session/owner/closed.json` ended15:42:53 UTC. No image installation,
reset, phone-record deletion or new OTA completion occurred. Diagnostic staging
is the new legal291667-byte package at durable0.

The noncommitted ABORT leaves the session's diagnostic RAM bitmap1 even though
its receiver pointer is released; the old complete-block prefix helper assumes
bitmap0 and is not applicable. Repair only the new adapter to validate idle,
bitmap1, last exact ABORT, original zero-durable journal and frozen native
counters. Do not change the receiver or old helper. Also preserve the primary
HTTP/measurement error instead of overwriting it with a generic closure error.

Next discriminator, not a replay: `--session session-w4`, same asset/receiver/
921600/browser/strict parser, only four in-flight frames instead of31. Two
ordered142/244-byte cells,10-second nominal each,20-second DATA hard limit;
stop the whole screen on the first error. A clean result implicates a burst-
sensitive return path; another malformed response requires investigating the
MCU TX/module/Android/browser boundary, not declaring a radio ceiling or
relaxing CRC. Same output/ownership/cleanup bounds. Host route tests include
window-binding and residual bitmap1 regression. Archive old served sources
under `session/sources/` before edits; old worker/receipts remain closed/frozen.

Window4 actually ran and failed at the same second DATA ACK: its first6 bytes
are absent from the browser notification stream. Native reception is complete:
578=4*142+10 bytes, zero RX/drop/UART/parser errors, exact ABORT seq6 and idle.
The244-byte cell again did not run. Both native closures reverified full30230,
the original Boot, BCB4/confirm_done1 and SD ready1. USB stop/server/launcher
exits0; both owned workers exited1 for the failed measurement, not forced
termination. Comparison is `.cache/p34-target50/failure-comparison.json`.
Neither sample lasts10 seconds, so sustained throughput remains NOT_MEASURED.
Do not repeat either unchanged input or blame UART baud from these observations.

Next missing discriminator is Android HCI versus browser notification bytes.
Read-only readiness on Android33 found empty standard snoop-mode properties;
the two public log paths are absent and the protected
`/data/misc/bluetooth/logs/btsnoop_hci.log` returns Permission denied. This does
not prove that the protected file is absent or logging is disabled. The scoped
Bluetooth-manager dump returned exit0 but zero stdout/stderr, so its
`BLUETOOTH_DUMP_RETRIEVED` envelope is NOT usable HCI evidence. Original command
receipts remain under `hci-readiness/phone/usb` and `bluetooth-dump/phone/usb`;
both private USB owners closed normally. No full-phone bugreport or system
setting mutation was attempted.

Human prerequisite: enable full Bluetooth HCI snoop logging in the phone's
developer options, then toggle phone Bluetooth off/on. First verify the log
retrieval route; only then prepare one discriminating short probe. Do not ask
for another firmware upgrade, delete records, shorten the30s health contract,
silently skip malformed ACKs or advertise a50KB/s result. No new Boot internal
phase timings have been captured. All probe/native/USB/listener owners are now
closed and the current firmware is retained. A first combined closeout command
exceeded cmd.exe's command-line limit before execution; shorter read/analysis
commands produced the audit without rerunning a device operation.

### P34-TARGET50-HCI01: Enabled-Setting Verification, 2026-09-30

The user reported HCI logging enabled. Read-only private USB inspections used
the exact phone/APK and preserved all recordings. Standard properties remain
empty; the vendor property `persist.sys.bluetooth.btsnooplogmode` reports
`disable`. Neither property alone proves the protected log file absent.

The direct AdapterService route is now verified:
`dumpsys activity service com.android.bluetooth/.btservice.AdapterService --print`.
It returned 92243 original bytes in `hci-direct-check/adapter.stdout`, unlike
the earlier empty manager dump. It reports Bluetooth ON,
`mSnoopLogSettingAtEnable = empty` and default setting null. Its retained
enable-transition records are September 11, not a new transition after the
user's setting change. No BTSNOOP/BTSNOOZ or packet data were found. This proves
scoped service-diagnostic retrieval, NOT usable full HCI capture/export.

Next human action: turn phone Bluetooth off/on once after selecting full HCI
logging; keep USB connected. Then inspect fresh service state and the scoped
export route before opening a new finite diagnostic cell. Do not issue another
OTA, assume an intact HCI packet, or reuse either spent browser probe. No
setting mutation, Bluetooth toggle, MCU attachment/reset or full-phone bugreport
was performed by the agent. `bugreportz -h` was help only.

Correction to ACK01: the prior "8 missing bytes" claim was a counting error.
`ack-prefix-correction.json` binds both original browser captures. Their second
ACK has 13 surviving bytes of an expected 19-byte frame, starting at offset6
with length `0900`. Reconstructing sequence3 gives a CRC match in both cases;
the missing six bytes are `a55a82010300` / `a55a82020300`. The preceding ACK is
complete and the next frame is sequence4. This remains an offline inference
about the browser stream, not an observed MCU TX/HCI packet or a root cause.
Original captures/comparison reports and the strict live parser are unchanged.

Evidence under `.cache/p34-target50/`: `hci-enabled-check/result.json`,
`hci-adapter-check/result.json`, `hci-direct-check/result.json` and each scope's
`phone/usb/closed.json`. All three USB scopes closed normally with
stop/server/launcher exit0, port5062 closed and the read-only ADB key unchanged.
New output audit: `hci-check-closeout.json`; the prior closeout is preserved.
No firmware/Flutter change or new sustained-throughput measurement occurred.

#### HCI01 Follow-Up: Full Setting Active, Export Not Yet Proved

The user confirmed phone Bluetooth off/on. The fresh service dump now records
the September30 01:06:05..01:06:06 enable transition, Bluetooth ON and
`mSnoopLogSettingAtEnable = full`; the vendor property is also `full`.
Originals: `.cache/p34-target50/hci-after-toggle/`. Do not ask for another
toggle or continue describing the logging setting as disabled. These are
setting/lifecycle observations, not proof of an exported HCI packet.

Direct AdapterService output is23825 bytes with no BTSNOOP/BTSNOOZ packet block.
The known public paths are absent and `/data/misc/bluetooth/logs` remains
permission-denied. `bluetooth_manager --print` also returns zero bytes.
`dumpstate -h` is inaccessible to shell (exit127); the later binary listing
specifically reports Permission denied, so do not claim dumpstate is absent.
The readable init configuration declares the ordinary `dumpstate`, `dumpstatez`
and `bugreportd` services. Their availability does not prove report generation
will succeed. No service was started by these read-only inspections.

The remaining identified route is `bugreportz` (previously verified version1.2
and help), retrieving a system report and extracting original Bluetooth logs.
Phone `/bugreports` is a symlink to
`/data/user_de/0/com.android.shell/files/bugreports`; the leaf does not currently
exist. This is a new output/privacy scope, not another routine OTA permission:
system reports can contain unrelated application diagnostics/device information.
Request at most two reports within that exact directory: one to prove export,
then one after a new short HCI-backed cell if export passes. Host outputs stay
under `.cache/p34-target50/hci-export/`; process locally, no upload or deletion
of existing phone files. No report command, protected-log copy or new physical
probe may be inferred from this preparation. Recheck actual output ancestry
and generator side effects before execution even if the scope is approved.

Read-only export receipts: `hci-export-capability/result.json` and
`hci-export-config/result.json`, relative to `.cache/p34-target50/`. Three fresh
USB scopes closed normally; output audit is `hci-after-toggle-closeout.json`.
No MCU attachment, reset, firmware/APK change, BLE probe or OTA was performed.
The retained30230/Boot and all prior recordings were untouched. HCI packet
content, corruption boundary and sustained throughput remain unmeasured.

#### HCI01 Report Authorization And Finite Export

The user explicitly approved the described phone directory/report scope and
requested no repeated unnecessary authorization. At most two reports in
`/data/user_de/0/com.android.shell/files/bugreports` are authorized for this
diagnosis: export proof, then post-probe evidence if useful. No per-report or
routine retrieval question is required. Existing phone files are not deleted;
all host outputs stay in `.cache/p34-target50/hci-export/`, with no upload.

`Tools/ota/p34_hci_export.py prove-export` is a fresh write-once first-report
entry, not an OTA runner. Before generation it checks the real phone parent,
the `/bugreports` alias, any existing leaf directory, existing filenames,
full logging and absence of another report service owner. Generation is bounded
to900 seconds and readback to180 seconds/256MiB. Failed or uncertain generation
is preserved and reconciled, never replayed to recover a missing host result.
Only original BTSNOOP ZIP members (at most8/64MiB) are retained on the host;
the whole report is hashed/read in memory and remains on the phone. ZIP paths,
duplicate members, record lengths, H4 lengths, truncation and drop counters
are checked. Export success is not target-link/throughput evidence. No new
physical probe starts before this route is proved.

#### HCI01 Export Proved And New Screen Prepared

Report1 started at01:42:14. USB disappeared after5.302 seconds; `bugreportz`
returned only BEGIN/progress, not OK. Subsequent property reads failed because
the phone was absent: the empty strings in the original `failure-services.json`
are NOT evidence that report services stopped. Keep that failed host result.
The independent read-only reconciliation found the same completed20583732-byte
ZIP, stopped dumpstatez and a native log ending at01:45:07 (173 seconds).
Report SHA-256: `77f06179f483a4552f8ff0de2c38559fc9e62f46da2edc776e0d136d7197d4b7`.
No replacement report was generated. The directory now contains that ZIP,
its104369-byte dumpstate log and8-byte `dumpstate-stats.txt`; no deletion.

The OEM names HCI logs `bt_hci_<date>_<time>_d.cfa`. The first retrieval's
filename-only filter missed them, not a failure of recording. After extending
the exact Bluetooth-log selector, original files were retrieved from the SAME
hashed archive into `hci-export/cfa-retrieved/`. Both contain standard BTSNOOP
version1/H4:14313 and9875 packets, no truncated packets or reported drops.
Their sizes/hashes and original ZIP member names are in that directory's
`result.json`. The full system report was never persisted on the host or
uploaded. The two target-bound ATT analyses found no E-Track connection; they
prove export/decoding capability, not the corruption boundary or throughput.

Host tests additionally exposed Windows ZIP member-name normalization. Validate
`orig_filename` against `filename` before accepting archive paths; use a raw-name
fixture instead of accidentally testing an already-normalized path. Failed
tests-r1/r2 remain; corrected tests-r3 passed16, tests-r4 passed29 including
11 HCI/ACL/L2CAP/ATT tests. The latter cover address/direction/generation binding,
fragment loss, overflow, handle reuse and non-target exclusion. No parser guard
was weakened. Service-read failures now retain an error instead of blank state.

New finite screen: `Tools/ota/p34_hci_session.py start`, output
`.cache/p34-target50/session-hci-w4/`. Sole Codex operator, unchanged30230,
original Boot, legal291667-byte package,921600 baud/window4 and unchanged strict
browser sender. Reuse the original142/244-byte cells in order, nominal10 seconds
and20-second hard DATA bound each; first error stops the entire screen. No END,
image installation, reset or record deletion. This is a discriminating new
HCI-observed input, not replay of either spent session. Validate current full
logging inside the owned USB scope before opening the page. Ordinary MCU full
identity/CONFIRMED/SD/idle admission and closure remain unchanged.

The wrapper reuses unchanged capacity Python/HTML/JS primitives, with fresh
source-bound tests and a900-second owned worker. The new session does not edit
the old sources or evidence. After an actual DATA probe AND normal USB/native/
HTTP/worker closure with retained state verified, `p34_hci_session.py report`
may generate the authorized report2. Never generate a system report during the
probe: report1 demonstrated that USB can briefly disappear. If the reply is
lost again, retrieve/reconcile the named original as above without generating
another report. Compare only target-connection ATT values against original
browser notifications; do not infer a UART/module/browser cause beforehand.

#### HCI01 Executed: Missing Bytes Already At The HCI Boundary

The HCI-backed142-byte/window4 cell ran and stopped on the same malformed
second DATA ACK. Native receipt is578 bytes (4 DATA + ABORT), terminalABORT,
zero receive/drop/parser/UART counters; complete30230, original Boot,
CONFIRMED/SD-ready/idle were reverified. The244-byte cell did not run. Worker
exited1 normally at02:24:34, with native/USB/HTTP owners closed and J-Link
history unchanged. This is not a sustained throughput measurement.

Authorized report2 completed and exported without the earlier USB interruption.
Originals are in `hci-export/probe-evidence/`:16384 +6590 complete HCI packets,
no reported drop/truncation. The first file includes the exact target address,
one complete connection/disconnection and48 ATT frames. The second has no
target connection. No third report is part of this batch.

`hci-export/ack-boundary.json` binds both raw/decoded HCI and browser/native
originals. All seven browser writes match one unique FFF2 write-command
sequence at HCI records13364,13377,13380..13383,13389. Discovery binds
FFF1 value handle0x000c and FFF2 value handle0x000f. The four browser
notifications match HCI records13376,13379,13386,13388 byte-for-byte, including
the malformed value. Expected INFO+BEGIN+four DATA ACKs total156 bytes;
HCI and browser each have150. ACK sequence3 lacks `a55a82010300` (six bytes).
The later ACK_ABORT at13391 is intact and is not mixed into the comparison.

Disposition: `CORRUPTION_ALREADY_PRESENT_AT_HCI`. The Android GATT/Chrome
receive processing is not the origin of this observed loss. MCU encoding/UART
output, module reception/packetization and controller-side behavior are not yet
individually separated. Existing real C session tests already verify exact CRC/
sequence/status/bitmap ACKs for16000 duplicate-payload frames; these are software
encoding evidence, not an electrical UART capture. Do not weaken the live parser.

This Chrome connection negotiated MTU247 and bidirectional data length251.
Connection interval changed45 ->7.5 ->45ms; the final45ms update precedes DATA.
No PHY-update observation establishes actual PHY. These parameters do not stand
in for Flutter OTA parameters or prove a radio throughput ceiling. Seven new
offline correlation/parameter tests pass in `hci-export/comparison-tests-r1/`.

### P34-TARGET50-RATE01: Reversible Return-Path Rate Discriminator

Owner: same Codex root and already-authorized device/task. One new independent
screen, `p34_rate_return.py start`, output `session-rate460-w4/`. Preserve
30230/full original Boot, legal package, Chrome sender, window4 and strict
142/244-byte cells (10s nominal/20s DATA bound, first error stops all). The sole
intentional link change is UART921600 ->460800, using the existing proved AT
probe/set/deferred-reboot controller. No MCU reset, image install, END, record
deletion or third system report. Capture any negotiated-parameter uncertainty;
this is not a fully controlled radio A/B or a50KB/s solution (the lower UART
cannot support50KB/s payload). It tests whether the ACK-prefix failure changes
with UART rate before choosing a more invasive firmware/module investigation.

Both normal and error cleanup call the existing verified rate restoration to
921600 before final full identity/CONFIRMED/SD/idle readback. Unknown AT outcomes
remain explicit failures, never blind setters. The worker bound is1200s: the
old900s capacity allowance plus two bounded150s rate transitions. The browser
window and ordinary cleanup allowances are not shortened. Source-bound host
tests passed18 Python and19 sender checks in `rate460-tests-r1/`. Existing
native/asset proofs are reused; no new firmware or APK is built.

The capacity worker now takes an explicit validated baud argument, defaulting
to unchanged921600 behavior, and binds native decoding/restoration to it. Before
this edit the exact HCI-run capacity source and route tests were preserved in
`hci-export/frozen-sources/`; their hashes still match the closed HCI admission.
Old sessions/report entries remain spent. A clean460800 sample supports a
rate-sensitive hypothesis only; a repeated prefix failure rejects that simple
hypothesis and calls for MCU-TX/module-boundary instrumentation, not more
identical trials or a claim that50KB/s has been achieved.

RATE01 host admission ended03:16:32 before reaching the MCU: the exact phone
was absent throughout eight checks in the20-second USB readiness window.
No AT setter, MCU attachment, browser page, DATA, or baud change ran. Preserve
`session-rate460-w4/` as the failed host attempt, not a failed460800 experiment.
USB stop/server/launcher exits0, port closed; worker exited1 normally without
forced termination. The `selected_baud` and older `final_retained_baud` fields
in that failed receipt describe planned settings, not observed changes. The
current adapter names the latter `required_retained_baud` to avoid that ambiguity.

Human prerequisite is reconnecting/unlocking the exact USB phone, not another
authorization. After that, use the fresh bounded entry:
`p34_rate_return.py start --session session-rate460-w4-usb2`.
This selector requires the original pre-device failure and absence of MCU
activity; it cannot replay an executed or uncertain physical test. Updated
`rate460-tests-r2/` passed19 Python tests; the unchanged19 sender checks reuse
their original source-bound result. No fresh worker has been started yet.
All owners are closed. Latest output audit: `hci-export/ack-boundary-closeout.json`.

### P34-TARGET50-SERIAL01: Burst Dependence Discriminator

RATE01 update: `session-rate460-w4-usb2` executed and closed normally at
2026-09-30T05:03:20Z with an incomplete diagnostic. Four DATA frames reached
the MCU (578 received bytes including ABORT, clean RX counters). ACK sequence3
in browser notifications lost the four-byte prefix `a55a8202`; no new HCI report
was generated, so its HCI boundary remains unmeasured. This differs from the
six-byte loss observed at921600. Restored921600 is proved by the AT response
and retained word, not the frozen460800 profile. Final full App/Boot hashes,
CONFIRMED, SD ready and idle were verified; USB and native owners closed.

Next finite cell: same root/operator/device, App30230, original Boot and
`assets/full.etu`;921600, window1,142-byte GATT writes,10s nominal/20s DATA bound.
Only one cell is needed: with window1 the244-byte ceiling would still produce
the same142-byte writes. `p34_serial_return.py start` creates a fresh owned
900-second session under `.cache/p34-target50/session-serial-w1` and reuses
the existing sender, collector, readback and cleanup. No END, installation,
MCU reset, AT setter, third system report, or deletion of phone records.
Admission requires the actual lower-rate failure, verified921600 restoration,
closed owners and source-bound host tests. Browser chooser/start remain human
actions. First error stops the screen; no retransmission or implicit replay.

Oracle: a clean serial sample supports burst/overlap dependence, not a proved
module defect or durable OTA speed. Failure still requires TX/module-boundary
observation rather than blind baud retries. Radio negotiation is unmeasured
in this new connection and cannot be treated as a controlled constant. A serial
sample is diagnostic, never a proposal to meet50KB/s using stop-and-wait.

Host checks: `serial-tests-r1/result.json` binds21 Python tests and20 sender
tests, all passing, including delayed-ACK stop-and-wait ordering. No production
firmware or Flutter source was changed for this discriminator. The current
checkout has no `.trellis` directory; project contracts and the local debugging
skill were used. Shared worker defaults remain142/244 and921600 for historical
callers; old admission hashes remain historical, not new runnable authorizations.

Existing frozen336-byte profiles at `session-hci-w4/mcu/samples/final/profile.bin`
and `session-rate460-w4-usb2/mcu/samples/final/profile.bin` each record6 ACK-send
calls,115 requested bytes (BEGIN20 + four DATA19 + ABORT19). Total call time is
1138.722us at921600 and2266.688us at460800; maximum call time199.229us and396.563us.
These aggregates support software-call completeness only, not intact UART-pin
bytes or per-ACK timing. They cannot assign the defect to the module.

SERIAL01 executed:90 DATA frames in10122.5ms, all ACKed,1.111386KiB/s repeated
payload (not durable throughput). Native RX12790 bytes, all RX/parser errors0,
no payload erase/program, unchanged payload readback and zero durable journal.
ABORT confirmed; full retained App/Boot,921600,CONFIRMED,SD/idle verified. Worker
exited0 without force at2026-09-30T05:26:36Z; USB and native reader closed.
This supports burst/overlap dependence. It does not establish reliable window4
operation or50KB/s. Original: `session-serial-w1/result.json` and `trial-142.json`.

Next host-only preparation (not device admission): copy the source-hash-verified
30230 lineage into `.cache/p34ag/f`, preserving `.cache/p34sr` and all root
production files. Add a diagnostic-only1ms post-ACK UART-idle gap, with a2ms
TX-drain timeout and no interrupt masking. Use actual transmit-complete, not
data-register-empty, and the already-validated288MHz DWT clock. Reuse existing
GCC App configure options and compile only App; never replace Boot. First host
tests cover TX busy timeout, actual-idle-before-gap, zero gap and counter wrap.
This is a candidate experiment, not an established fix or a speed claim.

### P34-TARGET50-GAP01: Isolated ACK-Gap Bootstrap

Codex root continues the user's approved finite P3-4 device scope. Writable
root remains `D:/github/my/E-Track`; no Boot replacement, arbitrary BCB edits,
record deletion or additional Android system report. Existing exact native
J-Link history permission remains limited to its connection-history file.

Host candidate: `.cache/p34ag` copies3267 hash-verified30230-lineage files;
only `USER/HAL/HAL_Bluetooth.cpp` changes and `USER/HAL/p34_ack_gap.h` is added.
GCC App build succeeded in243.94s after configure22.73s. Raw614736 bytes,
text613296/data940/bss559760;104-byte App growth, unchanged static RAM.
Original Boot was not built. There are638 warnings and0 errors. The first
`build.json` warning count was wrong because of an overescaped regex; preserve
it and use `assets/build-review.json` with the original raw log instead.

Candidate30232 FULL is291877 bytes, SHA256
`a1435094c6b7946f310f665c88461c5b818b92e53f5450d853420d0ea20fc37d`.
Forward restoration30233 FULL is291746 bytes, SHA256
`02a986932d3c3cb82478fb0f0e76637e8064b3c9bd227731f5008222a5c98860`;
it restores30230 executable behavior without a version downgrade. Both passed
Python/native byte-identical decode, Boot-header and workspace/guard checks.
Three negative candidate packages (CRC, length, same-version) were rejected
before preparation. Recovery is an offline asset, not an automatic second OTA.

Finite device matrix: one `ack-gap-bootstrap` FULL30230-to-30232 through the
existing verified Flutter APK at921600/window32, usual strict timeout/retries,
original App recording and full native readback. The old30230 receiver performs
this transfer and activation; it is not a measurement of the new gap. Normal
Boot reboot, rollback protection and30-second confirmation rule remain intact.
Retain fully verified30232 and original Boot. An uncertain installation stops
dependent mutations for reconciliation; do not reset/flash to repair collection.
The worker and network keep the existing bounded full-session deadlines.

After real confirmed30232, prepare a separate non-installing burst screen bound
to its new image/MAP and a legal newer diagnostic header. No30230-bound sampler
or old30231 package may be reused against30232. A clean window4 screen supports
the gap candidate only; durable throughput and installation targets need later
full measurements. On failure preserve originals and decide whether the prepared
forward restoration is needed; do not silently reinstall or repeat the screen.

The session adapter identifies the already-closed serial diagnostic's zero
durable journal as a known prior package; it never counts it as the new target
or overwrites it from the host. Old group dependencies remain unchanged. First
full tool regression:340 tests,338 passed, one outdated matrix expectation and
one old no-successor test assumption failed; originals remain in
`.cache/p34-session/tests/1790748717573576900`. Fixes retain no-replay checks and
require an explicit new prepared profile. The suite took582.82s, so its host-only
deadline is now900s; no device/transfer deadline or acceptance gate was relaxed.

Tool validation closure: second full batch
`.cache/p34-session/tests/1790749461200500400` ran340 tests in614.42s.338 passed;
the old600s assertion and historical recovery's now-stale source assumptions
failed. The runtime recovery guard correctly rejected source drift and was NOT
weakened. Two test methods were updated: bounded900s host timeout, and real
current-source rejection plus a clearly mocked original-source positive case.
The first targeted run (`.cache/p34ag/tests-r3`) caught external-tool paths in
that test's relative-path logic; its failed log is preserved. The corrected
two tests passed in `tests-r4`. AST comparison proves all other test nodes
unchanged, and every other source hash matches the second full batch. The new
source-bound receipt reuses338 actual passes plus2 executed passes, not a
claimed fresh340-test run. `tests/latest.json` points to that disclosed result.

Prepared profile: `.cache/p34-session/profile-ack-gap-bootstrap.json`, SHA256
`410f42c7da7e6c4cfbbe32513411f1e213d8505bcddb1d9ce4f32c8f973ee83b`.
This is not an installation receipt. New device start is tracked by the normal
session runner and must be reconciled before any further start or firmware work.

Start outcome: `20260930T064223-24800` stopped at the read-only phone preflight:
eight capture directories, matching the installed recorder's hard limit8.
No plan, network, App launch, MCU attachment or OTA occurred. Current session
pointer remains the completed30230 run. Private USB closed normally with all
exit codes0. Do not raise only the host STORE_LIMIT; the installed Dart recorder
also rejects `directories >= 8`.

Read-only review `.cache/p34ag/store-review/result.json` revalidated the exact
30229 directory and copied its three files byte-for-byte against their original
retained host versions. Resolved phone source:
`/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790689316781787-c27d732d2b0839d86b5c5b5f`.
Proposed, NOT authorized/executed: move this single directory to the sibling
`/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observation-archive/1790689316781787-c27d732d2b0839d86b5c5b5f`.
No bytes would be deleted; current30230 and the other seven working directories
remain untouched. The new location is outside the recorder's working root and
releases one slot. User previously requested all recordings be preserved, so
this new path-specific move requires confirmation; no implicit cleanup occurred.

User decision2026-09-30: the proposed move is approved, with standing approval
for equivalent future operations in this same diagnostic App. Scope: completed,
fully host-backed and byte-verified recordings may be moved from this App's
`files/p34-observations/` to its sibling `files/p34-observation-archive/`, keeping
the capture basename and all bytes. Protect the current recording, never delete
or overwrite, recheck stopped App/paths/remaining directory set, and keep a
write-once intent plus post-move readback. This is not permission to clear App
data, delete recordings, move other applications' files or widen host outputs.
Current finite operation is only capture1790689316781787-c27d732d2b0839d86b5c5b5f;
after verified movement, resume the unstarted30232 bootstrap with fresh admission.

Archive execution: `.cache/p34ag/archive-move/result.json` confirms the approved
directory move, all3 destination files byte-identical, original source absent,
exact7 other working captures unchanged. USB closed normally; no files deleted.

First post-archive start `20260930T071134-67700` failed network-only. QUIC
registered successfully; DNS resolved on attempt6 after241.26s, and origin logs
showed200 responses for both metadata and291877-byte package. The client then
raised `TimeoutError: The read operation timed out`; the old readiness classifier
did not retry this bare read exception. All network owners closed normally for
an error; no cells directory, App launch or MCU/OTA operation occurred.

Bounded correction: keep4 readiness offsets and strict content checks, but
classify bare TimeoutError as transient. `recover-network` additionally admits
only the ACK-gap no-cell read-timeout case with unchanged profile, closed owners,
registered QUIC, both served200 responses and the original HTTPS-timeout event.
It preserves the failure, restores only the verified30230 host pointer and
creates an explicitly linked fresh profile; it cannot replay any device cell.
13 readiness/network tests executed PASS;329 other passes reused after AST and
source-hash isolation checks, total342. Receipt: `.cache/p34ag/network-fix/result.json`.
One fresh service preparation follows this diagnosed repair; no repack, archive
repeat, changed firmware or relaxed OTA/confirmation gate.

Recovery completed: host pointer recovery receipt lives in
`.cache/p34-session/network-recovery/20260930T071134-67700/result.json`.
Fresh run `20260930T074117-47400` verified DNS and complete HTTP package on its
first readiness attempt in5.97s. At2026-09-30T07:52:07Z the device cell reached
READY_FOR_FULL_INSTALL_START: PID25698, retained30230 full image/Boot/CONFIRMED
and921600 checked, candidate291877-byte30232 package verified, native collector
running. Capture1790754695082531-439081ef12a43fece7cb7d72 is healthy with zero
lost/error; at the initial ready checkpoint upgradeStarts/Ends remained0.
User was invited to start once in the foreground, without switching back to chat.
This is readiness, not an installation or speed result; inspect current receipts
before any subsequent action. Other owners/old page invitations are historical.

Bootstrap closure (2026-09-30): the same run finished FULL_INSTALL_VERIFIED.
Original analysis `analysis/1790755606402319800/result.json` SHA256
`4cda7db7bbd2f3f4c6e57f324dac0f0996bde3661c0a42a1a2953c43a1d4c4f0`
reports35.882844s transfer,7.943521KiB/s and49.977486s installation/reconnect.
All2281 unique DATA segments were sent once, zero retransmissions and clean
native RX/parser counters; final durable291877. This remains OLD30230 receiver
timing, not an ACK-gap performance result or the1MiB reference. Boot residency
was bracketed21.8632..25.0337s; its collector did not observe confirmation,
but separate full native readback verified30232/CONFIRMED/SD/idle and original
Boot. Do not conflate that sampling gap with failed installation.

Retained614736-byte App SHA256
`ec6bde8aae98a7ae481c1e511191d45d3e3a08b00e198ccd647fc9a5311f10b3`.
Worker and network closed normally, exit0, no forced termination. Supported
quiesce preserved the completed capture and runtime config while stopping only
the verified diagnostic App; receipt `.cache/p34-session/quiesce/1790756072598835400`.

Next finite cell: `Tools/ota/p34_gap_screen.py`, output `.cache/p34ag/screen`,
window4/921600/142-byte GATT writes, one10-second repeated-payload screen with
the existing bounded drain/ABORT rules and900-second owned host lifetime.
The new context binds the confirmed30232 image/MAP/sampler and flash gate;
diagnostic successor30234 changes only the image header and is never installed.
No END, no payload erase/program, zero durable journal, original Boot/confirmed
30232 retained. Host tests reject old image, changed Boot, unconfirmed/busy or
wrong-rate state, and live/forced predecessor owners. The old30231 package and
30230 context are not valid substitutes. A failed screen is preserved rather
than replayed; a clean screen is not durable OTA throughput acceptance.

Preparation executed:16 Python checks and20 sender checks PASS, original logs
under `.cache/p34ag/screen/tests`. The initial host-only context selection was
rejected because a receive-pressure backend cannot consume an ACK-gap profile;
it was corrected to the matching family before any screen device access.
Diagnostic30234 package291885 bytes, SHA256
`a755bce1bb532f45c416764f78d4523abd8dfb4e6b3fe8f88f83cd5c84a87a21`,
native decode/byte identity/Boot/guards/workspace checks all PASS. This package
remains non-installing. Worker5724 started2026-09-30T08:23:58Z under900-second
supervisor ownership, session539976dffd03469d8191784604c1060c. Inspect its current
`session-w4/status.json` and original result before any follow-up; a PID alone
does not prove browser readiness or a completed screen.

Window4 completed CAPACITY_SCREEN_VERIFIED:252 frames in10034.9ms,
3.139045KiB/s repeated payload only. All ACKs and ABORT verified,35794 RX
bytes, zero UART/parser/drop counters, zero payload erase/program and zero
durable journal. Original trial SHA256
`11008fbc1e3def5e2944fdf8677ce9cb09d6043c4248ef19c132dcf493ff2bc3`.
Final full30232 image/original Boot/CONFIRMED/SD/idle/921600 all verified;
USB and worker closed normally2026-09-30T08:27:44Z. Unlike the old receiver's
second-DATA failure, this bounded screen had no ACK truncation. It supports the
gap candidate but neither proves its exact electrical root cause nor50KB/s OTA.

Finite follow-up refinement: `Tools/ota/p34_gap_burst.py`, same new package and
30232 bindings, window31 with142 then244-byte GATT writes, one10-second trial
per chunk size, no END/install/reset. Only execute after the complete clean
window4 result and normal native/USB/worker closure. First failure stops the pair;
no automatic replay. Owner lifetime900s, existing CRC/seq/credit/ABORT and native
zero-durable/payload checks unchanged. Preserve the window4 adapter and originals;
the follow-up has its own tests and write-once `session-w31` output.

Follow-up host checks:20 Python tests plus20 sender tests PASS, originals in
`.cache/p34ag/screen/tests-w31`. Worker20532 started2026-09-30T08:41:56Z with
session65c12b84ff774ba2bd7ac535e8b54164 and900-second lifetime. This is the current
screen owner; window4 is completed and must not be restarted. The two chunk
sizes share the same package, firmware, browser, baud and window; results remain
separate samples. No new Flutter capture or system bugreport is requested.

Window31 closed CAPACITY_SCREEN_VERIFIED, both chunks clean:142 bytes produced
713 frames/10348.4ms/8.612443KiB/s;244 bytes produced806 frames/10391.4ms/
9.695517KiB/s. These remain repeated payload, not durable OTA. Each original
passed all ACK/ABORT/zero-payload/zero-durable checks. Full30232/original Boot and
confirmed idle921600 state remained verified; worker/USB closed normally at
2026-09-30T08:46:11Z. No repeated firmware installation occurred.

Original write events show142-byte DATA writes consumed2705.10ms of10348.40ms;
the23 batch tails consumed7421.60ms. For244 bytes,494 DATA writes consumed
2009.20ms and26 tails8185.30ms of10391.40ms. Tail intervals run from the final
write completion to next batch's first write (or measurement end), so include
ACK wait and host scheduling, not an exclusive UART/MCU phase. Native max pump
gaps were103.666/95.348ms; clocks are not subtracted across domains.

Next host-only candidate `.cache/p34ab` copies3268 verified30232 source files.
It preserves EVERY ACK frame and FIFO bytes; no seq/CRC/status/durable semantics
are removed. `P34AckBatch` buffers at most12 complete19-byte ACKs (228 bytes)
only within one MCU pump; control/error or durable advancement flushes before
its response, pump exit flushes partial batches. The established TX-complete
plus1ms gap applies after an actual UART batch. An uncertain UART write latches
failure and is not replayed. Root production firmware is untouched; only the
isolated HAL adapter/new header change. Host primitive checks cover FIFO/size,
partial flush, control ordering, outside-pump immediate send and failure latch.
No device installation of this candidate is yet admitted or executed. Boot and
the30-second healthy-App confirmation are not modified.

ACK-batch host build succeeded: raw615096 bytes (360-byte growth over30232),
text613656/data940/bss560000 (240-byte static-RAM increase),638 warnings/0 errors.
Boot not built. Candidate30235 FULL292115 bytes SHA256
`5ae29c29c74a6837e72e3b9aa8cc3aa3df4ecb7e67fa345f620642f47f3870a8`;
forward30236 restoration291820 bytes SHA256
`bb244b77ba4e10fdde20dd8b33e4c29aae1dc91a83c9cb3837959133acf57eb3`.
Both decode byte-identically with Boot/header/guard/workspace checks. CRC,
truncation and same-version negatives stop before preparation. New target
MAP/ELF bindings were derived, not copied from30232.

Finite matrix extension: one `ack-batch-bootstrap`30232-to-30235 FULL via the
same verified diagnostic APK at921600/window32, original recording plus full
native identity/confirmation readback, same bounded ordinary apply/reconnect
allowance. This introduction transfer still measures30232. Only confirmed30235
can admit a subsequent new no-END link screen with its new bindings and a legal
newer diagnostic header. No automatic second install or forward restoration;
any uncertainty pauses dependent mutations for readback, not replay. Prepared
profile `.cache/p34-session/profile-ack-batch-bootstrap.json`, SHA256
`52eb87462d0ea724fbfa42d02163da994c2b7a121511c795e669f173bebd2516`.
It is preparation only; complete tool regressions and recording-slot admission
remain prerequisites. Old groups do not depend on the batch candidate assets.

2026-09-30T09:28Z recording-slot preparation stopped BEFORE any phone mutation:
private USB reported serial10ADA4197U001CK not found in all8 bounded checks over
19.70s. Runtime `.cache/p34ab/archive-30230/phone/usb` closed normally, all exit
codes0, key unchanged, port closed. No archive intent or move was issued; old
30230 capture1790690677080577-38c5360acee05543a0defc86 remains unmodified by this
attempt. Intended destination is the same App's approved sibling archive with
the identical basename, after full byte backup/verification and protection of
latest30232. The user was asked only to reconnect/unlock the phone, not for a
repeat permission. Preserve this failed USB window; any resumed archive uses
a fresh output and rechecks actual paths/files. New firmware OTA has NOT begun.

Tool regression closure: `.cache/p34-session/tests/1790760259799909900` executed
346 tests in751.898s:345 PASS, one stale direct-successor test assumption failed.
The runtime correctly returns the existing receive-pressure outcome for the
later ACK-batch group; only its actual direct successor may request a new profile.
`test_p34_receive.py` now checks `PREDECESSOR_GROUPS[group] == receive-pressure`
instead of treating every ACK family member as direct. No runtime guard changed.
The corrected method passed in `.cache/p34ab/regression-fix/targeted.log`.
Original source, failed result and AST comparison remain preserved. All other
source hashes and test AST nodes are unchanged:345 original executed PASS plus
1 executed targeted PASS, NOT a second fresh346-test suite. `tests/latest.json`
contains this disclosed source-bound result. Device operations remain blocked
only by the missing phone, not a pending test or a repeat permission request.

User reconnected the phone. Fresh bounded route `.cache/p34ab/archive-30230-r2`
verified the exact serial/APK, stopped App and eight working captures. All three
old30230 files were backed up and read twice; snapshot SHA matches the original
completed30230 analysis. The approved sibling-directory move then completed,
destination bytes all matched, source absent, exact other seven directories and
runtime configuration unchanged. Zero deleted files; USB closed normally with
all exit codes0 and unchanged ADB key at2026-09-30T09:48:20Z. The first failed
USB window remains preserved. New ACK-batch start is now preparing through the
normal source-bound session runner; no old transfer or browser screen is replayed.

Fresh ACK-batch run: `20260930T094904-31700`, group `ack-batch-bootstrap`, cell
`s04`. Prestart phone capture is the original completed30232 snapshot, App
stopped, seven working recordings; prior configuration is still byte-identical.
Network worker9400 started2026-09-30T09:52:28Z under finite ownership. This
record denotes preparation, not service readiness, DATA transmission or target
installation. Inspect live status and exact292115-byte candidate hash before
inviting the new foreground transfer; never use the expired predecessor URL.

Ready checkpoint2026-09-30T10:06:28Z: same run/cell reached
READY_FOR_FULL_INSTALL_START, App PID7925, capture
1790762757650934-dd5b864e26ea6ef1d45ad8d0. Exact APK unchanged; full30232 App,
original Boot, CONFIRMED/SD/idle/921600 and old diagnostic zero journal verified
without reset/flash. Both App queries and exact292115-byte30235 download passed.
Network9400 and cell21096 remain bounded/live; service expiry11:22:28Z.
This is readiness only. User may start the new foreground upgrade once after
the final ready check, and must not replay the old30232 upgrade or browser tests.

ACK-batch bootstrap completed FULL_INSTALL_VERIFIED in the same run. Original
report `analysis/1790763251018904100/result.json` SHA256
`0d4d621240500ec40f669f404426630cebb2c211d29aaa34e6f40d9c3c25ef29`:
38.700722s transfer,7.371143KiB/s,49.063462s installation/reconnect;2283 unique
segments, zero retransmission, complete ACK samples and final durable292115.
This is30232 receive timing, not the new batching result. Boot residency was
22.8656..24.8476s, separately from final confirmed readback. Target615096-byte
30235 SHA256 `20712c2f50a85177a1de80b29c9080753bb3b0545778bf389e258c50074608b1`,
original Boot, CONFIRMED/SD/idle/921600 all verified. Worker/network closed
normally; supported quiesce preserved recording/configuration at
`.cache/p34-session/quiesce/1790763789561616600`. No upgrade replay.

Next finite diagnostic: `Tools/ota/p34_batch_screen.py`, `.cache/p34ab/screen`,
same browser route/window31/921600 with142 then244-byte writes, one10-second
repeated-payload cell per chunk, stop pair on first failure. Bind the new30235
image/MAP and legal30237 header-only package; do not use the old30234 package.
No END, no installation/reset, zero durable and no payload erase/program,
original Boot and confirmed30235 retained.900-second owned worker, no new
system bugreport or Flutter recording. Context reuse is process-local and only
for the identical output path; a different output is rejected, source admission
and live full MCU identity remain required. This avoids repeating expensive
historical context construction inside one prepared operation, not its gates.

Screen preparation:14 Python tests and20 sender tests executed PASS under
`.cache/p34ab/screen/tests`. Legal header-only30237 package292128 bytes SHA256
`e80eacacc20ef17f726ba039ca603dddb07db2bbd70f68b6c3837c0d209366f2`;
native decoder byte identity, Boot/header, guards and workspace all PASS.
This is not an installation package admitted to END. Source-bound screen start
was prepared for the single declared window31 pair, not a repetition of the
completed FULL upgrade. The pair has now completed as recorded below.

Completed batch screen: `.cache/p34ab/screen/session-w31/result.json` is
`CAPACITY_SCREEN_VERIFIED`. At921600/window31,142-byte writes delivered806
frames in10216.2ms (9.861788KiB/s);244-byte writes delivered1147 frames in
10165.3ms (14.104355KiB/s). Actual UART batches were132/159, requesting
15353/21832 ACK bytes with0 errors; UART call time was0.299440/0.396751s.
Both cells have clean RX/parser/drop counters, verified ACK/ABORT, zero durable
and zero payload erase/program. These repeated-payload link measurements are
NOT durable OTA throughput and do not meet50KB/s.

The prior gap-only30232 window31 results were8.612443/9.695517KiB/s with the
same142/244-byte chunks. Batching improves this screen, especially larger GATT
writes; it does not by itself identify the remaining link wait. MCU pump-work
times (0.538864/0.741796s) overlap UART times and must not be added to them.

Worker17188 exited0 normally at10:41:00Z; owner and USB closed. Full
`mcu/closure.json` confirms the retained615096-byte30235 image SHA256
`20712c2f50a85177a1de80b29c9080753bb3b0545778bf389e258c50074608b1`,
original Boot SHA256
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`,
CONFIRMED, SD ready and idle. No END/install/reset or additional system report.

Next direction is a bounded Android connection-priority experiment. Locked
`flutter_blue_plus`1.35.5 and Android plugin4.0.5 archive hashes were verified
against the installed APK source lockfile. The Dart API supports
`requestConnectionPriority(connectionPriorityRequest: ConnectionPriority.high)`;
native success only means `BluetoothGatt.requestConnectionPriority` returned
true, NOT that a requested interval or PHY was negotiated. No connection-update
or read-PHY observation hook was found in the inspected plugin files. Do not
infer actual radio parameters from this API or invent module AT commands.

GitHub CLI read-only preflight verified account `Eitan-S-23`, the exact origin
repository and active development workflow353793017. Latest inspected successful
runs35998913094/35998421105 bind existing APK commit
`aea62c6490a529a47f74dde86669dc3e3c7605ff`. Python urllib's TLS route failed;
the contained GitHub CLI route succeeded without changing credentials. This is
connectivity/provenance evidence, not a new CI result or a guarantee of quota.
No new app source, branch, commit, push or APK has started.

### P34-TARGET50-ROLL01: Remove Diagnostic Batch-Tail Idle

Before implementing an APK priority experiment, original browser event analysis
identified a cheaper discriminating sender comparison. The fixed sender waits
for ALL31 ACKs before replenishing. Its142/244-byte cells had26/37 batches;
summed last-write-completion to final-ACK tails were6969.50/6792.10ms of
10216.2/10165.3ms total. Tail medians239.65/175.10ms. Actual write-Future sums
were2904.60/2952.90ms. These are same-browser-clock observations, not connection
intervals and not MCU phase times. Derived report with original trial hashes:
`.cache/p34-priority/research.json`. This supports testing rolling credit, not
claiming that all idle time is avoidable or that50KB/s is attainable.

`Tools/ota/p34_rolling_capacity.js` is a separate diagnostic sender inheriting
the existing transport/CRC/identity/lifecycle guards. It reserves at most31
outstanding frame sequences, releases each credit once on its exact valid ACK,
replenishes available credit without waiting for the entire old batch, then
drains every outstanding ACK before reporting speed. Duplicate ACKs do not
increase credit/numerator. No retransmission, END or durable-speed claim; a
partial uncertain write forbids appending ABORT. Missing ACKs retain bounded
deadlines. The existing fixed-window JS and completed evidence remain unchanged.
The shared host worker now accepts an explicit admitted sender option; its
default resource is byte-identical to the old fixed sender. Rolling results
add peak-outstanding/final-ACK accounting checks; all original native gates stay.

Self-tests: `.cache/p34-rolling/tests-v3/result.json` executes19 Python checks
and37 Node checks PASS. Prior36-test runs and the v2 failed discriminating
fixture are preserved: that fixture incorrectly hard-coded the first DATA
sequence as2 despite bypassing GET_INFO. The repair reads the actual first
wire sequence; production sender code did not change to satisfy that test.
The final test now proves refill occurs while that delayed ACK is outstanding.

Finite device plan, Codex root sole owner, same authorized phone/MCU and root:
`Tools/ota/p34_rolling_screen.py` prepares `.cache/p34-rolling`, reuses the exact
already-decoded30237 package from the fixed screen, and admits only confirmed
30235/original Boot/921600 after verifying all four prior outcome/closure hashes
and a fresh full native readback. One142-byte then one244-byte10-second cell,
window31, rolling sender only; stop pair on first failure. No END, install,
reset, APK, new system report, capture archive or data clearing. Zero durable,
unchanged payload and final full retained identity are required. The900-second
owned worker retains the existing600-second user window and serial USB/native
ownership. Only browser Bluetooth selection and starting the screen require
human interaction. Prepare/tests precede that invitation; do not reuse old UI.

The window31 screen was actually operated before a new chat invitation. Preserve
`.cache/p34-rolling/session-w31`: first142-byte cell stopped after272 sent frames
on DATA NAK;244-byte cell was NOT_RUN. Native run3 proves RX-ring peak4095,
overlay drop307, parser error1, UART hardware errors0. Browser observed statuses
2/3; its ABORT wait was blocked by the latched DATA error, so it correctly reports
`abortConfirmed=false`, not success. Separate full native closure shows the
actual ABORT reply (seq274), idle, zero durable, exact30235/App and original Boot,
CONFIRMED/SD ready and retained921600. Worker17976 exited1 normally11:31:23Z;
USB stop/server/launcher all exit0, port closed and key unchanged. No install,
reset, third system report or valid throughput result. Failure is not replayable.

The diagnosed refinement changes ONLY the rolling window to28:31 complete
142-byte wire frames require4402 bytes, exceeding the4095 usable RX-ring bytes;
28 frames require3976 bytes. Payload-only31*128 arithmetic is insufficient for
this bound. Keep the same rolling JS, exact package, receiver, baud, two chunk
sizes and duration. `.cache/p34-rolling28/session-w28` is a new finite pair,
first-error stop, not a repeat of successful OTA. Its entry additionally pins
all four failed-screen outcome/full-closure/owner/USB records before admission.
Existing session teardown/BEGIN reinitializes the ring; profile parser errors
are relative to the new run, so no reset or manual counter clearing is needed.
Fresh tests `.cache/p34-rolling28/tests/result.json`:19 Python and38 Node PASS,
including a wire-byte credit bound with80ms delayed ACKs. No performance result
is claimed until original sender events and fresh native closure both pass.

Completed window28 pair: `.cache/p34-rolling28/session-w28/result.json` is
`CAPACITY_SCREEN_VERIFIED`.142-byte writes:1221 frames/10169.6ms,
15.007965KiB/s, RX-ring peak3976.244-byte writes:1487 frames/10125.0ms,
18.358025KiB/s, ring peak3870. Both have zero new overlay/hardware/parser errors,
complete ACK/ABORT, zero durable and no payload erase/program. UART batches
168/192 cost0.421123/0.500076s; pump work0.780451/0.947377s overlaps that time.
The persistent parser total1 is the preserved prior failure; these new per-run
parser deltas are0, not a reset or erased error history. Full final30235/Boot
hashes and CONFIRMED/SD/idle/921600 pass. Worker12152 exited0 normally at
11:43:47Z, USB and native reader closed, original key unchanged. No new upgrade.

18.358025KiB/s is still a repeated-payload diagnostic, not durable OTA speed or
50KB/s acceptance. The safer rolling configuration is faster than the preceding
fixed-window31/244-byte14.104355KiB/s screen, but that comparison changes both
scheduling and the safety window; do not attribute the entire gain to one axis.
Actual pump cadence remains roughly70ms despite its20ms configured period.
Android priority is supported but untested; browser results do not prove the
Flutter link's interval. The installed Flutter sender already reclaims bitmap
credit inside its block loop, so do not transplant a duplicate sender based on
the browser-only bottleneck. No new Flutter source/CI/APK work has started.

The current Boot trace alone occupies22.8655572..24.8475859s. Installation/
reconnection remains49.063462s for the verified30235 upgrade. Further work on
the20s target must preserve30s healthy-App confirmation and full identity
checks. Boot replacement remains outside current authority; no Boot edit,
build or flash has been performed in this continuation.

## 2026-09-30 Authorized Boot Optimization: P34-BOOT-01

The user explicitly replied "authorized" to optimizing/flashing this F435 Boot
after J-Link recovery validation, retaining the original Boot and30-second
healthy-App confirmation. This supersedes the earlier task-local Boot exclusion
only for this device and bounded work; it does not authorize release, unrelated
devices, arbitrary BCB/EEPROM writes, clearing App data or external host outputs.
Codex root is sole operator; writable root remains `D:/github/my/E-Track`.

Latest retained state is the completed window28 screen:30235 image
`20712c2f50a85177a1de80b29c9080753bb3b0545778bf389e258c50074608b1`,
whole64KB Boot `55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`,
CONFIRMED/SD/idle/921600, all owners closed. The original Boot's source manifest
in `.cache/p34q/irqscreen/triage/boot-fix/run-002/result.json` matches every current
input before this new edit. Its14724-byte BIN matches the whole backup prefix,
but the remaining Boot region is NOT all FF. Recovery must preserve all65536
bytes, not synthesize a padded backup. No recovery or new Boot flash has run yet.

First candidate is default-OFF `P34_BOOT_SKIP_IDENTICAL_BLOCKS`: after validated
source loading and full padded4KB equality comparison, omit only redundant
internal erase/program. Keep every block's verified resume commit, final image
validation, rollback and confirmation policy. Read failure stops before erase;
mismatch uses the original erase/program/readback path. QSPI staysDIV8/36MHz.
Default build must reproduce original Boot bytes. Candidate tests must cover
equal/mixed/changed/tail blocks, read failure, failed progress commit/re-entry,
corruption after a saved checkpoint, apply and rollback. No claimed time saving
until a measured, identity-bound device trial; header-only packages are not a
representative general firmware workload.

Host preparation is bounded under `.cache/p34-boot`: verify whole backup, build
default and candidate Boot-only with GCC, run state-machine/protocol/QSPI checks,
verify map/size/artifacts and changed source scope. Before first device mutation,
complete an exact Boot-only J-Link command/readback/recovery gate, fresh full
App/Boot/BCB/idle observation and finite trial plan. Do not reuse old one-shot
repair commands or overwrite old build/acceptance evidence. No flash is admitted
merely because candidate compilation passes.

Preparation completed: default96/candidate103 state-machine checks,14 QSPI
checks and19 protocol checks PASS. Both GCC Boot builds and artifact validators
PASS,0 warnings/0 errors. Default14724-byte BIN exactly reproduces original;
candidate14780 bytes (+56), text14776/data4/bss9780, static RAM unchanged.
Report `.cache/p34-boot/preparation/result.json`; whole original recovery backup
is preserved there. The flag remains OFF by default; no shipping/release claim.

Read-only preflight attempt1 was rejected: Commander interpreted bare lengths
as hex, yielding oversized reads (and a partial App read), despite exit0.
No flash/reset/halt command ran. Preserve `.cache/p34-boot/device`. The repaired
entry emits explicit0x lengths and rejects partial-read text;15 host checks
include exact Commander length parsing. `.cache/p34-boot/device-r2/result.json`
is `BOOT_REPLACEMENT_PREFLIGHT_VERIFIED`: original whole Boot/App hashes,
advancing288MHz App, VTOR, CONFIRMED/SD/idle/retained baud all match; native
history unchanged and Commander exited normally. Never treat exit0 alone as
successful memory retrieval or truncate a failed capture into accepted evidence.

Activation matrix: `Tools/ota/p34_boot_activate.py`, one fresh unchanged-state
snapshot, one Boot-only full64KB download at0x08000000, full Boot verification
and unchanged615096-byte App verification before ordinary reset,10-second
startup allowance then fresh full Boot/App/health readback. Each Commander
process has180s timeout and hidden owned launch; no phone/OTA writer is opened.
Candidate whole-region SHA256
`a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4`;
bytes after its14780-byte code retain the original region's exact tail.
Three command-scope tests plus15 snapshot/length checks pass; exact source,
build and command hashes are bound in `.cache/p34-boot/activation/plan.json`.
The original whole-region restore command is prepared and address/length
checked against the same verified J-Link path; it has NOT been executed merely
to rehearse recovery. Any uncertain flash or identity failure stops further
mutations for reconciliation; restoration, if needed, is only original Boot,
never App downgrade or arbitrary BCB repair. SD failure after halt is diagnosed
separately and may require physical card/power intervention. This phase proves
Boot replacement/cold-start compatibility, not installation performance.

Activation completed with `CANDIDATE_BOOT_ACTIVE_30235_CONFIRMED` at
`.cache/p34-boot/activation/result.json`. Fresh full before/after images,
Commander normal exits, both Boot/App verification logs, advancing288MHz App,
VTOR, SD, idle, retained921600 and CONFIRMED passed. The original whole Boot
backup and restore script remain preserved; restoration was not performed.

Next finite cell, P34-BOOT-OTA-01: one30235-to30238 header-only FULL at
921600/window28 using the existing verified diagnostic APK. Package292114 bytes,
SHA256 `5329b49be82959fe3ce283681823d28cef055f7f4399507651564de41e41ad58`,
is bound in `.cache/p34-boot/ota-assets/validated.json`. Native exact decode and
four pre-mutation rejection checks passed. Initial result serialization failed
on a byte-valued header; preserve the partial result and all original package
bytes/nonces. The finish path reused them, reran native checks and wrote the
separate validated manifest. Do not regenerate the package.

This measures best-case identical-block Boot copying, not general firmware
installation speed. Keep every verified checkpoint, rollback, final raw target
verification and30-second healthy-App confirmation. Keep the existing bounded
session/USB/native deadlines and foreground route; verify live producer queries,
package download and exact new Boot map before inviting Start. Retrieve original
finished App bytes and final full target/new Boot identity; no repeat to repair
a collector. Retain confirmed30238 after success, otherwise reconcile state.

Before launch, non-deleting archival may move only the completed30232 capture
`1790754695082531-439081ef12a43fece7cb7d72` from `files/p34-observations/`
to `files/p34-observation-archive/` with the same basename. Under the existing
standing archive authority, first require stopped App, exact original completion
snapshot and full host backup; refuse overwrite, verify all moved bytes, the
remaining seven names and unchanged configuration. Protect current30235 capture
`1790762757650934-dd5b864e26ea6ef1d45ad8d0`. Host outputs remain under
`.cache/p34-boot/archive-30232`; no data deletion or MCU operation in this step.

Archive completed: all three files are byte-identical, remaining seven capture
names and configuration unchanged, current30235 protected. USB launcher/server
and shutdown exited0, port5062 closed, original ADB key unchanged. Result:
`.cache/p34-boot/archive-30232/result.json`. Re-entry rejection was tested before
backend/device access; do not replay this completed move.

Host regression accounting: first full run1790772626556013400 executed350 tests,
349PASS/1FAIL. The sole failure was the old all-groups matrix expecting32 for
the newly explicit28-window group. Only that method's new-group expectation was
corrected. The full retry1790773556342602100 reached900s with347 completedPASS
and no assertion failure; its partial log/timeout are retained, not called PASS.
Reconciliation reconstructs the exact original test bytes and matches their
original SHA256, proves the rest of the AST identical and checks every other
source hash. Five targeted tests (changed matrix plus four Boot integration
tests) passed;345 unchanged direct originalPASS cases are reused. Coverage350
is NOT a fresh350-test execution or independent acceptance. Source-bound proof,
raw targeted log and result: `.cache/p34-boot/regression-reconcile/`.

Prepared profile `.cache/p34-session/profile-boot-copy-measure.json` SHA256
`961839ac3d8318c42e9be6178ce58da8e141afdd3bb142bef8a5605e1d06ffae`.
Offline real-context checks resolve all eight new Boot trace symbols from the
candidate MAP, confirm only image block0 differs, and recognize the existing
30237 diagnostic staging package separately from the new target. This is not
live admission or a speed result. Start is now permitted only through the normal
source-bound session entry with new phone/MCU checks and the original collectors.

P34-BOOT-ENTRY-01: first start20260930T132445-19700 stopped after a successful
read-only phone inspection (seven records, exact stopped/completed30235) because
`Backend.predecessor` still required unchanged Boot. No plan/current-pointer
advance, service, MCU connection, config retirement, App launch or OTA occurred;
the USB receipt is normal and retained. Repair only the new Boot group's branch
to call the exact verified Boot-only transition; old groups retain equality.
The native reader also inherited the old Boot SHA constant. Bind the instance
SHA only after the new group's verified asset load; the shared legacy class
constant and all old groups remain unchanged. This second issue was caught
offline, before another native/OTA attempt.

Eight targeted checks cover current context/service, exact new native Boot SHA,
unchanged legacy SHA, wrong Boot/App/layout/MAP rejection, unchanged old-group
equality and start/replay guards. They passed in92.493s;343 unchanged direct
originalPASS cases are reused, total coverage351. Exact previous-byte
reconstruction and source checks prove the limited changes. Evidence chains:
`.cache/p34-boot/entry-fix/` then `.cache/p34-boot/identity-fix/`; neither rewrites
the first350-test failure, timeout, prior reconciliation or failed start.
Resume via a new normal start; current still points at completed30235, so no
failed attempted-transfer latch or phone configuration needs to be bypassed.

## 2026-09-29 Receive Restore Device Screen: P34-RECEIVE-02

User explicitly requested continuation until human intervention is necessary.
Codex root is the sole operator; writable root remains `D:/github/my/E-Track`.
The existing P3-4 device/task and exact J-Link history authorization remain in
force, without per-OTA/reset permission questions. No Boot/BCB edits or App data
clearing. Any additional phone capture deletion still needs its exact boundary.

Finite matrix:30228 ->30229 FULL bootstrap, then only after full confirmed30229,
30229 ->30230 exact1048576-byte PATCH screen. No extra repetition or silent
same-package replay. Both use existing verified APK,921600/window32, foreground,
same timeout/retry/MTU/write mode and original Boot. Candidate source/build is
the completed P34-RECEIVE-01 (614632 bytes); only staging QE reuse differs from
the prior coalescer receiver. Compact PATCH stays offline. Bootstrap timing is
old-receiver timing, not the optimization result. Stop measurement on integrity,
unknown state or unclosed owner; retrieve successful evidence instead of replay.

Prepare all assets, source-bound session regressions, new MAP/ELF bindings,
collectors and final full target/Boot/CONFIRMED extraction first. Keep existing
900s active,2700s native and3900s cell bounds, ordinary apply/reconnect allowance
and30s no-durable watchdog. No borrowed time from expired windows. Retain30230
after success, otherwise the last completely verified target; reconcile before
any recovery, never App-only downgrade across changed BCB.

Host prep is write-once under `.cache/p34-receive-screen/`: legal successor
finalization, at most512 pressure compression candidates, existing real decoder
positive/negative verification and independently named session groups. Preserve
all partial failures/nonces. The old PATCH32 pair and build manifests stay frozen.
Current phone doctor confirms stable completed30228,original snapshot hash
unchanged and8/8 captures; USB closed. Path-only cleanup preview is read-only.
No device mutation in this plan has started yet.

Current read-only doctor:
`.cache/p34-session/doctor/1790675061660788400/result.json`, PID21097,
stable completed capture and exact old pressure snapshot SHA unchanged;8/8.
`.cache/p34-receive-screen/cleanup-paths/result.json` resolves two candidate
phone-copy boundaries with USB closed and zero phone mutations:

- `/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790668713353005-ef0d63b6ae7d5f5566f7396b`
  is old30227, eligible only after archival equality while30228 is protected.
- `/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790670122706640-c95ade7747c6ab922b507946`
  is30228, to remain protected until full30229 confirmation and owner closure;
  then archival equality is required before freeing the pressure cell slot.

The exact phased deletion scope was initially PENDING, not implied by the older
30225/30226 grants. The user's latest current-thread reply reaffirmed authorization
in response to that exact two-directory question. It is now CONFIRMED for only
the two paths and phased conditions above. Record:
`.cache/p34-receive-screen/authorization-current-thread.json`.
R, all other phone captures and all computer originals are kept. Frozen audits
retain their historical PENDING state; this later confirmation does not rewrite them.

The initial512-candidate search completed without an exact witness. Preserve
`assets/failed.json`, all512 measurements, finalized30229/30230 images and
existing FULL/compact package nonces. The search inspected only four counts;
the bounded refinement is128 previously unsampled count/salt neighbors of the
closest original lengths (maximum640 total, not an unbounded retry). Its exact
list and original file hashes are in `assets/neighbor-recovery/intent.json`.
The recovery reuses only two inspected original recovery functions, with an
explicit AST integer-version mapping30226/30227/30228 to30228/30229/30230;
both original and generated helper bytes are retained. It must run the same
native positive/negative and Python decode oracles, never rewrap prior packages.
Physical matrix remains exactly the two declared cells; no device mutation.

The128 neighbor candidates also exhausted without a witness; its failure and
all640 original measurements remain intact. A different, local axis now has
at most128 candidates: keep the closest original control stream and change only
the last seek that is consumed by a following1-byte diff, correcting that diff
byte for the new valid old-image position. Positions with the same old byte are
excluded. There is no unused seek, zero-progress control, compressed tail or
padding. Record the exact basis, offsets, positions and source under
`assets/tail-recovery/`; require full LZMA consumption, byte-identical target,
native Boot/guard checks and the original negative-package matrix. This refines
the offline generator only; no extra physical cell or relaxed criterion.

Consumed-seek128 also exhausted. Independent final-diff/extra split probe16
under `final-span-probe/` found no exact length. Both results are preserved;
neither created an ETU. Stop these axes rather than repeating them. A separate
compatible encoder family now has a512-candidate cap under `assets/fast-recovery/`:
LZMA1 FAST/HC3,nice_len32,depth8; dict16384,lc2,lp0,pb0 and strict EOS/full
consumption remain unchanged. This changes only host encoding choices, not the
decoder or target image. It uses separate measurement paths to prevent a cached
NORMAL/BT4 sample from being mistaken for FAST. Preserve every earlier byte.
The resulting pressure input is a same-length transfer screen, not strict
same-package A/B; its different control/compression workload cannot be used to
claim an installation-time improvement. Native and Python oracles still apply.

FAST succeeded in22 measurements: count186532,seed1931,salt1,decoded stream
5091424 bytes,compressed stream1048472 bytes,complete ETU1048576 bytes. Exact
properties remain `0200400000`. Eighteen native commands passed (FULL/PATCH,
both PATCH decoder modes, CRC/truncation/version/base rejection); all decoded
images equal the finalized targets and native Boot/guard/lifecycle checks pass.
Final assets: FULL291692 bytes,compact309 bytes (offline only),pressure1048576.
Manifest `.cache/p34-receive-screen/assets/result.json`,
SHA`94dba64952b620dff9aab059e1ea5bb75bc65272f082166cc636eb23b4b02e79`.
All earlier failures, samples and original FULL/compact nonces remain unchanged.

Host-only `prepare-patch --group receive-bootstrap` created
`.cache/p34-session/profile-receive-bootstrap.json`,
SHA`f929108ffb6fb10dd827c1bd96fafa896e36865e740d14e9a3ef8c3d522e5a5d`,
bound to actual completed30228. Pressure profile is intentionally absent until
actual30229. Full session regression at
`.cache/p34-session/tests/1790678079455113900/` ran327 cases:325 PASS,two FAIL,
no errors/skips. The two old recovery tests accidentally depended on current
being30226; current is now30228. Only their fixtures were bound to the original
predecessor, and an advanced-owner rejection case was added. No production
recovery guard was weakened. The earlier chat claim that all310 old cases had
passed was corrected immediately after reading the completed failure log.

`.cache/p34-receive-screen/tests/r1/result.json`:18 affected-class tests executed
PASS;310 direct original PASS cases reused after proving every other source
unchanged and only the named fixture ASTs changed. Total coverage328, not a
328-case rerun. The original full-suite failure is preserved. Source-bound
`.cache/p34-session/tests/latest.json` is updated to this verified result.

Final read-only old30227 archival:
`.cache/p34-session/completed-prune/1790679062283890500/result.json` is
COMPLETED_CAPTURE_ARCHIVED,apply=false,phone_mutations=0,USB closed. Snapshot
1045549 bytes, SHA`894614a833cf8e3f37d0689c477cc42ea4463b6e6bbf40394e462775db7aebf5`,
matches the original exactly.8/8 captures remain, current30228 and R protected.
All three USB sessions closed with zero launcher/server/stop exit and unchanged
read-only ADB key. No App stop, deletion, J-Link, new OTA, service, CI, firmware
rebuild, commit/push or independent acceptance occurred in this continuation.

The two exact phased phone-copy deletions above are now confirmed by the latest
current-thread reaffirmation; no repeated permission question is needed. Next,
quiesce only the verified current completed App, recheck/archive and prune only30227, then run
fresh native/package/source/producer admission for receive-bootstrap. Open the
real observer window only near the user's App action. Do not ask again for the
existing J-Link history grant or routine in-matrix operations. A future successful
30229 must be fully confirmed before creating receive-pressure or pruning30228.

Execution under the reaffirmed scope:

- `quiesce/1790679899858388500/result.json`: APP_QUIESCED, exact PID21097,
  configuration preserved, process absent and USB closed.
- `completed-prune/1790679956806108400/result.json`: COMPLETED_CAPTURE_PRUNED,
  exact resolved old30227 path matched, snapshot1045549 bytes and original SHA
  `894614a833cf8e3f37d0689c477cc42ea4463b6e6bbf40394e462775db7aebf5`
  matched after fresh archival; exactly8 ->7 captures, only old30227 removed.
  Both USB closures have stop/server/launcher exit0, closed port and unchanged key.
- New receive-bootstrap run `20260929T110708-41800` entered preparation using
  the existing profile/assets and verified source-bound tests, without rebuilds.
  Its prestart phone inspection is APP_INSPECTED: stopped App,7 captures and
  unchanged3723593-byte completed30228 snapshot. Actual transfer is not yet proved.

### P34-RECEIVE-03: Stale Download Cache And Same-App Recovery

The first worker in `20260929T110708-41800/s04` closed with
`FULL_INSTALL_INCOMPLETE: RuntimeError: App file size bound` before downloaded
input admission. Its original USB command journal proves that the shared
`app_flutter/firmware/p34-coalesce-bootstrap-full.etu` still had291771 bytes;
the current expected package has291692. The health sample had starts/ends0/0.
Original raw App/Boot/CONFIRMED and native-reader closure passed. Device worker,
USB and native reader closed; the service was explicitly closed at11:16:29 UTC.
No full OTA ran in that failed observation. Preserve its result and source pins.

Fresh read-only `.cache/p34-receive-screen/cache-inspection/result.json` proves
the user subsequently downloaded the correct291692-byte package, SHA
`c307af0b13d4204a055bcd7dc8a52c654976dc288c77ec4710416809581c7222`.
PID8312 and capture `1790680525007381-6ccf9b4b5965b93430950b73` remain healthy,
starts/ends0/0, with8 captures. USB closed, no phone mutation. Therefore reuse
this exact App and capture; no new deletion permission, restart, service or
download is needed. Do not remove the failed capture or prematurely delete30228.

Root cause: implicit filename-identity assumption plus an integration-test gap.
The current helper now treats stale length/different bytes as pending and keeps
exact-byte admission. `p34_cached_resume.py` prepares only a new bounded observer
after verifying the exact original failure and unchanged source/asset chain.
Fresh same-PID/config/capture/zero-start checks and native checks precede Start;
normal full snapshot/readback/CONFIRMED checks follow it. A new observation time
does not rewrite the original App launch time. The original closed endpoint is
provenance, not a claim of live service. Physical matrix stays the same two cells.

Targeted tests preserved under `cache-recovery/tests-r1` and `tests-r2` exposed
one host read-vs-output boundary mistake in the new admission helper and then
one incomplete test fixture (`MAX_BYTES`). Both were corrected before any
recovery execution. Full source-bound regression is running at
`.cache/p34-session/tests/1790681794331100700/`; no PASS is claimed yet.
Prevention: test stale/same-length caches and the observation loop, keep explicit
read-only external tool inputs separate from output preflight, and reuse unused
App captures rather than treating host failures as permission for new launches.
The analogous frozen prefix controller remains immutable and is not replayed.
The executable recovery contract and negative matrix are in `docs/p34-session-tool.md`.

Completed regression update: the full run executed336 tests in524.232s with
334 passing test cases and four subtest errors in two old fixtures. Both lacked
the newly required stat response. Only those two fixture bodies were corrected;
the full failure is preserved. Ten targeted tests then passed in3.115s, including
both fixtures, the real failure input and cached-observer lifecycle.326 direct
original PASS cases were reused after source hashes and AST comparison proved
all other tested code unchanged. Coverage336 is not a336-case rerun.
The executable proof is `cache-recovery/fixture-retest.py`, its original output is
`cache-recovery/fixture-retest/result.json`, and `tests/latest.json` binds the
current sources and direct reuse evidence.

Same-App recovery started as `20260929T115119-cached-56200/s04`. It preserves
the failed run and copies only provenance/configuration bytes into a new local
observation directory. No App launch, service, download or deletion is requested.
The worker must freshly verify exact PID8312/config/capture, current cached bytes
and retained30228/Boot/CONFIRMED before it can invite Start. Device timing still
has no new result. Any changed App or started upgrade blocks this recovery rather
than granting a retry. Observe the new run; never restart the old completed OTA.

At11:54:10 UTC the cached observation became READY_FOR_FULL_INSTALL_START.
Its fresh retained readback is full30228/unchanged Boot/CONFIRMED; same PID8312,
same capture and exact291692-byte package passed pre-BEGIN query admission at
`runs/20260929T115119-cached-56200/cells/s04/queries/result.json`.
The original launch time remains11:15:27, resumed observation starts11:54:00.
The user is asked only for one foreground Start, with the ordinary25-minute
start allowance to about12:19 UTC. No service, restart, new capture or deletion.
Original failed run remains closed and immutable; current observer is deliberately
live within finite bounds. No new completed OTA or receive-speed result yet.

Later closure supersedes that READY invitation: at11:57:59 UTC `pidof` returned
exit1/empty, while the immediately preceding USB command had succeeded. This
was not a USB disconnect. The cached worker preserved its failure and closed
native/USB at11:58:00; its last health was starts/ends0/0. Read-only
`.cache/p34-receive-screen/app-exit-inspection/` confirms no current PID,
the same healthy16-record capture with zero upgrade starts/ends, no snapshot,
and8/8 directories. System exit-info labels reason10/subreason21 but specifically
describes `stop ... due to low memory state=empty`; do not infer a user force-stop
from the generic reason label. No replay, App restart or deletion was performed.

The same-App recovery no longer applies because the original process is gone.
The next physical prerequisite is one free capture slot. Its exact candidate is
`/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790680525007381-6ccf9b4b5965b93430950b73`,
which was resolved during the earlier read-only cache inspection. It is a newly
created unused recording, not either of the two previously authorized completed
copies. Ask once for archival/equality-checked deletion of only this phone copy;
preserve30228/R/all other phone records and all host originals. No such deletion
has occurred. Do not weaken the capture limit or reinterpret the earlier two-path
grant. After confirmation, prepare a tested no-BEGIN relaunch route, not a replay
of the old source-pinned launch or an automatic call to the same-App recovery.

The first action audit raced this shutdown: its top-level live-observation label
is superseded by the actual embedded CLOSED/CACHED_OBSERVATION_INCOMPLETE state
and the new closure audit. Preserve that original audit rather than rewriting it.

### P34-RECEIVE-04: Authorized Unused-Capture Cleanup And Relaunch

The user explicitly approved the immediately preceding one-directory request.
`.cache/p34-receive-screen/relaunch-authorization.json` records that grant;
do not ask again. Only the unused capture ending
`1790680525007381-6ccf9b4b5965b93430950b73` may be removed after fresh stopped-App,
zero-start, original-event equality, complete archival and exact resolved-path
checks. Keep every other phone capture and every host original. The owned failed
runtime configuration is archived through the existing checked retirement route,
not cleared. No firmware reset, flash, Boot change, capture-cap increase or APK
rebuild is part of this recovery.

`Tools/ota/p34_relaunch.py cleanup --root D:/github/my/E-Track` is write-once and
retains partial/uncertain results. Its `start` entry requires the successful exact
cleanup, source-bound tests and fresh stopped/config-retired state with the
protected completed30228 snapshot. It creates a new finite run using the normal
service/cell workers and full pre-BEGIN/native/finished-snapshot/readback checks.
It does not rewrite the failed plans or call the obsolete same-PID recovery.
The physical matrix remains one useful30228-to30229 bootstrap, then only after
full confirmed30229 one30229-to30230 pressure cell. Earlier observers sent no OTA.
Open the phone observation only after preparation and promptly invite the user to
keep the App foreground, rather than spending that window on host auditing.

Four new host tests passed in1.373s, including exact deletion order and path/data
negative cases, the real closed failure/authorization and retained-slot checks.
Evidence: `.cache/p34-receive-screen/relaunch/tests/result.json`. Existing336-case
coverage/source binding is unchanged; no core/firmware/App changes were needed.

Authorized cleanup completed: `.cache/p34-receive-screen/relaunch/cleanup/result.json`
is UNUSED_CAPTURE_PRUNED. The5090-byte event file exactly matches the original,
strict query validation proves zero upgrade starts, and the237-byte health file
is archived unchanged. The existing checked retirement archived the owned
configuration; only the exact granted recording was removed,8 ->7, other names
unchanged. USB closed. The interrupted turn completed this operation; do not
repeat cleanup. Subsequent continuation verified the completed receipt, current
closed owner and both test bindings before invoking the write-once `start` entry.

New run `20260929T133427-relaunch-69800` passed fresh prestart inspection:
App absent, configuration retired,7 records and the exact protected30228 snapshot.
The normal service owner is preparing; the phone App has not yet launched at the
prelaunch audit point. `.cache/p34-receive-screen/relaunch/prelaunch-audit.json`
verifies cleanup equality/closure and all selected host output paths. Do not
re-run cleanup or the older cached-start entry after an interruption; follow
this run's source-pinned owner/result instead.

At13:42:15 UTC the new run became READY_FOR_FULL_INSTALL_START: PID32525,
same verified291692-byte FULL package, fresh full30228/original Boot/CONFIRMED.
The user has been invited to tap Start once and keep the App foreground without
switching to chat. Start allowance ends about14:06 UTC; service expires15:05:15.
All current observers remain bounded/live; no new transfer result is claimed.

### P34-RECEIVE-05: Bootstrap Confirmed, Pressure Cell Preparation

`20260929T133427-relaunch-69800/s04` completed FULL_INSTALL_VERIFIED at
13:49:14 UTC. The original9334-record/9331-producer-line App snapshot is complete,
healthy and loss-free; raw SHA is
`6acd3dcb5f43cae001f4b20793e106494fc35cbb2062724e53a6d10353d3024e`.
Transfer291692 bytes took40.280338s (7.071824KiB/s),2279 DATA, zero retransmits,
complete ACK samples with P99=465880us. Installation/reconnect took48.821514s;
the two phases total89.101852s, excluding HTTP and initial binding. This bootstrap
was received by old30228 and is not a new-receiver speed result or1MiB reference.

Fresh full614632-byte App readback SHA
`0383af17bc76695fe651fa33a5235c8ef73361a2c94f6aba387776216137f637`
matches30229/3.2.29-p34r. Original65536-byte Boot SHA remains
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`;
BCB4/CONFIRMED, confirm_done1, SD ready1 and idle state verified. Worker/native/
USB closed, and network worker closed normally at13:50:29 UTC. Original report:
`runs/20260929T133427-relaunch-69800/analysis/1790689677272890000/result.json`.

Only after this actual confirmation, `prepare-patch --group receive-pressure`
created `.cache/p34-session/profile-receive-pressure.json`, SHA
`89167af710172f7b3456b20302dbe7c1b6c3486aa56ce40bf9bc8f495a8b63dc`.
It reuses the original prepared exact1048576-byte pressure package and target30230;
no assets/nonces, firmware or APK were regenerated. Current completed App PID32525
was quiesced with configuration preserved and USB closed at
`quiesce/1790689967150756100/result.json`. The already-confirmed second cleanup
phase now applies only to original30228 capture
`1790670122706640-c95ade7747c6ab922b507946`; current30229/R/all other captures and
all computer originals remain protected. No renewed permission request is needed.

Second-phase cleanup completed at
`completed-prune/1790690087375661800/result.json`: exact resolved old30228 path,
3723593-byte snapshot SHA
`c0c7bc45d2189eaafa1a351341579bb1f000235b2af0b9583e753b6ff2b3be88`
matches the original, only that recording removed,8 ->7 and USB closed. Current
30229 and all other records remain. The bootstrap completion/cleanup audit is
`.cache/p34-receive-screen/bootstrap-complete-audit.json`. The normal `start`
entry is now preparing receive-pressure from the already verified assets.

Pressure run `20260929T135725-69500/s04` reached READY_FOR_FULL_INSTALL_START
at14:05:28 UTC. Fresh full30229/original Boot/CONFIRMED admission and the current
exact1048576-byte downloaded PATCH passed before any Start; PID21364, target30230,
921600/window32. The user is invited to Start once and stay foreground, without
redownloading or switching to chat. The normal start allowance ends about14:29 UTC;
service expires15:28:50. Current owners remain finite/live. This is only readiness,
not a transfer/throughput result. Follow this run, never restart the completed
bootstrap. Prelaunch output audit: `.cache/p34-receive-screen/pressure-prelaunch-audit.json`.

### P34-RECEIVE-06: Exact1MiB Result And Closed Screen

Pressure run `20260929T135725-69500/s04` reached FULL_INSTALL_VERIFIED at
14:18:08 UTC. Exact1048576-byte PATCH transferred in116.718954s,
8.7732109045KiB/s,8192 unique DATA and zero retransmissions; all8192 ACK samples
are valid/complete, P99=353555us. One discovery, zero GATT/ACK/UART/parser/drop
errors. Installation/reconnect63.192273s; two measured phases179.911227s,
excluding HTTP download and initial binding. This is not a120s P95 assertion.

Compared descriptively with the earlier exact1MiB138.987678s/7.3675595904KiB/s
sample, transfer fell22.268724s (16.022085%) and throughput rose19.078927%.
It still misses9KiB/s: that needs113.777778s, another2.941176s reduction.
The two legal packages use different encoding/control workloads. Do not call this
strict same-package A/B, attribute the0.347195s installation difference to receive
optimization, or promote this one clean sample to formal reference/stability
acceptance.30/30,4h soak,10/10 recovery and independent acceptance remain open.

The unchanged, already-tested App timing analyzer partitions the new116.718954s
exactly: DATA GATT52.966977s; first-send preparation0.273948s; last-send to durable
61.506629s; same-block credit wait0; after-credit residual1.608552s; BEGIN to zero
durable0.223605s; final durable to END ACK0.139243s. There are7936 same-block gaps
and none consumes all32 credits. Relative to the old sample, last-send-to-durable
fell18.151359s and GATT fell3.800595s. Do not label the whole61.51s QSPI time.
Four-KiB durable interval P50/P95 changed534.344/716.975ms to448.920/622.795ms.

Native receiver observations corroborate reduced restore overhead: pump-work
32.968678s ->18.903269s; payload program4.123105s ->1.741045s; erase13.894193s
->11.760218s; journal read/program/verify and payload verify also fell. These
native phases overlap App waits and each other and must not be summed into an
extra wall-time saving. Strict internal Boot timing still reports EVIDENCE_GAP
(no target-confirmed sample in that trace), while final independent raw identity
and CONFIRMED verification passed. Runtime stack high-water remains unmeasured.

Retained full614632-byte30230/3.2.30-p34r App SHA:
`1b0fdb9578534975cce212eb5e9717e5e94711012b2c330463112e64ffa8b3cf`.
Original65536-byte Boot SHA:
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`.
BCB4/CONFIRMED, confirm_done1, SD ready1 and idle verified. Original snapshot is
3718509 bytes/33357 records/33354 producer lines, zero loss, SHA
`15964f32523ff3bc6ea23b0ba6d0fa644c94d7d1a673594d579d3ecbbcd617e3`.
USB/native/cell owners closed, cell worker exit0 without supervisor termination;
network owner closed at14:19:20 UTC with exit0. No extra phone cleanup or OTA.

Evidence: `runs/20260929T135725-69500/analysis/1790691391248239700/result.json`,
`.cache/p34-receive-screen/pressure-wait.json`, and
`.cache/p34-receive-screen/pressure-comparison.json`. The declared two-cell
receive screen is complete; P3-4 is not complete. Retain the candidate/30230,
original failed host attempts and all remaining phone/host records. There is no
implicit third cell or longer stability campaign below the throughput gate.
Next optimization work should isolate block-tail pipeline wait and GATT-call
cost; eliminating the entire1.608552s inter-send residual alone cannot recover
the missing2.941176s. Sender batching needs its own protocol/ACK/cancellation
design and host tests, not an increased credit window or weakened timeout/CRC.

## 2026-09-29 Receive Restore Candidate: P34-RECEIVE-01

User approved the next optimization batch. Codex root owns this implementation;
the only writable root is `D:/github/my/E-Track`. This batch is host-only and
does not replay either completed PATCH32 cell. Device retains verified30228 and
the original Boot. Sender batching is a separate candidate, not part of this one.

Original pressure App timing now partitions exactly to138.987678s:
DATA GATT56.767572s; first-send preparation0.299390s; block last-send to durable
79.657988s; same-block credit wait0s; after-credit residual1.821372s;
BEGIN to durable0=0.259761s; final durable to END ACK0.181595s.
All7936 same-block gaps have available credit at window32. Residual P50/P95/P99
is204/389/618us. These are App-observable boundaries, not isolated physical
costs or calibrated native intervals. Do not label79.66s as QSPI time.
Evidence: `.cache/p34-receive-restore/pressure-wait-r1.json`; new analysis tests
8/8 PASS at `.cache/p34-receive-restore/timing-r1/`. Historical inputs unchanged.

Finite host batch:
1. Preserve current dirty input bytes under `.cache/p34-receive-restore/before/`.
2. Add default-off `CONFIG_OTA_STAGING_QE_REUSE`. First restoration after binding
   remains full initialization; subsequent calls use the existing checked helper
   with boot-verified JEDEC ID and fresh status reads, never cached SR values.
3. Restore failures and erase/program errors invalidate eligibility; no silent
   operation retry or error-to-success fallback. Preserve N03 full-block compare,
   durable/bitmap/CRC/SHA semantics, protocol, Boot and installation behavior.
4. Run portable plus default/enabled real-HAL model tests. Cover state drift,
   ID fallback, rebind, restore failure, combined write/restore failures and
   recovery, alongside existing corruption/interruption/guard cases. Validate
   existing real driver helper separately; do not edit the driver unnecessarily.
5. If green, prepare a fresh App-only GCC candidate under `.cache/p34sr/{f,b}`;
   do not mutate old builds, generate OTA successors or install during this batch.

Host tests/build cannot prove physical speedup. The next device matrix must bind
new legal successor assets and complete observation/closure routes before use.
No commit/push/release/CI, independent acceptance or new phone cleanup in this batch.

### Receive Restore Host Results And Code Contract

`staging_restore_xip() -> 0/-1` retains the HAL result contract. The candidate
calls `qspi_xip_restore_checked(HAL::Qspi_GetJedecId(), 0)` only after a successful
full restoration. `OTA_StagingGetIo(io)` invalidates eligibility for non-null
bindings. BLE binds at initialization, not per DATA frame. The helper itself is
unchanged: W25Q128 only, fresh reset/SR1/SR2, exact `(0,2)` before reuse; other
IDs or status configurations retain full initialization. No cached QE boolean
authorizes memory mapping. Configuration0 remains the original full path.

| Input/state | Required result | Executed check |
| --- | --- | --- |
| First call/rebind | Full initializer | default/enabled HAL model |
| Valid W25Q128 SR pair | Checked restore; all six block-commit restores reuse only when enabled | HAL model plus real helper model |
| Changed protection/QE/status or different ID | Full initializer | HAL state/ID matrix; real helper65536 SR pairs |
| Restore failure on read/verify/erase/program | Error, no mapped read, no same-call retry; next recovery full | HAL failure matrix |
| Erase/program failure, cleanup restore succeeds or fails | Error and eligibility invalidated, including after successful cleanup | HAL combined-failure matrix |
| Corruption/interruption/invalid ranges/disabled OTA | Existing rejection and durable/bitmap behavior | portable/default/enabled regressions |

Portable staging112 checks PASS; enabled real-HAL163 checks PASS at
`.cache/p34-receive-restore/hal-r1/`. Default binary compiled without warnings
but exited `0xffffffff` with no model output twice. Both failures remain in
`hal-r1/default.log` and `hal-default-recheck/`; they are not relabeled PASS.
The exact same bytes, SHA`603a04a6af131524ffe8d18ca4dfac5f1695f6122dfe74a853cd8ea81396d47b`,
copied to `hal-name-probe/test_ota_staging_hal.exe`, ran163 checks PASS with no
rebuild. No IFEO or SilentProcessExit registry entry exists for default.exe;
name/path-associated host execution failure is observed, underlying cause UNKNOWN.
Future runners should use the explicit test name, not repeat the failing path.

Real driver helper suite10/10 PASS, no skips, at
`.cache/p34-receive-restore/driver-r1/result.json`, with original driver/HAL
inputs bound. This includes reset/status failures, full status-pair matrix and
mutation checks; the new HAL model is not presented as a replacement for it.
The timing-model8/8 plus these native/model checks are development self-tests,
not independent acceptance or physical throughput evidence.

The default-off ARM object is byte-identical to the preserved pre-change HAL
object under the actual production GCC compile command (candidate flag removed
from both commands). Both are5152 bytes with
SHA`7f9b0fed2f46c6157c8726040f908f1a98c8c6558620c2ca123843b036ca6878`.
Evidence: `.cache/p34-receive-restore/default-equivalence/result.json`.
This proves this disabled HAL translation unit unchanged, not whole-image
equivalence or runtime stack usage.

### Receive Candidate Build And Handoff

Fresh source `.cache/p34sr/f` inherits the measured coalescer source tree exactly
except `USER/HAL/HAL_OTA_Staging.cpp`. The previous binary is verified executable-
equivalent to the completed30228 readback outside the version/header region.
Source manifest, hashes and all copied filenames were checked before and after
build. Actual App compile enables only the new staging reuse flag in addition
to the inherited installation/coalescing/profile settings.

`.cache/p34sr/evidence/build.json`: RECEIVE_APP_BUILD_PASS,0 errors,638 warnings.
`warning-comparison.json` proves all638 diagnostics equal to the baseline after
source-root/separator normalization, preserving multiplicity; no new warnings.
App-only output `.cache/p34sr/b/app-gcc/X-Track-App-GCC.bin` is614632 bytes (+28),
SHA`53e43b46fa7f0aea8145e787966f03372fadcee6ef927be46254463cb156747e`.
This is an unfinalized build, NOT an installable successor asset.
GCC size: text613192,data940,bss559760 (the latter includes reserved sections,
not measured live heap/stack). Staging context remains16 bytes at the same
address;40KiB overlay,8KiB stack,32-byte guard and4632-byte post-link-reserve gap
remain unchanged. Runtime stack high-water remains NOT_MEASURED.

Next owner: Codex root. Prepare legal successors of retained30228 and a finite
single-variable receive-restore screen, with unchanged sender/window32/baud,
original Boot and full observation/identity closure. A bootstrap transfer installs
the candidate but measures the old receiver; only a subsequent legal transfer
measures this optimization. Keep the exact1MiB pressure criterion and identify
different successor-package bytes rather than calling them strict same-package
A/B. Bind/freeze new source-aware session/asset evidence; never repair old
preparation manifests after root HAL changes. Sender physical-write batching
remains separate and NOT_IMPLEMENTED in this batch. Do not replay completed
PATCH32 cells or delete unnamed phone captures to obtain evidence space.

No device/reset/OTA, Boot build, APK/CI, commit/push/release or independent
acceptance occurred. The successful build does not prove time saved or9KiB/s.

## 2026-09-29 PATCH32 Two-Cell Development Plan

### Final Two-Cell Outcome

Both declared cells are now complete. The pressure result is
`.cache/p34-session/runs/20260929T081420-42700/analysis/1790670723837319600/result.json`,
SHA`2dfe31ef5167cfa1ed5d94058d86c9b66c02ca56f44325cbb3a65101468d2949`.
Its status is the generic full-transfer `FULL_INSTALL_VERIFIED`; actual ETU kind
is PATCH, not FULL. `patch_install_measurement=true`,coalescer_bootstrap=false.

| Cell | ETU bytes | BEGIN-to-END ACK | KiB/s | DATA retransmits | Install/reconnect | Two-phase total |
| --- | --- | --- | --- | --- | --- | --- |
|30226-to-30227 FULL bootstrap |291771 |37.831629s |7.531597891 |0/2280 |48.689968s |86.521597s |
|30227-to-30228 pressure PATCH |1048576 |138.987678s |7.367559590 |0/8192 |63.539468s |202.527146s |

These totals exclude HTTP download, initial binding and later host full-readback
overhead. Different workload/package kinds are not a same-package A/B. The
1MiB screen is below9KiB/s; at the same length it needs at most113.777778s,
25.209900s less than observed. One138.99s sample is below the150s per-run bound,
not evidence for P95<=120s. Same-parameter30/30,4h soak,10/10 recovery, formal
reference admission and independent acceptance remain NOT_RUN/not admitted.
Do not label this completed development pair as P3-4 completion or start a
long campaign on a candidate that still misses the throughput gate.

The device retains30228/3.2.28-p34c,614604-byte App SHA
`ab1feaccaeb1afd52bd21e17e95f987d1b58161dbd92bd947f447397b47695d5`.
Original65536-byte Boot SHA is unchanged:
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`.
BCB=4/CONFIRMED,confirm_done=1,SD ready=1,session idle. The original snapshot
has33374 records,33371 producer lines, no loss and SHA
`c0c7bc45d2189eaafa1a351341579bb1f000235b2af0b9583e753b6ff2b3be88`.
Native/USB readers closed; device worker ended08:33:04 UTC and network worker
08:38:02 UTC, both exit0 without supervisor forced termination. The nested
tunnel launcher reports exit1 via the existing network context's job-termination
cleanup; listener_closed/worker_stopped are true. Preserve that original nonzero
receipt rather than claiming every nested process exited0. No App data clear,
third cell or further capture deletion follows. Keep30227/30228/R phone captures
and every host original; the last App is not forcibly stopped by this closeout.

The coalescing PATCH path ran successfully on device. Its observed configuration
restoration counters are patch603 calls/602 reused and backup309/308, with zero
failures or invalid cycle samples. They are not the host decoder's program-call
count, whole-installation seconds, or proof of speedup against an uncoalesced
same-package hardware baseline. Runtime stack high-water remains unmeasured.
Strict native Boot timing still has EVIDENCE_GAP for a missing target-confirmed
sample inside the trace; separate complete final target/Boot verification passed.

#### Original-Log Diagnosis And Next Owner

`.cache/p34-patch32/pressure-diagnosis-20260929.json` binds the original report
and snapshot, checks raw sample counts/bytes/extrema against its summary, and
derives only host-side observations without any device operation. DATA GATT
API durations sum56.767572s (8192 calls); all upgrade-labelled GATT calls
sum56.791413s, nested platform writes55.364385s, and the sole discovery0.022766s.
Do not add those nested sums or interpret a naive residual as pure ACK wait.

All256 successive durable4KiB confirmations are present. Their interval P50 is
534.344ms,P95=716.975ms,max=1033.758ms; quarter means are
570.157078/543.449516/537.886422/513.293266ms. This record does not reproduce the
earlier progressively slower Y transfer. There are no retries, GATT errors,
overlay/hardware drops, UART errors or parser errors. Native payload erase is
13.894193s/program4.123105s; pump_work32.968678s and other phases overlap those
operations and the App's sending/waiting. Different clock domains must not be
subtracted or summed into a causal transfer breakdown.

Next owner is Codex root: inspect original write-completion, window/credit and
durable transitions to choose one discriminating change, retaining exact ACK/
CRC/SHA/credit/4KiB guards. Neither higher baud nor a larger-than-admitted window
is justified by these observations. No new OTA is needed for that offline
analysis. Any future physical work needs its own finite successor matrix, not
replay of this successful package. Earlier READY/preparation text below is history.

### Bootstrap Completed; Pressure Preparation

The user reported success; the existing owner then completed full verification
at08:08:23 UTC. Original report:
`.cache/p34-session/runs/20260929T075409-91600/analysis/1790669255294501800/result.json`,
SHA`46e9016c6c923af079f11f94af395b43f3232fc62d63a1797bc4aa43c517d7a0`.
The291771-byte FULL transferred in37.831629s,7.531597891KiB/s,2280 unique/total
DATA, zero retransmits and complete ACK samples (P99=336064us). Installation/
reconnect48.689968s; non-overlapping two-phase total86.521597s, excluding download.
There was one discovery and zero GATT errors. This is not1MiB or same-package A/B.

Full614604-byte30227 App SHA is
`40aed03f0d676157b45714df43460169d218a43adbd40f971e349092d8a17b59`;
original Boot SHA remains
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`.
BCB=4/CONFIRMED,confirm_done=1,SD ready=1,session idle. The immutable App snapshot
SHA is`894614a833cf8e3f37d0689c477cc42ea4463b6e6bbf40394e462775db7aebf5`.
All native/USB owners closed normally; the device worker ended08:08:23 UTC and
the network08:09:32 UTC. Strict native Boot timing retains EVIDENCE_GAP for the
missing initialized/CONFIRMED-in-trace sample; separate full final identity passed.

Only after that real closure, pressure profile
`.cache/p34-session/profile-patch32-pressure.json` was written, SHA
`9e23af59f908adec4b95996c714aa52153580af042e59213f9ed71cffd85c22b`.
It binds the actual bootstrap report and unchanged exact1MiB package. Reuse the
source-bound310-case coverage, existing APK/build/package; no new build/test/CI
is needed merely because the predecessor advanced. The verified idle30227 App
PID23850 was stopped with configuration preserved and USB closed:
`.cache/p34-session/quiesce/1790669481351411400/result.json`.
Now apply only the previously authorized old30226 phone-copy cleanup, retaining
current30227/R/host originals, before the second fresh admission. No pressure
OTA or coalescer runtime performance has been observed yet. Earlier preparation/
READY/missing-pressure-profile text below is historical.

The conditional cleanup is complete:
`.cache/p34-session/completed-prune/1790669571026487400/result.json` verifies
the original30226 snapshot and deletes only the authorized
`1790663174745616-da201fb2336519ff9ce4b0f5` phone directory. Capture count8-to-7,
current30227/R/others unchanged, all host originals retained, USB closed normally.
The explicit `patch32-pressure/s04` start is now performing fresh admission;
this is the second and last physical cell in the declared screening plan.

Pressure run`20260929T081420-42700/s04` has now passed admission. Four initial
DNS readiness failures are preserved in its original actions; the same bounded
service subsequently passed HTTPS/package verification. No new tunnel/run or
device retry was substituted. Complete30227/unchanged Boot/CONFIRMED, Flash and
different old staging were checked, and the old-image reader closed normally.
PID21097 launched at08:22:05 UTC. At08:22:33 UTC, fresh producer records and the
exact1048576-byte PATCH yielded `READY_FOR_FULL_INSTALL_START` for30228 at
921600/window32. The pressure package hash remains
`92e3e03572e0ea34df866c30e9a177f075bb8a907434d6b6b314f8770b7b4cff`.
Original evidence is under `cells/s04/queries/` and `cells/s04/mcu/closure.json`.
At08:23:24 UTC, starts/ends0/0,loss0,healthy=true. One foreground Start was invited;
App-start wait ends about08:47:05 UTC, service09:45:24 UTC. The installed target
remains30227 until full post-pressure confirmation. Owners stay bounded/live for
the user action; do not replay bootstrap/pressure, add a compact third cell,
request the same permissions again, or claim a1MiB throughput result yet.

The user approved proceeding with the proposed host-first, two-cell plan after
completed30226/window32. Codex is the sole operator in D:\github\my\E-Track.
Retain all dirty work, original runs and old30223/30224 packages. The current
J-Link single-file history grant remains applicable; no new host output boundary,
Boot replacement, arbitrary BCB write, release or publication is inferred.

| Item | Bound input / operation |
| --- | --- |
| Baseline | Completed20260929T061847-23000/s04,30226, full original App/Boot/CONFIRMED evidence; all owners closed |
| Assets | New30227/30228 standard headers on the existing verified coalescer App build; original ELF/MAP/code/Boot reused |
| Build evidence | PATCH_APP_BUILD_PASS,614604 bytes,638 historical warnings/0 errors,720-byte own patch frame; no new build or runtime-stack claim |
| First cell | patch32-bootstrap/s04:30226-to-30227 FULL at921600/window32; the old receiver performs this install |
| Second cell | patch32-pressure/s04: actual completed30227-to-30228 legal exact1048576-byte PATCH at the same axes |
| Offline alternative | Compact30227-to-30228 PATCH is decoded/tested only; it is not a third physical cell and cannot run sequentially with the pressure alternative |
| Fixed boundaries | Original APK/Boot/protocol/CRC/SHA/credit/durable/retry rules and existing observation deadlines; no window beyond INFO/4KiB |
| Admission | Original build/source/decoder equivalence, positive/negative package checks, source-bound host tests, actual predecessor and free capture slot before launch |
| Stop / retain | Preserve any failed or uncertain action; no blind retry. After each success retain its fully verified target. No downgrade/Boot/BCB shortcut |
| Measurements | HTTP download, BEGIN-to-END ACK throughput, native PATCH/backup work, install/reconnect and full target confirmation separately |
| Next decision | If reference transfer is below9KiB/s, diagnose the original GATT/window/staging records before one-variable changes; no long campaign yet |

The two new groups are explicit descendants of speed-window32; original PATCH
groups keep window8 and their old asset dependencies. New artifacts live under
`.cache/p34-patch32/`; the existing asset engine is reused through a private
fixed-configuration adapter. All producer/nonces and intermediate failures are
write-once. Only actual completed30227 can create the pressure execution profile.
Capture cleanup eligibility remains distinct from permission to delete a phone
copy; archive, exact-path, idle and protected-current/R checks cannot be skipped.

### Host Preparation And Search Continuation

The first128-encoding search ended with `Bounded compression budget exhausted;
no exact witness`. `.cache/p34-patch32/assets/failed.json` and all partial inputs,
images, packages/nonces and measurement logs remain unchanged. One explicit
host-only continuation reuses the128 measurements, permits at most384 new
encodings, and rejects any changed input, other failure or prior continuation.
Its immutable inventory/source is in `assets/search-continuation/intent.json`.
Only46 new encodings were needed,174 total. The exact witness uses
count209367/seed1931/salt51:1048472 compressed bytes plus
104 package/header bytes, with no padding. Python strict EOS/full consumption,
byte-identical target, both native PATCH modes and13 pre-prepare rejection cases
passed; all18 native commands exited0.

The completed manifest is `.cache/p34-patch32/assets/result.json`, SHA
`655093a0de209d9b256ab244976239fbbb33bbfa282fe202b721773559d83068`.
FULL bootstrap is291771 bytes; compact PATCH307 bytes; pressure PATCH1048576 bytes,
SHA`92e3e03572e0ea34df866c30e9a177f075bb8a907434d6b6b314f8770b7b4cff`.
30227 image SHA`40aed03f0d676157b45714df43460169d218a43adbd40f971e349092d8a17b59`;
30228 SHA`ab1feaccaeb1afd52bd21e17e95f987d1b58161dbd92bd947f447397b47695d5`.
Bootstrap profile SHA`d5eddd138cc63342ce8394ed8918d4946111c16ae888161e27eab08b59f63610`
binds actual completed30226. The real pressure profile has not been created.
The17 new focused tests passed in75.021s at
`.cache/p34-patch32/tests/focused/1790666772512002000/result.json`.
The full310-test run in404.988s retained one obsolete test assertion failure:
`.cache/p34-session/tests/1790666927886135900/result.json`. That assertion said
window32 had no successor, contrary to the newly declared sole bootstrap
successor. Only those assertion bytes in `test_p34_speed16.py` changed; the
before-file hash, exact substitution and all other unchanged source hashes are
checked by `.cache/p34-patch32/retest.py`. All6 affected checks then passed in
27.550s;304 direct original PASS cases are reused, total310 covered. The final
source-bound report is `.cache/p34-patch32/tests/speed16-r1/result.json`, not a
fabricated310-case rerun. The original failed suite remains intact.
No physical cell, service, capture deletion, new build, CI, commit/push or formal
acceptance has occurred. The two exact additional phone-copy deletion boundaries
have been requested in this thread; general advance permission is not silently
extended to those paths. Only read-only recording archival may proceed meanwhile.

The first read-only archival is now
`.cache/p34-session/completed-prune/1790667632836054800/result.json`:
`COMPLETED_CAPTURE_ARCHIVED`, eight directories, original30225 snapshot identical,
phone mutations0. Private USB ended normally at07:40:54 UTC; all exits0, port
closed, original read-only ADB key unchanged. No App stop or native operation.
The requested exact deletion sequence, still awaiting confirmation, is:

- Before bootstrap, only
  `/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790651663430351-f87498813e0925f6ea4ed12c`.
- Only after full30227 confirmation and closed owners, before pressure, only
  `/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790663174745616-da201fb2336519ff9ce4b0f5`.

Each apply still requires original archival equality, exact resolved paths and
verified idle/absent App; current successful/R captures and all host originals
remain protected. Do not reopen service/observation windows while this permission
and full-store gate is unresolved. Existing exact J-Link history permission is
unchanged and must not be requested again.

### Authorized Bootstrap Admission

The user subsequently reaffirmed the advance grant in direct response to those
two exact staged paths. `.cache/p34-patch32/authorization-current-thread.json`
records that confirmation: execute the named cleanup and normal planned device
operations without per-step permission prompts. This does not broaden paths or
remove the actual30227 gate on the second deletion.

The verified idle30226 App PID21963 was stopped with configuration retained:
`.cache/p34-session/quiesce/1790668284103285700/result.json`. Only the authorized
old30225 phone copy was then archived/rechecked/resolved and deleted:
`.cache/p34-session/completed-prune/1790668338235057900/result.json`,8-to-7
directories. Both USB owners closed normally. Current30226/R/other phone captures
and all host originals remain intact. Proceed to the explicit bootstrap admission
with the unchanged tested source and prepared package; no OTA has occurred yet.

Bootstrap run`20260929T075409-91600/s04` is now admitted. Original complete30226
App/Boot and idle/CONFIRMED, receiver MAP/Flash and different old staging were
verified; its old-image native reader closed before App launch. The exact existing
APK launched as PID23850 at07:58:35 UTC. Fresh producer queries and downloaded
291771-byte30227 FULL package passed at07:59:03 UTC, yielding
`READY_FOR_FULL_INSTALL_START`,921600/window32. Original files are under
`cells/s04/queries/` and `cells/s04/mcu/closure.json`. At08:00:03 UTC the healthy
producer still showed starts/ends0/0 and loss0; the user was invited to one
foreground Start. App-start wait expires about08:23:35 UTC; the verified service
expires09:25:04 UTC. USB/native/network owners stay bounded and live for that
action, not closed merely because this message ends. Do not invoke a new start,
repeat cleanup, create the pressure profile or claim an installed30227 yet.

## 2026-09-29 Speed32 Takeover And Finite Screen

### Completed Window32 And Selection

The run `20260929T061847-23000/s04` completed normally at06:43:55 UTC.
`analysis/1790664201195542200/result.json` is FULL_INSTALL_VERIFIED, SHA
`ce31e9d0120a9b72ad92a50a7321d1ec59fc2b68665498ff026e0b2714074741`.
The exact291496-byte FULL package transferred at921600/window32 in35.988540s,
7.909853KiB/s,2278 unique/total DATA and zero retransmits. ACK samples are
complete; MCU drop/UART/parser/error counters are clean. The real App snapshot
SHA is `d0e2d8af8c65a15956749102bbc14de3d37f99044e7ab35ea90b02ed15d4fd39`.

Installation/reconnect took48.374671s; transfer plus installation/reconnect
total84.363211s, excluding HTTP download and initial binding. Against the
completed16 sample, transfer is15.246685% shorter, throughput18.023496% higher,
and the two-phase total8.365102% shorter. This is sequential successor screening,
not strict same-package A/B or the1MiB reference. ACK P99 increased from261827
to340282us. Both have one service discovery and zero write errors. Do not hide
latency changes, sum overlapping native phases or infer a causal install saving.
Derived comparison with exact original hashes/closed-owner/full-image checks:
`.cache/p34-speed32/comparison-20260929.json`.

The target is retained30226/3.2.26-p34s, full614412-byte App SHA
`17b4bcacd2fedb8e4a4654eb525f949a5a2826a41e6f6f13e76c95017fea4718`.
Original65536-byte Boot SHA remains
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`;
BCB4/CONFIRMED, confirm_done1, SD ready1 and idle session were read after reboot.
USB/native readers closed normally; the cell exited0 at06:43:56, and the root
closed the network at06:48:08, exit0/no forced termination. All originals stay.
The lower tunnel launcher reports exit1 because the existing network context
deliberately terminates its owned Job during cleanup (`prefix_phone.py` lines
203-216); this is distinct from supervisor `forced_termination=false` and main
worker exit0. The original closure confirms listener_closed/worker_stopped=true.
Do not summarize this as every child process having exit0.

The strict native Boot-phase result remains EVIDENCE_GAP because its initialized
target/CONFIRMED sample is missing; VTOR-only Boot residency is22.36..24.36s,
not internal copy time. Separate complete App/Boot/CONFIRMED readback succeeded.
This measurement gap is not permission to replay the successful installation.

DECIDED: shortlist window32, never expand beyond INFO/4KiB. Next owner is Codex
implementation/root: prepare a legal current30226 successor route for bounded
confirmation and the1MiB input; reassess the still48-second install/reconnect
separately. Preserve old AA/AB packages but do not send lower versions. Any new
PATCH-coalescing build/base must retain original Boot/protocol/CRC/SHA/durable
guards, get host validation and a declared finite physical plan before execution.
The oracle is full target/Boot/confirmation plus real reference throughput,
then unchanged30/30,4h soak and10/10 recovery gates. No formal acceptance or
production parameter selection is claimed by this single small-package result.

### 13:28 Takeover: Interrupted Config Retirement

Current human handoff: `20260929T061847-23000/s04` passed service readiness and
fresh full30225/original-Boot/idle/confirmed admission. The initial native reader
closed normally; the transition observer is owned by the same finite cell.
The diagnostic App launched at06:26:15 UTC, PID21963, and status is
`APP_LAUNCHED_CONNECT_AND_DOWNLOAD`. The user was asked to wake/unlock, connect
and download3.2.26-p34s without starting OTA. No transfer/query admission yet.
Start wait expires about06:51:15 UTC; service expires07:49:31 UTC. Keep actual
transfer/apply/readback allowances intact. Inspect this run, not the old failed
owner; never repeat its start or consume recovery again after this handoff.
The only external file update is the specifically approved JLinkDLL.ini history,
bound by native-before/after records in this run's original MCU closure.

New live admission: the explicit start consumed the final recovery into
`20260929T061847-23000/s04`. The original failed run/report remain unchanged.
Prestart phone inspection finished at06:19:14 UTC and USB closed normally;
the same temporary network is in its bounded DNS/HTTPS/package readiness.
No transfer has begun. Follow this exact run with status/collect/stop; do not
repeat start or consume recovery again. The phone's connect/download action is
requested only after App launch, and foreground Start only after full admission.

Current-thread authorization is now explicit: the user allowed the exact
J-Link history file update and advance-authorized subsequent in-scope work.
The supplemental immutable receipt is
`.cache/p34-session/retirement-recovery/1790661791457571800/authorization-current-thread.json`.
Keep the old machine-readable native authority unchanged for historical pins.
This supersedes the pending-permission checkpoints below. Execute the prepared
new linked window32 start with the final recovery report; do not repeat archival,
cleanup, the completed16 transfer or an already-consumed recovery. All ordinary
operations still follow the finite matrix and exact input/state admission.

Final consumable recovery supersedes the first report described below:
`.cache/p34-session/retirement-recovery/1790661791457571800/result.json`, SHA
`192f966dad4e06992b966971bd7628a08484d8036577be9f23ba82b7d977b062`.
The first report's host reload exposed a path-role error: a pinned external
`JLink_x64.dll` was treated as an output instead of a read-only source. The fix
hashes absolute pinned inputs without granting writes; archive/USB/observation
evidence still goes through project output guards. No DLL was loaded or executed.
The previous292-test PASS and before-fix sources are preserved. Scoped validation
at `.cache/p34-retirement-r3-tests/result.json` executed22 PASS, reused271 exact
unchanged PASS cases, total293; its AST comparison permits only `load_recovery`
and the new external-input regression to differ. A fresh bounded read-only USB
reconciliation passed under those new source hashes with zero phone/MCU mutations.
Use only this final report for `--retirement-recovery`; keep the first unchanged.

Final development result: `.cache/p34-session/tests/1790660919463604300/result.json`
executed292 tests, all PASS,0 failures/errors/skips (not independent acceptance).
The real read-only USB reconciliation is
`.cache/p34-session/retirement-recovery/1790661359573086100/result.json`,
`RETIREMENT_RECONCILED`, SHA
`bdeea0853a39ec7d21f466455de06f06cc59ccf8e2e90c3221392f9a86a272cc`.
The original629-byte config was found at its exact resolved archive path with
SHA `3727146db6dce80015f611f59ff6ee4b5b054d7110a6498e2e1b2da024271d4b`.
The original completed snapshot/count and absent PID/config were rechecked;
USB closed normally with its input key unchanged. Phone mutations0, native
operations0, no launch/OTA and no current-pointer rewind. The failed run remains
current. Next start uses this report via `--retirement-recovery`, after the
already-asked current-thread J-Link single-file permission is confirmed. Do not
rebuild packages, repeat cleanup/retirement or regenerate the recovery report
merely to continue. A source change requires actual affected validation and
source-bound reconciliation, not hand-editing the report.

The later run `20260929T045644-98600/s04` supersedes the earlier phone-not-found
checkpoint below. DNS/HTTPS passed. At05:01:55 UTC the exact previous config
move returned0, then its absence check failed because the phone disappeared.
The cell stopped before native admission, provisioning or launch, with original
`FULL_INSTALL_INCOMPLETE`. Its USB closed normally. This continuation closed the
remaining network normally at05:28:07 UTC; no forced termination or OTA replay.
The fresh doctor `1790659867472185600` confirms the exact phone/APK, no App PID,
no active config, seven captures and the original completed30225 snapshot; USB
closed normally. The archive still requires exact resolved-path/byte readback.

HOST-P34-RETIRE-01: add and test an explicit read-only retirement reconciliation,
then a single-use link into a fresh run of the same unspent30225-to30226 cell.
Do not alter failed evidence or rewind current. Keep package/nonce/axes and the
finite screening/stopping matrix below unchanged. No new cleanup, APK install,
firmware build, Boot/BCB write or formal acceptance is included. All host output
stays under this root; native history permission has been asked explicitly for
this thread before any J-Link contact. Until granted, only host/USB work proceeds.

HOST-P34-RETIRE-01 validation history: initial full host execution is preserved
at `.cache/p34-session/tests/1790660314729515200/`. It exposed the preexisting
window-matrix test's stale expectation for the later16/32 groups, then the new
test fixture's `run` attribute masked `unittest.TestCase.run` and terminated the
runner without a final suite report. Neither is an OTA result or a PASS. Both
were fixed in one batch, along with explicit failed-plan/cell-intent hashing.
The focused batch at `tests/retirement-focused-1/result.json` under the same
base executed21 tests with0 failures/errors/skips. An additional positive
new-owner/single-use test was then added before the fresh full host regression.

Root cause/lesson: a successful filesystem mutation followed by disconnected
readback is an outcome-reconciliation problem, not proof the mutation failed.
The original latch correctly prevented blind replay but lacked this exact
pre-admission recovery route. Preserve the no-launch boundary and closed
receipts; verify archive bytes without repeating the move. Similar post-action
failures must first identify the actual phase, never inherit this exception.
The stale matrix assertion was change propagation missed by earlier scoped
reuse; an all-group oracle must include every new axis. Test fixture names
must not shadow framework methods. These rules and executable signatures are
captured in the session-tool contract, not a new governance or acceptance scope.

### Explicit Authorization And Execution Entry

After the exact two-boundary question, the user explicitly authorized both
operations and asked to pre-authorize subsequent work. The current receipt is
`.cache/p34-speed32/authorization-20260929.json`. This supersedes the pending
permission statements below, which are retained as history. The named J-Link
history file and exact old Z phone copy are approved, with all archival/path/
idle checks unchanged. Routine in-scope P3-4 operations proceed under the finite
matrix without repeated questions. Unspecified external host paths, unrelated
devices, destructive recovery, Boot/BCB replacement or release/publication are
not inferred from the general advance statement.

Execute verified completed-30225 quiesce, then revalidated old-Z-only cleanup,
then fresh window32 start. All originals and current30225/R remain protected.
The device becomes human-dependent only after real query/package/capture
readiness; do not ask for Start during setup.

Completed under this grant: `quiesce/1790656699531130300/result.json` stopped
only the verified completed30225 App PID17309, preserved its configuration and
closed USB normally. `completed-prune/1790656796405145400/result.json` rearchived
and verified the original Z files, resolved its exact path, deleted only the
authorized Z capture, and verified the directory set changed8-to7 with current
30225/R/others retained. USB closed normally and input ADB key stayed unchanged.
Both paths are under `.cache/p34-session/`. No OTA was replayed. Next is the
explicit new32 start using the already-verified profile/package.

The subsequent start attempted `20260929T044431-40000` but the exact phone was
not visible in the bounded20-second private USB window at04:44:42-04:45:03 UTC.
Original `prestart-phone/result.json` is `PHONE_NOT_READY`; commands report
the exact device not found. USB closed normally, all three exit codes0, port
closed and ADB key unchanged. No plan/current-pointer update, network/J-Link
worker, app launch or OTA occurred. The source/asset/test state remains valid.
The user was asked to reconnect/unlock and confirm the phone available. Do not
repeat without that state change, and never repeat the completed quiesce/Z
deletion. Resume with the already-prepared explicit window32 start once the
phone is available; fresh admission supplies current identity/space then.

The current user asked this Codex session to take over P3-4 with speed first,
then approved the proposed execution plan. Preserve the dirty main worktree,
all old runs and frozen inputs. This is implementation/development work, not
independent acceptance, commit/push, release, Boot replacement or P3-8 work.

The original `20260929T030709-75800/s04` succeeded at 03:24:56 UTC:
`analysis/1790652269440491900/result.json` is `FULL_INSTALL_VERIFIED`, SHA
`2f1379e12d591225e81b973e976270cc80cfb0964f34f832d6c12f3a690e7934`.
291412 bytes, 921600/window16, 42.462693 seconds / 6.701930827844574 KiB/s;
2277 unique/total DATA, zero retransmits and complete ACK samples. Installation
and reconnect were 49.601807 seconds, combined 92.064500 seconds. Full 30225
raw image, unchanged original Boot, idle/CONFIRMED and SD ready were verified.
Relative to Z/window8, observed transfer time fell 31.4652% and combined phases
fell 16.9578%; different legal packages mean sequential screening, not strict A/B.

The old agent stopped on API `invalid_encrypted_content`, not an OTA failure.
The cell owner had exited normally at 03:24:56 UTC. The current session inspected
the exact ownership/closure records, preflighted local stop outputs, and used
the existing `stop --run 20260929T030709-75800 --cell s04` entry. The network
exited normally at 03:56:13 UTC, exit 0, no forced termination. Its closed
receipt is `runtime/network/closed.json`. No device operation or transfer was
repeated. Do not turn either old READY notes or unexpired URL time into live state.

| Field | New finite screen |
| --- | --- |
| Operator/root | Current Codex sole operator; D:\github\my\E-Track |
| Predecessor | Actual completed `20260929T030709-75800/s04`, 30225, original Boot |
| Group/cell | `speed-window32/s04`, one zero-start full transfer |
| Axis | 921600, requested window32; sender still clamps to INFO and frozen 4 KiB capacity |
| Fixed inputs | Existing verified APK, N04 executable/MAP/ABI, Boot, GATT reuse, without-response, MTU negotiation and original retry/durable/CRC/SHA guards |
| Target | 30226 / 3.2.26-p34s; 614412 bytes, only standard header differs |
| Target SHA | 17b4bcacd2fedb8e4a4654eb525f949a5a2826a41e6f6f13e76c95017fea4718 |
| Package | 291496-byte FULL .etu; acdbdb19b58c0ea58db0b5c74c216e959b3b2fef9bb396ee3012a1af928260c0 |
| Recovery | Retain last verified 30225 until normal OTA; after success retain30226. Uncertain outcome requires original snapshot/full identity reconciliation, never automatic replay/downgrade/Boot or BCB writes |
| Runtime | Existing finite network/cell/start bounds; 900-second active observation plus normal install/readback/cleanup allowances, never shortened by setup |
| Stop/selection | Integrity error, uncertain state or no progress uses existing stop/ABORT rules; no unchanged retry. Compare original window8/16/32 observations; only an evidence-supported finalist advances to a separately recorded limited confirmation |
| Remaining acceptance | Legal 1 MiB, >=9 KiB/s, duration/retransmission gates, same-parameter30/30,4h soak,10/10 recovery and independent acceptance remain unexecuted |

Assets/profile were prepared once by `prepare-speed32`, reusing the admitted
N04 build without firmware/APK compilation. Python/native decode, Boot/guards/
workspace and all four negative cases passed. Manifest:
`.cache/p34-session/speed-window32/assets/result.json`; profile:
`.cache/p34-session/profile-speed-window32.json`. Original generator/nonce
and all input hashes are preserved. Source-bound affected host tests executed
58 checks (zero failures/errors/skips) and reused 220 unchanged original cases:
`.cache/p34-speed32/tests-r1/result.json`. No window32 device run exists yet.

One bounded read-only USB preview confirmed the exact phone/APK and8/8 capture
slots. It stopped on an additional `health.json.tmp` in old Z, not on an OTA or
phone connection failure. Original failed receipt:
`.cache/p34-session/completed-prune/1790655696859365300/result.json`.
Its USB closed normally with unchanged ADB input key and no phone mutations.
The narrow host fix archives this known pending file as opaque bytes after two
identical bounded reads; it never replaces normal health or the exact finished
snapshot as the verdict. Unknown files, multiple snapshots, unstable/oversize
pending files still reject. Eight affected tests passed and 272 prior checks
were reused, total280 covered, at
`.cache/p34-speed32/tests-cleanup-r1/result.json`. A new read-only archival
attempt is justified by this diagnosed/fixed input-shape issue, not an OTA retry.

That second preview (`completed-prune/1790655929269461700/result.json` under
`.cache/p34-session/`) stopped because the retained nonempty-file primitive
rejects zero bytes. The original `stat` receipt proved the pending file is empty.
The final fix uses `pending_health_bytes(p, package, remote)` only for the exact
capture's `health.json.tmp`: stat0..8192, read at most8193, verify exact length
and identical bytes on two reads. Ordinary nonempty log reads stay unchanged.
The modeled tests now use this real stat/read command shape, including empty,
nonempty, changed and oversized pending files. Final eight tests passed with
272 unchanged cases reused: `.cache/p34-speed32/tests-cleanup-r2/result.json`.

The final read-only preview succeeded:
`.cache/p34-session/completed-prune/1790656251261324700/result.json` is
`COMPLETED_CAPTURE_ARCHIVED`, apply=false, phone_mutations=0, eight directories
retained. Z's1042424-byte snapshot matches the original SHA
`a55518197fa069e7f7042a76b7313fca29a0e99866d69744a35b76d5aacba311`.
Both health reads, events and the exact zero-byte pending file were preserved.
All three bounded USB scopes closed normally with unchanged ADB input key;
the last closed at04:31:14 UTC. No App stop/config change, phone deletion,
J-Link contact, MCU reset/flash or new OTA occurred. Current source pins match
the final test result. No new32 worker/network was started. The next device
mutation remains gated by the two explicit current-thread permissions below.

Before any new device mutation, resolve these explicit boundaries in the current
thread, then verify phone identity, stopped/completed App, capture capacity and
fresh MCU/Boot/BCB/staging identity. The current agent asked permission for:

- `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`: J-Link connection-history
  updates only, no cleanup or other project-external writes. An old authorization
  receipt is not this thread's authorization; generic continue is insufficient.
- The one old Z phone directory
  `/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790606692563314-ee73468a16dc2b5a592c55c7`:
  delete only after byte-identical local archival and exact idle/path checks.
  Preserve current30225, R, every other phone directory and all host originals.

At the preparation checkpoint, neither requested exception had yet been explicitly granted; the later explicit authorization above supersedes that checkpoint.
No J-Link connection, phone deletion or new OTA has been performed by this agent.
Proceed with offline work meanwhile. Once admitted, use the existing `quiesce`,
exact predecessor `prune-completed`, and explicit window32 start, not a new
controller or old Y/Z commands. Keep shared runtime sources unchanged while owned
workers run. A failed host collector never justifies replay of successful16/32.

## 2026-09-29 Speed16 Live Admission

The user confirmed the phone connected. `p34.bat quiesce --run
20260928T144139-55600 --cell s04` verified the exact phone/APK/completed Z
capture and preserved the configuration; the App already had no PID, so no
force-stop was issued. Original result:
`.cache/p34-session/quiesce/1790651002804054200/result.json`.
The already-authorized `prune-completed --run 20260927T162548-11400 --cell s04
--apply` archived and verified only Y, then removed that phone copy. Count 8 to
7; Z/R and the other directories are unchanged. Original result:
`.cache/p34-session/completed-prune/1790651057136539800/result.json`.
Both USB closures report normal exits/closed port/unchanged input key.

The prepared start command created `20260929T030709-75800/s04`. The same new
QUIC tunnel's DNS failed at offsets 0/15/45/90 seconds and resolved on the
existing fifth check at 150 seconds; HTTPS succeeded. No second service was
started. Network worker PID 3644 and cell worker PID 12904 are bound to their
runtime configurations/heartbeats, not identified by PID alone.

Fresh MCU admission retains Z/30222 and the original full Boot. At 03:13:39 UTC,
BCB=4/CONFIRMED, SD ready and idle/zero session durable/bitmap were observed.
The preserved journal belongs to the completed Z package, not the new package;
no journal erasure or control BEGIN/ABORT was performed. The sender's first
different-package BEGIN must still confirm zero durable/bitmap.

At 03:14:51 UTC the new phone capture passed query/package readiness: two real
GET_INFO records, MTU247/chunk244/without-response, and the exact 291412-byte
30225 package. App PID17309/capture1790651663430351-f87498813e0925f6ea4ed12c.
At 03:16:47 UTC health was healthy/zero loss/error with starts=ends=0.
The user was asked to press Start once while keeping the App foreground.
This is READY, not a speed or installation result.

Original current evidence is under `.cache/p34-session/runs/20260929T030709-75800/`:
`actions.jsonl`, `cells/s04/queries/result.json`, `cells/s04/fresh-begin.json`,
`cells/s04/mcu/receiver-admission.json`, and `runtime/{network,s04}`.
App-start deadline is 03:39:25 UTC; cell supervisor approximately 04:15:58 UTC;
service expires 04:37:50 UTC. Preserve independent active/install/readback
allowances; reconcile current receipts before any retry. Do not replay Z.

## 2026-09-29 Read-Only Takeover Of The Prepared Speed Screen

The current user again prioritizes P3-4 speed. Root/main is
`1e1f92f2254bf826b44d9807c5522051991906e8`, two commits ahead of the local
`origin/main` reference; no fetch, checkout, index update, commit or push ran.
Existing product/Boot/Flutter/CI changes, untracked tools and original evidence
remain intact. The tested APK/firmware lineage is not this dirty root tree.

The takeover rehashed 102 distinct expected file records: all matched, including
the current test sources, APK, prepared package, Z inputs/full readback and
matching GCC ELF/map. The prior 10 executed plus 259 reused checks were not rerun.
The original Z result and both normal worker closures were inspected; the service
is expired, no later run directory exists, and no USB/OTA command was replayed.
Receipt: `.cache/p34-speed16/takeover-20260929/result.json`.

The conservative process inventory returned NEEDS_RECONCILIATION because it also
listed PowerShell PID 9160. A read-only WMI check of its creation time, executable,
command line and parent identified the scheduled cc-connect daemon, not an OTA
reader. No process was stopped or modified. The initial receipt is preserved;
the separate disposition is `takeover-20260929/reconciliation.json` in the same
speed16 directory. This was a host inventory classification, not a failed product
test or a reason to repeat a transfer.

The last device sample remains September 28 15:00:25 UTC: Z/30222, original Boot,
BCB 4/CONFIRMED, SD ready, idle session and baud 921600. The post-reboot session's
zero durable/bitmap does not prove staging Flash erased. No fresh device identity
is claimed. Current phone availability has been asked but not confirmed; the
known-unavailable USB path is not retried without that state change.

The next action remains the already-prepared speed-window16/s04 screen below,
not native instrumentation, PATCH preparation or obsolete Y-to-Z instructions.
The existing exact Y-only archival cleanup grant is retained. Once the phone is
available, use fresh phone/APK/space admission, completed-Z quiesce, verified
Y-only cleanup, then fresh network/MCU/recording/package admission before Start.
Keep Z/R and all host originals. No new speed measurement, build, CI, hardware
operation, deletion or independent acceptance occurred in this takeover.

## 2026-09-29 Transfer Speed First: Window 16

The user explicitly prioritizes actual OTA speed and authorizes proceeding.
P34-WAIT-01 remains unresolved but is no longer a prerequisite for all speed
work. No new native-clock instrumentation, APK build, PATCH pressure campaign
or formal 30-run campaign is part of this first speed-screening batch.

The subsequent read-only recording preview stopped before phone admission:
`.cache/p34-session/completed-prune/1790614710331686200/result.json` reports
`exact phone did not become online in the bounded USB window`. The private
USB scope ran 16:58:41-16:59:02 UTC on September 28 (00:58:41-00:59:02 Beijing
September 29), then closed with stop/server/launcher exit 0, port closed and
ADB key unchanged. No App stop/deletion, BLE/J-Link, network service or OTA ran.
Do not repeat without the phone reconnect/unlock or other discriminating change.

The next human dependency is reconnecting/unlocking phone 10ADA4197U001CK.
The previously occupied store also requires exact cleanup scope if still full:
after byte-identical archival, remove only the old Y phone copy
`/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790526764868470-ce28d15e511394dcc11d74d0`.
Keep Z, R and every host original. The old specific X deletion grant is already
consumed. On September 29 the user explicitly approved the exact Y directory
request above and stated that the phone cannot currently connect to the PC.
Y cleanup is now authorized but NOT EXECUTED; this does not authorize deleting
Z/R, other captures or clearing App data. No further USB attempt is made while
the known unavailable-phone condition persists. Existing device/network owners
remain CLOSED; the old service is expired and must not be reused.

The necessary offline package/profile/tests are complete. After the user reports
the phone available, first recheck exact phone/App/recording state. Then use
`quiesce --run 20260928T144139-55600 --cell s04` and the exact
`prune-completed --run 20260927T162548-11400 --cell s04 --apply` after archive
verification, retaining the current Z record. Start a fresh finite QUIC/MCU
window using `profile-speed-window16.json`, not a replay of Z or the old Y-bound
profile. No per-OTA approval is needed for this already-declared speed screen.
Authorization and output audit: `.cache/p34-speed16/authorization-pause.json`.
The earlier E120 receipt remains an unchanged pre-approval snapshot.

The proposed same-package short pair would first require rebuilding the old
prefix/control-state route for Z. To avoid making that preparation the main
task, use one zero-start full window-16 screen against the existing N04 window-8
records: Y 70.363044 s and Z 61.957856 s. X 53.658056 s remains historical
context; its receiving executable preceded the N04 installation change and is
not a third byte-identical N04 receiver. This full screen is sequential evidence,
not strict same-package A/B. A controlled short pair remains an option only if
the screening result is ambiguous and useful enough to justify its preparation.

| Field | This finite batch |
| --- | --- |
| Owner/root | Codex sole operator; D:\github\my\E-Track |
| Retained receiver | Verified Z 30222 / 3.2.22-p34i; unchanged original Boot |
| Group/axes | speed-window16, s04 only, 921600/window 16 |
| Target | 30225 / 3.2.25-p34s, 614412 bytes; only standard header differs from Z |
| Raw target SHA | 72bc7fd20d2d615d135a4c73af1b86f89fcff8569cfdfc62bbdc4849a733d999 |
| Package | 291412 bytes; SHA 4a2e4a5ff01ea6c2fdd129ff95a9766ee734adc3900ad169e60207779850e94e |
| APK/transport | Existing verified p34probe APK; GATT reuse, without response and original MTU negotiation |
| Actual changed link parameter | Window 8 to 16; no baud, receiver code, Boot or sender-code change |
| Observation | Existing valid App stopwatch and MCU timing/readback; invalid native epoch trace is not a gate |
| Stop/integrity | maxRetries=5; 30 s no durable progress abort; preserve CRC, sequence, bitmap, 4 KiB durable and final raw/Boot/CONFIRMED checks |
| Runtime | Existing finite network/cell lifetimes and 900 s active observation with apply/readback reserve |
| End state | Retain verified 30225 after success; reconcile uncertainty without replay or downgrade |

Codes 30223/30224 remain reserved in the preserved offline coalescer assets;
this screening uses explicitly bounded 30222-to-30225 admission instead of
overwriting those identities. Those old AA/AB headers cannot be installed after
30225 without preparing newer legal headers. No new firmware compilation ran.

New assets passed Python/native decode, Boot/guard/workspace checks and four
invalid-package rejection cases. Evidence:
`.cache/p34-session/speed-window16/assets/result.json`.
Ten targeted group/configuration/identity/cleanup-selection checks passed, with
259 prior cases reused (269 total covered): `.cache/p34-speed16/tests-r1/result.json`.
This includes protecting original Z and selecting only its actual predecessor
Y for a potential archive cleanup; eligibility is not deletion authorization.

Report actual seconds, throughput and retransmissions against both N04 samples.
A result slower than Z does not justify more identical attempts. A modest gain
within the existing variation is only a candidate, not a proven improvement;
a clear gain with integrity intact advances to limited confirmation. Do not
attribute any change to RF from these differently packaged sequential samples.
Recording-space admission comes before launch; preserve R, Z and all host
originals. No app-data clearing, Boot replacement or new external host output
is authorized by this note.

## 2026-09-28 Phone Reconnected: P34-WAIT-01

### Authorized Cleanup And Fixed-Window Diagnostic

#### Completed Z Measurement And Native Timing Gap

`20260928T144139-55600/s04` completed normally. Original result:
`analysis/1790607627016147200/result.json` = `FULL_INSTALL_VERIFIED`.
Z is 30222 / `3.2.22-p34i`, 614412 bytes, raw SHA-256
`3b9ea8e9eaa4c47e7523053172eb9c94bc2b72bb44c76da8d7d188219920046d`.
The complete 65536-byte original Boot still matches
`55200bb8b9399b5b2fa3e9b9d02d0504bec066f7624d0f293d82cb4244505f62`.
The App snapshot is healthy, zero loss/error, one completed start/end. The cell
worker closed normally at 15:00:44 UTC and the network worker at 15:03:06 UTC;
both exit 0 without forced termination. USB and MCU readers closed. Do not ask
for another Start, reuse the endpoint, or replay the successful upgrade.

| Bound measurement | Result |
| --- | --- |
| Package / baud / window | 291526 bytes / 921600 / 8 |
| BEGIN-to-END ACK | 61.957856 s, 4.594951758 KiB/s |
| DATA | 2278 unique / 2278 total, zero retransmits |
| ACK latency | 2278 complete samples, P95 231.477 ms, P99 279.531 ms |
| Installation and reconnect | 48.906839 s |
| Combined observed phases | 110.864695 s |

The original seven-check App wait model's function/loop bodies were reused
unchanged for Z, not rerun for old X/Y and not substituted for native evidence.
New derived evidence is `.cache/p34-session/native-diagnostic/z-analysis.json`.
Z's transfer partitions are DATA GATT 26.497391 s, estimated credit wait
18.216853 s, last-send-to-durable 15.850700 s, and other boundaries 1.392912 s.
Relative to Y, transfer is 8.405188 s shorter: GATT is actually 1.237074 s longer,
while estimated credit wait is 7.354064 s shorter and block-tail confirmation
2.343908 s shorter. Z is still 8.299800 s slower than X. This does not support
calling the transport fixed, attributing BLE speed to QUIC, or mixing install
time into transfer. Y/Z both observed about 49 s after receive, but sequential
different legal packages are not formal repetition or same-package A/B proof.

The 1085775-byte native log is preserved. Query-time capability was real, yet
strict complete-log analysis rejected `native clock/order moved backwards`:
five global backward steps (largest 332740 us), nine same-thread backward
steps, no duplicate raw lines. Whole-capture counts are 2288 method calls,
2287 write callbacks and 1685 notifications. Counts alone do not establish
lost DATA, one-to-one transfer pairing or the reason for time reversal. Do not
sort these timestamps, synthesize monotonic time, subtract epochs from the App
stopwatch, or infer native latency from the successful collector receipt.

`P34-WAIT-01` remains NEED_EVIDENCE. Next instrumentation must put native
monotonic timestamps and operation/packet identity inside producer records,
then test their pairing/loss/clock gates before another device experiment.
Changing logcat display format alone is not proof of a monotonic producer clock.
This successful OTA must not be repeated to replace its invalid native timing.
Retain Z; the old Y-bound AA bootstrap and Y-to-Z window-16 profiles are stale.
AA/AB assets and prior self-tests remain preserved, not installed or rebuilt.
Evidence E114-E115 and the final current-batch output audit are authoritative
over the earlier readiness descriptions below.

Latest runtime: `20260928T144139-55600/s04` reached
`READY_FOR_FULL_INSTALL_START` at 2026-09-28 14:45:23 UTC. The fresh Y/Boot
checkpoint and downloaded 291526-byte Z package passed the existing gates.
`android-trace/query.json` contains actual PID 7119 markers: one successful
FFF2 write callback and one FFF1 notification, no pending callback. This proves
the existing APK's native logging route works in this window, not a speed gain
or explanation of the older X/Y regression. The App health at 14:52:12 UTC
still had zero starts/ends and zero lost/error; the user was asked to tap Start
once and stay foreground. New observations must come from this live owner.

The preceding `20260928T140443-82100` attempt stopped at network preparation:
HTTP/2 TCP 7844 connections timed out, while that same cloudflared self-check
reported successful QUIC connectivity. No device cell was created. Network
worker, listener and launcher closed; original error/plan/logs are preserved.
Official parameter documentation retrieval also timed out at TLS; the local
2026.9.1 client's own protocol diagnostics were the actionable evidence.

The maintained entry gained `recover-network`, restricted to this diagnosed
no-cell failure with verified closure and the actual completed Y predecessor.
It restores only the host current pointer and writes a separate QUIC profile;
it does not modify the original profile or device. The private phone-module
adapter changes only the exact owned cloudflared launcher argument from http2
to quic, leaving ADB, frozen helper bytes, URLs, package and BLE parameters
unchanged. Nine focused network/profile/CLI tests passed; 254 prior cases are
reused by that follow-up receipt (263 total covered). Recovery evidence is in
`network-recovery/20260928T140443-82100/result.json`.

The single changed-protocol attempt above successfully registered the tunnel
and verified the firmware service before opening the device cell. No firewall,
account, billing or system network setting was changed. Evidence E110-E113.

After the explicit user grant, `quiesce/1790601092639185100/result.json`
confirmed the exact completed Y/configuration while the App PID was already
absent. No force-stop command was necessary. Then
`completed-prune/1790601173261839000/result.json` archived and byte-verified X
and removed only its authorized phone copy: 8/8 to 7/8 slots, all other seven
directories unchanged. Both USB scopes closed with stop/server/launcher exit 0,
port closed and the read-only ADB key unchanged. No BLE/J-Link or OTA ran here.

The existing session tool now has `n04-diagnostic8` and `prepare-diagnostic`.
This separate group binds actual completed Y to the already frozen Z bytes at
921600/window 8; it does not edit/repack the paused window-16 arm. The original
APK/sender, N04 executable and Boot stay fixed. Profile:
`.cache/p34-session/profile-n04-diagnostic8.json`.

`Tools/ota/p34_android_trace.py` captures only the freshly launched exact PID's
FBP Android tag on owned ADB port 5062. One joined reader is bounded to 16 MiB
and 2600 seconds, within the original cell/USB deadline. No log buffer clear,
logging-setting change, APK replacement or implicit device operation occurs.
Its query gate requires actual FFF2 method/write-success and FFF1 notification
markers before READY. Missing/partial/ambiguous/error/PID/clock evidence rejects
the gate. Captured epoch time is not synchronized to the App stopwatch, and the
write callback means local buffer availability, never durable confirmation.
The phone UI itself is unchanged; the operator must not tap Start before READY.

Bounded execution plan: one diagnostic group, s04 only. Reuse the existing
fresh App/Boot/BCB/staging/clock/flash admission, immutable download verification,
MCU trace, full snapshot and final raw readback route. Start Android collection
before asking the user to connect/query/download. Only after both readers and
native query markers are ready may the user start one zero-start Y-to-Z FULL.
Allow the normal 900-second active observation budget and full apply/reconnect
verification; maxRetries=5 and 30-second no-durable-progress abort stay intact.
Missing native markers stop before inviting DATA; uncertain device results are
reconciled, never replayed. Retain Z if verified, otherwise determine actual
state. No reset, flash, Boot replacement, AA installation or window-16 test is
included. Installing Z invalidates the old Y-bound AA bootstrap profile, which
must be rebound to actual retained state before any later AA work.

Host validation: `.cache/p34-session/native-diagnostic/validation.json` binds
59 distinct current-batch tests and 198 unchanged prior cases (257 covered).
The initial 57-test batch kept its two subtest errors from a missing MAX_BYTES
test-fixture field. After correcting only that fixture and adding the mandatory
collector guard, five targeted tests passed, including old observer/worker
regressions. An AST scope-list bookkeeping failure is also retained; no extra
test run was needed to correct its redundant nested-function name. These are
development self-tests, not new speed measurements or independent acceptance.

The native trace still needs real query-time capability and per-packet pairing;
`P34-WAIT-01` remains unresolved. Preparation is not proof that the old regression
has been explained. Evidence: E107-E109 on the progress board.

The user reports the phone connected and requests continuation. This is the
external-state change needed after the two preserved USB-absence attempts, not
permission to replay their directories or a completed OTA. Sole operator: Codex;
writable root remains `D:\github\my\E-Track`.

The immediate finite action is one read-only original-history retrieval in
`.cache/p34-session/n04-window16/android-history-03`. Reuse the unchanged
`xy-android-history-ready.py` and its six-check E91 receipt with only its output
directory rebound at invocation. Its original 20 s enumeration wait, 150 s
command budget with cleanup reserve, private ADB port 5062, exact phone/user/APK
identity and graceful closure gates remain. Preserve main/system buffer metadata
and PID/tag-filtered `logcat -d` for original X/Y; no clearing buffers, stopping
the App, deleting captures, opening BLE/J-Link, changing firmware or new OTA.

After retrieval, bind retained log timestamps to the original X/Y intervals.
Missing or rotated history is an evidence gap, not proof of radio/Android/MCU
causality. That outcome requires a minimal fixed-window-8 diagnostic plan before
changing receiver or window. An unauthorized/unavailable phone requires only the
specific physical action actually reported. AA/AB and Z remain prepared/unrun.

### Executed Retrieval And Next Diagnostic Gate

`android-history-03/result.json` records successful exact phone/user/APK
admission and retrieval at 2026-09-28 09:07:36-09:07:50 UTC. Both filtered original
PID logs are zero bytes with successful command exits. Main/system buffers are
each 4 MiB, but the empty filtered result does not establish when/why the original
records disappeared. There are no native samples to bind to the X/Y transfer
intervals, so `P34-WAIT-01` remains unresolved. Do not repeat historical retrieval
without a new discriminating reason or call this proof of radio interference.

One subsequent read-only recording preview completed at
`.cache/p34-session/completed-prune/1790587482883000100/result.json`.
Eight of eight recording slots remain occupied. The exact X phone snapshot is
byte-identical to its original completed capture; Y's protected capture is still
present. Both private USB scopes closed gracefully with port 5062 closed and
the read-only ADB key unchanged. No App stop/deletion, BLE/J-Link access, new OTA,
firmware/APK build, CI or host test rerun occurred.

The user has been asked for the previously unresolved exact cleanup scope:
after verified idle state, stop only the diagnostic App and delete only
`/data/user/0/com.wen.gaia.gaia.p34probe/files/p34-observations/1790525527314706-832f67cf9bb33036d6f7a279`.
Keep Y/R and every host original. No deletion or stop is authorized by this note;
wait for the user's answer and recheck the exact state before any apply step.

The user subsequently answered "allowed" to that exact request, followed by
continuation. This authorizes the diagnostic App's verified-idle quiesce and
only the named X phone copy deletion after byte-identical archival. Execute the
existing `quiesce --run 20260927T162548-11400 --cell s04`, then
`prune-completed --run 20260927T160919-23000 --cell s04 --apply` serially.
Retain configuration, all other captures, the original Boot and current Y.
Preserve failures and reconcile uncertain outcomes without repeating deletion.
Host outputs stay below `.cache/p34-session/{quiesce,completed-prune}` with
existing contained USB environments and locks. No new OTA is part of cleanup.

The next useful input is a **fixed 921600/window-8 diagnostic on retained Y**,
not AA bootstrap or window 16. Host inspection found matching locked package
versions `flutter_blue_plus 1.35.5` / `flutter_blue_plus_android 4.0.5` in the
existing local package sources under `.cache/p3-3-t1b/fbp/`. Java defaults to DEBUG
and has method-entry, characteristic-write and notification callback log markers.
Its write-without-response callback is a local Android buffer event, not a
remote durable ACK. This is a source finding, not proof that current-device logs
are enabled or complete. No APK rebuild is justified before testing the existing
route's actual query-time markers.

Before the diagnostic transfer, extend the existing session entry with an
explicit window-8 diagnostic group and a bounded exact-PID native log collector;
keep Y/N04, the sender and existing legal Z bytes fixed. Preserve the old
`n04-window16` profile rather than changing its axes in place. Validate the live
collector on pre-start queries, then admit one zero-start transfer only with
recording space, fresh MCU identity and both readers ready. Pair serial native
method/write callbacks with the App's GATT samples, and compare notification
timing with ACK/credit gaps. Do not subtract unsynchronized epochs or equate a
local write callback with device confirmation. Missing markers require stopping
that observation route before DATA and deciding the smallest instrumentation
change, not another blind OTA. No new diagnostic group or physical transfer has
been created in this return batch yet.

Evidence is linked as E104-E106 in the progress table; E106 audits these new
read-only outputs and preserves the prior offline batch rather than rewriting
its point-in-time E103 audit.

## 2026-09-28 Offline Continuation: P34-INSTALL-03

### HOST-P34-PATCH-PREP-01: Remaining Offline Batch

The user requested completion of the remaining work that does not require the
phone/computer connection. This batch builds on E95-E97, not a new decoder
investigation. Planned outputs are `.cache/p34-patch-next/` plus the short,
project-local source/build roots `.cache/p34pc/f` and `.cache/p34pc/b`.

1. Verify the immutable N04 source/build and the actually completed Y identity.
   Copy that source lineage and overlay only `ota_patch.c` / `ota_patch.h` from
   the E95-tested implementation. Build the complete GCC App with the inherited
   N03/N04 flags plus `OTA_PATCH_COALESCE_WRITES=1`. This is explicitly App-only:
   do not rebuild Boot, the simulator, Y/Z or unrelated dirty working files.
2. Check the final ELF/MAP, linker assertions, 40 KiB overlay, 8 KiB stack/guard,
   remaining heap/Flash capacity and affected compiler stack reports. Derive new
   runtime bindings rather than reuse Y's addresses. Static checks are not
   runtime stack high-water or hardware admission.
3. Prepare local development images AA 30223 / `3.2.23-p34c` and AB 30224 /
   `3.2.24-p34c`, reserving the already frozen Z 30222 unchanged. AA contains the
   new receiving decoder; AB differs only in its standard firmware header.
   Prepare a normal FULL bootstrap from Y to AA, a compact AA-to-AB PATCH, and
   an exact 1 MiB AA-to-AB pressure PATCH. The two PATCH encodings are alternative
   inputs, not two sequential upgrades to the same version. Reuse the established
   legal non-minimal stream construction with a finite 128-compression search
   for this new image pair; never regenerate the old witness or pad an ETU.
4. Validate every new package through the real native decoder/Boot checker and
   host unpacker, including changed input/identity/integrity rejection cases.
   Reuse E95's unchanged decoder suite rather than rerun it. Complete PATCH
   installation-summary parsing, capture-capacity checks and a fail-closed
   handoff/finite observation plan. No service, USB/BLE/J-Link, App mutation,
   OTA, CI, commit/push, production release or independent acceptance runs here.

Physical order remains gated by P34-WAIT-01: retrieve the original Android
history first when the phone is available; absent evidence calls for a fixed
window-8 diagnostic, not changing the receiver/window to explain the old delay.
Preparation does not authorize skipping that diagnosis or activating AA/AB now.
Formal reference suitability and real timing/stability remain separate gates.

### HOST-P34-PATCH-PREP-01: Executed Offline Closeout

The currently defined phone-independent preparation is complete. No phone,
USB/BLE/J-Link, listener, tunnel, OTA, APK rebuild, CI, commit or push ran.
Y remains the last verified installed receiver. AA/AB are prepared, not installed;
Z and the previous evidence remain unchanged. This is implementation self-test,
not independent acceptance or completion of P3-4.

**Source and complete App build.** The frozen 3267-file N04/Y source lineage was
copied to `.cache/p34pc/f`, overlaying only `ota_patch.c` and `ota_patch.h`.
One complete GCC App-only build in `.cache/p34pc/b` enabled coalescing while
retaining N03/N04 flags. It produced 614604 bytes, 192 more than Y, with **638
warnings and zero errors**. Boot and the simulator were not rebuilt. The first
post-build verifier incorrectly expected overlay address `0x20048000`; the actual
frozen layout is `0x20058000`. Its failure and producer were preserved. Corrected
verification consumed the successful original build/logs without recompilation.

- Final overlay: 40960 bytes at `0x20058000`; stack: 8192 bytes at `0x20056000`;
  guard: 32 bytes at `0x20055fe0`. Heap-to-guard is 5144 bytes, or 4632 after the
  linker heap reserve. These are linker facts, not runtime stack peaks.
- `ota_patch_apply` own compiler frame is 720 bytes. The 336-byte N03 profile
  and public decoder ABI remain unchanged. Do not add mutually overlaid sections
  as if their storage were simultaneously live.
- All 638 warning diagnostics match N04 after normalizing source roots,
  separators and CMake's `D_` spelling of a drive root, preserving multiplicity.
  The first root-only comparison in `observation-r2/result.json` is preserved as
  false; the complete normalization is recorded in the final audit. Warnings
  remain warnings, including inherited `wchar_t` and vendor diagnostics.
- Source/build receipts: `.cache/p34-patch-next/firmware/{source,build}.json`.
  Original verifier failure: `firmware/failed-build.json`. The 19/19 affected
  layout/flag/FULL/PATCH parser checks in `tests/unit-r1/result.json` remain valid
  by their recorded function hashes; later driver changes did not rerun them.

**Fixed local development assets.** AA is 30223 / `3.2.23-p34c`, raw SHA-256
`a71d927b62d25ed989b214461a4c38be914b6f69289c74e0b328dceb61a8957e`.
AB is 30224 / `3.2.24-p34c`, raw SHA-256
`4aae2ab7ea9616359ec0c3764011800697a9b54038483e78ddfc1db0ec57c6ac`.
Both are 614604 bytes; only the standard header differs between AA and AB.

| Input | Complete ETU Bytes | Native Candidate Writes, Old / Coalesced | Purpose |
| --- | ---: | ---: | --- |
| Y to AA FULL | 291670 | FULL decoder: 633 | Normal bootstrap; Y, not AA, performs installation |
| AA to AB compact PATCH | 307 | 601 / 601 | Header-only functional smoke; not a representative update compression ratio |
| AA to AB pressure PATCH | 1048576 | 209773 / 601 | Exact legal non-minimal pressure input, not automatic formal reference admission |

The pressure search used 64 of its 128 encoding attempts, seed 1931, count
209376 and salt 15. It has progressing controls, exact LZMA consumption and no
padding/no-op tail. Both PATCH encodings decode to byte-identical AB in Python,
the original native decoder and the coalescing native decoder, with Boot/header
validation and workspace guards intact. Thirteen invalid-package cases reject
CRC damage, truncation, same version, and PATCH base version/SHA mismatch before
candidate preparation. Native source comparison binds original hashes and allows
only documented CRLF/LF equivalence; no original source or evidence was rewritten.

The pressure package still needs **209978 base reads and 4609 package reads** in
both modes, plus both decode passes. The 99.71% reduction in candidate writes is
not an installation-time estimate. Compact PATCH has no callback-count gain on
this particular header-only change. Neither result explains the prior FULL
transfer regression. Manifest: `.cache/p34-patch-next/assets/result.json`.
Package hashes are respectively:

    FULL:     2cf56f5a724183fe0daa6445a0c7133380bba103e0eb24452118eda12defeea7
    compact:  fc8d41ecb30ace240c2784ad691e9979dd4dfeb0d42ec399870e26f1cf0c1d11
    pressure: e8635f05ca3708679fa7108e36fb488f0d3b2cb8315c7512ef6e7bf0a9f71987

**Existing session integration.** `p34.bat prepare-patch --group patch-bootstrap`
is host-only and has prepared `.cache/p34-session/profile-patch-bootstrap.json`
from the actual completed Y descriptor. `patch-compact` and `patch-pressure`
profiles require an actual completed AA bootstrap; no such evidence or profile
was fabricated. All three groups use s04, 921600/window 8, complete transfer and
zero prefix. `transferMode=full` means complete transfer, independently of the
ETU's `kind=patch`. Old groups retain their old dependencies and axes.

The old fixture service accepted only FULL. A context-local adapter now reuses
its common metadata/file-hash validation on a private copy, then exposes the
exact bound PATCH kind/base. It does not modify that frozen module or old FULL
contexts. Wrong diagnostic receiver version/raw SHA fails before URL issuance;
token signing, expiry, Range and byte checks remain the original implementation.
The real state object was tested without opening a socket. Host HTTP admission
requires `-patch.etu`, the full raw base SHA and exact base version. Native
analysis now passes the explicit package kind and requires PATCH plus backup
summaries, rather than misclassifying them as missing FULL evidence.

The complete changed-session batch executed 236 tests. Its **209 existing cases
passed**, while the new PATCH cases exposed a discarded SHA field in the legacy
parser and an invalid test assumption that rebound Flash addresses must move.
The result at `.cache/p34-session/tests/1790577436378568500/` remains FAILED
(two subtest failures, two errors). The repair reads the already-validated query
pairs and tests the actual new image/MAP binding, not compulsory address movement.
Before-fix snapshots match the executed source hashes. The bounded reconciliation
proves that only `patch_service` and that new test method changed; all other AST
and input bytes are unchanged. **27/27 PATCH checks then passed**, zero
failures/errors/skips, reusing the 209 actual original PASS lines without another
full run. Evidence: `.cache/p34-patch-next/tests/patch-r2/result.json` and
`tests/reconcile-before.json`. The current test pointer binds this composite
self-test proof, not a fabricated 236-test rerun or independent acceptance.

**Observation preparation.** The existing APK and its actual source commit were
verified, with no build or download. A local Git blob was absent even though its
tree and checkout file existed. The first `observation/failed.json` is retained;
`observation-r2/result.json` reused the two successful original source reads and
verified the remaining file against its committed Git blob hash, without fetching.
Recorded limits are 64 MiB per capture, 1 MiB pending, 256 MiB total store and
eight directories. Scaling Y's original 1042565-byte/9330-record snapshot from
2278 to 8192 DATA segments estimates **3749207 bytes and 33552 records**, with 256
durable blocks. This is an estimate, not a queue, free-space or runtime guarantee.
The original service/native/active limits remain unchanged.

### Finite Physical Handoff After This Batch

1. When the phone is actually available, resolve `P34-WAIT-01` first through the
   prepared read-only original Android history route. No cleanup or new OTA is
   needed to try that retrieval. If history is gone, design the minimal fixed
   window-8 discriminating observation from that fact; do not skip diagnosis by
   installing AA or changing to window 16.
2. For the PATCH branch, require actual retained Y, matching APK, complete raw
   App/Boot identity, idle/CONFIRMED/SD/Flash admission and sufficient recording
   space. Last observed storage was 8/8; the exact phone-copy cleanup gate remains
   unresolved. This offline work grants no deletion, App-data clearing or reset.
3. Execute one ordinary Y-to-AA FULL bootstrap only after those gates pass.
   Preserve original App/native logs, final AA raw identity and original Boot.
   Its installation is performed by Y and is not a coalescer speed measurement.
4. Only actual completed AA permits `prepare-patch --group patch-compact` **or**
   `prepare-patch --group patch-pressure`. Pick one input before the cell. Both
   target AB, so they cannot run sequentially. An attempted alternative is latched
   without a successor or replay. Choosing Y-to-Z first similarly invalidates the
   existing Y-bound bootstrap profile; rebind from the actual retained state.
5. Capture download, full BEGIN-to-END ACK, GATT/ACK/durable/MCU counters,
   PATCH/backup restore summaries, Boot residency and final reconnect/raw identity
   separately. Retain existing 900 s active, 2700 s native and 3900 s cell bounds,
   maxRetries=5 and the 30 s no-durable-progress abort. Pressure installation cost
   and stack peak remain unknown; a collector deadline is not authority to reset,
   abort irreversible installation, repeat a successful upgrade or extend limits.
6. Missing summaries or mismatched identity remain evidence gaps/failures. Repair
   analysis from originals where possible. Reference suitability, production
   integration, repeatability, 9 KiB/s, P95/maximum time, 30/30, soak, reconnect and
   independent acceptance remain pending. No formal gate is lowered.

The next owner is Codex implementation, still the sole operator. Current source
changes and cache artifacts are local, not committed/pushed/mainline delivery.
The final audit is `.cache/p34-patch-next/closeout.json`; the progress table links
E98-E103. The first audit incorrectly treated the three declared mutable progress
documents in E97's broad file inventory as frozen outputs. Its producer/failure
are retained in `audit/`; reconciliation excludes only those declared documents
and still verifies every original evidence record and all other prior files.
Do not rerun source preparation, the successful build, fixed asset
generation, observation preparation or unchanged tests simply on continuation.

### Earlier Decoder-Only Batch (E95-E97)

Owner: Codex root, sole operator; original card ownership unchanged. The user
cannot connect the phone to the computer and requested phone-independent work.
No USB, BLE, J-Link, OTA, phone cleanup, firmware installation or CI is planned
in this batch. Y remains the last verified image; Z is unrun and immutable.
P34-WAIT-01 is still unresolved and window-16 physical screening remains paused.

### Evidence And Bounded Candidate

The original 1 MiB PATCH witness at
`.cache/p3-4-size-check-20260920/cases/reference-1MiB.etu` has SHA-256
`131624717d5972039ee76847d4a410fc21edebf9a5b4730d37b9dfe2ab04573e`.
The exact identity must be checked against the original witness before use. Its
603764-byte target required 212679 candidate-program callbacks. The real
`ota_patch.c` currently writes each short diff/extra piece immediately, even
when adjacent control groups produce contiguous output. This is an observed
operation-count hotspot, not a measured duration or the cause of the FULL
X-to-Y transmission regression.

Implement `OTA_PATCH_COALESCE_WRITES`, default 0, in the portable PATCH decoder.
Reuse its existing 1024-byte `work` buffer across diff, extra and control-group
boundaries; add only conditional buffered/programmed counters, not another
buffer. Flush full buffers through the existing program-plus-immediate-readback
path. Flush a partial tail only after successful control and stream completion.
Check continuity and overflow-safe bounds; propagate every error without a
cleanup flush. Keep public I/O/info structs, the 40 KiB workspace ceiling,
base identity, two-pass LZMA checks, CRC/SHA, backup, marker-last, rollback and
BLE durable semantics unchanged. Do not enable the candidate in a device build.

### Host Verification Plan

- Compile the real decoder with the existing golden/vendor/rejection suite in
  both default-off and enabled modes. The vendor case must retain six writes
  by default and produce four when enabled, with identical target bytes.
- Add public-API cases for diff/extra/control boundaries, full buffers and
  partial tails, base-window edges, malformed/truncated streams, first/full/tail
  write and readback failures, no flush after failure, and workspace guards.
- Reuse the immutable original 1 MiB package/base/target with new binaries and
  new evidence under `.cache/p34-session/patch-coalesce/`; never overwrite or
  regenerate the original witness. Measure the program count and workspace
  rather than infer performance from source. The expected enabled count is
  `ceil(603764/1024) = 590`, not an executed result yet.
- All compiler/test/temp/home/AppData/cache outputs stay under a fresh guarded
  project-local run. Preserve failed runs. Reuse unrelated 209-test, APK, N03,
  checked-restore and physical evidence without rerunning them.

The witness is a non-minimal pressure representation for 30204-to-30205, not a
current-Y upgrade asset. Host success will not establish actual seconds saved,
current-device 1 MiB admission, throughput, stability or independent acceptance.

### Compiler-Only Follow-Through

The first host batch passed. Reuse the existing GCC `ota_patch.c` recipe from
`MDK-ARM_F435/cmake-generated/build-gcc-release/compile_commands.json`, replacing
only the output and adding the opt-in define for the second mode. Compile only
this translation unit and an ABI-size probe into a fresh `arm-r1` directory.
Preserve the original object, build tree, Y/Z assets and the completed host run.
This checks target compilation, private/public type sizes and compiler stack
reports, not final linking, installed RAM usage, runtime stack peaks or timing.

### Executed Result And Evidence

The candidate is implemented and host-validated, still default-off. No new
phone/MCU operations, firmware links, APKs, device-ready upgrade assets, CI,
commits or pushes were produced. Host-only ETU fixtures were generated solely
inside this batch's output root. The original witness and all X/Y/Z evidence remain inputs,
not rewritten outputs. P34-WAIT-01 and the paused window-16 ordering are unchanged.

| Measurement | Default off | Coalescing enabled |
| --- | ---: | ---: |
| Same complete ETU bytes | 1048576 | 1048576 |
| Byte-identical target bytes | 603764 | 603764 |
| Candidate-program callbacks | 212679 | 590 |
| Maximum callback bytes | 1024 | 1024 |
| Base-read callbacks | 212886 | 212886 |
| Package-read callbacks | 4609 | 4609 |
| Host workspace peak bytes | 34136 | 34144 |
| ARM private state size bytes | 7584 | 7592 |
| ARM public I/O / info size bytes | 32 / 88 | 32 / 88 |
| Compiler-reported `ota_patch_apply` own-frame bytes | 712 | 720 |

The program-call reduction is **99.72258662115206%** on this pressure witness,
not an installation-time reduction. The two LZMA passes and the 212886 base
reads remain; actual QSPI/page operations and seconds are not measured here.
The stack rows describe one compiler-reported frame, not a complete call-chain
bound or runtime stack measurement. No new 1 KiB buffer was allocated.

Original executed evidence:

- `.cache/p34-session/patch-coalesce/r1/result.json`: `HOST_PASS`, 12 test groups,
  0 failures/errors/skips, 53.260 s reported by unittest. This includes 84 focused
  public-API positive/rejection/fault cases, two deliberately broken coalescers
  rejected by the runtime oracle, the original 167-check suite in each mode,
  exact-capacity/one-byte-short checks in each mode, and the original 1 MiB
  witness through the real decoder plus the unmodified full Boot validator.
  Ten native host compilations, zero compiler warnings/errors; all 67 bound
  input files unchanged. Result SHA-256:
  `2abb2ceaa7e0a89c2840bf2731d3b263303652c784a26c35026e6996c37a1e3e`.
- `.cache/p34-session/patch-coalesce/arm-r1/result.json`: `ARM_OBJECT_PASS`, four
  object-only compilations using the recorded GCC recipe, two symbol reads and
  two section-size reads, zero compiler warnings/errors. The original production
  object/build recipe and all bound inputs are unchanged. Result SHA-256:
  `0cfa264597e760ea07407f61db4b336037b3829ec7e7ddab4c45bcac324df9f1`.
- `.cache/p34-session/patch-coalesce/closeout.json`: final source/output/original
  evidence audit. This batch does not replace E89-E94 or their original failures.

The executed host command was:

```cmd
C:\Users\SU\AppData\Local\Programs\Python\Python313\python.exe -I -S -B -X utf8 tests\ota\test_ota_patch_coalesce.py --root D:\github\my\E-Track --out D:\github\my\E-Track\.cache\p34-session\patch-coalesce\r1 --witness-dir D:\github\my\E-Track\.cache\p3-4-size-check-20260920
```

Do not rerun into `r1` or `arm-r1`; the runners refuse existing output roots.
Only changed dependencies or a new planned comparison justify a new run.
The compiler-only command was isolated Python on
`.cache/p34-session/patch-coalesce/arm-check.py`; its exact compiler commands,
source binding, `.o` and `.su` outputs are retained in `arm-r1`.

### Validation And Failure Semantics

`ota_patch_apply(io, device, package_len, out_info)` and both public structs are
unchanged. A build must explicitly define `OTA_PATCH_COALESCE_WRITES=1` to select
the candidate; other values than 0/1 fail preprocessing. Both diff and extra
paths append to the unused part of `work`; `verify` remains a separate buffer.

| Case | Required and observed behavior |
| --- | --- |
| Vendor oldpos-only / multiple control groups | Same target; default six writes, enabled four |
| Diff, extra, control and 1024-byte boundaries | Continuous bounded writes; each write immediately read back |
| First, full or tail program failure | `candidate_write`; no later storage callback or cleanup flush |
| Readback error or byte mismatch | `candidate_verify`; no later storage callback or success metadata |
| Base/second-pass package read failure | `read`; pending bytes discarded, workspace wiped and released |
| Invalid control, seek overflow or unconsumed control | `patch_control`; pending partial tail never flushed |
| Truncated, trailing or excessive decoded stream | Rejected before candidate preparation |
| Final CRC / firmware-header / target-version mismatch | Rejected after synthesis, no successful image metadata |
| Exact workspace capacity / one byte short | Success / `workspace` before candidate erase or write |
| Broken short-flush / dropped-tail implementations | Native behavioral oracle rejects both |

Wrong: flush each control fragment, flush pending bytes during error cleanup,
or replace readback with a successful program return. Correct: validate exact
stream/control completion before the final partial flush, then run unchanged
CRC and Boot-header checks. The FULL decoder, receive staging, BLE credit,
backup, STAGED and rollback call chains were not edited.

Next owner remains Codex implementation for development work. Keep this
candidate separate while P34-WAIT-01 needs Android/native evidence. Before
enabling it on a device, bind a new receiving build to the retained Y lineage,
verify the final MCU memory/stack layout, prepare matching legal PATCH assets
and a finite observation plan, and measure installation phases plus final
reboot/raw identity. The old 30204-to-30205 witness cannot be sent to Y. Product
integration/publication and independent acceptance remain pending.

## 2026-09-27 Continuation: P34-INSTALL-02

Owner: Codex root, sole operator; original P3-4 card ownership unchanged.
The sections dated September 25 below are historical. W 30219 is now installed
and verified; the phone/power prerequisites described there are no longer the
current blocker. This remains implementation/development work, not acceptance.

### Evidence And Hypothesis

Reuse the original U/W measurements rather than repeat an upgrade for logs.
W's transfer took 58.164197 s and installation/reconnect took 62.951594 s.
Its `BLEACT` apply/stage values are 16306/13784 receiver tick milliseconds,
not calibrated wall time; Boot VTOR residency is 22.776099--24.858343 s, not
pure Flash copy time. The original full-image/Boot/CONFIRMED proof is separate
from the missing trace-internal final confirmation sample.

`HAL_OTA_Package.cpp` restores XIP after candidate writes and backup erases/
writes. `en25qh128a_qspi_xip_init()` always writes SR1=0/SR2=2, including the
nonvolatile status-write busy wait. The real decoder produces hundreds of
candidate writes (W: 628). This is a plausible fixed per-call cost, not yet a
measured N04 root cause or a promised speedup. Candidate/backup XIP reads are
not the old N03 staging readback path.

### Bounded Implementation And Verification

1. Add an opt-in installation-only checked restore. For the boot-verified
   `0xEF4018` chip, safely reset, read SR1 (0x05) and SR2 (0x35), and skip the
   status rewrite only for exactly SR1=0/SR2=2. Other chips and mismatched
   status use the unchanged full initializer; reset/read errors fail closed.
   Short reads wait for CMDSTS then drain the exact byte count, never RXFIFORDY.
2. Leave each apply/backup entry on full initialization. Only subsequent
   installation restores opt in. Startup, N03 staging, Boot, decoder chunk
   size, immediate readback, CRC/SHA, backup, marker-last and rollback remain
   unchanged. The production default stays off until physical validation.
3. Gate phase-level diagnostic summaries separately. Count legacy/reused
   restores, failures and invalid cycle samples, and sum bounded per-restore
   DWT deltas with 64-bit carry. Do not subtract a single 32-bit counter across
   an entire apply phase or change the frozen 336-byte N03 profile ABI.
4. Compile the actual driver/HAL functions against a recording host model.
   Cover exact/missing QE, all mismatched status bits, other chip identities,
   reset/read/write/busy failure, short-read completion, the default-off path
   and timing wrap/invalid-counter behavior. Preserve failed results and use
   fresh contained output folders. Reuse the unchanged 173-test session result.
5. Build only a new App from a new copy of the frozen N03 source lineage,
   overlaying the reviewed N04 delta. Never modify old snapshots or generators.
   Rebind the new ELF/MAP/RTT/layout and verify finalized package decoding before
   opening another device window. No APK rebuild or Boot replacement is planned.

### Next Physical Matrix, Not Yet Started

Prepare two legal sequential targets X and Y after W. W-to-X bootstraps the new
App but is still received/applied by W, so it cannot prove the new installation
path. X-to-Y exercises N04; Y retains the same new executable with a legal
successor header. Use the existing APK, 921600/window 8, zero-start FULL packages,
one planned upgrade per cell and original App/native observations. This is a
sequential diagnostic group, not a strict byte-identical package A/B.

Before mutation, freeze actual versions/hashes and receiver-specific bindings,
extend the existing session entry with explicit W/X predecessor checks, and
prepare observers, extraction and cleanup with their existing finite deadlines.
Do not delete the completed-W pointer or replay U/V/W. Unknown state, integrity
failure, nonzero MCU errors/retries or invalid measurement stops dependent work;
collect original evidence and verify the retained target before any next cell.
Missing logs alone never justify another successful OTA.

The prior V-stop/U-delete grants are consumed. They do not permit stopping the
current W App or deleting another phone recording. Request only the exact new
permission actually needed after host preparation. No device action, candidate
version reservation or new package generation is claimed by this plan.

All controllable writes stay in `D:/github/my/E-Track`, with new host/build
outputs under `.cache/p34-session/n04`. No commit/push, release, external output,
BCB editing, Boot flashing, app-data clearing or automatic UI taps are included.

### Executed Host Result And Current Gate

The implementation/host portion above is now complete. W is still installed.
There has been no W-to-X or X-to-Y transfer, no new MCU attachment, no Boot
replacement, no APK rebuild/reinstall, no CI or Git publication.

| Evidence | Result |
| --- | --- |
| `.cache/p34-session/n04/host-r3/result.json` | 10/10 host tests, no skips; four optimization/profile combinations, all 65,536 SR1/SR2 pairs, reset/read/FIFO/busy failures, HAL error propagation and timing wrap/invalid-counter tests |
| `.cache/p34-session/n04/firmware/source.json` | 3,267 files copied from the source-bound N03 lineage, exactly the three declared product overlays; old source trees untouched |
| `.cache/p34-session/n04/firmware/build.json` | Original GCC configure/build/size/nm all exit 0; 638 warnings, 0 errors; App 614412 B, +832 B versus W; no Boot build |
| `.cache/p34-session/n04/assets/x/result.json` | X 30220 / 3.2.20-p34i, package 291425 B, host-verified |
| `.cache/p34-session/n04/assets/y/result.json` | Y 30221 / 3.2.21-p34i, package 291494 B, same executable as X, host-verified |
| `.cache/p34-session/tests/1790523037400706900/result.json` | 196/196 session regressions, 0 failures/errors/skips, 0 device operations; 23 new N04 checks |
| `.cache/p34-session/completed-prune/1790523326257184100/result.json` | V phone recording archived read-only and byte-identical to the original completed snapshot; 8/8 slots, 0 phone mutations; USB stop/server/launcher exit 0, port closed |

Both packages pass the existing Python unpacker and native full decoder/Boot
header oracle, including byte-exact target comparison, workspace guards/lifecycle
and four invalid-package gates before preparation. Each invokes 632 candidate
programs with a maximum write of 1024 B. These remain host counts, not seconds.
The N03 profile is still schema 2 / 336 B. Session member layout is reused only
because its source/type inputs are unchanged; each runtime object's address,
the new image/ELF/MAP, RTT signature expectations and Flash gate are rebound.

The root production flags are off. Only this new App build enables both
`CONFIG_OTA_INSTALL_QE_REUSE=1` and `CONFIG_OTA_INSTALL_PROFILE=1`. The
614412-byte raw build and finalized X/Y bytes are different artifacts; use their
respective recorded hashes. X raw-image SHA-256 is
`6909cdd0a100f89503dab039576d1c8dc50c63a360d07bbbca2d4038e6f52064`,
Y is `ab5bddfc7ab7b35f7d6a4896232c97f7b4d52c4ae92caad5e1fa7cec14bb48d0`.
X package SHA-256 is
`00019bbab3dde6cd7af4ccf905f972ac2fee86f8eaff75a129b5bba8c2a0d87c`,
Y is `37e70190bf11c148035c7740c25e558f41edf1b54671ce8f2e20e6662f62c41c`.

### Executable Interface And Observation

The low-level signature is:

    qspi_status_t qspi_xip_restore_checked(uint32_t verified_jedec_id, bool *reused_qe)

`reused_qe` is optional, initialized false, and true only after successful
XIP enable without status programming. It is not a cached permission to reuse
the next call. Every eligible call resets with the existing recovery delay and
freshly reads both status bytes. All other chips/configurations retain the old
initializer; reset/read errors propagate without enabling XIP.

The installation HAL's `qspi_restore_xip(bool allow_reuse = true)` is the only
production opt-in caller. Full/patch/backup entry passes false. Candidate prepare/
program and backup erase/program retain their original validation/error behavior
and may use checked restore afterwards. Startup and N03 staging do not opt in.

The separate, gated RTT summary has this exact field order:

    P34INSTALL: phase=full|backup rc=INT opt=UINT hz=UINT calls=UINT reused=UINT fail=UINT invalid=UINT ticks=UINT legacy=HI:LO reuse=HI:LO max=UINT

`legacy` / `reuse` are 64-bit sums of successful bounded per-call CYCCNT
deltas, emitted as two uint32 words. `ticks` remains receiver millis, not wall
time. The existing native trace captures these original RTT bytes; no frozen
N03 profile field is repurposed. The consumer requires complete full/backup
lines, the target-bound BLEACT marker, the admitted clock, zero failure/invalid
counts and consistent totals. Identical duplicate lines are deduplicated;
conflicts, truncation, invalid counts and clock disagreement remain EVIDENCE_GAP.
All-fallback data may be a valid observation but is not a reuse/speed benefit.

| Case | Required behavior |
| --- | --- |
| EF4018, exact 0/2 status | No status write; normal XIP configuration enabled; later full data readback remains |
| Other chip or mismatched status | Original full initialization, no assumed SR2 equivalence or QE-only mask |
| Reset/read/status-program/busy failure | Original error propagates; no successful-reuse flag |
| Counter wrap within a short call | Unsigned per-call delta, then 64-bit accumulation |
| Disabled/changed/stalled clock, failed or over-bound call | Invalid count increases; no fabricated cycle time |
| New App with relinked symbols | Recompute installed-context Flash addresses from its MAP, even when the BLE profile size is unchanged |
| Successful OTA with incomplete timing | Retain/reconcile its original result; no replay merely to fill the log |

Wrong: use a 32-bit subtraction over the entire 16-second apply phase, wait for
RXFIFORDY on a one-byte status read, or keep W's addresses after installing X.
Correct: measure each bounded restore, wait CMDSTS then drain one byte, and bind
the newly linked target's exact MAP/ELF before opening the post-install reader.

### Preserved Host Failures

`host-r1` preserves the fixture's enum-comparison compile errors. It did not
execute product paths and is not a passed negative test. `host-r2` preserves
one native process startup exit `0xffffffff`; GDB observed no startup stack.
The byte-identical executable at a new evidence path passed all 65,536 pairs
(`diagnostic-r2/renamed.json`). The exact underlying host cause is unknown;
it is not attributed to firmware or the user. Descriptive executable names are
used by the passing `host-r3` route; other original results are not rewritten.

The GCC build itself succeeded once. Its first post-build symbol parser failed
to match CRLF nm lines and incorrectly reported `N03 profile ABI changed`.
`failed-build.json` and all original command output remain. The corrected
`selected_symbols` uses complete split lines; the host test covers both original
CRLF and normalized LF and rejects duplicate symbols. `reconcile` consumed the
same successful build/size/nm records, rechecked the source and artifacts, and
created `build.json` without another compiler invocation. Do not rerun either
the build or this completed reconciliation.

### Finite Device Continuation

`p34.bat prepare-install` has frozen both packages and
`.cache/p34-session/profile-n04-bootstrap.json`, whose predecessor is original
completed W. On a subsequently completed X it binds the already-frozen Y package
to the real X descriptor and writes `profile-n04-measure.json`. That execution
profile does not exist yet; host fixtures are not X installation evidence.

Both new cells remain NOT_RUN. The current stop condition is the 8/8 phone
recording store plus missing new idle-App-stop/record-deletion permission.
The progress board lists the exact V/W app-relative directories. V is freshly
archived; W stays protected until X completes and must then be archived/checked
again before any permitted deletion. Keep all host originals, phone R and other
records. This note requests no blanket app-data clearing or arbitrary PID stop.
No new service is live, and the old W endpoint must not be reopened.

New outputs are confined to `.cache/p34-session/n04`, the named host-test run
and the named read-only V archive. Final selected-output/source/owner audit:
`.cache/p34-session/n04/closeout.json`. Everything is local and uncommitted;
the original card owner and formal 1 MiB/repeat/soak/acceptance requirements remain.

### September 28 Authorization And Continuation

The user explicitly answered "allow" to the exact idle-App/recording request
above and asked the sole operator to continue P3-4 proactively. This supersedes
the September 27 permission-pending statements, not their historical receipts.
The authorized sequence is: verify and quiesce the completed idle W App, then
archive/recheck and remove only V's phone recording; after X succeeds with full
target/unchanged Boot/idle/CONFIRMED proof, verify and quiesce idle X, then
archive/recheck and remove only W's phone recording. Keep the current protected
recording, phone R and other records, and all host originals. Derive exact remote
paths from the original completed run/query via `prune-completed`, never from a
hand-copied suffix. Record any uncertain mutation before continuing.

Reuse the frozen X/Y assets and the 10/196 passing host results without rebuilds
or unchanged reruns. First execute W quiesce and V cleanup, then explicit
`n04-bootstrap/s04` with `profile-n04-bootstrap.json`. Bind `n04-measure` only
after X actually completes. Required in-App connect/download/Start actions
remain with the user, with both collectors and the actual verified HTTPS route
prepared first. No automatic UI taps, Boot replacement, arbitrary BCB writes,
App-data clearing, Git publication or new external filesystem scope is implied.
The sole default writable root remains `D:/github/my/E-Track`; the exact existing
J-Link history exception remains unchanged. At this entry no new device mutation
has occurred and W's old observation/network owners are CLOSED.

### September 28 Executed Cleanup

- `quiesce --run 20260927T141330-27800 --cell s04`: APP_QUIESCED,
  exact PID 14476/configuration/original completed snapshot verified, process
  absence checked twice, configuration retained; 24.1102 s.
  Receipt: `.cache/p34-session/quiesce/1790525285971464500/result.json`.
- `prune-completed --run 20260927T130601-85100 --cell s04 --apply`:
  COMPLETED_CAPTURE_PRUNED, re-archived original V snapshot byte-identical,
  only its derived directory removed, all seven other directories unchanged;
  21.1 s. Receipt:
  `.cache/p34-session/completed-prune/1790525321016466800/result.json`.
- Both private USB receipts show stop/server/launcher exit 0, port closed and
  the read-only ADB key unchanged. All host originals and phone W/R remain.
- Explicit `start --group n04-bootstrap --profile
  .cache/p34-session/profile-n04-bootstrap.json --cell s04` created run
  `20260927T160919-23000`; network preparation is in progress. No DATA or X
  installation is established by this preparation entry.

### September 28 Live X Admission

Run `20260927T160919-23000/s04` reached READY_FOR_FULL_INSTALL_START at
2026-09-27 16:12:39 UTC (September 28 00:12:39 Beijing). The before-checkpoint
verified complete W and unchanged Boot, idle/CONFIRMED, SD/clock/Flash admission.
The new HTTPS origin and actual phone download match the frozen X package,
291425 B. Original evidence is `cells/s04/mcu/closure.json`,
`cells/s04/mcu/receiver-admission.json`, `cells/s04/queries/result.json` and
`cells/s04/queries/package.etu` under that run. The original diagnostic APK
launched as PID 25984, capture `1790525527314706-832f67cf9bb33036d6f7a279`.

The user was invited to tap Start once and keep the App foreground. Both
observers and the verified temporary service remain deliberately live within
their existing deadlines; the App-start wait ends around 00:37 Beijing. Query
`status` on this exact run before continuation. Readiness is not DATA, installed
X, N04 speed benefit or a reason to create another run. Do not stop an active
transfer to fit a spent setup window. The 10/196 host tests and fixed assets
were reused, not rerun or regenerated.

### September 28 X Completed, Y Preparation

X completed normally in `20260927T160919-23000/s04`. Original analysis:
`analysis/1790526076589424400/result.json` in that run. Transfer 53.658056 s,
291425 B, 2277 DATA, zero retries/MCU errors; installation/reconnect 62.950062 s.
Full X/unchanged Boot, SD ready, idle/CONFIRMED and the new MAP-derived Flash
admission passed. Candidate/backup BLEACT ticks were 16214/13786; Boot VTOR
residency was 22.4363867--24.7391479 s, not pure copy time. The missing final
trace-internal confirmation sample remains a gap; separate full identity/state
readback proves completion. This old-W-installed bootstrap is not N04 benefit.
Cell/network owners closed normally at 16:21:32 / 16:22:19 UTC.

`prepare-install` then bound already-frozen Y to X's actual completed descriptor
in `.cache/p34-session/profile-n04-measure.json`; no package regeneration, test
rerun or device operation. Authorized exact X quiesce succeeded (PID 25984,
configuration preserved) at `quiesce/1790526219160579400/result.json` under
`.cache/p34-session/`. W was re-archived and byte-compared, then only its phone
copy was removed at `completed-prune/1790526290167723200/result.json`; all seven
other records, including current X and R, remain. Both USB scopes closed.

Explicit `n04-measure/s04` created `20260927T162548-11400`. DNS initially returned
11001 and resolved at the existing 150-second retry; first HTTPS check passed.
The observation-side recheck encountered 530 and is in its existing bounded
retry, before any Y App launch or DATA. Do not recreate this attempted run or
replay X to repair a service issue. Preserve its original readiness failures.

### September 28 Y Completed And Measured Result

Y completed in `20260927T162548-11400/s04`; original analysis is
`analysis/1790527302778574900/result.json`. Full Y/unchanged Boot, SD ready,
idle/CONFIRMED and receiver admission passed. Cell/network owners closed
normally at 16:42:04 / 16:42:50 UTC. Y App PID 11230 remains unstopped. The
original DNS/530 readiness failures recovered within the existing schedule;
they are not transfer failures and are not erased. No successful OTA was replayed.

| Observable | X bootstrap, old W installer | Y measurement, new X installer |
| --- | ---: | ---: |
| Package bytes | 291425 | 291494 |
| Transfer seconds | 53.658056 | 70.363044 |
| DATA / retransmissions | 2277 / 0 | 2278 / 0 |
| Installation/reconnect seconds | 62.950062 | 49.657590 |
| Combined seconds | 116.608118 | 120.020634 |
| GATT call duration sum, seconds | 19.922598 | 25.300668 |
| Platform write sum, nested in GATT, seconds | 19.408682 | 24.802507 |
| ACK P99, milliseconds | 242.137 | 430.766 |
| MCU pump work, seconds | 9.339392 | 9.440300 |
| Payload verify, seconds | 0.710864 | 0.711065 |

Installation/reconnect is 13.292472 s / 21.1159% shorter in this single sequential
comparison. Transfer is 16.704988 s / 31.1323% longer; the combined interval is
3.412516 s / 2.9265% longer, not an end-to-end improvement. Both have zero retries,
clean MCU counters, one discovery, MTU payload 244 and without-response writes.
The native staging work is nearly unchanged. GATT/ACK tails increased; the cause
is not established. Do not subtract overlapping GATT, ACK and MCU clocks to claim
exclusive shares or attribute the entire installation difference to one function.
No pause/terminal interruption lies inside the successful Y transfer; the
pre-BEGIN DEVICE_LINK_CHANGED/query retirement remains in the original log.

The strict N04 profile verifier found full/backup summaries in original trace
evidence: calls 634/309, reused 633/308, legacy 1/1, failures 0/0, invalid 0/0.
Legacy DWT cycles are 2719305/2722901; reuse sums are 19907458/9739580 at the
admitted 288000000 Hz. These are bounded per-restore sums, not whole-phase time.
Summary ticks 84/48 also cover restore calls only. BLEACT candidate/backup phase
ticks are separately 10434/10970; Boot residency is 22.8947777--24.9083712 s,
not pure copy time. The trace-internal final confirmation gap remains; separate
full target/state readback proves success. Production defaults remain off.

GATT sums were computed offline from only `OTA_LINK_SAMPLE label=upgrade`
records in each bound `analysis/ID/observations.log`, with exact counts 2280/2281
matched to the original summary. Query, late-query and reconnect writes are
excluded. The shell pipeline uses `rg -o
OTA_LINK_SAMPLE.label=upgrade.kind=gatt_write.us=[0-9]+ LOG | rg -o [0-9]+`
(and `platform_write`) before summing microseconds. No new device I/O occurred.

### September 28 Offline Transfer-Wait Diagnosis

This is read-only reuse of the original X/Y App logs, not a new device run or
an unchanged test rerun. Derived result and original log size/SHA-256 bindings:
`.cache/p34-session/n04-window16/xy-durable-analysis.json` (progress board E89).
The original logs and earlier audit receipts remain unchanged.

Each log has one successful `upgrade` summary and 73 increasing durable
notifications: offset zero, 71 complete 4096-byte blocks, and one final partial
block. Compare successive notifications only within their own App stopwatch.
These intervals contain sending, staging and ACK handling, not isolated Flash
time. The last partial blocks differ (609/678 bytes) and are excluded from the
aligned complete-block statistics. Percentiles use nearest rank.

| App observation | X bootstrap | Y measurement |
| --- | ---: | ---: |
| BEGIN to final durable notification, seconds | 53.479719 | 70.184565 |
| Final durable notification to END ACK, seconds | 0.178337 | 0.178479 |
| Complete-block interval median, seconds | 0.761855 | 0.986993 |
| Complete-block interval P95, seconds | 0.850922 | 1.306824 |

Y is slower at 61 of the 71 complete-block offsets. Their total difference is
16.720131 seconds; the five largest positive differences total only 3.037872
seconds. Difference by successive block bands 1-16 / 17-32 / 33-48 / 49-64 /
65-71 is +0.444947 / +2.744056 / +5.479269 / +5.720519 / +2.331340 seconds.
This is broad degradation with larger later-band differences, not just a few
isolated stalls. The final-durable-to-END difference is only 0.000142 seconds:
the added receive time is not installation/reconnect included by mistake.

The frozen source comparison leaves `Libraries/Bluetooth`, `Libraries/OTA`,
`HAL_Bluetooth.cpp` and `HAL_OTA_Staging.cpp` unchanged. N04 adds the checked
QSPI restore and installation HAL profiling; the old staging initializer is
unchanged. The APK and link settings were identical. However W and X are not
the same complete binary, and these are different legal packages. This does
not rule out indirect receiver effects or establish radio/phone scheduling as
the cause. Do not infer a root cause from unchanged source or phase totals.

For the already-prepared window-16 cell, inspect whether the later-block
degradation improves alongside GATT/ACK timing and clean MCU/retry counters.
Use all applicable window-8 observations, not only slow Y as a baseline. A
clean faster sample is a screening candidate, not final selection or stability
proof. If no clear gain or the same late degradation remains, stop blind baud
changes and narrow the next diagnosis to App write/window waits versus receiver
scheduling. No extra successful OTA is authorized merely to collect logs.
Keep installation measurements separate. Y retention, the pending exact phone
recording cleanup boundary, and Z NOT_RUN are unchanged.

### September 28 Causal Diagnosis Takes Priority

The user explicitly asked to investigate the increased transfer time before
moving on. Pause the physical ordering of P34-LINK-16; preserve all prepared
Z assets and profiles. Window enlargement is a screening axis, not evidence
explaining the prior regression.

Next bounded operation: one read-only historical Android log retrieval for
the already-bound phone 10ADA4197U001CK, user 0, exact unchanged diagnostic APK,
and original X/Y PIDs 25984/11230. Reuse the existing private ADB/Windows Job
and filesystem guards; sole operator remains Codex. Output stays under
`.cache/p34-session/n04-window16/android-history-01`, with the existing project
device lock. Per-command deadlines and one 150-second command budget apply;
the reused USB owner's maximum is 600 seconds and it closes immediately after
the fixed reads. No App stop/start, recording deletion, logcat clear, BLE
connect/disconnect, MCU attachment, package mutation or new OTA is included.

Read buffer metadata and tag/PID-filtered logs only. Missing, rotated or
unbound old events remain an evidence gap. Current connection parameters are
not substituted for the original transfer. The previous exact cleanup request
remains pending and is not needed for this read-only retrieval. No new phone
observation slot is created.

The first historical-reader attempt closed after the immediate `get-state`
reported the exact phone absent; no identity or logcat command ran. Its original
receipt is preserved under `android-history-01`. The adapter omitted the
project's known asynchronous ADB enumeration wait. Reuse the unchanged tested
`wait_online` function from `prefix_usb_ready.py` through a separate source-bound
adapter, with one fresh `android-history-02` USB scope. A 20-second bounded
absence or unauthorized device stops this route; do not repeatedly reopen it.

### Executed Wait Decomposition And USB Gate

`P34-WAIT-01`, NEED_EVIDENCE. Derived original-log result:
`.cache/p34-session/n04-window16/xy-wait-analysis.json`. The adjacent
`xy-wait-analysis.py` is a read-only, source/hash-bound reproducer, not a device
runner. Seven model checks cover free/full credit, shared ACKs, invalid timing,
overfull windows and nearest-rank statistics. Six checks verify the USB adapter's
use of the existing bounded enumeration wait. Receipts are in
`xy-wait-validation.json`; the unchanged 209-test suite was not rerun.

Each DATA segment is paired with exactly one original GATT/platform call using
ordering and payload+14 frame length. The three non-DATA calls are excluded.
First-send end plus its ACK latency reconstructs the App confirmation time.
If eight prior same-block segments remain outstanding after a send, the first
following confirmation estimates when credit becomes available. Subtracting
the next GATT duration from the next logged send end leaves a continuation
residual, not a directly observed native write-start timestamp. No negative
intervals are accepted. All 2277/2278 sends and ACK samples are covered; the
2230/2249 reconstructed ACK groups equal the original OK ACK counts.

| App-side partition, seconds | X | Y | Difference |
| --- | ---: | ---: | ---: |
| DATA GATT call duration | 19.839831 | 25.260317 | +5.420486 |
| Estimated full-window credit wait | 17.144176 | 25.570917 | +8.426741 |
| Last send in each block to durable notification | 15.373334 | 18.194608 | +2.821274 |
| Post-credit continuation residual | 0.820373 | 0.844465 | +0.024092 |
| First-send preparation residual | 0.142453 | 0.131344 | -0.011109 |
| BEGIN to zero-durable notification | 0.159552 | 0.182914 | +0.023362 |
| Final durable notification to END ACK | 0.178337 | 0.178479 | +0.000142 |
| Sum | 53.658056 | 70.363044 | +16.704988 |

This is a partition of observable App elapsed time, not isolated physical cost
for each layer. Platform call time is nested in GATT. ACK latency sums and MCU
cycles are not added. Same-block post-credit residual P99 is 1.233/1.196 ms;
there is no large accumulated delay after credit is visible to the App. Native
aggregate pump average spacing is 88.702731/83.227164 ms, maximum
186.128583/187.212514 ms; pump work is 9.339392/9.440300 seconds and ACK-write
call totals 0.427056/0.428088 seconds. These do not support a broad MCU work or
average pump slowdown, but cannot rule out per-packet scheduling/phase effects.

The remaining distinction is Android native write/callback/notification queue,
Bluetooth connection/radio/module delay, versus per-packet receiver scheduling.
Do not label the remaining uncertainty as proven radio noise or assume the
installation change is harmless merely because receive sources match.

The corrected historical reader's `android-history-02` stopped after its
20-second readiness window: nine checks all reported the exact phone absent.
No identity, package, logcat or BLE command reached the target. Both USB attempts
closed normally (stop/server/launcher 0, port 5062 closed, read-only ADB key
unchanged); both failure originals and sources remain. Phone recording cleanup
permission is unrelated to this read-only path. The next required action is to
connect/unlock the exact phone, then retrieve still-retained original PID/tag
logs using a fresh declared output. Never reuse an attempted directory or rerun
the successful OTA to reconstruct history. If native history is unavailable,
design a minimal fixed-window-8 diagnostic before any window-16 screening.

Window 16 remains physically deferred; Z, the current pointer, Y, original
Boot and all frozen packages/observations remain unchanged. No firmware/APK
build, CI, source integration, publication or independent acceptance occurred.

### P34-LINK-16: Next Finite Host Preparation

Owner: same sole Codex implementation session. Prepare one explicit Y-to-Z
zero-start FULL cell at 921600/window 16, preserving the already-installed N04
executable, unchanged Boot, APK/MTU/write mode, retry/integrity rules and both
observers. Z is planned as 30222 / 3.2.22-p34i, header-only versus Y, with its own
immutable legal package. This is a new sequential input group, not a same-package
A/B, not a repeat of Y, and not an entry in the historical 30214 S03 matrix.

The rationale is the new 70.36-second window-8 sample, increased GATT/ACK tails
and unchanged staging work. Window 16 is a discriminating unmeasured setting;
do not treat it as selected or infer 1 MiB/9 KiB/s acceptance. Also retain the new
installer's summaries to observe repeatability during the planned useful transfer.
Stop dependent operations on integrity/clock/counter failures or uncertain state;
missing collectors do not authorize replay. No additional repeat/soak batch is
silently added here. Root product firmware and APK are not rebuilt or modified.

Extend only the existing session/asset entry and affected host regressions.
Keep X/Y and earlier executed generator snapshots/bytes immutable. Old groups
must not acquire the future Z asset dependency. Bind the new profile only to the
actual completed Y descriptor. Fix the historical W cleanup unit fixture to use
its explicit W pointer, not today's device pointer; no real pointer is rewritten.
Outputs remain under `.cache/p34-session/n04-window16`, the explicit new profile
and fresh host-test directories. All device owners are closed before source edits.
Preparing a group does not grant another phone capture deletion or stop; resolve
the recording slot under the applicable exact authority before opening a window.

### P34-LINK-16 Host Result And Remaining Gate

Z is frozen at `.cache/p34-session/n04-window16/assets/result.json`:
30222 / 3.2.22-p34i, 614412-byte target, raw SHA-256
`3b9ea8e9eaa4c47e7523053172eb9c94bc2b72bb44c76da8d7d188219920046d`;
291526-byte package SHA-256
`b146f66958c4bc65bb9869da1ae0a9b3f5237d8c74284a17022d324ce54d6cdb`.
Python/native decoding, byte-exact target/Boot-header checks and all four invalid
package gates passed. The real native decoder counted 634 candidate writes,
maximum 1024 B. X/Y bodies and earlier generator snapshots are unchanged.

The final 209/209 host suite passed with zero failures/errors/skips/device I/O:
`.cache/p34-session/tests/1790529686907407300/result.json`, unittest 349.078 s,
whole command 378.8466 s. Added cases cover Y/Z identity and unchanged body/MAP/
Boot, exact window-16 configuration, original Y predecessor, old-group dependency
isolation, immutable package reuse, X-only cleanup selection, idle-PID races,
missing Y timing, no replay/successor, and host-timeout evidence/old-PASS retention.

Preserve both earlier host timeouts: the 180-second run
`tests/1790528616715899400/timeout-note.md` has no complete test count; the
300-second run `tests/1790529092813664500/timeout.json` retains 198 `ok` lines and
an unfinished cleanup-selection case, not an overall PASS. All paths here are
under `.cache/p34-session/`. The old StringIO logging lost partial output at the
first timeout; current logging flushes each line. Rejecting a clearly wrong
cleanup target from the current read-only plan avoids needless full-chain work;
eligible targets still undergo the complete proof and descriptor recheck.
The final host cap is 600 seconds. No device timeout or criterion was relaxed.

Read-only X archival after the successful suite:
`.cache/p34-session/completed-prune/1790530145775269600/result.json`, 55.815 s,
8/8 directories, zero phone mutations, full original snapshot byte-identical.
USB stop/server/launcher exit 0, port closed, ADB key unchanged. Y App was not
stopped and X was not deleted. Its exact canonical App directory is listed in
the progress board. The existing V/W deletion grants are consumed; the root has
asked to explicitly bound subsequent previous-record cleanup to this diagnostic
App's observations directory, preserving current/R and all host originals.
Until that boundary is confirmed, no Z service, App launch or OTA is started.

Prepared next commands are the board's exact Y quiesce, original X
`prune-completed --apply`, then `start --group n04-window16 --profile
.cache/p34-session/profile-n04-window16.json --cell s04`. Do not rerun host tests
or repackage Z merely for continuation. Output/source/owner audit is separate at
`.cache/p34-session/n04-window16/continuation-audit.json`; the old host-only
N04 closeout is not rewritten. P3-4 and formal 1 MiB/repeat/soak/acceptance remain
in progress, with source integration and Git publication still not claimed.

## Historical September 25 Work

Owner: Codex root, 2026-09-25. Development self-test, not independent acceptance.
The user cannot currently connect the phone to the PC and requested useful
P3-4 work without that dependency. No phone, BLE, J-Link, reset, deployment,
firmware-package generation or CI operation was performed in this batch.

## Result And Scope

`P34-INSTALL-01`: the actual portable full-package, backup, Boot state-machine
and confirmation-commit implementations now have one connected host I/O census.
Thirteen native scenarios passed 304 checks. Fifteen Python consumer/boundary
tests passed. Host GCC compilation reported zero warnings and zero errors under
`-Wall -Wextra -Werror`.

This is executed C code with injected in-memory NOR/EEPROM ports, not a static
estimate. It identifies work to measure; it does not measure physical duration,
UART/BLE throughput, QSPI timing, startup health or phone rediscovery. N04 phase
timing and speed benefits remain NOT_RUN. N02's four physical cells remain
NOT_RUN. There is no new installed 30215 firmware.

Production sources were not changed. The original recovery probe, helper
sources, fixed packages/nonces, APK and failed evidence remain unchanged. The
new test/tool sources and this note are uncommitted; no main/development push,
merge or release occurred.

## Fixed Inputs

The driver reads the existing `.cache/p34-next/assets/result.json`, verifies
each selected file's byte length and SHA-256, and passes the original files as
read-only inputs. Fault injection changes only the native process's RAM copies.

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `screen.etu` | 290773 | `cdf57ec392dea39157e4bede4d004dbdf396fa3c4b0016efe448367a260affb1` |
| Retained 30214 image | 613344 | `17d52849ec32719c748cb3475fd3d522da2762e29add905e56dc93ac63159242` |
| Expected 30215 image | 613344 | `df5f3f45e8b2668ff2b71939c372c7e83f4fbba7382ce4bb5f8e06754a9bf379` |

The native executable compiles the current root's `ota_package.c`,
`ota_backup.c`, `boot_state_machine.c` and their real crypto/header/BCB
dependencies. It does not execute the installed Boot binary or recreate the
device's current persistent state. Source/header and host-executable hashes are
recorded in the result. Candidate erase policy is explicitly modeled after the
source-bound `HAL_OTA_Package.cpp`; this HAL and the AT32/QSPI/I2C drivers are
not executed by the host model.

## Normal-Path Census

Original result:
`.cache/p34-next/install-workload/run-001/results/normal-0.json`.
Counts below are successful port operations, not physical bus transactions.

| Phase | Reads | Erases | Programs / Commits |
| --- | --- | --- | --- |
| Candidate generation | Package: 1208 calls / 581482 B; candidate: 3022 / 1226784 B | Candidate: 151 x 4 KiB, modeled HAL policy | Candidate: 625 calls / 613344 B |
| Backup and STAGED | Candidate: 9591 / 2453648 B; backup: 5995 / 1840200 B; current App: 2548 / 1226792 B | Backup: 151 x 4 KiB; candidate header: 1 x 4 KiB | Backup: 152 / 613376 B; candidate header: 2 / 32 B; BCB: 1 / 64 B |
| Boot apply | Candidate: 9740 / 3066992 B; internal App: 7196 / 1841296 B; EEPROM: 767 / 49088 B | Internal App: 150 x 4 KiB | Internal App: 150 / 614400 B; BCB: 153 / 9792 B |
| Confirmation commit only | EEPROM: 7 / 448 B | None | BCB: 1 / 64 B |

The final 4 KiB internal block contains padding; target image length is still
613344, not 614400. A successful modeled Boot return must be TEST_BOOT with the
entire target byte-identical. Only then does the harness call the real
confirmation helper. This models the commit, not the actual App health gate.

The 153 Boot BCB writes include 150 verified-copy checkpoints plus transitions
to APPLYING, TEST_BOOT and the decremented boot-attempt state. EEPROM page
splitting, ACK polling and physical write-cycle delays are below this model.

The backup phase writes 154 NOR port calls in total, including both slot
headers. Do not label all 154 as backup-payload writes.

## Diagnostic Direction

`P34-INSTALL-01` is DECIDED for the next measurement scope, not for a production
optimization:

- Measure candidate erase, decode/program and validation separately around
  `HAL::OTA_PackageApplyStaging`, `candidate_prepare`, `candidate_program` and
  the package decoder. The 625 program calls each traverse the current HAL's
  XIP disable/restore path; its physical cost is still unknown.
- Measure backup erase/copy/validation and the STAGED commit independently.
  Preserve marker-last, readback and the unknown-commit classification. The
  candidate header's re-erase is intentional retry safety, not removable merely
  because an earlier erase exists.
- Measure Boot external validation, internal erase/program/verify and EEPROM
  checkpoint costs. Keep the 4 KiB durable-resume rule until an explicitly
  evaluated alternative preserves crash recovery. No Boot change was made or
  authorized by this host diagnostic.
- Measure actual App readiness and phone identity verification in their own
  clock domains. The historical 63.561774 s App interval cannot be apportioned
  using this host census or PC wall time.

Do not multiply these read counts by the old N03 small-read latency: current
candidate/backup App reads use XIP `memcpy`, whereas the previous staging
readback observation came from a different QSPI path. Likewise, an operation
count is not an explanation of how many seconds it consumes.

Owner/next: Codex root prepares actual phase instrumentation only with a
validated advancing clock and a separately bound receiving firmware. Include
N04 measurements in a planned full upgrade, not an extra successful upgrade
just for collection. N03 remains the separately host-tested receive-side
candidate; this diagnostic does not install or validate its physical benefit.

## Validation Matrix

| Scenario | Executed Oracle |
| --- | --- |
| Normal | Decoder produces the exact fixed target; backup equals retained App; Boot returns verified TEST_BOOT; confirmation helper commits target version |
| Corrupt package payload | Real payload CRC rejection before candidate erase/program; no Boot execution |
| Corrupt candidate before backup | Header/image validation rejects it; no backup erase or BCB write |
| Backup write returns corrupted bytes | Immediate readback failure; BCB remains CONFIRMED; current App unchanged |
| BCB changes to TEST_BOOT before backup | Stage gate rejects with no backup erase or BCB write |
| Cut before checkpoint write, blocks 1/75/150 | Persisted resume stays at 0/74/149; re-entry completes the exact target |
| Cut after checkpoint write, blocks 1/75/150 | Persisted resume is 1/75/150; re-entry completes the exact target |
| Corrupt persisted App prefix after cut at 75 | Bad target is not accepted; the state machine restores the exact retained backup and CONFIRMED state |
| Corrupt committed candidate before Boot | State machine restores the retained backup, not a falsely successful new target |

Cuts use `setjmp`/`longjmp` at the EEPROM port before or after a complete BCB
write. They are modeled loss of control flow, not a physical power-loss test or
a test of every partially programmed EEPROM byte. No injected failure is
silently counted as a speed sample.

The Python tests reject missing checks, success hiding a negative phase code,
missing/uncalled phases with I/O, invalid counts, absent payload or confirmation
writes, wrong inputs/final identity, and promotion to hardware timing. They
also check finite/deduplicated cut positions, binding tampering, existing-output
refusal and project-sibling output rejection before any mkdir.

## Commands And Evidence

Entry points, from the explicit project root with isolated Python:

```text
python -I -S -B -X utf8 tests/ota/test_install_workload.py --root D:/github/my/E-Track --out .cache/p34-next/install-workload/python-tests-r1
python -I -S -B -X utf8 Tools/ota/install_workload.py --root D:/github/my/E-Track --assets .cache/p34-next/assets/result.json --out .cache/p34-next/install-workload/run-001
```

These paths already contain the successful results. Do not replay them or
rerun unchanged inputs just to refresh a timestamp. Use a fresh project-local
output only when sources/inputs or a justified check changes.

- `.cache/p34-next/install-workload/python-tests-r1/result.json`: 15 tests,
  zero failures/errors/skips; original unittest log beside it.
- `.cache/p34-next/install-workload/run-001/result.json`: 13 scenarios,
  304 native checks, source/input preservation, compiler identity, commands,
  raw logs and per-phase results. `HOST_MODEL_PASS` never means hardware PASS.
- Each phase records `ran`, `interrupted`, `result_code` and resource/op
  `calls`/`bytes`. Unexecuted/interrupted results are null, not zero-success.
  BCB assertions use out-of-census reads so validation does not inflate counts.
- Compile/native subprocesses have 120-second bounds and propagate failures;
  failed runs retain intent, raw output and a failed result rather than being
  overwritten. The candidate `.etu` and image inputs are never regenerated.

All selectable outputs, GCC temporary files and child home/cache directories
are under `.cache/p34-next/install-workload`. The existing project path guard
is reused. No PowerShell host, external output/cleanup, private ADB server or
native debugger was launched. The previous network normal-closure EVIDENCE_GAP
is unchanged and no missing receipt was manufactured.

## Remaining Physical Gates

Phone USB is currently unavailable. Acknowledgment of the earlier complete
E-Track power cycle is still missing. Keep the existing `after-power` probe
unused until that action is confirmed; it does not itself need the phone.
QSPI whitelist/disable state, advancing DWT, SD, full App/Boot identity and
idle/CONFIRMED admission must be reconciled before any physical performance
cell. The older network URLs remain unusable.

The new offline files do not change the previous product or helper bindings.
Only the already-allowed board/plan documents were updated. Source-pin checks
must still run when resuming hardware work; this note is not a waiver.
