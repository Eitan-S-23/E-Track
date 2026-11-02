# P3-5 v5 Independent Offline Acceptance

Overall PASS: all 18 required criteria are independently EXECUTED PASS from one
admitted offline command; 22 original-evidence checks pass. EXECUTED refers to
the evaluation, not new hardware. P35-IR-01 and the formal packaging finding
P35-IR-02 are closed for this task boundary. Main integration, P5 endurance and
production release are not authorized or claimed by this result.

## Identity And Scope

- Frozen evaluator: 54a860d122afba3c7361e0b77a50c29905f37ad2.
- Freeze tree: bfef1d0169f09c58a268f39bd1ad7be3f7d473ea.
- App source: d717e6a04fefa538a363f07cfe344c7935dcc384; actual APK version 97,
  SHA256 f37c3282cd6420672d766b1761bd84f68fd29297248069a74a0bdb9fea78e1f8.
- Firmware source: 18f6b3d3af0c24b1ce81573700cd61005b7c530e.
- Original acquisition source: ff59986aae202b6e234c6f108c75ce16781abac6.
- Original observations: 2026-11-02 implementation-owned App/ACK, native,
  protected test-backend, CI and passive MCU originals, independently reviewed
  by the original non-implementer /root. The packet keeps their exact command,
  source, date, ownership, interruption and recovery records.

The original 30307-to-30309 group has ten genuine OFF/ON link losses and fresh
MCU resumes in the unchanged R01-R10 windows. Its original R01 actual cut is
4096, not zero. The separate 30313 supplement supplies initial BEGIN seq 291,
actual disconnect 318, fresh resumed BEGIN 376 and first DATA 379, all zero.
Its complete 5306-record original exactly equals the acknowledged stream.
No new point is spliced into the original group. Positive committed and tail
positions, process recovery, HOME/background progression and the 600-second
locked observation retain their separate captures and original boundaries.

Final full App readback for 30313 is
4126d801e6bd6efd57a9f20d5a128a50cfb5a46580dc10d9a2227702247d5805.
It matches CI and fresh post-reboot identity; physical Boot, confirmation,
advancing health/storage journal, NO_UPDATE and terminal resource cleanup
match the dated originals. This is not a newly sampled current device state.

## Evidence And Failures

The ordered packet parts reconstruct the existing 137752729-byte ZIP with SHA256
092f38cca6cf92ed3096e23f39914d411fed860b0adde2e84fb7fede7c629640.
It contains 11015 original path references and 6786 SHA-256 objects. The evaluator
reads exact bytes directly from ZIP, without extraction, executing archived
scripts, reading former machine-private caches or opening a network/device.
Original source comparisons use read-only Git objects from the preserved history.

v1-v3 and earlier failed physical/host observations remain unchanged. The failed
30312 point still resumes at 8192; the original 30313 partial download and its
same-artifact range recovery remain explicit. Auxiliary Logcat is incomplete,
not a substitute for the complete primary App/acknowledged stream. All five
reviewed firmware builds report 641 warnings and zero errors each. No
continuously transferring ten-minute or multi-cycle endurance claim is made.

Adapter self-test initially caught two preparation defects: a leftover old
module reference and an incorrect assumed 30308 initial version. Originals prove
30307. Both were repaired before the initial runner freeze; original failed
smoke output remains in the predecessor preparation archive.

v4 reached frozen NOT_RUN precheck but its evaluator failed before parsing the
originals: the caller's lowercase predecessor SHA differed from the canonical
CLI plan's uppercase representation. v4 is honestly EVIDENCE_GAP due to the
harness-origin missing result, not PRODUCT_FAIL or PASS. Its exact stderr,
closed receipt, frozen contract and failed matrix were committed as
25cb4a5ec35e498e0fec5b0c7dd671c15d0a98a5 before the source repair.

v5 uses the canonical validator loader; a new regression reproduces the saved
plan exactly. Thirteen host test methods pass. It takes the actual v4 failed
matrix as predecessor, with an automatically computed rerun plan and no REUSED
claims. All 18 criterion IDs, gates and original numerical windows are retained.
The only newly executed formal command is the offline evaluation; no product,
CI, radio, installation, reset, flash or cloud operation was repeated.

## Revalidation And Delivery

At the registered bundle commit, run the standard validator against
P3-5-v5.contract.json and P3-5-v5/evidence-matrix.json, supplying
P3-5-v5/history/v4/contract.json and history/v4/matrix.json as the actual previous
pair. Do not rerun the evaluation command against an already-final matrix.
The freeze source commit alone does not contain the later evidence bundle.

The evidence commit and the later FREEZE-INDEX/task-record commit are separate.
This local task branch remains pending main integration; no push/merge or release
is included. Original raw whitespace is preserved, with staged Git blob bytes
checked exactly instead of formatting historical logs to pass whitespace lint.
