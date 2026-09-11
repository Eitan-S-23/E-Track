# P3-3 T1b 路径 A 能力核查报告（bless / WinRT GATT server）

- 日期：2026-09-11　角色：实现 agent（非独立验收）
- 性质：**开发观测输入**，不是验收证据；本报告**未广播、未连接、未对目标设备注错**。
- 授权依据：用户 2026-09-11 决定——授权在 `D:\github\my\E-Track` 内准备仿真 harness、
  项目内隔离依赖环境与只读能力检查，「先固定 bless 版本，核实能否控制 ATT Write
  Response，再决定是否开发完整协议仿真」。
- 边界：全部写入位于项目内 `.cache/p3-3-t1b/`（该目录已被 Git 忽略）；
  无项目外写入，无设备操作。

## 1. 环境固定

| 项 | 值 |
| --- | --- |
| 解释器 | Python 3.13.12（本机唯一：`py -0p` 仅列 3.13） |
| 隔离环境 | `.cache/p3-3-t1b/venv`（项目内） |
| pip 缓存 | `.cache/p3-3-t1b/pip-cache`（显式重定向，未落用户目录） |
| 固定版本 | **`bless==0.2.6`** |
| 产物 | `bless-0.2.6-py3-none-any.whl` sha256 `2b4b4ce8ee70a987886f22ca369e2093624aea315abe609bd01499f2d16056d1` |
| 对照产物 | `bless-0.3.0-py3-none-any.whl` sha256 `29c5a87a100a43f1dddab29e46a5adfdc871d42f4d421f13ae5c7a0ec23e7a6b` |

**为什么不是最新版 0.3.0**：`bless==0.3.0` 在 Python 3.13 上**装不上**。其元数据按
`python_version >= "3.12"` 钉死 `winrt-Windows.Devices.Bluetooth==2.0.0b1`，而该版本
已不在 PyPI（现存 `2.2.0, 2.3.0, 3.0.0, 3.1.0, 3.2.0, 3.2.1`）；改用 sdist 构建同样
失败。这是路径 A 的**既有依赖限制**，如实记录，不作变通（不手改其依赖钉）。

`bless==0.2.6` 在 3.13 上解算通过，安装后的完整依赖集（`pip freeze`）：

```text
bleak==3.0.2
bless==0.2.6
pywin32==312
typing_extensions==4.16.0
winrt-runtime==3.2.1
winrt-Windows.Devices.Bluetooth==3.2.1
winrt-Windows.Devices.Bluetooth.Advertisement==3.2.1
winrt-Windows.Devices.Bluetooth.GenericAttributeProfile==3.2.1
winrt-Windows.Devices.Enumeration==3.2.1
winrt-Windows.Devices.Radios==3.2.1
winrt-Windows.Foundation==3.2.1
winrt-Windows.Foundation.Collections==3.2.1
winrt-Windows.Storage.Streams==3.2.1
```

## 2. 第一问：bless 能否控制 ATT Write Response —— **否**

WinRT 后端的写请求处理器对两个版本都是「回调返回后无条件应答」：

- 0.2.6 `bless/backends/winrt/server.py:347-353`：

  ```python
  self.write_request(str(sender.uuid), value)

  if request.option == GattWriteOption.WRITE_WITH_RESPONSE:
      request.respond()

  logger.debug("Write Complete")
  deferral.complete()
  ```

- 0.3.0 `bless/backends/winrt/server.py:409-415`：同一结构，`request.respond()`
  在 `:411-412`。

配套事实：

- 用户回调的**返回值不参与决策**：`bless/backends/server.py:271`
  `self.write_request_func(characteristic, value)`，返回值被丢弃；回调签名
  `write_request(self, uuid, value)` 无返回契约。
- 因此**没有**任何公开 API（无开关、无返回约定、无异常约定）可以扣住、延迟或拒绝
  ATT 写响应。评审意见得到确认：**停止 FFF1 的 OTA ACK 通知 ≠ 停止 ATT 写响应**，
  以 bless 既有写路径无法制造 native 写黑洞。
- 附带的风险：若让 `write_request_func` 抛异常，则 `request.respond()` 与
  `deferral.complete()` 双双跳过，但这是**未定义路径**（依赖异常穿过 pythonnet 事件
  回调），不作为方案。

## 3. 第二问：WinRT 层是否存在控制点 —— **有**

只读 API 面检查（`winrt-Windows.Devices.Bluetooth.GenericAttributeProfile==3.2.1`
投影，未创建 service provider、未广播）：

| API | 成员 | 用途 |
| --- | --- | --- |
| `GattWriteRequest` | `respond`、`respond_with_protocol_error`、`option`、`state`、`value`、`add_state_changed` | 应答时机与应答内容的**应用层控制点** |
| `GattLocalCharacteristic` | `add_write_requested`、**`remove_write_requested`**、`add_read_requested`、`remove_read_requested` | 处理器可**撤销并替换** |
| `GattWriteOption` | `WRITE_WITH_RESPONSE`、`WRITE_WITHOUT_RESPONSE` | 可按写模式分支 |

可达路径（bless 侧）：`BlessServer.get_characteristic(uuid)`
（`bless/backends/server.py:185`）→ `BlessGATTCharacteristicWinRT.obj`，即裸
`GattLocalCharacteristic`（0.2.6 `winrt/characteristic.py:89-91` 以 `obj=gatt_char`
构造）。bless 自身正是用它注册处理器：`winrt/server.py:238`
`characteristic.obj.add_write_requested(self.write_characteristic)`。

**结论的准确边界**：控制点在 **WinRT 层**存在，但**不在 bless 公开 API 层**。
使用它意味着绕开 bless 的写路径（`BlessServer.write_request` / `write_request_func`
不再参与），协议应答逻辑需在自定义处理器内自行实现；bless 仍可承担广播、服务与特征
声明、通知发送。

## 4. 第三问：不 respond 时 Windows 栈的语义 —— **文档未规定，必须实测**

已核 UWP 参考文档两页（`GattLocalCharacteristic.WriteRequested`、
`GattWriteRequestedEventArgs`）：**仅一句「write was requested」的说明，无任何 remarks**
描述「处理器返回而未调用 `Respond` / 未完成 deferral」时的行为——既不承诺扣住响应，
也不承诺自动应答或超时断开。

可从 API 设计**推定**（不构成证明）：`GattWriteRequest.Respond()` 与 `GattWriteRequestedEventArgs.GetDeferral()`
的存在意味着应用层可以异步决定应答时机；但**系统级超时、协议错误兜底或断连策略均无
文档承诺**。这一项只能在真实连接下实测，属于 **B1（广播/连接/注错）未授权范围**。

## 5. 只读适配器能力（`BluetoothAdapter` 属性）

| 属性 | 值 |
| --- | --- |
| `device_id` | `\\?\USB#VID_2C0A&PID_8761#00E04C239987#{92383b0e-...}` |
| `bluetooth_address` | `153416961622864` |
| `is_low_energy_supported` | true |
| `is_peripheral_role_supported` | **true** |
| `is_central_role_supported` | true |
| `is_advertisement_offload_supported` | true |

注意事项：

- 这是**适配器自述能力**，不等于 Windows GATT server 实际可广播、可被 Android 发现；
  按评审意见，**仅支持外设角色不足以证明方案可行**。
- 该属性读取本身不需要广播/连接，属只读检查。
- 主机的 Windows 版本为 10.0.19045，WinRT GATT server 自 10.0.15063 起提供。

## 6. 路径 A 的可行性分级

| 级别 | 内容 | 判定 |
| --- | --- | --- |
| A0 | 用 bless 公开 API 扣住写响应 | **不可行**（§2，源码级确定） |
| A1 | bless 负责广播/服务声明/通知 + 自定义 `add_write_requested` 处理器接管应答 | **机制具备、语义未验证**（§3 控制点存在，§4 未决） |
| A2 | 完全自写 WinRT GATT server，不用 bless | 不推荐：自研面扩大，且未解决 §4 的同一未决问题 |

## 7. 未决项清单（只能由实测判定）

1. `remove_write_requested` 能否与注册时的 bound method 匹配（pythonnet 投影下
   delegate 同一性未验证）；若不匹配，替代办法是**子类覆写** `write_characteristic`
   后再注册（`add_write_requested` 在 `init` 期取 `self.write_characteristic`，子类覆写
   会在注册前生效）——两条路都必须实测确认。
2. 处理器返回而不 `respond()`、且不 `complete()` deferral 时：Windows 栈是否真的扣住
   ATT 写响应；有无系统超时、协议错误兜底或断连。
3. 扣住写响应的同时，能否继续在 FFF1 上发送通知（ACK 通道）——ATT 事务串行性未知。
4. 客户端写模式必须为 **write-with-response**（应用侧优先选有响应写，见
   `lib/services/bluetooth_service.dart:2173-2187`）；若外设只声明无响应写，判据 B1
   的前提不成立。
5. bless 0.2.6 每回调新建事件循环（`asyncio.new_event_loop()`），自定义处理器下
   通知发送与写处理器是否互相阻塞未测。

## 8. 建议：先做最小机制验证，再决定是否开发完整协议仿真

不直接投入完整 FFF0/FFF1/FFF2 协议仿真（`docs/ota-binary-contracts.md` §5 的
INFO/BEGIN/ACK/断供全流程），而是先做**单特征最小机制验证**：

1. 起 bless 服务，声明一个 **write-with-response** 特征；
2. 用自定义处理器接管它（§6 A1）；
3. 用 Android 侧（或第二台手机）发一次写；
4. 分别在「立即 respond」「推迟 N 秒 respond」「不 respond 且不 complete deferral」
   三种策略下观测写回调是否返回——**只判机制，不判协议**。

- 若第 3 种策略确实扣住写响应 → A 路径成立，再开发完整协议仿真（回归 §7）。
- 若 Windows 栈在无响应时自动应答或断开 → A 路径**不可行**，如实报具体 API 限制，
  按 A→B/C 比较；本报告不写「永远无法实测」。

## 9. 本报告**未**做的事（NOT_RUN）

- 未广播、未创建 `GattServiceProvider`、未连接任何设备、未注错。
- 未安装/未修改任何 MCU 固件，未使用 J-Link。
- 未对目标 AT32F435 板或测试手机做任何操作。
- 未改动冻结契约、历史验收包、`main` 分支或他人工作树内容。
