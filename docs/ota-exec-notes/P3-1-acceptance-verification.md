# P3-1 独立验收报告（BLE 帧层 / MCU 侧）

- 日期：2026-09-02
- 验收者：Claude（**非实现会话**，独立验收；实现者为 P3-1 实现 agent）
- 依据：`AGENTS.md` §OTA 执行规约 §3（实现者不自验收）、
  `docs/acceptance-execution-contract.md`、`docs/ota-prompts/prompt-P3-1-implementation.md`、
  `PLAN-OTA-EXEC.md` P3-1 卡、冻结契约 `docs/ota-binary-contracts.md` §5
- 验收原则：**不采信实现报告的任何结论**，所有数字与判定均由本会话独立复算/复跑得到；
  临时产物一律落 `.cache/`（已被 `.gitignore` 忽略），工作区源文件全程只读。

---

## 1. 单轮验收结果

| 项目 | 结论 |
|---|---|
| 单轮验收结果 | **PASS** |
| 验收形态 | `docs/acceptance-execution-contract.md` 意义上的**合同制正式验收** |
| 冻结合同 | `docs/acceptance-contracts/P3-1-v2.contract.json`（v2，status=FROZEN，`parent_contract_sha256` 绑定已废弃的 v1） |
| 证据矩阵 | `docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json`（`round_id=P3-1-V2-FREEZE-20260902-01`） |
| 判据规模 | **17 条**：全部 `required=true` 且全部 `EXECUTED PASS`，无 `NOT_OBSERVED`、无 `FAIL`、无 `REUSED`（真机 BLE 闭环不属本卡冻结范围，见 §9-J 与合同 `scope.excluded_by_freeze`） |
| 证据规模 | 命令 13 条、产物 17 项、证据哈希 27 项；无 `REUSED` 判据（首轮全量执行） |
| 校验器 | `Tools/acceptance/validate_bundle.py` → `VALIDATION=PASS`（EXIT=0） |
| 综合评分 | **93 / 100** |

合同与矩阵的精确指纹登记见本报告 §12（本文件不在任何 manifest profile 枚举范围内，
记录哈希不会形成"改文档 → 改指纹 → 改合同"的自指循环）。

> 依 `docs/acceptance-execution-contract.md` §2，任务状态与单轮验收结果分离，
> 验收者不覆盖实现认领人；本报告只给出单轮验收结果。
> 本报告是合同判据的**人读叙述面**，机器可校验面以上表的合同与证据矩阵为准。

---

## 1bis. 本轮新增的验证工具（均落在 Validation manifest 指纹范围内）

`Tools/provenance/manifest_profiles.json` 的 Validation profile 只枚举 `Tools/`
与 `tests/`。为使判据引用的验证工具受 manifest 绑定，八个验收脚本按既有实践
（`tests/ota/p2_6_*.py`）命名并落在 `tests/ota/`：

| 脚本 | 作用 | 本轮输出 |
|---|---|---|
| `tests/ota/p3_1_verify_contract_alignment.py` | `ota_ble_frame.h` ↔ 契约 §5 机器比对 | `PASS drift=0 checks=47` |
| `tests/ota/p3_1_verify_production_binary.py` | 生产 ELF/map 红线静态实证 | `PASS required_api=14 ble_syms=16 test_syms_leaked=0` |
| `tests/ota/p3_1_verify_portability.py` | 反斜杠 include 扫描（带阳性对照） | `PASS control_hits=1 live_hits=0` |
| `tests/ota/p3_1_verify_mutation.py` | harness 鉴别力变异测试 | `PASS effective_detected=4/4 problems=0` |
| `tests/ota/p3_1_verify_artifacts.py` | 9 个申报产物 SHA-256 独立复算 | `PASS match=9 mismatch=0` |
| `tests/ota/p3_1_verify_text_isolation.py` | 文本协议隔离：行为 + 接线双证 | `PASS cases=3 transparent=0` |
| `tests/ota/p3_1_verify_rx_ring_budget.py` | 接收环/overlay 预算按生产编译 flag 反读（§4bis） | `PASS ring=4096 receiver=4164 session_obj=568 overlay=40960 headroom=32700` |
| `tests/ota/p3_1_verify_command_fidelity.py` | 冻结命令 ↔ 冻结日志逐字节复算（§6bis） | `PASS cases=11 mismatched=0 masked_lines=3` |

八者均 fail-closed：无锚点、无阳性对照、无原始产物、探针编译失败时直接判失败，
不存在常量 PASS 路径。

---

## 2. 独立复跑：全部 host 测试（本会话实测）

```text
[test_ota_ble_frame]   exit=0  P3_1_BLE_FRAME=PASS   checks=39  failures=0
[test_ota_ble_session] exit=0  P3_1_BLE_SESSION=PASS checks=105 failures=0
[test_ota_staging]     exit=0  P2_1_STAGING=PASS     checks=48  failures=0
[test_ota_package]     exit=0  P2_2_PACKAGE=PASS     checks=102
[test_ota_sd]          exit=0  P2_4_OTA_SD_ALL=PASS  core_checks=29 adapter_scenarios=5
```

- 实现者仅声称跑过 SD 层回归；本轮**主动扩大**到 staging / package 全回归，均全绿。
- 全部编译在 `-Wall -Wextra -Werror` 下通过。

## 3. 独立复算：产物一致性（9/9 全部匹配）

对 `P3-1-build-evidence.md` §4 声明的 9 个 SHA-256 逐一重算：

```text
一致 = 9    不一致 = 0    缺失 = 0
```

| 产物 | 大小 | 时间戳 | 结论 |
|---|---|---|---|
| X-Track-App-GCC.elf / hex / bin / map | 867952 / 1694382 / 602864 / 2433909 B | 2026-09-02 00:21:39 | MATCH |
| X-Track-Boot.elf / hex / bin / map | 36860 / 41485 / 14724 / 100450 B | 2026-08-15 00:16 | MATCH |
| LVGL.Simulator.exe | 5864960 B | 2026-09-02 00:20:49 | MATCH |

Boot 时间戳早于本卡属**正常**：本卡零 Boot 源变更，Ninja 判定无需重编；已独立复现
`ninja: no work to do.` 空跑，证明产物与当前全部源同步（不存在"改了源没重编"）。

## 4. 生产构型红线（静态实证，非文档引用）

| 红线 | 手段 | 结果 |
|---|---|---|
| 新源确已链接进生产 ELF（非孤儿源） | `arm-none-eabi-nm --defined-only` + map | 生产实际调用的 **14 个公共 API 全部在 ELF 内**；ELF 内 `ota_ble_*` 符号共 **16 个**；三个新对象 `ota_ble_{ring,frame,session}.c.obj` 均出现在链接 map 中 |
| "被 GC" 与 "没编译" 严格区分 | map `Discarded input sections` 区 | `ota_ble_ring_count` 无生产调用点，被 `-ffunction-sections`+`--gc-sections` 合法回收；map 中可见 `.text.ota_ble_ring_count 0x16` 记录，证明**已编译**而非源未参与构建 |
| 生产构型零测试符号 | nm 精确匹配测试专有符号 | `make_full_package`/`last_tx`/`tx_status`/`count_programs_in`/`make_rejection_package`/`fixture_`/`run_frame_tests` **全部 0** |
| 禁止 struct memcpy 解析 wire | 全文件扫描 | `ota_ble_frame.c` 中 **memcpy 出现 0 次**，纯逐字节 LE 组装 |
| 禁止无界动态分配 | 扫描 malloc/calloc/realloc/free/new/delete | 新增三源 **0 命中** |
| RAM 门槛（A5 断言 / overlay） | map 实证 | `.ota_overlay 0x20058000 0xa000`(40960B)；`s_ble_session` = **0x238 (568B)** 主 RAM |
| overlay 子分配不越界 | 生产编译探针 + map（§4bis） | 环 4096B + receiver 4164B = 8260B ≤ overlay 40960B，**余量 32700B**；`ws_size < ring + sizeof(receiver)` 显式校验，不足即拒绝（用例 18/19 覆盖，且拒绝路径不泄漏 overlay） |
| 接收缓冲 ≥ 4KB（看板冻结要求） | 生产编译探针反读（§4bis） | `CONFIG_OTA_BLE_RX_RING_SIZE` 在生产构型下实际展开 **4096B**，且为 2 的幂（`ota_ble_ring_init` 掩码回绕前提） |
| CI 可移植性（反斜杠 include） | 见 §5 | 参与编译手写源 **0 命中** |

## 4bis. 接收环与 overlay 预算：按生产编译 flag 反读（本轮新增取证）

看板 P3-1 目标写明「UART 接收缓冲 ≥4KB（现 512B）」。源码里出现
`#define CONFIG_OTA_BLE_RX_RING_SIZE 4096` **不足以定案**：该宏在
`ota_ble_session.h` 里带 `#ifndef` 兜底，真正生效的值取决于生产构型的 `-D`
与 include 顺序——读源码字面量属于"以文档引用代替实证"。

`tests/ota/p3_1_verify_rx_ring_budget.py` 改为从
`build-gcc-release/compile_commands.json` 取 `Libraries/OTA/ota_ble_session.c`
的**原样生产编译命令**（剔除 `-o`/`-M*` 等输出依赖类参数后复用全部 flag），
用同一套 flag 编译一个只含三个数组定义的探针 TU，再用
`arm-none-eabi-nm -S` 从符号大小反读编译期常量：

```text
编译器 = arm-none-eabi-gcc
取证 TU = Libraries/OTA/ota_ble_session.c（生产 flag 原样复用）
[实测] CONFIG_OTA_BLE_RX_RING_SIZE = 4096B（按生产 flag 展开）
[实测] sizeof(ota_staging_receiver_t) = 4164B
[实测] sizeof(ota_ble_session_t)      = 568B
[实测] map .ota_overlay               = 40960B

[判据1] 接收环 >= 4096B: True
[判据2] 环尺寸为 2 的幂（掩码回绕前提）: True
[判据3] 环 + receiver = 8260B <= overlay 40960B: True（余量 32700B）
P3_1_RX_RING_BUDGET=PASS ring=4096 receiver=4164 session_obj=568 overlay=40960 headroom=32700
```

三条判据互相独立：判据 2 若不满足，`ota_ble_ring_init` 会 fail-closed；判据 3
若不满足，BEGIN 将恒返回 `ERR_BUSY`——即"编得过但跑不通"的静默失效，仅靠单元
测试（跑在 host 上、不受 MCU overlay 尺寸约束）无法暴露。探针只写 `.cache/`，
不触碰工作区源码，也不改动生产构建目录。

## 5. CI 可移植性：带阳性对照的重做

`P3-1-build-evidence.md` §6 记录的自检命令 `rg "#include.*\\"` 因 shell 转义
**实际未生效**（会被 shell 吃掉反斜杠或报 trailing backslash）。本轮改用
`tests/ota/p3_1_verify_portability.py` 重做，
并强制要求阳性对照（对照为空即直接判失败，杜绝把扫描失效误读为通过）：

```text
扫描文件数 = 893
[阳性对照] .old 存档命中 1 处
  Libraries/USB_MSC/msc_diskio.c.old:25  #include "msc_class\msc_bot_scsi.h"
[正式] 参与编译的手写源命中 0 处   → CI 可移植性红线通过
```

阳性对照命中证明正则确有鉴别力，因此"0 命中"是**有效结论**而非扫描失效。

## 6. harness 鉴别力验证（变异测试，本轮核心增量）

`docs/acceptance-execution-contract.md` §7 要求 harness 必须 fail-closed、
禁止常量 PASS。仅"测试全绿"不足以证明这一点，故在 `.cache` 副本上注入产品缺陷
（工作区源全程只读）：

| 变异 | 注入缺陷 | 测试反应 |
|---|---|---|
| M1 | CRC16 多项式 `0x1021` → `0x1022`（偏离合同） | **变红** ✅ |
| M2 | seq 16bit 回绕比较退化为无符号比较 | **变红** ✅ |
| M4 | END 整包 SHA-256 复核门禁短路 | **变红** ✅ |
| M3 | 仅禁用 session 层 `off < durable_off` 幂等短路 | 仍全绿 → 判定为**等价变异** |
| M5 | **同时**禁用 session 层短路 **与** staging 层幂等 | **变红** ✅ |

**M3 定性**：`ota_staging_receive()` 自身对 `offset < durable_off` 返回
`OTA_STAGING_DUPLICATE`，session 层再映射为 `ACK_DATA/OK` 且不重写。即
R8-4 幂等是 **staging + session 双层防御**，禁用其一后外部可观测协议行为完全不变，
测试保持绿色是**正确的**（黑盒契约未被破坏）。M5 证明该行为整体确被测试锁定。

> 结论：**有效变异 4/4 全部被捕获**，harness 具备真实鉴别力，非常量 PASS。

## 6bis. 命令忠实性：冻结命令 ↔ 冻结日志逐字节复算（本轮新增）

`docs/acceptance-execution-contract.md` §4 要求"PASS/FAIL 都必须绑定原始证据和实际
观测值"。但合同 `commands[].command` 字段若只是事后追述，整份证据矩阵就退化为自述：
校验器只会核对日志文件的路径/大小/SHA-256，**不会验证"该命令确实产出该日志"**。

`tests/ota/p3_1_verify_command_fidelity.py` 把 11 条冻结命令原样重跑，与证据包内
对应日志逐字节比对：

```text
[OK  ] test-ble-frame.log              exit=0  复跑 3126B  / 冻结 3126B
[OK  ] test-ble-session.log            exit=0  复跑 8205B  / 冻结 8205B
[OK  ] test-regression.log             exit=0  复跑 15230B / 冻结 15230B  （掩码行 [195, 198, 200]）
[OK  ] verify-contract-alignment.log   exit=0  复跑 2848B  / 冻结 2848B
[OK  ] verify-production-binary.log    exit=0  复跑 1161B  / 冻结 1161B
[OK  ] verify-portability.log          exit=0  复跑 424B   / 冻结 424B
[OK  ] verify-artifacts.log            exit=0  复跑 1796B  / 冻结 1796B
[OK  ] verify-text-isolation.log       exit=0  复跑 637B   / 冻结 637B
[OK  ] verify-mutation.log             exit=0  复跑 1285B  / 冻结 1285B
[OK  ] verify-rx-ring-budget.log       exit=0  复跑 772B   / 冻结 772B
[OK  ] build-sync-check.log            exit=0  复跑 99B    / 冻结 99B

=== 命令 11 条；不忠实 0 条；随机量掩码行合计 3 行 ===
P3_1_COMMAND_FIDELITY=PASS cases=11 mismatched=0 masked_lines=3
```

**归一化范围受严格限制**，只允许四类与语义无关的差异，其余一律判失败：

| # | 掩码对象 | 来源 | 正则 |
|---|---|---|---|
| 1 | CRLF/LF | Windows 与 bash 管道混用 | 整体替换 |
| 2 | `tempfile.mkdtemp()` 随机后缀 | P2-4 回归把 `.etu` 打进随机临时目录并打印绝对路径 | `(etrack-[0-9a-z-]*?-)[0-9A-Za-z_]{8}` |
| 3 | `aes_nonce=<32 hex>` | 打包器每轮生成新随机 nonce | `(aes_nonce=)[0-9a-f]{32}` |
| 4 | `header_crc32=<8 hex>` | 该 CRC 覆盖含随机 nonce 的头部，必然随 3 变化 | `(header_crc32=)[0-9a-f]{8}` |

三处随机量已用**两次独立复跑定性**：`test-regression.log` 共 211 行，恒定只有第
195/198/200 行变化，且互为因果（随机目录 → 随机 nonce → nonce 派生的 CRC）；其余
10 条日志逐字节完全相同、零掩码。掩码按精确正则替换，只有"差异完全落在被掩码片段内"
的行才会归一化后相等，因此掩码不可能吞掉其他位置的真实回归；被掩码行号逐条打印，
便于复核掩码是否越界（本轮 `masked_lines=3`，与定性结论一致）。

第 12 条冻结命令（全量 GCC 构建）代价过高不在此复跑，已按 **DEV-2** 显式登记：
其原始 stdout（293478B）直接入包为 `commands/full-build-raw.log` 自证，
而非只留一个派生的 warning 统计。

> 意义：合同的 `command` 字段由此从"事后追述"升级为**可复算判据**（`COMMAND-FIDELITY`），
> 12 条被验证的命令日志同时作为该判据的 artifact 绑定（沿用 P2-6 的 custody 模式）。

## 7. 判据逐条核对

### 7.1 看板 P3-1 卡验收字段（唯一任务源）

| 判据 | 证据 | 结论 |
|---|---|---|
| 模拟发送器对向量包全传 | 用例 20-34：40 段全 ACK → 块边界 4KiB → bitmap bit0 → 尾段整包 durable → END OK → **staged payload 逐字节一致** → ETSL 记录长度/CRC/target/SHA8 → commit marker | **PASS** |
| 丢段/乱序/重复/注错全部正确恢复 | seq 断档 ERR_SEQ 后可续（44-47）、0xFFFF 回绕（48-51）、重复 BEGIN/DATA 幂等（35-42）、非对齐 off/短段/越界/错 session（53-56）、冲突内容 fail-closed ABORTED 后重传成功且字节一致（62-65）、ABORT→resume 不重擦已 durable 块（79-87） | **PASS** |

### 7.2 派工书完成判据

| # | 判据 | 结论 |
|---|---|---|
| 1 | 向量包全传 | PASS（同上） |
| 2 | 丢段/乱序/重复/注错恢复 | PASS（同上） |
| 3 | 文本协议非 OTA 期兼容、活跃期无串扰 | PASS：用例 101/103/105（空闲到 sink、活跃期丢弃且**永不到 sink**、拆除后恢复）；HAL 层活跃期关闭 200ms X-Trace 上行；`CONFIG_BT_USE_TRANSPARENT = 0`（生产构型下 debug 透传代码不编译） |
| 4 | RAM/栈/buffer 静态 + 运行期证据 | **部分**：静态 map 实证齐全，并经 §4bis 生产编译探针把"环 4096B / receiver 4164B / session 568B / overlay 40960B、余量 32700B"由源码字面量升级为按实际编译取证；host 运行期覆盖 workspace 容量拒绝与 ring 排空；**MCU 真机运行期实测缺失**（实现者已在证据 §8 登记，归 P3-3 真机闭环；合同 v2 已把真机闭环移出判据集、改在 `scope.excluded_by_freeze` 登记，见 §9-J） |
| 5 | 全部测试与构建通过并逐项报告 warning/error | PASS：全量 637 / 增量 395 warning、0 error；新增三源 0 warning；warning 归属已逐项归因既有源 |

### 7.3 冻结契约 §5 一致性

`ota_ble_frame.h` 与 `docs/ota-binary-contracts.md` §5 逐项比对一致：帧布局
（`A5 5A | cmd | session | seq | len | payload | crc16`）、CRC16-CCITT-FALSE 覆盖范围、
命令表 0x00-0x04 / 0x80-0x84、INFO 50B、BEGIN 101B、END 32B、DATA `u32 off + 128B`、
ACK 10B/9B、20 个状态码、`proto_ver` 恒 1、`max_window_segs` 恒 32。**未发现契约漂移**。

## 8. 接线与 diff 审查

- `HAL_Bluetooth.cpp`（+241/-15）：ISR/主循环对 HW 环的消费**严格互斥**且无竞争——
  `isr_active` 由主线程处理 BEGIN 时置位（同线程），置位后 `bt_rx_service` 的 while
  条件立即失效，ISR 侧仅在 `isr_active` 为真时读取。竞争窗口分析未发现丢字节或伪字节注入路径。
- `HAL_OTA_Package.{h,cpp}`：新增 `OTA_OVERLAY_BLE=3` owner，**复用**既有
  `overlay_acquire/release` 互斥机制，无自研新机制，符合"标准化+生态复用"优先级。
- `CMakeLists.txt`：仅 3 行新源，经生成脚本再生（未手改生成物）。
- `proj.uvprojx`：仅新增 6 个 `<File>` 条目（3 `.c` + 3 `.h`），Legacy target 未动。
- `PLAN-OTA-EXEC.md`：仅 3 处（状态行、证据行、§10 一行），回写最小化。
- **行尾伪变更已确证还原**：逐文件比对 HEAD 与工作区的 CRLF 计数与 diff 行数，
  三处全部自洽（1045-1=1044、43+8=51、177+3=180）；`HAL_Bluetooth.cpp` HEAD 与工作区均全 LF。
  实现者"字节级还原"声明属实。

---

## 9. 发现与处置

| 编号 | 级别 | 内容 | 处置建议 |
|---|---|---|---|
| A | 流程缺口（**本轮已闭环**） | 首轮技术验收时 `docs/acceptance-contracts/` 下不存在 P3-1 冻结合同，`Tools/acceptance/validate_bundle.py` 无校验对象 | **已按规范补齐**：冻结 `P3-1-v2.contract.json`（v2 / FROZEN / `parent_contract_sha256=null`）、三类 manifest、证据矩阵与紧凑证据包，校验器 `VALIDATION=PASS` |
| B | 文档订正 | `P3-1-build-evidence.md` §6 的自检命令因 shell 转义未真正生效 | 订正为带阳性对照的脚本式扫描（本报告 §5 已给出可复现结论） |
| C | 申报偏差（轻微） | 声称"10 个新增文件"，实际未跟踪新增 **12 个**（6 源 + 2 文档 + 4 测试） | 收口时按实际清单登记 |
| D | 设计事实（非缺陷） | R8-4 幂等在 staging 与 session **双层**实现，session 层为冗余短路 | 登记备查；不需修改（防御纵深合理） |
| E | 证据边界（已登记） | MCU 真机运行期 RAM/栈实测、AC5 构建未执行；Boot 未重编（零源变更） | 维持现状，真机闭环归 P3-3 |
| F | **验收发现（非判据）** | `.github/workflows/firmware-build.yml` 的测试步骤列出了 boot 三套与 staging/package/patch，但**未接入** `tests/ota/test_ota_ble_frame.py` 与 `test_ota_ble_session.py`；两套 BLE 测试目前只有本地执行证据，CI 上不会跑 | 不作为本轮合同判据（看板 P3-1 卡验收字段与派工书完成判据均未要求 CI 接线，事后加门槛违反 `docs/acceptance-execution-contract.md` §5 关于门槛来源的约束）。已在合同 `scope.excluded_by_freeze` 内显式记录为"因冻结范围而排除"，不构成静默漏判。**用户裁定：另开一张卡**——已新建看板 P3-6「BLE 帧层测试 CI 接线」并在看板 §9 变更登记表登记，详见下方 §9ter |
| G | 取证方法升级（**本轮已闭环**） | 「接收缓冲 ≥4KB」原本只有源码字面量支撑，而 `CONFIG_OTA_BLE_RX_RING_SIZE` 带 `#ifndef` 兜底，字面量不等于生产构型实际展开值 | 已改为 §4bis 的生产编译探针反读（`compile_commands.json` 原样 flag + `nm -S`），并联立 map `.ota_overlay` 核算 BEGIN 子分配余量；冻结为判据 `RX-RING-BUDGET` 与 `OVERLAY-SUBALLOCATION-HEADROOM` |
| H | 取证方法升级（**本轮已闭环**） | 合同 `commands[].command` 若为事后追述，校验器只核对日志哈希、无法证明"该命令产出该日志" | 已加 §6bis 命令忠实性复算（11/11 逐字节一致，3 行随机量掩码已定性），冻结为判据 `COMMAND-FIDELITY` |
| I | 合同边界（已登记为 DEV-3） | 判据 `FRAME-WIRE-CONTRACT` 的权威来源 `docs/ota-binary-contracts.md` **不在任何 manifest profile 的枚举范围内**（Governance 只枚举 `docs/ota-prompts/` 与 6 个 `top_files`），无法由 `input_groups` 绑定指纹 | 已改以 `external_inputs`（`EXT-BINARY-CONTRACT`，category=`fixture`）显式冻结其包内副本 `external/ota-binary-contracts.md` 与 SHA-256，并由 C1 的 `criterion.external_inputs` 引用。**profile 范围变更须走 `.github/workflows/acceptance-governance.yml`，不在本卡处置** |
| J | **合同瑕疵（用户复核发现，本轮已闭环）** | v1 的判据 `HW-BLE-CLOSED-LOOP`（真机 BLE 闭环）把 `gate.basis` 标为 `frozen_requirement`，但其 `expected` 内的 `disconnect_resume=10/10` 在看板 P3-1 卡验收字段与派工书 `docs/ota-prompts/prompt-P3-1-implementation.md` 中**均查无来源**，系验收会话自拟；该判据还绑定 host 测试的命令与日志充当「真机」证据，且恒为 `NOT_OBSERVED` | 门槛不得自拟（同 `docs/acceptance-execution-contract.md` 关于门槛来源的约束）。`Tools/acceptance/validate_bundle.py:562-571` 只校验 `gate.basis` 取值是否落在枚举 `GATE_BASES` 内，**无法核实其声称的来源是否真实存在**，故未拦截；该判据 `required=false`，本就不参与 `overall=PASS` 门禁（`validate_bundle.py:719-731`），列入合同反而制造了「18 条只过 17 条」的误导观感。**用户裁定：删除该判据**，改在 `scope.excluded_by_freeze` 登记真机闭环由 P3-3 卡验收字段「对真机传输 toy 包与真包成功」承接；合同升版 `P3-1-v2` |

### 9bis. 合同内登记的授权偏差

| 编号 | 内容 | 理由 |
|---|---|---|
| DEV-1 | 命令忠实性复算允许 3 行随机量掩码（mkdtemp 后缀 / AES nonce / nonce 派生 CRC32） | 三者均为打包器与临时目录的固有随机量，已用两次独立复跑定性为恒定的第 195/198/200 行；掩码用精确正则且逐行打印行号，不会吞掉其他位置的真实回归（§6bis） |
| DEV-2 | 全量 GCC 构建命令不参与忠实性复跑 | 单次构建代价过高；改为把其**原始 stdout**（293478B）直接入包 `commands/full-build-raw.log` 自证，而非只留派生统计 |
| DEV-3 | `docs/ota-binary-contracts.md` 以 `external_inputs` 而非 `input_groups` 绑定 | 该文件不在任何 profile 枚举范围内（同上 §9-I）；扩大 profile 范围属治理变更，须走 acceptance-governance CI |

> 工作区其余未跟踪文件（`.cache-cmake-time-test.cmake`、`.claude/*.js`、`.claude/*.py`）
> 为**先前会话遗留**，会话初始快照即存在，不归属 P3-1。

### 9ter. §9-F 的落地：新立看板 P3-6（用户裁定"另开一张卡"）

CI 接线缺口不并入 P3-1（门槛来源约束），按用户裁定转为独立任务卡。为不破坏看板的
机器门禁，本次回写是**整套卡机制**而非只加一个标题：

| 落点 | 内容 |
|---|---|
| §6 卡片 | 新增 `#### P3-6 BLE 帧层测试 CI 接线`，含依赖 / 目标 / 验收 / 注意四段。验收要求 CI 日志中出现两套测试的**实际执行输出**，并须给出"接线确实生效"的反证（注入缺陷令 workflow 变红后还原，或等效 fail-closed 证明）——仅有 workflow 文本 diff 或本地执行证据不算通过 |
| §8.1 readiness 矩阵 | 新增第 6 行 `P3-6`，其后 `P4-1`…`P5-3` 顺序号由 6…12 顺延为 7…13 |
| §9 变更登记表 | 登记缺口、"不并入 P3-1"的理由、用户裁定与后续约束；状态 `已登记/已开卡` |
| §10 会话日志 | 追加本轮验收与新立卡的记录 |

`tests/ota/test_acceptance_bundle.py` 对 §8.1 有四重机器约束：矩阵必须**严格镜像**
看板正文 `#### P\d+-\d+` 的出现顺序、顺序号必须是连续 1..N、`dispatch` 由
`content_readiness` 与 `dependency_state` **推导**（不可手填）、且首批可派单集合被
`assertEqual({"P3-1","P3-2","P4-2"}, dispatchable)` **精确钉死**。因此新行若填成
READY + SATISFIED 会自动变为 `DISPATCHABLE` 并直接打红该断言。

此处未为了让门禁通过而捏造依赖：P3-6 的 `BLOCKED_BY_DEPENDENCY` 是**真实硬依赖**
——`tests/ota/test_ota_ble_frame.py` 与 `test_ota_ble_session.py` 当前仍是未跟踪文件，
在 P3-1 收口合并前接线，CI 会因找不到测试文件直接变红。回写前后各跑一次
`python -B -m unittest tests.ota.test_acceptance_bundle`，均为 `Ran 65 tests ... OK`。

P3-6 卡内另行记录了两处后续地雷：`.github/workflows/firmware-build.yml` 是 Production
profile 的 `top_file` 与 `required_path`，改它会使 P3-1-v2 合同内的 Production 指纹失效，
故 P3-6 须自带新 `task_id` 的合同、不得回改 P3-1 的合同或矩阵；以及待 P3-1 合并后把
P3-6 的 `dependency_state` 置 `SATISFIED` 时，它会变为 `DISPATCHABLE` 并触发上述"首批
派单集合精确受控"断言，须与派工书编写同批走治理变更。

## 10. 评分

| 维度 | 分项 | 分数 |
|---|---|---|
| 技术 | 代码质量（零 wire memcpy / 零动态分配 / env 全注入 / fail-closed / 并发互斥正确） | 95 |
| 技术 | 测试覆盖（144 项 host 用例，变异有效 4/4 检出） | 96 |
| 技术 | 规范遵循（可移植性与生产红线全过；扣：证据文档自检命令无效、文件数申报偏差） | 88 |
| 战略 | 需求匹配（看板 2 条判据全满足；派工书判据 4 的真机运行期证据归 P3-3） | 94 |
| 战略 | 架构一致（复用 overlay owner / staging，无自研新机制，契约零漂移） | 96 |
| 战略 | 风险评估（并发与 fail-closed 分析充分；扣：两套 BLE 测试未接入 CI，见 §9-F） | 90 |
| **综合** | | **93** |

## 11. 验收结论

P3-1 单轮验收结果 = **PASS**（合同制正式验收）。冻结合同 `P3-1-v2` 的 **17 条判据**
全部 `required=true` 且全部 `EXECUTED PASS`，无 `NOT_OBSERVED`、无 `FAIL`、无 `REUSED`：
host 测试 5 套全绿（BLE 帧 39 + 会话 105 + 既有 OTA 回归）、产物哈希 9/9 一致、
生产二进制红线静态实证全过、契约 47 项零漂移、可移植性带阳性对照通过、
接收环按生产编译 flag 反读实测 4096B 且 overlay 余量 32700B、
全量构建 0 error 且 P3-1 新源编译期 0 warning、11 条冻结命令逐字节可复算，
并经变异测试证明 harness 具备真实鉴别力（有效变异 4/4 检出、1 项等价变异定性正确）。

流程侧亦已完备：冻结合同 `P3-1-v2`、三类 manifest（Production/Validation/Governance）、
证据矩阵与紧凑证据包齐备，`Tools/acceptance/validate_bundle.py` 校验通过
（`VALIDATION=PASS`，EXIT=0）。

依 `docs/acceptance-execution-contract.md` §2，本报告只给出**单轮验收结果**，
不代替实现认领人的任务状态回写，也不代替主会话的 Git 收口闭环（同规约 §Git/Worktree）。

本轮为纯验收会话：未修改任何工作区**产品源文件**（新增内容仅为
`docs/acceptance-contracts/P3-1-v2/**` 验收资产、`tests/ota/p3_1_verify_*.py` 验证工具、
本报告与看板回写），未执行 git commit/push/merge，未触碰 P2-6 证据根，
变异与构建等临时产物落于 `.cache/p3-1-acceptance/`（在 `.gitignore` 内），项目外无写入。

---

## 12. 合同制验收资产指纹登记

> 本文件 `docs/ota-exec-notes/**` 不在 `Tools/provenance/manifest_profiles.json` 的
> 任何 profile 枚举范围内，因此在此登记哈希**不会**回过头改变任何 manifest 指纹，
> 也就不会形成「改文档 → 改指纹 → 改合同 → 改合同哈希」的自指循环。
> 对照：`PLAN-OTA-EXEC.md` 是 Governance 的 `top_file`，故看板回写**只记录路径与结论、
> 不记录任何哈希**——否则每次回写都会让刚冻结的合同失效。

### 12.1 合同与证据矩阵

| 资产 | 路径 | 字节 | SHA-256 |
|---|---|---|---|
| 冻结合同 | `docs/acceptance-contracts/P3-1-v2.contract.json` | 30066 | `E38FF2A6AD38806BDCD8AF589DEC3BFC3D0BEBD5C4837C572C482F97D2D99424` |
| 证据矩阵 | `docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json` | 19335 | `81703655EFA4C4FDC4F14DB6F4D90C4C7DE9929EF2517F7920E462047EADC9D7` |
| 已废弃 v1 合同 | *不入包*（见下方说明） | 30092 | `2CBC789BE235FDAA3C82B2E02844FF7C66FC58A27849A49B5923E6ED68364480` |

合同关键字段：`schema=etrack-acceptance-contract-v2`、`contract_id=P3-1-v2`、
`task_id=P3-1`、`version=2`、`parent_contract_sha256=2CBC789B…`（绑定 v1）、`status=FROZEN`、
`performance_gates=[]`（本卡无性能门禁，避免把历史测量值反向冻结为门槛）。
矩阵关键字段：`round_id=P3-1-V2-FREEZE-20260902-01`、`overall_result=PASS`、
`previous_matrix_sha256=null` / `rerun_plan=null`（首轮无证据复用）。

**关于 v1 未入包**：v1 与 v2 是**同一轮次内**的合同自我修正——同一天、同一 Head、
同一验收会话、同一批证据，差异仅为删除一条自拟门槛的判据（§9-J）。v1 从未提交、
从未推送、从未合并，仓库历史中不存在它。规约要求的是 `parent_contract_sha256` 绑定，
并未要求 parent 合同文件在场，故此处只登记其字节数与哈希，不复制一份内容完全相同的
证据包（规约 §6「默认不保留重复副本」）。

> 与 `P2-6-v1/v2/v3` 并列保留三份完整证据包的做法不同：P2-6 的三个版本是**三个真实
> 轮次**，证据在增长（29 / 36 / 72 个文件）；本卡的 v1 不是一个独立轮次。若后续治理
> 认为草稿合同也须留档，可从本节哈希复核，并在下一轮补档。

### 12.2 三类 manifest（Head `77e14cfe5c8e3d8b9d72f4d73cc84009aa267557`）

| Profile | 文件数 | `ManifestSHA256`（内部稳定指纹） |
|---|---|---|
| Production | 2918 | `9A63A80F44935978B2294EF8BB58F6C9CF434E720025C3D8032403B0CCC3E598` |
| Validation | 142 | `579A4728663F3DEB0337EE6492734D1BC3F88BE456F6E493D2A98564F71FDFF6` |
| Governance | 24 | `079F13886686E267220F53817D5D4506FA26491030D92D80AE2DF610F2343808` |

生成命令（逐 profile 各执行一次）：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "& 'Tools\provenance\source_manifest.ps1' -RepoRoot '.' -OutputDirectory 'docs\acceptance-contracts\P3-1-v2\manifest-<profile>' -Profile '<Profile>'"
```

**收敛顺序（固定一轮）**：先把看板改动一次做完（含 §9ter 的 P3-6 新卡），再
重生成 Governance manifest → 重算合同/矩阵 → 重跑校验器。Governance 文件数保持 24
（P3-6 只改 `PLAN-OTA-EXEC.md` 内容，未新增文件），`ManifestSHA256` 随之更新。

**收敛稳定性验证**：合同与矩阵被重写之后，再次生成一份 Governance manifest 到
`.cache/p3-1-acceptance/stability-check/gov/`（工作区外产物落在 `.gitignore` 内），
结果与包内一致，证明 `docs/acceptance-contracts/**` 不在 Governance 枚举范围内，
"重算合同 → 再次失效"的循环不存在，一轮即收敛。

**升 v2 时三类 manifest 的实测行为**：证据包目录由 `P3-1-v1/` 改名为 `P3-1-v2/`、
看板同步回写后，三类 manifest 全部重新生成，Production（2918）与 Validation（142）的
`ManifestSHA256` **一字未变**，只有 Governance 因 `PLAN-OTA-EXEC.md` 内容改变而更新。
这与规约 §7「manifest 保存位置变化不得触发产品复验」一致，也再次说明合同升版没有
触动任何产品输入。

### 12.3 校验命令与结果

```bash
python -B Tools/acceptance/validate_bundle.py \
  --contract docs/acceptance-contracts/P3-1-v2.contract.json \
  --matrix   docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json \
  --repo-root .

VALIDATION=PASS contract=P3-1-v2 round=P3-1-V2-FREEZE-20260902-01 overall=PASS
EXIT=0
```

校验器会从该 worktree **重新枚举并读取**每个 profile 的真实文件，并逐项复核
证据/产物的路径、大小与 SHA-256，因此 manifest 自洽不足以通过。

### 12.4 紧凑证据包清单

`docs/acceptance-contracts/P3-1-v2/` 下共 **27 项证据哈希**：

| 分组 | 数量 | 内容 |
|---|---|---|
| `artifacts/` | 3 | 生产 App 的 ELF（867952B，nm 符号取证）、链接 map（2433909B，Discarded 区 / `.ota_overlay` / `s_ble_session` 取证）、`artifact-index.json` |
| `commands/` | 14 | 13 条冻结命令的 stdout，含 `full-build-raw.log`（293478B 原始构建输出，DEV-2） |
| `manifest-*/` | 9 | 三类 manifest 各 3 个文件（`source-manifest.json` / `summary.json` / 说明） |
| `external/` | 1 | `ota-binary-contracts.md`（`EXT-BINARY-CONTRACT`，DEV-3 绑定） |

按规约"默认不保留完整构建目录或重复源码副本"：只收判据真正取证的产物，
未收 Boot 侧产物（本卡无判据引用）、未收整棵 `build-gcc-release/`。
