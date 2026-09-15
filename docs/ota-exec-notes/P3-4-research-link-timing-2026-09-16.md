# P3-4 调用链与链路测量接线研究

会话: Claude(P3-4 实现 agent) ｜ 日期: 2026-09-16 ｜ 基线: main `9f67314700f2c796c66f56533b6db6166706353c`

本文档是 `PLAN-OTA-EXEC.md` P3-4 卡的编码前置 research（看板 §0 规则 4）。
范围：BLE OTA 升级链路的调用链分解、分阶段测量方案、测量接线设计、共享依赖、
验证入口与设备实验操作单草案。全部行号基于上述基线提交。

本批只做**测量接线与开发自测**；设备实测、AT 改速、烧录、安装均 NOT_RUN，
等待用户对操作单的明确授权（见 §8）。不预设任何提速倍数或根因结论。

## 1. 权威依据

- 派工书: `docs/ota-prompts/prompt-P3-4-experiment.md`
- 统计/门槛语义: `docs/ota-cross-system-contracts.md` 的
  `OTA-XC-BLE-PERFORMANCE`（分阶段测量）、`OTA-XC-BLE-TUNING`（门槛与样本
  定义，冻结不可反向修改）、`OTA-XC-RETRY-POLICY`（timeout 公式）
- 帧协议: `docs/ota-binary-contracts.md` §5（128B 段/4KB 块/credit 窗口/ACK 语义）
- 需求背景: `docs/ota-exec-notes/P3-4-P3-8-requirements-2026-09-15.md`（OTA-DEC-014）
- 前期观察: `docs/ota-exec-notes/P3-3-ble-speed-and-background-research-2026-09-15.md`
  （实测基线约 1.6-2.4 KB/s；本文的"待测热点"清单源于此，不是根因结论）

## 2. 完整调用链（Flutter 发送端）

### 2.1 升级编排（`lib/services/ota_service.dart`）

```
startOtaUpgrade (行 791)
 ├─ 身份/资产校验（本地包 SHA）
 ├─ findExactOtaCharacteristicsByAddress(address)            ← 发现 #1（行 863）
 ├─ _bindTransport (行 1773-1819)
 │   ├─ requestOtaMtu(address, 247)                          ← MTU 协商（行 1796-1813）
 │   ├─ subscribeOtaNotifyByAddress(...)                     ← 订阅 FFF1（行 1690-1790）
 │   ├─ _ChannelAdapter(ble, address, serviceId, writeCharId,
 │   │    chunkSize=MTU-3, notifyStream, writeWithResponse)
 │   └─ OtaBleTransport(channel)                             ← 传输实例（行 1773）
 ├─ transport.getDeviceInfo()                                ← 重连身份复核（行 891）
 ├─ transport.transfer(package, sha, etuHeader,
 │    windowSegments: recheck.maxWindowSegments, ...)        ← 行 906
 └─ END OK → dispose → _waitForTargetIdentity               ← 重启后复核
      └─ 循环 _probeTargetIdentity → _bindProbeTransport
           （独立发现+MTU+订阅+GET_INFO，按连接代次失效）
```

后台恢复 `resumeFromBackground`（行 1305）三级复核（链路代次/重新发现/INFO 身份）
后 `transport.resumeFromBackground()` 恢复发送；该路径会再次调用
`findExactOtaCharacteristicsByAddress`（行 1397）——其发现耗时也计入发现成本。

### 2.2 传输主循环（`lib/ota/ota_ble_transport.dart` `transfer` 行 273-552）

```
BEGIN 轮次（幂等续传；durable 倒退 fail closed，行 327-333）
 └─ 块循环（行 347）: blockStart = durableOff 按块对齐
     └─ 发窗循环（行 356）
         ├─ trackSend(seq, seg)（行 390）→ await _sendSegment（行 391）
         │   └─ _ChannelAdapter.writeChunk
         │       └─ ble.writeOtaCharacteristicByAddress   ← 每分片入口
         ├─ 窗口约束: inFlightCount >= effectiveWindow 停（行 386）
         ├─ waitForChange(ackTimeout)（行 398）
         │   超时 → 重发在途未确认段（复用原 seq，行 405-419）
         │         sendCountOf(seg) > retries → resume/中止
         └─ 块尾: durable 同步 + 锁存错误消费（行 436-462）
 END 轮次（行 471-540）: END OK 校验 durable==total + 尾块位图合法
```

### 2.3 ACK 视图（`_TransferAckView` 行 1369-1574）

`onAck` 校验链（任一步失败不覆盖权威进度）：

| 分支 | 行号 | 语义 |
|---|---|---|
| payload 解析失败 | 1420-1427 | 畸形 ACK |
| 非 ACK_DATA（异步 ABORT） | 1428-1434 | 错误锁存 |
| seq 不在途 | 1435-1440 | 重复/迟到/未知 ACK，整帧忽略 |
| status != OK | 1441-1446 | 错误锁存（首错保留） |
| durable 越界/倒退 | 1447-1452 | 畸形 |
| 跨窗伪跳跃 | 1453-1462 | 畸形 |
| bitmap 非法 | 1463-1467 | 畸形 |
| 写入确认判定失败 | 1468-1480 | ERR_STATE（无推进幂等 ACK） |
| **确认点**（行 1481） | durableOff 更新 | **ACK 样本终点** |

确认集合构成（行 1481-1491）：
- ACK 自身段（`inFlight.remove(f.seq)` 回收的 seg）；
- `advanced`（durable 跨块前移）时：旧块全部在途段随提交一并确认（inFlight.clear）；
- 未 advanced 时：新 bitmap 置位的在途段（`_harvestBitmap` 回收）。

段号是块内 0-31，**唯一段标识 = 字节偏移 `blockStart + seg*128`**
（`blockStart` 即确认时刻前的 `durableOff`，MCU 只按整块提交，传输期
durableOff 恒为当前块起点）。参考包 1,048,576B = 8192 唯一段。

### 2.4 移动端写入热点（`lib/services/bluetooth_service.dart`）

`writeOtaCharacteristicByAddress`（行 1342-1381）移动端分支**每次写入**：

```
device.discoverServices()          ← 行 1363，逐分片重复发现（2026-09-15 待测热点）
→ 循环找 FFF0/FFF2 → ch.write(data, withoutResponse: !writeWithResponse)
```

Windows 分支走 `_adapter.writeCharacteristic`（UUID 直写，无重复发现）。
严格发现入口 `findExactOtaCharacteristicsByAddress`（行 1609-1666）只做一次
发现并精确匹配 FFF0/FFF2/FFF1，无降级。`requestOtaMtu`（行 1796-1813）移动端
`requestMtu(247)` 返回协商值-3，Windows 恒 20。

### 2.5 MCU 侧（接收端，仅梳理不改）

`USER/HAL/HAL_Bluetooth.cpp`: `BT_SERIAL.begin(115200)`（行 332）；
`ble_isr_hook` ISR 搬运 HW 环 → `BT_OtaPump` → `ota_ble_session_pump`；
`ble_env_send` 逐字节回 ACK。`Libraries/OTA/ota_ble_session.c` 会话状态机，
`ota_staging.c` durable staging。既有 RTT 打点：`BLEACT:` 行含 apply/stage
耗时。**MCU 固件本批零改动**；UART vs staging 开销的分解先依赖既有 RTT 打点
+ 主机侧 ACK 延迟样本（§4.4），插桩不足再按操作单申请固件批次。

## 3. 分阶段测量方案（OTA-XC-BLE-PERFORMANCE 对齐）

### 3.1 阶段与时钟域

| 阶段 | 起点 | 终点 | 时钟域 |
|---|---|---|---|
| 下载（latest→本地包） | 已有下载链路 | 本地包 SHA 校验通过 | App 单调时钟（既有） |
| 绑定（发现+MTU+订阅） | findExact 调用 | 订阅流就绪 | App（OtaLinkStats） |
| GET_INFO 复核 | getDeviceInfo 写开始 | INFO 到达 | App |
| BLE 传输 | **BEGIN 首帧写开始** | **END ACK 完整到达** | App |
| 重启/重连/GET_INFO | probe 开始 | 目标身份确认 | App（probe 独立 stats） |

- BLE 传输时长的测量边界：transfer() 内首个 BEGIN 帧写调用开始（含写队列
  排队与帧分片）到 `_dispatchFrame` 分发 END ACK 的时刻。包含正常 ACK 等待
  与重传，符合 TUNING 冻结口径。
- **单一时钟域**：每个 OtaLinkStats 实例持有自己的 `Stopwatch`（单调），
  同一绑定内所有时间戳同源；跨域（主机 vs MCU RTT）不做减法，MCU 侧数据
  独立成表按事件序列对齐。
- 重叠阶段不求和：绑定/GET_INFO/传输/probe 各自独立记录，分析侧只做
  分组统计，不做跨阶段相加。

### 3.2 观测点清单（接线后可采集）

| 观测项 | 来源 | 粒度 |
|---|---|---|
| 服务发现次数/耗时 | writeOtaCharacteristicByAddress 内 discoverServices()、findExact/subscribe 内发现 | 每次调用 |
| MTU 协商 | requestOtaMtu 请求值/返回值/chunkSize | 每绑定 |
| 写入模式 | writeWithResponse | 每绑定 |
| GATT 写耗时 | writeOtaCharacteristicByAddress 整方法（channel 层） | 每帧 |
| 平台写耗时 | 移动端 ch.write / Windows adapter 写 | 每帧 |
| ACK 延迟样本 | 首次发送结束 → 首个有效确认 | 每唯一段 |
| ACK 分类计数 | ok/duplicate/error/malformed/no-progress | 累计 |
| durable 推进 | onAck advanced 事件 (us, off) | 每块提交 |
| 段发送计数 | 首发/重发、唯一段集合 | 累计 |
| 传输终态 | outcome + code | 每 transfer |
| MCU 侧 | 既有 BLEACT: RTT 行（stage/apply 耗时） | RTT 采集 |

### 3.3 ACK 延迟样本语义（冻结定义的工程映射）

`OTA-XC-BLE-TUNING` 冻结定义逐条映射到接线：

| 冻结条款 | 工程实现 |
|---|---|
| "从该段首次完整发送结束" | `_sendSegment` await 返回且该偏移首次发送（sendCount==1）时记 firstSendEnd |
| "到首个由 durable_off/bitmap 明确确认该段的有效 ACK 到达" | onAck 行 1481 确认点：确认集合 = ACK 自身段 ∪ advanced 回收的旧块在途段 ∪ bitmap 置位段 |
| "多个段可共享同一 ACK" | 确认集合逐段生成样本（终点同、起点各异） |
| "重复、无推进或非法 ACK 不计样本" | seq 不在途（duplicate）、写入确认判定失败（no-progress）、四类畸形/错误路径均在确认点之前 return，不产生样本 |
| "重传不创建新样本" | firstSendEnd 仅记录首次；重发段偏移已在唯一集合中，不再更新 |
| "同参数组合全部 clean run 样本合并" | 原始样本逐条落日志，合并与 P99 计算在分析侧做 |
| P99 nearest-rank | 升序排序取第 ceil(0.99*N) 个，不插值不删样本 |

重传率：`重传 DATA 帧数 = Σ每偏移发送次数 − 唯一偏移数`；
`唯一 DATA 段数 = ceil(total/128)`。clean run（无注错）门槛 ≤1%。

### 3.4 观测者效应声明（前后对照的口径前提）

- 采样时间戳全部取自平台调用前后（await 边界），日志输出发生在时间戳之后，
  因此**单样本值不受输出开销污染**；
- 每帧日志输出会在帧与帧之间引入微小额外耗时，**总传输时长有轻度膨胀**；
  所有对照组合（优化前后、各 baud 档）必须使用**同一发送器版本（同一插桩
  commit）**，口径一致，差异才有意义——这也是 TUNING "绑定发送器/固件提交"
  条款的要求；
- 逐帧日志量级：1MiB 参考包 ≈ 8192 段 ≈ 每轮约 2.5 万行采样日志，logcat
  可承受；与既有 `OTA sent n/total` 每段打印同量级。

## 4. 测量接线设计

### 4.1 架构

新文件 `lib/ota/ota_link_stats.dart`：`OtaLinkStats` 纯观测收集器。

原则（对应派工书红线）：
1. **只读观测**：不改任何控制流、超时、判据；不新增测试专用命令。
2. **单一时钟**：实例级 Stopwatch；JSON 导出声明 `clock` 字段。
3. **fail-closed 完整性**：`outcome=ok` 的传输若存在无样本的唯一段，
   导出 `ackSamples: "partial:missing=N"` 而非静默缺行；摘要与采样行
   双通道交叉可校验。
4. **无生产后门**：无 AT 命令、无固定包、无统计旁路；插桩与既有
   `otaMonoLog` 同类（只加日志与内存计数），生产构型可用同一代码。

### 4.2 日志格式（logcat 采集契约）

```
OTA_LINK_SAMPLE label=<upgrade|probe|query> kind=<gatt_write|discover|platform_write|ack_latency> us=<n> [bytes=<n>] [off=<n>]
OTA_LINK_STATS {json 摘要}
```

- `OTA_LINK_SAMPLE` 逐事件流式输出（原始样本，跨轮合并的原料）；
- `OTA_LINK_STATS` 每绑定结束时输出一次聚合摘要（计数、分位数、终态、
  完整性声明），用于快速校验与"摘要变异检出"负例测试；
- 解析脚本（实验 harness 侧）后续批次交付，本批先冻结行格式。

### 4.3 接线点（全部为最小参数传递 + 时间戳记录）

| 文件 | 位置 | 接线 |
|---|---|---|
| ota_link_stats.dart | 新文件 | 收集器实现 |
| ota_ble_transport.dart | 构造（行 52） | 可选 `stats` 参数 |
| ota_ble_transport.dart | transfer 头 | 传输起点（首个 BEGIN 写前，一次性） |
| ota_ble_transport.dart | 发窗/重发循环（行 391/417） | 段发送记录（偏移+首次发送结束时刻） |
| ota_ble_transport.dart | _TransferAckView（行 1369） | 可选 stats + blockStart 语义 |
| ota_ble_transport.dart | onAck 确认点（行 1481 前） | 确认集合快照→样本；ACK 分类计数；durable 推进 |
| ota_ble_transport.dart | _dispatchFrame（行 684） | END ACK 到达时刻（END OK 语义的终点） |
| ota_ble_transport.dart | getDeviceInfo | 往返计时 |
| ota_service.dart | startOtaUpgrade | 创建 stats(label=upgrade)；绑定/复核阶段计时；终态摘要输出 |
| ota_service.dart | _bindProbeTransport | 独立 stats(label=probe) |
| ota_service.dart | readDeviceInfo | 独立 stats(label=query) |
| bluetooth_service.dart | writeOtaCharacteristicByAddress | 方法级 GATT 写计时 + 移动端分支内 discover/ch.write 拆分计时 |
| bluetooth_service.dart | requestOtaMtu / subscribe / findExact / discoverServicesByAddress | 可选 stats 透传 + 各自耗时 |

签名变更方式：相关方法追加**可选命名参数** `OtaLinkStats? stats`（默认
null 时零行为差异）。受影响测试 fake：`ota_service_session_test.dart`
（行 472-501）与 `ota_service_upgrade_test.dart`（行 2634-2675）的四个
override 需同步补参数；`bluetooth_adapter_notify_test.dart` 用真实
BluetoothService + fake adapter，不受影响。

### 4.4 MCU 侧开销分解路线（不改固件的前置）

主机侧 ACK 延迟样本 ≈ UART 传输(128B+协议头) + MCU 解析 + staging 写 +
ACK 组包 + UART 回传 + BLE 通知 + 主机调度。分解依据：
- 既有 `BLEACT:` RTT 行已有 apply/stage 耗时 → staging 侧直接观测；
- 115200 下 128B 段 + ACK 的 UART 线时间可理论计算并与样本分布对照；
- 若分解粒度不足（如需逐块 staging commit 计时），在操作单中申请**独立
  固件插桩批次**（RTT 计时行，生产构型恢复证明按派工书要求），本批不做。

## 5. 共享依赖与串行协调

- `bluetooth_service.dart`、`ota_service.dart`、`ota_ble_transport.dart`
  是 P3-3 已验收资产，P3-8（后台 OTA/通知）也将触碰同一批文件——
  按需求文档约定**串行协调**，本批改动保持最小插桩形态，为 P3-8 留出
  改动空间；
- 测试基建复用：`_UpgradeFakeBle`（fake MCU 真值语义）、`_McuSim`
  （transport 级 fake channel）、`_FakeNotifyAdapter`（adapter 层）——
  新增测试沿用同模式，不新建平行 fake 体系；
- 帧协议/窗口/重试逻辑零改动：插桩不触碰 trackSend/onAck 的控制流，
  仅在既有状态更新前后读取；
- 本批不实现 GATT 连接内复用（候选优化 §7）；优化实现等基线实测证据，
  复用失效语义（设备/连接代次/UUID 绑定、断连与服务变化失效）在优化批次
  按派工书测试要求覆盖。

## 6. fixture 盘点（截至基线）

| 资产 | 体量 | 状态 |
|---|---|---|
| tests/ota-vectors/toy-full.etu | 748B | golden，**无上板资格**（派工书 §现有组件） |
| tests/ota-vectors/p2-3-*.etu | 213B 等 | 离线向量 |
| .cache/p2-6-hardware-20260819/P2-6-FULL-v2.8.1.etu | 282,328B | 硬件轮资产，实验复用需授权核定 |
| P3-3 离线资产（3.2.1/3.2.2 真包） | ~284,608B | 见 P3-3-offline-assets-2026-09-13.md |
| **1MiB 参考包** | 1,048,576B | **不存在**。TUNING 冻结 referencePackageBytes；合法来源只能是对应真机版本的已校验 .etu（身份+SHA 完整），不以无意义填充凑数 |

实验前需在操作单中核定参考包来源与上板资格（真机版本对齐、无意义填充
禁令）；golden toy 不自动具备刷写启动资格。

## 7. 候选优化清单（全部待实测证据，本批不实施）

1. **逐分片 discoverServices()**（bluetooth_service.dart 行 1363）：连接内
   复用已发现的 FFF0/FFF2，严格绑定设备地址/连接代次/精确 UUID，断连、
   服务变化、设备切换即失效。实施前提：基线数据显示发现耗时占传输耗时
   显著比例（阈值在实验分析时按数据裁定，不预设）。
2. **连接参数优先级**（flutter_blue_plus `requestConnectionPriority`，
   全仓零调用）：作为独立输入组进入实验矩阵，需设备授权后实测；不承诺
   倍数。
3. AT 逐档 baud（115200→921600）：纯实验阶段，前置为客户端热点分解完成
   （派工书：先固定 baud 做客户端前后对照，再固定发送器进 AT 档）。
4. MCU UART RX 环/baud 刷新（`HAL_Bluetooth.cpp`）：115200 下 128B 段线
   时间 ~11ms；若样本显示 ACK 延迟贴近 UART 线时间则 MCU 侧是主导因素，
   AT 档实验验证；固件改动属授权批次。

## 8. 设备实验操作单草案（待用户授权，未执行）

**范围**：115200 基线测量 + 客户端热点分解（不含 AT 改速；AT 档实验待
基线数据后再单独立单）。

| 项 | 内容 |
|---|---|
| 设备/固件 | E-Track 目标板（AT32F435），固件 = main 当前 GCC 产物或指版本；烧录前核对身份 |
| 发送器 | debug APK（dev/flutter/apk/** 分支 CI 产出），commit 与插桩版本绑定 |
| 包身份 | 待核定：优先复用已校验真包资产；1MiB 参考包来源待批（§6） |
| 操作 | 安装 APK（需授权）、连接、发起 OTA 升级 N 轮（N 待定，建议 ≥5 clean run）|
| 采集 | adb logcat（OTA_LINK_* + OTA_MONO 行）+ J-Link RTT（BLEACT: 行）；每轮原始日志独立保存不覆盖 |
| 测量边界 | 每轮记录：包 SHA/长度、发送器 commit、MTU、写模式、发现计数、分阶段耗时、ACK 样本全集、durable 序列 |
| 风险 | 烧录 halt 打断 SDIO 致 SD 挂死（已知，拔插恢复）；升级失败设备停留旧版本（可重试/回退） |
| 恢复 | 升级失败→按合同 ABORT/重连恢复；设备异常→断电重启；无不可逆操作（不改 AT 参数、不烧非授权固件） |
| 配额 | 安装/传输轮次上限、烧录次数上限待用户指定 |

**本批不申请**：AT 改速、生产参数回填、任何主线合并/发布。

## 9. 验证入口（本批）

- 分支：项目内独占 worktree，`dev/flutter/**`（预授权范围）；
- CI：`flutter-dev-checks.yml` 双宿主（Ubuntu analyze+test / Windows test）；
- 新增测试（`test/ota/`）：
  1. OtaLinkStats 单元：nearest-rank P99 正确性（含 ceil 语义）、样本
     记录规则、重复/无推进/非法不采样、JSON 导出完整性字段；
  2. transport 接线（_McuSim 模式）：clean run 每唯一段恰一样本、
     `outcome=ok` 且样本完整、丢 ACK 重发不增样本、重传计数正确、
     durable 事件序列单调；
  3. service 接线（_UpgradeFakeBle 模式）：绑定阶段字段（发现/MTU/订阅/
     写模式）被填充、probe/query 独立、摘要行输出；
  4. 负例（变异检出）：摘要计数被人为篡改/样本缺失时完整性声明变
     `partial`——验证"摘要变异能被检出"；
  5. 既有 11 个测试文件全部保持绿（签名变更的 fake 同步）。
- 不做：本地 Flutter 构建（禁令）、真机、APK 产物外的任何发布动作。

## 10. 未决项

1. 1MiB 参考包的合法来源与上板资格（§6/§8）——设备实验授权时一并裁定；
2. MCU 侧既有 RTT 打点是否足够分解 UART vs staging（§4.4）——基线数据
   出来后评估；
3. 连接优先级实验是否纳入首轮矩阵（§7.2）——授权时裁定；
4. 开发自测的分支名与轮次（§9）——实施时按预授权细则执行。

## 11. 本文档之外

本批实施记录（接线 diff、测试结果、CI run）在后续 P3-4-*.md 文档与看板
回写中留痕；本文只固化研究结论，不虚构任何未执行的测量结果。
