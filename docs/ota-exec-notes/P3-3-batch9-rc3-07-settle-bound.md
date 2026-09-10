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
  （`_poisonWriteChannel`）已拒绝全部业务帧与 ABORT（见 `_writeFrameChecked`
  入口与 `_writeFrameLocked` 排队复核），唯一仍可能在途的写入是 GET_INFO
  探针；探针字节被吞进悬空帧后由 MCU 坏帧自复位（`ota_ble_frame.c` 失败分支
  reset）与有界探针重试（`maxResyncProbes = 20`、单次 800ms）接管。
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
时序，也不能证明 native 写在宽限归零后不会与探针字节交错。正式计划需补：

- **环境**：一台 Android 真机（装 CI 产出的 dev debug APK）＋ 一个可控的 BLE
  从机：接受连接与 ATT 写但不回写响应（例如第二台手机的 BLE Peripheral
  Simulator，或 nRF52/nRF Connect 测试从机），使 `writeCharacteristic` 在
  native 层悬挂。**不使用**需要改 MCU 固件的注入手段（属另一组件范围）。
- **观测点**：应用侧终止发布时间。正式计划需授权一次 dev-only 插桩提交：
  在 `ota_service.dart` 的 WRITE_TIMEOUT 终态发布分支加一行
  `debugPrint('OTA_TERMINAL ${DateTime.now().microsecondsSinceEpoch}')`，
  由既有 `flutter-dev-checks.yml` 出 dev APK（不涉及 release/发布）。
- **命令**（Windows，项目内落盘）：
  ```text
  adb -s <serial> logcat -c
  adb -s <serial> logcat -v threadtime -s flutter > .acceptance-<id>/logcat.txt
  ```
  真机驱动一次 OTA → 从机进入写黑洞 → 等待应用终止。
- **上界与判据**（单一手机时钟，两项都由 logcat 时间戳给出）：
  1. 传输路径：最后一次 `OTA sent <n>/<total>`（即最后一次 durable 进展）
     与 `OTA_TERMINAL` 的差值 **< 30s**（判据取 33s 作蓝牙栈调度余量；
     修复前该差值会达到 ~50s，两者可分辨）。
  2. 取消路径：`操作已取消` 之前的 ABORT 尝试到终态的差值 **< 30s**
     （writeTimeout + 2×writeTimeout）。
  3. 交错：同一次会话的 MCU 侧 RTT 日志（J-Link 闭环，见 AGENTS.md）
     必须显示悬空帧以 CRC 失败收场、随后 GET_INFO 探针重新同步，
     不出现 ABORT 被吞进悬空 payload 的迹象。
- **配额与失败分类**：按执行合同 §3、§7.1 在正式计划内登记；观测失败先留
  证据再分类，不盲重试。本轮不执行真机、不修改 MCU、不改冻结协议。
