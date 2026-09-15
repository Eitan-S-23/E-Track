# P3-3 实机前置阻断：BCB vcode 与运行镜像 version_code 不一致 —— 澄清与最小恢复方案（2026-09-13）

> 依据：用户 2026-09-13 八条意见第 2 条——BCB 不一致提升为实机前置阻断，
> 先核对原始证据与 BCB 仲裁结果，确认后提交最小恢复方案；
> 不得删除一致性检查、直接改 BCB 数字或擅自烧录"对齐"。
> 本文为澄清与方案文档，**未执行任何真机操作**。

## 1. 观测事实（已有原始证据，零新增观测）

来源：`docs/ota-exec-notes/P3-3-t1a-jlink-board-identification-2026-09-12.md`（只读轮，证据文件在 `.cache/p3-3-t1a-step1-r1/jlink/`，SHA 见该文 §7）。

| 项 | 观测值 | 证据 |
| --- | --- | --- |
| 板上 App fw_header version_code | **30200**（3.2.0） | `app16k.bin` 转储 off8 实读 `0x75F8`；header_crc32 与双零法全镜像 SHA 均重算一致（该文 §2.2） |
| BCB CONFIRMED cur_vcode | **20801**（2.8.1） | App 启动期 RTT 自报 `OTA: BCB already CONFIRMED vcode=20801`（`rtt-terminal.log`，287 B，sha256 前 16 `320e698d341a7d21`） |
| 差值 | 20801 ≠ 30200，**不一致成立** | 两值来自同轮只读观测，互为独立通道（QSPI 转储 vs RTT 自报） |

不一致**确实成立**，不是记录笔误。最直白的读法（该文 §6 已登记、本轮未推翻）：
该板当前镜像不是经 OTA 确认流程落地的——BCB 的 CONFIRMED 记录停留在 2.8.1，
之后 App 被 J-Link 直烧为 3.2.0，BCB 未随之更新。

## 2. 为什么这是实机升级闭环的硬阻断（代码证据链）

### 2.1 升级提交路径会撞上一致性检查

SD 升级页提交链：`OtaUpdate.cpp` CommitStaged（`USER/App/Utils/OtaUpdate/OtaUpdate.cpp:549-576`）：

1. `RequireConfirmedBcb()`（OtaUpdate.cpp:549）只检查 BCB **state==CONFIRMED**
   （OtaUpdate.cpp 内 `RequireConfirmedBcb` 实现）——**不比对 vcode**，本阻断在此层不触发；
2. 真正的检查在 `HAL::OTA_BackupStage` → `ota_backup_stage`
   （`Libraries/OTA/ota_backup.c:330`）。其 §2b（`ota_backup.c:385-391`）：

   ```c
   /* 2b) 当前 CONFIRMED BCB cur_vcode 必须等于当前 App fw_header 的 vcode。
    * 不一致说明 BCB 已过期/错位，禁止据此自拷备份或提交 STAGED。 */
   if (current.cur_vcode != app_header.version_code)
   {
       result = OTA_BACKUP_ERR_APP_HEADER;
       ...
   }
   ```

   板上 20801 != 30200 → `OTA_BACKUP_ERR_APP_HEADER` → CommitStaged 以
   `stage:app_header` 落 `OTA_SD_ERR_STAGED_COMMIT` 失败。

即：**toy/真包任何一次走完整闭环，只要走到提交（CommitStaged），都会被此检查
拒绝**。这不是概率性问题，是确定性的。

### 2.2 为什么"选更高目标版本"绕不过去

`ota_backup.c:410`（`cand_header.version_code <= app_header.version_code` 拒绝）
比较的是**候选 vs 当前镜像**版本，与本阻断（**BCB vs 当前镜像**版本）是两个
独立检查。把目标版本从 3.2.0 提到 3.2.1/3.2.2 只满足 410，不触及 385。385
在 410 之前执行（§2b 在 §3 之前），先失败先返回。

### 2.3 该检查是刻意设计，不是可放宽的冗余

- 注释原文自述语义：「不一致说明 BCB 已过期/错位，**禁止据此自拷备份或提交
  STAGED**」——BCB 是 backup 自拷与 STAGED 提交的身份基准，基准错位时继续
  操作会把 backup 槽内容标错版本。
- 本检查与 `OtaUpdate.cpp:546` 注释的 P2-5 阻断体系同源（candidate 身份三元
  一致、CONFIRMED 门禁），是已冻结防错板机制的一部分。
- 用户 2026-09-13 意见明确：不能通过验收合同临时放宽。

## 3. BCB 仲裁结果核对

`boot/src/boot_state_machine.c:452`：确认路径会把 `next.cur_vcode` 置为被确认
镜像的 `version_code`（`bcb_make_idle` 分支之外的 CONFIRMED 分支）。正常 OTA
闭环确认后，BCB vcode 必然等于运行镜像 vcode。当前板 20801≠30200 只与
「J-Link 直烧后 BCB 未更新」的历史路径自洽——板上 App 区逐字节等于磁盘
`X-Track-App-GCC.bin`（含 finalize 头），而 finalize/J-Link 烧录路径不写 BCB。

结论：**不一致是历史直烧遗留的板级状态问题，不是 boot 仲裁代码缺陷**；但按
现网代码，它使该板无法完成任何新的 OTA 提交。

## 4. 最小恢复方案（待审批，未执行）

原则：不删除/不绕过 385 检查、不改任何产品代码、不手改 BCB 数字、不擅自烧录。

**方案 A（推荐）：走真实 OTA 通道自然重同步 BCB——用真包闭环本身修复**

依赖：BCB 阻断必须先解除才可走闭环，而解除手段就是闭环本身——存在循环依赖。
具体拆解：

1. toy 3.2.1 包传输到 STAGED 完成、**Apply 成功**（Apply 只走 candidate
   prepare/write，不触发 385——见 §2.1 调用链：Apply 前置只有
   RequireConfirmedBcb 的 state 检查）；
2. **CommitStaged 在该板上会失败**（385）——这是第一次实机执行时**必然观测
   到的产品行为**，本身就是本阻断的直接实机证据；
3. 失败后的恢复决策需要用户裁定（见下）。

**方案 B（备用，需单独授权）：J-Link 直烧一个"BCB 与镜像一致"的完整状态**

用一个已确认镜像版本（如 3.2.1 finalize 后）整体重烧 App + 按确认语义更新
BCB（或使用 boot 既有的 TEST_BOOT/CONFIRM 流程让 boot 自己写 BCB）。这是
真机写入操作，**不在现有授权内**，须按合并操作单单独列项审批。注意：直烧
本身不写 BCB（这正是当前不一致的成因），所以必须选能让 boot 仲裁自己落
BCB 的路径（TEST_BOOT 流程），而不是再直烧一次镜像。

**用户需裁定的点**：A 的第 3 步失败后是否允许进入 B；或是否有其他指定路径。

## 5. 对合同/矩阵的影响

- 已在 `P3-3-v1.contract.json` 新增 external input `EXT-BOARD-STATE`
  （category=hardware_state，fingerprint/evidence 为 PENDING 占位）：BCB 不
  一致解决证据回填后，C-TOY-LOOP / C-REAL-LOOP 方可执行。
- C-TOY-LOOP / C-REAL-LOOP 的 description 已写明前置：EXT-BOARD-STATE 已按
  最小恢复方案解决并留证。
- 矩阵对应判据 notes 已登记该阻断为硬前置。
- 本文档即为 `EXT-BOARD-STATE.evidence_path` 指向内容的雏形；恢复方案获批
  并执行后，执行证据回填该输入的 fingerprint/evidence_sha256。

## 6. 边界声明

- 本轮**零真机操作**：未连接 J-Link、未读写设备、未改 BCB、未烧录。
- 全部证据引用自已入库文档与代码行号（`ota_backup.c:385/410`、
  `boot_state_machine.c:452`、`OtaUpdate.cpp:549-576`、板识别记录 §2/§6/§7）。
- 恢复方案未获批前，任何实机升级闭环执行都应被验收会话拒绝。
