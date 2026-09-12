# P3-3 B1-M 最小机制验证 —— 交付报告（2026-09-11）

> 任务：在**仅 PC 蓝牙适配器 + 本项目专用测试手机**范围内，验证「中心端写完成事件」在
> 外设三种应答策略（立即 / 延迟 N=3 s / 不应答 H=20 s）下的可观测行为。
> 定位：**B1-M 最小机制验证**，不冒充完整 T1b/B1 产品观测，不占用也不重置既有 T1a/A1 额度。

## 0. 结论

| 策略 | 轮次 | 外设侧应答 | 中央侧 native 写完成事件 | 判定 |
| --- | --- | --- | --- | --- |
| 立即应答（对照） | r9 | +34 ms 应答被接受 | +122 ms `chr: fff2 GATT_SUCCESS (0)` | **通过** |
| 延迟应答 N=3 s | r20 | +3.046 s 应答被接受（`released_early=False`） | +3.215 s `chr: fff2 GATT_SUCCESS (0)` | **通过** |
| 不应答 H=20 s | r21 | 20.028 s 内未应答；唯一应答尝试被系统拒绝（`RO_E_COMMITTED`） | 15 s 内无事件；首个回调 +20.104 s 且为 `GATT_UNLIKELY (14)` | **通过** |

三策略各**一次**写观测，全部使用：外设仅声明 `WRITE(8)`、客户端 `writeWithResponse: true`、
判据事件仅为中央侧 `onCharacteristicWrite`（`[FBP-Android]`）。

## 1. 实验前固定的判据（执行中未调整）

| 项 | 值 | 来源 |
| --- | --- | --- |
| N（延迟应答） | 3.0 s | 事前固定 |
| H（不应答窗口） | 20.0 s | 事前固定，须覆盖产品写超时 10 s 与客户端 15 s |
| T_c（客户端写超时） | 15 s | FBP `fbpTimeout(15)`，源码：`.cache/p3-3-t1b/fbp/flutter_blue_plus-1.35.5/lib/src/utils.dart:16-21` |
| 单策略时限 | ≤ 5 min（harness `--total-limit`） | 事前固定 |
| 三策略合计 | ≤ 20 min | 事前固定 |
| 判据事件 | 中央侧 native `onCharacteristicWrite` | `FlutterBluePlusPlugin.java:2385`，注释：writeWithResponse 的完成回调在远端回写响应之后 |

**排除项**（不得替代判据事件）：写请求已提交、UI 卡住、Dart Future 未完成、外设日志自身。
**不可证明项**：物理写是否已取消。

## 2. 装置与身份

| 端 | 项 | 值 |
| --- | --- | --- |
| 外设（PC） | 适配器 device_id | `\\?\USB#VID_2C0A&PID_8761#00E04C239987#{92383b0e-f90e-4ac9-8d44-8c2d0d0ebda2}` |
| 外设（PC） | 适配器地址 / 角色 | 153416961622864；LE + peripheral role 均支持 |
| 外设（PC） | 广播名 | `B1M-ETrack`（harness `--name`） |
| 外设（PC） | 广播地址 | **每会话轮换（RPA）**：r9 `70:54:77:E6:26:1D`、r20 `79:3C:46:3A:E3:30`、r21 `5F:5F:28:82:34:FD` |
| 中心（手机） | 序列号 / 机型 / 系统 | `10ADA4197U001CK` / vivo V2312A / Android 13（SDK 33） |
| 中心（手机） | 应用 | `com.wen.gaia.gaia` 1.0.60 (86)，release，非 dev CI 产物 |
| 中心（手机） | APK SHA-256 | `428a5d3a3f5c829df19e523800124712ffa30eb620ce0af277fe38352f90e382`（45951912 B） |
| 双方 | 服务 / 写特征 | `0000fff0-...` / `0000fff2-...`，外设声明属性仅 `WRITE(8)` |

判据不依赖客户端源码版本，只依赖写路径存在（`_sendInputOnce` → `writeByAddress(..., writeWithResponse: true)`）
与 native 日志通道存在（`classes.dex` 含 `[FBP-Android]`、`onCharacteristicWrite`）。

**产物**：三策略原始证据在 `.cache/p3-3-t1b/runs/b1m-{immediate-r9,delayed-r20,withhold-r21}/`
（`identity.md` + `peripheral.log` + `peripheral.jsonl` + `logcat.txt`）；harness 源码
`docs/ota-exec-notes/tools/p3-3-b1m/b1m_peripheral.py`。

## 3. 三策略原始证据（决定性行）

### 3.1 r9 立即应答 —— `.cache/p3-3-t1b/runs/b1m-immediate-r9/`

```text
[   156883313 us] write_request ... option=0 with_response=True length=2 payload_hex=4131 hold_s=0.0
[   156885507 us] respond ... held_us=34087 released_early=False respond_error=None complete_error=None
[   167199911 us] run_end writes_seen=1 exit_code=0
```

手机侧：`21:44:02.090 onMethodCall: writeCharacteristic` → `21:44:02.212 onCharacteristicWrite: chr: fff2 / status: GATT_SUCCESS (0)`。

### 3.2 r20 延迟应答 N=3 s —— `.cache/p3-3-t1b/runs/b1m-delayed-r20/`

```text
[    78681353 us] write_request ... option=0 with_response=True payload_hex=4131 hold_s=3.0
[    81684684 us] respond ... released_early=False held_us=3045805 respond_us=1303 respond_error=None complete_error=None
[    91202250 us] run_end writes_seen=1 exit_code=0
```

手机侧：`22:35:02.870 onMethodCall: writeCharacteristic` → `22:35:06.085 onCharacteristicWrite: chr: fff2 / status: GATT_SUCCESS (0)`
（+3.215 s，落在 PC 应答之后）。

### 3.3 r21 不应答 H=20 s —— `.cache/p3-3-t1b/runs/b1m-withhold-r21/`

```text
[   221909793 us] write_request ... option=0 with_response=True payload_hex=4131 hold_s=20.0
[   241915627 us] respond ... released_early=False held_us=20028353 state_before_respond=2 respond_error=OSError: [WinError -2147483618] 已提交对象。 complete_error=None
[   250943757 us] run_end writes_seen=1 exit_code=0
```

手机侧：

```text
22:40:27.575 onMethodCall: writeCharacteristic
22:40:42.579 I/flutter: 写入失败(5F:5F:28:82:34:FD/fff0/fff2): Unsupported operation: 未找到目标特征: fff2   ← +15.004 s
22:40:47.680 E/[FBP-Android]: onCharacteristicWrite chr: fff2 / status: GATT_UNLIKELY (14)                        ← +20.104 s
22:40:54.203 BluetoothGatt: onConnectionUpdated()（链路存活）
```

`WinError -2147483618` = `0x8000001E` `RO_E_COMMITTED`（"The object has already been committed"）
⇒ 我方唯一一次应答**发生在 20.028 s 且被系统拒绝**，远端从未收到我方成功应答。

## 4. 本轮获得的机制结论（可复用）

1. **WinRT 本地特征设 `static_value` 会静默丢弃 `WRITE(8)` 位**：设置后回读 `properties=0`，
   客户端在 FFF0 内找不到可写特征而不发写。这是 r1–r8 共 8 轮零写的真根因（探针
   `.cache/p3-3-t1b/prop_static_vs_write.py` 四组对照：A/B/C/D → 0/8/8/8）。已从 harness 删除。
2. **Windows 广播地址每会话轮换（RPA）**：已观测 4 个不同地址；每轮必须重新扫描，
   用上一轮地址重连必 10 s 超时（r21 中 22:39:37 复用 r20 地址即复现）。
3. **`GattServiceProviderAdvertisementStatus` 的 getter 不可作广播判据**：
   `advertising_started advertisement_status=3`（Aborted 值域）与 r9 成功轮相同，判据只看
   手机侧能否扫到 + 能否连接。
4. **中心端遗留 ACL 链路会让广播在约 5–6 分钟内不可见**：r9 后手机侧从未出现 disconnect，
   r11–r17 连续扫不到；`am force-stop` 应用释放本机自建 GATT 客户端后，经 ACL 监督超时
   （约 5–6 min）广播重新可见。这是 r11–r17 连续失败的主因，不是 Windows 广播子系统故障
   （`BluetoothLEAdvertisementWatcher` 期间一直能收到周围 6–9 个广播源）。
5. **FBP 15 s 写超时在应用层可能被伪装**：`bluetooth_service.dart:1315` 的 `catch (_) {}`
   吞掉 `FlutterBluePlusException(Timed out after 15s)`，随后 1317 行抛出
   `UnsupportedError('未找到目标特征: ...')`，日志文案与真实根因不符；**但时刻（+15.004 s）
   可判定为 15 s 超时**。
6. **迟到 native 错误样本（r21 的核心附加值）**：Dart 侧 15 s 已判失败后，native 层在
   +20.104 s 仍投递 `GATT_UNLIKELY (14)` 失败回调。与仓库内 RC3-08 整改场景（"迟到在途写错误
   不得覆盖已决终止"）同型，可作为该防线的真实来源样本。
7. **`state_before_respond` 字段不具区分力**（harness 自身缺陷）：该值在 `self._rec.log(...)`
   中求值，实际读取时刻在 `request.respond()` 之后；r20（应答成功）与 r21（应答被拒）都读到 2。
   已在本报告与各轮 `identity.md` 中标注，**不得用作判据**。

## 5. 轮次台账（含失败轮，用于成本与原因追溯）

| 轮次 | `writes_seen` / `exit_code` | 说明 |
| --- | --- | --- |
| r1–r8（immediate） | 0 / 2 或 5 | harness `static_value` 缺陷 → 中央侧无写；r1 为脚本错误 |
| `b1m-setup-probe-fixed`、`b1m-smoke`、`b1m-adv-probe`、`b1m-loopback-imm` | 0 / 0 或 5 | 只建服务/回环/自检，**不计入写额度** |
| r9（immediate） | **1 / 0** | 修复后首次有效写 → 立即应答**通过** |
| r10–r19（delayed） | 0 / 5 | r10 界面导航失败；r11–r17 广播不可见（见 §4.4，含一次点击落飞书横幅）；r18 无输出（Python 缓冲，改 `-u` 后正常）；r19 手机侧自动化脚本未找到目标行 |
| r20（delayed） | **1 / 0** | 延迟应答 N=3 s **通过** |
| r21（withhold） | **1 / 0** | 不应答 H=20 s **通过** |

**时限核算**：三次有效观测的 harness 实测运行时长为 r9 167.2 s、r20 91.2 s、r21 250.9 s，
**合计 509.3 s ≈ 8.5 min ≤ 20 min**，单轮均 ≤ 5 min，符合事前判据。失败轮不计入该时限，
其系统问题与重试见 §4.4；从 r9 到 r21 的整段会话跨度约 58 min。

## 6. 未证实项与局限

- **不能证明「物理写已取消」**：本实验只观测中央侧写完成事件与状态码，不观测无线层/物理层。
- **r21 中 20 s 处终结主体未证实**：手机侧首个 native 回调（+20.104 s）与 PC 侧我方应答尝试
  （+20.028 s）在各自时钟上几乎重合，且请求对象当时已被系统终结；究竟是 Windows 本地 GATT
  侧请求超时，还是客户端协议栈终止该 ATT 事务，本轮证据**无法区分**。分离需再做一次
  `--window 40` 观测，**超出本轮授权范围，未执行**。
- 两台设备的单调时钟不可相减：本报告所有间隔均为**各自时钟内的差值**。
- 单次样本，无重复观测；**产品侧 10 s 写超时未被单独观测**（仅作为 H 的设计依据）。
- r9/r20 的写路径为遥控透传 `writeByAddress`，**不是** OTA 专用
  `writeOtaCharacteristicByAddress`；本实验不验证 OTA 传输路径本身。
- 未涉及 MCU、未使用 J-Link、未做断电注错。

## 7. 边界遵守与收尾

| 项 | 实际执行 |
| --- | --- |
| 范围 | 仅本机 PC 蓝牙适配器 + 指定测试手机；未安装任何新测试工具（`winrt` 仅装入项目内 `.cache/p3-3-t1b/venv`） |
| 额度 | 三种策略各 1 次写；未使用亦未重置 T1a/A1 额度 |
| 系统设置 | 未重置系统蓝牙、未清配对、未清应用数据；用户按授权开启手机免打扰 |
| 进程 | 实验结束后 harness 自行退出（`run_end writes_seen=1 exit_code=0`）、logcat 采集超时退出、无残留 logger；未全局按名杀进程 |
| 设备侧状态 | 手机当前**不持有**该 BLE 链路（`dumpsys bluetooth_manager` 对该地址计数为 0） |
| 设备侧写入披露 | `adb logcat -c` 清空过手机日志缓冲；`uiautomator dump /sdcard/ui.xml` 覆盖过手机侧同名文件（Android 标准落点，非项目产物） |
| 宿主机 | 未启动 PowerShell；未做项目外写入（唯一项目外工具 `adb.exe` 未被修改） |
| 项目内产物 | 全部落在 `.cache/p3-3-t1b/`（runs/、venv/、探针脚本）与 `docs/ota-exec-notes/tools/p3-3-b1m/` |
| Git | 未提交、未推送、未合并、未打标签；正式验收保持 `NOT_RUN`；T2 仍 `ENV_BLOCKED` |

## 8. 后续（不在本报告范围）

- **T1a 侧**：OTA_MONO 五事件插桩 → 与 `74f8814` 一次推送至独占 dev 分支 → 跑
  `flutter-dev-checks.yml` 取 dev debug APK → 按最终 headSha 核对双宿主与 APK → 再执行
  最多 1 次 A1 观测（§2.2 六项前置逐项核对）。**尚未开始**。
- 若需分离 §6 中 r21 的 20 s 终结主体，需另行授权一轮 `--window 40` 观测。
