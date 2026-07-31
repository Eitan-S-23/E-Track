# P2-3 independent acceptance (2026-07-31)

Role: Codex, non-implementation independent acceptance session.

Baseline: `14d54765642965afc7005b9f155bed45366e3912`.

Verdict: **ACCEPT**. The four findings from the first review are closed, the
host/build matrix passes, a vendor-generated multi-control patch succeeds on
the public API, and an independent hardware spot check produced the expected
candidate byte-for-byte within the frozen memory budget. P2-3 may be marked
`complete`; P2 progress becomes `3/6`.

No commit or push was performed.

## 1. First-review findings closed

| First-review finding | Independent re-acceptance result |
|---|---|
| Legal vendor `[0,0,z]` controls rejected | Closed. `[0,0,z]` advances `oldpos`; only `[0,0,0]` is rejected as non-progress. |
| Frozen inner validation order was changed | Closed. A first LZMA pass restores `ph_hcrc -> ph_psize -> decoded length -> base -> candidate`; candidate erase/write starts only after the first four stages pass. |
| `PATCH_CONTROL`, `FW_HEADER`, `IMAGE_METADATA` untested | Closed. All three are reached through public `ota_patch_apply()` tests. |
| Sign-magnitude evidence reversed | Closed. `0f00000000000080` is documented and decoded as vendor sign-magnitude `-15`; two's-complement reinterpretation is `-9223372036854775793`. |

Static review also confirmed that the implementation still bypasses the
RAM-only vendor wrappers/core without modifying `bsdiff_lzma_AES128-main/`,
uses bounded callback I/O, and leaves BCB/ETSL state transitions outside P2-3.

## 2. Independent host and build evidence

- `python tests/ota/test_ota_patch.py`: **167/167** checks passed.
  The vendor regression contains 11 control groups, including nine
  `[0,0,-256]` oldpos-only groups, and produces the frozen 4096-byte target
  exactly. The `[0,0,0]` package returns `PATCH_CONTROL`.
- Measured workspace peak: **21832 / 40960 bytes** on the largest host case.
  The hardware run measured 21784 bytes. Neither path allocates `old_size` or
  `new_size`.
- Existing regressions independently passed with frozen counts:
  fw_header `16/16`, Boot protocols `19/19`, BCB `27/27`, Boot state machine
  `96/96`, P1-6 protocol `21/21`, golden vectors `9/9`, P2-1 `48/48`, and
  P2-2 `102/102`. The PowerShell 7 bootstrap supplement passed `42/42`.
- Fresh GCC production build at `D:\p23-accept-20260731-prod` passed. Boot is
  `14236B`, SHA-256
  `5656466564891B54666325DA4545F3F819BA38F50660AB4772809B5647135AB5`,
  and its three LOAD segments are `R E`, `RW`, `RW` with no RWX. App is
  `563148B` and built with warnings from existing repository categories but
  zero errors.
- Evidence GCC build at `D:\etfwe3` passed with
  `.p2_3_control @ 0x20057800 / 0x800`; the production ELF contains neither
  that section nor the evidence symbols.
- AC5 forced recompilation of `ota_patch.c`, `HAL_OTA_Package.cpp`, and
  `HAL.cpp`, followed by link/fromelf, passed:
  `Code=265448 RO-data=288536 RW-data=1296 ZI-data=495380`,
  `0 Error(s), 0 Warning(s)`, bin `554784B`.
- Final fresh configure matrix:
  production/P2-3-only returned `0/0`; P1-6+P2-3, P2-1+P2-3, and
  P2-2+P2-3 returned `1/1/1` and each emitted its exact mutual-exclusion
  diagnostic.

## 3. Independent hardware spot check

Hardware evidence directory: `D:\p23-accept-hw-20260731`.

The hardware-only package `hardware-patch.etu` is 197 bytes. Its decoded stream
is 4120 bytes with control `(4096,0,-2976)`. The valid run is recorded in
`case-success-retry.log`; the earlier `case-success.log` timeout was an
acceptance orchestration error that disconnected after Ready and missed the
one-shot harness. Its untouched control block proves that attempt never ran.

The valid run reached:

```text
HAL_OTA_PatchEvidenceReady = 0x08043350
HAL_OTA_PatchEvidenceDone  = 0x08043354
status=2 actual=0 detail=0
workspace_peak=21784
candidate writes=4 x 1024B
```

The candidate was read back from QSPI and matched the expected image exactly:

```text
candidate SHA-256 = 98647453355ED273CE1C9019FA86749E4F7AB803A815145028895BA80AB79BB5
expected  SHA-256 = 98647453355ED273CE1C9019FA86749E4F7AB803A815145028895BA80AB79BB5
```

The harness also proved workspace wipe/release, candidate-header cleanup, and
byte-identical BCB snapshots before/after the P2-3 operation. This satisfies
the card's `PC simulation + hardware spot check` acceptance option; rejection
branches remain exhaustively covered on the host public API.

## 4. Board restoration audit

The complete pre-test internal Flash snapshot was saved before the P2-3 run:

```text
original-internal-flash.bin
length=1048576
sha256=7D8C8E058AB56736458B25549756E584C8C14512F0122929F5F56A18CE8DAA00
pre-test PC=0x0802B808 VTOR=0x08010000 CFSR=0
```

Restoring that snapshot verbatim did not boot because the pre-test snapshot
already contained 15 zeroed bytes in the App image around `0x0804244C`; it
differed from the preserved P2-2 production App only at those 15 bytes and
failed the fw_header double-zero SHA. During that failed reset Boot legitimately
advanced the external EEPROM BCB to `ROLLBACK`, then could not validate the
rollback slot. Read-only Boot globals showed:

```text
active=B state=ROLLBACK action=PHYSICAL_RECOVERY status=SLOT(-3)
PC=0x08001E3C (boot_platform_delay_ms / recovery wait)
VTOR=0x08000000 CFSR=0
```

This was a restoration-input defect, not a P2-3 apply failure: the damaged
bytes were present in the snapshot taken before the P2-3 test. Recovery used
the previously accepted P1-6 command harness only to snapshot and clear BCB,
then restored a 1MiB image composed of the original snapshot plus the preserved
valid P2-2 production App (`vcode=20800`, `563188B`). Only 15 bytes differ from
the original snapshot. The restored image SHA-256 is
`FAB0923771F1B403FACE16A4D519E6E048A7533C9D5EF1F443E9FA75B44602B1`.

Recovery evidence in `board-restore-retry`:

```text
BCB before: active=2 state=5 cur_vcode=20800
clear: status=2 detail=0
BCB after clear: active=0
first reset:  PC=0x080960F6 VTOR=0x08010000 CFSR=0
second reset: PC=0x0802C1B0 VTOR=0x08010000 CFSR=0
RTT: OTA: HANDOFF vtor=0x08010000
RTT: OTA: BCB already CONFIRMED vcode=20800
```

The board is therefore back on the preserved production Boot/App in a stable
`CONFIRMED` state. No P2-3 harness was run during restoration.

## 5. Diff and review hygiene

A separate temporary Git index was populated from `HEAD` and all P2-3 changes
were staged into it. `git diff --cached --check` returned `0`. The two files
previously suspected of EOL churn stage as small semantic edits only:

```text
.github/workflows/firmware-build.yml          1 insertion, 0 deletions
MDK-ARM_F435/cmake-generated/CMakeLists.txt  19 insertions, 0 deletions
```

No vendor file is changed. The remaining deliberate debt is duplicated stream
plumbing between `ota_package.c` and `ota_patch.c`; it is explicitly deferred
to P2-5/P2-6 so the already accepted P2-2 source/evidence identity is not
silently rewritten.

## 6. Disposition

- P2-3: `complete`.
- P2 aggregate progress: `3/6`.
- No implementation source was changed by this acceptance session.
- No commit or push was performed.
