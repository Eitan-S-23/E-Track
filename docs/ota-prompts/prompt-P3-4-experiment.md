# P3-4 AT 提速实测 Spec

task_id: P3-4

## 任务类型

`EXPERIMENT`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-4` 行。本文件不得另行维护该状态。

## 目标

在 P3-1 真实 MCU transport 上先分解客户端/MCU 链路耗时，按证据优化必要热点，再以 115200 为基线逐档测量蓝牙模块/MCU UART 在可支持波特率直至 921600 的稳定性、有效吞吐、丢段/重传和升级总时长，为生产波特率及 BLE 活性参数提供可复核数据。

## 非目标

- 不先选 921600 再为结果辩护。
- 不改 BLE 字节协议、credit 窗口、128B DATA 或硬件引脚。
- 不把一次成功或短 toy 包结果当生产稳定性结论。
- 不在没有预先裁定门槛时从观测值反向发明合格线。
- 不把 `discoverServices()` 源码热点当作已证实的唯一瓶颈，不预设提速倍数。
- 不借提速删除后台保护或实现后台通知；Android 后台 OTA 与进度由 P3-8 承接，不重开 P3-3。

## 前置依赖

- `P3-1` parser/session/staging 必须可用并提供统计点。
- 可使用 PC 发送器或 P3-3 调试 transport，但测量端必须记录准确输入字节和 ACK。
- 吞吐、错误率、稳定性和统计口径见已冻结的 `OTA-XC-BLE-TUNING` 与 `OTA-XC-RETRY-POLICY`。实验按共享合同测量，再报告同时满足全部门槛的单一参数组合；产品门槛不从测量结果反向生成。
- 先确认开发自测路线、采集范围和设备操作授权；P3-3 的旧烧录、安装、传输或恢复额度不能沿用。调用 Flutter 发送器时须使用已提交版本，受影响 App 构建按其 AGENTS 走 Actions。

## 权威合同

- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-BLE-PERFORMANCE`
- `OTA-XC-BLE-TUNING`
- `OTA-XC-RETRY-POLICY`
- `OTA-XC-TEST-VECTORS`
- `docs/ota-binary-contracts.md` §5.5

## 现有组件和代码入口

- `USER/HAL/HAL_Bluetooth.cpp::BT_Init/BT_Update`：UART baud 和调度。
- 蓝牙模块 AT 命令入口及现有 115200 配置。
- P3-1 的 transport 统计、ACK 和 staging 进度。
- `tests/ota-vectors/` toy full，以及一份与正式体量相当的已校验 `.etu` fixture。
- `app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart::writeOtaCharacteristicByAddress/requestOtaMtu` 与 `ota_service.dart::writeChunk`：核对逐分片发现、协商 MTU、GATT 写入和连接代次。
- 任何 fixture 的真实传输/END 前先核对合法长度和设备应用行为；golden toy 不自动具备刷写启动资格，不以无意义填充凑参考包体量。

## 输入输出与调用方向

- 输入：候选波特率、固定测试包、统一发送器版本、固定 timeout/retry 参数集合、注错配置。
- 输出：CSV/JSON 数据表和 Markdown 结论，逐轮记录 baud、package hash/size、开始结束时间、有效 B/s、重传/ACK/CRC/seq/session 计数、断连、最终 staging hash 和设备状态。
- 每个候选档必须使用相同包、发送器、线端协议和测量边界；任何变量变化单独成组。
- 增加发现次数/耗时、协商 MTU/写净荷、写入模式、写等待、ACK 等待和 durable 推进证据；下载、BLE、设备应用及重连分别报告，不混淆时钟域或把重叠阶段求和。具体统计语义引用 `OTA-XC-BLE-PERFORMANCE`。
- 客户端优化先在固定 baud/包/参数下做前后对照，再固定优化后发送器进入 AT 逐档组；不得将源码优化与 baud 变化混为同一因果结论。

## 状态机与生命周期所有者

- 实验 harness 负责配置、计时和采集，不拥有产品状态。
- MCU/Flutter transport 继续按各自合同运行；实验不得用直接写 Flash 替代真实 staging 路径。
- 每轮前恢复已知空闲状态，AT 改速后双方读回/握手确认，再开始传输。
- 每轮结束以完整摘要和 durable completion 判定，不以“串口没有报错”判定。
- 连接内特征复用由原 BLE 所有者负责，严格绑定设备/连接代次/UUID；断连或服务变化即失效，旧代次迟到结果不能重建新连接缓存。不能为速度破坏帧写锁、取消或身份复核。

## 错误、超时、重试、取消、恢复与幂等

- 500ms 是基线变量，不是门槛；每组参数必须完整记录。
- AT 命令失败、双方 baud 不一致、日志丢失或统计复位失败记为 harness/环境问题，不得计入产品成功率。
- 传输失败后按合同 ABORT/重置 session，下一轮不得复用污染的 seq/bitmap。
- 同一配置的重复轮次必须可独立重放；原始日志不可被后处理覆盖。

## 允许修改范围

- P3-1/P3-3 中已有的可配置 baud/timeout/统计接口，只做最小实验接线。
- 对实测支持的客户端热点，可最小修改 `app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart`、`lib/services/ota_service.dart`、`lib/ota/ota_ble_transport.dart` 及对应 `test/ota/` 回归；先记录调用链、证据和共享依赖，不扩展为无关重构。
- `tests/ota/` 或项目内专用实验目录中的 PC sender、解析脚本和 fixture 索引。
- `docs/ota-exec-notes/P3-4-*.md` 及项目内证据目录。

## 禁止修改与生产红线

- 禁止启用硬件流控或改 PCB 假设。
- 禁止放宽 CRC、seq、readback、摘要或 durable 判据换取更高吞吐。
- 禁止把测试专用 AT 命令、固定包、统计后门留在生产构型。
- 禁止只保留汇总表而删除决定性原始日志。
- 禁止用 P3-4 测量结果反向放宽或改写 `OTA-XC-BLE-TUNING` 中的生产门槛和统计口径。

## 必须新增或调整的测试

- harness 自检：计时、计数复位、日志缺行、错误返回和最终摘要变异能被检出。
- 每个候选 baud 至少执行预先固定数量的完整包轮次，另做可重复的丢段/乱序/重复注错。
- 对选定候选再做长时间连续传输和冷启动/重连复测。
- 恢复生产构型后静态检查测试标记零命中，并重跑 P3-1 host 回归。
- 涉及 GATT 复用时覆盖有效连接复用、服务变化/断连失效、设备切换、迟到发现/写入与取消代次；证明不再逐分片重复发现，也没有跨连接使用旧特征。
- 计时/计数负例必须能发现日志缺失、不同参数混组、错误摘要和时钟域混用。治理或宿主测试通过不能代替真实吞吐数据。

## 完成判据

- 数据表覆盖 115200 基线及所有硬件实际支持的逐档候选直至 921600，不能支持的档位有明确 AT/握手证据。
- 每轮绑定包 SHA、固件/发送器 commit、参数和原始日志 SHA。
- 按预先裁定门槛给出唯一推荐生产 baud/timeout/retry 参数；若无档位达标则明确失败，不选“最好但不合格”的值。
- 推荐值经独立复跑得到一致结论，审批后将选定生产 baud/timeout/retry 回填共享契约文档；参数选择不等于修改原性能门槛。
- 提交完整耗时分解及优化前后对照；若热点假设未被证实，保留否定结果，不强行改代码或承诺加速。
- 使用未来受验版本的真实 Actions 和设备证据；按执行合同冻结实现/runner、前检及最小复验，不修改旧冻结包或把开发自测记为独立 PASS。

## 停止条件

- 共享门槛发生未重新冻结的变更，或没有单一候选参数组合同时满足全部门槛时，完成有效采集后停止，不宣布生产值。
- AT 命令可能不可逆改变模块且无恢复路径时停止并请求硬件责任人确认。
- 测量日志无法证明走真实 BLE/staging/readback 链时停止。
- 发现 P3-1 功能错误时先回到实现卡修复，污染数据全部作废。

## 后续证据

保存 AT 请求/应答、每轮统计、失败分类、发送端和 MCU 日志、参数表、最终 staging 摘要、真机/模块标识、生产构型恢复证明和独立复跑报告。

## Luna 可自行决定

PC sender 语言、数据表工具、串口采集实现、绘图方式和实验批次组织；不得自行决定产品门槛或删除不利结果。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
