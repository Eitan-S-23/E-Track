# OTA Companion And Admin Scroll Investigation

## Scope

User-reported baseline: Android 1.0.85, MCU 3.3.35, target 3.3.36.
The device-originated update disconnects and returns to the phone-connection
prompt. The App remains in reconnect/identity verification while the MCU keeps
running. Investigate both entry points without assuming a reset or deadlock.

The Admin scope includes both App/MCU delta dialogs, announcements and an audit
of other nested scrolling containers. Preserve modal background locks and
gesture/focus ownership. No redesign, channel changes or package regeneration.

Active root: `D:/github/my/E-Track`, primary main `1d05da5a` matched to remote.
Another agent is reducing disk usage. Preserve unrelated changes and evidence.
No main commit/push, release or deployment is authorized by this task.

## Initial Evidence

The original 3.3.35 App-only J-Link installation preserved the old confirmed
BCB. Its startup RTT reported `vcode=30330`, while the full App image is 30335.
`ota_backup.c` requires the confirmed BCB version to equal the validated running
App version before backup or STAGED commit. These relevant source files are
byte-identical between original 3.3.35 source `48ad9f03` and current main.

Thus the previous statement about matching delta baseline hashes was correct
but incomplete: it did not establish the installation prerequisite. Neither
removing this safety guard nor overwriting a BCB version field is an authorized
repair. The standard supported complete-state reconciliation must be reviewed
separately before any persistent device-state change.

END2 OK precedes candidate application/backup/STAGED commit. OtaService then
disconnects intentionally and waits for the target identity. A later activation
failure can therefore produce exactly this apparent reconnect stall without an
MCU reset. A fresh passive RTT snapshot is the next discriminating observation.

## Bounded Observation

- Sole operator: this root session; shared device lock and foreign-debugger check.
- Input: original hash-bound 3.3.35 ELF/map and full App image from
  `.cache/jlink-335-20261119/assets/manifest.json`.
- One passive snapshot of full App/Boot, matching RTT buffer, initialized
  confirmation state and advancing health counters. No Flash/RAM writes,
  explicit halt, reset, OTA, EEPROM access or consumed RTT read pointer.
- Reuse the existing standard Commander, bounded process, path guards and
  SU desktop launcher. Native call limit 120 seconds, whole observation 180 seconds.
- Outputs: `.cache/ota-companion-20261120/observe-01/`; shared temporary lock
  `.cache/p34-live-device.lock`. Only the existing SU SEGGER native-history
  exception permits external automatic writes; all controllable outputs stay local.
- Preserve the current firmware/state. An uncertain outcome stops new device
  operations for reconciliation; never repeat an OTA to repair host collection.

## Findings And Original Observations

The passive observation completed at `observe-01/result.json` under the output
directory above. The full running App still hashes to
`05d0b280cf2b0df09cff1b4f1bda15a7924d6b1cf44789997a9ac12eba43a55a`;
the full Boot remains
`01e4b9e162bfaaf9fda070aa13c0cec3f377b8d696db01f731e0ab3d1464e527`.
Initialized state is CONFIRMED, health counters advance and fault registers are
clear. The matching live RAM contains the current boot's original
`OTA: BCB already CONFIRMED vcode=30330` line. No new reset, halt or write was
requested. The retained RTT text ends inside a metrics line, so this is not a
complete activation trace or a newly read EEPROM dump. No missing ACK/error
value is inferred from that truncated text.

The original 3.3.35 `ota_backup_stage` code explicitly rejects this mismatch
with `OTA_BACKUP_ERR_APP_HEADER` before erasing backup or writing BCB. Added
`t13_app_only_install_stale_bcb` reproduces 30335/30336 images against confirmed
30330, verifies zero Flash/EEPROM writes and unchanged boot records, and uses a
separate consistent fixture as a successful control. The original guard is
unchanged. This establishes a definite installation blocker independent of
which UI initiated the transfer or whether the selected ETU is full or delta.

The App intentionally disconnects after END2 OK and then waits for target
identity. MCU activation happens after that ACK. Thus transfer completion is
not evidence of activation or reboot. Do not remove the backup guard, declare
success from END2, or try another full/delta transfer against this unresolved
state. The earlier installation was physically correct but NOT OTA_READY.

## Scroll Audit

| Container | Result / Change |
| --- | --- |
| App and MCU delta base lists | Shared `.delta-base-list` now chains vertically to its sheet |
| Announcements | `.announcement-list` now chains to the page |
| Firmware operation history | Same fix for `.firmware-history-list` |
| Long confirmation details and errors | Inner text now chains to the dialog; the error header permits native vertical touch pan and retains its existing no-drag message marker |
| App/MCU main version lists, delta job list, distribution table and horizontal tabs | Existing native chaining retained; no new containment added |
| Outer sheets, confirmation dialog and floating resource panel | Retain containment; modal background locks and dismiss/focus rules are unchanged |
| Feedback and task/notification content | No separate bounded inner scroller requiring a change |

Twelve new browser cases exercise actual desktop wheel/mobile touch input at
both boundaries, assert that the correct owner scrolls, preserve the modal and
its background position, and verify zero business mutations. They never move
the owning scroller in order to satisfy an assertion. Native gesture latching
can consume the first gesture at a scripted boundary; the oracle explicitly
checks continued input with at most one further independent gesture. Original
single-gesture failures and geometry are retained rather than relabeled green.

## Development Checks

Original outputs are under `.cache/ota-companion-20261120/`.

- `backup-01`: 155975 backup assertions and 24 health assertions pass, including
  the new stale-version and consistent-state controls. This is a host test, not
  a physical EEPROM repair.
- `ui-before-01`: eight real list-boundary failures and two initial fixture
  failures. `ui-before-02` corrects the long-dialog fixtures and reproduces all
  four long-text wheel/touch failures before the CSS fix.
- `ui-after-01/02/03`: preserve the eight passing cases, four single-gesture
  failures, and diagnostic geometry. `ui-oracle-01/02` discriminates native
  continued-gesture behavior without changing the product again.
- `ui-after-04`: all 12 final boundary/ownership cases pass.
- `types-01`: Admin TypeScript check passes.
- `ui-full-01`: all 285 Admin browser tests pass, including modal gestures,
  Back/focus behavior and the 12 new native scroll cases. Elapsed time 11.3 minutes.
  The original Node `NO_COLOR`/`FORCE_COLOR` environment warning is retained;
  it is not a product error and was not suppressed.

No Flutter or MCU product source/build inputs changed. There is no reason to
rebuild 1.0.85, 3.3.35 or 3.3.36, re-sign a package or generate another delta to
deliver these Admin CSS and test changes. Local self-tests are not independent
acceptance or evidence that the Admin has been deployed.

## Prevention And Remaining Work

The OTA error is a cross-layer/implicit-assumption failure: raw image identity,
CONFIRMED state and advancing runtime were treated as sufficient while the
confirmed version invariant was omitted. A direct-install qualification must
also bind the current BCB version and validate the subsequent backup/STAGED
preconditions. Preserve the fail-closed guard and use a supported complete-state
reconciliation, not a blind field write or an App-only downgrade. The previous
installation record and shared index are explicitly corrected.

The UI error is incomplete propagation of an earlier version-list fix: inner
lists were still using the containment intended for outer modal boundaries.
The shared CSS, native-input tests and Admin README now distinguish those owners.
This repository has no `.trellis/` spec tree; knowledge is kept in its existing
operational records and component guide instead of inventing another workflow.

Physical state repair and a real 3.3.35 -> 3.3.36 OTA remain pending. No Boot,
EEPROM/BCB, QSPI or user SD data was written in this investigation. Any proposed
persistent-state recovery needs a reviewed bounded plan and explicit authority
for its affected records before execution. Main commit/push and Admin deployment
also remain unperformed and require authorization. All source/record changes
are LOCAL_PENDING, not remote delivery.

## Authorized Continuation

The user's subsequent `authorization` reply approves backing up and repairing
the persistent upgrade-control state, with a controlled restart if necessary,
and committing/pushing/deploying the Admin scrolling fix. It does not authorize
Boot replacement, SD-data changes, channel/delta mutations or other releases.
The earlier pending statements above describe the pre-authorization checkpoint.

The root session is the sole device operator. First capture the current full
App/Boot, candidate/backup/recovery slots and staging journal/payload while the
App is healthy and idle. Then preserve both EEPROM records and configuration
before a reviewed identity-bound transaction. Reuse the existing inactive-BCB
commit and firmware validation routines; never patch a version field in place.
The existing P3-4 rollback helper is specifically pinned to 30287 -> 30286 and
is not directly applicable to this confirmed-30330/running-30335 mismatch.
No previous recovery plan is replayed merely because its files exist.

The finite continuation is: one backed-up state inspection, the minimum
validated reconciliation/restoration sequence, and one prepared 3.3.35 ->
3.3.36 OTA observation if device/App prerequisites are available. A failed or
uncertain operation is reconciled before any further mutation. Retain the
successfully upgraded original target. All selected host output stays under
`.cache/ota-companion-20261120/`; the established SU SEGGER native-history
exception remains the only permitted automatic external write.

Admin delivery uses exact-source main CI and the existing Admin-only deployment
workflow. Worker/Public, schema, Access, secrets and channel/delta identities
stay unchanged. Reuse the completed host/browser checks; any new recovery code
receives its own targeted host checks before device execution.

### Current Flash Backup

`state-01/result.json` records a fresh passive full-region backup. App 3.3.35
and the complete unchanged Boot match their original hashes. Runtime, watchdog,
SD and QSPI remain healthy; no active transfer, recorder or debugger breakpoint
was present. No halt, reset, RAM/Flash write or EEPROM access occurred, and all
owned native processes closed. The watched external metadata is unchanged.

The candidate header is erased. The verified backup is 30329, length 614416,
CRC32 2010600807, raw SHA-256
`a853e482ba5f9c55265a56b9b5dcf3131ddf75c912f4e1dd714cb1b565fe8483`.
The valid recovery is 30276. Staging has a committed 313-byte package for 30336.
The four full QSPI regions are archived before any repair. An erased candidate
header means candidate application has not completed; it does not prove that
backup-version rejection was the first activation error. Keep that distinction
while investigating the remaining activation path.

### Selected Reconciliation Route

Use standard Commander only for the existing storage-idle main-loop rendezvous
and deliberate resume/restart. Reuse the qualified CoreSight GPIO/EEPROM ports
to capture both BCB copies twice and all configuration bytes, then run an
identity-bound draft of the existing Boot physical-recovery confirmation kernel.
The C kernel validates the original full 3.3.35 image before deriving one entire
inactive BCB record; the wire adapter writes its eight 8-byte pages, waits for
each write cycle and verifies readback. The old active record, configuration
bytes 128..255, App, Boot and all QSPI regions must remain unchanged.

This reuses `recovery_confirm/{confirm,confirm_io,eeprom_page,gpio_page,read_pair}`
and the unchanged Boot/BCB implementation rather than adding a flasher or
temporarily replacing the App. The old model's image/version pins do not fit
this board; bind a separate task-local host model to 30330 -> 30335 and the
actual original App/Boot and verified 30329 backup. Its pure-C ABI remains
host-only; no arbitrary target-function call or executable RAM upload is used.
The only missing reader capability is configuration bytes 128..255; a read-only
adapter extends that range and is checked against the existing EEPROM wire
model. No page write is added to the read-only snapshot interface.

Before EEPROM mutation, require the saved stable pair, fresh identical pair,
settled CONFIRMED/no-copy/no-resume state, verified backup reference and exact
full image identity. Test complete/partial writes, drift, invalid identities
and immutable configuration offline first. Two finite native cells are planned:
one read-only EEPROM backup/resume (1200 seconds), followed by the admitted
single transaction/restart (2400 seconds). A changed or uncertain state stops
the mutation path. No App/Boot/QSPI/SD programming is part of this route.

### EEPROM And Candidate Confirmation

`repair-host-02/result.json` passes 115 assertions for the source-bound adapter
and exact image pins, including partial-record writes and both native/model
EEPROM framing. The earlier 115-assertion host run is retained separately;
the second binds the added actual SDIO2 idle/DATA0 admission checks.

`eeprom-read-01/result.json` completes the authorized read-only EEPROM cell.
Both records pass CRC and the repeated pair is stable. B is active, sequence
1003, state CONFIRMED, boot_try/copy_phase/resume_block all zero, current version
30330 and backup 30329/614416/2010600807. All 256 bytes are saved before repair.
The ordinary App resumes healthy without a reset; no EEPROM payload, App,
Boot, QSPI or SD write occurred. Native AP state and debug freeze/breakpoints
are restored and the shared device lock is released.

The candidate header is not committed, but its complete 630760-byte payload
already hashes to original 3.3.36
`44325d8921509881c52e0ba96c65a0c9591181a0f78794ed8cecb7a3154ce49b`.
This strengthens the diagnosis: the supplied delta has already reconstructed
the correct target, while the independently read confirmed-version mismatch
blocks the backup/STAGED transaction. A complete BLEACT log is still not
claimed. The next cell rechecks all saved Flash/EEPROM bytes before committing
only the inactive BCB, then performs the authorized restart and readback.

### Reconciliation Completed

`eeprom-repair-01/result.json` completes that transaction. Eight verified 8-byte
pages commit the whole inactive A record: sequence 1004, CONFIRMED, current
version 30335, with boot_try/copy_phase/resume_block still zero. The previous
active B record and all configuration bytes 128..255 remain unchanged. The old
candidate reference is deliberately preserved by the confirmed-state kernel;
it is not silently promoted to a new staged candidate.

One authorized ordinary reset then produces the fresh original RTT line
`OTA: BCB already CONFIRMED vcode=30335`. Full App/Boot readback matches the
original hashes above, all four QSPI regions are unchanged, and runtime,
watchdog and SD health pass. No App, Boot, QSPI or SD programming occurred.
Owned hardware processes closed and the shared device lock was released.
The exact adapter SHA-256 is
`c6911ce040b423c99cfe2f1530ba582e7184f4a327a567777ae8002d096fc8e8`;
do not edit this completed source or replay its read/repair cells.

This removes the demonstrated backup/version prerequisite failure. It is not
yet evidence that a subsequent wireless OTA succeeds. `phone-01/result.json`
finds no ready USB phone; its private ADB server closes, the original key is
unchanged, and no phone launch, install, reset or data mutation occurs. The
remaining physical check is one prepared device-originated 3.3.35 -> 3.3.36
OTA using original App 1.0.85, followed by target/Boot confirmation and original
App-log retrieval. Do not repeat a successful upgrade to recover host logs.

### Initial Admin Delivery And Desktop Follow-Up

Main `9ed63498fd3ba83f2dd454c8c3ccf3ea0791805e` delivers the initial CSS,
regression and investigation record. Exact-source backend Actions `44599364344`
passes 501 Worker tests, 285 browser tests and the contracts/typechecks;
candidate Actions `44599364349` passes with App/MCU builds skipped. Admin-only
deployment `44602404051` succeeds with deployment ID
`25aa04d3-155d-4858-979b-28f6e23b2fb2`. Configuration, Worker/Public, schema,
secrets and channel/delta state are preserved.

Actual live desktop checks nevertheless expose a narrower Chromium wheel gap:
with a pre-scrolled background and sparse delta jobs, exhausted inner-list
wheel input can remain latched instead of reaching the sheet. Computed
overscroll is already auto, events are trusted/not prevented, and both owners
scroll normally when targeted directly. Diagnostic removal of outer containment
does not fix it. Preserve `keyring-cloud-live-01..04` as failed probes, not
successful delivery evidence. `keyring-cloud-live-05` passes real touch at both
edges for App/MCU deltas, announcements and history; all ten served assets match
9ed63498 and no business state is changed. Touch-only success does not waive
desktop verification.

The follow-up in `sheet-gestures.js` forwards only exhausted vertical wheel
input from the named inner lists/text to an eligible ancestor. In-range native
scrolling, touch/drag, nested scroll ownership, zoom/horizontal input, modal
containment and hidden background locks remain intact. Pixel, line and page
units are handled explicitly. Sparse-job/pre-scrolled fixtures reproduce both
desktop failures before the fix while their two touch controls pass
(`ui-sparse-before-01`). After the fix, `ui-scroll-after-01` passes all 18 scroll
cases and `types-02` passes. The existing Node color-environment warnings remain
visible. Full exact-source CI and a second Admin deployment/live wheel-and-touch
readback remain pending for this follow-up; no App or firmware rebuild is needed.

### Continuation Audit Checkpoint

Controllable outputs remain under `.cache/ota-companion-20261120/`. Completed
native sessions include authorized automatic updates under
`C:/Users/SU/AppData/Roaming/SEGGER/`. The watched
`C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`
also changed in both hash and modification time; no selected command invoked
PowerShell, and its writer is not attributed. Do not declare it unchanged,
blame another agent or clean it. The other watched PowerShell startup cache
remained unchanged during those snapshots. A final continuation path/process
audit is still required; the earlier `final-audit.json` belongs to its original
checkpoint and must not be overwritten.

## Follow-Up Delivery Completed

Main `2ad213fae81f395c0e70efed472d8386e1741564` delivers the exhausted-wheel
fix and completed state-repair record. Backend Actions `44613804222` passes
all 291 browser tests, 501 Worker tests, 60 Public/Access/deployment contracts
and the three typechecks. Original logs are in `keyring-logs-03/`. Candidate
`44613804107` and ordinary build `44613804194` both skip App/MCU packaging;
no shipping artifact was rebuilt. Existing test-fixture image/text warnings
and Actions/Node deprecation warnings are retained, not hidden as zero warnings.

Admin-only Actions `44615534351` succeeds and verifies deployment
`77ec808f-c927-4d17-af10-401f84c04990` on that exact source, with production and
preview runtime configuration unchanged. Its originals are in `keyring-logs-04/`.
Worker/Public, schema, credentials, channel pointers and delta enablement are
not changed or redeployed.

`keyring-cloud-live-06/result.json` completes the full real-owner readback.
HTML and all nine JS/CSS assets match Git object bytes. All 16 real native-input
observations execute and pass: App delta, MCU delta, announcements and history,
each with wheel/touch at both boundaries. No check is waived for missing rows
or geometry. Modal backgrounds remain locked; page errors, unexpected writes
and synthetic business records are all zero. Channel and delta identities match
before/after. Long confirmation/error dialogs are covered by the exact-source
browser suite without manufacturing errors or mutations in the live Admin.
Earlier failed desktop and touch-only probes remain immutable history.

## Current USB Prerequisite

`notify-usb-01/result.json` confirms one delivered real current-user Feishu
mention requesting cable/unlock only, explicitly not an OTA start. `phone-02`,
`phone-03` and `phone-04` preserve the later private-5048 read-only attempts:
zero ready devices, all owned processes/ports closed and the original key
unchanged. The user's subsequent confirmation that USB is connected is valid;
an empty private ADB inventory is not proof of a missing cable.

Read-only Windows PnP inspection identifies the exact `10ADA4197U001CK` phone,
its iQOO Z8x MTP interface and WINUSB ADB interface, all with device error code
zero. WMIC identifies the existing PID 19052 as
`D:/install/leidian/LDPlayer4/adb.exe`, serving port 5037. One explicit read-only
`host:devices-l` inventory request to that already-running socket returns OKAY
and lists the expected serial as `device`; it performs no phone command and
cannot start, stop or version-replace the foreign server. These observations
support an existing ADB/USB-owner conflict, not an App or firmware failure.
No foreign process was stopped and no automatic UI input was injected.

The next step requires the user to close that ADB service, or explicitly approve
stopping only this identified service and its current debug connections. Do not
kill unrelated processes, silently use the global server for device operations,
clear App data, install a replacement APK or start OTA before collection works.
After private USB enumeration succeeds, verify V2312A, installed 1.0.85/111 and
APK SHA-256 `72460beec718e9991d3df82ce3fe8770c4c8fa38108c422c292dfdf583f3bb87`.

Original release 1.0.85 does not enable `TRACE_DEV_DEVICE_OBSERVATION`, so its
development-only `p34-observations` finished snapshots must not be assumed to
exist. Use its real PID-bound logcat and native connection diagnostics, paired
with one RTT reader and full target/Boot/confirmation readback. Do not rebuild
the release or fabricate a snapshot/footer to satisfy the development collector.
Both original 3.3.35 and 3.3.36 maps locate `_SEGGER_RTT` at `0x200537a8`; a fresh
signature and current full-image identity still gate actual capture. The USB
link is for observation, while the user initiates the real update on the MCU
and firmware transfer still uses BLE. Real post-repair OTA remains NOT_RUN.

## Continuation Write Audit

`continuation-audit-01/result.json` verifies all 62 recorded owned command
closures, absent device lock and closed private ADB port. It accounts for 1,010
task-cache files (217,911,709 bytes) without moving/deleting historical files.
The only remaining related process is the separately identified foreign ADB;
it is not an owned collector. Controllable outputs, subprocess homes/caches,
notification receipts and Git metadata remain under the project root. The
notification CLI inherited log path is disabled. No credentials are copied.

The completed native adapter still matches its recorded hash. Authorized SEGGER
history updates remain recorded separately. The Windows PowerShell startup
cache named above has changed again since the native audit, with no process
attribution; no selected PowerShell invocation or external cleanup occurred.
Do not infer that a concurrent agent caused it or relabel it as unchanged.
The final post-delivery audit uses a fresh successor directory, not a rewrite
of the original investigation or native receipts. This is implementation
verification, not independent acceptance or whole APP-COMPANION card completion.

## Authorized USB Handoff And OTA Window

The user explicitly permits stopping only the identified LDPlayer ADB service.
`adb-release-01` stops before any action because WMIC's piped UTF-16 output was
decoded incorrectly; `adb-release-02` is blocked by that preserved no-stop lock.
The third cell reconciles the dead, zero-operation owner and uses the exact
old executable's standard `kill-server` once. PID 19052 and port 5037 close.
No emulator or phone is restarted. `phone-05` now sees V2312A and verifies the
original 1.0.85/111 APK hash above, PID 15804; the old empty private inventory
was an ADB ownership issue. Original keys and App data are unchanged.

The prepared functional observation reuses `live_mcu.MCU` binding/inspection,
standard Commander/RTTLogger, the existing private ADB/Windows Job primitives
and qualified SU launcher. This ARM-OB reports S/N -1, so the thin argument
adapter retains the proven default USB selection; exact full App/Boot reads
and the absence of another debugger gate it. No new flashing/storage protocol,
firmware build, AT tuning, debugger write or explicit reset is introduced.

One window captures original PID-bound logcat and one RTT reader, first checks
the running 30335/Boot/health and both original ELF/maps, then waits for the
user's device-originated update. Preparation is bounded to 900 seconds; arming
the actual test starts a separate 600-second transfer/reboot/verification budget.
No automatic phone UI input occurs. The preserved 313-byte staging package may
resume; this is a functional activation check, not a fresh-throughput comparison.
After fresh target Boot confirmation, allow App reconnect, close the reader and
perform full original-30336/unchanged-Boot plus health readback. Retain the target.
An unknown result stops mutations for reconciliation, never another OTA to
recreate lost logs. Outputs stay in `ota-inputs-01/` and `ota-session-01..03/` under
the existing task cache; sensitive raw phone logs use a private ACL. The normal
release has no development snapshot, so no footer is fabricated or bypassed.

## First Post-Repair Attempt

`ota-session-01` stopped before device inspection because the authorized LDPlayer
ADB had restarted. `ota-session-02` could not qualify that SYSTEM-owned process
from SU and did not stop it. The third adapter keeps identity/stop admission in
the SYSTEM parent and native capture in the existing SU desktop. It qualifies
and stops only the same authorized service, now PID 25296, then retains private
port 5048. The failed preparations are not OTA attempts.

The successful collector starts at 22:10:35 UTC, acknowledges the arm at
22:21:21 UTC, and delivers the one start reminder at 22:21:39 UTC. Original
App 1.0.85/111, PID 15804, then performs GET_INFO/CAPS2 and one BEGIN2. At
06:21:56.176 Shanghai time it receives ACK_BEGIN2 status 14 (`ERR_BUSY`), epoch
4202504752, with durable/accepted/credit all zero. The original log contains
no DATA2 or END2 write. App abort/terminal records complete without a transfer.
This is a real failed start, not NOT_RUN: the collector's `otaObserved=false`
only means its narrower BLEACT activation marker was not observed.

The collector closes at 22:25:28 UTC. Full original 30335 App and unchanged
Boot, confirmed state, SD/runtime and idle receiver/overlay checks pass. Staging
headers/journal remain unchanged; no target confirmation occurs. Original App
PID and key are preserved, all owned tools close and private ADB stops. The
terminal handle is subsequently unavailable; verify both recorded owner PIDs
are gone and preserve its completed receipts before reconciling any leftover
owner lock. No phone restart, APK installation, automatic UI input or MCU reset
was requested. The user is told USB can be disconnected; no further phone
operation is needed for this diagnosis.

`ERR_BUSY` has several BEGIN admission sites; it does not uniquely establish a
battery failure or an old session. Current 30335 source no longer checks GPS
speed, but still requires recording to be closed and either charging or at
least 30 percent battery, as well as available overlay memory. The relevant
files are byte-identical to original 48ad9f03. One additional passive snapshot,
`busy-read-01`, reuses the original observer and exact ELF/map to read those
runtime predicates. Its Power ADC offset is verified from the original ELF;
PH2 charging input follows the board configuration and vendor GPIO layout.
It neither requires USB phone access nor changes device state. It can identify
the current blocker but cannot reconstruct a transient predicate at the exact
earlier BEGIN instant. No retry, rebuild or safety-guard removal is planned.

## Current Admission And Remaining Boundary

`busy-read-01/result.json` completes the passive check: ADC 2043 maps to the
firmware's clamped 3300 mV and 0 percent, PH2 does not indicate charging,
recording is closed, receiver state is IDLE and overlay owner is FREE. The
current safety predicate is therefore false. This is a definite current
admission blocker, not proof of the exact earlier BEGIN branch. Both App and
device-originated BLE entry points use the same receiver guard; simulated GPS
speed is absent from 30335's predicate. Do not bypass the guard based on USB or
J-Link supply alone. A further OTA requires the MCU to recognize charging or
report at least 30 percent, with recording stopped, and a newly prepared window.

The later snapshot also contains `Reset: NRST WDT`, and its initialized health
tick is 148997 versus 1981441 at the prior observation's end. A later boot has
occurred; its timing and cause are unknown. Neither collector issued a reset,
halt, Flash write or RAM write. This is not the target-activation reset: full
App remains the original 30335, full Boot is unchanged and BCB confirmation
remains 30335. The new boot explicitly prevents treating the later RAM snapshot
as the earlier BEGIN's instantaneous state. No new reset or retry is performed
to reconstruct the missing interval.

Original App logs preserve the complete ACK error and terminal records. Android
truncates the long `OTA_LINK_STATS` JSON; it is not a complete statistics export
or a usable throughput sample. The attempted read-only UI observer first missed
Android's `topResumedActivity=` spelling; its successor could not establish a
focused window from that device's `dumpsys window windows` output. No screenshot
was taken and those false/inconclusive foreground receipts do not override the
real foreground/GATT records. No UI input, relaunch or replacement App was used
to repair observation, and USB was released after the original log retrieval.

The Admin scrolling work remains deployed and verified on 2ad213fa. The
functional 30335 -> 30336 upgrade is still unsuccessful, not whole-card PASS.
Retain original 30335 and its repaired control state. Current work is limited
to original-evidence analysis and scoped main documentation delivery; no more
phone use, firmware/App rebuild, backend deployment or channel/delta change.

## Observation Closure Audit

`observation-audit-01/result.json` independently recomputes the failed start
from the original complete ACK record, checks 160 recorded owned command
closures, and verifies the absent device lock and closed private ADB port.
The old parent and SU child PIDs both exited; `busy-read-01/reconciled-owner.json`
preserves their completed outcome before the leftover lock was removed. The
remaining ADB PID belongs to a separate server, not the closed private collector;
no further stop or phone command is performed.

All selected outputs remain in the active root: task-cache originals, the three
shared documentation files and authorized Git metadata. The prior audit files
and completed repair/collection sources remain immutable. No credentials were
copied. The PowerShell startup cache again changed without an attributed writer;
no selected command launched PowerShell and no external file was cleaned. The
passive follow-up's watched SEGGER files were unchanged; its native-history
exception remains the only authorized external output boundary. A fresh
post-delivery audit is required instead of overwriting this checkpoint.

## Autonomous Remediation Authorization

The user's latest instruction authorizes continuing necessary scoped work,
including its required authorization, without stopping for routine approval.
The preceding analysis-only boundary is superseded for this remediation batch.
Root remains the sole operator; no subagents, channel promotion, firmware safety
bypass, Boot replacement, App-data clearing or unrelated cleanup is included.

Use the exclusive sparse worktree `.worktrees/ota-companion-fix-20261120`, branch
`dev/flutter/ota-companion-fix-20261120`, from current main `2db67b95`.
Controllable outputs stay in `.cache/ota-companion-fix-20261120` and this worktree;
the prior originals and completed helpers stay immutable. There is no Trellis
tree. Existing main records remain authoritative until this batch is integrated.

The finite batch preserves matched ACK command/status through transport and
service, explains BEGIN/DATA/END rejection without claiming ERR_BUSY uniquely
identifies battery, and projects safe owner-produced failure text through the
existing notification label. Reboot probes retain valid non-target responses
for deadline feedback without shortening the window or weakening target
version/full raw SHA checks. Cancelled, stale-link and abandoned callbacks may
not replace current owner state. ABORT ordering, durable/credit, retry limits
and statistics outcome names remain unchanged.

Add transport/service/snapshot regression cases, then run full Ubuntu/Windows
Flutter development CI and required exact-source APK/EXE verification. Shipping
uses a new App version and the existing original-signed candidate route; do not
rebuild immutable 1.0.85 or MCU 3.3.35/3.3.36, publish channels or regenerate a
delta merely to test feedback. Necessary main integration/push is in this scope.

Separately prepare one MCU-only passive watch (at most 240 seconds) using the
standard Commander, original 30335 ELF/map and existing contained host/observer
primitives. Verify idle state, sample health/power and clock registers, preserve
RTT memory without consuming its reader pointer, and inspect whether a fresh
boot occurs. No reset, halt, RAM/Flash write, OTA or phone is required. A missing
device or no reset in this bounded interval does not establish the historical
watchdog cause. Any further hardware change must follow discriminating evidence;
real OTA remains gated on firmware-reported safe power and a prepared phone.

### Initial Development Feedback

Development source `9e4811f15928f189fad2c62229b8ab38feecaced`, run
`44637193444`, fails both hosts because the new service test references an
incorrect harness name. Use the existing `_BackgroundOwnerHarness`; no product
analysis error is reported. The service integration file did not compile, so
its new cases are NOT_RUN, not passing. Other test counts are Linux 799 passed /
16 skipped / 1 failed and Windows 755 passed / 60 skipped / 1 failed. Original
console logs are preserved in `keyring-logs-01` under the new task cache.

The follow-up also makes notification-safe failure text an explicit terminal
field. Generic backend/transport error details are not automatically forwarded
to the notification; this avoids leaking an exception's signed URL or token.
This is an internal projection change, not a native notification schema change.

Second development run `44638689257`, source `80fd49e02c8c1832249aed95e5ebbb73f8024f22`,
passes analysis on both hosts. Linux reports 971 passed / 16 skipped / 2 failed;
Windows reports 919 passed / 68 skipped / 2 failed. Both failures are old-identity
and wrong-full-SHA regression expectations still naming REBOOT_RECONNECT_FAILED.
Update those two assertions to TARGET_FIRMWARE_NOT_CONFIRMED, retaining their
false-success/current-identity guards. Reuse the stronger existing full-SHA
case rather than retaining a duplicate new fixture. The new rejection, cleanup,
notification and stale/late-response cases pass in this failed batch. Original
full logs/reports are retained in `keyring-artifacts-01/02`; no failed run is
relabelled successful and no tests are disabled.

### Passive Watch Result

`passive-watch-01/result.json` completes one standard-Commander observation.
Thirteen samples cover 121508 firmware milliseconds with advancing main-loop
and watchdog-feed counters, clear fault registers, SD ready and idle receiver/
overlay. No counter discontinuity is observed. Reported core clock is 288 MHz,
SysTick reload is 287999 and DWT deltas agree with approximately 288000 cycles
per millisecond. There is no evidence here of a clock-rate defect or a new reset;
this short interval does not establish the cause of the earlier WDT boot.

Every sample reports ADC 2040..2042, clamped 3300 mV / zero percent, no charging
and recording closed. The power admission predicate remains false. Full original
30335 App and unchanged Boot match before/after, confirmation remains 30335,
all owned debugger commands close and the shared lock is absent. No phone,
reset, halt or RAM/Flash write occurs. Watched SEGGER and PowerShell metadata
remain unchanged during this watch. Do not repeat it merely to obtain a reset.

### Recorded Feedback Contract

#### Scope And Trigger

This is the implementation record for rejected BLE commands and post-transfer
identity feedback, not a change to frozen OTA acceptance or the wire protocol.
The defect combines lost cross-layer error metadata with the false assumption
that failing to verify a target always means the device never responded.

#### Signatures

- `OtaTransportException(message, {code, status, ackCommand})` preserves the
  matched response command at the receive boundary.
- `OtaTerminalState.mcuRejection({required status, ackCommand})` maps safe text
  and the existing status-specific retryability.
- `OtaTerminalState.taskFailureReason` and `OtaTaskSnapshot.failureReason` are
  optional owner-produced text; `toMap()['label']` remains the native interface.
- `_probeTargetIdentity(..., onNonTargetIdentity)` reports only validated,
  current-link, same-hardware non-target identities within the active wait.

#### Contracts

Do not infer an ACK command from the phase after ABORT. Publish failed terminal
state only after bounded cleanup and owner-generation rechecks. Error snapshots
do not grant credit or durable progress. Keep valid non-target observations local
to the wait: they do not refresh the service's current identity. Target success
still requires both version and the complete raw SHA. Retain the full window and
stable probe statistics outcome names. Raw backend/transport strings are not
notification-safe by default.

#### Validation And Error Matrix

| Input | Feedback / invariant |
| --- | --- |
| BEGIN2 ERR_BUSY | Named command/status, recording/power/idle guidance; zero DATA/END, no automatic retry |
| DATA2/END2 rejection | Original command/status survives ABORT; no reboot-success claim |
| Valid non-target responses until deadline | TARGET_FIRMWARE_NOT_CONFIRMED; last observed version, not a claim of current connectivity |
| No usable identity response | REBOOT_RECONNECT_FAILED; retain uncertainty and later recheck |
| Wrong hardware | Existing DEVICE_IDENTITY_CHANGED, not a non-target observation |
| Cancelled, abandoned or stale-link callback | Cannot alter the current owner's feedback, identity or success |

#### Good, Base And Bad Cases

Good: an old response followed by the correct target within the window succeeds.
Base: no reply times out without inventing an identity. Bad: the target version
with a different full raw SHA remains unconfirmed, never completed.

#### Tests Required

`ota_pipeline_transport_test.dart` checks matched BEGIN/DATA/END/ABORT metadata.
`ota_service_upgrade_test.dart` exercises the real owner flow, ABORT/cancel
ordering, notification projection and all identity cases above.
`ota_background_test.dart` checks failed-only projection with no invented percent.
Full Linux/Windows Actions checks and original-signed APK/EXE builds remain
distinct from a phone installation or successful physical OTA.

#### Wrong Versus Correct

Wrong: remove the battery guard, call END ACK success, or label every timeout a
disconnected device. Correct: preserve the original rejection, finish cleanup,
retain only valid observations and report exactly what was or was not verified.
