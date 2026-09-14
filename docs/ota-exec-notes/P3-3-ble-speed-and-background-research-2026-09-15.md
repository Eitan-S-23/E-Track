# P3-3 实测后新需求研究：BLE 传输提速 + 后台运行/状态栏进度 —— 2026-09-15

> 需求来源：用户 2026-09-15 飞书实测反馈（第六轮受验 APK fb6a91e6，
> 三缺陷实机验证通过后）原文：
> 「实测OTA没有问题，只是存在几个问题1.ble传输很慢不能加快吗？
> 2.网络下载固件包和ble传输时必须要保持软件在前台吗？不能切后台吗？
> 用状态栏显示下载传输进度这样」
>
> 性质：research（编码前落盘）。两项均为 App 侧（flutter_Trace）改动，
> 固件源码与冻结 BLE 帧协议零变更。等用户确认立项后按看板规则立卡实施。

## 0. 实测基线（第六轮实测观测）

- 包体：284,608 B ETU（v6 真包 3.2.3）。
- 传输耗时：约 2~3 分钟（用户体感实测）→ **有效速率约 1.6~2.4 KB/s**。
- 下载（Quick Tunnel 链路）与传输期间 App 须保持前台，切后台即中断。

## 1. 需求①：BLE 传输提速

### 1.1 现状证据（admission worktree，commit ce30190 附近）

| 项 | 现状 | 位置 |
| --- | --- | --- |
| 写模式 | `withoutResponse: !writeWithResponse`（默认无响应写，无逐包应用层 ACK） | `lib/services/bluetooth_service.dart:1330`（writeCharacteristic） |
| MTU | 请求 247（chunk 244 B） | `lib/services/bluetooth_service.dart:1795`（requestOtaMtu） |
| 段大小 | `dataSegmentSize = 128`（DATA 帧载荷，冻结契约） | `lib/ota/ota_ble_codec.dart:89` |
| 窗口 | 32 段（设备 INFO.max_window_segs 上限，冻结契约） | `lib/ota/ota_ble_transport.dart:296-400` |
| 连接优先级 | **全仓 grep `requestConnectionPriority` 零命中——从未请求** | — |
| 传输循环 | 逐段 `await` 写 + ACK/位图回收窗口 | `lib/ota/ota_ble_transport.dart:296-400` |

插件版本：`flutter_blue_plus: ^1.32.11`（pubspec.yaml:37），
`device.requestConnectionPriority(ConnectionPriority.lowLatency)` 完整可用，
零依赖变更。

### 1.2 根因分析

- BLE 从机默认连接间隔由 Android 系统定（BALANCED 档通常 30~50 ms）；
  本 App 从未调用 `requestConnectionPriority`，链路事件频率受限 →
  每秒可调度的连接事件少，吞吐天花板被连接间隔锁死。
- 128 B 段与 32 段窗口是**冻结契约**（`docs/ota-binary-contracts.md`），
  设备端解析依赖，不可改。
- 逐段 `await` 的 method-channel 往返（约 1~3 ms/段）在当前速率下不是
  主瓶颈（2470 段 × 2 ms ≈ 5 s，占总时长 <4%）。

### 1.3 方案

**主抓手（协议零变更）**：OTA 传输开始前调用
`device.requestConnectionPriority(ConnectionPriority.lowLatency)`
（flutter_blue_plus 支持，Android 平台；底层向设备发 LL 连接参数更新请求，
7.5~15 ms interval）。

- 预期：连接事件率 ×3~4，吞吐预计 **3~5 倍**（284 KB 包从 2~3 分钟 →
  **约 40~60 秒**）。
- 传输完成后恢复 `ConnectionPriority.balanced`（降低设备端连接态功耗）。
- **不动冻结契约**：连接参数是链路层协商，非 BLE 帧协议字段；窗口 32、
  段 128、BEGIN/bitmap/ACK 语义全部不变。
- 风险：AT32 端 BLE 栈可能拒绝参数更新请求（从机有权拒绝）。实测确认；
  被拒绝则速率不变（无害降级）。传输日志插桩记录请求前后实际生效间隔
  不可直接读取（Android 不暴露），以**同包传输耗时对比**作为提速证据。

**第二梯队（仅当主抓手实测不足时）**：发送侧流水线化——当前逐段
`await` 写，可改为窗口许可下连发多段再统一等 ACK 回收（协议不变，
仅 App 侧调度）。先实测主抓手再决定是否需要。

### 1.4 工作量

小。`bluetooth_service.dart` 加一个 `requestOtaConnectionPriority()` 方法 +
传输流程（ota_ble_transport / ota_service）在开始/结束处调用 + 传输耗时
日志插桩（秒级起止时间戳落传输记录）。改动约 30~50 行 + 单测（mock
requestConnectionPriority 调用序列）+ CI + 实机验证一轮。

## 2. 需求②：下载/传输切后台 + 状态栏进度

### 2.1 现状证据（原生基建已齐，缺 OTA 集成）

| 项 | 现状 | 位置 |
| --- | --- | --- |
| 前台服务样板 | **`UpdateForegroundService.kt` 已存在**（APK 自更新用）：dataSync 类型、双通知渠道（LOW 进度/HIGH 完成）、`setProgress(100, progress, indeterminate)`、PARTIAL_WAKE_LOCK（1h）、start/stop 静态入口 | `android/.../UpdateForegroundService.kt`（278 行全量实现） |
| Manifest 声明 | `foregroundServiceType="dataSync"`（:39-41）+ `FOREGROUND_SERVICE`/`_DATA_SYNC`/`_LOCATION`（:74-76）+ `POST_NOTIFICATIONS`（:68）+ `WAKE_LOCK`（:71,81）全齐 | `android/app/src/main/AndroidManifest.xml` |
| 通知权限引导 | `requestNotificationsPermission()`（Android 13+ 运行时）已实现 | `lib/services/notification_service.dart:60-72` |
| Dart 通知封装 | NotificationService（flutter_local_notifications ^17.2.2）已有 | `lib/services/notification_service.dart` |
| OTA 下载/传输执行体 | Dart isolate 内（OtaService 下载协程 + OtaBleTransport 传输循环） | `lib/ota/`、`lib/services/` |

即：Android 原生前台服务 + 通知进度条的完整模式在本项目**已为 APK 自更新
落地过一次**，OTA 固件升级缺的只是把同一模式接到固件下载/传输链路上。

### 2.2 方案

1. 新建 `OtaForegroundService.kt`：复用 `UpdateForegroundService` 样板
   （去 APK 安装/FileProvider 分支），通知文案改「固件升级」，进度条
   `setProgress`，渠道独立（`ota_firmware` / `ota_firmware_result`），
   通知 ID 独立（如 2402）避免与 APK 自更新互踩。
2. MethodChannel（现有 MainActivity.kt 已有 channel 先例）暴露
   `start/progress/stop/complete` 四个方法。
3. Dart 侧（OtaService/升级页 controller）：
   - 升级流程开始（下载启动）→ start 前台服务；
   - 下载阶段 → 通知「正在下载固件包 x%」；
   - 传输阶段 → 通知「正在传输至设备 x%」（段级进度已有，映射到通知）；
   - 成功 → 完成态通知（可点击回 App）；失败/取消 → stop。
4. 进度更新节流：通知刷新不高于 1 次/秒（Android 通知刷新开销），
   复用现有进度回调加节流即可。
5. 断连恢复语义不变：现有 BEGIN/bitmap 断点续传机制照旧，前台服务只是
   保活载体。

### 2.3 关键风险

- **厂商省电**：小米/华为等激进 ROM 可能杀前台服务（用户可手动免打扰/
  自启动白名单，文档注明即可，代码无法根治）。
- **Doze 下 BLE**：前台服务 + WakeLock 已是 Android 给的最大缓解；Deep
  Doze（屏幕灭长时间闲置）仍可能断链——传输场景通常分钟级，风险低。
- **Android 15 dataSync 6 小时时限**：分钟级传输远低于时限，无影响。
- **Android 13+ 无通知权限**：前台服务本身不需要通知权限即可保活运行，
  只是进度条不可见——首启引导请求权限（基建已有），拒绝则保活仍生效。

### 2.4 工作量

中等。原生服务 ~150 行（大量照抄现有样板）+ MethodChannel ~60 行 +
Dart 集成（升级页 controller/OtaService 钩子 + 节流）~100 行 + 单测
（Dart 侧调用序列与进度映射 mock；原生通知行为实机验证）+ CI + 实机
验证一轮（切后台传输不中断 + 状态栏进度可见）。

## 3. 验证方案（两项共用）

- CI：flutter-dev-checks 双宿主（analyze+tests）全绿；新增单测覆盖
  ① 连接优先级调用序列（mock）② 前台服务调用序列与进度映射（mock
  MethodChannel）。
- 实机（需用户装机配合，受验包 p33acceptance 覆盖安装）：
  - ① 同一 284KB 包传输耗时前后对比（提速倍数实测）；
  - ② 下载中/传输中切后台（Home 键、息屏）→ 传输不中断、状态栏进度条
    可见且推进、回前台页面状态一致。

## 4. 待用户决策

1. 两项是否立项（立卡进 PLAN-OTA-EXEC.md，属 P3-3 后续增量；
   不动冻结契约，无需阻塞登记）。
2. 已登记待办是否并入同批：升级历史空桩（getUpgradeHistory 恒 `[]`）、
   启动 snackbar 空指针（ble_controller.dart:123，改动小）。
3. 实机验证轮的 APK 构建额度（届时按笔申请）。

## 5. 边界声明

- 本轮纯研究：零代码改动、零真机操作、零云端写入。
- 全部结论援引 admission worktree（ce30190）源码行号与 pubspec 版本。
