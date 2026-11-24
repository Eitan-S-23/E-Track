# Cross-Block Pipeline Prototype

Owner: Codex root. User approved the larger cross-block direction after pausing
the early-erase experiment. Writable root: D:/github/my/E-Track. Device remains
group16/C30278 from the previous full readback; no MCU operations in this batch.
The phone's debug APK update is reconciled below.

## Status And Scope

Implemented a default-off C receiver/session and the actual Dart sender transport.
The measured-baseline Dart integration passed both development CI hosts, most
recently at `db4f007bf63b43b7c89e2798b88af41fd1a903bd` on
`dev/flutter/p34-pipeline-link-20261007`. The final debug APK is installed and its
raw hash verified. Full firmware integration/build and two legal packages are
complete, but no new MCU firmware is installed or measured. Current MCU admission
and the observation route precede any OTA; CI is not throughput evidence.

Current screening decision: reuse the existing synchronous staging erase/write
port under `P34_OTA_PIPELINE_SYNC=1`, preserving its XIP restore-before-return
lifetime. Two-block credit allows UART ISR reception during blocking IO; parsing
does not run during that call. This is PARTIAL OVERLAP, not an asynchronous QSPI
implementation. The old vendor XIP routine has unbounded internal waits; the
pipeline's cooperative deadline cannot interrupt a blocking callback. No new
driver timing guarantee is claimed. A true async adapter would require excluding
all UI/task/IRQ XIP readers and is deferred pending this screening result.

The sync port uses one existing block write, not 16 separate XIP restorations.
V2 ACK length is 27 bytes: retain the measured 2 ms/12-frame ACK batching policy
with length-aware buffering, instead of inadvertently sending each ACK separately.
The sender physical cap is 24 rather than the baseline's 28. Preserve batch12,
GATT reuse and PHY/reboot settings from the measured APK; disclose these axes.

The C core uses two alternating 4 KiB payload buffers, one reusing the existing
staging receiver's block. The supplied asynchronous port owns a source pointer
until it returns a quiescent result. While the previous block erases/programs,
the next block can be accepted into the other buffer. Third-block reception is
rejected until a verified journal commit frees capacity.

Reuse: BEGIN/session journal loading, full payload readback, persistent bitmap
arbitration and finalization remain in `ota_staging.c`. The new default-off
`ota_staging_commit_buffer` verifies bytes and commits the existing journal
without clearing a buffer that the pipeline may be filling. It does not erase
or program payload and cannot commit an offset beyond the durable frontier.
Readback/journal calls still use the existing synchronous port. The selected sync
screening adapter also reuses blocking payload IO; it does not bound the vendor's
unbounded internal XIP waits or expose an asynchronous hardware lifetime.

## API And Ownership Contract

- `ota_pipeline_begin(pipe, store_io, payload_io, epoch, sha256, total_len)`:
  zero-initialized storage, nonzero epoch, unchanged ETU size bounds. Restores
  only the verified persistent prefix. Returns BUSY while hardware owns memory.
- `ota_pipeline_receive(pipe, epoch, offset, data, len)`: ordered 128-byte segments,
  final segment may be short. Gaps, wrong epochs and capacity violations have no
  receive side effects. Same-content volatile duplicates are idempotent; conflicts
  stop the pipeline. Durable duplicates do not rewrite Flash.
- `ota_pipeline_poll(pipe, now_ms)`: one bounded transition or port poll, not a
  busy-wait loop. Erase, 256-byte program pages, full readback and journal commit
  are ordered. Unsigned elapsed arithmetic handles tick wrap.
- Payload port `start/poll`: OK = quiescent success; BUSY = retains ownership;
  negative = quiescent failure. `cancel` is a request, NOT proof of quiescence.
  The 4000 ms operation deadline requests cancellation once and rejects further
  DATA; the caller must continue settling before freeing/reusing the overlay.
  A port that never settles blocks release, never fabricates safe completion.
- `ota_pipeline_can_release` protects hardware pointer lifetime, not completion
  or success. A session owner must also check terminal state/durable identity.
- The real C session now applies ETU admission, frame CRC, epoch/session/sequence
  validation, incremental package SHA/CRC, resume-prefix rehash and existing
  finalize/activate hooks. Host hooks model activation/reset; real package apply,
  boot and phone-side reboot identity verification have NOT been exercised.
- Session init is a one-time owner operation, not a live-cancel API. During
  DRAINING, keep calling the pump and retain the overlay/ISR ring until the
  payload port returns quiescent. `ota_ble_session_active()` includes DRAINING.
  No replacement BEGIN, mapped INFO read or legacy ABORT may bypass that hold.

## Prototype Payloads

These are development wire extensions, not amendments to frozen v1. C and Dart
framing, negotiation and pre-admission v1 fallback are implemented and host-tested.

CAPS (16 bytes): `P2BL`, u8 version=2, u8 slots=2, u16 segmentBytes=128,
u32 echoed nonzero nonce, u32 maxInFlightSegments=24. All integers little-endian.
CAPS does not open a session or grant credit. Dart rejects wrong nonce, magic,
version, capacity and length. Missing/unsupported capability must retain v1;
connection/session validation must precede enabling a pipeline generation.

ACK credit body (16 bytes): u32 epoch, u32 durable_off, u32 accepted_off,
u32 credit_end. Invariants:

    0 <= durable_off <= accepted_off <= credit_end <= total_len
    credit_end = min(total_len, durable_off + 8192)
    durable_off is block-aligned unless equal to total_len
    accepted_off is segment-aligned unless equal to total_len

The sender also requires `accepted_off <= submitted_off`. Reservation happens
before asynchronous physical writes so early callbacks cannot create untracked
credit. Inconsistent/malformed snapshots cancel the sender generation; stale
epochs and coherent older snapshots cannot roll progress backwards. Accepted
RAM bytes never drive durable progress or final success.

The v2 DATA carries an epoch word in addition to the existing offset and
128-byte payload. Its 146-byte frame makes 28 frames occupy 4088 of
4095 ring bytes. Therefore this prototype explicitly caps physical in-flight
DATA at 24 (3504 bytes), leaving control-frame headroom. This differs from the
old 28-segment cell and must be recorded in future comparison inputs. Two-block
receive credit is separate from this physical outstanding-frame limit.

### C Wire And Lifecycle

All frames retain the existing sync/header and CRC16 envelope. Multi-byte fields
are little-endian. V1 DATA stays capped at 132 payload bytes even when the v2
parser is compiled. Unknown commands and all upstream commands remain rejected
by the downlink parser.

| Command | Payload | Reply |
| --- | --- | --- |
| CAPS2 `0x10` | nonzero u32 nonce; session=0 | `0x90`, the 16-byte CAPS body above |
| BEGIN2 `0x11` | existing 101-byte BEGIN with proto=2, then u32 epoch; session=0 | `0x91`, u8 status, u8 session, 16-byte credit body |
| DATA2 `0x12` | u32 epoch, u32 absolute offset, 1..128 payload bytes | `0x92`, u8 status, 16-byte credit body |
| END2 `0x13` | u32 epoch, 32-byte package SHA | `0x93`, u8 status, 16-byte credit body |
| ABORT2 `0x14` | u32 epoch | `0x94`, u8 status, 16-byte credit body |

CAPS is accepted only while idle, with a complete payload port, and does not
allocate overlay or touch staging. BEGIN must use its negotiated nonce as epoch.
The most recently used epoch cannot be reopened; the future sender must choose
a fresh nonzero nonce on every connection/session generation. An exact active
BEGIN retry keeps the original begin seq, epoch, length and package SHA and
returns current credit without reinitialization or platform IO. A replacement
while active/draining is BUSY, not an implicit abort.

DATA seq is fixed as `(begin_seq + 1 + (offset - resume_off)/128) mod 65536`;
END seq is `begin_seq + 1 + ceil((total_len - resume_off)/128) mod 65536`.
Retries must retain the original seq. Gaps, wrong seq/epoch/session and malformed
lengths do not consume sequence or receive credit. Conflicting volatile
duplicates terminate; identical duplicates do not rehash. Only verified journal
commits update durable progress and emit extended credit. Valid duplicate traffic
cannot defeat the separate 30-second no-durable-progress watchdog.

ABORTED for ABORT2 is sent only after the outstanding payload operation settles;
errors stop new reception immediately but do not free pending buffers. An early
END cannot erase a SHA-error journal while payload hardware is busy. Error ACK
snapshots are informational only and must not grant sender credit; failed BEGIN
or unauthenticated frame errors can carry zero epoch/progress. Stale v1 controls
are ignored during v2, including INFO (which might invoke mapped Flash reads).

Any future cooperative adapter still must exclude ALL external-XIP users across BUSY
intervals, settle physical operations on error/cancel, and use consistent macro
definitions across C/C++ objects. These are unimplemented hardware requirements,
not properties proved by the C fixture or the presence of callback declarations.

## Executed Checks

Evidence: `.cache/p34-pipeline1/`.

| Check | Result | Boundary |
| --- | --- | --- |
| First C receiver batch | 688 checks PASS | `tests1/result.json`; prior core before payload codecs/expanded faults |
| Expanded C receiver batch | 3218 checks PASS | `tests2/result.json`; includes 114 existing staging checks |
| Exact R2 GCC flags, ARM objects | PASS, 0 warnings/errors | `arm1/result.json`; not a complete firmware link |
| ARM receiver and overlay | 8336 + 4096 = 12432 bytes of 40960 | Both payload buffers aligned; actual compiled layout |
| Disabled staging object | Byte-identical to R2 | Original and current source compiled with identical admitted flags |
| Prior default regressions | 114 staging / 171 session checks PASS | `default1/result.json`; before the session extension |
| Real session extension, first passing batch | 348 checks PASS | `session2/result.json`; includes 171 original v1 checks |
| Real session extension, final batch | 372 checks PASS | `session3/result.json`; includes 171 original v1 checks; separate disabled build also passes 171 |
| Current session ARM objects | PASS, 0 warnings/errors | `arm-session1/result.json`; no full firmware link |
| Current ARM layout | session 632B, env 52B, max frame 146B, overlay 12432B | Compiled constants, not a whole-program stack bound |
| Disabled frame/ring regression | 39 checks PASS, 0 warnings/errors | `frame2/result.json`; original frame/ring suite |
| Dart measured-baseline transport | PASS on both hosts | Run 37591312719; Ubuntu 686 pass/16 skip, Windows 669 pass/33 skip; zero failures |
| Sync port/session | 258 checks PASS | `sync1/result.json`; includes 171 legacy checks, ring blackout and six physical-operation failure/resume cases |
| Current C regressions | PASS | `session4/result.json`: default 171, cooperative 372; `sync2/result.json`: sync 258 |
| ACK batching | PASS in v1 and v2 | `ack1/result.json`; 12-frame boundary, 2 ms deadline, mixed lengths, durable flush, FIFO bytes |
| Complete GCC App | PASS | `fw-on/result.json`: 622884B; `fw-off2/result.json`: 619580B, byte-identical to saved R2 build |
| Full build diagnostics | 641 warnings, 0 errors per mode | Existing 639 plus wchar_t link warnings for two added objects; not a zero-warning build |
| Exact target ABI | 632B, 21 fields derived | `layout1/result.json`; actual candidate flags, not inherited R2 offsets |
| Forward packages | Native decode and four rejection cases each PASS | `assets2/result.json`: bootstrap 30278 to 30281, 296354B; measure 30281 to 30282, 296357B |
| Current Dart/APK | PASS | Run37604830571; Linux688 pass/16 skip, Windows671 pass/33 skip; zero failures; Android debug APK built and verified |
| Windows EXE | NOT_RUN | Not included in the development workflow; no release/EXE authority inferred |
| Hardware throughput | NOT_RUN | No pipeline installation, OTA or new timing sample |

Expanded tests cover each erase/page operation across three full blocks and the
short tail, faults before/partway/after physical success, pending buffer lifetime,
third-block rejection, stale epochs, duplicate conflicts, timeout/cancel/tick
wrap, readback/journal uncertainty, and 240 reset cut points with both readback
implementations. Resets retain only simulated NOR; no host test operates a board.
C and Dart tests contain the same CAPS/ACK payload vectors and have now executed
on both sides. This is not a physical MCU/phone interoperability measurement.

The session fixture additionally tests real byte-fragmented frames, capability
admission, third-block rejection while erase is held, seq wrap and offset binding,
stale epoch/session/v1 controls, resume-prefix SHA/CRC, final digest rejection,
delayed ABORT, conflicting duplicate/early END/timeout drain, and uncertain
physical results for the erase and all 16 pages of a full block. Synchronous
staging IO is forbidden by the fixture while a payload operation is pending.
The 24 command-length boundary checks also preserve the smaller v1 DATA limit.

`session1` preserves a failed 120-second run: the inherited native fixture's
workspace was not 8-byte aligned, so v2 admission rejected it; a later fixture
loop lacked a finite stop. The repaired test uses an explicitly aligned union
and a bounded loop. The production alignment guard was NOT weakened. There was
no device operation. `session2`/`session3` are the subsequent successful runs.
`frame1` preserves the original fixture's MSVC C4701 warning-as-error on the
roundtrip output struct. Explicit zero initialization removed that diagnostic
without weakening parser assertions; `frame2` passes all 39 checks.

## CI Access, Source Binding And Remaining Work

The earlier Windows keyring failure is historical (`ci-access/failure.json`).
The user supplied a private project-local token input; actor Eitan-S-23, repository
ID 1310649784 and workflow ID 353793017 were verified. Access works. No global
credential configuration was changed. Never print, hash into evidence, archive,
copy, commit or upload the credential input.

Source binding matters: root Flutter files are older dirty P3-4 work, not the
measured APK. Authoritative candidate files are in `.cache/p34-pipeline1/link-src/`
and the full tree is in the dev branch above, based on measured source
`b6e6e32df1fdf5418aa94ba6ac858256e8ef9066`. Root integration prototypes are not the
tested artifact and must not replace it. Shared root HEAD/index were unchanged.

CI runs: model-only 37586561030 passed; first transport run 37590430897 failed
(required timestamp argument and five lint findings), then the corrected transport
run 37591312719 passed. Preserve failed receipts, do not describe the whole batch
as error-free. Original logs: `ci-model1/original-logs/`, `ci-link2/original-logs/`.
Both successful integration hosts used Flutter 3.47.6 / Dart 3.13.5, framework
`5fc346839b5d0eef006ed8404392afb4dfae428d`. Windows EXE NOT_RUN, APK NOT_REQUESTED.

Sender implementation retains the measured serial writer and batch callbacks,
uses durable-only progress and a fresh epoch per attempt. V2 ERR_STATE/ERR_SESSION
terminate instead of v1's in-place ABORT+BEGIN recovery; fresh-attempt durable resume
is supported. Keep this limitation explicit. Background without runtime ownership
still stops safely. Missing CAPS can fall back before v2 admission, not afterward.

Next: collect the corrected debug APK, verify its same-signer installation,
prepare original collectors/retrieval and current MCU admission, then screen.
Do not begin a device window with a fake port, a silently disabled APK, or the
paused early-erase assets. Group16 Boot remains unchanged.
Keep old peers, journal/readback/CRC/SHA, rollback and final identity checks.
The prior 12-13.5 s / at least 30% throughput target remains a screening target,
not an achieved or predicted result.

Full-link follow-up: `fw-off` compiled but failed the byte-identity check because
the prototype changed the private v1 BEGIN ACK argument from sequence to frame.
Only the session object differed. Restoring the disabled private ABI produced
`fw-off2` with exact R2 bytes; no hardware operation was involved. The enabled
App adds 3304 bytes. Its ELF/bin extraction agrees; Boot was not rebuilt.

`assets` preserves a first preparation attempt: bootstrap encoding/native checks
passed, but target binding rejected the inherited 576B R2 session layout. The
guard was not weakened. Compiling the existing ABI probe with the actual candidate
flags derived the 632B layout, and `assets2` uses those offsets. Package sizes
differ from the 294068B reference; compare normalized throughput, not identical
package A/B claims. Neither package has been installed.

## Current APK And Finite Device Plan

The explicit `runtime-pipeline` development APK option injects both
`OTA_P34_RUNTIME_CONFIG=true` and `P34_OTA_PIPELINE=true`. Baseline/runtime APK
options still leave the pipeline off. This only changes the owned development
branch workflow, not main or production release. The first explicit APK run
37598134153 at `c3c94dc9c1d67fb569170fbe45ac026bccc091cf` passed but is superseded
before installation: END timing was recorded before sequence/status/full-credit
validation. It must not supply the screening measurement.

The repaired sender preserves the matched waiter's original arrival timestamp
and records it only after successful END validation. Tests cover an unrelated
later END ACK, delayed write settlement and incomplete END. Run 37602237480
passed its tests but failed analyze on the now-unused `ackEnd` constant. Removing
that constant produced commit `db4f007bf63b43b7c89e2798b88af41fd1a903bd`:
checks run 37603644809 and explicit APK run 37604830571 both succeeded. Raw APK
and report collection is under `ci-apk5`; Windows EXE is not requested.

`ci-link4/commands.jsonl` retains a Schannel TLS failure before any Git commit
or remote mutation. The same scoped submission then succeeded using Git's
OpenSSL backend with normal certificate verification, no global Git changes.
A later read-only urllib status query also hit TLS EOF; standard GitHub CLI
queries recovered. Neither event is a device failure or renewed credential block.

Read-only phone check (`phone-inspect1/result.json`) confirmed original serial,
awake state, installed APK SHA matching the measured baseline, unchanged runtime
config and the intact completed group16 capture (8940 records, zero lost, healthy).
Awake is not a claim that Android keyguard is unlocked. No App launch, install or
OTA ran in that check. Private ADB closed normally with the source key unchanged.

| Field | Planned bounded scope |
| --- | --- |
| Owner and authority | Codex root, existing authorized P3-4 board/phone; no agents; writable project root only |
| APK | Exact db4f007 development APK, same `.p34probe` ID and pinned development signer; preserve config, permissions and original completed capture |
| MCU admission | Fresh group16 Boot and C30278 identity/health before bootstrap; standard SEGGER only; no supply interruption |
| Bootstrap | One legal full 30278 to 30281 package; old receiver falls back to v1; this installs the pipeline and is not its speed result |
| Screening | After verified bootstrap, one full 30281 to 30282 transfer; same executable outside version header; explicitly verify v2 and effective physical cap24 |
| Axes | Keep baud921600, batch12, GATT reuse, PHY and reboot policy; v2 146B DATA/cap24 differs from baseline 142B/cap28 |
| Oracle | Verified target raw image/Boot, durable progress, no overflow/recovery/integrity failure; normalized throughput at least 30% over 16.819722 decimal kB/s |
| Measurement | New package296357B; approximately13.55s meets the normalized throughput screening threshold, not a forecast or identical-package A/B |
| Recovery/stop | Preserve failures; read current state first; no blind OTA repeat or App-only downgrade across changed BCB; retain verified successor |
| Human action | No automatic UI taps; invite Start only after actual query/package/collector readiness |
| Runtime | Existing finite USB/network/coordinator and postcheck deadlines; no new default one-shot permission quota |

Under the newly supplied project-external write rule, current-turn permission
was requested for J-Link's native history/config updates inside
`C:/Users/SU/AppData/Roaming/SEGGER/` (principally `JLinkDLL.ini`), with no cleanup.
Old task-note permission references are not treated as a new filesystem grant.
The user subsequently answered "允许，以后同类授权都允许". The same automatic
history/config updates are now standing-authorized in that exact directory;
cleanup, adjacent directories and expanded device operations are excluded.
The decision is recorded in AGENTS.md and the device experiment policy. No
J-Link process had run at that approval checkpoint. Firmware, logs, readbacks,
caches and packages stay in the project.

### Installed APK And Reconciled Timeout

Final APK: 131680786 bytes, SHA256
`0480434aeb4dd0845aca04b9ce91fc33abe6f578dcee6f6487955e0bb4a3a175`.
`ci-apk5/apk.json` binds original reports and the actual fixed signing certificate.
Both hosts used Flutter3.47.6/Dart3.13.5 and framework
`5fc346839b5d0eef006ed8404392afb4dfae428d`; Ubuntu688 pass/16 skip and
Windows671 pass/33 skip, zero failures. APK PASS; Windows EXE NOT_RUN.

The existing same-signer installer passed its four host guard tests and input
validation. `install1` issued one `adb install -r --no-streaming`; the host command
timed out at180s. The original failed result is preserved, not rewritten as PASS.
Its worker exited normally with error, and private ADB closed with the original
key unchanged. No uninstall, data clear, App launch, OTA or MCU operation occurred.

Read-only `install-reconcile1/result.json` subsequently verified that the exact
new APK WAS installed, original config and all archived capture bytes remain
identical, and Bluetooth scan/connect permissions are granted. Its USB server
also closed normally. No second install was attempted. The timeout is a host
completion-observation failure with reconciled installed state, not proof of a
failed Android install. The App remains unlaunched by this agent.

Current C core was rerun after the disabled-ABI repair: `tests3/result.json`
passes3218 checks. Linked overlay is at0x20058000, length40960, aligned8; session
is632B. New pipeline poll and sync callback stack frames are48B and16B; the
inlined session parser frame is384B. These are individual compiler `.su` values,
not a whole-program or runtime stack high-water proof.

Remaining: fresh current MCU readback/health (native-history boundary permission
now granted), complete v2-aware observation/retrieval binding, bootstrap, target
postcheck and screening. No new measured speedup exists. Root HEAD/index and
main were not changed; firmware changes and task notes are still local, while
the sender is preserved on the named development branch.

### Permission Follow-Up And Live Checkpoint

After the standing SEGGER native-history approval, standard Commander V8.18
verified the actual board (`current-device1/result.json`): complete619580B App
matches C30278, full64KiB group16 Boot matches, flags0x010104, App VTOR, SD ready,
zero CFSR/HFSR, no observed halt, idle BLE session, and advancing health over30s.
No reset, Flash programming or supply interruption was commanded. Commander
still performs its normal debug-connection register writes; "read-only" describes
the requested memory acquisition, not a claim of zero SDK register side effects.
Native configuration before/after records are retained under the authorized
SEGGER directory exception; no external cleanup was performed.

`observe.py` reuses the existing standard Commander invocation and derives health,
profile and session addresses from the exact asset map/ABI. `observer-tests1`
passes9 host checks, including CRC-corrupt, truncated, out-of-credit and incomplete
v2 END rejection. The prepared240-sample trace brackets RAM reads with receiver
header/VTOR checks and preserves validated v2 credit frames plus the frozen END
profile. This trace has NOT run; no live capture readiness or v2 negotiation is
claimed from these host tests.

`trial.py` reuses the R2 phone/USB/network collectors and original finished-snapshot
validator, binding the reconciled final installed APK rather than the old APK.
`bootstrap/check2/result.json` passes offline sender/target checks. The served
filename is corrected to `p34-pipeline-bootstrap-full.etu`, as required by the
actual App contract; the immutable package bytes are unchanged. Runtime schema9
requests28 segments; the compiled negotiated v2 transport clamps actual physical
in-flight DATA to24. Preserve that explicit difference from the v1 baseline.

The new bounded phone inspection (`bootstrap/inspect-state/result.json`) returns
PHONE_NOT_READY: eight original ADB get-state queries report the original phone
serial absent. Windows connected-device enumeration also lacks VID2D95/original
serial while the J-Link remains present. This is not an APK-install failure or
an OTA failure: neither App launch nor OTA ran. Private ADB closed normally,
port5062 closed and its original key is unchanged. The supervisor exited normally;
its exit0 does not override the semantic PHONE_NOT_READY result.

Required human action: reconnect/unlock the original test phone and acknowledge
USB debugging if prompted, without touching J-Link. After actual reappearance,
use a fresh inspection/output binding, not a replay of consumed `inspect-launch`.
Then verify observation-store space (archive only an exact older completed capture
through the existing route if full), establish live package/query/native capture,
and invite Connect/Start. Bootstrap30278->30281 and screening30281->30282 both
remain NOT_RUN. The paused early-erase campaign stays paused. No new measured
speedup, production publication, commit or mainline change is claimed.

### Phone Reconnected, Pipeline Receiver Installed

User reported ready; Windows and private ADB verified original phone10ADA4197U001CK
and final APK0480434a. `bootstrap/inspect-state2` retained the original complete
group16 snapshot. Eight capture slots were occupied. The existing archive worker
copied and moved exactly the older completed R2 capture, preserving current
configuration and latest snapshot; no deletion or reinstall occurred.

Bootstrap30278->30281 EXECUTED: original `bootstrap/trial/cells/s04/finished/snapshot.jsonl`
is complete,9046 records, zero loss. App reports target30281/rawSHA
`223e28ac7718b0266f84baa773946e8bc48ee2079b81f6e5e995950d7d606ac0`.
Matched App statistics: BEGIN-to-END17.806480s,2316 DATA segments, zero retransmits,
complete ACK samples. Reconnect phase33.740039s includes failed/abandoned probes;
do not call the entire session error-free. This was v1 bootstrap, not pipeline
speed measurement. `bootstrap/trace/analysis.json` preserves a stable receiver-bound
END profile, clean UART/ring/parser counters and no v2 ACKs, as expected.

`bootstrap/postcheck/result.json` verifies all622884 App bytes, unchanged complete
group16 Boot, confirmed flags0x010104, SD ready, zero fault status, idle BLE and30s
advancing health. The pipeline receiver is now installed and retained. All
bootstrap coordinator/network/USB owners closed normally. No J-Link programming,
explicit reset, Boot change or supply interruption was used.

Measurement30281->30282 remains UNSTARTED at the latest live checkpoint. Its exact
296357B package, APK and target bindings pass `measure/check3`. After another
exact older-capture archive, `measure/trial` failed before any App launch/OTA:
six valid NXDOMAIN replies exhausted the inherited roughly12s DNS window. Its
failed receipts and normally closed resources remain intact. `measure_resume.py`
only classifies this exact validated-DNS exhaustion as transient for the existing
0/15/45/90s readiness schedule; six host checks preserve TLS/malformed fatal
behavior and finite exhaustion. No system DNS change. `measure/trial-dns` then
verified its new HTTPS service and unchanged package on its second readiness
attempt. No bootstrap, successful archive or APK installation was replayed.

Actual measurement App PID30726, capture1791378145846839-3ab41c21c29d90b45a3211a6,
is READY_FOR_FULL_INSTALL_START with verified query/download bytes. Runtime
schema9 requests28; negotiated v2 remains physically capped24. As of the last
poll, upgradeStarts=upgradeEnds=0, healthy=true, lost=0. User must tap Start for
3.2.82-pl while keeping App foreground; no automatic tap is authorized.

Native observation limitation: `measure/trace/console.json` retains a360s host
timeout before the user started OTA. The old fixed240-sample schedule did not
finish within its allowance. No final measurement is inferred from it. A premature
readiness probe also found no first sample yet; the subsequent real bracketed
sample passed. `live_trace.py` now uses the same standard Commander/read-only
commands through stdin, one completed sample at a time, with a1200s total bound
and early normal `qc` when the original App collector finishes. It is a small
sampling/lifetime adapter, not a Flash implementation or replacement SDK. Its
initial missing-module import failed before outputs/device operations and was
corrected to the existing `p34_batch_trial.clone`. Live receiver-bound readiness
is recorded in `live-capture/measure/trace/ready.json`; closure/analysis are still
pending. Do not edit source-pinned live helpers or repeat this invocation.

Next on actual completion: retrieve the existing finished snapshot, let the native
reader close, run `observe.py postcheck --arm measure`, then `analyze.py`. The
analysis selects `measure/trial-dns` and `live-capture/measure/trace`, not the failed
attempts. It compares the same matched App start/end statistic fields on both
sides, labels reconnect separately, and does not compare v2 durable-only ACK P99
against v1 volatile bitmap ACK P99 as equivalent. If no Start arrives, reconcile
normal expiry before opening a fresh window; never replay a successful OTA for
missing host evidence. Production integration/commit and hardware speedup remain
unclaimed pending the actual screening result.

### Screening Executed: Benefit Observed, Not Fully Accepted

The user completed30281->30282. Original App snapshot
`measure/trial-dns/cells/s04/finished/snapshot.jsonl` is1072447B, SHA256
`238b0516d9bc8653aae99ab0d778a64bd6a5323e7e70357211d569a35a825db8`.
Its original footer hash/counts, ordered sequences, one completed invocation,
APK sentinel/PID, package/config and before/after identities were checked without
rewriting the snapshot.9492 records,9489 producer lines, zero capture loss.

`screen-result1.json` records the same matched App statistics on both sides:

| Metric | Previous group16/v1 | Pipeline single screen |
| --- | --- | --- |
| Legal package bytes | 294068 | 296357 |
| BEGIN write to validated END arrival | 17.480900s | 13.814972s |
| Decimal throughput | 16.822246kB/s | 21.451871kB/s |
| DATA retransmissions | 0 | 0 |
| Valid ACK sample count | 2298 | 2316 |

Observed transmission saves3.665928s (20.971% less time). Package-normalized
throughput improves27.5209%, below the30% screening target. The older headline
17.483523s used global MONO markers; this comparison deliberately uses the same
matched statistics fields for both runs, not a mixture. Reconnect phase is
17.451528s, not an exact END-to-identity measurement or exclusive Boot apply time.
One failed discovery probe remains in the App log. No identical-package A/B,
reliability,1MiB or soak completion is claimed. V2 ACK latency is durable-only
and must not be compared directly against v1 volatile bitmap confirmation.

Actual DATA batch bytes338045 equal296357 +2316*18, matching v2 framing rather
than v1's14B overhead. This is sender wire-byte/path evidence with bound compiled
artifacts, not a recovered original CAPS/MCU-credit capture. Final standard
Commander readback (`measure/postcheck/result.json`) matches all622884 bytes of
30282/rawSHA `d973f6d517ca6cc28e0434ac870da4b4bd04778c4ce56dbbcb08edaa2c0100f3`,
unchanged full group16 Boot, confirmed flags0x010104, SD ready, no fault/halt and30s
advancing health. The verified successor remains installed. No repeat OTA/reset,
Flash programming or supply interruption was used for this reconciliation.

Two unfinished observation issues prevent a complete acceptance claim:

- The old full-snapshot validator requires v1 `MONO_BUDGET_START` and
  `MONO_END_ACK_OK`. The new pipeline path emits its matched transfer statistics
  but not those markers. Its original `R2_OTA_INCOMPLETE`/CaptureError receipt
  remains failed; it is not evidence of failed physical installation. A separate
  scoped raw-integrity/statistics record is not a retroactively green acceptance.
- The replacement native reader has no closure receipt and its359 saved samples
  contain no receiver-bound terminal profile or v2 ACK. No debugger remains in
  the current Windows process inventory, but graceful closure is not proved.
  `live-capture/measure/trace/analysis.json` explicitly records the measurement
  gap. Runtime UART/ring-drop counters for this transfer remain UNKNOWN. Do not
  infer zeros from post-reboot counters or repeat a successful OTA to replace logs.

The implementation has a useful single-run speed improvement, but the entire
optimization task is not closed: observation compatibility/lifecycle, integrated
source and commit consolidation, and repeatability/acceptance remain unfinished.
No new commit or push was made in this result-reconciliation turn.
