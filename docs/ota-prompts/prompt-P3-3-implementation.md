# P3-3 Flutter 传输与升级 UI 实施 Spec

task_id: P3-3

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-3` 行。本文件不得另行维护该状态。APK 构建继续使用 GitHub Actions，禁止以本地 APK 构建替代验收。

验收归属按 2026-09-10 用户授权裁定 `OTA-DEC-013`：本卡完成前必须取得 APK 实际安装及 toy/真包实机证据。开发自测与本卡正式验收分开，不将这些完成门槛推迟到 P3-5。

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
- model、摘要、BLE 调参、App 兼容、HTTP 恢复和 token v2 的用户裁定已传播到并冻结在共享合同；实现依赖满足后，才能形成正式端到端行为。

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
- Actions：analyze/test/build APK，并满足 app 子项目要求的 APK/EXE 构建门；受验 APK 的实际安装由本卡独立验收验证，不能只检查 APK 文件或签名。

## 完成判据

- `startOtaUpgrade()` 对 fake transport 和真机路径均不再固定失败。
- toy 包和正式包都能按合同完成下载、传输、重连和 GET_INFO 复核。
- UI 显示真实设备/版本、下载进度和 durable 进度，不出现硬编码值。
- 所有错误/取消可恢复到确定状态，不留并发 subscription、临时文件或活动 session。
- GitHub Actions 产出通过测试的 APK，app 子项目要求的 APK/EXE 构建门满足，且下节三类实机证据齐全；缺少任一 required 证据不得宣布本卡完成。

## 验收归属与实机证据

本节落实 `OTA-DEC-013` 的方案 A，是 P3-3 的最小实机门禁，不代替 P3-5 的真实后端集成与十次断连续传。以下是证据类别，不是预先创建的正式合同或 PASS 矩阵。

| 证据项 | 完成时点 | 最低成功观察 |
|---|---|---|
| APK 实际安装 | P3-3 完成前 | 在实际 Android 手机上安装并启动本卡冻结的 Actions 验收 APK，记录包名、版本、设备/系统、安装结果及 APK SHA-256；参与传输的必须是同一受验 APK。 |
| toy 包实机闭环 | P3-3 完成前 | 用可启动的受控测试 OTA 包，实际经过手机 App、BLE 和 MCU，达到下述共同成功终点；保留该包独立的身份和原始轨迹。 |
| 真包实机闭环 | P3-3 完成前 | 用面向实际设备的真实固件 OTA 包，实际经过手机 App、BLE 和 MCU，达到下述共同成功终点；不得由 toy 成功代替。 |

toy 与真包各至少一轮成功。共同成功终点为：真实 `OtaService` 完成设备 INFO、latest/下载、长度和整包 SHA 校验、BEGIN/DATA/END；MCU 确认 `durable_off == total_len` 且 `ACK_END` 成功；随后真实升级、重启、新连接 `GET_INFO` 的目标 versionCode 和完整 raw SHA-256 与冻结的目标镜像一致。只看到 GATT 写成功、UI 100%、END ACK 或仍运行旧固件均不足以完成该判据。不得用 PC sender、fake transport 或 fake MCU 替代手机主路径。

资产必须在正式合同中分别绑定路径/来源、size、package SHA-256、目标版本和目标 app.bin 的 raw SHA-256、硬件/布局/Boot 兼容字段、full/patch 类型及基版条件。toy/真包是用途分类，full/patch 是包类型分类；本节不把两者混同，也不额外要求两类资产各跑全套 full/patch 矩阵。同一资产不得重复命名后同时充当两类成功证据。

用于上述成功判据的 toy 必须是经审定、保留真实 Boot/BCB/OTA 路径且具有合法 fw_header/向量的可启动受控固件包，不要求固定为 4KB。`tests/ota-vectors/` 的 toy-old/new.bin 和 toy full/patch golden vectors 仅凭名称或解析通过不能证明可启动；不满足条件的向量只用于对应解析/拒绝测试，不得直接刷入并要求启动，不得旁路完整性、防错板或防降级检查来制造成功。

本卡真机验收不依赖 P3-5 的启动或完成，P3-5 也不承担为本卡补齐完成证据的职责。P3-1/P3-2 实施前置不变。P4-2 未就绪时，本卡可在验收合同审批后，以版本化、符合冻结共享合同的受控 HTTP 测试服务作为显式外部输入；APK 经受控配置使用真实 HTTP 请求与下载，不旁路 latest、兼容、token 或摘要检查，不把包直接注入 service 状态。必须绑定测试服务/fixture 身份并标注不宣称真实 P4-2 register/R2/D1 链已通过。服务部署或远端写入仍需其自身授权。

实机执行须冻结实际 baud/timeout/retry、设备/固件/Boot 身份、包的安全准入和操作范围；不得以本卡功能成功替代 P3-4 生产参数/性能验收。所需外部输入尚未具备时保留相应缺口，不因本次归属裁定记 PASS。最低成功数量不是执行或重试授权，具体命令、超时、配额、恢复方式和操作授权按执行合同审批；复验和证据复用仍按 v3 机制。

## 停止条件

- 任一受影响共享条款发生未重新冻结的变更，或实现依赖尚未完成且必须选择跨系统行为时，停止对应部分。
- Worker 实际 JSON 与共享合同不一致时记录实现缺口，不在 Flutter 建第二套兼容 schema 掩盖。
- 平台 BLE 库不能提供可靠通知/MTU/重连语义时先建立最小可复现证据，不无界换库。
- 需要修改冻结 binary contract 才能继续时停止。

## 后续证据

保存 Actions run/commit/APK hash、Flutter test 明细、fake transport traces、HTTP response fixture hash、下载文件 hash、真机每次 durable_off/bitmap、重连次数和最终 GET_INFO 对比。

## Luna 可自行决定

状态管理内部拆分、typed DTO/Result 类、stream/queue 实现、widget 布局细节、fake 接口和本地文件目录结构，只要不改变合同和现有项目视觉语言。

## 2026-09-12 批次：验收准入整改与任务级授权

本批由 Codex 非实现会话派发，授权记录为 `P3-3-IMPL-AUTH-20260912`。
用户本轮原文：“请给出给实现agent的提示词，若实现过程中需要什么授权权限，也请一并给实现agent”。
以下为依据该委托明确授予的本批权限，不是对所有操作的笼统授权，也不追认历史越权。
本节细化原 Spec，并仅在列明位置扩展修改/开发验证范围；冻结协议、产品门槛和独立验收
责任不变。旧模板中一概禁止实现者提交的表述，不覆盖本节及执行合同 §7.3.2 的明确授权。

### 本批目标与依据

你是 P3-3 的实现 agent，不是本卡独立验收人。完成一批可执行验证的集中整改，并交付
正式验收准备材料；不要自验收置完成，也不要为了凑齐证据重新跑整套历史固件/硬件战役。

先读 `PLAN-OTA-EXEC.md` 的 P3-3 卡、根/app AGENTS、
`docs/acceptance-execution-contract.md` §5/§6/§7.3、
`docs/flutter-development-validation.md`，以及
`docs/ota-exec-notes/P3-3-research-flutter-ota.md` §6.18。
缺陷依据和未覆盖项以 §6.18 的集中清单为准，原 RC3 已修子项不归零。
OBS/OPS 涉及的操作单和原始证据按该节链接读取，不执行历史采集脚本来“看结果”。

复核基线是 `c89c58f44dec1745980f0f2a54e612af48f6d32c`，不是已审批的正式 freeze_commit。
开工重读实际 HEAD、diff 与文件；如有后续改动，核对差异，不以旧行号机械覆盖。
任务状态只从看板读取，保留原实现认领，新增批次执行记录即可。

### 已授予的实施权限

1. **本地写入与独占工作树**：可在 `D:\github\my\E-Track` 内修改本批范围文件，
   在 `.cache/worktrees/p3-3-<id>/` 创建专用 worktree，并为其写入本仓库内必要的 Git
   worktree 元数据。所有命令显式设置 cwd；写入前检查实际路径与完整父链。
   日志、依赖缓存、下载、测试临时产物留在项目内。未经路径级另批，不写本机用户目录、
   `%TEMP%`、盘符根、兄弟仓库，不启动未容纳的本机 PowerShell。
2. **暂存、提交、推送**：可在独占的 `dev/flutter/p3-3-*` 或
   `dev/flutter/apk/p3-3-*` 分支显式暂存/提交本批源码、测试、必要文档，以既有
   `Eitan-S-23` 凭据推送同名分支。开发 WIP 提交不要求测试先绿或合同先冻结。
   不并发操作共享 index；不能独占时由主会话串行执行同一授权动作。
   禁止 `git add .`、夹带缓存/无关脏文件、强推、推 main/master/tag、合并或改变远端/凭据。
3. **必要治理稿整合**：允许将已审查且与 P3-3/OTA-DEC-013 直接相关的既有未提交稿
   移植到上述独占分支并提交，包括本 Spec、P3-5 Spec 的归属裁定、
   `docs/ota-spec-decisions.md` 的 OTA-DEC-013、`docs/flutter-development-validation.md`、
   `tests/ota/test_acceptance_bundle.py` 的对应政策回归，以及 P3-3 看板/研究记录。
   先逐 hunk 确认来源和关联，保留共享工作树原件，不擅改已批准语义。
   这不是整仓脏文件提交授权；发现不能明确归属的改动，排除并交主会话协调。
4. **开发自测**：可推送/dispatch `flutter-dev-checks.yml`，运行双宿主 analyze/test
   和 debug APK 模式，读取日志并下载产物到已预检的项目内路径，无需逐批重复请示。
   APK 请求使用 `all`；失败必须定位，有实际修复/输入变化或已证实环境恢复才复跑。
   不降低断言、吞分析错误或用 targeted 绿替代整批应有的 all 检查。
5. **新增 build-only 授权**：本批允许在上述专用分支手动 dispatch
   `.github/workflows/build.yml`，参数必须为 `publish_release=false`、
   `replace_existing_release=false`，不传 release_tag，不使用 tag ref。
   仅用于取得 release-mode APK 与 Flutter Windows EXE/完整运行包，不是发布。
   执行前检查待运行 ref 的实际 workflow：manual 路径的 docs_changed 必须为 false，
   Pages 和 Create GitHub Release/Cloudflare 整条链必须不可进入；不得修改这些保护条件。
   结束后核对 Android/Windows job 成功、Pages/release job skipped。
   该授权最多 3 个实际运行，含首跑与有修复依据的重跑；同输入盲重试不在授权内。
6. **新增治理 CI 授权**：可对同一专用分支 dispatch
   `.github/workflows/acceptance-governance.yml` 并读取日志；最多 3 个实际运行，
   后续运行同样须有修复/输入变化或已定位的环境恢复。允许取消本次自行启动且已确认
   不应继续的 CI run，不得取消他人的运行。配额耗尽后集中报告，不换分支名重置。
7. **CI 运行环境与签名边界**：第 5/6 项仅限 GitHub 本次临时托管 runner，不得改成
   本机或自托管 runner。允许既有工作流在该 job 解析出的 GITHUB_WORKSPACE、RUNNER_TEMP、
   RUNNER_TOOL_CACHE 与该临时 runner 的 HOME/用户配置缓存目录内生成、使用、清理构建
   临时产物；记录实际落点，此例外不适用于开发机相同名称目录。仅允许第 5 项按既有
   Android 签名步骤使用仓库已配置的凭据，不新增/修改/导出凭据，不上传私钥或 keystore。
   未配置固定签名时如实记录实际签名类型，不能把 release 模式说成固定生产签名；
   开发自测工作流仍不得获得生产签名/发布密钥。

上述授权从本批生效，不必再问“能否提交验证分支/跑指定 CI”。它不提供不存在的 token、
SDK、workflow scope 或沙箱写权限；真实能力不足时报告具体条件，不绕过系统限制。

### 本批允许修改的补充范围

除原 Spec 的 Flutter OTA/蓝牙/UI 及测试范围外，允许修改 `Tools/flutter/dev_apk.py`、
确有共享影响的 `Tools/flutter/dev_checks.py` 与对应 `tests/ota/test_flutter_dev_*.py`。
允许同步 `flutter-dev-checks.yml` 的必要验证接线，以及 `build.yml` 的构建准备、测试、
输入绑定和产物取证步骤；应核对其 Gradle/SDK 准备是否与实际 app 构建输入一致。
不能修改发布/部署逻辑、权限和触发保护来绕过本节第 5 项。

允许修正本批操作单、开发指南中与实际验证行为冲突的说明，追加 P3-3 执行/审计记录。
不修改 MCU、Boot、固件发布、冻结二进制/跨系统合同、profile 定义或历史冻结验收包。
如需要新规则或这些范围的改变，交非实现会话裁定，不能自行弱化门槛。

### 必须一次交付的整改

1. **OBS-SEC-01**：校验规范化后的 query 参数及明确的公开端点允许范围，阻止编码、
   大小写、重复参数和 token 别名绕过。把 `%74oken`、`sign%61ture`、`access_token`
   等反例变成真实 runner 回归；正常无凭据端点仍可用。不得将不可信 URL 先写日志/产物
   再拒绝，不使用真实秘密作测试值。
2. **OBS-01**：修复 observer 与真实扫描适配层之间的成功/错误语义。平台拒绝启动、
   运行中扫描流错误、正常完成但未见目标必须可区分；不得无条件返回 true。
   测试须覆盖 BluetoothService/adapter 接线，不只测试手工注入 false 的 observer。
3. **OBS-02**：为启动、停扫、连接、身份读取及清理建立有界异常/超时结局。
   每次操作只有一个终止结果，迟到回调不能再发起连接/GET_INFO 或覆盖已终止状态。
   分别注入抛错、永不完成和迟到完成；处理未被物理取消的在途动作，不能将
   Future.timeout 等同于 native 操作已取消，也不能以无界 await 收尾掩盖问题。
4. **RC3-07/02 插桩增量**：区分中止决定、停止业务写、ABORT 收尾与真正的终态发布。
   单调时钟事件放在实际边界；延迟 ABORT 的测试必须能识别旧打点提前宣告终止。
   修正操作单中无来源的严格 `<30s` 表述，保持冻结合同“30 秒无 durable 进展必须中止”
   与 `maxRetries=5` 不变；不擅加容差、不延长预算、不回改历史结果。
   新硬件测量门禁及含糊的中止边界由非实现会话审查后再用于观测。
5. **OBS-03**：修正 target 日志的地址插值，断言完整 target 行及其与 connect/identity
   的地址关联，不只断言 matched_by。
6. **OPS-01**：把 B1-M 三次已执行写如实记为已用 3、剩余 0；保留所有失败和零写尝试，
   补齐整段时间、清日志、设备文件覆盖及授权来源审计。没有原授权原文/锚点则标明缺失，
   不编造批准，不把本次授权用于追认旧动作。原始日志不可重写；影响裁定留给非实现会话。
7. **ADMIT-01/02/03**：交付稳定提交和真实构建结果，整理正式验收的合同/NOT_RUN 矩阵
   草案、runner 依赖、设备/Boot 身份、安全资产及 HTTP 服务输入。缺值明确留缺口。
   不擅自把合同标为已审批冻结或声称用户已批准，不把开发日志填成独立 EXECUTED PASS 或 REUSED。
   每份 toy/真包应有独立来源、包 SHA/size、目标版本和 raw SHA、可启动及兼容性依据；
   golden vectors 不因能解析就获得上板资格。

### 验证与交付

按影响范围先跑针对性负例，再跑完整回归。以下宿主入口只运行测试，不做本地 Flutter
构建；调用前仍须容纳其临时目录、缓存与子进程写入：

    python -X utf8 -B tests/ota/test_flutter_dev_apk.py -v
    python -X utf8 -B tests/ota/test_flutter_dev_checks.py -v
    python -X utf8 -B tests/ota/test_acceptance_bundle.py AcceptanceExecutionPolicyTests PostP26SpecGovernanceTests -v

Flutter 编译/打包全部走 Actions；Linux 的 Windows 专属 skip 不能替代 Windows 实跑。
稳定批次取得双宿主 all 检查、必要治理 CI 与第 5 项 build-only 结果。release APK/EXE
与 debug APK 分开记录，Windows 交完整运行包而非只有裸 exe；不使用 LVGL Simulator 替代。
这不是对外发版请求，不创建/覆盖 release/tag/candidate；将来发版仍须原版本规则与单独授权。

交付 `docs/ota-exec-notes/P3-3-admission-remediation-2026-09-12.md`：
每项列“ID / 真实改动 / 负例鉴别力 / 自测证据 / 未覆盖项”；同时给出提交链、workflow
run URL、真实输入/SDK/依赖身份、命令退出码、原始失败及修复、APK/EXE size 与 SHA-256、
warning/error 数和剩余授权配额。不要只凭 HEAD 相同忽略运行期工具链改写或产物漂移。
将“源码整改、开发自测、构建验证、独立验收”四种结果分开，回写看板与会话日志。

### 未授予的操作与停止边界

本批**没有新增真机额度**。APK 安装/覆盖、停止既有应用、卸载/清数据、广播/连接/注错、
J-Link halt/reset/烧录、SD/BCB 写入、断电、RTT 下行、logcat 清空、设备文件覆盖，
均不能从上述 CI/代码授权推导。旧操作单尚未对清账目，不得据旧“剩余 3”继续 B1-M。
安装及 toy/真包闭环仍是本卡完成门槛，但由非实现验收会话在确切设备、APK/固件包、
输出路径、签名冲突处理、超时、恢复方式与配额审批后执行，不要求实现者提前自验收。

如确需额外动作，一次列出准确路径/设备、操作、资产 SHA、副作用、预算与收尾方案，
再申请针对性授权；不能先试、事后搬文件或追认。普通范围内缺陷批量修复并自测，
不每修一点重开验收。授权/安全冲突、凭据不足、配额耗尽、同因连续失败且无实际修复，
只暂停受影响动作并报告，其他独立安全工作继续。禁止合并、发布、部署、自验收置完成。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
