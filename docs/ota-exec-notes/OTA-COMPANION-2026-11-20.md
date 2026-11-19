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
