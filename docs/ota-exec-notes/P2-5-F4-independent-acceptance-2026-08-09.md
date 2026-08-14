# P2-5 F4 整改后独立验收报告（2026-08-09）

## 0. 结论

本轮独立验收不通过。P2-5 保持“阻塞”，P2 总进度保持 `4/6`。

已独立通过的部分包括生产清理、F4 扫描 harness、五类模拟器 F4 fixture、11 组宿主回归、TEST_BOOT 新 OTA 门禁 harness、fresh GCC App/Boot 构建以及 fresh `.etu` candidate 一致性。

决定性阻断发生在生产模拟器 Startup 稳定性门槛。fresh `/t:Rebuild` 后，连续四次启动结果为 `PASS, FAIL, PASS, FAIL`，失败轮停在 Startup 的 `Loading/ETM` 画面，进程为 `Responding=False`、`Hung=True`。此前两组独立双启动也均为 `FAIL, PASS`，另一次 30 秒探测仍未恢复。因此无法满足“生产入口从 Startup 开始，至少连续启动两次且响应正常”。

按照验收提示词“发现实现缺陷时停止扩展验证”的 fail-fast 要求，本轮未写物理 SD、未调用 J-Link、未烧录、未执行真机 F4 和完整 OTA。不得使用实现会话的 r3 真机结果替代本轮独立验收。

## 1. 验收身份与快照

- 工作树：`D:\github\my\E-Track-p2-5-20260801`
- 分支：`p2-5-20260801`
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- F4 实现前基线：`0023e5f`
- 原始证据：`.acceptance-p2-5-f4\20260809-082528\`
- 本轮未执行 commit、push、merge、rebase、reset、checkout 或 stash。
- 本轮未修改实现代码，仅新增验收证据、本报告和看板阻塞记录。

验收前命令均已原样落盘：

```text
git rev-parse --show-toplevel
git rev-parse HEAD
git status --short --branch
git diff --stat 0023e5f
git diff --check
git diff --name-status 0023e5f
```

`git diff --check` 退出 `0`，保留 15 条 LF 到 CRLF 提示，不将其粉饰为工作树干净。完整原始输出见 `preflight\01-10`。

相对 `0023e5f` 的实际内容差异共 13 个文件，与实现证据合并申报逐项一致：

```text
Libraries/OTA/ota_confirm_health.c
Libraries/OTA/ota_confirm_health.h
MDK-ARM_F435/cmake-generated/compile_commands.json
PLAN-OTA-EXEC.md
Simulator/LVGL.Simulator/HAL/HAL_Encoder.cpp
Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c
USER/App/Config/Config.h
USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp
USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h
USER/App/Pages/Menu/MainMenu.cpp
USER/HAL/HAL_EEPROM.cpp
USER/HAL/HAL_OTA_Package.cpp
tests/ota/test_ota_confirm_health.c
```

以下文件在 `git status` 中显示修改，但相对基线无内容差异，已如实归类为状态项：

```text
Tools/jlink/jlink-common.ps1
USER/App/App.cpp
USER/App/Utils/OtaUpdate/OtaUpdate.cpp
USER/lv_port/lv_port_indev.cpp
```

`compile_commands.json` 是 CMake 生成副产物，未隐藏。未跟踪项包括既有 `.claude` 提示词、历史验收/整改文档、根级 `build-gcc-release/`、flash 脚本/日志及全部验收目录；完整列表见 `preflight\07-untracked-files.txt`，最终状态另见本轮 `final` 审计。

## 2. 生产清理检查

| 检查项 | 结果 | 证据 |
|---|---|---|
| `USER/App/App.cpp` 唯一生产入口 `Pages/Startup` | 通过 | `APP_STARTUP_COUNT=1` |
| 无 FirmwareUpdate 页面直达 | 通过 | `APP_DIRECT_FIRMWAREUPDATE_COUNT=0` |
| 模拟器 PC 路径恢复 `.` | 通过 | `SIM_NORMAL_PATH=True` |
| 生产 RTT 命令开关为 0 | 通过 | `RTT_DEBUG_CMD_ZERO=True` |
| 最终 ELF/bin 无 `F4TRACE/F4PROBE/RTTCMD:/RttDebugCmd_Poll` | 通过 | marker count 均为 0 |
| 指定三个文件 UTF-8 无 BOM | 通过 | 头字节 `23 69 6E`、`23 69 66`、`23 20 50` |
| `USER/main.cpp` F1 修复未改变 | 通过 | 相对基线 diff 0 行 |
| 看门狗保持启用且超时 10000ms | 通过 | 配置静态核对 |
| `HAL_Config.h`、`boot/`、冻结契约无 F4 diff | 通过 | diff 0 行 |
| `RTE_Components.h` 无 diff | 通过 | diff 0 行 |
| 源码 include 无反斜杠 | 通过 | 0 命中 |
| `git diff --check` | 通过 | rc=0 |

源码内仍可搜索到 6 条 `RTTCMD:` 字符串，但全部位于 `#if CONFIG_RTT_DEBUG_CMD_ENABLE` 禁用分支。fresh ELF/bin 字符串审计均为 0，故不判为生产插桩残留。完整清理审计见 `static\01-production-cleanup-and-diff-audit.txt`。

## 3. F4 专项复核

### 3.1 独立 harness

独立编译并运行 `static\f4_scan_acceptance.cpp`，编译和运行均退出 `0`：

```text
F4_ACCEPTANCE_HARNESS=PASS
FILTERED scans=4 rows=1
MIXED scans=256 rows=0 reads=257 more=1
ROWMAX rows=24 reads=25 more=1
EXACT_SCAN reads=257 more=0
DEVICE_PRIORITY=4
```

该 harness 覆盖隐藏文件、非 `.etu`、路径过长条目消耗扫描上限；`.etu` 位于上限之后；ROW_MAX 截断；0 行/仅上级行；恰好 256 项不误报；设备错误最高优先级；正常小目录选择路径。

### 3.2 量化独立复算

原始实现日志的 SHA、字段和算术均重新计算，结果如下：

| 指标 | 独立复算 |
|---|---:|
| 测量时 SD 根目录实际条目 | 8（ETU 1、目录 4、隐藏 2、其他 1） |
| 根目录 `lv_fs_dir_read` 平均/最坏 | `136.111us / 378us` |
| 修复后根目录 `LoadFiles()` | `44.941ms` |
| 已测最大目录 | 96 项 |
| 96 项完整/修复路径 | `4.157ms / 4.153ms` |
| 96 项读取平均/最坏 | `29.144us / 313us` |
| 最终 257 次读取最坏外推 | `97.660ms` |
| 扫描加 24 行 UI 保守值 | `307.497ms` |
| 实现预声明 UI 阈值 | `320ms` |
| 阈值裕度 | `12.503ms` |
| 每 32 项喂狗最坏间隔 | `12.160ms` |
| 相对 10000ms IWDG 裕度 | `9987.840ms`，约 `822.37x` |
| heap 修复后页面到文件完成 | `817ms` |
| 含 100ms 输入轮询上界 | `917ms` |

原 F4 触发目录已不可恢复，修复前同目录 `LoadFiles()` 总耗时不能直接实测。本报告不沿用旧的“>10 秒即扫描耗时”推断；后续证据已将旧复位根因更正为 LVGL heap OOM/HardFault 后次生 WDT。完整复算见 `static\02-f4-quantitative-recalculation.txt`。

### 3.3 模拟器 F4 fixture

fixture 全部位于本轮证据目录，使用 fresh EXE，未改 `lv_fs_pc.c` 或其他生产源码：

| 场景 | 结果 | 关键观察 |
|---|---|---|
| 300 余过滤项且 ETU 在上限后 | 通过 | 显示 `MORE FILES EXIST, NOT ALL SHOWN`，不显示“未找到 ETU” |
| 可见行达到 ROW_MAX 且仍有条目 | 通过 | 24 行路径显示截断提示 |
| 恰好 256 项 | 通过 | 显示“未找到 ETU”，不误报截断 |
| 子目录仅 `..` 可见且目录仍有剩余 | 通过（一次 Startup 挂起后复跑） | `only-up-r2-after.png` 显示截断提示 |
| 正常小目录 | 通过 | fresh ETU 可见并进入 `2.7.0 -> 2.8.1` 二次确认 |

确认页截图同时证明用户上轮指出的布局问题已修正：页面标题未被内容框遮盖，“返回”和“开始导入”文字在按钮内水平、竖直居中。

截断文案在 240px 屏幕右侧仍有边缘裁切，但可见文本明确表达“仍有文件且未全部显示”。该项沿用上轮口径记为非阻断显示缺陷。

### 3.4 真机 F4

未执行。原因不是设备不可用，而是生产模拟器连续启动门槛先失败，按 fail-fast 停止扩展验证。本轮不能据实现会话旧 RTT、旧地址或旧真机闭环宣告真机 F4 通过。

## 4. 宿主回归与门禁

以下 11 条正式命令均退出 `0`：

```text
python tests/boot/test_fw_header_vectors.py
python tests/boot/test_boot_protocols.py
python tests/boot/test_boot_state_machine.py
python tests/boot/test_p1_6_protocol.py
python tests/ota-vectors/test_vectors.py
python tests/ota/test_ota_staging.py
python tests/ota/test_ota_package.py
python tests/ota/test_ota_patch.py
python tests/ota/test_ota_sd.py
python tests/ota/test_ota_update.py
python tests/ota/test_ota_backup.py
```

| 测试 | 结果 |
|---|---:|
| fw_header | 16/16 |
| Boot Ymodem / ETSL | 19/19 |
| Boot state machine | 96/96 |
| P1-6 protocol | 21/21 |
| OTA golden vectors | 9/9 |
| P2-1 staging | 48/48 |
| P2-2 package | 102/102 |
| P2-3 patch | 167/167 |
| P2-4 SD core/adapter | 29/29 + 5/5 |
| P2-4 Session | 7/7 |
| P2-5 backup | 108/108 |
| P2-5 confirm health | 24/24，基线为 17/17，无回退 |

TEST_BOOT 新 OTA 门禁采用允许的生产等价 harness。`Begin()` 和 `Apply()` 在非 CONFIRMED 状态均拒绝，打开/关闭计数不变：

```text
BEGIN_TEST_BOOT rejected=1 result=busy error=gate:bcb_not_confirmed opens=5/5 closes=5/5
APPLY_TEST_BOOT rejected=1 applied=0 error=gate:bcb_not_confirmed opens=2210/2210 closes=2210/2210
OTA_TEST_BOOT_GATE_HARNESS=PASS
```

初次门禁 harness 编译因 PowerShell 拼接 `-I` 参数错误失败，原始日志保留为 `static\04-ota-gate-harness.log`；修正验收脚本后正式结果为 `static\05-ota-gate-harness-final.log`，未修改生产代码。

## 5. Fresh 构建

### 5.1 GCC Release App/Boot

正式命令：

```text
cmake --build MDK-ARM_F435\cmake-generated\build-gcc-release --clean-first --parallel
```

结果：退出 `0`，耗时 `531449ms`，`1249` 行编译 warning，`0` error，`0` failed。warning 未粉饰。构建日志 SHA-256 为 `8DCDFCB42C6564E83DAE9909D3E3A283B97092479A623810C27D3C589C502570`。

| 产物 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| App raw bin | 598684 B | 2026-08-09T09:06:24.4234512+08:00 | `8C0832F3B8701685442DC0C634E64E95CC3EB73EE899151E18D6BB89D66585D9` |
| App ELF | 859732 B | 2026-08-09T09:06:24.1944727+08:00 | `EE7B3E3DD5807B2C8290694C72545FAD137CB3CFCD61E260307C0ED643B31939` |
| App map | 2232959 B | 2026-08-09T09:06:24.2022839+08:00 | `DEC808F0A74BC8FF2827170D13E75C03CCD48795992D67EAD565E544E66F5274` |
| Boot bin | 14724 B | 2026-08-09T09:06:19.8398414+08:00 | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| Boot ELF | 36860 B | 2026-08-09T09:06:19.5366132+08:00 | `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC` |

Boot 小于 64KiB，恰有 3 个 LOAD segment，RWX segment 为 0。fresh map 严格解析得到：

```text
0x20045e14                _SEGGER_RTT
```

该地址本轮只完成 map 解析，未执行 `mem8` 签名验证，因此不得用于本轮 RTT 结论。

### 5.2 AC5

按 AGENTS.md 正式尝试，未注入 `--cpp11`：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\MDK-ARM_F435\build_f435.ps1' -AutoStale"
```

退出 `1`，历史阻断仍为 `MDK-ARM_F435\Objects\X-Track.lnp` 缺失。该结果未写成通过。

## 6. 模拟器决定性失败

fresh rebuild 命令：

```text
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' 'D:\github\my\E-Track-p2-5-20260801\Simulator\LVGL.Simulator.sln' /m /t:Rebuild /p:Configuration=Debug /p:Platform=x64 /v:minimal
```

结果为退出 `0`、`102 warning / 0 error`。fresh EXE：

| 路径 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| `Simulator\Output\Debug\x64\LVGL.Simulator.exe` | 5877760 B | 2026-08-09T09:26:12.8420601+08:00 | `76E16E80C5C37BE2866A0F9D8A7E16F80059E49DAA021D0088D4C796DAE6B5C3` |

决定性复现命令：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .acceptance-p2-5-f4\20260809-082528\sim_startup_runner.ps1 -RunCount 4 -ObserveSeconds 11 -OutputPrefix startup-series
```

结果：

| 轮次 | Responding | Hung | CPU | 画面 |
|---|---|---|---:|---|
| 1 | True | False | 2.203s | 正常进入仪表盘 |
| 2 | False | True | 46.438s | 停在 `Loading/ETM` |
| 3 | True | False | 2.047s | 正常进入仪表盘 |
| 4 | False | True | 34.313s | 停在 `Loading/ETM` |

截图 SHA：

```text
startup-series-run1.png F39AB76DE28A5909D36580FE4B0E7A8ABCA264783B0142013FAC548937906B3E
startup-series-run2.png 375B60CD19F81443BB0DEB49B559F25015F85C2598A411E02773FC8DB2549E77
startup-series-run3.png C9C0158E619FDA65FF0F82961326888FD4B504BA3251CBA8CDF44DF6F3A58CA4
startup-series-run4.png C5276F1370A5335743E10ACC1244620DA39327CDD6ABC1CC4004AC82CFD6EA18
```

另外两组双启动分别为 `FAIL,PASS` 和 `FAIL,PASS`。一次 30 秒探测首轮仍未恢复，随后窗口客户区失效导致验收截图构造失败。所有轮次结束后 `LVGL.Simulator` 残留进程均为 0。

本轮不对根因作未经证明的实现判断，但现象稳定发生在生产 Startup 内，早于 FirmwareUpdate 页面，且明确违反要求的连续两次响应性门槛。应由实现会话定位模拟器 Startup/Win32 事件循环或跨启动状态问题，验收会话不修改源码绕过。

## 7. Fresh 升级包一致性

本轮没有复用实现会话 r3 包，而是从本轮 fresh raw App 重新生成。`build_ts=1786237584`。

| 资产 | 大小 | SHA-256 / vcode |
|---|---:|---|
| raw App | 598684 B | `8C0832F3B8701685442DC0C634E64E95CC3EB73EE899151E18D6BB89D66585D9` |
| v20800 finalized App | 598684 B | `3D4E561AB6B8F3207BA4AD07A5BA4658AAD3FDA3EBBD784E081A8107B55CC829` |
| v20801 finalized App | 598684 B | `1DF28BEB3CF6F86C9E6ECBABB140F0D11020605076EDFC99A54581CE9EFB45B1` |
| fresh `P2-5-FULL.etu` | 281137 B | `8BB5819F6D0BF5BBCD1BE1518488D2CF61BBB17753C33641ED34C5EF45AAAE50` |
| unpack candidate | 598684 B | `1DF28BEB3CF6F86C9E6ECBABB140F0D11020605076EDFC99A54581CE9EFB45B1` |

`finalize`、`verify`、`pack-full`、`unpack --verify-fw-header` 和 `fc /b` 均退出 `0`。candidate 与 v20801 finalized App 大小、SHA 和逐字节比较完全一致；`target_vcode=20801 > baseline_vcode=20800`。

首次封包验收脚本因 Windows PowerShell 5.1 将 Python stderr warning 提升为 `NativeCommandError` 而退出 `1`，未形成产品失败。验收脚本改为按原生进程退出码判定后正式重跑通过；失败记录保留为 `package\00-first-attempt-failure.txt`。

## 8. 真机与 SD 未执行项

本轮开始时 `E:` 未挂载；未向任何项目外路径写入。模拟器门槛失败后按 fail-fast 停止，因此以下项目未执行：

- 未覆盖 `E:\P2-5-FULL.etu`，未做 SD 写后回读和 SD 直接解包。
- 未读取当前设备 baseline vcode 或 BCB。
- 未用 P1-6 CLEAR_BCB 恢复 v20800 CONFIRMED 基线。
- 未烧录 fresh Boot/v20800 App。
- 未执行 `mem8 0x20045e14 16` RTT 签名验证。
- 未执行最终生产固件真机 F4 文件管理、截断提示、耗时和 WDT 检查。
- 未执行 `CANDIDATE VERIFY -> BACKUP + STAGED -> APPLYING -> TEST_BOOT -> CONFIRMED`。
- 未采集重启后至少 90 秒 RTT。
- 未验证二次普通复位仍为 `BCB already CONFIRMED vcode=20801`。
- 未验证升级后屏幕、按键和基本页面功能。

本轮未调用 `JLink.exe`、`JLinkRTTLogger.exe` 或 `JLinkGUIServer`，没有污染旧地址、旧固件或旧日志。设备状态未被本验收会话改变。

## 9. 验收矩阵

| 要求 | 结果 | 说明 |
|---|---|---|
| 验收前快照与改动清单 | 通过 | 原始命令、状态、diff、完整 untracked 清单已落盘 |
| 生产代码清理 | 通过 | Startup、PC 路径、BOM、WDT、契约、插桩均符合 |
| F4 扫描边界 | 通过 | 独立 harness 与五类 fixture 通过 |
| F4 量化阈值 | 通过 | `307.497ms < 320ms`，喂狗裕度 `822.37x` |
| 正常 ETU 选择与确认 | 通过（模拟器） | fresh ETU 可见，确认页和按钮布局正常 |
| 真机 F4 无 WDT/HardFault | 未执行 | 模拟器 fail-fast |
| 11 组宿主回归 | 通过 | 全部 rc=0，无基线回退 |
| TEST_BOOT 新 OTA 门禁 | 通过 | 生产等价 Begin/Apply harness 均拒绝 |
| fresh GCC App/Boot | 通过 | 1249 warning、0 error；Boot 14724B、无 RWX |
| AC5 正式尝试 | 历史阻断 | 缺 `X-Track.lnp`，未注入 `--cpp11` |
| 模拟器 `/t:Rebuild` | 通过 | 102 warning、0 error |
| 模拟器连续两次 Startup | **失败** | 多轮交替挂起，无连续两次通过 |
| fresh ETU/candidate 一致 | 通过 | `fc /b` rc=0，target 20801 > 20800 |
| SD 写入与回读 | 未执行 | fail-fast，且 `E:` 未挂载 |
| RTT 地址签名 | 未执行 | 仅从 fresh map 得到 `0x20045e14` |
| 真机完整 OTA | 未执行 | fail-fast |
| 二次复位 CONFIRMED | 未执行 | fail-fast |

最终判定：不通过。P2-5 继续阻塞，P2 保持 `4/6`。

## 10. 关键证据索引

- 快照：`.acceptance-p2-5-f4\20260809-082528\preflight\`
- 生产清理：`static\01-production-cleanup-and-diff-audit.txt`
- F4 复算：`static\02-f4-quantitative-recalculation.txt`
- F4 harness：`static\03-f4-harness.log`
- 门禁 harness：`static\05-ota-gate-harness-final.log`
- 宿主回归：`host-tests\00-summary.log` 及 `01-11` 日志
- fresh GCC：`build\01-fresh-gcc-app-boot-build.log`、`build\06-fresh-artifact-audit.log`
- AC5：`build\07-ac5-formal-attempt.log`
- 模拟器构建：`simulator\01-msbuild-rebuild.log`、`simulator\02-msbuild-summary.txt`
- Startup 阻断：`simulator\startup-series-repeat.log`、`simulator\06-simulator-verdict.txt`
- F4 fixture：`simulator\05-fixture-run-aggregate.log`、`simulator\*.png`
- fresh 包：`package\08-package-summary.json`、`package\01-07` 日志
