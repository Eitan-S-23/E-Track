# P2-5 F4 实现整改 R2 证据（2026-08-09）

## 0. 结论与边界

本文件是实现/整改会话证据，不是独立验收签字。当前实现侧整改、宿主回归、
fresh GCC/模拟器构建、final-r2 制包、六类模拟器 fixture、连续 12 次真实 Startup
和生产清理均已完成。P2-5 必须继续保持 `阻塞`，P2 必须继续保持 `4/6`；只有新的
非实现会话可以将其改为完成。

- 活动 worktree：`D:\github\my\E-Track-p2-5-20260801`
- 分支：`p2-5-20260801`
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- 基线：`0023e5f`
- 原始证据根：`.remediation-p2-5-f4\20260809-104540\`
- 本会话未执行 commit、push、merge、rebase、reset、checkout 或 stash
- 用户已明确授权覆盖 `E:\P2-5-FULL.etu`，并授权运行可能更新
  `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 的 SEGGER/J-Link 工具
- final-r2 实现侧真机预演已完成，设备当前运行 v20801 生产 App，BCB 为 `CONFIRMED`

最终工作树原始快照保存在：

- `.remediation-p2-5-f4\20260809-104540\final-snapshot-r4\01-git-status.txt`
- `.remediation-p2-5-f4\20260809-104540\final-snapshot-r4\02-diff-stat.txt`
- `.remediation-p2-5-f4\20260809-104540\final-snapshot-r4\03-diff-check.txt`
- `.remediation-p2-5-f4\20260809-104540\final-snapshot-r4\04-name-status.txt`

`final-snapshot-r3\` 原样保留一次采集脚本失败：PowerShell 参数名与自动变量 `$Args`
冲突，六条命令实际都退化为裸 `git` 并退出 `1`。随后改用显式 `GitArguments` 参数生成
`final-snapshot-r4\`，六条命令全部退出 `0`；该失败不属于源码或 `git diff --check` 回退。

最终 `git status --short --branch --untracked-files=normal` 原文：

```text
## p2-5-20260801...origin/p2-5-20260801
 M Libraries/OTA/ota_confirm_health.c
 M Libraries/OTA/ota_confirm_health.h
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
?? build-gcc-release/
?? docs/ota-exec-notes/P2-5-F4-fix-2026-08-05.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r2.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-07.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-09.md
?? docs/ota-exec-notes/P2-5-F4-post-acceptance-remediation-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-review-2026-08-06.md
?? docs/ota-exec-notes/P2-5-hardware-verification-2026-08-05.md
?? flash-app.jlink
?? flash-probe.jlink
```

相对基线的 diff stat 为 `14 files changed, 359 insertions(+), 59 deletions(-)`。
`Tools/jlink/jlink-common.ps1`、`USER/App/App.cpp`、`USER/App/Utils/OtaUpdate/OtaUpdate.cpp`
和 `USER/lv_port/lv_port_indev.cpp` 出现在 status，但相对 `0023e5f` 无内容差异；本会话没有
通过 checkout/reset 等方式处理这些既有状态。

相对 `0023e5f` 的实质 tracked 改动覆盖以下 14 个文件；另有本任务证据、提示词和
历史报告为 untracked，均未被清理或覆盖：

```text
Libraries/OTA/ota_confirm_health.c
Libraries/OTA/ota_confirm_health.h
MDK-ARM_F435/cmake-generated/compile_commands.json
PLAN-OTA-EXEC.md
Simulator/LVGL.Simulator/HAL/HAL_Encoder.cpp
Simulator/LVGL.Simulator/lv_conf.h
Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c
USER/App/Config/Config.h
USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp
USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h
USER/App/Pages/Menu/MainMenu.cpp
USER/HAL/HAL_EEPROM.cpp
USER/HAL/HAL_OTA_Package.cpp
tests/ota/test_ota_confirm_health.c
```

本轮直接实现侧收口集中在：

- `FirmwareUpdate.cpp/.h`：完整截断提示、布局、异步清理/返回。
- `Simulator/LVGL.Simulator/lv_conf.h`：恢复共享 MCU LVGL pool 到 `128U * 1024U`。
- `.claude/prompt-P2-5-verification.md`：更新 final-r2 包元数据。
- `PLAN-OTA-EXEC.md`：追加实现整改完成、等待独立验收记录。

其余 tracked 差异来自本 worktree 既有 P2-5/F1/F4 整改成果，本会话未恢复或覆盖。

## 1. Startup 复现、根因与整改机制

### 1.1 第七轮独立验收的旧 harness

原始脚本：

` .acceptance-p2-5-f4\20260809-082528\sim_startup_runner.ps1 `

脚本在系列开始、每轮 `finally` 和每轮结束后都无条件执行：

```powershell
Get-Process LVGL.Simulator -ErrorAction SilentlyContinue | Stop-Process -Force
Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
```

因此它没有测试正常窗口关闭生命周期，也没有验证 `WM_CLOSE` 后 5 秒内自行退出；
每轮都以 Force 终止上一进程，再立即启动下一进程。该模式违反本轮要求“只有确认
卡死并完成证据采集后才允许 Force”。

旧 harness 的原始结果如下，EXE SHA-256 为
`76E16E80C5C37BE2866A0F9D8A7E16F80059E49DAA021D0088D4C796DAE6B5C3`：

| 证据 | 退出模式 | 逐轮结果 | 失败特征 |
|---|---|---|---|
| `03-startup-initial-repeat.log` | 每轮无条件 Force | FAIL, PASS | run1 `Responding=False/Hung=True`, CPU `24.938s` |
| `03-startup-rerun11-repeat.log` | 每轮无条件 Force | FAIL, PASS | run1 `Responding=False/Hung=True`, CPU `44.875s` |
| `startup-series-repeat.log` | 每轮无条件 Force | PASS, FAIL, PASS, FAIL | 失败 CPU `46.438s/34.313s` |
| `03-startup-30s-probe-failure.txt` | Force harness 扩展观察 | FAIL | 30 秒仍未恢复，窗口客户区失效 |

旧失败轮工作集约 `148-200 MB`、Private Memory 约 `186-236 MB`，但每轮强制结束，
无法证明正常关闭后的下一次生产启动也会失败。

### 1.2 修正后的 lifecycle harness

项目内 harness：

` .remediation-p2-5-f4\20260809-104540\sim_lifecycle_runner.ps1 `

它逐轮记录 EXE 时间/哈希、PID、窗口句柄、`Responding`、`IsHungAppWindow`、CPU、
Working Set、Private Memory、Startup 视觉判定、主界面视觉判定、主界面稳定观察、
`WM_CLOSE` 时间和残留进程。只有 `WM_CLOSE` 超时、进程不响应/窗口已挂起并完成失败
截图后，才允许 Force 终止。本轮 12 次均未进入 Force 分支。

fresh rebuild 命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\.remediation-p2-5-f4\20260809-104540\run_final_simulator_build.ps1"
```

- 退出码：`0`
- warning：`102`
- error：`0`
- EXE：`Simulator\Output\Debug\x64\LVGL.Simulator.exe`
- 大小：`5879296 B`
- 时间：`2026-08-09T17:52:22.7508281+08:00`
- SHA-256：`1A18E957C039D0FB6B8A51F8B7DBF19C20E0BE9B17974F28858E844F621F59E1`

12 轮命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\.remediation-p2-5-f4\20260809-104540\sim_lifecycle_runner.ps1" -RunCount 12 -MainObserveSeconds 10 -StartupDeadlineSeconds 30 -EvidenceName "lifecycle-final-r2-12x"
```

| Run | Startup ms | Main ms | CPU s | WS B | Private B | Responding/Hung | WM_CLOSE ms | Residual | 结果 |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| 1 | 2399 | 4797 | 1.359 | 56438784 | 93741056 | True/False | 92 | 0 | PASS |
| 2 | 1831 | 4645 | 1.172 | 56442880 | 93765632 | True/False | 73 | 0 | PASS |
| 3 | 1805 | 4643 | 1.281 | 56508416 | 93822976 | True/False | 82 | 0 | PASS |
| 4 | 1920 | 4750 | 1.344 | 56463360 | 93761536 | True/False | 76 | 0 | PASS |
| 5 | 1835 | 4677 | 1.266 | 56467456 | 93777920 | True/False | 167 | 0 | PASS |
| 6 | 1898 | 4766 | 1.484 | 56500224 | 93835264 | True/False | 94 | 0 | PASS |
| 7 | 1846 | 4692 | 1.188 | 56471552 | 93786112 | True/False | 83 | 0 | PASS |
| 8 | 1889 | 4731 | 1.297 | 56451072 | 93806592 | True/False | 82 | 0 | PASS |
| 9 | 1855 | 4705 | 1.344 | 56512512 | 93818880 | True/False | 100 | 0 | PASS |
| 10 | 1831 | 4672 | 1.234 | 56500224 | 93822976 | True/False | 80 | 0 | PASS |
| 11 | 1986 | 4834 | 1.672 | 56430592 | 93712384 | True/False | 72 | 0 | PASS |
| 12 | 1824 | 4645 | 1.438 | 56438784 | 93745152 | True/False | 120 | 0 | PASS |

结论：`PASS_COUNT=12`、`FAIL_COUNT=0`。每轮都捕获真实 Startup 动画，进入主界面后
继续观察至少 10 秒，全部 `Responding=True/Hung=False`，关闭方式全部为
`WM_CLOSE`，退出码全部 `0`，下一轮前残留全部 `0`。首轮、末轮及每轮 Startup/最终
截图均在 `simulator\lifecycle-final-r2-12x\screenshots\`。

### 1.3 根因判定

本轮没有修改 Startup 页面、Win32 消息泵、flush、paint 或窗口显示产品代码，也没有
增加 sleep/超时、跳过 Startup、禁用 timeline 或直接进入 Dialplate。静态清理确认：

- `USER/App/App.cpp` 仍唯一执行 `manager.Push("Pages/Startup")`。
- `StartUpView.cpp` 仍创建并启动 `lv_anim_timeline`，无 `_WIN32` 视觉绕过。
- Startup 视觉实现无 `LV_EVENT_DRAW_POST`、`lv_draw_*`、shadow 或 mask 路径。
- 模拟器文件系统仍使用 `LV_FS_PC_PATH "."`。

在没有 Startup/Win32 产品修复的前提下，正确的正常关闭生命周期连续通过 12 次，
而旧失败证据明确来自每轮无条件 Force 的 harness。故本轮判定第七轮“Startup 交替挂起”
是旧 harness 生命周期假象，而不是可在生产正常关闭路径复现的缺陷。修复措施是保留并
使用项目内 lifecycle harness，不对产品代码作无证据投机修改。

## 2. FirmwareUpdate 缺陷与布局整改

### 2.1 LVGL heap-use-after-free

ASan 原始失败：

`simulator\fixture-results\small-full-repro-stdout\small-full-repro-stdout-stderr.log`

根因是 LVGL 按钮/输入事件回调仍在分发栈上时，同步执行 `ReleaseUI()`，其内部
`lv_obj_clean(_root)` 删除当前事件目标和子树；LVGL 回调返回后继续访问已释放对象，形成
heap-use-after-free。结果页返回、浏览器返回和进入路径切换均可能触发同类重入。

修复机制：

- `RequestEnterPath()`、`RequestGoUp()`、`RequestBack()` 只写 pending 状态。
- 使用 `lv_async_call(onAsyncAction, this)` 将 `EnterPath/GoUp/ReleaseUI+Pop` 延迟到当前
  LVGL 事件分发完成后执行。
- `pendingAsync` 合并重复请求，`ReleaseUI()` 清理 timer/group/对象指针和 pending 状态。
- Pop 前仍先 `ReleaseUI()`，但不再在触发 Pop 的按钮回调栈内同步删除对象。

修复后 ASan stderr：

`simulator\fixture-results\small-full-fixed\`，stderr 为空。

### 2.2 截断提示与布局

- 截断提示改为居中的完整两行：`MORE FILES EXIST` / `NOT ALL SHOWN`。
- `SetBrowserMessage()` 在有提示时把列表高度从 `LIST_H` 调整为 `LIST_H_MESSAGE`，为提示
  让出独立空间。
- 标题位于内容框上方，不再被列表/面板覆盖。
- 确认页“返回”“开始导入”和结果页“返回”使用零上下 padding 与明确居中布局。
- browser/confirm/work UI 按需创建，MainMenu 与 FirmwareUpdate 不再同时保持高峰 UI。

final-r2 fixture 命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\.remediation-p2-5-f4\20260809-104540\run_final_fixtures.ps1"
```

| 场景 | 动作 | 退出码 | stderr | WM_CLOSE | 结果 |
|---|---|---:|---:|---|---|
| trunc-root | 截断目录 | 0 | 0 B | 74 ms | PASS |
| rowmax-root | ROW_MAX | 0 | 0 B | 73 ms | PASS |
| exact256-root | 恰好扫描上限 | 0 | 0 B | 86 ms | PASS |
| only-up-root | 只有 `..`/进入上级 | 0 | 0 B | 90 ms | PASS |
| small-root | ETU 选择/二次确认 | 0 | 0 B | 74 ms | PASS |
| small-root | 取消、再确认、Candidate Verify、结果返回、再次进入、浏览器返回 | 0 | 0 B | 74 ms | PASS |

聚合：`AllPassed=true`，六个 stderr 均为 `0 B`，ResidualProcesses=`0`。canonical EXE
SHA-256 全部一致为 `1A18E957...1F59E1`，fixture 使用的 ETU SHA-256 为
`C0F8862D...F2D8E8`。

人工查看以下 final-r2 截图：

- `simulator\fixture-results-final-r2\trunc\trunc-browser.png`
- `simulator\fixture-results-final-r2\small-select\small-select-confirm.png`
- `simulator\fixture-results-final-r2\small-full-flow\small-full-flow-result.png`
- `simulator\fixture-results-final-r2\small-full-flow\small-full-flow-final-main.png`

确认标题、完整截断提示和按钮文字布局满足反馈；Candidate Verify/结果页非黑屏，返回和
再次进入均稳定。

## 3. 完整实现侧回归

### 3.1 11 组宿主测试

所有命令原文保存在 `host-tests-final-r2\00-commands.txt`，逐条原始日志和 SHA-256 在
`host-tests-final-r2\12-summary.json`。

| 命令 | 退出码 | warning/error | 关键结果 |
|---|---:|---|---|
| `python tests/boot/test_fw_header_vectors.py` | 0 | 0/0 | 16/16 |
| `python tests/boot/test_boot_protocols.py` | 0 | 0/0 | 19/19 |
| `python tests/boot/test_boot_state_machine.py` | 0 | 0/0 | 96/96 |
| `python tests/boot/test_p1_6_protocol.py` | 0 | 0/0 | 21/21 |
| `python tests/ota-vectors/test_vectors.py` | 0 | 0/0 | 9/9 |
| `python tests/ota/test_ota_staging.py` | 0 | 0/0 | 48/48 |
| `python tests/ota/test_ota_package.py` | 0 | 0/0 | 102/102 |
| `python tests/ota/test_ota_patch.py` | 0 | 0/0 | 167/167 |
| `python tests/ota/test_ota_sd.py` | 0 | 0/0 | 29/29 + adapter 5/5 |
| `python tests/ota/test_ota_update.py` | 0 | 0/0 | 7/7 |
| `python tests/ota/test_ota_backup.py` | 0 | 0/0 | backup 108/108 + confirm health 24/24 |

聚合：`PassCount=11`、`FailCount=0`。

### 3.2 F4、TEST_BOOT 门禁与 boot validators

入口命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\.remediation-p2-5-f4\20260809-104540\run_final_static_harnesses.ps1"
```

所有内层 gcc/g++/Python 命令原文在 `build\final-static-r2\00-commands.txt`；11 个步骤
退出码均 `0`、warning=`0`、error=`0`。

```text
F4_ACCEPTANCE_HARNESS=PASS
FILTERED scans=4 rows=1
MIXED scans=256 rows=0 reads=257 more=1
ROWMAX rows=24 reads=25 more=1
EXACT_SCAN reads=257 more=0
DEVICE_PRIORITY=4

BEGIN_TEST_BOOT rejected=1 result=busy error=gate:bcb_not_confirmed opens=5/5 closes=5/5
APPLY_TEST_BOOT rejected=1 applied=0 error=gate:bcb_not_confirmed opens=2212/2212 closes=2212/2212
OTA_TEST_BOOT_GATE_HARNESS=PASS
P1_1_BOOT_ASSERTIONS=PASS bin=14724
P1_4_BOOT_HANDOFF_ASSERTIONS=PASS
```

### 3.3 fresh GCC Release App/Boot

```powershell
cmake --build MDK-ARM_F435\cmake-generated\build-gcc-release --clean-first --parallel
```

- 退出码：`0`
- warning：`1249`
- error：`0`
- FAILED：`0`
- App FLASH：`598836 / 960 KB`，`60.92%`
- App RAM：`352960 / 352 KB`，`97.92%`，约余 `7488 B`
- Boot FLASH：`14724 / 64 KB`，`22.47%`
- Boot RAM：`9784 / 352 KB`，`2.71%`
- 原始日志：`build\gcc-release-r2\01-clean-build.log`

warning 数量直接以原始日志中的 `warning:` 统一统计，没有隐藏为“构建成功”。

### 3.4 final-r2 制包

完整命令在 `artifacts\final-r2\00-package-commands.txt`。七个步骤
`finalize-v20800 / verify-v20800 / finalize-v20801 / verify-v20801 / pack / unpack /
byte-compare` 退出码均为 `0`。pack 与 unpack 各有 1 条 vendor 示例 key 提示，error=`0`；
其余步骤 warning/error=`0/0`。

- build timestamp：`1786267671`
- baseline vcode：`20800`
- target vcode：`20801`
- `TargetGreaterThanBaseline=true`
- `CandidateByteIdentical=true`

### 3.5 AC5 正式构建尝试

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'MDK-ARM_F435\build_f435.ps1' -AutoStale -AutoFonts"
```

- 退出码：`1`
- compiler warning：`0`
- compiler error：`0`
- failed：`1`
- `Cpp11Injected=false`
- 原因：历史缺失 `MDK-ARM_F435\Objects\X-Track.lnp`，脚本要求先运行 UV4 `-b`
- 未生成 AXF/BIN，未手工向 `build_f435.ps1` 注入 `--cpp11`
- 证据：`build\ac5-final-r2\02-summary.json`

## 4. 最终产物

| 产物 | 大小 | 时间 | SHA-256 |
|---|---:|---|---|
| GCC raw App | 598836 B | 2026-08-09T17:27:51.5927660+08:00 | CA8CA3412632ECCBE847B18AD99271C035248D8BC39FD7CEE5A5B7DDAB71AF8C |
| v20800 final App | 598836 B | 2026-08-09T17:35:48.7737306+08:00 | 20F0F3E3BC619BCA6A06B9F2E48DEF2FF9DDEDEE02E0898A1EBB640397E92B9E |
| v20801 final App | 598836 B | 2026-08-09T17:35:49.4011345+08:00 | 4E6F511846CC6C3F81A01D68C81036C4DF82F9A7AB5EE775611F6702EB2D02BA |
| Boot bin | 14724 B | 2026-08-09T17:27:47.7681823+08:00 | 5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594 |
| Simulator EXE | 5879296 B | 2026-08-09T17:52:22.7508281+08:00 | 1A18E957C039D0FB6B8A51F8B7DBF19C20E0BE9B17974F28858E844F621F59E1 |
| P2-5-FULL.etu | 281186 B | 2026-08-09T17:35:50.6284087+08:00 | C0F8862D6D3A7003F48C640028AAFF7ABE3BACD1FE9DF3A090D0FFB3F4F2D8E8 |
| 解包 candidate | 598836 B | 2026-08-09T17:35:51.0337730+08:00 | 4E6F511846CC6C3F81A01D68C81036C4DF82F9A7AB5EE775611F6702EB2D02BA |

路径：

- App/ETU/candidate：`.remediation-p2-5-f4\20260809-104540\artifacts\final-r2\`
- Boot：`MDK-ARM_F435\cmake-generated\build-gcc-release\boot\X-Track-Boot.bin`
- Simulator：`Simulator\Output\Debug\x64\LVGL.Simulator.exe`

candidate 与 v20801 final App 已由 `fc /b` 和最终清理审计双重证明逐字节一致。

## 5. 最终生产清理

审计命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\.remediation-p2-5-f4\20260809-104540\run_final_cleanup_audit.ps1"
```

首轮审计有两项 harness 误报：把 Startup 音乐的 `_WIN32` 分支误当视觉绕过，并把注释
中的 `LV_EVENT_DRAW_POST` 文本误当代码。原结果保存在
`final-audit-r2\attempt1-*`；收紧为只检查 `StartUpView.cpp` 且先剥离注释后重跑，
`PASS_COUNT=16`、`FAIL_COUNT=0`。

真机预演和文档收口后再次运行同一审计，结果保存在 `final-audit-r3\`，仍为
`PASS_COUNT=16`、`FAIL_COUNT=0`。

| 清理项 | 结果 |
|---|---|
| App 生产入口为 `Pages/Startup`，无 Dialplate/FirmwareUpdate 直达 | PASS |
| Startup timeline create/start，无 `_WIN32` 视觉绕过 | PASS |
| Startup 无 DRAW_POST/lv_draw/shadow/mask 风险代码 | PASS |
| 模拟器 FS 为正常 `LV_FS_PC_PATH "."` | PASS |
| `CONFIG_RTT_DEBUG_CMD_ENABLE=0` | PASS |
| App/Boot/Simulator 无 F4TRACE/F4PROBE/RTTCMD:/临时计时标记 | PASS |
| watchdog 仍为 `CONFIG_WATCH_DOG_TIMEOUT (10 * 1000)`，相对基线无 diff | PASS |
| `LV_MEM_SIZE=(128U * 1024U)` | PASS |
| `USER/main.cpp` F1 watchdog/confirm-health 双 feed 在位 | PASS |
| FirmwareUpdate.cpp/.h、PLAN-OTA-EXEC.md 为有效 UTF-8 无 BOM | PASS |
| FirmwareUpdate include 无反斜杠 | PASS |
| candidate 与 final v20801 App 逐字节一致 | PASS |
| `git diff --check` 退出 0 | PASS |
| 无 LVGL.Simulator/JLinkRTTLogger/JLinkGUIServer 残留 | PASS |

注意：`Simulator/LVGL.Simulator/lv_conf.h` 是 MCU 与模拟器共享配置。基线中的 `72 KiB`
会在 MCU 上压缩 LVGL pool，而 Windows 使用 custom malloc，不能用模拟器表现证明安全；
因此本轮按 AGENTS.md 恢复 `128 KiB` 并重新执行 fresh GCC、制包、fixture 和 12 次 Startup。

## 6. 真机与项目外操作

### 6.1 授权与执行入口

用户在本会话明确授权真机预演、覆盖 `E:\P2-5-FULL.etu`，以及 SEGGER/J-Link 对
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 的可预见更新。项目内执行脚本与
原始证据位于：

- harness：`.remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1`
- 证据：`.remediation-p2-5-f4\20260809-104540\hardware-preview-r2-20260809-185928\`

最终执行命令均退出 `0`：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1" -Phase BackDiag
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1" -Phase Ui
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1" -Phase TestBoot
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1" -Phase Confirmed
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1" -Phase Finalize
```

### 6.2 真机返回/再次进入假失败的根因

真机早期诊断尝试使用 `Capture-Health -SaveRam`，在 MCU 已 halt 时执行：

```text
savebin <...>-ram.bin, 0x20000000, 0x00060000
```

该命令读取完整 `393216 B` RAM，单次暂停约 `10.43s`；原始文件时间差约 `10.8s`，
包含少量连接和写盘开销。生产 IWDG 保持 `10s`，J-Link 在读取结束后执行 `g` 时报告
`CPU is not halted`。这证明 MCU 已在暂停期间被 WDT 复位。后续编码器动作实际落在重新运行
的 Startup 或 Dialplate 上，因而被旧 harness 误判为 FirmwareUpdate 返回/再次进入失败。

历史失败证据原样保留在：

- `04-back-diagnostic-attempt1\`
- `04-back-diagnostic-attempt2\`
- `04-back-diagnostic-attempt3\`
- `04-ui-attempt2\01-enter-browser.log`

整改只修改项目内证据 harness，没有为该假失败修改产品代码：

- `Capture-Health -SaveRam` 现在直接拒绝完整 RAM 抓取。
- PageManager 与页面 vtable 每次从最终 ELF 用 `arm-none-eabi-nm` 重新解析。
- PageManager/页面对象改用短地址探测；FirmwareUpdate 只抓 rows/state 成员区 `8320 B`，
  单次约 `0.22s`。
- 任一 J-Link 日志出现 `CPU is not halted` 立即判失败。
- UI 阶段先复位，真实运行 Startup，并在操作前确认当前页为 Dialplate。

### 6.3 BackDiag 与 UI 预演结果

修正后 `BackDiag` 完成以下链路：

```text
Dialplate -> MainMenu -> FirmwareUpdate -> Browser Back -> MainMenu
-> rotate to FirmwareUpdate -> press -> FirmwareUpdate
```

最终页面管理器运行地址为 `0x200504F0`，返回后单次按压即可再次进入 FirmwareUpdate；
全程没有探针诱发 WDT、HardFault 或页面错位。

完整 UI 阶段从真实 Startup 开始，结果见 `04-ui\ui-summary.json`：

| 检查点 | 实读结果 |
|---|---|
| Startup 完成 | 当前页 `Dialplate`，vcode `20800`，BCB `CONFIRMED` |
| 首次进入文件管理 | mode `0`，rowCount `6`，ETU 路径 `/P2-5-FULL.etu` |
| Browser Back 后再次进入 | mode `0`，ETU 仍可见 |
| 第一次二次确认 | mode `1`，选择路径/文件名正确 |
| 取消 | 回到 mode `0` |
| 第二次二次确认 | mode `1` |
| Candidate Verify/导入约 70s | mode `3`，`ResultSuccess=1` |
| 结果页返回并再次进入 | mode `0`，再次进入和最终 Browser Back 均通过 |

`BrowserBackPassed`、`CancelPassed`、`ResultBackPassed`、`ReentryPassed`、
`CandidateAndStagePassed` 全部为 `true`。UI 阶段结束前仍为 v20800/`CONFIRMED`，
`SD_IsReady=1`、`VTOR=0x08010000`、`CFSR=0`；RTT 未命中 `HardFault`、WDT reset、
`RTTCMD:`、`F4TRACE` 或 `F4PROBE`。

### 6.4 OTA 启动闭环与最终状态

随后复位进入升级启动链：

- `05-test-boot\test-boot-rtt.log`：`OTA: TEST_BOOT confirmed vcode=20801`
- TEST_BOOT 后实读：vcode `20801`、BCB `CONFIRMED`、`SD_IsReady=1`、
  `VTOR=0x08010000`、`CFSR=0`
- 第二次复位 `06-confirmed-reboot\confirmed-reboot-rtt.log`：
  `OTA: BCB already CONFIRMED vcode=20801`
- 第二次复位后实读仍为 v20801/`CONFIRMED`，无 HardFault 或 WDT

本轮从最终 map/ELF 重新取得的地址为：

| 符号 | 地址 |
|---|---|
| `_SEGGER_RTT` | `0x20053E14` |
| `EncoderDiff` | `0x20053118` |
| `SD_IsReady` | `0x2005320C` |
| `g_ota_state_snapshot` | `0x20053EBC` |
| `g_ota_health` | `0x20053EC0` |
| PageManager | `0x200504F0` |

这些地址只属于本轮最终 ELF，不得被后续会话复用。

`E:\P2-5-FULL.etu` 回读结果为 `281186 B`、时间
`2026-08-09T17:35:52+08:00`、SHA-256
`C0F8862D6D3A7003F48C640028AAFF7ABE3BACD1FE9DF3A090D0FFB3F4F2D8E8`，与项目内
final-r2 ETU 一致。最终审计时无 `JLinkRTTLogger`、`JLinkGUIServer` 或模拟器残留进程。
设备当前运行 final-r2 v20801 生产固件，BCB 为 `CONFIRMED`。

## 7. 尚存风险与独立验收入口

- MCU App RAM 已到 `97.92%`，主 RAM 约余 `7488 B`。本轮模拟器和静态/宿主回归无
  LVGL heap 耗尽，且 final-r2 真机实现侧 UI/OTA 预演已通过；该余量仍需独立验收关注。
- Force 与 WM_CLOSE 对比来自旧独立 EXE和本轮 fresh EXE，不是同一字节的主动 Force A/B；
  本轮按规则不得为制造对照而强制终止健康进程。根因判定依赖“旧 harness 明确无条件
  Force + 本轮未改 Startup/Win32 产品层 + 正常生命周期 12/12”证据链。
- AC5 仍受历史缺失 `X-Track.lnp` 阻断，不能声明 AC5 生产构建通过。
- 真机预演暴露出一条验证工具约束：生产 WDT 开启时禁止 halt 后抓取完整 384 KiB RAM；
  任何状态抓取都必须短于 WDT 窗口并检查 `CPU is not halted`。
- 本轮真机结果是实现侧预演，不是独立验收。P2-5 仍为 `阻塞`，P2 仍为 `4/6`。

新的独立验收会话应从以下入口开始：

1. 阅读 `.claude\prompt-P2-5-verification.md`，不要沿用旧 RTT 地址、旧哈希或旧 SD 包。
2. 注意设备当前已是 v20801/`CONFIRMED`；独立重跑前应使用最终 Boot 与 final-r2 v20800
   baseline 恢复起点，并独立确认 vcode/BCB。
3. 使用 `.remediation-p2-5-f4\20260809-104540\artifacts\final-r2\P2-5-FULL.etu`，不得复用
   历史包或历史哈希。
4. 先 fresh 重建模拟器并复跑项目内 `sim_lifecycle_runner.ps1`，正常关闭，不得每轮 Force。
5. 独立复跑六类 fixture，人工核对标题、截断提示和按钮居中。
6. 在新会话取得明确授权后重新写入 `E:\P2-5-FULL.etu`，回读并重新计算 SHA-256。
7. 使用独立会话的最终 map 重新解析/验签 `_SEGGER_RTT`，不得沿用本报告地址；再执行
   真机文件管理和完整 OTA
   `STAGED -> APPLYING -> TEST_BOOT -> CONFIRMED`。
8. 真机探测只读必要地址或紧凑成员区，禁止 halt 后抓取完整 RAM。
9. 只有独立会话全部通过后，才可将 P2-5 改为完成并把 P2 改为 `5/6`。
