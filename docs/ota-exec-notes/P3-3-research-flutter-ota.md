# P3-3 Flutter 传输与升级 UI — 集中检查 research 记录

日期：2026-09-07。执行者：Claude(P3-3 实现 agent, P3-3-IMPL-20260907)。
范围：集中检查 + 批量实施派工书 `docs/ota-prompts/prompt-P3-3-implementation.md` 允许的全部产品改动。本文件是编码前 research 落盘（看板 §0 规则 7）。

## 1. 依据与基线

- 基线 main：`0ef3cc14f6fdbece4f15b45864b94cb1007af735`（P3-1/P3-2/P3-6/P3-7 已完成合入，派单状态修正已由治理提交 0ef3cc1 落库）。
- Spec：`docs/ota-prompts/prompt-P3-3-implementation.md`（唯一实施派工书）。
- 冻结条款：`docs/ota-cross-system-contracts.md` §3-§8（OTA-XC-FLUTTER-DEVICE-DTO、CLOUD-QUERY-MAPPING、HTTP-LATEST、ASSET-SELECTION、HTTP-DOWNLOAD、HTTP-RESUME、HTTP-ERROR、FLUTTER-TRANSPORT、BLE-LIFECYCLE、COMPATIBILITY、UNKNOWN-FIELDS、RETRY-POLICY、CANCEL-RECOVERY、SECURITY）+ `docs/ota-binary-contracts.md` §5（帧/CRC16/INFO/BEGIN/DATA/ACK/状态码）、§4.5（会话恢复）、§2.1（etu 外层头）。
- 子项目规则：`app/bluetooth_flutter_Trace/AGENTS.md`（禁本地构建；Actions 验证门禁；Eitan-S-23 推送身份；本机未安装 Flutter SDK，本地连 `flutter analyze` 都不可执行——全部静态检查只能靠代码审阅 + Actions）。

## 2. 集中检查结果（发现清单）

| ID | 发现 | 影响 | 处置 |
|---|---|---|---|
| R1 | `ota_service.dart` 现有 latest 解析是松散 Map（`versionName ?? version`、`sizeBytes ?? file_size` 等别名兜底），flat 字段 `downloadUrl/sha256/fileName/sizeBytes` 在顶层。冻结合同 schema v2 把这些全部挪进 `asset` 对象，且新增 `requestId/releaseId/targetImageSha256/minAppVersionCode` 等必需字段 | 旧解析对 v2 响应必然缺字段抛 FormatException；对旧字段别名容忍违反 OTA-XC-UNKNOWN-FIELDS | 全量重写为 typed `FirmwareLatestInfo` DTO 解析：schemaVersion==2、updateAvailable 分流、asset kind∈{full,patch}（recovery 出现即终止）、错误码白名单、CLIENT_TOO_OLD/兼容 409 终止态 |
| R2 | `downloadFirmware()` 每次 delete `.part` 从零下载、无 sidecar、无 Range、无 If-Range、无 Content-Digest 交叉核对 | 违反 OTA-XC-HTTP-RESUME 全部条款 | 新 download owner：sidecar(assetId/releaseId/sha/sizeBytes/etag)+`.part` 绑定、`localPartSize==size` 走整文件校验、Range: bytes=N-、If-Range 不匹配截断、206/416/ETag 规则、原子 rename、24h 清理 |
| R3 | `startOtaUpgrade()` 固定返回 false（ota_service.dart:234-243），无 BLE transport | 完成判据直接失败 | 新增 `lib/ota/` domain：DeviceOtaInfo DTO + model 映射、BLE codec（A5 5A 帧、CRC16-CCITT-FALSE、seq 回绕、INFO/BEGIN/DATA/END/ABORT 编解码）、BLE transport owner（FFF0/FFF2/FFF1 精确绑定、MTU-3 分片、credit 窗口=当前 4KB 块、durable_off/block_bitmap 续传、重连重 BEGIN）、`startOtaUpgrade()` 状态机 |
| R4 | `ota_upgrade_page.dart:593-596` 硬编码 `deviceModel='igpsport-bsc300'`、`currentVersion='0.0.0'`，且页面 `_checkForUpdate` 无设备连接数据流 | 违反 OTA-XC-DEVICE-MODEL/FLUTTER-DEVICE-DTO（禁止硬编码身份） | 删除硬编码，改为进入页面即通过 GET_INFO 建立快照；无设备/查询失败时检查更新按钮禁用并给出原因，不得用默认身份发请求 |
| R5 | `bluetooth_service.dart` 的 `findTransparentUuidsByAddress` 有"任取第一个可写特征"降级路径（1327-1349 行），remote_control_page 依赖它做透传 | OTA 若复用该函数会踩 OTA-XC-FLUTTER-TRANSPORT 红线第 1 条 | OTA 不复用降级路径：在 bluetooth_service.dart 内新增精确版本 `findExactOtaCharacteristicsByAddress`（FFF0 服务内精确 FFF2 可写 + FFF1 可通知，缺一即 null，无降级）；原 `findTransparentUuidsByAddress` 保留给遥控页不动。移动端另加 `requestMtu` 协商辅助 |
| R6 | 移动端 write 走 `ch.write(..., withoutResponse: !writeWithResponse)`；OTA 需要 FFF2 write-with-response 还是 withoutResponse 合同未指定，但 MTU-3 分片要求按协商 MTU | 传输正确性 | BLE 帧分片写入用 withoutResponse=false（writeWithResponse）逐片确认，速率由 credit 窗口限流而非 GATT 层；这是保守选择，不依赖平台队列行为 |
| R7 | `appVersionCode` query 参数在 `share_links.dart firmwareLatestUri` 中不存在；`currentVersion` 字符串参数被旧页面使用 | OTA-XC-CLOUD-QUERY-MAPPING 要求 appVersionCode 必填 0..2100000000，currentVersionCode 必填非负整数，currentImageSha/hw/layout/boot/proto 必填 | 扩展 `firmwareLatestUri`：typed 参数全部显式传入；App build number 复用 `AppUpdateService` 的 platform `getAppInfo` 通道（不复制第二套平台通道），Android 可读，Windows 通道未实现——Windows 下 OTA BLE 本就走 WinBle 路径，getAppInfo 失败时 fail closed 不发请求 |
| R8 | 项目无 `test/` 目录、pubspec 无 test 依赖之外的脚手架、本机无 Flutter SDK | Spec 要求新增 DTO/query/latest/download/codec/UI 测试 | 新建 `test/` 目录 + `flutter_test` 测试文件；本地无法运行（无 SDK），测试执行留待 Actions（build.yml 无 test 步骤——Spec 允许修改 build.yml 的测试步骤；本地能做的静态检查=逐文件代码审阅 + 与合同字段逐项比对，如实列为未验证项） |
| R9 | build.yml 只有 analyze（continue-on-error: true）+ build，无 `flutter test` 步骤 | Spec「必须新增或调整的测试」要求 Actions 产出通过测试的 APK | 在 build.yml android job 的 Analyze 之后、Clear cached artifacts 之前加 `flutter test`（无 continue-on-error，失败即红）。该文件路径不在 P3-3 卡内但 Spec 允许修改范围明确含 `.github/workflows/build.yml` 的测试步骤 |
| R10 | `cancelUpgrade()` 只取消 HTTP CancelToken，置 `isUpgrading=false`，BLE 无概念 | OTA-XC-CANCEL-RECOVERY 分层归责 | 重建取消路径：HTTP 层 cancel token+删 .part+sidecar；BLE 层停止新写入+尽力 ABORT（连接可用时）+清 session；UI 明确选择是否保留已校验包 |
| R11 | win_ble 路径的 notify 是 250ms 轮询构造的 Stream（bluetooth_service.dart:1149-1186） | OTA ACK 延迟在 Windows 下受轮询粒度影响 | 可接受：Windows 是辅助平台，真机验收在 Android。不修改既有轮询结构（越范围），transport 直接消费该 Stream |
| R12 | P3-3 任务卡验收要求"真机 toy/真包传输"，Spec 末条把真机安装/传输留 P3-5 | 验收归属差异 | 按 dispatch-readiness 记录处置：实现覆盖 fake transport 测试与真机路径代码，真机观测不在本卡实施内冒充；正式验收冻结前由非实现主会话确认归属 |
| R13 | 9 个未跟踪文件 + .P3-5 空文件在工作区 | 写入边界 | 全部原样保留不动，不纳入本卡任何提交 |

## 3. 修改文件清单（映射 Spec 允许范围）

| 文件 | 动作 |
|---|---|
| `app/bluetooth_flutter_Trace/lib/ota/ota_device_info.dart` | 新增：DeviceOtaInfo 不可变 DTO + wire model→deviceModel 映射 + INFO 50B payload 解析 |
| `app/bluetooth_flutter_Trace/lib/ota/ota_ble_codec.dart` | 新增：A5 5A 帧编解码、CRC16-CCITT-FALSE、seq 回绕比较、INFO/BEGIN/DATA/END/ABORT/ACK 各 payload |
| `app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart` | 新增：BLE transport owner（精确 FFF2/FFF1 绑定、订阅、分片、credit、ACK 解析、重连恢复） |
| `app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart` | 新增：latest schema v2 typed DTO + fail-closed 解析 + 错误码/终止态模型 |
| `app/bluetooth_flutter_Trace/lib/ota/ota_download.dart` | 新增：download owner（sidecar、Range/If-Range、摘要、原子 rename、保留策略） |
| `app/bluetooth_flutter_Trace/lib/services/ota_service.dart` | 重写：状态机编排 + 对外 API 保留兼容签名 |
| `app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart` | 新增精确 OTA 特征发现 + MTU 请求辅助（不改既有降级函数） |
| `app/bluetooth_flutter_Trace/lib/config/share_links.dart` | firmwareLatestUri 扩展 typed query |
| `app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart` | 删硬编码身份、接 GET_INFO/状态机/双进度/取消/兼容提示 |
| `app/bluetooth_flutter_Trace/test/ota_*.dart` | 新增测试（DTO/codec/latest/download 纯 Dart 逻辑 + fake transport） |
| `.github/workflows/build.yml` | android job 加 `flutter test` 步骤 |

## 4. 正反例与判定口径（实现内嵌）

- 正：INFO model 精确 8B `E-Track\0` → `e-track-at32f435`；CRC16 样例向量复算；latest patch 选中条件 `base_image_sha256 == currentImageSha`（raw 域）；`localPartSize==sizeBytes` 不发 Range。
- 反（必须 fail closed）：model 非 ASCIIZ/非 E-Track → `UNKNOWN_DEVICE_MODEL`（不发请求）；INFO image_sha256 非 32B；latest 未知 errorCode/未知 asset.kind/required 缺失/未知 schema major；download 长度或 SHA 不符；BLE 未知 ACK status/未知 proto_ver；特征缺 FFF2 或 FFF1；BEGIN 后 session 不匹配。
- durable 进度：只有 ACK 的 durable_off/block_bitmap 进入 UI durable 显示；GATT 已写/HTTP 已下载字节只进各自进度条。
- 恢复：断连→重连→重新发现特征→GET_INFO（复核 model/身份）→重新 BEGIN（同 package_sha256）→按 MCU 回 durable_off+bitmap 续传（重发 bitmap 中 0 的段）；MCU 回 ABORTED/ERR_* 不可恢复码则终止。

## 5. 环境与操作边界

- 本机无 Flutter SDK：不能本地跑 analyze/test（AGENTS.md 允许的本地检查在本机不可用），全部验证依赖 Actions（需用户授权推送后才能触发）。
- 不执行 git commit/push（主会话职责）；不动 9 个未跟踪遗留文件；不烧录、不碰硬件。
- 所有新文件落在 `app/bluetooth_flutter_Trace/`（lib/test）与 `.github/workflows/build.yml`，均在项目根内。

## 6. 非实现会话集中预审（2026-09-07）

审查者：Codex（本批非实现会话）。用户请求按项目规范验收上述实现交付。

**结论：集中预审不通过，先批量整改；正式验收 NOT_RUN，不得将 P3-3 置完成。**
本节是 acceptance-execution-contract.md §7.3 的准入审查，不是已冻结的正式轮次，
不伪造 PRODUCT_FAIL/EXECUTED 矩阵，也不把 JavaScript 算例当作 Flutter 自测或真机证据。
§1 至 §5 保留实现者原记录；其中“已实现”“覆盖”的声明须以本节实际核查为准。

### 6.1 基线、范围与准入

- HEAD 仍为 0ef3cc14f6fdbece4f15b45864b94cb1007af735；实现位于未提交工作区。
  本次完整读取 10 个相关 Dart 产品文件、6 个新增测试文件及 build.yml，
  并核对 MCU ota_ble_session.c、页面入口、pubspec、合同、Spec 和既有交接记录。
- 未找到 P3-3 版本化验收合同、审批冻结点、证据矩阵或验收派工书。
  不能拿当前 HEAD 为未提交实现背书，不能在此状态运行正式产品观测。
- where flutter / where dart 均未找到工具；未运行 Flutter analyze/test、APK/EXE 构建。
  APK/EXE 按子项目规则只走 Actions；本轮未获提交、推送或 dispatch 授权，未触发 CI。
- 既有卡面仍要求 APK 可安装、真机 toy 包与真包传输；实施 Spec 末条又将真机安装/传输留给 P3-5。
  沿用 dispatch-readiness 记录：不修改或自行豁免这些门槛，正式冻结前须裁定归属。
  无论真机观测归哪张卡，P3-3 代码仍必须实现重连及最终身份复核。
- 正式产品/硬件观测执行次数为 0；无重试消耗。尚无获批正式操作配额，剩余额度不自行设定。
  本次没有前轮 P3-3 冻结合同/矩阵可生成 rerun plan；不重开 P3-1/P3-2/P3-6/P3-7 历史验收。

### 6.2 一次性整改清单

以下均属于本批功能或其必要测试的阻断，不以风格偏好或历史无关债务增加门槛。
“自测证据”列如标未执行，即没有 Dart/Flutter 运行结论；源码推导不是编译器诊断输出。
路径链接相对本文所在目录。

| 发现 ID | 依据/判据 | 影响范围与复现条件 | 批量处置 | 自测证据 |
|---|---|---|---|---|
| PR01 / P1 | Actions analyze/test/build；Spec 必须可编译 | [transport:110](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L110) 将 ack 推断为 OtaAckResult，随后 [152](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L152) 赋入 OtaAckPayload，[157](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L157) 又把 OtaAckResult 传给只接收 OtaAckPayload 的 fromAck。[页面:27](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L27) 使用 FirmwareLatestInfo，却未直接 import DTO，ota_service 也未 export；Dart import 不传递导出。[下载测试:32](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L32) 调用不存在的 OtaFirmwareAsset()，产品只声明私有构造器。 | 一次修齐产品及测试的类型、构造器和导入错误，再跑完整 analyze/test；不能仅靠新增 test 步骤声称可构建。 | 三组明确的静态类型/API 矛盾；Flutter 未执行，非编译器实测。 |
| PR02 / P1 | OTA-XC-HTTP-LATEST | [asset.parse:154](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart#L154) 对已经取出的 asset Map 查找 asset.assetId、asset.kind 等带点键；[helper:351](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart#L351) 直接 m[name]，不做路径解析。合同和正例 fixture 的键是 assetId、kind 等，所有正常 full/patch 响应第一项即失败。 | 分离字段键与诊断标签；用冻结嵌套结构验证两个正例和每个 required 字段负例，禁止改服务器 schema 来迁就客户端。 | 离线取合同示例和实际 getter 键，8 个带点键全部不存在；现有正例也会遇到该错误，尚未运行。 |
| PR03 / P1 | binary §5.1；任意 GATT 分片 | [transport:331](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L331) takeBytes 清空缓冲；半帧从 offset=0 开始时 break，但 [356](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L356) 只有 offset>0 才回存。20B 通知承载 60B INFO 时首片被直接丢弃，不能 GET_INFO。 | 始终保留未消费尾部；覆盖每个切分点、单字节通知、半帧头、连帧和坏帧后的重同步。 | 源码对应的离线模型：整帧解析 1 帧，3×20B 解析 0 帧；不是 Dart 执行。 |
| PR04 / P1 | binary §5.4/§5.5，4KB 窗口和包尾 | [transport:118](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L118) 及 [162](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L162) 用字节 durableOff 除以段数 32，再乘 32×128。durable=4096 得到下一 offset=524288，而非 4096；8KB 包直接越界 break 后发 END。另 [134](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L134) 向下取整段数，任何非 128 倍数包尾均漏发。 | 统一字节/段/块单位，尾段向上取整；END 前验证 durable 恰等于 total；覆盖两块、大包、durable 非零恢复及短尾。 | 离线算例 4096→524288；129B 尾块只算 1 段，应为 2 段。 |
| PR05 / P1 | binary §5.1/§5.6/§5.7；ACK 是唯一真相 | [waiter:403](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L403) 一问一答只匹配 cmd；[ACK waiter:413](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L413) 对 DATA/BEGIN/END 不区分且不核对 seq。迟到 DATA OK 能完成 END waiter；真实 MCU 每段 ACK，而 [131](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L131) 每块仅接首个 ACK，后续进度在已完成 waiter 上丢失。ACK_ABORT/异步 ABORTED 未分发；ERR_SEQ 不对齐，ERR_SESSION/ERR_STATE 不重 BEGIN，durable/bitmap 未验证范围。 | 按操作、session、seq 关联响应，持续消费并验证 ACK；区分错误处置，不把其他命令 OK 当 END；保留可解释的最后 ACK，覆盖迟到/乱/重复/丢 ACK、序号缺口及回绕。 | 已对照 [MCU 每段 ACK:573](../../Libraries/OTA/ota_ble_session.c#L573)、[seq 检查:272](../../Libraries/OTA/ota_ble_session.c#L272)、[ACK_ABORT:707](../../Libraries/OTA/ota_ble_session.c#L707)；未运行 BLE。 |
| PR06 / P1 | OTA-XC-FLUTTER-TRANSPORT 精确 FFF0/FFF2/FFF1 红线 | 新发现函数 [1386](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1386) 复用了 [1646](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1646) 的模糊比较器，任意 128-bit UUID 都只截第 4..7 位比较，并未校验 Bluetooth Base UUID。非标准服务/特征也能冒充 FFF0/FFF2/FFF1。 | OTA 使用严格 UUID 规范化，仅允许真正标准 Base 的短长格式等价；同时绑定实际支持的 write mode，不能接受仅 withoutResponse 却强制 withResponse。遥控降级行为不得被顺带破坏。 | 离线模型接受 1234fff0-1111-2222-3333-444455556666 为 fff0；标准 Base 正例也被接受，反例有区分依据。 |
| PR07 / P1 | OTA-XC-BLE-LIFECYCLE；Spec 最终成功链 | [service:351](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L351) 一见 END OK 就置 durable=100%、显示“固件升级完成”并返回 true。没有 waitingForReboot/reconnecting，也没有比较新 GET_INFO 的目标 versionCode/raw image SHA；设备尚未安装、回滚或未重启同样显示成功。 | END 仅标包传完；完成重启/重连/GET_INFO/目标比较后才能 completed。明确等待失败、回滚、断连和身份不符的终态。 | 静态全调用链确认：唯一成功出口在 END 后；targetImageSha256 不参与升级后比较。 |
| PR08 / P1 | OTA-XC-CANCEL-RECOVERY；Spec 并发禁止 | [cancelUpgrade:389](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L389) 只发 ABORT 并清 isUpgrading，transport [135](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L135) 的 DATA 循环和 [321](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L321) 的分片循环没有取消检查，可能与 ABORT 交错并继续写。downloadFirmware 没有忙锁；[下载按钮:467](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L467) 不看 isUpgrading，可创建多个 owner 写同一 partial。取消先于 token 注册/写流关闭时，文件清理还存在竞态。 | 单一操作所有者和取消代次/令牌，先停止新写、等待在途操作退出，再 ABORT/清理/释放 busy；所有入口防重入；UI 明确已校验包保留选择。 | 静态核对；无“取消后零 DATA/END/rename”、双击、取消再开始的运行证据。 |
| PR09 / P1 | OTA-XC-FLUTTER-DEVICE-DTO/TRANSPORT；后台与断连恢复 | service/transport 没有 App lifecycle 或真实连接状态监听，没有重连流程；_ChannelAdapter 初值 connected=true，只在通知 error/done 时变 false，写失败也不更新。旧 DTO 没绑定地址/连接代次；[readDeviceInfo:109](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L109) 的两个早退还保留旧 _deviceInfo。 | 后台/断连停止写入、使旧快照失效；恢复须重新发现→GET_INFO→同包 BEGIN→消费 durable/bitmap。通过真实连接状态和代次管理，不能由通知流是否关闭猜连接。 | 对三个新增主文件检索 lifecycle、connectionState、reconnect 无实现；目前只有显式再点开始前的一次 GET_INFO。 |
| PR10 / P1 | Spec subscription/session 所有权和先订阅后 GET_INFO | [bindTransport:439](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L439) 每次覆盖 _transport 而不 dispose 旧对象，正常“进页读身份→开始传输”就泄漏订阅。[subscribeNotify:1191](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1191) 异步 discover/setNotify，但 bind 只取得 Stream，未等待订阅就绪便发送 GET_INFO。transport dispose 也未完成/取消待处理 waiter。 | 一个连接代次仅一个订阅；显式等待 notify ready；重绑、失败、取消、关闭时统一完成 waiter 和释放旧资源，避免旧回调修改新会话。 | 静态核对生产适配器；没有延迟启用 CCCD、重复读身份、页面重建/关闭的测试。 |
| PR11 / P1 | OTA-XC-COMPATIBILITY/UNKNOWN-FIELDS 终止态红线 | [latest catch:206](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L206) 解析错误不终止/清旧资产；[HTTP error:469](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L469) 仅处理 426/409，400 UNKNOWN_DEVICE_MODEL 和其他状态的未知 errorCode 不进入稳定终态。旧 latest/file 可留下；download/start 不检查 terminal，反而主动清它。先查到旧包再收到 426/未知响应，仍能通过旧按钮下载/传输。 | 失败统一分类并保留 requestId/本地码；终止状态与资产、按钮、service 入口一并闭锁，不能由下一次下载清除；只有显式重新建立有效查询链才可解锁。 | 静态状态转移证据；现有测试只测错误 DTO，不测 service/UI 不再产生 HTTP/GATT 副作用。 |
| PR12 / P1 | OTA-XC-HTTP-DOWNLOAD/IMAGE-IDENTITY；已校验包绑定 | [latest 赋值:201](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L201) 换资产不使旧 _firmwareFile 失效；[start:327](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L327) 只重算文件自己的 SHA 发给 MCU，从未与选中 asset 的 size/SHA/release 身份复核。先下载 A、再查得 B 而不重下，可显示 B 却发送 A；下载后文件变化也失去 metadata 身份约束。 | 持有绑定 assetId/releaseId/size/SHA 的 verified package；最新清单变化时失效旧包，BEGIN 前验证当前字节仍匹配该身份；不得将重算结果无条件当作新可信摘要。 | 静态调用链确认，不等同于已观测实机换包。 |
| PR13 / P1 | OTA-XC-HTTP-RESUME/HTTP-DOWNLOAD/HTTP-ERROR | [download:97](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L97) 只看 200/206，完全不校验 Content-Range、Accept-Ranges、Content-Length、If-Range 与强 ETag 一致性或 Content-Digest；[115](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L115) 还会在无/弱新 ETag 时沿用旧值。401/410/409/416 没有重新 latest/作废旧 URL 的流程；完整 partial SHA 错或超长仍直接用旧 URL 重下。24h 清理只扫描 .part，孤立 sidecar 不清。 | 在写入/追加前验证响应头和区间身份；分清 206 body digest 与完整包 digest；按错误码刷新 metadata/URL，并仅在身份和强 ETag 全一致时续传；正确处理孤儿及取消收尾。 | 源码/fixture 核对；mock 的 206 本身缺 Accept-Ranges，且没有实现报告所称的 If-Range 失配返 200、弱 ETag、416、Content-Digest 正反例。 |
| PR14 / P2 | OTA-XC-UNKNOWN-FIELDS/SECURITY/CLOUD-QUERY-MAPPING | [latest:69](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart#L69) 容许 no-update 缺 errorCode；true 分支不检查 errorCode，忽略 appId/deviceModel/channel，targetHardware/transport 当可选；version/baseVersion/size 上界、URL scheme/host、文件名等缺校验。full 缺 baseImageSha256 与显式 null 不区分。query 不验证 channel 枚举。DeviceOtaInfo 缺要求的 wireModel 字段。 | 恢复 required 字段/枚举/范围及输入身份校验；副作用前验证 URL/文件名/尺寸；未知可选字段仍忽略，不发明别名 schema。补全 DTO 字段。 | 静态核对；PR02 修复后须逐字段负例，不能被更早 assetId 错误“代红”。 |
| PR15 / P2 | OTA-XC-RETRY-POLICY/BLE-TUNING | [transport:120](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L120) durableDeadline 是 final，进展后并未重置；传输超过 30 秒后一次无推进 ACK 即可误中止，慢写期间又不检查截止。maxRetries=5 从未使用，DATA ACK timeout=10000ms 超出冻结 500..2000ms 调参范围。metadata receiveTimeout 仍为 5 分钟，无 429 Retry-After/有界重试实现。 | 用单调时钟、真实 lastDurableProgress 与全操作截止；实现状态相关且有界的重试；metadata 15s/20s 和退避按合同；P3-4 最终参数仍待实测，不擅自裁定生产档位。 | 静态检索 maxRetries 仅定义一处、durableDeadline 仅初始化/比较；无 fake clock 或重试次数测试。 |
| PR16 / P1 | Spec UI 状态测试和真实数据展示 | [页面 Obx:99](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L99) 只读取普通 _latestInfo，而 [service:63](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L63) 不是 Rx，也未 update；该 Obx 没有响应式依赖，存在 GetX improper-use 错误，且后续清单变化不能驱动刷新。用中文 status.contains 决定阶段，失败/取消后也没有确定恢复入口。 | 使用明确、可订阅的领域 phase/快照；组件状态由 phase 驱动，不解析日志文案；补 widget 状态、失败、取消、重建测试。 | 静态依赖检查；未运行 Flutter widget/屏幕验证。 |
| PR17 / P1 | Spec 必须新增测试；harness 有鉴别力 | [codec 测试:22](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_codec_test.dart#L22) 把 4 个零字节 CRC 写成 0x2F3E，应为 0x84C0；[218](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_codec_test.dart#L218) 的 LE fixture 实为 durable=0x00400000、bitmap=0x0F，期望却为 0x40000000/0x0F0000。fake MCU [328](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L328) 按调用次数而非位图收齐推进、不在下一块重置计数，[343](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L343) 对未收齐包也无条件 END OK，seq 永远回 0；没有 service/widget/真实断连恢复/取消/并发覆盖。 | 修正独立 oracle，fake 精确模拟 MCU seq、去重、块/尾边界和 END 完整性；同批增加上述失败路径测试。不能只把错误期望改到迁就现实现。 | 独立算法复算上述数值；6 个测试文件存在但未运行，不能称测试覆盖已经验证。 |
| PR18 / P2 | Spec 进入页面 GET_INFO 的实际调用链 | 新页面 [31](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L31) 只从构造参数取地址，为 null 时直接不读身份；[仪表页入口:8258](../../app/bluetooth_flutter_Trace/lib/pages/speedometer_page.dart#L8258) 和 [10472](../../app/bluetooth_flutter_Trace/lib/pages/speedometer_page.dart#L10472) 都仍调用无 connectedDevice 的页面。即便已有蓝牙连接，从这两个入口仍无法检查更新。 | 从可信已连接设备状态传入/解析地址，或明确引导选择设备；补两个入口集成测试。若必须扩改既有入口文件，先按 Spec 确认必要 UI 接线范围，不扩展到无关页面改版。 | 静态交叉引用确认；device_detail_page 的带设备入口已单独保留，不把所有入口混称可用。 |

PR04 的同批边界还包括 INFO.maxWindowSegments：目前 DTO 虽读取该值，transport 却始终按 32 段发送，
没有消费协商上限。应拒绝不支持的 INFO 或正确限制在途段数，不能把“当前 MCU 固定 32”当作忽略输入的理由。

### 6.3 已执行与未执行

实际执行的只读检查包括 git --no-optional-locks status --short --untracked-files=all、
git --no-optional-locks log -6 --format=oneline、git --no-optional-locks diff --stat、
git --no-optional-locks ls-files docs/acceptance-contracts/P3-3* docs/ota-prompts/*P3-3*、
where flutter、where dart，以及逐文件 rg -n、diff、合同和 MCU 调用链核对。
合同文件检索只有实施 Spec；Dart/Flutter 工具检索无结果。

另执行一次 Node 内联源码对照算例（node v24.13.0，exit 0），仅投影字段查找、
整数运算、半帧保留逻辑、UUID 比较及 CRC/LE fixture。
原始结果： [.cache/p3-3-prereview/readonly-probes.json](../../.cache/p3-3-prereview/readonly-probes.json)。
SHA-256：f67ec2fbe82e172b6a36b1165c265b6f81b94f19800eb17277576ef60f46446f。
这是诊断算例，不是被验 Dart 的执行，也不是可复用的正式验收 harness；不得填成 Flutter PASS。

| 算例 | 观测值 |
|---|---|
| 冻结 latest.asset 对实际带点键查找 | 8/8 查询键缺失 |
| durable=4096 的下一块起点 | 实现公式 524288；协议应为 4096 |
| 129B 尾块段数 | 实现公式 1；协议应为 2 |
| 相同合法 INFO 的完整帧/3×20B | 完整帧 1；分片 0 |
| 非 Bluetooth Base 的伪 FFF0 | 比较器返回 true |
| CRC16("123456789") / CRC16(4 个 0) | 0x29B1 / 0x84C0 |
| 测试中 9B ACK 的 LE 解析 | durable=4194304；bitmap=15 |

git diff --check 检出实现者新增的看板证据行末 CR（原行 626），另有两条 LF→CRLF 提示。
这属于非阻断文档/EOL 整理项，不把它升级为产品缺陷；本轮保留原实现证据文本，避免整文件换行伪 diff。
build.yml 的两个 flutter test 步骤没有 continue-on-error，test/ 已进入 app_build_required 分类；
这些是静态接线事实，不是 CI 成功证据。既有 flutter analyze 的 continue-on-error: true 未被本批修改。

没有执行/声称通过：Flutter analyze、Flutter test、widget 测试、Android APK、Windows EXE、
安装检查、真实 latest/download、BLE 传输、重启重连、J-Link、合同/矩阵最终校验。
实现 commit SHA、Actions run URL、APK SHA-256 均尚不存在本批有效证据，不能引用旧运行代替。

### 6.4 后续顺序与写入审计

1. 实现者按 PR01 至 PR18 做一个整改批次，连同相关调用点、fixture、负例一起修；局部自测不算新正式轮次。
2. 提交/推送须另获用户授权；经授权取得同一整改批次的 analyze/test、Android 和 Windows Actions 结果。
   发布/版本号处理仍按 app/AGENTS.md 执行，验收需求不自动授权发布。
3. 确认真机判据归属及操作计划；把实现和所有实际 runner 提交，再按 v3 审批冻结合同和 NOT_RUN 矩阵。
   使用现有 Flutter 组件 profile，并覆盖真正测试/runner 依赖；不为了本卡重开无关固件/硬件或治理回归。
4. 准入通过后才做正式观测、证据封包及 validate_bundle.py；首次正式轮次之后按实际前轮生成最小 rerun plan。

本轮主动写入仅限活动根 D:/github/my/E-Track 内：本研究文档追加本节、PLAN-OTA-EXEC.md
状态/证据/日志，以及 .cache/p3-3-prereview/readonly-probes.json。
写前已对规范化目标与全部已存在父链执行 realpath 和 fsutil reparsepoint 检查；新建日志目录后再次检查。
全部命令显式指定项目工作目录，使用 cmd.exe，不启动 PowerShell、不运行既有临时脚本。
未改产品、测试、workflow 或冻结规范，未提交/推送/部署/烧录，也未清理任何项目外产物。
结束复核已完成：17 个被审源码/测试/workflow 和 9 个遗留文件的 SHA-256 全部与审查时一致。
缓存目录只有上述一份 JSON；三个主动输出文件的实际落盘路径全部仍在活动根内，没有主动项目外写入。
看板保留原有 728 个 CRLF 行尾；只对补丁影响的既有行尾做格式恢复，并断言规范化文本内容未变化。
看板相对 HEAD 为 6 增/2 删（进入本会话时为 3 增/2 删），没有整文件换行伪 diff。
产品/workflow 范围 git diff --check 返回 0，仅有两条既有 LF→CRLF 提示；看板原证据行的 CR 行末提示仍按上文登记，未隐瞒。

### 6.5 整改批次记录（实现者回写，2026-09-07）

按 §6.4 第 1 步对 PR01–PR18 做单一整改批次，产品与测试同批修复；本节为该批次的处置登记。
自检方式限于源码级：逐行核对新实现与 MCU 真值模型、Grep 交叉验证调用点 API 签名、
独立复算测试 oracle 数值。本机仍无 flutter/dart（`where flutter`/`where dart` 无结果），
analyze/test 未执行，须按 §6.4 第 2 步获用户授权推送后取 Actions 结果。

#### 6.5.1 逐项处置

| 发现 ID | 处置（文件为主锚点） |
|---|---|
| PR01 | [ota_upgrade_page.dart](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart) 直接 import `ota/ota_firmware_latest.dart`；[ota_firmware_latest.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart) 的 `OtaFirmwareAsset` 改公有构造器（测试 `assetOf` 即用）；[ota_ble_transport.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart) 重写后 ACK 一律 `OtaAckPayload`、结束态 `OtaAckResult`，类型链核对无矛盾。 |
| PR02 | `ota_firmware_latest.dart` 字段键与诊断标签分离（`_requireString(raw, name, {label})`），asset 嵌套 Map 直接键访问；测试新增正例 + 每个 required 字段负例（`ota_firmware_latest_test.dart`）。 |
| PR03 | transport 帧重组始终保留未消费尾部（offset=0 也回存）；测试覆盖单字节分片（60B INFO 按 1B 通知）与垃圾前缀重同步（`ota_ble_transport_test.dart`）。 |
| PR04 | 块数学统一字节单位：`blockStart = (durableOff ~/ 4096) * 4096`，尾块段数向上取整；测试断言 8192B 双块 `durableProgress == [0, 4096, 8192]`、4225B 短尾 `tailOffsets == [4096, 4224]`（末段 payload 5B）。`transfer` 消费 INFO `maxWindowSegments`（PR04 附带项）：窗口上限用例断言 `maxInFlight <= 4`。 |
| PR05 | waiter 按 cmd+session+seq 关联；每段 ACK 逐个消费（非每块首个）；ACK_ABORT/异步 ABORTED 分发；ERR_SESSION/ERR_STATE 区分处置（ERR_STATE 后 teardown、重 BEGIN resume）；`ota_ble_transport_test.dart` 覆盖迟到/重复 ACK、END ERR_STATE 后 resume（beginCalls=2）、未知 status（0x7F）抛 ACK_MALFORMED。 |
| PR06 | [bluetooth_service.dart:1763](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1763) `_strictBleUuidEquals`：norm 后等值，或双方均为标准 Bluetooth Base UUID（`0000xxxx-0000-1000-8000-00805f9b34fb`）时仅比较 16-bit 短码；`findExactOtaCharacteristicsByAddress` 同时返回 FFF2 实际 writeMode，ota_service 按 `'writeMode' != 'without'` 绑定写模式。 |
| PR07 | [ota_service.dart](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart) `startOtaUpgrade`：END OK 仅置 `waitingReboot` → `_waitForRebootReconnect`（20×3s 有界轮询，取消代次随时退出）→ `reconnectVerify` 新 transport GET_INFO → `deviceHardwareMatches`（硬件身份，版本/镜像除外）+ `currentVersionCode == latest.versionCode` + `currentImageSha256Hex == latest.targetImageSha256` → `completed`；不符分别进 `TARGET_IDENTITY_MISMATCH` / `REBOOT_RECONNECT_FAILED`（retryableLater）。 |
| PR08 | 取消代次 `_cancelGeneration`：`cancelUpgrade` 递增，传输循环每步核对；HTTP 走 CancelToken + 删 partial；transport `isCancelled` 停止发送循环 + `abortBestEffort`；`downloadFirmware`/`startOtaUpgrade`/`checkFirmwareUpdate` 入口忙锁防重入；测试覆盖取消 mid-transfer（CANCELLED + 帧数停止增长）。 |
| PR09 | `readDeviceInfo` 入口 `_deviceInfo = null` 先失效旧快照；OtaTransportException DISCONNECTED 时置空快照（恢复须重新 GET_INFO）；`_ChannelAdapter` 写失败与通知流 error/done 均置 `_connected = false`。 |
| PR10 | `_bindTransport` 重建前 `await old.dispose()`；`subscribeOtaNotifyByAddress` 订阅就绪后才返回流，随后才允许发 GET_INFO。 |
| PR11 | 终态闭锁 `_terminalLocked()`：非 retryableLater 终止态拒绝 latest/下载/传输入口；`_terminalFromDioError` 对所有非 2xx 解析错误体，未知 errorCode/未知状态/无可解析体 fail closed 进终态；仅 `readDeviceInfo` 成功解锁。 |
| PR12 | `_VerifiedPackage` 绑定 assetId/releaseId/sha256/sizeBytes/versionCode；`_invalidatePackageIfChanged` 清单变化即失效旧包；BEGIN 前 `verifyFileMatchesAsset` 复核当前字节（startOtaUpgrade 内）。 |
| PR13 | `_checkResumeHeaders` 完整头校验集（Accept-Ranges/Content-Range 精确区间/Content-Length==剩余/与 If-Range 一致强 ETag），违规作废重下（restartUsed 一次）；416→RANGE_AT_END、401/410→URL_EXPIRED、409→ASSET_CONFLICT；Content-Digest（RFC 9530，sha-256 base64→hex）对实收字节交叉核对；24h 清理含孤儿 sidecar 与 `.part.json.tmp`；本批新增「无 Range 请求却返回 206」fail closed（作废后仍强制 206 即抛 RESUME_PROTOCOL）；测试新增 11 项（头违规三类、无条件 206、416/401/409、200 长度失配、digest 正反例、孤儿清理）。 |
| PR14 | `ota_firmware_latest.dart`：false 分支必需 errorCode、true 分支禁止 errorCode、appId/deviceModel/channel/transport 回显校验、versionCode/baseVersionCode 0..2100000000、sizeBytes ≤ `OtaFirmwareAsset.maxPackageBytes`(0x180000)、downloadUrl http(s)+host、fileName 字符集/长度/后缀、full 的 baseImageSha256 缺键与显式 null 区分；[share_links.dart](../../app/bluetooth_flutter_Trace/lib/config/share_links.dart) channel 枚举校验；[ota_device_info.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_device_info.dart) 补 `wireModel` 字段；测试负例 19 项 + channel 非法负例。 |
| PR15 | transport 构造器 `{ackTimeout = 2000ms, retries = 5, noProgressTimeout = 30s}` 全参数化（P3-4 实测前默认取 clamp 上限，不杜撰生产档位）；no-progress 截止按 durable 推进重置；metadata Dio 连接 15s/接收 20s，下载 Dio 独立无接收超时；`_getLatestWithRetry` 429/503/网络错误重试 ≤3 次（Retry-After 或 1s/2s，单次上限 30s）。测试注入小超时验证 TIMEOUT 与 NO_DURABLE_PROGRESS 路径。 |
| PR16 | `OtaPhase` 枚举 + `Rx<OtaPhase> phaseRx`，UI 全部由 phase 驱动（不解析状态文本）；固件信息卡 Obx 锚定 `phaseRx.value`；新增 [ota_upgrade_page_test.dart](../../app/bluetooth_flutter_Trace/test/ota/ota_upgrade_page_test.dart) 14 用例（idle/downloading/transferring/waitingReboot/reconnectVerify/readyToInstall/completed/cancelled/终止态三类/固件信息卡/连接身份三态/按钮防重入）。 |
| PR17 | codec oracle 修正：CRC16([0,0,0,0]) = 0x84C0（原 0x2F3E）；9B ACK `durableOff = 0x400000`、`blockBitmap = 0x0F`（原 0x40000000/0x0F0000，LE 字节序独立复算）。transport 测试 fake 按 MCU 真值全量重写：sendFrame 按 cmd 回显 seq、INFO session=0、ACK_DATA/END/ABORT 带 MCU session、ACK_BEGIN 帧头新 session；bitmap 按位收齐才推进 durable 并清零；重复 BEGIN 同 sha 幂等保留进度；END 缺段回 ERR_STATE。共 19 用例（含窗口上限、单字节分片、垃圾前缀、取消、abort、dispose）。 |
| PR18 | 页面进入自动解析连接设备：显式 `connectedDevice` 优先，否则遍历 `FlutterBluePlus.connectedDevices` 取首个 `isConnected`（Dart 3.0 无 `firstOrNull`，用 for 循环）；平台通道异常静默降级为未连接。speedometer 两个无参入口由此可用；device_detail_page 带设备入口保留。附带修复：`otaService` getter 改为先 `Get.isRegistered` 再 put，避免每次 build 构造被丢弃的 OtaService/Dio。 |

#### 6.5.2 本批改动文件

产品（7）：
`lib/ota/ota_ble_transport.dart`（重写后本轮核对）、`lib/ota/ota_download.dart`（本轮补无条件 206 fail closed）、
`lib/ota/ota_firmware_latest.dart`（重写后本轮核对）、`lib/ota/ota_device_info.dart`（wireModel + deviceHardwareMatches）、
`lib/services/ota_service.dart`（全量重写）、`lib/pages/ota_upgrade_page.dart`（全量重写 + getter 修复）、
`lib/config/share_links.dart`（channel 枚举）、`lib/services/bluetooth_service.dart`（PR06 严格 UUID + 订阅就绪，前轮落）。

测试（6）：`ota_ble_codec_test.dart`（oracle 修正）、`ota_device_info_test.dart`（wireModel/hardwareMatches）、
`ota_ble_transport_test.dart`（fake 重写 19 用例）、`ota_firmware_latest_test.dart`（fixture 补必填 + PR14 负例 19 项）、
`ota_download_test.dart`（206 头/分类码/digest/孤儿 11 项新增）、`ota_upgrade_page_test.dart`（新增 14 用例）。

#### 6.5.3 已执行与未执行

已执行（本机，全部只读或项目内源码编辑）：
- 新实现与 MCU 真值模型逐行核对（[Libraries/OTA/ota_ble_session.c](../../Libraries/OTA/ota_ble_session.c) 每段 ACK/seq 检查/块提交路径）；
- Grep 交叉验证调用点签名（ShareLinks.firmwareLatestUri、BluetoothService.requestOtaMtu/subscribeOtaNotifyByAddress、
  AppUpdateService.getLocalAppVersionCode、主项目 BluetoothDevice 构造先例 bluetooth_service.dart:831）；
- 测试 oracle 独立复算（CRC16、LE 字节序、块/尾段数学）；
- 无 Range 却 206 的实现真空档在测试设计时发现并同批补齐。

未执行/待验证（如实保留）：
- flutter analyze / flutter test：本机无 SDK，6 个测试文件（5 改 1 新增）均未运行；
  须按 §6.4 第 2 步获用户授权提交推送后取 Actions run 结果，APK/EXE 亦同。
- 真机判据（APK 可安装、真机 toy 包与真包传输、重启复核）全部未执行，归属正式验收轮次。
- P3-4 生产调参档位未定：ackTimeout 当前默认 2000ms（clamp 上限）为占位默认，非实测裁定。
- 本批未 commit/push/部署/烧录；未改 workflow、冻结契约与既有 9 个未跟踪遗留文件。

本批写入边界：产品/测试源码 + 本 research 文档 + 看板回写（Python 字节编辑），
全部位于活动根 D:/github/my/E-Track 内；无项目外写入。

### 6.6 整改批次独立复核（P3-3-RC2，2026-09-07）

审查者：Codex（非实现会话）。依据仍为验收执行合同 §7.3、冻结二进制/跨系统合同和原 PR01-PR18。
本次复核结论：**整改批次仍未通过集中预审，不能认定 18 项已全部关闭；正式验收 NOT_RUN。**
RC2 只是本研究文档的整改复核标识，不是新开的正式验收轮次，不产生 EXECUTED PASS/FAIL 矩阵。

本次 HEAD 与上次预审相同，均为 0ef3cc14f6fdbece4f15b45864b94cb1007af735。
实现仍未提交，未找到 P3-3 验收合同/矩阵或验收派工书，不能用这个治理提交冻结未提交的 Dart 字节。
未授权提交、推送、dispatch、部署或硬件操作；这些动作均未执行。正式产品/硬件观测次数仍为 0。
本次只复核本整改批次和它直接调用的 BLE/MCU 接口，不重跑已完成卡或无关治理/固件回归。

#### 6.6.1 原清单对照

下表的“已修”仅表示所列局部源码错误已消除，所有 Flutter 运行验证仍未执行，不表示正式 PASS。

| 原项 | 本次复核 |
|---|---|
| PR01 | 原类型混用、产品页面 DTO import、资产构造器问题已调整；但新增/遗留编译阻断见 RC2-01，不能关闭编译项。 |
| PR02 | 嵌套 asset 键与诊断 label 已分离，原带点键错误已修；解析器的新增回归另见 RC2-02。 |
| PR03 | offset=0 的未消费半帧现在保留，原丢首片错误已修。 |
| PR04 | 4KB 字节换算、短尾向上取整、INFO 窗口参数接线已修；窗口重传和 ACK 可信度仍见 RC2-05/06。 |
| PR05 | 一问一答 waiter 现在关联 cmd/session/seq；持续 ACK 视图没有同等校验，重传也未闭合，见 RC2-05/06。 |
| PR06 | 精确发现和实际 write mode 已加入；最终写入仍经过旧模糊 UUID 匹配，见 RC2-08。 |
| PR07 | END 不再直接置 completed，已有目标版本/SHA 比较；“重连”未实现连接且可能读取重启前 INFO，见 RC2-07。 |
| PR08 | 有取消标志和代次，但 ABORT 被自身拦截，操作锁及 HTTP 取消仍有竞态，见 RC2-03/04。 |
| PR09 | readDeviceInfo 入口清旧 DTO、适配器写失败置 false 已加入；后台、真实断连通知及恢复所有权仍未实现，见 RC2-07。 |
| PR10 | 串行路径已 await 旧订阅释放和 CCCD 就绪；并发 readDeviceInfo/页面重建仍会夺取在途 transport，见 RC2-04。 |
| PR11 | 常见 HTTP 终止码和 typed schema 错误会清旧资产；取消/重入和部分错误分支仍可留下或发布陈旧状态，见 RC2-04/11。 |
| PR12 | verified 包身份记录、清单变更失效及文件摘要检查已加入；检查后的异步间隙和二次读文件未绑定同一字节快照，见 RC2-04。 |
| PR13 | 增加了响应头、digest、孤儿清理逻辑；实际 Dio 错误路径、200 回退及恢复合同仍有缺陷，见 RC2-09/10/11。 |
| PR14 | wireModel、channel 请求枚举、部分 required/size/fileName 校验已加；NO_UPDATE 分支被错误加字段，固件版本域也被收窄，见 RC2-02/11。 |
| PR15 | metadata 15s/20s、默认 ACK 2000ms、Stopwatch 重置已加入；重试窗口不能恢复、单次写等待无截止，见 RC2-05。P3-4 档位仍未实测。 |
| PR16 | phase Rx 锚点和 Get.put 重复构造已修；widget 测试不可编译，检查按钮未响应 busy 变化，见 RC2-01/04/12。 |
| PR17 | 三个 CRC/LE oracle 数值已改正确；fake 仍不验证 seq/END 完整性，新增测试并未实际运行，见 RC2-01/12。 |
| PR18 | 无参入口增加了一次移动端 connectedDevices 查询；没有连接变化后的重新解析或多设备选择证据，不能称所有入口/恢复均已验证，见 RC2-07。 |

#### 6.6.2 剩余阻断与整改回归

| ID / 级别 | 依据、定位与可复现条件 | 同批处置与应补证据 |
|---|---|---|
| RC2-01 / P1 | 编译准入仍失败。[transport:62](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L62) 和 [67](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L67) 同时声明 static maxRetries 与实例 maxRetries；同名成员冲突。[widget 测试:75](../../app/bluetooth_flutter_Trace/test/ota/ota_upgrade_page_test.dart#L75) 使用 OtaUpgradePage 却没有 import 页面；[83](../../app/bluetooth_flutter_Trace/test/ota/ota_upgrade_page_test.dart#L83) 的 findButton(String label) 使用作用域内不存在的 tester。前者为本次重写引入，后两者在新增测试中。 | 修齐声明、import、参数作用域，并让真正的 analyze/test 执行一次。这里是明确的静态符号矛盾，不冒充编译器实际输出，也不声称已穷举全部编译错误。 |
| RC2-02 / P1 | 新增 schema 回归：[latest:85](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart#L85) 在判断 updateAvailable 前强制 appId/deviceModel/channel，而冻结 [HTTP-LATEST:184](../ota-cross-system-contracts.md#L184) 的 NO_UPDATE 只有 schemaVersion/requestId/updateAvailable/errorCode。合法无更新及同形停发响应会变成 LATEST_SCHEMA_INVALID。测试 [noUpdateBody:48](../../app/bluetooth_flutter_Trace/test/ota/ota_firmware_latest_test.dart#L48) 反而补了非必需字段，掩盖回归。另 [485](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart#L485) 把固件 versionCode/baseVersionCode 限到 App 专用的 2100000000；[冻结注册合同:913](../ota-cross-system-contracts.md#L913) 明确固件 versionCode 为 u32，两者不是同一数值域。 | 按响应分支校验，保留冻结的最小 NO_UPDATE/CHANNEL_STOPPED 正例；禁止为适配实现修改 fixture schema。分开 App 与固件版本范围，补合法 u32 边界正例；channel 回显还须与本次请求一致，不能仅判属于 stable/beta。 |
| RC2-03 / P1 | 取消时 ABORT 永远不发送。[abortBestEffort:329](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L329) 先 cancel()，再调用 _writeFrame；[536](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L536) 首步 _checkUsable 立即因 _cancelled 抛 CANCELLED，被自身 catch 吞掉。即便连接正常，ABORT 写入次数也是 0。 | 分离“停止 DATA/END”与“受控发送 ABORT”的通路；等待/隔离在途写，不能临时重新解锁旧发送循环。补 connected=true 时恰发 ABORT、之后零 DATA/END 的测试；现有用例只验断连时不抛，抓不到此错误。 |
| RC2-04 / P1 | 所有者/代次仍不完整。[start:450](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L450) 检查 busy 后 await 文件摘要，[469](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L469) 才上锁，两个 start 可同时通过。checkFirmwareUpdate 从不上锁，readDeviceInfo 不受 busy/代次约束并可 dispose 正在传输的对象。下载刷新清单 [339](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L339) 暂时解除锁；_downloadOnce 没有检查代次就 [386](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L386) 发布文件/readyToInstall。取消发生于目录清理、latest 刷新或完成校验时，旧操作仍可能启动新 HTTP 或覆盖 cancelled。BEGIN 的实际字节在 [505](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L505) 二次读入，和先前 await 校验的快照不是同一份。 | 在首个 await 前取得单一操作所有权；内部 refresh 不解除用户入口锁；每次 await 后及发布状态/rename/新请求前检查代次；取消等待旧操作退出后释放锁。一次读取并验证待发不可变字节，绑定同一 DTO/latest 快照。新增真实 OtaService 的双击、刷新期间取消、文件替换、页面重建和旧回调晚到测试。检查按钮位于非 Obx 的 build 路径，busy 变化也须实际禁用；保留已校验包仍缺用户明确选择。 |
| RC2-05 / P1 | 可恢复传输仍失效。[transport:222](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L222) 用 pendingSeqs 限窗；超时 [257](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L257) 仅 clear localSent，不回收/重用 pendingSeqs。32 个 ACK 丢失后 pending=32，下一轮仍在入口 break，实际零重传。另 [BEGIN:456](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L456) 每次超时重试都取新 seq，而 MCU 的 [同包重复 BEGIN:377](../../Libraries/OTA/ota_ble_session.c#L377) 只回进度、不重设 expected_seq；首次 BEGIN(seq=0) 的 ACK 丢失后重试 seq=1，后续 DATA(seq=2) 必遇 MCU expected_seq=1。ERR_SEQ 后重复 BEGIN 也不能消除此缺口。 | 以段/原帧/seq 管理重传与累计确认，不能永久消耗窗口；按真实 MCU 幂等规则复用请求 seq 或进行受控 teardown/新 BEGIN。补丢 BEGIN ACK、丢 DATA/ACK、跨块累计 ACK、seq 缺口/回绕测试。30s last-durable 截止须跨 resume 保留并覆盖 writeChunk 等待；当前 Stopwatch 每次 BEGIN 重建，单次 write 仍无显式截止。 |
| RC2-06 / P1 | ACK 视图仍不按请求关联。[viewAccepts:370](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L370) 接受同 session 的各类 ACK；[onAck:632](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L632) 不检查 pendingSeqs.remove 是否成功，直接覆盖 durable/bitmap。旧 seq、重复迟到 ACK、错误命令 ACK 可使进度倒退或跳过块；没有 0..total、4KB/尾块对齐、bitmap 有效位检查，BEGIN 也不拒成功 session=0。 | 给连续 ACK 消费器实施真正的操作/session/seq、单调性和窗口范围校验，明确周期 bitmap ACK 的合法规则；不得仅凭一问一答 waiter 已关联就宣告整个 transport 关联正确。补旧 ACK 倒退、未知 seq、伪 END/BEGIN、越界 durable/bitmap/session 负例。 |
| RC2-07 / P1 | “等待重启重连”不等于真正重连。[service:706](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L706) 只 discover/bind，第一次发现旧连接尚在时 [713](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L713) 即返回并读旧 INFO，导致正常升级未完成就 TARGET_IDENTITY_MISMATCH；若设备已断开，根本没有 connectDevice/connect 调用，而 [discoverServicesByAddress:1052](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1052) 明确要求已连接。20 次循环也不能保证含慢调用的总耗时为 60s。service/transport/page 仍没有 App lifecycle 或真实连接状态订阅；只在特定异常后清 DTO 不满足断连即失效。 | 监听真实断开/重连代次，同一目标地址建立连接，再读新 INFO；覆盖重启前旧连接暂存、真实断开、回滚和总截止。后台/断连停止写入并失效 DTO，恢复重新发现/GET_INFO/BEGIN。无参页面当前仅首次取第一个已连接设备，须补连接变化及多设备目标选择检查，不能将其视作已验证的恢复路径。 |
| RC2-08 / P1 | 精确 UUID 红线只修到 discovery，没修到写入。[适配器:1015](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1015) 仍调用 writeByAddress；它再次枚举服务并在 [1123](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1123) 使用旧 _uuidLikeEquals。若非标准 1234fff0-1111-2222-3333-444455556666 排在标准服务之前，严格发现会跳过它，但实际写入又会把它当标准 FFF0，并可能写错 FFF2。 | 写入必须复用严格绑定的 characteristic 或 OTA 专用严格 writer；保持遥控旧行为不变。测试必须执行最终 write 路径，不能只验证 _strictBleUuidEquals。离线同一反例：strict 拒绝、legacy writer 接受。 |
| RC2-09 / P1 | 401/409/410/416 分类在生产 Dio 下不可达。[download:101](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L101) 使用默认仅接受 2xx 的 Dio；非 2xx 先抛 badResponse，[109](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L109) 只处理 cancel 后 rethrow，因此后面的 status==416/401/409 分支不会运行。service 也拿不到 _needsFreshManifest 依赖的领域码。新下载测试同样使用默认 Dio，实际执行会暴露异常类型不符。 | 在 DioException.response 路径按冻结错误体/状态码分类，或显式设置受控 validateStatus 后统一处理，并关闭/消费响应流。用默认生产配置验证 401/409/410/416，而不是放宽测试 adapter 掩盖。 |
| RC2-10 / P1 | 合法 If-Range→200 回退被错误拒绝。[download:143](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L143) 先计算 expectedRemaining；[151](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L151) 截断并清 localPartSize 后没有重算；最终仍与旧剩余长度比较。4096B 资产已有 1024B，合法 200 全量 body=4096，却被拿来和 3072 比较，必报 LENGTH_MISMATCH。该分支还跳过全新 200 的 Content-Length 检查。 | 在确定最终响应模式后统一计算本次期望长度并校验头；补真实 partial+If-Range 失配+200 完整 body 的成功用例，验证覆盖而非追加及首次调用直接成功。 |
| RC2-11 / P2 | 恢复/边界仍不符合冻结合同。修复 RC2-09 后，401 一律删 partial 并当 URL_EXPIRED，没有按 TOKEN_INVALID/TOKEN_EXPIRED/未知 errorCode 分流；409 ASSET_CONFLICT 不触发 service 的重新 latest。完整 partial SHA 错或超长仍用旧 URL 重下。[digest:368](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L368) 将已提供但非法/错误长度的 sha-256 header 当缺失忽略；“强”ETag 仍仅排除 W/。[URL:276](../../app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart#L276) 为 mock 在生产解析器全局放行 HTTP。另 BACKEND_UNAVAILABLE 重试耗尽被 [service:848](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L848) 返回 null，通用 catch 不清旧资产，不满足失败后禁止沿旧清单进入 BLE。 | 按错误码和资产身份决定保留、失效、重新 latest，不以 HTTP 状态粗分类代替合同；完整/超长损坏 partial 按合同重新取清单。严格校验存在的 digest/强 ETag，生产保留 HTTPS 边界，测试不放宽生产解析。失败闭锁包括通用 JSON/后端错误及旧资产；补负例与 URL 刷新后的同身份续传。 |
| RC2-12 / P1 | 测试“MCU 真值”声明仍不成立。[fake END:622](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L622) 默认 status=OK，从未判断 _durableOff==_totalLen，也不验包摘要；整个 fake 没有 MCU 的 expected_seq/ERR_SEQ 判定，ABORT 在 [440](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L440) 被忽略。延迟 ACK 的 doSend 读取发送时的新 durable/bitmap，而非处理对应请求时的快照。widget 测试只人工改 phase getter，不执行真实 OtaService 编排，无法证明重连、取消、并发和最终成功。已有无 ACK 测试断言 DATA>=64，RC2-05 当前逻辑实际只能发首窗；它没有被执行过。 | 修正 fake 的状态/seq/幂等/END/ABORT 和 ACK 快照，对照真实 MCU；补会话级服务正反例。明确区分静态展示 widget 测试与真实服务状态转换测试。先证明负例因目标判据变红，再使用其结果，不能以 19/14 等用例数量替代运行。 |

上述 RC2-01/02/10 是整改中新出现的具体回归；其余是原项未闭合、同根因调用链遗漏或补强检查发现。
不增加新的产品范围，不修改冻结协议，不要求为每一条分别开正式验收轮次。

#### 6.6.3 本次证据与限制

已实际执行：源码/测试/合同逐项读取、MCU 同包 BEGIN/seq/END 分支核对、git status/log/diff、
where flutter、where dart、P3-3 合同文件检索，以及一次 Node 离线源码对照算例。
Node 算例只是控制流/算术/字段模型，不执行 Dart；以下数值不是 Flutter 测试或真机观测。
一次内联命令因超过 cmd 长度限制在启动前被拒，未产生文件；缩短命令后算例执行 exit 0。

| 离线算例 | 结果 |
|---|---|
| 冻结 NO_UPDATE 的字段 vs 分支前 required | 缺 appId/deviceModel/channel，会在业务分支前被拒绝 |
| cancel 后进入普通写通路 | _cancelled=true，ABORT 写次数 0 |
| 首窗 32 个 ACK 丢失后 | pending=32、localSent=0、canRetransmit=false |
| BEGIN(0) ACK 丢失→重复 BEGIN(1)→DATA(2) | MCU expected_seq 仍为 1，DATA 得 ERR_SEQ |
| partial=1024、size=4096、200 全量回退 | 实收 4096 与旧 expectedRemaining=3072 不符 |
| 同一个伪 FFF0 UUID | 严格 discovery 拒绝，实际 legacy writer 比较器接受 |
| 局部修复复核 | 下一块 4096→4096；129B 尾块 2 段；offset=0 保留尾部；assetId 键不带前缀 |

原始诊断：[recheck-2.json](../../.cache/p3-3-prereview/recheck-2.json)，SHA-256：
b50e01286f39be53202b7c4909beb870a8950a6aece520ef76978d827eb0a328。
上轮 readonly-probes.json 未覆盖，旧结论仍只对应旧代码，不用于给本批复用 PASS。

Flutter/Dart 仍未在 PATH 中找到；本次 analyze/test、Android APK、Windows EXE、安装、真实 HTTP、
BLE/J-Link、重启重连及 validate_bundle.py 正式校验全部 NOT_RUN。
没有本批实现 commit SHA、Actions run URL 或 APK/EXE 成功证据；不拿当前治理 HEAD 或旧 CI 代替。
工作区 diff --check 仍仅报告原看板证据行 626 的末尾 CR 和两条 LF→CRLF 提示，未把该非功能项当作新增产品阻断。

#### 6.6.4 收尾与下一步

先按上述同根因组批量修复产品、真实服务测试和 fake；尤其先消除静态编译错误，不能继续用“测试文件已新增”代替运行。
获得用户明确提交/推送授权后，通过 Actions 验证稳定整改批次；正式验收仍须实现/runner 先提交、
真机判据归属确认、v3 审批冻结及执行前矩阵检查。缺 SDK 不允许本地构建或跳过独立验收，也不自动授予推送权限。
未运行过正式 P3-3 轮次，当前不虚构 rerun plan；进入正式轮次后再按实际前轮最小复验。

本次主动输出仅为项目内本节、看板状态/证据/日志、.cache/p3-3-prereview/recheck-2.json。
写前规范化所有路径并检查完整父链无 reparse，命令显式工作目录为 D:/github/my/E-Track，使用 cmd.exe。
结束复核已完成：18 个被审源码/测试/workflow 与 9 个遗留文件的逐文件 SHA 聚合值均与写入前一致，
上轮 readonly-probes.json 的 SHA-256 也未改变；没有修改产品、测试、workflow 或冻结合同。
三个本轮主动输出的实际路径全部仍在活动根内，缓存目录仅保留旧诊断和本次 recheck-2.json。
看板只增加两条复核记录并更新当前状态；原 728 个 CRLF 行尾保留，对补丁影响的既有行尾只做了
格式恢复且断言规范化内容未改变。看板相对 HEAD 为 9 增/2 删（进入本次复核时为 7 增/2 删）。
本节全部文件链接和行锚点已检查有效；未启动 PowerShell，NODE_COMPILE_CACHE 未设置，无主动项目外写入。

### 6.7 第二批整改（P3-3-IMPL-20260907，RC2 批次收尾，2026-09-07）

本节为 §6.6 复核打回后的第二批整改回写。目标一次消解 §6.6.4 的全部阻断：
静态编译错误、widget 测试缺陷、取消/重传/重连根因、HTTP 回归与本轮补齐的
service 会话级测试支撑。全部改动仍未提交、未推送；Flutter analyze/test 仍
只能依赖 Actions（本机无 SDK，见 §6.6 尾部结论）。

#### 6.7.1 产品代码改动（app/bluetooth_flutter_Trace）

- `lib/services/ota_service.dart`：
  - 构造器新增三个测试注入点：`downloadDio`（独立下载 Dio）、
    `firmwareDirProvider`（目录提供器）、`latestUriBuilder`（latest URI 构造）。
    生产缺省行为不变（独立下载 Dio、应用文档目录 firmware/、ShareLinks
    latest query 全参数构造）。
  - `isFirmwareServiceConfigured` 判定改为
    `_latestUriBuilder != _defaultLatestUriBuilder ||
    ShareLinks.hasFirmwareUpdateEndpoint`：注入 latest 构造器即视为测试已
    配置固件服务端点。ShareLinks 的 URL 来自
    `String.fromEnvironment('TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL')`，默认空，
    `flutter test` 无 dart-define 时恒 false 且 `firmwareLatestUri` 抛
    StateError——这是 service 会话测试在 Actions 上可运行的唯一路径。
  - 极早期取消时序缺陷（静态自检发现，产品级）：原实现 cancelUpgrade 经
    `OtaFirmwareDownload.cancel` 取消在途请求，但其内部 CancelToken 注册
    发生在 `_resolveDir` 等首个 await 之后，取消在注册窗口内会丢失（挂起
    下载永不停止）。修复：OtaService 在发起 download 前创建 `CancelToken`
    并传入（download 本支持 `cancelToken` 参数），持有
    `_activeDownloadToken` 字段使 cancelUpgrade 在任何时序下都能直接取消；
    `_downloadOnce` finally 清空字段。
- 其余 RC2 修复（transport abort 旁路、窗口释放、seq 重置、重连闭环、
  HTTP 分流、字段键、半帧、块数学）已在前两批完成，本轮未再改动。

#### 6.7.2 测试改动（app/bluetooth_flutter_Trace/test/ota/）

- `ota_service_session_test.dart`（新建，service 会话级 4 用例）：
  - 入口互斥：挂起下载期间第二次 checkFirmwareUpdate 被忙锁拒绝且不发
    新 latest 请求（adapter requestCount 不变）。
  - 取消链路：挂起下载 → cancelUpgrade → downloadFirmware 返回 false、
    phase==cancelled、无 partial/sidecar 残留 → 重新下载成功且无 .part
    残留。
  - URL_EXPIRED 刷新：401 TOKEN_EXPIRED → 自动重新 latest 一次并重下
    成功（latest 2 次、download 2 次）。
  - BACKEND_UNAVAILABLE 耗尽：503 三连（retryAfter 1s 真实退避）→
    retryableLater 终态、清空 latestInfo/downloadedFirmwareFile、不闭锁
    入口。
  - fake 支撑：`_FakeBle extends BluetoothService`（onInit 空实现阻止
    平台通道、四方法覆写签名与父类逐字一致含默认参数、broadcast 通知流
    ——多次 _bindTransport 每次 listen 不抛 StateError；GET_INFO 应答
    INFO 帧 session=0/seq 回显）、`_FakeAppUpdateService`（固定
    appVersionCode=42）、`_LatestMockAdapter`/`_DownloadMockAdapter`
    （行为序列 + requestCount + gated Completer；取消分支返回普通响应
    而非抛错——dio 取消后 fetch 返回值无人消费，孤儿异常会成为
    uncaught error）。
  - 骨架选择：普通 `test()` + 真实时间（不用 testWidgets——FakeAsync
    接管 Timer/微任务后，下载写盘/sha256 流式读/目录遍历等真实
    dart:io 异步不会完成，会挂死）；`runZonedGuarded` 吞 Get.snackbar
    无 overlay 上下文时在 GetQueue 逃逸的 null! TypeError
    （GetQueue._check 只捕 Exception，Get.testMode 只保护 navigation
    路径——源码级核对 GetX 4.7.2）。
  - fixture 合法性：fileName 满足 ASSET-NAMING
    （`e-track-at32f435-v2.9.0-full.etu`，full 后缀）、downloadUrl
    https（RC2-11 解析器校验）、channel stable 与 ShareLinks.updateChannel
    默认值一致（回显校验恰好通过）、asset sha256 与实发字节一致。
- `ota_upgrade_page_test.dart`（既有 widget 测试补齐页面导入与
  tester 使用）：已在上一批完成，本轮复核无回归。

#### 6.7.3 静态自检结论（无法本地运行）

本机无 Flutter SDK，`flutter analyze`/`flutter test` 不能本地执行（§6.6
尾部已声明）。本轮对六个测试文件与 ota_service.dart 构造改动做了逐文件
静态核对，逐项与真实源码比对：

- import 完整性：六个项目内导入（ota_ble_codec/ota_device_info/
  app_update_service/bluetooth_service/ota_service + crypto/dio/
  flutter_test/get/dart:async/dart:io/dart:typed_data）覆盖全部引用；
  包名 ble_monitor 与 pubspec.yaml 一致。
- fake 覆写签名：`findExactOtaCharacteristicsByAddress`/
  `requestOtaMtu`/`subscribeOtaNotifyByAddress`/
  `writeOtaCharacteristicByAddress` 与 bluetooth_service.dart:1149/1424/
  1492/1578 的参数名、类型、命名参数默认值逐字一致；`onInit` 空实现
  阻止 `initBluetooth()`（bluetooth_service.dart:448-451）；
  `getLocalAppVersionCode` 覆写跳过 MethodChannel
  （app_update_service.dart:303）。
- AppUpdateService.onInit 非 Android 直接 return（:55-57），测试宿主
  （Windows）安全；WidgetsBindingObserver mixin 无构造副作用。
- GET_INFO 链路：GET_INFO 帧 10B < fake MTU 247 单片写 →
  decodeFrame 可解 → INFO 应答 cmd=0x80/session=0/seq 回显 →
  _ResponseWaiter.matches（cmd+seq 全等、session==0 直通）→
  DeviceOtaInfo.fromInfoPayload（wireModelETrack/protoVer 1/
  maxWindowSegs 32 全部通过 buildInfoPayload fixture）。
- 取消链路：cancelUpgrade → `_activeDownloadToken.cancel()`（新增，
  覆盖注册窗口）→ dio fetch 的 cancelFuture 完成 → adapter gated
  分支 `Future.any` 返回 → CancelToken.isCancel → OtaPhase.cancelled；
  `_download.cancel(assetId)` 同时走 OtaFirmwareDownload 自身的取消/
  partial 清理路径。
- transport 测试的 _FakeMcuHost 用单订阅流（channel 直连单次订阅）
  与 service 测试经 _ChannelAdapter 多次绑定用 broadcast 不冲突
  （_ChannelAdapter.notifications 每次新建转发 controller）。
- GetX 4.7.2（pubspec.lock 核对）、dio 5.x（pubspec.yaml ^5.4.0）。

已知残余风险（如实声明）：静态自检不能替代编译与运行。类型推断错误、
未使用的导入告警（analysis_options 的 lint 而非编译错误）、Obx 订阅时序
等仍需 Actions 上的 `flutter analyze`/`flutter test` 最终确认。
下一 gate：用户授权提交推送 → Actions run URL → 正式验收轮次。

#### 6.7.4 本轮主动输出

- 产品代码：`app/bluetooth_flutter_Trace/lib/services/ota_service.dart`。
- 测试代码：`app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart`。
- 文档：本节。
- 看板：P3-3 卡保持「进行中」，§10 会话日志追加一行（Python 字节编辑，
  保留既有 CRLF 行尾分布）。
- 未提交、未推送、未触发 workflow；未宣告任何验收结论。


### 6.8 RC2 第二批整改独立集中复审（P3-3-RC3，2026-09-08）

审查者：Codex（非实现会话，复审自 2026-09-07 跨日至 2026-09-08）。
依据验收执行合同 §7.3，核对 §6.6 的 RC2 清单、§6.7 新交付和直接调用链。
结论：**整改未闭合，不满足正式验收准入；正式验收仍为 NOT_RUN**。
以下为源码/测试静态发现，不冒充编译器输出、Flutter 执行或正式失败轮次。
不能将“测试已新增”或“缺 SDK”当作缺陷关闭证据。

#### 6.8.1 集中整改清单

各项均在本卡范围内，按根因批量处置，不要求逐条开新轮次或重验无关历史卡。
P1 为功能/可执行性/证据可信度阻断；P2 为合同或交互缺陷，不是风格建议。

| 发现 ID | 依据/判据 | 当前影响与定位 | 处置 | 自测证据/状态 |
|---|---|---|---|---|
| RC3-01 / P1 | 编译准入；RC2-01 | [transport:662](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L662) 的 const 异常构造插入实例 writeTimeout.inSeconds，不是常量表达式；[latest test:10](../../app/bluetooth_flutter_Trace/test/ota/ota_firmware_latest_test.dart#L10) 用 'a' * 64 作可选参数默认值，也不是编译期常量；[transport test:812](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L812) 等在子类裸调用父类 static packBeginAck/packAck，static 方法不继承。 | 修齐产品及全部测试的常量/作用域错误，static helper 限定声明类或改顶层函数，再取得真正 analyze/test 输出。 | 明确的 Dart 常量/成员解析矛盾，非编译器实测。超时 const 为本批新增回归，其他为测试补查发现。 |
| RC3-02 / P1 | harness fail-closed；RC2-12 | [session test:101](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L101) 的 runZonedGuarded handler 为空，吞掉所有异步异常，不只 snackbar；测试体 Future 出错跨 error-zone 还会退化为等待超时。[185](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L185) 下载后立刻取消，未等待 adapter 进入，早期 token 可在 Dio 分发前拦截，首个 gated 行为未消费；[198](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L198) 第二次请求仍命中未 complete 的 gate。[widget test:143](../../app/bluetooth_flutter_Trace/test/ota/ota_upgrade_page_test.dart#L143)、161、175、186 对含不定进度 CircularProgressIndicator 的阶段 pumpAndSettle，动画不会静止。 | 用可控通知/overlay 替身隔离 UI 副作用，其他异常必须上抛；分开注册前取消和 adapter 已进入后取消，用 entered barrier/计数断言；忙碌 UI 使用定量 pump。 | 普通 test 使用真实 IO 本身合理，不能靠全局吞错背书。新 4 用例没有真实 startOtaUpgrade、双 start、刷新时取消或重连复核覆盖，全部 NOT_RUN。 |
| RC3-03 / P1 | binary §4.4/§4.5/§5；MCU 真值；RC2-12 | [public begin:130](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L130) 仅返回 ACK、不更新 _session；[测试:495](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L495) begin 后 ABORT 实发 session=0，fake [1007](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1007) 回 ERR_SESSION，不可能满足 ABORTED/session=1。ERR_SEQ 注入后 expected_seq 停在 3，后续 DATA 都被拒，恢复 bitmap 应为 3，不是 [406](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L406) 的 0xFFFB，缺 30 段而非 1 段。[失段用例:194](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L194) 报 bitmap 全满但 durable=0，transport 不发 END，只会无进展超时；[213](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L213) 又把 32 段 bitmap 写成 16 位。fake [785](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L785) teardown 保留未 durable RAM 位图/内容，与实际 staging 新 BEGIN 不同；延迟 [emit:1030](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1030) 仍读取发送时可变状态。 | 修正 public begin 状态和 oracle；fake 区分 durable 与 RAM，按真实 MCU 处理 seq、ABORT、新包重建、ACK 快照。当前 fake 明确省略真实 SHA 校验，不能宣称其 END 已验证整包摘要。补对应负例。 | 只读算例：32 位缺段 16 的 mask=4294901759，现 oracle=65535；ERR_SEQ 后已收前两段 bitmap=3，现 oracle=65531。非 Dart/MCU 执行。 |
| RC3-04 / P1 | 单一 owner、取消代次；RC2-04 | [readDeviceInfo:190](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L190) 和 [checkFirmwareUpdate:238](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L238) 只查 busy、不取得锁，App-info await 后也不复核；可与下载/传输并发，read 可 dispose 在途 transport。[_checkLatestLocked:275](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L275) 无 generation/token，取消后仍重试/发布旧清单；[refresh:403](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L403) await 后不查取消就继续 latest/新 token 下载。进度/错误分支也不查代次。[cancel:743](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L743) 不等旧 owner 退出便解锁，旧 finally 可清掉新操作锁。 | 全部入口首个 await 前取得同一 owner；代次/token 贯穿 App-info、latest 重试、目录/校验、刷新和发布；取消等待旧 owner 退出，finally 只释放自身。补并发入口、刷新时取消、旧回调晚到的真实服务用例。 | start 锁前移、同一份包字节校验、刷新不临时解锁、download token 提前持有已修，但不能据此关闭整个互斥/取消项。 |
| RC3-05 / P1 | HTTP-RESUME:271；FLUTTER-TRANSPORT:1057；RC2-03/04 | [UI:959](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L959) 和 [download:312](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L312) 允许显式取消后保留未校验 .part/sidecar，违反冻结删除规则；可以选择保留的是已校验完成包。反而 [service:730](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L730) 的 keepPackage=false 不删除 _firmwareFile。ABORT 旁路 [375](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L375) 未与在途 MTU 分片串行化：DATA 首片后取消留下半帧，随后 ABORT 字节可被当作旧 DATA payload，不能解码成完整 ABORT。 | 恢复冻结取消策略，不自行放宽 partial 保留；对已验证包明确展示并落实保留/删除。建立安全帧中止边界，覆盖每个 MTU 切分点取消；等 sink 关闭后确认删除，不能忽略删除失败就称无残留。 | token 修复只覆盖请求注册窗口；完整 partial 快速 rename、最终 hash/rename 仍无 token 检查，清理与落盘仍可能竞争，现测试未覆盖。 |
| RC3-06 / P1 | binary §5.5 ACK 唯一真相；RC2-06 | BEGIN 只拒 session=0，[view.reset:198](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L198) 直接信任 durable/bitmap，越界 BEGIN durable 可跳过 DATA；END [313](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L313) OK 也不核对 durable==total。DATA 仅限制全包范围，未限制当前可提交窗口。[onAck:780](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L780) 仅回收单个 seq，前移 durable 后不累计回收旧块 inFlight；旧块合法 ACK 晚到被误判倒退，下一块还会按旧段号跳过/旧 seq 重发。[_viewAccepts:420](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L420) 仅接 DATA，异步 ACK_ABORT 无 waiter 时被丢弃。 | BEGIN/DATA/END 统一校验 session、进度和位图；在途绑定绝对 offset/块代次，durable 累计回收已提交区，合法迟到 ACK 不回退也不误杀；单独处理会话事件。 | 只读视图算例：pending=seq1、32，先收 seq32 durable=4096/bitmap=0，seq1 未回收；后收其旧 durable=0 即 malformed。须补跨块乱序/提交 ACK、伪跳跃、坏 BEGIN/END、异步 ABORTED 测试。 |
| RC3-07 / P1 | BLE-TUNING/RETRY-POLICY 的 30 秒无 durable 进展；RC2-05 | [230](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L230) 先 await 发完整窗，[241](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L241) 才查 noProgress；末 ACK 已推进则 [240](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L240) 直接 break/reset，超期被略过。10 秒是每分片超时，不能限制总时间；MTU=23、每片 1 秒，32 段可等 224 秒。BEGIN/ABORT/END 也未用剩余总预算。 | 单调时钟维护最后真实 durable 的绝对截止，将剩余预算应用到每次写、ACK 和 resume；timeout 后隔离迟到写。补慢而单片不超时、持续无 durable ACK 和跨 resume 负例。 | Stopwatch 移出 resume 循环已修，截止覆盖仍不完整。224 秒只是 Node 算术/控制流反例，不是性能实测。 |
| RC3-08 / P1 | DEVICE-DTO:118；BLE-LIFECYCLE；FLUTTER-TRANSPORT:1058；RC2-07 | service/transport/page 没有 App lifecycle 或真实连接订阅，DTO 无地址/连接代次绑定。[_waitForRebootReconnect:800](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L800) 虽新增 disconnect/connect，却把第一次可连接当已重启，可能立即读旧固件并误报目标不符；deadline 在 disconnect 后开始且 await 无剩余预算。快速掉线恢复时 MCU 仍 ACTIVE，新 transport 的低 seq BEGIN 不重置 MCU expected_seq；落后 DATA 会被幂等 ACK，未必进入 ERR_SEQ 重对齐分支。页面 [65](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L65) 只解析一次移动端连接列表，不处理连接/目标变化。 | 生命周期归同一 owner，地址/连接/session 变化即失效 DTO；后台停写，恢复重新发现/INFO/受控 BEGIN。区分新 GATT 连接和 MCU 真正重启，所有 await 纳入总截止。补 MCU 未 teardown 快速重连、旧身份暂存、回滚、后台与多设备目标测试。 | 新增 connect 是真实局部修复，不等于重连闭环；8 个测试文件均没有真实服务 startOtaUpgrade 调用。真机 NOT_RUN。 |
| RC3-09 / P1 | FFF1 通知/任意 GATT 分片；范围内前次遗漏 | Windows [subscribeOtaNotifyByAddress:1506](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1506) 订阅后不消费通知事件，而是 250ms 轮询 readByAddress 并按 last 去重；底层 [359](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L359) 是 WinBle.read。FFF1 只要求 notify、未保证可读；连续分片/同值通知会丢失，不能可靠重组 60B INFO/ACK 流。 | 暴露并消费真实特征通知事件，保留每片及顺序，正确建立/取消订阅；补 adapter 层 notify-only、多片和重复片测试，不用绕开 adapter 的 fake 替代。 | 静态核对实际调用链。没有 Windows BLE 实测，不以 EXE 构建绿代替协议验证。 |
| RC3-10 / P1 | HTTP-ERROR/UNKNOWN-FIELDS 终止闭锁；RC2-11 | [_checkLatestLocked:351](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L351) 通用异常不清旧资产：先下载成功，再收到 200 body=[]，FormatException 后旧 latest/asset/file 仍可被入口消费。[_getLatestWithRetry:878](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L878) 先按 429/503 重试，不识别未知/终止 errorCode。下载 [167](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L167) 将所有 409 当 ASSET_CONFLICT，410 也不看码；未知/兼容错误会错误刷新。[service:472](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L472) 的 HTTP_STATUS 不闭锁、不保留 requestId。刷新 [408](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L408) 固定 channel=null，丢失显式 beta 查询身份。 | 按状态+稳定码先分类，再决定重试/刷新/终止；坏 JSON/未知响应清可用资产并闭锁，保留 requestId；绑定同一 query/channel。补已有验证包后坏 latest、未知 409/503、兼容下载错误和 beta 刷新。 | 常见 BACKEND_UNAVAILABLE 耗尽已清资产，但其他分支未覆盖；该会话测试事前没有下载，file==null 断言也不证明旧验证文件被清。 |
| RC3-11 / P2 | HTTP-RESUME/DOWNLOAD 的强 ETag、digest、响应流 | [_isStrongEtag:579](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L579) 仍把 abc 等未加引号的非法标签当强 ETag；sidecar [513](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L513) 不校验标签就发 If-Range。206 违规 [208](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L208) continue 前不关闭/消费旧 body，若干头校验退出分支也遗留流。[digest:418](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L418) 依赖可归一化 base64.decode，未核对规范 padding，且找到首个合法项即返回。 | 在接收与 sidecar 读取处校验强 ETag；严格验证已提供 digest 的规范且唯一项。每条早退/重请求路径取消或有界消费旧流，补坏 ETag/digest 与流关闭断言。 | 完全无法解析 digest 时拒绝已修；现谓词的只读算例仍接受 abc，没有真实 Dio 流资源测试。 |
| RC3-12 / P2 | UI 数据流与可恢复状态；RC2-04/16 补查 | [cleanupFirmware:748](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L748) 清 file/verified 不更新 phase/Rx；“忽略” [501](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L501) 不 await/刷新。readyToInstall 忽略后下载仍因 [440](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L440) 的 phase 禁用，旧安装按钮却可能还在而文件已删除。检查按钮 [281](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L281) 不考虑稳定 terminal，仍提供可点“检查更新”但被 service 拒绝。 | 将清包变为受 owner 管理的状态转换，同步文件/阶段/可执行意图；忙碌时不得旁路删除；UI 展示真实禁用原因。补点击忽略后重下载、终态入口、取消保留验证包的交互。 | Obx 局部修复已确认；现 widget 只驱动展示字段，没点击这些入口，不证明转换正确。 |

#### 6.8.2 RC2 子项处置核对

“已修”仅指所述源码矛盾已消除，不代表 Flutter PASS 或整个原 ID 关闭。

| RC2 项 | 当前静态处置 |
|---|---|
| RC2-01 | 原 maxRetries 重名、页面 import、tester 参数已修；其他编译项见 RC3-01。 |
| RC2-02 | 精简 NO_UPDATE/CHANNEL_STOPPED、固件 u32/App 域分离、expectedChannel 已修，正反例未执行。 |
| RC2-03 | ABORT 不再被取消标志直接挡住；public begin 与分片取消见 RC3-03/05。 |
| RC2-04 | start 锁前移、同份字节校验、内部刷新不解锁、提前创建下载 token 已修；入口/代次未闭合，见 RC3-04/05/12。 |
| RC2-05 | BEGIN/END 复用 seq、原 seq 重发、bitmap 回收已加入；跨块、快速断连恢复及截止见 RC3-06/07/08。 |
| RC2-06 | DATA cmd/session/seq 过滤及基础范围、BEGIN session 非零已加；全链校验与旧块 ACK 见 RC3-06。 |
| RC2-07 | 已新增真实 disconnect/connect API；生命周期/重启完成/总截止见 RC3-08。 |
| RC2-08 | adapter 已用 OTA 专用严格 writer，不再回到旧模糊 writer；实际 adapter 测试仍缺，Windows 通知见 RC3-09。 |
| RC2-09 | validateStatus 放行 401/409/410/416，原分类分支不可达已修；分类完整性见 RC3-10。 |
| RC2-10 | resumed+200 截断后再算剩余量，并统一查 200 Content-Length，原长度回归已修；新增测试未运行。 |
| RC2-11 | HTTPS、坏/超长 partial 触发 LOCAL_CORRUPT、部分 token 分流、无法解析 digest 拒绝、常见 503 耗尽清资产已加；剩余见 RC3-05/10/11。 |
| RC2-12 | fake 增加 seq/END/ABORT 和 4 个 HTTP 会话测试属实际改进；oracle、ACK 快照、吞错及真实 BLE 服务状态链见 RC3-02/03/08。 |

#### 6.8.3 实际检查与证据缺口

HEAD：0ef3cc14f6fdbece4f15b45864b94cb1007af735（治理提交，不是本批实现 commit）。
被审实现仍为未提交修改/未跟踪文件，共 19 个产品/测试/workflow 文件，其中 test/ota
有 8 个文件。发现均针对当前字节，不拿前两次诊断为本批复用 PASS。

已执行 git status/log/rev-parse/diff、源码/测试/冻结合同读取、MCU seq/重复 BEGIN/
END/ABORT 核对、SDK 与合同文件检索、git diff --check、Node 只读模型和写入预检。
Node 只是源码/控制流/算术模型，不执行 Dart/Flutter/MCU，不是正式 runner。
辅助检查一次方法截取范围失准已纠正：readDeviceInfo 从第 190 行至下一入口前，
确无上锁赋值；一次 cmd 表达式因尖括号被拒，无产物。fsutil 中文输出识别补全后，
写入前逐级核对无 reparse 通过，未绕过失败的路径守卫写入。

| 检查/证据 | 本轮结果 |
|---|---|
| where flutter / where dart | 均 exit 1，PATH 未找到；没有安装 SDK 或做本地构建。 |
| P3-3 版本化验收合同 | docs/acceptance-contracts 无匹配；实现未提交，未具备审批冻结和 NOT_RUN 矩阵前检条件。 |
| git diff --check | exit 2：既有看板 626 行末尾 CR/空白，另有两个 LF 转 CRLF 提示；不作为新增产品阻断。 |
| flutter analyze / flutter test | NOT_RUN。上表是静态发现，不是伪造的 SDK 输出。 |
| Actions / APK / EXE / 安装 | NOT_RUN，无本批实现 SHA、run URL、APK/EXE SHA-256；Analyze 既有 continue-on-error 仍在，未来须核对实际 step outcome，不能只看 job 绿色。 |
| 真实 HTTP / BLE / 重启重连 / toy 与真包 / P3-4 参数 | NOT_RUN；未部署、烧录或触发任何硬件操作。 |
| validate_bundle.py 正式前检/最终校验 | NOT_RUN，不能为当前脏工作树伪造正式合同或 PASS 矩阵。 |

未进行正式产品观测，未消耗硬件/部署观测配额，不虚构 rerun plan 或正式失败轮次。
P3-3 卡面真机 toy/真包判据与实施 Spec 的 P3-5 归属差异仍待冻结前非实现主会话确认；
本次不豁免、迁移或降低门槛，也不重开已完成 P3-1/P3-2。

#### 6.8.4 批量整改与写入审计

先修本批明确编译错误、会挂起/吞错的测试及同根因产品问题，再经用户明确授权提交/
推送，以 Actions 获得可信 analyze/test 和 APK/EXE 结果。缺 SDK 不授权本地打包或推送；
首次真实产品观测留在后续已批准正式合同，不要求为了准入提前跑真机。

本轮主动写入仅本 research 和 PLAN-OTA-EXEC.md：apply_patch 追加本节、更新 P3-3 状态、
追加复审记录及 §10 日志，保留实现认领。所有命令显式在 D:/github/my/E-Track 下使用
cmd.exe，写前校验规范化目标与完整父链无 reparse。看板必要行尾格式恢复前后规范化
内容一致，保留原 728 个 CRLF 的对应行；不运行 PowerShell、SDK、包管理器或外部输出脚本。

19 个产品/测试/workflow、9 个遗留文件、2 个既有诊断做写前/写后逐文件哈希核对，
不得被文档回写修改。既有诊断仍为：

- .cache/p3-3-prereview/readonly-probes.json：f67ec2fbe82e172b6a36b1165c265b6f81b94f19800eb17277576ef60f46446f。
- .cache/p3-3-prereview/recheck-2.json：b50e01286f39be53202b7c4909beb870a8950a6aece520ef76978d827eb0a328。

未修改产品、测试、workflow、冻结合同或认领，未提交/推送/部署；
本轮未选择任何项目外输出、移动或删除路径。
### 6.9 RC3 第三批整改交付（P3-3-IMPL-20260907，2026-09-08）

对应 §6.8 复审的 12 组问题，本批全部整改完成。交付物只到静态自检；
flutter analyze/test 与 APK/EXE 构建未运行（本机无 Flutter SDK，
验证须待用户授权提交/推送后走 GitHub Actions），正式验收保持 NOT_RUN。

#### 6.9.1 处置总览（对 §6.8.1 权威表）

| 组 | 处置 | 落点 |
| --- | --- | --- |
| RC3-01 编译 | 已修 | transport const 插值引用运行时字段、latest test 常量默认值、transport test static 作用域 |
| RC3-02 测试可信度 | 已修 | session test 去掉 runZonedGuarded 全吞、widget 定量 pump、onNotify 替身隔离 Get.snackbar；本批补真实 startOtaUpgrade 集成测试（见 6.9.3） |
| RC3-03 fake MCU 忠实模型 | 已修 | _McuSim 按 ota_ble_session.c/ota_staging.c 真值重写（seq delta 三分支、BEGIN 幂等/resume、块提交、END sha+durable 校验、ABORT teardown 保留 durable） |
| RC3-04 入口互斥/取消代次 | 已修 | _runExclusive owner 锁（二重入口同步段拒绝、finally identical 只释放自身）+ generation 同步段锚定 + cancelUpgrade 等待 owner 完全退出后才发布 cancelled；集成用例「双 start 拒绝」「取消后旧 ACK 晚到不复活」 |
| RC3-05 取消删除策略 | 已修 | partial 恒删（keepPartial:false 不放宽）；UI 取消对话框按 BLE/下载两阶段给出冻结语义（BLE：MCU durable 保留可续传、已校验包二选；下载：分片恒删）；ABORT 帧级完整性 + 取消旁路预算拦截修复（见 6.9.2-2） |
| RC3-06 ACK 唯一真相 | 已修 | DATA/END ACK durable 单调推进全链校验、END OK 时 durable==total fail closed、跨块 ACK 回收（块尾段 ACK 丢失靠幂等重发回收在途窗口） |
| RC3-07 30 秒总截止 | 已修 | 无 durable 进展预算：writeTimeout 前置 _checkNoProgress、_capByBudget 封顶；跨 resume 预算保留为测试缺口（见 6.9.4） |
| RC3-08 生命周期/重连 | 已修 | _waitForTargetIdentity 三态判定（目标/旧身份继续等/硬件变化终止，60s 截止）+ 页面 connectionStateChanged 订阅、WidgetsBindingObserver 后台停写恢复重读、didUpdateWidget 换设备重读；集成用例「快速重连旧身份不误判」「重启后硬件变化终止」 |
| RC3-09 Windows FFF1 通知 | 已修 | BluetoothAdapter 新增 supportsCharacteristicValueStream/characteristicValueStreamOf，WinBleAdapter 消费 WinBle.characteristicValueStreamOf 事件流（替代轮询读，多片/重复片不丢不去重），OTA 与遥控透传两个订阅路径接入，adapterForTest 注入通道 + 7 用例 adapter 层测试 |
| RC3-10 终止闭锁/资产清理 | 已修 | 非 retryableLater 终止态闭锁全部入口，readDeviceInfo 成功解锁；cleanupFirmware 忙碌拒绝/失败返回 false 不静默 |
| RC3-11 强校验/流清理（P2） | 已修 | latest/download ETag 与 digest 校验、下载流异常路径 drain |
| RC3-12 UI 状态流（P2） | 已修 | 忽略按钮 await cleanupFirmware 且失败区分提示；canCheck 终止态闭锁 + hint；cancelled+hasFile 保留「开始 BLE 传输」入口且不显示误导进度快照 |

#### 6.9.2 关键设计记录

1. **双 oracle 测试结构**：transport test 的 _McuSim 是完整真值模型
   （可注入故障矩阵：ACK 丢失/谎报/延迟、seq 失配、会话超时主动
   ABORT、flash 静默丢失等），覆盖协议层边界；本批新增的集成测试
   _UpgradeFakeBle 是精简 happy path 版（真实 OtaService 全链路 +
   重启状态机），聚焦 service 层编排。两者不复用同一 fake，避免
   注入矩阵复杂度污染集成时序断言。
2. **取消旁路预算拦截修复**：原 _writeFrameChecked 的
   _checkNoProgress 在 allowCancelled 分支之外、_capByBudget 统一
   封顶——预算耗尽时取消路径的 ABORT 帧会被 noProgress 抛断或
   Duration.zero 立即超时，被 abortBestEffort 的 catch(_) 吞掉
   永远发不出，MCU 会话残留 ACTIVE。修复后取消旁路只保留单分片
   writeTimeout 上限，跳过预算检查；正常路径预算语义不变。
3. **generation 同步锚定**：入口同步段（_isUpgrading 置位前）取
   _cancelGeneration 快照，body 内每个 await 后核对；「注册前
   取消」窗口由同步代码先于 body microtask 执行的语义保证。
4. **WinBle 通知流语义**：win_ble 1.1.1 的
   characteristicValueStreamOf 按「订阅时传入的三元组字符串原样
   匹配」回放平台通知事件（WinHelper.subscriptions 反查），无
   格式转换；同值通知不去重（协议层 ACK 幂等承担），多片按流序
   送达（原轮询读版丢片）。
5. **GetMaterialApp 测试宿主**：Get.dialog 依赖 Get.key 挂载，
   取消对话框交互测试必须用 GetMaterialApp 而非 MaterialApp。

#### 6.9.3 本批交付文件

- 新增 test/ota/ota_service_upgrade_test.dart：真实 OtaService +
  完整 MCU 应答 fake 的 startOtaUpgrade 集成测试（补 §6.8 点名的
  「8 个测试文件均无真实 startOtaUpgrade 调用」缺口），5 用例：
  ①端到端成功闭环（read→check→download→start→completed，断言
  MCU 收满 8 段、durable=1024、END sha 复述一致、探测 1 次确认）；
  ②rebootDelayProbes=1 模拟 MCU 未重启完：第一次探测旧身份丢弃、
  3 秒轮询后第二次确认（真实时间，30s 超时上限）；
  ③重启后 hardwareRevision 漂移：identityChanged 终止；
  ④传输在途二次 start：同步段忙锁拒绝（notifyLog 断言）且不打断
  在途传输；⑤传输在途取消：ABORT 送达 MCU、durable 保留、
  cancelled 终态在补发旧 ACK 后不被复活、keepPackage=true 包保留。
  fake 的 dataGate 只挂 ACK 发送不挂帧处理（MCU 侧照常落盘，
  entered barrier 消除取消时序歧义）。
- 新增 test/ota/bluetooth_adapter_notify_test.dart：RC3-09 adapter
  层 7 用例（notify-only 订阅透传、连续多片按序、重复片不去重、
  流取消退订、订阅失败返回 null、遥控初始读失败忽略、可读初始值
  先到）。
- 修改 lib/services/bluetooth_service.dart：adapter 接口扩展 +
  Windows 分支通知流化 + adapterForTest 注入。
- 修改 lib/pages/ota_upgrade_page.dart：取消对话框、终止闭锁、
  连接订阅、生命周期、cancelled 入口。
- 修改 test/ota/ota_service_session_test.dart（RC3-02 重写）、
  test/ota/ota_upgrade_page_test.dart（取消对话框/忽略/终止闭锁/
  生命周期 10 用例）、lib/ota/ota_ble_transport.dart（预算旁路）、
  lib/services/ota_service.dart（owner 锁/取消/三态判定）等，
  此前批次已列 §6.8.2，不重复。

#### 6.9.4 静态自检证据与测试缺口

- 本机无 Flutter SDK（where flutter/dart 均 exit 1），无法运行
  flutter analyze/test；本批用 Python 状态机括号配平（五态：
  code/line_comment/block_comment/squote/dquote）替代正则剔除法
  （正则法对字符串插值产生误报，已弃用）：
  - ota_service_upgrade_test.dart：{} 79/79、() 300/300、[] 35/35
  - ota_service_session_test.dart：{} 56/56、() 306/306、[] 22/22
  - ota_upgrade_page.dart：{} 68/68、() 482/482、[] 41/41
  - bluetooth_service.dart：{} 451/451、() 947/947、[] 41/41
  - ota_ble_transport.dart：{} 157/157（前批）
- 符号级核对：覆写方法签名与 BluetoothService 基类逐字匹配、
  OtaBleCodec 常量/seqCompare/buildInfoPayload 存在性、latest 响应
  mock 用 fromString+application/json 与 download mock 用流式+
  content-length（RC3-11 校验依据）对齐真实解析路径。
- **测试缺口（如实声明）**：跨 resume 的 30 秒无 durable 进展预算
  保留（同一包 BEGIN→取消→重新 BEGIN 续传时预算不应重置）未写
  自动化用例——需要可控边界时钟注入，当前注入面与时钟抖动会使
  断言不稳定；由代码审查保证 _noProgressClock 仅在 transfer 的
  finally 清空（重新 transfer 重置预算，取消不重置）。此缺口不
  影响其余判据，留待 Actions 跑绿后评估是否补可控时钟抽象。
- MCU 残留 ACTIVE 会话的兜底路径（下次升级 BEGIN 前 resume 语义
  + 受控 ABORT teardown）已由协议层幂等保证，未单列用例。

#### 6.9.5 写入审计

本批（2026-09-08 整改）主动写入仅限项目内：
lib/services/bluetooth_service.dart、lib/pages/ota_upgrade_page.dart、
lib/ota/ota_ble_transport.dart、test/ota/ 下 4 个测试文件、
本 research §6.9、PLAN-OTA-EXEC.md 看板（P3-3 保持「进行中」+ §10
日志一行，字节级编辑保留 CRLF 分布）。临时自检脚本
.cache_bracket_check.py 建于 app/bluetooth_flutter_Trace/ 下、用后
即删，无残留；一条错误命令曾在仓库根创建空文件 tmp_p39.py，
发现后立即删除，git status 无残留。9 个未跟踪遗留文件（.P3-5、
.cache-cmake-time-test.cmake、.claude/ 下 7 个脚本 + 2 个既有
诊断）未被触碰。未提交、未推送、未触发 workflow、未运行真机
操作；Actions 验证与版本化冻结合同待用户明确授权后进行。

### 6.10 RC3 第三批整改独立集中复核（2026-09-08）

审查者：Codex（非实现会话）。复核对象为 §6.9 新交付，不是对 §6.8 相同输入
重复派验，也不是第四轮正式验收。**结论：整改未闭合，不接受“RC3-01 至
RC3-12 全部修复、仅待授权”的交付结论；P3-3 保持进行中，正式验收 NOT_RUN。**
以下“已修”均仅指指定源码矛盾已消除，不是 Flutter、Actions 或真机 PASS。
保留实现认领、历史记录及 §6.8.2 已修子项，不把未解决问题重新编号。

#### 6.10.1 输入、范围与复用边界

- 当前 HEAD 仍为 `0ef3cc14f6fdbece4f15b45864b94cb1007af735`。最近提交是治理
  提交，本批实现和 runner 仍未提交。不能以 HEAD 相同推定工作树未变。
- §6.9、两个新增测试文件及现有文件内的新逻辑构成本轮实际交付。当前被审范围为
  21 个产品/测试/workflow 文件：6 个 tracked 输入、5 个 lib/ota 文件、10 个
  test/ota 文件；再按直接依赖核对 DTO/codec、MCU seq/staging、平台库 API、
  pubspec/lockfile、入口及冻结合同。未扩展到其他产品卡或历史验收。
- 没有前批已冻结 Git tree 或完整批次输入锚点，故 `git diff HEAD` 只代表累计实现
  差异，不能充当 §6.8 到 §6.9 的精确增量。本表的“本批修改”由交付记录与当前
  源码交叉核实，不臆造其他文件“未变化”。本轮读前/写前的 44 个文件内存哈希
  核对未见漂移，仅用于保护本次输入，不输出工作树 manifest、不代替 v3 冻结。
- `Flutter` profile 覆盖客户端、依赖配置和 build.yml；test/ota 属 `Validation`，
  现有配置没有可临时改用的逐文件 Flutter 测试 profile。公共 service、codec、
  adapter、fake 与查询/下载相互影响，不能靠某一文件哈希相同复用整项结论。
  正式冻结时仍须审批命令和传递依赖，不能手工缩小校验器的失效范围。
- `docs/acceptance-contracts/` 未检出 P3-3 版本化合同/矩阵。没有原始
  EXECUTED PASS 可复用，本轮不伪造 rerun plan，不运行无输入的正式校验器。
  后续正式复验须由 `validate_bundle.py` 比较冻结 tree/profile、外部输入及
  判据/命令定义，严格按 `required_commands` 执行。

#### 6.10.2 原 ID 逐项处置

依据仍是实施 Spec、binary/XC 冻结合同和执行合同 §7.3；§6.8.1 是问题映射表，
不是新增合同。P1 为功能、可执行性或证据可信度问题，P2 也不降级为风格建议。

| 原 ID | 合同依据 | 本批修改与依赖影响 | 本次证据及剩余问题 | 结论 |
|---|---|---|---|---|
| RC3-01 / P1 | Spec analyze/test/build；原 RC2-01 | 原 transport const 插值、latest 默认值和 static helper 作用域已改正；新增 lifecycle/owner/测试 barrier 又涉及类型与 API。 | [service:335](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L335) 把 `int? gen` 传给 [1091](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1091) 的必需 `int` 参数；[页面:44](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L44)/[103](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L103) 使用锁定 flutter_blue_plus 中不存在的 `BluetoothConnectionStateEvent`/`FlutterBluePlus.connectionStateChanged`，实际 API 是 `OnConnectionStateChangedEvent`/`FlutterBluePlus.events.onConnectionStateChanged`；[session test:619](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L619) 对可空 public 字段 `entered` 直接解引用，不能靠字段 null-check 提升；[query test:7](../../app/bluetooth_flutter_Trace/test/ota/share_links_latest_query_test.dart#L7) 仍有非编译期常量的字符串乘法。前者为整改回归，query const 是同类前次遗漏。 | 部分修复；仍有明确静态编译矛盾，编译器验证 NOT_RUN。 |
| RC3-02 / P1 | fail-closed harness；Spec 服务状态链测试 | 全吞异常的 zone 已移除，四个忙碌展示测试改为定量 pump，新增真实 `startOtaUpgrade` 调用和 entered barrier。 | [session test:108](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L108) 在默认空 `notifyLog` 时传 `onNotify:null`，仍走真实 snackbar；[352](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L352) 等 cancel 完成后才在 [354](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L354) 放行 latest gate，而 cancel 正等待被 gate 卡住的 owner，形成死锁。新增升级正例 [64](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L64) 的 `0x62` 字节转 hex 是 `62...62`，不等于 [92](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L92) 的 `bb...bb`，成功、旧身份再探测、双 start 三例无法确认目标。download 测试 [425](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L425)、[581](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L581)、[600](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L600) 仍用空错误体期待 409/410 刷新，与已改正的按码分类不符。 | 部分修复；新增用例不等于可信、可结束的运行证据。 |
| RC3-03 / P1 | binary §4.4/§4.5/§5；真实 MCU 语义 | public BEGIN 已保存 session；fake teardown 清 RAM、保留 durable，ACK 延迟前快照及 32 位 mask 已改善。 | [fake:1086](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1086) 同包 ACTIVE 分支无条件回 ACK，绕过 `dropAllBeginAcks`，故 [676](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L676) 并非“BEGIN ACK 全丢”。[194](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L194) 谎报 durable=4096 后要求新 BEGIN=0 仍成功，必撞 [transport:204](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L204) 的回退拒绝。快速重连例的真实 seq 问题见 RC3-08。两个 fake 都只核对 END 复述与 durable，不做 MCU [664](../../Libraries/OTA/ota_ble_session.c#L664) 的真实流式 SHA 校验；不能宣称“完整 MCU/整包摘要通过”。 | 部分修复；oracle/注入分支仍不可信。 |
| RC3-04 / P1 | 单一 owner；CANCEL-RECOVERY；Spec 取消后不继续操作 | read/check/download/start 已共用 `_runExclusive`，generation 在同步段锚定，finally 只释放自身。 | [执行器:939](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L939) 恢复 body 前不查取消；[read:230](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L230) 发现/绑定/GET_INFO 之间也不查，注册前或发现中取消仍可新建 transport 并写 GET_INFO。check 的 App-info await 后直接调用 latest，[1095](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1095) 请求前无检查/CancelToken，取消不能停止在途 metadata 请求。取消 [837](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L837) 先 await 文件清理才停止 transport；owner 在 [942](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L942) 解锁后，取消仍可能在 [859](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L859) 删除新操作正在使用的包。清包入口同根因见 RC3-12。 | 部分修复；不是完整取消/互斥闭环。 |
| RC3-05 / P1 | HTTP-RESUME:271；FLUTTER-TRANSPORT:1057；取消帧完整性 | service/UI 已不再提供显式取消保留 partial；完成包保留/删除二选已接入；ABORT 取消旁路不再被预算直接拦截。 | [abortBestEffort:415](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L415) 与 [写帧:726](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L726) 没有串行 owner/队列。允许 DATA 写完整帧不能阻止 ABORT 同时插入；[测试:718](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L718) 先等 transfer 退出、再发 ABORT，绕开真实服务并发路径。下载 [79](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L79)/[310](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L310) 的校验/rename 仍无 token 检查；[cancel:339](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L339) 不等 sink 关闭就删，[617](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L617) 吞删除失败，不能保证取消后无 partial/sidecar/迟到完成文件。 | 部分修复；删除策略文案已修，执行原子性未修全。 |
| RC3-06 / P1 | binary §5.5/§5.6，ACK 是唯一进度真相 | BEGIN durable/bitmap 基础范围、END durable==total、跨块回收旧 inFlight、异步 ACK_ABORT 消费已加入。 | [onAck:902](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L902) 仍只查全包范围/对齐与单调性，[928](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L928) 没有限制当前可提交窗口。8192B 包首块的在途 ACK 报 durable=8192/bitmap=0 会被接受并清 inFlight，可跳过第二块而发 END。现新增测试只查 BEGIN 的 `>total`，不覆盖包内跨窗伪跳跃；BEGIN 帧头/payload session 一致性及 END bitmap 也未统一校验。 | 部分修复；跨块回收已修不等于 ACK 全链合法。 |
| RC3-07 / P1 | BLE-TUNING/RETRY-POLICY：30 秒无 durable 进展 | Stopwatch 覆盖 transfer，发窗逐段查预算；写和等待加入 cap，取消 ABORT 旁路保留单次超时。 | [744](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L744) 在帧外计算一次 `perChunkTimeout`，分片循环既不重算剩余预算也不检查截止。MTU=23 的 142B DATA 有 8 片，每片 9s 均未超 10s，但整帧可耗 72s，违反 30s。BEGIN [570](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L570) 也复用写前/首次调用算出的 timeout，不按本次剩余量封顶。现“慢 ACK”不模拟慢分片写；全丢 BEGIN 注入另有 RC3-03 问题。 | 部分修复；总截止仍可被绕过，非仅跨 resume 测试缺口。 |
| RC3-08 / P1 | DEVICE-DTO:118；BLE-LIFECYCLE；FLUTTER-TRANSPORT:1058 | DTO 新增地址绑定，重启后旧身份继续等、目标身份确认、硬件变化终止；页面补生命周期和连接回调。 | [页面:79](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L79) 只改 `_backgrounded`，不暂停/取消 service 的在途 DATA/END；连接事件只改页面目标，service/channel 无真实连接代次订阅，显式设备断连仍可保留旧 DTO。页面销毁后这些回调也消失。重启等待 [995](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L995) 仍在 disconnect 之后才设截止，connect/discover/bind/INFO/dispose 均未用剩余总预算。快速恢复 ACTIVE 时，落后 seq 的 OK ACK 在 [890](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L890) 被回收，即使 bitmap 未确认该段；无 pending 就不会触发重发超限 ABORT，能按错误 offset 顺序填洞，真实 MCU 流式摘要失败。新增 [734](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L734) 对 ABORT/BEGIN 次数的期待不由当前路径保证。 | 部分修复；后台、真实重连及总截止未闭合。 |
| RC3-09 / P1 | 精确 FFF0/FFF2/FFF1；真实通知与 adapter 调用链 | WinBleAdapter 已调用真实特征事件流，OTA 不再轮询/去重；新 7 例覆盖 service 订阅分支。 | 通知流 API 与 lockfile 的 win_ble 1.1.1 源码相符，此子项源码已修。直接上游 [能力读取:1920](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1920)/[通知能力:1727](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1727) 却仍调用 [_getProperty:1994](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1994) 的 `object.getField(...)`；实际 `BleCharacteristic` 只有 `uuid`/`properties`/`toJson`，没有 getField，能力全回 null，正常 FFF2/FFF1 被严格发现拒绝。新 fake 直接传三元组给订阅方法，没有走发现入口。此为该路径共享依赖的前次遗漏，不另编新 ID。 | 通知轮询子项源码已修；整个 adapter 路径部分修复，Windows BLE 未实测。 |
| RC3-10 / P1 | HTTP-ERROR/UNKNOWN-FIELDS；稳定终止闭锁 | 坏 JSON 对象的 FormatException 会清资产，409/410 已按码分流，刷新记住显式 channel，部分下载错误携带 OtaHttpError。 | [latest retry:1099](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1099) 仍先按 429/503 重试，不先识别未知/终止码；未知 503 后若下一次返回 200，仍可能继续选包。下载 [validateStatus:118](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L118) 未放行 400/426 等供统一分类，落入 [service generic catch:580](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L580) 而不闭锁；空/坏错误体经 [_tryHttpError:521](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L521) 返回 null，也只置 failed，保留可重试旧清单。requestId header 在这些路径丢失。 | 部分修复；错误分类和终止入口未闭合。 |
| RC3-11 / P2 | HTTP-RESUME/DOWNLOAD：强 ETag、digest、流关闭 | 裸 ETag 已不被当前响应谓词接受；digest 的唯一 sha-256 项和 padding 长度增加校验；若干早退分支会 drain。 | [ETag:637](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L637) 的 `[!-~]` 包含双引号，仍接受 `"a"b"`；[sidecar:568](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L568) 未校验旧标签就发 If-Range，缺强 ETag 时 [429](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L429) 还跳过一致性检查。[_drainBody:488](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L488) 及错误体 fold 无大小/时间边界，下载 Dio 又无 receiveTimeout，违规不结束的响应可阻塞清理和重试。现测试无这类流取消/有界关闭断言。 | 部分修复；不能以“有 drain”关闭资源问题。 |
| RC3-12 / P2 | UI 用户意图/领域状态；清包与恢复 | 忽略按钮已 await，readyToInstall 清包回 idle；canCheck 与 terminal 对齐，cancelled+hasFile 提供入口。 | [cleanup:877](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L877) 只查 busy，不取得 owner，exists/delete 期间仍可启动新传输，属于 RC3-04 的同根因调用点。取消 [850](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L850) 先发布 cancelled 再异步删除，清空非 Rx file/verified 后无新阶段通知；页面 [1086](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L1086) 不 await/刷新，可能留下已删包的传输入口。稳定终态提示“重新读取”时 DTO 通常非 null，但 [436](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L436) 只在 DTO==null 才提供重读按钮，当前页无对应恢复意图。 | 部分修复；忙碌/删除/恢复的真实状态转换仍需服务与 UI 联测。 |

#### 6.10.3 反例、纠正与测试边界

- **RC3-02 的 gate 环**：测试 `await cancelUpgrade()` -> service 等 `_ownerDone`
  -> owner 等 `_getLatestWithRetry()` -> fake `await latestGate.future` -> gate 只在
  cancel 返回后的下一行 complete。不能靠加大测试 timeout 或重新全吞异常修复。
  onNotify 应当真正隔离 UI，不能以空日志代表“不注入”。
- **RC3-03 的 oracle 不得反向定义合同**：空 409/410 错误体不应被产品改回
  “已归档/已禁用”以迁就旧测试；测试正例应提供真实稳定码，并另测坏体闭锁。
  伪造 durable 前进后又回退不是普通可恢复丢段，不要求实现者删除 fail-closed
  校验来满足“谎报后仍成功”。fake 若只覆盖复述校验，必须收窄证据声明。
- **取消分片只读算例**：按冻结 CRC16 组一帧 142B DATA，在前 20B 后插入完整
  10B ABORT，再跟 DATA 余片。流总长 152B，DATA 候选 CRC 失败，完整合法
  ABORT 数为 0。当前代码无帧级串行化，允许该交错；仅“继续写完 DATA”不够。
  必须覆盖真实 `cancelUpgrade` 路径与受控 MTU 分片 barrier，不能先等待旧发送退出。
- **RC3-07 算术纠正**：当前 DATA 是 8+4+128+2=142B；MTU=23 的净荷是 20B，
  共 8 片，不是旧记录算例中的 7 片。每片 9s、帧开始 cap=10s 时累计 72s。
  这是控制流反例，不是实测耗时。§6.9.4 所需的跨 resume 用例应检查同一次
  transfer 内受控 ABORT/BEGIN 的剩余预算，不把用户结束取消后新建 transfer
  强行规定为沿用旧定时器；当前普通分片写的截止缺陷仍须先修。
- **快速 ACTIVE 重连只读模型**：按现有测试 expected_seq=16、bitmap=31，
  选择合法即时 ACK 顺序，实际新收段可为 `20..31,5..19`，而非先补 `5..19`。
  含前置段 `0..4` 的累计接收恰 4096B，BEGIN（含测试准备）2 次、ABORT 0 次，
  不等于测试期待的 3/1。测试包原 SHA 为
  `2c2691040bbd48c838587cf04bc964133bd58f64234b69e2cad75824e945d68d`，按真实 MCU
  `boot_sha256_update` 接收顺序所得为
  `5fbbb7eed35e538c54ea13575a6b659358aa5f4ef78047a370131fcbb48cd0bc`。
  此模型不执行 Dart/MCU，只说明 fake 省略真实 SHA 时漏掉的产品路径；不能修改
  MCU 或冻结合同来适配客户端。模型初版误把 durable 前的幂等重发也计入摘要，
  已按 MCU :550-558 纠正，以上仅采用纠正后的 4096B 结果。
- **平台库依据**：只读获取 pub.dev 的两个锁定版本归档，在内存解压核对 API，
  未安装 SDK/依赖、未落盘下载文件。flutter_blue_plus 1.35.5 归档 SHA-256 为
  `bfae0d24619940516261045d8b3c74b4c80ca82222426e05ffbf7f3ea9dbfb1a`，win_ble 1.1.1 为
  `2a867e13c4b355b101fc2c6e2ac85eeebf965db34eca46856f8b478e93b41e96`，均与 pubspec.lock
  一致。前者 `lib/src/flutter_blue_plus.dart:96` 提供 events，
  `lib/src/bluetooth_events.dart:4/72` 提供上述实际事件 API；后者
  `lib/src/models/ble_characteristic.dart:3` 与 `lib/src/win_ble.dart:362` 分别证明
  capability 对象形态与通知流签名。不能用未实际执行的 adapter fake 替代平台实测。

#### 6.10.4 实际执行与正式准入

| 检查/命令 | 本轮实际结果 |
|---|---|
| `git --no-optional-locks rev-parse --show-toplevel --show-prefix --git-common-dir HEAD`；`status --short --untracked-files=normal`；`log -8 --oneline`；`diff --stat`/指定文件 diff | 根目录与 HEAD 如上；实现脏文件保留。status 对既有 `.manifest-test-mzl4deqo/`、`.pytest_cache/` 报无法读取，未清理或擅自宣称其内容已审计。 |
| `where flutter`；`where dart` | 各 exit 1，PATH 未找到；项目也无 `.dart_tool/package_config.json`。未安装 SDK 或本地构建。 |
| `rg`/`type`/Node 只读源码、合同、测试和调用链检查 | 完成本表静态核对。Everything 查询因 IPC 未运行失败，未启动该程序；一次非锁定 Flutter 文档读取超时，未作为任何结论的依据。 |
| `node -p process.version`；Node 内联字节/控制流模型 | Node v24.13.0；CRC 公开向量复算 0x29B1；摘要 fixture 不相等、ABORT 交错、72s 分片预算、跨窗 ACK、ETag 和 ACTIVE seq 反例见上。只读模型，不是 Dart 测试或正式 runner。 |
| `git --no-optional-locks diff --check` | 写前 exit 2：既有看板 626 行尾 CR/空白，以及页面/service 两个 LF->CRLF 提示。此为接手时已有状态，不虚报全绿，不作为新增产品缺陷。 |
| `fsutil reparsepoint query <目标及完整父链>`；Node realpath/目录边界核对 | 两份文档及到 D:/ 的 8 个唯一链路节点均明确返回非 reparse point，规范化实际目标均在活动根内。Node 子进程方式未取得有效输出时没有写入，改为直接 cmd/fsutil 核对后才修改文档。 |
| Flutter analyze/test；Actions APK/EXE；安装、真实 HTTP/BLE/重启/真机 toy/真包/P3-4 参数 | 全部 NOT_RUN。本轮没有实现 commit、对应 run URL 或产物哈希；Analyze 仍有既有 continue-on-error，今后须看实际 step outcome，不能只看 job 绿色。 |
| v3 合同/NOT_RUN 矩阵前检、正式观测、最终校验、rerun plan | 全部 NOT_RUN；没有可复用正式 PASS，不构造失败轮次，硬件/部署观测消耗 0。 |

下一批应在同一范围内集中修复源码和测试，先消除类型/API、循环等待和错误 oracle，
再对 owner/取消/预算/连接/HTTP 分类的共享路径补定向自测。本会话不兼任实现者。
本机不能执行的 analyze/test 如实保留；需要 Actions 时先获得针对已审稳定提交的
commit/push 或 workflow 授权，不能把“待 CI”当作源码已闭合。

正式验收还须满足实现与 runner 已提交、合同审批冻结、执行工作树门禁和 NOT_RUN
矩阵前检。P3-3 卡面 toy/真包真机判据与 Spec 末条 P3-5 归属差异仍待冻结前确认；
§9 的 P3-1-v2 历史裁定明确由 P3-3 承接，不能只引用实施报告就自行豁免或迁移。
当前不重开 P3-1/P3-2 或其他历史验收，不修改冻结判据或已批准 profile。

#### 6.10.5 写入审计

本轮主动写入仅本 research（追加 §6.10）与 `PLAN-OTA-EXEC.md`（P3-3 动态更新、
追加本次集中复核及 §10 日志）。所有执行工作目录显式指定为
`D:/github/my/E-Track`，使用 cmd.exe；写前完成上述规范化路径和完整父链检查。
文档回写不改变 schema、profile 或 runner，仅做定向结构、历史保留与输入保护检查，
不借治理记录重跑历史产品/硬件回归。

保留 728 个原有 CRLF 对应行，不把行尾格式化混入内容整改。产品/测试/workflow、
9 个遗留文件、2 个既有诊断及其他只读输入由本轮读前/写后哈希复核保护；本轮未改
产品/测试、未执行旧临时脚本、未运行 PowerShell、未创建外部输出/缓存、未移动或
删除任何文件，未 commit/push/dispatch/部署/烧录。平台包读取只在内存，辅助检查
结果只写入本节，不另建 manifest、证据包或测试副本。
### 6.11 RC3 第四批整改交付（P3-3-IMPL-20260907，2026-09-08）

交付者：Claude（实现会话，承接 §6.10 独立复核）。整改对象为 §6.10.2 逐项
处置表确认未闭合的 RC3-01 至 RC3-12，不重新编号。本批交付＝源码/测试修改 +
静态核对；**Flutter analyze/test、Actions APK/EXE、真机全部 NOT_RUN**（本机
无 Flutter SDK，未获 commit/push 授权）。下表「已修」仅指已完成代码修改且
静态核对未再发现 §6.10.2 所列矛盾，不是运行验证通过。P3-3 保持进行中。

#### 6.11.1 本批修改文件与编辑量（从会话记录重建）

96 次 Edit（无新建文件；`.github/workflows/build.yml` 与
`lib/config/share_links.dart` 为更早批次遗留脏文件，本批未触碰）：

- 实现（lib，45 次）：[ota_download.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart) 17、
  [ota_service.dart](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart) 11、
  [ota_ble_transport.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart) 10、
  [ota_upgrade_page.dart](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart) 5、
  [bluetooth_service.dart](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart) 2。
- 测试（test/ota，51 次）：ota_ble_transport_test 19、ota_service_upgrade_test 11、
  ota_download_test 9、ota_service_session_test 5、bluetooth_adapter_notify_test 4、
  ota_upgrade_page_test 2、share_links_latest_query_test 1。

#### 6.11.2 原 ID 逐项处置

| 原 ID | 合同依据 | 根因（详见 §6.10.2） | 实际修改及共享依赖 | 源码整改状态 | 实际执行证据 | 未执行项/剩余风险 |
|---|---|---|---|---|---|---|
| RC3-01 | Spec analyze/test；原 RC2-01 | 四处静态编译矛盾（可空传必需参数、不存在的事件 API、可空 public 字段解引用、非 const 字符串乘法） | `_checkLatestLocked` 增 `int? generation` 参数并贯穿重试与发布（[service:340](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L340)），调用方以 `_runExclusive` 的非空代次传入；页面改用 1.35.5 实际 API `OnConnectionStateChangedEvent` + `FlutterBluePlus.events.onConnectionStateChanged`（[页面:44-48](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L44)/[116](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L116)），订阅异常退化为一次性解析；session test 的 `entered` 改为 adapter 构造注入 `Completer<void>?`（test:85/88/223），不再解引用可空 public 字段；query test 改 `final validSha`（test:9-10）。 | 已完成代码修改；grep/sed 核对四处未再发现矛盾 | 静态核验命令见 6.11.3；无编译器验证 | analyze NOT_RUN（无 SDK）；页面事件 API 仅静态对照 §6.10.3 的 flutter_blue_plus 1.35.5 归档源码 |
| RC3-02 | fail-closed harness；Spec 服务状态链测试 | 空 notifyLog 走真实 snackbar、cancel/latest gate 死锁环、hex 摘要 fixture 混淆、空错误体期待与按码分类矛盾 | session test `makeService` 默认注入 onNotify 收集器（空 `notifyLog` 不再触 snackbar）；latest gate 改为在发起 cancel 前完成（死锁环拆除，测试不再依赖 cancel 返回后放行）；upgrade test 摘要 fixture 修正为 `List<int>.filled(32, 0x62)` → hex `'62'*32`，文件头注释固化「0x62 是 ASCII 'b'，勿与 hex 'b'(0xBB) 混淆」口径；download test 409/410 正例补真实稳定码 errorBody（ASSET_ARCHIVED/ASSET_DISABLED），空体改为 fail-closed 闭锁断言（见 RC3-10/11 组）。 | 已完成代码修改；测试用例与 lib 分流语义逐行对照 | 静态写入与逐行对照；未运行 | flutter test NOT_RUN；「测试可信」仍待真实运行佐证 |
| RC3-03 | binary §4.4/§4.5/§5；真实 MCU 语义 | fake 不做 MCU 真实流式 SHA 校验；ACTIVE 分支绕过注入；谎报 durable 与回退拒绝冲突 | 两个 fake（transport test `_McuSim` 与 upgrade test `_UpgradeFakeBle`）统一双层流式 SHA 模型：`_stagedBytes`（journal 持久字节，块提交追加、erase 清零）+ `_shaBytes`（会话层，BEGIN 重置为前者副本、新段按接收顺序 append、END 一次性 sha256 比对）＝ [ota_ble_session.c:664](../../Libraries/OTA/ota_ble_session.c#L664) 内容级摘要语义；ACTIVE 分支尊重 `dropAllBeginAcks` 注入；BEGIN durable 回退/越界与 transport 回退拒绝 fail-closed 对齐；END 复述一致但内容不符 → ERR_SHA 并 erase。 | 已完成代码修改；两个 fake 均带流式 oracle（test/ota/ota_ble_transport_test.dart:1252-1291、ota_service_upgrade_test.dart:724-858） | 静态核对 fake 与真值 :377-702 语义映射；未运行 | flutter test NOT_RUN；「完整 MCU/整包摘要通过」的运行证据待真机/CI |
| RC3-04 | 单一 owner；CANCEL-RECOVERY；Spec 取消后不继续操作 | 恢复 body 前不查取消、read 链与 latest 请求无取消、cancel 清理顺序倒置、owner 解锁后删新操作正用的包 | `_runExclusive` finally 仅当代次未变才复位（防取消后旧 owner 复位新操作状态）；read 链发现后查代次再绑定/GET_INFO；check 的 App-info await 后带代次检查并以 `_activeLatestToken` 挂接在途 latest（cancelUpgrade 第一时间取消）；cancelUpgrade 顺序改为 取消 latest token → 取消下载 token → transport abort → 下载 cancel → `await owner` → owner 空闲才删包（[service:862-924](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L862)）。 | 已完成代码修改；调用链静态核对 | 静态核对 _runExclusive 六个调用点（read/check/download/start/cleanup/cancel 内删包）；未运行 | flutter test NOT_RUN；并发时序仅由测试静态覆盖（upgrade test 传输在途二次 start/取消两例） |
| RC3-05 | HTTP-RESUME:271；FLUTTER-TRANSPORT:1057；取消帧完整性 | ABORT 与 DATA 分片写无串行 owner 可交错半帧；下载校验/rename 无 token 检查；cancel 不等 sink 关闭就删；吞删除失败 | 写帧串行化：`_writeFrameChecked` 更名 `_writeFrameLocked` 并经帧写锁串行（[transport:799-815](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L799)，ABORT 与 DATA 分片不再交错）；下载 `cancel` 先有界等待在途 download future（`_inFlight` 表）再删 partial/sidecar；整文件校验通过后 rename 前核对取消令牌；`invalidatePartial` 统一删除路径且失败上报（不再吞）。 | 已完成代码修改 | 静态核对锁序与取消路径；transport test 增受控 MTU 分片 barrier + 真实 cancelUpgrade 交错用例（静态写入） | flutter test NOT_RUN；交错反例的运行验证待 CI |
| RC3-06 | binary §5.5/§5.6，ACK 是唯一进度真相 | onAck 无当前可提交窗口限制，跨窗伪跳跃可清 inFlight 跳块发 END；BEGIN/END 校验不统一 | onAck 增跨窗伪跳跃 fail closed：`ack.durableOff - durableOff > blockSize` 记畸形（[transport:1000-1009](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L1000)），8192B 包首块在途 ACK 报 durable=8192/bitmap=0 被拒；BEGIN ACK `reset` 过同链 `_durableValid`/`_bitmapValid`；END OK 核对 durable==total。 | 已完成代码修改；§6.10.3 的 8192B 反例路径已封堵 | 静态核对；transport test 跨窗伪跳跃负例（静态写入） | flutter test NOT_RUN |
| RC3-07 | BLE-TUNING/RETRY-POLICY：30 秒无 durable 进展 | 帧外一次 perChunkTimeout，MTU=23 的 8 片各 9s 累计 72s 绕过总预算；BEGIN 复用写前 timeout | 分片循环内逐片重算 `perChunkTimeout` 并按剩余预算封顶（[transport:841-845](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L841)）；BEGIN ACK 等待以剩余预算封顶（重试每轮不再固定 2s）。 | 已完成代码修改；§6.10.3 的 72s 控制流反例已封堵 | 静态核对；transport test 慢分片写用例（静态写入） | flutter test NOT_RUN |
| RC3-08 | DEVICE-DTO:118；BLE-LIFECYCLE；FLUTTER-TRANSPORT:1058 | 页面只改标志不暂停在途 DATA/END；重启等待不用剩余预算；快速重连 MCU 仍 ACTIVE 时低 seq 幂等 ACK 被当写入确认按错误顺序填洞 | transport 增 `_pauseGate`/`_waitIfPaused`（发送/重发/读取三循环挂起，[transport:248/270/317/485](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L248)），cancel/dispose 释放暂停门；页面对 paused/inactive 调 service 暂停、resumed 恢复；重启等待 deadline 前移到 disconnect 之前、循环内查剩余预算；快速重连幂等 OK（durable 未推进且权威位图不含该段）fail closed 记 ERR_STATE → 传输循环 ABORT teardown + BEGIN 重对齐（[transport:1011-1027](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L1011)），不按错误 offset 顺序填洞。 | 已完成代码修改；§6.10.3 快速重连模型（真实接收顺序 `20..31,5..19`）由 ERR_STATE fail-closed 阻断 | 静态核对；transport test 快速重连用例改真实流式 SHA 语义 fake（静态写入） | flutter test NOT_RUN；后台暂停/真实重连行为待 Windows CI 与真机 |
| RC3-09 | 精确 FFF0/FFF2/FFF1；真实通知与 adapter 调用链 | 能力读取走 `object.getField(...)`，真实 win_ble `BleCharacteristic` 无该成员，能力全回 null 正常特征被拒 | `_getProperty` 对 'uuid'/'properties' 直接成员访问；新增 `_propField` 按 win_ble 1.1.1 `Properties` 的 9 个 `bool?` 字段读取、`_propContains` Map/List/字段三分支（[bluetooth_service.dart:1742-1816/2013-2072](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1742)）。测试用真实 `win_ble.BleCharacteristic`/`Properties` 对象覆盖「发现→精确选择（fff5 可写诱饵负例）→写入→订阅→通知」链；Windows 分支以 `skip: !Platform.isWindows` 门控，由 build.yml windows-2022 job 执行；另补重新绑定资源所有权 2 例（退订一一对应、失败不留残留流）。 | 已完成代码修改；win_ble 1.1.1 归档源码级核对（构造器命名参数、无 getField、进程式连接器导入安全） | win_ble 1.1.1 归档下载解包至项目内 `.cache/win_ble-1.1.1/`，src.tar.gz SHA-256 `2a867e13c4b355b101fc2c6e2ac85eeebf965db34eca46856f8b478e93b41e96`，与 §6.10.3 复核者独立下载的哈希一致 | 本机无 SDK 无法运行；Windows 发现链用例仅静态写入；真实 Windows BLE 实测 NOT_RUN |
| RC3-10 | HTTP-ERROR/UNKNOWN-FIELDS；稳定终止闭锁 | latest 先按 429/503 重试不先分类，未知码可被后续 200 洗成成功；下载 400/426 落 generic catch 不闭锁；requestId 丢失 | latest retry 改分类先于重试（仅 `isAutoRetryable` 网络类/429/503 进重试，稳定码与未知码直接闭锁）；终止闭锁扩展到空/坏错误体的稳定 4xx；下载 `validateStatus` 受控放行 + 非受控状态经 Dio badResponse 统一转换 `HTTP_STATUS`（`OtaDownloadException` 增 `httpStatus`，401/409/410 携带 `httpError`）；闭锁文案携带 requestId/errorCode。测试负例组：409/410 空体 fail closed 不猜刷新、400/426 统一转换、401 超大错误体按裸状态码闭锁、未知码不被 200 洗白。 | 已完成代码修改；lib 看码分流（L167-204/207-268）与测试逐行对照 | 静态核对；download test RC3-10/11 组 8 用例（静态写入） | flutter test NOT_RUN；真实 HTTP 服务端行为实测 NOT_RUN |
| RC3-11 | HTTP-RESUME/DOWNLOAD：强 ETag、digest、流关闭 | ETag `[!-~]` 含双引号接受 `"a"b"`；sidecar 不校验旧标签；drain/fold 无界；下载无 receiveTimeout | `_isStrongEtag` 字符集改 `[!#-~]`（排除内部未转义引号 0x22）；sidecar 读取侧同标准校验（坏 ETag 置 null → 作废 partial 从零重下，不发 Range/If-Range）；206 响应 ETag 非强走 ifRangeSent 违规两轮请求重下；`_drainBody` 增 `maxBytes`（64KB）有界消费；下载 Dio 增 receiveTimeout；Content-Digest 保持唯一 sha-256 项 + 规范 base64 校验。测试：sidecar/响应两侧坏 ETag、drain 字节级有界观测（`deliveredBytes` 计数的 async\* 生成器在订阅取消后停止）、digest 多项/短 base64 负例。 | 已完成代码修改；两侧 ETag、有界 drain、digest 语义静态核对 | 静态核对 + 测试静态写入 | flutter test NOT_RUN；恶意/超大响应实测 NOT_RUN |
| RC3-12 | UI 用户意图/领域状态；清包与恢复 | 清包只在入口检查一次 busy；取消先发布再异步删除；稳定终态无实际可执行的恢复入口 | `cleanupFirmware` 纳入 `_runExclusive`（清包期间新传输入口确定性被拒，[service:946-980](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L946)）；`cancelUpgrade` 删包与 cancelled 终态在 owner 退出后同一发布点一次性成立；页面在终止闭锁但身份快照仍在时提供「重新读取身份解锁」实际可执行入口（OutlinedButton → readDeviceInfo 成功即清终止态恢复查询链）；取消按钮 await cancelUpgrade 后刷新 UI。测试：真实 service 状态转换 3 例（清包 owner 互斥、取消删包一次性一致、终止闭锁经真实 readDeviceInfo 解锁后完整走通传输——MCU durable 已满时 BEGIN 续传直达 END）+ page 恢复入口用例（fake readDeviceInfo 对齐真实契约清 terminal）。 | 已完成代码修改；owner/发布/入口三链静态核对 | 静态核对 + upgrade/page test 静态写入（upgrade test:305-416） | flutter test NOT_RUN；真实 UI 联测待 Windows CI |

#### 6.11.3 实际执行与证据

| 检查/命令 | 本轮实际结果 |
|---|---|
| `git --no-optional-locks status --short` | 脏文件与 gitStatus 基线一致（第三批起累计），本批新增修改均落在既有 lib/test 文件内；9 个遗留未跟踪文件与 2 个既有诊断保留未动。 |
| grep/sed 逐点核验 | RC3-01 四处矛盾消除；`_runExclusive` 六调用点；transport 写帧锁/`perChunkTimeout`/`_waitIfPaused` 三循环挂起/onAck 跨窗 fail closed/幂等 OK 判定；download validateStatus 分流、`_drainBody` 边界、`_isStrongEtag` 字符集；bluetooth_service `_getProperty`/`_propField`/`_propContains`；service 文案（`升级已在进行中`/`固件文件不存在`/`固件包已清理`/`设备身份已确认`/`已进入终止状态`）与测试断言逐字一致；fake MCU BEGIN/END 对 durable 已满续传（跳 DATA 直达 END、流式 SHA 重建匹配）的闭环推演。 |
| win_ble 1.1.1 归档核对 | `curl` 下载 pub.dev 归档 + `tar` 解包至项目内 `.cache/win_ble-1.1.1/`（仓库既有忽略目录）；src.tar.gz SHA-256 `2a867e13c4b355b101fc2c6e2ac85eeebf965db34eca46856f8b478e93b41e96`，与 §6.10.3 复核者记录一致。核对结论：`BleCharacteristic({required this.uuid, required this.properties})`、`Properties` 9 个 `bool?` 字段、无 `getField`、`discoverServices` 返回 `List<String>`、`characteristicValueStreamOf` 命名参数三元组、WinConnector 为 Process.start 进程式（flutter_test 导入安全）。 |
| Node transcript 提取（`node .claude/list_batch4_edits.js`） | 本批 96 次 Edit 的文件/次数分布见 6.11.1，用于交付记录重建，不作为源码证据。 |
| `python` 行尾检查 | research 文件纯 LF（CRLF=0）、UTF-8、以换行结尾；本节以 LF 追加，不触碰 §6.8/§6.9/§6.10。 |
| `where flutter`；`where dart` | 沿用 §6.10.4 结论（各 exit 1，无 SDK）；本批未安装 SDK、未本地构建。 |
| Flutter analyze/test；Actions APK/EXE；真机 BLE/J-Link | **全部 NOT_RUN**。测试仅静态写入未运行；Actions 未触发（无 commit/push 授权）；硬件观测消耗 0。 |

#### 6.11.4 未执行项与剩余风险

- **Flutter analyze/test NOT_RUN**：本机无 SDK。本批全部测试（含 RC3-09 Windows
  发现链组、RC3-10/11 负例组、RC3-12 真实 service 状态转换）只完成静态写入，
  未经过编译器与测试宿主检验——不能排除类型/导入/语法层的新矛盾。
- **Actions APK/EXE 未执行**：未获 commit/push/workflow 授权（Actions 构建要求
  不是推送授权）。windows-2022 job 是 RC3-09 Windows 发现链用例的唯一可执行
  宿主；ubuntu job 会按 group skip 跳过该组。
- **真机/J-Link NOT_RUN**：后台暂停、真实重连、MCU 快速恢复 ACTIVE 等 BLE
  时序行为仅静态覆盖。
- `lib/config/share_links.dart` 与 `.github/workflows/build.yml` 为更早批次遗留
  脏文件，本批未触碰，其状态由前批交付记录负责。
- P3-3 卡面 toy/真包真机判据与实施 Spec 的 P3-5 归属差异仍待冻结前确认，
  本批不自行豁免、迁移或降低。

#### 6.11.5 写入审计

本批主动写入全部位于活动根 `D:/github/my/E-Track` 内：

- 产品/测试：`app/bluetooth_flutter_Trace/lib/`（5 文件）与
  `app/bluetooth_flutter_Trace/test/ota/`（7 文件），共 96 次 Edit。
- 本 research 追加 §6.11（LF 追加，不改既有节）。
- `PLAN-OTA-EXEC.md`：P3-3 动态回写 + §10 日志追加一行（Python 字节级编辑
  保 CRLF）。
- 项目内忽略目录 `.cache/win_ble-1.1.1/`：win_ble 1.1.1 归档解包（只读核对
  用）；`.claude/list_batch4_edits.js`：transcript 提取辅助脚本。

未执行：commit/push/merge/workflow dispatch/部署/烧录/设备复位；未修改项目外
SDK、缓存或工具链；未清理任何遗留文件或历史产物；未创建验收合同、未填 PASS
矩阵、未把卡置「完成」。本批自测与正式验收分开记录；正式验收仍须由非实现
独立会话在实现与 runner 提交、合同审批冻结、执行工作树门禁与 NOT_RUN 矩阵
前检满足后推进。

### 6.12 RC3 第四批整改独立集中复核（非正式轮次，2026-09-08）

审查者：Codex（非实现独立会话）。接手对象为本文件 §6.11 的新交付，
不是对 §6.10 的相同输入重复开审。依据仍为实施 Spec、冻结 XC/binary 条款
及验收执行合同 §5、§6、§7.1、§7.3；前审意见与本节均不新增合同。

结论：**整改未闭合，P3-3 保持进行中；正式验收 NOT_RUN。**
下文“已修”只指注明的源码子项，绝不表示 analyze/test、Actions 或真机通过。
本次未修改产品代码、测试、workflow、冻结合同或实现认领人。

#### 6.12.1 输入范围、依赖与准入

- 当前 HEAD 仍为 0ef3cc14f6fdbece4f15b45864b94cb1007af735，最新提交是治理提交。
  工作树仍有 7 个 tracked 脏文件（包括看板），lib/ota、test 和本 research
  仍未跟踪。§6.11 以及当前代码中的帧写队列、latest CancelToken、双层摘要
  fake、Properties 字段读取和新增用例，足以确认有实际新交付，不能因 HEAD
  相同认定代码未变。
- §6.11 申报本批修改 5 个 lib 文件和 7 个测试文件；当前累计受审范围为
  10 个产品 Dart 文件、10 个 OTA 测试文件及 build.yml，共 21 个输入。
  本次沿这些输入作定向源码/测试核对，并核查直接 MCU、codec/DTO/query、
  依赖锁文件、平台 API、UI 入口和合同。不执行旧临时脚本，不重验 P3-1/P3-2。
- 没有上一批完整输入锚点或冻结 Git tree，无法独立重建“96 次 Edit”或证明
  其他文件跨批次完全未变。git diff HEAD 是累计差异；§6.11 的编辑量只作
  实现方交付说明，不充当源码或运行证据。47 个相关/遗留文件的本轮内存哈希
  仅用于读写期间漂移保护，不落工作树 manifest、不代替 v3 冻结。
- 共享影响：owner/取消同时影响 read、latest、download、start、cleanup 和 UI；
  帧写队列/ACK/计时与两个 MCU fake 相互依赖；HTTP 分类同时依赖 Dio、
  OtaHttpError、下载器与 service；Windows 能力读取位于发现、写入和通知的
  公共上游。现有 Flutter profile 覆盖产品/依赖/build.yml，测试属 Validation。
  不能凭一个文件哈希相同复用这些调用链的结论，也不临时改成逐文件 profile。
- docs/acceptance-contracts 未找到 P3-3 合同；实现和 runner 未提交，工作树
  门禁、审批冻结、NOT_RUN 矩阵前检均未满足。没有原始 EXECUTED PASS，
  不生成虚构 rerun-plan、不登记正式失败轮次。后续正式复验仍须由
  validate_bundle.py 比较冻结 tree、受审 profile、外部输入和判据/命令定义，
  按 required_commands 执行，不人工缩小或默认全跑。

#### 6.12.2 原 ID 逐项结论

P1 为功能/可执行性/证据可信度问题；P2 仍是合同或交互问题，不降为风格建议。
“回归”指整改引入的新矛盾；没有跨批字节锚点的补查只标前次遗漏或新观测。

| 原 ID | 合同依据 | 本批修改与依赖影响 | 本次证据及剩余项 | 结论 |
|---|---|---|---|---|
| RC3-01 / P1 | Spec :98-105 analyze/test；原编译准入 | nullable generation 调用链、连接事件 API、entered 局部变量、query 常量已调整；依赖 service/page/测试宿主。 | [service:352](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L352) 与 [1215](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1215) 类型已对应；[page:48](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L48)/116 使用 events.onConnectionStateChanged；[session test:632](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L632) 取局部 barrier；[query test:8](../../app/bluetooth_flutter_Trace/test/ota/share_links_latest_query_test.dart#L8) 改 final。原 const 插值/默认值/static helper 修复保留。不据此宣称整个测试集可编译。 | 原列四处源码已修；整体编译/运行证据不足，analyze/test NOT_RUN。 |
| RC3-02 / P1 | 执行合同 §7/§7.3 harness fail-closed；Spec 服务状态链测试 | 去掉全吞 zone、定量 pump、真实 start 和可取消 latest gate 保留；新通知替身及 SHA fake 改变原测试假设。 | [session test:97](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L97)/109 的默认 notifyLog 为 const []，却无条件 add；[154](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L154) 的忙锁提示即抛 UnsupportedError。这是通知替身整改回归；401 刷新例也会在通知处抛错，令 [346](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L346) 计数轮询等不到 2。另有丢 ACK 可续传成功却期望 TIMEOUT、慢写期望错误码不符、第一份 ACK barrier 被当作整块落盘等 oracle 矛盾，见 §6.12.3。 | 部分修复；仍不能把测试新增/静态写入当作可信自测。 |
| RC3-03 / P1 | binary §4.4/§4.5/§5；真实 MCU staging/session | 两个 fake 已加入 journal 前缀与按接收顺序累积的内容 SHA，ACTIVE 全丢 BEGIN ACK 注入已修；这些改进保留。 | [transport fake:1547](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1547) 及 [upgrade fake:780](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L780) 在写段前仍缺当前 4KB 窗口检查，真实 [staging:499](../../Libraries/OTA/ota_staging.c#L499) 会拒绝越窗。upgrade fake 还缺已 durable offset 幂等及新包清 journal 分支；[BEGIN:695](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L695) 不执行真实 MCU 的包头/版本检查，故 [恢复正例:405](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L405) 读到 vcode=20900 后再次装目标 20900 仍能“成功”，不能证明 MCU 恢复语义。此为共享 oracle 的前次遗漏/新用例暴露，不要求实现者迁就错误正例。 | 部分修复；内容 SHA 子项源码已修，不能声明“完整 MCU 真值已验证”。 |
| RC3-04 / P1 | Spec :78-79；CANCEL-RECOVERY；单一 owner | 入口取得 owner、body 前和部分 await 后检查代次、latest token 已加入；cleanup 也进入 owner。 | [cancel:888](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L888) 在 ABORT/下载清理之后才取 _ownerDone，取消本身未持有覆盖全流程的忙锁；旧 owner 在 [1021](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1021) 退出即可开放新入口。新操作可在该窗口进入，取消再等待新 owner 并删除其新包/覆盖其终态。绑定中取消的 [251](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L251) 只 return，迟到创建的 transport/订阅不释放；重启 probe 也不携带 generation，见 RC3-08。 | 部分修复；取消 owner 与发布/释放边界仍未闭合。 |
| RC3-05 / P1 | HTTP-RESUME :271；FLUTTER-TRANSPORT :1057；取消帧完整性 | 普通取消的帧级队列与 rename 前 token 检查已加入，UI 仅对完成包提供保留选择。 | [download:738](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L738) 的 _quietDelete 仍吞 delete 异常，_deletePartial/invalidatePartial 因而不能兑现“失败上报”；[434](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L434) 等 5s 超时后仍删，不证明 sink 已关闭。rename 的 await 之后 [399](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L399) 无取消复核，迟到完成文件不在 partial 扫描范围。帧写 [844](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L844) 的 Future.timeout 不取消底层 write，队列却可释放并发 ABORT；移动端 writer 的 discoverServices 后仍可能迟到执行 ch.write。所谓 MTU barrier/真实 cancelUpgrade 交错用例未找到：现 [transport test:761](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L761) 仍先等 transfer 退出再 ABORT，service fake 的单片大小是 247。 | 部分修复；正常帧串行已修，超时隔离、删除与 rename 原子性未修全。 |
| RC3-06 / P1 | binary §5.5/§5.6/§5.7；ACK 是唯一真相 | 跨窗增量限制、BEGIN 帧头/payload session 一致性、END durable/bitmap 检查已加。 | [transport:228](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L228) 只在发窗前取错误；窗内某 ACK 置 malformed/error 后，后续合法提交 ACK 可令 [258](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L258) 直接退出末块并进入 END，未再次消费已锁存错误，未知状态可被后来的进度掩盖。新增跨窗负例 [test:854](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L854) 实际注入 bitmap=1 而非报告称的 0；旧 bitmap 检查也会拒绝，不能独立证明新增跨度门禁有鉴别力。 | 部分修复；局部 ACK 校验已修，末块错误传播及负例仍缺。 |
| RC3-07 / P1 | BLE-TUNING/RETRY-POLICY 30s 无 durable 进展 | 逐分片重算 remaining、BEGIN ACK 等待封顶已落在 [transport:838](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L838)/632；原 72s 分片算例的直接漏洞已修。 | 不再沿用旧“每片固定 10s”的发现。新增 [慢写用例:991](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L991) 对 BEGIN 也延迟，111B BEGIN 已用理想 480ms，第一 DATA 分片只剩 20ms；当前 timeout 分支为 WRITE_TIMEOUT，不是断言的 NO_DURABLE_PROGRESS，且旧帧外 cap 也能拒绝该输入。物理迟到写未隔离见 RC3-05，跨受控 resume/真实发送截止未实测。 | 预算计算源码已修；相关隔离与可信运行证据不足，不能关闭整个原 ID。 |
| RC3-08 / P1 | DEVICE-DTO :118；BLE-LIFECYCLE；FLUTTER-TRANSPORT :1058 | pause gate、快速 ACTIVE 幂等 ACK 检查、probe timeout 已加入；生命周期仍由页面持有。 | [page:95](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L95) 先解除暂停再尝试重读，忙碌时 [service:229](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L229) 直接返回旧 DTO，所以恢复传输未重新发现/INFO。页面销毁后 observer 消失，service/channel 无真实连接代次订阅；显式断连也不使 DTO 立即失效。截止仍在 [disconnect:1074](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1074) 后创建，并非报告称的前移；probe [1090](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1090) timeout 只放弃等待，不取消 [1124](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1124) 的连接/绑定/GET_INFO，超时或取消后仍可处置全局 transport 和 phase。 | 部分修复；后台恢复、真实断连失效和迟到 probe 未闭合。 |
| RC3-09 / P1 | FFF0/FFF2/FFF1 精确发现与真实通知 | Properties 字段读取与真实 BleCharacteristic 发现链测试已补；与专用 writer/notify 共同核查。 | [bluetooth:1778](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1778)/2039 已对接实际字段，普通 win_ble 对象不再全回 null；[adapter test:269](../../app/bluetooth_flutter_Trace/test/ota/bluetooth_adapter_notify_test.dart#L269) 确实经过 Windows 发现、精确选择、写入/订阅。项目内归档 SHA 与 lockfile 相符。保留此前真实通知流、不去重子项；不把剩余无关 getField fallback 当作本路径仍坏的依据。 | 所列发现/通知源码已修；Windows 用例及真实 BLE 运行证据不足，NOT_RUN。 |
| RC3-10 / P1 | HTTP-ERROR/UNKNOWN-FIELDS；稳定终止闭锁 | latest 先分类、下载 badResponse 转领域错误、裸 4xx 闭锁已加入，旧 unknown-503 直接洗白路径已有修复。 | [service:510](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L510) 的 _needsFreshManifest 跨用户操作保留；二次 URL_EXPIRED 留 true 后，下次稳定终止错误 [579](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L579) return null，外层 [475](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L475) 仍能自动刷新，并在 [345](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L345) 清终止态。另 [1265](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1265) 仅凭码决定 retry，未约束 429/503 状态；下载已解析 INVALID_PARAMETER/UNKNOWN_DEVICE_MODEL 等已知非兼容码不满足 stableReject，仍开放旧清单重试。_tryHttpError 没传 x-request-id，下载终态也未填 requestId/兼容 required/actual 字段。此为残留及前次遗漏，新增下载器异常测试不等于 service 闭锁测试。 | 部分修复；终止态仍可被内部刷新绕过，诊断字段未贯通。 |
| RC3-11 / P2 | HTTP-RESUME/DOWNLOAD 强 ETag、digest、资源关闭 | 响应/sidecar 两侧排除内部引号、缺强 ETag 作废 partial、64KB 消费上限及 service receiveTimeout 已加入。 | [download:585](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L585)/606 的 break 仅取消 Dio 包装流。锁定 Dio 5.9.0 的 handleResponseStream :70 主动订阅 source，却未把 responseSink 的 onCancel/onPause 传回 source；原始流可继续读取。receive timer 只在数据到达时启动，响应头已到而第一块正文永不到时仍可挂起。新 [drain test:788](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L788) 假设取消包装流即停止 async* 源，未验证真实底层取消及首块停滞。依赖源码证据见 §6.12.3。 | 部分修复；ETag 子项源码已修，实际流释放/时间边界未闭合。 |
| RC3-12 / P2 | UI 用户意图/确定状态；Spec 同一 DTO 查询链 | cleanup owner、取消按钮 await 和终止态重读按钮真实存在；这些 UI 修复保留。 | [service:563](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L563)/831 仍可在文件清理前发布 cancelled，且取消全流程 owner 竞态见 RC3-04。更重要的是 [read:259](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L259) 替换身份并解锁时没有使旧 latest/asset/verified 失效；新身份可不经 latest 继续用旧包。新增 [恢复测试:413](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L413) 恰把这个路径当成功，fake 又省略真实 BEGIN 版本门禁，不能证明“有效查询链已重建”。此为范围内前次遗漏/新用例暴露，与 RC3-03/08 同根因归并。 | 部分修复；清包 UI 入口已修，恢复状态链和取消原子性未闭合。 |

#### 6.12.3 反例、纠正与证据边界

以下 JavaScript 只读算例与控制流推演不执行 Dart、Flutter 或 MCU，不记测试 PASS。

1. **测试不是产品合同。** 全丢 DATA ACK 用例先把 4096B 真正提交到 fake
   journal，重发耗尽后受控 ABORT 保留 journal，新 BEGIN 可回 durable=4096，
   直接 END 且内容 SHA 正确。因此 [test:326](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L326)
   的 TIMEOUT 不是该输入的必然结果，不能为迁就它禁掉合法续传。
   [upgrade test:282](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L282)
   等到的是第一份 ACK 挂起，不是第八段提交；取消可在后七段之前生效，
   [292](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L292)
   的 durable=1024 断言没有 barrier 保证。需要测试真实 owner 状态链，
   不能以多次 sleep 或 fixture 预填整块状态代替。
2. **负例鉴别力。** 慢写模型：BEGIN=111B、MTU-3=20、6片*80ms=480ms，
   500ms 预算剩 20ms，80ms 的首个 DATA 分片进入 WRITE_TIMEOUT。
   它既未构造原先“同一 DATA 帧各片未单独超时、累计超期”的反例，
   也不能支持 NO_DURABLE_PROGRESS 的固定断言。跨窗模型的实际输入为
   durable=8192、bitmap=1、total=8192；有效 mask=0，旧 bitmap 门禁也拒绝。
   应隔离被检门禁，不为当前测试数量或标题补记通过。
3. **末块 ACK 错误不能被冲淡。** 一块包、第一 DATA ACK 为 CRC 正确的未知
   status，随后正常 ACK 累积到 durable=4096：onAck 已锁存 malformed，
   但 for 循环不检查它，末块完成条件跳过下一次 takeError，仍可进入 END。
   只检查每个 ACK 字段而不检查结束边界，无法保证 fail closed。
4. **取消须绑定原 owner。** 合法调度为：取消进入并等待 ABORT/磁盘清理；
   旧 owner 退出开放入口；新下载/传输取得 owner；取消随后读取新 _ownerDone，
   等新操作结束，再删除新包并发布 cancelled。现有双 start 用例不覆盖
   这个“旧 owner 已退出、cancel 尚未结束”的窗口。probe timeout 同样不是
   取消底层 Future，迟到的 _bindTransport 仍能 dispose 新 owner 的 transport。
5. **HTTP 闭锁的跨调用反例。** 第一次用户下载遇 TOKEN_EXPIRED，刷新后
   又遇 TOKEN_EXPIRED，_needsFreshManifest 留 true；第二次用户下载遇
   HARDWARE_INCOMPATIBLE，stableReject 清资产并 return null，外层仍消费
   旧 true，再发 latest 并清 terminal，后续正常响应可继续下载。只测
   OtaDownloadException.httpStatus 不执行该 service 转换链，无法覆盖此缺口。
6. **Dio 原始依赖只读核对。** 本次从 pub.dev 读取 dio-5.9.0.tar.gz，
   仅在内存解压，SHA-256 为
   d90ee57923d1828ac14e492ca49440f65477f4bb1263575900be731a3dac66a9，
   与 pubspec.lock 一致。lib/src/dio_mixin.dart :558-575 在 stream 模式
   返回 handleResponseStream 包装后的 ResponseBody；该 handler :70-101
   无 source 取消转发，:46-80 的接收 timer 只在收到 data 后启动；
   io_adapter.dart :161-175 只给等响应头的 request.close 加 timeout。
   因此 64KB break 不证明底层断流，60s receiveTimeout 也不能证明首块正文
   停滞必然退出。测试应观测上游订阅取消/关闭和停止继续投递，而非仅即时计数。
7. **纠正交付描述，不倒逼错误实现。** latestGate 当前仍在 cancel 返回后
   complete，但 adapter [570](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L570)
   已用 Future.any 响应 cancelFuture，不能继续把原先的 gate 环当未修；
   当前先修通知 const 列表回归。_runExclusive 的 finally 实际按 identical
   释放，不是 §6.11 所述“仅代次未变才释放”，不要求据错误描述改它。
   END OK 的非零 bitmap 也不是正常 MCU 残留：真实
   [staging:455](../../Libraries/OTA/ota_staging.c#L455) 提交后 discard_ram_block，
   durable==total 时有效 bitmap 为 0；当前 endBitmapValid 的实现并未错误
   放宽，不应为了 fake 注释中的“非零合法”改变合同或产品校验。

#### 6.12.4 实际命令与未执行项

| 检查/命令 | 本次实际结果 |
|---|---|
| cmd.exe 下 git rev-parse --show-toplevel、git --no-optional-locks status --short、git log -8 --format=fuller、diff --stat/指定文件 diff | 活动根 D:/github/my/E-Track，HEAD 如上；无新实现提交，脏文件保留。status 仍提示既有 .manifest-test-mzl4deqo/、.pytest_cache/ 无访问权限，不宣称已审计这两个目录内容。 |
| type、rg、Node 只读文件/行号/哈希及函数调用链检查 | 完成上述集中静态复核；47 个保护输入在写前未漂移。JS 算例通过 functions.exec 仅在内存计算；不生成新 runner/manifest/产物。 |
| where flutter；where dart；dir /a app/bluetooth_flutter_Trace/.dart_tool | 各 exit 1：PATH 未找到 Flutter/Dart，项目无 .dart_tool；未安装 SDK，未执行本地构建。 |
| rg --files docs/acceptance-contracts -g *P3-3* | exit 1，无匹配版本化合同；未运行无正式输入的 validate_bundle.py。 |
| Node SHA-256 核对 .cache/win_ble-1.1.1/src.tar.gz，及归档对象 API 阅读 | SHA 为 2a867e13c4b355b101fc2c6e2ac85eeebf965db34eca46856f8b478e93b41e96，与锁文件一致；只读使用已有归档，不再下载/解包该目录。 |
| Node fetch + 内存 tar 解压读取锁定 Dio 5.9.0 | exit 0；SHA 与 lockfile 一致，决定性源码位置见 §6.12.3；无落盘网络下载。 |
| git --no-optional-locks diff --check | 写前 exit 2：既有看板 626 行 CR/行尾空白及页面/service 两条 LF->CRLF 提示。不清理历史内容，不当作本批产品缺陷。 |
| git --no-optional-locks diff --check -- .github/workflows/build.yml app/bluetooth_flutter_Trace | exit 0，仍有上述两条行尾提示；此检查只覆盖 tracked diff，不冒充 untracked 测试编译或整批测试通过。 |
| fsutil reparsepoint query 两份文档及完整父链；Node realpath/relative 边界检查 | 8 个唯一节点明确非 reparse point，实际路径均位于活动根内，写前预检通过。 |
| Flutter analyze/test；Actions APK/EXE；真实 HTTP/BLE/重连、toy/真包、安装与 J-Link | 全部 NOT_RUN。没有本批实现 SHA、对应 Actions run URL 或 APK/EXE 哈希，不拿 HEAD 治理提交/历史 run 背书。build.yml 的测试 step 无 continue-on-error；Analyze 仍有既有 continue-on-error，后续须核对实际 step outcome 与 SDK 版本，不能只看 job 绿色。 |
| 正式冻结/NOT_RUN 矩阵前检、正式观测、最终校验、rerun-plan | 全部 NOT_RUN；正式产品、硬件、部署观测消耗 0，无正式 PASS 可复用。 |

辅助读取失败如实保留：两次 sed 读取被 MSYS signal pipe 权限拒绝，改用
Node/type/rg；一次 rg 引号参数未被 cmd 按预期解析，随后纠正；curl 的
Schannel 凭据初始化失败。当前 Flutter stable 导出页读取只作辅助，后续导出
链读取超时，未作为编译/API结论或 SDK 身份证据；没有据此另报编译缺陷，
也未为失败读取落盘临时文件或放宽环境权限。

下一批应沿本表批量修复及补齐有鉴别力、能结束的自测，尤其是取消窗口、
真实 OtaService 闭锁/恢复、底层流取消与单点 ACK 错误传播。已修的编译、
Windows 能力、ETag、摘要和普通帧串行子项不每轮归零。待稳定批次经明确
授权提交实现与 runner、取得相关 Actions 自测结果，再审批冻结并执行 v3
准入；不以昂贵正式验收代替开发检查。当前不申请以提交/推送代替修复。

P3-3 卡面真机 toy/真包要求与实施 Spec :113 的 P3-5 归属差异仍须冻结前
明确裁定。本次不豁免、不迁移、不降低判据；commit/push/workflow dispatch、
部署、烧录、复位和其他真机操作均未获本轮授权，均未执行。

#### 6.12.5 本次写入审计

计划写入仅本 research（追加 §6.12）和 PLAN-OTA-EXEC.md（P3-3 动态状态、
追加本次集中复核记录及 §10 会话日志）。apply_patch 使用已预检的项目内
目标；所有命令显式指定活动根并使用 cmd.exe。保留既有研究历史、728 个
CRLF 对应行、实现认领、9 个遗留文件、三份本批辅助脚本和两份既有诊断。
回写后已核对：45 个非文档保护输入哈希未变；research 既有历史字节前缀完整，
看板精确只有一个动态状态替换、一个复核记录及一个日志追加，728 个原有
CRLF 对应行均保留。本次不修改产品/测试，不执行
历史脚本、PowerShell、包管理器、SDK 或硬件工具，不新建验收证据包。
本轮未选择任何项目外输出、缓存、日志、下载、移动或删除路径。

末尾链接校验发生一次本会话的写入预检遗漏：未整体引用的 Node 表达式含
比较运算符，被 cmd 当作重定向，误建
D:/github/my/E-Track/r.line}}))（0 字节）。发现后未继续使用该命令；先核对
规范化实际路径、零长度和完整父链无 reparse，再用 apply_patch 仅删除这个
本轮误建文件，并验证无残留。不涉及项目外写入或遗留文件清理。Node 子进程
调用 fsutil 未取得有效结果时未执行删除，改为直接 cmd/fsutil 完成预检。
后续含 shell 元字符的内联校验作为一个安全参数传入 Node，避免再由 cmd
解释源码运算符；此辅助校验事故不伪装成产品/测试失败或正式验收轮次。

### 6.13 RC3 第五批整改交付（P3-3-IMPL-20260907，2026-09-08）

交付者：Claude（实现会话）。整改对象为 §6.12.2 逐项结论中仍未闭合的测试
可信度、fake MCU 真值、取消交错、ACK 末块错误传播、慢写预算反例、身份恢复
闭锁、HTTP 闭锁与下载流清理缺口；§6.12.3 反例纠正按复核结论维持不改。
本批跨多个上下文窗口完成：lib 侧修复（ota_download/ota_service/
ota_ble_transport/ota_upgrade_page）先落盘，随后收尾测试侧并完成本节交付。
**Flutter analyze/test、Actions APK/EXE、真机全部 NOT_RUN**（本机无 Flutter
SDK，`where flutter` / `where dart` 均未找到；未获 commit/push 授权）。本文
「已修」仅指完成代码修改且静态落盘复核未再发现 §6.12.2 所列矛盾，不等于
运行验证通过。P3-3 卡保持「进行中」。

#### 6.13.1 本批修改文件（交付时逐项落盘复核）

- 实现（lib，均在既有 P3-3 改动文件内）：
  - `lib/ota/ota_download.dart`：RC3-11⑤ 首块停滞时间界 + 早退 drain 主动
    取消 token（4 处编辑覆盖 6 个 drain 调用点与 `_parseContentDigest`
    签名扩展）。
  - `lib/services/ota_service.dart`：RC3-04⑤ 取消绑定原 owner 快照
    （`ownerAtCancel = _ownerDone` 同步快照，不追等快照后新进入的 owner）、
    RC3-10⑤ 残留刷新标志稳定终止态守卫、RC3-08⑤/12⑤ 身份重验先于恢复
    放行与身份变更失效旧清单旧包。
  - `lib/ota/ota_ble_transport.dart`：RC3-06⑤ 块结束锁存错误消费
    （transfer 块尾 `takeError()` + `_classifyAckError` 同链处置）、
    RC3-05⑤ 迟到物理写隔离（帧取消后迟到的底层写经 2×writeTimeout settle
    隔离，不再污染写串行化链）。
  - `lib/pages/ota_upgrade_page.dart`：RC3-08⑤ 终态恢复入口
    （`_readDeviceInfo` 重新读取身份解锁终止态，入口按钮文案
    「重新读取身份解锁」）。
- 测试（test/ota）：
  - `ota_service_session_test.dart`：RC3-02⑤ notifyLog 默认改为可增长列表。
  - `ota_ble_transport_test.dart`：RC3-02⑤ 丢 ACK 期望修正、RC3-03⑤ fake
    4KB 窗口门禁/durable 幂等/新包清 journal、RC3-06⑤ bitmapOverride=0
    鉴别力与块尾锁存错误用例、RC3-07⑤ 慢写用例重写、RC3-05⑤ MTU=23 在途
    ABORT 用例。
  - `ota_service_upgrade_test.dart`：RC3-02⑤ 块提交 barrier、RC3-03⑤
    fakeInspectEtuHeader 门禁、RC3-08⑤/12⑤ 身份漂移作废旧包用例、
    RC3-10⑤ INVALID_PARAMETER 闭锁用例、RC3-05⑤ 小 MTU 分片在途取消用例。
  - `ota_download_test.dart`：RC3-11⑤ drain token 断言与首块停滞用例。

#### 6.13.2 逐项处置（对 §6.12.2）

| 项 | §6.12.2 批评要点 | 处置 |
|---|---|---|
| RC3-02⑤ | session test makeService 默认 `notifyLog = const []` 仍无条件 add；transport test:326 丢 ACK 可续传成功却期望 TIMEOUT；upgrade test:282/292 等的是第一份 ACK 挂起而非第八段提交（durable=1024 断言无 barrier） | session test 默认改为可增长 `<String>[]`；transport test 丢 ACK 场景改为期望续传成功（丢失窗口过后 ACK 恢复、durable 推进到位），NO_DURABLE_PROGRESS 用例改用 `respondDataAck=false`（真无 ACK）构造；upgrade test 取消前轮询等待 `stagedDurable >= 1024`（真实 journal 块提交 barrier）再取消，durable 断言不再依赖 ACK 到达时刻 |
| RC3-03⑤ | 两个 fake 写段前缺 4KB 窗口检查（真值 ota_staging.c:499-503）；upgrade fake 缺已 durable offset 幂等与新包清 journal；BEGIN:695 缺真实 MCU 包头/版本检查；test:854 注入 bitmap=1 无独立鉴别力 | `_McuSim` 写段前增越当前 4KB 窗段 ERR_OFFSET 门禁（含独立验证用例「fake 门禁：越当前 4KB 窗的段 → ERR_OFFSET」）+ 已 durable offset 幂等 + 不同 sha 新包 `_eraseStaged` 清 journal；`_UpgradeFakeBle` 增 `fakeInspectEtuHeader`（magic/header_len/CRC/flags/algorithm/key/hw_rev/layout/min_boot/target_vcode/full base 检查链，错误映射对齐真值 BEGIN 前置校验）；跨窗伪跳跃注入改 `bitmapOverride=0`（`_bitmapValid(0,·)` 恒真，唯一可拒谓词落到 durable 跨窗检查，负例有独立鉴别力） |
| RC3-04⑤ | 取消可能等待后来进入的新 owner 再删其包（service:888） | `cancelUpgrade` 发起处同步快照 `ownerAtCancel = _ownerDone`，只等待快照时已在途的 owner；快照后新进入的 owner 不被旧取消链删除其包。测试见 upgrade test owner 快照用例 |
| RC3-05⑤ | transport test:761 先等 transfer 退出再 ABORT（未测在途交错）；service fake 单片 247（撕裂永不发生） | transport test 增「MTU=23 下取消：在途 DATA 写完后 ABORT 从帧边界发出」用例（transfer 在途时 `abortBestEffort`，断言 ABORT 完整帧 + `pendingByteCount==0`）；service 侧 `_UpgradeFakeBle` 增 `otaMtu` 注入（语义对齐真值 `requestOtaMtu` 返回写净荷上限，注入 20 等价 ATT MTU 23）与 `writeChunkDelay` 慢速写，新增「小 MTU 分片在途取消」用例：两段 DATA 落地后 `cancelUpgrade`，断言 `abortCalls==1`（经 fake 跨 chunk 重组 + `decodeFrame` 同步字/长度/CRC16 校验，撕裂即失败）、`dataOffsets` 按 128 步长连续无撕裂、`endCalls==0` |
| RC3-06⑤ | 末块 ACK 错误可能被后续提交进度掩盖继续进 END（transport:258）；跨窗负例需 bitmap=0 | lib：transfer 块结束处锁存并消费错误（`takeError` → `_classifyAckError` → resume/terminal/抛出处置链），错误不再被块提交进度冲掉。测试：新增「块尾提交不得掩盖在途畸形 ACK」用例（伪跳跃 8192 注入 + 后续整块提交仍提交，期望 ACK_MALFORMED、`endCalls==0`）；跨窗负例注入改 bitmapOverride=0 |
| RC3-07⑤ | 慢写对 BEGIN 帧也延迟（111B 在 MTU=23 下 6 片×80ms=480ms，500ms 预算剩 20ms，首个 DATA 分片进 WRITE_TIMEOUT 而非断言的 NO_DURABLE_PROGRESS）；未构造「同一 DATA 帧各片未单独超时、累计超期」反例 | 慢写用例重写：写延迟仅作用于 DATA 帧分片（控制帧不受预算）；预算 520ms 并按片间边界检查与写完成间隔各留 40ms 计时余量；期望码修正为 WRITE_TIMEOUT（片级 cap 先于累计无进度检查触发，与协议语义一致）；截断证据断言完整 DATA 帧 0、`pendingByteCount==140`（7 片×20B 半帧滞留）——修复缺失时用例红 |
| RC3-08⑤/12⑤ | upgrade test:413 恰把「身份变化后沿用旧清单旧包」当成功 | lib：恢复链改为身份重验先于恢复放行（后台恢复不先放行传输）、重读身份返回新 DTO、身份变更即失效旧清单与旧包；page 终态恢复入口走 `_readDeviceInfo`。测试改写为「终止闭锁经重新读取身份解锁：身份漂移作废旧清单与包」：rev3→4 漂移后终止态解锁但旧包作废（`downloadedFirmwareFile isNull`、不触 BLE 重建、入口指引明确），原「沿用旧包」断言删除 |
| RC3-10⑤ | 残留刷新标志可绕过稳定终止态再次 latest/download（service:475） | lib：稳定终止态守卫拦截残留刷新标志，终止态不洗白；requestId 贯通、retry 状态约束收紧。测试：新增「下载 INVALID_PARAMETER 稳定闭锁」用例——三步状态机 adapter（401/TOKEN_EXPIRED → 400/INVALID_PARAMETER → 401 残留），断言终止态 code/requestId 贯通/phase failed/包清理；终止后第二轮 401 再置残留标志被守卫拦截（`_LatestOkAdapter.calls` 停在 2） |
| RC3-11⑤ | 64KB 后退出包装流不保证取消 Dio 底层响应；首块正文停滞仍可能挂起（download:585） | lib：主读循环对包装流套 `Stream.timeout(receiveIdleTimeout)` 首块停滞界（Dio 5.9.0 接收空闲计时器只在首个 data 事件后启动，响应头已到而正文永不到时裸 await for 无限挂起）；早退路径 `_drainBody` 增 `cancelToken` 参数并在达 64KB 界主动取消——补接线 6 个调用点：未请求 206、200 Content-Length 不符、`_parseContentDigest` 内 3 处 fail-closed drain（经新参数传入）及调用点传 token；续传头违规分支仅反复失败（即将 throw）路径取消 token（`restartUsed ? token : null`）——首次违规要走 continue 从零重下，取消同一 token 会让重试请求立即 CANCELLED、把协议违规误归因为用户取消，首次违规由有界 drain 限流量。测试：drain 用例传入自有 `CancelToken` 并断言 `token.isCancelled`（达界主动取消的直接观测，修复前仅 break、断言红）；新增「首块正文停滞」用例（`stallAfterChunks=1` 注入、receiveTimeout 压至 200ms、期望 TimeoutException、partial 已收 1024B 保留供续传、用例自身 10s 超时防挂起假绿） |

§6.12.3 反例纠正处置（均不改，维持复核结论）：

- latestGate：第四批已修，本批无动作。
- `_runExclusive` identical 释放：释放语义正确，不改。
- END OK 非零 bitmap 不是合法残留：不改冻结合同，不为 fake 注释改产品
  校验。fake 的 END 上报在 ACTIVE 会话下携带真实位图、teardown 后置 0，
  与真值语义一致；该反例不构成缺陷。

#### 6.13.3 实际执行与证据

| 检查 | 命令/方式 | 结果 |
|---|---|---|
| SDK 可用性 | `where flutter` / `where dart` | 均未找到——Flutter analyze/test NOT_RUN 的直接依据 |
| 产品改动范围 | `git status --short`（app 子目录） | tracked 修改仍为 P3-3 既有 5 文件（share_links/ota_upgrade_page/app_update_service/bluetooth_service/ota_service）叠加本批内容；`lib/ota/`、`test/` 为本卡新增未跟踪目录（提交前须逐路径显式 add，沿 P3-1 收口先例） |
| 第五批落盘复核 | grep + Read 逐项核对四个测试文件与三个 lib 文件的批评点锚点 | §6.13.2 表中全部处置在交付前逐项确认存在：session test L97-102 notifyLog、transport test 丢 ACK 期望与 fake 门禁用例、upgrade test barrier L362-366/门禁 L421-450/恢复链 L511-550/INVALID_PARAMETER L552+/小 MTU 用例、download test token 断言与停滞用例、lib owner 快照 L912、块尾锁存 L302-319、写串行化 L788-820、drain 接线 L332-372、page 恢复入口 L145-460 |
| 真机/Actions | 未执行 | 无 commit/push/dispatch/烧录授权，一律 NOT_RUN |

#### 6.13.4 未执行项与剩余风险

- Flutter analyze/test NOT_RUN：全部测试修改仅经静态写入与人工推理核对，
  不排除类型/语法层新矛盾；须在有 SDK 的环境（或 Actions）跑绿后才可视为
  验证通过。
- Actions APK/EXE 未触发：未获 commit/push 授权；本批不满足 app 子项目
  AGENTS.md 的 Actions 验证门，不得报告为「完成」。
- 真机/J-Link NOT_RUN；真机判据归属（P3-3 卡面 toy/真包真机判据与实施
  Spec P3-5 的归属差异）仍待冻结前裁定。
- 慢写用例（RC3-07⑤）依赖真实计时（`Future.delayed` 抖动），CI 慢 runner
  上存在理论偶发红面；已按片间检查与写完成间隔各留 40ms 双侧余量压缩。
- 小 MTU 交错用例（RC3-05⑤ service 级）依赖 30ms/片写延迟与 5ms 轮询的
  相对时序（单 DATA 帧写窗口 240ms ≫ 轮询粒度）；极端调度抖动下若取消
  恰落帧间缝隙，ABORT 先入写串行队列、下帧在 `_checkUsable()` 处 CANCELLED
  停写，断言仍成立（无撕裂），但段数下界用 `>= 2` 而非精确值以容纳该边界。
- `lib/ota/`、`test/` 未跟踪目录提交前的显式路径清单未生成（收口时由主
  会话处理）。

#### 6.13.5 写入审计

本批主动写入：上述 lib 4 文件、test 4 文件、research 本节追加、
PLAN-OTA-EXEC.md P3-3 卡回写（状态行更新字段 + 复核记录后追加交付记录 +
§10 日志一行）。全部位于活动项目根 D:\github\my\E-Track 内。未执行
commit/push/workflow dispatch/部署/烧录/设备复位；未创建冻结验收合同、
未填 PASS 矩阵。既有脏文件、遗留未跟踪文件、历史诊断与证据原样保留。

### 6.14 RC3 第五批整改独立集中复核（非正式轮次，2026-09-09）

审查者：Codex（非实现独立会话，2026-09-08 开始，跨日至 09-09）。
对象为 §6.13 新交付。依据是实施 Spec、冻结 XC/binary 条款及验收执行合同
§5、§6、§7.1、§7.3，前审意见不构成新合同。本次不修改产品代码或测试。

**结论：整改未闭合，P3-3 保持进行中；正式验收 NOT_RUN。**
下文“源码已修”仅覆盖明确列出的子项，不代表编译、Flutter test、Actions
或真机通过。旧问题继续使用 RC3-01 至 RC3-12，不因本批新增回归将已修子项归零。

#### 6.14.1 实际输入、共享依赖与准入

- HEAD 仍为 0ef3cc14f6fdbece4f15b45864b94cb1007af735，最新是治理提交，
  不是本批 OTA 实现提交。7 个 tracked 脏文件仍在，lib/ota、test 和本
  research 未跟踪。§6.13 与当前 owner 快照、块尾错误处理、独立 probe、
  严格删除、rename 后复核、流超时及测试新增分支，确认确有新整改输入。
- 本批申报修改 4 个 lib 和 4 个测试文件。集中核查这些文件，并沿其调用链
  核查 BluetoothService、codec/DTO/latest/query、widget/adapter 测试、
  workflow、锁文件及 MCU session/staging/header。累计范围仍是 10 个产品
  Dart 文件、10 个 OTA 测试文件与 build.yml；未扩到无关产品或历史验收。
- 没有第四批完整字节锚点或冻结 tree，不能重建精确跨批 diff，也不能仅据
  HEAD 或单文件哈希证明依赖“未变化”。git diff HEAD 是累计差异。当前
  52 个文件的内存哈希只用于本次读写漂移保护，写前全部一致；不落盘 manifest，
  不替代 v3 Git 对象冻结，不把实现方编辑次数当证据。
- 共享依赖影响：owner/取消覆盖 read/latest/download/start/cleanup/UI；
  分片队列、ACK 错误与预算共用 transport 和两个 MCU fake；恢复/probe
  共享真实 CCCD/通知通道，不因 Dart 对象分开而隔离；下载流依赖 Dio 5.9.0
  的包装/取消语义，HTTP 分类还经过 OtaHttpError 与 service/UI。Flutter
  profile 覆盖产品、锁文件及 build.yml，测试属于 Validation；正式失效
  粒度仍按已审批 profile，不临时改为逐文件白名单。
- 本机 PATH 无 Flutter/Dart，项目无 .dart_tool；未找到 P3-3 版本化验收
  合同。实现与 runner 未提交，受影响宿主自测无运行证据，审批冻结、执行
  worktree 门禁和 NOT_RUN 矩阵前检均未满足。没有原始 EXECUTED PASS，
  不创建虚构合同、矩阵或 rerun-plan，不登记正式失败轮次。后续正式复验
  必须由 validate_bundle.py 比较冻结 tree/profile、外部输入及判据/命令
  定义，按 required_commands 执行，计划不授予操作权限。

#### 6.14.2 原 ID 逐项结论

P1 为功能、编译或证据可信度问题，P2 为合同/交互问题；均非风格建议。
“整改回归”有本批新增分支和交付记录依据；其他补查注明新观测或前次遗漏。

| 原 ID | 合同依据 | 本批修改与依赖影响 | 本次证据 | 处置状态 |
|---|---|---|---|---|
| RC3-01 / P1 | Spec analyze/test/build；原编译准入 | 旧 nullable、事件 API、entered、query 常量修复保留；新增 header fake 与取消超时触及导入/作用域。 | [download:487](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L487) 使用 TimeoutException，文件未导入 dart:async，锁定 Dio 导出链也不导出该类型。[transport test:1635](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1635)/1643/1646/1647/1698 引用只在 main 内定义的 crc32Of、fakeDeviceHardwareRev/LayoutId/BootVersion/fakeCurrentVcode；[upgrade test:813](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L813) 同样越作用域调用 main 内 crc32Of。属于本批整改回归。 | 部分修复：历史已修保留，新增明确静态编译矛盾未修；未取得编译器输出。 |
| RC3-02 / P1 | 执行合同 §7/§7.3 harness fail-closed；Spec 真实服务状态链测试 | session 通知列表改可增长，upgrade 取消改等真实 durable；新用例消费真实 OtaService，但输入/oracle 仍须核对。 | [session:102](../../app/bluetooth_flutter_Trace/test/ota/ota_service_session_test.dart#L102) 与 [upgrade:362](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L362) 子项已修。丢 ACK [test:474](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L474) 仍要求第一次 TIMEOUT，与内部 ABORT+BEGIN 后直接 END 成功矛盾；[download test:836](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L836) 先发 1KB，却只捕获 TimeoutException；[upgrade test:599](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L599) 的第三份 401 实际被入口锁挡住而根本未消费。取消测试还延后安装 transfer 错误处理，见 §6.14.3。 | 部分修复：通知与 durable barrier 源码已修；旧 ACK oracle 未修，新超时 oracle/负例仍不足；test NOT_RUN。 |
| RC3-03 / P1 | binary §4.4/§4.5/§5；ota_sd_inspect_header 真值 | 两个 fake 补窗口、已提交段幂等、新包清 journal 和 BEGIN 头检查；内容 SHA/ACK 快照继续保留。 | [transport fake:1832](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1832)、[upgrade fake:1107](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L1107)/1120 窗口和 durable 子项成立。两个 inspect 只校验 full 分支，flags=patch 后未查 base_vcode/base_sha8/最小 payload；full 空 payload 错映射 ERR_BASE。对照 [MCU:316](../../Libraries/OTA/ota_sd.c#L316)/329。upgrade fake [1098](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L1098) 仍允许非尾短段，[1124](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L1124) 不比较重复段内容，与 [MCU:533](../../Libraries/OTA/ota_ble_session.c#L533)/585 不同。这些为共享模型补查，不要求真实 MCU 迁就 fake。 | 部分修复：窗口/journal/内容 SHA 子项源码已修；新增 header 模型不能编译且语义覆盖不完整，不能称完整 MCU 真值验证。 |
| RC3-04 / P1 | Spec 单一 owner；CANCEL-RECOVERY | 取消同步 ownerAtCancel；read 绑定取消后 dispose；与下载清理、发布和重连共用。 | [service:912](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L912) 只固定等待对象。[925](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L925) 在 ABORT await 后仍取当前 _asset/_download；[945](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L945)/967 仅检查当前 owner 是否空，无法识别已进入又结束的后来 owner，仍能删除其新包/覆盖结果。start 的 [749](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L749) 取消早退未像 read:252 那样释放迟到 bind。未找到交付表所称的 owner 快照竞态用例；现有双 start/cleanup 测试不是该窗口。 | 部分修复：快照与 read 清理已修；取消全流程资源归属和 start 绑定清理未闭合。 |
| RC3-05 / P1 | HTTP-RESUME :271；FLUTTER-TRANSPORT :1057；安全帧边界 | 加严格删除、rename 后取消复核、5s 超时不强删；加 2×writeTimeout settle 和小 MTU 取消用例。 | [download:128](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L128)/441/810 的局部修复保留。但 [cancel:482](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L482)/496 将“没有 inFlight”也当作未退出，跳过已有 partial 清理；正文取消仅经过 [400](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L400)/451 的 close/remove，无兜底删除。transport [873](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L873) 等待结束仍未废弃写通道，且超时留下半帧后会放行 ABORT。新慢写用例 [1227](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1227) 明确保留 140B 半帧，却没有接着验证 ABORT。 | 部分修复：正常帧串行、严格删除与 rename 检查已修；无在途清理为整改回归，超时帧/迟到写隔离未修全。 |
| RC3-06 / P1 | binary §5.5/§5.6/§5.7 ACK 权威及恢复 | 新块尾 takeError，跨窗注入 bitmap 改 0；共享恢复预算和错误锁存。 | [transport:307](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L307) 修住原末块错误直达 END。但 [228](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L228)/232 已处理的可恢复错误，到块尾再次处理；[takeError:1104](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L1104) 并不清锁存，导致同一错误扣两次 resumeLeft，retries=1 时一次可恢复错误即拒绝 ABORT+BEGIN（整改回归）。[注入:2037](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L2037) 的 bitmap=0 已修，但整个跨窗负例仍可能被后续 ACK 倒退门禁拒绝，不能称只有一个拒绝谓词。 | 部分修复：旧末块错误传播、bitmap 注入子项已修；重复处置回归未修，独立负例证据不足。 |
| RC3-07 / P1 | BLE-TUNING/RETRY-POLICY 30s 无 durable 进展 | 逐片 remaining/BEGIN 等待 cap 保留；慢写仅作用 DATA，期望改 WRITE_TIMEOUT，新增 settle 影响真实退出时限。 | [transport:856](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L856) 的逐片预算源码已修，新的 [test:1183](../../app/bluetooth_flutter_Trace/test/ota/ota_ble_transport_test.dart#L1183) 比旧 BEGIN 先耗尽预算的输入更有针对性；但 settle 可在预算耗尽后再等 20s 并让物理写落地，未证明中止/通道隔离。另 [BEGIN:204](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L204)/212 接受恢复时新 durable，却不重置无进展时钟，只有块循环 [297](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L297) reset；“刚获得恢复进展仍按旧截止超时”为跨 resume 前次遗漏。 | 部分修复：原逐片预算漏洞源码已修；跨 resume、物理写隔离与计时运行证据不足，不关闭原 ID。 |
| RC3-08 / P1 | DEVICE-DTO :118；BLE-LIFECYCLE；FLUTTER-TRANSPORT :1058 | 身份探测前移到 resume 之前，deadline 前移，probe 改局部 transport 并加 abandoned 检查。 | [service:1002](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1002) 仍用旧 transport，不重新发现；[1014](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1014) 吞身份读取错误后恢复发送，违背 fail-closed。lifecycle/连接 observer 仍只在 [page:83](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L83)/103；service 无真实连接代次失效。deadline 已在断开前，但 [1158](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1158) 的 disconnect 本身未封顶。abandoned 仅在整个 bind 后检查，迟到 [1268](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L1268)/1275 仍会订阅并于 finally 退订同一 CCCD，见 §6.14.3。 | 部分修复：顺序/deadline/局部 probe 子项已修；恢复失败放行、真实连接失效和迟到底层操作未闭合。 |
| RC3-09 / P1 | FFF0/FFF2/FFF1 精确发现、真实通知 | 本批未申报修改此处；沿恢复绑定的上游重核专用 writer/notify、Properties 字段及 Windows 测试接线。 | [Bluetooth:1778](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1778)/2039 仍直接读真实 Properties/uuid；[adapter test:269](../../app/bluetooth_flutter_Trace/test/ota/bluetooth_adapter_notify_test.dart#L269) 使用真实 win_ble 对象且由 Windows 分支执行，不拿无关 getField fallback 推翻已修结论。普通通知不再轮询/去重。共享 CCCD 迟到退订风险归 RC3-08，不重新编号。 | 所列发现/通知源码已修；Windows 测试及真实 BLE 证据不足，NOT_RUN。 |
| RC3-10 / P1 | HTTP-ERROR/UNKNOWN-FIELDS；稳定终止与诊断 | 增稳定终态刷新守卫、清刷新标志、记忆 channel、latest 重试约束状态、下载 requestId 头回填。 | [service:500](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L500)/635/1415 和 [download:714](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L714) 局部修复成立，不能继续报告原稳定终态必被刷新洗白。但 [service:624](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L624) 构造下载终态仍丢 minAppVersionCode/requiredValue/actualValue，兼容 UI 可显示 null；[605](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L605) 对下载的自动/稍后重试码仍未约束 HTTP 状态。新 INVALID_PARAMETER 用例证明分类/入口闭锁意图，未触发跨调用残留标志反例，详见 §6.14.3。 | 部分修复：刷新闭锁、channel、latest 重试与 requestId 子项源码已修；兼容诊断与下载分类残留，守卫运行证据不足。 |
| RC3-11 / P2 | HTTP-RESUME/DOWNLOAD 流关闭、时间边界 | 早退达 64KB 时取消 token，正文包装流加 timeout；修改覆盖多处 drain/错误体读。 | [download:332](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L332) 首次坏 206 仍不取消上游；新请求不会自动替代/终止旧响应。[655](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L655)/683 的 drain/错误体仍无首事件 timeout。正文 [393](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart#L393) 的新 timeout 只退出包装流，finally 未取消 token，首块永久不到时底层仍在。Dio 5.9.0 锁定源码已独立只读重核，见下文；[stall test:836](../../app/bluetooth_flutter_Trace/test/ota/ota_download_test.dart#L836) 并非零正文负例。 | 部分修复：ETag、达界取消和正文等待上限子项源码已修；首次坏 206、错误体时间界与真实上游关闭未闭合。 |
| RC3-12 / P2 | UI 确定状态；Spec 同一 DTO 查询链 | 成功重读且身份漂移时清旧资产；页面终态按钮确实走 _readDeviceInfo。 | [service:235](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L235)/276 只在 previousInfo 非空时失效旧包：若一次 read 失败已清 DTO、却保留旧资产，下次成功重读的 previousInfo 为 null，可给新身份保留旧 latest/file。这是新分支的范围内残留，不否认直接成功漂移已修。[取消 catch:590](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L590)/872 仍可早于清理发布 cancelled，最终发布的 owner 竞态见 RC3-04。现 [upgrade test:491](../../app/bluetooth_flutter_Trace/test/ota/ota_service_upgrade_test.dart#L491) 只断言 cancel 返回后，不证明期间无中间态。 | 部分修复：清包 owner/UI 入口与直接身份漂移源码已修；失败后重读和取消状态原子性未闭合。 |

#### 6.14.3 决定性反例、纠正与测试证据边界

以下均为当前源码控制流或只读 JS 算例，不是执行 Dart/Flutter/MCU，也不是
正式 PRODUCT_FAIL/HARNESS_FAIL。实际编译与运行必须在修复后取得真实输出。

1. **编译作用域需先闭合（RC3-01）。** 两个 crc32Of 分别声明于 transport
   test:29 与 upgrade test:98 的 main 局部作用域；使用它们的 fake 类均在
   main 结束之后。transport fake 使用的四个设备常量同样是 main 局部变量。
   imports、类继承和旧 packAck 顶层化都不会使这些局部变量跨作用域可见。
   download 新增 on TimeoutException 也不能依靠 Dio 内部 import 获得类型。
   这是静态可定位矛盾，不冒称已经得到 analyzer 报错。

2. **丢 ACK 用例仍违背输入（RC3-02）。** respondDataAck=false 只在
   _McuSim:2017 丢应答，不阻止前面的 DATA 真正提交。4096B 收满后，
   原传输两轮重发超限触发内部 ABORT；新 BEGIN 回 [4096,0]，SHA 用 journal
   全前缀重建，随后 END 合法成功。test:489 的 fail('应中止') 仍会被走到，
   增加第二次 transfer 成功断言没有修正第一次的错误要求。不得为了测试
   TIMEOUT 而破坏合法持久化恢复。NO_DURABLE_PROGRESS 的高 retries 输入
   与此不同，不能混作一条已修证据。

3. **新增测试仍需区分真正触发点（RC3-02/06/10/11）。** 下载停滞 fake
   在 yield 之后才检查 stallAfterChunks（test:976-982）；即使填 0 也会先发
   一块。当前值 1 已使 Dio source 回调先启动 200ms receive timer，包装流
   后到的 timeout 不是唯一或最先的超时来源；DioException.receiveTimeout
   不被 test:845 的 on TimeoutException 捕获。此输入不能证明“首个正文
   事件永不到”被新门禁处理，也没有观察上游取消完成。
   INVALID_PARAMETER 的 [401,400,401] 输入中，第二次 downloadFirmware
   在 service:474 已被 terminalLocked 拒绝，第三个 HTTP 响应根本没有消费。
   原残留路径需先让一次调用经历两次 URL_EXPIRED，再在下一次调用首个下载
   收到稳定拒绝；本批源码守卫已补，但当前用例没有对此提供鉴别力。
   跨窗注入 bitmap=0 的第一份 ACK 不再触发旧 bitmap 校验，这是已修；
   不过删去跨度校验后，发窗循环仍可能继续发送本块，后续合法 ACK 的
   durable=0 相对已采信的 8192 倒退，又在块尾被拒。整个用例的相同
   ACK_MALFORMED/endCalls=0 结果不等价于跨度门禁具有独立鉴别力。

4. **错误处理安装时机（RC3-02/04）。** transport test:917 的 transfer
   future 到 test:929 才被 try/await 接管，中间先 await abortBestEffort；
   cancel 会先使在途 ACK 等待失败。迟到安装 handler 不能保证没有未处理
   Future 错误。产品的 BEGIN/END/GET_INFO roundtrip 同样先注册 waiter，
   再 await 分片写，之后才 await waiter.future；在慢写期间 cancel/dispose
   调 completeError（transport:1176）可早于错误处理器安装。应在真实宿主
   验证这些时序且不全局吞错，不以最后捕获了同一异常说明此前无 uncaught。

5. **owner 快照不是取消事务（RC3-04/12）。** 合法调度：A 传输在等 ACK；
   cancel 使 A 退出，自己仍等慢 ABORT；A finally 开锁；B 下载进入并完成，
   发布新包及 ready；旧 ABORT 返回；cancel 读取 B 的 _asset/_download，
   等已完成的 ownerAtCancel，看到 _ownerDone==null 后删除 B 新包并发布
   cancelled。即使 B 尚未完成，cancel:925 也已经取了后来者的下载资源。
   “不再等待新 owner”只修了一步，不能据此声称不处置新 owner。

6. **超时后半帧仍可吞 ABORT（RC3-05/07）。** 本批慢写 fixture 明确在
   timeout/settle 后留下 140/142B DATA 帧；此时 ABORT 的 A5 5A 被当作旧
   DATA 的最后两个 CRC 字节。按当前 4096B fixture、session=1、seq=1
   的只读 CRC16 算例，旧 DATA 所需 CRC 为 0xD7B0，拼入值为 0x5AA5，
   CRC 不符，余下 8B ABORT 又没有同步字，不能组成完整 ABORT。完整帧队列
   不会自动修复上一帧的截断；2×writeTimeout settle 也没有取消底层 Future、
   阻止更晚落地或废弃后续写入口。不能把该等待解释为已证明物理隔离。
   同时，本批 cancel 的 settled 初值 false，在没有在途 future 时直接返回，
   因而已完成的网络失败所留下的 partial 也不再清理；正文取消路径并未在
   download finally 自行兑现注释中的删除承诺。

7. **块尾新增重复预算消费（RC3-06）。** takeError 是锁存读取而非消费。
   单个 ERR_SEQ 在循环头使 resumeLeft 从 1 到 0 并 break，块尾又读到同一
   错误，_classifyAckError(0) 抛 ACK_STATUS，连一次 ABORT+BEGIN 都没有。
   默认 5 次预算同样可被两次一组消耗。只读计数模型得到
   5 -> 4 -> 3 -> 2 -> 1 -> 0/拒绝，而不是五次独立恢复。须同时保护
   “末块不漏错”和“已处理错误不重复计次”，不撤掉正确的 fail-closed 门禁。

8. **Dart 对象局部化未隔离平台资源（RC3-08）。** probeAborted 只在
   _bindProbeTransport 返回后检查；若 MTU await 期间超时，随后仍会执行
   subscribe。旧 probe 的 finally dispose 会走 BluetoothService:1590
   的 setNotifyValue(false)，Windows 侧则是 :1566 的 unsubscribe；它们
   与新 owner 使用同一特征。没有全局 _transport 赋值不代表不会关闭新
   会话通知。断开 await 也仍可阻止 60s deadline 被检查。后台恢复的
   catch-all 后继续 resume 更是明确 fail-open，不以 MCU 重试兜底替代
   合同要求的重新发现/有效 INFO。

9. **身份失效要覆盖失败再成功（RC3-08/12）。** 先在 A 建清单/已验证包，
   read(B) 失败清空 DTO 但未清资产，再 read(B) 成功时 previousInfo=null，
   便绕过漂移清理；新 DTO、地址与旧资产能并存。直接 A->B 一次成功漂移
   的新用例有价值，但没有覆盖这个失败历史。

10. **Dio 原始依赖核对（RC3-11）。** 本次只读 fetch/内存解包
    dio-5.9.0.tar.gz，SHA-256 仍为
    d90ee57923d1828ac14e492ca49440f65477f4bb1263575900be731a3dac66a9，
    与 pubspec.lock:184 一致。实际归档路径为
    lib/src/response/response_stream_handler.dart：:70 主动订阅 source，
    :46-80 仅收到 data 后启动 receive timer，:94-100 的 CancelToken 才
    关闭原响应并取消 source；返回包装流没有 onCancel 转发。
    因此新增正文 Stream.timeout 解决本端等待，但不自动解决底层关闭；
    drain/readErrorBody 仍须覆盖首事件永不到。首次坏 206 不应直接取消
    将用于重试的同一 token，这个顾虑正确；然而以 null 跳过取消又声称
    “下一请求取代旧连接”不成立，须有请求级资源隔离/关闭证据。
    64KB 后 token.isCancelled 是动作观测，不等于上游取消已完成。

继续维持 §6.12.3 的纠正：latestGate 由 cancelFuture 打断，不能再称必然
死锁；_runExclusive 的 identical 释放合理；真实 staging 提交后清位图，
END OK bitmap=0。前者通知列表回归本批已修，后者虽有过时“非零合法”注释，
不要求为注释更改正确校验或冻结合同。MCU full 包 inspect 不校验 payload
内容 CRC，fixture 的该占位值本身也不作为本次否决理由。

#### 6.14.4 实际执行、未执行与下一步

| 检查/命令 | 本次结果 |
|---|---|
| cmd.exe：git rev-parse --show-toplevel、git log、git --no-optional-locks status --short --untracked-files=all、diff --stat/指定权威文件 diff | 活动根及 HEAD 如上；7 个 tracked 脏文件与未跟踪实现/测试保留；权威合同/profile 未见工作树修改。status 的 .manifest-test-mzl4deqo/、.pytest_cache/ 既有访问警告保留，不宣称检查过目录内容。 |
| type、rg、Node 只读文件/行号/哈希、调用链与 import/作用域核查 | 完成表中集中静态检查，52 个保护输入写前未漂移；未跑历史临时脚本或自建测试 runner。 |
| where flutter；where dart；项目 .dart_tool 检查 | PATH 均未找到，项目 .dart_tool 不存在；未安装 SDK、未执行本地构建/打包。 |
| rg --files docs/acceptance-contracts -g *P3-3* | 无匹配版本化合同；不运行缺正式输入的 validate_bundle.py，不制造前检失败轮次。 |
| Node fetch、SHA-256、内存 tar 解包锁定 Dio；JS 只读 CRC/预算模型 | 依赖哈希与 lock 一致；0xD7B0 与 0x5AA5 反例、双扣预算控制流见 §6.14.3。只读模型不记 Dart 或 MCU PASS；网络内容未落盘。 |
| git --no-optional-locks diff --check | 写前 exit 2，仅既有看板 L626 行尾空白；另有 page/service 两条 LF->CRLF 提示。不修改历史证据行；该检查不覆盖 untracked 文件的编译。 |
| fsutil reparsepoint query 两份文档及完整父链；Node realpath/relative | 8 个唯一节点均明确不是 reparse point，文档实际路径在活动根内；已完成写前边界预检。 |
| Flutter analyze/test；Actions APK/EXE | NOT_RUN。本批无实现提交 SHA、对应 run URL、APK/EXE job 结论或产物哈希，不能以治理 HEAD 或历史 run 背书。Windows 发现链由 windows-2022 执行；Analyze 既有 continue-on-error 仍要求核对实际 step outcome，不能只看 job 绿色。 |
| 真实 HTTP/BLE/重连、toy/真包、安装、J-Link；正式合同冻结/矩阵前检/产品观测/最终校验/rerun-plan | 全部 NOT_RUN。正式产品、硬件、部署观测消耗 0；未获 commit/push/dispatch/部署/烧录/设备复位授权，均未执行。 |

辅助读取瑕疵：一次 Node 引号形式只输出了表达式，改为实际文件读取；
一次 Dio 归档成员路径遗漏 response/ 导致读取失败，按实际路径重读成功；
一次只读哈希预检超过 cmd 命令长度，改为仅传路径、在 Node 内计算并回传比对。
均未把失败输出当证据通过，未生成文件、未调用 PowerShell、无待清理产物。

下一批由实现者沿原 ID 同批修复与自测，优先消除编译/测试 oracle 回归，再
核查 owner、超时物理写、底层流和恢复查询链，不要求逐点重新开审或提前跑真机。
待稳定批次经用户明确授权提交实现与 runner、取得受影响宿主测试和对应
Actions 结果，再由非实现会话审批冻结、执行 worktree/NOT_RUN 矩阵前检。
不得用正式高成本验收代替开发自测，也不以缺 SDK 为源码缺陷关闭依据。

P3-3 卡面真机 toy/真包要求与实施 Spec 的 P3-5 归属差异仍待冻结前裁定；
本次不自行豁免、迁移或降低任何判据。没有新整改/输入变化时，不对本批相同
输入再开一轮集中复核。

#### 6.14.5 写入审计

本次主动写入仅本 research（追加 §6.14）和 PLAN-OTA-EXEC.md（P3-3 更新
说明、本次集中复核记录、§10 日志）。写前规范化目标并检查完整父链，无
reparse point；使用 apply_patch 定点改文档，所有命令显式以活动根为工作
目录并用 cmd.exe。看板既有 728 个 CRLF 对应行、research 历史 LF 前缀、
实现认领、9 个遗留文件、第四批 3 份及第五批 2 份脚本、两份既有诊断均保留。

收尾核对保护输入、历史前缀、看板精确修改范围及行尾；如补做行尾恢复，仅
作格式还原，不改变历史文本。未执行任何历史脚本、包管理器、SDK、硬件
工具或 PowerShell；未选择项目外输出、缓存、日志、下载、移动或删除路径。
本节及看板记录是非正式静态复核记录，不是新冻结证据包。

实际收尾：看板仅一个状态说明替换、一个复核记录及一个日志追加；在内存中
逆转这三处后，原始字节 SHA-256 恢复为
e368b9c4c91d674c5595c1b7f546258a3cf4b694ea5a0b8639d298bcfbb2af22，
728 个 CRLF 对应行完整，无须行尾格式恢复。research 的原 110379 个 UTF-16
字符前缀按 UTF-8 重算 SHA-256 为
e166af7dcced3a1e30a9a6ecf873f5aa082ee71ff3e30d21db93b6b3735004b1，
与追加前一致；49 个本节文件/行号链接存在且未越出文件范围。

证据限制：52 个保护输入在首次文档回写前已逐项比对无漂移；随后用户发送
“继续”后工具内存存储不可再读，未保留完整哈希输出，故收尾不宣称重新完成
50 个非文档输入的逐文件哈希比对。产品/测试未被本次写入工具选作目标，
不据此虚构跨批次不变或运行 PASS。收尾一次 Node 内联语法/引用错误未完成
读取，改用安全编码单参数后取得上述真实核对结果；没有重定向或文件生成。
