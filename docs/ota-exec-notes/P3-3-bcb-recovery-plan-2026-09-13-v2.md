# P3-3 BCB 一致性恢复：原始证据核实与可执行最小恢复方案（2026-09-13 第二版）

> 依据：用户 2026-09-13 分项批复第 4 条——不批准原方案 A（先传输再观察已知
> 拒绝不是"自然重同步"），不批准 A 失败后自动进入 B；要求先核实已有原始证据
> 的身份与仲裁依据，提交**从当前 CONFIRMED 状态出发的**可执行最小恢复方案；
> TEST_BOOT 方案必须说明合法进入路径、前后状态、写入区域、复位次数、备份和
> 失败处理；恢复操作另行审批。本文档零真机操作、零代码改动。

## 1. 原始证据身份核实（零新增观测，全部引用既有证据产物）

### 1.1 板上 App fw_header version_code = 30200（3.2.0）

| 核对面 | 内容 | 来源 |
| --- | --- | --- |
| 直接转储 | `app16k.bin`（16384 B，sha256 前 16 `a2f4133c43bf65f6`）off8 实读 `0x75F8` = 30200 | `P3-3-t1a-jlink-board-identification-2026-09-12.md` §2.2 表 |
| 密码学复核 | 双零法全镜像 SHA `d97534841302c16d…1f7401dd` 与板上头内记录一致；header_crc32 `7011438F` 重算一致 | 同上 §2.2「独立复核」 |
| 与磁盘对照 | 板上 App 区 = 磁盘 `X-Track-App-GCC.bin`（602984 B，`7328c1b1…`）+ finalize 头；P3-2 冻结记录 `header_double_zero_sha256` 同摘要自洽 | 同上 §2.2；`P3-2-acceptance-round1.md:50` |
| 证据文件 | `.cache/p3-3-t1a-step1-r1/jlink/`（全部 sha256 已登记于该文 §7） | 主 worktree |

### 1.2 BCB CONFIRMED cur_vcode = 20801（2.8.1）

| 核对面 | 内容 | 来源 |
| --- | --- | --- |
| 直接观测 | App 启动期 RTT 自报 `OTA: BCB already CONFIRMED vcode=20801`（`rtt-terminal.log`，287 B，sha256 前 16 `320e698d341a7d21`） | 同上 §3.3 |
| 代码归属 | 该行由 `USER/HAL/HAL_EEPROM.cpp:180`（`OTA_ConfirmBoot` 的 `OTA_CONFIRM_ALREADY_CONFIRMED` 分支）打印——只在 `bcb_arbiter` 返回有效记录且 `state==CONFIRMED` 时出现，值取自主导 BCB 的 `cur_vcode` 字段 | `HAL_EEPROM.cpp:157-183` |
| 仲裁机制 | `bcb_arbiter`（`Libraries/EEPROM/eeprom_bcb.c:163`）读 BCB-A（EEPROM 0x00）/BCB-B（0x40）各 64B，校验 magic/schema/CRC 后按 16bit 回绕 seq 选主导记录；打印的 20801 即主导记录的 `cur_vcode` | `eeprom_bcb.c:163-209` |

**结论：两值身份核实无误**——30200 来自 QSPI App 区 finalize 头（转储+摘要重算），
20801 来自 EEPROM BCB 主导记录（经 App 仲裁代码自报）。不一致是**板级持久状态**
（EEPROM 里的 BCB 记录停留在 2.8.1 确认时点），不是代码缺陷、不是观测误差。

### 1.3 仲裁依据核实（20801 的合法来历）

- `20801 = 2.8.1`（2*10000+8*100+1），是 P1-3 验收（2026-07-28）真机 TEST_BOOT
  流程合法确认的版本：STAGED(cur=20800, cand=20801) → 一次普通 reset → App
  `ota_confirm_test_boot` 提交 CONFIRMED → RTT 取得 `OTA: TEST_BOOT confirmed
  vcode=20801`（`P1-3-P1-5-acceptance-2026-07-28.md` §5，105-120 行）。
- 当前板上 App 3.2.0 是 P3-2（2026-09-03）J-Link 直烧的
  `X-Track-App-GCC.bin`（finalize 后）；**直烧路径只写内部 flash，不写 EEPROM
  BCB**（finalize/烧录工具链无 EEPROM 写入步骤，P3-2 证据链亦无 BCB 写记录）。
- 时序：BCB 20801（2026-07-28）早于镜像 30200（2026-09-03）——BCB 滞后于
  直烧镜像，与"CONFIRMED 记录未被直烧更新"完全自洽。

### 1.4 为什么 385 检查不会自愈

`ota_backup_stage`（`Libraries/OTA/ota_backup.c:330`）§2b（:385）：
`current.cur_vcode != app_header.version_code` → `OTA_BACKUP_ERR_APP_HEADER`。
该检查在每次 CommitStaged 时从 EEPROM 重新读 BCB、从 flash 重新读 fw_header，
两侧只有人为/固件动作才会变。**板子保持现状（不烧录、不升级）时，20801 与
30200 都不会自己变**——任何新的 STAGED 提交都会被确定性拒绝。原方案 A 的
缺陷（用户指出）也在此：CommitStaged 失败后 candidate 槽已写入 STAGED 之外
的候选数据（传输阶段写入），BCB 并不会因此变化，"自然重同步"不成立。

## 2. 从当前 CONFIRMED 状态出发的恢复路径全集（代码枚举）

从「BCB=CONFIRMED(20801)、App=30200」出发，能让 BCB 与镜像重新一致的**全部**
代码路径（不新增代码、不手改 EEPROM）：

| # | 路径 | 触发条件 | 写 BCB 的代码 | 可行性判定 |
| --- | --- | --- | --- | --- |
| P1 | 状态机 IDLE/CONFIRMED 分支的 `commit_confirmed(io, &active, &current, app_header.version_code)` | BCB 主导记录失效（CRC/魔数坏）或 state=IDLE 且内部 App 校验通过 | `boot_state_machine.c:433-457`（`commit_confirmed` 把 `cur_vcode` 置为**当前内部 App 的 version_code**=30200） | **需先把 BCB 置为无效/IDLE**——本身又是一次写，循环依赖；不能从 CONFIRMED 直接进（CONFIRMED 分支只 jump 不改写） |
| P2 | 状态机 TEST_BOOT 分支：App 侧 `ota_confirm_test_boot` 提交 CONFIRMED，`next.cur_vcode = current.cand_vcode` | BCB state=TEST_BOOT 且 App 健康门就绪 | `ota_confirm.h:21-76`（`USER/main.cpp:91` 轮询调用） | **需先让 BCB 进入 TEST_BOOT**（见 P3/P4） |
| P3 | OTA 完整闭环：CommitStaged 成功 → boot STAGED→APPLYING→TEST_BOOT → 新 App 确认 | CommitStaged 不再被 385 拒绝 | 同 P2 | **被 385 阻断**（本恢复要解的问题本身）——只能用于 BCB 已恢复后的正常升级，不能作为恢复手段 |
| P4 | P1-6 证据钩子 `stage_slots`：外部预置 candidate+backup 槽后，boot 把 BCB 写为 STAGED(cur=当前镜像 vcode, cand=候选 vcode)，之后走 P2 | `P1_6_TEST_ENABLE` 编译的 Boot + 命令块驱动的 STAGE_SLOTS opcode | `boot_p1_6_test.c:563-606`（`stage_slots`：要求 `current.state ∈ {IDLE, CONFIRMED}` **且 `internal.version_code == current.cur_vcode`**） | **同样被一致性前置挡住**：`stage_slots` 入口校验 `internal.version_code != current.cur_vcode` 即 `OTA_P1_6_DETAIL_STAGE_VALIDATE` 失败（板上 30200 ≠ 20801） |
| P5 | P1-6 证据钩子 `clear_bcb`：把 BCB-A/B 双块写 0xFF（仲裁结果变 NONE），再让状态机走 P1（NONE 分支 → `commit_confirmed`，`cur_vcode`=内部 App 30200） | `P1_6_TEST_ENABLE` 编译的 Boot + CLEAR_BCB opcode | `boot_p1_6_test.c:538-556`（写 0xFF）+ `boot_state_machine.c:536-543`（NONE → `commit_confirmed`） | **可行**——两次连续固件状态转换（清空→重建），全部由 boot 既有代码执行；但需 P1_6_TEST_ENABLE 版 Boot 在板上（当前板上 Boot 是生产 Boot，无此钩子） |
| P6 | 物理恢复（YMODEM 重灌 + `accept_physical_recovery` → `commit_confirmed`） | App/backup/recovery 全部无效 + 按住恢复键 ≥3s | `boot_main.c:100-122, 813-843` | 破坏性（要求 App 全无效才进入），**不适配**——板上 App 本来就健康，仅为修 BCB 把 App 弄坏属于本末倒置 |

**枚举结论：在不动 EEPROM 二进制、不新增产品代码的前提下，能从
「CONFIRMED(20801) + 镜像 30200」恢复一致的路径只有 P5（P1-6 clear_bcb +
状态机重建），且它要求先把一个 `P1_6_TEST_ENABLE` 版 Boot 放上板**。P4 的
stage_slots 演练入口同样有 cur_vcode==internal.version_code 前置（这一点比
此前澄清文档的认知更进一步：**连测试钩子也不允许在 BCB 错位状态下工作**，
所有固件路径共享同一一致性纪律）。

## 3. 推荐恢复方案：P5 变体「TEST_BOOT 全流程」（从 CONFIRMED 出发）

### 3.1 总体设计

不直接改 BCB 数字、不手写 EEPROM 字节；让**既有固件代码**以真实状态机路径
重建 BCB，且重建后 `cur_vcode` 取自**真实内部 App 镜像头**（30200），不经过
任何人工数字。

工具选择上的关键事实（与上一版方案的差异）：
- `P1_6_TEST_ENABLE` 是 CMake 选项（默认 OFF，`CMakeLists.txt:48`），只影响
  **Boot** 侧（`boot_p1_6_test.c` 只编入 Boot target；App 侧的 P1-6 引用仅
  是 checkpoint 记录，不改变 App 行为）。**烧一个 P1_6_TEST_ENABLE 版 Boot
  不触碰 App 镜像与 BCB 数据语义**——它只增加 boot 的命令处理块。
- 但当前板上 Boot 是生产 Boot（16KB 转储已逐字节核对）；替换 Boot 是**真机
  写入操作**，须用户单独授权。

### 3.2 逐步操作序列（每步含状态、写入区域、验证点）

前置：制作 `P1_6_TEST_ENABLE=ON` 的 GCC Boot（本地构建，与 CI 同参数
SOURCE_DATE_EPOCH=1786320000；产物 SHA 留档）。App 不重烧（保持 30200 镜像
与其板上身份证据链）。

| 步 | 操作 | 前状态 | 写入区域 | 后状态（预期） | 验证 | 失败处理 |
| --- | --- | --- | --- | --- | --- | --- |
| R0 | 烧录 P1_6 Boot 到 0x08000000（J-Link loadfile，hex 覆盖 0x08000000..0x08004000 Boot 区；**不触碰 0x08010000 App 区**）；复位 | BCB CONFIRMED(20801)，App 30200 | 内部 flash Boot 区（64KB 窗口的 boot 段） | 同左（Boot 替换不影响 BCB/App） | 烧后 RTT 确认 boot 启动日志 + App 仍 30200（GET_INFO 或头转储） | 烧录失败→保持断言失败证据，停止；App 区被误写的可能由 hex 地址范围静态预检排除（loadfile 前核对 hex 覆盖区间） |
| R1 | 只读快照：P1-6 SNAPSHOT(opcode 4, arg1=BCB_ONLY) 取 BCB-A/B 原始 64B×2 | CONFIRMED(20801) | 无（快照只读） | — | 控制块 `OTA_P1_6_OFF_BCB_A_RAW/_B_RAW` 与 §1.2 观测一致（state=CONFIRMED、cur_vcode=20801、seq、CRC） | 不一致→停止，重新核实（说明板上状态与证据链漂移，须重新评估全部前提） |
| R2 | CLEAR_BCB(opcode 1)：boot 把 BCB-A(0x00)/BCB-B(0x40) 各写 0xFF 并读回比对 | CONFIRMED(20801) | **EEPROM 0x00..0x7F（两块 BCB 记录区，128B）** | 仲裁结果=NONE | P1-6 状态 PASS；SNAPSHOT 复核双块全 0xFF | FAIL(detail=EEPROM)→停止留证；EEPROM 写坏属硬件事件，不得重试超 1 次 |
| R3 | 复位（普通 reset，1 次） | BCB=NONE | boot 状态机 `commit_confirmed`：写**非主导块**（seq 从 0 起的 A 块） | **CONFIRMED(cur_vcode=30200)** ← 状态机 NONE 分支用 `app_header.version_code` 重建 | RTT 取得 `OTA: TEST_BOOT confirmed vcode=30200` 或 `already CONFIRMED vcode=30200`（`main.cpp:91` 路径）；SNAPSHOT 复核 state/cur_vcode/seq/CRC | 未出现确认行→读快照分类（EEPROM 错/状态机 hold），停止 |
| R4 | 只读终态核验：SNAPSHOT + App GET_INFO/version 读数交叉 | CONFIRMED(30200) | 无 | 同左 | BCB.cur_vcode == 30200 == App fw_header.version_code；385 前置条件满足 | 不一致→停止 |
| R5 | 换回生产 Boot：重烧磁盘原版 `X-Track-Boot.bin`（16KB，与 §1.1 板识别证据同一基线）；复位；RTT 确认正常启动 | CONFIRMED(30200)，App 30200 | 内部 flash Boot 区 | 恢复原 Boot，板上状态与验收起点一致 | boot 逐字节=磁盘原版（savebin 比对）；App 30200 不变；BCB 快照仍 CONFIRMED(30200) | 失败→重试 1 次；仍失败→留证停（P1_6 Boot 残留不影响 OTA 功能正确性，但须在验收报告登记） |

**复位次数合计：3 次**（R0 烧后复位、R3 重建复位、R5 换回复位）。每步 J-Link
连接按既有防坑清单（首次连接可能触发 nRESET 回退，已在本板观测过一次，操作单
按"每次连接都可能复位"申报）。

### 3.3 前后状态总账

| 项 | 前 | 后 |
| --- | --- | --- |
| BCB 主导记录 | CONFIRMED, cur_vcode=20801, cand/backup=20800 系列 | CONFIRMED, cur_vcode=30200, state/try/copy/resume 复位（bcb_make_idle+commit_confirmed 语义） |
| App 区 | 30200（P3-2 finalize 镜像，**全程不动**） | 30200（不变） |
| Boot 区 | 生产 Boot（板上原版） | 生产 Boot（R5 换回；中间短暂为 P1_6 版） |
| EEPROM BCB 区 | 20801 记录（A/B 双块，seq 不详→快照留档） | 30200 记录（单块起，seq=0） |
| backup/candidate/recovery 槽 | 未观测（本方案不触碰） | 不变 |

### 3.4 备份与可回滚性

- **BCB 原始字节备份**：R1 快照把 BCB-A/B 原始 128B 留档（项目内证据目录，
  含 CRC），任何时点可经 J-Link EEPROM 写回恢复原状态（回滚路径仅声明存在，
  执行仍需授权——EEPROM 直接写回属"改 BCB 数字"类操作，只在恢复流程本身
  翻车且用户批准时使用）。
- **App 镜像不动**：板上 3.2.0 的全部身份证据（§1.1）在恢复前后保持有效。
- **Boot 双向备份**：R0 前板上 Boot 已有 16KB 转储留档（板识别轮）；R5 写回
  的就是磁盘原版，逐字节可核。

### 3.5 失败分类预案

| 失败点 | 分类 | 处理 |
| --- | --- | --- |
| R0 烧录失败 | HARNESS_FAIL | 留证停止；板上 Boot 可能半写——J-Link 读回比对确认；若损坏则按 R5 同法写回磁盘原版（已授权范围内？否——烧录均需本操作单授权，操作单把"失败后写回原版 Boot"列为同批授权项） |
| R1 快照与 §1.2 不符 | EVIDENCE_GAP | 停止并重新核实全部前提（板上状态已漂移） |
| R2 EEPROM 写失败 | PRODUCT_FAIL（EEPROM 器件/驱动） | 留证停止，不重试（1 次失败即停） |
| R3 未确认 | PRODUCT_FAIL（boot/App 状态机） | 快照+RTT 留证；App 若在跑则 BCB 为 NONE/未重建，**禁止再 reset 瞎试**（NONE+App 有效每次启动都会重建，1 次失败后读快照定位） |
| R4/R5 核验不符 | PRODUCT_FAIL | 留证停止 |

### 3.6 与升级链的衔接

恢复完成（R4 通过）后，385 前置满足（cur=30200=镜像 vcode），升级链合法
起点为「BCB CONFIRMED(30200) + App 3.2.0」——正是用户第 4 条要求的"保持
原定升级链的合法起点"。toy 3.2.1 闭环与真包 3.2.2 闭环在此基础上按各自合同
判据执行，**恢复流程不消耗、也不替代任何一次升级闭环**。

### 3.7 备选（不推荐）：若用户不愿烧 P1_6 Boot

无其他合规路径（§2 枚举）：P1-P4/P6 均不可用或被阻断。替代是**修改产品代码
为恢复增加入口**——违反"不新增代码"的恢复纪律，不提交。

## 4. 授权申报（真机操作，逐项列明）

| 项 | 内容 | 次数 | 超时 |
| --- | --- | --- | --- |
| A1 | 烧录 P1_6_TEST_ENABLE Boot（hex 覆盖区间预检 + loadfile + 复位） | 1 | 5 min |
| A2 | J-Link EEPROM/控制块读写会话（R1 快照、R2 命令、R4 快照；含 RAM 控制块 `OTA_P1_6_CONTROL_ADDRESS` = `0x20000000+0x58000-512` = `0x2005 7E00` 写命令字） | 3 | 每次 5 min |
| A3 | 普通复位触发状态机重建（R3） | 1 | 2 min |
| A4 | 烧回生产 Boot（R5）+ 终态核验 | 1 | 5 min |

- **不包含**：断电注错、candidate/backup 槽写入、App 烧录、升级闭环（另按
  各自授权）；P1-6 的 STAGE_SLOTS/INSTALL_SLOT/CORRUPT_SLOT opcode 本单不用。
- **每次 J-Link 连接都可能触发 nRESET 回退**（本板已观测过），按此最坏情况
  申报；复位不写任何数据，状态机 NONE/CONFIRMED 均为安全态。
- 依据：用户第 7 条"可能触发复位的 J-Link 连接不能作为免费只读预检"——本单
  把全部 J-Link 会话（含快照）列为待批项。

## 5. 对合同/矩阵的影响

- `EXT-BOARD-STATE` 的解决证据 = 本方案 R1-R4 执行留证（快照文件 + RTT 日志
  + 复位后确认行）；fingerprint/evidence_sha256 在执行后回填。
- C-TOY-LOOP / C-REAL-LOOP 前置改为「EXT-BOARD-STATE 已按批准的恢复方案
  R4 终态核验通过」。
- 操作单 O 序列中删除"O3 含预期 385 拒绝观测点"（原方案 A 产物）；BCB 恢复
  作为独立准备操作（本单 §3.2 R0-R5）排在升级闭环之前。

## 6. 边界声明

- 本文档零真机操作、零代码改动、零构建（P1_6 Boot 构建属准备阶段，在获批
  后执行并留产物 SHA）。
- §2 路径枚举的每一条都引用了现行源码行号；若 freeze_commit 后源码变化，
  须复核 `ota_backup.c:385`、`boot_state_machine.c:433-457/536-543`、
  `boot_p1_6_test.c:538-606`、`ota_confirm.h:21-76`、`main.cpp:52-105`
  未变，否则本方案须升版。
- 不删除任何一致性检查；不直接改写 BCB 数字（R2 清空由固件 CLEAR_BCB 代码
  执行，R3 重建值取自真实 App 镜像头——全程无人工数字介入 BCB 字段）。
