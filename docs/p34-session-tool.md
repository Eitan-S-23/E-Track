# P3-4 Session Tool

The repeatable local entry is `p34.bat` at the project root. It uses isolated
Python and explicit project cwd; no PowerShell, local Flutter build, CI rerun,
APK reinstall, package regeneration or firmware installation is implicit.

## Commands

### ACK-Gap Diagnostic Candidate

Scope: `ack-gap-bootstrap` introduces the isolated1ms UART ACK-gap candidate
through one FULL30230-to-30232 OTA. It reuses the full session observer, not
the repeated-payload browser diagnostic. It is not a throughput acceptance run.

Signatures: `p34_ack_gap_assets.load()` verifies the host package/source/MAP
manifest; `load_for_context(c, specification)` requires exact30230 bindings.
`p34.bat prepare-patch --group ack-gap-bootstrap` prepares the immutable profile;
`p34.bat start --group ack-gap-bootstrap --cell s04 --profile
.cache/p34-session/profile-ack-gap-bootstrap.json` performs fresh admission.
Preparation never installs. The profile requires `ack_gap=true`, QUIC,
`native_diagnostic=false`,921600/window32 and complete predecessor evidence.

Readiness also retries a bare socket `TimeoutError` within the existing four
offsets; metadata/byte mismatches and unclassified errors still stop immediately.
`recover-network --run FAILED_RUN --cell s04` supports the ACK-gap network-only
read-timeout case only when there is no device cell, owners are closed, QUIC
registered, both origin requests returned200, and the final HTTPS event records
TimeoutError. It preserves the failed run and links the new profile while
restoring only the completed predecessor's host pointer. It cannot recover an
attempted OTA. Tests cover missing response evidence, cell presence, wrong error,
old HTTP2-to-QUIC behavior and bounded read-timeout retries.

| Validation | Oracle |
| --- | --- |
| Wrong source, package, MAP, version or negative decode proof | Reject before device access |
| No complete30230 predecessor or open/uncertain owner | No profile/start |
| Existing attempted cell | Preserve original result; no implicit replay |
| Successful bootstrap | Full30232 raw identity, original Boot, ordinary confirmation and original App recording |
| Historical receive/PATCH groups | Their dependencies do not include future ACK-gap assets |
| Forward30233 baseline package | Prepared recovery asset only; not an admitted automatic install |

Tests include exact context/service/collector binding, old-family isolation,
wrong profile flags and delayed serial ACK ordering. The gap primitive is tested
for transmit-drain timeout, idle-before-gap, zero gap and wrapping cycle count.
Wrong: treat DATA-register-empty as the final stop bit or disable RX interrupts.
Correct: wait for transmit-complete, then a bounded diagnostic DWT gap with RX
interrupts enabled. Firmware validation is separate from the sender/tool tests.

After verified bootstrap, `python -I -S -B -X utf8 Tools/ota/p34_gap_screen.py
test|prepare|start|status` is the separate browser-screen entry. Run each command
separately from the explicit project root. `worker` is supervisor-only. Outputs
are write-once under `.cache/p34ag/screen`; `start` cannot reuse a spent cell.
The entry pins the completed30232 report, full App/original Boot, normal owner
closure, confirmed idle921600 state, new MAP/sampler and flash-gate addresses.
It prepares a header-only30234 successor, verified by the existing native full
decoder, but sends no END. One142-byte/window4 repeated-payload trial measures
ACK integrity; it must ABORT with zero durable/payload mutation and retain30232.
The browser requires the human Bluetooth chooser and Run Link Screen action.
No extra system bugreport, automatic UI tap or firmware installation is included.

Host tests reject old30230 identity, changed Boot, missing confirmation, busy
state, wrong retained rate and live/forced predecessor owners, plus the existing
sender/CRC/ABORT checks. Correct: admit new30232 bindings and a newer legal header.
Wrong: replay the30230-bound capacity context or call repeated payload OTA speed.

`p34_gap_burst.py test|start|status` is the follow-up only after a clean, normally
closed window4 screen. It reuses that package and gap receiver, with window31
and142/244-byte chunks. `tests-w31` and `session-w31` remain separate write-once
outputs. A failed first chunk prevents the second; neither chunk installs or
claims durable throughput. Its host tests include failed/durable predecessors,
unclosed USB, forced workers and the exact two-chunk/no-rate-change invocation.

### Byte-Preserving ACK Batch Candidate

`p34_ack_batch_assets.py prepare` is host-only and write-once under `.cache/p34ab`.
`p34.bat prepare-patch --group ack-batch-bootstrap` binds the completed30232
predecessor to30235 FULL. `p34.bat start --group ack-batch-bootstrap --cell s04
--profile .cache/p34-session/profile-ack-batch-bootstrap.json` still requires
current tool tests and fresh recording/device admission. This is not acceptance.

Profile contracts: `ack_gap=true`, `ack_batch=true`, QUIC, no native Android
diagnostic,921600/window32. All old-family manifests remain separately pinned;
old groups do not load new assets. A closed, clean window31 zero-durable
diagnostic identifies prior staging, never the new target. Missing/changed
source, MAP, package, decoder negatives or full predecessor blocks admission.

Batching keeps all complete ACK frames/FIFO bytes, never suppresses CRC/seq or
changes durable meaning. Only a bounded pump scope buffers at most228 bytes;
control/errors and durable advancement flush immediately, pump exit flushes
the tail, failed writes latch without replay. Actual UART batches retain the
TX-complete/1ms-gap primitive. Software-call profile counts now count batches,
not individual encoded ACKs; requested bytes still cover every transmitted byte.
Tests cover source identity, exact new context/service, old-family isolation,
bad proof/profile rejection and the compiled FIFO primitive. Forward30236 is
an offline recovery artifact, not a second admitted OTA.

After the verified30235 bootstrap, `p34_batch_screen.py test|prepare|start|status`
owns `.cache/p34ab/screen`. Its window31 pair uses142 then244-byte GATT writes,
fresh30235 MAP/full identity, and header-only30237 diagnostic package; no END,
installation or additional system report. Existing source-bound ACK/ABORT and
native zero-durable/payload checks remain mandatory. Context construction may
be reused only within one process and the identical output; cross-output reuse
fails. Tests cover old/wrong identity, confirmation/rate/owner guards, and this
single-output invariant. Do not reuse a completed diagnostic directory.

### Receive-Restore Screen (30228 To 30230)

`Tools/ota/p34_receive_assets.py prepare --root ABSOLUTE_ROOT` is a host-only,
write-once asset preparation using the verified `.cache/p34sr` App candidate.
The normal `prepare-patch` and `start` commands accept `receive-bootstrap` and
`receive-pressure`; both use `s04`,921600/window32 and the existing verified APK.
No compact group or automatic third cell exists. The actual matrix, retained
state and exact capture-cleanup authority live in P34-RECEIVE-02 in the existing
installation note, not in this command documentation.

The first group requires real completed `patch32-pressure`30228 and installs
30229. Its transfer still measures the old receiver. The second requires real
completed `receive-bootstrap`30229 and installs30230 via exact1MiB PATCH. Static
construction of a pressure context in a test is not a future device identity.
New source-aware profiles require `receive_restore=true`, `native_diagnostic=false`,
QUIC and hash-bound `patch_prior_assets` for the two prior PATCH32 cells. Each
asset-family loader verifies its own immutable manifest. Old groups never depend
on the future receive assets, and old build results are not relabeled.

| Input/state | Required behavior |
| --- | --- |
| Valid30228 and checked candidate | Prepare bootstrap profile, no device action |
| No complete30229 | Reject pressure profile before device/backend construction |
| Different candidate result/flag/Boot/layout or changed raw/MAP | Reject rather than substituting an old build |
| Wrong window, source pin or prior-family asset hash | Fail closed before a new run |
| Existing attempted/completed receive-pressure | Return original result; no replay or implicit successor |
| Capture cleanup | Only the original immediate predecessor; current capture and all other directories protected; eligibility is not deletion authorization |

`ReceiveTests` covers the new binding, package, profile, transition and negative
cases. Run the contained `p34 test` route before use. Formal throughput/stability
acceptance remains separate, and a legal successor comparison is not strict
same-package A/B.

### Cached Download Observation Recovery

Scope: an unadmitted `receive-bootstrap` worker failed with
`RuntimeError: App file size bound` because a reused download filename still
contained a prior package. A filename's existence is not download completion.
`Backend.downloaded_package(c, p) -> bytes | None` checks the stat size before
reading. A stale length or same-length different bytes returns pending within
the existing start deadline; malformed stat and transport failures still raise.
Only exact expected bytes can admit Start. No cache is deleted or overwritten.

After all original owners close and the same App has the correct cached bytes:

    python -I -S -B -X utf8 Tools/ota/p34_cached_resume.py start --root ABSOLUTE_ROOT --run ORIGINAL_FAILED_RUN

The root must be explicit and cwd must equal it. The helper requires source-bound
session tests, the original exact failure and unmodified inputs, a successful
original native closure, and a fresh same-PID/config/capture check with zero
upgrade starts/ends. It creates a new finite observation run, not another App
launch, service, download or transfer. `origin-record.json` preserves the old
endpoint as provenance only; the old service is closed and is not needed.
`launch.json.time` stays the original App launch time, while
`observation_resumed_at` starts the new bounded observation allowance.

| Input/state | Result |
| --- | --- |
| Old cache exists before download | Pending, no Start admission and no deletion |
| Exact current bytes, same unused App | Fresh native check and observation can proceed |
| Same filename/length but different bytes | Pending, never accepted as the current package |
| New PID/capture/config, any upgrade start, lost/error or snapshot | Reject recovery; reconcile original evidence |
| Prior owner unclosed, different failure, already resumed run | Reject; no generic retry or extra cell |
| Completed resumed observation | Normal original snapshot/full raw App/Boot/CONFIRMED oracles |

Tests cover stale and same-size cache mismatches, strict exact-byte admission,
the real original failure, identity/start-count negatives, the observation
deadline and a modeled lifecycle proving reader closure before final readback
and USB closure before analysis. Wrong: reopen the App to repair a collector or
increase its capture limit. Correct: observe the same unused capture and retain
the original failure in a separate, source-bound successor record.

### Command Reference

### Unused App Exit Relaunch

When Android has killed the unused App, the same-PID recovery cannot be reused.
The separately authorized exact recording and its original events are bound by
`Tools/ota/p34_relaunch.py`; it is not a generic deletion or retry interface.

    python -I -S -B -X utf8 tests/ota/test_p34_relaunch.py
    python -I -S -B -X utf8 Tools/ota/p34_relaunch.py cleanup --root ABSOLUTE_ROOT
    python -I -S -B -X utf8 Tools/ota/p34_relaunch.py start --root ABSOLUTE_ROOT

Cleanup requires an absent process, the exact unused capture/configuration,
zero start/end counts and original event-byte equality. It archives the owned
configuration through the existing retirement helper, checks all selected files
and the resolved path, then removes only the authorized recording. A changed
path, active App, new snapshot or different bytes rejects before deletion.
The remaining directory set must equal the original set minus that one capture.

Start requires that completed cleanup, unchanged source-bound tests, absent
App/configuration, seven remaining records and the protected30228 snapshot.
It creates a new plan with the original30228 predecessor, and uses the normal
finite network/cell workers. Old failed plans are neither rewritten nor restarted.
Both entries are write-once; partial failures require reconciliation, not replay.
The four standalone host tests bind their source and the existing full core-test
receipt; they do not substitute for physical OTA or independent acceptance.

### Command Table

| Command | Behavior |
| --- | --- |
| `p34.bat doctor` | One bounded private-USB check of phone/APK/permissions and original App capture; reports unresolved work without changing the App or MCU |
| `p34.bat start --cell s01` | Reuse a live session or prepare a new verified service, reconcile an owned idle App/configuration, then open the bounded MCU/App observation route |
| `p34.bat status` | Read current receipts and deadlines only; no backend import, ADB, J-Link, DNS, downloads or artifact hashing |
| `p34.bat collect` | Preserve original App records/snapshots through the live USB owner or a new bounded read-only USB scope; never replay a transfer |
| `p34.bat collect --offline` | Re-validate the already-preserved snapshot/configuration and original MCU closure; no USB, J-Link, service or transfer |
| `p34.bat collect --verify-mcu` | Reconcile a closed prefix using its stored readback, or one bounded same-generation staging readback if missing; no BEGIN, DATA, END, tuning, reset or install |
| `p34.bat stop` | Refuse active/uncertain transfers, close the selected observer first, then its service; use the App's cancel/ABORT route during transmission |
| `p34.bat test` | Run contained host regressions and bind their result to the tool sources; no device or network calls |
| `p34.bat recover-prestart --run ID --cell s04` | For the diagnosed full-store/unrecorded full launch only: verify closed owners and unchanged native generation, then retire its exact App process/configuration; no OTA, launch or capture deletion |
| `p34.bat prepare-window8` | Host-only write-once preparation/revalidation of V from verified U; no firmware/APK build or device access |
| `p34.bat prepare-repeat` | Host-only write-once preparation/revalidation of W from verified V; preserves the frozen nonce and executed generator snapshot |
| `p34.bat prepare-install` | Freeze X/Y once from the App-only N04 build; bind W-to-X now and X-to-Y only after real completed X evidence; host-only |
| `p34.bat prepare-window16` | Freeze header-only Z from the verified N04 build and bind one Y-to-Z 921600/window-16 cell to completed Y; host-only, no stop/deletion/OTA |
| `p34.bat prepare-patch --group patch-bootstrap` | Bind prepared AA FULL bytes to actual completed Y; host-only, no repack, App stop, service or installation |
| `p34.bat prepare-patch --group patch-compact` / `patch-pressure` | Bind one prepared AA-to-AB PATCH alternative only after actual completed AA; the two inputs cannot run sequentially |
| `p34.bat prepare-patch --group patch32-bootstrap` | Bind the fixed 30227 FULL package to actual completed30226 at921600/window32; no device operation |
| `p34.bat prepare-patch --group patch32-pressure` | Bind the exact1MiB 30228 PATCH only after actual completed30227; no future-predecessor placeholder |
| `p34.bat quiesce --run ID --cell s04` | Stop only the current, verified completed diagnostic App under the applicable exact permission; preserve its configuration and every capture |
| `p34.bat prune-completed --run PREDECESSOR_RUN --cell s04` | Read-only archival preview of the immediate original predecessor: V protects U, W protects V, or X protects W; no stop or deletion |
| `p34.bat prune-completed --run PREDECESSOR_RUN --cell s04 --apply` | Separately authorized deletion of that one verified phone copy after archival, stopped-App and resolved-path checks; never clear App data |

Use `--run ID` to inspect/collect a particular historical run and `--cell s02`
through `s04` for the remaining declared cells. V1 defaults to `s01`; pass the
current cell explicitly to `status`, `collect` and `stop` when using S02-S04.
Repeated `start` for a live
cell returns its status instead of starting another operation. A completed or
uncertain transfer is not permission to replay it. After interruption, inspect
`status` and `collect` before changing the experiment.

Start with `status`, not a full `doctor` on every message. Run `doctor` when a
new device window actually needs checking. If a cell was invoked, `start` with
that same cell returns its result instead of repeating it. Advance explicitly
with the next planned `--cell`; do not create another continuation script.

The wrapper selects `python` on PATH; set `P34_PYTHON` to an existing executable
if needed. It always supplies `-I -S -B -X utf8` and the repository root.

## N03 Paired Arms

Use `start --group n03-a --cell s01` for retained 30214 and the fixed 30216
probe T. Use `--group n03-b` with its prepared profile for the bound 30215 N03
receiver and byte-identical T. These are separate comparison groups, not new
results in the old screen matrix.

N03 groups no longer open Chrome for a zero control. They read the old journal
twice, verify ETRJ CRC and a known package identity different from T, and bind
stable idle samples in `fresh-begin.json`. No preparatory BEGIN/ABORT is sent;
this is not a native zero-state observation. The pinned App's normal BEGIN
must confirm zero durable and bitmap before DATA. Collection additionally
requires original zero-durable-before-DATA evidence, strict ABORT, the next
profile generation, no retransmissions, clean MCU counters and final staging
and retained-image readback. Same-package, corrupt, unknown or changing state
stops without browser fallback or replay.

The actual sampler now supports the bound 288-byte and 336-byte layouts.
Its local dependency `.cache/p34-next/prefix_mcu.py` is included in the test
source binding. This remains a local tool with required cached assets/helpers,
not a clean-clone delivery. The earlier manual-SD choice was superseded by the
user's 2026-09-27 decision to install R through ordinary BLE OTA. `identity
--group n03-b --profile PATH` remains a read-only receiver check, not an installer.

The prepared B profile has an explicit `predecessor` descriptor containing the
A run/cell and immutable plan/report/readback records. Only a clean reconciled
N03 A with closed owners can advance to B, using the identical T and cell.
Underlying snapshot, configuration, journal, prefix and full-image records are
rechecked. Same-group invocation still returns its old result, not a replay.
The previous App is retired only when its live snapshot/config/PID/capture
identity exactly matches that preserved predecessor. Do not delete `current.json`
or old captures to force a group change.

### Normal OTA Bridge

`start --group n03-install --cell s04 --profile PATH` installs the fixed R only,
using the existing diagnostic APK in schema-2/full/zero-prefix mode at retained
921600/window 4. The installation profile explicitly binds the completed A.
Its own run holds its configuration, original App snapshot and separately bound
before/after native identities. The old-image reader closes before App launch;
it is not polled across END/apply/reboot. The user starts the full foreground
upgrade only after `READY_FOR_FULL_INSTALL_START`, not the prefix control.

`status/collect/stop --run INSTALL_RUN --cell s04` manage this same owner.
Repeated installation starts return the attempted run, including a failure;
they do not replay OTA. `collect --offline` reconciles preserved files without
devices. `collect --verify-mcu` reuses the original full R/Boot/CONFIRMED readback
or performs one bounded native-only recovery if absent. Collector failure is
not permission to reinstall. Full observation has a 900-second active bound
in addition to the existing 1500-second App-start wait.

Before B, close installation owners and create a profile binding both the
original A `predecessor` and the installation's exact `run/cell/plan/report`
under `installation`. B retirement then requires that completed installation's
exact config/snapshot/PID/capture, not A's obsolete App process. R remains on the
device; B sends byte-identical T and strictly aborts without installing T.
The original snapshot's PID stays bound even if its process has exited. A
stopped App may be archived only after two unchanged `pidof` reads prove absence;
a different live PID or an unverified absence still blocks retirement. The cell
checks the same live/absent state again immediately before archival.
The bootstrap upgrade is received by the old firmware and cannot measure N03
receiving benefit or unobserved internal installation-phase timings.

Flash admission addresses are derived from the receiver's exact, hash-checked
MAP using the existing strict section/size/object parser. Historical 30214
addresses cannot be inherited by R. A successful receiver admission additionally
records the image, MAP, addresses and original Flash gate receipt; a retained
identity closure alone cannot mask a failed `open()` admission. Missing admission
keeps installation reconciliation incomplete until a bounded read-only recovery
supplies it. Never repeat the successful OTA to repair this host gap.

Status samples its clock after reading the heartbeat. It ignores prelaunch
retirement health, binds current health to the admitted App capture, and never
turns a stale started/completed capture back into a Start invitation while native
verification is running.

Frozen ABORT profile decoding binds the schema to the exact phase list: the
retained 288-byte/eight-phase layout is schema 1; N03's 336-byte layout with
appended `payload_verify` and `journal_verify` is schema 2. Do not accept an
arbitrary schema with a matching byte count or reinterpret schema-2 bytes as
schema 1. The compiled R header and both schema/phase combinations are covered
by the contained host suite.

## Current Profile

### N03 Full Successor

`p34.bat prepare-full` is host-only and freezes U, target 30217 / `3.2.17-p34n`,
from R's built N03 executable using the production header finalizer and packer.
It does not rebuild firmware or APK, and refuses to overwrite partial assets.
An existing complete preparation is rechecked and reused without a new nonce.
Python/native decoder and negative results are in
`.cache/p34-session/n03-full/assets/result.json`. U is not the old-body probe T.

`start --group n03-full --cell s04 --profile .cache/p34-session/profile-n03-full.json`
is the single declared zero-start full validation received by R, at 921600/window
4. Its predecessor is the fully reconciled B, with A and R-installation originals
still verified. The user's existing foreground connect/download/start steps are
unchanged. Repeated Start returns the attempted full run, never repeats OTA.

The before/after identity checkpoints stay separate. Between them one bounded
native thread reads R's schema-2 END profile, existing BLEACT timing markers,
Boot state/tick samples and U's initialized App state. Only a live matching App
RTT read pointer can be written; no RTT down commands, tuning, manual reset or
Boot write is part of this observer. An old ring may be preserved read-only
during Boot, with its original descriptor and explicit retained-buffer label.
The thread is joined before final U/Boot/CONFIRMED readback. Modeled native-link
tests exercise the real reader through R, Boot and U before hardware use.

Report device `millis()` activation values as tick intervals, not automatically
wall seconds: interrupt-masked Flash work may distort that clock. Boot uses
host-monotonic observation brackets; its outcome variables are not per-block
progress. Phone END-to-reboot verification remains its own clock domain.
Coarse observation gaps cannot turn a successful OTA into permission to replay.
All full DATA offsets must cover U exactly from zero, with the original summary
and END/reboot markers; this is not the 1 MiB reference or strict same-package A/B.

### U-To-V Window-8 Successor

`start --group n03-window8 --cell s04 --profile .cache/p34-session/profile-n03-window8.json`
uses U 30217 as receiver and frozen V 30218 / `3.2.18-p34n` as target, at
921600/window 8/full/zero-prefix mode. All older groups retain their original
axes. U and V differ only in the standard firmware header, with the original
MAP, executable, Boot, sender, write mode and native observation route retained.
The manifest is `.cache/p34-session/n03-window8/assets/result.json`; revalidation
never regenerates the package nonce. T is never an installation target.

The profile binds the complete U report/plan and its full post-install identity,
not merely a version string or B's prefix. Complete original DATA, zero retries,
closed owners, full U/Boot and CONFIRMED remain prerequisites. An attempted
window-8 run is returned on repeated Start, including a failed result; it cannot
be replayed by selecting another group. The U-to-V comparison is sequential
legal full packages, not byte-identical full A/B or stability acceptance.

For the completed U-to-V batch the user separately approved stopping the verified idle
U diagnostic App and deleting only B's phone directory
`files/p34-observations/1790500881632914-6e3a13cdcca1e84e5e34d497`.
Run the current host tests before quiesce or device preparation. Quiesce verifies
the original snapshot/configuration/PID, checks again immediately before stop,
and verifies process absence twice with configuration preserved. A different
PID/configuration, active capture or unresolved owner stops this route. The
existing guarded `prune --delete CAPTURE` separately checks resolved Android
paths, original host copies and stopped-App state. Keep all host evidence and
the phone's successful R/U recordings. Quiesce never deletes or archives files;
the next admitted cell performs the usual exact configuration archival.

The concrete host boundary is `cells_for(group) -> dict[cell, (baud, window)]`
plus `completed_full_predecessor(store, descriptor)`, where the descriptor has
exactly `run`, `cell`, `plan` and `report`. Original plan/hash/group checks happen
before following predecessor links. It cannot accept B's prefix or R's bootstrap
installation as completed U. `quiesce(store, run, cell)` additionally requires
the current run, `s04`, current source-bound tests and closed prior owners.

| Case | Required Result |
| --- | --- |
| Verified U, explicit V profile, full `s04` at 921600/window 8 | One new bound run, with fresh phone/native admission before Start |
| Original non-window-8 group | Original cell matrix, unchanged |
| Existing attempted V run, even if failed | Return that attempt, never replay it |
| Wrong/missing predecessor, stale tests, different live PID/config or active capture | Refuse before the affected device mutation |
| Exact completed U, original process already absent twice | Quiesce succeeds without another force-stop and preserves configuration |

`tests/ota/test_p34_window8.py` asserts these transitions, real U/V asset and
configuration binding, header-only/no-regeneration reuse, negative gates and
trace-close-before-target-readback ordering. In modeled device tests no real
USB/native operation runs. Correct: consume the verified current predecessor.
Wrong: remove `current.json`, weaken its identity checks or relabel a completed
transfer to force another Start.

### V-To-W Single Window-8 Repeat

The explicit `n03-window8-repeat` group selects V 30218 as receiver and frozen
W 30219 / `3.2.19-p34n` as target. Its finite plan is one zero-start full OTA
at 921600/window 8, not W16 or a stability campaign. W retains V's N03 executable,
MAP, ABI and original Boot; only the standard firmware header differs.

`prepare-repeat` has already produced the 290985-byte package in
`.cache/p34-session/n03-window8-repeat/assets/result.json` and the profile
`.cache/p34-session/profile-n03-window8-repeat.json`. Reuse them; do not generate
another nonce. `Tools/ota/p34_successor_assets.py` checks the declared successor
specification and stores its own executed source snapshot with the assets.
This avoids requiring mutable generator-origin bytes to remain unchanged just
to consume a prior package. U/V's original pinned generators remain untouched.

The profile binds V's original plan/full report, complete DATA, full target/Boot
readbacks and CONFIRMED state, while retaining the R/U/V asset chain. Only an
explicit `start --group n03-window8-repeat --cell s04 --profile
.cache/p34-session/profile-n03-window8-repeat.json` can advance to this group.
An attempted W remains latched, including failure; another Start/group cannot
replay it. Current V proof is historical, not fresh admission for W. Prepare the
real collectors and verify the downloaded W before inviting foreground Start.

W's run `20260927T141330-27800/s04` completed and retains W 30219.
It transferred 290985 bytes in 58.164197 seconds at 4.885566 KiB/s, with 2274
DATA segments, zero retries and clean MCU counters. Installation/reconnect took
62.951594 seconds. Full W/original Boot, SD ready and idle/CONFIRMED were verified.
The report is `runs/20260927T141330-27800/analysis/1790519079813719500/result.json`
under `.cache/p34-session/`. All observation/network owners are closed;
the W diagnostic App's last PID is 14476 and was not stopped after success.

The user separately approved V's idle App stop and removal of only the U phone
recording bound by original run `20260927T114731-53800/s04`. Both completed,
with receipts `quiesce/1790518283969446300/result.json` and
`completed-prune/1790518321954691500/result.json` under `.cache/p34-session/`.
The deletion changed the directory set from 8 to 7 by removing U alone; W
subsequently created its own recording. All host originals and phone R/V/W
records remain. The two earlier manually copied U suffixes remain withdrawn.
These completed permissions do not authorize another deletion or stopping W.

`completed_capture_target(store, run)` derives the exact remote directory from
the verified U report/query in the current V chain. `prune-completed` does not
accept a hand-copied directory. Its default preview retrieves health/events and
the single full snapshot, validates the original footer/config/PID/hash and
stores every retrieved byte under `.cache/p34-session/completed-prune/ID/`.
Preview may read the historical U recording while V's App remains idle; it
neither stops the App nor deletes a recording. It uses bounded private USB,
so it is not an offline command.

The first such preview succeeded in 17.8157 seconds at
`.cache/p34-session/completed-prune/1790517930450246300/result.json`.
The full U snapshot matches its original bytes/hash, all eight directories
remain and private USB closed normally. This does not satisfy deletion authority
or create a free recording slot for W.

Only a separately authorized `--apply` checks that the App is stopped, resolves
the selected Android directory, records an immutable intent and removes exactly
that one phone copy. The remaining-directory set must match, protecting V and
every other recording. A completed apply is returned without another device
operation; an uncertain/missing apply result blocks replay and requires
reconciliation. Prefix cleanup remains a separate command and permission.

`tests/ota/test_p34_repeat.py` adds 17 cases for real V/W assets and predecessor
binding, header-only reuse/provenance, quiesce, archival preview, exact deletion,
unsafe inputs and replay rejection. The current affected suite is 173/173 PASS
at `.cache/p34-session/tests/1790516956682472200/result.json`, with zero failures,
errors, skips or device operations. The test-child bound is 180 seconds; no
device lifetime was extended. Documentation changes do not require replaying
these tests, previous firmware/Flutter CI or completed physical upgrades.

### Unrecorded Full-Store Recovery

The pinned diagnostic APK holds at most eight recording directories. Preparation
requires a verified free slot before creating a plan, service or native owner.
A new launch must expose its own original open header, PID and configuration
stamp; an older capture's terminal counters are not the new process's result.

For the preserved `20260927T103556-51500/s04` prestart failure, ordinary `start`
still returns the original failure. The explicit `recover-prestart` route checks
the full-store failure, original B snapshot, exact launch/configuration, closed
owners and fresh unchanged R/Boot/session/profile before stopping only that owned
unrecorded App and archiving its configuration. It writes a new immutable report
and `runs/ID/prestart-recovery.json`, without altering the failed receipt or
current pointer. A different PID/configuration/generation, an admitted full
query/transfer, or an uncertain prior retirement blocks this path.

Capture deletion is separate and requires exact user scope. `prune` without
`--delete` only inventories. `prune --delete CAPTURE` rechecks preserved terminal
payloads, a stopped App and the resolved App-relative path before deleting only
that phone directory; it never clears App data or removes host evidence. For this
incident only A's already-archived directory
`1790495235875333-2365d84b31a6d2f9b8cdf972` is authorized, retaining B and the
successful R-install recording.

After that cleanup, use `start --group n03-full --cell s04 --profile PROFILE
--prestart-recovery .cache/p34-session/runs/ID/prestart-recovery.json` to advance
once from the preserved failed preparation. The next plan binds the recovery
receipt, unchanged completed B and identical U. Prestart must observe the App
stopped, configuration absent and the same original B snapshot. Repeating Start,
with or without the same recovery pointer, returns the new attempted run rather
than replaying it. A recovery receipt is neither installation evidence nor an
authorization for another capture deletion.

Local settings: `.cache/p34-session/profile.json`. This profile binds the
already-verified 30214 receiver, Boot, fixed 30215 package, diagnostic APK and
known App configurations. V1 reuses the source-pinned device/USB/HTTP primitives
from the existing local P3-4 evidence, but does not execute their old continuation
controllers. The cached artifacts are still required on this machine; this is
not a claim that a fresh clone contains them. Missing/changed inputs fail with
the concrete path rather than triggering a build, download or guessed recovery.

The initial cells remain 460800/window 4, 8, 16 and 921600/window 4. Each is a
32768-byte prefix and strict ABORT, not END or installation. Live full App/Boot,
Flash/SD/BCB/clock and link checks are still required; only immutable artifacts
and completed host/CI evidence are reused. There is no automatic 115200 rerun.

Profiles and scripts do not grant permissions. The current task's existing
device authorization and exact J-Link connection-history exception remain
required. A different device/firmware/Boot or profile needs explicit new inputs
and the applicable authorization. The tool must not invent compatibility.

## Lifecycle And Evidence

Runs: `.cache/p34-session/runs/ID/`; current pointer: `current.json` in the same
tool directory. Plans, attempts, failures and original files are preserved.
Expired endpoints are not presented as live, and a closed receipt takes
precedence over an old `worker_alive` heartbeat. New sessions use new output
directories and only replace the current pointer.

Network supervision is bounded to 5480 seconds, service to 5400 seconds and a
cell to 3900 seconds. The App-start wait is separately bounded to 1500 seconds;
the cell supervisor lifetime is not extra time to tap Start. A reconciliation
readback has a separate 180-second owner. DNS readiness has its own bounded child queries and does
not consume a physical measurement. HTTPS readiness retries only service-side
transience (502/503/504, TLS reset/EOF, and the quick tunnel's 530 during edge
re-registration) at offsets 0/15/45/90 s; metadata or byte mismatches fail at once.
The real HTTPS metadata, correct
`prefix-screen-full.etu` name and complete fixed package must verify before
opening the MCU window. Source/asset/plan binding is checked on execution, not
on every status request. Operational board edits are not executable inputs.

An expired service is refreshed only after old owners close and a fresh App
capture proves no unresolved transfer. Exact owned configurations are archived
inside the diagnostic App before replacement. No `pm clear`, arbitrary process
kill, protocol relaxation or successful-OTA replay is used to repair a collector.

A completed prefix can be retired for the next cell only when its exact
configuration, original snapshot, PID/capture identity, terminal health and
verified retained/readback proof match. An unknown, active or unreconciled
completed App still blocks preparation. No completed snapshot is deleted.

`command.lock` serializes control commands. A normally returned or failed
command releases only its own lock. If a host process is externally killed and
the lock remains, inspect its PID and owned runtimes before removing that exact
project-local lock; do not blindly clear locks or kill processes by name.

The tool prepares and observes. The user still connects/selects the device,
downloads and taps the foreground prefix control when the status is
`READY_FOR_32K_PREFIX_START`. An App snapshot or host test alone is not physical
throughput/stability acceptance.

## Recovery Contract

`status` returns JSON with `run`, `cell`, `result`, `network`, `worker`,
`progress`, `analysis` and `next_action`. It does not hash evidence or contact
devices. Fresh App counters override the old ready marker with
`TRANSFER_ACTIVE`/`FINALIZING`; stale or closed ownership never invites another
transfer. Source/identity verification belongs to execution, not polling.

| Observed State | Correct Action | Rejected Shortcut |
| --- | --- | --- |
| `NO_SESSION` or expired idle endpoint | `doctor`, then `start --cell sNN`; preserve previous owners and exact configuration | Reinstalling the APK or replaying an old tunnel launch |
| Live ready/active cell | Read `status`; keep an active App in the foreground | Another start/OTA to obtain more logs |
| App finished, host parser failed | `collect --offline`; if staging proof is missing, `collect --verify-mcu` | Repeating the successful prefix or manufacturing a footer |
| `PREFIX_RECONCILED` | Keep the failed original receipt and the separate proof; select the next planned cell | Rewriting old `result.json` to PASS |
| Different capture, configuration, image or MCU generation | Stop and reconcile the observed change | Killing an unknown App or accepting an old readback as current |

Derived results live under `runs/ID/analysis/TIMESTAMP/`; `analysis/latest.json`
is only a pointer. Each interpretation binds the original plan, configuration,
launch, snapshot and current parser sources. A later parser may re-read the
same immutable bytes without making the original worker look successful.
Historical MCU closure is labelled separately from a new staging readback.

`Tools/ota/p34_observation.py` is the repository-owned snapshot verifier,
promoted from the N01 verifier without changing its envelope/footer, original
DATA coverage, ABORT or identity requirements. The App logs its configuration
at initialization and at transfer start. Multiple stamps must be identical;
conflicting or malformed stamps fail. Only letter case in a valid MAC address
is equivalent, not another address or a changed hash. Original JSONL and
unwrapped messages retain every stamp; there is no synthetic footer or record.

`p34.bat test` covers lifecycle ownership, replay rejection, snapshot corruption,
duplicate/conflicting stamps, MAC identity, readback-generation checks and
read-only recovery. The original verifier regressions are included. Test results
bind all tool/parser/test sources and stay separate from actual hardware results.

## Current Limitations

September 28 completion: X bootstrap `20260927T160919-23000/s04` and Y measurement
`20260927T162548-11400/s04` both completed with full target/original Boot/SD/
idle/CONFIRMED proof. Y is retained; all observers and temporary services closed.
The current diagnostic App's last PID is 11230 and it has not been stopped.
Installation/reconnect improved 62.950062 to 49.657590 s in this one comparison,
but transfer increased 53.658056 to 70.363044 s; combined time increased 2.93%.
Keep both findings. Exact authorized V/W phone cleanup completed, preserving X/Y,
R and all host originals. The following W discussion is historical, not current.

Current completed run: `20260927T141330-27800/s04`, W 30219. The single
window-8 repeat is complete; repeated Start of that group returns this result and must not
replay it or silently advance to a later version. W's cell and network closed
at 14:24:48 and 14:25:18 UTC respectively. The temporary endpoint is no longer
usable. Full raw W/Boot and final idle/CONFIRMED are verified; the diagnostic
App remains retained after success, last PID 14476, not a claim of process exit.

The full/window-8/repeat profiles define R-to-U, U-to-V and V-to-W respectively.
Their `identity` receiver bindings are not automatically the newly installed
target. In particular, `identity --group n03-window8-repeat` describes V, not
current W. The explicit N04 profiles below now support W/X with newly bound
targets; `quiesce` still needs exact permission and is not an arbitrary PID
stop. Do not remove `current.json`, relabel an old attempt or extend a
completed cleanup grant to bypass these guards.

Original U/window-4 and V/window-8 reports remain historical. The offline
`n03-window8-repeat/comparison.json` binds all U/V/W originals. The two window-8
transfers were 55.009445 and 58.164197 seconds, averaging 56.586821 seconds;
against U's single sample this is 41.37% less transfer time and 25.17% less
combined transfer/installation time. Package identities differ. This is not
strict same-package A/B, the 1 MiB throughput gate or stability acceptance.
Installation still takes about 63 seconds. Do not repeat W to obtain more logs.

### N04 Installation Candidate

Host preparation is complete, not a measured installation improvement:
`P34-INSTALL-02` in `docs/ota-exec-notes/P3-4-install-workload-2026-09-25.md`
owns the finite W-to-X bootstrap / X-to-Y measurement plan. X/Y are
30220/30221, preserve N03 and Boot, and both packages are immutable. The App-only
GCC build has 638 warnings/0 errors; the original post-build CRLF parser failure
was reconciled without recompiling. Ten driver/HAL tests and 196 session tests
pass; those are development self-tests, not physical or independent acceptance.

The prepared initial profile is `.cache/p34-session/profile-n04-bootstrap.json`.
Its group is `n04-bootstrap`; use only `s04` at 921600/window 8. The subsequent
`n04-measure` profile is created by `prepare-install` only after X has really
completed and its original full image/Boot/idle/CONFIRMED evidence is verified.
Both packages can be prepared now without inventing that future predecessor.
W-to-X has now been prepared and admitted as described above; X-to-Y remains
NOT_RUN. Y is header-only relative to X; W-to-X still uses the
old installer, so only X-to-Y can observe the new receiving App's install path.

The generic installed-context transition now recalculates Flash gate addresses
from the target MAP. Assuming identical addresses was only valid for the old
header-only U/V/W sequence. RTT, session addresses, image/ELF/MAP and the unchanged
336-byte/schema-2 BLE profile are all bound to the actual target.
`P34INSTALL` summaries are separate RTT records; missing/conflicting or invalid
cycle samples remain gaps while full image/Boot confirmation stays authoritative.

The current V archive is
`.cache/p34-session/completed-prune/1790523326257184100/result.json`:
8/8 phone directories, zero phone mutations, original snapshot matched, USB
closed. W App was not stopped in that historical preparation. On September 28
the user approved idle W stop/V deletion and later idle X stop/W deletion only
after X succeeds, under the exact sequence recorded in the installation note. The exact
directories are derived from original run/query records and listed in the board.
All host originals and the current/protected phone capture remain retained.
Do not start a service or ask for foreground Start until the real recording slot
and state prerequisites are met; the old W endpoint is closed.

Native `boot` timing keeps its strict initialized/CONFIRMED-in-trace gate. The
additional `boot_residency` field can expose a bounded VTOR residency observation
without that final sample, explicitly labelled weaker than confirmation. It
does not repair the strict gap or substitute for separate full post-install
identity/Boot confirmation. Parser updates consume originals into a new analysis
directory, never replay OTA or fabricate a trace sample.

This is a local P3-4 development tool, not a persistent production update
service. Closing or expiring a temporary service makes its hostname unusable;
the next authorized `start` provisions a new verified origin. Cache-independent
artifact discovery/bootstrap and a permanent authenticated update endpoint are
not implemented. A missing pinned dependency is a preparation error, not
authorization to regenerate it, install an SDK or deploy a service.

### Prepared PATCH Route

#### Current PATCH32 Successor

The declared pair has executed: bootstrap30227 completed in run
`20260929T075409-91600/s04`, pressure30228 in`20260929T081420-42700/s04`.
Both have original full target/Boot/CONFIRMED readbacks and closed owners.
The pressure's exact1MiB transferred in138.987678s (7.367559590KiB/s), zero
retransmits; install/reconnect63.539468s. Throughput is below9KiB/s and formal
reference/stability/independent acceptance is not complete. Retain30228 and all
originals. Repeated start is not another trial; there is no automatic pressure
successor or compact third cell. See the current task note for original-log
diagnosis and remaining gates. Preparation descriptions below remain the API
contract, not an invitation to rerun either successful cell.

The approved two-cell route after completed30226 is `patch32-bootstrap` followed
by `patch32-pressure`, both `s04` at921600/window32. The legacy `PATCH_GROUPS`
remain unchanged at window8; `PATCH32_GROUPS` and `ALL_PATCH_GROUPS` keep selection
explicit. There is no `patch32-compact` device group. The307-byte compact and
1048576-byte pressure packages have the same30228 target and are alternatives,
not consecutive upgrades. The first FULL package is291771 bytes and introduces
the verified coalescing receiver30227. These reuse the614604-byte App executable,
ELF/MAP and original Boot; no firmware or APK rebuild is implicit.

`p34_patch32_assets.prepare(store)` requires the actual completed/closed
`speed-window32` owner and writes `.cache/p34-patch32/input-admission.json` plus
immutable assets. `load()` rechecks original30226 lineage and all package proofs.
The bootstrap profile is `.cache/p34-session/profile-patch32-bootstrap.json`;
`prepare_patch(store, "patch32-pressure")` refuses any predecessor other than
real completed30227. Profile flags must include `patch32=true`,
`native_diagnostic=false`, and `tunnel_protocol="quic"`. A complete transfer still
uses `transferMode="full"`; ETU `asset.kind="patch"` independently binds the exact
base SHA/version. Final full target/Boot/CONFIRMED readback remains mandatory.

The first size search exhausted128 encodings without an exact witness. Its
`assets/failed.json`, inputs, finalized images and existing ciphertext/nonces
remain unchanged. `p34_patch32_recovery.resume(store)` is an explicit host-only
continuation for that exact failure, not generic retry. It validates original
inputs and both existing packages before writing a `search-continuation/intent.json`
snapshot; one512-total search reuses128 measurements and permits at most384 new
ones. Any other failure, completed/partial continuation, changed owner or prior
native-validation output rejects. Success adds the witness and all normal
Python/native positive and pre-prepare negative checks without rewrapping old
packages. Repeating ordinary preparation after success only verifies/reuses.

| Input / state | Required result |
| --- | --- |
| Actual completed30226, fixed bootstrap | `PATCH_PROFILE_PREPARED`, no service or device access |
|30227 not yet completed | No pressure execution profile |
| New group with window8, native diagnostic or HTTP/2 | Reject before device action |
| Wrong base/kind/specification or changed manifest | Reject rather than silently reuse another package |
| Attempted bootstrap/pressure | Return original status; only an explicit legal successor may advance |
| Search-budget failure with immutable partial assets | One bounded offline continuation; preserve original failure/nonces |
| Completed or partly failed continuation | Reject replay; preserve all outputs |
| Capture cleanup | Only immediate completed predecessor eligible; exact deletion permission still required |

`Patch32Tests` checks these boundaries, source pins, MAP/profile-size binding,
old-group isolation, no-replay transitions and preserved partial assets. Correct:
create the first profile now and the second after original30227 completion.
Wrong: fabricate a30227 report, append padding to reach1MiB, regenerate an old
nonce, or delete a phone capture merely because it is eligible. This remains
development preparation, not formal reference/performance/stability acceptance.

Current host evidence:17 focused PATCH32 cases PASS; the complete310-case run
had309 PASS and one obsolete window32-no-successor assertion. After changing
only that assertion to the exact allowed bootstrap descendant,6 affected
Speed16 checks passed and304 unchanged original PASS cases were directly reused.
`.cache/p34-patch32/tests/speed16-r1/result.json` binds the original failed log,
before/after assertion bytes, all source hashes and per-case reuse. Do not call
this a new310-test execution or discard the initial failure.

#### Historical Window8 Preparation

The offline batch `HOST-P34-PATCH-PREP-01` in the installation note prepares AA
30223 and AB 30224 from the measured N04/Y lineage with the opt-in PATCH output
coalescer. These are local development assets, not installed firmware or formal
reference admission. `P34-WAIT-01` still has priority over physical receiver or
window changes. There is no phone operation implicit in preparation.

The manifest is `.cache/p34-patch-next/assets/result.json`: Y-to-AA FULL is
291670 bytes, AA-to-AB compact PATCH is 307 bytes and AA-to-AB pressure PATCH is
exactly 1048576 bytes. Compact is a header-only smoke input, not a normal-update
compression claim. The pressure representation is legal and deliberately
non-minimal, not padding. Both PATCH inputs produce the same AB, so only one
can follow a completed AA. The bootstrap profile is already prepared at
`.cache/p34-session/profile-patch-bootstrap.json`, bound to actual completed Y.
AA-to-AB profiles do not exist until real AA closure/timing is available.

`PATCH_GROUPS` owns the three explicit groups, all s04/921600/window 8.
`patch_asset_groups(group)` loads the bootstrap and only the selected alternative;
`n04_asset_groups(group)` never adds Z to this branch or PATCH to old X/Y.
Attempted alternatives have no automatic successor and cannot replay. A prior
Y-to-Z installation is not the Y predecessor of the prepared bootstrap profile.

`transferMode="full"` still means a complete transfer with `prefixBytes=0`.
ETU type is separately `package_kind`/HTTP `asset.kind`. PATCH metadata requires
the exact raw base SHA-256/version and a `-patch.etu` filename. The context-local
`patch_service` adapter preserves the frozen FULL service, byte identity, token
signing/expiry and Range implementation; a mismatched diagnostic base query is
rejected before signing. `p34_full_trace.analyze()` passes the actual kind to
`install_restore_timing`, which requires exactly PATCH/backup or FULL/backup.
Final success still requires complete target/Boot readback and confirmed state.

The existing APK supports this route. Its capture limits are unchanged:
64 MiB/capture, 1 MiB pending, 256 MiB store and eight directories. The 1 MiB
transfer projection is about 3.75 MB from original Y capture density; it does
not prove queue capacity or free phone storage. Pressure installation cost and
runtime stack peaks remain unmeasured. Keep the existing finite observation
bounds and no-replay rule after a collector failure.

Self-test evidence is `.cache/p34-patch-next/tests/patch-r2/result.json`:
27 new PATCH checks executed PASS, with 209 existing PASS cases reused from the
completed initial batch. The initial batch's two new-path errors/two subtest
failures are preserved at `.cache/p34-session/tests/1790577436378568500/`.
The scope proof binds before-fix hashes and unchanged AST outside `patch_service`
and the one new address test; it is not a fabricated 236-test rerun. Real service
metadata/download/Range were tested through the state object without a listener.
No original source/build/package or device campaign is rerun to repair these
host-only issues. See the installation note and progress table E98-E103 for the
actual build, warnings, immutable packages, failures and physical handoff gates.

### Y-To-Z Window-16 Screening

`P34-LINK-16` in the installation note declares one new finite input group,
`n04-window16/s04`. Use `prepare-window16` to bind actual completed Y, then only
the explicit start with `.cache/p34-session/profile-n04-window16.json`. Do not
start until source-bound host checks and the recording-slot/permission gates
pass. Preparation is host-only and cannot stop an App, delete a capture or send
DATA. It is not automatic authorization for those actions.

Z is 30222 / 3.2.22-p34i, 291526 package bytes, header-only relative to Y. The
manifest is `.cache/p34-session/n04-window16/assets/result.json`; decoding and
four invalid-package gates have passed. Reuse its nonce, N04 executable/MAP/ABI,
Boot and existing APK. Only this group changes s04 to 921600/window 16; all old
group axes and the X/Y asset dependencies remain unchanged. An attempted Z is
latched and has no automatic successor. Preserve both install summaries and
full post-reboot identity; no same-package A/B, 1 MiB or stability claim follows.

The completed-capture selector may now preview X while verified Y is current;
only the original immediate predecessor can be selected. A wrong target is
rejected from the read-only plan before expensive history verification, while
eligible targets still require the whole original chain and an unchanged
descriptor. Apply remains a separately authorized exact phone-copy deletion.

Host checks now write line-buffered `unittest.log` as cases finish. A timeout
preserves `timeout.json`, partial output and the old PASS pointer, with unknown
completed-suite count rather than a fabricated result. The host-only batch cap
is 600 seconds; no device/network/start/active deadline changed. Original
180/300-second failures remain in their own evidence directories. This is not
permission to replay physical measurements or silently promote partial tests.

#### Interface And Validation

`cells_for("n04-window16")` changes only `s04` to `(921600, 16)`.
`n04_asset_groups(group)` preserves X/Y's original two-manifest dependency set;
only window 16 additionally requires Z. `prepare_window16(store)` requires
current completed `n04-measure` plus verified N04 timing, returns
`WINDOW16_ASSETS_READY` with immutable asset/profile records and
`device_operations=0`, and never creates a device run. The profile binds exactly
the original Y run/cell/plan/report. `FULL_SUCCESSOR_GROUPS` owns common lineage
loading; `WINDOW8_GROUPS` no longer conflates that lineage with window-16 axes.

| Input / State | Required Result |
| --- | --- |
| Complete Y, fixed Z, explicit window-16 start | Fresh admission, one full cell, original observation and final identity |
| Old X/Y group | Original window 8 and dependency set; no future Z requirement |
| Missing/wrong Y, missing reconciled timing, mismatched asset | Fail before the affected preparation/device action |
| Wrong cleanup run name | Read-only early rejection; no full historical replay or deletion |
| Exact eligible cleanup target | Full original chain plus unchanged descriptor, archive and path checks |
| Previously attempted Z | Return its original result, including failure; no replay or automatic successor |
| Host timeout | Partial file/console receipt, unknown final count, no PASS-pointer replacement |

Correct: bind the real Y descriptor, retain its capture, and consume Z's frozen
package. Wrong: remove `current.json`, reinterpret an old window-8 group as 16,
regenerate a nonce after partial failure, or turn a host timeout into permission
to repeat OTA. `Window16Tests`, the expanded transition tests and two timeout
tests exercise these boundaries without hardware. The final suite is 209/209
PASS at `.cache/p34-session/tests/1790529686907407300/result.json`.

The exact X preview is
`.cache/p34-session/completed-prune/1790530145775269600/result.json`: 8/8,
zero mutations, original snapshot matched, USB closed. No Z run exists yet.
Its start remains gated by explicit recording-cleanup scope, not by another
unchanged test/build/CI run. The board records the requested boundary and the
exact original X directory; Y App is still retained, last PID 11230.
# Fixed-Y Native Diagnostic (2026-09-28)

## Transfer-Speed Follow-Up (2026-09-29)

The original window32 run `20260929T045644-98600/s04` failed after moving the
completed30225 config into its hash-named archive, when the next ADB read lost
the phone. No native checkpoint, new config, App launch or transfer occurred.
Keep its original failure and closed-owner receipts. `recover-retirement --run
20260929T045644-98600 --cell s04` performs only a fresh private-USB readback:
the original completed capture, absent process/config, exact resolved archive
and bytes, unchanged capture count, and graceful USB closure must all pass.
It neither moves files nor changes current. A passing report can be supplied
explicitly to the normal window32 start using `--retirement-recovery PATH`.
That creates a new linked run and repeats full native/package/producer admission,
not an OTA. Once current advances, the report cannot start another run. Other
failure phases, native/App artifacts, source drift, unknown closure or archive
mismatch reject; normal repeated start remains latched. This exception is not
permission to reset, downgrade, clear data or replay a successful transfer.

#### Retirement Recovery Contract

Scope: only the interrupted completed30225 configuration retirement before
native admission in the window32 group. This does not generalize old failure
receipts into retry credits.

Signatures: `failure(store, run, profile_path)` verifies original host evidence;
`reconcile(store, run)` performs bounded USB readback;
`load_recovery(store, report_path, profile_path)` rechecks the immutable report;
`start(..., retirement_path=report_path)` consumes it by advancing to a new run.
CLI commands are `recover-retirement --run ID --cell s04` and normal window32
`start --retirement-recovery PATH`. The flag is invalid on other commands/groups.

Contracts: success is `RETIREMENT_RECONCILED` with `failed_run`, original `inputs`,
`sources`, `archive`, `observation`, `usb`, `no_launch=true`, `no_transfer=true`,
`phone_mutations=0`, and `mcu_operations=0`. `RETIREMENT_RECOVERY_FAILED` is not a
usable report and returns a failing CLI exit. New evidence lives under
`.cache/p34-session/retirement-recovery/`; private USB reuses the existing
contained home/AppData/temp/Android paths and read-only ADB key. Native-history
permission remains separate. The new plan binds `retirement_recovery` by hash.

| Validation / error | Required behavior |
| --- | --- |
| Original move succeeded; following read lost phone | Admit readback only after exact plan-intent, predecessor and closed-owner checks |
| Native/config/provision/launch artifact exists | Reject this recovery route; preserve and reconcile the actual operation |
| Config absent, App absent, original snapshot/count and archived bytes match | Produce a source-bound report without moving/deleting/launching anything |
| Archive mismatch, new process/config/capture, unresolved USB closure | Fail without a reusable report |
| Explicit report, same failed current owner | Fresh linked run, full admission, unchanged package/nonce/window; old failure retained |
| Source/evidence drift or current already advanced | Reject rather than replay; ordinary repeated start remains latched |

Good case: archive succeeded, fresh USB confirms its exact bytes, then a new
owner is admitted explicitly. Base case: no recovery flag preserves the original
attempt latch. Bad case: use an old report after another run advanced current.
`RetirementRecoveryTests` covers these cases, native/App markers, unknown owners,
changed phone state, archive mismatch, closure, command scope and one-owner
consumption. `Window8Tests` enumerates all groups with explicit16/32 expectations.
Wrong: rewind `current.json` or rerun `mv` because a later read failed. Correct:
preserve that receipt, verify the resulting state, then use the bound report.

Window16 has now completed as `20260929T030709-75800/s04`, retaining 30225;
its cell and network owners are closed. Use `prepare-speed32` for the newly
declared one-cell 30225-to-30226 successor, then only the explicit
`start --group speed-window32 --cell s04 --profile .cache/p34-session/profile-speed-window32.json`
after current source-bound tests, permissions and recording-space admission.
This preserves the N04 executable, original Boot/APK and old groups' axes;
new `s04` requests 921600/window32 and remains limited by device credit/4KiB.
The write-once new package is 291496 bytes. No attempted32 run has an automatic
successor or replay; preparation and capture eligibility do not grant deletion
or native-history permission. See the installation note's Speed32 section for
the finite matrix, current exact boundaries and original16 completion evidence.

The new host contract is `prepare_speed32(store) -> SPEED_WINDOW32_PREPARED`
with immutable `profile`/`assets` records and `device_operations=0`.
`cells_for(SPEED32_GROUP)["s04"]` is `(921600, 32)`; its only admitted predecessor
is the fully reconciled, closed `SPEED16_GROUP`. Old group asset dependencies
exclude the future32 manifest. Profile flags must explicitly select32, disable
native epoch diagnostics and retain QUIC. Sources include the new tests.

| Validation / error | Oracle |
| --- | --- |
| Completed16, exact successor, explicit32 | Prepare/reuse identical package and profile; a later start performs fresh admission |
| Wrong/missing predecessor, incomplete result or open owner | Reject before preparation/device mutation |
| Reused assets | Same nonce/bytes; no packer, build or device call |
| Existing attempted32, successful or failed | Return its original status; no replay or automatic successor |
| Wrong axis/profile flags | Reject rather than quietly testing another group |
| Cleanup candidate | Only original Z selected under protected30225; eligibility is not deletion permission |

`Speed32Tests` exercises those cases plus executable/MAP/Boot identity, known
staging exclusion and source pins. The first affected batch executed58 checks
and reused220 unchanged cases. Do not replace the predecessor/current pointer
to force another OTA; use a new explicitly declared legal successor instead.

Completed-capture archival also admits one optional `health.json.tmp`, the
producer's atomic-write temporary. It must be at most8192 bytes and identical
on two reads; archive its original bytes as opaque diagnostics. The normal
health and exact finished snapshot remain the only completion evidence. The
scoped `pending_health_bytes(p, package, remote)` uses stat plus a bounded read
and supports zero bytes; it does not weaken the retained nonempty-file primitive.
Unknown
filenames, multiple snapshots, changed/oversize pending files still fail closed.
Preview never deletes; apply still needs explicit directory authorization,
stopped App, resolved path and exact remaining-directory checks. Two new tests
plus six affected checks cover the fix; the original failed preview is retained.

`prepare-speed16` derives only the legal target header/package for a full
`speed-window16` screen from the actual completed Z owner. It does not compile
firmware or an APK. Use the generated `profile-speed-window16.json`, explicit
`--group speed-window16 --cell s04`, and the normal start/collect/stop lifecycle.
The target is 30225, retaining the N04 executable and original Boot at
921600/window 16. The profile keeps the working QUIC service route but does not
require native epoch logs, whose old full-record timing failed validation.

Compare with the existing Y/Z window-8 N04 receive records as sequential
screening, not strict same-package A/B. No automatic successor or replay is
enabled. Exact completed-predecessor cleanup can now select Y under protected
Z; that selection is not permission to delete it. Record each needed directory
authorization and archive verification before `--apply`.

`prepare-diagnostic` binds the actual completed Y to the existing immutable Z
asset without rebuilding it or editing `profile-n04-window16.json`. Use explicit
`--group n04-diagnostic8 --cell s04 --profile .cache/p34-session/profile-n04-diagnostic8.json`
for the new `start`. This is 921600/window 8, not the paused window-16 experiment.

The group owns an exact-PID `[FBP-Android]` logcat reader before user connection
and queries, capped at 16 MiB/2600 seconds. `android-trace/query.json` must show
FFF2 write-success and FFF1 notification markers before READY. No marker means
no invitation to transfer; it is not a reason to repeat a successful OTA.
Original logs, bounded reader closure and the existing App/MCU evidence remain
separate. Native epoch and App stopwatch are not synchronized, and a local
without-response write callback is not a durable ACK. The Android trace needs
separate packet/count correlation before any causal performance conclusion.

This extends the existing finite device plan, not cleanup authority or formal
acceptance. Preserve Y/R and archived X; any subsequent deletion needs its exact
scope. Installing Z invalidates the previously prepared Y-bound AA bootstrap.

`recover-network --run RUN --cell s04` is restricted to a closed diagnostic
network failure before any device-cell directory/runtime exists. It also checks
the original profile, verified Y predecessor, HTTP/2 timeout and affirmative
QUIC precheck before preparing a separate QUIC profile and restoring only the
host current pointer. It cannot recover an attempted OTA or uncertain closure.

The actual Z run completed at `20260928T144139-55600/s04`. Native query markers
worked, but the full epoch log contained backward timestamps. Its successful
collector receipt is not a valid native latency result. Preserve that log and
use producer-side monotonic time/packet identities in future instrumentation;
do not replay Z or "repair" its timestamps. Current retained firmware is Z.
