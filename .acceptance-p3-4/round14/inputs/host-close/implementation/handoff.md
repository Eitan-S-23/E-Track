# P34-HOST-CLOSE-01 Caller Integration

Owner: original host implementer; next owner: the current independent reviewer.
R: `D:/github/my/E-Track/.cache/p34-final`.
C (this fresh implementation evidence): `R/.cache/p34-host-close-01-callers-20261013`.
Base HEAD: `02013607ca38eaf5cff0d5c4fc3de8259fbff916`.
Branch: `acceptance/p3-4-v2-20261009`; existing changes remain uncommitted.

## Pre-Edit Findings And Scope

Read the existing task note, Independent Review: P34-HOST-CLOSE-01, and
`.cache/p34-host-close-01-review-20261013/final-review.json` plus its three
caller observations. The primitive is independently verified, but the batch
is NOT_CLOSED because C1/C2/C3 remain. Its source SHA-256 is still
`a0d98161aadccee0346b8f7438cf65566ae6e72d7cf8cc576641e833d7cc6431`.
Neither `live_host.py` nor the accepted `ProcessCloseTests` will be edited.
The prior review's corrected fsync fixture issue is not a remediation item.

The three caller issues are one batch: Network.close must drain remaining
owned resources after tunnel failure; Network._start/read must keep the reader
operation error through close; Phone.close must keep the stop-command error
through server cleanup. Network.start's outer failure-save/close path is part
of the same error-propagation repair. Use the existing Process preservation
helper and bounded one-shot cleanup pattern, not a new controller.

Only lifecycle code in `live_phone.py` and corresponding live tests may change.
Use a one-shot attempted/error state distinct from confirmed closure, retain
truthful resource observations and cleanup diagnostics, and never retry a
failed close or overwrite its receipt. Handle partial HTTP startup without
calling BaseServer.shutdown before serve_forever has a started thread: the
standard library explicitly documents that call as deadlocking otherwise.
The existing five-second thread join and stop/operation budgets are retained.

Shared-root rules match the versions already read in this thread; shared root
is read-only. No `.trellis` exists in R. `host_io.checked_output` preflight
resolved R, both code targets, C and its outputs with directory-boundary and
reparse checks. All commands use cmd.exe, login:false, explicit R and Python
`-I -S -B -X utf8`. Tests use fresh contained `P34_HOST_TEST_OUT` directories
and the existing `build.run` / `selftest.py` entry. Originals of this turn's
two editable files are retained to produce an incremental caller-only patch,
not a HEAD diff that repeats the already accepted primitive change.

No device operations, additional OTA, commit, push, CI, new formal round or
historical contract/matrix/accounting writes. A/B CLOSED, v11 HARNESS_FAIL,
v12 EVIDENCE_GAP, v13 candidate-original-evidence PASS and cumulative 3/3 remain
unchanged. These modeled callers neither explain v12 nor prove a real reader
leak. Whole P3-4 completion and the P3-5/P5 responsibilities remain unchanged.

## Implementation And Validation

Disposition: DECIDED, C1/C2/C3 implemented and development self-tests passed.
The current independent reviewer still owns adjudication of P34-HOST-CLOSE-01.
This is not independent acceptance or a new formal round.

| Subitem | Implementation | Regression oracle |
| --- | --- | --- |
| C1 | Network.close makes one best-effort pass through tunnel, HTTP shutdown/server close, bounded join, handler close and state observations. Failure is cached separately from confirmed closure. A common receipt finalizer is shared with Phone.close; it does not own a new process, thread or controller. | Terminate and handle-close failures still attempt remaining resources once. Multiple cleanup errors, unknown/live thread state, receipt failure, partial startup and duplicate close are covered. |
| C2 | Network._start/read uses Process._close_after_error on an operation failure; normal completion still propagates a cleanup failure. Network.start keeps its primary error while closing, records the primary type/message plus secondary notes, and keeps a startup-receipt error explicit without replacing the primary. | Real caller and Process methods, modeled process/Job APIs and a contained loopback HTTP server cover reader exit 7, exit-zero cleanup failure, nested reader/tunnel cleanup failures, and outer error/save/close combinations. |
| C3 | Phone.close keeps a stop-command error through Process._close_after_error, then records port/server observations and cleanup diagnostics. Failed close is one-shot; a successful stop followed by failed cleanup is still an error. | Normal and primary/cleanup failures, write failure, unknown/live port state, no foreign stop and repeat-close no-replay/no-overwrite checks. The stop timeout remains 10 seconds. |

The existing five-second HTTP thread join, DNS retry codes, request limits,
readiness, synchronous single-reader flow and prepare/operation deadlines are
unchanged. Shutdown is skipped for a known unstarted HTTP thread to avoid the
documented standard-library deadlock; the bound socket and log handler still
close. Failure/unknown observations remain distinct from confirmed closure.
No promise is made that a forced process death or unavailable filesystem can
produce a final receipt.

Existing receipt keys remain. Close receipts add `cleanup_complete` and
`cleanup_errors` entries (`step`, `type`, `message`, `notes`). Failed state
observations are null, not invented false/closed values. `startup-failed.json`
keeps the primary type/message and includes secondary notes after the owned
network cleanup pass. Exceptions also retain `process_cleanup_error`,
`network_cleanup_error` or `startup_receipt_error` as applicable. Repeated
failed close rethrows the cached failure without reissuing commands, observing
ports, re-cleaning resources or rewriting receipts.

The only existing test fixture adjustment is giving NetworkStartupTests' Tool
fake the real Process._close_after_error method. Assertions and the accepted
ProcessCloseTests are not weakened or rewritten. Static scope checks confirm
that all non-lifecycle Phone/config functions and seven other bound sources,
including live_host.py, remain unchanged.

## Actual Self-Tests

| Fresh output under C | Actual methods | Result |
| --- | ---: | --- |
| `baseline-focus` | 3 | Exit 1, four failing subcases/checks on the original caller: both tunnel cleanup errors skip HTTP cleanup, and reader/stop primary errors are replaced. No setup error. |
| `focused` | 17 | Exit 1, two setup/precondition errors in one outer-start test; the other 16 methods pass. The fixture had populated server before entering the existing single-use gate. Original failed log retained. |
| `focused-2` | 17 | Exit 0, all pass after placing fixture resource assembly inside mocked _start; the single-use gate and primary/cause assertions remain. Final source identity. |
| `live-suite` (wrapper `live-command`) | 134 | Exit 0, all pass, no skips or timeout. This is the existing 117 plus 17 new caller methods, not 151 distinct methods. Unittest 171.795 s; contained child receipt 173.896 s. Final source identity. |

The complete final live log contains no warning/traceback diagnostics. Each
run retains exact argv/cwd, P34_HOST_TEST_OUT, source hashes, full log, real
exit/timeout status and a summary parsed from the actual unittest count. The
selftest top-level `tests=1` denotes one file, not one test method. The earlier
independent fsync fixture correction remains an unchanged historical record;
it is unrelated to this turn's single-use fixture correction.

Recorded command entrypoints, explicit cwd R, cmd.exe, login:false:

    python -I -S -B -X utf8 .cache/p34-host-close-01-callers-20261013/evidence.py before
    python -I -S -B -X utf8 .cache/p34-host-close-01-callers-20261013/evidence.py baseline-focus
    python -I -S -B -X utf8 .cache/p34-host-close-01-callers-20261013/evidence.py focused
    python -I -S -B -X utf8 .cache/p34-host-close-01-callers-20261013/evidence.py focused-2
    python -I -S -B -X utf8 .cache/p34-host-close-01-callers-20261013/evidence.py live
    python -I -S -B -X utf8 .cache/p34-host-close-01-callers-20261013/evidence.py audit

The live wrapper executes the unchanged repository entry:

    python -I -S -B -X utf8 Tools/ota/p34-acceptance/selftest.py live --out D:/github/my/E-Track/.cache/p34-final/.cache/p34-host-close-01-callers-20261013/live-suite

Its P34_HOST_TEST_OUT is
`D:/github/my/E-Track/.cache/p34-final/.cache/p34-host-close-01-callers-20261013/live-cases`.
Targeted runs use `C/<run>/cases`. The standard runner contains all controllable
home, temporary and cache paths. These completed write-once directories must
not be reused as another test's output.

## Identities And Audit

| Source relative to R | Entry SHA-256 | Final SHA-256 |
| --- | --- | --- |
| `Tools/ota/p34-acceptance/live_phone.py` | `8b0d22329acf2f2c877fd8dccdb0d19d3ffa872de6f42358602bb224e001594b` | `3c524300133818dfed7d056a525ffe044082d0dc5c185aea8a16b98532b89723` |
| `tests/ota/test_p34_live_route.py` | `751ef1833852ab39ee113a6fa9ae7f67f24bd60062f790b8aa452febf3ad336d` | `848e5e1902982052da0d8be0d5fd6a82c8992e77e0564165f6a673e7191c5cb5` |

Unchanged live_host.py SHA-256:
`a0d98161aadccee0346b8f7438cf65566ae6e72d7cf8cc576641e833d7cc6431`.
Final focused log SHA-256:
`c8b793653ce6c697bfb92d69452477e7fa1c0a56b4d825e7e454f3a7818d8ad0`.
Final live log SHA-256:
`e3b3363ed9bf3ee4a7562633f72b92ebf26182808c858e61c3404198e83ebca6`.

`C/changes.patch` is relative to this turn's saved entry bytes, so it does not
repeat the accepted primitive patch. `C/audit.json` is the final write-audit
authority: 25,496 protected inputs, both Git indexes, saved entry originals,
all previous implementation/reviewer outputs, final source/log bindings,
unchanged primitive test body, unrelated Phone/config definitions, syntax and
method counts. C's ignored outputs are inventoried separately from git status.
Git's LF-to-CRLF normalization notices are preserved; they are not whitespace
errors. No machine-wide filesystem trace or attribution of historical external
metadata changes is claimed. No PowerShell or external output path was selected.

Root cause remains caller integration with the primitive's explicit cached
failure behavior: old finally blocks replaced the primary or stopped later
cleanup. The caller fixes now consume the existing helper and one-shot pattern.
The tests prevent that same omission across startup/read/close within this
scope. The corrected development fixture is a gate-aware setup change, not a
loosened gate or a product fix. These lessons are kept in this implementation
handoff; no old audit, Spec, task board or acceptance matrix is rewritten.

## Return To Reviewer

Current independent reviewer: consume the incremental patch, entry/final
hashes, `focused-2/summary.json`, `live-command/summary.json`, original logs
and `audit.json`, then review C1/C2/C3 as the same P34-HOST-CLOSE-01 batch.
The primitive remains the previously verified input. Do not recruit another
freezing agent, replay old review scripts, append OTA or infer a v12 cause.
This uncommitted caller integration is ready for your bounded recheck, not a
claim that all P3-4 or any P3-5/P5 final campaign has completed.
