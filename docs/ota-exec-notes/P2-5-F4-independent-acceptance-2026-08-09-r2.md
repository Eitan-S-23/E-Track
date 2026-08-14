# P2-5 F4 整改后独立验收报告 R2（2026-08-10）

## 0. 结论

本轮独立验收不通过。P2-5 必须保持“阻塞”，P2 总进度必须保持 4/6。

本轮生产模拟器、F4 语义 harness/fixture、11 组宿主回归、TEST_BOOT 门禁、fresh GCC App/Boot、finalize/封包/解包、SD 回读、P1-6 CLEAR_BCB、fresh RTT 验签和真机状态迁移证据大部分有效。但两项强制量化门禁没有使用本轮最终无插桩生产固件重新测量：`307.497 ms` 来自 2026-08-06 的 `F4PROBE/F4METRIC` 插桩日志，`817/917 ms` 来自 2026-08-07 的 `F4TRACE/RTTCMD:` 插桩固件。后者实测镜像为 `600820 B`、SHA-256 `5153E656...8FB3A12F`，与本轮 finalized v20800 App `598836 B`、SHA-256 `66EC8DD2...4E679D3` 明确不同。

此外，真机硬件目录没有任何屏幕图片；复用的实现侧 `hardware_preview_r2.ps1` 在汇总阶段无条件写入 `CandidateAndStagePassed = $true`。RAM 状态和后续 RTT 能证明导入完成及 OTA 状态迁移，但不能独立留证屏幕确实出现指定文字 `CANDIDATE VERIFY` 和 `BACKUP + STAGED`。由于“只有全部条件通过”才允许完成，本轮按 fail-fast 判定不通过。

仍可独立确认的真机状态链为：

~~~text
v20800 / CONFIRMED
  -> 文件管理、二次确认及导入完成状态
  -> 重启并应用
  -> TEST_BOOT confirmed vcode=20801
  -> 普通复位
  -> BCB already CONFIRMED vcode=20801
~~~

最终设备实读为 v20801、BCB CONFIRMED、SD_IsReady=1、VTOR=0x08010000、CFSR=0。全链未出现 WDT、HardFault、恢复模式死等或生产调试标记。

## 1. 验收身份、边界与快照

- 活动 worktree：D:\github\my\E-Track-p2-5-20260801
- 分支：p2-5-20260801
- HEAD：0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e
- 指定基线：0023e5f
- 原验收证据：.acceptance-p2-5-f4\20260809-231127\
- 纠错复核证据：.acceptance-p2-5-f4\20260810-040604\
- 验收身份：非实现会话；纠错复核发现硬件 wrapper 实际复用了 .remediation-p2-5-f4 下的实现侧 harness，因此不再把其无条件汇总字段作为独立通过依据。
- 本轮未执行 commit、push、merge、rebase、reset、checkout 或 stash。
- 本轮未修改实现源码。允许写入仅为本证据目录、本文档和 PLAN-OTA-EXEC.md 状态。

验收前正式快照命令均退出 0：

~~~text
git rev-parse --show-toplevel
git rev-parse HEAD
git status --short --branch --untracked-files=all
git diff --stat
git diff --check
git diff --name-status
git diff --numstat
git ls-files --others --exclude-standard
git diff --binary
git diff --raw
~~~

验收前完整 status 共 4252 行，SHA-256 为 B8E725584DDAEBF07D5A72B06877182BEC4445C716F7E8C15FB0597166F29F97；完整 untracked 清单共 4238 行，SHA-256 为 30DD9B8A502D06E7E1FB3B08B933903E26F5D64DD067BCE75ABE99016C6B297B。原始文件分别为 preflight\03-status-all.txt 和 preflight\08-untracked.txt。

验收前 git status 的全部跟踪文件状态为：

~~~text
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
~~~

其中 git diff --name-status 的实际内容差异为 14 个文件：

~~~text
M Libraries/OTA/ota_confirm_health.c
M Libraries/OTA/ota_confirm_health.h
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
~~~

Tools/jlink/jlink-common.ps1、USER/App/App.cpp、USER/App/Utils/OtaUpdate/OtaUpdate.cpp 和 USER/lv_port/lv_port_indev.cpp 在 status 中显示修改，但当时没有进入普通内容 diff；本报告不将其隐去。未跟踪项包含历史验收/整改目录、构建目录、提示词、报告和 flash 脚本，逐文件完整清单保存在上述 4238 行原始文件中。

验收前 git diff --check 退出 0，仅输出 16 条 LF 将被 Git 转为 CRLF 的提示；未将这些提示粉饰为“干净工作树”。

## 2. 生产清理与静态入口

生产清理最终审计全部通过：

| 检查项 | 结果 |
|---|---|
| 生产入口唯一 manager.Push("Pages/Startup") | 通过，计数 1 |
| 无 FirmwareUpdate 直达入口 | 通过，计数 0 |
| LV_FS_PC_PATH | 通过，为 "." |
| Startup timeline 创建并启动 | 通过 |
| Startup 无 Win32 视觉绕过 | 通过 |
| Startup 无 shadow/custom draw 等风险路径 | 通过 |
| LV_MEM_SIZE | 通过，128 KiB |
| CONFIG_RTT_DEBUG_CMD_ENABLE | 通过，为 0 |
| App/Boot ELF 与 bin 无 F4TRACE、F4PROBE、RTTCMD:、RttDebugCmd_Poll | 通过，命中 0 |
| App 看门狗 | 通过，10000 ms |
| USER/main.cpp 相对基线 | 通过，内容差异 0 |
| 三个指定文件 UTF-8 BOM | 通过，均无 BOM |
| 源码 include 反斜杠 | 通过，命中 0 |
| 最终 candidate 与 v20801 final App | 通过，逐字节一致 |
| 残留模拟器/J-Link 进程 | 通过，0 |

证据为 static\23-production-cleanup-audit-final.txt 和 build\gcc\07-artifact-summary.json。

## 3. 模拟器阻断独立复核

### 3.1 Fresh Rebuild

正式命令：

~~~text
& 'D:\vs2019\MSBuild\Current\Bin\MSBuild.exe' 'D:\github\my\E-Track-p2-5-20260801\Simulator\LVGL.Simulator.sln' /m /t:Rebuild /p:Configuration=Debug /p:Platform=x64 /v:minimal
~~~

结果：

| 项目 | 值 |
|---|---|
| 退出码 | 0 |
| 开始 | 2026-08-09T23:18:53.1604032+08:00 |
| 结束 | 2026-08-09T23:30:15.4917790+08:00 |
| 耗时 | 682324 ms |
| warning | 102 |
| error | 0 |
| EXE 大小 | 5880832 B |
| EXE 时间戳 | 2026-08-09T23:20:15.2260015+08:00 |
| EXE SHA-256 | 70E38F5D11D295E9161EF39A806C1024CC50DD728D46EF5E705A3C7685F93643 |
| 构建后残留进程 | 0 |

TEMP、TMP、APPDATA、LOCALAPPDATA 均重定向到本轮证据目录。

### 3.2 正确生命周期连续启动

正式命令：

~~~text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\.acceptance-p2-5-f4\20260809-231127\sim_lifecycle_runner.ps1" -RunCount 6 -MainObserveSeconds 10 -StartupDeadlineSeconds 30 -EvidenceName "lifecycle-independent-6x"
~~~

命令退出 0，六轮均在启动前确认无残留 LVGL.Simulator，均经过真实 Startup，到达仪表盘后继续观察 10 秒，均以 WM_CLOSE 正常退出；没有任何 Force 结束。

| 轮次 | PID | HWND | Startup 到仪表盘 | Responding | Hung | CPU | WorkingSet | PrivateMemory | 结束 |
|---:|---:|---|---:|---|---|---:|---:|---:|---|
| 1 | 17188 | 0x6E0B0E | 5161 ms | True | False | 1.266 s | 56139776 B | 93376512 B | WM_CLOSE 99 ms |
| 2 | 15700 | 0x430AA8 | 4999 ms | True | False | 1.172 s | 56492032 B | 93700096 B | WM_CLOSE 85 ms |
| 3 | 3788 | 0x680AFE | 4790 ms | True | False | 1.406 s | 56549376 B | 93831168 B | WM_CLOSE 101 ms |
| 4 | 10280 | 0x280BA2 | 4675 ms | True | False | 1.406 s | 56532992 B | 93822976 B | WM_CLOSE 114 ms |
| 5 | 2380 | 0x7C0AE6 | 4897 ms | True | False | 1.203 s | 56537088 B | 93822976 B | WM_CLOSE 100 ms |
| 6 | 10896 | 0x12D0764 | 4981 ms | True | False | 1.266 s | 56483840 B | 93732864 B | WM_CLOSE 76 ms |

六轮 Startup 专名截图 SHA-256：

| 轮次 | Startup 截图 SHA-256 | 仪表盘截图 SHA-256 |
|---:|---|---|
| 1 | 0E7B2DDE3D566F9280A5884E96893F18E86CE2E8EE767229C59767A618747D2E | EFC6E26FD0974C48FECA13B26A6CB0DB5D3669A7F001509AA0FCBAA830FFBC1B |
| 2 | 6291C1F7FFCEA5992FAA180AE801C29FB7A13241C5A919239CD4C6E17ABE3FA2 | 209B8377BA0C1C6F27EADDD02D67F7BD4B1AD6238396A957665DD04879BD7A93 |
| 3 | E6D19C3D201A05CC48DD3C66C3B3B3EA330BC8716583814EE4ECA5CCA9267BF0 | BA5375B117EE61FA6609BF8824BBFE7405B081A7FBC6D9A6EFB3E51CD785B0CE |
| 4 | 0A7AF9B59428460E587A906F3A2A68AAB96FB407F0D9C5D21BC5E5969411AC8B | B941878B9B324B4E96C0C0C943768F19AA747737D427EAB3CE3A6B4AE48517B4 |
| 5 | 6291C1F7FFCEA5992FAA180AE801C29FB7A13241C5A919239CD4C6E17ABE3FA2 | F946EB292163AA1C92E0767C62AF245CB9E93848F9B1E3BBBB39C0977A13BE90 |
| 6 | 541AB7B7E82B53B904BABE36CA9E813D2559AFADC25EE4DBE712ADB93A4D6E3D | 04DC5E49A42143B8761F9B58A7F6D382D8115EC12DF0135027F1BF7B4B70AA14 |

### 3.3 旧结论污染机制

旧验收脚本在系列开始时和每轮 finally 中均无条件执行 Stop-Process -Force。它没有向窗口发送 WM_CLOSE，也没有等待 LVGL/Win32 正常 teardown；强制终止后立即进入下一轮，测试的是被破坏的进程/窗口生命周期，而不是生产模拟器正常关闭再启动的生命周期。

本轮对照满足以下条件：

- 没有修改 Startup 或 Win32 产品层来规避。
- 生产入口仍为 Pages/Startup，Startup timeline 仍创建并运行。
- 使用同一 fresh EXE 完成 6/6 真实 Startup。
- 每轮关闭前 Responding=True、IsHungAppWindow=False。
- 每轮只用 WM_CLOSE，76 至 114 ms 内退出。
- 每轮前后残留进程均为 0。
- product Startup/Win32 相对基线无内容 diff。

因此上轮交替挂起不构成可复现的生产缺陷，判定为旧 harness 强制终止生命周期造成的验收污染。对照证据为 simulator\05-harness-comparison.txt、simulator\lifecycle-independent-6x\logs\results.json 和逐轮 CSV/截图。

## 4. F4 专项复核

### 4.1 独立生产等价 harness

编译和运行均退出 0，warning/error 为 0/0：

~~~text
F4_ACCEPTANCE_HARNESS=PASS
FILTERED scans=4 rows=1
MIXED scans=256 rows=0 reads=257 more=1
ROWMAX rows=24 reads=25 more=1
EXACT_SCAN reads=257 more=0
DEVICE_PRIORITY=4
~~~

覆盖关系：

| 要求 | 结果 | 独立证据 |
|---|---|---|
| 隐藏、非 ETU、路径过长均消耗扫描上限 | 通过 | FILTERED、MIXED |
| ETU 在扫描上限之后显示截断，不显示未找到 | 通过 | MIXED reads=257、more=1 |
| 扫描截断提示明确 | 通过 | trunc fixture |
| ROW_MAX 截断提示明确 | 通过 | ROWMAX、rowmax fixture |
| rowCount=0 时截断提示有效 | 通过 | MIXED rows=0、trunc fixture |
| 只有 .. 时截断提示有效 | 通过 | only-up fixture |
| 恰好扫描上限结束不误报 | 通过 | EXACT_SCAN more=0；修正后的 256 项 fixture |
| deviceReady=false 优先级最高 | 通过 | DEVICE_PRIORITY=4 |
| 正常小目录 ETU 可选择并进入确认 | 通过 | small-select、small-full-flow |

原复制的 exact256 fixture 实际包含 258 个条目，其中 255 个 txt 加 3 个模拟器支持文件，因此其截断提示本来就是正确结果，不能用于“恰好 256”判据。本轮只在新验收 fixture 中移除 exact-253.txt 与 exact-254.txt，使实际条目数精确为 256；生产文件未改。修正后状态 PASS、残留进程 0，截图 SHA-256 为 466DFBBCEC3C79BFE4357F082CF0052A298A8AD9A167785FD6650F0295417A60。

### 4.2 模拟器 fixture 与布局

| 场景 | 结果 | Responding/Hung | 截图 SHA-256 |
|---|---|---|---|
| 扫描截断 | PASS | True/False | 94879821AB5A9AADA81702B074DFE3736C0862564FCED3685E7E81DB71C9EDD4 |
| ROW_MAX 截断 | PASS | True/False | 0B4F43B2C220C5C70A580F2BD44513A8B9F55B5D68DA744F39C6402CA19010C5 |
| 精确 256 | PASS | True/False | 466DFBBCEC3C79BFE4357F082CF0052A298A8AD9A167785FD6650F0295417A60 |
| 仅 .. 的子目录 | PASS | True/False | 6E3382AC5E49DE021ACB0C1039320409E6912BE81F9132CEEAE0A6FCBE4C67B8 |
| 正常小目录选择 | PASS | True/False | AD53C3537303FB25BE5BF322026917E35C8387CD0D58480B7268D16B0AF48B4B |
| 完整取消/重选/导入/返回流 | PASS | True/False | AD53C3537303FB25BE5BF322026917E35C8387CD0D58480B7268D16B0AF48B4B |

目视检查确认：

- “文件管理”标题位于内容框上方，没有被遮挡。
- 截断提示为两行 MORE FILES EXIST / NOT ALL SHOWN，含义明确。
- “返回”和“开始导入”文字在按钮内水平、竖直居中。
- fresh ETU 可见、可选择并进入二次确认。
- 完整流覆盖 Candidate Verify、取消、再次确认、结果返回和再次进入。

### 4.3 量化复算（输入无效，不计通过）

下表算术本身可重复，但输入不是本轮最终无插桩生产固件，不能作为本轮通过证据：

| 指标 | 值 |
|---|---:|
| 历史插桩根目录 LoadFiles | 44.941 ms |
| 已测最大目录 | 96 项 |
| 单次读最坏值 | 378 us |
| 257 次读保守上界 | 97.660 ms |
| 24 行 UI 保守上界 | 209.837 ms |
| LoadFiles 总上界 | 307.497 ms |
| 实现预声明阈值 | 320 ms |
| 阈值裕度 | 12.503 ms |
| 每 32 项喂狗最坏间隔 | 12.160 ms |
| 相对 10000 ms WDT 裕度 | 9987.840 ms，约 822.37 倍 |
| 历史插桩页面加载到列表，首次/再次进入 | 817 ms / 817 ms |
| 加 100 ms 输入轮询上界 | 917 ms |

输入 provenance 如下：

- `44.941 ms` 与单读数据来自 `.cache\p1-7-unlock\run-20260806-191731\unlock-final-reset-rtt.log`，含 `F4PROBE`，SHA-256 `899FCC88...17613E`。
- 最大目录数据来自 `.cache\p1-7-unlock\run-20260806-202255\unlock-final-reset-rtt.log`，含 `F4METRIC`，SHA-256 `25C6A551...EA0506E`。
- 两次 `817 ms` 来自 `.cache\p2-5-f4-remediation-20260807\scoped-cache-r1\entry-focus-confirm-rtt.log` 和 `physical-back-reenter-rtt.log`，均含 `F4TRACE`、`RTTCMD:`；对应镜像验证记录为 `600820 B`、SHA-256 `5153E656...8FB3A12F`。
- 本轮 finalized v20800 App 为 `598836 B`、SHA-256 `66EC8DD2...4E679D3`，最终 ELF/bin 临时标记命中数为 0。

因此 `static\17-f4-quantitative-recalculation.txt` 只能作为历史整改估算，不能证明本轮 final-r2 生产固件满足 `320 ms` 和约 `917 ms` 门禁。精确审计见 `.acceptance-p2-5-f4\20260810-040604\02-quantitative-provenance.txt`。

### 4.4 真机 F4

最终无插桩生产固件从真实 Startup 进入 Dialplate、MainMenu、FirmwareUpdate：

- 根目录 rowCount=6，P2-5-FULL.etu 可见，DeviceReady=1。
- 文件管理返回 MainMenu 后再次进入仍可用。
- ETU 首次选择进入 mode=1，取消回到 mode=0，再次选择重新进入 mode=1。
- 导入结果 mode=3、ResultSuccess=1、ApplyPending=0、StagePending=0。
- 结果页返回和再次进入文件管理通过。
- 各阶段 PC 可执行、SD_IsReady=1、VTOR=0x08010000、CFSR=0。
- 无 WDT、HardFault、黑屏或不可接受冻结。

真机没有使用完整 384 KiB RAM 抓取；只抓取 FirmwareUpdate 必要的 8320 B 紧凑成员区，避免 halt 超过 10 秒污染产品行为。

## 5. 宿主回归与 TEST_BOOT 门禁

11 条正式宿主命令均退出 0：

| 命令 | 结果 |
|---|---|
| python tests/boot/test_fw_header_vectors.py | 16/16 |
| python tests/boot/test_boot_protocols.py | 19/19 |
| python tests/boot/test_boot_state_machine.py | 96/96 |
| python tests/boot/test_p1_6_protocol.py | 21/21 |
| python tests/ota-vectors/test_vectors.py | 9/9 |
| python tests/ota/test_ota_staging.py | 48/48 |
| python tests/ota/test_ota_package.py | 102/102 |
| python tests/ota/test_ota_patch.py | 167/167 |
| python tests/ota/test_ota_sd.py | 29/29 + 5/5 |
| python tests/ota/test_ota_update.py | Session 7/7 |
| python tests/ota/test_ota_backup.py | backup 108/108；confirm health 24/24 |

总计 11/11 进程退出 0，低于基线的项目为 0。完整日志及每份日志 SHA-256 位于 host-tests\12-summary.json。

生产等价 TEST_BOOT 门禁 harness 通过：

~~~text
BEGIN_TEST_BOOT rejected=1 result=busy error=gate:bcb_not_confirmed opens=5/5 closes=5/5
APPLY_TEST_BOOT rejected=1 applied=0 error=gate:bcb_not_confirmed opens=2212/2212 closes=2212/2212
OTA_TEST_BOOT_GATE_HARNESS=PASS
~~~

Begin() 和 Apply() 在非 CONFIRMED 状态均拒绝，未产生额外打开/关闭不对称或 apply 副作用。Boot artifact 与 handoff validators 也均退出 0。

## 6. Fresh 构建

### 6.1 GCC Release

正式命令：

~~~text
cmake --build MDK-ARM_F435\cmake-generated\build-gcc-release --clean-first --parallel
~~~

结果：退出 0，耗时 530696 ms，warning 1249，error 0，failed 0。warning 未粉饰。

| 产物 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| App raw bin | 598836 B | 2026-08-09T23:48:58.7811909+08:00 | 1B5F84FABB30F949AB823ED22F8B93DD444EC0A5DA82E2A139488B0B482AB2FB |
| App ELF | 859836 B | 2026-08-09T23:48:58.4584249+08:00 | A117A23461374FBAFB2707A37F3B86AEFFBEBAF873B133362BFEC4FC25BE4341 |
| App map | 2233500 B | 2026-08-09T23:48:58.4652598+08:00 | 5A59DE96814EC499B72A4E003E65D00EB1D69A6B7131DC53D5133D75C2BC5C43 |
| Boot bin | 14724 B | 2026-08-09T23:48:55.1682468+08:00 | 5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594 |
| Boot ELF | 36860 B | 2026-08-09T23:48:54.1516064+08:00 | D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC |
| Boot HEX | 41485 B | 2026-08-09T23:48:55.0242183+08:00 | FF3BADEF69BE6D97FD66815B8DF90EFD962A708B559C8951D4B56380F8001F71 |

Boot 小于 64 KiB，恰有 3 个 LOAD segment，RWX segment 为 0。最终 map 严格符号行解析为：

~~~text
0x20053e14                _SEGGER_RTT
~~~

### 6.2 AC5

按 AGENTS.md 正式尝试：

~~~text
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& '.\MDK-ARM_F435\build_f435.ps1' -AutoStale"
~~~

退出 1，原因仅为 MDK-ARM_F435\Objects\X-Track.lnp 缺失；warning/error 计数为 0/0，没有手工注入 --cpp11。该历史工具链限制如实记录，不冒充成功，也不阻断本轮指定 GCC 生产固件闭环。

## 7. Finalize、封包、解包与 SD

本轮全部从 fresh raw App 重新生成：

| 资产 | vcode | 大小 | SHA-256 |
|---|---:|---:|---|
| raw App | 未 finalize | 598836 B | 1B5F84FABB30F949AB823ED22F8B93DD444EC0A5DA82E2A139488B0B482AB2FB |
| v20800 finalized App | 20800 | 598836 B | 66EC8DD2539F3B51004373318C5BC1812099DB33F4D3D8E1C9BC40FB44E679D3 |
| v20801 finalized App | 20801 | 598836 B | E7D40BC810D5EA92CF426DF0E4BE90971CA8730235E34F74EA78DED65EB1DBD6 |
| fresh full ETU | target 20801 | 281170 B | 142F1033759ACBA329E2E12E4B450F296C08AA6F924919A3126366815E86B459 |
| unpack candidate | 20801 | 598836 B | E7D40BC810D5EA92CF426DF0E4BE90971CA8730235E34F74EA78DED65EB1DBD6 |

finalize、verify、pack-full、unpack 和 fc /b 均退出 0。fc /b 明确输出 no differences encountered，candidate 与 v20801 finalized App 逐字节一致。

SD 写入前 E: 根目录为 9 个条目。只覆盖 E:\P2-5-FULL.etu，未修改其他文件或 F4ACC fixture。写后：

| 项目 | 结果 |
|---|---|
| E:\P2-5-FULL.etu 大小 | 281170 B |
| 回读 SHA-256 | 142F1033759ACBA329E2E12E4B450F296C08AA6F924919A3126366815E86B459 |
| 从 E: 直接解包 | 退出 0 |
| SD candidate 大小 | 598836 B |
| SD candidate SHA-256 | E7D40BC810D5EA92CF426DF0E4BE90971CA8730235E34F74EA78DED65EB1DBD6 |
| 与 v20801 final App 比较 | 退出 0，逐字节一致 |
| 写后根目录条目数 | 9 |
| 根目录名称差异 | 0 |

## 8. J-Link、基线恢复与 RTT 验签

J-Link 参数始终为 AT32F435RGT7 / SWD / 1000 kHz。TEMP、TMP、APPDATA、LOCALAPPDATA、HOME、J-Link 脚本和日志均指向本轮证据目录；每阶段前清理并检查 JLinkRTTLogger、JLinkGUIServer 和其他 J-Link 残留。

### 8.1 初始设备

独立实读初始设备为：

~~~text
vcode=20801
BCB=CONFIRMED
SD_IsReady=1
VTOR=0x08010000
CFSR=0
~~~

RTT 地址来自本轮 fresh map：0x20053E14。启动 logger 前执行：

~~~text
mem8 0x20053E14, 16
20053E14 = 53 45 47 47 45 52 20 52 54 54 00 00 00 00 00 00
~~~

签名为 SEGGER RTT。

### 8.2 P1-6 正式恢复

本轮 fresh 构建 P1-6 test Boot：

| 项目 | 值 |
|---|---|
| 大小 | 18720 B |
| SHA-256 | ABD042DB09B27198D2C52E9EE4E8C15D0C524BD28CB55023DD2AECAC9098CE55 |
| warning/error | 0/0 |
| P1_6_TEST_ENABLE | true |

正式恢复过程：

1. 烧录 fresh P1-6 test Boot 与本轮 v20800 finalized App，两个 loadfile 均 Verify successful。
2. 通过仓库正式 CLEAR_BCB RAM 控制块流程执行，结果 status=2、detail=0。
3. 烧录本轮生产 Boot 与 v20800 finalized App，两个 loadfile 均 Verify successful。
4. 普通复位后独立实读 v20800/CONFIRMED、SD_IsReady=1、VTOR=0x08010000、CFSR=0。

未直接修改 EEPROM。

## 9. 真机 OTA 完整闭环

### 9.1 升级前

- BCB=CONFIRMED。
- vcode=20800。
- 生产 Boot SHA-256 为 5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594。
- 生产 App 为本轮 v20800 finalized App，SHA-256 为 66EC8DD2539F3B51004373318C5BC1812099DB33F4D3D8E1C9BC40FB44E679D3。
- RTT 地址 0x20053E14，mem8 签名通过。

### 9.2 UI 与导入

使用真实 Startup 和真实编码器路径完成：

1. Startup 到 Dialplate 正常。
2. Dialplate 到 MainMenu 正常。
3. 进入 FirmwareUpdate 文件管理，P2-5-FULL.etu 可见。
4. 浏览器返回 MainMenu，再次进入仍正常。
5. 选择 ETU，确认页现场观察为 2.8.0 到 2.8.1。
6. 取消后回到文件管理，再次选择进入二次确认。
7. 原报告记为“现场观察 UI 出现 CANDIDATE VERIFY”，但没有独立屏幕证据保留。
8. 原报告记为“现场观察 UI 出现 BACKUP + STAGED”，但没有独立屏幕证据保留。
9. 导入结果页显示成功；内存状态为 mode=3、ResultSuccess=1、ApplyPending=0、StagePending=0。
10. 结果页返回和再次进入文件管理均正常。

硬件证据目录的图片文件数量为 0。独立 wrapper 通过 `Invoke-Expression` 复用了实现侧 `.remediation-p2-5-f4\20260809-104540\hardware_preview_r2.ps1`，该脚本在 1050-1054 行把多项汇总布尔值直接赋为 `$true`，包括 `CandidateAndStagePassed`。`mode=3`、`ResultSuccess=1` 以及随后 `TEST_BOOT/CONFIRMED` RTT 是有效状态证据，但不能替代两个指定 UI 文字的独立留证。审计见 `.acceptance-p2-5-f4\20260810-040604\03-hardware-ui-evidence-audit.txt`。

### 9.3 TEST_BOOT

按提示复位后，重新验签 RTT 并启动新的 90 秒采集。日志 SHA-256 为 E74DCABF99FE90F5371F91FDBF7C91600BB9D9701224073C956F0C9BD556F8B5，包含：

~~~text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
OTA: TEST_BOOT confirmed vcode=20801
~~~

90 秒窗口内没有 WDT、HardFault、恢复模式死等或调试标记。采集后实读 vcode=20801、BCB=CONFIRMED、SD_IsReady=1、VTOR=0x08010000、CFSR=0。

### 9.4 二次普通复位

再次普通复位、重新验签并采集。日志 SHA-256 为 832D825E85EF9B66C58B898EAEB8C1BFF659CA4D15DFFD64E6F2C045E9755D25，包含：

~~~text
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
OTA: BCB already CONFIRMED vcode=20801
~~~

二次复位后仍为 v20801/CONFIRMED。

### 9.4.1 完整 RTT 原始行

以下为本轮关键阶段的完整 logger 文本（分隔线和四行设备输出均保留；对应原始文件位于 hardware 子目录）：

~~~text
BASELINE
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20800

PRE-REBOOT AFTER UI
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20800

TEST_BOOT 90 SECOND WINDOW
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: TEST_BOOT confirmed vcode=20801

SECOND NORMAL RESET
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20801

FINAL CURRENT DEVICE
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20801
~~~

### 9.5 升级后功能

使用真实编码器完成 Dialplate -> MainMenu -> FirmwareUpdate -> 浏览器返回 -> MainMenu。页面管理器状态与紧凑 FirmwareUpdate 状态均正确；最终 SD_IsReady=1、VTOR=0x08010000、CFSR=0。屏幕、编码器、返回和基本页面功能正常。

## 10. 验收矩阵

| 要求 | 结果 | 说明 |
|---|---|---|
| HEAD 与完整工作树快照 | 通过 | HEAD、4252 行 status、4238 行 untracked、diff 全部留证 |
| 不修改实现代码 | 通过 | 本会话仅证据、报告、PLAN 状态 |
| 模拟器 Rebuild | 通过 | rc=0，102 warning，0 error |
| 真实 Startup 连续至少两次 | 通过 | 6/6，均响应，均 WM_CLOSE |
| 旧模拟器阻断污染复核 | 通过 | Force 生命周期污染，不是生产缺陷 |
| F4 扫描上限语义 | 通过 | 独立 harness |
| 扫描/ROW_MAX 截断提示 | 通过 | harness + fixture |
| rowCount=0 与仅 .. | 通过 | harness + only-up |
| 恰好上限不误报 | 通过 | 修正后的精确 256 fixture |
| deviceReady 优先级 | 通过 | DEVICE_PRIORITY=4 |
| 正常 ETU 选择与确认 | 通过 | 模拟器和真机 |
| 标题与按钮布局 | 通过 | 专名截图目视检查 |
| LoadFiles 320 ms 阈值 | 失败 | 307.497 ms 来自 2026-08-06 插桩日志，不是本轮 final-r2 固件 |
| 输入到列表约 917 ms 上界 | 失败 | 817 ms 来自不同哈希的 2026-08-07 `F4TRACE/RTTCMD:` 固件 |
| 真机文件管理无 WDT/HardFault | 通过 | 真实 Startup、返回、重入、完整导入 |
| 11 组宿主回归 | 通过 | 全部 rc=0，无基线回退 |
| Begin/Apply TEST_BOOT 门禁 | 通过 | 生产等价 harness |
| fresh GCC App/Boot | 通过 | 1249 warning，0 error |
| Boot 小于 64 KiB、3 LOAD、无 RWX | 通过 | 14724 B、3、0 |
| 最终固件无临时标记 | 通过 | App/Boot ELF/bin 命中 0 |
| AC5 正式尝试 | 已执行，历史限制 | 缺 X-Track.lnp，rc=1，未注入 --cpp11 |
| fresh finalize/ETU/candidate | 通过 | fc /b 无差异 |
| SD 仅覆盖授权文件 | 通过 | 根目录 9 -> 9，名称差异 0 |
| fresh map RTT 地址与签名 | 通过 | 0x20053E14，SEGGER RTT |
| v20800/CONFIRMED 基线 | 通过 | P1-6 CLEAR_BCB 正式流程 |
| CANDIDATE VERIFY | 失败 | 无屏幕证据；汇总布尔值无条件置真 |
| BACKUP + STAGED | 失败 | 无屏幕证据；汇总布尔值无条件置真 |
| TEST_BOOT 90 秒 RTT | 通过 | HANDOFF + confirmed v20801 |
| 二次复位仍 CONFIRMED | 通过 | BCB already CONFIRMED v20801 |
| 升级后基本页面功能 | 通过 | 真实编码器路径 |
| 残留进程 | 通过 | 模拟器/J-Link 均 0 |

最终判定：不通过。P2-5 保持“阻塞”，P2 保持 4/6。

## 11. 非产品失败与边界事件

### 11.1 验收 wrapper 两次错误

首次 wrapper 退出 1，原因是 PowerShell Replace 的 Replacement 为空字符串；错误发生在转换参考 harness 阶段，J-Link 未启动，设备未复位、未读写。

第二次 wrapper 退出 1，原因是 RTT 签名 helper 同时返回 PASS 文本和日志路径，包装器将两者错误拼成一个路径。该次在汇总 JSON 阶段失败；没有 flash 或 BCB 写入，已完成的 reset、签名、20 秒 RTT 与健康探测原始证据保留在 00-current-device\。修正的是验收 wrapper，不是生产实现。

最终正式各 phase 均通过。两个错误分别保留在 hardware\00-wrapper-attempt1-error.txt 和 hardware\00-wrapper-attempt2-error.txt。

### 11.2 SEGGER 外部 INI

尽管 APPDATA 已重定向，SEGGER 仍刷新：

~~~text
C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini
~~~

发现后立即停止扩展操作并向用户报告，随后用户明确回复“授权”，授权仅覆盖该精确路径以及既有 E:\P2-5-FULL.etu。

授权前后 JLinkDLL.ini 均为 859 B，SHA-256 均为 D4FB1AD31E202D8C54307F664B5AA8EE08121252A04D5A7ACACFA60D6239E4B9；内容未变，仅时间戳由 2026-08-10T01:40:14.1562785+08:00 刷新到 2026-08-10T02:30:12.0935655+08:00。没有手工恢复或清理该文件。

## 12. 未执行项

未在本轮最终无插桩生产固件上重新测量 `LoadFiles <= 320 ms` 和输入到列表约 `917 ms` 上界；真机两个指定 UI 文字也没有形成独立屏幕证据。发现该 provenance 阻断后按 fail-fast 停止，没有再次覆盖 SD、烧录、复位或启动 J-Link/logger。

此外，AC5 正式尝试仍受历史工具链限制：MDK-ARM_F435\Objects\X-Track.lnp 不存在，因此 build_f435.ps1 -AutoStale 退出 1。本轮没有修改工程配置或手工注入 --cpp11 来规避。

## 13. 关键证据索引

- 验收前快照：.acceptance-p2-5-f4\20260809-231127\preflight\
- 模拟器构建：simulator\04-msbuild-summary.json
- 模拟器生命周期：simulator\lifecycle-independent-6x\logs\results.json
- 旧/新 harness 对照：simulator\05-harness-comparison.txt
- F4 fixture：simulator\fixture-results\
- F4 harness：static\04-f4-summary.json
- F4 量化：static\17-f4-quantitative-recalculation.txt
- 生产清理：static\23-production-cleanup-audit-final.txt
- TEST_BOOT 门禁：static\15-gate-summary.json
- 宿主回归：host-tests\12-summary.json
- fresh GCC：build\gcc\03-build-meta.json、build\gcc\07-artifact-summary.json
- AC5：build\ac5\02-summary.json
- 包一致性：package\08-summary.json
- SD 写入与回读：sd\05-write-readback-summary.json
- 初始设备：hardware\00-current-device-r2\current-device-summary.json
- P1-6 恢复：hardware\01-p16-build\summary.json、hardware\02-prepare-baseline\prepare-summary.json
- v20800 基线：hardware\03-baseline\baseline-summary.json
- 真机 UI：hardware\04-ui\ui-summary.json
- TEST_BOOT：hardware\05-test-boot\test-boot-summary.json
- 二次复位：hardware\06-confirmed-reboot\confirmed-summary.json
- 升级后 UI：hardware\07-post-confirmed-ui\post-confirmed-ui-summary.json
- 授权记录：hardware\00-external-write-authorization.txt
- 硬件阶段命令：hardware\00-commands.txt
- 初步最终审计：hardware\07-final-external-and-process-audit.json
- 独立纠错 provenance：.acceptance-p2-5-f4\20260810-040604\

最终收尾审计已完成，原始文件为 final-r2\04-final-audit.json、final-r2\05-final-summary.txt、final-r2\01-git-diff-check.txt、final-r2\02-git-status-all.txt 和 final-r2\03-git-diff-name-status.txt。

最终审计摘要：

- git diff --check 退出 0，输出文件 SHA-256 为 4EC424AF0863A6DCBF24AE8CC8D09B58604A3D8EFD3B22F07C844A10881440D0。
- 最终 status 退出 0，共 5191 行，文件 SHA-256 为 7E37CF7BF9EC7EFD7427C2C0129BC54B06F157396E9E34FA825DAE0BA2CC4E1D。
- 最终 name-status 退出 0，文件 SHA-256 为 DE940DF8E06A467806A88F55B766DDD870832D015E0E8EE676E121D5F627EC8E。
- 残留 LVGL.Simulator、JLink、JLinkRTTLogger、JLinkGUIServer 数量均为 0。
- E: 已挂载，根目录条目 9 个，E:\P2-5-FULL.etu SHA-256 为 142F1033759ACBA329E2E12E4B450F296C08AA6F924919A3126366815E86B459，和本轮 ETU 一致。
- 授权范围内 SEGGER INI 内容 SHA-256 仍为 D4FB1AD31E202D8C54307F664B5AA8EE08121252A04D5A7ACACFA60D6239E4B9。
- 最终设备摘要为 v20801/状态 4/SD=1/VTOR=0x08010000/CFSR=0；升级后编码器、FirmwareUpdate 和浏览器返回均为 true。

上述设备状态和 OTA RTT 链仍属有效证据，但不能覆盖本报告 §4.3 和 §9.2 的强制门禁失败。本次纠错复核没有修改实现文件，也没有再次操作 SD 或 J-Link。
