# P3-1 编码前研究笔记：BLE 传输层（帧 parser / 会话 / RX 缓冲落位）

- 日期：2026-09-01
- 作者：P3-1 实现 agent（Claude）
- 状态：研究结论，作为实现依据。冻结权威 = `docs/ota-prompts/prompt-P3-1-implementation.md` + `docs/ota-binary-contracts.md` §4.2/§4.5/§5 + `docs/ota-cross-system-contracts.md` §7/§8。本文与权威冲突时以权威为准。

## 1. 已核实的架构事实（带出处）

### 1.1 UART / 调度链路

| 事实 | 出处 |
|---|---|
| BT 串口 = `CONFIG_BT_SERIAL` = `Serial`（USART1/PA9/PA10），115200 | `USER/HAL/HAL_Config.h:92`、`HAL_Bluetooth.cpp:15` |
| `BT_Update` 由 `taskManager.Register(BT_Update, 200)` 每 200ms 调度，内含 X-Trace 周期上行 + RX drain + TinyBTPlus encode | `USER/HAL/HAL.cpp:148`、`HAL_Bluetooth.cpp:56-84` |
| `HardwareSerial` 每实例内嵌 `_rxBuffer[SERIAL_RX_BUFFER_SIZE]`（512B，`mcu_config.h:40`），3 个实例（Serial1/2/5）共用同一宏，无按实例尺寸机制 | `Platform/Core/HardwareSerial.{h,cpp}` |
| IRQHandler 每字节：存 HW 环（满则丢新字节）→ 调用 `_callbackFunction(this)`；`attachInterrupt(void(*)(HardwareSerial*))` 可挂回调 | `HardwareSerial.cpp`（attachInterrupt 在 224 行，flush=RX 环复位在 281 行） |
| `available()`/`read()` 仅操作 volatile head/tail，可在 ISR 上下文安全调用（head=ISR 写，tail=reader 写） | `HardwareSerial.cpp` |
| 调试串口 = Serial5（RTT 无法采集）；`CONFIG_BT_USE_TRANSPARENT=0`（透传代码已编译剔除） | `HAL_Config.h`、`HAL_Bluetooth.cpp:72-83` |
| 模拟器（`Simulator/LVGL.Simulator`）有自己的 `HAL/HAL_Bluetooth.cpp` 拷贝，include 路径不含 `USER/HAL`——MCU 侧改动不影响模拟器 | `LVGL.Simulator.vcxproj:423` + include 路径 |

### 1.2 RAM 布局与 overlay 仲裁（P2-6 v3 冻结口径）

- 主 RAM 352KB（0x20000000..0x20058000）：生产已分配 357088B，**堆空洞仅 3360B**；顶部为 `.ota_stack_guard`(32B)+`.ota_stack`(8192B)，A5 断言封顶。
- RW_IRAM2 160KB 是 `OVERLAY` 别名区：`.sram_ext`（LiveMap snapshotBuf 163840B）与 `.ota_overlay`（`g_ota_overlay_workspace` 40960B）**同址 0x20058000**，链接断言 `SIZEOF(.ota_overlay)==0xA000`（`cmake/linker/x-track-app-gcc.ld.S:244-272`）。
- 运行时仲裁：`overlay_acquire(owner)`（临界区内，仅 owner==FREE 时成功；owner 枚举 FREE/LIVE_MAP/PACKAGE）；LiveMap 在屏期间整页持有（`LiveMap.cpp:412` 获取、632 释放），获取失败降级无快照运行（`HAL_OTA_Package.cpp:286-311`）。
- **结论：LiveMap 在屏时 BLE BEGIN 必然拿不到 overlay → ERR_BUSY。** 这是 overlay 架构固有约束（物理同址，非软件缺陷）；实际升级场景用户停留在非地图页。发送端按 §5.7 ERR_BUSY 重试。

### 1.3 可复用组件（全部通过注入接口使用，禁止复制逻辑）

| 组件 | 用途 |
|---|---|
| `ota_staging_begin/receive/finalize`（`Libraries/OTA/ota_staging.{h,c}`） | 唯一 staging 写入通道；receiver 内嵌 4KB 块缓冲；begin 自动做 ETRJ 匹配 resume / 整页擦除重建 |
| `ota_sd_inspect_header`（`Libraries/OTA/ota_sd.h`） | BEGIN 的 64B etu_header 全项校验（magic/CRC/flags/alg/key/hw/layout/boot/version/base/kind），错误直接映射 §5.7 |
| `boot_sha256_*`（`boot/include/boot_crypto.h`，ctx 112B） | 增量 SHA-256（块提交时机 + resume 前缀回填） |
| `HAL::OTA_StagingGetIo`（`USER/HAL/HAL_OTA_Staging.h`） | QSPI staging IO（read/erase_4k/program，含范围校验） |
| `HAL::OTA_OverlayAcquireLiveMap/Release` 模式（`HAL_OTA_Package.cpp`） | 本卡照该模式新增 BLE owner |

## 2. ≥4KB RX 缓冲落位决策（本卡核心架构判断）

合同 §5.1 冻结"MCU UART 环形缓冲 ≥4KB"。排除的方案：

| 方案 | 排除原因 |
|---|---|
| 全局 `SERIAL_RX_BUFFER_SIZE` 512→4096 | 3 实例 × +3584B = +10752B .bss，堆空洞仅 3360B，A5 链接断言必炸 |
| 仅 BT 串口实例扩 4096 | 需改 `HardwareSerial` 类（Platform/Core，不在允许范围）；且 +3584B > 3360B 仍溢出 |
| RX 环放 `.ota_overlay` 且由 HW 环高频轮询泵送（无 ISR 分流） | 921600（P3-4 目标档）下 512B HW 环要求轮询 ≤5.5ms，零余量；且"提高轮询频率"并未真正提供 ≥4KB 缓冲 |
| RX 环常驻 .bss | 4KB + 4KB receiver ≈ 8.3KB > 3360B 空洞 |

**定稿方案：ISR 回调分流 + overlay 内 4KB 环（受控 RX buffer）**

1. `BT_SERIAL.attachInterrupt(hook)` 挂 ISR 回调（既有机制，非新外设路径）。
2. 会话空闲（`g_active=0`）：hook 立即返回，字节留在 512B HW 环，文本/GET_INFO 路径照旧（GET_INFO 帧 10B、BEGIN 帧 109B，远小于 512B）。
3. BEGIN 成功：获取 overlay（新 owner BLE）→ 在 workspace 内构造 4KB RX 环 + `ota_staging_receiver_t`（4160B）→ 置 `g_active=1`。
4. 会话活跃（`g_active=1`）：hook 里 `while(serial->available()) ota_ble_isr_feed(read())` 把 HW 环即时搬空进 overlay 4KB 环（HW 环永不积压；tail 仅 ISR 动）。pump（20ms）只消费 overlay 环（SPSC：head=ISR、tail=pump，与 HardwareSerial 同构）。4KB @ 921600 = 44ms 容量 ≫ 20ms 泵周期。
5. 会话结束（END/ABORT/超时）：先置 `g_active=0` → pump 排空 overlay 环残留（可能含下一帧前缀，继续喂 parser）→ release overlay → 文本通道恢复。

**已知边界（接受并记录）**：BEGIN 处理末尾"排空 HW 环→置 active=1"之间存在 <1µs 窗口（pump 自身几条指令），字节日 86µs@115200，命中需 BEGIN 帧尾恰落窗口。若命中且其后无字节：帧尾滞留 HW 环 → CRC 失败 → 发送端超时重传即恢复（fail-closed，不损 durable 数据）。不采用关中断临界区包住 drain（drain 含 parser 推进，临界区过长）。

**内存预算**：主 RAM .bss 新增 ≈ session 控制块+parser 状态+132B 重组缓冲+sha ctx+IO/回调注入 ≈ 650B < 3360B ✓；overlay 子分配 4096+4160=8256B ≤ 40960B（apply 走 PACKAGE owner 用全区，与 BLE 时间互斥）✓。

## 3. 协议实现要点（§5 全项 → 实现决策）

### 3.1 顶层 demux（HAL UART 层职责，合同 §5.1）

- 1 字节 hold-back 状态机：IDLE 收 `0xA5` → HOLD；HOLD 收 `0x5A` → 进二进制帧 parser；否则 `0xA5` 与当前字节都走文本（当前字节若又是 `0xA5` 则保持 HOLD）。`A5 A5 5A` 序列文本侧只漏一个 `A5`——按合同"收到 A5 5A 进入二进制处理器"的字面语义实现。
- 会话活跃期：非帧字节**丢弃**（有界），不喂 TinyBTPlus（合同：活跃期文本 parser/回显/透传零调用、上行只允许 ACK/事件帧）。
- 帧失败（CRC/长度）后从失败点重新扫描 `A5 5A`（重新同步），已消费字节不回吐文本。

### 3.2 帧 parser（增量式，跨任意 read 边界）

- 状态机：SYNC1→SYNC2→CMD→SESSION→SEQ→LEN→PAYLOAD[len]→CRC。len>132（DATA 帧 payload 上限 4+128）→ ERR_FRAME 立即拒绝。
- cmd 定长表在 parser 层：GET_INFO=0、BEGIN=101、END=32、ABORT=0；DATA∈[4,132]。语义校验（off 对齐、包尾定界）留 session 层。
- CRC16-CCITT-FALSE（poly 0x1021, init 0xFFFF, 不反射）覆盖 cmd..payload，逐位实现（921600 下 ≈0.26% CPU，省 512B 查表 flash）。
- **任何校验失败在产生 staging 副作用之前拒绝**（帧 CRC 先于一切 session/staging 动作）。

### 3.3 seq / session / 幂等

- `(int16)(seq-expected)`：=0 正常推进；<0 重发帧 → 幂等重发当前 ACK（实时 durable_off+bitmap）；>0 → ERR_SEQ。
- BEGIN 重置 expected=begin_seq+1；重复 BEGIN 同 sha → 幂等回当前进度（不重跑 `ota_staging_begin`，避免复位 RAM 块缓冲丢失已收未落盘段）；不同 sha → 按新会话处理（staging 自动整页重建）。
- session 不匹配 → ERR_SESSION；未 BEGIN 先 DATA/END → ERR_STATE。GET_INFO：session 必为 0，不建会话，seq 不校验（无会话上下文，仅回显）。
- MC UID 会话号：非零递增 u8（1..255 回绕避 0）。

### 3.4 内部错误 → §5.7 wire status 映射（合同未逐条显式覆盖处的决策）

| 内部情形 | wire status | 依据/理由 |
|---|---|---|
| overlay 被 LiveMap/PACKAGE 占用，BEGIN 无法获取 | **ERR_BUSY(0x0E)** | "拒绝新 OTA，稍后重试"语义一致；ERR_FLASH 保留给真实 QSPI IO 失败 |
| 同 offset 不同内容 DATA（staging ERR_DATA） | **ABORTED(0xFF)** + 终止会话 | 合同"不同内容占用已接收 offset 必须 fail closed"；0xFF 处置="状态已清理,可重新 BEGIN"，与恢复路径（重新 BEGIN resume）吻合 |
| END 时 durable_off<total_len（缺段） | **ERR_STATE(0x05)** | 发送端重新 BEGIN resume 续传；ACK 自带 durable_off+bitmap |
| END sha 复述不符 / 整包 SHA 复核不符 | **ERR_SHA(0x10)** + 擦除 staging 槽头 4KB 页 + 终止 | "整页擦除重传"——擦 ETRJ/位图页后，同 sha 重新 BEGIN 也走整页重建（否则 resume 会复活坏数据） |
| finalize IO 失败 | **ERR_FLASH(0x0F)** + 终止会话（staging 保留） | 发送端重新 BEGIN resume 后重试 END/finalize |
| `ota_sd_inspect_header` 各失败项 | ERR_HDR/HW_REV/LAYOUT/BOOT_VER/VERSION/BASE/LEN | 一一对应（ota_sd.h 错误枚举 → §5.7） |
| BCB 非 CONFIRMED | ERR_BUSY | 与 SD 路径同门槛（staging 擦除前置条件） |
| JEDEC 白名单外 | ERR_OTA_DISABLED | §0.7 |
| proto_ver≠1 | ERR_PROTO | §5.7 |
| 30s 无有效帧（会话超时） | 上行 0x84 ACK(status=ABORTED) + 清理 | 合同"会话超时"活跃期出口；超时以**有效帧**（CRC 过）重置，纯噪声不重置（防 DoS 压制文本通道） |

### 3.5 增量 SHA-256（END 复核零额外整包读）

段在块内乱序 → 不能按段增量。按**块**增量：块收齐落盘时 `sha_update(receiver->block, block_len)`（块序天然有序）；BEGIN resume（durable_off>0）时先从 staging 读回 [0,durable_off) 分块回填 hash；END 时 `sha_final` 与 package_sha256 比对。

### 3.6 时序参数（实验基线，禁止冻结——P3-4 标定）

| 参数 | 默认 | 落点 |
|---|---|---|
| `CONFIG_OTA_BLE_RX_RING_SIZE` | 4096 | `mcu_config.h`（派工书点名"受控 RX buffer"） |
| `CONFIG_OTA_BLE_PUMP_PERIOD_MS` | 20 | `HAL_Config.h` + 组件头默认值 |
| `CONFIG_OTA_BLE_LIVENESS_MS` | 500 | 同上（合同明示"初值非契约"） |
| `CONFIG_OTA_BLE_SESSION_TIMEOUT_MS` | 30000 | 同上（合同未定值，P3-4 标定） |

泵独立注册 `taskManager.Register(BT_OtaPump, CONFIG_OTA_BLE_PUMP_PERIOD_MS)`；`BT_Update` 保持 200ms（X-Trace 周期不变），其 X-Trace 与文本 drain 在会话活跃期由查询函数门控（活跃期关 X-Trace=合同 §5.1）。

## 4. 文件规划

新增（纯 C、host 可测、`#include` 全正斜杠）：

- `Libraries/OTA/ota_ble_ring.{h,c}` — SPSC 字节环（ISR 写/pump 读，满丢+计数）
- `Libraries/OTA/ota_ble_frame.{h,c}` — CRC16 + 帧编码器 + 增量 parser + demux 状态机
- `Libraries/OTA/ota_ble_session.{h,c}` — 会话状态机 + staging 接线（env 注入：now_ms/send/bcb/ota_disabled/overlay 仲裁+workspace 指针/info provider(P3-2)）
- `tests/ota/test_ota_ble.c` + runner — host 单元测试

修改：

- `USER/HAL/HAL_Bluetooth.cpp` — demux 集成、ISR hook 挂载、泵函数、X-Trace/文本门控
- `USER/App/Common/HAL/HAL.h` — `BT_OtaPump()` 声明（必要 HAL 声明）
- `USER/HAL/HAL.cpp` — 泵注册（调度接线）
- `USER/HAL/HAL_Config.h` — 时序参数宏
- `MDK-ARM_F435/Platform/mcu_config.h` — RX ring 尺寸（受控 RX buffer）
- `USER/HAL/HAL_OTA_Package.{h,cpp}` — overlay owner 枚举加 `OTA_OVERLAY_BLE` + `OTA_OverlayAcquireBle/ReleaseBle/GetWorkspace`（照 LiveMap 模式；同 owner 仲裁不可复制）
- `MDK-ARM_F435/proj.uvprojx` — 新源入 OTA 组；随后用 `D:\github\other\keil_translate_cmake\keil_to_cmake.py` 重新生成 `cmake-generated/CMakeLists.txt`（生成物不手改）

## 5. 测试计划（host，`tests/ota/` 模式）

- parser：逐字节/随机分片/粘包/噪声注入重同步/坏 magic/坏长度(len>132、cmd 长度不符)/坏 CRC/截断；均不得有 staging 副作用。
- seq：顺序、回绕（int16 语义）、重发幂等、gap→ERR_SEQ。
- session 状态机：GET_INFO 空闲可执行不建会话；未 BEGIN 先 DATA→ERR_STATE；session 不符→ERR_SESSION；ABORT 清理恢复文本；超时→0x84 ABORTED。
- staging 交互：块收齐落盘推进 durable_off+bitmap；off<durable 幂等不重写（R8-4）；同 offset 不同内容→0xFF 终止；END 缺段→ERR_STATE；END sha 复核失败→擦槽头页；resume 恢复 durable_off/bitmap（§4.5）。
- 隔离：活跃期文本回调零调用、X-Trace 门控、上行仅 ACK/事件帧。
- buffer：4KB 环高水位/溢出丢字节计数 fail-closed。
- 生产构型无测试符号（测试注入全在 env 结构，无 `#ifdef TEST` 留痕）。

## 6. 风险与边界（实现时复查）

1. BEGIN/会话结束的 ISR 过渡窗口（§2 已述，<1µs，重传恢复）。
2. LiveMap 在屏时 BEGIN→ERR_BUSY（§1.2 已述，固有约束）。
3. END 整包 SHA 复核为 resume 前缀回填 + 块增量两段合成，务必在测试向量里覆盖"断点在块边界/块中间"两种 resume。
4. `ota_staging_receive` 的段长语义：整段恒 128、包尾段按 total_len 定界——session 层须先于 staging 校验，保证错误码精确。
5. CMake 生成物必须经生成脚本再生（手改会被覆盖）；生成后 diff 应只含新源行。

## 7. 实现后修正记录（2026-09-02，会话层联调时发现）

### 7.1 【产品 bug】整包摘要读已清空的 RAM 块（§3.5 原方案不可实现）

§3.5 原方案"块收齐落盘时 `sha_update(receiver->block, block_len)`"在实现中被证明**不可实现**：

- `ota_staging.c` 的 `commit_current_block` 在 program+verify+清位图位之后、返回之前调用
  `discard_ram_block`（`memset(receiver->block, 0xFF, ...)`）。
- session 层在 `ota_staging_receive` 返回 `OTA_STAGING_BLOCK_COMMITTED` **之后**才读
  `receiver->block` 喂 `boot_sha256_update` / `boot_crc32_update`——读到的全是 0xFF，
  整包摘要必然错误 → END 摘要校验必失败 → BLE OTA 永远无法完成。
- 最初实现按 §3.5 写了独立的 `session_digest_commit_block`（BLOCK_COMMITTED 分支读块缓冲），
  host 测试的 END 整包 CRC 检查暴露该缺陷后整函数删除。

**修正决策：摘要跟随段，不跟随块**——`session_handle_data` 的
OK / BLOCK_COMMITTED / PACKAGE_COMPLETE 分支直接用 wire 上的段数据
（`data` / `data_len`）喂整包增量摘要；`DUPLICATE` 分支（同段同内容重发）幂等 ACK
但不重喂。块序天然有序 ⇒ 段序在流式到达时同样天然有序（seq 严格推进保证），
无需重组。resume 前缀仍从 flash 读回 `[0, durable_off)` 分块回填（flash 内容此时
已落盘，可安全读）。该修正使 §3.5 的"按块增量"退化为"按段增量 + flash 前缀回填"。

### 7.2 摘要时序与 staging 交互的其它已核实细节

- 返回值语义：`BLOCK_COMMITTED`/`PACKAGE_COMPLETE` 只表示该段**触发了块落盘**，
  并不改变"新写入段"的事实，与 OK 同喂摘要；DUPLICATE 才是"本段此前已接收"。
- staging 位图为块粒度、RAM segment_bitmap 不持久化 ⇒ 块中途 resume 必然整块重发，
  session 层摘要不能假设"段恰好只喂一次跨 resume"——重发段到达时走 DUPLICATE，
  摘要不重喂，恰好自洽。
- 尾段（`total_len` 非 128 倍数时）在 durable_off 未推进到尾块时会被 staging 以
  `offset - durable_off >= 4096` 拒绝（ERR_RANGE）——测试用例须先提交块 0 再发尾段。

### 7.3 host 测试结果（修正后）

- `tests/ota/test_ota_ble_session.py`：**105 checks, 0 failures**
  （`P3_1_BLE_SESSION=PASS`）。覆盖：GET_INFO 字段布局、BEGIN 拒绝矩阵 13 例、
  完整传输 5000B/40 段（块边界 ACK、ETSL 整包 CRC、staging 字节精确）、
  幂等（重复 BEGIN/重放 seq/durable 下重发不重写 flash）、seq 语义（断档/重放/回绕）、
  数据校验矩阵、ERR_DATA fail-closed+重传恢复、END 五路径（含 BEGIN 声明 sha 与
  真实流不符→ERR_SHA 擦槽头页）、ABORT+resume（不重擦已 durable 块、整包 CRC 自洽）、
  会话替换（overlay release/acquire 恰好各一次）、liveness 500ms 重发 ACK_DATA、
  30s 超时→0x84、坏 CRC 帧不重置超时、文本隔离（活跃期丢弃、teardown 恢复）。
- `tests/ota/test_ota_ble_frame.py`：39 checks 无回归（`P3_1_BLE_FRAME=PASS`）。
- `tests/ota/test_ota_sd.py`：P2_4 口径回归通过（core 29 + adapter 5 场景），
  证明本卡未破坏既有 staging/SD 行为。
- 测试夹具踩坑（记录防复发）：①变异 ETU 头字段后必须重算 header_crc@60，
  否则后续用例在 `ota_sd_inspect_header` 的 CRC 关卡即被拒（ERR_HDR）而非到达
  预期检查点；②ISR 环 4096B 容量下 DATA 帧 142B ⇒ 测试中每 4 帧泵一次，
  40 帧一次入环会溢出丢字节；③TX 捕获缓冲 256 帧才够 END 多路径用例。
