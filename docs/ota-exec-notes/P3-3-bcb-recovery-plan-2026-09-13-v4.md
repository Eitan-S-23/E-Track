# P3-3 BCB 一致性恢复方案（2026-09-13 第四版）

> 依据：用户 2026-09-13 第四轮裁定第 1 条（BCB 恢复三项整改）。本版取代
> `P3-3-bcb-recovery-plan-2026-09-13-v3.md`（v3 保留作历史）。v3 的 §1 恢复
> 语义、§2 源码实证（命令处理时机/HOLD/结果块/CLEAR_BCB/SNAPSHOT 行为）、
> v2 §1 证据核实（30200/20801 身份、385 不自愈）全部继续有效，本版不重复。
>
> 本版四项修正（g-j，接续 v3 §0 的 a-f）已全部落地为 runner 代码 + 离线
> 验证（`Tools/jlink/test-p1-6-recovery-cmd.ps1`，24/24 PASS；公共函数在
> `Tools/jlink/p1-6-common.ps1`，两者均入 Validation profile required_paths），
> **未上板**（裁定明示不授权上板验证）。

## 0. 第四轮修正映射

| 修正 | v3 缺陷 | v4 落点 |
| --- | --- | --- |
| g RAM 提交时序缺口 | v3 §2 称「写块时序安全（staged magic=0 逐字写入）」——staged 文件 magic=0 不证明板上 RAM magic=0；板上残留旧 COMMAND/ARM/DONE magic + 新 body 会在最后一次 magic 写入前解析为有效命令（离线 T12 复现：cmd/arm/done 全 True） | §2.1 失效优先两阶段：每个命令会话先独立失效会话（w4 magic=0 + savebin 读回 + 程序化断言 magic==0 且 decode 全 invalid，fail-closed），通过后才写 body。runner：`Invoke-P16ControlInvalidate` 已内置于 `Write-P16BlockInPlace` 与 `Invoke-P16StartEncodedControl` 两入口（离线 T18 锁定）。穷举证明：130 个中断点中除「失效前完整旧态（确定性已知）」与「提交后完整新命令」外全部 invalid（T13/T13b，COMMAND/ARM/DONE/garbage 四种初始态） |
| h Boot 恢复范围不完整 | v3 §3 S6/§4 称生产 Boot「16KB bin」「0x08000000-0x08003FFF」——磁盘实测 **14,724 B**（非 16,384）；测试 Boot 18,720 B、HEX 末址 0x0800491F。仅 loadbin/verifybin 较短生产文件不能证明测试 Boot 多写区域已还原；v3 默认尾部为可还原区 | §3 S0/S6：受影响区域 = **0x08000000-0x08004FFF（20,480 B = 5×4KB 扇区）**，按实测推导（HEX 数据末址 0x0800491F 落扇区 4；扇区 4KB 依据 `at32f435_437_flash.c:744` 注释）。S0 全区备份 + 锚点断言（前 14,724 B 与磁盘生产 bin 逐字节全等）+ 尾部 5,756 B 板上原值登记 SHA（**不假定 0xFF**）；S6 loadbin 备份全区 + verifybin + 全区读回 SHA 全等。**不扩大擦除**：恢复重写的正是测试 Boot 已擦的扇区 0-4；执行前以 S1 烧录日志实际 erase 信息核对边界，实测超出本范围即停止重新申报。runner：`Invoke-P16BootRegionBackup` / `Assert-P16BootBackupMatchesProduction` / `Invoke-P16BootRegionRestore`（离线 T16/T16b/T17/T17b/T17c） |
| i REC4/FR4 澄清 | v3 §6 FR4 称定位 SNAPSHOT 为「只读……不写 EEPROM/flash」——错误：SNAPSHOT 是完整 P1-6 命令会话（RAM 写 512B + 复位 + HOLD）；未写明与 REC5 的替代关系、轮询/RTT 连接/备用动作次数与超时；S4 备注「计划外 nRESET 不构成失败」可被读作无限复位默许 | §3 S4、§6 FR4、§7-§8 全部重写：定位会话如实归类（含 RAM 写入与 1 次复位）、与 REC5 明确「同形态同判据一次消费不叠加」、RTT 轮询/超时/备用次数写死数值、计划外 nRESET 设登记阈值 |
| j 首次启用测试 Boot 前控制块受控 | v3 未要求 S1 之后、首个命令会话之前对板上控制块做受控处理；复位不清 RAM，若 RAM 恰有残留有效旧命令，复位①/②后 boot 可能执行非预期命令 | §3 S1 表格新增「控制块受控」要素：复位①后、S2 之前必须先执行失效会话（与 g 同一机制）；该失效已内置于每个命令会话 Phase 0，S2 的失效会话即首次命令前的受控动作 |

## 1. 恢复语义（不变）

见 v3 §1：清空 BCB → NONE → 内部 App 镜像头 version_code=30200 重建
CONFIRMED。目标态 `CONFIRMED(30200)+App 3.2.0+生产 Boot`。

## 2. 固件命令执行模型（v3 §2 全部有效，本节补充）

### 2.1 控制块写入时序（修正 g/j）

每个 P1-6 命令会话 = **两个 J-Link 连接**（v3 为一个）：

```
Phase 0  失效会话（Invoke-P16ControlInvalidate）：
  h
  w4 0x20057E00, 0x00000000        # 先把板上 magic 清零
  savebin <pre-readback.bin>, 0x20057E00, 512
  qc
  → 主机程序化断言：读回 512B、magic==0、decode 全部 invalid，
    任一不满足立即 throw（fail-closed，不写任何 body word）

Phase 1  启动会话（Invoke-P16StartEncodedControl -StartMode Reset）：
  h
  w4 0x20057E04..0x20057FFC ×127   # body（staged，magic 仍为 0）
  w4 0x20057E00, <magic>           # 最后提交 magic
  savebin <write-readback.bin>     # 写入读回
  verifybin <committed.bin>, 0x20057E00
  r  g                             # 复位：boot 执行命令 → HOLD
  Sleep <wait>
  h
  savebin <capture.bin>, 0x20057E00, 512   # 采结果块
  qc
  → 写入读回 SHA 与 committed 全等 + 结构有效 + 结果块按 Expected 断言
```

- **残余唯一窗口** = Phase 0 的 w4 失效之前中断 = 板上完整旧状态
  （确定性已知：上一会话的结果块或受控失效态），不存在 magic/body 混合态。
- 中断穷举（离线 T13/T13b）：COMMAND 初始态全 130 步、ARM/DONE/garbage
  初始态关键 5 步，除 Step 0（完整旧态）与 Step 129（完整新命令）外全部
  parse 为 invalid，violations=0。
- S1 烧录测试 Boot 后的**首次**命令会话（S2）的 Phase 0 即「首次启用测试
  Boot 前控制块受控」：复位①后 RAM 内容不受控（复位不清 SRAM），必须先
  失效并断言，才允许写入第一条命令（修正 j）。

### 2.2 Boot 区受影响区域（修正 h，实测绑定）

| 事实 | 数值 | 来源 |
| --- | --- | --- |
| 生产 Boot bin | **14,724 B**（0x3984，末字节 0x08003983） | 主 worktree `build-gcc-release/boot/X-Track-Boot.bin` 实测 |
| 测试 Boot bin / HEX 末址 | 18,720 B / **0x0800491F** | #25 产物（SHA-16 `ABD042DB09B27198`），HEX 全记录解析（离线 T17 独立复算一致） |
| flash 扇区 | 4 KB | `at32f435_437_flash.c:744`「every bit is used to protect the 4KB bytes」 |
| 受影响区域 | **0x08000000-0x08004FFF（20,480 B，扇区 0-4）** | 0x0800491F 落扇区 4 → 上界扇区对齐 |
| 尾部未知区 | 5,756 B（0x08003984-0x08004FFF） | 生产 bin 之外、测试 Boot 之前板上内容**未知**，登记 SHA，不假定 0xFF |

执行前核对（写进 S1/S6 验收）：S1 烧录日志的 erase 信息必须与上表边界
一致；**实测擦除超出 0x08004FFF 时立即停止**，按实际边界重新申报备份/
恢复范围后才能继续（不得默认剩余区域可牺牲，也不得未经批准扩大擦除）。

## 3. 操作序列 v4（复位 6 次 + FR4 备用至多 1 次额外；会话 10-12 个）

### S0（REC0）Boot 区全区备份 —— REC1 的前置，无复位

| 要素 | 内容 |
| --- | --- |
| 操作 | `Invoke-P16BootRegionBackup`：savebin 0x08000000/0x5000（1 个 J-Link 会话） |
| 写入 | 无（只读 flash） |
| 校验 | 读回 20,480 B；`Assert-P16BootBackupMatchesProduction`：前 14,724 B 与磁盘生产 Boot bin **逐字节全等**（备份有效性锚点，离线 T16 正例/T16b 负例：前缀篡改 1 字节、备份短于生产 bin 均拒绝）；全区 SHA-256 与尾部 5,756 B SHA 登记 |
| 失败 | 锚点失配 → HARNESS_FAIL：板上 Boot 与磁盘生产 bin 不一致（前提坍塌，S6 恢复目标错误），停止重核板识别轮证据 |

### S1（REC1）烧录 P1_6_TEST_ENABLE Boot —— 复位①

| 要素 | 内容 |
| --- | --- |
| 操作 | J-Link `loadfile <#25 X-Track-Boot.hex>`（静态解析 HEX 范围=0x08000000-0x0800491F，预检不过不烧；烧前核对 hex SHA `409d4f16…`）→ `r` `g`（复位①） |
| 写入 | 内部 flash 0x08000000-0x08004FFF（§2.2 受影响区域；擦除以烧录日志 erase 信息留证并与 §2.2 边界核对） |
| 控制块受控（修正 j） | 复位①后、S2 之前**不写任何命令**；S2 的 Phase 0 失效会话即首次命令前的受控动作（RAM 在复位后内容不受控，必须先失效断言） |
| 预期后态 | BCB 仍 CONFIRMED(20801)；复位①后 P1_6 Boot 正常路径 jump App 3.2.0 |
| 失败 | §6 FR1 |

### S2（REC2）SNAPSHOT 基线 —— 复位②（2 会话）

控制块 opcode=4/arg0=0/arg1=1(BCB_ONLY)；走 §2.1 两阶段。
EEPROM/flash 只读；**BCB_A_RAW/BCB_B_RAW 原始 128B 留档**（清空前唯一
字节级备份）。裁剪选项（默认保留，审批时裁定）见 v3 §3 S2。

### S3（REC3）CLEAR_BCB —— 复位③（2 会话；唯一 BCB 持久清空）

控制块 opcode=1；前置 validate_internal_app；EEPROM 0x00-0x7F 写全 0xFF
（128B，持久）+ RAM 512B。结果块快照须显示 active=NONE、双块 raw 全 0xFF。

### S4（REC4）显式复位触发重建 —— 复位④（1 会话 + 1 RTT logger 进程）

| 要素 | 内容 |
| --- | --- |
| 操作 | J-Link 单会话 `r` `g`（复位④，不写任何块：上一步结果块 magic=DONE ≠ COMMAND → boot 走 NO_REQUEST 正常路径）→ 退出后启动 RTT logger 采集（纪律见 §8） |
| 写入 | **EEPROM BCB 区：状态机 NONE 分支 commit_confirmed 写非主导块（64B 记录，持久）**——复位本身即写 EEPROM 的触发器 |
| 预期 | NONE → commit_confirmed(cur_vcode=**30200**) → CONFIRMED → jump App 3.2.0 |
| 结果校验 | RTT logger 采集 App 启动自报 `OTA: BCB already CONFIRMED vcode=30200`（RTT 地址用板上 App 生产 map `_SEGGER_RTT`，2026-09-12 板识别轮已验证） |
| 失败 | 无自报行 → §6 FR4（**注意：FR4 备用会话含 RAM 写入与 1 次复位，不是只读**） |

### S5（REC5）SNAPSHOT 终态核验 —— 复位⑤（2 会话）

同 S2 形态。结果校验：kind=done、status=PASS；快照 CONFIRMED /
cur_vcode=30200 / seq 从 0 起 / CRC 有效；app 快照 vcode=30200。
**与 FR4 备用会话的关系见 §6 FR4——一次消费，不叠加。**

### S6（REC6）Boot 全区恢复 + REC7 RTT 终证 —— 复位⑥（1 会话 + 1 logger）

| 要素 | 内容 |
| --- | --- |
| 操作 | `Invoke-P16BootRegionRestore`：loadbin S0 备份全区 @0x08000000 + verifybin（log 断言 `Verify successful.` 恰 1 次）+ savebin 全区读回 + **SHA-256 与 S0 备份全等** + 尺寸 20,480 守卫（离线 T17b/T17c）→ 会话尾部 `r` `g`（复位⑥） |
| 写入 | 内部 flash 0x08000000-0x08004FFF **从 S0 备份逐字节还原**（含尾部 5,756 B 板上原值——不是只写生产 bin 的前 14,724 B）；恢复重写的扇区 0-4 正是 S1 已擦的扇区，**不扩大擦除** |
| 预期 | 生产 Boot（无 P1_6 钩子）→ CONFIRMED(30200) jump App |
| 结果校验（REC7） | RTT logger 采集**生产 App** 新鲜自报 `OTA: BCB already CONFIRMED vcode=30200`（纪律见 §8） |
| 失败 | §6 FR6 |

## 4. 写入/擦除范围总账（修正 h）

| 步 | 目标 | 区域 | 字节 | 持久性 |
| --- | --- | --- | --- | --- |
| S0 | Boot 区 | 0x08000000-0x08004FFF 只读备份 | 20,480（读） | — |
| S1 | Boot 区 | 内部 flash 0x08000000-0x08004FFF（扇区 0-4） | 20,480（擦+写） | 持久（S6 还原） |
| S2/S5 | RAM 控制块 | 0x20057E00-0x20057FFF（含 Phase 0 失效写） | 512+4 | 非持久 |
| S3 | EEPROM BCB | **0x00-0x7F 写全 0xFF** | 128 | **持久（不可逆：原 20801 记录清除，仅 S2 备份留档）** |
| S4 | EEPROM BCB | 非主导块 commit_confirmed 记录 | ≤64 | 持久 |
| S6 | Boot 区 | 内部 flash 0x08000000-0x08004FFF 从 S0 备份还原 | 20,480 | 持久（还原，SHA 全等核验） |
| 全程 | App 区 | **0x08010000（内部 Flash）零写入**；QSPI 槽零写入 | 0 | — |

## 5. 完成判据（四条全部满足）

1. **生产 Boot 已按全区恢复**：S6 verifybin 成功 + 全区读回 SHA-256 与
   S0 备份全等（含尾部 5,756 B 板上原值）+ S0 锚点断言通过（备份前
   14,724 B = 磁盘生产 bin，证明备份就是生产 Boot + 板上原尾部的忠实
   快照）。可选增强：S6 后另采一次 savebin 与 S0 备份二次比对。
2. **App 身份未变**：S5（或 FR4 备用会话，见 §6）快照 app_vcode=30200、
   app_sha256 与板上镜像身份证据一致；App 区零写入由 S1/S6 地址范围
   预检+留证保证。
3. **BCB 与 App 一致**：S5（或 FR4 备用会话）快照 CONFIRMED /
   cur_vcode=30200 / CRC 有效（boot 侧独立读 EEPROM）。
4. **新鲜终证**：REC7 生产 App RTT 自报 `OTA: BCB already CONFIRMED
   vcode=30200`。

## 6. 失败分类与额度（默认零自动重试）

| 编号 | 失败点 | 分类 | 处理 |
| --- | --- | --- | --- |
| FR0 | S0 备份锚点失配 / 读回失败 | HARNESS_FAIL | 停止；板上 Boot 身份与磁盘生产 bin 不一致，重核板识别轮证据后才可重新申报 |
| FR1 | S1 烧录/verify 失败 | HARNESS_FAIL | 留证停止；J-Link 读回比对评估半写状态；**不自动重烧**（追加烧录另行申报） |
| FR2 | S2 快照与 2026-09-12 证据不符 | EVIDENCE_GAP | 停止，重新核实全部前提；不得继续 S3 |
| FR3 | S3 `detail=EEPROM` | PRODUCT_FAIL | 留证停止，**零重试**；字节级恢复须用 S2 备份+另行授权 |
| FR3b | S3 `detail=APP_INVALID` | PRODUCT_FAIL | 未写 EEPROM，留证停止；恢复方案整体作废重审 |
| FR4 | S4 无 App 自报行（RTT 120s 窗口内未匹配） | PRODUCT_FAIL | 见下文 **FR4 备用会话**专节 |
| FR5 | S5 快照不符 | PRODUCT_FAIL | 留证停止；与 S4 自报行交叉定位（App 侧/boot 侧读数不一致属严重异常，单独分类报告） |
| FR6 | S6 恢复失败（烧录/verify/读回 SHA 失配） | HARNESS_FAIL | 留证停止，零自动重试；**测试 Boot 残留不满足 §5 判据 1**，实机判据 ENV_BLOCKED，追加恢复另行申报 |

### FR4 备用会话（修正 i，取代 v3「只读 SNAPSHOT 定位」表述）

- **如实归类**：备用会话 = 完整 SNAPSHOT 命令会话（§2.1 两阶段，
  2 个 J-Link 连接）——**含 RAM 控制块 512B+4B 写入与 1 次复位⑤**，
  EEPROM/flash 只读。「免费只读」表述作废；它是一次真实的命令执行。
- **与 REC5 的关系（明确）**：备用会话与 REC5 **同形态、同判据**。
  - 若备用会话返回 kind=done、status=PASS 且快照满足 §3 S5 全部结果
    校验（CONFIRMED / cur_vcode=30200 / seq 从 0 起 / CRC 有效 /
    app_vcode=30200），则该会话**即为终态核验**，REC5 视为已消费——
    不再单独执行 REC5（避免「定位一次、正式再来一次」的重复复位）。
    此路径下总复位 = 6（S1-S4 + 备用复位⑤ + S6 复位⑥）。
  - 若快照异常 → 停止（FR5 口径），**不得再执行 REC5 盲试**。
  - 即正常路径 REC5 照常执行；只有 FR4 触发时备用会话**替代** REC5。
- **次数**：恰 1 次，无更多备用；触发后总复位数 6→7、总会话数 10→12，
  已计入 §7 申报。
- 仍不明 → 停止；**禁止连续复位盲试**（NONE+有效 App 每次复位都重建，
  重复复位只会重复同一结果）。

## 7. 授权申报（REC 独立编号，未批未执行）

| 编号 | 内容 | J-Link 会话 | 复位 | 持久写入 |
| --- | --- | --- | --- | --- |
| REC0 | S0 Boot 全区备份（savebin 20,480B + 锚点断言 + SHA 登记） | 1 | 0 | 无（只读） |
| REC1 | S1 烧录测试 Boot（HEX 范围预检、SHA 核对、loadfile、erase 边界核对） | 1 | 1（①） | Boot 区 20,480B |
| REC2 | S2 SNAPSHOT 基线命令会话（两阶段） | 2 | 1（②） | 仅 RAM |
| REC3 | S3 CLEAR_BCB 命令会话（两阶段）——**EEPROM 0x00-0x7F 持久清空** | 2 | 1（③） | **EEPROM 128B** |
| REC4 | S4 复位会话 + RTT logger 采集 App 自报（§8 纪律） | 1 + logger×1 | 1（④） | EEPROM commit 记录（复位触发） |
| REC5 | S5 SNAPSHOT 终态核验命令会话（两阶段；FR4 触发时被备用会话替代） | 2 | 1（⑤） | 仅 RAM |
| REC6 | S6 Boot 全区恢复（loadbin+verifybin+全区读回 SHA 全等） | 1 | 1（⑥） | Boot 区 20,480B（还原） |
| REC7 | S6 后 RTT logger 采集生产 App 终证行 | logger×1 | 0 | 无 |

- 合计：复位 **6 次**（FR4 备用触发时 7 次）；J-Link 会话 **10 个** +
  RTT logger 进程 2 个（FR4 备用触发时 12 个）。v3「每命令 1 会话」
  作废——失效门禁使每个命令会话 +1 连接（修正 g/j 的直接代价）。
- **计划外 nRESET 阈值（修正 i）**：J-Link 连接按「每次都可能触发
  nRESET」最坏情况申报（本板 2026-09-12 观测过一次）。S4 备注的
  「NONE 态计划外复位与重建结果幂等」**仅用于解释已发生事件的登记
  口径，不构成任何额外复位授权**。执行中每次计划外复位按次登记于
  轮次报告；**单步内 ≥2 次或全程累计 >2 次 → 立即停止**，重新申报
  后才可继续。
- **不包含**：App 烧录、QSPI 槽写入、断电注错、STAGE_SLOTS/
  INSTALL_SLOT/CORRUPT_SLOT、升级闭环（另按各自授权）；本单与 A1/B1-M/
  升级闭环配额互不借用。

## 8. RTT 采集纪律（REC4/REC7 共用，数值写死）

| 项 | 数值/规则 |
| --- | --- |
| logger 残留清理 | 启动前 `Stop-Process -Name JLinkRTTLogger -Force`，确认零残留；用户侧 RTT Viewer 须关闭（单读指针互抢） |
| RTT 地址来源 | 生产 App map 严格符号行 `^\s*_SEGGER_RTT\s+` 解析 + `mem8 <RTT> 16` 读到 `53 45 47 47 45 52 20 52 54 54` 签名后才可用；每次复位后重查（地址可漂移） |
| 采集窗口 | logger 启动后 **120 s** 硬超时（App 启动自报行在启动后数秒内出现，120 s 留足裕量；`timeout` 包裹，超时自动终止） |
| 目标行匹配 | `OTA: BCB already CONFIRMED vcode=30200`（精确子串；REC4 与 REC7 同一行） |
| 轮询 | logger 退出/超时后一次性读取输出文件判定；无进程内反复重启 logger 的轮询——**每编号至多 1 个 logger 进程** |
| 备用动作 | REC4 无行 → §6 FR4 备用会话（1 次）；REC7 无行 → FR6 停止。无其他备用 |
| 采集后 | 再确认零残留 logger；输出文件 + 时间戳 + SHA 登记留证 |

## 9. 对合同/操作单的影响

- `EXT-BOARD-STATE`：fingerprint/evidence_sha256 待 §5 四条证据齐后回填。
- C-TOY-LOOP / C-REAL-LOOP 前置 = §5 四条全部满足。
- 实机操作单第四版（同批 #35 修订）的前置链、O1 证书方法、D 序列与
  EXT 引用同步本版 REC0/S0、全区恢复口径与 §8 RTT 纪律。
- 云端写入单 B0-B4 暂停标注维持（#20）。

## 10. 边界声明

- 本版文档零真机操作；runner 代码改动（`Tools/jlink/p1-6-common.ps1`
  新增失效门禁三函数、Boot 全区备份/锚点/恢复三函数、
  `Invoke-P16StartEncodedControl` 内置 Phase 0）已离线验证
  **24/24 PASS**（T1-T11 原 v3 项 + T12-T15 时序修复 + T16-T18 Boot
  范围与门禁）。烧录与全部 REC **未批未执行**。
- 源码行号基线：本 worktree 当前 HEAD（同 v3 §9 列表）；freeze_commit
  后相关文件变化须复核升版。
- 不直接改写 BCB 数字：S3 清空由固件 CLEAR_BCB 代码执行，S4 重建值取
  自真实 App 镜像头；字节级回滚备份（S2）仅在恢复流程翻车且另行获批时
  使用。S0 备份的尾部 5,756 B 是板上未知原值——恢复目标是**还原原样**，
  不是重写为任何假定值。
