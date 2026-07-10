# Agent Build Guide

This repository contains Keil MDK projects for the AT32F435/AT32F403A firmware.
Agents must follow this guide when asked to compile the F435 firmware.

## Default Build Entry Point (firmware and/or simulator)

**Default action:** when asked to compile the MCU firmware, the LVGL
simulator, or both, run the one-click batch file instead of hand-assembling
the per-step commands below:

```bat
build_f435_and_simulator.bat --no-pause
```

- The batch runs, in order:
  `MDK-ARM_F435\build_f435.ps1 -AutoStale -AutoFonts` (firmware) then
  MSBuild on `Simulator\LVGL.Simulator.sln` (simulator). It self-locates the
  repo root via `%~dp0`, so it works from any working directory.
- `--no-pause` skips the trailing interactive `pause`, suitable for
  non-interactive agent runs.
- Outputs are identical to the per-step build: firmware
  `MDK-ARM_F435\Track.bin`, `MDK-ARM_F435\Objects\X-Track.{axf,hex}`; simulator
  `Simulator\Output\Debug\x64\LVGL.Simulator.exe`.
- Acceptance criteria are the same as the sections below: `armlink`/`fromelf`
  exit code 0, record the `Program Size` line and output timestamps; if
  warnings exist, say so (warnings present, errors zero) — do not disguise
  warnings as success detail.
- From a bash shell a `.bat` runs directly
  (`./build_f435_and_simulator.bat --no-pause`); if argument parsing looks
  wrong, use `cmd //c build_f435_and_simulator.bat --no-pause`.

**When to fall back to the per-step / precise commands below:** the one-click
batch always uses `-AutoStale` and cannot do precise incremental or new-source
handling. Use the per-step commands in "Preferred Incremental Build" /
"Reliable Manual Incremental Fallback" (firmware) and "LVGL Simulator"
(simulator) when any of these apply:

1. Only a few known sources changed and you want to recompile just those —
   use `build_f435.ps1 -Sources ...` to save time.
2. You only need firmware **or** only need the simulator — the one-click batch
   builds both, so a single-side need should use the matching per-step command.
3. New project files were added whose dep entries Keil has not generated yet —
   use `build_f435.ps1 -NewSources ... -ExtraLinkObjs ...`.
4. A widely-included header such as `lv_conf.h` changed — the one-click batch
   is fine (`-AutoStale` rebuilds all dependents); if only the firmware side
   matters, the per-step command also requires `-AutoStale`, never relink-only.

## F435 Project Facts

- Workspace root: `D:\github\my\AT32F435RGT7_SDIO`
- Keil project: `MDK-ARM_F435\proj.uvprojx`
- Target name: `X-Track`
- Compiler: ARM Compiler 5, not AC6
- Installed uVision path observed on this machine: `D:\install\keil5 mdk\UV4\UV4.exe`
- Installed AC5 tools observed on this machine: `D:\install\keil5 mdk\ARM\ARMCC\bin`
- Main outputs:
  - `MDK-ARM_F435\Objects\X-Track.axf`
  - `MDK-ARM_F435\Objects\X-Track.hex`
  - `MDK-ARM_F435\Track.bin`
  - `MDK-ARM_F435\Listings\X-Track.map`

## Address Decoding

When decoding crash, HardFault, backtrace, PC, LR, or call-stack addresses for
this project, use the repository-local addr2line first:

```powershell
.\Tools\addr2line.exe -e .\MDK-ARM_F435\Objects\X-Track.axf -a -f -C <address>
```

If diagnosing an older copied AXF, replace the `-e` argument with that exact
AXF file. Do not prefer a globally installed `addr2line` while
`Tools\addr2line.exe` is available.

## Preferred Incremental Build

Use Keil's incremental build command first:

```powershell
$uv4 = 'D:\install\keil5 mdk\UV4\UV4.exe'
$project = 'D:\github\my\AT32F435RGT7_SDIO\MDK-ARM_F435\proj.uvprojx'
& $uv4 -b $project -t 'X-Track'
```

If `UV4.exe` is already running, uVision behaves as a single instance. The
command can return before the build finishes, and `-o some.log` may not create a
log file. In that case, do not assume the build failed or succeeded from the
process return alone. Monitor `MDK-ARM_F435\Objects` and the final outputs until
file timestamps stop changing.

Useful monitor command:

```powershell
Get-ChildItem .\MDK-ARM_F435\Objects -File |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 20 Name,Length,LastWriteTime
```

## Reliable Manual Incremental Fallback

If `UV4.exe -b` does not rebuild the changed file, use the Keil-generated
dependency and link files instead of guessing compiler flags:

- Compile commands are stored in `MDK-ARM_F435\Objects\proj_X-Track.dep`.
- Link input and linker options are stored in `MDK-ARM_F435\Objects\X-Track.lnp`.
- Use `armcc.exe` for `.c` and `.cpp` files.
- Use `armasm.exe` for `.s` files.
- After any object file is rebuilt, always rerun `armlink.exe` and `fromelf.exe`.

Do not compare changed source files only against `X-Track.axf`. Relinking
refreshes the `.axf` timestamp and can hide stale object files. Compare each
source/header dependency against its own `.o` file.

Example that proved necessary for `USER\HAL\HAL.cpp`:

- Source: `USER\HAL\HAL.cpp`
- Object: `MDK-ARM_F435\Objects\hal.o`
- If `USER\HAL\HAL.cpp` is newer than `hal.o`, recompile `HAL.cpp` using the
  exact command recorded in `proj_X-Track.dep`, then relink.

Use this PowerShell pattern to recompile one source from `proj_X-Track.dep`.
Change only `$source` when another file is stale:

```powershell
$projectDir = 'D:\github\my\AT32F435RGT7_SDIO\MDK-ARM_F435'
$source = '..\USER\HAL\HAL.cpp'
$dep = Join-Path $projectDir 'Objects\proj_X-Track.dep'
$armcc = 'D:\install\keil5 mdk\ARM\ARMCC\bin\armcc.exe'
$armasm = 'D:\install\keil5 mdk\ARM\ARMCC\bin\armasm.exe'

function Split-KeilArgs([string]$s) {
  $tokens = New-Object System.Collections.Generic.List[string]
  $sb = [System.Text.StringBuilder]::new()
  $inQuote = $false
  for ($i = 0; $i -lt $s.Length; $i++) {
    $ch = $s[$i]
    if ($ch -eq '"') { $inQuote = -not $inQuote; continue }
    if ([char]::IsWhiteSpace($ch) -and -not $inQuote) {
      if ($sb.Length -gt 0) { $tokens.Add($sb.ToString()); [void]$sb.Clear() }
      continue
    }
    [void]$sb.Append($ch)
  }
  if ($sb.Length -gt 0) { $tokens.Add($sb.ToString()) }
  $tokens.ToArray()
}

$text = Get-Content -LiteralPath $dep -Raw
$entry = [regex]::Matches($text, '(?ms)^F \((?<src>[^)]*)\)\([^)]*\)\((?<cmd>.*?)\)\r?$', 'Multiline') |
  Where-Object { $_.Groups['src'].Value -eq $source } |
  Select-Object -First 1
if (-not $entry) { throw "Source not found in dep file: $source" }

$cmd = ($entry.Groups['cmd'].Value -replace '\r?\n', ' ').Trim()
$args = @(@(Split-KeilArgs $cmd) + @($source))
$tool = if ([IO.Path]::GetExtension($source).ToLowerInvariant() -eq '.s') { $armasm } else { $armcc }

Push-Location $projectDir
& $tool @args
if ($LASTEXITCODE -ne 0) { throw "$tool failed: $LASTEXITCODE" }
Pop-Location
```

After object compilation, relink and regenerate images:

```powershell
Push-Location 'D:\github\my\AT32F435RGT7_SDIO\MDK-ARM_F435'
& 'D:\install\keil5 mdk\ARM\ARMCC\bin\armlink.exe' --via '.\Objects\X-Track.lnp'
if ($LASTEXITCODE -ne 0) { throw "armlink failed: $LASTEXITCODE" }

& 'D:\install\keil5 mdk\ARM\ARMCC\bin\fromelf.exe' --i32combined --output '.\Objects\X-Track.hex' '.\Objects\X-Track.axf'
if ($LASTEXITCODE -ne 0) { throw "fromelf hex failed: $LASTEXITCODE" }

& 'D:\install\keil5 mdk\ARM\ARMCC\bin\fromelf.exe' --bin -o 'Track.bin' '.\Objects\X-Track.axf'
if ($LASTEXITCODE -ne 0) { throw "fromelf bin failed: $LASTEXITCODE" }
Pop-Location
```

Expected successful link output includes a `Program Size` line, for example:

```text
Program Size: Code=224788 RO-data=87780 RW-data=1088 ZI-data=263256
```

The exact values may change after code changes.

### build_f435.ps1 Quick Usage

`MDK-ARM_F435\build_f435.ps1` wraps the dep/lnp reuse above. Prefer it over
hand-running armcc/armlink for incremental firmware builds.

- Recompile specific already-known sources:
  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'MDK-ARM_F435\build_f435.ps1' -Sources @('..\USER\App\Pages\Dialplate\Dialplate.cpp','..\USER\HAL\HAL.cpp')"
  ```
- Auto-pick every stale source (source/header newer than its own `.o`): pass
  `-AutoStale` and omit `-Sources`.
- New project files Keil has not generated dep entries for yet: use
  `-NewSources 'src|template'` (borrows a same-kind compile command, swaps the
  base name) and `-ExtraLinkObjs '.\Objects\<base>.o'` to append the new object
  to the link. Example (new image C array borrowing `img_src_battery.c`):
  ```powershell
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'MDK-ARM_F435\build_f435.ps1' -NewSources @('..\USER\App\Resource\Image\img_src_foo.c|..\USER\App\Resource\Image\img_src_battery.c') -ExtraLinkObjs @('.\Objects\img_src_foo.o')"
  ```

Conventions:
- From bash, call PowerShell with `-Command "& 'script' -arg @('a','b')"`; the
  `-File` form collapses arrays into a single string.
- Keep `.ps1` files ASCII. Windows PowerShell 5.1 reads `.ps1` as GBK on a
  Chinese-locale system, so non-ASCII comments/strings break tokenization. Put
  Chinese explanations in `.md`.
- Judge staleness by source/header vs its own `.o`, never against
  `X-Track.axf` (relink refreshes the axf and hides stale objects).
- 本机**可以**通过板载 J-Link 直接烧录与调试 MCU（旧结论"cannot flash"已作废，
  2026-07-03 实测），完整闭环流程见下节 "J-Link 自动烧录与 RTT 闭环调试"。

### J-Link 自动烧录与 RTT 闭环调试（免人工操作设备）

本机板载 J-Link（ARM-OB STM32 2012 固件）+ SEGGER 工具
`C:\Users\SU\SEGGER\JLink_V818\` 可全自动完成 烧录→复位→控制页面→采集 RTT
→分析 的闭环，agent 不需要请用户操作设备。经验要点（均为实测踩坑）：

1. **烧录**（约 33s / 552KB）：
   ```
   JLink.exe -Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1
     -ExitOnError 1 -CommandFile <脚本>
   脚本内容: h → loadfile "<绝对路径>\X-Track.hex" → r → g → qc
   ```
   - 设备名必须用**全名 AT32F435RGT7**（V8.18 内置 Artery 支持；缩写名如
     AT32F435RG 会弹 GUI 选择框导致命令行挂死）。
   - SWD 速度必须 **1000 kHz**；4000 时老板载调试器报
     "Failed to initialized DAP"。
   - 烧录会 halt MCU，可能把正在传输的 SD 卡打断成软复位救不回的挂死态
     （现象：`SD_IsReady=0`、LiveMap stat 的 lineMiss/sdMs 全 0、瓦片不显示）。
     恢复：拔插 SD 卡（CD 引脚触发自动重新挂载）或整机断电。误判前先从
     map 查 `SD_IsReady` 地址用 `mem` 读值确认。
2. **RTT 采集**：
   ```
   timeout <秒> JLinkRTTLogger.exe -Device CORTEX-M4 -If SWD -Speed 1000
     -RTTAddress <addr> -RTTChannel 0 <输出文件>
   ```
   - RTT 控制块地址每次链接后可能变化，必须从
     `MDK-ARM_F435\Listings\X-Track.map` 查 `_SEGGER_RTT` 符号。
   - 地址必须用严格符号行解析，不要从上下文里抓第一个十六进制数：
     `Select-String -LiteralPath 'MDK-ARM_F435\Listings\X-Track.map' -Pattern '^\s*_SEGGER_RTT\s+'`。
     用 J-Link `mem8 <RTT> 16` 读到 `53 45 47 47 45 52 20 52 54 54`
     (`SEGGER RTT`) 后，才允许把该地址用于 logger 或 down channel。
   - 采集用泛型 `CORTEX-M4` 设备名即可（只读 RAM，无需 flash 算法）。
   - 用户的 RTT Viewer 与 logger 会互相抢数据（RTT 单读指针），采集前请
     用户关闭 Viewer。
   - `JLinkRTTLogger.exe` 是长运行/交互式进程，agent 采集前必须先清残留：
     `Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue`。
     采集必须带明确超时，超时后再次确认无残留 logger；多个 logger 会抢同一个
     RTT 读指针，导致日志缺行、串行或读到旧固件输出。
3. **RTT 下行命令控制设备**（`USER\App\App.cpp`，宏
   `CONFIG_RTT_DEBUG_CMD_ENABLE`，生产固件置 0 整体移除）：
   固件 100ms 轮询 down channel 0 行命令：`ping` / `livemap` / `dialplate`
   / `back`，执行后回显 `RTTCMD: ...`。主机侧发送 = J-Link mem write：
   down[0] 描述符位于 `_SEGGER_RTT+0x60`（pBuffer 指针在 +0x64、WrOff 在
   +0x6C），先 `mem32` 读出 pBuffer 地址，逐字节 `w1` 写入命令（含 `\n`），
   再 `w4` 把 WrOff 写为命令字节数。
   - down[0] 是 16 字节环形缓冲，不是每次都从 0 开始写。连续发送命令时，
     先读 descriptor 的 pBuffer/Size/WrOff/RdOff，按 WrOff 取模续写，再把
     WrOff 更新到新位置。若回显出现 `unknown 'psreset'` 这类缺首字母命令，
     说明 WrOff/RdOff 或 descriptor 已错，必须复位并重读 descriptor，禁止
     继续用污染状态采集性能数据。
   - 每次烧录或重新链接后，`_SEGGER_RTT`、down descriptor、pBuffer 都按新
     map 重读；旧地址即使还能读到 RAM 数据，也可能不是当前固件的 RTT 控制块。
4. **其他 J-Link 手段**：`r`+`g` 复位设备（GPS 模拟器回起点，测量前必做，
   否则 50-80km/h 随机游走十几分钟就会跑出地图瓦片覆盖区，表现为 miss=0
   空白地图）；`h`+`regs` 短暂 halt 读 PC，配 `Tools\addr2line.exe` 解
   RAMCODE 地址判断死机位置。
5. **LiveMap 每秒 RTT 统计行**（性能测量的标尺）：
   `update reload lineHit lineMiss lineReadKB sdMs refrMs refrCnt refrPxK`
   —— sdMs=渲染管线内 SD 等待、refrMs=LVGL 刷新总耗时（含 SD）、
   refrPxK/76.8≈每秒整屏次数、refrMs 接近 1000 表示渲染引擎已吃满。
6. **J-Link 闭环防卡死清单**（2026-07-10 复盘补充）：
   - J-Link 可用；若闭环卡住，优先怀疑 agent 进程管理、RTT 地址漂移或 down
     channel 写错，不要先下结论为"本机不能 J-Link"。
   - 烧录后必须按"重查 map → 验证 SEGGER RTT 签名 → 读取 down descriptor
     → 发送 `gpsreset`/`livemap` → 启动单个 logger"顺序执行。
   - 任何性能日志若来源于旧 RTT 地址、残留 logger、错误命令回显、或与当前源码
     状态不匹配，必须标记为污染日志并重测，不能参与路线判定。

### LiveMap 性能与 SDIO 改动防坑清单（2026-07 帧率优化战役沉淀）

完整根因链、性能账本与实验方法见仓库根
`导航帧率优化全程复盘与踩坑手册.md`（改动 SDIO 驱动 / LiveMap 渲染 /
行缓存 / 做性能测量之前必读）。**改地图/滚动/渲染参数、做性能调优或排查
地图故障时，先读仓库根 `LiveMap参数调整与优化操作手册.md`——查表式手册，
参数位置/调法/验证命令/故障速查全部可直接照抄，无需理解实现。**
以下为红线级规则：

1. **SDIO 的 NVIC 中断从未使能**，`sd_irq_service` 是死代码。多块读靠
   数据完成后**同步发 CMD12**（`stop_flag=0`）；不要把停卡逻辑放回中断，
   也不要在未确认中断链路的情况下启用任何"由中断收尾"的外设路径。
2. `sd_init` 末尾的 CMD16(512) 是**全局前置条件**（`scr_find`/`sd_switch`
   会把卡块长改成 8/64），不是可删的冗余。
3. 改 SD 驱动必须先跑带隔离的自检（`CONFIG_SD_MULTIBLOCK_SELFTEST` 模式：
   开机测试→RTT 报告→完整重初始化），禁止直接改生产读写路径后连续盲试。
4. 烧录（halt 打断 SDIO 传输）可能把 SD 卡挂死到软复位救不回：现象是
   `SD_IsReady=0`、stat 全 0、瓦片消失——先 J-Link 读 `SD_IsReady`
   （map 查地址）再定位，恢复=拔插卡，不是代码 bug。
5. 行缓存 LRU 悬崖：缓存条数 < 整帧工作集时跨帧命中率≈0，**扩条数是
   伪优化**；有效的是加大读粒度摊薄单次事务 ~150µs 固定开销（当前
   16 行/条已是拐点，32 行实测增益反转，勿再加大）。
6. 视口快照三坑：①对行主序瓦片做窄列读取有 60 倍读放大——水平方向
   必须走 16px 网格 margin（`SNAPSHOT_GRID_X`）；②缺瓦片区域每行重试
   open 会以 FAT 目录遍历拖死主循环——失败负缓存（2s）必须保留；
   ③`SetMapTile` 按 tileNum 算容器尺寸，快照模式 tileNum=0 会得到
   0 高容器使整页被裁剪不绘制——容器尺寸必须取瓦片容器矩形。
7. GPS 模拟器会随机游走出地图覆盖区且经轨迹 GPX 持久化（复位无效），
   测量前必须执行 复位→RTT 命令 `gpsreset`→`livemap` 三连；
   miss/sdMs 全 0 + 空白地图先怀疑出界/SD 挂死，不要当渲染 bug 修。
8. 帧率三层限制 = min(像素速度, REFR_PERIOD 31Hz, 渲染能力 24.5FPS)。
   zoom16 慢速下 5-8FPS 是**内容变化率**所限（位图平移最小 1px），
   不是性能缺陷；评估优化必须用高倍缩放或压测速度（临时调
   `SIM_SPEED_*` 到 300-400，测完恢复 50-80）打满引擎再看能力值。
9. profiling 注意测量边界：本架构 SD 等待嵌在渲染管线内部，
   `refrMs - sdMs` 才是纯渲染；"某函数耗时高"≠它是根因。
10. LVGL 对象"不显示/invalidate 无效"优先查**父链尺寸与可见性裁剪**
    （绘制与失效共用同一套裁剪），再查内容；模拟器可用"失败填充改
    红色+截图"二分：白=没画（裁剪），红=画了（内容问题）。模拟器
    PC 路径下有地图数据，可完整验证 LiveMap 显示链路。

### C++11 (`--cpp11`) Group Option in `proj.uvprojx`

AC5 compiles C++ under the old standard by default. C++11 features
(`nullptr`, lambdas, `auto`, range-for, etc.) require the `--cpp11` flag,
which in this Keil project is set per `<Group>` via `<GroupOption>` ->
`<Cads>` -> `<VariousControls><MiscControls>--cpp11</MiscControls>`. A
group whose `.cpp` uses C++11 but has no `<GroupOption>` inherits the
target default (no `--cpp11`) and fails with `Error: #20: identifier
"nullptr" is undefined` and `#29: expected an expression` on lambdas.

This was the real cause of `RouteImport.cpp` / `RouteSelect.cpp` failing
to compile (13 x `#20` + 1 x `#29`): their `Pages/RouteImport` and
`Pages/RouteSelect` groups had only `<Files>`, no `<GroupOption>`, while
`Pages/Dialplate`, `Pages/LiveMap`, etc. carry the `--cpp11` group option.
Of 126 `.cpp` entries in `proj_X-Track.dep`, 74 carry `--cpp11` and 52 do
not -- a newly added page group lands in the wrong half if you forget the
option. Note the sources already used `nullptr` in the committed version;
the error only surfaced when an `-AutoStale` incremental build actually
recompiled them.

Diagnosis: check whether the compile command recorded for that `.cpp` in
`Objects\proj_X-Track.dep` contains `--cpp11`. After normalizing away
timestamps and base names, a char-by-char diff against `Dialplate.cpp`'s
command should differ only by `--cpp11`.

Fix: copy the entire `<GroupOption>` block from an existing page group
(e.g. `Pages/LiveMap`) into the missing group -- the key field is
`Cads/MiscControls = --cpp11`. Do NOT inject `--cpp11` into
`build_f435.ps1` as a workaround; that violates the "reuse Keil config,
do not hand-write compiler flags" rule. After editing `proj.uvprojx`,
run a full `UV4 -b` so Keil regenerates `proj_X-Track.dep` and
`X-Track.lnp` with the correct flag; only then will `build_f435.ps1
-AutoStale` pick it up. Acceptance: `0 Error(s), 0 Warning(s)` plus the
`Program Size` line.

Prevention: when adding a new page group to `proj.uvprojx` whose `.cpp`
uses any C++11 feature, copy an existing page group's `<GroupOption>`
block rather than writing a bare `<Group>` with only `<Files>`.

## Things Agents Must Not Do

- Do not report "no files changed" by comparing source timestamps with
  `X-Track.axf`; compare source/header dependencies with their corresponding
  object files.
- Do not treat `UV4.exe -b` returning as proof that the build is complete when a
  uVision instance is already running.
- Do not wait indefinitely on `UV4.exe` if it is acting as the GUI single
  instance.
- Do not hand-write include paths, macros, scatter file paths, or CPU flags.
  Reuse `proj_X-Track.dep` and `X-Track.lnp`.
- Do not delete `Objects`, `Listings`, or generated firmware outputs unless the
  user explicitly requests a clean rebuild.
- Do not switch the project to AC6. This project is configured for AC5.

## LVGL Simulator and UI Lessons Learned

The Windows simulator is the fastest way to validate Dialplate UI changes, but
it has a few project-specific traps:

- Simulator solution: `Simulator\LVGL.Simulator.sln`
- Simulator exe: `Simulator\Output\Debug\x64\LVGL.Simulator.exe`
- Build command:

```powershell
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' 'Simulator\LVGL.Simulator.sln' /m /p:Configuration=Debug /p:Platform=x64 /v:minimal
```

- Screenshot command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .claude\cap.ps1
```

- Screenshot output: `.claude\sim_new.png`
- If MSBuild fails with `LNK1104` on `LVGL.Simulator.exe`, a simulator process
  is still running and locking the exe. Stop it first:

```powershell
Stop-Process -Name LVGL.Simulator -Force -ErrorAction SilentlyContinue
```

- If `LNK1104` persists after stopping the process, rename the locked exe aside
  so MSBuild can write a fresh one:

```powershell
Move-Item 'Simulator\Output\Debug\x64\LVGL.Simulator.exe' 'LVGL.Simulator.exe.locked' -Force
```

- Always inspect `.claude\sim_new.png` before reporting UI success. Do not rely
  on "build succeeded" alone.
- `.claude\cap.ps1` should terminate simulator instances, but verify with:

```powershell
Get-Process LVGL.Simulator -ErrorAction SilentlyContinue
```

### Avoid LVGL Draw/Shadow Paths in This Project

Previous simulator/device white-screen and startup crash work traced back to
heavy LVGL drawing paths. For dynamic UI and animations in this project:

- Do not add `shadow_width`, `shadow_opa`, or other `shadow_*` styles.
- Do not use `LV_EVENT_DRAW_POST`, custom `lv_draw_*`, or mask/event based
  drawing for simple HUD effects.
- Prefer simple `lv_label`, `lv_img`, and plain `lv_obj` rectangles.
- Keep animations as timers that move/show/hide existing simple objects.
- See `docs\启动动画卡死根因与修复.md` before touching startup animation or
  adding visual effects that allocate draw buffers.

### Startup Animation Simulator Rules

Recent simulator freeze debugging introduced one important pitfall: do not
"fix" simulator stability by bypassing the startup page or disabling its
timeline. The simulator must still exercise the real startup animation.

- `USER\App\App.cpp` should push `Pages/Startup` in the simulator too. Do not
  add `_WIN32` logic that pushes `Pages/Dialplate` directly unless the user
  explicitly asks to skip startup animation.
- `USER\App\Pages\StartUp\StartUpView.cpp` should create and use
  `ui.anim_timeline` in the simulator. Do not set it to `nullptr` under
  `_WIN32`, and do not make the logo/scanline jump to the final state only for
  the simulator.
- Simulator-only startup music can stay disabled if needed, but the visual
  startup animation must remain visible and timed.
- If startup stability regresses, first simplify risky drawing paths and page
  transition behavior; do not remove the startup animation as a workaround.
- Before reporting that startup UI is fixed, build a fresh
  `Simulator\Output\Debug\x64\LVGL.Simulator.exe` and confirm its timestamp.
  A source edit without a rebuilt exe is not a valid simulator verification.
- Debug simulator freezes from process/window output, not screenshots alone.
  Probe `IsHungAppWindow`, `Responding`, CPU time, working set, private memory,
  and leftover `LVGL.Simulator` processes across repeated launches. Screenshots
  are only for visual confirmation.
- Always test at least the second simulator launch after a startup change. A
  known failure mode only appeared on a later launch, not the first one.

### Current Windows Simulator Freeze Analysis

Do not confuse two different startup issues:

- Device-side startup crashes documented in `docs\启动动画卡死根因与修复.md`
  were caused by the old `LV_EVENT_DRAW_POST` / `lv_draw_*` self-drawing
  startup architecture corrupting LVGL memory on 32-bit targets.
- The recent Windows simulator freeze was a separate simulator event-loop and
  Win32 paint/windowing stability problem. Repeated process probes after the
  latest fixes showed stable memory, not runaway allocation.

Current working conclusion for the Windows simulator freeze:

- It was not primarily a memory leak. A 12-run repeated startup test stayed
  responsive with private memory peaking around 87.5 MB and working set around
  52 MB, then all simulator processes exited cleanly.
- The risk path was the simulator's Win32 integration: window show/paint and
  message pumping around startup, plus an LVGL loop that could starve Windows
  messages or re-enter expensive paint work. Earlier hangs were observed around
  window-show/paint behavior rather than steadily increasing memory.
- Stability fixes should stay in the simulator layer: poll Win32 messages before
  `lv_timer_handler()`, throttle the main loop sleep, avoid direct synchronous
  `GetDC` / `StretchBlt` flush work where `InvalidateRect` + `WM_PAINT` can do
  it, prefer `ShowWindowAsync`, and keep process priority below normal.
- Startup animation fixes should stay in the UI layer: use simple LVGL objects
  and `anim_timeline`; do not add shadows, draw callbacks, masks, or manual
  `lv_draw_*` code to make the animation prettier.
- If a future simulator run freezes the PC again, first kill residual
  `LVGL.Simulator.exe` processes, confirm a fresh exe timestamp, then instrument
  process/window state. Look for `hung=True`, CPU pegging, or memory growth
  before changing UI behavior.

### Shared `lv_conf.h` Pitfall

`Simulator\LVGL.Simulator\lv_conf.h` is not simulator-only. The F435 Keil
project also compiles against this same file.

- Do not reduce `LV_MEM_SIZE` to tune simulator behavior. Under `_WIN32` the
  simulator uses custom `malloc`, so the built-in LVGL pool size may not affect
  simulator runs, but it directly changes the embedded firmware.
- A previous reduction from `128 KB` to `72 KB` produced a device-side black
  screen after flashing while the simulator still ran normally. Restore and
  keep the ARDUINO/LVGL built-in pool at `128U * 1024U` unless device memory is
  re-profiled and the firmware is tested on hardware.
- After any `lv_conf.h` change, rebuild firmware with `build_f435.ps1
  -AutoStale` so all source files depending on the header are recompiled. A
  relink or single-source compile is not sufficient.

### Navigation / GPX Import / File Browser Lessons Learned

These lessons came from the GPX route import and file browser work. Re-check
them before changing `RouteSelect`, `RouteImport`, `LiveMap`, navigation data
flow, LVGL filesystem paths, or Chinese/icon fonts.

- Do not leave temporary page-entry changes in `USER\App\App.cpp`. It is fine
  to temporarily push `Pages/RouteSelect` or `Pages/RouteImport` for simulator
  screenshots, but restore the production entry to `manager.Push("Pages/Startup")`
  and rebuild the simulator before reporting. The simulator must still exercise
  startup animation and land on Dialplate by default.
- For visual validation of a deep page, a temporary direct entry is acceptable
  only if the final build is done after restoring `Pages/Startup`. Keep a
  dedicated screenshot such as `.claude\route_import_1.png` or
  `.claude\route_select_align_fixed.png`; do not trust the last `.claude\sim_new.png`
  unless you know which temporary entry produced it.
- `RouteSelect` uses the global LVGL encoder/keypad group. A child page must
  not call `lv_group_remove_all_objs()` during `onViewUnload()` or after a Pop,
  because the parent page (`MainMenu`) may already have rebuilt its own group
  during `onViewWillAppear()`. Remove only objects owned by that page:
  check `lv_obj_get_group(obj) == lv_group_get_default()`, call
  `lv_group_remove_obj(obj)`, then clear focused/edited/key-focus states.
- `lv_list_add_btn()` creates child labels with LVGL's default list layout.
  On this project it can make file/folder icons and text appear vertically
  biased inside the row, especially after custom row heights. If row alignment
  matters, disable the row layout with `lv_obj_set_style_layout(row, 0, 0)`
  and explicitly align child 0/1 with `LV_ALIGN_LEFT_MID`.
- The MCU LVGL filesystem driver uses `'/'` as the drive letter. LVGL strips
  the first path character before calling the driver, so `"/MAP"` reaches
  SdFat as `"MAP"` but `"/"` reaches SdFat as an empty string. The SdFat
  LVGL port must normalize empty real paths to `"/"` for both file and
  directory open. If root browsing works in the simulator but the device says
  "无法打开目录" while maps still load, inspect this path-stripping contract first.
- Do not assume simulator filesystem behavior proves MCU filesystem behavior.
  The simulator PC driver prefixes paths with `LV_FS_PC_PATH`, while the MCU
  driver calls SdFat directly after LVGL strips the drive letter. Test root
  path, subdirectories, and GPX file open paths separately.
- `RouteSelect` should preserve directory browsing and GPX filtering:
  directories are entries whose returned name begins with `/`, hidden entries
  and `System Volume Information` are skipped, and non-directory files are
  shown only when their extension is `.gpx` case-insensitively.
- When selecting a GPX, pass both the full LVGL path and the clean file name:
  `selectRoute.gpxPath` must be the browsed full path (for example
  `"/Navigation/foo.gpx"` or `"/Track/foo.gpx"`), while `routeName` is only
  the display name. The navigation import step later opens `selectedGpxPath`
  with `lv_fs_open()`.
- The Chinese subset font is not a full CJK font. Verify required Chinese
  characters against `USER\App\Resource\Font\font_cn_16.c.chars` before using
  new text. Example: `类` was not present, so use `文件格式` instead of
  `文件类型` unless the font is regenerated.
- If required Chinese characters are missing, regenerate the Chinese subset
  with the project font tooling instead of switching to an unavailable font or
  leaving square boxes. Use `Tools\font_gen` and update the generated
  `USER\App\Resource\Font\font_cn_16.c` / `.chars` outputs. Generate
  AC5-safe source string literals with:
  ```powershell
  python Tools\font_gen\gen_font.py --cstr "<text>"
  ```
  Put the generated UTF-8 `\xNN` literal in C/C++ source files rather than raw
  Chinese text. If the font output or a new generated font source changes,
  ensure the simulator and Keil project file entries still include the affected
  source and rebuild the simulator/F435 side that uses it.
- `cn_16` may not render ASCII punctuation used by LVGL truncation. If a
  Chinese label with `LV_LABEL_LONG_DOT` is too narrow, LVGL can append dot
  characters that render as square boxes. Prefer making the label wide enough,
  switching long mode, or hiding competing fields when no value is needed.
  The LiveMap navigation banner hit this with `路线已就绪`: a 78 px label
  triggered dot mode; no-distance status text needs a wider label and an empty
  distance field rather than `"--"`.
- Keep icon fonts and text fonts separate. `iconfont_20` should only display
  known icon glyphs, while Chinese status labels should use `cn_16`. Do not
  concatenate icon UTF-8 bytes with Chinese text into one label unless that
  label's font is known to contain both glyph sets.
- `bahnschrift_24` has a limited glyph set. Do not assume it can render
  arbitrary letters such as `GPX`; use `bahnschrift_17` or `bahnschrift_13`
  for compact Latin labels unless the target font's glyph map has been checked.
- Missing icons do not require new bitmap resources by default. For small UI
  elements such as GPX document icons, start/end route markers, and simple
  decorative route segments, prefer simple LVGL objects (`lv_obj`, `lv_label`,
  `lv_arc`, rectangles/circles) to avoid adding image/font resources.
- Avoid `shadow_*`, custom draw callbacks, masks, and `lv_draw_*` in these
  pages. Previous startup/device failures traced to heavy LVGL draw paths.
  For RouteImport and RouteSelect, keep visuals to labels, arcs, images, and
  plain rectangles/circles.
- If `image2` is used for design references, obey the local naming convention:
  save generated candidates as normalized `1.png`, `2.png`, `3.png` under the
  requested output folder. Do not rely on model/API/timestamp names. If the
  user says not to use a provided UI screenshot as a base image, generate from
  text only and omit `--input-image`.
- Do not treat generated mockups as pixel-perfect assets. Use them as layout
  direction, then implement in LVGL using project fonts and resource limits.
  Always inspect the simulator screenshot after implementation; build success
  alone is not UI validation.

### Dialplate UI Ownership

The current instrument panel is implemented primarily in:

- `USER\App\Pages\Dialplate\DialplateView.cpp`
- `USER\App\Pages\Dialplate\DialplateView.h`
- `USER\App\Pages\Dialplate\Dialplate.cpp`
- `USER\App\Resource\ResourcePool.cpp`
- `USER\App\Resource\Image\img_src_dialplate_skin.c`

There is a detailed object-by-object adjustment guide in:

```text
docs\仪表盘LVGL对象调整指南.md
```

Use that guide before changing Dialplate coordinates, colors, fonts, icon
resources, MAX/频谱 animation, or bottom button objects.

### Dialplate Skin Image Rules

`dialplate_skin` is a baked full-screen skin. Several UI details are part of
the baked image, not standalone LVGL objects.

- Do not "repair" skin seams by pasting tiny rectangles from unrelated images.
  It creates visible stitched edges.
- If a baked region must match the design, use the original full skin/design
  region at the same coordinates, or regenerate the full skin consistently.
- Preferred regeneration script:

```powershell
python .claude\fix_dialplate_skin.py
```

- The script updates both `.claude\skin_new_240.png` and
  `USER\App\Resource\Image\img_src_dialplate_skin.c`.
- After regenerating `img_src_dialplate_skin.c`, rebuild the simulator and
  firmware; otherwise the C array and preview image will diverge.
- Current design references commonly used for comparison:
  - `UI\仪表盘.png`
  - `UI\now1.png`
  - `.claude\sim_new.png`

### Dialplate Icon Font Rules

Iconfont glyphs are compiled into LVGL C font files. Adding a new icon is not
just changing a UTF-8 string.

- Icon source folder: `Tools\图标`
- Converter: `Tools\图标\convert_iconfont.bat`
- Current climb icon package example: `Tools\图标\font_5t5ay47raff`
- Current climb glyph: `U+E6F2`, UTF-8 string `"\xEE\x9B\xB2"`

Regenerate icon fonts with:

```bat
Tools\图标\convert_iconfont.bat --no-pause font_5t5ay47raff USER\App\Resource\Font\font_iconfont_16.c 16 4
Tools\图标\convert_iconfont.bat --no-pause font_5t5ay47raff USER\App\Resource\Font\font_iconfont_20.c 20 4
```

When adding a new generated font file such as `font_iconfont_16.c`, also:

- Add `IMPORT_FONT(iconfont_16)` in `USER\App\Resource\ResourcePool.cpp`.
- Add the source file to `Simulator\LVGL.Simulator\LVGL.Simulator.vcxproj`.
- Add the source file to `Simulator\LVGL.Simulator\LVGL.Simulator.vcxproj.filters`.
- Add the source file to `MDK-ARM_F435\proj.uvprojx`.
- If `MDK-ARM_F435\Objects\proj_X-Track.dep` and `X-Track.lnp` do not yet
  include the new file, compile it using `build_f435.ps1 -NewSources` and link
  with `-ExtraLinkObjs`.

Example for a new font borrowed from an existing iconfont compile command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\MDK-ARM_F435\build_f435.ps1' -Sources @('..\USER\App\Pages\Dialplate\DialplateView.cpp','..\USER\App\Resource\ResourcePool.cpp') -NewSources @('..\USER\App\Resource\Font\font_iconfont_16.c|..\USER\App\Resource\Font\font_iconfont_20.c') -ExtraLinkObjs @('.\Objects\font_iconfont_16.o','.\Objects\font_agencyb_12.o')"
```

### Dialplate MAX Spectrum Rules

The MAX area has been iterated visually. Avoid reverting it to a stretched bar.

- Current spectrum shape: 3 columns, 16 segments per column.
- Each column is made of small `lv_obj` rectangles in
  `ui.maxBar.spectrumSegs[SPECTRUM_BAR_NUM][SPECTRUM_SEG_NUM]`.
- Height changes are controlled by `frames` in `Spectrum_Update()`.
- Current intended range: minimum about `2/16` segments, maximum `16/16`.
- Do not implement the spectrum as one tall object per column with changing
  height. The intended design is stacked small rectangles.
- The background mask must follow the narrow upper frame, not the wider lower
  frame, to avoid covering the right border.

## Typical Dialplate Verification Flow

For Dialplate UI changes, use this order:

1. Edit source files.
2. Build simulator.
3. Run `.claude\cap.ps1`.
4. Inspect `.claude\sim_new.png` visually.
5. Kill/check simulator processes if needed.
6. Build F435 firmware with `build_f435.ps1`.
7. Report simulator status, firmware `Program Size`, output timestamps, and
   whether warnings/errors occurred.

If the simulator screenshot is white, do not immediately assume the UI change
is correct. Rerun capture once, then run the simulator directly from
`Simulator\Output\Debug\x64` if needed. Also check for locked/stale simulator
processes.

## Verification Checklist

Before reporting success:

- Confirm `armlink.exe` returned exit code 0.
- Confirm both `fromelf.exe` commands returned exit code 0.
- Report the final timestamps for `X-Track.axf`, `X-Track.hex`, and `Track.bin`.
- Report the `Program Size` line from the successful link.
- If warnings exist, say warnings were present and errors were zero. Do not hide
  warnings as success details.
