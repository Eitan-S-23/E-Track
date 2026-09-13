# P3-3 码表页扫描接真实 BLE 修复与本轮验收作废记录（2026-09-14）

## 1. 用户决策（本轮唯一权威指令）

用户在 O2 实机验收进行中发现受验 App 码表「设备」界面点「扫描设备」后永远只显示
三台假设备（iGPSPORT BSC300_1234 / SR30_5678 / HR40_9012，假详情页写死
「已连接 / 固件版本 v1.23.0 / 电量 100%」）。经三次质疑后，用户于 2026-09-13
约 23:40（本地）明确决策：**「现在立刻修，验收重来」**。

- 中止本轮 O 序列验收（当时 O1 已完成、O2 进行中）。
- 立刻修复码表页扫描，接真实 BLE。
- 修复后重新构建受验 APK（需用户授权新额度）、重新冻结合同 v4、O1-O5 全部重跑。

## 2. 假设备根因（源码定位）

受验 App 导航：`MainAppPage` 设备 tab → 大圆盘舞台 → 「码表」节点 →
`SpeedometerPage`（`lib/pages/speedometer_page.dart`）。其内部 tab 3（设备）
原实现为高保真演示稿，未接任何真实功能：

- `_AvailableDevicesPanel`：三行写死 `_DeviceRow`（iGPSPORT BSC300_1234 /
  SR30_5678 / HR40_9012），onTap 进假详情页 `_RideDeviceDetailPage`。
- `_RideDeviceDetailPage` → `_ConnectedDevicePanel` 写死「已连接」
  「固件版本：v1.23.0」「电量：100%」；`_DeviceInfoPanel` 写死 SN1234567890。
- `_TopChrome` 设备名写死 'iGPSPORT BSC300'，isConnected 为假值
  （`selectedIndex != 3`）。
- `_DevicesPage` 扫描按钮是本地布尔翻转（`_scanning`），不触发任何 BLE 调用。

实机证据：`.cache/p3-3-device-execute/20260913-r1/o2-screen-livecheck.png`
（受验版码表页设备子页截图，三台假设备行可见）。
真实 BLE + OTA 链此前挂在「功率计」线（PowerMeterPage → DeviceDetailPage →
OtaUpgradePage），码表线未接——这是 UI 集成缺口，不是 OTA 功能缺陷。

## 3. 修复内容（提交 3b5dd4b，分支 dev/flutter/apk/p3-3-admission）

单文件改动 `lib/pages/speedometer_page.dart`（+171/-555，EOL 全 CRLF 无伪变更）：

1. **_DevicesPage**：接入 `BleController`（Get.put permanent，沿用
   power_meter_page 既有惯例）；进入设备子页 postFrame 自动开扫
   （`startScan()` 自带权限申请与蓝牙状态检查，失败 snackbar 提示）；
   扫描/停止/刷新改调真实 `startScan()`/`stopScan()`；UI 状态由
   `isScanning` 真实值经 Obx 驱动。
2. **_AvailableDevicesPanel**：删三行写死假设备，改由
   `discoveredDevices`（RxList，跨页累计）驱动；名称取 `getDeviceName`
   （advName 回退 platformName），空名兜底 remoteId；RSSI 经
   `_rssiBars`（0→1，≥-55→4，≥-70→3，≥-85→2，else 1）映射 1-4 格；
   已连接设备 type 列显示「已连接」；行点击/「详情」按钮进真实
   `DeviceDetailPage(device:)`（含连接控制与固件升级入口）。
   空列表显示空状态（正在搜索/暂未发现设备）。
3. **_TopChrome**：删 `selectedIndex`/`isConnected` 假参数，改 Obx 由
   `connectedDevices` 真实驱动「已连接/未连接」与设备名；点击进
   `_openFirstConnectedDeviceDetail`（无连接设备时 toast 提示）。
4. **删除死链块 411 行**（Python 按锚点字节删除，行 7800-8210）：
   `_RideDeviceDetailPage` / `_ConnectedDevicePanel` / `_DeviceInfoPanel` /
   `_DeviceFirmwareUpdateRow` / `_DeviceSettingRow` / `_DeviceSwitchRow` /
   `_DeviceRowBase`。grep 确认零残留引用、'iGPSPORT' 字符串零残留。
   `_DeviceScreenLine`/`_SignalBars`/`_DetailTopBar`/`_DetailInfoRow` 被
   缩略图与路线详情页复用，保留。
5. `_showDeviceMoreActions`「设备详情」项改调
   `_openFirstConnectedDeviceDetail`；`_showDeviceSyncActions`
   「检查固件更新」项（真实 `OtaUpgradePage()` 入口）保留不动。

静态自检：已删类零残留引用；`_ScanPanel`/`_showMissingDeviceActions` 签名
匹配；`dart:async`（unawaited）既有导入；`_DeviceThumbnail` 对未知 kind
兜底码表缩略图。本机无 Flutter SDK，编译验证依赖 flutter-dev-checks CI。

## 4. 本轮验收作废范围（如实登记）

| 项 | 状态 | 作废原因 |
|---|---|---|
| O1（latest/证书观测） | 已完成，证据在 20260913-r1/ | 用户决策中止本轮 |
| O2（download/激活时序） | 进行中停止（logcat 已停，日志保留） | 同上 |
| O3/O4/O5 | 未启动 | 同上 |
| 冻结包 R1（bundle_commit=421bd290，索引登记 3a982b0，contract_sha256=859151770E46A68BABFDA4F12D2CD288DD9625EF5BD93B16517DC04281DCCD38，round_id=P3-3-V3-FREEZE-20260913-R1） | 作废 | freeze_commit=a178ecc 后 profile 内出现新提交 3b5dd4b，执行门禁必红 |
| 受验 APK（versionCode=86，SHA-256 c1c89084…） | 作废 | 源码已变，重跑必须用新构建 |

O2 停止动作：后台 logcat 采集任务已停（2026-09-13 约 23:45），日志文件保留
在 20260913-r1/ 作为作废轮证据，不参与任何后续判定。

## 5. 后续路线（待执行）

1. flutter-dev-checks CI 绿（run 34767437874，2026-09-13T16:03:36Z 触发）。
2. 向用户申请新受验 APK 构建额度（build-only 唯一笔已消耗；新构建走
   build.yml dispatch，注入链不变：applicationId `com.wen.gaia.gaia.p33acceptance`
   + Quick Tunnel endpoint）。
3. 重新冻结合同 v4（新 freeze_commit=3b5dd4b 起点之后、freeze_tree、
   profile_config_blob；task_id 不变，parent_contract_sha256 绑定 v3 合同）。
4. O1-O5 按 v4 合同全部重跑（配额按新合同重置口径与用户确认）。
5. 时间约束：Quick Tunnel 8h 窗口至本地约 04:26；若重跑超窗需重启隧道，
   新隧道域名将进入 APK 构建输入（endpoint 注入链级联），意味着再一轮
   APK 构建——需在窗口内完成或向用户申请追加。

## 6. 会话操作记录

- 2026-09-13 23:40 用户决策修复+验收重来。
- 2026-09-13 23:45 停止 O2 logcat 采集。
- 2026-09-14 00:0x 完成 speedometer_page.dart 全部 10 处编辑与静态自检。
- 2026-09-14 00:03 提交 3b5dd4b 并推送，触发 flutter-dev-checks run 34767437874。
- 2026-09-14 00:06 首轮 CI 双宿主 analyze FAIL（唯一 issue：
  `lib/pages/speedometer_page.dart:46:15 prefer_const_constructors`——
  `_TopChrome` 无参化后外层 Padding 可整体 const 化；tests 双宿主 PASS）。
  提交 9e619a6 修复（`const Padding(...)`，内层 const 一并去除避免
  unnecessary_const），触发 run 34767809400。诊断证据：
  `.cache-ci/devchecks-34767437874/.../logs/analyze.log`。

## 7. 第二轮整改：用户实测反馈 4 项 UI 问题（2026-09-14）

新受验 APK（run 34768946670，versionCode=86，包名
com.wen.gaia.gaia.p33acceptance，SHA-256
56301807a9a26583c1d55ead1ca67e55faf7c8a2f4a1452f95c402b39225a31b，
46,682,584B）安装后，用户亲自实机导航验证（此前已明确由用户接管实机
调试，agent 不再用 adb 操控），于 2026-09-14 上午反馈 4 项问题，要求
一次性改完（每轮 UI 改动→新 APK 构建需消耗用户授权额度，避免多轮）：

1. 设备图标应按蓝牙广播内容分类（广播名含「手表」用手表图标等）。
2. 点击设备进入的详情页照搬功率计浅色页，需改为码表风格。
3. 列表行只有「详情」按钮没有「连接」按钮，连接要绕进详情页底部。
4. 「可用设备」右侧刷新按钮与上方「扫描设备」按钮功能重叠，删除。

### 整改实现（提交 4156cf2，两文件 +446/-99，全 CRLF 字节编辑）

- `lib/controllers/ble_controller.dart` 新增 `getDeviceCategory`：
  广播名+平台名关键词分类（watch/heart/earphones/power/cadence/speaker/
  phone/tv/keyboard/mouse/beacon/computer，中英文关键词），标准 GATT
  服务 UUID 兜底（180d→心率、1818→功率、1816/1814→踏频）。分类顺序
  经误匹配自查（earphones 先于 phone/power，避免 'headphone'/
  'Powerbeats' 误判；'bsc'/'mega'/'car' 等高危子串不入表）。
- `lib/pages/speedometer_page.dart`：
  - 新增 `_CategoryDeviceThumbnail`：computer→既有码表造型
    `_ComputerDeviceThumbnail`、heart_rate→既有 `_HeartRateDeviceThumbnail`，
    其余类别深色圆角容器+Material 图标（Dart 3 record 解构）。
    删除误传 kind（type 字段）的 `_DeviceThumbnail` 与失去调用方的
    `_RadarDeviceThumbnail`——原 bug 根因即 `_DeviceRow` 把
    type（'已连接'/MAC）传给 kind，永远落到码表缩略图兜底。
  - 新增码表线深色详情页 `_SpeedometerDeviceDetailPage`
    （_RideColors.background 深底 + _GlassPanel 玻璃拟态 + _DetailInfoRow
    信息行，Obx 响应连接态；含连接控制与「检查单片机固件更新」入口
    →OtaUpgradePage(connectedDevice:)，保育 O2-O5 验收操作路径）。
    顶栏入口与列表行入口全部切换；功率计线 DeviceDetailPage 不动。
  - `_DeviceRow` 新增可空 `onConnect`：未连接且 isConnectable 时显示
    橙色填充「连接」按钮直连（已连接/不可连接时隐藏）；信号格
    _SignalBars 移入名称行腾出按钮宽度；按钮 64x38/fontSize 14。
  - 删「可用设备」标题行刷新按钮（IconButton→const Align 左对齐标题）；
    `_refreshDevices` 保留供 `_showMissingDeviceActions` 帮助页复用。
  - 删 `device_detail_page.dart` import（码表线零引用后）。

编辑脚本：`.claude/p33_r3_ui_fix.py`（一次性资产，不入提交）。自检：
两文件 LF-only=0；`_DeviceThumbnail`/`_RadarDeviceThumbnail` 类与调用
零残留；`DeviceDetailPage(` 仅存于 `_SpeedometerDeviceDetailPage` 前缀
内；onRefresh 终态 3 处（帮助页声明/调用/传参）；Icons.refresh 终态
1 处（帮助页「重新扫描」项）；三处类边界拼接结构完好。

### 验证与后续

- flutter-dev-checks run 34771695273（4156cf2，2026-09-13T17:28:27Z 触发）
  结果见下方追加记录。
- CI 绿后：向用户申请新受验 APK 构建额度（上笔「授权」已消耗于
  56301807 APK）→ 新 APK 构建→手机替换安装→用户实测 4 项整改效果
  → v4 合同重冻结（freeze_commit=4156cf2 或其后）→ O1-O5 重跑。

### CI 结果（2026-09-14 本地约 01:50 追记）

flutter-dev-checks run 34771695273（4156cf2）双宿主全绿：

- Flutter self-tests (ubuntu-latest): success
- Flutter self-tests (windows-2022): success

四项整改（广播分类图标/深色详情页/行内直连/删刷新按钮）通过
analyze+tests 双宿主验证。下一步：向用户申请新受验 APK 构建额度。
Quick Tunnel ideas-coastal-province-enrollment 实测 curl exit 35
（SSL connect error，HTTP 000），存活状态待诊断。

## 8. 第三轮 Quick Tunnel + 服务重建（2026-09-14 01:48）

第二轮运行时资产（隧道 ideas-coastal-province-enrollment + 服务，
00:30-00:31 重建）在 00:33 D2 检查后死亡：cloudflared 与服务进程均
不存在（tasklist 零匹配），curl 出口 exit 35（SSL connect error）。
死轮日志归档为 tunnel-r2-20260914.log / service-r2-20260914.log。

第三轮重建（01:48，同链路同参数）：

| 项 | 值 |
|---|---|
| Quick Tunnel 公网地址 | `https://started-monitors-shower-cherry.trycloudflare.com` |
| cloudflared 进程 | PID 11312（pidfile tunnel.pid，--no-autoupdate，--url http://127.0.0.1:8443） |
| 受控 v2 服务 | 127.0.0.1:8443，--active-release toy-30201，--public-base-url = 新隧道地址；启动行双 fixture 核验通过（toy fc4ae5a9…/284092、real 0a2eb26a…/284112） |
| D2 宿主端到端 | 14/14 ALL PASS（quicktunnel-hostcheck-r3.log；latest 200+schema v2+30201、downloadUrl https 前缀、下载 284092B+SHA 一致、证书链默认信任库校验、4 个未知端点 404） |
| 预计 8h 窗口 | 至本地约 09:48 |

新域名将进入下一轮受验 APK 构建输入（firmware_latest_url 注入链），
等用户授权新构建额度后执行 build.yml dispatch。

## 9. 第三轮受验 APK 构建+身份实测+装机（2026-09-14 02:0x）

用户授权新构建额度后派发 build.yml（同注入链，新隧道 endpoint）：

```
gh workflow run build.yml --ref dev/flutter/apk/p3-3-admission
  -f publish_release=false -f replace_existing_release=false
  -f firmware_latest_url=https://started-monitors-shower-cherry.trycloudflare.com/api/public/firmware/latest
  -f release_application_id_suffix=.p33acceptance
```

- Run 34772842511：Build Android APK / Build Windows EXE 均 success；
  Deploy GitHub Pages 与 Create GitHub Release 均 skipped（参数生效）。

身份五元组（全部本机实测）：

| 项 | 实测值 |
|---|---|
| 文件 | `.cache/p3-3-apk-r3/ble-monitor-android.apk`，46,699,144B |
| SHA-256 | `b9c0bdd5d9c8b7d5c45405bb40cd65ce989109286ad377b069595739c013607d` |
| 包名/版本 | `com.wen.gaia.gaia.p33acceptance`，versionCode=86，versionName=1.0.60 |
| 签名 | v2 scheme Verifies（v1/v3/v3.1/v4 false，1 signer）；证书 SHA-256 `aa1ed438e60da2c45d9b08ed72a831ec6fc63883ddf30eb889802cb1db75880d`（与上轮 c1c89084… 不同，符合跨 run 不可假定相同；O1 双侧比对以本值为受验侧基准） |
| endpoint 注入 | APK 内 2 处 `started-monitors-shower-cherry.trycloudflare.com/api/public/firmware/latest`（grep -a 静态确认） |

装机：卸载旧 p33acceptance（上轮 56301807 版）→ 安装新 APK 双 Success
→ monkey 启动，pidof 确认进程存活（13748），dumpsys versionCode=86 /
versionName=1.0.60。生产包 com.wen.gaia.gaia 全程未动（pm list 并存确认）。

### 写入边界事件（如实登记）

gh run download 下载 APK 时 shell cwd 已脱离 worktree（机制不明），
APK 落在了主仓 `.cache/p3-3-apk-r3/`（越界）。发现后立即 mv 回
worktree `.cache/p3-3-apk-r3/`；主仓侧目录已空，但空目录壳被残留
句柄占用暂无法 rmdir（仅空目录，无内容损失），待句柄释放后清理。
隧道/服务/D2/归档日志等其余资产核实均在 worktree 内，无其他越界。

### 待用户实测

手机上受验 App（p33acceptance）已装好并启动。用户实测 4 项整改：
设备页扫描 → 图标按广播分类、列表行「连接」直连、无刷新按钮、
点进详情页为码表深色风格。

## 10. 第三轮整改：删除列表行冗余详情按钮（2026-09-14 02:2x）

用户实测第三轮 APK 后反馈第 5 项：列表行「连接」按钮右侧的「详情」按钮
与整行点击进详情功能重复，要求删除。

- 改动：`speedometer_page.dart` `_DeviceRow` 删除详情 OutlinedButton 块
  （Python 字节编辑，711B/17 行，单处替换 count==1 断言；CRLF 完好、
  `'详情'` 按钮文本零残留、`'连接'` 保留 1 处、类结构闭合完好）。
- 详情入口保留为点击整行（onTap 不变，仍进 _SpeedometerDeviceDetailPage）；
  已连接/不可连接设备行无按钮，整行点击进详情。
- 提交 bed3aa0，推送触发 flutter-dev-checks run 34774089038。
- 首次脚本运行因自检断言本身写错（永假式）中断，文件未写入无副作用，
  修正断言后重跑成功。

## 11. 第四轮受验 APK 构建+身份实测+装机（2026-09-14 02:4x）

用户授权后派发 build.yml（bed3aa0，注入链同第三轮、隧道域名未变）：

- Run 34774834925：Build Android APK / Build Windows EXE 均 success；
  Deploy GitHub Pages 与 Create GitHub Release 均 skipped。构建 9 分钟。

身份五元组（全部本机实测，显式绝对路径下载，无 cwd 漂移）：

| 项 | 实测值 |
|---|---|
| 文件 | `.cache/p3-3-apk-r4/ble-monitor-android.apk`，46,699,144B |
| SHA-256 | `d241f7ca2fe5da80d0aaaaaf197b10c0433fb16f12da23f38dbbe4d8c47a0df0`（与上轮 b9c0bdd5… 不同，确认为新内容构建） |
| 包名/版本 | `com.wen.gaia.gaia.p33acceptance`，versionCode=86，versionName=1.0.60 |
| 签名 | v2 scheme Verifies（1 signer）；证书 SHA-256 `fe0664a64d718f5def70cffbda760a1777daa9e2c869c30db0e8d12c5ea72ff3`（第三轮 aa1ed438→本轮 fe0664a6，跨 run 新 debug 证书；O1 受验侧基准以本值为准） |
| endpoint 注入 | 2 处 `started-monitors-shower-cherry.trycloudflare.com/api/public/firmware/latest` |

装机：设备 10ADA4197U001CK，卸旧 p33acceptance → 安装 Success →
monkey 启动，pidof 29948，dumpsys versionCode=86/versionName=1.0.60。
生产包 com.wen.gaia.gaia 未动。

待用户复测 5 项整改（图标分类/行内连接/无刷新按钮/深色详情页/
列表行无详情按钮——详情入口为点击整行）。


## 12. r3 隧道死亡登记与真机 latest 请求固化（2026-09-14 03:1x）

### r3 隧道+服务死亡（03:12 左右）

r3 Quick Tunnel（started-monitors-shower-cherry）与受控服务 python 进程
于本地 03:09-03:12 间双双死亡（tasklist 零匹配；tunnel.log 无正常 shutdown
行，进程无声消失）。tunnel.log 死亡时间轴（共 7 条 ERR）：

- 2026-09-13T19:09:41Z（本地 03:09:41）首个 datagram 错误：UDP 超时
  （no recent network activity，IPv6 2606:4700:a8::8）——距最后一次成功
  请求（03:08:27 参数缺失 400）约 1 分钟。
- 19:10:00Z-19:10:47Z QUIC 拨号连续超时（IPv4/IPv6 交替）。
- 19:11:30Z wsasendto: A socket operation was attempted to an
  unreachable network（UDP 网络不可达）。
- 19:11:33Z 最后一次重注册成功（sjc07）后进程消失。

根因链：手机蜂窝/热点链路瞬断（UDP 不可达）→ cloudflared QUIC 断链疯狂
重连 → 进程死亡 → Quick Tunnel 域名随进程永久失效。与 r1/r2 同模式：
本环境蜂窝链路撑不起 Quick Tunnel（r1 约 2.6h、r2 约 3min、r3 约 1.4h）。

### 影响登记

- r3 endpoint（https://started-monitors-shower-cherry.trycloudflare.com/
  api/public/firmware/latest）永久失效，无法通过重启进程恢复（Quick
  Tunnel 域名与进程生命周期绑定）。
- 第四轮受验 APK（d241f7ca…）注入的 endpoint 随之作废：App 检查更新
  将连接失败。O1-O5 在服务路线修复前暂停。
- v4 合同 EXT-HTTP-TEST-SERVICE fingerprint 与 C-RELEASE-BUILD 的
  endpoint 事实随之失效；路线变更须升合同版本（v5）并重新冻结。

### 真机 latest 请求证据固化（装机轮真实观测，服务日志原始行）

装机与用户实测期间，真机 App 共发起两条 latest 请求，均 200（1130 字节，
完整响应含 toy-30201 更新元数据）：

1. 2026-09-14 02:16:26,915（装机后 monkey 启动时段）
   `GET /api/public/firmware/latest?appId=trace&deviceModel=e-track-at32f435&channel=stable&currentVersionCode=30200&currentImageSha=000…000&hardwareRevision=1&layoutId=1&bootVersion=1&protocolVersion=1&appVersionCode=86 -> 200 (1130 bytes) req=b38b8866aa074cf58ee06b6a0462ac8d`
   ——currentImageSha 全 0（App 未连接板卡时的自发起检查）。
2. 2026-09-14 02:45:51,039（用户实测 5 项整改时段）
   `GET /api/public/firmware/latest?appId=trace&deviceModel=e-track-at32f435&channel=stable&currentVersionCode=30200&currentImageSha=4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b&hardwareRevision=1&layoutId=1&bootVersion=1&protocolVersion=1&appVersionCode=86 -> 200 (1130 bytes) req=dae7de1be3b1430b82015a6235de17f1`
   ——currentImageSha 非零：App 已真实 BLE 连接板卡并经 GET_INFO 读到
   当前镜像 SHA 后发起检查更新。该条证明真机链路（App→公网隧道→受控
   服务→返回更新元数据）完整工作，距 toy 闭环仅差下载/传输/重启步骤。
   两条请求不替代 O1 正式观测轮（无伴随采集窗口），作为链路真实工作的
   独立佐证留档。

### 待用户决策

服务路线二选一（两案均需合同 v5 升版+新 APK 构建授权，成本相同）：

- A. Tailscale（*.ts.net 机器名 + Let's Encrypt 证书，默认信任库信任）：
  地址永久固定，进程死亡重连后域名不变——结构性根治蜂窝抖动杀隧道的
  问题。代价：电脑与手机各装 Tailscale 客户端并登录同一账号（免费）。
- B. 重赌 Quick Tunnel（第四条隧道）：零新安装，但按 r1-r3 规律隧道寿命
  约 2 小时，需将「隧道→APK 构建→装机→O1-O5 全程」压入窗口，蜂窝
  再抖动一次即再烧一轮额度。
