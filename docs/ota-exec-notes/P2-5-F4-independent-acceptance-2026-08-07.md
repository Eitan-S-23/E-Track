# P2-5 F4 整改后独立验收报告（2026-08-07）

## 0. 结论

**F4 整改通过；P2-5 整体验收不通过，状态保持“阻塞”，P2 保持 `4/6`。**

最终无插桩 GCC 生产固件已能稳定进入文件管理页，根目录 `.etu` 可见并可进入
`2.8.0 -> 2.8.1` 二次确认；`F4ACC` 301 项目录正确显示截断提示。真实页面内部加载
两次独立 trace 均为 `817 ms`，含 100 ms 输入轮询的上界为 `917 ms`，最终生产固件
人工观测约 1 秒多。唯一 logger 连续连接约 295 秒期间设备无重启，随后实读
`PC=0x08043056`、`VTOR=0x08010000`、`CFSR=0`，F4 原阻断已关闭。

P2-5 的新决定性失败发生在选择 fresh `P2-5-FULL.etu` 并开始导入后：UI 出现
`CANDIDATE VERIFY`，随后黑屏并重启。重启后 RTT 明确记录：

```text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 ...
Reset: NRST WDT
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20800
```

原始日志：
`.acceptance-p2-5-f4/20260807-191534/hardware/06-ota-failure/rtt-post-candidate-verify-reset.log`，
287 B，SHA-256
`FC408B70B4C05AD55155B7909E9192F0D8F84C3E157D06D68CBE5F2004B738B7`。

失败后 RAM/Flash 实读仍为 BCB `CONFIRMED(4)`、vcode `20800`、`SD_IsReady=1`、
VTOR `0x08010000`、CFSR `0`。`BACKUP + STAGED` 未到达，版本没有跃迁。按 fail-fast
规则停止，不继续尝试 APPLYING、TEST_BOOT、CONFIRMED 或第二次复位。

另记录两个 UI 布局缺陷：主内容框遮挡顶部“文件管理”标题下部；“返回”和
“开始导入”按钮文字偏左上，未水平/垂直居中。它们不是本轮 WDT 的判定依据，但应随
实现整改处理。

## 1. 独立性与证据范围

- 验收角色：Codex，非实现会话。
- 活动 worktree：`D:\github\my\E-Track-p2-5-20260801`。
- F4 实现前基线：`0023e5f`。
- HEAD：`0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e`。
- 本轮证据目录：`.acceptance-p2-5-f4/20260807-191534/`。
- 未修改实现源码，未执行 commit、push、merge、rebase 或 stash。
- 仅修改本报告和 `PLAN-OTA-EXEC.md` 的验收状态/日志。
- 用户明确授权覆盖 `E:\P2-5-FULL.etu`；未删除或改写 SD 上其他条目。
- 用户明确授权 SEGGER 本轮自动维护
  `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。

## 2. 验收前快照与改动清单

| 命令 | 退出码 | 结果 |
|---|---:|---|
| `git rev-parse --show-toplevel` | 0 | `D:/github/my/E-Track-p2-5-20260801` |
| `git rev-parse HEAD` | 0 | `0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e` |
| `git status --short --branch` | 0 | 工作树非干净，完整状态见 `01-preflight-snapshot.log` |
| `git diff --stat 0023e5f` | 0 | 已落盘，未把生成文件描述为“工作树干净” |
| `git diff --check` | 0 | 无错误 |

相对 `0023e5f` 的 7 个 tracked 改动文件：

1. `MDK-ARM_F435/cmake-generated/compile_commands.json`
2. `PLAN-OTA-EXEC.md`
3. `Simulator/LVGL.Simulator/lv_fs_if/lv_fs_pc.c`
4. `USER/App/Config.h`
5. `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp`
6. `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.h`
7. `USER/App/Pages/Menu/MainMenu.cpp`

实现证据文件清单与上述源码改动逐项核对一致。`compile_commands.json` 为生成文件但
确有状态，`RTE_Components.h` 已恢复无 diff。

最终 `git status` 还列出以下 4 个 `.M` 路径，但 `git diff HEAD -- <path>`、
`--numstat` 和 `--shortstat` 均为空，仅出现 LF 将在 Git 下次触碰时转 CRLF 的提示；
未把这些状态隐藏为“工作树干净”，也未擅自还原：

1. `Tools/jlink/jlink-common.ps1`
2. `USER/App/App.cpp`
3. `USER/App/Utils/OtaUpdate/OtaUpdate.cpp`
4. `USER/lv_port/lv_port_indev.cpp`

原始证据见
`01-preflight-snapshot.log`、`02-complete-file-list.log` 和
`04-remediation-evidence-audit.log`。

## 3. 生产清理复核

| 检查项 | 结果 | 证据 |
|---|---|---|
| App 生产入口为 `manager.Push("Pages/Startup")` | 通过 | `03-production-cleanup.log` |
| 模拟器 PC 文件系统恢复正常 `.` 路径 | 通过 | `03-production-cleanup.log` |
| 无 `F4PROBE`、`F4TRACE`、临时 RTT 计时输出 | 通过 | 源码、ELF、bin 字符串审计 |
| 无临时页面直达、测试 harness 或验收编译开关 | 通过 | Startup 与编译标记审计 |
| 生产 RTT 下行命令整体移除 | 通过 | `CONFIG_RTT_DEBUG_CMD_ENABLE=0`；无 `RTTCMD:`/`RttDebugCmd_Poll` |
| `FirmwareUpdate.cpp/.h`、`PLAN-OTA-EXEC.md` UTF-8 无 BOM | 通过 | 首字节审计 |
| `USER/main.cpp` F1 喂狗修复未变 | 通过 | 相对基线无 diff |
| 看门狗未关闭，超时仍为 10000 ms | 通过 | 配置审计 |
| 冻结契约未被 F4 修改 | 通过 | `PLAN-OTA.md`、`docs/ota-binary-contracts.md` 零 diff |
| 源码 include 使用正斜杠 | 通过 | 源码审计 |
| `git diff --check` | 通过 | rc=0 |

## 4. F4 专项复核

### 4.1 Harness 与模拟器边界

独立 F4 harness 退出码 0：

```text
MIXED scan=256 rows=0 reads=257 more=1
ROWMAX rows=24 reads=25 more=1
EXACT_SCAN scan=256 reads=257 more=0
DEVICE_PRIORITY message=4
F4_SCAN_HARNESS=PASS
```

五类模拟器 fixture 均通过：

| 场景 | 结果 |
|---|---|
| 隐藏、非 ETU、路径过长均消耗扫描上限 | 通过 |
| 大量非 ETU 且 ETU 位于上限之后 | 显示截断，不误报“未找到 ETU” |
| `ROW_MAX` 满且仍有条目 | 显示截断 |
| 仅 `..` 返回项 | 截断提示仍有效 |
| 恰好 256 项 | 不误报截断 |
| 小目录 ETU | 可列出并进入 `2.7.0 -> 2.8.1` 确认页 |
| `deviceReady=false` | 设备错误保持最高优先级 |

最终有效截图使用按窗口标题枚举得到的真实 LVGL 小窗口，不采用早期固定句柄误截结果。
关键证据：`simulator/26-*.png`、`simulator/27-only-up-inside.png`。

### 4.2 量化独立复算

| 指标 | 结果 |
|---|---:|
| 单次 `lv_fs_dir_read` 平均 / 最坏 | 136 us / 378 us |
| 修复后根目录 `LoadFiles()` | 44.941 ms |
| 96 项目录完整 / 修复路径 | 4.157 ms / 4.153 ms |
| 96 项目录单次读取平均 / 最坏 | 29 us / 313 us |
| 257 次最坏外推 | 97.660 ms |
| 扫描 + 24 行 UI 保守值 | 307.497 ms |
| 每 32 项喂狗最坏间隔 | 12.160 ms |
| 相对 10000 ms IWDG 裕度 | 9987.840 ms，约 822.37x |

最终修复 trace 的首次进入和返回后二次进入均为：

```text
device ready=1 dt=754
ui dt=763/764
files rows=6 dt=817
```

两份原始日志 SHA 分别为
`75392FA849E374E217AA175E9C8DF3F6CC27E278CF7A1D7CA388A8AE2230B82B` 和
`DF7E2973A2D540790FCB0A0B2DAE86A31C9463F5FE5FE3FA2EE5BEB8E68D7129`。
RTT 输入轮询周期为 100 ms，因此注入点击到列表完成的严格上界约 `917 ms`。
独立复算见 `hardware/03-f4-ui/03-trace-latency-independent-recalc.log`。

### 4.3 最终生产固件真机 F4

- 用户实测点击“文件管理”到浏览器显示约 1 秒多，存在人工计时误差，与 `817/917 ms`
  量化一致。
- 根目录 `.etu` 可见，根目录没有截断误报。
- `F4ACC` 显示截断提示；可见片段为
  `ORE FILES EXIST,NOT ALL SHOW`，虽左右裁切但仍明确表达“仍有文件、未全部显示”。
- 单个 RTT logger 从 21:37:01 至 21:41:56 连续连接，stdout 明确显示已找到当前
  RTT control block，295 秒期间数据 0 B；设备由用户持续操作且无重启。
- 操作后实读 `PC=0x08043056`、`VTOR=0x08010000`、`CFSR=0`、
  BCB `CONFIRMED`、`SD_IsReady=1`。
- 根目录 fresh `.etu` 可选择，二次确认显示 `2.8.0 -> 2.8.1`。

结论：F4 的静默截断、错误空目录提示、WDT/HardFault 和不可接受冻结均已关闭。
截断文案边缘裁切记为非阻断显示缺陷。

## 5. 宿主回归与 TEST_BOOT 门禁

11 组正式命令退出码均为 0：

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
| P2-5 backup / confirm health | 108/108 + 17/17 |

汇总见 `07-host-tests-summary.log`。

TEST_BOOT 新 OTA 门禁采用生产等价 harness 验证：`Begin()` 与 `Apply()` 在非
CONFIRMED 状态均拒绝，`Apply()` 的 `opens_before=2210`、`opens_after=2210`，
无额外打开副作用。证据见 `06-apply-gate-harness.log`。

## 6. Fresh 构建与模拟器

### 6.1 GCC Release App/Boot

正式命令必须从 `MDK-ARM_F435/cmake-generated` 执行：

```powershell
.\do_build.bat release rebuild
```

退出码 0；1249 行 `warning:`、3 个 CMake warning、0 error。warning 未粉饰。

| 产物 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| `app-gcc/X-Track-App-GCC.bin` | 598392 B | 2026-08-07 19:52:47 | `2BBECE85ADD70231425637BCD474DBADBC14A16836B8AA9B4759EC98A07AB25C` |
| `app-gcc/X-Track-App-GCC.elf` | 859680 B | 2026-08-07 19:52:47 | `4CB5611B967D6C20BF985C1E04964AB503C5E59FF7234B5AAF6784DE377AA8A7` |
| `app-gcc/X-Track-App-GCC.map` | 2232628 B | 2026-08-07 19:52:47 | `38B52DABB9657077D976B429DBA67A312F24535A79EA90D72481B25D3E7A2749` |
| `boot/X-Track-Boot.bin` | 14724 B | 2026-08-07 19:52:42 | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| `boot/X-Track-Boot.elf` | 36860 B | 2026-08-07 19:52:42 | `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC` |
| `boot/X-Track-Boot.map` | 94509 B | 2026-08-07 19:52:42 | `FE98B12262515BA173921044F8FD227D0D2429E5D13948ED1275E8DB655C207E` |

Boot 小于 64 KiB；3 个 LOAD segment，无 RWX。最终 App ELF/bin 中
`F4TRACE/F4PROBE/RTTCMD:/RttDebugCmd_Poll` 均为 0。

一次从仓库根错误调用 cwd-sensitive `do_build.bat`，更新了验收前已存在的根级
`build-gcc-release/` 并以 4 error 失败；该结果未用作正式构建且未擅自清理目录。
正式证据为 `build/12-fresh-gcc-app-boot-build-correct.log` 和
`build/15-fresh-gcc-artifact-audit.log`。

### 6.2 AC5

按 AGENTS.md 正式调用 `build_f435.ps1 -AutoStale`，退出码 1，原因是历史
`MDK-ARM_F435/Objects/X-Track.lnp` 缺失。未向脚本注入 `--cpp11`。证据：
`build/16-ac5-build-attempt.log`。

### 6.3 模拟器

MSBuild fresh rebuild 退出码 0，102 warning、0 error。最终 EXE：

```text
Simulator/Output/Debug/x64/LVGL.Simulator.exe
size=5877248
sha256=8F5D770F43FA004096D5EADEE7EC7412C3C78222F3FA9C4ADEE9A7A60569F815
```

连续两次真实 Startup 均 `Responding=True`、`Hung=False` 并进入仪表盘。

## 7. 最终包与 SD 一致性

本轮未复用实现会话旧包，而是从本轮 fresh raw App 重新生成：

| 资产 | 大小 | SHA-256 / vcode |
|---|---:|---|
| raw App | 598392 B | `2BBECE85ADD70231425637BCD474DBADBC14A16836B8AA9B4759EC98A07AB25C` |
| v20800 finalized App | 598392 B | `0A35BA40B54C93D7AE504EED117D3391798F8EA1199DDBF5DCA4BFC83001BC3C` |
| v20801 finalized App | 598392 B | `799DFDD1A736F184EB5BC5C3A15A9851FB2600E485B704154832FE7EAAAF501A` |
| fresh `P2-5-FULL.etu` | 281051 B | `49CB3AE2212F67D87B8AA8C0E332C4B1AACDFBD8132A1216CBDD89B4C383C0E7` |
| unpack candidate | 598392 B | `799DFDD1A736F184EB5BC5C3A15A9851FB2600E485B704154832FE7EAAAF501A` |

- baseline vcode `20800`，target vcode `20801`，满足目标大于基线。
- candidate 与 v20801 finalized App 逐字节一致。
- SD 写入前旧包为 281272 B、SHA `B86BE8AD...F42694`，已只读归档至项目证据。
- 仅覆盖 `E:\P2-5-FULL.etu`；写后回读 281051 B、SHA `49CB...C0E7`，字节一致。
- 再从 `E:` 直接解包得到 target vcode `20801` 和 candidate SHA `799D...501A`。
- SD 根目录实际 9 项，完整清单见 `hardware/04-sd-media/01-sd-package-write-readback.log`。
- `E:\F4ACC` 实际 301 项：隐藏 `.etu` 100、非 `.etu` 100、超长路径 `.etu`
  100，`zzzz-after-limit.etu` 为第 301 项，明确位于 `SCAN_MAX=256` 之后。

## 8. 真机基线与 RTT

使用 fresh Boot 和本轮 v20800 finalized App 建立同源基线。第一次 J-Link 连接因瞬时
`Failed to initialized DAP` 退出 1，未开始烧录；完全相同的 1000 kHz 命令重试
成功，Boot/App 各一次 `Verify successful`。

fresh map 严格解析：

```text
0x20045e14                _SEGGER_RTT
```

`mem8 0x20045E14 16` 实读 `53 45 47 47 45 52 20 52 54 54`，签名通过。

基线实读：

```text
flash 0x08010408 = 0x00005140  # vcode 20800
RAM   0x20045EBC = 04 01 01 00 # CONFIRMED
RAM   0x2004520C = 01          # SD ready
VTOR  = 0x08010000
CFSR  = 0x00000000
```

段 A RTT 为 286 B，SHA
`A266CBF3756F12F49D8D5B63037298E62E7AD928AD960B4D1FE33AC15BB81FB8`，包含
`HANDOFF`、`Reset: NRST SW` 和 `BCB already CONFIRMED vcode=20800`，无 WDT、
无 HardFault。

## 9. P2-5 阻断复现

### 9.1 精确步骤

1. 烧录并验证本轮 fresh Boot + v20800 finalized App。
2. 确认 BCB=CONFIRMED、vcode=20800、SD ready、VTOR/CFSR 正常。
3. 将本轮 fresh `P2-5-FULL.etu` 写入 SD 根目录并直接从 SD 解包回读。
4. 物理编码器进入文件管理，确认 fresh `.etu` 可见。
5. 选择包，确认页显示当前 `2.8.0`、目标 `2.8.1`。
6. 点击开始导入，UI 出现 `CANDIDATE VERIFY`。
7. 随后设备黑屏并重启；`BACKUP + STAGED` 未出现。
8. 新 RTT 采集显示 `Reset: NRST WDT`，BCB 仍 CONFIRMED v20800。

### 9.2 失败证据

| 项目 | 结果 |
|---|---|
| RTT 地址 | `0x20045E14`，fresh map 重取并验签 |
| 失败阶段 | `CANDIDATE VERIFY` |
| 复位原因 | `Reset: NRST WDT` |
| RTT 日志 | 287 B，SHA `FC408B70...4B738B7` |
| 重启后 BCB | `CONFIRMED(4)` |
| 重启后 vcode | `20800` |
| 重启后 SD | ready=1 |
| 重启后 VTOR/CFSR | `0x08010000` / `0` |

日志字节及 SHA 与 2026-08-05 F4 WDT 日志相同，但本轮触发点不同：F4 文件浏览已
稳定通过，本次在 candidate 校验阶段触发。不得据相同 reset 文本沿用旧根因，需由
实现会话针对 candidate verify 调用链重新定位。

## 10. 未执行项

以下项目因 candidate verify WDT 触发 fail-fast 而未执行：

- `BACKUP + STAGED` 完成与成功结果页。
- 重启后的 STAGED -> APPLYING -> TEST_BOOT。
- 至少 90 秒 TEST_BOOT RTT。
- `OTA: TEST_BOOT confirmed vcode=20801`。
- 第二次普通复位后的 `OTA: BCB already CONFIRMED vcode=20801`。
- 升级后屏幕、按键和基本页面功能检查。

TEST_BOOT 新 OTA 门禁已有生产等价 Begin/Apply harness 通过，但不能替代未到达的真机
状态链。

## 11. 最终矩阵

| 条件 | 结果 |
|---|---|
| F4 两个阻断和四项整改关闭 | 通过 |
| 临时插桩、页面直达、模拟器测试路径清理 | 通过 |
| F4 边界无静默截断/错误空提示 | 通过 |
| 文件管理无 WDT/HardFault且保持响应 | 通过 |
| 文件管理耗时可接受 | 通过，817 ms；端到端上界 917 ms；人工约 1 秒多 |
| 全部宿主回归无回退 | 通过 |
| fresh GCC App/Boot | 通过，有 warning、0 error |
| AC5 正式尝试 | 未完成，历史 `.lnp` 缺失 |
| 模拟器重建和两次 Startup | 通过 |
| SD 包、candidate、final App 一致 | 通过 |
| CANDIDATE VERIFY | **失败，触发 WDT** |
| BACKUP + STAGED | 未到达 |
| STAGED -> APPLYING -> TEST_BOOT -> CONFIRMED | 未到达 |
| 最终 vcode=20801 | **失败，仍为 20800** |
| 第二次复位仍 CONFIRMED | 未执行 |
| TEST_BOOT 新 OTA 门禁 | 通过（生产等价 harness） |

最终状态：**P2-5 阻塞，P2 维持 `4/6`。**

## 12. 文件系统与进程审计

- 本轮主动项目内输出均位于
  `.acceptance-p2-5-f4/20260807-191534/`、本报告或 `PLAN-OTA-EXEC.md`。
- 用户授权的项目外写入仅为 `E:\P2-5-FULL.etu` 覆盖；未改写 `F4ACC` 或其他条目。
- SEGGER 自动维护的 `JLinkDLL.ini` 为 859 B，SHA-256
  `D4FB1AD31E202D8C54307F664B5AA8EE08121252A04D5A7ACACFA60D6239E4B9`，最终时间戳
  `2026-08-07 22:17:27.838 +08:00`；内容未由验收会话手工编辑。
- 一次 UI RTT helper 在用户交互期间失去 exec cell，但只留下一个独占 logger；
  stdout 证明连接正常，发现后立即清理，未并发抢读。该窗口只与用户目视和后续
  PC/VTOR/CFSR 实读组合使用，不以“0 B 日志”单独判定通过。
- 最终 `JLinkRTTLogger`、`JLinkRTTViewer`、`JLinkGUIServer`、`JLink`、
  `LVGL.Simulator` 残留进程均为 0；最终收尾审计见本轮 evidence。
- 未执行 commit、push、merge、rebase 或 stash。
