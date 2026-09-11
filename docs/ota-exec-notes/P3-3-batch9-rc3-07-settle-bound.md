# P3-3 第九批 RC3-07：settle 宽限与中止边界

范围：`app/bluetooth_flutter_Trace`（Flutter OTA 应用层）。
本笔记只记录 RC3-07 的「超时后 settle 等待逃出 durable 预算」一项：源码边界、
新用例的鉴别力，以及仍需真机/原生观测的部分。MCU、冻结契约与历史验收包未改动。

## 1. 反例复盘（复核报告成立）

`ota_ble_transport.dart` 的分片写路径在超时处理器里独立等待 `2 * writeTimeout`：

- 初始等待受剩余 durable 预算封顶（`perChunkTimeout = _capByBudget(writeTimeout)`）；
- 超时后的 settle 等待不封顶。默认值下 `writeTimeout = 10s` ⇒ 额外 20s，
  终止发布时刻可达「预算 + 20s」＝ 50s，超出 30s 合同窗口（BUDGET-TUNING
  的无 durable 进展中止窗口）。`Future.timeout` 不取消底层 native 写，
  这点实现原本就承认，问题只在**等待时长逃出了预算**。

## 2. 源码闭合

`_writeFrameLocked` 的超时分支改为：

```dart
} on TimeoutException {
  final settleGrace = _capByBudget(writeTimeout * 2);
  if (settleGrace > Duration.zero) {
    try {
      await pendingWrite.timeout(settleGrace);
    } catch (_) {} // 迟到错误不覆盖本帧超时语义
  }
  throw OtaTransportException('BLE 单次写入超时（…s）', code: 'WRITE_TIMEOUT');
}
```

- **传输路径**：settle 宽限由剩余 durable 预算封顶 ⇒「本帧抛出 WRITE_TIMEOUT」
  的时刻 ≤ 预算截止（默认 30s），由构造保证，不靠口径解释。预算耗尽时宽限为 0。
- **不降低任何门槛**：`noProgressTimeout` 仍为 30s、`writeTimeout` 仍为 10s、
  宽限上限仍是 2×writeTimeout；封顶只会缩短等待，不会放宽判据。
- **代价已明写**：宽限为 0 时不再为迟到分片保留串行队列。此时废弃标记
  （`_poisonWriteChannel`）已拒绝全部**新的**业务帧与 ABORT（见
  `_writeFrameChecked` 入口与 `_writeFrameLocked` 排队复核），但**这一片
  超时的物理写本身仍是在途的**——`Future.timeout` 不取消底层 `writeChunk`，
  它可能在任意更晚的时刻落地，照样能在已同步的解析器上制造新的悬空半帧。
  所以解除隔离不能只看「收到匹配的 INFO 应答」：还要求该应答出自一个
  **发出时设备上零在途旧物理写**的探针（`_resyncProbeAuthoritative`，
  `ota_ble_transport.dart:1136-1138`），且探针 seq 与废弃世代都匹配
  （`_isResyncEvidence`，同文件 1074-1080）；不满足就继续 fail-closed，
  先等旧写结算（`_awaitDeviceWritesIdle`）再重新取证。悬空帧的收场仍是
  「投递字节逼 MCU 按自身 len 吃满 → CRC 失败 → 解析器自复位」
  （`ota_ble_frame.c` 失败分支 reset），由有界探针重试驱动
  （`maxResyncProbes = 20`、单次 800ms，总时限见 §4.4）。
- **取消路径**（transfer 退出后 `_noProgressClock` 已置空）：宽限仍取
  2×writeTimeout，该路径的终止上界是 `writeTimeout + 2×writeTimeout`，
  以单次写超时为唯一依据，不受 durable 预算约束（该路径本就不属于预算覆盖范围）。

## 3. 用例鉴别力（`test/ota/ota_ble_transport_test.dart`）

新增替身注入口：`hangAtDataChunk`（分片写永不返回）、`slowDataChunkAt` +
`slowDataChunkDelay` + `slowDataChunkFails`（迟到成功 / 迟到错误）、
`writeTimeline`（`start#n` / `done#n` / `error#n` 次序观测）。

| 用例 | 构造 | 判据 | 修复前 |
| --- | --- | --- | --- |
| 接近预算耗尽的写挂起 | 预算 1500ms、写超时 5s、MTU=23、片 1-3 各 300ms、片 4 卡死 | 墙钟 ∈ [1000ms, 3000ms) 且错误码 WRITE_TIMEOUT；随后业务帧被拒 | 片 4 超时后再等 10s ⇒ ~11.5s |
| 迟到成功 | 写超时 100ms、片 1 在 200ms 落地 | 仍抛 WRITE_TIMEOUT；抛出时刻 `pendingByteCount == 122`（宽限确实等到了迟到写，队列未提前放行） | 与修复后一致（防止回退成「立即上抛」） |
| 迟到错误 | 同上，片 1 在 200ms 抛 StateError | 调用方看到的是 WRITE_TIMEOUT；迟到错误被吞；`writeTimeline == [start#1, error#1]`；无字节落地 | 与修复后一致（防止迟到错误穿透） |
| 取消交错 | 预算 600ms、写超时 500ms、片 1 写 1.5s、50ms 时取消（ABORT 入队） | 墙钟 < 1000ms（宽限被预算截断为 100ms）；ABORT 一个字节都没写；迟到片 1 落地后仍是干净半帧前缀 | 宽限 1000ms ⇒ 终止发布推到 1.5s（迟到写落地处） |

原有「慢写 + 小 MTU」用例的收尾断言按新语义修正：预算 520ms 到期时宽限为 0，
抛出时刻片 7 可能尚未落地，故先断言半帧前缀（120B 或 140B），待迟到片落地后
再断言恰好 140B 且无后续帧字节混入——不变量（无完整 DATA 帧、无交错）不变。

## 4. 仍需真实 native 观测的部分（NOT_RUN，交正式计划）

注入时长用例只能证明**逻辑边界**，不能证明真实 GATT 写在 Android 蓝牙栈上的
时序。下面把正式计划的观测量、拓扑、时限与操作边界写成可直接执行的形式；
未执行前一律记 NOT_RUN，不得用「日志没有错误行」推定通过。

### 4.1 观测量口径（先纠正）

- **durable 进展只能取 `onDurableProgress`**（`ota_service.dart:877-883`，
  UI 文案「…（MCU 落盘确认）」）。它是传输层 `_noProgressClock` 复位的依据
  （`ota_ble_transport.dart:404`），30s 窗口从**它**起算。
- **禁止**用 `onSent` 的 `OTA sent <n>/<total>`（同文件 884-887，注释明写
  「GATT 已写字节只作为传输活性参考，不进 durable 进度」）当锚点：它只说明
  字节交给了 GATT 栈，与 MCU 是否落盘、预算何时复位无关，用它作起点量出的
  不是合同窗口，判据会失去鉴别力。
- 判据一律用**单调时钟的绝对时刻**（`microsecondsSinceEpoch`），起点与终点
  取自同一次会话的应用侧 logcat：起点 = 最后一次 `OTA_DURABLE`，
  终点 = 终止发布。
- **不放宽 30s**：`noProgressTimeout` 仍为 30s，判据就是 `< 30s`，
  不设 33s 之类余量。修复前的实测差值会达到 ~50s（预算 + 20s settle），
  两者在 30s 处已可分辨；加余量只会掩盖回归。

### 4.2 插桩（提交在 §7.3.2 授权内；观测执行另行授权）

插桩提交本身属既有 §7.3.2 范围（dev 分支 WIP + dev debug APK），只加三行观测
输出，不改语义：

```dart
// ota_service.dart, onDurableProgress 回调内（durableOff 变化时才打印）
debugPrint('OTA_DURABLE $durableOff/$total '
    '${DateTime.now().microsecondsSinceEpoch}');
// OtaTransportException 失败分支，abortBestEffort 之前
debugPrint('OTA_FAIL_AT ${e.code} ${DateTime.now().microsecondsSinceEpoch}');
// 同分支 _phase.value = OtaPhase.failed 之后
debugPrint('OTA_TERMINAL ${e.code} ${DateTime.now().microsecondsSinceEpoch}');
```

插桩只进 dev 分支与 dev APK，不进 release、不改协议、不改 MCU。

### 4.3 拓扑与判据（两次会话，各自独立取证）

**T1：应用侧预算闭合（判据 1-3）**

- 设备：一台 Android 真机（装本次 dev debug APK）＋ 一个可控 BLE 从机：接受
  连接与 ATT 写但**不回写响应**（第二台手机的 BLE Peripheral Simulator，或
  nRF52/nRF Connect 测试从机），使 `writeCharacteristic` 在 native 层悬挂。
  **不使用**需要改 MCU 固件的注入手段（属另一组件范围）。
- 命令（Windows，项目内落盘）：
  ```text
  adb -s <serial> logcat -c
  adb -s <serial> logcat -v threadtime -s flutter > .acceptance-<id>/logcat.txt
  ```
  真机驱动一次 OTA → 从机进入写黑洞 → 等待应用终止。
- 判据：
  1. 传输路径：`OTA_TERMINAL` − 最后一次 `OTA_DURABLE` **< 30s**。由构造保证：
     单片超时与 settle 宽限同由 `_capByBudget` 封顶
     （`ota_ble_transport.dart:1165-1202`），预算耗尽时宽限为 0。
  2. 收尾段有界：`OTA_TERMINAL` − `OTA_FAIL_AT` **< 30s**。写通道此时已废弃，
     `_writeFrameChecked:1087-1092` 对非探针帧（含 ABORT，`abortBestEffort`
     走同一入口且 `resyncProbeSeq == null`）立即拒绝，实测应 ≈0；若 > 1s，
     报告必须写明该次为何没走拒绝分支，不得含糊通过。
  3. 取消路径（独立一次会话）：用户在写黑洞期间取消，`操作已取消` 之前最后一次
     ABORT 尝试到取消终态 **< 30s**（上界 writeTimeout + 2×writeTimeout，
     该路径 `_noProgressClock` 已置空，不受 durable 预算约束）。

**T2：MCU 侧帧边界（判据 4）**

- 设备：真机 ＋ AT32F435 目标板（**生产固件**；J-Link 烧录与 RTT 采集沿用
  `AGENTS.md` 既有闭环）。
- 判据：同一次会话的 MCU 侧 RTT 日志显示悬空帧以 CRC 失败收场、随后 GET_INFO
  探针重新同步；不出现 ABORT 被吞进悬空 payload 的迹象。
- **拓扑不可合并**：T2 要求 MCU 在环且仍在运行，才能观测解析器行为；T1 要求的
  「从机不回写响应」是另一套装置。因此 T2 是**独立的一次会话**，其证据只证
  MCU 侧解析器行为，**不得**用来证明 T1 的 30s 界限；反之亦然。两者靠同一
  dev APK 与协议一致性关联，不靠会话同一性。
- **预检（只读，先做）**：用 RTT logger 确认生产固件的帧解析失败/自复位分支
  确有 RTT 输出。若该分支不打进 RTT，本判据记 ENV_BLOCKED，**不得**用
  「RTT 没有错误行」推定通过，**也不得**为此改 MCU 固件（属另一组件范围，
  须另行授权与计划）。

### 4.4 探针与恢复路径的时限（明确，不与 4.3 叠加）

- 废弃期 GET_INFO 探针序列只有一个端到端总时限：
  `probeBudget = resyncProbeTimeout × maxResyncProbes = 800ms × 20 = 16s`，
  实际预算 `max(调用方 timeout, probeBudget)`（默认 max(10s, 16s) = 16s，
  `ota_ble_transport.dart:128-140`）。
- 等待在途旧物理写结算（`_awaitDeviceWritesIdle(remaining())`，同文件
  185/198）**计入同一预算**，不是可与 16s 相加的第三段等待；预算耗尽即抛
  TIMEOUT 并保持废弃，不假装恢复。
- 传输路径的终止发布**不含**探针重试：T1 的黑洞场景下终止由传输路径在 30s
  预算内发布，探针重试属于其后的恢复路径，两段时间不得相加成一条判据。

### 4.5 操作边界、恢复与配额

- 允许：J-Link 烧录生产固件、连接/断开 BLE、发起真机 OTA、清 logcat、拉取
  RTT、`r`+`g` 复位、按既有流程拔插 SD 恢复挂死。
- 禁止：改 MCU 固件、改冻结协议或验收包、安装/卸载其他应用、清应用数据、
  写 SD 卡内容、使用 release 签名产物或发布流程。
- 恢复：每次会话结束复位设备、停 logger、清残留进程；观测失败先留证据再按
  执行合同 §3、§7.1 分类，不盲重试。
- 配额：每项判据以「1 次烧录 ＋ 1 次会话」为一轮；失败分类后按最小范围复测，
  不重跑整套流程。
- 本轮不执行真机、不修改 MCU、不改冻结协议。
