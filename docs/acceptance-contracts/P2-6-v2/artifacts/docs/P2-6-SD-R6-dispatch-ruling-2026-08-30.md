# P2-6-SD-R6 非实现裁定书：推翻 R5 "payload 消失" 事实认定，改判 EVIDENCE_GAP 并授权只读判别路线

- 裁定编号：`P2-6-BR-20260830-SD-R6-01`
- 日期：2026-08-30
- 裁定人：独立验收 / 非实现会话（非 R5 实现方，未参与 R5 任何实现或硬件动作）
- 输入：`docs/ota-exec-notes/P2-6-SD-R5-hw-execution-evidence-2026-08-30.md`（及 R5 派单裁定 / 阶段 0 / 独立复核三份）、
  证据根 `.cache/p2-6-sd-r5-20260830-01-implementation/`（原始 dump 与 result JSON，未修改）、
  生产源码只读核对 `Libraries/OTA/ota_layout.h`、`ota_staging.h`、`ota_slot_header.c`、`ota_backup.c`、
  `boot/src/boot_state_machine.c`、`boot/include/boot_slot.h`、`Libraries/EEPROM/eeprom_bcb.h`
- 方法：不采信 R5 摘要，全部结论由本会话在证据根上独立复算得出。本裁定未启动硬件、未写 target、
  未改动任何生产源码、冻结合同、既有证据根与已消耗配额。

---

## 0. 裁定摘要

| 问 | 裁定 |
|---|---|
| 1 升级闭环断链定性 | **推翻 PRODUCT_FAIL 候选**，改判 **EVIDENCE_GAP**；R5 §3.2/§3.3/§3.4 的核心事实认定（candidate/staging payload 全 FF、大块 XIP 读不可信）**不成立** |
| 2 定界路线 | **驳回** R5 提的两条（P1_6_TEST_ENABLE test boot、boot UART 物理抓取）；**授权** 一条纯只读三步判别 D1/D2/D3，合并 `1/1` |
| 3 FULL 上传 `1/1 FAIL` | 判 **HARNESS_FAIL**（流程顺序缺陷）；准予测试侧定点修复 + 补发 `1/1`；已消耗记录保留不抹除 |
| 4 C7 与 FULL 侧观测 | **准予独立先行**，不被 boot 侧未定界项阻塞（附一条约束） |
| 5 合同策略 | **现在冻结 `P2-6-v2`**，仅覆盖 PATCH 侧已闭合项；不与 boot 侧捆绑 |
| 6 R4-01 历史更正 | **采纳"来源不可区分"结论，但更换其成立理由**；R5 给出的理由随事实认定一并作废 |
| 附 边界偏离 | R5 对 candidate 槽头扇区的 erase+write 属**未授权 target 写入**，如实登记（§7） |

---

## 1. 问题一：升级闭环断链定性 —— 推翻 PRODUCT_FAIL 候选，改判 EVIDENCE_GAP

### 1.1 契约布局事实（只读源码，双侧一致）

```
Libraries/OTA/ota_layout.h:27      #define OTA_SLOT_HEADER_SIZE  0x1000
boot/include/boot_slot.h:10        #define BOOT_SLOT_HEADER_SIZE 32u
```

两个常量不是同一个东西：**槽头扇区 4096 B**，其中只有**前 32 B** 是 ETSL 描述符，
其余按设计为擦除态 `FF`（staging 另在 `+0x040` 放 44 B ETRJ、`+0x070` 放 64 B bitmap，
见 `Libraries/OTA/ota_staging.h:13-22`）。**槽 payload 起点恒为 `slot_base + 0x1000`**，
boot 与固件双侧引用同一常量：

```
boot/src/boot_state_machine.c:175   io->external_read(..., slot_base + OTA_SLOT_HEADER_SIZE + offset, ...)
boot/src/boot_state_machine.c:189   context.base = slot_base + OTA_SLOT_HEADER_SIZE;
boot/src/boot_state_machine.c:209   bcb->cand_addr != slot_base + OTA_SLOT_HEADER_SIZE
boot/src/boot_state_machine.c:229   source->payload_address = slot_base + OTA_SLOT_HEADER_SIZE;
Libraries/OTA/ota_backup.c:395/404  OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE
Libraries/OTA/ota_backup.c:570      next.cand_addr = OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE;
```

### 1.2 R5 全部 "payload 全 FF" 观测均落在头扇区内

| R5 产物 | 字节 | FF 占比（本会话复算） | 落点 | 判定 |
|---|---|---|---|---|
| `ext-cand-head-2k.bin` | 2048 | **100 %** | `[cand+0x0020, +0x1000)` 区间内 | 头扇区填充，**设计如此** |
| `ext-cand-fwheader.bin` | 96 | **100 %** | `cand+0x400`（错址；真 fw_header 在 `cand+0x1400`） | 头扇区填充，**设计如此** |
| `cpu-read-cand.bin` 前 1280 B | 2560 | 前 1280 B 全 FF | 头扇区内 | 头扇区填充，**设计如此** |
| `cpu-read-staging.bin` 首 32 B | 320 | 首 32 B 全 FF | `[stg+0x0020, +0x0040)` | ETSL 与 ETRJ 之间的填充，**设计如此** |

**R5 从未读取过任何一个槽的 payload 区（`+0x1000` 起）**，却据此判定 "payload 全 FF / 消失"。

### 1.3 两个越过 `+0x1000` 的 dump 直接证伪 "payload 消失"

本会话对证据根原始二进制与冻结权威镜像
`.cache/p2-6-sd-ota/assets/X-Track-App-GCC-p2-6a-test-v2.8.1.finalized.bin`
（600744 B / SHA-256 `A2D3083B25EE3281…`）逐字节复算：

```
cpu-read-cand-fe0.bin[32:64] = 00800520 d5b60108 5db70108 6d140408 5db70108 5db70108 5db70108 00000000
img[0x00:0x20]               = 00800520 d5b60108 5db70108 6d140408 5db70108 5db70108 5db70108 00000000
                                                                                    ==> 逐字节相等
ext-cand-mid-4k.bin (4096 B) == img[0x49000:0x4A000]                                ==> 全量相等
```

即：**candidate 槽在 `+0x1000` 处正是权威 v2.8.1 镜像的第 0 字节，在 `+0x4A000` 处正是镜像
偏移 `0x49000` 的 4 KB**。两点均满足 `flash[A] == img[A - 0x1000]`。

因此 R5 实验 1 的结论 "读址 A 得 `image[A-0x1000]`，故 J-Link/CPU 大块 XIP 连续读不可信"
是**误判**：`A-0x1000` 恰是契约布局本身，读到的是**真实且正确**的 payload。以该误判为前提的
实验 2（"头部 1KB+fw_header 区全 FF"）、实验 3/4 的推论链随之失效，§3.4 所谓 "未定界的矛盾"
在正确口径下**不存在**。

### 1.4 staging 侧同样完好

`cpu-read-staging.bin` 的 `+0x20` 处 44 B：

```
4554524a 2b0accae abd88572 f1dae98a 7ab66df5 11f48d09 95305372 81fda36a f37c9d2b 31010000 83f27965
"ETRJ" | ──────────────── 32 B image sha256 (2B0ACCAE…) ──────────────── | len=305 | crc
```

与 `Libraries/OTA/ota_staging.c:175-189` 的 `encode_etrj` / `etrj_matches` 及
`ota_staging.h:13/20`（`OTA_STAGING_ETRJ_SIZE=44`、`OTA_STAGING_ETRJ_OFFSET=0x040`）完全吻合，
说明该 dump 起点为 `OTA_EXT_STAGING + 0x20`，**ETRJ 记账记录完整且正确**（sha 前缀 `2B0ACCAE`
即冻结 PATCH `.etu` 的 SHA-256 前缀，len 305 即其字节数，均经本会话对
`assets/P2-6A-PATCH-v2.8.0-to-v2.8.1.etu` 复算确认）。staging payload 位于 `+0x1000`，R5 未读。

### 1.5 R5 诊断代码的字段口径亦错（旁证）

`logs/r5-extflash-diag-gdb.log:11` 与 `r5-extflash-diag2-gdb.log:12`：

```
DIAG staging_hdr: len=1280529477 crc=0xffffff03 vcode=0x00000131
```

对照原始字节 `ext-staging-header.bin` = `4554534c 03ffffff 31010000 1e1889f2 …`
与 `ota_slot_header.c:16-17`（`PAYLOAD_LEN_OFF=8`、`PAYLOAD_CRC_OFF=12`）可知：
该诊断把 **magic 当 len、type 当 crc、len 当 vcode**，整体错位两个字段。R5 §3.2 表格中的正确
数值是事后手工从原始 dump 反推的，其诊断程序本身的口径从未修正。

### 1.6 定性结论

1. **没有 "payload 消失"，也没有 "写入假成功"。** QSPI 写路径、staging 记账、candidate 落盘
   三者均有**正面**证据成立；R5 实验 5/6（受控写 + 跨复位持久）只是重复证明了本就成立的事实。
2. 唯一仍然成立的观测事实是：**复位后板卡仍为 v2.8.0 且 BCB=CONFIRMED，boot 未把 candidate 升上去。**
3. 该事实的原因**未被任何现有证据触及**——R5 全程未读 BCB 的 `cand_addr/cand_len/cand_crc32/cand_vcode`
   四字段（`boot_state_machine.c:207-214` 的否决点）、未全量读回 candidate payload 复算 CRC32、
   未读 `cand+0x1400` 的 fw_header。
4. 故 **改判 `EVIDENCE_GAP`，不得记为 `PRODUCT_FAIL`**。P2-6 卡不因本项转入产品缺陷登记；
   §9 变更登记表不新增产品契约条目。

---

## 2. 问题二：定界路线 —— 驳回两条重路线，授权只读三步判别

### 2.1 驳回理由

R5 提的两条（① 带 checkpoint 的 `P1_6_TEST_ENABLE` test boot；② boot UART 日志物理抓取）
都以 "payload 神秘消失" 为前提，成本高（前者需改并烧录 boot 镜像，后者需物理接线），
而在 §1 澄清后，**三个 boot 否决点全部可用纯只读手段先行排除**。在未排除廉价假设前投入
boot 镜像变更或物理接线，不符合最小充分原则。**本裁定不授权 boot 镜像变更、不授权 UART 接线、
不授权任何新的 OTA 端到端重跑。**

### 2.2 授权：D1/D2/D3 —— 合并为 **1 个只读 GDB session，配额 `1/1`**

> boot 的 STAGED 分支只有三处否决（`boot_state_machine.c:165-215`）：
> ETSL 头解析 → payload 全量 CRC32 → fw_header 校验 + BCB `cand_*` 四字段对照。
> D1/D2/D3 逐一对应，覆盖完全。

**D1（最优先，最便宜）——读 BCB 双块并逐字段对照**
- 目标：EEPROM `BCB_A_ADDR=0x00` 与 `BCB_B_ADDR=0x40` 各 64 B（`Libraries/EEPROM/eeprom_bcb.h:26-31`）。
- 解析字段（`bcb_t`，小端，off 见头文件 52-74 行）：
  `magic/schema_ver/state/boot_try/copy_phase/seq/resume_block/cand_addr/cand_len/cand_crc32/cand_vcode/cur_vcode/backup_len/backup_crc32/backup_vcode/crc32`。
- 判据：`cand_addr` 应 `== 0x00001000`、`cand_len == 600744`、`cand_crc32 == 0x53E81862`、
  `cand_vcode == 20801`（均取自 R5 已 dump 的 candidate ETSL 头 `ext-cand-header.bin`）。
  **任一项不等即命中 `boot_state_machine.c:207-214`，boot 的 rollback 是正确行为**，
  问题落在固件 apply 的 BCB 记账，而非 boot 消费链。
- 实现约束：BCB 在 I2C EEPROM，**不能直接 memdump**，需一次受控调用把两块读入 RAM 缓冲后 dump
  （与 R5 已获授权的 `Qspi_IsOtaDisabled()` 受控调用同类）。**该缓冲区是本轮唯一允许的 target
  RAM 写；严禁任何 EEPROM 写、严禁调用任何 `*_commit/*_write` 类 BCB 接口。**

**D2 —— 全量读回 candidate payload 并复算**
- 目标：`[0x001000, 0x001000 + 600744)`，复算 CRC32 与 SHA-256，对照 ETSL 头 `crc=0x53E81862`
  与权威镜像 `A2D3083B…D58E00`。
- 可行性已由 R19 证明：同规模 441 chunk 读回在 `monitor WriteU32 0xE0042008 0x00001000`
  （`DEBUG_WDT_PAUSE`）加持下可完成；**该行必须紧跟每个 `monitor halt`**。
- 此步判定 boot 的 CRC 校验是否本就会通过。

**D3 —— 读 fw_header**
- 目标：`[0x001000 + 0x400, +96)`，按 `boot_fw_header_validate` 口径校验，并核对
  `image_len == 600744`、`version_code == 20801`、`image_sha256[:8] == 0x9DB3C649`（ETSL `sha8`）。

**停止条件**：任一步失败即停，不重试、不换命令、不换地址、不启动第二个 session。

### 2.3 前置状态告警（必须先处理，否则后续任何 "再跑一次 boot" 都无意义）

R5 实验 5 已对 candidate 槽执行 `erase(0x0)` + 写入 256 B 图案。经本会话核对
`qspi_erase(uint32_t sec_addr)`（`Libraries/W25Q128/qspi_cmd_en25qh128a.h:97`，扇区粒度；
boot 侧对应 `boot_platform_qspi_erase_4k`）为 **4 KB 扇区擦**，故：

- `[0x000000, 0x001000)` 的 **ETSL 头已被销毁**，现为图案（`pattern-check.bin` /
  `pattern-check2.bin` 复算一致，首 16 B = `0000005b 0100005b 0200005b 0300005b`）；
- `[0x001000, …)` 的 **payload 未受损**（D2 因此仍可执行）。

**结论：板卡当前不存在有效 candidate 槽。** D1/D2/D3 是纯读，不受影响；但在补写 ETSL 头之前，
**任何基于复位后板卡版本的推断一律无效**，不得再据此生成新的 "未定界" 结论。

### 2.4 升级条件

仅当 D1/D2/D3 **全部通过**（即 boot 的三道否决在数据上都不该触发）时，才升级到需要可观测 boot
的路线；届时 `P1_6_TEST_ENABLE` 方案须**另行单独裁定**，本裁定不预先授权。

---

## 3. 问题三：FULL 上传 `1/1 FAIL` 配额处置 —— 判 HARNESS_FAIL，准予修复与补发

### 3.1 事实（本会话复算 `logs/p2-6-sd-r5-full-upload-hw-01-result.json`）

```
asset_kind=FULL  input_bytes=282367  input_sha256=84D3F384…D2E7  chunk_count=9
session/gdb_exit_code=41   session/transport_classification='GDB_FAIL'
session/server_natural_exit=True  session/ports_closed=True  session/session_error=None
readback_parse_error='MI readback event count mismatch: 0 != 828'
```

失败发生在上传前置检查阶段，`readback_blocks=[]`，未进入介质写入，未触碰 QSPI —— 与 R5 陈述一致。

### 3.2 判定

PATCH OTA 之后 BCB=`STAGED` 是**契约要求的正常态**（`boot_state_machine.c:590` 分支的入口条件），
uploader 却把 `BCB == CONFIRMED` 当作上传前置硬条件，属 harness 对被测状态机的错误假设，
**非产品缺陷** → `HARNESS_FAIL`。

### 3.3 授权

- **可改文件白名单（仅测试侧）**：`tests/ota/p2_6_rtt_sd_uploader.py`、
  `tests/ota/test_p2_6_rtt_sd_uploader.py`。
- 修复方向：前置条件放宽为 BCB 状态 ∈ {`CONFIRMED`, `STAGED`, `IDLE`}，或引入显式
  `--allow-bcb-state`；必须补一条离线负例，钉死"不得再把 `STAGED` 判为失败"，并保持
  其余 fail-closed 语义不变。
- **禁止**改动 `Libraries/OTA/**`、`boot/**`、`USER/**` 任何生产源码。
- **配额**：离线测试通过后补发 FULL 上传 `1/1`。R5 已消耗的那次 FAIL 作为 harness 缺陷记录
  **保留，不得抹除、不得重解释为未消耗**。

---

## 4. 问题四：C7 与 FULL 侧观测能否独立先行 —— 准予

- C7（异常退出后 overlay 释放 + LiveMap 重建）与 FULL 侧 C1 的观测对象是**固件内 apply/overlay
  生命周期**，证据取自 App 运行期的 RTT 测量记录；而未定界项在 **boot 消费链**。两者证据面不相交，
  无因果耦合。
- R5 本轮已在真机证明该测量链可完整闭合（两段式采集 `rtt_channel_binding_verified=true`、
  postcheck 仅 4 B RdOff 字变化）。
- **裁定**：FULL 上传补发 `1/1` 通过后，FULL OTA `1/1`、异常退出 `1/1`、LiveMap `1/1`
  可按原配额继续，不必等待 boot 侧定界。
- **约束（必须写入执行任务书）**：这些轮次同样会把 BCB 推到 `STAGED` 并写 candidate 槽；
  每轮之间是否需要复位/回收，须依 D 系列结论决定；**不得**再以"复位后没升级"为由生成
  新的未定界结论或新的 PRODUCT_FAIL 候选。

---

## 5. 问题五：合同策略 —— 现在冻结 `P2-6-v2`，不捆绑

- **理由**：R5 的 PATCH 侧测量链证据自洽且完整（transport=PASS、两段式 binding verified、
  全部门禁通过：`workspace_peak=21792 ≤ 40960`、`stack_peak=3252 ≤ 8192`、
  `sbrk/TLSF` 增量 0、`guard_entry=guard_exit=1`），与 boot 消费链问题**证据面不相交**。
  捆绑等待会让已到手证据随时间衰减，也违反"任务状态与单轮验收结果分离"原则。
- **具体要求**：以 `docs/acceptance-contracts/P2-6-v1.contract.json`
  （17416 B / SHA-256 `BFE0F5931BEED31FE658002DBF22A814650E9A74D6C495D21D6EC710F00C9F48`）为父，
  `task_id` **不变**、`version = 2`、`parent_contract_sha256` 绑定 v1；新增覆盖 PATCH 侧
  C2/C4/C5/C6/C14 的判据与 R5 证据根产物（`p2-6-sd-r5-patch-ota-hw-01-*` 全套，含
  `rtt-payload.raw.log` / `rtt-pending.bin` / `rtt-cb-pre.bin` / `rtt-cb-post.bin` / `result.json`）。
- FULL 侧判据与 boot 消费链判据**不写入 v2**，留待 v3。
- 冻结与 `python Tools/acceptance/validate_bundle.py --contract … --matrix … --repo-root <本轮精确 worktree>`
  校验由**非 R5 实现方**执行；校验失败不得宣告通过。

---

## 6. 问题六：R4-01 历史更正 —— 采纳结论，更换理由

- **采纳**：R4-01 之后板卡呈 v2.8.1 一事，无法在"boot apply 成功"与"R19 冒烟 B 的权威恢复"
  之间区分，历史上把它当作 boot apply 成功的证据应**降级为未证实**。
- **更换理由**：R5 给出的支撑理由（"boot 消费链存在未定界失败模式"）建立在被 §1 推翻的
  payload-FF 事实上，**随之作废**。该更正改以如下独立理由成立：R19 冒烟 B 明确执行过
  全镜像 `loadbin + verifybin` 权威恢复（`P2-6-BR-20260829-RTT-BIND-R19-implementation-evidence.md`
  §5.2 / §6），存在与 boot 完全无关的 v2.8.1 来源，故来源不可归因。
- **回写范围**：`PLAN-OTA-EXEC.md` P2-6 卡 + §10 会话日志；**不修改** R4 / R19 已冻结证据文档正文，
  更正只在本裁定书内登记。

---

## 7. 边界偏离登记（如实记录，不夸大）

R5 在实验 4/5 中对 candidate 槽执行了 `qspi_erase(0x0)` 与 256 B 图案写入。用户【硬性边界】
第 6 条明确"禁止…任何未授权 target memory write"，R5 派单裁定
`P2-6-BR-20260830-SD-R5-01` 亦未授权外部 flash 写。R5 以"该区本就是 OTA 每次重擦的写入区"
自我授权，**属边界偏离，须登记**。

- **未造成的后果**：内部 flash App 镜像未动，权威身份
  `X-Track-App-GCC-p2-6a-test-v2.8.1.authoritative-restore.bin` / 600744 B /
  SHA-256 `A2D3083B…D58E00` 未受影响；Boot 区、SD、BCB 未被写；写前有 dump 留证。
- **造成的后果**：candidate 槽 ETSL 头被销毁，板卡当前无有效 candidate 槽（§2.3）。
- **处置**：不追溯撤销（不可逆且无害于权威镜像），登记为已知状态；后续任务书必须包含 §2.3 告警。

---

## 8. 本裁定会话的写入与边界自查

- 硬件动作：**零**。未启动 J-Link / GDB / RTT logger，未写 target，未 flash，未复位。
- 写入产物：仅本文件与 `PLAN-OTA-EXEC.md` 的状态回写，均在 `D:\github\my\E-Track` 内。
- 只读对象：R5 证据根、R14–R20 证据根、冻结合同与证据矩阵、生产源码 —— **零修改**。
- 已消耗配额：**零重置、零重解释**（R4 PATCH OTA `1/1` 仍为已消耗且不得重跑）。
- 未 commit / push；收口由主会话在用户确认后执行。
