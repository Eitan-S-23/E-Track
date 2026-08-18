# P3-1 MCU BLE 帧层实施 Spec

task_id: P3-1

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` 的“P2-6 后 OTA Spec readiness 矩阵”中 `P3-1` 行。本文件不得另行维护该状态。

## 目标

在 MCU App 中实现冻结 BLE 二进制协议的 UART demux、增量帧解析、OTA session、ACK 上行和 staging 写入接线；OTA 活跃期必须隔离现有文本协议、周期 `X-Trace` 和调试透传。实现必须复用既有 durable staging 组件，不得新造第二套持久化进度。

## 非目标

- 不修改 BLE 帧、命令、payload、状态码或 `.etu` 字节合同。
- 不实现 Flutter 页面、Cloudflare API、正式资产发布或 P3-4 的生产参数裁定。
- 不改变 SD OTA、candidate/apply/backup/BCB 的既有校验状态机。
- 不启用 UART 硬件流控。

## 前置依赖

- `P2-1` staging 与 `P2-2` package path 已收口。
- `docs/ota-binary-contracts.md` §4.2、§4.5、§5 为只读权威来源。
- BLE 性能门槛和统计口径见 `OTA-XC-BLE-TUNING` 与 `OTA-XC-RETRY-POLICY`；生产 baud、timeout 和 retry 组合由 `P3-4` 使用同一候选参数组合形成证据，当前实现只保留有界可配置的实验基线。

## 权威合同

- `OTA-XC-SCOPE`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-BLE-TUNING`
- `OTA-XC-RETRY-POLICY`
- `OTA-XC-CANCEL-RECOVERY`
- `OTA-XC-SECURITY`
- `docs/ota-binary-contracts.md` §5（字节协议唯一来源）

## 现有组件和代码入口

- `USER/HAL/HAL_Bluetooth.cpp`：115200 初始化、200ms `BT_Update()` 调度、当前文本回显和透传入口。
- `Libraries/Bluetooth/Bluetooth.{h,cpp}`：现有 TinyBTPlus 文本解析器。
- `USER/HAL/HAL.cpp`：`BT_Update` 的 200ms 注册点；需要评估 OTA 接收调度是否必须提高频率或改为独立泵送。
- `MDK-ARM_F435/Platform/mcu_config.h`：当前全局 RX buffer 为 512B。
- `Libraries/OTA/ota_staging.{h,c}`：唯一 staging receiver、4KB 活跃块、durable_off 和 bitmap 实现。
- `USER/HAL/HAL_OTA_Staging.*`、`USER/App/Utils/OtaUpdate/`：QSPI IO 和后续 package/apply 入口。

## 输入输出与调用方向

- 输入：蓝牙 UART 任意分片字节流、系统 tick、连接状态、staging IO。
- 输出：现有文本字节继续送 TinyBTPlus；完整 OTA 帧送独立 parser/session；上行只通过统一二进制 encoder 产生 INFO/ACK。
- MCU parser 必须支持帧跨任意 UART read 边界、多个帧同批到达、噪声后重新同步和有界丢弃。
- staging 写入只通过 `ota_staging_begin/receive/finalize` 或等价既有封装；ACK 的 durable/bitmap 直接来自该组件返回值。

## 状态机与生命周期所有者

- HAL UART demux 拥有“文本或二进制”顶层分流，不拥有 durable 事实。
- 新 OTA transport/session 组件拥有帧解析、seq/session 校验、命令分派和活性计时。
- `ota_staging` 拥有 durable_off、bitmap、重复段幂等和 QSPI readback 结果。
- BEGIN 成功后进入活跃期；END、ABORT、合同定义的会话超时或不可恢复错误退出活跃期并恢复文本通道。
- GET_INFO 不创建活跃 session；INFO 内容由 P3-2 provider 提供，P3-1 只负责协议封装和发送。

## 错误、超时、重试、取消、恢复与幂等

- 所有协议错误映射只引用二进制合同 §5.7，不得新增私有 wire status。
- CRC、长度、offset、seq、session 和状态错误必须在产生 staging 副作用前拒绝。
- `off < durable_off` 的 DATA 不重写 Flash，直接回当前 ACK。
- 同一活跃块内的重复段由 staging bitmap 幂等处理；不同内容占用已接收 offset 必须 fail closed。
- 断连后持久化恢复只按同 package 身份和二进制合同 §4.5 进行。
- 500ms 仅作为可配置实验初值；生产超时、重试次数和 session 过期值不得在本卡擅自冻结。
- ABORT 和超时必须停止接收、清理 RAM session、恢复文本通道，同时保持持久化日志符合恢复合同。

## 允许修改范围

- `USER/HAL/HAL_Bluetooth.*`、必要的 HAL 声明和调度接线。
- `Libraries/Bluetooth/`，或在 `Libraries/OTA/` 新增职责单一的 BLE transport/parser 文件。
- `MDK-ARM_F435/Platform/mcu_config.h` 及 GCC/AC5 工程源文件清单，仅用于受控 RX buffer/新源接入。
- `tests/ota/` 下的 MCU host 单元测试、stubs 和必要的构建治理测试。

## 禁止修改与生产红线

- 禁止修改 `PLAN-OTA.md`、`docs/ota-binary-contracts.md` 或既有冻结提示词。
- 禁止用 `struct memcpy` 解析 wire 数据，禁止无界动态分配，禁止让 parser 写越界。
- 禁止启用 RTS/CTS，禁止把 UART 丢字用增大重试次数掩盖。
- 禁止让 OTA 活跃期继续输出文本、`X-Trace` 或 debug passthrough。
- 禁止复制或替代 `ota_staging` durable 状态，禁止绕过 package/apply/BCB 校验。
- 禁止把测试注入、统计标记或固定 PASS 逻辑留在生产构型。

## 必须新增或调整的测试

- parser：逐字节、随机分片、粘包、前导噪声、坏 magic、坏长度、坏 CRC、截断和超长帧。
- seq：正常递增、重复、乱序和 16 位回绕。
- session/state：GET_INFO、BEGIN 成功/失败、未 BEGIN DATA、错误 session、END、ABORT、超时恢复文本。
- staging：32 段乱序、缺段 ACK、重复段、已 durable 段、包尾短段、读回失败和断连恢复。
- 隔离：活跃期文本 parser/回显/debug 零调用，退出后恢复。
- buffer：高水位、溢出 fail closed、≥4KB 容量事实和生产构型无测试符号。
- 既有 OTA host 测试不得回退；新公共头影响广泛时执行 App+Boot GCC 构建，AC5 只作辅助兼容检查。

## 完成判据

- PC 模拟发送器可驱动 full vector 从 BEGIN 到 END，最终 staging 字节、durable_off 和摘要一致。
- 丢段、乱序、重复、CRC/seq/session 注错均得到合同规定的恢复或终止行为。
- 文本协议在非 OTA 时保持兼容，OTA 活跃期无文本串扰。
- MCU RAM/栈/buffer 使用有静态与运行期证据，无无界增长。
- 所有新增测试和适用构建通过，warning/error 逐项报告。

## 停止条件

- 发现冻结二进制合同无法由现有 staging API实现，先记录精确冲突，不得改合同迁就实现。
- 共享候选合同尚未独立复核，或 `P3-4` 尚未按固定门槛得出唯一候选参数组合时，不得声称生产超时、重试或波特率已经定案。
- ≥4KB RX 方案会破坏冻结 RAM 门槛且无合同内方案时停止并登记资源决策。
- 需要改 Boot、SD OTA 或 BCB 语义才能继续时停止。

## 后续证据

实现/验收会话需保存 host 测试明细、parser/状态机覆盖、buffer 高水位、生产构型符号扫描、GCC size/map、模拟丢包日志和最终 staging SHA-256。P3-4 再补真实波特率/吞吐证据。

## Luna 可自行决定

parser 的文件拆分、环形缓冲数据结构、静态队列布局、内部类/函数名、测试 fixture 组织和日志格式，只要满足有界内存、现有工程风格及全部合同。

## 阻断性决策

- `OTA-DEC-003`：BLE 性能门槛、统计口径与候选参数组合。
