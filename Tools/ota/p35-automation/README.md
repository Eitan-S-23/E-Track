# P3-5 Release Automation Runner

## Single-Upgrade Development Entry

The explicit repeat requested after the first single run uses `detached.py`:
a hidden Win32_Process.Create supervisor outside terminal Jobs, with the existing
owned command-tree deadlines/receipts inside it. Actual parent-exit, timeout and
terminal-return probes pass; no scheduler or service is installed. The task's
protected credentials are loaded inside its adapter, not stored by the broker.
The new3.3.3 upgrade completed with a healthy5392-row App original under
`.cache/p35-repeat-20261101/`, but the pipeline remains EVIDENCE_GAP after logcat
skipped seq3445. All available live rows match the complete App file; recovery
normally sealed it and closed owned resources. See `p35-single-repeat-20261101.md`
in the task's execution notes for the original hash/check command and2191-file
manifest. Retain the earlier failed single evidence below. Do not treat supervisor exit0 as a test
PASS: require the actual pipeline, device, sealed/live audit and restoration.

The user redirected development to one complete successful upgrade before
handoff. Set `test_profile="single-upgrade"` on the pipeline configuration and
its pinned runner template, with `cases=[]` and `allow_bluetooth_toggle=false`.
The same `runner.py pipeline` entry builds/publishes a new test firmware and
invokes `runner.py run --single-upgrade`. A direct single-plan offline check
also requires `check --single-upgrade`. The ordinary ten-event validator rejects
single plans; no formal criterion is waived or replaced.

Single success still requires post-reboot target version/full image identity,
NO_UPDATE, exact healthy sealed/live records and owned cleanup. Results say
`single-upgrade-no-injection`, planned0/recovered0, never 10/10. No injected cuts
or automatic retries are allowed in this profile. Cloud/build restoration is
unchanged and normal protected review remains separate from pipeline automation.

Current work: `.cache/p35-single-20261101/`;110 host tests plus42 final affected
tests pass. The real single3.3.2 upgrade is verified by post-reboot full identity,
but automation is EVIDENCE_GAP after host interruption:5152 live rows,8708 intact
original rows and an unhealthy duration-limit footer. NO_UPDATE/normal STOP were
not run. Scripted recovery restored cloud state and reconciled device resources;
no repeated OTA. See `docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/p35-single-upgrade-20261101.md`.
Pipeline7 is terminal FAIL before ARM, with cloud/build restored and resources
closed; its former RUNNING description below is historical. Original lifecycle
audit distinguishes its transient App pause from pipeline6's native write error.

Old healthy pre-BEGIN download captures do not permanently prohibit reopening
the App. A present PID is admitted only after idle-service checks, normal same-PID
foreground and stable native HOME/PID observations. A current recorder,
firmware/device page, unknown UI, changed PID or active service still rejects;
there is no forced restart or clearing of old records.

## Current Result: Pipeline6 Failed, Resources Reconciled

Real `pipeline6-01` built/published new3.3.0 through CI41281354490, selected it,
downloaded/verified it on the phone, scrolled/started BLE and proved actual OFF
and restored ON during R01. It then received an explicit `log-write-failed` App
error. All601 recorded body rows are present in the events stream, but the seal
is unhealthy: this is not ten-event PASS. R01 FAIL, R02-R10 NOT_RUN; no END/apply.
Build/channel state restored. One STOP and the subsequent owned-App closeout
preserved the failed original and released the device leases, without OTA replay.

The next bounded App diagnostic retains the actual native return/expected count,
which the old emitter discarded, and fixes failed-stop UI notification. It does
not relax native return or live sequence checks. WIP `4b46c887e13a8cbb5c024610f4f2506486e72f28`,
version1.0.68+94, passed development CI41282761975 and nonpublishing APK/EXE
CI41283076516 and was installed with19 old captures unchanged. Actual controls
passed108/108 idle and54/54 one-pair radio-interaction records, without OTA or a
native failure. The exact failure remains unclassified; instrumented real
pipeline7 is running against freshly reviewed3.3.1, not counted as PASS. See the
task-note continuation and `writer-diagnostic/`; earlier pending descriptions are
history.

## Current Continuation: Structured Events Candidate

The optional `preparation.log_buffer="events"` selects continuous
`logcat -b events` for the repaired test App's `__android_log_bswrite` records.
It is incompatible with `startup_log_tag`; default plans are unchanged. Strict
native return counts, five-second live readiness, sequence/content equality and
the real ten-window oracles remain mandatory. Failure-buffer diagnostics never
fill missing live evidence. No global logging property or file-polling fallback
is used by this profile.

The fifth real pipeline built/published test 3.2.99 and restored its temporary
settings, but failed at ARM with no live rows, before any query/download/OTA.
Actual main-buffer inspection also contained zero P35 rows although the App
original was healthy. One subsequent STOP/archive/owned-App closeout resolved
resources without changing the failed verdict. This is distinct from pipeline4's
already proved scroll/BEGIN and repaired radio-state check.

Events source batch: 219/219 host tests; App commit
`fe645d099dde3e1f53580ef6e9d6931f7cbbbf0e`, version `1.0.67+93`; development CI
41277456757 and nonpublishing APK/EXE CI 41278085367 passed. The installed APK was
hash-verified with all17 old captures unchanged. `events-reader-01` then passed
real five-second readiness, fresh30293/full-hash identity and exact26-row archive
equality, with no OTA/radio/property writes and verified owned cleanup. The next
real unified `pipeline6-01` is now running against freshly reviewed3.3.0. See the
latest task-note appendix for immutable failures, artifact/resume receipts and
the disclosed external OCSP-cache observation. Older "latest" sections below
are historical results, not the present resource state.

## Fault Repair: Real OFF/ON Qualified, Full Campaign Still Incomplete

The first-cut reader now supports the explicit plan option
`preparation.radio_state_reader="vivo-pd2312-sdk33-getState-v1"`. It binds the
actual phone's build fingerprint and framework hash before calling its inspected
`IBluetoothManager.getState` getter. OFF requires state10; ON requires state12.
Turning/BLE-only states remain unknown. Missing, failed or malformed replies are
not OFF, and the existing five-second read/ten-second transition bounds remain.
Default plans do not use this ROM-specific interface.

The exact temporary SERVICE/Client-only adapter envelope also returns unknown,
not an immediate malformed-state error. Permanent absence still fails within
the original deadline. The active failure stage now names `R01-radio-off`, and
the case preserves the original execution error when cleanup also fails.

STOP recovery may audit a healthy sealed original for safe partial-transfer
cleanup after live failure. It never fills missing live rows, clears that failure,
retries STOP or admits apply/full-durable history. The old run remains failed.

`fault-host-final-01` passed all 212 host methods in 758.129 seconds, including
the real caller with synthetic ten-event getter states and recovery negatives.
`radio-closeout-03` safely closed the original failed owner after USB returned.
Then `radio-reader-live-01` executed one no-OTA OFF/ON pair: actual getter replies
confirmed OFF and ON, reconnect returned fresh 30293/full-hash identity, and all
58 live records matched the sealed original. One ARM/STOP; no firmware query,
download or upgrade. Observed log.tag remained M before/off/after-on/after-wait.
Owned App/logcat/private ADB closed; all canonical locks are absent.

This qualifies the repaired state reader and this no-load capture only. The
eight missing rows from pipeline4 remain an unresolved transfer-run live gap;
their cause is not proved or claimed fixed. No additional pipeline/OTA group
was run for this repair. Full-chain completion and formal acceptance remain
unachieved. Evidence and exact bindings are in the latest task-note appendix
and `.cache/p35-native-log-20261101/fault-repair-audit-01/audit.json`.
The earlier pending-USB and NOT_RUN statements below are retained history.

## Latest Physical Result: Scroll Passed, First Cut Failed

`pipeline4-01` actually built and registered new 3.2.98 through CI 41270193796,
selected it via the normal test API and ran the real phone entry. The runner
downloaded/verified the package, scrolled to p35-start, tapped it once and received
the initial BEGIN. Thus the former scrolling failure is physically resolved.

R01 issued one disable. The actual dump first reported TURNING_OFF, then only a
SERVICE/Client envelope with no AdapterProperties section. The reader correctly
did not invent OFF. One enable restored confirmed ON, but zero recoveries were
proved. R01 is FAIL; R02-R10 are NOT_RUN. Full-chain completion is NOT achieved.
The App sealed 709 healthy records, with a partial 20480-byte durable prefix and
no END/apply/completed state. Host logcat has 701 matching rows, missing sequences
700..707: retain this distinct live-evidence gap, never count it as full equality.

Cloud channels and build variables restored (stable revision 30, beta 11).
`radio-reconcile-01` retrieved/audited the original and read actual Bluetooth ON.
Its optional standard help query printed help with exit255; that failed receipt
is retained. `radio-closeout-01` attempted only remaining safe closeout, but the
USB device list was empty. No App stop/resume/new ARM/radio action was performed
by either reconciliation. Private ADB closed; the original device lock and App
ownership remain unresolved pending USB reconnection. Do not replay the group.

The startup policy now optionally accepts `allow_info_baseline: true`. Only I
selects a no-property-write path; M retains the earlier bounded V/M route, other
values reject, and all live readiness gates still apply. Its affected 116-test
batch passed in startup-host-03. The actual fourth run took the I/no-write path.
Normal protected approvals remain separately recorded. See the latest task-note
appendix for exact sources, package hashes and retained failures.

## Latest Continuation: Archive Repair And Logging State Drift

The second real pipeline, `pipeline2-01`, built/registered 3.2.96 through CI
41266403336, then rejected the previously reconciled readyToInstall archive
before App launch/ARM. It restored build variables and channels (stable revision
26, beta 11); no device lock remained. All ten events are still NOT_RUN.

P35-ARCHIVE-READY now admits a healthy sealed, verified-download archive only
when its complete history proves no BEGIN/session/durable/DATA and the test App
is absent. It neither stops a running App nor ignores incomplete records. The
original failure is reproduced in `archive-red-01`; consolidated regressions
pass 198/198 in `ready-host-02`. Historical results/originals were not rewritten.

The subsequent read-only phone preflight found log.tag=I, not the planned M.
No property was written. `reader-current-01` then qualified the real five-second
reader and 25 matching sealed records with fresh 30293/full-hash identity, but
log.tag changed from I before launch to M after sealing without a property write
in that invocation. Its overall FAIL remains: telemetry/archive passed, stable
configuration did not. The source of the change is unknown, not attributed to
the phone, another agent or Flutter. App/logcat/ADB closed and locks are absent.
Third-pipeline configuration/build/approval/OTA have NOT_RUN. Establish exclusive
logging-setting ownership before another build; do not force the stale baseline
or repeat a successful observation. Details and exact originals are in the
latest appendix of `p35-launch-fix-20261101.md`.

## First Pipeline Outcome And Pre-BEGIN Recovery

The real `pipeline-live-01` built/registered/downloaded new 3.2.95 in CI
41263663499. Package verification and restored-policy live telemetry passed.
It stopped before the first upgrade tap: a passive success snackbar and the
firmware ScrollView were both marked scrollable, so the runner rejected the
viewport. Zero BEGIN and zero radio cuts; all ten cases NOT_RUN. The original
pipeline result remains UNRESOLVED_STATE, not a successful-chain claim.

Both build variables and the stable pointer were automatically restored
(stable revision 24, beta 11). `reconcile-ready-01` independently bound the
original owner, unchanged prior captures, all 270 live overlap rows and full
pre-BEGIN history, then sealed the same capture and closed only its owned App.
All device/reconciliation locks and private ADB are now closed. Original JSONL
SHA256: 3804a30b1294d7c16e05e7af933394ad2a2670c79d548cadb7917dbda7a24793.

P35-NAV-01 repair reuses `smoke.scroll_viewport`: on the known firmware page,
one native ScrollView can exclude a passive, anonymous leaf success snackbar;
unknown/actionable competitors still fail. `runner.tap` no longer duplicates
viewport selection. P35-CLEANUP-READY only admits readyToInstall cleanup with
no start/resume intent and complete zero-session/zero-durable pre-transfer
history. It does not admit uncertain starts or any BEGIN/apply history.
The new tests replay the unchanged failing native hierarchy and preserve default
no-OTA smoke restrictions. Full-chain success still requires a complete successor.

## Qualified Opt-In Startup Logging

The user approved the global runtime comparison and delegated same-scope work.
`reader-global-01` qualified the actual reader with the installed native APK:
36 original records, no loss/error, five-second initial gate, fresh 30293/full
hash identity and continuing telemetry after exact `log.tag=M` restoration.
Temporary `V` lasted 115.987 seconds. No OTA/radio action; original and owned
cleanup are complete. This is a qualified startup configuration, not proof of
the exact vendor logger root cause or an unconditional default-setting fix.

Runner plans can now explicitly opt into:

    "startup_log_tag": {"before": "M", "during": "V", "seconds": 300}

under `preparation`. Default plans make no property calls. The real runner sets
only runtime `log.tag`, before a verified absent test App is launched, and caps
setup while reserving restoration time. It restores/readbacks the original
before querying for updates, then requires two genuinely new idle records within
the existing event bound. Foreign values, missing telemetry, uncertain writes
and failed restore stop the campaign; an unresolved restoration retains ownership.
No persist.* setting, log clearing, fabricated row or file-polling fallback.

`startup-host-02` passed all 113 affected host tests. The first 112/113 batch is
retained: its new integration fixture incorrectly started with a target/package,
and the readiness adapter needed to hand its last verified state to the campaign.
These are host regressions, not physical ten-disconnect evidence. The real
`pipeline` was then started once for 3.2.95, CI run 41263663499; its live outcome
must be read from `pipeline-live-01/result.json`, never inferred from dispatch.
Evidence is under `.cache/p35-native-log-20261101/`. Historical blockers below
remain originals; their pending-authorization text does not revoke the approval.

## Current State: Native APK Installed, Live Gate Still Fails

The build/install-pending text below is historical. The authorized nonpublishing
Release build `41256532990` completed on `d4d10f9e9649a439fc23d5ae72b8b4b1841710ab`;
`install-reconcile-01` verified the test APK installation without a second install.
Both `reader-native-01` and `reader-native-tag-01` failed the unchanged five-second
real Android reader gate. Their sealed idle-only originals (24 and 28 records),
dedicated-tag restoration and owned cleanup are retained. Do not rebuild,
reinstall or repeat those variants merely because an older summary says NOT_RUN.

Latest `callback-read-01` reverified the same phone and APK, absent test process/
services and runtime `log.tag=M`; it changed no setting and started no App,
capture or OTA. Private ADB closed. Offline inspection confirms that the native
writer's positive return is not a logd-delivery acknowledgement. It does not
prove why this phone loses these records, or that `M` caused it.

P35-LIVE-01 remains unresolved; P35-PIPELINE-01 and R01-R10 remain NOT_RUN.
The proposed next discriminator is a separately approved, bounded global
`log.tag` startup comparison, not another already-failed tag-only trial.
No global-setting change is authorized by this note. See the final continuation
section of `p35-launch-fix-20261101.md` for scope, oracle and restoration.
All referenced evidence is under `.cache/p35-native-log-20261101/`.

## Latest Continuation: Native Logging Candidate

Development checks pass at `d4d10f9e9649a439fc23d5ae72b8b4b1841710ab`, run
`41255844575`: Ubuntu 890/16/0 and Windows 871/35/0 (passed/skipped/failed),
candidate checks 11/0/0 each. The first duplicate-parameter test failure is
preserved. The recorder candidate calls Android liblog synchronously after its
original file flush and fails capture health on native rejection; it does not
weaken the host reader, fabricate telemetry or change the five-second bound.
The underlying missing debug-print output cause is still unproven. A native
positive return alone is not live-delivery qualification.

The source-bound nonpublishing Release APK/EXE build and test-App-only update
remain NOT_RUN, pending the exact request in
`.cache/p35-native-log-20261101/release-build-request.json`. The old build/install
one-shot covered another source and is not silently reused. No Debug APK was
requested. After the Release candidate is verified, the existing real reader
must receive fresh same-capture records and match the sealed original before
`pipeline` can run. R01-R10 and full-chain validation remain NOT_RUN.

The existing 3.2.95 firmware bootstrap approval is already granted; older
REQUESTED/NOT_APPROVED text below is historical. Latest read-only recheck retains
highest backend version 30294, stable/beta revisions 22/11 and restored build
variables, with no active firmware run. This is not a fresh phone identity.
Full CI logs, both digest-verified artifacts, failed originals, reconciliation
and containment audit are under `.cache/p35-native-log-20261101/`.

## Test Firmware Pipeline (2026-11-01)

`pipeline` composes the existing protected GCC rehearsal workflow, verified
artifact download, normal test-channel publication, existing real `run` campaign,
and restoration. No production Release/gate changes, APK rebuild, new uploader,
firmware deletion or device downgrade. Version is an explicit reviewed input,
not automatically incremented after a failed test.

**Host-tested, not live-qualified.** This new entry has not run a new CI/cloud/device
campaign. The earlier real runner stopped on missing fresh logcat telemetry
(`CAPABILITY_MISSING`); passing no-OTA smoke/host tests does not establish working OTA.

From this worktree root:

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py pipeline-check --config .cache\pipeline.local.json
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py pipeline --config .cache\pipeline.local.json --out .cache\p35-pipeline\FRESH_RUN --execute
```

The second command has real side effects and needs actual task authorization.
`pipeline.example.json` intentionally rejects until placeholders are replaced.
Bind the development firmware branch/commit/workflow blob, newer version, test
owner actor hash, full public query, and an existing reviewed runner plan's
path/length/hash. Phone/APK/current identity and controls come from that plan.
New target/hash/release/package values come only from real CI artifacts. This
adapter supports the existing v2 candidate/full-package campaign and derives ten
4096-byte-aligned windows from actual ETU size. This development window policy
does not amend any frozen formal plan. Public query `protocolVersion=1` and BLE
transfer `firmware.protocol=2` are separate fields. The offline check has no
network, device or output effects; it does not qualify credentials/live capability.

Use installed `gh` with explicit inherited `GH_TOKEN`, and provide the current
Access token through `P35_ACCESS_TOKEN`. Never put tokens in config/arguments.
They are omitted from cloud receipts and the phone subprocess. Contained host
helpers own gh/phone processes and caches. Cloud requests are restricted to the
two existing test Pages origins, with expected staging owner and CSRF checks;
no redirects, direct SQL/R2 writes or production route are allowed.

Protected-environment approval remains in the existing workflow. The script waits
within `build.seconds`; it never approves itself. If the bootstrap descriptor
needs a new target binding, obtain its existing required approval first, then
configure only these exact reviewed changes (or leave `variables` empty when the
environment is already correct):

```json
"variables": {
  "OTA_PREVIOUS_RELEASE_JSON": {"before": "EXACT_OLD_JSON", "during": "EXACT_APPROVED_JSON"},
  "OTA_APPROVED_BOOTSTRAP_BASELINE_SHA256": {"before": "OLD_HASH", "during": "APPROVED_HASH"}
}
```

No bootstrap approval is invented. GitHub variable PATCH has no CAS: exclusive
use of the rehearsal environment is required, values are checked before/after
writes, and foreign values are not overwritten on restoration. The local lock
cannot exclude other hosts/operators. Channel updates use the backend's revision
CAS, check both channels, and retain beta/flags. Arrange exclusive test ownership
before execution. Restoring the pointer does not delete registered test firmware.

One invocation performs at most one dispatch and one phone campaign. It binds
before/after run inventory, branch/source/workflow/attempt and a per-run metadata
marker. Artifact digest/size, keyed build/profile, package hashes, test registration
and public latest selection must pass before starting the phone. Failed runner
results propagate. A lost activation reply still enters state-checked restoration;
foreign changes do not get overwritten. Existing outputs reject instead of replaying.

For unresolved remote state, preserve the run directory and
`.cache/p35-pipeline.lock`. After the original owner exits, use cleanup-only:

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py pipeline-recover --prior .cache\p35-pipeline\OLD_RUN --out .cache\p35-pipeline\FRESH_RECOVERY --execute
```

Recovery never redispatches/builds, relaunches the phone or retries OTA. It requires
a terminal bound CI attempt before restoring variables. Unbound dispatch, active
CI or foreign ownership stops for explicit reconciliation. Device/reconcile locks
still require the existing device recovery route and are never deleted here.
Original results remain unchanged.

Verification: 29 new tests (including real offline CLI invocations), 60 runner
tests and offline replay of the retained real 3.2.94 artifact passed in
`.cache/p35-pipeline-tests-20261101/run-03/`. Earlier red path-fixture tests remain
in `run-01/` and `run-02/`. No new live CI/cloud/device operations. This new scope
was implemented by the previous reviewer and requires a different independent
reviewer, not self-acceptance.

### Input Binding Repair And Current Blockers (2026-11-01)

P35-REVIEW-04 now reads the input once, validates that byte snapshot, saves it
unchanged through `h.raw`, and hashes the same bytes. `test_binding.py` exercises
the actual `runner.main(run)` save and `smoke.reconcile` attribution gate for LF,
CRLF, compact and four-space JSON. All bind; changing the saved bytes still
rejects before downstream device admission. No historical plan is rewritten.

The development batch ran `test_binding`, `test_runner`, `test_campaign` and
`test_pipeline`: 102/102 passed in 167.342 seconds. Exact command/streams/closure:
`.cache/p35-remediation-20261101/host-01/`. This is host testing, not OTA evidence.

P35-LIVE-01 is still unresolved. Current no-OTA diagnostics first verified the
phone/APK/idle services, then stopped on a diagnostic caller argument error
before reading logs (`phone-read-01`). The corrected preflight found no USB
device (`phone-read-02`); `usb-timeline-01` independently recorded eight empty
enumerations over an eight-second bound. All private ADB owners closed. No App
launch, recording, upgrade or radio toggle occurred in this batch. These results
do not establish the old zero-log cause or prove the real-time reader works.

Normal read-only GitHub/test API checks succeeded using existing credentials:
firmware source `18f6b3d3af0c24b1ce81573700cd61005b7c530e`, workflow blob
`09603ac912e13c18b025015c9086cae4a8783453`, no active firmware runs, highest
registered version 30294, stable revision 22 and beta revision 11. The current
bootstrap descriptor still targets 3.2.92. Proposed 3.2.95 binding and exact
restorable variable values are in
`.cache/p35-remediation-20261101/approval-request.json`, explicitly NOT APPROVED.
Its descriptor SHA256 is
`5e6659656c306dc16460641db74387b4b1caed165bf6e73ed2675d6ff11af5fd`.
No dispatch, variable/channel mutation or pipeline execution was performed.

Next: restore phone USB availability; obtain the exact bootstrap approval;
finish bounded real reader diagnosis and fresh device identity; then prepare and
execute the real pipeline. The proposed version must be rechecked against that
identity and the live backend. Ordinary protected-environment approval remains
required. Full-chain development validation remains **NOT COMPLETED**, and
independent acceptance remains **NOT_ADJUDICATED**.

## Evidence Boundary Code-Spec

Current live follow-up: the user-approved one-shot `log.tag.flutter=V`
experiment in `.cache/p35-remediation-20261101/reader-tag-01/` failed the unchanged
5-second actual Android reader gate. The temporary value was read back as V,
then restored to the exact original empty value and independently rechecked.
The property was changed after App startup, before ARM; this does not test a
possible startup-cached setting. The 25-record idle App original was sealed and
the owned App/logger/ADB closed. A subsequent read-only all-buffer PID query
retrieved the same App's lifecycle events, but no P35 text. Do not call this a
reader fix or infer that all logcat/PID delivery is broken. Root cause and the
unified pipeline remain unresolved/NOT_RUN. Do not repeat this unchanged variant
or broaden phone logging settings without evidence and the applicable authority.

### 1. Scope / Trigger

Applies to campaign plan persistence/recovery and logcat readiness before any
latest/download/start/radio action. These are separate gates: valid saved bytes
do not prove a live producer, and a sealed App file does not qualify injection.

### 2. Signatures

- `runner.main(['run', '--plan', INPUT, '--out', FRESH, '--execute'])`
- `strict_json(configuration: bytes)` followed by `validate_plan(value)`
- `h.raw(FRESH / 'plan.json', configuration)` and `inputs.planSha256`
- `Android.next_state(limits.event_seconds)` using `Android._pump_logcat()`
- `Android.retrieve(capture_id)` compares the original sequence with live rows.

### 3. Contracts

Read the input once. Validate, preserve and hash the same immutable byte snapshot.
Recovery hashes the preserved bytes before admitting device work. Never rewrite
historical plans or remove this check to repair a mismatch.

Real-time readiness requires a new owned capture header, consecutive valid states
and continuing records within the existing event bound. The automatic campaign
must consume logcat, not the no-OTA Smoke file cursor. A command exit, available
log buffers, unrelated log traffic or an App-file heartbeat is insufficient.

### 4. Validation And Error Matrix

| Input / observation | Required result |
| --- | --- |
| Equivalent LF, CRLF, compact or indented input | Preserve exact bytes; recovery attribution passes |
| Saved plan bytes genuinely changed | Reject before device admission |
| Empty PID logcat while App file grows | `CAPABILITY_MISSING`; no query/download/upgrade/injection |
| Broad logcat has only unrelated processes | Host transport works; target emission remains unqualified |
| Same owned capture is proven idle after failure | Recovery may seal/retrieve it; live qualification stays failed |
| Unknown ownership, applying or incomplete cleanup | Keep owner and originals; no replay or force-stop |

### 5. Good / Base / Bad Cases

Base: one captured input byte sequence owns both the saved plan and its hash.
Good: real `Android.next_state()` consumes new capture rows; original retrieval
later confirms every row and the seal. Bad: a test computes inputs.json from an
already normalized plan, or a file-polling smoke is presented as a logcat fix.

### 6. Tests Required

`test_binding.py` exercises the actual input-save and recovery-attribution path:
four byte layouts, exactly one input read, byte-identical save, same-byte hash,
and modified-file rejection before the downstream device gate. Existing 102-test
batch evidence remains in `host-01`; document edits do not turn it into a new run.
Live qualification must separately bind PID/APK, argv/start order, capture ID,
sequence, event bound and original content. Retain empty streams and failed runs.

### 7. Wrong Vs Correct

Wrong: `h.save(saved, parsed)` plus `sha256(input.read_bytes())` mixes normalized
saved bytes with another input read. Correct: `configuration = input.read_bytes()`;
validate it, `h.raw(saved, configuration)`, hash `configuration`.

Wrong: change timeouts or switch to file polling because logcat is empty.
Correct: compare direct/native/PID/broad reads; locate emission versus transport
failure; qualify the actual reader after an evidenced change, before pipeline.

## Earlier Runner History

Status: development validation, bounded P35-READY-01 repair review and Release
APK/EXE build verification passed at
`d5adfa7de758c075285dc314fdf89166f9bd9423`.
**NOT live-qualified.** New-source build `40821941564/1` passed; its APK and
Windows assets are downloaded and locally verified. Physical capability
qualification and formal P3-5 adjudication remain outstanding.
The verified d5adfa7d test APK was already updated/installed once, with installed
SHA256 e49c3d4ed52cfe28cef86e070df75b7549299b671712ea8de57a412227d5d6a0 and
versionCode92. The older same-version APK predates this recorder. Do not reinstall
either to debug a host script. Originals: `.cache/p35-capability-d5ad/install-02/`
in the implementation worktree; installed APK identity and USB closure passed.
Missing capability is an error, not a mock,
screenshot fallback or permission to start an upgrade for collector qualification.

Latest source self-test:20b2155742eacd73d868d2a06c61ca16b685b157,
checks-only run40931296343/1, analyze/full tests PASS on both hosts. The interrupted
01b80499 build40926252219 failed its Android tests; only its Windows EXE passed.
The new commit changes one test's event waiting, not product code. Its authorized
nonpublishing build40934084986 passed and its test APK was updated once, with
installed SHA2561b87a49ec0355f0b50e6fe3e44274e693b44574512559d7abc25c0476adf4dd7.
The complete terminal smoke20b21557-01 stopped at capture-start: zero logcat bytes,
TIMEOUT and unresolved ownership. This is not a physical PASS. Current read-only
inspection found no USB devices; the original lock/result remain unchanged.

The user requested a P3-5 script without screenshot/model-driven control. This
runner provides native UI discovery, owned continuous logcat, the ten-event
state machine, bounded Bluetooth fault injection and strict result accounting.
It deliberately does not port the Debug-only runtime, use `run-as`, implement
a BLE sender, create a Cloudflare fixture, or modify firmware/Boot state.

## Standalone No-OTA Smoke (Stage A)

Run one command from this Git worktree root:

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py smoke --plan .cache\p35-smoke-20b21557.local.json --out .cache\p35-smoke\FRESH_RUN_ID --execute
```

Replace FRESH_RUN_ID with a never-used directory name, or omit --out when the
configured run_id is fresh. Existing outputs deliberately block instead of
overwriting uncertain/history evidence. A new output alone does not justify a
physical repetition after a known product FAIL; first establish changed inputs,
a useful declared observation or independent execution authority.

No AI session/service, chat response, screenshot/video or manual business tap is
part of execution. Python3.10+ and the already installed ADB executable are the
only host prerequisites; no pip/Appium/Flutter/Gradle installation is needed.
`smoke.example.json` is the public schema2 template. A private project-local
configuration binds authorized serial/model, ADB/key size and SHA256, installed
test APK SHA256/version, exact lowercase target MAC, optional exact advertised
name, scenario and limits. Placeholders are rejected before ADB. The advertised
name only navigates connected rows that hide MAC; the actual device detail MAC
is mandatory before connection. Firmware version/hash pins may be null: actual
post-arm GET_INFO then supplies starting identity, and every captured record must
bind to that unchanged identity. No firmware package, target upgrade identity or
invented OTA window is required.

Manual preparation: USB connection, unlocked phone, initial USB/Bluetooth
permission dialogs, Bluetooth already on, and target powered/available. The
exact candidate test APK must already be installed. Do not install/clear data to
make this pass. Keep the phone/target free of other operators and upgrades during
the finite window. A system dialog/foreign foreground produces BLOCKED, never
automatic permission approval.

The script checks the worktree lock, previous original captures and OTA service;
verifies phone/installed non-debuggable APK; launches only the test package;
follows the installed speedometer native semantic route to the configured device
detail; verifies MAC before connecting; enters firmware page; starts one capture;
calls `p35-reconnect`'s normal connector plus GET_INFO; requires a new identity
event and bounded heartbeat/time coverage; stops capture; retrieves exact App
JSONL; checks remote size/SHA256, open/close IDs, full sequence/count/body digest,
health/loss, live/stored equality and unchanged identity; reports; and closes its
owned App/logcat/private ADB processes. Reconnect does not disconnect an established
link, toggle global Bluetooth or transfer firmware. Stage A never clicks upgrade
check/download/start/resume. Native fields and fresh node/viewport bounds replace
fixed screen coordinates. Missing/ambiguous/disabled controls cannot cause blind
taps; each mutation has a bounded observation, not just command exit0.

Device discovery traverses the unique package-owned native scroll viewport in
both directions (at most 24 swipes, also bounded by stage/total deadlines).
Each read first checks foreground and PID. Coordinates come from that viewport;
MAC plus row positions, not RSSI or whole XML equality, track scroll progress.
The list is anchored by its available-device header/MAC rows; a scrollable scan
snackbar does not become a second candidate viewport. Multiple actual device-list
viewports still fail closed.
An advertised name never overrides a different MAC in the same row, and the
detail page must still verify the exact MAC before connecting. Search observations
and scroll intent/return receipts are retained in `journal/`. A missing target,
missing viewport or exhausted coverage returns `TARGET_SEARCH_INCOMPLETE`/exit2,
not a claim that the target is powered off or absent from the full scan results.
This is native accessibility traversal, not screenshots, Dart memory access or
a backend scan-list API. A future full-data interface requires an explicit App
observation contract and a separately verified APK; it is not silently present
in the installed Release build.

One normal reconnect action may emit both connector and page-read GET_INFO
identities. The bootstrap selects the latest identity already present in the
received query batch, never a future record from the final archive. Coverage
starts there once; any later identity/link loss is still a test FAIL and cannot
move that boundary. This avoids misclassifying an intermediate identity refresh
inside an already-observed bootstrap batch as a coverage failure.

Stage A now uses `observationSource=app-file`: before one ARM it verifies the
original file baseline and current process; a unique new file's strict header,
target-bound sequence and unchanged sampled prefix establish ownership. Each
bounded prefix is preserved under `observations/`, with host time, stage and
consumed sequence in `journal/` and `capture.fileSamples`. Partial tail lines wait;
complete corruption, truncation, prefix changes and source conflicts fail closed.
The final file must equal the observed sealed bytes and pass the unchanged fresh
identity/heartbeat/count/hash/health criteria. It is never substituted for live
observations. Logcat is diagnostic; actual overlapping records must agree. This
does not qualify file polling for Stage B fault-trigger timing.

Read-only inspection of the exact unresolved owner uses the same recovery entry:

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py smoke-reconcile --plan .cache\p35-smoke-20b21557.local.json --prior .cache\p35-smoke\p35-smoke-20b21557-01 --out .cache\p35-file-fix-20261030\FRESH_INSPECTION --execute --inspect-only
```

It never ARM/STOP/launches or releases the original lock. `inspection.json`
classifies A/B/C/D from baseline, actual files, phone/APK and original/current
PID. Recovery without `--inspect-only` admits only positively attributed active
or sealed captures, or a positively verified unstarted recorder. A sealed file
never causes another STOP; an unhealthy seal remains FAIL but can independently
resolve ownership. Successful zero-log recovery archives and releases the exact
original lock only after owned cleanup; the original TIMEOUT/result is untouched.
An absent/changed process, unreadable store or ambiguous candidate retains it.
A pre-ARM navigation failure may have no logcat file at all. Recovery then requires
one confirmed original launch, returned HOME/DEVICES taps only (no uncertain
scroll/upgrade/recorder actions), the same PID/APK, unchanged original capture
baseline and a known native scan page or device-center home with no recorder/
upgrade controls. A background owner may be restored only through the existing
same-PID foreground route, never by cold-launching its replacement.
`PRE_ARM_NAVIGATION_VERIFIED` does not start a capture or reconstruct smoke PASS.
Only after fresh pre-ARM page/store checks may cleanup stop the originally owned
test App and release that exact owner. Missing/changed evidence keeps the lock;
`--inspect-only` never stops the App or releases ownership.
Full WindowManager dumps are parsed only after explicit current policy/animator/
session/display framing and a completed current windows section. A nested LAST
ANR display/focus is historical, not a second live foreground. Historical-only,
truncated, locked or conflicting current observations remain blocked before
reading a UI hierarchy.

New launches retain `launch-returned` (successful activity result and process
binding) separately from `launch-confirmed` (UI readiness). If launch succeeded
but UI validation failed, zero-log reconciliation can derive that attribution
from the closed original ADB command/stream receipts, pre/post PID observations
and the original capture-directory/readback baseline. It never inserts an event
in the old journal. A campaign-format prior is admitted only for a plan-bound
pre-ARM launch failure with all ten cases NOT_RUN and query-only original actions
apart from the single test-App launch. Use a schema2 smoke configuration with
the same phone/APK/device/current firmware pins; the ordinary `smoke-reconcile`
entry remains the only recovery route. This resolves ownership, not campaign PASS
or permission to replay the failed formal command.
For that narrowly attributed pre-ARM launch, an already-exited original process
can also be resolved without launching or stopping any App: two fresh absence
observations, an available non-busy service dump and repeated unchanged original
capture baseline are required, with no current test-App foreground or new file.
A replacement PID, unavailable service state or changed baseline remains blocked.
`PRE_ARM_PROCESS_EXITED_VERIFIED` resolves the old launch only; it does not claim
current firmware identity, UI readiness or an observed upgrade state.
A previous recovery lease that only restored the same original PID may be
reconciled after its owner is dead and ADB is closed: its byte-matched original
lock, no-new-capture inspection and unique launch intent/confirmation must agree;
any tap/scroll/stop/unknown action prevents this narrow route. Originals are
archived, not deleted to bypass uncertainty.

Default evidence: `.cache/p35-smoke/RUN_ID/`. Optional `--out` must name a fresh
worktree-local directory. Existing outputs are never reused. `result.json` records
stage, reason, automation/test/cleanup outcome and NOT_ADJUDICATED; `report.txt` and the
console are redacted summaries. Original `app-capture.jsonl`, integrity report,
`journal/`, split `usb/` command/closure receipts, `logcat.*`, previous originals
and `audit.json` remain without deletion. Raw originals/USB/UI receipts are private
local evidence and can contain IDs; do not publish them. Configuration copies
redact serial/MAC/key paths and retain configuration SHA256. No credential bytes
are written to reports.

| Exit | Outcome | Meaning |
| --- | --- | --- |
| 0 | PASS | Complete configured no-OTA sequence and owned cleanup observed; not independent acceptance |
| 1 | FAIL | Confirmed test/integrity/host/cleanup failure; inspect stage and originals |
| 2 | BLOCKED | Invalid input, unavailable phone/UI/identity, busy target or unresolved action; no AI fallback |

`automationOutcome=COMPLETED` is separate from `testOutcome=PASS/FAIL` (also exposed
as `outcome`). Completion requires the entire configured route, verified original
archive, resolved capture and owned cleanup/lock closure. Known healthy idle,
same-target false link/fresh flags or wrong expected firmware pins produce FAIL,
not fabricated fresh identity. The script still completes the bounded capture,
stop, retrieval and audit without a chat turn. `capture.failures` identifies the
codes, first/last sequence and affected count; `freshIdentityVerified=false` and
`identityBound=false` prevent misusing this as a qualified device identity.
The flags/identity in original JSONL are never rewritten.

Safety/integrity failures set `automationOutcome=STOPPED` and stop further test
actions. One bounded stop/salvage is allowed only for
this run's positively identified, still-idle capture. Uncertain taps/stops are not
replayed. Corrupt telemetry/unknown state prevents even that stop. Host workers
still close and partial originals remain. Unresolved actions keep the lock and
report BLOCKED, with underlying failure in `executionError`. Existing unresolved
locks are never deleted: liveness and prior owner result/USB closure are inspected/preserved
before BLOCKED. A dead PID is not proof its action finished. Reconcile owner and
actual device result before another mutation; do not erase a lock/log to bypass
admission.

The installed recorder is one-use per OtaService lifetime. A sealed capture can
leave arm disabled in the same process. Without explicitly authorized
`lifecycle: {"restart_closed_recorder": true}`, this is BLOCKED before a collector
or capture starts. The public template defaults to false; omitted lifecycle also
defaults to false. The user's2026-10-29 permission enables it in the private config.
The old config's exact bytes remain in `.cache/p35-smoke.pre-restart-20261029.json`.

With this permission, only a unique native p35-arm showing the installed exact
`closed` status, audited sealed old captures and stable idle firmware UI with an
enabled p35-check can trigger one test-package force-stop. That check button is
never clicked. Old PID absence and a different new PID are required; no uncertain
stop/restart is replayed. The normal launch/MAC connection/navigation then runs
automatically. All prior capture filenames and exact remote size/hash are checked
again and retained under `after-restart-captures/` before arming. The newly owned
test-App process is closed at final cleanup only after its capture/original is
resolved and its current native/producer state is still idle. Unknown/busy state
prevents that stop and reports explicit unresolved cleanup. No ordinary App,
data/log deletion, APK operation, global Bluetooth toggle or MCU reset is involved.
Repeated same-process capture is not claimed; this is a verified new process.

A cold launch also records process ownership: the pre-launch PID query must
prove that the test package has no process, and launch/PID/foreground must be
confirmed. Its new process is closed once after sealed-capture and idle guards,
without a preparation restart. A pre-existing process is not owned or stopped
merely because the runner brings it forward. Ambiguous/changed PIDs or an
unconfirmed launch retain the unresolved state and never authorize a blind stop.
`cleanup.ownedAppLaunchConfirmed` distinguishes this ownership from
`cleanup.appRestartConfirmed`.
An owned cold launch does not waive an attempted preparation restart's integrity
gate: changed/missing old originals keep the new process and unresolved lock,
without a second process stop. Any unresolved owned action reports BLOCKED/exit2,
including an unconfirmed cold foreground or a cold-process stop timeout. The
underlying execution/cleanup error stays in the private result.

Offline commands:

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py smoke-check --plan CONFIG
python -I -S -B -X utf8 Tools\ota\p35-automation\test_runner.py -v
python -I -S -B -X utf8 Tools\ota\p35-automation\test_smoke.py -v
```

`test_smoke.py` uses synthetic Phone/Process endpoints for the complete real
route, decoder, retrieval and cleanup, plus real report/lock filesystem behavior
and isolated CLI subprocesses. Fixtures remain under
`.cache/p35-standalone-selftest-20261029/`; their retained synthetic locks are not
the worktree device lock. No physical ADB/OTA/AI calls occur in these tests.

Lifecycle regression completion on2026-10-30:54 smoke methods pass; the43 runner
methods' unchanged-source PASS is reused (97 total). Added terminal-route
negatives cover ambiguous pre-launch PID, unconfirmed/error/timeout launch,
missing/ambiguous post-launch PID, changed existing PID and a replaced owned PID
at cleanup. Unknown outcomes preserve the lock and never replay launch/stop or
read an unconfirmed hierarchy. Originals and closed-process receipts:
`.cache/p35-repaired-build-20261030/host-tests-04/` (smoke), `host-tests-03/`
(runner). The first expanded smoke batch's failed injection fixture is retained;
its PID replacement is now explicitly injected at cleanup, not before reporting.
Flutter test wait remediation passes full Ubuntu885/16/0 and Windows866/35/0
development tests (passed/skipped/failed), plus11 candidate checks each; both
analyzers report no issues. Exact source, original failing build, raw job streams
and full unextracted development-log archives are bound in the task note's
P35-CONT-10. Development PASS is not an APK/EXE build or independent acceptance.

Provenance: `runner.foreground_ok` and `runner.idle_equivalent` adapt repairs by
the prior acceptance agent in `.cache/p35_capability.py` (multi-display null focus
and layout-only XML movement). That adapter is not imported or required by the
delivery. A different independent reviewer must review the adopted functions and
their consumers. This agent provides implementation/self-tests only. Physical
Stage A was subsequently attempted and failed; see the physical self-test below.
Stage B retains the existing campaign below; no real OTA/fault run is authorized
here. Historical verification statements below retain their original scope.

Final host self-test on2026-10-29: 43 existing +24 new unittest methods passed,
zero failures, including four actual isolated CLI invocations (expected exits
0/0/2/2). Originals and closure receipts:
`.cache/p35-standalone-selftest-20261029/final-01/`. The original install audit
inventory also rehashed successfully, without repeating installation. This is
implementation self-test, not physical smoke or independent acceptance.

### Physical Self-Test And Host Repairs

The user's supplied MAC is now bound in the private configuration; display_name
is empty. The first actual unattended run is
`.cache/p35-smoke/p35-smoke-20261029-01/`: it verified phone/APK, launched and
navigated the test App, and armed one real capture. It reported FAIL at cleanup,
with original executionError=IDENTITY_MISMATCH at capture-start. Initial states
were healthy/idle but linkConnected=false/freshConnection=false. No OTA, radio
injection, reinstall, force-stop, MCU reset or cloud operation occurred.

Host repairs distinguish bounded bootstrap from the post-GET_INFO oracle:
pre-query records must already be healthy, target-bound and idle, but are not
claimed as fresh identity. PASS still requires both link flags true on a new
identity event and every subsequent coverage record. False flags produce a
product FAIL while permitting safe deterministic sealing; missing/malformed
fields remain fatal. Disconnected idle recorders may be stopped safely;
corrupt/wrong-target/busy captures may not. Unsealed growing files are preserved
as prefixes rather than falsely checked as immutable archives.

The supported bounded recovery entry closes/retrieves only an evidenced owner's
existing recorder, never replays the smoke or starts another capture:

```bat
python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py smoke-reconcile --plan .cache\p35-smoke.local.json --prior .cache\p35-smoke\p35-smoke-20261029-01 --out FRESH_WORKTREE_LOCAL_RECOVERY --execute
```

To resolve an already recovered old owner, add `--sealed-original` with the
retained App JSONL path. This is query-only with respect to the recorder: it
requires the original failed configuration, dead owner/closed USB, unchanged APK
and App PID, healthy idle sealed bytes equal to that local original, no active
recorder/OTA service and an enabled native `p35-check` idle guard. It never clicks
that check button. It verifies current remote size/hash and cleanup, archives
exact old lock/result/sealed bytes in the fresh output, then releases only that
proved owner and its own recovery lease. Outcome ORIGINAL_OWNER_RESOLVED is not
smoke PASS. Open/changed originals, busy UI or cleanup failure retain both locks;
even a lone recovery lease blocks a new smoke. Normal recovery without this
argument continues preserving the old owner lock.

It binds the original configuration, capture ID, same installed APK/App PID,
original lock and dead owner/closed USB route. A fixed exclusive recovery lease
serializes actions. A previous lease can be reclaimed only after proving its
owner dead, no mutation intent/stop/start, and successful USB closure; its original
bytes/results are preserved. Existing capture stop is issued at most once, only
after a healthy idle prefix check. A sealed existing file needs no stop. If the
App is backgrounded, the existing launcher brings only that test App forward and
must retain the original PID; no hierarchy is read from the foreign foreground.
There is no force-stop/restart, upgrade or explicit reconnect/GET_INFO button
replay in recovery. Bringing the existing page foreground can invoke its normal
read-only GET_INFO lifecycle callback; the observed event1394 is retained.

Recovery01 was blocked when the phone switched to chat; no hierarchy or stop
was issued and USB closed. With the tested foreground/lease fix, recovery02
ended the original capture once and retrieved 1404 unchanged records, 825019
bytes, archive SHA256
45f31eb1e5abb4758ccb04e61b8f7615da572284015317191a101a788c4bdce0.
Originals: `.cache/p35-smoke-reconcile-20261029-02/`. Sequence/count/body digest/
healthy footer/remote size/hash passed. This is ORIGINALS_RECOVERED, never PASS
for the original unattended run. Original failed result/device lock stay intact.
Host repair/recovery prolonged the App capture to1399.001s, not the configured
8s observation; the recovered history must not be called that short smoke.
Recovery02's cleanup boolean fields were not reset despite verified closure;
the later host fix resets them, while preserving those historical result bytes.

The recovered identity event1394 still has both link flags false; all1404 records
have false link/fresh flags. It reports versionCode30293 and image SHA256
709eb0d46625e00a29003d8036d59e7754377bcb389efc6e26c0be6cbf131cdb,
not a qualified fresh-connection oracle. OtaService.startP35Recording directly
constructs BluetoothDevice.fromId with the lowercase address, bypassing
BleController._mobileOtaDevice's existing canonical uppercase Android MAC path.
An App repair may later reuse that canonical device/state source, never force
telemetry flags true. The user's subsequent direction supersedes proposing an
APK update as prerequisite: first validate deterministic completion and a truthful
FAIL verdict on this existing APK. App source/binary remains unchanged. Do not
build/download/reinstall to repair this host script. A consumed one-use recorder
still needs an explicitly authorized fresh test-App process, not data clearing.

Post-repair host regressions passed43 existing +30 new methods, zero failures.
Receipts/derived hardware analysis are under
`.cache/p35-live-fix-selftest-20261029/`. Only implementation self-test and recovery
are reported. No independent acceptance or physical ten-fault campaign occurred.

Latest host-only batch after product-verdict/owner-release changes passes43
runner +40 smoke methods (83 total), with unchanged before/after source hashes.
Originals: `.cache/p35-product-verdict-tests-20261029/final-03/`. A single-main
synthetic route covers completed product PASS/FAIL and explicit cleanup failure.
The actual query-only owner-resolution command returned ORIGINAL_OWNER_RESOLVED,
exit0, stopAttempts0, with identical1404-record original and confirmed USB closure.
Evidence: `.cache/p35-smoke-owner-release-20261029-01/`. Resolved old lock bytes
are archived there; actual device/recovery locks are absent and port5093 is closed.
No new capture or App restart occurred. Full physical smoke on the corrected
script remains unexecuted pending an authorized fresh test-App process.

Latest authorized lifecycle/full-smoke result supersedes that pending status:
90 host tests pass (43 runner +47 smoke), with unchanged before/after source pins.
Original host receipts: `.cache/p35-restart-selftest-20261029/final-01/`.
One actual terminal invocation completed the entire no-OTA route on the existing
APK in158.836s without AI/chat/manual business actions. Result automationOutcome
COMPLETED, testOutcome FAIL, exit1: all27 original records retain false link/fresh
flags, so freshIdentityVerified/identityBound are false. The27-record/16041-byte
JSONL has verified sequence/count/body digest/footer/remote hash;14 post-query
heartbeats and13.367s of producer coverage exceed the configured8s minimum.
Old1404-record original is byte-identical before/after one verified restart.
Owned new App, recorder/logcat and private ADB closed; both locks are absent.
No APK build/download/install, OTA, fault injection, MCU or cloud mutation occurred.
Result/report/originals: `.cache/p35-smoke/p35-smoke-20261029-02/`; top-level command
receipts: `.cache/p35-smoke-entry-20261029-02/`. This demonstrates implementation
execution/self-test, not product PASS or independent acceptance. Real Stage B is
still unexecuted/ungranted; the App observation-source issue remains unresolved.

### Recorder Source Repair Self-Test (2026-10-30)

The observation-source repair now passes checks-only development validation at
`01b80499633c6f63c4774703794aa6c78d1c06df` on the existing development branch:
[run 40917454753/1](https://github.com/Eitan-S-23/E-Track/actions/runs/40917454753).
The recorder reuses BluetoothService's canonical native device handle and reads
its actual connection state on every snapshot; generation-bound freshness and
the host's PASS criteria are unchanged. Ten added regressions cover canonical
MAC lookup and real service/recorder lifecycle with synthetic BLE, not a phone.
Both hosts report no analyze issues. Full tests: Ubuntu885 passed/16 skipped/0
failed; Windows866/35/0. Candidate checks:11 passed on each host.

This does not supersede the installed APK's physical FAIL above. No new APK/EXE
build, APK download/install, phone operation or independent acceptance ran in
this repair batch. The installed version92 remains unchanged. Original failed
and green CI receipts are retained under `.cache/p35-recorder-fix-20261030/`;
the task note records their exact inputs and conclusions. A later authorized
changed-APK build/install and one no-OTA physical smoke are still needed before
claiming product PASS. Existing host/provenance review obligations remain.

## Legacy Entry Points

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
receipts. The existing worktree device lock is respected. Legacy probe/run/retrieve
never install or restart the APK; smoke launches only the installed test App.
Legacy start admission requires a known idle,
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
Flutter may place the tap action below the identifier container. The resolver
accepts exactly one package-owned clickable descendant (or ancestor), rejecting
multiple actions, hidden/disabled controls or foreign nodes. The bootstrap selector
is restricted to p35-arm; a plan cannot substitute an upgrade button before capture.

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

### Automatic Campaign Handoff, Fixed30294

`run` now launches the pinned test App, discovers/connects the exact MAC and opens
the firmware page through Smoke.start/navigate. It reuses that Phone, private ADB
and device lock; only one owned logcat and one ARM are used. `record_smoke` is
never called. Fresh query-bound identity gates the original Campaign. After ten
recoveries and post-reboot target identity, the normal App latest action must
produce NO_UPDATE before one STOP and strict original/logcat equality audit.
Shared Smoke cleanup closes the originally launched App and the same logger/ADB.
Unknown post-transfer/apply/reboot state keeps the lock/App; a bounded original
prefix is preserved without manufacturing a footer or repeating the upgrade.

One command from the implementation worktree, only after real assets and user
device authorization are bound:

    python -I -S -B -X utf8 Tools\ota\p35-automation\runner.py run --plan .cache\p35-campaign-30294-20261030\plan.pending.json --out .cache\p35-campaign-30294-20261030\run-once --execute

That configuration currently rejects execution: target30294 is fixed but image/
package/release/window bindings are null and adapter permission is false. No
3.2.94 asset has been built. Exact source/protected build/test-cloud authorization
is in p35-build-30294-preparation.md and the project-local build-execution.json/
authorization.json. The old pending plan and runtime FAIL remain unchanged.
After the true full package exists, derive ten windows from its length and
observed candidate protocol; do not use the1MiB template as a real package.
The optional preparation fields configure exact advertised name, bounded command/
cleanup times and the already-qualified closed-recorder lifecycle route.
Probe/retrieve remain legacy read-only entries; their admission is not run's
automatic launch/navigation. No extra App build, install or preliminary smoke.

Ten-event preparation2026-10-30: the existing `run` entry is retained. The private
`.cache/p35-ten-prepare-20261030/plan.pending.json` binds the observed phone/test
APK/current30293 identity but deliberately leaves target/package/release/protocol
and all ten windows null, with adapter permission false. It is BLOCKED, not a
real runnable configuration. Local3.2.93 full/patch packages cannot be a forward
target for a board already on30293; example30294/1MiB windows are not assets.
`readiness.json` records the remaining inputs, exact future command and self-tests.
No device execution, build, download or installation accompanied preparation.

Existing originals qualify the actual logcat record mapping (39/39 App records),
not transfer-event latency or adapter command capability. `run` uses owned-PID
logcat, never Stage A's slow file polling, for injection. It rechecks the latest
durable/bitmap before disable and actual link-loss position afterwards; missed
windows fail rather than count as recovery or widen the plan. The original
foreground-page prerequisite is superseded for run by Automatic Campaign Handoff
above; it remains a prerequisite for the legacy read-only probe.

Run reports retain all ten `caseResults`: untouched cases are NOT_RUN, the active
failed stage is FAIL, and completed recovery observations remain RECOVERY_OBSERVED
if final identity/archive/cleanup fails. PASS requires full campaign success.
Detailed successful recovery rows and raw originals remain private in result.json;
the console excludes raw archive/final/device rows. A failed attempt is not
restarted to produce10/10. Implementation prepares; acceptance executes one group.

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
Read-only probe/retrieve can preserve and reconcile an old lock only after the
existing helper proves its owner is no longer running. They do not erase it.

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

Final Release-integration development validation:
[run 40776361875/1](https://github.com/Eitan-S-23/E-Track/actions/runs/40776361875),
Flutter 3.47.8 / Dart 3.13.7. Analyze reports no issues on both hosts. Full tests:
Ubuntu 869 passed / 16 skipped / 0 failed; Windows 850 / 35 / 0. Candidate profile
checks: 10 passed on each host. P35 host tests: 43 passed locally and on both CI
hosts. No Debug APK requested. Node runtime deprecation annotations remain; these
are not release packaging/signing or hardware results.

The four failed development inputs and final green input retain ten original
API ZIPs, verified against API lengths/digests without extraction. Inventory and
full result summary: `.cache/p35-automation-release-tests/verification.json` in
the source worktree; originals: `.cache/p35-integration-20261028/records/p35-auto-*`
under the authorized project root. No successful device operation was repeated.
Code is on `dev/flutter/p35-automation-20261029`, not main. This final results
paragraph is a local handoff update, not an extra unchanged-code CI dispatch.

Authorized build-only continuation: `build.yml` run
[40809830781/1](https://github.com/Eitan-S-23/E-Track/actions/runs/40809830781)
passed Android and Windows Release builds on the same `ff3ce0f5` source, including
full tests (869/16/0 and 850/35/0), analysis and artifact uploads. Android fixed
signature verification passed. Existing `.p35acceptance`, `adaptive-v2-candidate`
and the permanent test firmware endpoint were retained. No version bump was made
for this nonshipping exact-source verification; these bytes must not replace a
published same-version package. Release and Pages jobs were skipped. No install,
execution, backend mutation, merge or push was performed. Android dependency/SDK
warnings and missing App self-update signing-public-key configuration remain.
Full build details and local download disposition are in the task note.
Windows artifacts were retrieved and verified locally. Android was initially
incomplete; the user's subsequent continuation completed a new HTTP206 tail and
the full local APK/vendor verification. See the task note's readiness follow-up.
That old `ff3ce0f5` APK still contains the stale connection-generation observation
issue; it is not a binary of reviewed repair `d5adfa7d`. Artifact integrity does
not qualify live automation or permit installing the old APK for the campaign.

The subsequent authorized `d5adfa7d` build is
[40821941564/1](https://github.com/Eitan-S-23/E-Track/actions/runs/40821941564).
Android and Windows analysis/tests/Release builds/uploads pass; test counts are
875/16/0 and 856/35/0. Local APK SHA256 matches CI, fixed signer and package
identity pass, and the Windows AMD64 bundle matches its standalone EXE.
Artifacts and verification.json are under the project root's
.cache/p35-integration-20261028/p35-fix-build-40821941564/.
This is a nonpublishing exact-source build, still 1.0.66+92/.p35acceptance;
no release replacement, device installation or OTA occurred. Full diagnostics,
artifact identities and download provenance are in the appended task note.
# Acknowledged Live Stream Candidate

The current single-upgrade profile does not cover background, screen lock,
intentional disconnect or resume. Ordinary P3-5 covers ten adapter-disconnect
windows, not every background/P5 fault. New run reports explicitly include
`plannedCoverage`; planned scope is not evidence of successful execution.

The opt-in `preparation.live_stream_port` uses the new `p35-arm-stream` control,
the pinned side-by-side test APK, loopback-only port49135 and an owned private
ADB forward. `live_stream.py` receives each original batch, verifies sequence,
identity and final body digest, writes/fsyncs the exact bytes, then ACKs the
batch length/SHA256. Five-second live and two-second publisher ACK bounds apply;
there is no reconnection, gap suppression, file-polling fallback or OTA control
in the publisher. `live-stream.wire` preserves even rejected/partial frames.
The existing logcat stream remains diagnostic and gets its own equality report.
Its loss is not hidden or backfilled, and old plans retain their original route.

In reliable mode a native mirror rejection is persisted once in the App's
`p35-logcat-diagnostics/CAPTURE_ID.json`, with the exact failed original line,
hash and native return. `FAILED_DISABLED` explicitly records that subsequent
native mirroring stopped; it is not lossless-Logcat success. This diagnostic
failure no longer stops an already persisted/ACKed primary stream. Failure to
persist the diagnostic still fails capture, and primary stream/storage failures
remain strict. `NO_NATIVE_ERROR_OBSERVED` also does not prove lossless Logcat.
The host requires this status file and binds it to the original during retrieval.
Legacy non-stream capture still fails on a native write error. No missing rows
are synthesized or copied back into Logcat.

This is a development repair candidate, not a change to frozen P3-5 acceptance.
Real no-OTA high-rate qualification and current coverage are tracked in
`docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/p35-log-integrity-20261101.md`.
App96 source900b4a2e passes dual-host development CI41309522637 and nonpublishing
APK/EXE CI41309995282. After the user identified the prior accidental install
cancellation, phase04 installed the same APK and passed the real no-OTA probe:
6061 original records/649 batches, exact live/App byte equality, healthy footer,
pre/post-load30303 full-hash identities and verified owned cleanup. Native
Logcat again returned-11 at1325; its failure and4736 missing later rows remain
explicit diagnostics while the primary stream stayed complete. Evidence is in
`.cache/p35-log-integrity-20261101/probe-04/` and `audit-04/`. Earlier failed
attempts remain unchanged. This is not lossless-Logcat, full-pipeline or
background/disconnect/resume acceptance; those combined scenarios were not run.

User-required follow-through subsequently passed the real single pipeline:
CI41313723543 built/published new3.3.4, App96 downloaded/verified/transferred it,
fresh post-reboot identity matched the full target hash and latest returned
NO_UPDATE. All5205 App/live-stream/Logcat records match, with a healthy original
footer. Build values and test stable pointer/settings restored (revision42),
beta11 unchanged; owned App/ADB/stream/locks closed. Evidence and limitations:
`docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/p35-stream-pipeline-20261101.md`.
This is REAL_SINGLE_PIPELINE_PASS, not a ten-cut/background or whole-card result.

## Explicit Development Scenario Profiles

The opt-in pipeline/template `test_profile` may also be `resume-once` or
`background-lock`. Direct `run`/`check` use `--scenario-coverage`, mutually
exclusive with `--single-upgrade`. Both require the reliable stream and actual
runtime state schema2 from the new App candidate; old schema1/container originals
remain valid and unchanged. Mixed state schemas inside one capture are rejected.

- `resume-once` requires `allow_bluetooth_toggle=true`, one positive durable
  window (4096 through below the midpoint), and no display-control permission.
  Pipeline derives that window from the newly built ETU. Recovery uses the
  unchanged OFF/link-loss/MCU resume-offset/first-DATA/durable-progress oracles.
- `background-lock` requires `allow_bluetooth_toggle=false`, `cases=[]` and
  `allow_display_control=true`. It verifies acknowledged runtime ownership,
  Home background progress, actual screen lock with continued durable progress,
  and return to the same task without another BEGIN. Each progress interval
  lasts at least two seconds; this is not long-duration background endurance.
- Secure keyguard is never disabled. Wake requests a real user unlock, bounded
  to120 seconds while the same live capture continues. Existing activity/PID
  restoration is single-use. Failed or unknown display state keeps unresolved
  ownership rather than replaying sleep/wake or restarting the sender.

The ordinary ten-window plan and single-upgrade prohibitions are unchanged.
Planned coverage is not executed coverage. Code/tests and current real-execution
disposition are recorded in
`docs/ota-exec-notes/Flutter-release-fastpath-2026-10-26/p35-scenarios-20261101.md`.

For long runtime records, explicitly set `preparation.logcat_binary=true`
(requires `live_stream_port` and the events buffer). It uses the byte-preserving
`adb exec-out logcat -B` route, retains `logcat.stdout` as binary wire and saves
exact P35 message bytes as `logcat-decoded.jsonl`. The binary parser validates
header sizes, buffer ID, actual PID, payload/string lengths and UTF-8. It does
not reconstruct truncated text from App records. A read-only real-buffer check
matched3111 long messages to the existing App original with no new OTA.

The older text renderer may clip long JSON despite a successful native write.
Diagnostic parse errors retain line numbers, lengths and hashes and explicitly
set `exactEquality=false`. They do not erase an independently validated complete
App/ACK stream or masquerade as complete Logcat delivery. The native status,
wire identity and missing-sequence inventory are separate. Old failed results
remain unchanged; `verifiedStages` preserves completed device/query stages if a
later evidence step fails. No primary parse, sequence, footer or hash check is
relaxed by the diagnostic-only treatment.

Binary diagnostics also retain `logcat-live-snapshot.bin` and a distinct finite
`logcat-terminal.bin` read after sealing. A closing live collector may leave a
partial last frame; strict decoding still rejects it. Prefix auditing reports
its exact location/hash and only decodes complete frames. Paired original
coverage checks overlap, missing sequences and original header/footer without
merging or backfilling either wire file. `completeCombinedCoverage=true` is NOT
`exactLiveCaptureBytes=true`. Primary App/ACK-stream integrity is independent.

Real development coverage now includes one resume and one background/lock run,
ending at30306 with verified full hash. Their original pipeline failures remain
failures; later host repairs are covered by real-original replay and host tests,
not a new physical pipeline PASS. See the scenario note for exact dispositions.
