# P3-3 Flutter 传输与升级 UI 实施 Spec

task_id: P3-3

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-3` 行。本文件不得另行维护该状态。APK 构建继续使用 GitHub Actions，禁止以本地 APK 构建替代验收。

## 目标

把现有“latest 查询 + 下载 + SHA 校验”补成完整 Flutter OTA domain：精确 GET_INFO、设备 DTO、兼容查询、可取消/恢复的固件下载、FFF2/FFF1 BLE transport、credit/续传、进度 UI、重启重连和最终身份复核，并实现 `startOtaUpgrade()`。

## 非目标

- 不在 Dart 中重新声明 BLE 字节 schema；codec 必须引用冻结合同和共享实现。
- 不修改 MCU、D1 migration、发布 workflow 或 admin。
- 不把 OTA 逻辑塞进页面 widget，页面只订阅领域状态和发出用户意图。
- 不在本卡裁定 BLE 性能门槛、App 最低版本语义或 HTTP Range 产品策略。

## 前置依赖

- `P3-1` 提供 MCU transport，`P3-2` 提供可信 INFO。
- Cloudflare latest/download 必须最终符合 `P4-2` 实现的共享合同。
- model、摘要、BLE 调参、App 兼容、HTTP 恢复和 token v2 的用户裁定已传播到共享合同；只有这些候选条款完成独立复核且实现依赖满足后，才能形成正式端到端行为。

## 权威合同

- `OTA-XC-FLUTTER-DEVICE-DTO`
- `OTA-XC-CLOUD-QUERY-MAPPING`
- `OTA-XC-HTTP-LATEST`
- `OTA-XC-ASSET-SELECTION`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-HTTP-RESUME`
- `OTA-XC-HTTP-ERROR`
- `OTA-XC-FLUTTER-TRANSPORT`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-COMPATIBILITY`
- `OTA-XC-UNKNOWN-FIELDS`
- `OTA-XC-RETRY-POLICY`
- `OTA-XC-CANCEL-RECOVERY`
- `OTA-XC-SECURITY`

## 现有组件和代码入口

- `app/bluetooth_flutter_Trace/lib/services/ota_service.dart`：latest、download、size/SHA 校验；`startOtaUpgrade()` 当前固定失败。
- `app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart`：当前硬编码机型和 `0.0.0`。
- `app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart`：跨平台 write/notify、FFF0 服务发现；OTA 不得使用任意特征降级选择。
- `app/bluetooth_flutter_Trace/lib/config/share_links.dart`：firmware latest URL/query 构造。
- `app/bluetooth_flutter_Trace/lib/services/app_update_service.dart` 的 platform `getAppInfo`：可复用读取 App build number 的既有入口，不复制第二套平台通道。
- `.github/workflows/build.yml`：APK analyze/build/产物和 OTA endpoint dart-define。

## 输入输出与调用方向

- 输入：已连接 BluetoothDevice、P3-2 INFO、App build number、latest JSON、下载 asset、用户取消/重试意图。
- 输出：不可变 `DeviceOtaInfo`、typed latest DTO、已校验本地 asset、BLE session 状态、durable progress、最终结果。
- 调用顺序固定为：发现精确特征并订阅 -> GET_INFO -> latest -> compatibility -> download/verify -> BEGIN/DATA/END -> 等待重启 -> 重连 GET_INFO -> 比对目标。
- 页面不得直接生成 query、写 characteristic、解析 ACK 或操作 `.part` 文件。

## 状态机与生命周期所有者

OTA domain service 至少区分 idle、queryingDevice、checkingLatest、downloading、readyToTransfer、beginning、transferring、finalizing、waitingForReboot、reconnecting、completed、cancelled、failed；具体内部名称可不同，但转换必须单向可审计。

- download owner 管本地文件、CancelToken 和摘要。
- BLE transport owner 管 characteristic、notify subscription、seq/session、credit 和重连。
- MCU ACK 是 durable progress 唯一来源；HTTP 下载进度和 GATT 已写字节不得显示为设备 durable 进度。
- 页面销毁不得自动杀死仍由用户确认继续的 service；App 生命周期变化必须走显式暂停/恢复规则。

## 错误、超时、重试、取消、恢复与幂等

- HTTP 按 `OTA-XC-HTTP-ERROR` 和 `OTA-XC-RETRY-POLICY`；未知错误 fail closed。
- 下载恢复只按 `OTA-XC-HTTP-RESUME`；旧 `.part` 必须绑定 assetId/sha/size。
- BLE 按二进制合同 ACK/status 和 P3-4 最终生产参数；不得用固定 delay 代替 credit。
- 断连后重新发现服务、精确绑定 FFF2/FFF1、重新 GET_INFO/BEGIN，并以 MCU durable/bitmap 续传。
- 用户取消：停止 HTTP/GATT 新操作，连接可用时尽力 ABORT；未校验文件删除，已校验包的保留由 UI 明确选择。
- 重复点击开始、系统回调重入和页面重建不得创建两个并发 session。

## 允许修改范围

- `app/bluetooth_flutter_Trace/lib/services/ota_service.dart`，并可拆分 `app/bluetooth_flutter_Trace/lib/ota/` 或职责清晰的 DTO/codec/transport 文件。
- `app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart` 中精确 characteristic 能力和 MTU/连接辅助接口。
- `app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart` 及必要的 UI 状态组件。
- `app/bluetooth_flutter_Trace/lib/config/share_links.dart` 和既有 platform app-info 接线。
- Flutter 单元/widget 测试、fake BLE/HTTP fixture、`.github/workflows/build.yml` 的测试步骤。

## 禁止修改与生产红线

- 禁止保留硬编码机型、版本或测试 URL 作为生产 fallback。
- 禁止选择“第一个可写/通知特征”进行 OTA；必须精确 FFF2/FFF1。
- 禁止在日志中打印完整 signed URL、token、AES key 或用户敏感标识。
- 禁止跳过 length/SHA 校验，禁止让 `.part` 或旧 metadata 进入 BLE。
- 禁止把未知 schema/status/kind 当 success，禁止吞掉 cancellation 后继续写入。
- 禁止本地构建 APK 冒充 Actions 产物。

## 必须新增或调整的测试

- DTO/query：INFO 全字段映射、非法 model/hash/version/proto、无硬编码身份。
- latest：patch、full fallback、no update、channel stopped、client too old、未知字段/错误码、缺 required 字段。
- download：正常、长度错、SHA 错、取消、重试、metadata 变化、最终原子 rename；Range 路径按 `OTA-XC-HTTP-RESUME` 做正反例。
- BLE codec/transport：任意 GATT 分片、ACK credit、丢/乱/重复、seq 回绕、断连恢复、未知状态、并发开始拒绝。
- UI：各状态、双进度区分、兼容阻断、取消确认、重连提示和最终成功/失败。
- Actions：analyze/test/build APK，artifact 可安装性由后续集成会话验证。

## 完成判据

- `startOtaUpgrade()` 对 fake transport 和真机路径均不再固定失败。
- toy 包和正式包都能按合同完成下载、传输、重连和 GET_INFO 复核。
- UI 显示真实设备/版本、下载进度和 durable 进度，不出现硬编码值。
- 所有错误/取消可恢复到确定状态，不留并发 subscription、临时文件或活动 session。
- GitHub Actions 产出通过测试的 APK，真机安装和传输留待 P3-5。

## 停止条件

- 任一受影响共享条款尚未独立复核，或实现依赖尚未完成且必须选择跨系统行为时，停止对应部分。
- Worker 实际 JSON 与共享合同不一致时记录实现缺口，不在 Flutter 建第二套兼容 schema 掩盖。
- 平台 BLE 库不能提供可靠通知/MTU/重连语义时先建立最小可复现证据，不无界换库。
- 需要修改冻结 binary contract 才能继续时停止。

## 后续证据

保存 Actions run/commit/APK hash、Flutter test 明细、fake transport traces、HTTP response fixture hash、下载文件 hash、真机每次 durable_off/bitmap、重连次数和最终 GET_INFO 对比。

## Luna 可自行决定

状态管理内部拆分、typed DTO/Result 类、stream/queue 实现、widget 布局细节、fake 接口和本地文件目录结构，只要不改变合同和现有项目视觉语言。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
