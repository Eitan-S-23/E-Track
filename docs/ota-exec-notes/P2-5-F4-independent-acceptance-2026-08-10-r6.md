# P2-5 F4 R3 Independent Acceptance Report (R6)

## Decision

P2-5 passes independent acceptance and is set to `完成`; P2 advances from `4/6` to `5/6`.

The governing standard is `.claude/prompt-P2-5-verification-r3.md`. This session did not change production implementation and did not run commit, push, merge, rebase, reset, checkout, or stash.

## Hash Gate And Reused Evidence

The frozen production manifest was independently recomputed before hardware work: `2945/2945`, missing `0`, mismatch `0`, manifest SHA-256 `17AD13C4FEDB585A0F0134BF26A527E47A24CAB2F602DF7D5EC32C6D32887C41`.

All bound artifacts matched the R3 table, including v20800/v20801 App, Boot, Simulator, ETU, unpacked candidate, current ELF, and map. The already-bound 12 host-test commands, fresh GCC build, fresh Simulator build, Startup `12/12`, six fixtures, F4 harness, and TEST_BOOT gate logs were audited with no missing evidence or hash mismatch. Because the hash gate stayed closed and this session changed only acceptance evidence and documentation, those expensive suites were not rerun.

## Independent Production Timing

Attempt 05 used the final production v20800 ELF with FPB breakpoints and DWT cycle counting. Initial and final Flash checks both passed `38/38` chunks on the first read, with no retry.

| Gate | Run 1 | Run 2 | Run 3 | Limit | Result |
|---|---:|---:|---:|---:|---|
| Root `LoadFiles` | 36.602 ms | 36.628 ms | 36.607 ms | 320 ms | PASS |
| `/F4ACC LoadFiles` | 47.103 ms | 47.095 ms | 47.021 ms | 320 ms | PASS |
| Input-to-list upper bound | 910.720 ms | 910.759 ms | 910.773 ms | 917 ms | PASS |

The final timing state was v20800, `CONFIRMED`, `SDReady=1`, `VTOR=0x08010000`, and `CFSR=0`.

## Physical UI And OTA

The user confirmed readiness before observation and then reported `全部正常，录像已保存`. All nine required UI/interaction items were recorded separately as PASS: title visibility, complete truncation text, centered buttons, ETU selection and second confirmation, cancel/back/re-entry, `CANDIDATE VERIFY`, `BACKUP + STAGED`, success result page, and no black screen, abnormal reset, HardFault, WDT, or truncated text. The observer retained the video but did not provide a repository-local path.

Machine-state capture independently bound the observation to `/P2-5-FULL.etu`, `ResultSuccess=1`, `STAGED`, `ApplyPending=0`, and `StagePending=0`. The ETU remained `281291` bytes with SHA-256 `5D7C388F7448896F8F67FF8B33E6380E48467235520FBE61891BA52A7B3F814E`.

The complete hardware chain passed:

1. Baseline v20800 was `CONFIRMED`, with `SDReady=1`, `VTOR=0x08010000`, and `CFSR=0`.
2. The current map resolved `_SEGGER_RTT=0x20053E14`; `mem8` verified the `SEGGER RTT` signature.
3. The same OTA cycle produced `OTA: HANDOFF vtor=0x08010000` and `OTA: TEST_BOOT confirmed vcode=20801`.
4. The second reset produced `OTA: HANDOFF vtor=0x08010000` and `OTA: BCB already CONFIRMED vcode=20801`.
5. Final health was v20801, `CONFIRMED`, `SDReady=1`, `VTOR=0x08010000`, and `CFSR=0`; the user additionally reported `复位后屏幕正常`.
6. Both decisive RTT segments had zero matches for HardFault, WDT reset, recovery, `RTTCMD:`, `F4TRACE`, `F4PROBE`, or `F4METRIC`.

## Harness Adjudication

The first `AfterOtaReset` health probe sampled too early: `PC=0x08001C1C`, `VTOR=0x08000000`. Repository-local `addr2line` resolves that PC to boot `i2c_delay`, proving installation was still in the Boot window. It was therefore a fail-closed harness timing error, not a product failure.

No second reset occurred before recovery evidence. The same attempt later showed App execution and produced the decisive `TEST_BOOT confirmed vcode=20801` RTT plus healthy v20801 state. Only after that was the required independent second reset issued. The adjudication is preserved in `.acceptance-p2-5-f4/20260814-091824/audit/07-ota-final-adjudication.json`.

## Closure

The final evidence matrix is `.acceptance-p2-5-f4/20260814-091824/evidence-matrix.md` and `.json`; the initial all-`NOT_OBSERVED` matrix remains unchanged as `evidence-matrix-initial.*`.

Final checks found `git diff --check=0`, zero Simulator/J-Link/RTT logger/server processes, unchanged global `JLinkDLL.ini` (`986` bytes, SHA-256 `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`), and unchanged `E:\P2-5-FULL.etu` (`281291` bytes, SHA-256 `5D7C388F7448896F8F67FF8B33E6380E48467235520FBE61891BA52A7B3F814E`). All agent-selected writes were inside `D:\github\my\E-Track-p2-5-20260801`; no cleanup outside that root was required.
