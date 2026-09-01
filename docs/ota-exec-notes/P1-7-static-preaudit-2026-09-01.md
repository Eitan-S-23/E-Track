# P1-7 离线静态前置审计（2026-09-01）

**会话性质**：非实现独立验收会话（承接 P2-6 收口）。

**本文不是 P1-7 的验收结论。** 看板 P1-7 的验收 1-5 全部需要 J-Link 实测或用户
物理配合，本会话无硬件授权，因此只做**离线可判定部分**的静态前置审计：确认三个
缺陷的修复形态确实落在源码里、三条红线未被踩、构建侧依赖已补齐。硬件轮次开始前
先把这些闭合，可以避免再出现"上了硬件才发现改错方向"的往返。

---

## 1. 审计项与结论

| # | 审计项 | 依据 | 结论 |
| --- | --- | --- | --- |
| S1 | 缺陷 A 提频已落源码 | `boot/platform/at32/boot_platform_at32.c` `boot_platform_init()` | PASS |
| S2 | 红线 2 调用顺序 | 同上 | PASS |
| S3 | `BOOT_RECOVERY_HOLD_MS` 未被改动 | `boot_platform_at32.c:13` = `3000` | PASS |
| S4 | 缺陷 B 修复形态 + 红线 3 | `MDK-ARM_F435/Platform/HAL/HAL_Power.cpp` `Power_Init()` | PASS |
| S5 | 缺陷 C 修复形态 | `boot/src/boot_main.c` | PASS |
| S6 | 红线 1 未被踩（SHA 校验未跳过/弱化） | `boot/src/boot_state_machine.c` | PASS |
| S7 | 构建侧依赖补齐 + `boot.bin <= 64KiB` | `MDK-ARM_F435/cmake-generated/CMakeLists.txt`、磁盘产物 | PASS（见 §3 局限） |

### S1 / S2 提频与调用顺序

`boot_platform_init()` 当前序列为：

```text
system_clock_config()          <- 第一行
system_core_clock_update()
g_boot_millis = 0
SysTick_Config(system_core_clock / 1000)
configure_power_hold()
configure_recovery_key()
boot_platform_delay_ms(2)      <- PA15 上拉稳定延时
configure_uart()
configure_eeprom_gpio()
```

与红线 2 要求的「`system_clock_config()` → `system_core_clock_update()` →
`SysTick_Config()` → `configure_power_hold()` → …」逐项一致。两个致命前提都被满足：
`crm_reset()` 发生在任何 `crm_periph_clock_enable()` 之前；`SysTick_Config()` 取到的
是提频后的 `system_core_clock`，故 boot 内毫秒计时不会被压缩 36 倍。

### S3 恢复键时长常量

`BOOT_RECOVERY_HOLD_MS = 3000`（`boot_platform_at32.c:13`）未被改动，
`boot_platform_recovery_key_held()` 仍以该常量作为持续按住的判据。这是红线 2 的
语义落点——提频若顺序写错，这里会实际退化成 ≈83ms。**该常量正确不等于实测正确**，
真值仍必须由验收第 3 项在硬件上测。

### S4 缺陷 B 与红线 3

`Power_Init()` 以 `#if defined(OTA_TARGET_APP)` 分岔：

- OTA 路径：只 `pinMode(CONFIG_POWER_EN_PIN, OUTPUT)` + `digitalWrite(HIGH)`，
  **不再拉低 PD2**，因此不会在 boot 已锁存后主动撤除供电保持 1 秒。
- `#else` legacy 路径：`LOW → delay(CONFIG_POWER_WAIT_TIME) → HIGH` 的上电防抖
  **原样保留**，符合红线 3「不得删除防抖逻辑本身，只允许在 boot 交接路径跳过」。

### S5 缺陷 C

`boot/src/boot_main.c` 在状态机之前**不存在** `boot_platform_recovery_key_held()`
调用。该函数在 boot 内的唯一调用点是 `receive_physical_recovery()`（:106），而后者的
唯一调用点是 `outcome.action == BOOT_STATE_ACTION_PHYSICAL_RECOVERY` 分支
（:188-199）。即恢复模式入口只由状态机判定，与契约 `PLAN-OTA.md` §4/§5.3 一致。

### S6 红线 1

`validate_internal_app()` 在 `boot_state_machine.c` 中有 8 个调用点
（:536 / :562 / :579 / :595 / :657 / :683 / :789 / :826），CONFIRMED 分支的整镜像
SHA-256 校验未被跳过、未加旁路开关、未按 vcode 或状态短路。提速是靠提频取得的，
不是靠削弱校验——这正是立卡时明确禁止的那条捷径。

### S7 构建侧

`BOOT_PROJECT_SOURCES` 已含本修复所需的两个新依赖（CMakeLists.txt:567-568）：
`../Platform/Core/at32f435_437_clock.c` 与
`../RTE/Device/-AT32F435RGT7/at32f435_437_pwc.c`。

磁盘产物 `MDK-ARM_F435/cmake-generated/build-gcc-release/boot/X-Track-Boot.bin`
= `14724B` ≤ `65536B`，P1-1 的 64KiB 硬约束不回退。

---

## 2. 仍需硬件/用户的 5 项（本会话无法判定）

| 验收项 | 需要什么 |
| --- | --- |
| 1. 复位到 RTT 签名 ≤1.5s（基线 15.5s） | J-Link 会话 |
| 2. PD2 锁存拉高后不再出现回 0 样本 | J-Link 会话 |
| 3. 恢复键仍需持续按住 ≥3s，短按不进入；boot 侧 1000ms 延时为真实 1s | J-Link 会话 |
| 4. boot 主频实测 288MHz（DWT CYCCNT 或 CRM_CFG sclksts） | J-Link 会话 |
| 5. 电池供电（拔掉 J-Link 与 USB）按开机键正常开机 | **用户物理配合** |

第 5 项不可由任何 agent 代做：它要求拔掉一切外部供电，而外部供电正是当初掩盖
该缺陷的原因。前 4 项可在一次硬件会话内连测。

---

## 3. 方法与局限（如实登记）

- 本审计**只读源码与既有磁盘产物，未重新构建、未上硬件**。
- S7 的尺寸结论取自既有产物（构建时间 2026-08-15 00:16），其晚于全部 boot 源码
  mtime（2026-08-14 14:56）；`boot/` 自 `0023e5f`(2026-08-05) 起无新提交且工作树
  干净。据此判定该产物与当前源码一致。**这是基于 mtime 与提交序的推断，不是重建
  验证**；硬件轮次必须以本轮实际烧录镜像的尺寸与哈希为准，不得引用本节数字。
- S1-S6 是"修复形态存在且未踩红线"的静态判定，**不能替代任何一项实测**。源码正确
  与器件行为正确是两件事，P1-7 的全部数值结论仍属于硬件会话。

## 4. 顺带发现（未处置，需授权）

- 仓库根存在两个被 `.gitignore` 忽略的历史残留目录：`.codex-worktree-p1-6-20260729/`
  与 `.codex-worktree-p2-20260729/`，内含旧版 boot 源码副本。检索 boot 常量时会命中，
  易与生产树混淆。**本会话未清理**（属既有产物，需用户授权）。
- `git worktree list` 另有两个注册在项目根之外的 worktree：
  `D:/github/my/E-Track-p2-4-20260731`、`D:/github/my/E-Track-p2-5-20260801`。
  位于写入边界之外，本会话未触碰。
