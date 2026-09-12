# P3-3 T1a 步骤1（真机身份读取）首轮实测记录 —— 2026-09-12

> 依据：`docs/ota-exec-notes/P3-3-batch9-device-observation-sheet.md` §2.2/§4；
> 用户分阶段指令“步骤1”。载体为方案乙产物 `com.wen.gaia.gaia.dev`
> （sha256 `e38bb365…c72011a`，CI run `34625885805`）。
> **本轮未停机、未复位、未烧录、未卸载、未清数据**；A1 配额 1 授权 / 0 消耗。
> 正式验收 `NOT_RUN`；T2 保持 `ENV_BLOCKED`。

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| `.dev` APK 安装/共存 | 成功（与生产版并存，未卸载、未清数据） |
| 运行时权限 | User 0 已授予 BLUETOOTH_SCAN / CONNECT / FINE_LOCATION / POST_NOTIFICATIONS |
| 真实 BLE 扫描可用 | **是**（功率计页，见 §3） |
| 目标板是否在广播 | **否**：3 分钟扫描仅见 5 台非目标设备（§3.2） |
| 服务发现（FFF0/FFF2/FFF1） | **NOT_RUN**（无绑定目标） |
| 通知订阅 | **NOT_RUN**（同上） |
| GET_INFO（设备身份） | **NOT_RUN**（同上） |
| `OTA_MONO` 事件 | 全部日志中 **0 条** |
| 目标板地址绑定 | **未取得**（目标板未出现，无地址可绑） |

判定口径：本次既不是“设备未暴露 OTA 服务”，也不是“GET_INFO 失败”，
而是**无候选目标设备**——`readDeviceInfo` 从未被调用。

**后续补充（同日，J-Link 只读回合）**：目标板经 J-Link 侧识别已确认**在线且应用全速运行**，
固件身份可逐字节核对；§3.3 的“生产版占连接”假设未能证实，但「板子没电/固件没跑/MCU 卡死/
被调试器顶在停机态」等已在板侧被排除。详见
`docs/ota-exec-notes/P3-3-t1a-jlink-board-identification-2026-09-12.md`。

## 1. 一个必须先说的观测陷阱：码表页是硬编码演示页

`USER` 侧 `speedometer_page.dart` 的“设备/码表”链路**不是真实 BLE 实现**：

- 扫描子头注释自述：`固定子头：扫描雷达 + 停止扫描（本地视觉状态，不接真实 BleController）`
  （`speedometer_page.dart:7256`）。
- “可用设备”三行是字面量：`iGPSPORT BSC300_1234`（码表）、
  `iGPSPORT SR30_5678`（雷达）、`iGPSPORT HR40_9012`（心率带）
  （`:7405/:7417/:7429`）。
- 设备详情页 `_RideDeviceDetailPage` 的 `已连接` / `固件版本：v1.23.0` /
  `电量：100%` 同为字面量（`:7819/:7830/:7839`）。
- 该页“检查单片机固件更新”卡片推的是 `const OtaUpgradePage()`
  （`:7989`，**不带设备参数**）。

后果：从码表页进入固件页时，`_deviceAddress` 恒为 null
（`(widget.connectedDevice ?? _resolvedDevice)?.…`），
`_readDeviceInfo()` 在 `if (address == null) return;` 处直接返回，
**既不发 GET_INFO，也不做服务发现/订阅**。页面因此稳定显示
“未连接设备 / 连接码表后自动读取设备身份”。

本轮共复现 3 次（截图 `ui-05-ota.png`、`r3-01-ota.png`、`r4-02-after.png`），
每次都从该演示页的固件卡片进入，均未产生任何 `OTA_MONO` 事件。

`grep -c OTA_MONO` 对 `logcat.txt`/`logcat-part1.txt`/`logcat-full-dump.txt`/
`logcat-r2..r4.txt` 全部为 **0**。

## 2. 真实入口与真实调用链

真实设备身份链路的入口是**设备页 → 功率计**：

- `device_tab_page.dart:489` `Get.to(() => const PowerMeterPage())`
- `power_meter_page.dart:244` `Get.to(() => DeviceDetailPage(device: device))`
  （`device` 来自 `bleController.discoveredDevices`，真实扫描对象）
- `device_detail_page.dart:146` `Get.to(() => OtaUpgradePage(connectedDevice: device))`
  —— **只有这条路径才会显式绑定设备地址**。

## 3. 本轮真实观测

### 3.1 真实扫描可用

`功率计` 页 → `开始扫描`，应用日志逐台输出地址与名称，例如：

```text
I/flutter: 获取设备名称，设备ID: F1:22:33:3A:0A:C4
I/flutter: 扫描结果中设备名称: AIMA-3A0AC4
I/flutter: BleController接收到扫描结果: 7 个设备
```

UI 同时显示 MAC 与 RSSI（如 `08:38:E6:59:63:27  -60dBm  可连接/一般/厂商数据`）。

### 3.2 目标板未出现

> **⚠ 本小节结论已于同日撤回**：第二轮实测证明应用日志出口在 **5 台**处恒定饱和
> （1044 行日志只有 5 个去重 MAC，而扫描峰值 17 台）。下面的「仅 5 个地址」
> 是**日志出口上限**，不是扫描结果。且检索关键词 `igpsport` 本身也是错的——
> 固件下发的模块名是 `AT+NAME=XTrace`（`USER/HAL/HAL_Bluetooth.cpp:234`）。
> 更正记录见 `docs/ota-exec-notes/P3-3-t1a-step1-scan-r2-2026-09-12.md` §2/§3。

15:55–16:08 连续扫描（含一次 60 秒延长观察），去重后**仅 5 个地址**：

```text
08:38:E6:59:63:27   烟雨江南pad
F1:22:33:3A:0A:C4   AIMA-3A0AC4
AE:02:22:37:82:3E   AJBLE94
22:04:25:0A:64:9F   Cleartone
64:C9:3A:8A:0D:1D   （无名称）
```

- 无任何 iGPSPORT 设备；
- 日志中 `igpsport|fff0|ota` 命中数 **0**；
- 因此没有可绑定的目标板地址，步骤1 的后续动作全部 **NOT_RUN**。

### 3.3 一个可能的原因（未验证，不视为结论）

`com.wen.gaia.gaia`（生产版）与 `com.wen.gaia.gaia.dev` **同时在运行**
（PID 7059 / 13914，`ps -A` 与 `dumpsys activity processes` 均可证）。
若生产版在后台已占住目标板的 BLE 连接，目标板通常不再广播，
扫描自然看不到。**本轮未停止生产版进程**（不属于已授权动作），
故该假设无法由本轮证据证实或证伪。

## 4. 缺口报告（按要求区分类别，不归因 HTTP 端点）

1. **目标板未出现在扫描结果中** —— 需现场确认目标板是否上电、是否在广播范围内，
   以及是否需要先释放生产版占用的连接。这是**设备侧/现场条件**缺口。
2. **码表入口无法绑定设备**（§1）—— 这是**开发 APK 的功能缺口**：
   演示页的固件入口没有设备参数，无法完成服务发现/订阅/GET_INFO。
   它**不是** HTTP 端点问题，也与 `TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL`
   是否注入无关（截图中的“固件服务未配置”仅反映该常量未注入，
   而身份读取是纯 BLE 路径，不依赖它）。
3. **目标板 MAC 的记录出口**：`dumpsys bluetooth_manager` 在本机
   （vivo PD2312 / V2312A，Android 13 级）返回 0 字节，系统侧不可读。
   但**应用日志已提供可用出口**（`获取设备名称，设备ID: <MAC>`），
   因此一旦目标板出现即可直接绑定地址，无需新增观测能力。

## 5. 产物与证据路径（均在项目内、被忽略目录）

`\.cache\p3-3-t1a-step1-r1\`

| 文件 | 内容 |
| --- | --- |
| `logcat-r4.txt` | 本轮以应用 PID 过滤的有界 logcat（37467 行，15:55–16:08） |
| `logcat-r2.txt` / `logcat-r3.txt` | 前两轮 logcat（含 `r3` 的管道存活验证） |
| `r4-01-before.png` / `r4-02-after.png` | 演示页固件卡片点击前后对照（可复现“未绑定”） |
| `r6-01-powermeter.png` … `r6-05-stop.png` | 真实功率计页扫描全程截图 |
| `ui-05-ota.png` / `r3-01-ota.png` | 未连接设备态截图（含“固件服务未配置”芯片） |

## 6. 本轮边界

- 未执行：BEGIN/DATA/END、J-Link 停机/复位/烧录、卸载、清数据、擦除、WDT 或调试寄存器更改。
- 未读取或注入任何 secret；未修改生产工作流。
- 电源/广播状态、生产版进程归属等**设备侧条件**未做任何更改。
