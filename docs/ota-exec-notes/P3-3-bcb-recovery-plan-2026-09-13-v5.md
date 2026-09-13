# P3-3 BCB 一致性恢复方案（2026-09-13 第五版）

> 依据：用户 2026-09-13 集中执行授权 `P3-3-EXEC-AUTH-20260913` 第三节
> （设备恢复授权）。本版取代 `P3-3-bcb-recovery-plan-2026-09-13-v4.md`
> （v4 保留作历史）。v4/v3 的以下内容全部继续有效，本版不重复：
> - v3 §1 恢复语义（清空 BCB → NONE → 内部 App 镜像头 version_code=30200
>   重建 CONFIRMED；目标态 `CONFIRMED(30200)+App 3.2.0+生产 Boot`）。
> - v3 §2 / v4 §2 源码实证（命令处理时机、HOLD、结果块、CLEAR_BCB、
>   SNAPSHOT 行为；30200/20801 身份、385 不自愈）。
> - v4 §2.1 两阶段命令会话（Phase 0 失效 + Phase 1 启动）与中断穷举结论。
> - v4 §2.2 Boot 区受影响区域实测绑定（0x08000000-0x08004FFF，20,480B，
>   尾部 5,756B 未知内容登记 SHA、不假定 0xFF、不扩大擦除）。
>
> 本版四项修正（k-n，接续 v4 §0 的 g-j）已落地为受管执行脚本
> `Tools/jlink/p3-3-recovery-execute.ps1`（分 Phase 入口 + 每 Phase 主机侧
> fail-closed 断言），并保持 `Tools/jlink/p1-6-common.ps1` /
> `Tools/jlink/test-p1-6-recovery-cmd.ps1` 的 24/24 离线验证结论不变。

## 0. 第五轮修正映射（授权第三节逐条）

| 修正 | v4 缺陷 | v5 落点 |
| --- | --- | --- |
| k FR4/REC5 替代关系计数矛盾 | v4 §6 FR4 正文写「此路径下总复位 = 6」，但 §7 总账写「FR4 备用触发时 7 次 / 12 个会话」——把「替代」误登记成「追加」，与用户授权上限（10 会话/6 复位）冲突 | §3 S5、§6 FR4、§7 总账统一为：**FR4 触发时备用 SNAPSHOT 会话替代 REC5（S5）**，占用 S5 的 2 个命令会话与复位⑤，总复位仍 6、命令会话仍 10。不存在「替代却又增加」的路径；S5 与备用互斥执行，恰好一个 |
| l 首次启用测试 Boot 前的 RAM 失效时序 | v4 修正 j 的落点是「S2 的 Phase 0 失效会话即首次命令前的受控动作」——但 S1 复位①已经让测试 Boot 启动过一次，启动时若 RAM 残留有效旧命令会被立即执行；失效晚于第一次启动 | §3 S1 重构为 S1a/S1b 两段：**S1a 在同一 J-Link 连接内完成 全区备份 → loadfile 测试 Boot → w4 清 RAM magic → savebin 失效读回**（全程 halt，测试 Boot 从未运行），主机断言（备份锚点 + 失效读回 + erase 边界）全部通过后才执行 S1b 复位会话。测试 Boot 第一次启动执行（或检查）任何命令之前，RAM magic 已实测失效且已验证 |
| m 备份不许裁剪 | v4 §3 S2 留有「裁剪选项（默认保留，审批时裁定）」；授权明确「REC0 的 Boot 全区备份和 REC2 的清空前 BCB 原始 128B 备份必须保留，不允许裁剪」 | 删除裁剪选项：REC0 全区 20,480B 备份、REC2 结果块内 BCB_A_RAW/BCB_B_RAW 原始 128B（hex 提取落盘 + SHA 登记）均为强制留档，无任何审批路径可裁剪 |
| n 授权额度对齐与失败收尾 | v4 §7 按「触发时 7 次/12 个」申报，与授权「正常路径最多 10 个 J-Link 命令会话、2 个 RTT logger、6 次主动复位；另预留最多 2 个仅用于身份/RTT 签名核对的命令会话」不一致；REC6 失败收尾未声明额度共用 | §7 总账改按授权口径：命令会话 ≤10、RTT logger ≤2（每个 ≤120s）、主动复位 ≤6、签名核对会话 ≤2（不写块不复位）；REC6 作为失败后生产 Boot 安全收尾与成功路径**共用同一额度**（恢复动作只执行一次）；计划外 nRESET 阈值维持（单步 ≥2 次或全程累计 >2 次即停止） |

## 1. 恢复语义（不变）

见 v3 §1。目标态 `CONFIRMED(30200)+App 3.2.0+生产 Boot`。

## 2. 固件命令执行模型（v4 §2 全部有效，本节补两点）

### 2.1 两阶段命令会话（不变）

见 v4 §2.1：每个命令会话先失效（w4 magic=0 + savebin 读回 + 程序化断言
fail-closed）再写 body；残余唯一中断窗口 = 失效前完整旧态（确定性已知）。
`Invoke-P16StartEncodedControl` 内部即此两阶段（含 StartMode Reset 的
复位与 DONE 轮询），`Invoke-P16Command` 为命令级包装。

### 2.2 Boot 区受影响区域（不变）

见 v4 §2.2：0x08000000-0x08004FFF（20,480B = 扇区 0-4）；生产 Boot bin
14,724B、测试 Boot 18,720B、HEX 末址 0x0800491F、尾部 5,756B 未知内容。
执行前静态断言 HEX 记录范围（离线 T17 同款解析），烧录日志 erase 信息
实测留证并与边界核对；无法从日志解析出精确扇区边界时记录原文交独立
复核判定，**不得推定**「反正只擦了这些」。

### 2.3 S1 失效时序前移（修正 l）

```
S1a（REC0+REC1 合并连接，全程 halt，测试 Boot 未运行）：
  h
  savebin <backup.bin>, 0x08000000, 0x5000     # REC0 全区备份
  loadfile "<test-boot.hex>"                    # REC1 烧录（HEX 范围 0x08000000-0x0800491F）
  w4 0x20057E00, 0x00000000                     # RAM magic 失效（复位前！）
  savebin <s1a-invalidate-readback.bin>, 0x20057E00, 0x200
  qc
  → 主机断言（全部通过才允许 S1b）：
    1) backup.bin 尺寸 = 0x5000
    2) Assert-P16BootBackupMatchesProduction：前 14,724B 与磁盘生产 Boot bin
       逐字节全等；尾部 5,756B SHA-256 登记
    3) Test-P16InvalidatedControl：失效读回 magic==0 且 decode 全 invalid
    4) 烧录日志 erase 信息与 §2.2 边界核对（实测超界即停止重报）
S1b（REC1 复位会话，1 次复位①）：
  r, g, Sleep, qc                               # 测试 Boot 首次启动——此时 RAM magic 已实测为 0
```

- 命令顺序由 J-Link CommandFile 顺序执行 + `-ExitOnError 1` 保证：
  savebin 备份失败则 loadfile 不执行；w4/loadfile 失败则后续命令不执行。
- REC0 与 REC1 共享物理连接（不增加会话数），但证据与判据分离：
  备份 bin、烧录日志、失效读回各有独立文件与独立断言（REC0/REC1 仍是
  两个独立授权编号）。
- 顺序妥协的失败路径（如实申报）：锚点/失效断言在 loadfile 之后才发生，
  若失配，板上已烧入测试 Boot——按 §6 FR0 停止，并可用 §6 REC6 失败收尾
  （备份文件本身已存在；若备份锚点失配则恢复前提坍塌，维持 FR0 停止，
  不得用磁盘生产 bin 冒充全区备份恢复尾部未知区）。

## 3. 操作序列 v5（复位 6 次；命令会话 10 个 + RTT logger 2 个 + 签名核对会话 ≤2）

| 步 | 内容 | 会话 | 复位 | 持久写入 |
| --- | --- | --- | --- | --- |
| S1a | REC0 全区备份 + REC1 烧录测试 Boot + RAM 失效（§2.3） | 1 | 0 | Boot 区 20,480B（擦+写） |
| S1b | REC1 复位①：测试 Boot 首次启动（RAM 已受控） | 1 | ① | — |
| S2 | REC2 SNAPSHOT 基线（opcode=4/arg0=0/arg1=1 BCB_ONLY，两阶段）；BCB_A_RAW/BCB_B_RAW 128B 强制留档（修正 m） | 2 | ② | 仅 RAM |
| S3 | REC3 CLEAR_BCB（opcode=1，两阶段）；EEPROM 0x00-0x7F 写全 0xFF（持久） | 2 | ③ | **EEPROM 128B** |
| S4 | REC4 复位④（极简会话 r/g/Sleep/qc）→ RTT 签名核对（预留会话）→ logger 采集 App 自报 | 1+1 | ④ | EEPROM commit 记录（复位触发） |
| S5 | REC5 SNAPSHOT 终态核验（两阶段，opcode=4/arg0=0/**arg1=0 含内部 App 快照**——snapshot_app 只读 App 区+镜像头，物理写入仍仅 RAM 控制块；QSPI 槽仍不快照）；**FR4 触发时被备用会话替代（修正 k）** | 2 | ⑤ | 仅 RAM |
| S6 | REC6 Boot 全区恢复（loadbin 备份 + verifybin + 全区读回 SHA 全等）+ 尾部复位⑥ → REC7 RTT 签名核对（预留会话）→ logger 采集生产 App 终证 | 1+1 | ⑥ | Boot 区 20,480B（还原） |

- S2 基线断言：status=PASS、detail=NONE、active∈{A,B}（活动块有效，
  eeprom_bcb.h:89-94 枚举 A=1/B=2/NONE=0/ERROR=-1）、cur_vcode=20801
  （与 2026-09-12 板识别证据一致）；BCB_A_RAW/BCB_B_RAW 落盘 + SHA 登记
  （清空前唯一字节级备份，不裁剪）。
- S3 断言：status=PASS、detail=NONE（EEPROM/APP_INVALID 即 §6 FR3/FR3b）、
  active=NONE（=0）、双块 raw 全 0xFF。
- S5 终态断言（arg1=0 含 App 快照）：status=PASS、active∈{A,B}、
  cur_vcode=30200、seq=0（NONE 分支 commit_confirmed 走 bcb_make_idle，
  eeprom_bcb.c:315 置 0）、result_crc_valid、app_result=VALID（=1，
  ota_p1_6_test.h:100-103）、app_vcode=30200、app_sha256 与板上镜像
  身份证据一致（执行时回填比对）。
- S4/S6 的 RTT 采集时序：logger 在复位会话退出后启动；复位会话内
  `Sleep 8000` 让 App 完成启动并把自报行写入 RTT up buffer（环形缓冲
  保序，未被读走不丢），logger 附着后读走并匹配目标行
  `OTA: BCB already CONFIRMED vcode=30200`（REC4 与 REC7 同一行）。
  J-Link 会话与 logger 不得并发（单调试器连接，脚本内互斥保证）。
- 首启前控制块受控（修正 l）：S1a 已完成失效+验证，S2 的 Phase 0 失效
  是既定门禁的例行执行（非首次受控动作）。

## 4. 写入/擦除范围总账（不变，除 S1a 行）

| 步 | 目标 | 区域 | 字节 | 持久性 |
| --- | --- | --- | --- | --- |
| S1a | Boot 区 + RAM 控制块 | flash 0x08000000-0x08004FFF（擦+写）；RAM 0x20057E00 失效写 4B | 20,480 + 4 | 持久（S6 还原）/ 非持久 |
| S2/S5 | RAM 控制块 | 0x20057E00-0x20057FFF（含 Phase 0 失效写） | 512+4 | 非持久 |
| S3 | EEPROM BCB | **0x00-0x7F 写全 0xFF** | 128 | **持久（不可逆：原 20801 记录清除，仅 S2 备份留档）** |
| S4 | EEPROM BCB | 非主导块 commit_confirmed 记录 | ≤64 | 持久 |
| S6 | Boot 区 | 内部 flash 0x08000000-0x08004FFF 从备份还原 | 20,480 | 持久（还原，SHA 全等核验） |
| 全程 | App 区 | **0x08010000（内部 Flash）零写入**；QSPI 槽零写入 | 0 | — |

## 5. 完成判据（四条全部满足；不变）

1. **生产 Boot 已按全区恢复**：S6 verifybin 成功 + 全区读回 SHA-256 与
   S1a 备份全等（含尾部 5,756B 板上原值）+ S1a 锚点断言通过。
2. **App 身份未变**：S5（或 FR4 备用会话）快照 app_vcode=30200、
   app_sha256 与板上镜像身份证据一致；App 区零写入由 S1a/S6 地址范围
   预检+留证保证。
3. **BCB 与 App 一致**：S5（或 FR4 备用会话）快照 CONFIRMED /
   cur_vcode=30200 / CRC 有效。
4. **新鲜终证**：REC7 生产 App RTT 自报 `OTA: BCB already CONFIRMED
   vcode=30200`。

## 6. 失败分类与额度（默认零自动重试）

| 编号 | 失败点 | 分类 | 处理 |
| --- | --- | --- | --- |
| FR0 | S1a 备份锚点失配 / 读回失败 | HARNESS_FAIL | 停止；板上 Boot 身份与磁盘生产 bin 不一致，重核板识别轮证据后才可重新申报。此时若测试 Boot 已烧入且备份可用，按下行 REC6 收尾；备份不可用则维持停止（不得用生产 bin 冒充全区备份） |
| FR1 | S1a 烧录/verify 失败、S1b 复位证据异常 | HARNESS_FAIL | 留证停止；J-Link 读回比对评估半写状态；**REC6 失败收尾**（备份有效时） |
| FR2 | S2 快照与 2026-09-12 证据不符 | EVIDENCE_GAP | 停止，重新核实全部前提；不得继续 S3 |
| FR3 | S3 `detail=EEPROM` | PRODUCT_FAIL | 留证停止，**零重试**；字节级恢复须用 S2 备份+另行授权 |
| FR3b | S3 `detail=APP_INVALID` | PRODUCT_FAIL | 未写 EEPROM，留证停止；恢复方案整体作废重审 |
| FR4 | S4 无 App 自报行（120s 窗口内未匹配） | PRODUCT_FAIL | **FR4 备用会话**（替代 REC5/S5，见下） |
| FR5 | S5（或备用会话）快照不符 | PRODUCT_FAIL | 留证停止；与 S4 自报行交叉定位；**不得再盲试** |
| FR6 | S6 恢复失败（烧录/verify/读回 SHA 失配） | HARNESS_FAIL | 留证停止，零自动重试；测试 Boot 残留不满足 §5 判据 1，追加恢复另行申报 |

### FR4 备用会话（修正 k 后的唯一形态）

- 备用会话 = 完整 SNAPSHOT 命令会话（两阶段，2 个命令会话 + 复位⑤），
  含 RAM 512B+4B 写入与 1 次复位，EEPROM/flash 只读。
- **与 REC5 的关系（消除矛盾）**：备用会话**替代** S5——正常路径执行
  S5；FR4 触发时不执行 S5，改为执行备用会话。二者互斥，恰好消费其一个
  的 2 命令会话与复位⑤。**总复位恒为 6、命令会话恒为 10**，无任何
  「替代却又增加」的路径。
- 备用会话返回 kind=done、status=PASS 且快照满足 §3 S5 全部终态断言 →
  该会话即为终态核验，REC5 视为已消费；快照异常 → FR5 口径停止。
- 次数：恰 1 次，无更多备用；仍不明 → 停止，禁止连续复位盲试。

### REC6 失败收尾（授权明确：与成功路径共用额度）

- 允许在「备份有效、恢复前提仍成立」时，把 REC6 用于失败后的生产 Boot
  安全收尾（FR0/FR1/FR2/FR3b/FR5 之后）：从 S1a 备份全区还原生产 Boot。
- **共用同一额度**：恢复动作（loadbin+verifybin+读回 SHA 核验）只执行
  一次——成功路径在 S6 消费；失败收尾路径替代性消费。不得自动重复
  CLEAR_BCB、直接写回 BCB 原字节或追加烧录。
- 失败收尾后：BCB 状态以实测为准（S3 未执行则仍为 CONFIRMED(20801)
  阻断态；S3 已执行则由复位后状态机自行推进或停留，如实记录），停止
  并重新申报，不继续 S4/S5。

## 7. 授权额度总账（P3-3-EXEC-AUTH-20260913 第三节口径）

| 项 | 上限 | 说明 |
| --- | --- | --- |
| J-Link 命令会话 | **10**（正常路径恰好 10，见 §3 表） | S1a(1)+S1b(1)+S2(2)+S3(2)+S4(1)+S5(2)+S6(1)；FR4 触发时备用会话替代 S5，恒为 10 |
| RTT logger 进程 | **2**（REC4/REC7 各 1） | 每个最长 **120 秒**；启动前清残留；每编号至多 1 个 logger |
| 主动复位 | **6**（S1b①/S2②/S3③/S4④/S5⑤/S6⑥） | FR4 替代路径下复位⑤来自备用会话，恒为 6 |
| 身份/RTT 签名核对会话 | **≤2**（REC4/REC7 前各 1） | 仅 mem8 读 RTT 签名（Test-P1RttSignature）；不写块、不复位、不产生持久写入 |
| REC6 失败收尾 | 与成功路径共用 | 见 §6 |
| 计划外 nRESET | 单步 ≥2 次或全程累计 >2 次 → 停止 | 每次按次登记于轮次报告；幂等说明仅解释已发生事件，不构成复位授权 |
| 不包含 | App 烧录、QSPI 槽写入、断电注错、STAGE_SLOTS/INSTALL_SLOT/CORRUPT_SLOT、升级闭环 | 授权明示排除；与 O 序列、历史 A1/B1-M 配额不互借 |

## 8. RTT 采集纪律（REC4/REC7 共用；数值不变）

| 项 | 数值/规则 |
| --- | --- |
| logger 残留清理 | 启动前 `Stop-P1RttLogger` + 确认零残留；用户侧 RTT Viewer 须关闭（单读指针互抢） |
| RTT 地址来源 | 生产 App map 严格符号行 `^\s*_SEGGER_RTT\s+$` 解析（Get-P1MapRttAddress）+ 签名核对会话读到 `53 45 47 47 45 52 20 52 54 54` 后才可用；每次复位后重查（地址可漂移） |
| 采集窗口 | logger **120 s** 硬超时；复位会话内 `Sleep 8000` 先让自报行落入 buffer（§3） |
| 目标行匹配 | `OTA: BCB already CONFIRMED vcode=30200`（精确子串；REC4 与 REC7 同一行） |
| 轮询 | logger 退出/超时后一次性读取输出文件判定；**每编号至多 1 个 logger 进程**，无进程内重启轮询 |
| 备用动作 | REC4 无行 → §6 FR4 备用会话（1 次，替代 S5）；REC7 无行 → FR6 停止。无其他备用 |
| 采集后 | 再确认零残留 logger；输出文件 + 时间戳 + SHA 登记留证 |

## 9. 执行入口（受管脚本）

- 脚本：`Tools/jlink/p3-3-recovery-execute.ps1`（ASCII）。
- 分 Phase 入口，每个 Phase 独立调用、独立留证、fail-closed：
  `S1A | S1B | S2 | S3 | S4 | S5 | S6`（S4/S6 各含签名核对 + logger）。
- 参数：`-Phase`、`-RunDirectory`（不存在才创建，全部输出收敛于
  `<repo>/.cache/p3-3-recovery-execute/<round>/`）、`-ProductionBootBin`
  （默认主 worktree `build-gcc-release/boot/X-Track-Boot.bin`，执行时
  先复制进 RunDirectory 并 SHA 登记，断言 14,724B 与哈希）、
  `-TestBootHex`（默认 `.cache/p3-3-recovery-boot/boot/X-Track-Boot.hex`，
  断言 SHA-256 `409d4f16…` 与 HEX 范围）、`-ProductionAppMap`（生产 App
  map，RTT 地址解析）、`-RttTimeoutSeconds`（默认 120）。
- 每 Phase 结束输出 `REC*_RESULT=PASS` 摘要行 + 关键实测值；任一断言
  失败即抛错停止（不自动重试、不自动进入下一 Phase）。
- 脚本不实现「一键 ALL」：逐 Phase 由执行会话调用并核对证据后再推进，
  与 §6 失败即停原则一致。

## 10. 边界声明

- 本版文档零真机操作；执行授权 `P3-3-EXEC-AUTH-20260913` 已覆盖 REC0-REC7
  执行一次，**以独立复核通过为前置**（操作单第五版 + 本版）。
- 源码行号基线：本 worktree 当前 HEAD；freeze_commit 后相关文件变化须
  复核升版。
- 不直接改写 BCB 数字：S3 清空由固件 CLEAR_BCB 代码执行，S4 重建值取
  自真实 App 镜像头；字节级回滚备份（S2 BCB raw）仅在恢复流程翻车且
  另行获批时使用。S1a 备份的尾部 5,756B 是板上未知原值——恢复目标是
  **还原原样**，不是重写为任何假定值。
