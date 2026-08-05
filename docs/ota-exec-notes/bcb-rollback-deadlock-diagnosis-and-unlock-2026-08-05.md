# P1-7 真机 BCB ROLLBACK 死锁诊断与解锁（2026-08-05）

> 会话角色：诊断+解锁会话（承接 P1-7 两个真机调试 agent 的工作）。
> 结果：诊断证据链逐行复核闭合；已按官方 P1-6 通道完成解锁，设备恢复进 App。
> 归属：P1-7 卡（本 worktree 看板 2026-08-04 新立；主仓库看板尚无此卡，
> 因立卡修改未提交——曾被误判"卡不存在"，特此更正）。

## 1. 事故时间线（综合前两个 agent 汇报）

1. 实现 agent 完成缺陷 A（boot 提频 288 MHz，真机实测 `CRM_CFG=0x900A` 生效）
   与缺陷 B（PD2 不再重复锁存）后，**烧录了未 finalize 的 App**（0x400 处为
   0xFF 占位头，未经 `etu_pack.py finalize` 回填 ETFW）。
2. 当时 BCB 为 CONFIRMED → boot 校验内部 App 失败 → 进入回滚并持久化。
3. 此后即使重烧 finalize 合法 App，boot 仍停在恢复模式等待，无法进 App。

## 2. 死锁证据链（本会话逐行复核，全部属实）

| # | 结论 | 证据位置 |
|---|------|----------|
| 1 | CONFIRMED 态校验内部 App 失败 → `begin_rollback()` | `boot/src/boot_state_machine.c:578-588` |
| 2 | `begin_rollback()` 把 `state=ROLLBACK`、`copy_phase=BCB_COPY_ROLLBACK` 经 `commit_record→bcb_commit` 持久化进 EEPROM | 同文件 `:256-273` |
| 3 | ROLLBACK 分支只校验外部 backup/recovery 槽，**从不校验内部 App** | 同文件 `:713-761` |
| 4 | 两槽均无效 → `return_recovery(BOOT_STATE_STATUS_SLOT)` → PHYSICAL_RECOVERY | 同文件 `:767-770` |
| 5 | 外部恢复槽从未安装（bootstrap 输出 `P1_5_EXTERNAL_RECOVERY_SLOT=NOT_INSTALLED`） | `Tools/jlink/deploy-ota-bootstrap.ps1:126` |
| 6 | 故 ROLLBACK 态下重烧内部 App 无效，状态自锁 | 由 3+4+5 推出 |

**关键澄清**：finalize 缺失是入锁诱因，不是卡死原因；卡死原因是 ROLLBACK
自锁 + 恢复槽缺失。反复重烧 App 属方向性错误。

## 3. 解锁面（本会话查明）

- **干净复位态**：`boot_state_machine.c:534-544`，BCB 仲裁 `NONE`（两副本均
  无效）→ 校验内部 App → 合法则自动 `commit_confirmed` 并跳转。bootstrap
  首次部署即靠此路径自愈（`deploy-ota-bootstrap.ps1:148` 以
  `OTA: BCB already CONFIRMED` 为验收行）。
- **EEPROM 只能由 MCU 侧代码写**：BCB 在 I2C EEPROM（0x50，256 B，8 B/页），
  boot 用软件位拽驱动（`boot/platform/at32/boot_platform_at32.c:13-17,200-290`）；
  J-Link 无法直接写（前会话该结论正确）。
- **官方擦除通道**：`OTA_P1_6_OPCODE_CLEAR_BCB`
  （`boot/src/boot_p1_6_test.c:707-719`），先 `validate_internal_app` 不合法
  即拒绝（防变砖保险），合法才擦两副本。投递 = J-Link 向 RAM 控制块
  （`OTA_RAM_ORIGIN+LENGTH-512`）写命令+CRC+magic，boot 开机轮询执行。
  主机侧封装：`Tools/jlink/p1-6-common.ps1`（`Invoke-P16Command`）。
  钩子由 `P1_6_TEST_ENABLE` 门控（`boot_main.c:142`、
  `cmake-generated/CMakeLists.txt:684-686`），生产 boot 不含。
  `test-p1-6-matrix.ps1:330` 证实 CLEAR_BCB 是验收矩阵标准准备步骤。
- **设计的物理恢复出口**（本次未用）：PHYSICAL_RECOVERY 循环等 PA15 按住
  3 秒后走 YMODEM 串口收恢复镜像（`boot_main.c:100-120`、
  `boot_platform_at32.c:134-146`、`boot_recovery.c:243`、`boot_ymodem.c`）。

## 4. 路线对比与选择

| 路线 | 动作 | 结论 |
|------|------|------|
| R1 CLEAR_BCB（**采用**） | 测试 boot + RAM 命令 + 回烧生产 boot | 全自动、零新代码、风险最低 |
| R2 恢复键+YMODEM | 用户按键 3s + 串口发镜像 | 需人工与连线，留作后备/独立验收项 |
| R3 INSTALL_SLOT 走完 ROLLBACK | 装恢复槽让回滚自然完成 | 动作最大，属 P1-6 矩阵既有内容 |

用户要求"无需人工参与"，选 R1。

## 5. 解锁执行记录（2026-08-05 凌晨）

- 测试 boot 构建：`.cache/p1-7-unlock/gcc-test/`（`P1_6_TEST_ENABLE=ON`，
  bin=18760 B ≤64 KB，`P1_6_CTRL` 512 B 段就位）；生产 boot 沿用前会话产物
  `.cache/p1-7-unlock/gcc-release/boot/X-Track-Boot.bin`（14768 B，含提频）。
- 驱动脚本：`.cache/p1-7-unlock/unlock-clear-bcb.ps1`（只调 harness 函数；
  失败自动回烧生产 boot）。
- 第 1 轮：烧测试 boot 后被 harness 单实例断言拦截（`JLinkGUIServer` 残留，
  JLink.exe 退出后自动驻留）→ 失败保护生效，生产 boot 自动回烧，设备状态
  未变。修正：步骤间清理 `JLinkRTTLogger`/`JLinkGUIServer` 残留。
- 第 2 轮（成功），关键输出：
  ```text
  P1_7_UNLOCK_CLEAR_BCB=PASS status=2 detail=0 polls=1
  P1_7_UNLOCK_RTT_ADDRESS=0x20045E34
  P1_7_UNLOCK_RESET=PASS pc=134555534 vtor=134283264 cfsr=0
  P1_7_UNLOCK_CONFIRMED=PASS vcode=20800
  P1_7_UNLOCK=PASS run_directory=.cache/p1-7-unlock/run-20260805-044335
  ```
  `vtor=134283264 = 0x08010000`（App 向量表基址，交接成功）；RTT 匹配
  `OTA: HANDOFF vtor=0x08010000` 与 `OTA: BCB already CONFIRMED vcode=20800`。
- 终态：生产提频 boot + finalize App(vcode=20800) + BCB CONFIRMED，App 运行。
- 残留清理：JLinkRTTLogger/JLinkGUIServer 已清，J-Link 进程数=0。

## 6. 后续与债务

- P1-7 验收 1-5（启动 ≤1.5 s、PD2 无回落、恢复键 3 s、288 MHz、电池开机）
  仍待非实现会话执行；其中第 5 项需用户物理配合。
- 烧录 halt 可能挂死 SD 卡（AGENTS.md 红线）：若瓦片不显示/`SD_IsReady=0`，
  拔插 SD 或整机断电，勿当代码 bug。
- **系统性债务**：外部恢复槽 `NOT_INSTALLED` 使"CONFIRMED+App 坏"直接落入
  PHYSICAL_RECOVERY 死等。建议另立卡：安装恢复槽，或在部署清单中强制
  槽安装步骤。
- 教训（防复发）：真机烧 App 前必须 finalize（AGENTS.md 已有规定，事故即
  违反此条触发）；进 ROLLBACK 后勿再反复重烧 App，先读 BCB 状态定位。
