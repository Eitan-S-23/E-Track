# P2-5 F4 第二轮整改收口证据（2026-08-09）

## 0. 结论与边界

本文件是实现会话证据，不是独立验收签字。F4 实现整改、可获得的 GCC 真机量化、
生产态清理及 r3 真机 OTA 闭环均已完成；P2-5 仍保持阻塞，P2 仍为 4/6。
必须由非实现会话按 .claude\prompt-P2-5-verification.md 重新验收。

- 工作树：D:\github\my\E-Track-p2-5-20260801
- 分支：p2-5-20260801
- HEAD：0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e
- 整改依据：.claude\prompt-F4-remediation.md
- 前置复核：docs\ota-exec-notes\P2-5-F4-review-2026-08-06.md
- 本会话未执行 commit、push、merge、rebase、reset、checkout 或 stash

| 判据 | 实现会话结论 |
|---|---|
| §1 截断提示 | 已实现，由 fixture、模拟器截图及独立 F4 验收覆盖 |
| §2 GCC 真机量化 | 当前介质可复现实测已完成；原 F4 根目录的精确历史数据不可恢复，限制如实保留 |
| §3.1 SCAN_MAX | 按观测最坏值保留 256，同步加载保守估计小于 0.32 s |
| §3.2 ASCII 文案 | MORE FILES EXIST, NOT ALL SHOWN |
| §3.3 BOM | 三个指定文件均无 UTF-8 BOM |
| §3.4 改动申报 | 功能改动、临时改动、生成副产物、预存状态和项目外授权均已申报 |

## 1. 对应 §1：截断提示

FirmwareUpdate::LoadFiles() 的最终规则：

- scanCount 与 rowCount 分离。
- 目录读取返回真实条目后 scanCount 即递增，隐藏项、非 .etu 文件和其他过滤项
  同样消耗 SCAN_MAX。
- 主循环同时受 ROW_MAX=24 和 SCAN_MAX=256 限制。
- 命中任一上限后额外 probe 一次；只有 probe 读到真实后续条目才设置
  moreEntries，恰好读完不误报。
- moreEntries 分支优先于 TXT_EMPTY，覆盖 rowCount=0 和只有返回上级行的场景。
- deviceReady=false 的 TXT_FILE_INVALID 最后写入，仍是最高优先级。
- 固件侧每 32 个扫描条目调用 WDG_ReloadCounter()，并由
  #if !defined(_WIN32) 隔离模拟器。

对应文件：

- USER\App\Pages\FirmwareUpdate\FirmwareUpdate.cpp
- USER\App\Pages\FirmwareUpdate\FirmwareUpdate.h

模拟器 fixture 使用 300 个 .txt 条目加 1 个 test.etu，共 301 项。最终截图显示：

    MORE FILES EXIST, NOT ALL SHOWN

| 证据 | 大小/时间 | SHA-256 |
|---|---|---|
| .cache\sim-trunc-final.png | 4914 B / 2026-08-06T20:46:10.7969682+08:00 | 29861435E81FCD6CCB3EEA367302CE55A63C3E23D295F788C54AFFACEADC52B6 |
| .cache\p2-5-wdt-remediation\20260808-hardware-r7-ota-closure\15-f4-trunc.png | 9783 B / 2026-08-09T00:13:08.5909063+08:00 | 318BF88970AE18414EA7E37615179102A87AF9C858CFED7967AEAE988F2CACAF |

独立报告 docs\ota-exec-notes\P2-5-F4-independent-acceptance-2026-08-07.md
已确认 F4ACC 301 项目录显示截断提示，文件管理页不再出现 F4 WDT/HardFault。

## 2. 对应 §2：GCC 真机量化

### 2.1 方法与不可恢复项

临时计时固件直接使用 SEGGER_RTT_printf。每次重新链接后均从最新 GCC map 查找
_SEGGER_RTT，用 J-Link mem8 验证前 10 字节为
53 45 47 47 45 52 20 52 54 54，并清理残留 logger/server，确保单一 logger。

2026-08-05 触发 F4 时的 SD 根目录已被后续测试改变，因此不能恢复：

- 原触发目录的精确条目数；
- 修复前版本在同一目录上的完整 LoadFiles 总耗时。

历史 WDT 只证明旧路径超过 10000 ms 下界。本文件不把当前目录或线性外推冒充为
原目录直接实测。

### 2.2 可复现数据

根目录日志：

- .cache\p1-7-unlock\run-20260806-191731\unlock-final-reset-rtt.log
- SHA-256：899FCC880C13539179F07BA494D5302EF95F33C8884C387DE2CFF31A0717613E

    F4PROBE: path=/ entries=8 etu=1 dir=4 scanCount=8 more=0
             read_calls=9 read_avg_us=136 read_max_us=378
             read_total_us=1225 total_us=44941

根目录分类为 entries=8、etu=1、dir=4、hidden=2、other=1。修复版 LoadFiles
总耗时 44.941 ms，其中目录读取 1.225 ms。

卡上已遍历的最大目录为 /MAP/16/51857：

    F4METRIC: p=/MAP/16/51857 n=96 full=4157 ra=29 rm=313 rt=2827
              fixed=4153 more=0 fa=29 fm=311 ft=2834

- 96 项完整/修复路径：4.157 ms / 4.153 ms
- 单次读取平均/最坏：约 29 us / 313 us
- 全部采样单次读取最坏：378 us
- 目录发现日志 SHA-256：5D3BC25C5A52FA159B935EA855276E63C954AA378DBA5F346F7CD8CA42D01358
- 紧凑日志 SHA-256：25C6A551B2C8BF56E88F71E5379A884F0D70E8457F859095F5DB4A0ECEA0506E

### 2.3 插桩清理与最终 GCC 产物

构建命令：

    cmake --build MDK-ARM_F435\cmake-generated\build-gcc-release --parallel

构建退出 0；存在仓库既有 warning，error=0。

| 产物 | 大小 | 时间 | SHA-256 |
|---|---:|---|---|
| app-gcc\X-Track-App-GCC.bin | 598684 B | 2026-08-08T23:39:06.134+08:00 | F7AFDD6D80C39B5446D19C37DCD34850994596145F2E93FA97855F6D6B819473 |
| app-gcc\X-Track-App-GCC.elf | 859732 B | 2026-08-08T23:39:05.923+08:00 | 2AA0B46220F34243AA2E80F6592F7B61EECA9995E46F96670DBFA8886E61340B |
| app-gcc\X-Track-App-GCC.map | 2232959 B | 2026-08-08T23:39:05.930+08:00 | DEC808F0A74BC8FF2827170D13E75C03CCD48795992D67EAD565E544E66F5274 |
| boot\X-Track-Boot.bin | 14724 B | 2026-08-08T23:39:01.990+08:00 | 5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594 |

清理核对：

- FirmwareUpdate.cpp 不再包含 Arduino.h、SEGGER_RTT.h、__f4_*、F4PROBE、
  F4FULL 或 F4METRIC。
- 最终 ELF_TEMP_MARKERS=0。
- LoadFiles() 内 WDG_ReloadCounter 调用数为 1。
- CONFIG_RTT_DEBUG_CMD_ENABLE=0，生产固件不启用 RTT 下行调试命令。

## 3. 对应 §3.1：SCAN_MAX 取值

用向上取整的单次读取最坏值 380 us 计算：

1. 每 32 项喂狗最坏间隔：32 x 380 us = 12.160 ms。
2. 相对 10000 ms IWDG：10000 / 12.160 = 822.37 倍。
3. SCAN_MAX=256 加一次 probe，共 257 次读取：257 x 380 us = 97.660 ms。
4. 按较慢根目录样本将可见 UI 成本放大到 24 行，扫描加 UI 为 307.497 ms，
   保守记为小于 0.32 s。
5. 整次加载相对 10000 ms IWDG 约 31 倍裕度；喂狗是兜底，不是避免十几秒
   同步冻结的唯一手段。

独立验收最终页面两次 trace 均为 files rows=6 dt=817 ms；输入轮询 100 ms 后，
端到端上界约 917 ms。该值包含页面初始化/UI 创建，不替代 LoadFiles 单独计时。

结论：保留 SCAN_MAX=256、同步扫描和每 32 项喂狗。降低上限会增加大目录后部
.etu 漏列概率。若后续介质测得显著更高的 dir_read 延迟，必须重算；若同步方案
不能同时满足 UI 时延和文件可见性，再升级为 lv_timer 分帧加载。

## 4. 对应 §3.2：ASCII 文案

最终定义：

    TXT_SCAN_LIMIT = MORE FILES EXIST, NOT ALL SHOWN

该通用语义适用于扫描条目上限和可见行上限，不再把 ROW_MAX=24 写成扫描限制，
并保持纯 ASCII。

## 5. 对应 §3.3：BOM

| 文件 | 头三字节 | 结果 |
|---|---|---|
| USER\App\Pages\FirmwareUpdate\FirmwareUpdate.cpp | 23 69 6E | 无 BOM |
| USER\App\Pages\FirmwareUpdate\FirmwareUpdate.h | 23 69 66 | 无 BOM |
| PLAN-OTA-EXEC.md | 23 20 50 | 无 BOM |

## 6. r3 包、E: 回读和真机闭环

### 6.1 授权范围内的项目外操作

用户授权的唯一项目外写入是用 r3 fresh v20801 包覆盖 E:\P2-5-FULL.etu，
随后只做长度和 SHA-256 回读。

- 记录：.cache\p2-5-wdt-remediation\20260809-hardware-r8-r3-final\00-sd-package-readback.json
- 记录时间：2026-08-09T00:56:30.186+08:00
- 记录 SHA-256：D206D844E8214BD1AEE67631DEB83B1727D4BC2D7FD471D5A276BFE4BEBB8129
- 源/目标长度：281085 B / 281085 B
- 源/目标 SHA-256：E1EA4B5FA79462BAD3F8BD404E3D48A38E261C8C5482D1788C00692AC6B69E3D
- LengthMatch=true，HashMatch=true

未修改 E: 其他内容。

收尾只读审计时 E: 已未挂载，E_ROOT_EXISTS=False，因此没有再次读取或重写介质。
本节结论以 2026-08-09T00:56:30.186+08:00 已落盘的写后回读 JSON、源包及当时
目标哈希为依据。

### 6.2 P1-6 安全清理与 OTA 状态链

设备状态恢复复用仓库已有 P1-6 流程，不直接写 EEPROM：

    . .\Tools\jlink\jlink-common.ps1
    Invoke-P16Command -Opcode 1

测试 Boot + v20800 烧录验证后，CLEAR_BCB 返回 status=2、detail=0；随后重新
烧录生产 Boot + v20800。最终 GCC map 的 RTT 地址为 0x20045E14，mem8 验签为
SEGGER RTT。J-Link 参数为 AT32F435RGT7、SWD、1000 kHz。

证据目录：

.cache\p2-5-wdt-remediation\20260809-hardware-r8-r3-final

RAM 快照：

- 确认页：00 00 01 00 00 00 06 01，rowCount=6，mode=1
- 导入完成：00 00 01 00 00 01 06 03，resultSuccess=1，rowCount=6，mode=3
- 导入完成状态：SDReady=1、VTOR=0x08010000、CFSR=0

TEST_BOOT RTT：

    OTA: TEST_BOOT confirmed vcode=20801

- 07-test-boot\test-boot-rtt.log
- 284 B，2026-08-09T00:49:26.894+08:00
- SHA-256：E74DCABF99FE90F5371F91FDBF7C91600BB9D9701224073C956F0C9BD556F8B5

二次复位 RTT：

    OTA: BCB already CONFIRMED vcode=20801

- 08-confirmed-reboot\confirmed-reboot-rtt.log
- 286 B，2026-08-09T00:52:14.552+08:00
- SHA-256：832D825E85EF9B66C58B898EAEB8C1BFF659CA4D15DFFD64E6F2C045E9755D25

confirmed-reboot-summary.json 记录 Vcode=20801、OtaStateSnapshot=04 01 01 00、
SDReady=1、VTOR=0x08010000、CFSR=0、Wdt=false、HardFault=false。

包一致性：

| 产物 | 大小 | SHA-256 |
|---|---:|---|
| raw App | 598684 B | F7AFDD6D80C39B5446D19C37DCD34850994596145F2E93FA97855F6D6B819473 |
| v20800 finalized App | 598684 B | C86005214508953030B6A4076BD817B88ECE8CDB3D31D7DD9D846CA2891387C7 |
| v20801 finalized App | 598684 B | E680ADFAA05263F16FC9D8996EC6546CB7B90B41501E6EE3888F1D2079B30E0E |
| ETU candidate | 598684 B | E680ADFAA05263F16FC9D8996EC6546CB7B90B41501E6EE3888F1D2079B30E0E |
| r3 ETU | 281085 B | E1EA4B5FA79462BAD3F8BD404E3D48A38E261C8C5482D1788C00692AC6B69E3D |

完整 manifest：

- .cache\p2-5-wdt-remediation\20260809-hardware-r8-r3-final\artifact-manifest.json
- SHA-256：BA29EA95B291B414E9B411AD12AC5CF002FCAA447CD31587E338E2AEDDE01EAB

该结果是实现会话真机自验，不能替代非实现会话验收。

## 7. 对应 §3.4：改动申报

### 7.1 功能改动

| 文件 | 内容/来源 |
|---|---|
| USER\App\Pages\FirmwareUpdate\FirmwareUpdate.cpp | 扫描上界、周期喂狗、probe、消息优先级、ASCII 文案；后续按需 UI、ReleaseUI 和按钮对齐 |
| USER\App\Pages\FirmwareUpdate\FirmwareUpdate.h | SCAN_MAX=256、ReleaseUI 声明 |
| USER\App\Pages\Menu\MainMenu.cpp | 仅对 FirmwareUpdate 释放 MainMenu 缓存，降低 LVGL heap 峰值 |
| USER\App\Config\Config.h | 生产 CONFIG_RTT_DEBUG_CMD_ENABLE=0 |
| PLAN-OTA-EXEC.md | P2-5 状态、证据和 §10 会话日志 |

工作树中还保留 P2-5 前置实现/回归改动，不冒充为本轮新改动：

- Libraries\OTA\ota_confirm_health.c
- Libraries\OTA\ota_confirm_health.h
- USER\HAL\HAL_EEPROM.cpp
- USER\HAL\HAL_OTA_Package.cpp
- USER\lv_port\lv_port_indev.cpp
- tests\ota\test_ota_confirm_health.c
- Simulator\LVGL.Simulator\HAL\HAL_Encoder.cpp

### 7.2 临时改动最终状态

- USER\App\App.cpp 已从 Pages/FirmwareUpdate 恢复为 Pages/Startup。
- Simulator\LVGL.Simulator\lv_fs_if\lv_fs_pc.c 的 LV_FS_PC_PATH 已恢复为 "."。
- .cache\sim-test-dir 和模拟器目录中的 301 个 fixture 文件已清理。
- FirmwareUpdate RTT 计时插桩已删除，最终 ELF_TEMP_MARKERS=0。
- .cache\sim-trunc2.png 仅是历史中间截图，不作为最终证据。

### 7.3 生成、预存和项目外状态

- MDK-ARM_F435\cmake-generated\compile_commands.json 为 CMake configure
  生成副产物，不是手工编辑构建规则。
- MDK-ARM_F435\RTE\_X-Track-App-AC5\RTE_Components.h 在接手快照中曾有
  预存改动，来源为既有 AC5/RTE 生成状态；本轮未编辑，不计为本轮功能改动。
- C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini 为 SEGGER 此前自动维护的
  项目外配置，已获用户授权保留，本轮未清理。
- E:\P2-5-FULL.etu 仅执行第 6.1 节授权操作，未修改 E: 其他内容。
- 收口编辑时曾因 apply_patch 相对路径按 Agent 启动目录解析，误建
  D:\github\my\E-Track\docs\ota-exec-notes\P2-5-F4-fix-remediation-2026-08-09.md。
  该文件为 16293 B，SHA-256
  6B0A856A0350419A0E2DF0855FE82D43B2C5739872C28B0857F393DE4AE570E3。
  已先向用户披露并获得对该准确路径的删除授权，再用 apply_patch 删除；最终
  WRONG_EXISTS=False，未修改 D:\github\my\E-Track 的其他文件。

## 8. 验证矩阵

宿主摘要：

- .cache\p2-5-wdt-remediation\20260808-host-tests-final\host-tests-summary.log
- 786 B，2026-08-09T00:05:10.525+08:00
- SHA-256：FA1F23CA82F455AD080338801C12C835C97BD49C7C5A6BBD26046A0A490350E6

| 测试组 | 结果 |
|---|---|
| backup | 108/108 |
| confirm health | 17/17 |
| P2-2 | 102 |
| P2-3 | 167/167 |
| P2-4 | 29 + 5 + scenarios 7 |
| P2-1 | 48/0 |
| P1-3 | 96/0 |
| P1-1 | 16 |
| test_vectors.py | Ran 9 OK |

构建与模拟器：

- GCC Release 退出 0，有既有 warning，error=0。
- 模拟器生产入口为 Pages/Startup，LV_FS_PC_PATH "."。
- 最终 exe：5879296 B，2026-08-08T22:18:30.589+08:00，
  SHA-256 CB81A9CABB53CB7D768730382A71255F506FCE48CE5CBC5DBDBF8E8C2C60B3B9。
- 截断截图已目视确认。
- AC5 仍受历史 X-Track.lnp 缺失阻断，不能写成通过。

收尾审计：

- git diff --check：0
- 分支/HEAD：p2-5-20260801 /
  0023e5ff0af054438cbb2ed9e5bc99ae0e9b5c7e
- JLinkRTTLogger、JLinkGUIServer、JLink、JLinkRTTViewer、LVGL.Simulator：
  均为 0 个残留进程
- 正确证据文件位于活动 worktree；误建的兄弟仓库文件不存在

## 9. 待独立验收

本实现会话不改变 P2-5 阻塞结论。下一会话必须按
.claude\prompt-P2-5-verification.md 重跑完整状态链、RTT 决定性行、fresh 包
一致性、无 WDT/HardFault、进程/路径审计及 AC5 现状。若结果冲突，以原始
J-Link、RTT 和回读证据为准，并保持 fail-fast。
