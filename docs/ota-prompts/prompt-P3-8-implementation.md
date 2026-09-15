# P3-8 Android 后台 OTA 与通知进度 Spec

task_id: P3-8

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-8` 行，本文件不复制任务状态。

## 目标

Android 在用户前台发起并完成实际接管后，允许设备 OTA 在正常切应用、下拉通知栏及
锁屏时继续；通知和页面显示同一真实阶段/进度，回前台不重启任务，终态可靠释放资源。

## 非目标

- 不重开 P3-3-v9、不把新功能缺失追溯为旧验收失败，不修改其冻结合同和证据。
- 不承诺用户强制停止、系统终止进程或关闭 Bluetooth 后仍持续运行。
- 不实现 iOS/Windows 同等后台能力，不修改 BLE 字节协议、包格式或性能门槛。
- 不把 App 自更新的安装通知、dataSync 服务或普通本地通知当成设备 OTA 后台能力。
- 不负责 P3-4 的波特率选择和提速，不自动改变 P3-5 的依赖或十次断连判据。

## 前置依赖

- 消费已完成 P3-3 的设备身份、下载、transport、取消和升级后复核链，不创建第二套协议栈。
- 不以 P3-4 或真实 P4-2 部署作为软件实施前置；正式实测的资产、HTTP 输入与设备身份仍须审批绑定。
- 先按根/App AGENTS 确认 Actions 自测入口。设备安装、后台/锁屏操作、OTA 和恢复步骤
  另列操作单、配额与恢复方式取得授权，不沿用 P3-3 的旧额度。

## 权威合同

- `OTA-XC-ANDROID-OTA-BACKGROUND`
- `OTA-XC-OTA-PROGRESS`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-FLUTTER-TRANSPORT`
- `OTA-XC-CANCEL-RECOVERY`
- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-HTTP-RESUME`
- `docs/ota-binary-contracts.md` §5，以及 `docs/acceptance-execution-contract.md`。

## 现有组件和代码入口

- `lib/services/ota_service.dart`：现有 OTA 编排、后台暂停/恢复及最终身份复核。
- `lib/ota/ota_ble_transport.dart`：发送、取消、预算、连接失效与 durable 真相。
- `lib/pages/ota_upgrade_page.dart`：当前生命周期观察与进度展示，只保留 UI 职责。
- `lib/services/bluetooth_service.dart`：严格 GATT 发现、能力和连接代次管理。
- `android/app/src/main/kotlin/com/wen/gaia/gaia/UpdateForegroundService.kt`、`MainActivity.kt`
  和 AndroidManifest：可参考桥接/通知基础，不混用 App 自更新的任务、通知或终态。
- `lib/services/background_task_service.dart` / `notification_service.dart`：核对既有
  扫描和通知职责，避免后台观察者互相取消、重启 BLE 或竞争执行所有权。

## 输入输出与调用方向

页面发起任务，OTA service 建立任务身份并申请 Android 执行接管；原生服务实际确认后
才能宣告后台可用。执行者向页面和通知发布同一只读快照，通知操作返回当前执行者。
语义签名、任务键、快照和取消边界只引用共享合同，不另建不一致的进度或会话模型。

## 状态机与生命周期所有者

同一任务只有一个执行所有者，生命周期独立于页面；实现必须说明 Flutter 引擎或原生
执行器如何保持存活。服务启动请求成功不等于已接管，必须处理异步确认和迟到确认。
已接管时正常后台/锁屏不暂停传输或无进展预算；回前台只重附着当前任务。
接管失败/丢失时仍走既有安全回退，不能简单删除 pauseForBackground。
BLE 阶段按系统要求使用 connectedDevice 服务类型与权限；唤醒锁和服务有界持有。

## 错误、超时、重试、取消、恢复与幂等

- 权限拒绝、通知渠道关闭、服务启动受限或引擎失效必须报告，并保留可行的前台路径。
- 断连和服务失效后重新发现/读身份，按 MCU durable 状态恢复，不把 UI 快照当 session 真相。
- 旧任务的通知点击、取消、进度和接管确认不得污染新代次；重复操作不产生双发送器。
- 取消按钮只在可取消阶段可用，点击时再次核对阶段；MCU 应用/重启后不承诺撤回。
- 进程被终止/强制停止时不伪造完成；下次明确恢复需先复核包、设备和真实 durable 状态。
- 成功、失败、取消、释放均清理前台服务、锁、监听与订阅，不影响 App 自更新或新 OTA。

## 允许修改范围

- `app/bluetooth_flutter_Trace/lib/services/` 内 OTA、BLE、通知及后台入口的必要接线。
- `lib/ota/`、`lib/pages/ota_upgrade_page.dart`，以及现有依赖注入/任务注册的最小接线。
- `android/app/src/main/` 的服务、桥接、Manifest、通知资源与相应 Android 测试。
- 必要的 pubspec/lock 或 Android 构建依赖及 `test/ota/`；新增依赖须说明用途和平台兼容。
- `docs/ota-exec-notes/P3-8-*.md`、看板及本卡后续验收准备资料。
- 修改前一次列清具体文件与共享依赖；不借机重写 App 自更新、云端或 MCU 实现。

## 禁止修改与生产红线

- 不以常亮屏幕、普通通知、dataSync 空壳或删除后台保护冒充后台执行保障。
- 不以手机发送字节、END ACK 或传输百分比代替设备完成；应用/重连阶段不得虚构百分比。
- 不弱化 UUID、CRC、seq、摘要、credit、durable、取消写锁或重连身份校验。
- 不篡改已冻结合同/profile 快照、历史证据或原任务认领；新 runner 须进入真实受审依赖。
- 不新增生产发布、云端写入、安装卸载、AT 改速、烧录或其他硬件权限；不本地构建 Flutter。

## 必须新增或调整的测试

- 接管已确认/延迟确认/被拒、权限拒绝、渠道关闭、服务或引擎失效的状态转换。
- 有效后台任务切换/锁屏/回前台不会重复 BEGIN、重启发送器或让 UI 暂停真实预算。
- 通知与 UI 同源，非 durable 字节不推进设备进度，END ACK 后仍等待最终身份复核。
- 旧通知/旧回调/取消竞态/新任务代次隔离，完成与全部异常路径的资源释放。
- 进程重建恢复不能信任缓存进度、错误包/设备/摘要拒绝，App 自更新通知互不干扰。
- App 全量 analyze/test 与要求的 Actions APK/EXE；Android 原生部分须有可运行测试或
  明确实机观测，不能以 Dart fake 代替平台服务证据。
- 独立真机覆盖正常后台、锁屏、下拉通知/回页面、断连恢复、权限回退与终态清理。
  具体设备/Android 版本、包、时长、事件配额和恢复步骤在执行前统一审批。

## 完成判据

共享合同的后台接管/回退和通知语义均有可信正反例；必要 Actions 实际通过。
真实后台与锁屏期间能观察到 MCU durable 推进，UI/通知与设备事实一致；最后以新连接
GET_INFO 的目标版本与完整 raw SHA-256 判定升级成功，并有服务/锁/订阅收尾证明。
所有 required 判据须按本卡独立合同冻结、执行前检查和最终矩阵校验，不自验收置完成。
阶段耗时、吞吐和无进展截止仍如实记录，不把挂后台停发后的补传冒充连续后台运行。

## 停止条件

发现冻结协议冲突、需要范围外产品改动、无可验证执行所有者、前置权限/设备条件不足，
或操作可能不可恢复时，保留证据并暂停受影响动作。普通实现缺陷集中整改，不反复重开
正式验收；重跑只按实际输入变化、执行合同和剩余额度安排，不盲试或删除不利日志。

## 后续证据

保留提交/Actions run/SDK 与 APK 身份、设备/系统版本、任务键及阶段日志、服务实际接管
与停止证据、通知截图/点击路径、MCU durable/最终身份和恢复记录；日志与产物有 SHA-256。
截图不能单独证明后台继续传输，进程/服务在场也不能代替设备进度与最终身份事实。

## Luna 可自行决定

桥接与类的命名、服务内组织、必要依赖选择、通知布局及更新节流方式由实现选择；
不得改变实际接管先于放行、唯一任务所有者、进度真相、取消和安全回退语义。

## 阻断性决策

无尚未裁定的需求归属。具体设备条件、权限、执行配额和正式合同审批仍是运行前置，
不是已经取得的运行证据，也不因本 Spec 存在而自动授权。
