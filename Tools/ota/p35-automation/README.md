# P3-5 Release Automation Runner

Status: host runner and Release-capable App integration implemented; development
validation in progress. **NOT live-qualified.** Installed Release92 predates the
new recorder and semantic identifiers; a rebuilt, verified Release APK is required.
Missing capability is an error, not a mock,
screenshot fallback or permission to start an upgrade for collector qualification.

The user requested a P3-5 script without screenshot/model-driven control. This
runner provides native UI discovery, owned continuous logcat, the ten-event
state machine, bounded Bluetooth fault injection and strict result accounting.
It deliberately does not port the Debug-only runtime, use `run-as`, implement
a BLE sender, create a Cloudflare fixture, or modify firmware/Boot state.

## Entry Points

Run from the containing Git worktree root, with isolated Python. No third-party
Python package or local Flutter build is needed.

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py --help
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py check --plan PATH_TO_REVIEWED_PLAN
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py probe --plan PATH_TO_REVIEWED_PLAN --out .cache\p35-probe-UNIQUE
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py run --plan PATH_TO_REVIEWED_PLAN --out .cache\p35-run-UNIQUE --execute
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py retrieve --plan PATH_TO_REVIEWED_PLAN --capture-id CAPTURE_ID --out .cache\p35-retrieve-UNIQUE
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py audit --archive APP_JSONL --capture-id CAPTURE_ID
python -I -S -B -X utf8 Tools\ota\p35-automation\test_runner.py -v
```

- `check`: schema/identity/window validation only. No tool/device/process launch,
  input hash verification or output write. It does not qualify a real asset.
- `probe`: requires recording already explicitly started from the App toolbar;
  starts only an owned private ADB/logcat route, verifies the running APK,
  checks the native accessibility tree and requires fresh Release telemetry. No
  UI tap, Bluetooth toggle, install, launch, reset or upgrade. It must not be run
  while the phone/device is unavailable. `PROBE_READY` only qualifies the check
  control and current telemetry, not injection timing or the entire campaign.
- `run`: requires `--execute`, a reviewed plan and explicit
  `allow_bluetooth_toggle=true`. Both live paths require a fresh output directory,
  pinned executable/key/package files and the exact already-running Release APK.
  Bluetooth adapter toggling affects ALL phone Bluetooth connections, not just the
  target. This impact needs task-level authorization; writing the script grants none.
- Tests use explicitly synthetic, in-memory events. A test's ten successes are
  never ten physical recoveries and never a P3-5 formal PASS.
- `retrieve`: no PID, UI or live transfer required. Reads the exact capture ID
  from app-owned external files using the authorized Android shell, preserving
  partial files too. It does not use run-as or an exported provider. A missing
  footer, hash/count mismatch or unhealthy capture is not a successful archive.
- `audit`: offline verification of unchanged App originals, without ADB or writes.

`plan.example.json` intentionally contains missing hashes/paths and refuses to
run. The30294 target and1MiB windows are examples, NOT assets that were built or
registered. Retained30293 is not an automatically refreshed observation. Replace
all example inputs from actual current device and immutable artifact records;
do not reuse the obsolete30292 plan, downgrade, edit BCB or publish a new package
just because a template names it.

## Ownership And UI

The existing `p34-acceptance/live_host.py` supplies guarded paths, isolated home/
temp/cache directories, Windows Job process ownership and original split-stream
receipts. The existing worktree device lock is respected. The APK is neither
installed nor restarted by this script. Start admission requires a known idle,
connected, identified target in the foreground with required permissions already
granted; no permission dialog is automatically approved.

The standard Android `uiautomator dump --compressed /dev/tty` command produces
the accessibility hierarchy. Some Android builds do not support this stdout
route; probe fails explicitly rather than silently choosing a global device file
or a screenshot. This route and the actual phone's Bluetooth service command/
state format still need a device capability check. No Appium server is installed.

Selectors use exact `resource-id`, `text` or `content-desc`. Flutter `ValueKey` is
NOT an Android selector. Multiple matches, a disabled/missing node, a foreign
foreground window or a changed App PID stop execution. `input tap` coordinates
come only from the just-read unique clickable accessibility node, never fixed
screen coordinates or image recognition. Bounded swipes use the unique native
scroll viewport, not fixed display dimensions. `Semantics.identifier` exposes
`p35-arm`, `p35-stop`, `p35-reconnect`, `p35-check`, `p35-download`, `p35-start`
and `p35-identity`. Qualify their actual Android mapping before live use.

The initial check control must already be exposed to probe. `navigate` is only
an optional bounded in-App route after that admission; it does not replace the
known connected-idle initial-state requirement. System-wide Bluetooth toggle
uses standard `cmd bluetooth_manager disable/enable`, with actual service-state
readback and App-side disconnection confirmation. Host command completion alone
does not establish a disconnect.

## Release Telemetry Integration

**This is a new integration, not an existing Release92 API.** `OtaP35Recorder`
reuses `OtaObservationWriter` but keeps the old, frozen single-upgrade diagnostic
format unchanged. OtaService supplies real phases, verified assets and GET_INFO;
OtaLinkStats receives state only after transport ACK/window validation. Nothing
is copied from the plan. No Debug-mode switch or old automatic observer is enabled.

The producer emits one small JSON object after `OTA_P35_STATE ` to the target
process log. Each state transition and actual BEGIN/DATA/identity event must be
emitted, plus a heartbeat faster than `limits.event_seconds`. Required keys are
exactly `runner.STATE_KEYS`, with schema1:

| Fields | Meaning / truthful source |
| --- | --- |
| captureId, seq, monoUs | Random capture identity, consecutive sequence and monotonic clock; no silent gap/reset |
| deviceAddress, currentVersionCode, currentImageSha256 | Actual identified target and fresh GET_INFO identity, not plan constants |
| phase, event | Actual OtaPhase; event is state/heartbeat/beginAck/data/identity |
| targetVersionCode, targetImageSha256, releaseId, latestUrl | Actual real-backend selection; latestUrl has no query/token |
| packageSha256, packageBytes, packageVerified | Selected asset identity; only packageVerified=true means actual local bytes passed verification |
| protocol, durable, bitmap, session | Actual accepted wire state; v1 has a 32-bit bitmap, v2 has null bitmap and resumes durable; protocol null before BEGIN |
| sendOffset | Actual first/resumed DATA offset on data events; null otherwise |
| linkConnected, freshConnection | Real BLE link status and identity from the new connection; not whether a button was clicked |
| healthy, lost, error | Producer/capture health; true/0/null required, loss must never be hidden |

Before query there may be no package/manifest; SHA fields may be null and numeric
asset fields zero. Before starting an upgrade all bindings must be present and
match the plan. On an injected disconnect retain the last acknowledged durable/
bitmap and last validated package/current identity as historical fields; only
new GET_INFO on a new link may set `freshConnection=true`. A completion event
must be a new connection's full version/hash identity, not END ACK or UI100%.

Each line is flushed before being published to logcat. The recorder is owned by
the service, not the page or chat session. It stores originals at
`/sdcard/Android/data/APP_ID/files/p35-observations/CAPTURE_ID.jsonl` on Android
(the actual directory comes from path_provider). No permission/provider is added.
The archive contains open/close records; the footer binds SHA-256 and count of
exact state-line bytes. USB loss does not stop App recording. Process death can
leave a partial tail/missing footer; retrieve it, do not forge completion or
repeat the upgrade. Android shell access to this directory still needs phone
qualification. Uninstall/clear-data removes app-owned files; never use either to
repair collection. No automatic deletion/rotation: 32 retained files, 128 MiB per
capture, 256 queued records and one hour bound fail explicitly. This is not an
extra background execution guarantee while no OTA service owns the runtime.

## Campaign Semantics

One admitted package/session group has ten independent physical disconnect and
resume events at nonoverlapping predeclared durable windows. All ten share the
final completed-upgrade identity record. This grouping is a candidate execution
plan; the independent P3-5 owner must approve its coverage against the canonical
Spec before formal execution. It is not a demand for ten APP or firmware versions.

The runner waits for a fresh checkingUpdate transition, actual backend selection,
download verification, and initial zero-durable/zero-bitmap BEGIN. It then waits
for each MCU-confirmed boundary, toggles Bluetooth off, verifies the actual
disconnect remained inside the declared window, restores Bluetooth, drives the
configured reconnect/resume controls, and verifies BEGIN plus first missing DATA
according to the negotiated protocol and subsequent durable progress. v1 plans
require partial-bitmap coverage; v2 plans must use bitmap=any because no bitmap
exists on that wire protocol. It finally requires fresh post-reboot target
identity, complete durable bytes and a verified unchanged App archive.

There are no screenshots or model turns in the critical loop. Host radio commands
still have latency; a fast link may escape a narrow window before disable takes
effect. The script rejects that case. Do not silently widen frozen windows or
claim precision that was not measured. Packet-loss/RF weakening, adapter disable,
and App-requested disconnect are different fault types; this runner implements
only the declared adapter-disable type, not every P5 physical fault.

Capture starts BEFORE UI actions and the existing owned logcat process writes
stdout independently of the state machine or model. Consumers reject malformed/
oversized/replayed/lost records and backlog, enforce event/stage/whole-run bounds,
and stop after30s without durable progress. A command's exit0 is not a state
oracle. All actual actions have immutable intent/result records. Uncertain taps
and failed cases are not repeated until they pass. No MCU reset, App force-stop,
data deletion, manual SQL, runtime-config injection or downgrade exists here.

Bluetooth restoration is attempted after an injected fault, including uncertain
disable. On unrecoverable capture/USB failure the runner stops further test actions
and closes only its owned host workers; it does not cancel a potentially applying
upgrade. Device outcome stays unknown until originals/current state are reconciled.
An execution error leaves the existing device-owner lock as a reconciliation
signal. Do not delete it or rerun an existing output directory blindly.

## Result Boundaries

`AUTOMATION_COMPLETED` means the script observed its declared sequence. It ALWAYS
retains `formalAcceptance=NOT_ADJUDICATED`. Final P3-5 acceptance still requires
the real P4-2/backend/fixture provenance, exact candidate/profile bindings,
applicable Boot/MCU evidence and the independent frozen-contract evaluation.
No source in this directory grants device, cloud, signing, merge or release rights.

Implementation author self-tests, script readiness, live qualification, actual
ten-event execution and whole-card acceptance are five different claims. At this
delivery live qualification and formal acceptance remain NOT_RUN. Development
CI runs are checks-only, not a Debug APK and not the Release build gate.

Initial host-only Windows verification on2026-10-29:34 unittest methods passed, including a
synthetic full ten-event campaign and negative cases; four real Python CLI
invocations passed their expected exits (help, valid offline check, incomplete
template rejection, missing-execute rejection). These run only host code, not adb.
Original command streams/exit receipts: `.cache/p35-automation-tests-20261029/`.
