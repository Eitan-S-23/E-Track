# P1-2 App relocation implementation evidence (2026-07-27)

> Implementer: Codex implementation session.
> Status: local implementation and evidence collection complete; A9b/A9c CI runs and independent acceptance are still pending.
> This card remains `进行中`. It must not be marked `完成` by this implementation session.
> A10 is explicitly excluded: all App runtime checks below are restricted debugger starts, not the normal boot chain.

## 1. Scope and target isolation

Implemented targets:

| Logical target | Physical target | Output |
|---|---|---|
| X-Track-Boot | CMake `X_Track_Boot` linker skeleton | `<build>/boot/` |
| X-Track-App-GCC | CMake `X_Track_App_GCC` | `<build>/app-gcc/X-Track-App-GCC.*` |
| X-Track-App-AC5 | Keil `X-Track-App-AC5` | `Objects-App-AC5/`, `Listings-App-AC5/`, `Track-App-AC5.bin` |
| X-Track-Legacy-GCC | CMake `X_Track` | existing output names unchanged |
| X-Track-Legacy-AC5 | Keil `X-Track` | existing output names unchanged |

Structural checks:

```text
Keil target count: 2 (X-Track, X-Track-App-AC5)
Legacy target XML versus HEAD: identical
Legacy/App RTE targetInfo entries: 44 / 44
Legacy/App --cpp11 groups: 24 / 24
Legacy/App group count: 52 / 53
Legacy/App file count: 422 / 425
App-only files:
  ..\Libraries\OTA\fw_header_placeholder.c
  ..\Libraries\OTA\ota_vtor_check.c
  ..\Libraries\OTA\ota_vtor_check.h
```

The generated App-AC5 build directories and binary are ignored. The small generated target header
`MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h` is versioned, matching the existing tracked legacy target header.

## 2. A1-A4 and A7: linker/scatter layout

### A1 GCC App Flash

Source: `cmake/linker/x-track-app-gcc.ld.S`, preprocessed through `ota_layout.h`.

```text
Memory Configuration

Name             Origin             Length             Attributes
FLASH            0x08010000         0x000f0000         xr
RAM              0x20000000         0x00058000         xrw
RW_IRAM2         0x20058000         0x00028000         xrw
```

The workflow's exact inline layout assertion was also run locally against the current map/bin and returned:

```text
OTA_LAYOUT_ASSERTIONS=PASS
```

### A2 AC5 App Flash

`MDK-ARM_F435/Listings-App-AC5/X-Track-App-AC5.map`:

```text
Load Region LR_IROM1 (Base: 0x08010000, Size: 0x0008732c, Max: 0x000f0000, ABSOLUTE, COMPRESSED[0x00086f7c])
```

### A3 vectors and hard upper bound

Current maps:

```text
GCC  .isr_vector  0x08010000  0x20c
AC5  ER_VECTORS   Exec base 0x08010000, Size 0x0000020c, Max 0x00000400
```

GCC deliberate 0x404-byte vector negative probe:

```text
ld.exe: App vector table exceeds the reserved prefix
ld.exe: section .fw_header LMA [08010400,0801045f] overlaps section .isr_vector LMA [08010000,08010403]
collect2.exe: error: ld returned 1 exit status
GCC_VECTOR_OVERFLOW_EXIT=1
GCC_VECTOR_OVERFLOW_NEGATIVE=PASS
```

AC5 deliberate 0x404-byte vector negative probe:

```text
Error: L6291E: Cannot assign Fixed Execution Region ER_FW_HEADER Load Address:0x08010400. Load Address must be greater than or equal to next available Load Address:0x08010404.
Finished: 0 information, 0 warning and 1 error messages.
AC5_VECTOR_OVERFLOW_EXIT=1
AC5_VECTOR_OVERFLOW_NEGATIVE=PASS
```

The AC5 error proves the vector occupied through `0x08010403`, so the fixed header at `0x08010400` was rejected.

### A4 fixed 96-byte firmware header

```text
GCC .fw_header                  0x08010400  0x60
GCC __fw_header_start__         0x08010400
GCC __fw_header_end__           0x08010460
AC5 ER_FW_HEADER Exec/Load base 0x08010400, Size/Max 0x60
AC5 g_ota_fw_header_placeholder 0x08010400, Data 96
```

### A7 RAM and overlay

```text
GCC RAM      0x20000000 / 0x00058000
GCC RW_IRAM2 0x20058000 / 0x00028000
GCC .sram_ext 0x20058000 / 0x28000

AC5 RW_IRAM1 Exec base 0x20000000, Max 0x00057ff8
AC5 RW_OTA_VTOR_NOINIT Exec base 0x2004c8b8, Size/Max 0x8, UNINIT
AC5 RW_IRAM2 Exec base 0x20058000, Size/Max 0x00028000, UNINIT
```

Both controlled sources derive these values from `Libraries/OTA/ota_layout.h`. The GCC linker contains
the overlay size and contiguity assertions. Manual comparison with frozen contract sections 0.4, 10.1,
and 10.2 found no value drift.

## 3. A5 and A9d: placeholder/finalize boundary

Current raw images were copied, finalized, packed as full `.etu`, unpacked with
`--verify-fw-header`, and compared byte-for-byte.

| Toolchain | Raw size | Raw SHA-256 | Final SHA-256 | Result |
|---|---:|---|---|---|
| GCC | 561144 | `62E00AB4355A15ACB92F7261B1F113CA5A34104C5BBCEFA66184E165CF2CEE69` | `FA3675C60E394577FC8A8681F1264317AD3CF1C88F8F3C1C8C4073CC046B7BB9` | PASS |
| AC5 | 552828 | `9EC2D458752F3AD550BFC375641C5618FB326B1B56290357FC747BCFCB224C57` | `74925369155F368E5FFBA6235AB0B869C95552EDA4A97BD9CA039056C342AB57` | PASS |

For both toolchains:

```text
RawHeaderAllFF=True
FinalMagic=ETFW
VectorPrefixUnchanged=True
CandidateMatchesFinal=True
```

The unpacker verified the header CRC32 and double-zero image SHA. The development pack test printed the
expected warning that `OTA_AES_KEY` was unset and used the vendor example key; this does not affect the
header/finalize evidence and no test package is a release asset.

Workflow semantics:

- Build artifacts are placeholder `X-Track-App-GCC.bin/.hex/.elf/.map`.
- The release job first enforces `OTA_BOOT_CHAIN_READY == true`.
- Only the downloaded `.bin` is finalized and verified before Release/Cloudflare use.
- Placeholder `.hex`/`.elf` are never uploaded as formal recovery firmware.

## 4. A6: VTOR compile-time and runtime evidence

Static implementation:

- `OTA_TARGET_APP` selects `OTA_APP_VECTOR_OFFSET`; legacy selects zero.
- `ota_vtor_check()` is the first statement in `main()`, before `Core_Init()` and SysTick setup.
- GCC `.ota_vtor_noinit` is ELF `NOBITS`/linker `NOLOAD`, address `0x20044c18`, size 8.
- GCC symbols: expected `0x20044c18`, actual `0x20044c1c`.
- AC5 `RW_OTA_VTOR_NOINIT` is `UNINIT`, address `0x2004c8b8`, size 8.
- AC5 symbols: actual `0x2004c8b8`, expected `0x2004c8bc`.
- Boot linker preprocessing produced `FLASH 0x08000000/0x10000`, `RAM 0x20000000/0x58000`.

The App-GCC setup order intentionally retains the existing converter compatibility rule `lv_init()` before
`HAL::HAL_Init()`. `HAL::Display_Init()` starts `Backlight_SetGradual()`, which uses LVGL animation/TLSF.
The repository's existing conversion report already records this GCC-specific correction. Removing it
reproduced an independent `UNALIGNED` HardFault in `remove_free_block`; restoring it produced the stable
run below. AC5/legacy setup order is unchanged.

### Restricted debugger start, matching path

This is a restricted debugger start, not the normal boot chain. The debugger explicitly set MSP
`0x20058000`, VTOR `0x08010000`, and PC `0x0801afc0` (`Reset_Handler`). Sentinels were written before run.

After 8 seconds:

```text
PC = 08042808, IPSR = 000 (NoException), PRIMASK = 00
E000ED08 = 08010000
E000ED28 = 00000000
20044C18 = CAFEBABE DEADBEEF
```

The CPU reached the normal `main` loop, CFSR remained zero, and both sentinels remained unchanged.

### Restricted debugger start, injected mismatch

The debugger broke at `ota_vtor_check` (`0x08042820`), cleared the breakpoint, wrote VTOR
`0x08000000`, and resumed.

```text
PC = 08042850
IPSR = 000 (NoException)
PRIMASK = 01
E000ED08 = 08000000
E000ED28 = 00000000
20044C18 = 08010000 08000000
```

Disassembly identifies `0x0804284a..0x08042850` as `DSB; WFI; branch`, so the fail-closed loop and both
evidence values are confirmed. The device was then restored with the current legacy
`MDK-ARM_F435/Objects/X-Track.hex`; after 3 seconds it was in normal thread mode with
`VTOR=0x08000000`, and it was left running.

## 5. A8: artifact isolation and build results

AC5 App build:

```text
[LINK] armlink --via Objects-App-AC5\X-Track-App-AC5.lnp
[OK] target X-Track-App-AC5 build complete (armlink/fromelf exit code 0)
Program Size: Code=263620 RO-data=288408 RW-data=1244 ZI-data=453400
```

The earlier full uVision target build reported `0 Error(s), 0 Warning(s)`.

Building App-AC5 left all legacy hashes unchanged:

```text
Track.bin          0B950EB90F8C288B35E445E508C39B9E5F194F9183D5E9FDEC58E49B68BCC49C
X-Track.axf        D44E54480B60AE1E762A746A584F60AD37AD1D6B0C1491EE31CA7DAE2828D6E8
X-Track.hex        BD4C52AD5F0A89189A607D0537367A98796D504A6D3399E83D15B53ED29D5F04
```

Building legacy left all App-AC5 hashes unchanged:

```text
Track-App-AC5.bin      9EC2D458752F3AD550BFC375641C5618FB326B1B56290357FC747BCFCB224C57
X-Track-App-AC5.axf    F4BF15A8C73136B52A653CA9999B29A4177C29D3EA056DAD00DA04CB7B1AB097
X-Track-App-AC5.hex    4ABEF78DC4C2E03CCD7AB363B51D6738B53EB4378A1B9B2232C02A6A86B705CB
```

Legacy build result:

```text
[LINK] armlink --via Objects\X-Track.lnp
[OK] target X-Track build complete (armlink/fromelf exit code 0)
Program Size: Code=263496 RO-data=288312 RW-data=1244 ZI-data=453392
```

Root-project reference check:

```text
WorkflowProjectDir=MDK-ARM_F435/cmake-generated
WorkflowRootConfigureCount=0
TasksGeneratedSourceCount=85
TasksRootSourceCount=0
RootLinkerReferenceCount=0
```

## 6. A9 controlled-literal check

The complete PowerShell script from the frozen decision section 5.1 was run without modification.

```text
A9_CONTROLLED_LITERAL_CHECK=PASS
```

The only additional output was Git's existing LF-to-CRLF working-copy warning for modified text files.

## 7. Build/tool validation

- GCC current memory use: Flash `561144/983040`, main RAM `286240/360448`, overlay `163840/163840`.
- GCC raw bin SHA-256: `62E00AB4355A15ACB92F7261B1F113CA5A34104C5BBCEFA66184E165CF2CEE69`.
- AC5 raw bin SHA-256: `9EC2D458752F3AD550BFC375641C5618FB326B1B56290357FC747BCFCB224C57`.
- XML parse, YAML parse, PowerShell parse/ASCII, linker preprocessing, and `git diff --check` are part of the final pre-commit check.
- Local Ninja in this managed sandbox can hang before launching its first job, including a linker-only custom target. Exact generated compile/link commands succeed. Clean-checkout GitHub Actions is the A9b authority.
- GCC link succeeds but emits the existing newlib syscall and short-wchar compatibility warnings; errors are zero. These warnings are not hidden as success detail.

## 8. Pending CI and independent acceptance

- A9b clean-checkout push run: pending implementation commit/push.
- A9c `workflow_dispatch publish=true` with `OTA_BOOT_CHAIN_READY` unset: pending implementation commit/push.
- Implementation commit: pending.
- Independent non-implementation acceptance A1-A9d: pending.
- P1-2 remains `进行中`; P1-1 must not start until independent acceptance passes and the card is marked `完成`.
