# P3-3 复核窗口/版本号显示/按钮截断三缺陷修复研究（2026-09-14）

- 会话: P3-3-IMPL-20260907（实现会话，独占 worktree p3-3-admission）
- 触发: 用户 2026-09-14 实测 O4 后指令——「先修复复核窗口缺陷，此外还有
  软件中显示的版本号不对的问题也请改正，需要为正确的类似3.2.1这样，
  还有有时升级界面会有"重新读取身份啥啥"的一个按钮，这个按钮位于
  "检查更新"按钮的右边，这个按钮显示不全，存在显示截断问题」。
- 背景: O 序列 v5 轮 O2/O4 实测升级链成功但 App 复核环节假阴性
  （详见 `P3-3-o-sequence-execution-2026-09-14.md` §5.3）。

## 1. 缺陷 a：重启复核窗口假阴性

### 机制（实测取证）

`ota_service.dart:1561` `_waitForTargetIdentity`：

- 总窗口 `deadline = now + 60s`（:1570），从传输完成、设备复位前建立；
- 设备复位→BLE 可连接实测：toy 轮 ~67s、real 轮 ≥97s（22:14:41 与
  22:16:17 两次 connect 均 `device is disconnected`，22:27 才连上）；
  60s 窗口内 FBP 扫描回调对目标 MAC 计数 0（广播未恢复）；
- 第一轮探测 connect 抛 PlatformException 后，后续轮 connect 挂起
  （日志静默），外层 `.timeout(remaining)` 兜底耗尽窗口 → timedOut →
  REBOOT_RECONNECT_FAILED → UI 假阴性「升级失败」。

### 修复方案

1. **窗口 60s → 180s**：设备重启恢复（BCB 搬运 ~600KB + 启动 + BLE
   起播）实测 ≥97s，180s 留约 2 倍余量。
2. **单轮探测上限（新增）**：当前单轮 probe 的外层 timeout 用全部
   `remaining`——一轮 connect 挂起即吞掉剩余全部窗口。改为
   `min(remaining, 20s)` 单轮上限（正常成功轮 connect ≤10s +
   discover/MTU/subscribe/INFO 数秒，20s 内可完成；挂起轮最多吞 20s
   后 abandoned，3s 间隔后重试，180s 内仍有多轮机会）。
3. **超时文案改准确**（timedOut 分支）：
   - message 从「设备重启后 60 秒内未确认目标固件在运行」改为
     说明升级可能已完成、设备恢复慢于窗口、可稍后重连确认；
   - `_upgradeStatus` 「等待设备重启复核超时」同步带上时间量。
   retryableLater 保持 true（重新读取身份即解锁，语义不变）。
4. **参数注入化**：`_waitForTargetIdentity` 的窗口/单轮/间隔三个
   Duration 提为 OtaService 构造可注入参数（沿用 bluetoothService/
   downloadDio 等既有注入先例，ota_service.dart:72-81），生产默认
   180s/20s/3s；测试注入短值后可实测「窗口内晚到的目标身份仍确认」
   与「单轮挂起不吞窗口」。

### 测试影响面

- 现有测试无 timedOut 全窗口等待用例（fake BLE 用 `rebootDelayProbes`
  计数模拟延迟身份，`rebootDelayProbes: 1` 仅等 1 个 3s 间隔），窗口
  延长不影响现有测试时长；
- `ota_upgrade_page_test.dart:271/472` 注入 REBOOT_RECONNECT_FAILED
  终止态对象测 UI 样式，不跑真实窗口——message 文案若被断言需同步；
- 新增用例：注入短窗口/短单轮上限实测三态。

## 2. 缺陷 b：版本号显示

### 现状与根因

- 身份卡 `ota_upgrade_page.dart:318` 显示
  `'{deviceModel} • 固件 vcode {currentVersionCode}'`（如
  「e-track-at32f435 • 固件 vcode 30202」），用户期望「3.2.2」式
  版本名；
- BLE INFO 帧 50B 定长（`Libraries/OTA/ota_ble_frame.h`，协议版本 1 +
  model 8B + hw_rev 2B + layout_id 1B + boot_ver 1B + cur_vcode 4B +
  image_sha 32B + max_window_segs 1B）**不含版本名**；固件
  `ota_device_info_t` 无 verName 字段（fw_header 镜像头含 verName
  但未上报 INFO 帧）——显示版本名不能从 wire 报文直接取。

### 方案：App 侧按契约 §0.6 反解（零协议变更）

- 冻结契约 `docs/ota-binary-contracts.md` §0.6（PRE-1 冻结）：
  `version_code = major*10000 + minor*100 + patch`（u32）；
  `Tools/etu_pack.py:79 parse_version_name` 即该算法（30201→3.2.1、
  30202→3.2.2、20801→2.8.1 全部吻合实测）；
- 因此在 `lib/ota/ota_device_info.dart` 的 `DeviceOtaInfo` 加
  `versionName` getter 反解 vcode；`:318` 改显
  `'{deviceModel} • 固件 v{versionName}'`；
- **不动 wire 协议、不动固件、不动冻结契约**——若走 INFO 帧扩展需改
  冻结契约（OTA 规约第 2 条须置卡阻塞），反解方案完全规避；
- `:888` 升级完成卡已显 `latest.versionName（vcode …）`（清单权威
  值），保留不动。

### 风险

- vcode 反解依赖制包端遵守 §0.6 编码——本仓库 etu_pack.py 是唯一
  制包工具且强制校验 minor/patch ≤99，约束闭合。

## 3. 缺陷 c：「重新读取身份解锁」按钮截断

### 现状

`ota_upgrade_page.dart:426-467`：检查更新按钮（padding horizontal 32）
与 OutlinedButton.icon（label 最多「重新读取身份解锁」7 字 + icon）同在
`Row(mainAxisAlignment: center)` 内，Row 无弹性/wrap 处理，窄屏
（或 terminalLocked 态两个按钮同时出现）时总宽溢出被截断。

### 方案

Row → `Wrap(spacing: 12, runSpacing: 12, alignment:
WrapAlignment.center)`：宽度不足时按钮自动换行到第二行居中，不截断。
检查更新按钮保持原样。

## 4. 改动清单（预估）

| 文件 | 改动 |
| --- | --- |
| `lib/ota/ota_device_info.dart` | `DeviceOtaInfo.versionName` getter（§0.6 反解） |
| `lib/pages/ota_upgrade_page.dart` | :318 版本名显示；:426 Row→Wrap |
| `lib/services/ota_service.dart` | 窗口 180s/单轮上限 20s/间隔注入化 + timedOut 文案 |
| `test/ota/ota_service_upgrade_test.dart` | 新增窗口内晚到确认/单轮挂起不吞窗用例 |
| `test/ota/ota_device_info_test.dart` | versionName 反解用例 |
| `test/ota/ota_upgrade_page_test.dart` | 按钮布局（Wrap 存在性）/文案断言同步 |

验证：host 测试（flutter-dev-checks 全档）→ push 独占分支触发 CI。
不新增 APK 构建额度诉求（UI/服务层改动，APK 验证随下轮受验包一并）。
