# P3-3 第九批 RC3-03/05/07：写通道废弃标记的解除条件与 MCU 真值

- 日期：2026-09-11
- 范围：`app/bluetooth_flutter_Trace` 的写通道废弃（poison）语义；只读核对 MCU 侧
  `Libraries/OTA/**`、`USER/HAL/HAL_Bluetooth.cpp`。**未修改任何 MCU 源码、未修改
  冻结协议、未触碰历史 P3-1 验收**。
- 触发：第八批独立复核 RC3-03/05/07（`.cache/p3-3-review-batch8-20260910/review.md`）
  指出「重连即解除废弃标记」缺乏依据，且测试替身通过 `_pending.clear()` 制造了
  未经证明的干净解析器状态。

## 1. 结论摘要

1. 第八批的废弃标记作用域是「物理链路身份」= `(deviceAddress, otaLinkGeneration)`。
   **BLE 重连会让代次前进，从而静默解除标记**——这一解除条件没有任何证据支撑。
2. MCU 真值：帧解析器悬空状态保存在 `ota_ble_session_t::demux.parser` 里，**BLE
   连接事件不影响它**；`session_teardown()` 也不复位 demux。因此「真机重连后解析器
   回到同步态」是错误前提。
3. 应用侧**可达且可证明**的重新同步条件只有一个：**继续投递字节**，让悬空帧按
   自身 `len` 被吃完、CRC 失败、解析器自复位；再以一次 `GET_INFO → INFO` 往返
   （INFO 只可能由「被完整解析的 GET_INFO 帧」触发）作为**正向证据**解除标记。
4. 据此本批改为：废弃标记作用域 = **设备**（同地址进程内恒定，重连不解除）；
   废弃期间唯一放行的出站帧 = `GET_INFO` 探针；收到 INFO 应答才解除。无证据即
   保持 fail-closed。
5. 不需要 MCU 配合，因此**不提交跨组件需求**。

## 2. MCU 真值（只读核对，带行号）

### 2.1 解析器在 PAYLOAD 态吞掉一切字节（含同步字）

`Libraries/OTA/ota_ble_frame.c:260-272`：

```c
case OTA_BLE_PS_PAYLOAD:
    if (parser->payload_index < parser->len) {
        parser->payload[parser->payload_index] = byte;   /* 任意字节，含 A5 5A */
        ++parser->payload_index;
        parser->crc_calc = ota_ble_crc16_update_byte(parser->crc_calc, byte);
    }
    if (parser->payload_index >= parser->len) {
        parser->state = OTA_BLE_PS_CRC;
        parser->hdr_index = 0u;
    }
    break;
```

半帧之后写入的每个字节都被当作悬空帧的 payload/CRC，**不存在「遇到同步字就
重新对齐」的路径**。这与废弃标记的动机一致。

### 2.2 解析器只在这一帧被吃完之后才自复位

- 长度非法（`ota_ble_len_accept` 失败，`:240-251`）→ `ota_ble_parser_reset`；
- CRC 失败（`:303-313`）→ `ota_ble_parser_reset`；
- 帧完整且 CRC 通过（`:286-302`）→ `ota_ble_parser_reset`。

`ota_ble_parser_reset` 定义在 `:85`。也就是说：**只要继续投递字节，悬空帧必然在
有限字节内结束（最多 `len` 个 payload 字节 + 2 个 CRC 字节）并复位解析器**。
帧长上界由 `OTA_BLE_MAX_PAYLOAD = 132u`（`ota_ble_frame.h:25`）决定，即最多
132 + 2 = 134 字节就能清掉任何悬空帧。

复位后 demux 回到 IDLE（`ota_ble_frame.c:396-403`：BINARY 态下解析结果非 IDLE 即
`demux->state = OTA_BLE_DEMUX_IDLE`），后续字节重新走 `A5 5A` 同步扫描。

### 2.3 BLE 连接事件不复位解析器

- `ota_ble_demux_init` 只在 `ota_ble_session_init`（`ota_ble_session.c:799`，开机
  初始化）里被调用；全仓库没有第二处。
- `session_teardown`（`ota_ble_session.c:158-169`）复位 `isr_active`/`rx_ring`/
  `receiver`/`state`/`session_id` 并归还 overlay，**不触碰 `session->demux`**。
  会话超时（`:858-863`）走的就是 `session_teardown_aborted` → `session_teardown`。
- 空闲路径同样把字节喂给同一个 demux：`ota_ble_session_feed_idle`
  （`:821-830`）→ `session_feed_byte`（`:767-784`）→
  `ota_ble_demux_feed(&session->demux, ...)`（`:773`）。悬空解析器在会话 IDLE 期间
  继续吞字节。
- HAL 侧 `HAL::BT_Update`（`USER/HAL/HAL_Bluetooth.cpp:247-272`）与
  `HAL::BT_OtaPump`（`:275-279`）只做搬运与 pump，连接状态由 `BT_IsConnected`
  （`:281-288`）读取，**没有任何连接事件驱动的解析器复位**。

**推论**：`ota_service.dart` 侧「真实重连 → 链路代次前进 → 旧链路废弃标记失效」
在 MCU 侧找不到对应事实。旧代码注释里「靠 MCU 30s 会话超时 teardown 恢复同步」
同样不成立：teardown 不复位 demux，而且停写本身让悬空帧永远吃不完。

### 2.4 测试替身的不忠实之处

`test/ota/ota_ble_transport_test.dart` 的 `_FakeMcuHost.reconnect()` 原实现：

```dart
void reconnect() {
  _pending.clear();          // ← 无依据地制造干净解析器
  linkIdentity = Object();
}
```

`_pending` 正是替身里的「解析器重组缓冲」，对应 MCU 的 `demux.parser`。真机重连
不会清它。该替身因此把「重连后可写」这一**未经证明的结论**反向固化进了用例。

## 3. 可达的重新同步条件与实现选择

| 候选条件 | 依据 | 结论 |
| --- | --- | --- |
| BLE 重连 / 新增 link generation | 无（§2.3） | **否决**，删除该解除路径 |
| 等 MCU 30s 会话超时 teardown | teardown 不复位 demux（§2.3），且停写使悬空帧永远不结束 | **否决**，删除该说法 |
| MCU 断电/复位 | 会走 `ota_ble_session_init` → demux 复位 | 成立但应用不可控，仅作为兜底 |
| 继续投递字节直至悬空帧结束 | §2.1/§2.2 的解析器自复位路径 | **采用**：废弃期间放行 `GET_INFO` 探针帧 |
| 以 INFO 应答作为正向证据 | INFO 仅由「被完整解析的 GET_INFO」触发（会话帧语义），是接收方支持的可观测同步证据 | **采用**：收到 INFO 才解除标记 |

### 3.1 本批实现

1. **作用域改为设备**：`OtaBleChannel.linkIdentity` → `deviceScope`，由
   `BluetoothService` 按地址恒定返回同一对象（不再随 `otaLinkGeneration` 前进）。
2. **废弃期间唯一放行 `GET_INFO`**：它只读、幂等，且作为探针被吞时不产生任何副作用；
   其余帧（含取消路径的 ABORT）继续 fail-closed 抛 `WRITE_TIMEOUT`。
3. **正向证据解除**：仅当「本实例在废弃状态下发出的探针」收到 `session=0` 且
   `seq` 匹配的 INFO 时才解除，避免陈旧 INFO 误解除。
4. **有界重试**：一次 `GET_INFO` 可能整帧被悬空帧吞掉；探针在废弃状态下按
   ≤ 20 次、每次 ≤ 800ms 重试。上界依据 §2.2：134 字节 / 10 字节探针帧 ≈ 14 次。
   超过上界仍失败则保持废弃并抛出，绝不假装恢复。
5. **替身忠实化**：`reconnect()` 不再清 `_pending`；替身按 MCU 语义处理坏帧
   （整帧被吃完 → CRC 失败 → 丢弃并继续扫描剩余字节），不再把 CRC 失败抛成写错误。

### 3.2 未做与不做

- 不修改 MCU 源码、不修改冻结协议、不触碰 P3-1 历史验收。
- 不采用「写入固定长度填充字节冲掉悬空帧」方案：虽然 §2.2 能给出上界，但它会向
  MCU 注入非协议字节到文本通道（`bt_text_sink` → TinyBTPlus），属于未协调的
  跨组件行为变更。探针重试只复用既有帧，无需协调。
- 本改动不改变正常链路（未被废弃）的任何行为：`deviceScope` 只用于标记作用域，
  解除条件只在废弃期间生效。

## 4. 证据与验证计划

- 静态：本文 §2 的行号引用；改后 `flutter-dev-checks.yml` 双宿主 analyze + tests。
- 运行：`ota_ble_transport_test.dart` 中 RC3-05⑤ 用例改为忠实替身后，断言
  「重连后业务帧仍被拒绝（字节数不变）→ 探针重试 → INFO 证明 → 解除后可写」。
- 真机：本批不执行真机验证；若后续需要，判据是「截断写后同一设备重连，
  业务帧在无 INFO 证据前必须失败」。
