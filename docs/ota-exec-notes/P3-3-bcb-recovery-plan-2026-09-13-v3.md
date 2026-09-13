# P3-3 BCB 一致性恢复方案（2026-09-13 第三版）

> 依据：用户 2026-09-13 第三轮裁定第 3 条——P5 可作为候选恢复路线，但 v2
> 的 R0-R5 **尚不能执行**；实际恢复是「**清空 BCB → NONE → 根据有效 App
> 重建 CONFIRMED**」，不是 TEST_BOOT 全流程；清空 EEPROM 0x00-0x7F 是明确
> 的持久状态变更。本版按六项细节修正（a-f）重做操作序列，**补齐后集中审批
> 一次，不先上板尝试**。
>
> 本版取代 `P3-3-bcb-recovery-plan-2026-09-13-v2.md`（v2 保留作历史）。
> v2 的 §1 证据核实（30200/20801 身份、385 不自愈、路径枚举）本版不重复，
> 全部继续有效；本版只重做执行序列与申报。配套准备已完成：
> `P3-3-recovery-boot-build-2026-09-13.md`（P1_6 Boot 构建、产物身份、
> 命令生成/解析离线验证 13/13 PASS）。

## 0. 六项修正映射

| 修正 | v2 缺陷 | v3 落点 |
| --- | --- | --- |
| a 命令细节与复位重算 | R1-R4 未按「每次 P1-6 命令 invoke = 1 次复位」计（v2 合计 3 次是错的）；命令无完整控制块/触发/校验/退出要素 | §2 执行模型 + §3 S1-S6（**6 次复位**逐次编号，每命令五要素齐全） |
| b 写入如实标注 | R1/R4 标「无写入」、§4 称「复位不写任何数据」——错误：命令块写 RAM 512B 是真实写入；S4 的复位正是靠写 EEPROM（commit_confirmed）完成重建 | §4 写入总账：RAM 块写、EEPROM 0x00-0x7F 写 0xFF、commit 记录写、Boot 区 flash 写逐项列明 |
| c 完成判据含生产 Boot 恢复 | v2 把 R5 写成可失败残留（「P1_6 Boot 残留不影响 OTA 功能正确性」） | §5 完成判据四条：生产 Boot 恢复+核验、App 身份未变、BCB 与 App 一致、生产 App RTT 自报 |
| d R5 后新鲜 BCB 证据 | v2 无生产 App 侧新鲜证据要求 | §3 S6 含 REC7：RTT logger 采集生产 App 自报 `OTA: BCB already CONFIRMED vcode=30200`（列入授权） |
| e 写入/擦除范围按实际产物 | v2 预设「16KB」 | §4 按 #25 HEX 实测 0x08000000-0x0800491F + 烧录算法扇区对齐说明，不预设值 |
| f 失败分支与编号 | R5「重试 1 次」与 A4 申报 1 次矛盾；A1-A4 与历史 A1 配额混淆 | §6 失败分类统一「默认零自动重试，追加须另行申报」；§7 改 **REC1-REC7** 独立编号 |

## 1. 恢复语义（非 TEST_BOOT）

```
现状：BCB=CONFIRMED(cur_vcode=20801)，App 镜像=30200（健康，身份证据链完整）
目标：BCB=CONFIRMED(cur_vcode=30200)，App 镜像=30200（不动），生产 Boot 复位还原

路径：P1_6 Boot 的 CLEAR_BCB 命令把 EEPROM BCB-A(0x00)/BCB-B(0x40) 各 64B
      写 0xFF（持久写） → 仲裁结果 NONE → 一次普通复位 → 生产状态机
      NONE 分支 commit_confirmed 用【内部 App 镜像头的 version_code=30200】
      重建 BCB → CONFIRMED(30200) → jump App。
```

全程无人工数字介入 BCB 字段（重建值取自真实镜像头）；不删除任何一致性
检查；不动 App 区、backup/candidate/recovery 槽、QSPI。TEST_BOOT 状态
**不经过**（重建直接写 CONFIRMED，`boot_state_machine.c:536-543` NONE 分支
→ `commit_confirmed`，同文件 433-457）。

## 2. 固件命令执行模型（源码实证，行号为本 worktree 当前 HEAD）

- **处理时机**：`boot_main.c:144-149` —— 平台初始化后、**状态机之前**调用
  `boot_p1_6_process_command()`。控制块 magic ≠ COMMAND_MAGIC →
  `NO_REQUEST`，正常启动继续（生产 Boot 等价行为）。
- **命令执行后 HOLD**：任何有效命令（含 SNAPSHOT）执行完
  `result_finish()` 写 DONE magic 后返回 `BOOT_P1_6_HOLD`（
  `boot_p1_6_test.c:775`）→ `boot_platform_hold()` = `__WFI()` 死循环（
  `boot_platform_at32.c:825-831`）。**boot 停机，状态机不跑、不跳 App；
  唯一退出方式 = 复位**。因此每条 P1-6 命令需要一次独立复位来执行，
  命令完成后需要下一次复位才能继续正常启动——这是 §3 序列 6 次复位的
  来源。
- **结果块**：`result_finish`（`boot_p1_6_test.c:385-404`）在每条命令后都
  执行 `snapshot_bcb()`（读 EEPROM BCB-A/B 原始 64B×2 + 仲裁字段
  active/state/seq/cur_vcode/cand_vcode/backup_vcode 写入控制块）+
  `snapshot_app()`（App 头 vcode/len/CRC/SHA256），写 status/detail/
  result CRC，最后写 DONE magic。主机侧以 savebin+decode 验证
  `kind=done ∧ done=true ∧ result_crc_valid ∧ status=PASS(2)`。
- **CLEAR_BCB**（opcode=1，`boot_p1_6_test.c:707-719`）：前置
  `validate_internal_app` 必须通过（板上 App 30200 健康 → 通过；失败则
  `detail=APP_INVALID` 且**不写 EEPROM**）。执行体 `clear_bcb()`
  （538-556）：BCB-A/B 各写 64B 全 0xFF，**写后读回 memcmp 校验**，失配
  `detail=EEPROM`。
- **SNAPSHOT**（opcode=4，`boot_p1_6_test.c:720-744`）：arg0=0（不做槽
  快照）、arg1=`OTA_P1_6_SNAPSHOT_BCB_ONLY`(=1) 时只做 BCB 快照（不读
  QSPI App，app 快照失败不升级 FAIL）。
- **RAM 控制块**（#25 离线验证实测）：地址 `0x20057E00`（OTA_RAM 末尾
  512B）、尺寸 512、magic COMMAND=`0x43365045`/ARM=`0x41365045`/
  DONE=`0x44365045`。写块时序安全（staged magic=0 逐字写入 → 最后一次
  w4 写 magic 提交；部分写入不会被认作有效命令，离线 T4/T4b 证明）；
  CRC/inverse/尺寸防篡改 fail-closed（T6-T11）。

## 3. 操作序列 v3（6 次复位；每步含控制块/触发/写入/校验/退出五要素）

通用命令会话脚本形态（复用 `Tools/jlink/p1-6-common.ps1` 既有封装
`Invoke-P16StartEncodedControl -StartMode Reset -Expected Done`，离线已验证
其 `Get-P16WordWriteLines` 生成逻辑）：

```
h                                      # halt
w4 0x20057E04..0x20057FFC  ×127        # 写命令块 body（staged，magic 留 0）
w4 0x20057E00, 0x43365045              # 最后写 COMMAND magic 提交
verifybin <committed.bin>, 0x20057E00  # 整块读回比对
r                                      # ← 复位：boot 从头启动并执行命令
g
Sleep <wait>
h
savebin <capture.bin>, 0x20057E00, 512 # 采结果块
qc
```

（主机侧退出=qc；设备侧退出=boot HOLD（WFI），直到下一次复位。）

### S1（REC1）烧录 P1_6_TEST_ENABLE Boot —— 复位①

| 要素 | 内容 |
| --- | --- |
| 操作 | J-Link `loadfile <#25 X-Track-Boot.hex>`（先静态解析 HEX 地址范围=0x08000000-0x0800491F ⊂ Boot 64KB 区，预检不过不烧）→ `r` `g`（复位①） |
| 写入 | 内部 flash Boot 区 0x08000000-0x0800491F（HEX 实测）；擦除按烧录算法扇区对齐，范围 ≥ HEX 覆盖、上界远低于 0x08010000（App 区），执行时以 J-Link 日志 erase 信息留证。**不触碰 App 区/EEPROM/QSPI** |
| 预期后态 | BCB 仍 CONFIRMED(20801)（Boot 替换不写 BCB）；复位①后 P1_6 Boot 正常路径：状态机 CONFIRMED 分支只 jump → App 3.2.0 启动 |
| 结果校验 | 烧录 verify 成功行；产物 SHA 与 #25 §1.1 登记一致（烧前核对 hex 文件哈希 `409d4f16…`） |
| 失败 | 烧录/verify 失败 → 留证停止（§6 FR1），不自动重试 |

### S2（REC2）SNAPSHOT 基线 —— 复位②

| 要素 | 内容 |
| --- | --- |
| 控制块 | Kind=Command, opcode=4 (SNAPSHOT), arg0=0, arg1=1 (SNAPSHOT_BCB_ONLY), arg2=arg3=0；COMMAND magic 0x43365045 最后写 |
| 触发 | 通用命令会话（写块+verifybin+复位②+采结果） |
| 写入 | **RAM 控制块 512B（0x20057E00，非持久）**；EEPROM/flash 只读（snapshot_bcb 只读） |
| 结果校验 | kind=done、status=PASS、result_crc_valid；BCB 快照字段 = CONFIRMED / cur_vcode=20801 / active 与 v2 §1.2 自报一致；**BCB_A_RAW/BCB_B_RAW 原始 128B 留档**（唯一字节级回滚备份，§4） |
| 退出 | 设备 HOLD；主机 qc |
| 失败 | 字段与 2026-09-12 证据不符 → EVIDENCE_GAP，停止重核全部前提（§6 FR2） |

**裁剪选项（用户 a 项）**：可依 2026-09-12 板识别证据（RTT 自报 20801 +
代码归属核实）申请裁剪本步（-1 复位、-1 会话）。**代价**：CLEAR_BCB 的
result_finish 快照发生在清空**之后**（全 0xFF），跳过 S2 即**永久失去
清空前 128B 原始字节备份**，字节级回滚路径失效，只剩「重建到 30200」
单向路径。默认保留 S2；是否裁剪由审批时裁定。

### S3（REC3）CLEAR_BCB —— 复位③（**唯一的 BCB 持久清空**）

| 要素 | 内容 |
| --- | --- |
| 控制块 | Kind=Command, opcode=1 (CLEAR_BCB), arg0-3=0 |
| 触发 | 通用命令会话（复位③） |
| 前置 | 固件先 validate_internal_app（App 30200 有效才执行清空） |
| 写入 | **EEPROM 0x00-0x7F 共 128B 写全 0xFF（BCB-A 0x00 + BCB-B 0x40 各 64B，持久状态变更）** + RAM 控制块 512B |
| 结果校验 | kind=done、status=PASS、detail=NONE(0)；结果块内 snapshot_bcb 显示 active=NONE（清空后快照）、双块 raw 全 0xFF；`detail=EEPROM`/`APP_INVALID` 均按 §6 停止 |
| 退出 | 设备 HOLD；主机 qc |
| 失败 | §6 FR3（EEPROM 事件零重试；APP_INVALID 说明 App 前提坍塌） |

### S4（REC4）显式复位触发重建 —— 复位④

| 要素 | 内容 |
| --- | --- |
| 操作 | J-Link 单会话 `r` `g`（或板复位），**不写任何块**（上一步结果块 magic=DONE ≠ COMMAND → boot 走 NO_REQUEST 正常路径） |
| 写入 | **EEPROM BCB 区：状态机 NONE 分支 commit_confirmed 写非主导块（64B 记录，持久）**——本步的复位本身就是写 EEPROM 的触发器，v2「复位不写任何数据」表述就此废除 |
| 预期 | NONE → commit_confirmed(cur_vcode=**30200**，取自内部 App 镜像头) → CONFIRMED → jump App 3.2.0 |
| 结果校验 | RTT logger 采集 App 启动自报 `OTA: BCB already CONFIRMED vcode=30200`（`HAL_EEPROM.cpp:180` 路径；RTT 地址用板上 App 的生产 map `_SEGGER_RTT`，2026-09-12 板识别轮已验证可用）；logger 会话列入 REC4（超时+清残留纪律） |
| 备注 | NONE 态复位幂等：若 S3 后某次 J-Link 连接触发了计划外 nRESET（本板观测过），重建会提前发生且结果相同（commit 后 CONFIRMED 分支只 jump）；日志如实登记即可，不构成失败 |
| 失败 | 无自报行 → §6 FR4：允许 1 次只读 SNAPSHOT 定位会话（复位⑤前移，不写 EEPROM），仍不明 → 停止 |

### S5（REC5）SNAPSHOT 终态核验 —— 复位⑤

| 要素 | 内容 |
| --- | --- |
| 控制块 | 同 S2（opcode=4, arg0=0, arg1=BCB_ONLY） |
| 触发 | 通用命令会话（复位⑤） |
| 写入 | RAM 控制块 512B；EEPROM/flash 只读 |
| 结果校验 | kind=done、status=PASS；快照 = CONFIRMED / cur_vcode=30200 / seq 从 0 起 / CRC 有效；app 快照（result_finish 附带）= vcode 30200 与镜像头一致；385 前置 `cur==internal` 满足 |
| 退出 | 设备 HOLD；主机 qc |
| 失败 | §6 FR5 |

### S6（REC6）烧回生产 Boot + REC7 RTT 终证 —— 复位⑥

| 要素 | 内容 |
| --- | --- |
| 操作 | `loadbin <磁盘原版 X-Track-Boot.bin>, 0x08000000` + `verifybin`（文件取主 worktree `build-gcc-release/boot/X-Track-Boot.bin`，烧前核对与 2026-09-12 板识别轮登记的板上 Boot 身份一致）→ `r` `g`（复位⑥） |
| 写入 | 内部 flash Boot 区 0x08000000-0x08003FFF（生产 Boot 16KB bin；擦除扇区对齐留证同 S1）；**不触碰 App/EEPROM** |
| 预期 | 生产 Boot（无 P1_6 钩子）→ 状态机 CONFIRMED(30200) jump App |
| 结果校验（REC7） | RTT logger 采集**生产 App** 新鲜自报 `OTA: BCB already CONFIRMED vcode=30200`（d 项要求）；boot 区 savebin 抽样比对（可选增强：转储与磁盘原版逐字节核） |
| 退出 | 设备正常运行 App（验收起点态） |
| 失败 | §6 FR6：烧录失败零自动重试；**P1_6 Boot 残留不满足完成判据**，期间实机判据 ENV_BLOCKED，追加烧录须另行申报 |

## 4. 写入/擦除范围总账（e 项：按实际产物，不预设）

| 步 | 目标 | 区域 | 字节 | 持久性 |
| --- | --- | --- | --- | --- |
| S1 | Boot 区 | 内部 flash 0x08000000-0x0800491F（HEX 实测；擦除扇区对齐，上界 ≪0x08010000） | 18,720 | 持久（R6 还原） |
| S2/S5 | RAM 控制块 | 0x20057E00-0x20057FFF | 512 | 非持久 |
| S3 | EEPROM BCB | **0x00-0x7F 写全 0xFF** | 128 | **持久（不可逆：原 20801 记录清除，仅 S2 备份留档）** |
| S4 | EEPROM BCB | 非主导块 commit_confirmed 记录（0x00/0x40 之一，64B 内） | ≤64 | 持久 |
| S6 | Boot 区 | 内部 flash 0x08000000-0x08003FFF（+擦除扇区对齐） | 16,384 | 持久（还原） |
| 全程 | App 区 | **0x08010000（内部 Flash，非 QSPI）零写入**；QSPI 槽零写入 | 0 | — |

## 5. 完成判据（c 项：四条全部满足才算恢复完成）

1. **生产 Boot 已恢复**：S6 verifybin 成功 + 烧录文件 SHA 与板识别轮
   登记一致；（可选增强）savebin 转储逐字节=磁盘原版。
2. **App 身份未变**：S5 快照 app_vcode=30200、app_sha256 与板上镜像身份
   证据一致；App 区零写入由 S1/S6 HEX/bin 地址范围预检+留证保证。
3. **BCB 与 App 一致**：S5 快照 CONFIRMED / cur_vcode=30200 / CRC 有效
   （boot 侧独立读 EEPROM）。
4. **新鲜终证**：REC7 生产 App RTT 自报 `OTA: BCB already CONFIRMED
   vcode=30200`（生产 Boot + 重建后 BCB + 原 App 的完整组合态证据）。

四条齐 → `EXT-BOARD-STATE` 回填解决证据，升级链合法起点
「CONFIRMED(30200)+App 3.2.0+生产 Boot」成立，O 序列前置之一满足。

## 6. 失败分类与额度（f 项：默认零自动重试）

| 编号 | 失败点 | 分类 | 处理（追加动作均须先申报或属已申报的只读定位额度） |
| --- | --- | --- | --- |
| FR1 | S1 烧录/verify 失败 | HARNESS_FAIL | 留证停止；J-Link 读回比对评估半写状态；**不自动重烧**（追加烧录另行申报） |
| FR2 | S2 快照与 2026-09-12 证据不符 | EVIDENCE_GAP | 停止，重新核实全部前提（板上状态漂移）；不得继续 S3 |
| FR3 | S3 `detail=EEPROM`（写失败/读回失配） | PRODUCT_FAIL | 留证停止，**零重试**（EEPROM 器件事件）；此时 BCB 可能半清——字节级恢复须用 S2 备份+另行授权 |
| FR3b | S3 `detail=APP_INVALID` | PRODUCT_FAIL | 未写 EEPROM（前置校验挡住），留证停止；App 镜像前提坍塌，恢复方案整体作废重审 |
| FR4 | S4 无 App 自报行 | PRODUCT_FAIL | 允许 **1 次**只读 SNAPSHOT 定位会话（列入 REC4 额度；不写 EEPROM/flash）；定位后仍失败 → 停止；**禁止连续复位盲试**（NONE+有效 App 每次复位都重建，重复复位只会重复同一结果） |
| FR5 | S5 快照不符（state/cur_vcode/CRC） | PRODUCT_FAIL | 留证停止；与 S4 自报行交叉定位（App 侧/boot 侧读数不一致属严重异常，单独分类报告） |
| FR6 | S6 烧回失败 | HARNESS_FAIL | 留证停止，零自动重试；**P1_6 Boot 残留不满足 §5 判据 1**，实机判据 ENV_BLOCKED，追加烧录另行申报（v2「重试 1 次」与「残留不影响正确性」两处矛盾就此废除） |

任何失败：先留证据（J-Link 日志/结果块 bin+json/RTT 日志）再停止；
**禁止盲重试**；已消耗 REC 计入台账（§7）。

## 7. 授权申报（REC 独立编号，未批未执行）

| 编号 | 内容 | 次数 | 持久写入 | 备注 |
| --- | --- | --- | --- | --- |
| REC1 | S1 烧录 P1_6 Boot（含静态 HEX 范围预检、SHA 核对、loadfile、复位①） | 1 | Boot 区 flash | #25 产物 |
| REC2 | S2 SNAPSHOT 基线命令会话（复位②；可申请裁剪，见 §3 S2） | 1 | 仅 RAM | 128B 备份留档价值 |
| REC3 | S3 CLEAR_BCB 命令会话（复位③）——**EEPROM 0x00-0x7F 持久清空** | 1 | **EEPROM 128B** | 失败零重试 |
| REC4 | S4 显式复位（复位④）+ RTT logger 采集 App 自报行；含失败分支 1 次只读 SNAPSHOT 定位额度 | 1（+1 只读定位备用） | EEPROM commit 记录（复位触发） | 计划外 nRESET 幂等说明见 S4 |
| REC5 | S5 SNAPSHOT 终态核验命令会话（复位⑤） | 1 | 仅 RAM | — |
| REC6 | S6 烧回生产 Boot（含文件 SHA 核对、verifybin、复位⑥） | 1 | Boot 区 flash | 失败零自动重试 |
| REC7 | S6 后 RTT logger 采集生产 App 终证行 | 1 | 无 | 与 REC4 同纪律：明确超时、清残留 logger |

- 合计复位 **6 次**（S1-S6 各 1）；J-Link 会话按「每次连接都可能触发
  nRESET」最坏情况申报（本板 2026-09-12 观测过一次）；NONE 态计划外
  复位与 S4 结果幂等（§3 S4 备注）。
- **不包含**：App 烧录、QSPI 槽写入、断电注错、STAGE_SLOTS/
  INSTALL_SLOT/CORRUPT_SLOT、升级闭环（另按各自授权）；本单与 A1/B1-M/
  升级闭环配额互不借用。
- RTT logger / J-Link 会话纪律沿用 AGENTS.md 防坑清单（唯一 logger、
  超时、进程清理、map 重查地址）。

## 8. 对合同/操作单的影响

- `EXT-BOARD-STATE`：fingerprint/evidence_sha256 待 §5 四条证据齐后回填。
- C-TOY-LOOP / C-REAL-LOOP 前置 = 本方案 §5 四条全部满足。
- 实机操作单（`P3-3-device-operation-sheet-2026-09-13.md`）的前置链、
  O1 证书方法与 EXT 引用修订见同批 #21 修订；本文件取代 v2 成为 BCB
  恢复的唯一现行方案文档。
- 云端写入单（`P3-3-cloud-write-sheet-2026-09-13.md`）B0-B4 暂停标注
  见同批 #20 修订。

## 9. 边界声明

- 本版文档零真机操作、零源码改动；P1_6 Boot 构建/命令离线验证已完成
  （#25），烧录与全部 REC **未批未执行**。
- 源码行号基线：本 worktree 当前 HEAD（`boot_main.c:144-149`、
  `boot_p1_6_test.c:538-606/686-776`、`boot_platform_at32.c:825-831`、
  `boot_state_machine.c:433-457/536-543`、`eeprom_bcb.h:26-28`、
  `ota_backup.c:330/385`）。freeze_commit 后若上述文件变化，本方案
  须复核升版。
- 不直接改写 BCB 数字：S3 清空由固件 CLEAR_BCB 代码执行，S4 重建值取
  自真实 App 镜像头；字节级回滚备份（S2）仅在恢复流程本身翻车且另行
  获批时使用。
