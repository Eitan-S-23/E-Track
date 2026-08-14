# P2-5 F4 实现整改 R3 证据（2026-08-10）

## 0. 结论与边界

本文件是实现/整改会话证据，不是独立验收签字。实现侧已完成 Startup 生命周期复核、
SDIO 根因修复、FirmwareUpdate 回归、final-r5 fresh 构建封包、12 次模拟器真实 Startup、
同批次真机完整 OTA 预演和最终生产复位压力。P2-5 必须继续保持 `阻塞`，P2 必须继续
保持 `4/6`；只有新的非实现会话可以将其改为完成。

- 工作目录：`D:\github\my\E-Track-p2-5-20260801`
- 分支：`p2-5-20260801`
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- 基线：`0023e5f`
- 原始证据根：`.remediation-p2-5-f4\20260810-084053\`
- 本轮 final-r5 真机证据：`hardware-preview-r5b-20260810\`
- 本轮 final-r5 复位压力：`hardware-preview-r5-sdio-pressure\`
- 未执行 commit、push、merge、rebase、reset、checkout 或 stash
- 用户已授权覆盖 `E:\P2-5-FULL.etu`，并授权 SEGGER/J-Link 对
  `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 的可预见写入

最终工作树快照保存在 `.remediation-p2-5-f4\20260810-084053\final-snapshot-r5\`，
机器可读生产清理结果保存在
`.remediation-p2-5-f4\20260810-084053\final-production-cleanup-r5.json`。

## 1. 工作树状态与改动范围

最终 `git status --short --branch` 如下；其中既有差异和其他会话产物均原样保留：

```text
## p2-5-20260801...origin/p2-5-20260801
 M Libraries/OTA/ota_confirm_health.c
 M Libraries/OTA/ota_confirm_health.h
 M MDK-ARM_F435/Platform/Core/at32_sdio.c
 M MDK-ARM_F435/cmake-generated/compile_commands.json
 M PLAN-OTA-EXEC.md
 M Simulator/LVGL.Simulator/HAL/HAL_Encoder.cpp
 M Simulator/LVGL.Simulator/lv_conf.h
 M Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c
 M Tools/jlink/jlink-common.ps1
 M USER/App/App.cpp
 M USER/App/Config/Config.h
 M USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp
 M USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h
 M USER/App/Pages/Menu/MainMenu.cpp
 M USER/App/Utils/OtaUpdate/OtaUpdate.cpp
 M USER/HAL/HAL_EEPROM.cpp
 M USER/HAL/HAL_OTA_Package.cpp
 M USER/lv_port/lv_port_indev.cpp
 M tests/ota/test_ota_confirm_health.c
?? .acceptance-p2-5-f4/
?? .claude/prompt-F4-fix-implementation.md
?? .claude/prompt-F4-remediation.md
?? .claude/prompt-P2-5-verification.md
?? .remediation-p2-5-f4/
?? MDK-ARM_F435/cmake-generated/build-gcc-timing-r3/
?? MDK-ARM_F435/cmake-generated/build-gcc-timing-r4/
?? build-gcc-release/
?? docs/ota-exec-notes/P2-5-F4-fix-2026-08-05.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r2.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r3.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-07.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-09-r2.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-09.md
?? docs/ota-exec-notes/P2-5-F4-post-acceptance-remediation-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-review-2026-08-06.md
?? docs/ota-exec-notes/P2-5-hardware-verification-2026-08-05.md
?? flash-app.jlink
?? flash-probe.jlink
?? tests/ota/test_sdio_command_timeouts.py
```

相对 `0023e5f` 的 tracked 内容改动清单为：

```text
M Libraries/OTA/ota_confirm_health.c
M Libraries/OTA/ota_confirm_health.h
M MDK-ARM_F435/Platform/Core/at32_sdio.c
M MDK-ARM_F435/cmake-generated/compile_commands.json
M PLAN-OTA-EXEC.md
M Simulator/LVGL.Simulator/HAL/HAL_Encoder.cpp
M Simulator/LVGL.Simulator/lv_conf.h
M Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c
M USER/App/Config/Config.h
M USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp
M USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h
M USER/App/Pages/Menu/MainMenu.cpp
M USER/HAL/HAL_EEPROM.cpp
M USER/HAL/HAL_OTA_Package.cpp
M tests/ota/test_ota_confirm_health.c
```

此次接管直接新增的实现修复为：

- `MDK-ARM_F435/Platform/Core/at32_sdio.c`：9 个 SDIO 命令响应等待路径改为有界轮询。
- `tests/ota/test_sdio_command_timeouts.py`：静态回归 9 个等待函数均使用
  `SDIO_CMD0TIMEOUT` 且不会下溢或永久自旋。
- `.claude/prompt-P2-5-verification.md`：切换到 final-r5 路径、哈希和 fresh map RTT 规则。
- 本报告和项目内 final-r5/r5b harness、原始日志与摘要。

其余 tracked 差异是该 worktree 既有的 P2-5、F1、F4、FirmwareUpdate 生命周期和 UI
整改成果；本会话没有通过 checkout/reset 恢复、清理或覆盖来源不明的既有改动。

## 2. Startup 重复启动阻断复核

### 2.1 旧 Force harness 与正常生命周期对比

独立验收旧脚本 `.acceptance-p2-5-f4\20260809-082528\sim_startup_runner.ps1` 在系列开始、
每轮 `finally` 和轮次结束后无条件 `Stop-Process -Force`。旧 EXE SHA-256 为
`76E16E80C5C37BE2866A0F9D8A7E16F80059E49DAA021D0088D4C796DAE6B5C3`，结果为：

| 旧证据 | 退出方式 | 结果 | 失败特征 |
|---|---|---|---|
| `03-startup-initial-repeat.log` | 每轮 Force | FAIL, PASS | run1 `Responding=False/Hung=True` |
| `03-startup-rerun11-repeat.log` | 每轮 Force | FAIL, PASS | run1 `Responding=False/Hung=True` |
| `startup-series-repeat.log` | 每轮 Force | PASS, FAIL, PASS, FAIL | 失败停在 Loading/ETM |
| `03-startup-30s-probe-failure.txt` | Force 后扩展观察 | FAIL | 30 秒未恢复 |

项目内修正 harness：
`.remediation-p2-5-f4\20260810-084053\sim_lifecycle_runner.ps1`。它在每轮进入主界面后继续
观察 10 秒，正常发送 `WM_CLOSE` 并等待 5 秒，只有确认卡死且证据采集完成后才允许 Force。
final-r5 的 12 轮均未进入 Force 分支。

fresh 模拟器构建：

```powershell
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' `
  'D:\github\my\E-Track-p2-5-20260801\Simulator\LVGL.Simulator.sln' `
  /t:Rebuild /m /p:Configuration=Debug /p:Platform=x64 /v:minimal
```

- 退出码 `0`
- warning `102`
- error `0`
- EXE `5879296 B`
- 时间 `2026-08-10T14:56:37.8332001+08:00`
- SHA-256 `A9A14B426A29A44E522A22A9C3761C21D1B0C8FC378AE278F07B4450A6BD9ECF`

12 轮命令参数：`-RunCount 12 -MainObserveSeconds 10 -StartupDeadlineSeconds 30
-EvidenceName lifecycle-final-r5-12x`。

| Run | Startup ms | Main ms | CPU s | WS B | Private B | Responding/Hung | WM_CLOSE ms | Residual | 结果 |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| 1 | 2280 | 4625 | 1.234 | 56471552 | 93671424 | True/False | 105 | 0 | PASS |
| 2 | 1660 | 4538 | 1.281 | 56430592 | 93736960 | True/False | 170 | 0 | PASS |
| 3 | 1819 | 4689 | 1.281 | 56406016 | 93708288 | True/False | 84 | 0 | PASS |
| 4 | 1729 | 4631 | 1.234 | 56393728 | 93700096 | True/False | 147 | 0 | PASS |
| 5 | 1790 | 4705 | 1.406 | 56401920 | 93687808 | True/False | 95 | 0 | PASS |
| 6 | 1717 | 4580 | 1.234 | 56434688 | 93769728 | True/False | 116 | 0 | PASS |
| 7 | 1968 | 4822 | 1.297 | 56459264 | 93736960 | True/False | 85 | 0 | PASS |
| 8 | 1848 | 4720 | 1.281 | 56406016 | 93708288 | True/False | 87 | 0 | PASS |
| 9 | 1576 | 4481 | 1.375 | 56459264 | 93745152 | True/False | 93 | 0 | PASS |
| 10 | 2074 | 4919 | 1.328 | 56418304 | 93704192 | True/False | 104 | 0 | PASS |
| 11 | 1891 | 4766 | 1.422 | 56483840 | 94687232 | True/False | 91 | 0 | PASS |
| 12 | 1902 | 4782 | 1.094 | 56422400 | 93716480 | True/False | 85 | 0 | PASS |

聚合为 `12/12 PASS`、`Responding=True`、`Hung=False`、残留进程 `0`。498 个过程采样点
全部 responding、无 hung；采样峰值为 CPU `1.406s`、Working Set `56479744 B`、
Private Memory `94695424 B`，关闭前记录峰值为 CPU `1.422s`、Working Set
`56483840 B`、Private Memory `94687232 B`。证据：
`simulator\lifecycle-final-r5-12x\logs\summary.txt`、`results.json`、`resource-peaks.json`。

### 2.2 Startup 结论

`USER/App/App.cpp` 仍从 `manager.Push("Pages/Startup")` 启动，Startup timeline 真实创建和
运行，模拟器文件系统仍使用生产 PC 路径。本轮没有修改 Startup、Win32 消息泵、flush、
paint、窗口显示或添加等待时间。正常 `WM_CLOSE` 生命周期稳定 12/12，而旧失败只在无条件
Force harness 下出现，因此 Startup 交替挂起判定为旧 harness 生命周期假象，不对产品代码
作投机修改。

## 3. 本轮发现并修复的真实实现缺陷

### 3.1 根因

真机软件复位和扫描窗口复位压力暴露了独立于 Startup 的真实缺陷：SDIO 命令事务被软件
复位或调试 halt 打断后，部分响应等待函数使用 `while(1)`，另一些使用 `while(timeout--)`。
当控制器既不产生完成标志也不产生硬件 timeout 标志时，`while(1)` 永久自旋；后置递减写法
还会在退出条件判断前下溢。App 初始化因此停在 SD 路径，主循环无法继续，最终表现为 WDT
复位或永久无响应。

### 3.2 修复机制

`MDK-ARM_F435/Platform/Core/at32_sdio.c` 中以下 9 个路径统一改为
`while(timeout > 0)`，每次无完成标志时显式 `timeout--`，耗尽后返回
`SD_CMD_RSP_TIMEOUT`：

- `command_error`
- `command_rsp7_error`
- `command_rsp1_error`
- `command_rsp3_error`
- `command_rsp2_error`
- `command_rsp4_error`
- `command_rsp5_error`
- `command_rsp6_error`
- `check_card_programming`

修复没有关闭 WDT、持续喂狗、延长超时或改变 FirmwareUpdate 页面逻辑；它在真实故障层把
不可恢复的永久等待变成可返回的 SD 命令超时，使现有 SD 初始化/恢复路径能够继续。

新增回归：

```powershell
python tests/ota/test_sdio_command_timeouts.py
```

结果：退出码 `0`，raw warning/error 词计数 `0/0`，
`SDIO_COMMAND_TIMEOUTS=PASS functions=9`。

修复后真机压力：

- 普通软件复位 `12/12 PASS`。
- FirmwareUpdate 扫描窗口 50/75/100/125/150/200/250/300/400/500/650/800 ms
  打断后复位 `12/12 PASS`。
- final-r5 无插桩 v20801/CONFIRMED 再执行普通软件复位 `12/12 PASS`；每轮均为
  `SDReady=1`、`VTOR=0x08010000`、`CFSR=0`，RTT 无 WDT/HardFault/debug 标记。

前两组证据：`hardware-preview-r4-sdio-pressure\02-regular-reset-r2\summary.json` 和
`03-scan-interrupt-reset\summary.json`；最终生产组证据：
`hardware-preview-r5-sdio-pressure\02-regular-reset\summary.json`。

## 4. F4 时序门禁与 provenance

本轮没有复用历史 `307.497 ms`、`817/917 ms` 或旧固件哈希。先冻结最终生产源码：

- 文件数 `2943`
- source manifest SHA-256
  `D3268F4AE8BB6CF514EE3B7717BC14C8A65E3082ED91C2B8C462A883801BF293`
- `FirmwareUpdate.cpp` 生产源码 SHA-256
  `22AFC025B7A3FFD9006D6D5DFFDF7C5487F8B8AC4D3C20736A7C3FD1BC028FD7`

随后仅从该冻结源码派生 timing-r4 测量镜像，记录完整 instrumentation patch、timing ELF/map/
bin 哈希和 fresh map RTT 地址。测量完成后源码逐字节恢复，2943 文件复核 `0 mismatch`，再
fresh `--clean-first` 构建并生成 final-r5。测量镜像只用于计时，不作为最终生产镜像。

timing-r4 实测最坏值：

| 项目 | 最坏值 | 门禁 | 结果 |
|---|---:|---:|---|
| 根目录 `LoadFiles()` | `37.747 ms` | `320 ms` | PASS |
| 页面创建 | `814.028 ms` | - | PASS |
| 加 100 ms 输入轮询上界 | `914.028 ms` | `1000 ms` | PASS |
| `/F4ACC` 256 项截断扫描 | `47.020 ms` | `320 ms` | PASS |
| 单次目录读取 | `593 us` | - | PASS |
| 每 32 次读取喂狗上界 | `18.976 ms` | WDT `10000 ms` | `526.98x` 余量 |

原始汇总：`timing-r4\hardware-run-r4-20260810-01\07-complete-timing-summary.json`。
生产源码恢复和 post-timing fresh 构建证据分别位于 `source-freeze-r4\`、
`build\gcc-release-post-timing-r4\`。

## 5. FirmwareUpdate 与模拟器 fixture 回归

此前 MainMenu/FirmwareUpdate 同驻导致 LVGL heap 耗尽、同步事件回调内清理导致 UAF、
Candidate Verify 黑屏、返回/重入和布局问题的整改保持有效。final-r5 六类有效 fixture
`6/6 PASS`：截断、ROW_MAX、只有上级项、小目录选择、完整导入流和修正后的 exact256。

旧 `exact256` fixture 实际含 258 个运行时可见项，旧亮度判定属于假 PASS。本轮 harness 新增
`ExpectedEntryCount` 门禁，严格 256 项正确显示“未找到 ETU”且不显示截断提示。人工查看本轮
截图确认：

- `MORE FILES EXIST / NOT ALL SHOWN` 两行完整可读。
- “文件管理”标题无遮挡。
- “返回”和“开始导入”水平、垂直居中。
- Candidate Verify、工作页和结果页无黑屏或文字残缺。
- 取消、返回、结果返回、再次进入和最终浏览器返回稳定。

汇总：`simulator\fixture-results-final-r5\11-final-fixture-summary.json`。

## 6. 宿主测试、专项 harness 与构建

### 6.1 宿主测试

命令原文在 `host-tests-final-r5\00-commands.txt`，原始日志和摘要在
`host-tests-final-r5\13-summary.json`。下表 `W/E` 是统一正则从原始日志统计的 warning/error
单词出现次数；部分 error 是负向场景名称，不是执行失败，最终判定以退出码和 PASS marker
为准。

| 命令 | rc | raw W/E | 关键结果 |
|---|---:|---:|---|
| `python tests/boot/test_fw_header_vectors.py` | 0 | 0/0 | 16/16 |
| `python tests/boot/test_boot_protocols.py` | 0 | 0/0 | 19/19 |
| `python tests/boot/test_boot_state_machine.py` | 0 | 0/1 | 96/96 |
| `python tests/boot/test_p1_6_protocol.py` | 0 | 0/0 | 21/21 |
| `python tests/ota-vectors/test_vectors.py` | 0 | 1/0 | 9/9 |
| `python tests/ota/test_ota_staging.py` | 0 | 0/0 | 48/48 |
| `python tests/ota/test_ota_package.py` | 0 | 0/3 | 102/102 |
| `python tests/ota/test_ota_patch.py` | 0 | 0/0 | 167/167 |
| `python tests/ota/test_ota_sd.py` | 0 | 1/6 | 29/29 + adapter 5/5 |
| `python tests/ota/test_ota_update.py` | 0 | 1/6 | 7/7 |
| `python tests/ota/test_ota_backup.py` | 0 | 0/0 | backup 108/108 + health 24/24 |
| `python tests/ota/test_sdio_command_timeouts.py` | 0 | 0/0 | functions 9/9 |

聚合 `12/12 PASS`。

### 6.2 专项 harness

`build\final-static-r5\11-summary.json` 中 10 条编译、执行和校验命令均退出 `0`，
warning/error 为 `0/0`：

- F4 扫描：`F4_ACCEPTANCE_HARNESS=PASS`，覆盖过滤项、SCAN_MAX、ROW_MAX、exact scan、
  deviceReady 优先级。
- TEST_BOOT 门禁：`Begin()` 和 `Apply()` 均拒绝，文件 open/close 对称，
  `OTA_TEST_BOOT_GATE_HARNESS=PASS`。
- Boot artifact：`14724 B`、vector/MSP/reset handler 合法。
- Boot handoff：NVIC/PRIMASK/BASEPRI/FAULTMASK/CONTROL/VTOR/BX 断言通过。

### 6.3 fresh GCC Release

```powershell
cmake --build MDK-ARM_F435\cmake-generated\build-gcc-release --clean-first --parallel
```

- 退出码 `0`
- warning `1249`
- error `0`
- `FAILED` `0`
- Boot 与前一冻结产物逐字节一致。
- App 因 `__DATE__/__TIME__` 有 11 字节变化，故废弃旧 final-r4，重新生成 final-r5，未沿用
  旧哈希或旧 ETU。

### 6.4 AC5 正式尝试

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `
  "& 'MDK-ARM_F435\build_f435.ps1' -AutoStale -AutoFonts"
```

- 退出码 `1`
- warning `0`
- compiler error `0`
- precondition failure `1`
- 原因：历史缺失 `MDK-ARM_F435\Objects\X-Track.lnp`，脚本要求先由 UV4 生成。
- 命令没有注入 `--cpp11`，没有伪装为构建成功。

干净摘要：`build\ac5-final-r5\03-clean-summary.json`。

## 7. final-r5 产物与封包

| 产物 | 大小 | 时间 | SHA-256 |
|---|---:|---|---|
| raw App | 598852 B | 2026-08-10T14:26:15.5155083+08:00 | `8A5DEEBE5EB0D79AD2BD0CE0A9F0F93ACA6F99F5C3A3A87C0C10D9615783D741` |
| v20800 App | 598852 B | 2026-08-10T14:30:40.4593942+08:00 | `04F99BE0E30C3DE9C6DE4C65FE730C11B152BF7D87FB3747B90AE99E466B1381` |
| v20801 App | 598852 B | 2026-08-10T14:30:41.0664240+08:00 | `E77EAF2A2A2894051297E24733A35ED97014D5DAFDB88759826C22CC379DBF5A` |
| ETU | 281189 B | 2026-08-10T14:30:42.2647719+08:00 | `1A8F2FD5D579A578CB59BDBF2C26DD56FABC3A8C70A0A2013D853475DA2C8648` |
| 解包 candidate | 598852 B | 2026-08-10T14:30:42.7119338+08:00 | `E77EAF2A2A2894051297E24733A35ED97014D5DAFDB88759826C22CC379DBF5A` |
| Boot bin | 14724 B | 2026-08-10T14:26:13.2387003+08:00 | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| 模拟器 EXE | 5879296 B | 2026-08-10T14:56:37.8332001+08:00 | `A9A14B426A29A44E522A22A9C3761C21D1B0C8FC378AE278F07B4450A6BD9ECF` |

`P2-5-FULL-candidate.bin` 与 final-r5 v20801 App 逐字节一致，`fc /b` 退出 `0`。
manifest：`artifacts\final-r5\artifact-manifest.json`。

## 8. final-r5 真机实现侧预演

### 8.1 SD 写入和基线

`E:\P2-5-FULL.etu` 旧包 `281257 B / 44FAB404...1E366C` 先备份到项目内，再覆盖为
final-r5。回读为 `281189 B / 1A8F2FD5...2C8648`，与源文件一致。

使用 fresh P1-6 TEST_BOOT Boot 执行正式 `CLEAR_BCB`，随后烧录 final-r5 生产 Boot 和
v20800 App。最终 map `_SEGGER_RTT=0x20053E14`，`mem8` 验证 `SEGGER RTT` 签名；基线为
`vcode=20800 / CONFIRMED / SDReady=1 / VTOR=0x08010000 / CFSR=0`。

### 8.2 exact final-r5b UI 运行

第一次 final-r5 UI 运行因未在启动前等待用户明确就位，仅保留自动状态证据，不作为视觉
证据。随后新建 `hardware-preview-r5b-20260810`，重新执行 Setup、BuildP16、
PrepareBaseline、Baseline；停在基线并等待用户回复“开始观察”后，明确倒计时 5 秒才启动
UI 阶段。

自动状态断言：

- 真实 Startup 后当前页为 Dialplate。
- 文件管理进入、浏览器返回、再次进入通过。
- `/P2-5-FULL.etu` 可选，第一次二次确认通过。
- 取消回浏览器，再次选择和第二次确认通过。
- 导入结果 `mode=3 / ResultSuccess=1 / ApplyPending=0 / StagePending=0`。
- 结果返回、再次进入、最终浏览器返回通过。
- 预重启仍 `v20800 / SDReady=1 / CFSR=0`，RTT 无 WDT/HardFault。

同步视觉观察由用户在 exact final-r5b 运行结束后立即确认：

- `CANDIDATE VERIFY` 出现。
- `BACKUP + STAGED` 出现。
- 成功结果页出现。
- 全程无黑屏、重启或文字残缺。

用户本轮原话为：`1 2 3均出现，4无异常`。

观察 manifest：`hardware-preview-r5b-20260810\ui-observation-final-r5b.json`；
`04-ui\ui-summary.json` 的 `VisualObservations.OverallStatus=PASS`。首次附加因 PowerShell 5.1
按本地代码页读取无 BOM UTF-8 中文字段而失败，改为等价 ASCII 后重跑通过；失败和重跑
日志均保留，未影响设备或 UI 状态。

### 8.3 TEST_BOOT 到 CONFIRMED

重启后 RTT：

```text
OTA: HANDOFF vtor=0x08010000 ...
Reset: NRST SW
OTA: TEST_BOOT confirmed vcode=20801
```

健康探测：`vcode=20801 / CONFIRMED / SDReady=1 / VTOR=0x08010000 / CFSR=0`。

二次重启 RTT：

```text
OTA: HANDOFF vtor=0x08010000 ...
Reset: NRST SW
OTA: BCB already CONFIRMED vcode=20801
```

再次健康探测同样为 `vcode=20801 / CONFIRMED / SDReady=1 / VTOR=0x08010000 /
CFSR=0`。两段 RTT 均不含 HardFault、WDT、`RTTCMD:`、F4TRACE 或 F4PROBE。

关键证据：

- `05-test-boot\test-boot-rtt.log`，SHA-256
  `E74DCABF99FE90F5371F91FDBF7C91600BB9D9701224073C956F0C9BD556F8B5`
- `06-confirmed-reboot\confirmed-reboot-rtt.log`，SHA-256
  `832D825E85EF9B66C58B898EAEB8C1BFF659CA4D15DFFD64E6F2C045E9755D25`
- `07-final-external-and-process-audit.json`

## 9. 最终生产清理

最终检查结果：

- App 入口唯一为 `Pages/Startup`，Startup 页面仍创建并启动真实 `anim_timeline`。
- 模拟器文件系统仍使用生产默认 `LV_FS_PC_PATH="."`，无验收目录硬编码。
- `CONFIG_RTT_DEBUG_CMD_ENABLE=0`。
- final-r5 v20800/v20801、Boot 和模拟器二进制均不含 `F4TRACE`、`F4PROBE`、
  `RTTCMD:`、`F4TIMING` 或 `F4METRIC`。
- WDT 保持 `CONFIG_WATCH_DOG_TIMEOUT=(10 * 1000)`，未关闭或放宽。
- 共享 `LV_MEM_SIZE=(128U * 1024U)`。
- `USER/main.cpp` 的 F1 确认后持续喂狗机制未破坏。
- `FirmwareUpdate.cpp`、`FirmwareUpdate.h`、`PLAN-OTA-EXEC.md` 为 UTF-8 无 BOM。
- 指定源码 include 使用正斜杠。
- `git diff --check=0`；换行转换提示不属于 whitespace error，退出码为 `0`。
- `E:\P2-5-FULL.etu` 回读为 `281189 B / 1A8F2FD5...2C8648`，与 final-r5 源包一致。
- `LVGL.Simulator`、`JLinkRTTLogger`、`JLinkGUIServer` 残留进程均为 `0`。

机器可读清理摘要为 `final-production-cleanup-r5.json`；最终 git 六项快照位于
`final-snapshot-r5\`。本轮主动选择的项目外写入仅为用户已授权的
`E:\P2-5-FULL.etu` 和 SEGGER `JLinkDLL.ini` 可预见更新，未发现其他主动项目外产物。

首次清理脚本因把 PowerShell 自动变量 `$Matches` 当作本地布尔值，并错误绑定 nullable
长度参数，在实际大小和 SHA-256 均一致时仍把所有 `MatchesExpected` 写成 `false`。原始
误判保存在 `final-production-cleanup-r5-initial-script-failure.json`，首次快照摘要保存在
`final-snapshot-r5\07-snapshot-summary-initial-script-failure.json`；修正脚本只重算元数据，
未改任何产品文件，最终 `final-production-cleanup-r5.json` 为 `PASS`。

## 10. 尚存风险与独立验收入口

实现侧没有已知未关闭的 P2-5 产品缺陷。尚存验证/工具风险：

- AC5 仍因历史缺失 `Objects\X-Track.lnp` 无法进入编译；已如实记录，未手工注入
  `--cpp11`。
- 本轮 UI 指定文字采用用户同步观察，不是相机照片。新独立验收若要求图像证据，应在其
  exact fresh 运行中拍照或录像，不能复用本实现侧口述。
- timing-r4 是从冻结 final 生产源码派生的临时测量镜像；最终二进制已重新 fresh 构建且
  不含插桩。独立验收应复核 source-freeze、instrumentation patch、恢复校验和 final-r5
  manifest 的 provenance 链，不得再引用历史时序数字。

交给新的独立验收会话：

- 操作提示：`.claude\prompt-P2-5-verification.md`
- final-r5 产物：`.remediation-p2-5-f4\20260810-084053\artifacts\final-r5\`
- 实现侧总证据：`.remediation-p2-5-f4\20260810-084053\`
- exact 真机预演：`hardware-preview-r5b-20260810\`
- 最终复位压力：`hardware-preview-r5-sdio-pressure\`
- 当前设备：final-r5 v20801、BCB `CONFIRMED`
- 当前 SD：`E:\P2-5-FULL.etu`，SHA-256
  `1A8F2FD5D579A578CB59BDBF2C26DD56FABC3A8C70A0A2013D853475DA2C8648`

P2-5 继续 `阻塞`，P2 继续 `4/6`，等待新的非实现会话独立验收。
