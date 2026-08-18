# P2-6 后 OTA 跨系统合同

本文是 MCU、Flutter、HTTP、D1、GitHub Actions、R2 和 admin 之间的冻结共享规范。本文不覆盖 `docs/ota-binary-contracts.md` 的 BLE/.etu 字节定义，也不改变 `PLAN-OTA.md` 或 `PLAN-OTA-EXEC.md` 的任务范围。

- 规范层级：用户批准的冻结规范；冻结授权记录在 `docs/ota-spec-decisions.md` 记录 9。
- 本轮新增条款成熟度：`FROZEN`。
- 二进制协议唯一来源：`docs/ota-binary-contracts.md`，本文只引用其章节和语义，不复制字节偏移表。
- 任务状态唯一来源：`PLAN-OTA-EXEC.md` 的 P2-6 后 readiness 矩阵；本文不保存任务级 readiness 或派单资格。
- 决策过程索引：`docs/ota-spec-decisions.md`。`OTA-DEC-001` 至 `OTA-DEC-012` 均为 `DECIDED`，对应裁定已传播到本文。本文冻结只授权符合 readiness 与依赖条件的任务派单，不授权生产部署；生产部署仍须等待 P5 验收。

文中“必须”“不得”“仅”表示冻结规范性条款；“例如”“建议实现”“当前入口”属于非规范性说明。各条款的“裁定依据”只保留决定来源和审计链，不再构成决定阻断；实现和派单资格仍以 `PLAN-OTA-EXEC.md` readiness 矩阵为唯一来源。

## 1. 范围与非目标

### OTA-XC-SCOPE

本文规范以下跨系统边界：

1. MCU `INFO` 身份数据到 Flutter DTO，再到 firmware latest 查询的字段映射。
2. firmware latest、下载、CI 注册和 admin 操作的 HTTP 语义。
3. D1 release/asset/channel 数据模型、状态迁移、幂等和回填要求。
4. 正式发布链的输入、输出、资产角色、摘要和退出码。
5. BLE transport 的生命周期所有者，以及 Flutter/MCU 各自的恢复责任。
6. App 兼容、未知字段、错误封装、鉴权、摘要、取消和重试边界。

非目标：

- 不重新声明 `docs/ota-binary-contracts.md` 的帧、payload、状态码数值、`.etu` 或 recovery 字节布局。
- 不修改 v1 威胁模型；固件内容在 v1 仍不具备抗主动伪造签名保证。
- 不定义 v2 灰度、Ed25519、BLE 直刷内部 Flash 或 Boot A/B。
- 不创建任何版本化 acceptance contract；本文冻结不等于完成 P5 验收或获得生产部署授权。

## 2. 接口矩阵

所有行的 `clause_maturity` 均取其所引用条款的最低成熟度。`interface_completeness` 只允许 `COMPLETE`、`INCOMPLETE` 或 `BLOCKED_BY_DECISION`。本轮决定均已冻结，因此所有当前接口行为 `COMPLETE`，`clause_maturity=FROZEN`，`blocking_decisions` 为空；未来若出现新的 `OPEN` 或 `PROPOSED` 决定，必须重新传播决定阻断并降低对应接口成熟度。

| Producer | Consumer | 传输介质 | 条款 ID | schema 或结构引用 | 生命周期所有者 | 错误语义 | 幂等规则 | 兼容规则 | interface_completeness | clause_maturity | blocking_decisions | affected_tasks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MCU OTA identity provider | Flutter OTA domain | BLE `INFO` | `OTA-XC-INFO-MAPPING`, `OTA-XC-IMAGE-IDENTITY`, `OTA-XC-DEVICE-MODEL` | `docs/ota-binary-contracts.md` §5.2.1 + `DeviceOtaInfo` | MCU 负责真实值，Flutter 负责解析和不可变快照 | 二进制状态码只引用 §5.7；格式错误不得构造 DTO | `GET_INFO` 只读，可安全重试 | 未知 model/hash/protocol fail closed | `COMPLETE` | `FROZEN` | — | `P3-2`, `P3-3`, `P3-5`, `P5-1` |
| Flutter OTA domain | Worker latest API | HTTPS query | `OTA-XC-CLOUD-QUERY-MAPPING`, `OTA-XC-HTTP-LATEST` | `FirmwareLatestQuery` | Flutter 生成，Worker 校验 | `OTA-XC-HTTP-ERROR` | 相同查询无副作用 | `OTA-XC-COMPATIBILITY`, `OTA-XC-UNKNOWN-FIELDS` | `COMPLETE` | `FROZEN` | — | `P3-3`, `P4-2`, `P3-5`, `P5-1` |
| Worker latest API | Flutter OTA domain | HTTPS JSON | `OTA-XC-HTTP-LATEST`, `OTA-XC-ASSET-SELECTION` | `FirmwareLatestResponse` | Worker | `OTA-XC-HTTP-ERROR` | 只读 | schema v2 可加可选字段；download 只签 token v2 | `COMPLETE` | `FROZEN` | — | `P3-3`, `P4-2`, `P3-5`, `P5-1` |
| Worker/R2 | Flutter downloader | HTTPS binary | `OTA-XC-HTTP-DOWNLOAD`, `OTA-XC-HTTP-RESUME` | 选中 asset 的原始文件字节 | Worker 校验授权，R2 保存不可变对象，Flutter 校验长度和摘要 | `OTA-XC-HTTP-ERROR` | 单区间 `bytes=N-`；partial 绑定资产身份 | token v2；v1 仅有界兼容既有 public URL | `COMPLETE` | `FROZEN` | — | `P3-3`, `P3-5`, `P4-2`, `P4-3`, `P5-1`, `P5-2` |
| Flutter BLE transport | MCU BLE transport | FFF2 下行/FFF1 上行 | `OTA-XC-BLE-LIFECYCLE`, `OTA-XC-BLE-TUNING`, `OTA-XC-FLUTTER-TRANSPORT` | `docs/ota-binary-contracts.md` §5 | Flutter 管发送窗口，MCU 管 session/staging durable 状态 | 状态码唯一来源为二进制合同 §5.7 | 已提交 DATA 重传按 §5.5 幂等 | proto/max window 由 `INFO` 协商 | `COMPLETE` | `FROZEN` | — | `P3-1`, `P3-3`, `P3-4`, `P3-5`, `P5-1`, `P5-2` |
| GitHub Actions release job | metadata builder | 文件 + JSON | `OTA-XC-RELEASE-CLI`, `OTA-XC-ASSET-NAMING`, `OTA-XC-RELEASE-METADATA` | `FirmwareReleaseRegistration` | release job | 任一步非零即整链失败 | 相同输入产生相同 canonical metadata | schema v2；未知资产 kind 拒绝 | `COMPLETE` | `FROZEN` | — | `P4-1`, `P4-2`, `P4-4` |
| GitHub Actions R2 uploader | R2 immutable object | Wrangler/R2 object write | `OTA-XC-R2-UPLOAD`, `OTA-XC-R2-IMMUTABILITY` | `R2AssetUploadResult` | uploader 负责 put、HEAD/readback 和机器结果 | 失败输出稳定 JSON 且不得继续注册 | 同 key 同长度/摘要为 `ALREADY_PRESENT` | 媒体类型、长度和 RFC 9530 摘要稳定 | `COMPLETE` | `FROZEN` | — | `P4-1`, `P4-2`, `P4-4` |
| register client | Worker register API | HTTPS JSON | `OTA-XC-HTTP-REGISTER`, `OTA-XC-RELEASE-METADATA`, `OTA-XC-SECURITY` | `FirmwareReleaseRegistration` / `FirmwareReleaseRegistrationResult` | Worker | `OTA-XC-HTTP-ERROR` | 完全相同 metadata 重放返回 200 | schema v2；未知字段拒绝 | `COMPLETE` | `FROZEN` | — | `P4-1`, `P4-2`, `P4-4` |
| register API | D1/R2 | D1 batch + R2 HEAD/readback | `OTA-XC-D1-RELEASE`, `OTA-XC-D1-ASSET`, `OTA-XC-D1-CHANNEL`, `OTA-XC-D1-AUDIT`, `OTA-XC-D1-STATE`, `OTA-XC-D1-MIGRATION`, `OTA-XC-R2-IMMUTABILITY` | release、asset、channel、audit 记录 | Worker | 验证失败不产生 ready release | `OTA-XC-IDEMPOTENCY` | manifest 可验证记录进入 v2；其余 legacy 隔离 | `COMPLETE` | `FROZEN` | — | `P4-1`, `P4-2` |
| D1 latest state | Worker latest API | D1 query | `OTA-XC-ASSET-SELECTION`, `OTA-XC-D1-RETENTION` | ready release + available assets + channel revision | Worker | 不完整/不可用资产不得返回 | 只读 | recovery 永不自动分发；引用保护后才可清理 | `COMPLETE` | `FROZEN` | — | `P3-3`, `P3-5`, `P4-2`, `P4-3`, `P5-1`, `P5-2` |
| admin operator | firmware channel/release | Access-authenticated HTTPS | `OTA-XC-HTTP-ADMIN`, `OTA-XC-ADMIN-RETRACT`, `OTA-XC-ADMIN-STOP`, `OTA-XC-ADMIN-IDEMPOTENCY`, `OTA-XC-D1-CHANNEL`, `OTA-XC-D1-AUDIT`, `OTA-XC-IDEMPOTENCY`, `OTA-XC-D1-RETENTION` | `FirmwareAdminListResponse`, `FirmwareAdminChannelMutationRequest/Result`, `FirmwareAdminReleaseActionRequest/Result`, `FirmwareAdminRecoveryDownloadResult` | admin API | `OTA-XC-HTTP-ERROR`；CAS/幂等冲突不得部分更新 | channel 使用 expectedRevision；release action 使用 `Idempotency-Key` | channel 只指向 ready；recovery 仅 token v2 | `COMPLETE` | `FROZEN` | — | `P4-2`, `P4-3`, `P5-2` |
| GitHub environment/secrets | release job | Actions secret/variable | `OTA-XC-SECRETS`, `OTA-XC-RELEASE-GATE` | `firmware-rehearsal` / `firmware-production` environment | 仓库 owner/发布责任人 | 缺项或证据不一致必须硬失败 | 配置重放不产生资产 | rehearsal 与 production 凭据和资源隔离 | `COMPLETE` | `FROZEN` | — | `P4-1`, `P4-4` |

## 3. 设备身份与字段映射

### OTA-XC-INFO-MAPPING

裁定依据：`OTA-DEC-001`、`OTA-DEC-002`。

MCU 必须从当前运行镜像、Boot 常量和 BLE 协议实现读取真实身份；不得由 Flutter 页面、广播名或 Cloudflare 默认值代填。`INFO` 的字节布局和字段宽度只引用 `docs/ota-binary-contracts.md` §5.2.1。

| 语义 | MCU `INFO` 名称 | Dart `DeviceOtaInfo` | latest query | CI/JSON | D1 |
|---|---|---|---|---|---|
| 线端机型 | `model` | `wireModel` | 不直接发送 | `wireModel` 仅作审计 | 不作选包键 |
| 云端机型键 | 由映射得到 | `deviceModel` | `deviceModel` | `deviceModel` | `device_model` |
| 硬件修订 | `hw_rev` | `hardwareRevision` | `hardwareRevision` | `hardwareRevision` | `hardware_rev` |
| 分区布局代 | `layout_id` | `layoutId` | `layoutId` | `layoutId` | `layout_id` |
| Boot 版本 | `boot_ver` | `bootVersion` | `bootVersion` | `minBootVersion` | `min_boot_version` |
| 当前版本码 | `cur_vcode` | `currentVersionCode` | `currentVersionCode` | `versionCode`/`baseVersionCode` | `version_code`/`base_vcode` |
| 当前镜像身份 | `image_sha256` | `currentImageSha256` | `currentImageSha` | `targetImageSha256`/`baseImageSha256`；`from_image_sha256` 仅为 CLI/evidence 别名 | `target_image_sha256`/`base_image_sha256` |
| BLE 协议版本 | `proto_ver` | `protocolVersion` | `protocolVersion` | `minProtocolVersion` | `min_protocol_version` |
| 最大窗口段数 | `max_window_segs` | `maxWindowSegments` | 不发送 | 仅运行期协商 | 不持久化 |

MCU、Dart、JSON、SQL 的摘要字符串统一为 64 个小写十六进制字符；BLE 内仍按二进制合同传 32 字节原值。解析端必须拒绝非 32 字节摘要、非 ASCIIZ model、非法版本码或非合同协议版本。

### OTA-XC-DEVICE-MODEL

裁定依据：`OTA-DEC-001`。

`INFO.model` 的正式线端值固定为 7 个 ASCII 字符 `E-Track`，8 字节线格式精确为 `E-Track\0`。Flutter 必须通过显式不可变映射表将其映射为 Cloudflare `deviceModel=e-track-at32f435`。

- MCU 不得自行截断或发送 `e-track-at32f435`。
- Flutter 不得从蓝牙广播名、页面默认值或历史缓存猜测 `deviceModel`。
- 未知、缺少、非 ASCIIZ 或不精确匹配 `E-Track\0` 的 model 必须拒绝升级，不得使用默认映射。
- Flutter 对上述本地映射失败统一产生稳定领域错误 `UNKNOWN_DEVICE_MODEL`，保留原始 8 字节诊断摘要，不请求 latest，不进入下载或 BLE，也不得转换为 `NO_UPDATE`。
- Worker 不接收 wire model；若 latest 的 `deviceModel` 缺失或不是已注册的正式键，返回 HTTP 400 `UNKNOWN_DEVICE_MODEL`，不得加载 channel、执行兼容判断或签发 URL。

### OTA-XC-IMAGE-IDENTITY

裁定依据：`OTA-DEC-002`。

跨系统差分基版身份必须在以下位置使用同一 SHA-256 域：`INFO.image_sha256`、Flutter `currentImageSha256`、latest `currentImageSha`、patch `baseImageSha256`、release `targetImageSha256` 和 P3/P5 最终核验值。

`PLAN-OTA.md` 中的 `from_image_sha256` 是发布 CLI 和 verification evidence 对 patch 基版镜像身份的别名。它必须映射到注册 JSON `baseImageSha256` 和 D1 `base_image_sha256`，不新增第二个 JSON 字段、D1 列或摘要域。

跨系统镜像身份固定为最终 `app.bin` 的全部 `image_len` 字节原始 SHA-256。`fw_header.image_sha256` 的双零法属于独立的 header-integrity 摘要域，不得进入 `INFO.image_sha256`、latest、patch base、release target 或 P3/P5 的 raw identity 比较；它只用于冻结 header/槽校验及其截断别名。

资产文件摘要 `asset.sha256` 始终只表示被下载文件自身的字节摘要，不得与目标镜像身份混用，也不得复制为 `targetImageSha256`。

跨名称摘要域矩阵如下；每个 `sha8` 都只表示其所在摘要域完整值的前 8 个字节，不能把不同域的截断值互换，也不能从截断值反推或把截断值当作跨系统完整身份：

| 名称 | 算法与覆盖字节 | 正确来源/流向 | 禁止流向 |
|---|---|---|---|
| `.etu base_sha8` | SHA-256(上一正式版最终 `app.bin` 全部 `image_len` 字节) 的前 8B | 只供 .etu 外层头的差分基版快速拒绝，并与当前设备 raw 镜像 SHA 前 8B 比较 | 不得写入 `INFO.image_sha256`、latest、D1 `target_image_sha256` 或 asset 摘要 |
| `ETSL.sha8` | 写入 candidate/backup/recovery 槽的 `fw_header.image_sha256` 双零法完整摘要的前 8B | 只供片上槽头完整性/快速识别和启动前槽校验；槽校验必须与同一 header digest 的前 8B 比较 | 不得作为 patch 基版完整身份、latest 查询值或 release target identity |
| 包/patch header digest | `fw_header.image_sha256` 的 SHA 双零法：完整镜像中 `image_sha256` 与 `header_crc32` 字段按全零参与 | 只供 Boot/header 校验、槽头 `sha8` 填充和 `verify-fw-header` 证据 | 不得进入 `INFO.image_sha256`、latest、patch `baseImageSha256` 或 release target |
| `candidateImageSha8` | candidate apply 结果的 `fw_header.image_sha256` 双零法完整摘要的前 8B；与该 candidate ETSL.sha8 同域同值 | 只作本地/证据层的 header-integrity 截断别名，可与 candidate `ETSL.sha8` 交叉核对 | 不得替代 32B raw SHA，不得签发 URL 或作为 D1 唯一键 |
| `ETRJ.package_sha256` | 整个 .etu 文件（含 64B 外层头）的 raw SHA-256 | 只作 staging 会话身份和 BEGIN/恢复匹配 | 不得解释为镜像身份、patch 基版身份或 fw_header digest |

只有设备通过一次完整有效的 `INFO` 提供合法 32 字节 raw `image_sha256` 时，Flutter 才可构造 DTO 并请求 latest。字段缺失、长度错误、格式非法或无法计算时必须在 Flutter 本地 fail closed，不请求 latest，也不得借 full 绕过设备身份读取。

### OTA-XC-FLUTTER-DEVICE-DTO

裁定依据：`OTA-DEC-001`、`OTA-DEC-002`。

Flutter 必须建立不可变 `DeviceOtaInfo` 领域对象，至少包含 `wireModel`、`deviceModel`、`hardwareRevision`、`layoutId`、`bootVersion`、`currentVersionCode`、`currentImageSha256`、`protocolVersion` 和 `maxWindowSegments`。

- DTO 只能由一次成功且完整的 `GET_INFO` 响应创建。
- 页面展示、latest 查询、BEGIN 前兼容检查和升级后复核必须使用同一 DTO 快照。
- 连接断开、设备地址变化、session 变化或升级后重连时，旧快照失效并重新查询。
- 不得保留 `igpsport-bsc300`、`0.0.0` 或广播名派生的 OTA 默认身份。
- 本地 `UNKNOWN_DEVICE_MODEL` 和 Worker 返回的 `HARDWARE_INCOMPATIBLE`、`LAYOUT_INCOMPATIBLE`、`BOOT_TOO_OLD`、`PROTOCOL_UNSUPPORTED` 都是终止态；Flutter 必须保存 `requestId` 或本地证据码，禁止继续选包、下载或 BLE。

### OTA-XC-CLOUD-QUERY-MAPPING

裁定依据：`OTA-DEC-001`、`OTA-DEC-002`、`OTA-DEC-004`。

latest 请求由 `DeviceOtaInfo` 和本机 App 版本生成：

| 来源 | query 名 | 规则 |
|---|---|---|
| `ShareLinks.appId` | `appId` | v1 固定 `trace` |
| `DeviceOtaInfo.deviceModel` | `deviceModel` | 先完成 `OTA-XC-DEVICE-MODEL` 映射 |
| App 配置 | `channel` | `stable` 或 `beta` |
| `currentVersionCode` | `currentVersionCode` | 必填非负整数；不再依赖页面字符串版本 |
| `currentImageSha256` | `currentImageSha` | 必填 64 小写 hex |
| `hardwareRevision` | `hardwareRevision` | 必填非负整数 |
| `layoutId` | `layoutId` | 必填 0..255 |
| `bootVersion` | `bootVersion` | 必填 0..255 |
| `protocolVersion` | `protocolVersion` | 必填 0..255 |
| 本机 App build number | `appVersionCode` | 必填十进制整数，范围 `0..2100000000` |

旧 `currentVersion` 字符串只允许在迁移期作为非规范性兼容输入；当 `currentVersionCode` 存在时不得参与选包。

## 4. HTTP 元数据与下载

### OTA-XC-HTTP-LATEST

裁定依据：`OTA-DEC-004`、`OTA-DEC-012`。

公开入口为 `GET /api/public/firmware/latest`。请求参数集合由 `OTA-XC-CLOUD-QUERY-MAPPING` 定义；未知参数按 `OTA-XC-UNKNOWN-FIELDS` 拒绝。

有更新时返回 HTTP 200、`Content-Type: application/json`，候选 schema 为：

```json
{
  "schemaVersion": 2,
  "requestId": "request-id",
  "updateAvailable": true,
  "appId": "trace",
  "deviceModel": "e-track-at32f435",
  "channel": "stable",
  "releaseId": "release-id",
  "versionName": "2.8.1",
  "versionCode": 20801,
  "releaseTag": "mcu-e-track-at32f435-v2.8.1",
  "releaseNotes": "text",
  "targetImageSha256": "64-lowercase-hex",
  "targetHardware": "AT32F435RGT7",
  "transport": "ble",
  "minAppVersionCode": 0,
  "asset": {
    "assetId": "asset-id",
    "kind": "patch",
    "fileName": "e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu",
    "sha256": "64-lowercase-hex",
    "sizeBytes": 12345,
    "baseVersionCode": 20800,
    "baseImageSha256": "64-lowercase-hex",
    "downloadUrl": "signed-url",
    "expiresAt": 1780000000
  }
}
```

`asset.kind=full` 时 `baseVersionCode` 必须为 0，`baseImageSha256` 必须为 JSON `null`。公开 latest 不得返回 `recovery`。没有更新时返回 HTTP 200：

```json
{
  "schemaVersion": 2,
  "requestId": "request-id",
  "updateAvailable": false,
  "errorCode": "NO_UPDATE"
}
```

`disable_latest=1` 时返回 HTTP 200、`updateAvailable=false`、`errorCode=CHANNEL_STOPPED`，可附 `maintenanceMessage`，且不得签发下载 URL。

latest 的处理顺序固定为：参数校验和限流 → 加载有效 channel/release → 确认存在更新 → App 版本门禁 → 设备兼容与选包 → 签发 URL。

- `appVersionCode` 缺失、空值、非十进制整数、负数或大于 `2100000000` 时返回 HTTP 400 `INVALID_PARAMETER`。
- 只有在确认存在更新后才评估 App 门禁；`appVersionCode < release.minAppVersionCode` 时返回 HTTP 426 `CLIENT_TOO_OLD`。
- `CLIENT_TOO_OLD` 响应必须包含 `minAppVersionCode`，不得包含 asset、download URL、签名或其他取包信息。
- App 门禁通过后，兼容检查顺序固定为 hardware → layout → Boot → protocol。`hardwareRevision != release.hardwareRevision` 返回 HTTP 409 `HARDWARE_INCOMPATIBLE`；`layoutId != release.layoutId` 返回 HTTP 409 `LAYOUT_INCOMPATIBLE`；`bootVersion < release.minBootVersion` 返回 HTTP 409 `BOOT_TOO_OLD`；`protocolVersion < release.minProtocolVersion` 或协议版本不受支持时返回 HTTP 409 `PROTOCOL_UNSUPPORTED`。
- 上述设备兼容错误必须包含 `requestId`、失败维度对应的 required/actual 数值和 `releaseId`，不得包含 asset、download URL、签名或其他取包信息；不同维度不得折叠成 `UNKNOWN_DEVICE_MODEL` 或 `NO_UPDATE`。
- download endpoint 不接收也不重复校验 `appVersionCode`；兼容性以 latest 签发前门禁为准。
- Flutter 收到 `CLIENT_TOO_OLD` 或任一设备兼容错误后进入终止状态，不得转换为 `NO_UPDATE`，也不得进入下载或 BLE。

### OTA-XC-ASSET-SELECTION

裁定依据：`OTA-DEC-002`。

Worker 只从 channel 当前指向的 `ready` release 选包：

patch 的 `base_image_sha256 == currentImageSha` 比较必须使用 `OTA-XC-IMAGE-IDENTITY` 定义的最终 `app.bin` raw SHA-256，不得使用 asset 摘要、header 双零摘要或摘要前缀。

1. `version_code <= currentVersionCode` 时 `NO_UPDATE`。
2. 若存在 `kind=patch`、`r2_state=available` 且 `base_image_sha256 == currentImageSha` 的唯一资产，返回该 patch。
3. 只有输入 `currentImageSha` 来自完整有效 INFO，且不存在匹配的已验证 patch 或匹配 patch 不可用时，才返回唯一 `kind=full`、`r2_state=available` 资产。
4. full 缺失、重复或不可用时不得返回 patch 代替完整兜底，必须 fail closed 为后端不可用。
5. `recovery` 永不参与自动选包。
6. full 所属 release 必须具有权威 `target_image_sha256`，并通过资产长度和资产 SHA-256 检查；hardware、layout、Boot 和 protocol 已由 `OTA-XC-HTTP-LATEST` 在选包前分别判定，选包层不得把兼容错误改写成后端不可用。
7. 缺少权威目标镜像身份的 legacy release 不得进入 latest，也不得因为存在 full 文件而自动放行。

### OTA-XC-HTTP-DOWNLOAD

裁定依据：`OTA-DEC-012`。

公开下载入口为签名 URL `GET /api/public/firmware/download`。token v2 的 query 集合精确为 `tokenVersion=2`、`assetId`、`releaseId`、`kind`、`purpose`、`expiresAt`、`keyVersion`、`signature`；任一参数缺失、空值、重复或出现未知参数都必须拒绝。

签名输入为以下 UTF-8 canonical message，字段值按行替换，换行符固定为 LF，末行不追加额外字段：

```text
2
GET
assetId
releaseId
kind
purpose
expiresAt
keyVersion
```

`expiresAt` 是十进制 Unix epoch 秒；签名为 HMAC-SHA256，编码为 Base64URL 无 padding。token TTL 固定为 300 秒。`purpose=public-ota` 只允许实际 `kind=full|patch`，`purpose=admin-recovery` 只允许实际 `kind=recovery`，query 与 D1 资产类型或用途不一致时返回 `TOKEN_INVALID`。

`expiresAt` 是排他截止时刻：仅当 `currentEpochSeconds < expiresAt` 时 token 有效；`currentEpochSeconds >= expiresAt` 返回 `TOKEN_EXPIRED`。

部署必须记录固定且可审计的 `v2CutoverEpoch`，不得使用 Worker 启动时间或每次部署时间动态重置兼容窗口：

- 从 `v2CutoverEpoch` 起所有 signer 只生成 v2，部署回滚不得恢复 v1 signer；不能保持 v2 signer/verifier 时必须停止签发 URL。
- v1 token verifier 只接受精确旧 query 集合，且资产实际类型必须为 full/patch，用途只能按 `public-ota` 处理，recovery 始终拒绝。
- v1 `expiresAt` 必须不晚于 `v2CutoverEpoch+300`，并同时满足 `currentEpochSeconds < expiresAt` 和 `currentEpochSeconds < v2CutoverEpoch+300`。
- 到达 `v2CutoverEpoch+300` 时，运行时必须立即自动拒绝全部 v1，不依赖人工在该时刻部署。
- v1 verifier 源码在兼容窗口结束后的首个部署删除；行为上的拒绝从窗口截止时刻立即生效。

完整响应要求：

- full/patch：`Content-Type: application/vnd.e-track.etu`；只接受 `purpose=public-ota`。
- recovery：`Content-Type: application/octet-stream`；只接受 `purpose=admin-recovery`，且该 URL 不得出现在 public latest。
- `Content-Length` 等于 D1 `size_bytes`。
- `Content-Digest` 必须使用 RFC 9530 dictionary member `sha-256=:<base64>:`；`<base64>` 是资产原始字节 SHA-256 的 32 字节结果按 RFC 4648 标准 Base64（含所需 `=` padding）编码，不能填 64 位 hex、Base64URL 或带引号文本。
- `Content-Disposition` 文件名与 metadata `fileName` 一致并完成控制字符转义。
- `Cache-Control: public, max-age=31536000, immutable` 仅在 R2 key 不可变成立时使用。
- `X-Request-Id` 和 `X-Trace-Asset-Type: firmware` 必须存在。
- Flutter 在把 `.part` 文件原子重命名为最终文件前，必须同时验证长度和 metadata `sha256`；metadata/Dart/D1 仍使用 64 位小写 hex，响应 `Content-Digest` 只使用上述 RFC 9530 Base64 表示。响应摘要头用于交叉核对，不能替代 metadata 摘要。

### OTA-XC-HTTP-RESUME

裁定依据：`OTA-DEC-005`。

HTTP 恢复只支持单区间 `Range: bytes=N-`。多区间、suffix range、非十进制边界或其他非法 Range 返回 HTTP 400 `INVALID_PARAMETER`；服务器收到 `N >= sizeBytes` 时返回 HTTP 416。

- 网络失败或 App 重启保留 `.part`；用户显式取消必须停止请求并删除 `.part` 及 sidecar。
- 每个 asset 最多保留一个 partial；超过 `partialRetentionHours=24` 的 `.part` 和 sidecar 必须清理，不能因 assetId 不同无限积累。
- `.part` 必须具有原子 sidecar metadata，记录 `assetId`、`releaseId`、`sha256`、`sizeBytes`、强 ETag 和更新时间。任一身份字段变化立即作废。
- `localPartSize == sizeBytes` 时不发送 Range，先验证整文件 SHA-256；通过后原子转为完成文件，失败则删除并重新 latest。
- `localPartSize > sizeBytes` 时立即删除旧 partial 并重新 latest。
- 206 必须返回 `Accept-Ranges: bytes`、合法 `Content-Range`、`Content-Length` 和与 `If-Range` 一致的强 ETag。
- `If-Range` 不匹配而返回 200 时，Flutter 必须先截断旧文件，禁止把 200 body 追加到 partial。
- 206 的 `Content-Digest` 若存在，只表示本次 response body；完整 200 的 `Content-Digest` 才表示完整响应文件。
- 完整资产身份始终以 metadata `sha256` 为准，组装完成后必须重算整文件 SHA-256，通过后才能进入 BLE。
- 下载 URL 过期时重新 latest；只有 sidecar 与新 metadata 的 assetId、releaseId、sha256、sizeBytes 和强 ETag 全部一致时才允许继续 partial，否则从零开始。

### OTA-XC-HTTP-ERROR

除 `NO_UPDATE`/latest 侧 `CHANNEL_STOPPED` 这类 HTTP 200 业务结果外，失败统一为：

```json
{
  "errorCode": "STABLE_CODE",
  "message": "human-readable message",
  "requestId": "request-id",
  "retryAfter": 5
}
```

`retryAfter` 只在有意义时出现。稳定语义如下：

| errorCode | HTTP | 调用方行为 |
|---|---:|---|
| `INVALID_PARAMETER` | 400 | 修正请求，不自动重试 |
| `TOKEN_INVALID` | 401 | CI/download/Admin Access 凭据无效；重新鉴权，不把 401 改报权限不足 |
| `TOKEN_EXPIRED` | 401 | 凭据过期；取得新凭据或重新 latest 后再请求 |
| `ACCESS_FORBIDDEN` | 403 | Access 身份有效但不在允许主体集合；不得自动重试 |
| `ROLE_FORBIDDEN` | 403 | 已认证主体角色不足；不得降级角色要求 |
| `ORIGIN_FORBIDDEN` | 403 | admin mutation 非允许 same-origin；不得产生副作用 |
| `CSRF_INVALID` | 403 | admin mutation 的 CSRF cookie/header 缺失或不匹配；不得产生副作用 |
| `CLIENT_TOO_OLD` | 426 | 终止 OTA；响应只提供 `minAppVersionCode` 等兼容说明，不得包含取包信息 |
| `UNKNOWN_DEVICE_MODEL` | 400 | 本地映射失败时不发请求；Worker 收到未知 deviceModel 时终止，不得猜测正式机型 |
| `HARDWARE_INCOMPATIBLE` | 409 | 终止 OTA；记录 hardware required/actual，不得改报未知机型 |
| `LAYOUT_INCOMPATIBLE` | 409 | 终止 OTA；记录 layout required/actual，不得进入选包 |
| `BOOT_TOO_OLD` | 409 | 终止 OTA；记录 minBootVersion/bootVersion，不得进入下载 |
| `PROTOCOL_UNSUPPORTED` | 409 | 终止 OTA；记录 minProtocolVersion/protocolVersion，不得进入 BLE |
| `ASSET_DISABLED` | 410 | 丢弃本地 metadata，重新 latest |
| `ASSET_ARCHIVED` | 409 | 重新 latest；不得继续旧 URL |
| `RATE_LIMITED` | 429 | 遵守 `Retry-After`，只做有界重试 |
| `CHANNEL_STOPPED`, `BACKEND_UNAVAILABLE` | 503 | 保留设备状态，不进入 BLE；允许用户稍后重试 |
| `CAS_CONFLICT` | 409 | admin/CI 重新读取 revision，不盲重放 |
| `VERSION_REGRESSION` | 409 | 停止普通 publish；只有明确 retract 合同可移动到较低 vcode |
| `RELEASE_CONFLICT`, `RELEASE_INCOMPLETE` | 409 | CI 停止；不得覆盖旧 release 或把不完整 release 标 ready |
| `R2_OBJECT_CONFLICT` | 409 | 同 key 字节身份冲突，修正 releaseTag/key/资产，不得覆盖或自动重试 |
| `R2_VERIFY_FAILED` | 503 | put 后长度/摘要 readback 无法确认；不得注册，可按有界存储重试策略重试 |
| `RELEASE_NOT_FOUND` | 404 | admin/CI 停止并重新读取目标集合 |
| `RELEASE_NOT_READY` | 409 | publish/retract/recovery download 的目标仍为 draft；不得绕过 ready gate |
| `RELEASE_DISABLED` | 410 | 目标 release 不可再发布；必须选择其他 ready release |
| `RELEASE_ARCHIVED` | 410 | release 已归档；不得发布、撤回到该版本或签发 recovery URL |
| `RELEASE_IN_USE` | 409 | disable 目标仍被 channel 引用；先用独立 channel mutation 移动 pointer |
| `RELEASE_NOTES_REQUIRED` | 409 | 补齐 release notes 后由用户重新确认操作 |
| `RECOVERY_ASSET_UNAVAILABLE` | 409 | recovery 缺失、重复、未上传或不可验证；不得签发 URL |
| `FORMAL_RELEASE_REQUIRED` | 403 | CI 停止；不得将 nightly/candidate 注册为正式 firmware release |
| `IDEMPOTENCY_CONFLICT` | 409 | 同一 actor/key 被用于不同 fingerprint；不得执行或重放任一新副作用 |
| `IDEMPOTENCY_RESULT_EXPIRED` | 409 | 同 key 的 recovery 首次 URL 或 24 小时结果已过期，结果记录或永久 tombstone 命中；使用新 key 发起新操作 |

未知 `errorCode` 按不可恢复错误处理并保留 `requestId`，不得降级成成功或 `NO_UPDATE`。

## 5. D1、注册与资产生命周期

### OTA-XC-D1-RELEASE

裁定依据：`OTA-DEC-002`、`OTA-DEC-004`、`OTA-DEC-008`。

`firmware_releases` 是版本级记录。目标 migration 必须按下表建立或补齐字段；表中“校验”同时包含 D1 `CHECK`/FK/UNIQUE 和写入前的严格格式校验，不能只依赖 TypeScript 类型。

| 字段 | SQLite 类型 | NULL/默认 | 约束与语义 |
|---|---|---|---|
| `id` | TEXT | NOT NULL | PRIMARY KEY；创建后不可变 |
| `app_id` | TEXT | NOT NULL | FK `apps(id)` ON DELETE CASCADE |
| `device_model` | TEXT | NOT NULL | trim 后非空；与 channel/asset 查询键一致 |
| `version_name` | TEXT | NOT NULL | trim 后非空 |
| `version_code` | INTEGER | NOT NULL | `CHECK(0 <= version_code AND version_code <= 4294967295)`；由规范版本公式生成 |
| `release_tag` | TEXT | NOT NULL | trim 后非空；不可使用可变 latest URL 语义 |
| `commit_sha` | TEXT | NOT NULL | 40 位小写 hex |
| `run_id` | TEXT | NOT NULL | trim 后非空；表示 canonical provenance run id，production promotion 必须复用已批准 rehearsal 的值，不等于当前执行 run id |
| `state` | TEXT | `NOT NULL DEFAULT 'draft'` | `CHECK(state IN ('draft','ready','disabled'))` |
| `release_notes` | TEXT | `NOT NULL DEFAULT ''` | 正式发布前由 release gate 校验 |
| `target_image_sha256` | TEXT | NOT NULL | 64 位小写 hex；摘要域由 `OTA-XC-IMAGE-IDENTITY` 决定 |
| `hardware_rev` | INTEGER | NOT NULL | `CHECK(0 <= hardware_rev AND hardware_rev <= 65535)` |
| `layout_id` | INTEGER | NOT NULL | `CHECK(0 <= layout_id AND layout_id <= 255)` |
| `min_boot_version` | INTEGER | NOT NULL | `CHECK(0 <= min_boot_version AND min_boot_version <= 255)` |
| `min_protocol_version` | INTEGER | NOT NULL | `CHECK(0 <= min_protocol_version AND min_protocol_version <= 255)` |
| `target_hardware` | TEXT | NOT NULL | trim 后非空 |
| `transport` | TEXT | `NOT NULL DEFAULT 'ble'` | v1 `CHECK(transport = 'ble')` |
| `min_app_version_code` | INTEGER | `NOT NULL DEFAULT 0` | `CHECK(0 <= min_app_version_code AND min_app_version_code <= 2100000000)` |
| `archived` | INTEGER | `NOT NULL DEFAULT 0` | `CHECK(archived IN (0,1))` |
| `created_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | UTC SQLite 时间文本；不可改写 |
| `updated_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | 每次允许的状态更新时刷新 |

唯一键：

- `(app_id, device_model, release_tag)`。
- `(app_id, device_model, version_code)`。
- `(app_id, device_model, run_id)`。

`archived` 不等于撤回；撤回只改变 channel 指针。旧单资产列在迁移期可以物理保留，但完成 backfill 后不得继续作为 latest、下载或注册的规范读取源。

### OTA-XC-D1-ASSET

裁定依据：`OTA-DEC-002`、`OTA-DEC-006`、`OTA-DEC-007`。

`firmware_release_assets` 是文件级记录：

| 字段 | SQLite 类型 | NULL/默认 | 约束与语义 |
|---|---|---|---|
| `id` | TEXT | NOT NULL | PRIMARY KEY；创建后不可变 |
| `release_id` | TEXT | NOT NULL | FK `firmware_releases(id)` ON DELETE CASCADE |
| `kind` | TEXT | NOT NULL | `CHECK(kind IN ('full','patch','recovery'))` |
| `file_name` | TEXT | NOT NULL | 非空 plain ASCII file name；禁止 `/`、`\\`、控制字符和路径段 |
| `sha256` | TEXT | NOT NULL | 64 位小写 hex；仅表示该文件的原始字节摘要 |
| `size_bytes` | INTEGER | NOT NULL | `CHECK(size_bytes > 0)` |
| `r2_key` | TEXT | NULL | ready 前必须非空；指向 `OTA-XC-R2-IMMUTABILITY` 的唯一对象 |
| `r2_state` | TEXT | `NOT NULL DEFAULT 'not_uploaded'` | `CHECK(r2_state IN ('not_uploaded','available','archived','r2_deleted'))` |
| `github_url` | TEXT | NOT NULL | 不得包含 `/latest/download/`；必须绑定 immutable releaseTag/fileName |
| `base_image_sha256` | TEXT | `NOT NULL DEFAULT ''` | patch 为 64 位小写 hex；full/recovery 必须为空串哨兵 |
| `base_vcode` | INTEGER | `NOT NULL DEFAULT 0` | patch 为正且小于目标 release `version_code`；full/recovery 必须为 0 |
| `created_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | UTC SQLite 时间文本；不可改写 |
| `updated_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | R2 状态更新时刷新 |

必须同时满足：

- `kind='patch'` 当且仅当 `base_image_sha256 <> ''`、摘要长度为 64 且 `base_vcode > 0`；`kind <> 'patch'` 时必须同时满足 `base_image_sha256 = ''` 和 `base_vcode = 0`。该双向关系必须落为 D1 `CHECK`，不得只做应用预检查。
- 唯一键 `(release_id, kind, base_image_sha256)`，从而每 release 最多一个 full、最多一个 recovery、每个基版最多一个 patch。
- patch `base_vcode < firmware_releases.version_code`、同 release 恰一 full/正式链恰一 recovery 等跨行约束必须由实际 D1 trigger 或同一原子事务中的查询门槛验证。
- `r2_state='available'` 必须同时具有非空 `r2_key`，且 R2 HEAD/readback 长度和摘要与本行一致；不得只信请求体的 `r2Verified` 布尔值。

### OTA-XC-D1-STATE

裁定依据：`OTA-DEC-009`。

release 状态只允许 `draft`、`ready`、`disabled`：

1. CI 注册先创建或匹配 `draft`。
2. 同一原子批次内验证“恰好一个 full”以及本次登记的每个资产都具有匹配的 R2 size/digest，才可转 `ready`。
3. channel publish/retract 目标只允许 `ready` 且未 archived 的 release。
4. 已被任一 channel 引用的 release 不得转 `disabled`。
5. `disabled` 不可恢复为 `ready`；需要修复时发布更高 `version_code` 的新 release。
6. recovery 可以存在于 ready release，但 latest 永不自动分发。

正式发布工作流还必须在进入注册前证明 full、至少一个目标基版 patch、recovery 三类产物都已生成并通过各自验证；D1 ready 的“恰一 full”是最低数据完整性门槛，不替代 P4-1 三资产门禁。

### OTA-XC-D1-CHANNEL

`firmware_channels` 是 firmware latest、publish/retract 和停发开关的唯一持久化指针：

| 字段 | SQLite 类型 | NULL/默认 | 约束与语义 |
|---|---|---|---|
| `id` | TEXT | NOT NULL | PRIMARY KEY；创建后不可变 |
| `app_id` | TEXT | NOT NULL | FK `apps(id)` ON DELETE CASCADE |
| `device_model` | TEXT | NOT NULL | trim 后非空；必须与目标 release 相同 |
| `name` | TEXT | NOT NULL | `CHECK(name IN ('stable','beta'))` |
| `current_release_id` | TEXT | `NULL DEFAULT NULL` | FK `firmware_releases(id)` ON DELETE SET NULL；非空时必须指向同 app/model 的 `ready`、未 archived release |
| `revision` | INTEGER | `NOT NULL DEFAULT 0` | `CHECK(revision >= 0)`；每次成功 mutation 恰加 1 |
| `disable_latest` | INTEGER | `NOT NULL DEFAULT 0` | `CHECK(disable_latest IN (0,1))` |
| `disable_downloads` | INTEGER | `NOT NULL DEFAULT 0` | `CHECK(disable_downloads IN (0,1))` |
| `maintenance_message` | TEXT | `NULL DEFAULT NULL` | 仅作为 stop 说明；不得替代 stop flag |
| `last_action` | TEXT | `NOT NULL DEFAULT 'init'` | `CHECK` 至少覆盖 `init`,`publish`,`retract`,`stop_latest`,`resume_latest`,`stop_downloads`,`resume_downloads`；目标 schema 不再写 `rollback` |
| `last_actor` | TEXT | `NULL DEFAULT NULL` | 成功 mutation 的 actor 标识 |
| `last_actor_type` | TEXT | `NULL DEFAULT NULL` | NULL 或 `ci`,`access`,`system`,`test` |
| `last_request_id` | TEXT | `NULL DEFAULT NULL` | 与同一 mutation 的 audit 行一致 |
| `last_before_json` | TEXT | `NULL DEFAULT NULL` | canonical JSON object；不得含 secret/token |
| `last_after_json` | TEXT | `NULL DEFAULT NULL` | canonical JSON object；必须含更新后的 pointer/revision/stop flags |
| `created_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | UTC SQLite 时间文本；不可改写 |
| `updated_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | 每次成功 mutation 刷新 |

唯一键为 `(app_id, device_model, name)`。INSERT/UPDATE pointer 必须由 D1 trigger 或同一事务内的强制约束拒绝跨 app/model、非 `ready`、archived 或 `disabled` release；已被 channel 引用的 release 也必须由 trigger 拒绝转 `disabled`。所有 publish、retract、stop 和 resume 必须使用 `WHERE id=? AND revision=?` 的 CAS 语义，成功时原子写 pointer/flags、`revision + 1`、last_* 快照和 `OTA-XC-D1-AUDIT` 行；零行更新统一为 409 `CAS_CONFLICT`。同值 stop/resume 不得伪造 revision 增量或审计成功，可返回当前 revision 的明确幂等结果。

### OTA-XC-D1-AUDIT

firmware 操作复用共享 `audit_logs` 表，不创建可被绕开的第二套审计真相源。目标 migration 必须保留既有通用字段，并补齐 firmware reason 约束：

| 字段 | SQLite 类型 | NULL/默认 | 约束与语义 |
|---|---|---|---|
| `id` | TEXT | NOT NULL | PRIMARY KEY |
| `app_id` | TEXT | `NULL DEFAULT NULL` | FK `apps(id)` ON DELETE SET NULL |
| `actor` | TEXT | NOT NULL | CI 固定服务 actor 或 Access email；不得为空 |
| `actor_type` | TEXT | NOT NULL | `CHECK(actor_type IN ('ci','access','system','test'))` |
| `action` | TEXT | NOT NULL | firmware 至少覆盖既有 register、publish、retract、stop/resume、R2 state 变更，并固定包含 `disable_release`、`issue_recovery_download` |
| `target_type` | TEXT | NOT NULL | firmware 使用 `firmware_release`、`firmware_asset` 或 `firmware_channel` |
| `target_id` | TEXT | `NULL DEFAULT NULL` | 对应目标主键；批量注册可指 release id |
| `request_id` | TEXT | NOT NULL | 与响应 `X-Request-Id`/JSON `requestId` 一致；不设唯一键，一个请求可有多个原子审计效果 |
| `reason` | TEXT | `NULL DEFAULT NULL` | admin publish/retract/stop/resume/disable/recovery-download 必须 trim 后非空；CI/system 行可为空或使用稳定机器原因 |
| `ip` | TEXT | `NULL DEFAULT NULL` | 仅 admin 可记录；无值不得伪造 |
| `user_agent` | TEXT | `NULL DEFAULT NULL` | 仅 admin 可记录；不得含 token |
| `before_json` | TEXT | `NULL DEFAULT NULL` | canonical JSON object；创建操作可为空 |
| `after_json` | TEXT | `NULL DEFAULT NULL` | canonical JSON object；mutation 成功时必须包含结果状态，channel 操作必须包含新 revision |
| `created_at` | TEXT | `NOT NULL DEFAULT (datetime('now'))` | UTC SQLite 时间文本；不可改写 |

除主键 `id` 外不新增唯一键；`request_id` 允许关联同一事务的多行。表必须通过 `BEFORE UPDATE` 和 `BEFORE DELETE` trigger 保持 append-only。channel mutation 与其 audit insert 必须在同一 D1 原子批次内完成，任一失败全部回滚；鉴权失败、CAS 冲突和参数校验失败不得写成成功审计。完全相同的 register 幂等重放不得新增业务审计效果。

Admin release action 的 audit 映射固定如下：

- `disable_release`：`target_type=firmware_release`、`target_id=releaseId`；`before_json` 必须是只含 `state`、`archived` 的 canonical object，`after_json` 必须是同字段且 `state=disabled` 的 canonical object。
- `issue_recovery_download`：`target_type=firmware_asset`、`target_id=assetId`；`before_json` 必须是只含 `releaseId`、`assetId`、`kind`、`r2State`、`sha256`、`sizeBytes` 的 canonical object，`after_json` 必须是只含相同资产身份以及 `purpose=admin-recovery`、Unix epoch 秒 `expiresAt` 的 canonical object。两者都不得包含完整 URL、token、signature 或 HMAC key material。
- 两类 action 的 `actor` 必须是通过 Access owner 校验的主体，`reason` 必须非空，`request_id` 必须与响应一致。`request_id` 仍是非唯一关联字段，不能承担 release action 的幂等键或重放判定。

### OTA-XC-D1-MIGRATION

裁定依据：`OTA-DEC-010`、`OTA-DEC-011`。

迁移必须新增表/列，不得原地丢失旧单资产记录。旧 release 只有通过 `manifestSchemaVersion=1` 的版本化、不可变 backfill manifest 才可进入 v2。每条 manifest 必须绑定并提供：

- `releaseId`、`appId`、`deviceModel`、`releaseTag`、`runId`、`commitSha`、`versionName`、`versionCode`。
- `targetImageSha256`、`hardwareRevision`、`layoutId`、`minBootVersion`、`minProtocolVersion`、`targetHardware`。
- 不可变 artifact locator、asset SHA-256/size、最终 `app.bin` raw `image_len` SHA-256、验证工具版本、证据摘要、`verifiedBy` 和 `verifiedAt`。

manifest 必须由 Cloudflare/D1 迁移责任人与 OTA 发布链审查人批准，并逐字段匹配旧记录、逐字节验证 artifact。`targetImageSha256` 必须使用 `OTA-XC-IMAGE-IDENTITY` 的最终 `app.bin` raw SHA-256。

- 禁止把旧 asset `sha256` 复制为 `target_image_sha256`；也禁止从 deviceModel、当前默认配置、0、空串、固定硬件值或文件名猜测身份。
- 字段缺失、格式错误、旧记录不匹配、artifact 不可取得或任一验证失败时，该记录保持 legacy 隔离，不写伪造 v2 identity。
- legacy release 不得进入 latest、不得作为 patch 基版、不得触发 full fallback、不得 publish，也不得签发 recovery URL。
- channel 若仍指向未验证 legacy release，规范 v2 读取切换必须 fail closed；必须先提供有效 manifest 或通过显式 channel mutation 移动到已验证 release。
- 每条旧 firmware release 回填一个 `kind=full` asset，复制 file/sha/size/R2/GitHub 字段，base 哨兵为空串、base_vcode=0。
- 已发布 channel 指向的旧 release 必须先验证 R2 对象长度、asset 摘要和完整 manifest identity；任一无法验证时 migration/backfill 必须停止，禁止把记录标成 ready或切换规范读取源。
- 只有资产和全部 v2 release identity 字段都已验证、且当前被 channel 引用的旧 release 才可映射为 `ready`；未发布记录保持 `draft`，直至显式完整性校验；旧 `disabled` 保持 `disabled`。
- backfill 可重入；同一旧记录和同一 manifest 重复执行不得生成第二个 full 或改变已验证 identity。manifest 内容变化必须作为冲突拒绝，不能覆盖既有身份。
- 现有 `firmware_channels.last_action='rollback'` 必须迁移为 `retract` 语义；迁移只能改命名和审计解释，不得改变 pointer 或 revision。
- 共享 `audit_logs.reason` 的新增列允许旧非 firmware 行保持 NULL；新 admin firmware mutation 从 migration 生效后必须非空。
- 目标 migration 必须按 `OTA-XC-ADMIN-IDEMPOTENCY` 创建 `firmware_admin_idempotency` 表、`UNIQUE(actor_canonical,idempotency_key)` 和 `INDEX(retained_until)`，并落实 completed/action/expiry 的 CHECK 约束；migration 不得回填猜测的幂等结果，也不得留下可提交的 pending 行。表、约束、索引或既有 firmware 数据迁移任一步失败时，整次 migration 必须原子回滚。
- 同一 migration 还必须创建 `firmware_admin_idempotency_tombstones` 轻量 key-reuse guard，至少包含 `actor_canonical`、`idempotency_key`、`fingerprint`、原 action/release、`expired_at` 和 `tombstoned_at`，以 `(actor_canonical,idempotency_key)` 为 PRIMARY KEY/UNIQUE；tombstone 不得保存 response body、URL、token 或 signature，且不得被结果清理删除。
- migration 和 backfill 必须有实际 SQLite/D1 约束测试，不能只用 TypeScript 内存判断模拟唯一键。

### OTA-XC-D1-RETENTION

裁定依据：`OTA-DEC-007`。

保留范围为 `(appId, deviceModel)`。正式 release 按 `version_code` 降序计算“最近 10 个”，不得使用可变 `updated_at`；年龄从创建后不可改写的 `firmware_releases.created_at` 计算。

只有同时满足以下条件的 release 才能由 cleaner 列入候选：

- 排名在最近 10 个正式 release 之外。
- `ageDays >= 365`。
- 不被任何 ready patch 的 `base_image_sha256`、stable/beta pointer、未完成注册、恢复或清理任务引用。
- 不含需要自动删除的 recovery；recovery 永不进入自动候选。

cleaner 每月运行一次，但能力上限仅为生成不可变的 `retentionCandidateManifest`，不得执行 archived 状态迁移、审批、R2/GitHub 删除、D1 状态写入或任何 wildcard/batch-delete 接口。manifest 必须逐资产列出不可变 `releaseId`、`assetId`、`kind`、`r2Key`、`sha256`、`sizeBytes`、生成时间、引用查询快照摘要和规则版本；同一输入重放必须产生相同 manifest，内容变化按冲突拒绝。任一引用查询、状态查询或 manifest/audit 写入失败时，本轮 fail closed，不输出可执行删除指令。

归档和物理删除由独立受控执行器分阶段完成：它只接受一份完整 manifest，重新读取并核对全部资产身份、引用和状态。进入 archived 前必须由产品/运营 owner 与 Cloudflare 成本责任人共同批准并写入 append-only audit；任一批准缺失或记录失败均不得开始隔离。批准后执行器原子转为 archived 并写状态 audit，30 天隔离期从成功状态迁移及其 audit 时间开始。隔离结束后执行器必须重新检查全部引用，并由同一双人角色对最终不可变删除 manifest 再次批准；隔离前批准不能代替物理删除前批准。最终删除接口必须只接受该 manifest 列出的精确资产 ID，拒绝空列表、通配符、范围表达式和隐式“整 release”删除。

recovery 永不进入 cleaner 候选。用户另行授权 recovery 删除时，必须使用独立 `recoveryDeletionManifest`，逐项列出唯一 releaseId、assetId、kind=recovery、r2Key、sha256 和 sizeBytes；该 manifest 不得与普通候选合并或使用 wildcard，并经过同样的双人批准、30 天隔离、引用重查和最终 manifest 再批准流程。R2 删除后保留 D1 release/asset 记录，将资产状态记为 `r2_deleted`；D1 identity、摘要、状态历史和 append-only audit 不得物理删除。GitHub Release 资产默认永久保留，R2 删除不得自动连带删除 GitHub 资产；GitHub 删除需要另行双人批准。

### OTA-XC-R2-IMMUTABILITY

裁定依据：`OTA-DEC-006`、`OTA-DEC-007`、`OTA-DEC-008`。

R2 key 必须由 appId/deviceModel/versionCode/releaseTag/asset fileName 确定，并且写入后不可变：

- key 不存在时允许上传。
- key 已存在且 size/digest 完全一致时视为幂等成功。
- key 已存在但任一字节身份不同必须硬失败；不得使用覆盖参数把旧对象替换成新内容。
- register API 只接受已通过 HEAD 或回读验证的 R2 metadata。

### OTA-XC-IDEMPOTENCY

本条只覆盖 CI register 和 channel CAS。Admin disable/recovery-download 的重放语义由 `OTA-XC-ADMIN-IDEMPOTENCY` 单独管理。CI 注册幂等键为 `(appId, deviceModel, releaseTag, commitSha, canonicalProvenanceRunId)` 加完整规范化 metadata；其中 canonical provenance run id 是 `OTA-XC-RELEASE-METADATA` 的 `runId`，production 当前 `executionRunId` 不参与：

- 完全相同的重放返回 200、`idempotent=true`，不得新增 release/asset/audit 业务效果。
- releaseTag 相同但 commit、run 或 asset metadata 不同返回 409。
- R2 backfill 只能补齐同一 commit 和同一资产摘要，不得改变 release 身份。
- admin channel 操作必须携带 `expectedRevision`，成功时 revision 恰加 1；CAS 失败返回 409。
- audit log 必须记录 actor、reason、requestId、before、after，不得记录 secret/token。

### OTA-XC-ADMIN-IDEMPOTENCY

裁定依据：`OTA-DEC-011`。

Admin channel mutation 继续使用 `expectedRevision` 和同值 stop/resume 规则；本条只处理没有 revision 的 release action：`disable` 与 `recovery-download`。

两个 release action 都必须携带 `Idempotency-Key`。值必须是精确 36 个 ASCII 字符的小写 canonical UUIDv4；缺失或非法返回 HTTP 400 `INVALID_PARAMETER`。`X-Request-Id` 仍只用于链路关联，不参与幂等唯一性。

唯一范围为 `actorCanonical + key`，跨 `disable` 和 `recovery-download` 两个 endpoint。`actorCanonical` 是通过 Access 校验后的 actor email 经 trim 并转小写所得；不同 actor 可以使用相同 key，同一 actor 在另一 release/action 复用同一 key 必须触发 fingerprint 检查。

request fingerprint 固定为以下对象的 RFC 8785 canonical JSON UTF-8 字节做 SHA-256，并编码为 64 位小写 hex：

```json
{
  "method": "POST",
  "path": "/api/admin/firmware/releases/{canonical-release-id}/{action}",
  "body": {
    "appId": "trace",
    "deviceModel": "e-track-at32f435",
    "reason": "validated exact string"
  }
}
```

`path` 必须由已验证的 `releaseId` 和 action 重建，无 query、无尾部斜杠；不得直接使用可能存在不同编码形式的原始 URL 文本。body 是通过未知字段和类型校验后的精确请求值。

D1 必须新增 `firmware_admin_idempotency` 表；不得复用非唯一的 `audit_logs.request_id`：

| 字段 | SQLite 类型 | NULL/默认 | 约束与语义 |
|---|---|---|---|
| `actor_canonical` | TEXT | NOT NULL | trim 后小写 Access email |
| `idempotency_key` | TEXT | NOT NULL | 精确 36B 小写 canonical UUIDv4 |
| `fingerprint` | TEXT | NOT NULL | 64 位小写 hex |
| `method` | TEXT | NOT NULL | `CHECK(method='POST')` |
| `canonical_path` | TEXT | NOT NULL | 已验证 releaseId/action 重建的无 query 路径 |
| `action` | TEXT | NOT NULL | `CHECK(action IN ('disable','recovery-download'))` |
| `release_id` | TEXT | NOT NULL | FK release id；创建后不可变 |
| `state` | TEXT | NOT NULL | `CHECK(state IN ('pending','completed'))`；pending 只允许存在于未提交事务内 |
| `status_code` | INTEGER | NULL | completed 时精确为 200 |
| `response_body_json` | TEXT | NULL | completed 时为首次 canonical JSON 响应；可含 recovery URL，但不得复制到 audit/log |
| `request_id` | TEXT | NULL | completed 时为首次 requestId |
| `created_epoch_seconds` | INTEGER | NOT NULL | 首次成功事务使用的 epoch 秒 |
| `retained_until` | INTEGER | NOT NULL | 精确等于 `created_epoch_seconds+86400` |
| `original_expires_at` | INTEGER | NULL | recovery-download completed 时必填；disable 必须为 NULL |

主键或 UNIQUE 固定为 `(actor_canonical, idempotency_key)`；另建 `INDEX(retained_until)`。CHECK 必须保证 completed 行的 status/body/requestId 非空、`retained_until > created_epoch_seconds`，以及 `original_expires_at` 与 action 的双向关系。key 原值仅可存在于该受控表，不得进入 append-only audit、普通日志或错误响应。

结果表之外必须存在永久的 `firmware_admin_idempotency_tombstones` key-reuse guard：

| 字段 | SQLite 类型 | NULL/默认 | 约束与语义 |
|---|---|---|---|
| `actor_canonical` | TEXT | NOT NULL | 与结果表完全相同的 canonical actor |
| `idempotency_key` | TEXT | NOT NULL | 与结果表完全相同的 canonical UUIDv4 |
| `fingerprint` | TEXT | NOT NULL | 首次成功请求的 64 位小写 hex |
| `action` | TEXT | NOT NULL | 首次请求 action |
| `release_id` | TEXT | NOT NULL | 首次请求 release id |
| `expired_at` | INTEGER | NOT NULL | 原结果 `retained_until`；排他边界已到期 |
| `tombstoned_at` | INTEGER | NOT NULL | tombstone 写入的 epoch 秒 |

该表的 PRIMARY KEY/UNIQUE 为 `(actor_canonical,idempotency_key)`，另建 `INDEX(expired_at)`；只保存 key 身份和冲突判定资料，不保存 response body、URL、token、signature 或 secret。tombstone 永久保留，结果 body 的 86400 秒保存期限与 key 不得复用是两个不同语义。

命中 tombstone 时不得重新进入 pending 或业务副作用：fingerprint 相同返回 `IDEMPOTENCY_RESULT_EXPIRED`，fingerprint 不同返回 `IDEMPOTENCY_CONFLICT`；tombstone 字段或 fingerprint 不一致属于持久化完整性错误，事务 fail closed。

首次请求必须在一个 D1 原子事务内执行：先查 tombstone，再查结果表；只有两者均不存在时才按唯一键插入 `state=pending` 占位 → 执行业务 mutation 或 recovery token 签发 → 写 append-only audit → 写首次 HTTP 200 status/body/requestId/expiry → 更新为 `state=completed` → 提交。任一步失败必须回滚占位、mutation、token 结果和 audit；事务不得提交 pending 行。并发同 actor/key 只有一个事务能取得唯一键，其他请求在首事务提交后读取 completed 结果，在首事务回滚后才可重新竞争，不得产生双重 mutation、token 或 audit。

幂等结果保存期限为首次成功提交后的 86400 秒。所有判断必须在事务开始时读取一次单调一致的 `currentEpochSeconds`：仅 `currentEpochSeconds < retainedUntil` 为有效；`currentEpochSeconds == retainedUntil` 与更晚时刻均已过期。

- 同 key、同 fingerprint 的 disable 重放返回原业务结果和原 `requestId`，`idempotent=true`，不新增 audit。
- 同 key、同 fingerprint 的 recovery-download 仅在 `currentEpochSeconds < original expiresAt` 时返回同一 URL 和原 `requestId`，`idempotent=true`，不得新签 token 或新增 audit。
- 同 key、不同 fingerprint 返回 409 `IDEMPOTENCY_CONFLICT`，不得产生副作用。
- recovery URL 过期，即首次 URL 已满足 `currentEpochSeconds >= original expiresAt`、但幂等记录仍有效时，旧 key 返回 409 `IDEMPOTENCY_RESULT_EXPIRED`，不得返回 URL、重签 token 或新增 audit；调用方必须使用新 key。
- 新 key 在正常鉴权、release/asset 状态和 R2 验证通过后可以签发新 token，并新增一次 `issue_recovery_download` audit。
- 当 `currentEpochSeconds >= retainedUntil` 时，无论结果行是否仍存在，同 fingerprint 都返回 409 `IDEMPOTENCY_RESULT_EXPIRED`，不同 fingerprint 都返回 409 `IDEMPOTENCY_CONFLICT`；处理该边界的事务必须先写入或确认同一 tombstone，禁止利用 24 小时边界把旧 key 原地改造成第二次副作用。客户端必须使用新 key。

Cloudflare Cron 每小时在独立事务中处理 `state=completed AND retained_until <= cleanupEpochSeconds` 的记录：必须先以原 fingerprint/action/release 写入或核对 tombstone，确认成功后才可删除完整结果行；tombstone 永不删除。任一 tombstone 写入/核对失败都回滚该事务并保留完整结果行，不得先删后补。请求事务与清理事务竞争同一 key 时，两者均受同一 `(actor_canonical,idempotency_key)` 唯一约束和事务提交顺序约束；先提交者留下 tombstone，后提交者重读该 tombstone，边界结果始终按 fingerprint 返回上述 409，不得因 Cron 先后改变结果或产生新 mutation/token/audit。append-only audit 永不随幂等记录删除。完整 URL、token、signature 不得进入 audit 或普通日志。

### OTA-XC-HTTP-ADMIN

裁定依据：`OTA-DEC-011`、`OTA-DEC-012`。

P4-3 对外的 firmware admin HTTP 名称固定为现有 `/api/admin/firmware/...` 路由的以下扩展，不得另建同义 endpoint：

| Method | Path | 请求 | 最低角色 |
|---|---|---|---|
| `GET` | `/api/admin/firmware/releases?appId={appId}&deviceModel={deviceModel}` | 无 body；两个 query 都必填 | viewer |
| `GET` | `/api/admin/firmware/channels?appId={appId}&deviceModel={deviceModel}` | 无 body；两个 query 都必填 | viewer |
| `POST` | `/api/admin/firmware/channels/{stable|beta}/publish` | release mutation JSON | stable=owner，beta=publisher |
| `POST` | `/api/admin/firmware/channels/{stable|beta}/retract` | release mutation JSON | stable=owner，beta=publisher |
| `POST` | `/api/admin/firmware/channels/{stable|beta}/stop-latest` | stop mutation JSON | stable=owner，beta=publisher |
| `POST` | `/api/admin/firmware/channels/{stable|beta}/resume-latest` | stop mutation JSON | stable=owner，beta=publisher |
| `POST` | `/api/admin/firmware/channels/{stable|beta}/stop-downloads` | stop mutation JSON | stable=owner，beta=publisher |
| `POST` | `/api/admin/firmware/channels/{stable|beta}/resume-downloads` | stop mutation JSON | stable=owner，beta=publisher |
| `POST` | `/api/admin/firmware/releases/{releaseId}/disable` | release action JSON | owner |
| `POST` | `/api/admin/firmware/releases/{releaseId}/recovery-download` | release action JSON | owner |

所有路由只接受 HTTPS。GET 必须通过 Cloudflare Access 且至少为 viewer；POST 还必须通过允许主体、角色、same-origin 和 CSRF cookie/header 双提交校验，并要求 `Content-Type: application/json`、`Accept: application/json`。可选 `X-Request-Id` 合法时回显，否则服务端生成；响应 header `X-Request-Id` 必须与 JSON `requestId` 相同。`X-Request-Id` 仅用于关联日志和响应，不是 `OTA-XC-ADMIN-IDEMPOTENCY` 的幂等键。`disable` 和 `recovery-download` 还必须携带本合同定义的 `Idempotency-Key`。

publish/retract 的请求 JSON 恰为：

```json
{
  "appId": "trace",
  "deviceModel": "e-track-at32f435",
  "releaseId": "release-id",
  "expectedRevision": 7,
  "reason": "non-empty operator reason"
}
```

stop/resume 的请求 JSON 恰为：

```json
{
  "appId": "trace",
  "deviceModel": "e-track-at32f435",
  "expectedRevision": 7,
  "reason": "non-empty operator reason",
  "maintenanceMessage": "optional message for stop actions"
}
```

disable/recovery-download 的请求 JSON 恰为；path 中的 `releaseId` 是唯一 release 标识，body 不得重复携带：

```json
{
  "appId": "trace",
  "deviceModel": "e-track-at32f435",
  "reason": "non-empty operator reason"
}
```

`reason` trim 后必须非空。`releaseId` 只允许且只要求出现在 publish/retract body；`maintenanceMessage` 只允许出现在两个 stop 请求，resume 必须省略。未知字段、错误 channel、负 revision、path/body 身份不一致或字段类型错误返回 400 `INVALID_PARAMETER`，且不得写 release/channel/audit。

release 列表成功返回 HTTP 200；以下字段全部 required，数组可为空。后续 schema 只能新增可选字段，不得改名、改型或删除这些字段：

```json
{
  "ok": true,
  "requestId": "request-id",
  "firmwareReleases": [
    {
      "releaseId": "release-id",
      "appId": "trace",
      "deviceModel": "e-track-at32f435",
      "versionName": "2.8.1",
      "versionCode": 20801,
      "releaseTag": "mcu-e-track-at32f435-v2.8.1",
      "state": "ready",
      "archived": false,
      "releaseNotes": "text",
      "targetImageSha256": "64-lowercase-hex",
      "publishedChannels": ["stable"],
      "assets": [
        {
          "assetId": "asset-id",
          "kind": "full",
          "fileName": "e-track-at32f435-v2.8.1-full.etu",
          "sha256": "64-lowercase-hex",
          "sizeBytes": 12345,
          "r2State": "available",
          "baseImageSha256": null,
          "baseVersionCode": 0
        }
      ]
    }
  ]
}
```

channel 列表成功返回 HTTP 200；字段同样 required，`currentReleaseId` 和 `maintenanceMessage` 在无 pointer/说明时为 JSON `null`：

```json
{
  "ok": true,
  "requestId": "request-id",
  "firmwareChannels": [
    {
      "channel": "stable",
      "appId": "trace",
      "deviceModel": "e-track-at32f435",
      "currentReleaseId": "release-id",
      "revision": 7,
      "disableLatest": false,
      "disableDownloads": false,
      "maintenanceMessage": null
    }
  ]
}
```

六个 channel mutation 成功均返回 HTTP 200，JSON 恰为同一结果包络：

```json
{
  "ok": true,
  "requestId": "request-id",
  "action": "publish",
  "channel": "stable",
  "revision": 8,
  "currentReleaseId": "release-id",
  "disableLatest": false,
  "disableDownloads": false,
  "maintenanceMessage": null,
  "idempotent": false
}
```

`action` 只允许 `publish`、`retract`、`stop_latest`、`resume_latest`、`stop_downloads`、`resume_downloads`。成功状态必须来自提交后的同一 channel 行；真实 mutation 的 revision 恰加 1。仅同值 stop/resume 可以返回 `idempotent=true` 和未增加的当前 revision，且不得新增成功 audit。其他失败一律使用 `OTA-XC-HTTP-ERROR`，Access 身份无效为 401 `TOKEN_INVALID`/`TOKEN_EXPIRED`，主体、角色、origin、CSRF 分别使用 403 `ACCESS_FORBIDDEN`、`ROLE_FORBIDDEN`、`ORIGIN_FORBIDDEN`、`CSRF_INVALID`，不得继续复用 403 `TOKEN_INVALID`。

release disable 首次成功返回 HTTP 200：

```json
{
  "ok": true,
  "requestId": "request-id",
  "action": "disable_release",
  "releaseId": "release-id",
  "state": "disabled",
  "idempotent": false
}
```

disable 首次成功允许未被 channel 引用且未 archived 的 `draft` 或 `ready` release 原子转为 `disabled`，并在同一批次写 reason/audit/幂等结果。已 disabled 目标的新 key 普通请求返回 410 `RELEASE_DISABLED`；只有 `OTA-XC-ADMIN-IDEMPOTENCY` 识别出的同 key/同 fingerprint 重放可以返回原业务结果并将 `idempotent` 设为 true，不能由相同 reason、requestId 或当前 state 猜测。

recovery-download 成功只签发短期下载能力，不直接把 R2 对象写入 JSON。HTTP 200 响应恰为：

```json
{
  "ok": true,
  "requestId": "request-id",
  "action": "issue_recovery_download",
  "releaseId": "release-id",
  "assetId": "asset-id",
  "kind": "recovery",
  "fileName": "recovery-v2.8.1.bin",
  "sha256": "64-lowercase-hex",
  "sizeBytes": 12345,
  "downloadUrl": "signed-url",
  "expiresAt": 1780000000,
  "idempotent": false
}
```

该操作只接受同 app/deviceModel 的 `ready`、未 archived、未 disabled release，且必须存在恰一 `kind=recovery`、`r2_state=available`、R2 长度/摘要可验证的资产。URL 必须使用 `OTA-XC-HTTP-DOWNLOAD` 的 token v2、`purpose=admin-recovery`、TTL 300 秒，并绑定该 release/asset/kind；v1 recovery 始终拒绝。首次签发动作必须按 `OTA-XC-D1-AUDIT` 记录固定 action、owner、reason、requestId、assetId 和脱敏 before/after。同 key 重放、URL 过期和新 key 重签严格执行 `OTA-XC-ADMIN-IDEMPOTENCY`。

Admin 状态错误映射固定如下，不得使用“合同错误”或按实现方便复用其他状态：

| 操作条件 | HTTP/errorCode |
|---|---|
| release/channel 不存在或 app/deviceModel 不匹配 | 404 `RELEASE_NOT_FOUND` |
| publish/retract/recovery-download 目标为 `draft` | 409 `RELEASE_NOT_READY` |
| 目标 release 为 `disabled` | 410 `RELEASE_DISABLED` |
| 目标 release `archived=1` | 410 `RELEASE_ARCHIVED` |
| publish/retract 所需资产已 archived | 409 `ASSET_ARCHIVED` |
| recovery asset 已 archived | 409 `ASSET_ARCHIVED` |
| recovery 缺失、重复、非 available 或登记的 size/digest 不完整 | 409 `RECOVERY_ASSET_UNAVAILABLE` |
| R2 HEAD/readback 因后端故障无法确认 | 503 `R2_VERIFY_FAILED` |
| disable 目标仍被任一 channel 引用 | 409 `RELEASE_IN_USE` |
| channel `expectedRevision` 不匹配 | 409 `CAS_CONFLICT` |
| 普通 publish 造成 versionCode 回退 | 409 `VERSION_REGRESSION` |
| release action 缺少或非法 `Idempotency-Key` | 400 `INVALID_PARAMETER` |
| 同一 actor/key 的 fingerprint 不同 | 409 `IDEMPOTENCY_CONFLICT` |
| 同 key recovery URL 或 24 小时结果已过期，结果记录或 tombstone 命中 | 409 `IDEMPOTENCY_RESULT_EXPIRED` |

每个非幂等成功 mutation 必须把 release/channel 更新和 audit insert 放在同一 D1 原子批次；响应 `requestId`、适用的 `last_request_id` 和 audit `request_id` 必须相同。鉴权、参数、ready gate、CAS、R2 验证或后端失败不得留下部分状态、download URL 或成功 audit。

### OTA-XC-ADMIN-RETRACT

firmware channel 的旧 `rollback` 动作统一改名为 `retract`/“撤回”。撤回请求必须包含 `releaseId`、`expectedRevision` 和非空 `reason`，目标必须是同 app/deviceModel/channel 可发布的 `ready` release。

- 撤回只原子更新 channel pointer、revision 和 audit，不修改目标/当前 release 的 version、state 或资产。
- 撤回到较低 versionCode 只影响尚未升级设备；已升级设备因 MCU 防降级而得到 `NO_UPDATE`，不得收到降级包。
- UI/API 确认必须写明“已升级设备不会降级；救治方式是发布更高 versionCode 的修复版”。
- stable 撤回要求 owner，beta 沿用 publisher/owner 规则。
- CAS 冲突后调用方重新读取 channel 并要求用户再次确认，不自动重放旧意图。

### OTA-XC-ADMIN-STOP

每个 firmware channel 分别维护 `disable_latest` 和 `disable_downloads`：

- `stop_latest`/`resume_latest` 控制是否签发新的 update metadata/download URL。
- `stop_downloads`/`resume_downloads` 控制资产实际下载；stop 后已签发但尚未使用的 URL 也必须被 Worker 拒绝。
- 每次操作必须携带 `expectedRevision`、非空 `reason`，成功后 revision 恰加 1 并写 audit。
- stop 不改变 channel pointer、release state 或 R2 对象；resume 也不绕过 ready/asset 可用性校验。
- latest 停发返回 `OTA-XC-HTTP-LATEST` 定义的业务结果，download 停发返回 `OTA-XC-HTTP-ERROR` 定义的 503。

## 6. 发布 CLI 与注册 metadata

### OTA-XC-ASSET-NAMING

裁定依据：`OTA-DEC-006`。

正式版本必须匹配 `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)$`。minor 和 patch 范围为 `0..99`，所有段禁止前导零，不允许 prerelease 后缀；按冻结公式生成的 versionCode 必须落入 u32。

正式文件名固定为：

- full：`e-track-at32f435-v{targetVersion}-full.etu`。
- patch：`e-track-at32f435-v{baseVersion}-to-v{targetVersion}-patch.etu`。
- recovery：`recovery-v{targetVersion}.bin`。

deviceModel/role 使用小写，版本数字保持规范版本原样。完整 ASCII 文件名含扩展名最多 128 字节，必须是无路径、无控制字符的 plain file name。patch 的 `baseVersionCode` 必须小于 `targetVersionCode`。

非法名称、长度超限或同一 release 内资产重名返回 `INVALID_PARAMETER`，并且发布链必须在任何 GitHub Release、R2 或 D1 远端写入前失败。相同 canonical metadata 重放必须产生相同文件名，不同资产不得依赖目录上下文区分。

### OTA-XC-RELEASE-CLI

P4-1 必须把现有脚本扩展成一次处理资产数组的确定性链。规范输入：

- 占位头 GCC App bin、版本名、由冻结公式派生的 versionCode、build timestamp。
- 上一正式版最终 App bin 及其版本码/镜像摘要。
- releaseTag、commitSha、canonical provenance runId、release notes、deviceModel、target hardware；首次 production promotion 的 provenance runId 固定为已批准 rehearsal runId。
- `OTA_AES_KEY` secret；不得把 key 放入参数回显、metadata 或 artifact。
- 资产输出目录和 metadata 输出路径。

规范输出：最终 App bin（仅工作流中间产物）、full `.etu`、patch `.etu`、recovery `.bin`、`cloudflare-firmware-release-metadata.json` 和机器可读 verification summary。发布步骤只上传三类正式资产，不把占位头或未验证 candidate 当正式资产。

执行顺序严格引用 `PLAN-OTA.md` §6.1：finalize、full/patch 制包、patch 逐字节自验、recovery 生成、Release 上传、R2 上传/回读、注册。`bspatch` 工具退出码不能单独作为成功依据。

退出码约定：

- `0`：全部要求的本地验证或远端操作成功。
- `2`：缺少/非法 CLI 参数、环境变量或 secret 配置。
- `1`：输入、摘要、制包、自验、上传、回读、注册或幂等冲突失败。

任何失败都不得继续发布后续资产或把 release 标 ready。

### OTA-XC-RELEASE-METADATA

裁定依据：`OTA-DEC-002`、`OTA-DEC-004`、`OTA-DEC-006`、`OTA-DEC-008`、`OTA-DEC-009`。

注册 metadata 使用 `schemaVersion: 2`，顶层包含 release 身份和 `assets` 数组。候选结构：

```json
{
  "schemaVersion": 2,
  "appId": "trace",
  "deviceModel": "e-track-at32f435",
  "releaseTag": "mcu-e-track-at32f435-v2.8.1",
  "runId": "9001",
  "commitSha": "40-hex",
  "versionName": "2.8.1",
  "versionCode": 20801,
  "releaseNotes": "text",
  "targetImageSha256": "64-lowercase-hex",
  "hardwareRevision": 1,
  "layoutId": 1,
  "minBootVersion": 1,
  "minProtocolVersion": 1,
  "targetHardware": "AT32F435RGT7",
  "transport": "ble",
  "minAppVersionCode": 0,
  "isFormalRelease": true,
  "assets": [
    {
      "kind": "full",
      "fileName": "e-track-at32f435-v2.8.1-full.etu",
      "sha256": "64-lowercase-hex",
      "sizeBytes": 12345,
      "baseImageSha256": "",
      "baseVersionCode": 0,
      "githubUrl": "immutable-release-url",
      "r2Key": "immutable-key",
      "r2Verified": true
    }
  ]
}
```

资产数组必须包含恰一 full、恰一 recovery，并在存在可用上一正式版时包含对应 patch。数组按 `kind`、`baseVersionCode`、`fileName` 稳定排序，以便相同输入产生相同 metadata 字节。

`runId` 是 canonical release provenance 的一部分，不是“当前 workflow 执行编号”。rehearsal 首次生成 metadata 时，`runId` 固定为该次已批准 rehearsal 的 GitHub Actions run id；首次 production promotion 必须显式传入并复用同一 `approvedRehearsalRunId`，不得替换为 production 自身 run id。production 当前执行编号只记录为非 canonical 的 `executionRunId` audit 字段，不进入注册 metadata、metadata SHA、release 唯一键或幂等 fingerprint。

跨环境逐字节相等的 canonical metadata 包含上述复用的 `runId`、commit/version/release 字段、三资产名称/SHA/size 和确定性逻辑 `r2Key`/GitHub immutable URL。rehearsal 可以在不创建 GitHub Release 的情况下计算预期 immutable URL；environment binding、bucket 名、Worker/D1 origin、凭据和 `executionRunId` 均不进入 canonical metadata。若任一 canonical 字节变化，必须重新 rehearsal。

`versionName` 必须符合 `OTA-XC-ASSET-NAMING` 的规范版本；`versionCode` 必须为 u32；`minAppVersionCode` 必须位于 `0..2100000000`。metadata builder、register API 和 D1 写入必须在任何远端副作用前拒绝超范围值。`targetImageSha256` 使用最终 `app.bin` raw identity；每个 `asset.sha256` 只表示该文件字节。

### OTA-XC-SCHEMA-FIXTURE

裁定依据：`OTA-DEC-009`。

P4-2 拥有 `schemaVersion=2` 的 versioned schema fixture。fixture 的唯一权威来源是 `OTA-XC-RELEASE-METADATA` 与 `OTA-XC-HTTP-REGISTER`，不得从 P4-1 未完成的实际输出反向定义 schema。

fixture 最低覆盖：完整 full/patch/recovery 注册成功、完全相同 canonical metadata 重放、同 releaseTag 不同 metadata 冲突、非法或未知字段拒绝。fixture 变更必须同时验证 P4-1/P4-2 consumer 并由 OTA 架构审查人复核。

任务方向固定为前置到后置：`P4-2 -> P4-1`、`P4-2 -> P3-5`。P4-2 不依赖 P4-1，P4-1 与 P3-5 之间不建立自动依赖。

- P4-1 必须保留“真实三资产通过 register 后 D1 ready”的完成判据，并消费 P4-2 的真实 schema/API；不得建立临时 register stub 或第二 schema。
- P3-5 必须使用真实 P4-2 register/latest/download 链、R2 readback 和 D1 ready 的受控测试 release；不得手改 D1 或使用任意静态 JSON 冒充真实链。

### OTA-XC-R2-UPLOAD

裁定依据：`OTA-DEC-006`、`OTA-DEC-008`。

P4-1 继续通过 CI uploader 调用 Wrangler/R2 对象写入，不新增 public 上传端点。对下游稳定的是 uploader 的输入、R2 HTTP metadata、机器结果和退出码；Wrangler 的人类可读 stdout 不是合同。

每个 asset 上传输入必须来自 `OTA-XC-RELEASE-METADATA` 同一数组项，并满足：

- full/patch 的 `Content-Type` 为 `application/vnd.e-track.etu`；recovery 的 `Content-Type` 为 `application/octet-stream`。
- `Content-Length` 精确等于 `sizeBytes`，且本地读取字节数必须在产生远端副作用前核对。
- `Content-Digest` 使用与下载相同的 RFC 9530 `sha-256=:<32B digest 的标准 Base64>:` 格式。
- R2 custom metadata `sha256` 保存 64 位小写 hex，`kind` 保存 `full`/`patch`/`recovery`；HTTP digest 与 custom metadata 必须解码到同一 32 字节值。
- `Cache-Control` 只有在 key 不可变规则成立时才为 `public, max-age=31536000, immutable`；`Content-Disposition` 的文件名必须与 metadata `fileName` 一致并完成控制字符转义。

上传器必须先 HEAD：key 不存在时写入；key 已存在且 content length、custom metadata SHA-256 和实际 readback digest 全部一致时不得重写，返回 `ALREADY_PRESENT`；任一身份不同时返回 `R2_OBJECT_CONFLICT`。任何底层 2xx、Wrangler 退出码 0 或 HEAD metadata 都不能单独构成成功，必须完成全字节 readback 摘要和长度核对。

成功时进程退出码为 0，并向 stdout 输出恰一个 `R2AssetUploadResult` JSON object：

```json
{
  "ok": true,
  "status": "UPLOADED",
  "requestId": "request-id",
  "kind": "full",
  "fileName": "e-track-at32f435-v2.8.1-full.etu",
  "r2Key": "trace/firmware/e-track-at32f435/...",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "sizeBytes": 12345,
  "contentDigest": "sha-256=:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=:"
}
```

`status` 只允许 `UPLOADED` 或 `ALREADY_PRESENT`。失败时进程退出码为 1，stderr 输出恰一个 `OTA-XC-HTTP-ERROR` 形状的 JSON object；稳定 `errorCode` 至少包括 `INVALID_PARAMETER`、`R2_OBJECT_CONFLICT`、`R2_VERIFY_FAILED`、`BACKEND_UNAVAILABLE`，并可按该错误合同附 `retryAfter`。失败不得把 `r2Verified=true` 写回 registration metadata。参数或配置缺失仍按 `OTA-XC-RELEASE-CLI` 返回退出码 2。

### OTA-XC-HTTP-REGISTER

裁定依据：`OTA-DEC-002`、`OTA-DEC-004`、`OTA-DEC-006`、`OTA-DEC-008`、`OTA-DEC-009`。

CI 注册入口固定为 `POST /api/ci/firmware/releases`，仅接受 HTTPS：

- `Authorization: Bearer <TRACE_DEPLOY_TOKEN>` 必填且只允许一个 Bearer 凭据；Worker 按 `OTA-XC-SECURITY` 校验派生值。
- `Content-Type: application/json` 和 `Accept: application/json` 必填；可选 `X-Request-Id` 经格式校验后回显，否则 Worker 生成。
- 请求 body 必须完整匹配 `OTA-XC-RELEASE-METADATA` 的 `FirmwareReleaseRegistration`；未知顶层/asset 字段、重复 kind/base、非 formal release、未通过 R2 readback 的 asset 必须在 D1 副作用前拒绝。

首次成功注册必须在 release、assets、ready 转换和 audit 同一原子批次提交后返回 HTTP 201、`Content-Type: application/json` 和 `X-Request-Id`：

```json
{
  "ok": true,
  "requestId": "request-id",
  "releaseId": "release-id",
  "state": "ready",
  "idempotent": false,
  "assetsRegistered": 3
}
```

完全相同 canonical metadata 的重放返回 HTTP 200、同一 `releaseId`、`state=ready`、`idempotent=true` 和实际资产数，不新增 release/asset/channel/audit 业务效果。相同 releaseTag 但 commit、canonical provenance runId 或任一规范化字段不同返回 409 `RELEASE_CONFLICT`；production 自身 `executionRunId` 不得进入该比较。字段非法返回 400 `INVALID_PARAMETER`；Bearer 无效返回 401 `TOKEN_INVALID`；`isFormalRelease` 非 true 返回 403 `FORMAL_RELEASE_REQUIRED`；R2/DB 暂时不可用返回 503 `BACKEND_UNAVAILABLE`。所有失败响应必须使用 `OTA-XC-HTTP-ERROR` JSON 和同一 requestId，且不得留下 ready release、部分 assets 或 channel 改动。

### OTA-XC-RELEASE-GATE

裁定依据：`OTA-DEC-008`。

正式发布 job 必须继续满足：仅 `workflow_dispatch && publish=true` 进入、`firmware-production` environment 审批、`OTA_BOOT_CHAIN_READY` 未精确为 `true` 时首步硬失败且不得静默 skip。

解锁采用两阶段流程：

1. `OTA_BOOT_CHAIN_READY=false` 时，只允许在 GitHub environment `firmware-rehearsal` 使用独立 staging Worker、独立 staging D1 和 R2 bucket `trace-update-staging-releases` 完成三资产、metadata、全字节 readback、register ready/idempotency 演练。
2. rehearsal 不得产生任何 production 副作用，也不得创建 GitHub prerelease。rehearsal environment 不得取得任何 production Worker、D1、R2 或发布凭据。
3. rehearsal 与 production 必须运行同一 workflow、制包工具、schema 和注册客户端代码，只允许通过 environment bindings 切换 Worker、D1、R2 和凭据。
4. required evidence 包含三资产 SHA/size、patch 逐字节自验、recovery 校验、metadata SHA、staging R2 全字节 readback、staging register ready/idempotency，以及 rehearsal 前后 production D1、R2、channel、GitHub Release 快照证明的零副作用。
5. 独立 OTA 架构审查人必须不是该次 rehearsal 的实现作者。repository owner 只能在 reviewer 明确批准后，以人工且可审计方式设置 `OTA_BOOT_CHAIN_READY=true`。
6. 首次解锁后的 production 发布必须绑定已批准 rehearsal 的相同 commit、version 输入和 canonical metadata。production 必须把已批准 rehearsal run id 作为 `approvedRehearsalRunId` 复用到 metadata `runId`；自身 workflow run id 只写非 canonical audit。产生任何远端副作用前必须重新构建，并确认三资产及 metadata 摘要与 rehearsal 完全一致；不一致时硬失败并重新 rehearsal。
7. production dispatch 仍须经过 `firmware-production` environment 的独立审批。

gate 通过后保持 true，普通固件业务代码变化不自动关闭。以下输入发生语义变化时必须先恢复 false 并重新 rehearsal：Boot/OTA 状态机、二进制合同、Flash/layout/linker、finalize/pack/unpack、BLE OTA transport、发布 workflow、资产 schema、注册/下载安全合同、staging/production binding 边界。发生生产发布事故、关键验收撤销、受控工具链变化或无法证明既有证据仍适用时也必须 fail closed 并重新锁定。

禁止临时设置 true、修改 job 条件、使用 staging 凭据访问生产资源，或把失败的 production job 当作 rehearsal 证据。

## 7. BLE transport 与 Flutter 生命周期

### OTA-XC-BLE-LIFECYCLE

二进制帧、命令、ACK、状态码、分段、credit 和 durable 语义只引用 `docs/ota-binary-contracts.md` §5。跨系统生命周期如下：

- MCU 所有者：`USER/HAL/HAL_Bluetooth.cpp` 的 UART demux/调度入口，加独立 OTA transport/session 组件；`Libraries/OTA/ota_staging.*` 继续拥有 durable staging 事实。
- Flutter 所有者：OTA domain service 管理 service/characteristic 绑定、通知解析、发送窗口、重连和 UI 状态；页面不得直接拼帧或保存 session 真相。
- `GET_INFO` 可在空闲态执行且不创建 OTA session。
- BEGIN 成功到 END/ABORT/会话超时为 MCU OTA 活跃期；该期间文本回显、周期 `X-Trace` 和调试透传按冻结合同关闭。
- END 成功只代表 package 完整落盘并通过对应校验；最终升级成功必须等设备重启、重连并重新 `GET_INFO` 确认版本和镜像身份。
- 连接断开不会让 Flutter 猜测 durable 进度；重连后以相同 package 身份重新 BEGIN，并以 MCU 返回的 durable_off/bitmap 为唯一续传依据。

MCU 与 Flutter 都必须有可测试的状态转换日志，但日志不得包含 AES key、deploy token、完整签名 URL 或用户隐私标识。

### OTA-XC-BLE-TUNING

裁定依据：`OTA-DEC-003`。

P3-4 必须在 `115200..921600` 候选波特率中评估同一组 baud/timeout/retry 参数，并选择满足全部门槛的最高稳定档。不得从未来实测结果反向修改以下门槛，也不得从不同参数组合拼接通过结论。

- `referencePackageBytes=1048576`，表示 BLE 实际传输的完整合法 `.etu` `total_len`，不是解包后的 `image_len`。
- P95 完整耗时不超过 120 秒，任一单轮不超过 150 秒。
- `effectiveThroughputKiBps >= 9`。
- 无主动注错 clean run 的 DATA 重传率不高于 1%。丢段、乱序和断连注错按独立恢复判据验收。
- 同一候选参数组合连续 30/30 完整成功，完成 4 小时 soak 且不可恢复错误数为 0，重连恢复 10/10。
- `maxRetries=5`；30 秒无 durable 进展必须中止。
- 硬件 RTS/CTS 引脚接地，任何构型均不得启用 UART 硬件流控。
- 发送窗口不得超过 MCU `INFO.maxWindowSegments` 和冻结 4KB staging 窗口。

计时使用单调高精度时钟，从 BEGIN 首字节开始发送到成功 END ACK 完整到达，包含正常 ACK 等待和重传，不包含 latest 或 HTTP 下载。计时无效或 `elapsedSeconds <= 0` 时该轮无效。

`effectiveThroughputKiBps = referencePackageBytes / 1024 / elapsedSeconds`。不得使用首次发送字节数、UART/GATT 物理字节数或其他口径美化吞吐。

`dataRetransmissionRate = 重传 DATA 帧数 / 完成该包所需的唯一 DATA 段数`。

每个唯一 DATA 段的 ACK 延迟样本从该段首次完整发送结束，到首个由 `durable_off`/bitmap 明确确认该段的有效 ACK 到达。多个段可共享同一 ACK；重复、无推进或非法 ACK 不计样本，重传不创建新样本。同一参数组合的全部 clean run 有效样本合并计算，不得跨 baud、timeout 或 retry 配置混合。

P99 使用 nearest-rank：将 N 个样本升序排列，取第 `ceil(0.99*N)` 个，不插值，也不得删除合法高延迟样本。clean run 最终失败或存在无法确认的 DATA 段时，该轮不能通过成功门槛，也不得删除缺失样本美化 P99。

发送端 timeout 固定由 `clamp(3*P99_ACK, 500ms, 2000ms)` 得出。最终生产 baud/timeout 组合是 P3-4 的实验输出，不是本合同提前指定的固定档位。

### OTA-XC-FLUTTER-TRANSPORT

Flutter transport 必须：

1. 精确绑定 FFF0 服务、FFF2 写入和 FFF1 通知；不得沿用“任取第一个可写/可通知特征”的降级路径处理 OTA。
2. 按协商 MTU 的 `MTU-3` 对完整二进制帧做 GATT 分片；分片边界不是 OTA DATA 段边界。
3. 先订阅上行通知并验证 `GET_INFO`，再开始 latest/download/BEGIN。
4. 以 MCU ACK 为 credit 和 durable 真相；UI 已发送字节不得冒充 durable 进度。
5. 用户取消时发送 ABORT（连接可用时）、停止新写入、清理本地会话；已下载且摘要通过的包是否保留由 UI 明确选择。
6. App 进入后台、蓝牙断开或进程重启时不得继续盲写；恢复后重新发现特征、查询设备并按合同决定续传或重新下载。
7. 未知 ACK 状态、未知 protocolVersion、特征不匹配或摘要不一致均 fail closed。

## 8. 兼容、重试、取消与安全

### OTA-XC-COMPATIBILITY

裁定依据：`OTA-DEC-001`、`OTA-DEC-004`。

HTTP schema v2 和 BLE `proto_ver` 是不同版本域，不得混用。Worker response `schemaVersion=2`；Flutter 接受同 major schema 的新增可选字段，但 required 字段缺失即失败。BLE protocolVersion 不受支持时按二进制合同的协议错误终止。

latest 强制要求 `appVersionCode`，合法范围为 `0..2100000000`。release `minAppVersionCode` 使用相同范围；metadata builder、register API 和 D1 写入必须拒绝范围外值，避免产生任何客户端都无法满足的 release。

确认存在更新后，若 `appVersionCode < minAppVersionCode`，Worker 返回 426 `CLIENT_TOO_OLD` 并执行 `OTA-XC-HTTP-LATEST` 的信息最小化规则。Flutter 必须保持终止状态，不得下载、进入 BLE 或转换为 `NO_UPDATE`。

机型映射与设备兼容是两个独立阶段：`UNKNOWN_DEVICE_MODEL` 只表示 wire/cloud model 无法建立正式映射；映射成功后才允许产生 `HARDWARE_INCOMPATIBLE`、`LAYOUT_INCOMPATIBLE`、`BOOT_TOO_OLD` 或 `PROTOCOL_UNSUPPORTED`。每个错误都必须按 `OTA-XC-HTTP-LATEST` 的固定顺序、信息最小化和 Flutter 终止规则处理。

### OTA-XC-UNKNOWN-FIELDS

- public latest 的未知 query 参数返回 `INVALID_PARAMETER`。
- CI/admin JSON 的未知顶层或资产字段返回 `INVALID_PARAMETER`，防止拼写错误被静默忽略。
- Flutter 必须忽略 response 中未知的可选字段，但未知 `asset.kind`、未知 `errorCode`、未知 schema major 或 required 字段类型错误必须终止。
- D1 migration 不得使用宽松默认值把未知 state/kind 映射为 ready/full。

### OTA-XC-RETRY-POLICY

- metadata 请求每次连接超时 15 秒、响应超时 20 秒；仅网络错误、429 和 503 可自动重试，最多 3 次。
- 429 优先使用合法 `Retry-After`，否则采用 1 秒、2 秒退避；单次等待上限 30 秒。
- CI register 每次超时 30 秒、最多 3 次；只有无 HTTP 响应的网络失败可重试。明确 4xx/409 不得盲重试。
- R2 put/readback 每个操作上限 300 秒、最多 3 次；重试仍须遵守 `OTA-XC-R2-IMMUTABILITY`。
- BLE `maxRetries=5`，发送 timeout 由 `OTA-XC-BLE-TUNING` 的 P99 公式得出；30 秒无 durable 进展必须中止。

### OTA-XC-CANCEL-RECOVERY

取消和失败必须按层归责：

- HTTP 层负责停止请求并隔离未校验文件。
- Flutter BLE 层负责停止发送、尽力 ABORT、保留可解释的最后 ACK 和 package 身份。
- MCU BLE 层负责结束活跃 session、恢复文本通道，并保持已 durable staging 日志符合二进制合同恢复规则。
- MCU package/apply 层继续复用既有 staging、candidate、backup、BCB 状态机；BLE 层不得绕过其完整性和防降级检查。
- App 重启后只有在本地 metadata、文件摘要和设备返回的 package/session 恢复信息全部一致时才允许续传。

### OTA-XC-SECURITY

- CI 注册使用 `TRACE_DEPLOY_TOKEN`，Worker 只存/比较其派生校验值；admin 使用 Access 身份和角色授权。
- public download URL 使用有时限的 HMAC token 和 key version；过期/签名错误均返回 401。
- recovery 下载能力只能由通过 Access、owner 角色、same-origin、CSRF 和 non-empty reason 校验的 admin 请求签发；`purpose=admin-recovery` token 不得由 latest、CI register 或普通 publisher 取得。
- `OTA_AES_KEY` 只存在于受审批的 Actions secret 和 MCU 对应编译期 key 管理，不得进入日志、artifact、metadata、D1 或 GitHub Release notes。
- R2 和 GitHub URL 必须绑定不可变 releaseTag/文件名，禁止 `/latest/download/`。
- 所有 size、整数范围、文件名、路径段、SHA-256、URL host、R2 key 和枚举值在产生副作用前校验。
- v1 的 SHA-256、CRC 和 AES-CTR 提供损坏检测/保密，不提供固件发布者数字签名。下载 URL 签名也不等于固件内容签名。

### OTA-XC-SECRETS

P4-4 配置面：

| 名称 | 类型 | 使用方 | 规则 |
|---|---|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | GitHub secret | Wrangler/R2 | 必填，不输出 |
| `CLOUDFLARE_API_TOKEN` | GitHub secret | Wrangler/R2 | 最小权限，必填，不输出 |
| `TRACE_UPDATE_SERVICE_URL` | GitHub secret | register client | HTTPS origin，不含 token |
| `TRACE_DEPLOY_TOKEN` | GitHub secret | register client | Bearer，日志脱敏 |
| `OTA_AES_KEY` | GitHub secret | `Tools/etu_pack.py` | 32 hex；正式链缺失必须硬失败，禁止开发示例 key |
| `TRACE_R2_BUCKET` | GitHub variable | uploader | production 明确生产 bucket；rehearsal 固定 `trace-update-staging-releases`，不得共享凭据 |
| `OTA_BOOT_CHAIN_READY` | GitHub variable | release gate | 仅精确 `true` 解锁；时序见 `OTA-XC-RELEASE-GATE` |
| `firmware-rehearsal` | GitHub environment | rehearsal job | 独立 staging Worker/D1/R2 bindings，无 production 凭据，不允许 production 副作用 |
| `firmware-production` | GitHub environment | release job | 至少一名独立审批人，job 必须声明 environment |

Worker 侧 `DEPLOY_TOKEN_SHA256`、download HMAC current/previous key 及 key version 继续按现有 Worker secret 管理；P4-4 验收不得读取或打印 secret 明文。

## 9. 规范性测试向量

### OTA-XC-TEST-VECTORS

以下是跨系统规范向量，不替代 `tests/ota-vectors/` 的二进制 golden vectors。

| 向量 | 输入 | 预期 |
|---|---|---|
| `XC-LATEST-PATCH` | current vcode 20800；current image hash=`11`×32；ready target 20801；唯一 patch base=`11`×32；full 可用 | HTTP 200，`updateAvailable=true`，kind=`patch` |
| `XC-LATEST-FULL-FALLBACK` | 与上相同，但 patch base=`22`×32 | HTTP 200，返回 kind=`full` |
| `XC-LATEST-NO-UPDATE` | current vcode 20801；target vcode 20801 | HTTP 200，`NO_UPDATE`，无 downloadUrl |
| `XC-LATEST-RECOVERY-HIDDEN` | ready release 仅 recovery+full 可用 | latest 只可返回 full，不得返回 recovery |
| `XC-D1-DUP-FULL` | 同 release 插入第二条 full，base 哨兵均空串 | 实际 SQL 约束拒绝 |
| `XC-D1-DUP-PATCH` | 同 release、同 base hash 插入第二条 patch | 实际 SQL 约束拒绝 |
| `XC-D1-NO-FULL-READY` | draft 只有 patch/recovery | ready 原子门槛拒绝且 channel 不变 |
| `XC-R2-COLLISION` | 同 key 已存在但 digest 不同 | 上传/注册硬失败，不覆盖 |
| `XC-R2-DIGEST-ENCODING` | SHA-256 原始 32B 全为 `00` | metadata/custom metadata 为 64 个 `0`；`Content-Digest` 精确为 `sha-256=:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=:` |
| `XC-REGISTER-IDEMPOTENT` | 相同 releaseTag/commit/run/metadata 重放 | 200，`idempotent=true`，行数不增 |
| `XC-REGISTER-CONFLICT` | 相同 releaseTag，不同 commit 或资产摘要 | 409，无部分写入 |
| `XC-ADMIN-RETRACT` | stable 从 20801 指回 ready 20800，reason 非空、revision 匹配 | channel revision +1；已升级设备不执行降级 |
| `XC-ADMIN-CAS-AUDIT` | expectedRevision 过期或 audit insert 失败 | 409 或事务失败；pointer/revision/audit 均不发生部分变化 |
| `XC-ADMIN-RECOVERY-DOWNLOAD` | owner 对 ready、未 archived release 的唯一 available recovery 首次提交 reason | 200；返回 `purpose=admin-recovery` 的限时 URL 和匹配的 asset hash/size；按固定映射写一条签发 audit |
| `XC-ADMIN-RECOVERY-REJECT` | release 为 draft/disabled/archived，或 recovery 缺失、重复、archived、非 available | 分别返回合同固定的 409/410 errorCode；不得返回 URL 或写成功 audit |
| `XC-ADMIN-DISABLE` | owner disable 未被 channel 引用的 ready release，reason 非空 | 200 `disable_release`；state 原子转 disabled；audit 同批次提交 |
| `XC-ADMIN-DISABLE-IN-USE` | disable 目标仍被 stable/beta 引用 | 409 `RELEASE_IN_USE`；release/channel/audit 均不变 |
| `XC-UNKNOWN-QUERY` | latest 带未声明参数 | 400 `INVALID_PARAMETER` |
| `XC-DOWNLOAD-DIGEST` | 文件任一字节变异 | Flutter 整文件摘要失败，不进入 BLE |
| `XC-INFO-MODEL-VALID` | `INFO.model` 精确为 8B `E-Track\0` | Flutter 映射为 `e-track-at32f435` |
| `XC-INFO-MODEL-UNKNOWN` | 其他 ASCIIZ 或非法 model | Flutter 本地 `UNKNOWN_DEVICE_MODEL`，不请求 latest |
| `XC-LATEST-MODEL-UNKNOWN` | latest 的 deviceModel 未注册 | HTTP 400 `UNKNOWN_DEVICE_MODEL`；不加载 channel，无 URL |
| `XC-LATEST-DEVICE-COMPAT` | 映射已成功；依次令 hardware、layout、Boot、protocol 中恰一项不兼容 | 按固定阶段分别返回 409 `HARDWARE_INCOMPATIBLE`、`LAYOUT_INCOMPATIBLE`、`BOOT_TOO_OLD`、`PROTOCOL_UNSUPPORTED`；均无资产/URL |
| `XC-INFO-IMAGE-MISSING` | INFO hash 缺失、长度错误或无法计算 | Flutter fail closed，不得以 full 绕过 |
| `XC-DIGEST-DOMAINS` | 同一 finalized app.bin 同时计算 raw SHA、fw_header 双零 SHA、各自 SHA8；另计算 .etu package SHA，并保留 raw SHA8 与 header SHA8 不同的断言 | INFO/latest/D1 使用 raw 32B；`.etu base_sha8` 使用 raw 前 8B；ETSL/candidateImageSha8 使用 fw_header 双零摘要前 8B；ETRJ 只用 package SHA；任何域交叉替代均失败 |
| `XC-LATEST-APP-INVALID` | `appVersionCode` 缺失、非整数、负数或大于 2100000000 | 400 `INVALID_PARAMETER`，无 URL |
| `XC-LATEST-APP-TOO-OLD` | 存在更新且 appVersionCode 小于 minAppVersionCode | 426 `CLIENT_TOO_OLD`；包含门槛，不含资产/签名/URL |
| `XC-RANGE-RESUME` | sidecar 身份一致、N<size、If-Range 匹配 | 206，完整 Range headers；组装后重算整文件 SHA |
| `XC-RANGE-IF-RANGE-MISS` | `If-Range` 不匹配，服务器返回 200 | Flutter 先截断 partial，禁止追加 |
| `XC-RANGE-AT-END` | `Range: bytes=N-` 且 N>=sizeBytes | 416；Flutter 删除 partial 并重新 latest |
| `XC-RANGE-COMPLETE-PART` | localPartSize=sizeBytes | 不发 Range；整文件 SHA 通过则原子完成 |
| `XC-RANGE-STALE-PART` | sidecar 任一身份变化或超过 24h | 删除 `.part` 和 sidecar，不续传 |
| `XC-ASSET-NAME-FULL` | targetVersion=2.8.1 | `e-track-at32f435-v2.8.1-full.etu` |
| `XC-ASSET-NAME-PATCH` | base=2.8.0，target=2.8.1 | `e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu` |
| `XC-ASSET-NAME-INVALID` | 前导零、prerelease、minor/patch>99、重名或名称>128B | 远端副作用前 `INVALID_PARAMETER` |
| `XC-MIGRATION-VERIFIED` | schemaVersion=1 manifest 字段齐全且 artifact 验证一致 | 可按 channel/state 规则映射 v2，重复执行不增行 |
| `XC-MIGRATION-LEGACY` | 缺 manifest、字段、artifact 或验证失败 | legacy 隔离；不得 ready/latest/patch base/recovery URL |
| `XC-RETENTION-PROTECTED` | release 排名前 10、年龄<365d 或存在任一受保护引用 | 不进入清理候选 |
| `XC-RETENTION-CLEANER-BOUNDARY` | 同时超出 N/T 且无引用 | cleaner 只输出逐资产不可变 candidate manifest；archived/R2/D1/GitHub 均不变 |
| `XC-RETENTION-DELETE` | candidate manifest 身份匹配、隔离前双人批准、archived 满 30d、引用重查通过、最终 manifest 再次双人批准 | 受控执行器只删除 manifest 精确列出的 R2 对象，D1 资产转 `r2_deleted`，D1/audit/GitHub 保留 |
| `XC-RETENTION-RECOVERY-WILDCARD` | 普通 cleaner 包含 recovery，或 recovery manifest 使用空列表/通配符/整 release | fail closed；无 archived、删除或状态副作用 |
| `XC-ADMIN-IDEMPOTENT-REPLAY` | 同 actor/key/fingerprint，首次结果仍在 24h；recovery URL 未过期 | 返回原 requestId/业务结果，`idempotent=true`，无新 token/audit |
| `XC-ADMIN-IDEMPOTENT-CONFLICT` | 同 actor/key、不同 fingerprint | 409 `IDEMPOTENCY_CONFLICT`，无副作用 |
| `XC-ADMIN-IDEMPOTENT-URL-EXPIRED` | 同 key/fingerprint，原 recovery URL 已到排他截止但记录未到 24h | 409 `IDEMPOTENCY_RESULT_EXPIRED`；新 key 才可重签和新增 audit |
| `XC-ADMIN-IDEMPOTENT-CONCURRENT` | 20 个同 actor/key/fingerprint 请求并发首次到达 | 恰一 completed D1 行、一次 mutation/token、一次 audit；20 个调用得到同 requestId/业务结果 |
| `XC-ADMIN-IDEMPOTENT-BOUNDARY` | 已有 completed result：created=1800000000，retainedUntil=1800086400；分别在 1800000000、1800086399 和 1800086400 请求 | 前两者按有效窗口重放；后者先写/确认 tombstone，再返回 409 `IDEMPOTENCY_RESULT_EXPIRED`，均无新副作用 |
| `XC-ADMIN-IDEMPOTENT-EXPIRED-CONFLICT` | now>=retainedUntil，结果行存在或已由 Cron 清理；分别使用同 fingerprint 和不同 fingerprint | 不论清理先后，同 fingerprint 为 `IDEMPOTENCY_RESULT_EXPIRED`；不同 fingerprint 为 `IDEMPOTENCY_CONFLICT` |
| `XC-ADMIN-IDEMPOTENT-TOMBSTONE-RACE` | 同一过期 key 分别让请求事务先提交、Cron 先提交，以及两者并发 | 三种调度都只留下一个相同 tombstone；无第二次 mutation/token/audit，响应按 fingerprint 稳定为上述 409 |
| `XC-TOKEN-V2-CANONICAL` | 使用下方固定 key、精确 query 和 LF canonical UTF-8 字节 | signature 精确为 `DmjZ33S6hz_9jrbUtdv_BqGNvOY4GCjNJqIcBpvZuzU` |
| `XC-TOKEN-V2-UNKNOWN` | v2 query 缺失、重复、空值或出现未知参数 | `TOKEN_INVALID` |
| `XC-TOKEN-EXPIRY` | `currentEpochSeconds == expiresAt` | 401 `TOKEN_EXPIRED` |
| `XC-TOKEN-V1-PUBLIC-WINDOW` | v1 full/patch，expiresAt<=cutover+300，当前时间同时早于两个截止 | 有界接受；signer 不再生成 v1 |
| `XC-TOKEN-V1-RECOVERY` | 任意 v1 recovery 请求 | 始终拒绝 |
| `XC-TOKEN-V1-CUTOFF` | `currentEpochSeconds >= v2CutoverEpoch+300` | 运行时立即拒绝全部 v1 |
| `XC-BLE-THROUGHPUT` | 1MiB 合法 `.etu`，BEGIN 首字节至 END ACK 单调计时 | 按固定公式计算且至少 9KiB/s；P95/单轮满足 120/150s |
| `XC-BLE-P99` | 同一参数组合 clean-run ACK 样本 | nearest-rank P99；timeout=`clamp(3*P99,500ms,2000ms)` |
| `XC-RELEASE-REHEARSAL` | 使用下方固定 commit/version/runId/三资产/metadata digest；rehearsal executionRunId=9001，production executionRunId=9002 | 两阶段 canonical metadata SHA 均为固定值，staging readback 三项匹配，四类 production 快照前后相等，reviewer/owner gate 合法；任一语义回归使 gate=false |

#### XC-TOKEN-V2-GOLDEN

- 非生产测试 key：`keyVersion=7`，key bytes hex = `000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f`。
- 精确 query：`tokenVersion=2&assetId=asset-patch-20801&releaseId=release-20801&kind=patch&purpose=public-ota&expiresAt=1800000300&keyVersion=7&signature=DmjZ33S6hz_9jrbUtdv_BqGNvOY4GCjNJqIcBpvZuzU`。
- HMAC 输入是以下 67 个 UTF-8 字节；行间为单个 LF，最后一行 `7` 后无 LF：

```text
2
GET
asset-patch-20801
release-20801
patch
public-ota
1800000300
7
```

- 预期 HMAC-SHA256 hex：`0e68d9df74ba873ffd8eb6d4b5dbff06a18dbce6381828cd26a21c069bd9bb35`。
- 预期 Base64URL 无 padding：`DmjZ33S6hz_9jrbUtdv_BqGNvOY4GCjNJqIcBpvZuzU`。

#### XC-RELEASE-REHEARSAL-GOLDEN

- canonical provenance `runId=9001`；rehearsal `executionRunId=9001`，production `executionRunId=9002`，后者不进入 metadata。
- `commitSha=0123456789abcdef0123456789abcdef01234567`，`versionName=2.8.1`，`versionCode=20801`，`targetImageSha256` 为 64 个 `4`。
- 其余顶层值固定为 `schemaVersion=2`、`appId=trace`、`deviceModel=e-track-at32f435`、`releaseTag=mcu-e-track-at32f435-v2.8.1`、`releaseNotes=vector`、`hardwareRevision=1`、`layoutId=1`、`minBootVersion=1`、`minProtocolVersion=1`、`targetHardware=AT32F435RGT7`、`transport=ble`、`minAppVersionCode=0`、`isFormalRelease=true`。
- full：size `1048576`、SHA 为 64 个 `1`、`baseImageSha256=""`、`baseVersionCode=0`；patch：size `524288`、SHA 为 64 个 `2`、base SHA 为 64 个 `5`、`baseVersionCode=20800`；recovery：size `1048584`、SHA 为 64 个 `3`、`baseImageSha256=""`、`baseVersionCode=0`。文件名和逻辑 R2 key 按 `OTA-XC-ASSET-NAMING` 与 `OTA-XC-R2-IMMUTABILITY` 生成。
- full/patch/recovery 的 `githubUrl` 分别为 `https://example.invalid/releases/mcu-e-track-at32f435-v2.8.1/e-track-at32f435-v2.8.1-full.etu`、`https://example.invalid/releases/mcu-e-track-at32f435-v2.8.1/e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu`、`https://example.invalid/releases/mcu-e-track-at32f435-v2.8.1/recovery-v2.8.1.bin`。
- full/patch/recovery 的 `r2Key` 分别为 `trace/firmware/e-track-at32f435/20801/e-track-at32f435-v2.8.1-full.etu`、`trace/firmware/e-track-at32f435/20801/e-track-at32f435-v2.8.0-to-v2.8.1-patch.etu`、`trace/firmware/e-track-at32f435/20801/recovery-v2.8.1.bin`；三项 `r2Verified=true`。
- 按 `OTA-XC-RELEASE-METADATA` 字段顺序和稳定资产排序生成的 canonical metadata 长度为 `1800` UTF-8 字节，SHA-256 精确为 `47d2ee8057313e5e556dc5d41159cb2e51bf766cf8b526de8bb30a3b5096fd85`；rehearsal 与 production 必须逐字节相同。
- staging R2 全字节 readback 必须分别得到上述三组 size/SHA。production D1、R2、channel 和 GitHub Release 的 vector 快照均为 canonical JSON `[]`，前后 SHA-256 都精确为 `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`。
- implementer=`implementer@example.invalid`、reviewer=`reviewer@example.invalid`、gateSetter=`owner@example.invalid`，三者中 reviewer 不得等于 implementer；缺 reviewer 明确批准时 gate 保持 false，合法批准后 owner 才可置 true。任一受治理输入语义变化后预期 gate 立即恢复 false。

以上向量属于 `FROZEN` 合同的一部分；它们授权未来实现和验收按固定输入复算，但不构成 P5 通过或生产部署证据。

## 10. 非规范性实现入口

以下仅用于定位现有组件，不改变前述合同：

- MCU：`USER/HAL/HAL_Bluetooth.cpp`、`Libraries/Bluetooth/`、`Libraries/OTA/ota_staging.*`、`USER/App/Utils/OtaUpdate/`。
- Flutter：`app/bluetooth_flutter_Trace/lib/services/ota_service.dart`、`app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart`、`app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart`、`app/bluetooth_flutter_Trace/lib/config/share_links.dart`。
- Worker/D1/admin：`app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/firmware.ts`、`app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/errors.ts`、`app/bluetooth_flutter_Trace/cloudflare/update-service/migrations/0003_firmware_releases.sql`、`app/bluetooth_flutter_Trace/cloudflare/update-service/admin/functions/api/admin/[[path]].ts`、`app/bluetooth_flutter_Trace/cloudflare/update-service/admin/public/index.html`。
- 发布：`.github/workflows/firmware-build.yml`、`Tools/etu_pack.py`、`app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/build-firmware-release-metadata.mjs`、`app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs`、`app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs`。

当前源码仍是单资产/candidate 模型、Flutter BLE 传输尚未实现、MCU 仍有文本回显与 512B RX 缓冲。这些是实现缺口，不是修改本合同去迁就源码的理由。
