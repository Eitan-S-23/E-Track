# P2-6-SD-R5 派单三问独立裁定（2026-08-30）

- 裁定编号：`P2-6-BR-20260830-SD-R5-01`
- 会话角色：P2-6 非实现协调/裁定 agent（不改产品代码、不改 harness、不跑硬件、不 commit/push、不委派子 agent）
- 结论总览：问题一 `CLOSED（范围限定）`；问题二 `uploader 已闭合 / driver 缺陷形态已变但真机采集能力不存在（含治理缺口登记）`；问题三 `AUTHORIZED_RESUME`（新轮次 `P2-6-SD-R5`）
- 硬件动作：**零**（本会话未启动 J-Link/GDB/RTT，未写任何目标/SD/Flash）
- 本轮写入：本文件 + `PLAN-OTA-EXEC.md`（Python 字节级追加两行），均在项目根内

## 1. 输入与独立复算

| 输入 | 复算结果 |
|---|---|
| `docs/acceptance-contracts/P2-6-v1.contract.json` | 17416 B，SHA-256 `BFE0F5931BEED31FE658002DBF22A814650E9A74D6C495D21D6EC710F00C9F48`（certutil 实算，与任务书一致） |
| `docs/acceptance-contracts/P2-6-v1/P2-6-v1.evidence-matrix.json` | 14647 B，SHA-256 `50D7F8BA597F1BB724A86E9E069B7B03E7091A3D6A32E8D8696DC62EAE853122`（同上）；矩阵 `contract_sha256` 绑定 v1 值 |
| `tests/ota/p2_6_rtt_ota_driver.py` | 51578 B，SHA-256 `E63F8AC634A4CEDC8B0BE26C40390AC9B0B1938D5C1024AE8476B8737809331E`（工作区=HEAD `d27200d`，随 `3218ff0` 于 2026-08-30 16:07 入库） |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | 44202 B，SHA-256 `3DB142703250F5ACD1CF2FFD8D5933E18D86F14E0E2C69E37D496D7BE808F996` |
| `tests/ota/p2_6_rtt_sd_uploader.py` | 26870 B，SHA-256 `88253A46C11A69B12D55ABACF1B13CF005B4722798EE6E7B85D0DFDBE46FDB61`；第 36 行 `LV_FS_RES_UNKNOWN = 12` |
| R4-01 证据根 | `.cache/p2-6-sd-r4-20260825-01-implementation/` 存在（patch-upload/patch-ota/full-* 等子目录实测在位），本会话只读未动 |
| R19 正式验收根 | `.cache/p2-6-rtt-binding-20260829-18/` 存在（baseline/logs/scripts/snapshots/tmp + manifest.json），只读未动 |

R20 收口报告中合同/矩阵 SHA（`330F3A5A…`/`4D70BA80…`）为补正前旧值；R20 §6 已记录随后由补正会话以「改看板 + 重生成 Governance manifest + 重绑合同哈希」原子闭环，当前盘上文件即补正后最终版（上表实算）。

## 2. 问题一：RTT-CAPTURE-01 解除条件是否闭合

**裁定：CLOSED（以重定域形式），闭合范围仅限「通道绑定事实」，不覆盖对 `tests/ota/p2_6_rtt_ota_driver.py` 的修复授权。**

### 2.1 解除条件原文与实质

`PLAN-OTA-EXEC.md` 第 557 行（=实现证据 §40.5）：现有证据没有把 Telnet 字节与当前
`_SEGGER_RTT` Up-channel 绑定；未来需**真实只读 GDB snapshot**，离线无法闭合。

条件的实质是「采集到的字节必须由真实只读 GDB snapshot 证明来自当前固件的 Up-channel」；
Telnet 只是当时假定的采集载体。

### 2.2 闭合证据链

1. **Telnet 载体被定因结构性不可用**：R19 证据 §3.2（探针 F1）——telnet 客户端先连接、
   目标 reset+go 全速运行并输出 RTT 突发，telnet 仍零 payload；该通道在
   V8.18 server + ARM-OB V7.00 J-Link 上**永远不投递环数据，与核心状态无关**。
   「把 Telnet 字节绑定」在物理上无可绑定之物。
2. **绑定以更强形式完成**：R19 两段式结构 = 会话 1 GDB 只读快照推导 Up0 待读字节
   （pending 731B）→ 会话间独立 `JLinkRTTLogger` 采集（payload 731B）→ 逐字节一致
   （两者 SHA-256 同为 `206286D4D2B8866F29AF6308059E53AEB500CC3F79300C8506E3C3F921DDFC49`）
   → 会话 2 快照证明仅 Up0 的 4B RdOff 字 0→731 推进、控制块其余字节/环内容/measurement
   零变化。证据：v1 矩阵 `HW-CAPTURE-PAYLOAD`/`HW-POSTCHECK-RDOFF` 判据
   （`docs/acceptance-contracts/P2-6-v1/P2-6-v1.evidence-matrix.json` 第 26-65 行）。
3. **双分支真机 + 独立验收 PASS**：no-flash（根 -21）与 flash 恢复（根 -23）均
   `RTT_CHANNEL_BINDING_VERIFIED / UP0_RING_BYTES_AND_RD_OFF_PROVEN`，14 marker 全 1；
   正式验收根 -18 由非实现会话 2026-08-30 独立验收 PASS（v1 合同九判据全 EXECUTED PASS，
   `validate_bundle.py` EXIT=0）。看板第 555 行已冻结该判定。

### 2.3 为什么不覆盖 driver 修复授权

1. §40/第 557 行裁定的 KEEP_BLOCKED 冻结了**两个独立事项**：(a) 通道绑定证据缺口（解除
   条件）；(b) 「不授权任何离线修复」——指对 `tests/ota/p2_6_rtt_ota_driver.py` 及其
   单测的修改授权（§40.6 另设了五项修复门槛）。R19 全程未修改这两个文件（其脚本集在
   证据根 `scripts/` 下，是独立交付物），(b) 的授权缺口仍在，须经显式裁定。
2. R19 的验证反而**收窄了 driver 的可修复空间**：telnet 采集路径被定因结构性不可用，
   任何有效修复都必须把采集通道替换为 logger/两段式结构——这是结构性重构而非状态机
   补丁（见 §3.2 现状：工作区修复版仍走 telnet，真机上必然 fail-closed，无法采集）。
3. §40.6 的授权后置条件（修复前后双 hash、diff 仅限两个 test-only 文件、fixture 重跑、
   第二独立非实现 agent 复核）对 driver 的后续变更仍然有效，构成本裁定问题三白名单的
   前置门槛。

## 3. 问题二：R4-01 两处缺陷现状 / PRODUCT_FAIL / SD 写入

### 3.1 uploader 常量差一：已闭合

- 授权链：`P2-6-BR-20260824-SD-R3-02-01=AUTHORIZED_RESUME` 授权「仅修正 uploader 两处
  test-only 字面量」（看板 555 行）；SD-R4 派单 §38.4 明示「当前唯一已授权的 harness
  变化是 uploader 的 UNKNOWN=12 及同步诊断文本」。
- 实证：当前 `tests/ota/p2_6_rtt_sd_uploader.py:36` `LV_FS_RES_UNKNOWN = 12`，与固件
  `lv_fs.h`（`INV_PARAM=11`/`UNKNOWN=12`，实现证据 §35.6 三段互证）一致；R4-01 PATCH
  上传 `1/1 PASS`（实现证据 §39.4 冻结表）以真实 SD 写入+读回 SHA-256 匹配证明修复生效。
- **结论：不再是缺陷，无需任何新授权。**

### 3.2 driver「TCP connected 误记 payload ready」：缺陷形态已变，真机采集能力仍不存在

现状三层事实（禁止合并推定）：

1. **状态机修复已在工作区/git 落地**：当前 driver（`E63F8AC6…`）含
   `rtt_payload_ready`/`rtt_drain_complete`/`rtt_drain_deadline_expired` 状态与有界
   drain（`p2_6_rtt_ota_driver.py:471-892`）；单测含 banner-only、延迟、截断、重复、
   EOF/socket 错误、GDB 非零等 fail-closed 负例（`test_p2_6_rtt_ota_driver.py:241/295`
   等）；`.cache/p2-6-rtt-binding-independent-review-20260826-01/existing-p2-6-rerun.log`
   记录 48 项离线测试 `OK`，含 `test_ota_policy_rejects_banner_only_and_missing_payload`
   与 `test_channel_binding_stays_unverified`。§40.3 所述「connected 即记 PASS、
   banner-only 可 PASS」的缺陷在当前版本中已不存在。
2. **采集通道缺陷是结构性的且未修复**：当前 driver 的 RttCapture 仍走 GDB server
   `-rtttelnetport 24363` 的 `socket.create_connection`（`p2_6_rtt_ota_driver.py:58,525,604`），
   无任何 `JLinkRTTLogger` 路径。R19 探针 F1 已定因该 telnet 通道在本 J-Link 上永远
   只给 banner——因此修复版 driver 在真机上将正确地 fail-closed（不再误报 PASS），
   但**结构上无法取得 payload**，无法支撑 C1/C2、C4-C7、C14 的观测。
3. **治理缺口（如实登记，不追改）**：该修复发生于 2026-08-25 23:18（本地，
   `frozen-input-harness-independent.json` 记录的 mtime），即 §40 KEEP_BLOCKED（同日，
   「不授权任何离线修复」）之后；看板与 exec-notes 中**未找到**对这次 driver 修改的
   显式非实现授权裁定记录。修复版随后被 2026-08-26 独立复核（两根）、R17 静态审计钉死
   输入、v1 合同 Validation manifest 绑定（manifest 内实值 `E63F8AC6…`）并随 `3218ff0`
   入库。本裁定不回溯追改该历史，但认定：**driver 的任何后续变更必须回到显式授权轨道**
   （本裁定 §4 白名单 + §40.6 门槛）。

**裁定：该缺陷不再以「TCP connected 误记」形态存在（离线层面已按 §40.6 门槛修复并经
独立复核），但「采集通道结构性不可用」作为可定界 harness 缺陷仍然成立，其唯一已知
有效解法是 R19 已验收的两段式 logger 结构，属于待授权的 test-only 重构。**

### 3.3 PRODUCT_FAIL 证据：无

- R4-01 PATCH OTA 最终分类 `HARNESS_FAIL`（§39.1/看板 556 行）：GDB 取得唯一
  identity/state/result/PASS marker（`BCB=STAGED`、mode=3、`SD_IsReady=1`、
  `VTOR=0x08010000`、`CFSR=0`、owner=0，§39.2 六 marker 全列），产品路径正常到达结果态；
  失败仅因 RTT 文件 107B banner-only（§39.3）。
- R3-02 上传失败同样定性非 PRODUCT_FAIL（§35.8：生产行为符合 LVGL 契约、上传前设备
  状态全部正常）。
- 全部历史轮次（旧 PATCH 3/3、SD-R2、SD-R3 系列、R4-01、RTT-BIND R14-R20）无任何
  `PRODUCT_FAIL` 判定记录。缺失的测量数值不能从 R4-01 证据重建（printf 返回值未保存，
  §39.3），属证据缺口而非产品失败。

### 3.4 SD 卡写入历史：写入过一次（授权范围内）

- **是**：R4-01 PATCH 上传 `1/1 PASS` = PATCH `.etu` 经 uploader 写入 SD（用户当轮授权
  路径）并完整读回、SHA-256 等于冻结 PATCH（§38.4 第 3 步语义 + §39.4 冻结表）。
  随后 PATCH OTA 到达 `BCB=STAGED`，证明固件已从 SD 读取该文件并完成 staging。
- 其余轮次均未写 SD：旧 PATCH 3/3 三次都在 `lv_fs_open` 前失败（看板 565 行）；SD-R2
  上传 ENV_BLOCKED 未启动；R3-02 失败于写前只读探测（§35.5，SD 上未创建任何文件）；
  RTT-BIND R14-R20 全程无 SD 文件 API（v1 合同 `HW-NO-FLASH-WRITE` 及 R19 §9）。
- **SD 写入本身已被证明可用**，R5 无需重新验证写入路径的可行性，只需新路径授权。

## 4. 问题三：新轮次 `P2-6-SD-R5` 授权

**裁定：`AUTHORIZED_RESUME`。** 依据：R4-01 的唯一失败根因（采集通道不可用 + 状态机
误记）已双证据闭合（§3.2 状态机修复 + R19 方法论经独立验收 PASS）；无任何 PRODUCT_FAIL；
transport（§30.5）与 WDT 长时 halt（R18→R19）两大环境阻塞均已定因闭合；C1/C2、
C4-C7、C14 与升级态 RAM 峰值是 P2-6 仅存观测缺口（C3/C13/C16 已 PASS），不授权则本卡
永久停滞。

**风险显式分辨（硬边界执行）**：R19 的 no-flash/只读结论**不外推**至 SD 写入与真实
OTA 路径。SD 产品写入仅 R4-01 一次实证；OTA apply 窗口（BCB/reset/boot apply/flash
编程，含 R19 §6 发现的 boot 备份自主恢复机制）从未在 harness 控制下穿越；升级态测量
记录经 RTT 上报的形态与时序从未实测。因此每步独立 0/1 配额、首失败即停、设备状态
前置只读确认。

### 4.1 冻结计数（全部不清零、不重跑、不重解释）

旧 PATCH 上传 `3/3`、SD-R2 preflight `1/1 PASS`、SD-R2 正式上传 `1/1 ENV_BLOCKED`、
stack closure R3 `2/3`（禁 R3-3）、R3-03 preflight `1/1 ENV_BLOCKED`、R4-01
preflight `1/1 PASS`、R4-01 PATCH 上传 `1/1 PASS`、**R4-01 PATCH OTA `1/1 HARNESS_FAIL`
永不重跑**、RTT-BIND R14-R20 证据根只读。R5 各步是**新轮次的新配额**，不是对任何
旧配额的重置——沿用 SD-R2→R3→R4 的轮次演替先例（根因定因并修复后由非实现裁定
授权新编号轮次）。

### 4.2 可改 test-only 文件白名单（离线阶段，硬件启动前）

| 文件 | 允许的变更 | 门槛 |
|---|---|---|
| `tests/ota/p2_6_rtt_ota_driver.py` | 把 RTT 采集通道从 GDB server telnet 重构为 R19 已验收的两段式结构（GDB 只读快照推导 pending → 独立 `JLinkRTTLogger` 采集 → 逐字节比对 → 控制块级 diff 仅 RdOff 字变化）；保留既有 payload-ready/drain fail-closed 状态机 | §40.6 五项不变量全部保持；修复前后记录 SHA-256；`py_compile` + 全部既有单测 + 新增负例全绿 |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | 补两段式结构对应 fixture（logger 路径 banner-only 零字节、payload 与 pending 不一致、RdOff 越界推进、控制块越界变化） | 同上 |
| `tests/ota/p2_6_rtt_sd_uploader.py` 及其单测 | **默认禁改**；仅当两段式集成出现结构性必要时可最小适配，须先记录理由 | 变更前后 SHA-256 + 理由落盘 |

白名单外一律禁改（生产源码、CMake/linker、冻结提示词、`PLAN-OTA.md`、
`docs/ota-binary-contracts.md`、`Tools/acceptance/**`、`Tools/provenance/**`、原始
JSON 证据、`.cache` 旧根）。driver 整改完成后，须由**第二个独立非实现 agent** 复核
（复算 hash、检查 diff 仅限白名单、重跑全部 fixture）后方可启动硬件——沿用 §40.6
后置条件与 2026-08-26 独立复核先例。

### 4.3 硬件步骤与每步 0/1 配额（依序执行，首失败即停）

| # | 步骤 | 配额 | 关键约束 |
|---|---|---|---|
| 1 | fresh SD-preflight（只读硬件预检） | `0/1` | 既有冻结语义（96B 身份、受控停点、RTT 签名、`SD_IsReady=1`、`VTOR=0x08010000`、`CFSR=0`、BCB、overlay、write_calls=0、flash_calls=0）；**BCB 必须只读确认**：非 CONFIRMED/FREE（如 STAGED）立即停止请求新裁定，禁止自行 reset/清 BCB |
| 2 | 基线恢复（可选） | `0/1` | 仅当 PATCH OTA 需要 v2.8.0 基线而板卡不符、且用户明示授权时：一次 `loadbin` 写入冻结 v2.8.0 test 镜像（`AB38A4E7…`，600744B），默认设置 + `noreset` 语义按 R19 §6 实证方法；未经授权跳过本步并改走仅 FULL 路线或停止 |
| 3 | PATCH 上传 | `0/1` | 唯一新路径（用户当轮授权准确路径+写入操作+副作用）；只读 probe 期望 `LV_FS_RES_UNKNOWN=12`；MI 分块写入后完整读回 SHA-256 必须等于冻结 PATCH `2B0ACCAE…F37C9D2B` |
| 4 | PATCH OTA | `0/1` | 穿越真实升级窗口；全程 RTT 采集测量记录（两段式）；观测 C2/C4/C5/C6/C14 |
| 5 | FULL 上传 | `0/1` | 同 3；读回 SHA-256 等于冻结 FULL `84D3F384…C96DD2E7` |
| 6 | FULL OTA | `0/1` | 观测 C1/C4/C5/C6/C14 |
| 7 | 异常退出注错 | `0/1` | 观测 C7（overlay release） |
| 8 | LiveMap 恢复 | `0/1` | 观测 C7（LiveMap 重建） |

### 4.4 硬件前置（每个 halt 会话强制）

1. **每 halt 会话恰一行** `monitor WriteU32 0xE0042008 0x00001000`（空格分隔，R19 §2.1
   实测语法；DEBUG_WDT_PAUSE）——v1 合同 DEV-1 偏离沿用，非 flash、断电即失、不改镜像
   字节；server log 回显 count==1 由 fail-closed 校验。
2. **两段式 binding 结构**：GDB 会话内只读快照 → 会话间独立 logger 采集 → 会话 2 post
   快照；payload 与 pending 逐字节一致、仅 RdOff 字变化（R19 §3.2/§3.3 语义）。
3. **logger 生命周期披露**：`JLinkRTTLogger` 无自然退出，按 AGENTS.md 残留清理模式
   Stop-Process + 零残留验证，`capture.json` 记录 `logger_stopped_by`/`logger_stopped`/
   残留计数——v1 合同 DEV-2 偏离沿用；GDB/server 仍严格自然退出。
4. 用户当轮重新授权：`JLinkDLL.ini` 副作用、SD 写入准确路径与操作。历史授权不延续。
5. 启动前：端口 24361-24364 无监听、无 J-Link/GDB/RTT-logger 残留进程、新证据根唯一
   且原不存在、路径链无 reparse point。

### 4.5 停止条件（任一命中立即停止并保存原始证据，等待新的非实现裁定）

- 任一步结果非完整 PASS（含 `ENV_BLOCKED`/`TRANSPORT_NOT_READY`/`HARNESS_FAIL`/
  `PRODUCT_FAIL`）、marker 缺失或重复、身份/state/BCB/VTOR/CFSR/overlay 异常或不确定；
- `workspace_peak>40960B`、有效 `stack_peak>8192B`、guard 损坏、sbrk/TLSF required
  增量非零、读回不完整或 SHA-256 不匹配；
- BCB 非 CONFIRMED/FREE、需要基线恢复而未获用户授权；
- readiness/GDB/RTT 未满足、terminate/kill（logger 除外）、残留进程、监听端口、SEGGER
  收尾不确定；
- 需要重试、换路径、创建目录、覆盖/删除/移动旧文件、超出配额，或需要改生产源码/
  冻结契约/白名单外文件。

### 4.6 合同策略

新冻结 `docs/acceptance-contracts/P2-6-v2.contract.json`：`task_id=P2-6`、`version=2`、
`parent_contract_sha256=BFE0F5931BEED31FE658002DBF22A814650E9A74D6C495D21D6EC710F00C9F48`
（v1 文件 SHA-256）；**验收前冻结**（纠正 v1 DEV-3 的合同后冻结流程偏离）；判据覆盖
C1/C2、C4-C7、C14 观测与升级态 RAM 峰值回填，含至少一个鉴别性负例（fail-closed）；
性能门禁只引用 `protocol_contract` 冻结值（`8192B`/`40960B`），不得以历史测量加余量
造门槛。v2 冻结时点记录当时看板字节状态；R5 执行期间的看板回写集中在轮次收口一次
完成，避免 Governance manifest 反复失配（R20 §6 已登记的活文档设计问题，本裁定不改
profile，交后续治理裁定）。

## 5. 看板回写对 v1 复验的影响（如实登记）

本轮按交付要求回写 `PLAN-OTA-EXEC.md`（追加裁定行 + §10 日志行）会改变其字节与
SHA-256，使 v1 合同的 Governance manifest 在当前 worktree 复验变红——R20 §6 已登记的
已知设计问题，不改变 v1 已冻结的 PASS 判定与其证据包内 artifacts 的完整性。v1 的
复验能力保留于其生成时点的 git 提交链（`3218ff0`/`85e98a6`/`6122602`/`d27200d`）；
若需在当前树复验 v1，须按 R20 补正模式原子闭环（改看板 + 重生成 Governance manifest +
重绑 v1 哈希），该操作不在本轮授权范围。

## 6. 下一棒实现 agent 提示词（完整版；最终回复内为可转发版）

```text
你是 E-Track 项目的 P2-6-SD-R5 实现验证 agent，不是独立验收 agent。只执行本提示词
授权的动作；不得独立验收、不得宣布 P2-6 完成、不 commit/push/merge、不改生产源码、
冻结提示词、PLAN-OTA.md、二进制契约、Tools/acceptance、Tools/provenance 与 .cache 旧根。

仓库与冻结计数（全部不清零、不重跑、不重解释）：
- 根 D:\github\my\E-Track；分支 p2-6-implementation-20260819。
- 旧 PATCH 3/3；SD-R2 preflight 1/1 PASS；SD-R2 上传 1/1 ENV_BLOCKED；stack R3 2/3；
  R3-03 preflight 1/1 ENV_BLOCKED；R4-01 preflight 1/1 PASS；R4-01 PATCH 上传 1/1 PASS；
  R4-01 PATCH OTA 1/1 HARNESS_FAIL 永不重跑；RTT-BIND R14-R20 证据根只读。
- C3/C13/C16=PASS；C1/C2、C4-C7、C14 当前 NOT_OBSERVED，只能由本轮真实证据回填。

阶段 0（离线，硬件启动前）：
- 白名单仅 tests/ota/p2_6_rtt_ota_driver.py 与其单测：把 RTT 采集通道从 GDB server
  telnet 重构为 R19 已验收的两段式结构（GDB 只读快照推导 pending → 独立
  JLinkRTTLogger 采集 → 逐字节比对 → 控制块级 diff 仅 Up0 RdOff 字变化），保留既有
  payload-ready/有界 drain fail-closed 状态机；新增 logger 路径负例 fixture
  （零字节/不一致/越界推进/控制块越界变化）。uploader 默认禁改，结构性必要时最小适配
  并记录理由。修复前后记录 SHA-256；py_compile + 全部单测全绿。
- 整改完成后交第二个独立非实现 agent 复核（复算 hash、diff 仅限白名单、重跑 fixture），
  通过前不得启动硬件。
- 新建唯一证据根 .cache/p2-6-sd-r5-20260830-01-implementation/（原不存在、无 reparse
  point、项目内）；冻结输入逐项复算：ELF 35BB2AB7…76D019、map 2446B401…A45D0C13、
  test v2.8.0 AB38A4E7…E569A5E5、PATCH 305B 2B0ACCAE…F37C9D2B、FULL 282367B
  84D3F384…C96DD2E7。

硬件前置（每个 halt 会话）：
- monitor halt 后恰一行 monitor WriteU32 0xE0042008 0x00001000（空格分隔；WDT 暂停，
  断电即失，server 回显 count==1 fail-closed 校验）。
- 两段式 binding：GDB 快照→会话间独立 logger→post 快照；payload 与 pending 逐字节
  一致、仅 RdOff 字变化。JLinkRTTLogger 无自然退出：Stop-Process + 零残留验证并在
  capture.json 披露；GDB/server 严格自然退出。
- 启动前用户当轮重新授权 JLinkDLL.ini 副作用与全部 SD 写入路径；候选路径仅建议非授权。
- 启动前确认端口 24361-24364 无监听、无 J-Link/GDB/RTT 残留进程。

硬件步骤（每步恰一次，首失败即停）：
1. fresh SD-preflight 0/1：冻结语义全项 + BCB 只读确认；BCB 非 CONFIRMED/FREE（如
   STAGED）立即停止请求裁定，禁止自行 reset/清 BCB。
2. 基线恢复 0/1（可选）：仅当板卡非 v2.8.0 且用户明示授权，一次 loadbin 冻结 v2.8.0
   test 镜像；未授权则跳过并仅走 FULL 路线或停止。
3. PATCH 上传 0/1：新路径、只读 probe 期望 LV_FS_RES_UNKNOWN=12、MI 分块写入、完整
   读回 SHA-256 等于冻结 PATCH。
4. PATCH OTA 0/1：穿越真实升级窗口，全程两段式 RTT 采集测量记录（C2/C4/C5/C6/C14）。
5. FULL 上传 0/1 → 6. FULL OTA 0/1（C1/C4/C5/C6/C14）→ 7. 异常退出注错 0/1 →
   8. LiveMap 恢复 0/1（C7）。

停止条件（任一命中即停、保存原始证据、等待新裁定）：任一步非完整 PASS 或状态不确定；
workspace_peak>40960B、有效 stack_peak>8192B、guard 损坏、sbrk/TLSF required 增量非零、
读回 SHA 不匹配；BCB 异常；需要重试/换路径/覆盖旧文件/超配额；需要改白名单外文件。

合同与收尾：验收前冻结 docs/acceptance-contracts/P2-6-v2.contract.json（task_id=P2-6、
version=2、parent_contract_sha256=BFE0F5931BEED31FE658002DBF22A814650E9A74D6C495D21D6EC710F00C9F48）；
判据覆盖 C1/C2、C4-C7、C14 与峰值回填并含 fail-closed 负例；门禁只用 protocol_contract
冻结值。manifest 最后生成；R19 的 no-flash 只读结论不外推到 SD 写入与真实 OTA。
研究结论落盘 docs/ota-exec-notes/；结束回写看板任务卡与 §10 日志（PLAN-OTA-EXEC.md 用
Python 字节读写）。全部证据、日志、产物落项目内。
```

## 7. 边界自查

- 本会话零硬件动作、零 git 写操作、未修改任何产品代码/harness/冻结合同/矩阵/旧证据根。
- 主动写入：本文件与 `PLAN-OTA-EXEC.md`（Python 字节级 `rb`/`wb`，仅追加两行，未触碰
  既有行），均在 `D:\github\my\E-Track` 内且路径链无 reparse point。
- R4-01 根、RTT-BIND 各根（-14…-23）、v1 合同与矩阵全程只读。
- 项目外 `JLinkDLL.ini` 未触碰（本会话未启动任何 SEGGER 工具）。
