# P2-5 F4 实现整改 R4 证据（2026-08-14）

## 0. 结论与状态

本轮实现侧结论是：当前没有仍可复现的 P2-5 产品实现缺陷。此前多轮确实修过真实
缺陷，但最近反复失败的主因已经转为证据链和 harness 缺陷，而不是 OTA 功能每轮都
重新坏掉。

本报告不能代替独立验收，也不宣布 P2-5 通过：

- P2-5 继续 `阻塞`。
- P2 继续 `4/6`。
- 只有新的非实现独立验收会话可以改为 `完成` 和 `5/6`。

本轮生产源码冻结后未再修改产品实现；只修正项目内生产时序验证 runner 的未触发
重试分支，并整理独立验收入口。

## 1. 工作树与边界

- 活动 worktree：`D:\github\my\E-Track-p2-5-20260801`
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`
- 基线：`0023e5f`
- 未执行 commit、push、merge、rebase、reset、checkout 或 stash。
- 未恢复、清理或覆盖来源不明的既有改动。

开始快照原文位于：

- `.remediation-p2-5-f4\20260813-130000-r3\preflight\01-root.txt`
- `.remediation-p2-5-f4\20260813-130000-r3\preflight\02-head.txt`
- `.remediation-p2-5-f4\20260813-130000-r3\preflight\03-status.txt`
- `.remediation-p2-5-f4\20260813-130000-r3\preflight\04-diff-stat.txt`
- `.remediation-p2-5-f4\20260813-130000-r3\preflight\05-diff-check.txt`
- `.remediation-p2-5-f4\20260813-130000-r3\preflight\06-name-status.txt`

最终快照位于 `.remediation-p2-5-f4\20260813-130000-r3\closeout-r4\`。工作树包含
大量此前实现会话成果；本轮没有尝试把它们恢复成 HEAD。

最终 `git status --short --branch`：

```text
## p2-5-20260801...origin/p2-5-20260801
 M .github/workflows/firmware-build.yml
 M CMakeLists.txt
 M Libraries/OTA/ota_confirm_health.c
 M Libraries/OTA/ota_confirm_health.h
 M MDK-ARM_F435/Platform/Core/at32_sdio.c
 M MDK-ARM_F435/cmake-generated/CMakeLists.txt
 M MDK-ARM_F435/cmake-generated/compile_commands.json
 M MDK-ARM_F435/cmake-generated/do_build.bat
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
?? .claude/prompt-P2-5-verification-r2.md
?? .claude/prompt-P2-5-verification-r3.md
?? .claude/prompt-P2-5-verification.md
?? .remediation-p2-5-f4/
?? MDK-ARM_F435/cmake-generated/build-gcc-timing-r3/
?? MDK-ARM_F435/cmake-generated/build-gcc-timing-r4/
?? MDK-ARM_F435/cmake-generated/build-repro-config/
?? Microsoft/
?? Tools/provenance/
?? build-gcc-release/
?? cmake/reproducible_build.cmake
?? docs/ota-exec-notes/P2-5-F4-fix-2026-08-05.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r2.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r3.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09-r4.md
?? docs/ota-exec-notes/P2-5-F4-fix-remediation-2026-08-09.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-07.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-09-r2.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-09.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-10-r3.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-10-r4.md
?? docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-10-r5.md
?? docs/ota-exec-notes/P2-5-F4-post-acceptance-remediation-2026-08-06.md
?? docs/ota-exec-notes/P2-5-F4-review-2026-08-06.md
?? docs/ota-exec-notes/P2-5-hardware-verification-2026-08-05.md
?? flash-app.jlink
?? flash-probe.jlink
?? tests/ota/test_p2_5_build_provenance.py
?? tests/ota/test_sdio_command_timeouts.py
```

相对基线 `0023e5f` 的 tracked `git diff --name-status`：

```text
M	.github/workflows/firmware-build.yml
M	CMakeLists.txt
M	Libraries/OTA/ota_confirm_health.c
M	Libraries/OTA/ota_confirm_health.h
M	MDK-ARM_F435/Platform/Core/at32_sdio.c
M	MDK-ARM_F435/cmake-generated/CMakeLists.txt
M	MDK-ARM_F435/cmake-generated/compile_commands.json
M	MDK-ARM_F435/cmake-generated/do_build.bat
M	PLAN-OTA-EXEC.md
M	Simulator/LVGL.Simulator/HAL/HAL_Encoder.cpp
M	Simulator/LVGL.Simulator/lv_conf.h
M	Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c
M	Tools/jlink/jlink-common.ps1
M	USER/App/Config/Config.h
M	USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp
M	USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h
M	USER/App/Pages/Menu/MainMenu.cpp
M	USER/HAL/HAL_EEPROM.cpp
M	USER/HAL/HAL_OTA_Package.cpp
M	tests/ota/test_ota_confirm_health.c
```

## 2. 为什么此前一直“修复、测试、再失败”

历史问题分为两类，之前没有始终严格分开：

| 类别 | 已定位问题 | 处理结果 |
|---|---|---|
| 产品实现 | 确认后停止喂狗 | 已把喂狗门移出 TEST_BOOT 状态分支，并有编排回归 |
| 产品实现 | 目录过滤项不消耗扫描上限 | 已引入独立扫描上限和边界 fixture |
| 产品实现 | MainMenu 与 FirmwareUpdate 同驻导致 LVGL heap 耗尽 | 已改为按需 UI、页面缓存释放和安全生命周期 |
| 产品实现 | LVGL 回调内同步清理造成重入/UAF | 已改为异步清理/Pop |
| 产品实现 | 软件复位打断 SDIO 后响应等待可能永久自旋 | 9 条路径已改为有界等待，并增加 timeout 回归 |
| 验证工具 | 模拟器每轮无条件 `Stop-Process -Force` | 改为 `WM_CLOSE` 正常退出和残留检查 |
| 验证工具 | 时序引用历史插桩固件 | 改为最终生产 ELF 的 FPB 断点和 DWT CYCCNT |
| 验证工具 | 汇总字段无条件写 PASS | 禁止常量结果，要求原始状态和证据路径 |
| 验证工具 | 旧 J-Link 大块 `savebin` 随机伪差异 | 改为 16 KiB、每块独立 J-Link 会话 |
| 验证工具 | 固定 `ClrBP 1`，但后续句柄为 2/3/4 | 按实际断点句柄清除 |

因此，前半段确实存在产品缺陷；后半段多次“不通过”主要是验收证据不充分或 harness
自身产生假失败。继续在每个 harness 失败后无条件重跑 11 组宿主和全量构建是低效的，
也不会提高结论可信度。

本轮采用的新规则是：先绑定冻结源码和最终产物，再修验证工具；只有生产源码或绑定
哈希变化时才重跑全量回归。

## 3. Startup 重复启动

最终生产模拟器：

- 路径：`Simulator\Output\Debug\x64\LVGL.Simulator.exe`
- 大小：`5879296 B`
- 时间：`2026-08-13T08:30:52.4557675+08:00`
- SHA-256：`4CD9DD61DF1FF3BA12B7A0887C9049B4997480369DE78F3899E73CCCFE4A0596`
- 构建：`102 warning / 0 error`

生产入口仍为 `manager.Push("Pages/Startup")`，Startup 真实 timeline 未禁用，模拟器文件
系统仍使用正常生产路径。

正确生命周期连续测试：

| 轮次 | 结果 | 进入主界面 | 主界面观察 | WM_CLOSE 退出 | Responding/Hung | 残留 |
|---:|---|---:|---:|---:|---|---:|
| 1 | PASS | 6369 ms | 10 s | 207 ms | true/false | 0 |
| 2 | PASS | 4776 ms | 10 s | 135 ms | true/false | 0 |
| 3 | PASS | 4866 ms | 10 s | 93 ms | true/false | 0 |
| 4 | PASS | 4833 ms | 10 s | 87 ms | true/false | 0 |
| 5 | PASS | 4743 ms | 10 s | 176 ms | true/false | 0 |
| 6 | PASS | 5079 ms | 10 s | 688 ms | true/false | 0 |
| 7 | PASS | 5424 ms | 10 s | 678 ms | true/false | 0 |
| 8 | PASS | 4731 ms | 10 s | 111 ms | true/false | 0 |
| 9 | PASS | 5450 ms | 10 s | 95 ms | true/false | 0 |
| 10 | PASS | 4671 ms | 10 s | 223 ms | true/false | 0 |
| 11 | PASS | 4866 ms | 10 s | 536 ms | true/false | 0 |
| 12 | PASS | 5012 ms | 10 s | 196 ms | true/false | 0 |

原始结果和逐轮截图位于：

- `.remediation-p2-5-f4\20260813-130000-r3\simulator\startup-12\logs\results.json`
- `.remediation-p2-5-f4\20260813-130000-r3\simulator\startup-12\screenshots\`

Force 对照 4 轮在终止前也均 `Responding=true/Hung=false`，终止后残留为 0。该对照只
证明强制终止不是正常生命周期证据，不能用来给下一轮启动判定 PASS/FAIL。旧验收的
交替失败来自无条件 Force 的错误 harness 生命周期，不需要为此投机修改 Startup 产品层。

## 4. FirmwareUpdate 回归

六类模拟器 fixture 全部退出码 0、`STATUS=PASS`、残留 0：

- 截断根目录。
- ROW_MAX 边界。
- 恰好 256 项。
- 只有 `..`。
- ETU 选择和二次确认。
- Candidate Verify、取消、结果返回和再次进入完整流。

原始汇总：

- `.remediation-p2-5-f4\20260813-130000-r3\simulator\f4-runs\summary-pwsh7.json`
- `.remediation-p2-5-f4\20260813-130000-r3\f4\summary.json`

实现侧先前两次同步人工观察均记录为：`CANDIDATE VERIFY`、`BACKUP + STAGED`、成功
结果页出现，且无黑屏、重启或文字残缺。该观察只能作为实现侧预演输入，不能替代新
独立验收的照片、录像或当轮明确观察记录。

## 5. 最终生产固件时序

### 5.1 绑定和方法

时序不再引用历史 `307.497 ms`、`817 ms` 或 `917 ms` 插桩数据。Attempt 4 使用：

- 最终无插桩 v20800 App：`598828 B / 16D27D43...D72E58`
- 最终生产 ELF：`859836 B / 63D09478...F1800`
- 最终生产 map：`2233460 B / 9036B272...66EA5`
- 最终生产 Boot：`14724 B / 5842FF3E...4F6594`
- 方法：最终生产 ELF 硬件 FPB 断点 + DWT CYCCNT，不修改 Flash。

生产源码冻结清单在时序后保持：

- 文件数：`2945`
- manifest SHA-256：`17AD13C4FEDB585A0F0134BF26A527E47A24CAB2F602DF7D5EC32C6D32887C41`
- before/after：`0 mismatch`

2026-08-14 又逐项重算当前树中全部 2945 个文件：`Missing=0 / Mismatch=0 / PASS`。

### 5.2 Attempt 4 结果

| 轮次 | 根目录 LoadFiles | 页面到列表 | 含 100 ms 输入轮询上界 | /F4ACC LoadFiles | 结果 |
|---:|---:|---:|---:|---:|---|
| 1 | 36.569 ms | 810.690 ms | 910.690 ms | 47.136 ms | PASS |
| 2 | 36.577 ms | 810.740 ms | 910.740 ms | 47.102 ms | PASS |
| 3 | 36.565 ms | 810.707 ms | 910.707 ms | 47.079 ms | PASS |

门禁：

- `LoadFiles <= 320 ms`
- `/F4ACC LoadFiles <= 320 ms`
- `input-to-list upper <= 917 ms`

最坏值为 `36.577 ms / 47.136 ms / 910.740 ms`，全部通过。

初始和最终 Flash 校验均为 Boot 1 块 + App 37 块，共 38 块；所有块首读直接与生产
镜像一致，`RecoveredTransientReadCount=0`。最终状态为：

- `vcode=20800`
- BCB `CONFIRMED`
- `SDReady=1`
- `VTOR=0x08010000`
- `CFSR=0x00000000`
- 当前页为 Dialplate
- DWT 控制寄存器已恢复

原始证据：

- `.remediation-p2-5-f4\20260813-130000-r3\production-timing-r1\hardware\attempt-04\summary.json`
- `.remediation-p2-5-f4\20260813-130000-r3\production-timing-r1\hardware\attempt-04\05-repetition-01\root-production-dwt.log`
- `.remediation-p2-5-f4\20260813-130000-r3\production-timing-r1\hardware\attempt-04\05-repetition-02\root-production-dwt.log`
- `.remediation-p2-5-f4\20260813-130000-r3\production-timing-r1\hardware\attempt-04\05-repetition-03\root-production-dwt.log`

Attempt 3 的失败不是产品崩溃，而是 runner 固定执行 `ClrBP 1`，后续实际句柄为
`2/3/4`。Attempt 4 已按实际句柄清除。

### 5.3 Flash 重试策略修正

Attempt 4 运行后审计发现 runner 的未触发分支仍有缺陷：当首读失败时，旧逻辑把首读
也纳入“全部读取必须一致”，使瞬态首读永远无法恢复为 PASS。

现已固定为：

1. 首读一致立即通过，不做复读。
2. 首读不一致时再开两个独立 J-Link 会话。
3. 只有 retry 2 和 retry 3 都与生产镜像一致才通过。

已通过 PowerShell AST、静态规则和 5 项真值表测试。Attempt 4 的 76 个校验块全部首读
一致，因此该旧分支没有被执行，修正不改变 Attempt 4 的时序或 Flash 结论，也没有理由
为此再跑同一轮真机测试。

## 6. 回归和构建

冻结生产源码对应的宿主测试均退出码 0：

| # | 命令 | 退出码 |
|---:|---|---:|
| 1 | `python tests/boot/test_fw_header_vectors.py` | 0 |
| 2 | `python tests/boot/test_boot_protocols.py` | 0 |
| 3 | `python tests/boot/test_boot_state_machine.py` | 0 |
| 4 | `python tests/boot/test_p1_6_protocol.py` | 0 |
| 5 | `python tests/ota-vectors/test_vectors.py` | 0 |
| 6 | `python tests/ota/test_ota_staging.py` | 0 |
| 7 | `python tests/ota/test_ota_package.py` | 0 |
| 8 | `python tests/ota/test_ota_patch.py` | 0 |
| 9 | `python tests/ota/test_ota_sd.py` | 0 |
| 10 | `python tests/ota/test_ota_update.py` | 0 |
| 11 | `python tests/ota/test_ota_backup.py` | 0 |
| 12 | `python tests/ota/test_sdio_command_timeouts.py` | 0 |

注意：部分测试输出包含预期负向场景的 `FAIL` 字样，不能用字符串计数代替退出码；原始
日志和每项退出码在 `.remediation-p2-5-f4\20260813-130000-r3\host-tests\`。

专项结果：

- F4 专项 harness：编译 0、运行 0。
- TEST_BOOT 下 Begin/Apply 门禁：`OTA_TEST_BOOT_GATE_HARNESS=PASS`。
- 六类模拟器 fixture：`6/6 PASS`。

构建结果：

| 构建 | 退出码 | warning | error | 说明 |
|---|---:|---:|---:|---|
| fresh GCC Release App/Boot | 0 | 634 | 0 | post-timing 与冻结基线逐字节一致 |
| fresh 模拟器 | 0 | 102 | 0 | 最终 EXE 如 §3 |
| AC5 正式尝试 | 1 | 0 matches | 0 matches | 历史缺失 `Objects\X-Track.lnp`，未注入 `--cpp11` |

本轮仅修改证据 runner 和文档，生产源码 manifest 仍为 `2945/2945` 一致，因此没有再次
执行上述全量测试和构建。重复执行不会覆盖新的产品风险，只会浪费时间。

## 7. 最终产物

| 产物 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| v20800 App | 598828 B | 2026-08-13T20:14:31.6268048+08:00 | `16D27D43A87BB5FBC205F37B98F1AF2C75EA7CD18F669071FB9FD280B8D72E58` |
| v20801 App | 598828 B | 2026-08-13T20:14:32.2127177+08:00 | `142D4D80B4FDAF8BC26E195871B9D7E42460E70895324F8CBFB501AC2DD8A1AE` |
| Boot | 14724 B | 2026-08-13T20:01:57.8578801+08:00 | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| 模拟器 | 5879296 B | 2026-08-13T08:30:52.4557675+08:00 | `4CD9DD61DF1FF3BA12B7A0887C9049B4997480369DE78F3899E73CCCFE4A0596` |
| P2-5-FULL.etu | 281291 B | 2026-08-13T20:14:33.5755454+08:00 | `5D7C388F7448896F8F67FF8B33E6380E48467235520FBE61891BA52A7B3F814E` |
| 解包 candidate | 598828 B | 2026-08-13T20:14:33.9812661+08:00 | `142D4D80B4FDAF8BC26E195871B9D7E42460E70895324F8CBFB501AC2DD8A1AE` |

candidate 与 v20801 App 逐字节一致。`E:\P2-5-FULL.etu` 已在此前本会话明确授权范围
内覆盖并回读，大小和 SHA-256 与上表 ETU 一致；证据为
`.remediation-p2-5-f4\20260813-130000-r3\post-timing\sd-write\summary.json`。

## 8. 最终生产清理

最终检查项：

- App 生产入口为 `Pages/Startup`。
- Startup 真实动画 timeline 保留。
- 模拟器文件系统使用正常生产路径。
- `CONFIG_RTT_DEBUG_CMD_ENABLE=0`。
- 最终 App、Boot、candidate、ETU 和模拟器无 `F4TRACE`、`F4PROBE`、`RTTCMD:`、
  `F4TIMING` 或 `F4METRIC`。
- WDT 未关闭，`CONFIG_WATCH_DOG_TIMEOUT=(10 * 1000)` 未放宽。
- `LV_MEM_SIZE=(128U * 1024U)`。
- `USER/main.cpp` 的确认后持续喂狗机制未破坏。
- `FirmwareUpdate.cpp`、`FirmwareUpdate.h`、`PLAN-OTA-EXEC.md` 为 UTF-8 无 BOM。
- 指定源码 include 使用正斜杠。
- `git diff --check=0`。
- 无残留 `LVGL.Simulator`、`JLinkRTTLogger` 或 `JLinkGUIServer` 进程。

SEGGER 全局 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 在 Attempt 4 前后均为
`986 B / DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`，未变化。

## 9. 真机实现侧结果与剩余独立验收

本轮已在最终 v20800 生产固件上完成 3 次根目录和 3 次 `/F4ACC` 生产时序，且最终
保持 `v20800 / CONFIRMED / Dialplate / SDReady=1 / CFSR=0`。Attempt 4 没有执行 OTA，
也没有伪造视觉字段：`VisualOtaEvidence="Not executed; reserved for independent acceptance"`。

实现侧没有必要再重复全量宿主、构建或模拟器测试。新的独立验收只需：

1. 核对当前 2945 文件 manifest 和上表产物哈希未变化。
2. 使用修正后的 runner 独立执行一次 3 轮生产时序，确认门禁。
3. 在开始 OTA 前明确提醒用户开始观察，并保存当轮真机照片、录像或逐项人工记录。
4. 完成一次当前 ETU 的 `CANDIDATE VERIFY`、`BACKUP + STAGED`、成功结果页、重启、
   `TEST_BOOT confirmed vcode=20801` 和二次启动 `BCB already CONFIRMED vcode=20801`。
5. 检查取消、返回、再次进入、标题、完整截断提示和按钮居中。

若 manifest 或产物哈希变化，才触发相应构建和回归；不得无条件再跑一遍全部内容。

新的唯一入口：`.claude\prompt-P2-5-verification-r3.md`。

P2-5 继续 `阻塞`，P2 继续 `4/6`，等待新的非实现独立验收会话。
