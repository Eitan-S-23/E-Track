# P0-5 独立验收记录（2026-07-25）

验收人：Codex（非实现会话）
历史结论（2026-07-25）：**通过，P0-5 置“完成”**（见 §7）。2026-07-26 收口后复审整改见 §8；当前卡重新进入“进行中”，实现会话真机回归已完成，等待非实现会话独立复核。
过程摘要：首轮 JEDEC 走 Serial5 且 ID=0 不通过（§1-§5）；整改后 JEDEC 仍为 0 再次打回（§6）；RDID 读序修复后真机命中 `0xEF4018`、OTA enabled、注错 PASS、1000/1000 零错通过（§7）。

依据：`PLAN-OTA-EXEC.md` P0-5 卡内验收标准，以及 `AGENTS.md` J-Link/RTT 取证红线。

## 1. selftest=1 构建与烧录

- 临时置 `CONFIG_QSPI_SELFTEST_ENABLE=1`，执行
  `MDK-ARM_F435/build_f435.ps1 -AutoStale`。
- AC5/armlink/fromelf 均成功，未见 warning/error：
  `Program Size: Code=264972 RO-data=288308 RW-data=1244 ZI-data=461584`。
- 产物时间：`X-Track.axf` 2026-07-25 20:43:28，
  `X-Track.hex` / `Track.bin` 2026-07-25 20:43:29。
- 使用 `AT32F435RGT7`、SWD 1000 kHz，按
  `h -> loadfile -> r -> g -> qc` 烧录；SW-DP 为 `0x2BA01477`，
  Cortex-M4 r0p1，Flash download 与 Verify 均 `O.K.`。

## 2. RTT 取证

- 当前 selftest 构建的严格 map 符号：`_SEGGER_RTT=0x2004cf68`。
- J-Link `mem8 0x2004cf68 16` 得到
  `53 45 47 47 45 52 20 52 54 54`，RTT 控制块签名有效。
- 清理残留进程后只启动一个 `JLinkRTTLogger`。原始日志：
  `docs/ota-exec-notes/P0-5-qspi-rtt-2026-07-25.log`。

```text
Reset: NRST SW
QSPISELF: inject timeout rc=1 (PASS)
QSPISELF: start 1000 iters @0x7F0000 (reserved)
QSPISELF: done ok=1000 fail=0 / 1000
```

因此卡内“1000 次读/写/擦零错”和“注错超时返回错误码而非死循环”两项真机结果通过。

## 3. JEDEC 阻断

- RTT 日志没有卡内取证项要求的
  `QSPI: JEDEC=0x... whitelisted, OTA enabled`。
- 静态核对发现成功/失败两条 JEDEC 输出位于
  `USER/HAL/HAL_W25Q128.cpp`，均调用
  `CONFIG_DEBUG_SERIAL.printf`；该宏固定为 `Serial5`，不是 RTT，
  不满足 `AGENTS.md` “验收判定依赖输出必须直接走 RTT API”的红线。
- 更关键的是，按当前 selftest map 读取运行态：
  `g_qspi_ota_disabled=0x20005a6c`，
  `g_qspi_jedec_id=0x20005a70`。
  J-Link `mem8 0x20005a6c 8` 返回
  `01 00 00 00 00 00 00 00`，即 OTA disabled 为 `1`、JEDEC ID 为
  `0x000000`，并未命中白名单。
- 恢复默认固件后按新 map 重读仍得到同一状态，排除 selftest 产物或地址漂移误判。

这说明 RDID/白名单启动链当前没有在真机得到有效 JEDEC ID。即使 QSPI 自检数据路径可完成 1000 次擦写读回，也不能证明 JEDEC 判定目标已实现。

## 4. 默认固件恢复

- 已恢复 `CONFIG_QSPI_SELFTEST_ENABLE=0`。
- 再次执行 `-AutoStale` 构建，未见 warning/error：
  `Program Size: Code=263500 RO-data=288308 RW-data=1244 ZI-data=453392`。
- 默认产物时间：`X-Track.axf` 2026-07-25 21:02:15，
  `X-Track.hex` / `Track.bin` 2026-07-25 21:02:16。
- map 中 `QSPISELF` / `Qspi_SelfTest` 符号计数为 0；默认固件已重新烧录，
  Flash download 与 Verify 均 `O.K.`；无残留 `JLinkRTTLogger`。

## 5. 结论

**不通过。P0-5 打回并保持“进行中”，P0 进度仍为 4/6。**

整改要求：

1. 修复真机 `qspi_read_jedec_id` / RDID 命令口链路，使板载芯片读出白名单 ID，并使 `g_qspi_ota_disabled=false`。
2. 将 JEDEC 成功和失败标记直接输出到 RTT，整改后重新执行 selftest=1 构建、烧录、RTT 和运行态复验。

## 6. 整改复验（2026-07-25）

本轮针对 §5 的两项整改重新独立执行：

- `Qspi_Init` 已静态确认在 `qspi_read_jedec_id()` 前调用 `qspi_flash_reset()`；成功/失败 JEDEC 行已改为 `SEGGER_RTT_printf`。
- 临时置 `CONFIG_QSPI_SELFTEST_ENABLE=1`，`-AutoStale` 构建 0E0W：
  `Program Size: Code=265024 RO-data=288312 RW-data=1244 ZI-data=461584`。
  map 重新解析 `_SEGGER_RTT=0x2004cf68`，J-Link 签名仍为 `SEGGER RTT`；烧录 Verify `O.K.`。
- 单 logger 原始日志：`docs/ota-exec-notes/P0-5-qspi-rtt-retest-2026-07-25.log`。

```text
Reset: NRST SW
QSPI: JEDEC=0x000000 NOT whitelisted, OTA disabled
QSPISELF: inject timeout rc=1 (PASS)
QSPISELF: start 1000 iters @0x7F0000 (reserved)
QSPISELF: done ok=1000 fail=0 / 1000
```

- J-Link 直接读取 `g_qspi_ota_disabled@0x20005a6c` / `g_qspi_jedec_id@0x20005a70` 仍得
  `01 00 00 00 00 00 00 00`，即 OTA disabled=1、JEDEC ID=0。
- 注错和 1000 次擦写读回继续通过；JEDEC 白名单判定仍失败，因此不能放行。
- 已恢复 `CONFIG_QSPI_SELFTEST_ENABLE=0`，默认固件重新构建 0E0W：
  `Program Size: Code=263552 RO-data=288312 RW-data=1244 ZI-data=453392`；
  map 中自检符号计数为 0，默认固件已重新烧录并 Verify `O.K.`。

本轮结论仍为不通过：RTT 通道整改已验证，但真机 RDID 仍为 `0x000000`，需继续修复 RDID/flash 复位链后再次验收。

## 7. 第二次整改复验（2026-07-25）

本轮针对命令口小数据读的 RX FIFO 阈值问题重新独立验收：

- 静态确认 `qspi_read_jedec_id()` 已改为 kick 后等待 `QSPI_CMDSTS_FLAG`，再连续读取 3 字节，不再等待 32B RX FIFO 阈值；`Qspi_Init` 保留 flash reset，并通过 RTT 输出 `rc`。
- `CONFIG_QSPI_SELFTEST_ENABLE=1` 下独立执行 `-AutoStale`，AC5/armlink/fromelf 0E0W：
  `Program Size: Code=265028 RO-data=288308 RW-data=1244 ZI-data=461584`。
  `_SEGGER_RTT=0x2004cf68`，J-Link `mem8` 签名为 `SEGGER RTT`；烧录与 Verify 均 `O.K.`。
- J-Link 运行态读取 `mem8 0x20005a6c 8`：
  `00 00 00 00 18 40 EF 00`，即 `g_qspi_ota_disabled=0`、JEDEC ID=`0xEF4018`。
- 单 logger 原始日志：`docs/ota-exec-notes/P0-5-qspi-rtt-third-2026-07-25.log`。

```text
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
QSPISELF: inject timeout rc=1 (PASS)
QSPISELF: start 1000 iters @0x7F0000 (reserved)
QSPISELF: done ok=1000 fail=0 / 1000
```

- 已恢复 `CONFIG_QSPI_SELFTEST_ENABLE=0`，默认固件独立重建 0E0W：
  `Program Size: Code=263556 RO-data=288308 RW-data=1244 ZI-data=453392`；
  map 中 `QSPISELF` / `Qspi_SelfTest` 引用计数为 0，默认固件重新烧录并 Verify `O.K.`。
- 默认固件新 map `_SEGGER_RTT=0x2004af68` 签名有效，运行态再次读取同一 JEDEC/OTA 状态：
  `00 00 00 00 18 40 EF 00`。

结论：通过。P0-5 满足卡内真机压测、注错 fail-closed、JEDEC 白名单和默认固件恢复要求，可置“完成”。

## 8. 收口后复审整改（2026-07-26）

本节 supersede §7 的状态结论，不抹除历史取证。

- 修复 HAL 集成的 fail-closed 缺口：reset、JEDEC、自检和最终 XIP 初始化均成功后才允许 `OTA enabled`；XIP 或自检失败保持 `g_qspi_ota_disabled=true`。
- 修复自检循环吞错：每轮 XIP 初始化返回值和注错结果均纳入最终状态。
- 修复可选 QSPI MSC 后端：容量排除末尾 64KB 保留区，读路径首次解引用前确认 XIP 初始化，擦除/写入/XIP 错误不再恒报 `USB_OK`；同时修正 QSPI 头文件的 C++ linkage，并加入容量/保留区编译期一致性检查。
- 默认 AC5、selftest=1 和 QSPI-MSC 分支编译均通过（0 error/0 warning）。实现会话随后完成当前版本真机复验，详见 §9；看板仍需非实现会话复核后才可置“完成”。

## 9. 当前实现会话真机复验（2026-07-26）

本节是当前实现会话的回归证据，不替代看板规则要求的非实现会话验收。

- 组合固件 AC5 构建 0 error/0 warning：`Program Size: Code=267084 RO-data=288316 RW-data=1248 ZI-data=462604`。
- 当前 map `_SEGGER_RTT=0x2004cf68`，签名 `SEGGER RTT`；单 logger 证据见
  `docs/ota-exec-notes/P0-final-combined-rtt-2026-07-26.md`。
- RTT 取得 `QSPISELF: inject timeout rc=1 (PASS)`、`QSPISELF: done ok=1000 fail=0 / 1000`、
  `QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled`；运行态
  `mem8 0x20005a6c 8 = 00 00 00 00 18 40 EF 00`，logger 无残留。
- 复验后 selftest/stress 均恢复为 `0`，默认固件 `Code=263496` 重建、烧录和 Verify
  通过，默认运行态仍为 OTA enabled；仍需非实现会话复核后才能置完成。

## 10. 2026-07-26 独立复核（复审整改后）

本节由非实现会话在当前未提交工作区全新构建、烧录和采集；组合 RTT 证据为新日志，不复用实现会话的污染记录。

### 宿主前置与组合构建

`tests/bcb` 先执行 `gcc -Wall -Wextra -Werror -I../../Libraries/EEPROM ../../Libraries/EEPROM/eeprom_bcb.c test_bcb_arbiter.c`，27 个断言全部 `PASS`，摘要为 `0 failure(s)`。

临时仅将 `CONFIG_EEPROM_BCB_STRESS` 与 `CONFIG_QSPI_SELFTEST_ENABLE` 置 `1`（`rg -n "CONFIG_EEPROM_BCB_STRESS|CONFIG_QSPI_SELFTEST_ENABLE" USER/HAL/HAL_Config.h` 确认位置为 `USER/HAL/HAL_Config.h:35-44`），执行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'MDK-ARM_F435\build_f435.ps1' -AutoStale"
```

armlink/fromelf exit `0`，`0 Error 0 Warning`；`Program Size: Code=267084 RO-data=288316 RW-data=1248 ZI-data=462604`。组合产物时间：AXF 2026-07-26 17:26:22，HEX/BIN 2026-07-26 17:26:23（大小分别 6787320/1563103/555700 bytes）。

使用 `AT32F435RGT7`、SWD 1000 kHz 和 `h -> loadfile -> r -> g -> qc` 烧录，Flash download 557056 bytes，Verify `O.K.`。严格 map 解析命令分别匹配 `^\s*_SEGGER_RTT\s+`、`^\s*g_qspi_ota_disabled\s+`、`^\s*g_qspi_jedec_id\s+`，得到 `_SEGGER_RTT=0x2004cf68`、`g_qspi_ota_disabled=0x20005a6c`、`g_qspi_jedec_id=0x20005a70`；`mem8 0x2004cf68 16` 验证 `SEGGER RTT` 签名。

实际烧录命令及 command file：

```powershell
JLink.exe -Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1 -ExitOnError 1 -CommandFile p0-45-flash-acceptance.jlink
# p0-45-flash-acceptance.jlink: h; loadfile "...\MDK-ARM_F435\Objects\X-Track.hex"; r; g; qc
```

### RTT 与运行态判定

清理残留进程后只运行一个 `JLinkRTTLogger`（`CORTEX-M4`、SWD 1000 kHz、channel 0，420 秒硬超时）。原始日志为 [`P0-4-P0-5-independent-rtt-2026-07-26.log`](P0-4-P0-5-independent-rtt-2026-07-26.log)，长度 300 bytes，SHA-256=`236474D0B4391933EED607AE099B6F1E078C26BDFB211AF661EA8BB344FFE5C5`：

```powershell
JLinkRTTLogger.exe -Device CORTEX-M4 -If SWD -Speed 1000 -RTTAddress 0x2004CF68 -RTTChannel 0 docs/ota-exec-notes/P0-4-P0-5-independent-rtt-2026-07-26.log
```

```text
Reset: NRST SW
QSPISELF: inject timeout rc=1 (PASS)
QSPISELF: start 1000 iters @0x7F0000 (reserved)
QSPISELF: done ok=1000 fail=0 / 1000
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
```

日志命中白名单实值 `0xEF4018`（非 0），注错返回 `rc=1`，自检 `ok=1000 fail=0`。J-Link `mem8 0x20005a6c 8` 读回 `00 00 00 00 18 40 EF 00`，即 `g_qspi_ota_disabled=0`、JEDEC=`0xEF4018`，与 RTT 一致。

### 恢复现场

两个宏均恢复 `0`，再次 `-AutoStale` 构建：armlink/fromelf exit `0`，`0 Error 0 Warning`，`Program Size: Code=263496 RO-data=288312 RW-data=1244 ZI-data=453392`。默认产物时间：AXF 2026-07-26 17:44:37、HEX/BIN 17:44:38；map 中 `BCBSTRESS|QSPISELF|EEPROM_BCBStress_Run|Qspi_SelfTest` 命中数为 `0`。默认固件重新烧录并 Verify `O.K.`，新 RTT 地址 `0x2004af68` 的签名仍有效；按 `mem8 0x20005a6c 8` 复读 `00 00 00 00 18 40 EF 00`，即默认运行态 `disabled=0 / JEDEC=0xEF4018`，确认无残留 `JLinkRTTLogger`。

结论：**P0-5 独立复核通过，JEDEC 白名单、fail-closed 注错和 1000 次自检均满足。**
