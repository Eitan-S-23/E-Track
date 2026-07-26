# P0-4 独立验收记录（2026-07-25）

验收人：Codex（非实现会话）
最终结论：**通过，P0-4 置“完成”**（见 §8）。  
过程摘要：首轮因 J-Link 未枚举不通过（§1-§6）；复验因压测输出走 Serial5 而非 RTT 不通过（§7）；RTT 通道整改后真机 1000 次压测 `ok=1000 fail=0` 通过（§8）。PC 单测、契约样例、GCC/AC5 构建与 `build_f435.ps1` 自定位复核均通过。

## 1. PC 仲裁单测

用户给出的示例命令存在两个路径笔误：仓库实际文件名为 `eeprom_bcb.c`，从 `tests/bcb` 出发应使用 `../../Libraries/EEPROM`。独立执行：

```powershell
gcc -std=c99 -Wall -Wextra -Werror -I../../Libraries/EEPROM `
  test_bcb_arbiter.c ../../Libraries/EEPROM/eeprom_bcb.c `
  -o p04-bcb-test.exe
.\p04-bcb-test.exe
```

结果：20 项均 `PASS`，末行 `summary: 0 failure(s)`，进程退出码 0。

## 2. 契约 §8.3 交叉复算

不调用被测实现，使用 Python `zlib.crc32` 对契约样例前 60B 独立复算：

```text
len 60 crc=0x507F7BAC
```

与 `docs/ota-binary-contracts.md` §8.3 声明值及 LE 存储 `ac 7b 7f 50` 一致。

## 3. 双侧构建

### GCC

```powershell
gcc -std=c99 -Wall -Wextra -Werror -I. -c eeprom_bcb.c -o p04-eeprom-bcb.o
```

结果：退出码 0，0 warning，0 error。

### AC5 默认发货态

验收结束前已确认 `CONFIG_EEPROM_BCB_STRESS=0`，执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `
  "& '.\MDK-ARM_F435\build_f435.ps1' -AutoStale"
```

结果：`armlink`/`fromelf` 退出码 0，日志中 warning/error token 均为 0：

```text
Program Size: Code=265736 RO-data=288288 RW-data=1236 ZI-data=461584
```

默认产物（最终 `-Command` 复核后）：

```text
X-Track.axf  SHA256 03CFA774255B25E907020CEB6A1940BA55C5A89DF1660CE08AD0727E9E920B48
X-Track.hex  SHA256 F1F6EE9EBF61FCE8F94A218A34D597779CF31C2568472DF3E715C68D0B34D9DB
Track.bin    SHA256 2D992E3D69C876B69DC568498039FC91A365D524B2E2A1E95378F7BEE268AF34
```

## 4. 真机 J-Link / RTT

已按要求使用 SEGGER V8.18、设备全名 `AT32F435RGT7`、SWD 1000 kHz。`-AutoConnect 1` 的烧录命令因持续等待 J-Link 而超时；随后用 `-AutoConnect 0` 和显式 `connect` 做可控诊断，稳定得到：

```text
J-Link connection not established yet but required for command.
Connecting to J-Link via USB...FAILED: Cannot connect to J-Link.
```

`ShowEmuList` 无枚举结果，`pnputil /enum-devices /connected` 也没有 J-Link/SEGGER/相关 VID；无残留 `JLink`、`JLinkRTTLogger` 或 `JLinkGDBServer` 进程。

因此本次无法烧录 `CONFIG_EEPROM_BCB_STRESS=1` 固件，也无法验证 RTT 控制块签名或取得 `BCBSTRESS: done ok=1000 fail=0 / 1000`。这属于验收证据缺失，不能据 PC 结果推定真机通过。源码已恢复 `CONFIG_EEPROM_BCB_STRESS=0` 并重新生成默认固件，未把压测固件留作默认产物。

## 5. `build_f435.ps1` 超范围改动判定

**接受该改动留在 P0-4 一并收口；不单独立卡，不登记 §9。** 该改动修正的是构建工具的仓库定位错误，不改变 OTA/BCB 冻结契约；它直接消除跨仓库编译和整文件同步覆盖风险，且改动面小、行为可独立验证。

独立复核结果：

1. 从 `D:\github\my` 使用 `-File D:\github\my\E-Track\MDK-ARM_F435\build_f435.ps1`，实际编译并输出 E-Track 产物。
2. 从 `D:\github\my\AT32F435RGT7_SDIO` 使用 `-Command "& 'D:\github\my\E-Track\MDK-ARM_F435\build_f435.ps1'"`，仍编译 E-Track，而非当前目录的 AT32 仓。
3. 两次均输出相同 Program Size，三项 E-Track 产物 SHA256 逐字节一致。
4. AT32 仓三项产物哈希和时间戳前后不变：AXF `AD2CCB...C23772`、HEX `DF5704...6817`、BIN `E6B97A...1A226`。
5. 脚本 `ASCII_NONASCII_BYTES=0`，PowerShell AST `PARSE_ERRORS=0`，定位赋值为 `$projectDir = $scriptDir`。

非阻断文档残留：仓库 `AGENTS.md` 的 F435 workspace/UV4/手工 fallback 示例仍有 `D:\github\my\AT32F435RGT7_SDIO` 硬编码。它不影响本次脚本行为复核，也不属于 §9 契约变更；建议在 P0-4 最终收口时同步改成当前仓库/相对路径，避免其他入口继续沿用旧认知。

## 6. 复验剩余项

J-Link 设备恢复枚举后，重新执行：stress=1 构建 -> 烧录 -> 按当前 map 重查 `_SEGGER_RTT` 并验证签名 -> 单 logger 采集 `ok=1000 fail=0` -> 停 logger/复位 -> flag 恢复 0 -> 默认构建并烧录。取得该 RTT 行后才可将 P0-4 置“完成”。
## 7. 真机复验（2026-07-25，重新验收）

本次物理链路已确认可用：`ShowEmuList` 枚举 USB J-Link；`AT32F435RGT7` / SWD 1000 kHz 握手成功，SW-DP=`0x2BA01477`，Cortex-M4 r0p1。

### 压测构建与烧录

将 `USER/HAL/HAL_Config.h` 的 `CONFIG_EEPROM_BCB_STRESS` 临时置 `1`。用户给出的裸 `-File` 调用不会自动扫描陈旧对象，首次产物仍为 stress=0；按项目规则补 `-AutoStale` 后重编依赖源：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\MDK-ARM_F435\build_f435.ps1 -AutoStale
```

结果：0 warning / 0 error，`Program Size: Code=267236 RO-data=288292 RW-data=1240 ZI-data=462604`；map 确认 `HAL::EEPROM_BCBStress_Run` 已链接并由 `HAL_Init` 引用。当前 `_SEGGER_RTT`=`0x2004cf60`。

按 `h -> loadfile -> r -> g -> qc` 烧录成功，J-Link 报告 SWD 握手、擦除、编程和 Verify 均 `O.K.`。`mem8 0x2004cf60 16` 得到：

```text
53 45 47 47 45 52 20 52 54 54 00 00 00 00 00 00
```

### RTT 结果

停止残留 logger 后启动单个 `JLinkRTTLogger`（`CORTEX-M4`、SWD 1000 kHz、RTT 地址 `0x2004cf60`），明确等待 240 秒。日志仅有：

```text
========================================
Reset: NRST SW
```

没有 `BCBSTRESS: start`、`BCBSTRESS: done`、`commit rc` 或 `arbiter NONE` 行；原始日志保存在 `docs/ota-exec-notes/P0-4-bcbstress-rtt-2026-07-25.log`。停止 logger 后读取 up-buffer 描述符，`WrOff=RdOff=0x3c`，MCU PC 位于 LVGL `get_prop_core`，不是压测死循环。

静态交叉确认：压测函数内所有统计输出均调用 `CONFIG_DEBUG_SERIAL.printf(...)`；当前 `CONFIG_DEBUG_SERIAL` 定义为 `Serial5`，函数没有 `SEGGER_RTT_*` 输出。因此本次无法按卡内 §0.3 取得规定的 RTT 证据，不能以“无错误行”推定 `ok=1000 fail=0`。

### 复位收尾与结论

已将 `CONFIG_EEPROM_BCB_STRESS` 恢复为 `0`，以 `-AutoStale` 重建默认固件（0 warning / 0 error，`Program Size: Code=265736 RO-data=288288 RW-data=1236 ZI-data=461584`），并按同一 J-Link 流程重新烧录、复位、运行默认固件。最终未留压测宏或压测固件。

结论：**复验不通过，P0-4 保持“进行中”**。阻断项是压测结果未通过 RTT 输出通道可审计地取证；需将压测统计改为 `SEGGER_RTT_printf`（或明确绑定 RTT 输出）后再复验。用户消息中的 `P0-4-aceptance...` 为拼写误差，本仓库沿用既有规范文件名 `P0-4-acceptance...`。
## 8. RTT 通道修复后真机复验通过（2026-07-25）

实现已将 `EEPROM_BCBStress_Run` 内 8 处 `BCBSTRESS` 输出全部由 `CONFIG_DEBUG_SERIAL.printf` 改为 `SEGGER_RTT_printf(0, ...)`。独立静态核对结果：RTT 调用 8 处，旧 Serial5 压测调用 0 处，`CONFIG_DEBUG_RTT_ENABLE=1`。

将 `CONFIG_EEPROM_BCB_STRESS` 临时置 `1` 后，以 `build_f435.ps1 -AutoStale` 重编全部相关依赖：0 warning / 0 error，`Program Size: Code=267236 RO-data=288292 RW-data=1240 ZI-data=462604`。map 确认 `HAL::EEPROM_BCBStress_Run` 引用真实 `SEGGER_RTT_printf`，当前 `_SEGGER_RTT=0x2004cf60`。

按 `AT32F435RGT7`、SWD 1000 kHz、`h -> loadfile -> r -> g -> qc` 完成烧录和 Verify；SW-DP=`0x2BA01477`、Cortex-M4 r0p1。`mem8` 验证 RTT 控制块完整签名：

```text
53 45 47 47 45 52 20 52 54 54 00 00 00 00 00 00
```

停止残留 logger 后启动单个 `JLinkRTTLogger`，复位运行并等待最终行。原始日志 `docs/ota-exec-notes/P0-4-bcbstress-rtt-retest-2026-07-25.log`：

```text
========================================
Reset: NRST SW
BCBSTRESS: start 1000 iters
BCBSTRESS: done ok=1000 fail=0 / 1000
```

日志中无 `commit rc=`、`arbiter NONE`、`bootstrap commit FAIL`、`seq mismatch`，最终判定满足真机 1000 次写+读回零错标准。

取证后已将 `CONFIG_EEPROM_BCB_STRESS` 恢复为 `0`，以 `-AutoStale` 重建默认固件：0 warning / 0 error，`Program Size: Code=265736 RO-data=288288 RW-data=1236 ZI-data=461584`。默认 AXF/HEX/BIN SHA256 分别为 `615A0F3E07D1FF67212EE1B813444940F8D52B1972ECBD605FCDBD11AE0597B4`、`02BB1DA5C9B804092E8A4ACF8AF5ECCC3AD196F06846DD83432E63EB3FA510C1`、`9BF4A54CDB9FA7DB07BCD7A1B0C339424D2248CB854B93D3100DA23368B02572`；默认固件已重新烧录、复位运行，最终 map 不含压测符号，无残留 J-Link/logger 进程。

结论：**P0-4 独立验收通过，可置“完成”**。