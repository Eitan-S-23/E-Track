# P2-5 真机 SD 升级闭环验收报告（第三轮 / 独立验收会话）

**验收人**: Claude（非实现会话，独立验收）
**验收日期**: 2026-08-05 19:00 – 21:32
**工作目录**: `D:\github\my\E-Track-p2-5-20260801`（worktree）
**分支**: `p2-5-20260801` ｜ **HEAD**: `0023e5f`（未 commit / 未 push）
**依据提示词**: `.claude/prompt-P2-5-verification.md`
**证据目录**: `.cache/p2-5-verification/`

---

## 1. 验收结论：**不通过**

卡内验收硬条件为「真机完整一轮 SD 升级：STAGED → 重启 → APPLYING →
TEST_BOOT → CONFIRMED，RTT 全程留痕」。

**该闭环本轮无法在真机走通**，原因不是 OTA 状态机本身，而是**升级流程的入口
被一个 App 侧看门狗缺陷阻断**：在 SD 升级页点击"文件管理"按钮，设备黑屏重启，
无法进入文件列表选择 `.etu` 包，升级流程发不起来。

该缺陷已在**两次独立启动**上采到同一复位原因 `Reset: NRST WDT`，可稳定复现。
详细根因链与证据见 `.cache/p2-5-verification/blocker-filemanager-wdt-reset.md`。

**判定**：P2-5 **不通过**，卡置 `阻塞`，退回实现会话修复后重验。
本会话**未修改任何实现代码**绕过该缺陷（OTA 规约 §3 独立性要求）。

---

## 2. 验收环境与产物清单

### 2.1 真机与工具

| 项目 | 值 |
|---|---|
| 目标 MCU | AT32F435RGT7 |
| 调试器 | 板载 J-Link（ARM-OB STM32 2012） |
| J-Link 工具 | `C:\Users\SU\SEGGER\JLink_V818\` |
| SWD 速度 | 1000 kHz |
| RTT 控制块地址 | `0x20045E34`（GCC App map `_SEGGER_RTT`） |
| 设备侧 App | GCC Release 编译版本，vcode 20800 |

**本轮全程未烧录、未执行 `h`（halt）**，只做 RTT 采集与 `mem8`/`mem32` 只读。
提示词步骤 0 原脚本含 `h`，按 AGENTS.md J-Link 红线（halt 会打断 SD 传输、
可能把卡挂死成软复位救不回的 `SD_IsReady=0` 状态）予以剔除；签名验证只需
`mem8`，已成功，无需 halt。该偏离已在步骤 0 证据文档中记录。

### 2.2 落盘产物（哈希与时间戳实测）

| 文件 | 大小 | 落盘时间 | SHA256 |
|---|---|---|---|
| `.cache/p2-5-verification/rtt-A-baseline.log` | 559 B | 2026-08-05 20:15:40 | `5d60194838cdef790693bc1813ac0fde9d02a32a5ee7b19ab2103f22f404bb11` |
| `.cache/p2-5-verification/rtt-blocker-repro-01.log` | 287 B | 2026-08-05 21:07:12 | `fc408b70b4c05ad55155b7909e9192f0d8f84c3e157d06d68cbe5f2004b738b7` |
| `.cache/p2-5-verification/rtt-final-01.log` | 0 B | 2026-08-05 20:45:54 | `e3b0c442...7852b855`（空文件，无效采集，保留以示未隐藏） |
| `.cache/p2-5-hw/P2-5-FULL.etu` | 281042 B | 2026-08-04 17:37:55 | `9142837d527e99ff92814265ddd470853d99a2320eeaf546ade11a1af44635ed` |

采集命令（`sha256sum` / `stat` 实测，2026-08-05 21:32）：
```bash
sha256sum .cache/p2-5-verification/*.log .cache/p2-5-hw/P2-5-FULL.etu
stat -c '%n  %s B  %y' .cache/p2-5-verification/*.log .cache/p2-5-hw/P2-5-FULL.etu
```

### 2.3 文档产物

| 文件 | 用途 |
|---|---|
| `.cache/p2-5-verification/step0-baseline-evidence.md` | 步骤 0 前置检查全部实读输出 |
| `.cache/p2-5-verification/blocker-filemanager-wdt-reset.md` | 阻塞缺陷根因链与复现证据（**本轮核心产物**） |
| `.cache/p2-5-verification/capture-rtt.ps1` | 单段 RTT 采集脚本 |
| `.cache/p2-5-verification/capture-rtt-continuous.ps1` | 跨重启连续采集脚本（分段编号，避免覆盖） |
| `.cache/p2-5-verification/jlink-rtt-sig.jlink` 等 3 个 | 只读 `mem8`/`mem32` 脚本 |
| 本文件 | 验收报告 |

### 2.4 进程清理

采集结束后核对无残留（多 `JLinkRTTLogger` 会抢同一 RTT 读指针导致丢行；
`JLinkGUIServer` 会在 `JLink.exe` 退出后驻留并触发 harness 单实例断言）：
```
NO_JLINK_PROCESS
```

---

## 3. 步骤 0 前置检查：通过

完整实读输出见 `.cache/p2-5-verification/step0-baseline-evidence.md`，摘要：

| 检查项 | 结果 | 证据来源 |
|---|---|---|
| RTT 地址 | `0x20045E34` | GCC App map `_SEGGER_RTT` 符号行 |
| RTT 签名 | `53 45 47 47 45 52 20 52 54 54` = `SEGGER RTT` | JLink `mem8 0x20045E34 16` 实读 |
| 基线 vcode | **20800** | flash `0x08010408` 实读 `0x00005140` |
| fw_header magic | `ETFW`（`0x57465445` LE） | flash `0x08010400` 实读 |
| 目标 vcode | **20801** | `Tools/etu_unpack.py` 实测 |
| 候选镜像长度 | 598680 B | unpack 输出 `candidate_len` |
| 候选镜像 SHA256 | `4a329c374fb91aa68567cae1485bf9b42ff32ed5ce3b22e5f848e04c4526a375` | unpack 输出 |
| BCB 状态 | **CONFIRMED (4)** | RAM `0x20045EDC` 实读 `04 01 01 00` |
| 残留进程 | 无 | `NO_JLINK_PROCESS` |

**版本跃迁预期**：20800 → 20801。基线与目标不同，满足"能区分升级后确认与
升级前就已 CONFIRMED"的前提。

**BCB=CONFIRMED 的意义**：满足 OTA 规约 backup 锁定规则（仅 CONFIRMED 态允许
发起新 OTA），设备本可进入升级流程 —— 阻断不在门禁，而在 UI 入口。

---

## 4. 步骤 1-2 段 A 基线采集：通过

`.cache/p2-5-verification/rtt-A-baseline.log`（559 B，20:15:40）全文：

```
========================================
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST POR
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20800
LiveMap start: tiles=0 imgCache=8 view=240x320
LiveMap stat: update=46 reload=1 lineHit=614 lineMiss=42 lineReadKB=336 sdMs=39 refrMs=287 refrCnt=24 refrPxK=628
LiveMap stat: update=51 reload=0 lineHit=16 lineMiss=0 lineReadKB=0 sdMs=0 refrMs=171 refrCnt=9 refrPxK=406
```

判定要点：
- `BASELINE_VCODE` = **20800**，与 flash 实读一致 ✅
- 复位原因 `Reset: NRST POR`（上电复位），**非**看门狗 ✅
- `OTA: HANDOFF vtor=0x08010000` 说明 boot 正常交接 ✅
- QSPI 白名单通过，OTA 通道可用 ✅
- LiveMap 统计行正常产出（`lineHit`/`sdMs` 非零），说明 SD 卡挂载正常、
  设备功能正常运行 ✅

段 A 同时确立了本轮的**负向对照**：正常启动打印 `POR`，证明
`PrintResetReason()` 末尾的 `crm_flag_clear(CRM_ALL_RESET_FLAG)`
（`USER/main.cpp:144`）确实把标志清干净了，后续采到的 `WDT` 只能来自紧邻其前
的那一次复位，不是历史残留。

---

## 5. 步骤 3 触发升级：**阻断**

### 5.1 现象

用户在设备上进入 SD 升级页，点击"文件管理"按钮 → **设备黑屏并重启**，
无法进入文件列表，`P2-5-FULL.etu` 选不到，升级流程发不起来。

### 5.2 复位原因实测：看门狗复位

`.cache/p2-5-verification/rtt-blocker-repro-01.log`（287 B，21:07:12，
SHA256 `fc408b70b4c05ad55155b7909e9192f0d8f84c3e157d06d68cbe5f2004b738b7`）全文：

```
========================================
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 systick=0x00000000 icsr=0x00000000 iser=0x00000000 ispr=0x00000000
Reset: NRST WDT
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: BCB already CONFIRMED vcode=20800
```

该缺陷共采到**两次独立启动**的同一复位原因：

| 次序 | 时间 | 产物 | 状态 |
|---|---|---|---|
| 第 1 次 | 20:29 | `rtt-crash-filemgr-01.log`（287 B） | 原始文件被本会话误删，内容已在删除前于会话中完整读取（见 §9） |
| 第 2 次 | 21:07 | `rtt-blocker-repro-01.log`（287 B） | **产物在盘上**，内容与第 1 次逐字一致 |

操作侧确认：用户在 21:05:31–21:07:12 采集窗口内点击"文件管理"按钮，
并回报"点击了，还是崩溃"，与该日志时间与内容完全对应。

**两次复位原因均 = `NRST WDT`（看门狗复位），缺陷可稳定复现。**

### 5.3 根因链（代码事实，逐条可核）

**(1) App 侧有一只 10 秒独立看门狗，任何 BCB 状态下都在跑。**

`USER/HAL/HAL_Config.h:222-224`
```c
#define CONFIG_WATCH_DOG_ENABLE     1
#if CONFIG_WATCH_DOG_ENABLE
#  define CONFIG_WATCH_DOG_TIMEOUT (10 * 1000) // [ms]
```

`USER/HAL/HAL.cpp:141-142`（在 `HAL_Init()` 内，早于任何 OTA 判定）
```c
    uint32_t timeout = WDG_Init(CONFIG_WATCH_DOG_TIMEOUT);
    taskManager.Register(WDG_ReloadCounter, CONFIG_WATCH_DOG_TIMEOUT / 10);
```

> **这不是 boot 侧那只 TEST_BOOT 看门狗。** boot 侧的狗只在
> `boot/src/boot_main.c:203-204` 于 `outcome.bcb.state == BCB_STATE_TEST_BOOT`
> 时才启动；本轮 BCB=CONFIRMED，boot 狗不在跑。触发本次复位的是 App 自己的狗。

**(2) 喂狗完全依赖主循环持续转动。**

`USER/HAL/HAL.cpp:157-160`
```c
void HAL::HAL_Update()
{
    taskManager.Running(millis());
}
```

`USER/main.cpp:176-184`
```c
static void loop()
{
    HAL::HAL_Update();      // ← 唯一喂狗驱动点（经 taskManager）
    lv_task_handler();      // ← 文件浏览在这里面同步跑完
    ...
}
```

已核对定时器中断 `HAL_TimerInterrputUpdate()`（`USER/HAL/HAL.cpp:40-45`）
只做 `Power_Update` / `Encoder_Update` / `Audio_Update`，**不喂狗**——
主循环是唯一喂狗路径，这是最后一个可能的证伪点，已排除。

**(3) 文件浏览是阻塞式全目录扫描，且遍历上界失效。**

`USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp:567-591`
```c
    while (rowCount < ROW_MAX)
    {
        if (lv_fs_dir_read(&dir, name) != LV_FS_RES_OK || name[0] == '\0') break;
        if (IsHiddenEntry(name)) continue;                         // ← 不增 rowCount
        bool isDir = name[0] == '/';
        const char* clean = CleanName(name);
        if (!isDir && !ota_sd_has_etu_extension(clean)) continue;  // ← 不增 rowCount
        ...
        AddRow(clean, path, isDir, false);
    }
```

循环上界写的是 `rowCount < ROW_MAX`，但**被过滤掉的条目不增加 `rowCount`**
（隐藏项 `continue`、非 `.etu` 文件 `continue`、路径超长 `continue`）。因此在
一个含大量非 `.etu` 文件的目录上，该循环会遍历**整个目录**，条目数不受
`ROW_MAX` 约束。整个过程在 LVGL 事件回调内同步完成，`lv_task_handler()` 不返回。

**(4) 结论**：SD 目录扫描耗时 > 10 秒 ⇒ `WDG_ReloadCounter` 断供 ⇒ IWDG 超时
复位 ⇒ 表现为"点文件管理按钮后黑屏重启"，重启后 RTT 打印 `Reset: NRST WDT`。
与 §5.2 实测证据完全一致。

**(5) HardFault 已排除**：`USER/HAL/HAL_Config.h:128-129` 中
`CONFIG_HARDFAULT_AUTO_REBOOT 0`，HardFault 不会自动重启（会挂死），
因此"黑屏并重启"这一现象在本工程内只能由复位源解释，而复位源实测为 WDT。

### 5.4 与 F1 缺陷的关系：无关，F1 修复在位

F1（第一轮独立验收打回项）指 boot 侧 TEST_BOOT 看门狗的喂狗被错误地放在
`if(state == BCB_STATE_TEST_BOOT)` 分支内。本会话静态核对 `USER/main.cpp:69-73`：

```c
    if(wdt_configured)
    {
        HAL::OTA_WatchdogFeed();
        ota_confirm_health_feed(&g_ota_health);
    }

    if(state == BCB_STATE_TEST_BOOT)
    { ... }
```

喂狗在状态判断**之外**，**F1 修复确实在位**，与第二轮验收结论一致。
本轮是另一只狗（App 侧 `CONFIG_WATCH_DOG_*`）在另一条路径（文件浏览）上的
**独立新缺陷**，不是 F1 回归。

---

## 6. 步骤 4-6：未执行（被 §5 阻断）

| 步骤 | 内容 | 状态 |
|---|---|---|
| 步骤 4 | 设备重启（APPLYING 阶段） | **未执行**：STAGED 未提交，无可 apply 的候选 |
| 步骤 5 | TEST_BOOT → CONFIRMED（段 B 采集） | **未执行**：无升级动作，段 B 无采集窗口 |
| 步骤 6 | TEST_BOOT 期间拒绝新 OTA | **未执行**：设备从未进入 TEST_BOOT |

段 B 未采集是**阻断的必然后果**，不是采集失误：升级从未发起，就不存在
"重启后的首启"这一时刻。`.cache/p2-5-verification/rtt-final-01.log`（0 B）
是阻断确认过程中的一次空采集，无效，一并落盘不作删除以示未做取舍。

---

## 7. 步骤 7-8 判定表

提示词步骤 8 的 9 项通过条件，逐项对号：

| # | 条件 | 结果 | 证据 |
|---|---|---|---|
| 1 | 升级前基线 vcode 已记录且与目标不同 | ✅ 通过 | 20800（flash 实读）vs 20801（unpack 实测） |
| 2 | 屏幕依次出现 `CANDIDATE VERIFY` → `BACKUP + STAGED` | ❌ **不可达** | 未进入文件列表，升级未发起 |
| 3 | 导入结果页显示成功 | ❌ **不可达** | 同上 |
| 4 | 重启后 RTT 出现 `OTA: HANDOFF vtor=0x08010000` | ⚠️ 不适用 | 该行在两段日志中均出现，但来自**崩溃后重启**而非升级后重启，不能算作条件 4 的满足 |
| 5 | RTT 出现 `OTA: TEST_BOOT confirmed vcode=20801`（**决定性**） | ❌ **未出现** | 两段日志均只有 `OTA: BCB already CONFIRMED vcode=20800` |
| 6 | 该 vcode 等于包内目标 vcode | ❌ 未满足 | 实测仍是 20800，未跃迁 |
| 7 | RTT 无 `Reset: WDT` | ❌ **失败** | `rtt-blocker-repro-01.log` 明确含 `Reset: NRST WDT`，两次独立复现 |
| 8 | RTT 无 `BOOT: hold recovery key` | — 无法观测 | boot 日志走 UART5 不走 RTT；本轮未接 UART5。设备每次都进了 App（有 `HANDOFF` + App 日志），可间接判定未落入物理恢复 |
| 9 | 设备升级后功能正常 | ❌ 不适用 | 未升级；且点文件管理即复位，该路径功能不正常 |

**通过条件要求全部满足。条件 2/3/5/6/7/9 未满足，其中条件 5（决定性证据）
与条件 7（负向硬条件）明确失败 ⇒ 验收不通过。**

提示词失败排查节已预置该判据：出现 `Reset: WDT` 则「P2-5 判定为**不通过**，
退回实现会话」。需要指出的是，提示词把该签名归因于 F1；本轮实测与代码核对
表明它来自**另一只看门狗、另一条代码路径**（见 §5.4），修复方向与 F1 不同，
不能按 F1 的改法处理。

---

## 8. 与既有阻断的关系

| 阻断编号 | 内容 | 本轮状态 |
|---|---|---|
| F1 | 确认后停止喂狗（TEST_BOOT 分支内喂狗） | **已关闭**（第二轮验收结论，本轮静态复核在位） |
| **F4（本轮新增）** | 点击文件管理按钮触发 App 侧 10s IWDG 复位，升级入口不可用 | **开放**，阻断卡内验收硬条件 |

F4 的完整证据文档：`.cache/p2-5-verification/blocker-filemanager-wdt-reset.md`
（9795 B，21:19 落盘）。

### 8.1 给实现会话的修复方向（仅建议，本会话不改代码）

根因是"阻塞式全目录扫描跑在 LVGL 回调里，饿死 10 秒喂狗"。三个方向任选或组合：

1. **限制遍历总数**：`LoadFiles()` 的 `while` 增加独立的"已读条目数"计数器
   （与 `rowCount` 分开），到达上限即 `break`，使被过滤条目也计入上界。
   最小改动，直接消除无界遍历。
2. **扫描期间喂狗**：在遍历循环内周期调用喂狗（或 `HAL::HAL_Update()`），
   使长扫描不再触发 IWDG。治标，且需注意重入 LVGL 的风险。
3. **改为分帧/异步加载**：每次 `lv_timer` 回调只读固定条数，分多帧填表。
   最彻底，同时解决 UI 卡顿，改动量最大。

修复后**必须重跑本文件 §5.2 的采集方法**：点击文件管理按钮后不再出现
`Reset: NRST WDT`，且文件列表正常显示，方可继续走 §6 的段 B 采集。

### 8.2 未量化项（明确留给实现会话）

目录扫描实际耗时与 SD 卡根目录条目数**未量化**。量化需要在固件里插桩计时，
属于改实现代码，超出独立验收会话职权（OTA 规约 §3）。留给实现会话在修复时
一并测定超时裕度。

---

## 9. 会话操作失误声明

诊断过程中我执行了
```bash
rm -f .cache/p2-5-verification/rtt-crash-*.log
```
意图清理无效的空采集文件，但该通配符**同时删除了含关键证据的
`rtt-crash-filemgr-01.log`**（287 B，第 1 次崩溃日志）。这是本会话的操作失误，
如实记录，不做淡化。

补偿（已全部完成）：
- 该文件完整内容在删除前已于会话中读取，原文完整抄录于本文件 §5.2 与阻塞
  文档 §2.2 第 1 次；
- 根因判定不依赖该日志 —— 判定链是代码事实（§5.3），日志仅为佐证；
- **已补采**：21:05:31 重新挂 logger，用户再次点击后采到
  `rtt-blocker-repro-01.log`（287 B，SHA256
  `fc408b70b4c05ad55155b7909e9192f0d8f84c3e157d06d68cbe5f2004b738b7`），
  内容与被删文件逐字一致，原始产物已恢复到盘上。

---

## 10. 独立性与边界声明

- **未修改任何实现代码**。工作区唯一改动是
  `MDK-ARM_F435/RTE/_X-Track-App-AC5/RTE_Components.h`（Keil 工具在既往会话
  自动生成的残留），非本会话主动编辑，也与本判定无关。
- **未执行 `git commit` / `push` / `merge`**（OTA 规约 §5）。HEAD 仍为 `0023e5f`。
- **未烧录固件、未执行 halt**，全程只读 RTT 与内存。
- 所有产物落在 worktree `D:\github\my\E-Track-p2-5-20260801` 内，
  未使用 `D:\tmp`、`%TEMP%` 或兄弟仓库。
- 未使用裸 `git stash` / `git stash pop`。
- 采集结束无残留 J-Link 进程（`NO_JLINK_PROCESS`）。

---

## 11. 回写记录

- `PLAN-OTA-EXEC.md` P2-5 卡：`进行中` → **`阻塞`**，写明 F4 缺陷与阻断点；
  P2 计数保持 `4/6`（P2-5 本就未计入完成）。
- `PLAN-OTA-EXEC.md` §10 会话日志：追加本轮验收记录（含时间戳）。
- §9 变更登记表：**不登记**。F4 是实现缺陷，不触碰任何冻结契约
  （`PLAN-OTA.md` / `docs/ota-binary-contracts.md` 对文件浏览与 App 侧
  `CONFIG_WATCH_DOG_*` 均无条款），按 §0.4 无需登记。

---

**报告生成时间**: 2026-08-05 21:32
**报告路径**: `docs/ota-exec-notes/P2-5-hardware-verification-2026-08-05.md`
