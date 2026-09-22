# Bounded Device Sessions

Use this only when the task needs actual installation, connection, recording or
device verification. Historical addresses, package names, endpoints and receipts
are inputs to inspect, never current authority or reusable action quotas. Use the
current [device experiment policy](../../../../docs/device-experiment-policy.md)
and task matrix, not an old one-shot controller's caps, for new development work.

## Ownership And Preparation

| Owner | Work |
| --- | --- |
| Agent | Approved CI, APK verification, USB installation/launch, file retrieval, collector preparation, analysis and cleanup |
| User | Required permission dialogs, in-App connection/navigation/start, physical cable/card/power actions the agent cannot perform |
| Device/App | Protocol retries, durable progress, ordinary apply/reboot and automatic immutable diagnostic snapshot |

Prepare and test the whole route before involving the user. A staging package,
query log, finished snapshot and target readback are different artifacts. Reuse
an already verified APK/package when still applicable instead of rebuilding to
work around a host collector failure. An embedded endpoint must really be live;
an expired accountless tunnel cannot be recreated under the same hostname.

## CI And Installation

Read the actual [development workflow guide](../../../../docs/flutter-development-validation.md)
and workflow definition. Request a debug APK explicitly when needed; do not infer
APK production from a checks-only green run. Record both host outcomes, actual
SDK, scope, commit, artifact identity and APK application ID. Keep signed URLs,
credentials and full request bodies out of messages and retained diagnostics.

Before installation, verify phone serial/model and whether the exact package is
already installed. `pm list packages PACKAGE` is suitable for an absence check;
on some Android versions an absent `pm path PACKAGE` returns exit 1. After an
install, verify the installed APK's hash. A side-by-side debug ID avoids replacing
the user's normal app. No blind reinstall, data clearing or automatic UI taps.

An install/dispatch that returns a running session ID is still the same operation.
Poll that process. If its result is uncertain, inspect device/CI state rather than
issuing another installation/dispatch. Count actual attempts, not host reservations.

## USB Containment

Use a private ADB server port and explicitly bind every client to its host, port
and serial. Do not let a client silently start or connect to an unrelated global
server. Before launch, contain HOME/USERPROFILE, APPDATA/LOCALAPPDATA, TEMP/TMP/
TMPDIR and Android home paths. An existing `ADB_VENDOR_KEYS` file is a read-only
input, not permission to overwrite it or generate keys beside it.

The server's worker and all clients share a real deadline. Closure needs the
owned worker result and a port/process check, not just a sent stop command. A
supervisor-forced shutdown is not a graceful ADB shutdown even if the port closed.
Recover only after diagnosing the failure, preserving its receipt, checking the
remaining scope and starting a fresh owned runtime. A worker deadline is not a
whole-task approval deadline. Renew an owned window within the task plan without
asking again; host recovery never erases prior or uncertain device attempts.

## MCU Observation

Use the matching production GCC artifact and its original map/ELF. A new link
can move RTT. Check the exact symbol and signature before opening one reader.
Wait for initialized, advancing App time before asserting steady-state SysTick;
Boot and early startup can legitimately use different clock state.

Invalidate old channels, partial lines and readiness after reset/Boot/uncertainty.
Arrange capture before an authorized reset so one reader owns the resulting
startup confirmation. Do not consume it in a preflight reader and then require
it again in another reader. A missing startup line alone is not firmware failure
and is not permission to reset, flash, call firmware functions by changing PC,
or write EEPROM. Reusing an earlier current-boot confirmation requires explicit
evidence that the boot is unchanged, not just matching version text.

J-Link may write native history outside the redirected home. Its exact path and
operation need prior authorization; broad tool access or a copied old command
does not provide it. Keep all controllable logs/projects/readbacks local. Never
kill another user's debugger merely because its process name matches.

## Collect Before Declaring Success

1. Before transfer: exact current App/Boot, usable confirmation, live App-origin
   queries, downloaded package bytes and sufficient remaining observation time.
2. During transfer: one invocation at a time; repetitions/recovery follow the
   declared matrix, not per-invocation approvals. No injected disconnect unless
   included in scope. Keep foreground unless background ownership is implemented
   and acknowledged. MCU durable state, not sent bytes, defines progress.
3. After END: allow ordinary apply/reboot. Verify new connection identity and full
   raw target bytes plus the applicable Boot state. Do not reset just to hurry it.
4. Retrieve the automatic finished snapshot, preserving original bytes and APK/
   process/package bindings. Use the strict observation/statistics tools when
   present in the admitted source. A partial checkpoint cannot substitute for it.
5. Preserve original failures and final results. Close owned services and audit
   output locations. Keep product success, collector failure, measurement gaps,
   development checks and independent acceptance as separate conclusions.

## Failure Triage

| Observation | First discriminating check | Do not do |
| --- | --- | --- |
| Private ADB connection refused | Supervisor closed receipt, worker log and owned port | Reinstall the APK |
| WinError 5 replacing state | Same-file bounded retry; real shared-handle test | Repeat device operations or erase pending evidence |
| Extended Windows prefix on a vanished `.tmp` | Normalize a stable existing parent; inspect reparse ancestry | Whitelist arbitrary external paths |
| App header exists but no producer lines | Build marker, process identity, real query and health counters | Treat the header as working capture |
| UI success but collector failed | App's immutable snapshot and passive target/Boot readback | Repeat a successful OTA to recover a host file |
| Early ACKs in an otherwise complete log | Preserve invalid samples and explain the missing latency set | Invent zero latency or claim complete P99 |
| Slow OTA | Count discoveries, write mode/MTU, GATT/ACK and durable timing | Assume baud is the root cause |

The examples are diagnostic patterns, not fixed device IDs, retry budgets,
performance gates, approval grants or instructions to reopen frozen acceptance.
