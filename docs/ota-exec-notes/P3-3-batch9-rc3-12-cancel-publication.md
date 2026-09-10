# P3-3 第九批 RC3-12：取消文案的提前发布与历史记录纠正

范围：`app/bluetooth_flutter_Trace`（Flutter OTA 应用层）。
本笔记只记录 RC3-12 这一项：取消路径的可观测状态发布时机、历史记录纠正，
以及用例如何鉴别修复前后的行为。MCU/协议/冻结契约未改动。

## 1. 结论

- 用户取消路径上，**旧 owner 的退出分支不再发布任何文案**；`phase=cancelled`
  与「操作已取消」文案仍由 `cancelUpgrade` 在包清理完成后同段发布（第八批
  已修，本批保留）。
- 非用户来源的 `CANCELLED`（fail-closed）分支同样不再写 `_upgradeStatus`：
  旧实现无条件写 `BLE 传输失败: ${e.message}`，会把 `failClosed` 刚发布的
  「设备复核失败（后台恢复），升级已终止，可重试续传」覆盖成通用链路失败
  文案。该分支的 `phase=cancelled` 收尾语义**未改**（不改既有可重试语义）。
- 用例改为观测取消窗口内的**全部** `upgradeStatus` / `phase` 发布，而不是
  只匹配最终取消文案；并新增一条 fail-closed 文案不被覆盖的断言。

## 2. 历史记录纠正（复审意见成立）

第八批实现报告曾称 `3e10311` 不存在提前的 `cancelled` 赋值。该说法**错误**，
不能用修改后的文件反推修改前的状态。直接用原始对象复核
（`git show 3e10311:app/bluetooth_flutter_Trace/lib/services/ota_service.dart`）：

| 3e10311 行 | 内容 | 时机 |
| --- | --- | --- |
| 630 | `_phase.value = OtaPhase.cancelled;`（`OtaDownloadException` 的 `CANCELLED` 分支） | 下载清理前 |
| 707 | `_phase.value = OtaPhase.cancelled;`（`DioException` 的 `CancelToken.isCancel` 分支） | 下载清理前 |
| 930 | `_upgradeStatus.value = 'BLE 传输失败: ${e.message}';`（`OtaTransportException` 捕获首行，**无条件**） | ABORT/清理前 |
| 941 | `_phase.value = OtaPhase.cancelled;`（上者 `else` 分支，用户取消与 fail-closed 共用） | ABORT/清理前 |

正确表述：**旧问题存在**——三处（下载两处 + 传输一处）都抢在清理前发布
`cancelled`，传输一处还抢发失败文案。第八批修复了其中 630/707/941 三处
phase 赋值（改为静默或按代次限定），本批补齐第 930 行的文案发布。

## 3. 取消窗口内的发布点清单

| 位置 | 取消时的行为 | 处置 |
| --- | --- | --- |
| `ota_service.dart` 下载 `OtaDownloadException` `CANCELLED` | 直接 `return false`，不发布 | 第八批已修，保留 |
| `ota_service.dart` 下载 `DioException` cancel | 直接 `return false`，不发布 | 第八批已修，保留 |
| `ota_service.dart` 目标身份复核 `_RebootKind.cancelled` | 直接 `return false` | 既有，保留 |
| `ota_service.dart` 传输 `OtaTransportException` 用户取消分支 | 本批改为**不写文案**（原为无条件写） | 本批修复 |
| `ota_service.dart` 传输 `OtaTransportException` fail-closed 分支 | 本批改为**不写文案**（保留 `phase=cancelled`） | 本批修复 |
| `cancelUpgrade` 尾部 | 清理后同段发布文案 + `phase` | 第八批已修，保留 |
| `ota_upgrade_page.dart` 进度卡 | 直接渲染 `upgradeStatus`，无自有取消文案 | 无需改动 |

## 4. 用例鉴别力

`test/ota/ota_service_upgrade_test.dart`（RC3-12 取消原子性用例）：

- 监听 `upgradeStatusRx` 与 `phaseRx` 的**每一次**发布，并记录发布时刻的
  `pkgFile.existsSync()`。
- 窗口内断言：发布的文案中不得出现含「取消」「失败」的取值；发布的 phase
  中不得出现 `cancelled`/`failed`。旧实现在此处发布
  「BLE 传输失败: OTA 传输已取消」，该断言是其鉴别点。
- 收尾断言：`操作已取消` 只发布一次、且是最后一次发布，其发布时刻包文件
  必须已删除。
- 新增（fail-closed 文案）：`startFuture` 完成后断言
  `upgradeStatus == '设备复核失败（后台恢复），升级已终止，可重试续传'`。
  `startFuture` 已完成说明旧 owner 的 catch 已跑过，断言不在竞态窗口内。

## 5. 未做与不做

- 未把 fail-closed 的 `phase=cancelled` 改成 `failed`，未改其可重试语义。
- 未改 UI 契约（`upgradeStatus` 直接渲染、`cancelled` 不显示进度行）。
- 未触碰 `ota_ble_transport.dart` 的取消异常文案本身（`OTA 传输已取消`是
  传输层的错误描述，问题在于谁在何时把它当成 UI 文案发布）。
