# P2-6-SD-R5 阶段 0 离线实现证据（driver 两段式采集通道重构）

- 日期：2026-08-30
- 会话：R5 实现 agent（原 P2-6-SD-R5 派单裁定会话；用户在本轮对话中明确授权
  「给下一个 agent 的工作你不能做吗……继续」，由裁定 agent 转任实现 agent，
  治理上按角色转换登记：裁定与实现仍与后续独立验收会话分离）
- 分支：`p2-6-implementation-20260819`；零硬件动作（未启动 J-Link/GDB/RTT/OTA）
- 授权依据：`P2-6-BR-20260830-SD-R5-01=AUTHORIZED_RESUME`
  （`docs/ota-exec-notes/P2-6-SD-R5-dispatch-ruling-2026-08-30.md` §4.2 白名单：
  仅 `tests/ota/p2_6_rtt_ota_driver.py` 与其单测；§40.6 五项修复门槛）

## 1. 修改前后哈希（§40.6 门槛：双 hash 记录）

| 文件 | 修改前 | 修改后 |
|---|---|---|
| `tests/ota/p2_6_rtt_ota_driver.py` | 51578 B<br>`E63F8AC634A4CEDC8B0BE26C40390AC9B0B1938D5C1024AE8476B8737809331E` | 70942 B<br>`1B092AF294850AC353D48116D9205A5C1F9E9EF7476D51425891338735A64C56` |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | 44202 B<br>`3DB142703250F5ACD1CF2FFD8D5933E18D86F14E0E2C69E37D496D7BE808F996` | 53997 B<br>`411E01A7C866C74E440B43F97695602B7D2BF0DC6037A1EE2EEBBCFFE51CD5FB` |

白名单遵守：`p2_6_rtt_sd_uploader.py`（`88253A46…FDB61`）、
`p2_6_rtt_sd_preflight.py`、`p2_6_rtt_transport_qualifier.py` 及其全部单测
**未做任何改动**（无结构性必要：三者以 `measurement_policy=False` 调用
`run_gdb_session`，仅消费 transport 层字段，签名与字段全部保留）。

## 2. 结构性变更清单

R19（`P2-6-BR-20260829-RTT-BIND`，独立验收 PASS 的 `P2-6-v1` 合同）证明的
两段式采集结构移植进 driver：

1. **删除 `RttCapture` telnet 采集线程**：该通道在本 J-Link 上结构性只给
   banner（R19 探针 F1），数据采集职责整体移交两段式。
2. **新增 `probe_rtt_telnet`**：telnet 仅作 transport 可达性探针（连接 + 记录
   SEGGER banner 到 rtt log，与历史 banner-only 文件形态一致）；TCP connected
   语义上不再、也从未代表 payload ready；非 SEGGER banner fail-closed。
   `rtt_connected` 字段保留（transport qualifier 依赖其语义）。
3. **会话 1 OTA 脚本尾部（`gdb_command_file`）**：在 `P2_6_RTT_DRIVER PASS`
   marker 之后、`detach` 之前（核心 halted）新增快照段——RTT 控制块签名校验
   （quit 39）、Up0 尺寸校验（quit 40）、`dump binary memory` 控制块（0xA8B）
   与 Up0 环（`pBuffer..pBuffer+SizeOfBuffer`）、`P2_6_RTT_CB` descriptor
   printf、`SNAPSHOT_WRITTEN` 标记。
4. **`deterministic_stop_lines(attach=True)`**：`monitor halt` 后插入恰一行
   `monitor WriteU32 0xE0042008 0x00001000`（空格分隔，R19 实测语法；WDT 暂停，
   DEV-1 偏离模式）。
5. **新增 `rtt_descriptor` / `ring_slice` / `derive_rtt_pending`**（R19 precheck
   的 driver 版）：从会话 1 快照推导 pending 库存——签名/缓冲计数(3/3)/
   pBuffer SRAM 范围/尺寸 1024/Flags 1/偏移范围全 fail-closed；pending 须解析为
   恰一条与 `--kind` 匹配的完整记录（重复/异 kind/截断/空库存均失败并回填计数）。
6. **新增 `run_rtt_logger_capture`**（R19 capture 的 driver 版）：独立
   `JLinkRTTLogger` probe 连接（`-Device CORTEX-M4 -RTTAddress <addr>
   -RTTChannel 0`）读取 raw 文件；待读字节数到达后静默期（settle）确认无
   额外字节；payload 与 pending 逐字节一致；logger 无自然退出，按 AGENTS.md
   残留清理模式 Stop-Process + 残留进程计数 fail-closed（DEV-2 偏离模式，
   `logger_stopped_by` 显式披露）。
7. **新增 `post_snapshot_command_file` + `verify_rtt_postcheck`**（R19 postcheck
   的 driver 版）：短会话 2（halt + WDT 暂停 + dump post 控制块，零
   continue/call/reset）证明 logger 的唯一合法副作用——WrOff 不变、RdOff 恰好
   推进消费库存、控制块 0xA8B 中除 4 字节 RdOff 字外零变化。
8. **新增 `run_two_phase_ota_session` 编排**：会话 1（OTA 驱动 + 快照）→ derive →
   logger capture → 会话 2 post 快照 → postcheck；任何一阶段失败即 fail-closed
   并停止后续阶段；outcome 保持 `run_gdb_session` 字段布局，
   `rtt_channel_binding_verified` 仅在全链闭合（derive ELIGIBLE + capture
   payload==pending + postcheck PASS + 恰一条匹配记录）时为 true。
9. **`classify_transport_session` 扩展**：measurement 分支拆为
   `RTT_PAYLOAD_FAIL`（derive/capture 层失败）与 `RTT_POSTCHECK_FAIL`（第三阶段
   失败）两级；`GDB_FAIL` 仍先于 payload 判定（RTT 有记录不能覆盖 GDB 失败）。
   非 measurement 会话（preflight/uploader/qualifier）分类路径不变。
10. **`hardware_run` 接线**：新产物（cb-pre/cb-post/up0-pre/pending/payload/
    logger console/post 会话三件套）全部纳入唯一性输出保护、result JSON 的
    logs/sha256；最终判定加 `rtt_channel_binding_verified` 门禁。

## 3. 离线回归（全部本机实跑）

| 套件 | 结果 |
|---|---|
| `test_p2_6_rtt_ota_driver.py` | **38 项 OK**（1.4 s） |
| `test_p2_6_rtt_sd_preflight.py` | 3 项 OK |
| `test_p2_6_rtt_sd_uploader.py` | 7 项 OK |
| `test_p2_6_rtt_transport_qualifier.py` | 4 项 OK |
| `test_acceptance_bundle.py` | **65 项 OK**（35 s） |

`py_compile` 两文件通过；`--self-test`（`P2_6_RTT_OTA_DRIVER_SELFTEST=PASS
checks=9`）通过。

单测构成：原有 parser/classifier/符号/服务器清理/端口/输出边界等通道无关测试
全部保留；删除的仅是已不存在的 `RttCapture` telnet 线程行为测试（quiet
window/EOF/delayed socket 系列 10 项）；新增两段式测试 16 项
（全链 PASS+binding、空库存、重复/异 kind、截断、capture 超时/额外字节/不一致、
postcheck WrOff 变化/RdOff 停滞/越界字节、post 会话失败、GDB 非零、
binding 不自证、derive 8 项结构负例、环回绕库存、postcheck 5 变体、
logger 采集 3 组 mock 负例、脚本静态断言 2 项：会话 1 快照段/WDT 唯一性
与 post 脚本只读性）。

## 4. prepare-only 端到端离线验证（真实脚本生成）

命令（MSYS 路径转换屏蔽，沿用 R3-02 实证方法）：

```text
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' python tests/ota/p2_6_rtt_ota_driver.py \
  --prepare-only --kind PATCH \
  --package-path "/P2-6-SD-R5-20260830-01/P2-6A-PATCH-R5.etu" \
  --output-prefix p2-6-sd-r5-prepare-check
```

- `prepare_only=true`、`hardware_started=false`；result JSON 含全部 14 个
  logs 键与双脚本 SHA（gdb `DC1AAE6173997911…`、post `2439E09A83D3515F…`）。
- 生成的会话 1 脚本实测：第 6 行 `monitor halt` → 第 7 行 WDT 暂停（唯一）；
  第 420-422 行（`detach` 前）控制块/环 dump + `SNAPSHOT_WRITTEN`。
- 生成的 post 脚本实测：halt → WDT 暂停 → 签名校验（quit 41）→ dump
  `rtt-cb-post.bin` → detach；全文零 `continue`/`call`/`reset`/`loadbin`。
- 产物位于 `.cache/p2-6-sd-r2/{logs,tmp}/p2-6-sd-r5-prepare-check*`（项目内，
  不入库）。

## 5. §40.6 五项修复门槛逐项对照

1. *socket connected ≠ payload ready*：探针只做可达性；`rtt_payload_ready`
   由 derive（恰一条完整可解析记录）+ capture（逐字节一致）组合触发。✓
2. *banner-only、截断、缺失、socket 错误/提前关闭、超时、channel 未证实
   fail-closed*：空库存/截断/重复/异 kind 在 derive 失败；logger 超时/提前
   退出/额外字节/不一致在 capture 失败；telnet 连接失败→`RTT_NOT_READY`；
   非 SEGGER banner→`GDB_NOT_STARTED`；channel 未证实→binding 恒 false。✓
3. *有界 drain + 恰一条对应 kind 的完整记录*：两段式语义等价物=快照库存推导
   （恰一条）+ logger 交付到达 + settle 静默期（无额外字节）；重复记录失败。✓
4. *GDB 非零优先*：classify 顺序 `GDB_FAIL` 先于 payload 分支；server 非自然
   收尾/terminate/kill/端口残留→`CLEANUP_FAIL`；logger 残留→capture FAIL。✓
5. *fixture 覆盖*：banner-only（空库存）、截断、重复、完整+环内噪声恰一条
   （wraparound 用例）、socket 错误/提前关闭（探针连接失败与 logger 提前
   退出）、GDB 非零、capture 超时与额外字节、postcheck 三类越界——全部落地。✓

## 6. 边界与治理声明

- 本会话修改仅限白名单两文件；生产源码、冻结契约、`Tools/acceptance/**`、
  `Tools/provenance/**`、R14-R20 全部证据根、v1 合同与矩阵零改动。
- 两项制衡未撤：①硬件启动前，本整改仍需**第二个独立非实现 agent 复核**
  （复算修改后 hash、检查 diff 仅限白名单两文件、重跑全部 fixture）；
  ②硬件步骤（fresh preflight、SD 写入路径、JLinkDLL.ini 副作用）仍需用户
  当轮授权——本阶段零硬件。
- R19 的 no-flash/只读结论未外推：本阶段仅为离线 harness 重构；SD 写入与
  真实 OTA 路径的风险面分辨见派单裁定 §4。
- 治理缺口登记（裁定 §3.2）：本文件修改前的 `E63F8AC6…` 版本（2026-08-25
  23:18 工作区修改）无显式授权裁定记录；本轮修改基于派单裁定
  `P2-6-BR-20260830-SD-R5-01` 的显式白名单授权，回到授权轨道。
- 未 commit/push；全部产物落项目内。
