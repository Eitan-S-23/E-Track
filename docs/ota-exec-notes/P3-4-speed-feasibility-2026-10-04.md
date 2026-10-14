# OTA Speed Feasibility: Evidence Before Another Device Trial

## Decision

Owner: Codex root. Status: offline investigation completed, proposals NOT implemented.
Scope: D:/github/my/E-Track; no phone, BLE, J-Link, CI, deployment or firmware
operations in this investigation. Retained device remains verified30275.
The existing operational journal is P3-4-fixed-signing-2026-10-01.md.

There is no demonstrated50 decimal KB/s /20s general-update solution. There is
now a concrete installation candidate: reduce Boot copy-progress EEPROM commit
frequency, not another SHA or reconnect timeout tweak. Transport needs a measured
increase in sustained link service AND reduced block stalls. Double buffering
alone does not close the measured budget and violates the current v1 window if
implemented as cross-block prefetch without a negotiated protocol revision.

Do not start another OTA merely to obtain a new end-to-end number. The gates and
minimum observations below must discriminate a hypothesis first.

## Reproducible Evidence

Run from the project root using isolated Python and a fresh project-local output:

    python -I -S -B -X utf8 Tools/ota/p34_speed_feasibility.py --out .cache/p34-feasibility/analysis-next.json
    python -I -S -B -X utf8 tests/ota/test_p34_speed_feasibility.py .cache/p34-feasibility/tests-next

Executed outputs: .cache/p34-feasibility/analysis.json and tests/result.json.
Six tests passed, including partial-image uncertainty, changed bytes, grouped
commit counts, arithmetic and invalid input. These are analysis tests, not
performance or hardware acceptance. Original reports and captures were not edited.

The analyzer reuses strict original snapshot/closed-report checks and checks
image lineage, native trace digest and the installed Boot source digest.
It does not invent erased bytes beyond a raw image's recorded length.

| Role | Upgrade | Public transfer / KB/s | END to identity | Boot residency, host-clock bounds |
| --- | --- | --- | --- | --- |
| Control, header-only |30272->30273|17.487465s /16.790999|20.438290s|5.876218..9.164306s|
| Bootstrap, changed executable |30273->30274|16.821642s /17.456203|36.426757s|22.465650..24.787154s|
| Candidate, header-only |30274->30275|16.740038s /17.542732|20.361587s|6.719949..8.836719s|

Source anchors: each trial's analysis/latest.json and report, exact snapshots,
native-trace/result.json and installed-mcu/closure.json. Paths/digests are in
analysis.json. Native Boot residency is observed VTOR residence, not an internal
Flash timer. The initialized/CONFIRMED sampling gap is retained; final identity
and confirmation come from the separate full readback. Do not subtract these
host timestamps from App stopwatch timestamps or add overlapping native phases.

Public OTA_MONO duration16.740038s and diagnostic partition16.736466s have
different instrumented boundaries. Counterfactuals below use only the latter's
internally closed partition, not a mixture of the two.

## Transport: What Is And Is Not Known

Latest App diagnostic partition for293666B:

| Component | Time | Meaning |
| --- | ---: | --- |
| DATA GATT calls |10.203518s|Platform9.944115s is nested, not additional|
| Last chunk to durable confirmation |5.753145s|Includes path/queue/processing/notification latency, NOT just Flash|
| Other disjoint diagnostic spans |0.779803s|Before-last nonwrite plus BEGIN/END boundaries|
| Total diagnostic partition |16.736466s|~17.55KB/s on this boundary|
|50KB/s budget|5.873320s|Whole legal compressed package, not decompressed size|

Counterfactuals hold all unnamed costs fixed; they are neither forecasts nor
physical capacity bounds:

| Hypothetical change | Remaining time | Resulting arithmetic rate |
| --- | ---: | ---: |
| Remove ALL durable tail |10.983321s|26.74KB/s|
| Halve GATT time only |11.634707s|25.24KB/s|
| Halve GATT AND remove ALL tail |5.881562s|49.93KB/s|

Consequently neither an isolated wait reduction nor an assumed2x sender boost
is an adequate50KB/s plan. Halving connection interval is NOT evidence that
GATT duration halves. Changed scheduling may also change all these partitions.

Existing full HCI observation is30272->30273, not a new30275 HCI measurement:
.cache/p34-timed-ack/hci-measure-001/{result,queue,tail}.json. It shows actual
bidirectional2M, DLE251,15ms during DATA, no mid-DATA parameter change. MTU247
gives244B ATT value capacity. To deliver50KB/s with the latest DATA framing
(325796 wire bytes /293666 package bytes), roughly55.47KB/s DATA value traffic
is needed before other overhead: at15ms this is at least3.41 full244B DATA values
per connection interval on average. This is a demand calculation, NOT an
observation of packets per radio event; HCI completions cannot measure that.

In that HCI trace, feeding spans9.985125s include9.039436s with reported
outstanding DATA and0.945689s without. Completion reporting lag prevents
equating this to radio utilization or buffer fullness. It does not support
blaming the entire10s on Flutter round-trips. Native batch submission remains
a hypothesis, not a justified production rewrite.

The same trace has6.264057s durable tail:1.139760s at four64KiB payload boundaries,
5.055024s at67 ordinary full blocks,0.069273s final partial. Controller reports
split the total into1.570982s before and4.693075s after; neither is isolated
Flash cost. Native program/erase costs overlap this pipeline and cannot simply
be subtracted to assign the remainder to the module.

### LINK-03: Required Evidence Before Changing The Sender

Preferred next discriminating route: obtain the exact module firmware identity
and its supported connection/event-length/UART packetization controls, then use
an isolated sustained transport benchmark without automatic firmware activation.
This benchmark has NOT been implemented or authorized as a device action here.
It must use a separate non-activation service/command or vendor test firmware;
never send garbage through the current OTA END/apply path or call it OTA success.

Keep the same phone and compare the current pacing against one bounded native
queue implementation, with per-chunk callbacks, finite queue/backpressure,
connection-generation cancellation and receive byte/CRC counts. Separately
compare the existing BLE module against a known-capable peripheral only if such
hardware is explicitly provided/approved. Outcomes:

- Native queue raises sustained received rate above the required~55.5KB/s DATA
  value budget: pursue sender integration plus block-wait reduction. Raw rate
  alone is not50KB/s OTA; budget for journal/ACK/control traffic and margin.
- Host has queued work but confirmed receive rate stays below demand: do not
  write a larger Flutter queue; investigate module/event scheduling or hardware.
- Both endpoints meet raw demand but OTA remains slow: prioritize block pipeline
  and persistence instrumentation, not baud/PHY claims.

Missing: exact module firmware-specific supported controls and over-air/receiver
service timing. The prior manual review identifies AT+AINTVL as advertising,
NOT connection interval; no valid7.5ms-control command was established. No new
vendor source was obtained here. Do not invent AT commands or treat Android's
high-priority request as a guaranteed negotiated interval.

## Pipeline Feasibility And Safety

Contract docs/ota-binary-contracts.md:331-335 explicitly defines the credit window
as the CURRENT4KiB block. ACK bitmap describes the durable_off block, and the
window advances only after payload readback and journal update. Firmware
Libraries/OTA/ota_staging.c::ota_staging_receive rejects offsets at or beyond
durable_off+4096; commit_current_block is synchronous before the ACK is produced
by ota_ble_session.c::session_handle_data. These paths are present in the
source manifest used to build30275. The root Flutter source has the analogous
blockEnd guard, but that dirty root source is NOT substituted for the installed
APK's exact source. Original wire traces independently confirm block stop/wait.

A true two-block pipeline requires all of:

- A negotiated new receive-credit/accepted-offset representation distinct from
  persistent durable_off, with exact block/sequence association and v1 fallback.
- Two owned4KiB buffers with explicit FREE/FILLING/COMMITTING state, not reuse
  of the buffer being programmed. ISR byte queue is not a second staging buffer.
- Cooperative/asynchronous Flash operations so the foreground parser can make
  progress. Current QSPI waits poll synchronously and XIP is unavailable during
  operations; adding RAM alone does not create concurrency. Audit ISR/code/data
  placement and prevent LVGL or other clients accessing unavailable mapped QSPI.
- Ordered full readback and bitmap/journal persistence before durable advances.
  On disconnect/power loss, volatile accepted data can be lost and must resume
  from persistent state; no fake100% progress or END until all blocks commit.

Memory appears worth prototyping, not proven: current BLE phase uses a4096B RX
ring plus a receiver containing one4096B block within the40KiB exclusive overlay.
Another4096B may fit this phase. PACKAGE/LIVE_MAP are mutually exclusive, so
full-install LZMA peak must not be added as concurrent BLE use. However alignment,
metadata, actual sizeof on ARM, XIP-safe code and lifetime transitions must be
checked against the exact map and overlay allocator, not the general heap.

Minimum host prototype: fake Flash scheduler; one pending block plus one filling
block; randomized fragments/early ACKs/duplicates/credit shrink/cancellation;
error or power cut at every erase/program/readback/journal boundary; assert
durable is a contiguous verified persistent prefix and buffers never alias.
Reject old-peer cross-block traffic. Integrate the sender and receiver models
before any firmware build. This needs protocol/contract review; no frozen
contract or production code has been changed here.

Priority: AFTER raw-link service is shown adequate. Even ideal elimination of
all measured tail reaches only26.74KB/s with current feeding time.

Lower-scope alternative: pipeline WITHIN the existing4KiB block. Erase its
uncommitted destination early and program a256B page after both128B segments
arrive, while retaining the complete RAM block for duplicate checks/readback.
Keep durable unchanged until all pages and the journal commit verify. This can
preserve v1 credit/bitmap semantics, but still needs bounded Flash scheduling,
per-page state and interruption tests; it is not enabled by changing the sender
window. It overlaps only eligible persistence work, not all module/ACK latency,
and has no measured savings here. It is a potential incremental17KB/s improvement,
not a sufficient50KB/s proposal. Assess it only against a measured phase budget.

## Installation: Concrete Candidate, Not A Reconnect Guess

Installed Boot is the whole65536B image with SHA
a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4.
Its preparation/candidate CMake cache enables P34_BOOT_SKIP_IDENTICAL_BLOCKS.
The recorded boot/src/boot_state_machine.c source SHA
f4808a78c5f55ed4980f90f538cc7191ef88a09eed1e5678f354627c21a90d97 still matches.
Do NOT analyze Boot using the unrelated copied App-build Boot source, which
does not contain this installed optimization.

Known-byte4096B image comparisons:

| Workload | Different blocks | Fully known identical blocks | Unknown final padding |
| --- | ---: | ---: | ---: |
| Header-only control |1|149|1|
| Changed executable bootstrap |146|5|0|
| Header-only SHA measure |1|149|1|

This explains why changed-executable and header-only samples cannot be pooled
as a speedup proof. It does not give per-block erase/program times. In the
changed-executable sample, Boot residence alone has a22.465650s observed lower
bound, already beyond the20s total objective. An App reconnect-only change
cannot remove that Boot work. For other future images, costs remain workload
dependent; this is not a universal hardware lower bound.

### BOOT-CP-01: Group Copy-Progress Checkpoints

Exact code entry: boot_state_machine.c::copy_source:417-451 skips erase/program
for equal blocks but still calls commit_record after EVERY verified block.
commit_record invokes eeprom_bcb.c::bcb_commit:233-300, writing the complete64B
inactive record, readback and arbitration. Contract section3.3 uses eight8B
EEPROM pages with ACK polling. Existing tests explicitly require every resume
commit, including identical blocks (test_boot_state_machine.c:484,1120).

Proposed host-only first candidate: compile-time default-off APPLY checkpoint
group size16; retain the default every-block behavior and conservative ROLLBACK
behavior initially. Keep a volatile verified frontier separate from persisted
resume_block. Flush at each group boundary and final block before final image
validation / TEST_BOOT. Never batch STAGED->APPLYING, rollback entry, boot-try
consumption or confirmation state transitions.

For this151-block image, copy-progress transactions would fall151->10 (141 fewer,
~93.4% reduction). At the contract's nominal~5ms/page, the avoided page-write
cycle time is141*8*5ms =~5.64s. This is a nominal engineering estimate, NOT measured
savings or a20s promise: ACK-poll durations, arbitration/I2C costs and other
installation work remain unmeasured separately. Header-only Boot6.7..8.8s is
consistent with this being material, but does not establish attribution.

Safety tradeoff: a power cut can leave up to16 verified blocks beyond the last
persisted frontier; resume must revalidate/reprocess at most64KiB, never claim
unverified bytes. Confirm every intermediate persistent record remains valid
under existing A/B seq arbitration, including write failure after a physically
successful EEPROM transaction. A corrupt source cannot be used for replay.

Minimum verification before hardware:

1. Extend existing Boot state-machine tests for group1/4/16 and151-block inputs,
   with1, mixed and146 changed blocks. Compare final full bytes, validation,
   Boot-try semantics and transaction counts to unchanged behavior.
2. Inject power loss at every block and every8B page of checkpoint writes,
   including final flush, plus read failure/seq wrap/rollback/source replacement.
   Assert no bad image boot, persistent frontier never ahead of readback,
   bounded rework and complete eventual recovery. Do not merely delete existing
   every-block assertions to make new behavior pass.
3. Validate whether grouped frontier semantics require a successor contract;
   update affected acceptance inputs prospectively, not historical bundles.
4. Only after tests/review: obtain specific Boot replacement/recovery authority
   and prepare the exact known-good full Boot backup. Current analysis grants
   none. One discriminating observation should count/time EEPROM commits,
   internal Flash and Boot phases, rather than repeat a generic App-only OTA.

This is the first implementation candidate to evaluate for installation. It
does NOT guarantee20s for the146-changed-block case: even removing5.64 nominal
seconds leaves substantial Boot and pre-Boot work. Keep header-only and real
changed-executable acceptance separate.

## Next Action And Stop Rules

Preferred next implementation work is the offline BOOT-CP-01 recovery model,
in parallel in concept (not delegated agents here) with resolving LINK-03 module
capabilities. No more SHA/ACK micro-tuning or automatic APK installs.

No device window until there is a passing host model, explicit compatibility
decision, expected discriminator and complete observation route. Failed raw
link capacity screening blocks a50KB/s double-buffer implementation claim.
Failed checkpoint recovery tests reject batching regardless of estimated speed.
If Boot modification or protocol revision is needed, present its exact scope
for approval before changing or deploying it. No vendor/hardware capacity claim
may be inferred merely from nominal2M PHY.
